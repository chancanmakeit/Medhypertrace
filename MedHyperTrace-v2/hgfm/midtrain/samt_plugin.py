"""MS-Swift plugin for structure-aware mid-training (SAMT v1, round 64; design docs/design/SAMT_design_v1.md).

Load with `swift sft --external_plugins MedHyperTrace-v2/hgfm/midtrain/samt_plugin.py ...`. It reuses the graph-token
plugin (hgfm/llm/swift_plugin/plugin.py: `<graph>` token, projector `graph_proj`, placeholder replacement in the
pre-forward hook) and adds an HGFM v0.2 encoder that runs INSIDE the forward pass, so the encoder is trained end to end
through the frozen LLM:

  model_type `graph_enc_lm`  GraphTokenLoader + submodule `graph_enc` (HGFM v0.2 without its heads, fp32)
  template   `graph_enc`     row = messages + run_id + graph_refs; the collator batches the rows' hypergraphs from the
                             pickle $MHT_GRAPH_CACHE ({run_id: featurised run}, hgfm.midtrain.samt_graph) and the
                             reference indices; `_post_encode` runs the encoder (fp32, autocast off), takes the node /
                             edge states in placeholder order, appends the node/edge flag (as graph_vectors), projects
                             them and replaces the <graph> embeddings (= GraphTokenLM.embed).
  tuner_type `graph_align`   LLM frozen; encoder + projector trainable. Checkpoint = encoder.pt + projector.pt +
                             samt_meta.json only (no LLM weights).
Conditions for the probe (hgfm.midtrain.samt_probe) are applied by the same `graph_states` function.
"""
import json
import os
import pickle
import sys
from typing import Any, Dict, List, Optional

import torch
import torch.nn as nn

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2_ROOT = os.path.abspath(os.path.join(_HERE, '..', '..'))
if _V2_ROOT not in sys.path:
    sys.path.insert(0, _V2_ROOT)
from hgfm.midtrain.samt_model import GraphEncoder, graph_states, batch_graph, D_IN  # noqa: E402
from hgfm.llm.swift_plugin import plugin as gp  # noqa: E402  (registers graph_token_lm / graph_token / graph_lora)

from swift.model import ModelMeta, register_model  # noqa: E402
from swift.model.model_meta import MODEL_MAPPING  # noqa: E402
from swift.template import TemplateMeta, register_template  # noqa: E402
from swift.template.register import TEMPLATE_MAPPING  # noqa: E402
from swift.tuner_plugin import Tuner, tuners_map  # noqa: E402
from swift.utils import get_logger  # noqa: E402

logger = get_logger()
MODEL_TYPE, TEMPLATE_TYPE, TUNER_TYPE, ENC_NAME = 'graph_enc_lm', 'graph_enc', 'graph_align', 'graph_enc'


# ----------------------------------------------------------------------------------------------- model
class GraphEncLoader(gp.GraphTokenLoader):
    def get_model(self, model_dir, config, processor, model_kwargs):
        model = super().get_model(model_dir, config, processor, model_kwargs)
        dev = model.get_input_embeddings().weight.device
        enc = GraphEncoder()
        if dev.type != 'meta':
            enc = enc.to(dev)
        model.add_module(ENC_NAME, enc)     # fp32 on purpose: index_add / scatter in bf16 lose precision
        # the projector is what SAMT mainly trains: keep fp32 master weights (autocast still computes in bf16);
        # SFT loads projector.pt into its bf16 projector (load_state_dict casts)
        getattr(model, gp.PROJ_NAME).float()
        init = os.environ.get('MHT_SAMT_INIT')   # optional: continue from a SAMT checkpoint dir
        if init:
            enc.load_state_dict(torch.load(os.path.join(init, 'encoder.pt'), map_location='cpu'))
            getattr(model, gp.PROJ_NAME).load_state_dict(torch.load(os.path.join(init, 'projector.pt'), map_location='cpu'))
        return model


if MODEL_TYPE not in MODEL_MAPPING:
    register_model(ModelMeta(MODEL_TYPE, [], GraphEncLoader, template=TEMPLATE_TYPE, is_multimodal=True))


# ----------------------------------------------------------------------------------------------- template
_CACHE: Dict[str, Any] = {}


def graph_cache():
    path = os.environ.get('MHT_GRAPH_CACHE')
    if not path:
        raise ValueError('MHT_GRAPH_CACHE (pickle {run_id: featurised run}) is not set')
    if path not in _CACHE:
        with open(path, 'rb') as f:
            _CACHE[path] = pickle.load(f)
    return _CACHE[path]


