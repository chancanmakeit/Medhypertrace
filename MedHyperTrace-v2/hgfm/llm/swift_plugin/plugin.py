"""MS-Swift (ms-swift 4.6.x) plugin for the graph-token LM of hgfm/llm (GraphTokenLM, model.py / train.py).

Load with `swift sft --external_plugins MedHyperTrace-v2/hgfm/llm/swift_plugin/plugin.py ...`. It registers

  model_type `graph_token_lm`  GraphTokenLoader: the base causal LM (e.g. Qwen3-8B) + tokenizer with the extra special
                               token "<graph>" (embeddings resized to len(tokenizer), exactly as GraphTokenLM) + a
                               projector `graph_proj` = Linear(d_graph+2, H) -> ReLU -> Linear(H, H) attached to the LM.
  template   `graph_token`     GraphTokenTemplate: prompt = tokenizer.apply_chat_template([system, user],
                               add_generation_prompt=True, enable_thinking=False), answer = "yes"/"no" + eos, loss only on
                               the answer; head truncation to max_length and dropping of the oldest graph vectors, exactly
                               as train.encode/batches. The collator adds `graph_vecs` [B, G, d_graph+2] (zero padded)
                               and `graph_counts` [B]; `_post_encode` (swift's pre-forward hook) replaces every <graph>
                               input embedding by graph_proj(vector) and feeds `inputs_embeds` to the LM.
  tuner_type `graph_lora`      PEFT LoRA (r/alpha/dropout/target_modules from --lora_rank/--lora_alpha/--lora_dropout/
                               --target_modules) + trainable projector. Checkpoints = standard PEFT adapter files +
                               `projector.pt` (same state-dict keys as GraphTokenLM.proj) + `graph_token_meta.json`.
  optimizer  `graph_token`     AdamW with two groups: LoRA at --learning_rate, projector at --aligner_lr (as train.py:
                               --lr 1e-4 / --proj_lr 1e-3).

The text variant (sft_text, --no_graph in train.py) uses the SAME model_type / template / tuner / optimizer: its rows
have no <graph> placeholders and no graph_refs, so the collator adds no graph tensors and the hook is the identity
(the projector exists but receives no gradient, as in GraphTokenLM with use_graph=False).

Environment variables (read lazily, so they also reach dataloader workers):
  MHT_GRAPH_TOKENS   path of graph_tokens.pt (required only when a row has graph_refs)
  MHT_D_GRAPH        encoder width d_graph (default 192; projector input = d_graph + 2)
  MHT_PROJ_INIT      optional projector.pt to initialise graph_proj (round 64, SAMT); unset = random init as before
Data: convert build_sft output with swift_plugin/prepare_data.py (messages + run_id + graph_refs as a JSON string).
"""
import json
import os
import sys
from typing import Any, Dict, List, Optional

import torch
import torch.nn as nn

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..', '..'))   # .../MedHyperTrace-v2
if _V2_ROOT not in sys.path:
    sys.path.insert(0, _V2_ROOT)
from hgfm.llm.model import GRAPH_TOKEN, graph_vectors  # noqa: E402  (single source of truth for the vector layout)

from swift.dataset.preprocessor.core import RowPreprocessor  # noqa: E402
from swift.model import ModelMeta, register_model  # noqa: E402
from swift.model.model_meta import MODEL_MAPPING  # noqa: E402
from swift.model.register import ModelLoader  # noqa: E402
from swift.optimizers import optimizers_map  # noqa: E402
from swift.optimizers.base import OptimizerCallback  # noqa: E402
from swift.template import Template, TemplateMeta, register_template  # noqa: E402
from swift.template.register import TEMPLATE_MAPPING  # noqa: E402
from swift.tuner_plugin import Tuner, tuners_map  # noqa: E402
from swift.utils import get_logger  # noqa: E402

logger = get_logger()

MODEL_TYPE = 'graph_token_lm'
TEMPLATE_TYPE = 'graph_token'
TUNER_TYPE = 'graph_lora'
OPTIMIZER = 'graph_token'
PROJ_NAME = 'graph_proj'
EXTRA_KEYS = ['run_id', 'graph_refs']

