"""Graph-token LM for the LLM layer (C6), HyperG-style (round 38).

A frozen causal LM (default Qwen3-8B) + LoRA on q/k/v (r=8, alpha=32, dropout 0.1, as in
HyperG) + a 2-layer projector that maps HGFM node / hyperedge states (d=192, plus a 2-dim
node/edge type flag) to the LM hidden size. Each "<graph>" placeholder token in the prompt
has its input embedding replaced by the projected graph vector (GraphGPT / LLaGA / HyperG).
"""
import torch, torch.nn as nn

GRAPH_TOKEN = "<graph>"


class GraphTokenLM(nn.Module):
    def __init__(self, lm_name, d_graph=192, lora_r=8, lora_alpha=32, lora_dropout=0.1, dtype=torch.bfloat16, use_graph=True, ckpt=None):
        super().__init__()
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import LoraConfig, get_peft_model
        self.tok = AutoTokenizer.from_pretrained(f"{ckpt}/lora" if ckpt else lm_name)
        if self.tok.pad_token is None: self.tok.pad_token = self.tok.eos_token
        self.tok.add_special_tokens({"additional_special_tokens": [GRAPH_TOKEN]})
        self.graph_id = self.tok.convert_tokens_to_ids(GRAPH_TOKEN)
        import transformers
        # transformers >= 4.56 renamed torch_dtype -> dtype; older versions would silently ignore `dtype` and load fp32
        kw = {"dtype": dtype} if tuple(int(x) for x in transformers.__version__.split(".")[:2]) >= (4, 56) else {"torch_dtype": dtype}
        lm = AutoModelForCausalLM.from_pretrained(lm_name, **kw)
        lm.resize_token_embeddings(len(self.tok))
        targets = [n for n in ("q_proj", "k_proj", "v_proj") if any(n in k for k, _ in lm.named_modules())] or ["c_attn"]
        if ckpt:   # trained adapter + projector (eval)
            from peft import PeftModel
            self.lm = PeftModel.from_pretrained(lm, f"{ckpt}/lora")
        else:
            self.lm = get_peft_model(lm, LoraConfig(r=lora_r, lora_alpha=lora_alpha, lora_dropout=lora_dropout, target_modules=targets, task_type="CAUSAL_LM"))
        hid = lm.config.hidden_size
        self.use_graph = use_graph
        self.proj = nn.Sequential(nn.Linear(d_graph + 2, hid), nn.ReLU(), nn.Linear(hid, hid)).to(dtype)
        if ckpt: self.proj.load_state_dict(torch.load(f"{ckpt}/projector.pt"))

    def embed(self, input_ids, graph_vecs):
        emb = self.lm.get_input_embeddings()(input_ids)
        if self.use_graph and graph_vecs is not None and graph_vecs.numel():
            mask = input_ids == self.graph_id
            n = int(mask.sum())
            g = self.proj(graph_vecs[:n].to(emb.dtype))
            emb = emb.clone(); emb[mask] = g
        return emb

    def hidden(self, input_ids, attention_mask, graph_vecs=None):
        base = self.lm.get_base_model()   # LoRA layers are injected in place
        return base.model(inputs_embeds=self.embed(input_ids, graph_vecs), attention_mask=attention_mask).last_hidden_state

    def forward(self, input_ids, attention_mask, graph_vecs=None, labels=None):
        """Logits only where needed (vocab ~150k makes full-sequence logits the memory peak):
        with labels -> mean CE over answer tokens; without -> logits of the last position."""
        h = self.hidden(input_ids, attention_mask, graph_vecs); head = self.lm.get_base_model().lm_head
        if labels is None:
            last = attention_mask.sum(1) - 1
            return head(h[torch.arange(h.shape[0], device=h.device), last]).float()
        tgt = labels[:, 1:]; sel = tgt != -100
        logits = head(h[:, :-1][sel]).float()
        return torch.nn.functional.cross_entropy(logits, tgt[sel])

    def trainable_parameters(self):
        return [p for p in self.lm.parameters() if p.requires_grad] + list(self.proj.parameters())


def graph_vectors(sample, tokens):
    """Stack the vectors referenced by sample['graph_refs'] in placeholder order."""
    t = tokens[sample["run_id"]]; out = []
    for kind, i in sample["graph_refs"]:
        v = (t["h"][i] if kind == "node" else t["m"][i]).float()
        flag = torch.tensor([1.0, 0.0]) if kind == "node" else torch.tensor([0.0, 1.0])
        out.append(torch.cat([v, flag]))
    return torch.stack(out) if out else torch.zeros(0, tokens[sample["run_id"]]["h"].shape[1] + 2)
