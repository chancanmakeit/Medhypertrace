"""Recover pre-injection (clean) input_messages for prompt_injection steps in the
AEGIS-custom-dataset-8-13 records (round 24).

Why: recorded `input_messages` of prompt_injection steps contain the injected
instruction text (label leak). Recovery per framework, verified on 8-13:
  - dylan / llm_debate: step carries `original_input_messages`.
  - mdagents / clinical_agent / clinical_agent5: `injection_log.raw_history[*]`
    carries `modified_prompt` (== the user message actually sent) and
    `original_prompt`; substitute the latter for the former.
  - llm_debate Aggregator: flagged prompt_modified but recorded input carries no
    injected text and no injected_input_messages -> recorded input is already clean.
The old marker-truncation idea ('[UPDATED INSTRUCTION FOR') only covers the
direct_prepend+direct configs (16-50% of PI steps); this covers 100%.
"""
from typing import Any

def _n(s: Any) -> str:
    return " ".join(str(s).split())

def clean_input_messages(step: dict, raw_history: list) -> tuple[list, bool]:
    """Return (clean_messages, ok). ok=False means a modified step could not be repaired."""
    im = step.get("input_messages") or []
    if not step.get("prompt_modified"):
        return im, True
    if step.get("original_input_messages"):
        return step["original_input_messages"], True
    if "original_input_messages" in step and not step.get("injected_input_messages"):
        # llm_debate Aggregator: modification planned but nothing injected into the
        # recorded input (checked on 8-13: 876/876 contain no injection text).
        return im, True
    for r in raw_history or []:
        mp = r.get("modified_prompt")
        if not (r.get("prompt_modified") and mp):
            continue
        hit = [i for i, m in enumerate(im) if isinstance(m.get("content"), str) and _n(m["content"]) == _n(mp)]
        if hit:
            out = [dict(m) for m in im]
            for i in hit:
                out[i]["content"] = r["original_prompt"]
            return out, True
    return im, False

if __name__ == "__main__":
    import glob, json, os, sys
    for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.jsonl"))):
        n = ok = leak = 0
        for l in open(f):
            lg = json.loads(l)["injection_log"]
            for s in lg["conversation_history"]:
                if not s.get("prompt_modified"):
                    continue
                n += 1
                msgs, good = clean_input_messages(s, lg.get("raw_history"))
                ok += good
                t = (s.get("injection_process") or {}).get("instruction_template", "")[:50]
                txt = _n(" ".join(m["content"] if isinstance(m.get("content"), str) else json.dumps(m.get("content")) for m in msgs))
                leak += bool(t) and t in txt
        print(f"{os.path.basename(f)}: PI steps={n} repaired={ok} template_left={leak}")
