"""Audit of the public TracerTraj release (AgenTracer data-v1.0.0) before any use (round 71).

  python tracertraj_audit.py --root <agentracer-data-v1.0.0> --oat <patched OAT dir> [--out audit.json]

1. sha256 of every file vs MANIFEST.json.
2. Schema / label sanity: mistake_step is an int index into history (index convention inferred per file: 1-indexed if
   it is never 0 and sometimes equals len(history) -- the agentic split); mistake_agent equals that step's name; counts of
   error_source values (agentic) and of history lengths.
3. Overlap with our held-out E3 sets (Who&When 184, TraceElephant groupchat 174, loaded with OAT's loader):
   exact normalised question match, and exact match of any normalised history step text (>= 200 chars) — reported per
   split and domain. Train <-> test overlap inside TracerTraj (question).
4. Trivial step-level baselines on every split (the papers' metric, exact index match): random (1/n), first step,
   longest step (characters), last step; agent-level: most frequent agent, agent of the longest step.
"""
import argparse, glob, hashlib, json, os, re, sys
from collections import Counter

norm = lambda s: re.sub(r"\s+", " ", (s or "").strip().lower())


def content(h):
    c = h.get("content")
    return c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root"); ap.add_argument("--oat"); ap.add_argument("--out", default=None)
    a = ap.parse_args(); R = {"sha256": {}, "splits": {}, "overlap_e3": {}, "baselines": {}}
    man = json.load(open(os.path.join(a.root, "MANIFEST.json")))
    for f in man["files"]:
        h = hashlib.sha256(open(os.path.join(a.root, f["path"]), "rb").read()).hexdigest()
        R["sha256"][f["path"]] = h == f["sha256"]
    sys.path.insert(0, a.oat); cwd = os.getcwd(); os.chdir(a.oat)
    import data_pipeline as dp
    E3q, E3s = {}, {}
    for ds in ("who_and_when", "traceelephant_gc"):
        for t in dp.load_raw_trajectories(ds):
            E3q.setdefault(norm(t.get("question")), set()).add((ds, t["id"]))
            for b, e in t["step_char_boundaries"]:
                s = norm(t["text"][b:e])
                if len(s) >= 200: E3s.setdefault(s, set()).add((ds, t["id"]))
    os.chdir(cwd)
    trq = {}
    paths = sorted(glob.glob(os.path.join(a.root, "*", "*.jsonl")), key=lambda p: (p.split(os.sep)[-2], not p.endswith("train.jsonl")))
    for path in paths:   # train before test, so the test -> train question overlap check sees the train questions
        dom, split = path.split(os.sep)[-2], os.path.basename(path)[:-6]; key = f"{dom}/{split}"
        rows = [json.loads(l) for l in open(path)]
        # index convention, inferred from the labels: 1-indexed if mistake_step is never 0 and sometimes == len(history)
        ms = [int(r["mistake_step"]) for r in rows]
        off = 1 if min(ms) >= 1 and any(int(r["mistake_step"]) == len(r["history"]) for r in rows) else 0
        R.setdefault("index_offset", {})[key] = off
        st = Counter(); hl = []; qhit, shit, e3hit = 0, 0, set(); bl = Counter()
        for r in rows:
            h = r["history"]; n = len(h); hl.append(n)
            try: m = int(r["mistake_step"]) - off
            except Exception: st["mistake_step_not_int"] += 1; continue
            if not 0 <= m < n: st["mistake_step_out_of_range"] += 1; continue
            nm = lambda i: norm(h[i].get("name") or h[i].get("role"))
            st["agent_matches_step_name"] += nm(m) == norm(r.get("mistake_agent"))
            if "error_source" in r: st["error_source=" + str(r["error_source"])] += 1
            q = norm(r.get("question"))
            if split == "train": trq.setdefault(dom, set()).add(q)
            elif q in trq.get(dom, set()): st["question_also_in_train"] += 1
            if q in E3q: qhit += 1; e3hit |= E3q[q]
            if any(norm(content(x)) in E3s for x in h if len(norm(content(x))) >= 200): shit += 1
            ln = [len(content(x)) for x in h]
            bl["n"] += 1; bl["step_random"] += 1 / n; bl["step_first"] += m == 0; bl["step_last"] += m == n - 1
            lm = max(range(n), key=lambda i: ln[i]); bl["step_longest"] += m == lm
            cnt = Counter(nm(i) for i in range(n)); ag = norm(r.get("mistake_agent"))
            bl["agent_most_frequent"] += cnt.most_common(1)[0][0] == ag; bl["agent_of_longest_step"] += nm(lm) == ag
        hl.sort()
        R["splits"][key] = {"rows": len(rows), **dict(st), "history_len_median": hl[len(hl) // 2] if hl else None,
                            "history_len_max": hl[-1] if hl else None}
        R["overlap_e3"][key] = {"question_match_rows": qhit, "step_text_match_rows": shit,
                                "e3_trajectories_hit": sorted(f"{d}:{i}" for d, i in e3hit)[:50], "e3_trajectories_hit_n": len(e3hit)}
        R["baselines"][key] = {k: (v / bl["n"] if k != "n" else v) for k, v in bl.items()}
    print(json.dumps(R, indent=1))
    if a.out: json.dump(R, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
