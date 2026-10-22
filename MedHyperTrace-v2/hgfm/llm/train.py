"""Stage 3: LoRA + projector training of the graph-token LM (round 38).

Loss = next-token cross-entropy on the answer tokens only ("yes"/"no").
Usage (one GPU per fold):
  python -m hgfm.llm.train --lm Qwen/Qwen3-8B --data <fold>/sft/train.jsonl --tokens <fold>/graph_tokens.pt --out <fold>/ckpt
         [--no_graph] [--epochs 1] [--bs 4] [--accum 4] [--lr 1e-4] [--proj_lr 1e-3] [--max_len 2048] [--limit N] [--device cuda]
"""
import argparse, json, os, random, time
import torch
from hgfm.llm.model import GraphTokenLM, graph_vectors


def encode(model, s, max_len, with_answer=True):
    msgs = [{"role": "system", "content": s["system"]}, {"role": "user", "content": s["user"]}]
    prompt = model.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, **({"enable_thinking": False} if "qwen3" in model.tok.name_or_path.lower() else {}))
    p_ids = model.tok(prompt, add_special_tokens=False)["input_ids"]
    a_ids = model.tok(s["answer"] + model.tok.eos_token, add_special_tokens=False)["input_ids"] if with_answer else []
    if len(p_ids) + len(a_ids) > max_len:   # keep the end (target + question about it), drop the head of the prompt
        p_ids = p_ids[-(max_len - len(a_ids)):]
    return p_ids, a_ids


def batches(model, data, tokens, bs, max_len, device):
    for b in range(0, len(data), bs):
        part = data[b:b + bs]; seqs, labs, gv = [], [], []
        for s in part:
            p, a = encode(model, s, max_len); seqs.append(p + a); labs.append([-100] * len(p) + a)
            g = graph_vectors(s, tokens)
            n_ph = sum(1 for t in p if t == model.graph_id)
            gv.append(g[-n_ph:] if n_ph else g[:0])  # placeholders cut by truncation drop their oldest vectors
        L = max(map(len, seqs)); pad = model.tok.pad_token_id
        ids = torch.tensor([x + [pad] * (L - len(x)) for x in seqs]); lab = torch.tensor([x + [-100] * (L - len(x)) for x in labs])
        att = torch.tensor([[1] * len(x) + [0] * (L - len(x)) for x in seqs])
        yield ids.to(device), att.to(device), (torch.cat(gv).to(device) if gv else None), lab.to(device)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lm", default="Qwen/Qwen3-8B"); ap.add_argument("--data"); ap.add_argument("--tokens"); ap.add_argument("--out")
    ap.add_argument("--no_graph", action="store_true"); ap.add_argument("--epochs", type=int, default=1); ap.add_argument("--bs", type=int, default=4)
    ap.add_argument("--accum", type=int, default=4); ap.add_argument("--lr", type=float, default=1e-4); ap.add_argument("--proj_lr", type=float, default=1e-3)
    ap.add_argument("--max_len", type=int, default=2048); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--dtype", default="bf16"); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--grad_ckpt", action="store_true")
    a = ap.parse_args(); random.seed(a.seed); torch.manual_seed(a.seed); os.makedirs(a.out, exist_ok=True)
    dtype = {"bf16": torch.bfloat16, "fp32": torch.float32}[a.dtype]
    model = GraphTokenLM(a.lm, dtype=dtype, use_graph=not a.no_graph).to(a.device)
    tokens = torch.load(a.tokens); data = [json.loads(l) for l in open(a.data)]
    if a.limit: data = data[: a.limit]
    if a.grad_ckpt: model.lm.get_base_model().gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False}); model.lm.get_base_model().enable_input_require_grads()
    opt = torch.optim.AdamW([{"params": [p for p in model.lm.parameters() if p.requires_grad], "lr": a.lr},
                             {"params": model.proj.parameters(), "lr": a.proj_lr}], weight_decay=0.0)
    step, t0 = 0, time.time(); model.train()
    cuda = a.device.startswith("cuda") and torch.cuda.is_available()
    if cuda: torch.cuda.reset_peak_memory_stats()
    n_tok = n_slot = 0; t_steady = None; tok_steady = 0   # throughput: real tokens and padded slots; steady = after 5 optimizer steps
    for ep in range(a.epochs):
        random.shuffle(data)
        for k, (ids, att, gv, lab) in enumerate(batches(model, data, tokens, a.bs, a.max_len, a.device)):
            loss = model(ids, att, gv, lab) / a.accum; loss.backward()
            n_tok += int(att.sum()); n_slot += att.numel()
            if t_steady is not None: tok_steady += int(att.sum())
            if (k + 1) % a.accum == 0:
                torch.nn.utils.clip_grad_norm_(model.trainable_parameters(), 1.0); opt.step(); opt.zero_grad(); step += 1
                if step == 5:
                    if cuda: torch.cuda.synchronize()
                    t_steady = time.time()
                if step % 20 == 0 or step == 1:
                    mem = f" peak_alloc {torch.cuda.max_memory_allocated() / 2**30:.1f}G peak_reserved {torch.cuda.max_memory_reserved() / 2**30:.1f}G" if cuda else ""
                    rate = f" tok/s {tok_steady / (time.time() - t_steady):.0f}" if t_steady and time.time() > t_steady else ""
                    print(f"ep {ep} step {step} loss {loss.item() * a.accum:.4f} {time.time() - t0:.0f}s{rate}{mem}", flush=True)
    if cuda: torch.cuda.synchronize()
    stats = {"seconds": time.time() - t0, "optimizer_steps": step, "tokens": n_tok, "padded_slots": n_slot,
             "steady_tok_per_s": (tok_steady / (time.time() - t_steady)) if t_steady else None,
             "peak_alloc_gb": torch.cuda.max_memory_allocated() / 2**30 if cuda else None,
             "peak_reserved_gb": torch.cuda.max_memory_reserved() / 2**30 if cuda else None,
             "gpu": torch.cuda.get_device_name() if cuda else None}
    json.dump(stats, open(os.path.join(a.out, "train_stats.json"), "w"), indent=1); print("STATS", json.dumps(stats), flush=True)
    model.lm.save_pretrained(os.path.join(a.out, "lora"), save_embedding_layers=False); torch.save(model.proj.state_dict(), os.path.join(a.out, "projector.pt"))
    model.tok.save_pretrained(os.path.join(a.out, "lora"))
    json.dump(vars(a), open(os.path.join(a.out, "train_args.json"), "w"), indent=1); print("saved", a.out)


if __name__ == "__main__":
    main()
