"""eval.py for checkpoints trained with `swift sft` + this plugin.

Score of a prompt = logit("yes") - logit("no") at the first answer position (as eval.py); instance score = max over
the prompts of an instance; per-code AUROC vs the human majority, macro AUROC with a bootstrap CI; same output JSON
as eval.py so hgfm.llm.pool works unchanged. Prompts are built by the plugin's template (same code as training).
Usage:
  MHT_GRAPH_TOKENS=<fold>/graph_tokens.pt python MedHyperTrace-v2/hgfm/llm/swift_plugin/eval_swift.py \
      --lm Qwen/Qwen3-8B --ckpt <swift output>/vX-.../checkpoint-N --data <fold>/sft_graph/eval_human.jsonl --out eval.json
  [--no_graph] (text variant: data from sft_text; the template simply finds no placeholders)  [--zero_shot]
"""
import argparse
import collections
import json
import os
import sys
import warnings

warnings.filterwarnings('ignore', category=RuntimeWarning)
import numpy as np
import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
from swift.utils import import_external_file  # noqa: E402

# same module object as `swift ... --external_plugins plugin.py` would create (registers model/template/tuner/optimizer)
plugin = import_external_file(os.path.join(_HERE, 'plugin.py'))
convert = import_external_file(os.path.join(_HERE, 'prepare_data.py')).convert


def load(lm, ckpt=None, dtype=torch.bfloat16, max_len=2048, device='cpu'):
    from swift.model import get_model_processor
    from swift.template import get_template
    model, tok = get_model_processor(lm, model_type=plugin.MODEL_TYPE, torch_dtype=dtype, device_map=device)
    template = get_template(tok, template_type=plugin.TEMPLATE_TYPE, max_length=max_len, truncation_strategy='left')
    template.set_mode('transformers')
    if ckpt:
        model = plugin.GraphLoRATuner.from_pretrained(model, ckpt)
    model.eval()
    return model, template


@torch.no_grad()
def score(model, template, row, yes, no):
    """row: an original build_sft eval row (no answer)."""
    enc = template.encode({k: v for k, v in convert({**row, 'answer': None}).items()})
    batch = template.data_collator([enc])
    dev = next(model.parameters()).device
    batch = {k: (v.to(dev) if torch.is_tensor(v) else v) for k, v in batch.items()}
    batch = template._post_encode(model, batch)
    if 'inputs_embeds' in batch:
        batch.pop('input_ids')
    logits = model(**batch).logits[0, -1].float()
    return float(logits[yes] - logits[no])


def summarize(rows, args):
    from sklearn.metrics import roc_auc_score

    def auc(y, sc):
        return roc_auc_score(y, sc) if len(set(y)) == 2 else float('nan')

    codes = sorted({r['code'] for r in rows})
    per = {c: auc([r['human'] for r in rows if r['code'] == c], [r['score'] for r in rows if r['code'] == c]) for c in codes}
    rng = np.random.default_rng(0); boots = []
    for _ in range(500):
        b = [rows[i] for i in rng.integers(0, len(rows), len(rows))]
        boots.append(np.nanmean([auc([r['human'] for r in b if r['code'] == c], [r['score'] for r in b if r['code'] == c]) for c in codes]))
    return {'n': len(rows), 'macro_auroc': float(np.nanmean(list(per.values()))),
            'ci95': [float(np.nanpercentile(boots, 2.5)), float(np.nanpercentile(boots, 97.5))], 'per_code': per,
            'rows': rows, 'args': vars(args)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lm', default='Qwen/Qwen3-8B'); ap.add_argument('--ckpt', default=''); ap.add_argument('--data'); ap.add_argument('--out')
    ap.add_argument('--no_graph', action='store_true'); ap.add_argument('--zero_shot', action='store_true'); ap.add_argument('--max_len', type=int, default=2048)
    ap.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu'); ap.add_argument('--dtype', default='bf16'); ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args(); dtype = {'bf16': torch.bfloat16, 'fp32': torch.float32}[a.dtype]
    model, template = load(a.lm, None if a.zero_shot else (a.ckpt or None), dtype, a.max_len, a.device)
    tok = template.tokenizer
    yes, no = tok('yes', add_special_tokens=False)['input_ids'][0], tok('no', add_special_tokens=False)['input_ids'][0]
    data = [json.loads(l) for l in open(a.data)]
    if a.limit: data = data[: a.limit]
    inst = collections.defaultdict(list); meta = {}
    for s in data:
        inst[s['inst']].append(score(model, template, s, yes, no)); meta[s['inst']] = (s['code'], s['label'], s['auditor'])
    rows = [{'inst': k, 'code': meta[k][0], 'human': meta[k][1], 'auditor': meta[k][2], 'score': max(v)} for k, v in inst.items()]
    out = summarize(rows, a)
    json.dump(out, open(a.out, 'w'), indent=1); print(f"n={out['n']} macro AUROC={out['macro_auroc']:.3f} {out['ci95']}")


if __name__ == '__main__':
    main()
