"""TracerTraj public release (AgenTracer data-v1.0.0) -> Who&When-format folders for the OAT loader (E4, round 73).

  python tracertraj_to_ww.py --root <agentracer-data-v1.0.0> --out <dir> [--val_frac 0.1 --seed 0]

Output: <out>/{train,val,test}/Algorithm-Generated/<i>.json with {question, history[{name, role, content}], mistake_step
(0-indexed), mistake_agent, domain, question_ID, error_source} + <out>/manifest.json.
Rules (pre-registration E4 v1):
- index convention per file as audited (agentic 1-indexed -> minus 1; coding / math 0-indexed);
- test rows whose normalised question also occurs in train are dropped from test (21 math, 1 agentic) and listed;
- val = a fixed random fraction of train **by question** (all rows of a question go to the same side), for model selection;
- history names: `name` if present, else `role` (agentic: "assistant" everywhere); every step is a model step for OAT's
  Algorithm-Generated rule (no "Computer_terminal" names occur).
"""
import argparse, json, os, random, re
from collections import Counter

norm = lambda s: re.sub(r"\s+", " ", (s or "").strip().lower())


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root"); ap.add_argument("--out")
    ap.add_argument("--val_frac", type=float, default=0.1); ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(); man = {"dropped_test_question_in_train": [], "counts": Counter()}
    data = {}
    for dom in ("agentic", "coding", "math"):
        for split in ("train", "test"):
            rows = [json.loads(l) for l in open(os.path.join(a.root, dom, f"{split}.jsonl"))]
            off = 1 if dom == "agentic" else 0
            data[(dom, split)] = [(r, int(r["mistake_step"]) - off) for r in rows]
    trainq = {dom: {norm(r["question"]) for r, _ in data[(dom, "train")]} for dom in ("agentic", "coding", "math")}
    allq = sorted({(dom, q) for dom in trainq for q in trainq[dom]}); rng = random.Random(a.seed); rng.shuffle(allq)
    valq = set(allq[: int(round(a.val_frac * len(allq)))])
    outs = {"train": [], "val": [], "test": []}
    for (dom, split), rows in sorted(data.items()):
        for k, (r, m) in enumerate(rows):
            assert 0 <= m < len(r["history"]), (dom, split, k)
            q = norm(r["question"])
            if split == "test" and q in trainq[dom]:
                man["dropped_test_question_in_train"].append(f"{dom}/test/{k}"); continue
            dst = "test" if split == "test" else ("val" if (dom, q) in valq else "train")
            hist = [{"name": h.get("name") or h.get("role") or "assistant", "role": h.get("role") or "assistant",
                     "content": h.get("content") if isinstance(h.get("content"), str) else json.dumps(h.get("content"), ensure_ascii=False)}
                    for h in r["history"]]
            outs[dst].append({"question": r["question"], "history": hist, "mistake_step": m, "mistake_agent": r.get("mistake_agent", ""),
                              "domain": dom, "question_ID": r.get("question_ID"), "error_source": r.get("error_source"),
                              "source_row": f"{dom}/{split}/{k}"})
    for dst, recs in outs.items():
        d = os.path.join(a.out, dst, "Algorithm-Generated"); os.makedirs(d, exist_ok=True)
        for i, rec in enumerate(recs):
            json.dump(rec, open(os.path.join(d, f"{i}.json"), "w"), ensure_ascii=False)
            man["counts"][f"{dst}/{rec['domain']}"] += 1
    man["counts"] = dict(man["counts"]); man["args"] = vars(a)
    json.dump(man, open(os.path.join(a.out, "manifest.json"), "w"), indent=1)
    print(json.dumps(man["counts"]), "dropped", len(man["dropped_test_question_in_train"]))


if __name__ == "__main__":
    main()
