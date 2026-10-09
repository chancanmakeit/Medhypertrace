"""
Evaluate a trained AEGIS-med-SFT checkpoint on the medical test sets, with the
unified metrics: Agent/Error/Pair Micro/Macro-F1 (vendored compute_metrics) at the
trained granularity, plus earliest-error-step Top-1 for the with_step variant.

Prompts are built with aegis_med.build_prompt — the SAME template used to create the
training data — so train/eval are byte-consistent. Do NOT use the repo's
evaluate-v3.py for med-SFT (that builds the general-domain prompt).

Backends: --backend vllm  (OpenAI-compatible server, --base_url/--model)
          --backend hf    (local transformers checkpoint, --model = path)
          --backend mock  (plumbing check, no GPU)

Example (GPU box):
  python baselines/aegis_med_sft/eval_med_sft.py --variant with_step \
      --backend hf --model outputs/aegis-med-sft-withstep/huggingface_merged \
      --frameworks mdagents dylan llm_debate
"""
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

import argparse
import json

from common.data import load_jsonl
from common.paths import FILES
from common.splits import load_split
from common.aegis_metrics import compute_metrics
from baselines.aegis_med_sft.aegis_med import (build_prompt, build_target_json,
                                               parse_prediction, step_top1, SYSTEM)


def get_backend(args):
    if args.backend == "mock":
        def call(system, user):
            return ('{"faulty_agents":[{"agent_name":"Aggregator","error_type":"FM-3.2"}],'
                    '"earliest_error_step": 1}')
        return call
    if args.backend == "vllm":
        from openai import OpenAI
        client = OpenAI(base_url=args.base_url, api_key=args.api_key or "EMPTY")
        def call(system, user):
            r = client.chat.completions.create(
                model=args.model, temperature=0.0, max_tokens=args.max_new_tokens,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}])
            return (r.choices[0].message.content or "").strip()
        return call
    # hf
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map="auto")
    def call(system, user):
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
        ids = tok.apply_chat_template(msgs, add_generation_prompt=True,
                                      return_tensors="pt").to(model.device)
        out = model.generate(ids, max_new_tokens=args.max_new_tokens, do_sample=False)
        return tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True).strip()
    return call


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["no_step", "with_step"], required=True)
    ap.add_argument("--agent_key", choices=["instance", "role"], default="instance")
    ap.add_argument("--backend", choices=["hf", "vllm", "mock"], default="mock")
    ap.add_argument("--model", default=None)
    ap.add_argument("--base_url", default=None)
    ap.add_argument("--api_key", default=None)
    ap.add_argument("--max_new_tokens", type=int, default=512)
    ap.add_argument("--frameworks", nargs="+", default=list(FILES))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=1,
                    help="concurrent requests (feeds vLLM continuous batching)")
    ap.add_argument("--out", default=None, help="optional jsonl dump of raw outputs")
    ap.add_argument("--json_out", default=None,
                    help="per-framework metrics json (method key 'aegis_med_sft')")
    ap.add_argument("--pooled_out", default=None,
                    help="framework-agnostic pooled metrics json")
    args = ap.parse_args()

    llm = get_backend(args)
    dump = open(args.out, "w") if args.out else None

    per_fw = {}                       # {framework: {"aegis_med_sft": metrics}}
    pool_preds, pool_gts = [], []     # concatenated for correct pooled Micro-F1
    pool_shit = pool_stot = 0
    for name in args.frameworks:
        trajs = load_jsonl(FILES[name])
        _, te = load_split(name)
        te_trajs = [t for t in trajs if t.id in te]
        if args.limit:
            te_trajs = te_trajs[:args.limit]
        # inference: each trajectory is one independent call -> run concurrently so a
        # vLLM server batches them (feeds tensor/data-parallel serving).
        prompts = [build_prompt(t, args.variant, args.agent_key) for t in te_trajs]
        if args.workers > 1:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                outs = list(ex.map(lambda p: llm(SYSTEM, p), prompts))
        else:
            outs = [llm(SYSTEM, p) for p in prompts]

        preds, gts, psteps, gsteps = [], [], [], []
        parsed = 0
        for t, out in zip(te_trajs, outs):
            ok, pairs, est = parse_prediction(out)
            parsed += int(ok)
            preds.append(pairs)
            gt = json.loads(build_target_json(t, args.variant, args.agent_key))
            gts.append([(x["agent_name"], x["error_type"]) for x in gt["faulty_agents"]])
            if args.variant == "with_step":
                psteps.append(est)
                gsteps.append(t.labels.earliest_error_turn)
            if dump:
                dump.write(json.dumps({"id": t.id, "framework": name, "raw": out},
                                      ensure_ascii=False) + "\n")
        m = compute_metrics(preds, gts)
        parse_ok = parsed / max(len(te_trajs), 1)
        line = (f"[{name}] n={len(te_trajs)} parse_ok={parse_ok:.2f} | "
                f"Agent mi/ma={m['agent_micro_f1']:.1f}/{m['agent_macro_f1']:.1f} "
                f"Error mi/ma={m['error_micro_f1']:.1f}/{m['error_macro_f1']:.1f} "
                f"Pair mi/ma={m['pair_micro_f1']:.1f}/{m['pair_macro_f1']:.1f}")
        rec = dict(m)
        rec["parse_ok"] = parse_ok
        rec["n"] = len(te_trajs)
        if args.variant == "with_step":
            acc, n = step_top1(psteps, gsteps)
            line += f" | step Top-1={acc:.3f} (n={n})"
            rec["step_acc"] = acc
            # accumulate step counts for pooled step-acc
            pool_shit += acc * n
            pool_stot += n
        else:
            rec["step_acc"] = None
        per_fw[name] = {"aegis_med_sft": rec}
        pool_preds.extend(preds)
        pool_gts.extend(gts)
        print(line)
    if dump:
        dump.close()

    # per-framework json (for the framework-specific table) and pooled json (for the
    # framework-agnostic table). Pooled Micro-F1 is computed on concatenated pred/gt
    # (summed TP/FP/FN), NOT by averaging per-framework F1.
    if args.json_out:
        json.dump(per_fw, open(args.json_out, "w"), indent=1)
        print(f"\nwrote {args.json_out} (per-framework, method key 'aegis_med_sft')")
    if args.pooled_out:
        cm = compute_metrics(pool_preds, pool_gts)
        cm["step_acc"] = (pool_shit / pool_stot) if pool_stot else None
        cm["n"] = len(pool_preds)
        # pooled parse_ok = weighted mean over frameworks
        tot = sum(per_fw[f]["aegis_med_sft"]["n"] for f in per_fw)
        cm["parse_ok"] = sum(per_fw[f]["aegis_med_sft"]["parse_ok"] *
                             per_fw[f]["aegis_med_sft"]["n"] for f in per_fw) / max(tot, 1)
        json.dump({"pooled": {"aegis_med_sft": cm}}, open(args.pooled_out, "w"), indent=1)
        print(f"wrote {args.pooled_out} (framework-agnostic pooled)")


if __name__ == "__main__":
    main()