# keep our two extra columns through swift's dataset loader (it otherwise drops non-standard columns)
for _k in EXTRA_KEYS:
    if _k not in RowPreprocessor.standard_keys:
        RowPreprocessor.standard_keys.append(_k)


def d_graph() -> int:
    return int(os.environ.get('MHT_D_GRAPH', 192))


def build_projector(d_in: int, hidden: int, dtype) -> nn.Sequential:
    """Same architecture (and state-dict keys 0.* / 2.*) as GraphTokenLM.proj."""
    return nn.Sequential(nn.Linear(d_in, hidden), nn.ReLU(), nn.Linear(hidden, hidden)).to(dtype)


# ----------------------------------------------------------------------------------------------- model
class GraphTokenLoader(ModelLoader):
    """Base causal LM + "<graph>" special token + projector, mirroring GraphTokenLM.__init__."""

    def get_processor(self, model_dir, config):
        tok = super().get_processor(model_dir, config)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        tok.add_special_tokens({'additional_special_tokens': [GRAPH_TOKEN]})
        return tok

    def get_model(self, model_dir, config, processor, model_kwargs):
        model = super().get_model(model_dir, config, processor, model_kwargs)
        tok = processor
        model.resize_token_embeddings(len(tok))    # exactly like GraphTokenLM (no padding to a multiple)
        emb = model.get_input_embeddings()
        hid = model.config.get_text_config().hidden_size if hasattr(model.config, 'get_text_config') else model.config.hidden_size
        proj = build_projector(d_graph() + 2, hid, emb.weight.dtype)
        if emb.weight.device.type != 'meta':
            proj = proj.to(emb.weight.device)
        init = os.environ.get('MHT_PROJ_INIT')   # round 64: start from a SAMT-aligned projector (projector.pt)
        if init:
            proj.load_state_dict(torch.load(init, map_location='cpu'))
            logger.info(f'graph_proj initialised from {init}')
        model.add_module(PROJ_NAME, proj)
        model.graph_token_id = tok.convert_tokens_to_ids(GRAPH_TOKEN)
        return model


if MODEL_TYPE not in MODEL_MAPPING:
    # is_multimodal=True makes swift's trainer register Template.pre_forward_hook (-> _post_encode) on the model,
    # the same mechanism it uses for vision-language models. model_arch stays None (no vision tower).
    register_model(ModelMeta(MODEL_TYPE, [], GraphTokenLoader, template=TEMPLATE_TYPE, is_multimodal=True))


# ----------------------------------------------------------------------------------------------- template
_TOKENS_CACHE: Dict[str, Any] = {}


def _graph_tokens():
    path = os.environ.get('MHT_GRAPH_TOKENS')
    if not path:
        raise ValueError('rows contain graph_refs but MHT_GRAPH_TOKENS (path of graph_tokens.pt) is not set')
    if path not in _TOKENS_CACHE:
        _TOKENS_CACHE[path] = torch.load(path)
    return _TOKENS_CACHE[path]


def _parse_refs(refs) -> List:
    if refs is None:
        return []
    if isinstance(refs, str):
        refs = json.loads(refs)
    return [[str(k), int(i)] for k, i in refs]


