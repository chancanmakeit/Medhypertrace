"""Round 75: does step length predict flips in the medical-aegis branching pilot (2026-10-26)? Offline, no API.

  python branch_length_audit.py --aegis /home/claude/medical-aegis --pilot <dir with branch_pilot/*_candidates.jsonl>

For every pilot point (aggregator excluded, as in the data side's report): original step text = the step in the
control replay (same t, not resampled), resampled text = the step in the branch run; flip = branch final letter !=
control final letter. Reports flip AUROC of: original length, resampled length, length difference, |difference|,
and whether the resampled step's letter differs from the original (characters; whitespace-trimmed).
"""
import argparse, gzip, json, os, sys


def auroc(s, y):
    pos = [a for a, b in zip(s, y) if b]; neg = [a for a, b in zip(s, y) if not b]
    if not pos or not neg: return float("nan")
    return sum(1 if p > n else 0.5 if p == n else 0 for p in pos for n in neg) / (len(pos) * len(neg))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--aegis"); ap.add_argument("--pilot"); a = ap.parse_args()
    sys.path.insert(0, os.path.join(a.aegis, "scripts"))
    from branch_pilot import letter, llm_steps
    runs = os.path.join(a.aegis, "data_runs", "branch_pilot_2026-10-26"); pts = []
    for fw in ("llm_debate", "mdagents"):
        cands = [json.loads(l) for l in open(os.path.join(a.pilot, f"{fw}_candidates.jsonl"))]
        for p in (0, 1, 2):
            fb, fc = (os.path.join(runs, f"{fw}_p{p}_{arm}_rep0_out.jsonl.gz") for arm in ("branch", "control"))
            if not os.path.exists(fb): continue
            B = {r["id"]: r for r in map(json.loads, gzip.open(fb, "rt", encoding="utf-8"))}
            Cc = {r["id"]: r for r in map(json.loads, gzip.open(fc, "rt", encoding="utf-8"))}
            for x in cands:
                if x["pass"] != p or x["qid"] not in B or x["qid"] not in Cc or str(x["phase"]).startswith("aggregation"): continue
                hb, hc = llm_steps(B[x["qid"]]), llm_steps(Cc[x["qid"]]); t = x["t"]
                o, n = (hc[t].get("content") or "").strip(), (hb[t].get("content") or "").strip()
                pts.append({"fw": fw, "qid": x["qid"], "t": t, "len_orig": len(o), "len_new": len(n),
                            "letter_changed": letter(o) != letter(n),
                            "flip": letter(B[x["qid"]].get("response")) != letter(Cc[x["qid"]].get("response"))})
    y = [q["flip"] for q in pts]
    print(f"points {len(pts)}, flips {sum(y)}")
    for name, f in (("orig length", lambda q: q["len_orig"]), ("resampled length", lambda q: q["len_new"]),
                    ("resampled - orig", lambda q: q["len_new"] - q["len_orig"]), ("|resampled - orig|", lambda q: abs(q["len_new"] - q["len_orig"])),
                    ("letter changed", lambda q: float(q["letter_changed"]))):
        print(f"AUROC {name:20s} {auroc([f(q) for q in pts], y):.3f}")
    for fw in ("llm_debate", "mdagents"):
        sub = [q for q in pts if q["fw"] == fw]
        med = lambda v: sorted(v)[len(v) // 2] if v else None
        print(fw, f"n={len(sub)} flips={sum(q['flip'] for q in sub)}",
              "median len orig/new (flip):", med([q["len_orig"] for q in sub if q["flip"]]), med([q["len_new"] for q in sub if q["flip"]]),
              "(no flip):", med([q["len_orig"] for q in sub if not q["flip"]]), med([q["len_new"] for q in sub if not q["flip"]]),
              "letter changed among flips / non-flips:", sum(q["letter_changed"] for q in sub if q["flip"]), "/", sum(q["letter_changed"] for q in sub if not q["flip"]))


if __name__ == "__main__":
    main()