class GraphEncTemplate(gp.GraphTokenTemplate):

    def _encode(self, inputs) -> Dict[str, Any]:
        tok = self.tokenizer
        msgs = inputs.messages; answer = None
        if msgs and msgs[-1]['role'] == 'assistant':
            answer = msgs[-1]['content']; msgs = msgs[:-1]
        assert len(msgs) == 1 and msgs[0]['role'] == 'user', f'expected [system,] user [, assistant]; got {msgs}'
        chat = ([{'role': 'system', 'content': inputs.system}] if inputs.system is not None else []) + list(msgs)
        prompt = tok.apply_chat_template(chat, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        p_ids = tok(prompt, add_special_tokens=False)['input_ids']
        with_answer = self.is_training and answer is not None
        a_ids = tok(answer + tok.eos_token, add_special_tokens=False)['input_ids'] if with_answer else []
        if self.max_length is not None and len(p_ids) + len(a_ids) > self.max_length:   # keep the end (as plugin.py)
            p_ids = p_ids[-(self.max_length - len(a_ids)):]
        n_ph = sum(1 for t in p_ids if t == self._graph_id())
        extra = inputs.extra_kwargs or {}
        refs = gp._parse_refs(extra.get('graph_refs'))
        refs = refs[-n_ph:] if n_ph else []
        if len(refs) != n_ph:
            raise ValueError(f'{n_ph} <graph> placeholders but {len(refs)} refs (run {extra.get("run_id")})')
        enc = {'input_ids': p_ids + a_ids, 'labels': ([-100] * len(p_ids) + a_ids) if with_answer else None, 'loss_scale': None}
        if n_ph:
            enc['samt_run'] = str(extra['run_id']); enc['samt_refs'] = refs
        return enc

    def _data_collator(self, batch: List[Dict[str, Any]], *, padding_to: Optional[int] = None) -> Dict[str, Any]:
        res = super(gp.GraphTokenTemplate, self)._data_collator(batch, padding_to=padding_to)
        rows = [b for b in batch if b.get('samt_refs')]
        if rows:
            res.update(batch_graph([b['samt_run'] for b in rows], [b['samt_refs'] for b in rows], graph_cache()))
        return res

    def _post_encode(self, model: nn.Module, inputs: Dict[str, Any]) -> Dict[str, Any]:
        inputs = dict(inputs)
        B = inputs.pop('samt_graph', None); kind = inputs.pop('samt_kind', None); idx = inputs.pop('samt_idx', None)
        if B is None:
            return inputs
        input_ids = inputs['input_ids']
        base = self.get_base_model(model)
        dev = input_ids.device
        B = {k: (v.to(dev) if torch.is_tensor(v) else v) for k, v in B.items()}
        vec = graph_states(getattr(base, ENC_NAME), B, kind.to(dev), idx.to(dev))
        emb = base.get_input_embeddings()(input_ids)
        mask = input_ids == self._graph_id()
        if int(mask.sum()) != vec.shape[0]:
            raise ValueError(f'{int(mask.sum())} <graph> tokens in the batch but {vec.shape[0]} graph vectors')
        proj = getattr(base, gp.PROJ_NAME)
        g = proj(vec.to(proj[0].weight.dtype))
        emb = emb.clone(); emb[mask] = g.to(emb.dtype)
        inputs['inputs_embeds'] = emb
        return inputs


if TEMPLATE_TYPE not in TEMPLATE_MAPPING:
    register_template(TemplateMeta(TEMPLATE_TYPE, prefix=[], prompt=['<|im_start|>user\n{{QUERY}}<|im_end|>\n<|im_start|>assistant\n'],
                                   chat_sep=['<|im_end|>\n'], suffix=['<|im_end|>'],
                                   system_prefix=['<|im_start|>system\n{{SYSTEM}}<|im_end|>\n'],
                                   template_cls=GraphEncTemplate, stop_words=['<|endoftext|>']))


# ----------------------------------------------------------------------------------------------- tuner
class GraphAlignTuner(Tuner):
    """Frozen LLM; train only graph_enc + graph_proj. Saves only those two modules."""

    @staticmethod
    def prepare_model(args, model):
        model.requires_grad_(False)
        getattr(model, ENC_NAME).requires_grad_(True)
        getattr(model, gp.PROJ_NAME).requires_grad_(True)
        n = sum(p.numel() for p in model.parameters() if p.requires_grad)
        logger.info(f'graph_align: LLM frozen, trainable encoder + projector = {n / 1e6:.2f}M parameters')
        return model

    @staticmethod
    def save_pretrained(model, save_directory: str, state_dict: Optional[dict] = None, safe_serialization: bool = True, **kwargs) -> None:
        os.makedirs(save_directory, exist_ok=True)
        for name, fn in ((ENC_NAME, 'encoder.pt'), (gp.PROJ_NAME, 'projector.pt')):
            mod = getattr(model, name)
            torch.save({k: v.detach().cpu() for k, v in mod.state_dict().items()}, os.path.join(save_directory, fn))
        json.dump({'d_in': D_IN, 'd_graph': 192, 'graph_token': gp.GRAPH_TOKEN}, open(os.path.join(save_directory, 'samt_meta.json'), 'w'))

    @staticmethod
    def from_pretrained(model, model_id: str, **kwargs):
        getattr(model, ENC_NAME).load_state_dict(torch.load(os.path.join(model_id, 'encoder.pt'), map_location='cpu'))
        getattr(model, gp.PROJ_NAME).load_state_dict(torch.load(os.path.join(model_id, 'projector.pt'), map_location='cpu'))
        if kwargs.get('is_trainable'):
            getattr(model, ENC_NAME).requires_grad_(True); getattr(model, gp.PROJ_NAME).requires_grad_(True)
        return model


tuners_map[TUNER_TYPE] = GraphAlignTuner