class GraphTokenTemplate(Template):
    support_padding_free = False
    skip_prompt = True

    def _graph_id(self) -> int:
        return self.tokenizer.convert_tokens_to_ids(GRAPH_TOKEN)

    def _encode(self, inputs) -> Dict[str, Any]:
        """train.encode + the graph-vector part of train.batches, for one row."""
        tok = self.tokenizer
        msgs = inputs.messages
        answer = None
        if msgs and msgs[-1]['role'] == 'assistant':
            answer = msgs[-1]['content']
            msgs = msgs[:-1]
        assert len(msgs) == 1 and msgs[0]['role'] == 'user', f'expected [system,] user [, assistant]; got {msgs}'
        chat = ([{'role': 'system', 'content': inputs.system}] if inputs.system is not None else []) + list(msgs)
        # enable_thinking=False is what train.encode passes for Qwen3; chat templates without the switch ignore it
        prompt = tok.apply_chat_template(chat, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        p_ids = tok(prompt, add_special_tokens=False)['input_ids']
        with_answer = self.is_training and answer is not None
        a_ids = tok(answer + tok.eos_token, add_special_tokens=False)['input_ids'] if with_answer else []
        max_len = self.max_length
        if max_len is not None and len(p_ids) + len(a_ids) > max_len:   # keep the end, drop the head of the prompt
            p_ids = p_ids[-(max_len - len(a_ids)):]
        gid = self._graph_id()
        n_ph = sum(1 for t in p_ids if t == gid)
        extra = inputs.extra_kwargs or {}
        refs = _parse_refs(extra.get('graph_refs'))
        if refs:
            g = graph_vectors({'run_id': extra['run_id'], 'graph_refs': refs}, _graph_tokens())
            g = g[-n_ph:] if n_ph else g[:0]   # placeholders cut by truncation drop their oldest vectors
        else:
            g = torch.zeros(0, d_graph() + 2)
        if g.shape[0] != n_ph:
            raise ValueError(f'{n_ph} <graph> placeholders but {g.shape[0]} graph vectors (run {extra.get("run_id")})')
        encoded = {'input_ids': p_ids + a_ids, 'labels': ([-100] * len(p_ids) + a_ids) if with_answer else None,
                   'loss_scale': None}
        if n_ph:
            encoded['graph_vecs'] = g
        return encoded

    def _data_collator(self, batch: List[Dict[str, Any]], *, padding_to: Optional[int] = None) -> Dict[str, Any]:
        res = super()._data_collator(batch, padding_to=padding_to)
        vecs = [b.get('graph_vecs') for b in batch]
        counts = [0 if v is None else int(v.shape[0]) for v in vecs]
        if any(counts):
            dim = next(v.shape[1] for v in vecs if v is not None)
            out = torch.zeros(len(batch), max(counts), dim, dtype=torch.float32)
            for i, v in enumerate(vecs):
                if counts[i]:
                    out[i, :counts[i]] = torch.as_tensor(v, dtype=torch.float32)
            res['graph_vecs'] = out
            res['graph_counts'] = torch.tensor(counts, dtype=torch.long)
        return res

    def _post_encode(self, model: nn.Module, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """GraphTokenLM.embed: replace the input embedding of every <graph> token by proj(graph vector)."""
        inputs = dict(inputs)
        vecs = inputs.pop('graph_vecs', None)
        counts = inputs.pop('graph_counts', None)
        if vecs is None:
            return inputs
        input_ids = inputs['input_ids']
        base = self.get_base_model(model)
        emb = base.get_input_embeddings()(input_ids)
        proj = getattr(base, PROJ_NAME)
        mask = input_ids == self._graph_id()
        sel = torch.cat([vecs[i, :int(c)] for i, c in enumerate(counts.tolist())])   # row-major = placeholder order
        if int(mask.sum()) != sel.shape[0]:
            raise ValueError(f'{int(mask.sum())} <graph> tokens in the batch but {sel.shape[0]} graph vectors')
        g = proj(sel.to(emb.dtype))
        emb = emb.clone()
        emb[mask] = g.to(emb.dtype)
        inputs['inputs_embeds'] = emb
        return inputs


if TEMPLATE_TYPE not in TEMPLATE_MAPPING:
    # chatml meta is only used by swift's generation utilities (stop words); _encode above builds the prompt
    # with the tokenizer's own chat template, as train.encode does.
    register_template(TemplateMeta(TEMPLATE_TYPE, prefix=[], prompt=['<|im_start|>user\n{{QUERY}}<|im_end|>\n<|im_start|>assistant\n'],
                                   chat_sep=['<|im_end|>\n'], suffix=['<|im_end|>'],
                                   system_prefix=['<|im_start|>system\n{{SYSTEM}}<|im_end|>\n'],
                                   template_cls=GraphTokenTemplate, stop_words=['<|endoftext|>']))


# ----------------------------------------------------------------------------------------------- tuner
def _peft_inner(model):
    """HF model inside a PeftModel."""
    from peft import PeftModel
    return model.get_base_model() if isinstance(model, PeftModel) else model


class GraphLoRATuner(Tuner):
    """LoRA on the LM + full training of the projector; LoRA as GraphTokenLM's get_peft_model call."""

    @staticmethod
    def prepare_model(args, model):
        from peft import LoraConfig, get_peft_model
        targets = args.target_modules
        if isinstance(targets, (list, tuple)) and 'all-linear' in targets:
            raise ValueError('graph_lora: pass explicit --target_modules (e.g. q_proj k_proj v_proj)')
        model.requires_grad_(False)
        cfg = LoraConfig(r=args.lora_rank, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout,
                         target_modules=list(targets) if not isinstance(targets, str) else targets, task_type='CAUSAL_LM')
        model = get_peft_model(model, cfg)
        getattr(_peft_inner(model), PROJ_NAME).requires_grad_(True)
        logger.info(f'graph_lora: {cfg}')
        return model

    @staticmethod
    def save_pretrained(model, save_directory: str, state_dict: Optional[dict] = None, safe_serialization: bool = True,
                        **kwargs) -> None:
        os.makedirs(save_directory, exist_ok=True)
        inner = _peft_inner(model)
        proj = getattr(inner, PROJ_NAME)
        if state_dict is None:
            proj_sd = {k: v.detach().cpu() for k, v in proj.state_dict().items()}
        else:   # deepspeed: gathered trainable params, names like base_model.model.graph_proj.0.weight
            key = f'.{PROJ_NAME}.'
            proj_sd = {k.split(key, 1)[1]: v.detach().cpu() for k, v in state_dict.items() if key in f'.{k}'}
            if not proj_sd:
                proj_sd = {k: v.detach().cpu() for k, v in proj.state_dict().items()}
        # as train.py: the resized embedding / lm_head are not saved (the <graph> row is always overwritten by the
        # projector; the tokenizer + resize are rebuilt identically by GraphTokenLoader at load time)
        model.save_pretrained(save_directory, state_dict=state_dict, safe_serialization=safe_serialization,
                              selected_adapters=['default'], save_embedding_layers=False)
        torch.save(proj_sd, os.path.join(save_directory, 'projector.pt'))
        meta = {'graph_token': GRAPH_TOKEN, 'graph_token_id': int(getattr(inner, 'graph_token_id', -1)),
                'd_graph': d_graph(), 'vocab_size': int(inner.get_input_embeddings().weight.shape[0])}
        with open(os.path.join(save_directory, 'graph_token_meta.json'), 'w') as f:
            json.dump(meta, f, indent=1)

    @staticmethod
    def from_pretrained(model, model_id: str, **kwargs):
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, model_id, **kwargs)
        proj = getattr(_peft_inner(model), PROJ_NAME)
        sd = torch.load(os.path.join(model_id, 'projector.pt'), map_location='cpu')
        proj.load_state_dict(sd)
        if kwargs.get('is_trainable'):
            proj.requires_grad_(True)
        return model


tuners_map[TUNER_TYPE] = GraphLoRATuner


# ----------------------------------------------------------------------------------------------- optimizer
class GraphTokenOptimizerCallback(OptimizerCallback):
    """Two AdamW groups like train.py: LoRA params at --learning_rate, projector at --aligner_lr."""

    def create_optimizer(self, model=None):
        from transformers import Trainer as HfTrainer
        args = self.args
        model = model or self.trainer.model
        decay = set(HfTrainer.get_decay_parameter_names(None, model))
        proj_lr = args.aligner_lr if getattr(args, 'aligner_lr', None) is not None else args.learning_rate
        groups = []
        for is_proj, lr in ((False, args.learning_rate), (True, proj_lr)):
            named = [(n, p) for n, p in model.named_parameters()
                     if p.requires_grad and ((f'{PROJ_NAME}.' in n) == is_proj)]
            for use_wd in (False, True):
                ps = [p for n, p in named if (n in decay) == use_wd]
                if ps:
                    groups.append({'params': ps, 'lr': lr, 'weight_decay': args.weight_decay if use_wd else 0.0})
        logger.info(f'graph_token optimizer: llm lr {args.learning_rate}, projector lr {proj_lr}, '
                    f'wd {args.weight_decay}, groups {[len(g["params"]) for g in groups]}')
        cls, kw = HfTrainer.get_optimizer_cls_and_kwargs(args, model)
        return cls(groups, **kw)


optimizers_map[OPTIMIZER] = GraphTokenOptimizerCallback
