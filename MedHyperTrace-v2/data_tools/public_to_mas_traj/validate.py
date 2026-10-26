"""Validation of the converted public datasets (MHT r57), checks a-f of the task:

  a. medical-aegis export_schema_v1.check() on every record (+ run_id uniqueness)
  b. medical-aegis scripts/sources_provenance_analysis.py, run unchanged on a decompressed copy; its
     "slot_determined" table = share of steps whose read set equals the most common one for their slot
     (agent_id, phase, round) -- the partner's round-41 definition
  c. text_match statistics (datasets with per-step inputs)
  d. MAA exclusion: python -m data_tools.maa_exclusion check docs/interfaces/maa_exclusion_v1.json <file>
  e. counts and token sums (o200k output_tokens_est; plus Qwen3-8B counts of query + step outputs, the
     tokenizer of stats*.md)
  f. determinism: re-run the converter to a temp file and compare sha256

  python -m data_tools.public_to_mas_traj.validate --datasets who_and_when traceelephant mast_data aria \
      --data /home/claude/public_mas/mas_traj --tmp <scratch dir> --out analysis/public_mas_corpus/mas_traj_r57.json
"""
import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict

from .common import count_tokens, partner_module, read_jsonl_gz

MODULE = {"who_and_when": "whowhen", "traceelephant": "traceelephant", "mast_data": "mast", "aria": "aria",
          "aftraj": "aftraj", "mascope": "mascope", "agentrx_tau": "agentrx_tau"}
SPA = "/home/claude/medical-aegis/scripts/sources_provenance_analysis.py"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def qwen():
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "true")
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained("Qwen/Qwen3-8B")


def parse_spa(out):
    """slot_determined lines and the mode_share table of sources_provenance_analysis.py."""
    slot, mode = {}, {}
    sec = None
    for line in out.splitlines():
        if line.startswith("== read-set predictability"):
            sec = "mode"
            continue
        if line.startswith("== share of steps whose read set equals"):
            sec = "slot"
            continue
        if line.startswith("=="):
            sec = None
            continue
        if sec == "slot":
            m = re.match(r"^(\S+)\s+(.+?)\s+steps=\s*(\d+) slot_determined=([\d.]+)$", line)
            if m:
                slot[f"{m.group(1)}|{m.group(2).strip()}"] = {"steps": int(m.group(3)), "slot_determined": float(m.group(4))}
        elif sec == "mode":
            m = re.match(r"^(\S+)\s+(.+?)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+(\d+)$", line)
            if m and m.group(1) != "framework":
                mode[f"{m.group(1)}|{m.group(2).strip()}"] = {"steps": int(m.group(3)), "patterns": int(m.group(4)),
                                                              "mode_share": float(m.group(5)), "choice_steps": int(m.group(6))}
    return slot, mode


