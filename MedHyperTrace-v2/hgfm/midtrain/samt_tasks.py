"""Structure-aware mid-training (SAMT v1, round 64): question rows whose answers are carried by graph tokens.

Design: docs/design/SAMT_design_v1.md. The LLM is frozen; only the HGFM v0.2 encoder and the projector are trained, so the
LLM can only get the answer through the <graph> tokens (alignment stage, GraphGPT / LLaVA stage-1 style).
Prompt layout follows hgfm/llm/build_sft.py (task, final answer, <= K step lines "[sid] agent | phase | round r <graph>"
+ excerpt, <= M event lines "<graph> instr" incident to the target, question); the answer is short, loss on it only.

Objectives (answers never appear in the visible text):
  O1 match    4 steps of the run show "excerpt: [hidden]"; their 4 excerpts are given as options A-D; which one is
              step [t]'s?  Distractors: same run, preferring the same agent, then the same phase_canonical.
  O2 sources  which of the listed steps did [t] read?  Only for keys (dataset, framework, phase_canonical) whose source
              pattern {(phase_canonical, offset)} is not near-deterministic (top share < --det, C5 rule), and the
              candidates are the earlier steps whose phase_canonical occurs among the true sources (so the phase alone
              cannot solve it); needs >= 1 distractor.
  O3 readers  which of the listed steps read [t]'s output?  Same filter, mirrored (later steps).
  O4 answer   [t]'s excerpt is hidden; which option did it answer?  Only runs with structured answers (anchors).
Corpus rules = the TAPT pilot (round 62): public mas-traj/1 + medical-aegis anchor NORMAL runs; no MAA; family
`groupchat` excluded; MAA exclusion list v1; ids deduplicated. Held-out runs (md5(run_id) < --heldout, default 5%) only go to
probe.jsonl (pre-SFT check: real vs shuffled vs zeroed graph tokens).
Outputs (in --out): train.jsonl (swift rows: messages, run_id, graph_refs JSON string), probe.jsonl (same + obj,
dataset, answer), runs.jsonl.gz (trimmed runs for samt_featurise.py), stats.json.
Usage: python -m hgfm.midtrain.samt_tasks --public_dir /home/claude/public_mas/mas_traj --anchor a.jsonl.gz ... --out DIR
"""
import argparse, collections, gzip, hashlib, json, os, random, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from data_tools.maa_exclusion import norm_stem   # noqa: E402
from data_tools.public_to_mas_traj.common import add_phase_canonical   # noqa: E402
from hgfm.data_v02 import edges_of   # noqa: E402
from hgfm.midtrain.build_corpus import read   # noqa: E402

SYSTEM = ("You read the execution trace of a multi-agent system. Each listed step and interaction event carries a graph "
          "token that summarises it and its position in the interaction hypergraph.")
LET = "ABCD"


def excerpt(s, n=400):
    return " ".join((s.get("output") or "").split())[:n]


def step_line(s, hidden=False, n=400):
    line = f"[{s['step_id']}] {s['agent_id']} | {s['phase']} | round {s['round']} <graph>"
    return line + ("\n    excerpt: [hidden]" if hidden else "\n    excerpt: " + excerpt(s, n))