def validate(ds, data_dir, tmp, tok, rerun=True):
    path = os.path.join(data_dir, f"{ds}.jsonl.gz")
    chk = partner_module().check
    res = {"file": path, "sha256": sha(path), "bytes": os.path.getsize(path)}
    n = bad = 0
    probs = []
    ids = Counter()
    fw = Counter()
    fam = {}
    per_fw = defaultdict(Counter)
    corr = Counter()
    hows = Counter()
    q_tok = 0
    plain = os.path.join(tmp, f"{ds}.jsonl")
    texts = []
    with open(plain, "w", encoding="utf-8") as fo:
        for r in read_jsonl_gz(path):
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
            ids[r["run_id"]] += 1
            p = chk(r)
            if p:
                bad += 1
                probs.append([r["run_id"], p[:3]])
            f = r["framework"]
            fw[f] += 1
            fam[f] = r["framework_family"]
            corr[str(r["labels"].get("is_correct"))] += 1
            c = per_fw[f]
            c["records"] += 1
            texts.append(r["task"]["query"] or "")
            for s in r["steps"]:
                c[f"steps_{s['kind']}"] += 1
                if s["kind"] == "llm":
                    c["tok_llm_output_o200k"] += s["output_tokens_est"] or 0
                else:
                    c["tok_tool_output_o200k"] += count_tokens(s["output"])
                if s["sources"] is None:
                    c["steps_sources_null"] += 1
                elif not s["sources"]:
                    c["steps_sources_empty"] += 1
                if s["input_messages"] is not None:
                    c["steps_with_inputs"] += 1
                    c["steps_with_inputs_zero_sources"] += not s["sources"]
                for x in s["sources"] or []:
                    c[f"src_{x['inferred']}"] += 1
                    hows[(f, x["how"], x["inferred"])] += 1
                texts.append(s["output"] or "")
    # Qwen3-8B tokens of query + every step output (stats*.md tokenizer), batched
    qtok = 0
    for i in range(0, len(texts), 512):
        enc = tok._tokenizer.encode_batch(texts[i:i + 512], add_special_tokens=False)
        qtok += sum(len(e.ids) for e in enc)
    res["a_check"] = {"records": n, "pass": n - bad, "fail": bad, "examples": probs[:5],
                      "duplicate_run_ids": sum(1 for v in ids.values() if v > 1)}
    res["frameworks"] = {k: {"records": v, "family": fam[k]} for k, v in sorted(fw.items())}
    res["per_framework"] = {k: dict(v) for k, v in sorted(per_fw.items())}
    res["is_correct"] = dict(corr)
    res["how_inferred"] = {"|".join(k): v for k, v in sorted(hows.items())}
    # b. partner's script, unchanged
    out = subprocess.run([sys.executable, SPA, plain], capture_output=True, text=True)
    res["b_sources_provenance"] = {"returncode": out.returncode, "stderr_tail": out.stderr[-1500:]}
    slot, mode = parse_spa(out.stdout)
    res["b_sources_provenance"]["slot_determined"] = slot
    res["b_sources_provenance"]["mode_share"] = mode
    open(os.path.join(tmp, f"{ds}.spa.txt"), "w").write(out.stdout)
    # c. text match
    tm = {}
    for f, c in per_fw.items():
        if c["steps_with_inputs"]:
            tot = c["src_text_match"] + c["src_protocol"]
            tm[f] = {"steps_with_inputs": c["steps_with_inputs"],
                     "share_steps_zero_sources": round(c["steps_with_inputs_zero_sources"] / c["steps_with_inputs"], 4),
                     "sources_total": tot, "share_sources_text_match": round(c["src_text_match"] / tot, 4) if tot else None}
    res["c_text_match"] = tm
    # d. MAA exclusion
    out = subprocess.run([sys.executable, "-m", "data_tools.maa_exclusion", "check",
                          "docs/interfaces/maa_exclusion_v1.json", plain], capture_output=True, text=True, cwd=ROOT)
    res["d_maa_exclusion"] = {"stdout": out.stdout.strip(), "returncode": out.returncode, "stderr_tail": out.stderr[-500:]}
    m = re.search(r"(\d+) distinct queries; exact matches (\d+); probe candidates (\d+)", out.stdout)
    if m:
        res["d_maa_exclusion"].update(distinct_queries=int(m.group(1)), exact=int(m.group(2)), probe=int(m.group(3)))
    # e. tokens
    res["e_tokens"] = {"llm_output_o200k": sum(c["tok_llm_output_o200k"] for c in per_fw.values()),
                       "tool_output_o200k": sum(c["tok_tool_output_o200k"] for c in per_fw.values()),
                       "query_plus_step_outputs_qwen3_8b": qtok}
    # f. determinism
    if rerun:
        tmp_out = os.path.join(tmp, f"{ds}.rerun.jsonl.gz")
        out = subprocess.run([sys.executable, "-m", f"data_tools.public_to_mas_traj.{MODULE[ds]}", "--out", tmp_out],
                             capture_output=True, text=True, cwd=ROOT)
        res["f_determinism"] = {"rerun_returncode": out.returncode, "identical": out.returncode == 0 and sha(tmp_out) == res["sha256"]}
        for p in (tmp_out, tmp_out.replace(".jsonl.gz", "") + ".convert_report.json"):
            if os.path.exists(p):
                os.remove(p)
    rep = os.path.join(data_dir, f"{ds}.convert_report.json")
    res["convert_report"] = json.load(open(rep)) if os.path.exists(rep) else None
    os.remove(plain)
    return res


def trunc(x, k=300):
    if isinstance(x, str):
        return x if len(x) <= k else x[:k] + f"...[+{len(x) - k} chars]"
    if isinstance(x, list):
        return [trunc(v, k) for v in x[:12]] + ([f"...[+{len(x) - 12} items]"] if len(x) > 12 else [])
    if isinstance(x, dict):
        return {a: trunc(b, k) for a, b in x.items()}
    return x


def samples(ds, data_dir, out_dir, k=2):
    """two example records: the first record and the first one of a different framework (else the last)."""
    recs, first = [], None
    last = None
    for r in read_jsonl_gz(os.path.join(data_dir, f"{ds}.jsonl.gz")):
        if first is None:
            first = r
        elif r["framework"] != first["framework"] and len(recs) == 0:
            recs = [first, r]
            break
        last = r
    if not recs:
        recs = [first, last] if last else [first]
    os.makedirs(out_dir, exist_ok=True)
    json.dump([trunc(r) for r in recs], open(os.path.join(out_dir, f"{ds}.json"), "w"), indent=1, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", nargs="+", required=True)
    ap.add_argument("--data", default="/home/claude/public_mas/mas_traj")
    ap.add_argument("--tmp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--samples", default="analysis/public_mas_corpus/samples_r57")
    ap.add_argument("--no-rerun", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.tmp, exist_ok=True)
    tok = qwen()
    allres = json.load(open(a.out)) if os.path.exists(a.out) else {}
    for ds in a.datasets:
        print("validating", ds, flush=True)
        allres[ds] = validate(ds, a.data, a.tmp, tok, rerun=not a.no_rerun)
        samples(ds, a.data, a.samples)
        r = allres[ds]
        print(json.dumps({"a": r["a_check"], "d": {k: r["d_maa_exclusion"].get(k) for k in ("exact", "probe")},
                          "e": r["e_tokens"], "f": r.get("f_determinism")}, default=str), flush=True)
        json.dump(allres, open(a.out, "w"), indent=1, sort_keys=True, default=str)


if __name__ == "__main__":
    main()