def is_heldout(run_id, frac):
    return int(hashlib.md5(run_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < frac


class Builder:
    def __init__(self, a):
        self.a = a

    def prompt(self, r, E, listed, hidden, target, question):
        """listed: step indices (sorted); hidden: set of indices with hidden excerpt; target: index for incident events."""
        st = r["steps"]; refs, lines = [], []
        for i in listed:
            lines.append(step_line(st[i], i in hidden)); refs.append(["node", i])
        ev = [k for k, e in enumerate(E) if any(v == target for v, _ in e["members"])][: self.a.M]
        elines = []
        for k in ev:
            elines.append("<graph> " + E[k]["instr"]); refs.append(["edge", k])
        head = f"Task:\n{(r['task'].get('query') or '').strip()[: self.a.q_chars]}"
        fa = (r.get("final") or {}).get("answer")
        if fa is not None:
            head += f"\n\nSystem's final answer: {fa}"
        user = (f"{head}\n\nTrajectory (selected steps):\n" + "\n".join(lines) +
                ("\n\nInteraction events around the target:\n" + "\n".join(elines) if elines else "") + f"\n\n{question}")
        assert user.count("<graph>") == len(refs)
        return user, refs

    def fill(self, base, k, rng, n_steps, exclude):
        """Add context steps (random, not in exclude) until k listed."""
        rest = [i for i in range(n_steps) if i not in base and i not in exclude]
        rng.shuffle(rest)
        return sorted(set(base) | set(rest[: max(0, k - len(base))]))

    # ------------------------------------------------------------------------------------------------ objectives
    def o1(self, r, E, rng):
        st = r["steps"]; n = len(st)
        ok = [i for i, s in enumerate(st) if s["kind"] == "llm" and len(excerpt(s, 300)) >= 40]
        if len(ok) < 4: return None
        t = rng.choice(ok); ex_t = excerpt(st[t], 300)
        pool = [i for i in ok if i != t and excerpt(st[i], 300) != ex_t]
        def pri(i):   # same agent first, then same canonical phase, then the rest; random within a tier
            return (0 if st[i]["agent_id"] == st[t]["agent_id"] else 1 if st[i].get("phase_canonical") == st[t].get("phase_canonical") else 2, rng.random())
        pool.sort(key=pri); d = []
        for i in pool:
            if excerpt(st[i], 300) not in {excerpt(st[j], 300) for j in d + [t]}: d.append(i)
            if len(d) == 3: break
        if len(d) < 3: return None
        opts = [t] + d; rng.shuffle(opts)
        listed = self.fill(opts, self.a.K, rng, n, set())
        q = ("Steps " + ", ".join(f"[{st[i]['step_id']}]" for i in sorted(opts)) + " have hidden excerpts. Their excerpts are:\n" +
             "\n".join(f"{LET[j]}. {excerpt(st[i], 300)}" for j, i in enumerate(opts)) +
             f"\nWhich excerpt belongs to step [{st[t]['step_id']}]? Answer with the letter only.")
        user, refs = self.prompt(r, E, listed, set(opts), t, q)
        return user, refs, LET[opts.index(t)]

    def o23(self, r, E, rng, keys, mode):
        st = r["steps"]; n = len(st); sid = {s["step_id"]: i for i, s in enumerate(st)}
        srcs = [sorted({sid[x["step_id"]] for x in (s.get("sources") or []) if x["step_id"] in sid and sid[x["step_id"]] < i}) for i, s in enumerate(st)]
        rdrs = collections.defaultdict(list)
        for i, ss in enumerate(srcs):
            for j in ss: rdrs[j].append(i)
        ds = r["_ds"]; cands = []
        for t in range(n):
            true = srcs[t] if mode == "src" else sorted(rdrs[t])
            if not true or len(true) > self.a.K - 2: continue
            if (ds, r["framework"], st[t].get("phase_canonical")) not in keys: continue
            ph = {st[j].get("phase_canonical") for j in true}
            side = range(t) if mode == "src" else range(t + 1, n)
            c = [j for j in side if st[j].get("phase_canonical") in ph]
            if len(c) > len(true): cands.append((t, true, c))
        if not cands: return None
        t, true, c = rng.choice(cands)
        dis = [j for j in c if j not in true]; rng.shuffle(dis)
        listed = sorted(set([t] + true + dis[: max(1, self.a.K - 1 - len(true))]))
        listed = self.fill(listed, self.a.K, rng, n, set(range(t)) | set(c) if mode == "src" else set(range(t + 1, n)) | set(c))
        q = (f"Which of the listed steps did step [{st[t]['step_id']}] read (use as input)? List their ids in order, comma-separated."
             if mode == "src" else
             f"Which of the listed steps read the output of step [{st[t]['step_id']}]? List their ids in order, comma-separated.")
        user, refs = self.prompt(r, E, listed, set(), t, q)
        return user, refs, ", ".join(st[j]["step_id"] for j in true)

    def o4(self, r, E, rng):
        st = r["steps"]; n = len(st)
        ok = [i for i, s in enumerate(st) if (s.get("structured") or {}).get("answer") is not None]
        if not ok: return None
        t = rng.choice(ok)
        listed = self.fill([t], self.a.K, rng, n, set())
        q = f"Step [{st[t]['step_id']}] has a hidden excerpt. Which option did it give as its answer? Answer with the option only."
        user, refs = self.prompt(r, E, listed, {t}, t, q)
        return user, refs, str(st[t]["structured"]["answer"])


def pattern_keys(runs, det):
    """(dataset, framework, phase_canonical) keys whose source / reader pattern is not near-deterministic."""
    out = {}
    for mode in ("src", "rdr"):
        pat = collections.defaultdict(collections.Counter)
        for r in runs:
            st = r["steps"]; sid = {s["step_id"]: i for i, s in enumerate(st)}
            srcs = [sorted({sid[x["step_id"]] for x in (s.get("sources") or []) if x["step_id"] in sid and sid[x["step_id"]] < i}) for i, s in enumerate(st)]
            rd = collections.defaultdict(list)
            for i, ss in enumerate(srcs):
                for j in ss: rd[j].append(i)
            for t, s in enumerate(st):
                m = srcs[t] if mode == "src" else rd[t]
                if m:
                    pat[(r["_ds"], r["framework"], s.get("phase_canonical"))][tuple(sorted((st[j].get("phase_canonical"), j - t) for j in m))] += 1
        out[mode] = {k for k, c in pat.items() if c.most_common(1)[0][1] / sum(c.values()) < det}
    return out


def trim(r):
    keep = ("run_id", "framework", "framework_family", "framework_description", "question_id", "task", "final")
    o = {k: r.get(k) for k in keep}
    o["task"] = {"query": (r["task"].get("query") or ""), "dataset": r["task"].get("dataset")}
    o["steps"] = [{"step_id": s["step_id"], "agent_id": s["agent_id"], "agent_role": s.get("agent_role"), "phase": s["phase"],
                   "phase_canonical": s.get("phase_canonical"), "round": s.get("round"), "kind": s["kind"],
                   "output": (s.get("output") or "")[:2000],
                   "sources": [{"step_id": x["step_id"], "how": x.get("how")} for x in (s.get("sources") or [])],
                   "structured": {k: v for k, v in (s.get("structured") or {}).items() if k in ("answer", "agree")}} for s in r["steps"]]
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--public_dir"); ap.add_argument("--anchor", nargs="*", default=[]); ap.add_argument("--out")
    ap.add_argument("--exclude_families", nargs="*", default=["groupchat"])
    ap.add_argument("--maa_exclusion", default=os.path.join(os.path.dirname(__file__), "..", "..", "docs", "interfaces", "maa_exclusion_v1.json"))
    ap.add_argument("--K", type=int, default=10); ap.add_argument("--M", type=int, default=4); ap.add_argument("--q_chars", type=int, default=1500)
    ap.add_argument("--det", type=float, default=0.9); ap.add_argument("--heldout", type=float, default=0.05)
    ap.add_argument("--n", nargs=4, type=int, default=[9000, 6000, 6000, 3000], help="target train rows for O1 O2 O3 O4")
    ap.add_argument("--max_ds_share", type=float, default=0.35, help="max share of one dataset in each objective")
    ap.add_argument("--o4_per_run", type=int, default=3); ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); rng = random.Random(a.seed)
    excl = json.load(open(a.maa_exclusion)); maa = {e["norm_stem"]: e for e in excl["entries"]}
    runs, seen, st = [], set(), collections.defaultdict(collections.Counter)
    srcs = [(os.path.basename(p).split(".")[0], p) for p in sorted(__import__("glob").glob(os.path.join(a.public_dir, "*.jsonl.gz")))]
    srcs += [("anchor", p) for p in a.anchor]
    for ds0, p in srcs:
        for r in read(p):
            if ds0 == "anchor":
                if r["run_mode"] != "normal": continue
                r = add_phase_canonical(r); ds = "anchor_" + r["framework"]
            else:
                ds = ds0
            if r["run_id"] in seen: continue
            seen.add(r["run_id"]); st[ds]["runs_in"] += 1
            if r["framework_family"] in a.exclude_families: st[ds]["excluded_family"] += 1; continue
            e = maa.get(norm_stem(r["task"].get("query") or ""))
            if e and (not e["images"] or set(e["images"]) & set(r["task"].get("images") or [])): st[ds]["excluded_maa"] += 1; continue
            r = trim(r); r["_ds"] = ds; runs.append(r)
    keys = pattern_keys(runs, a.det)
    B = Builder(a); objs = {"O1": lambda r, E: B.o1(r, E, rng), "O2": lambda r, E: B.o23(r, E, rng, keys["src"], "src"),
                            "O3": lambda r, E: B.o23(r, E, rng, keys["rdr"], "rdr"), "O4": lambda r, E: B.o4(r, E, rng)}
    by_ds = collections.defaultdict(list)
    for r in runs: by_ds[r["_ds"]].append(r)
    for v in by_ds.values(): rng.shuffle(v)
    train, probe, used = [], [], set()
    for oi, (o, f) in enumerate(objs.items()):
        target = a.n[oi]; cap = int(a.max_ds_share * target) if len(by_ds) > 2 else target
        rows_o = collections.Counter()
        # round-robin over datasets so small datasets are not crowded out
        it = {d: iter(v) for d, v in by_ds.items()}; active = sorted(it)
        while active and sum(rows_o.values()) < target:
            for d in list(active):
                r = next(it[d], None)
                if r is None or rows_o[d] >= cap: active.remove(d); continue
                E = edges_of(r); reps = a.o4_per_run if o == "O4" else 1
                for _ in range(reps):
                    res = f(r, E)
                    if res is None: break
                    user, refs, ans = res
                    row = {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}, {"role": "assistant", "content": ans}],
                           "run_id": r["run_id"], "graph_refs": json.dumps(refs)}
                    used.add(r["run_id"])
                    if is_heldout(r["run_id"], a.heldout):
                        probe.append({**row, "obj": o, "dataset": d, "answer": ans}); st[d][f"{o}_probe"] += 1
                    else:
                        train.append(row); rows_o[d] += 1; st[d][f"{o}_train"] += 1
        print(o, "train rows", sum(rows_o.values()), dict(rows_o), flush=True)
    rng.shuffle(train)
    with open(os.path.join(a.out, "train.jsonl"), "w") as fo:
        for row in train: fo.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(os.path.join(a.out, "probe.jsonl"), "w") as fo:
        for row in probe: fo.write(json.dumps(row, ensure_ascii=False) + "\n")
    with gzip.open(os.path.join(a.out, "runs.jsonl.gz"), "wt", encoding="utf-8") as fo:
        for r in runs:
            if r["run_id"] in used: fo.write(json.dumps({k: v for k, v in r.items() if k != "_ds"}, ensure_ascii=False) + "\n")
    stats = {"datasets": {k: dict(v) for k, v in st.items()}, "n_train": len(train), "n_probe": len(probe), "runs_used": len(used),
             "nondeterministic_keys": {m: len(v) for m, v in keys.items()}, "args": vars(a)}
    json.dump(stats, open(os.path.join(a.out, "stats.json"), "w"), indent=1)
    print("train", len(train), "probe", len(probe), "runs", len(used), "keys", stats["nondeterministic_keys"])


if __name__ == "__main__":
    main()
