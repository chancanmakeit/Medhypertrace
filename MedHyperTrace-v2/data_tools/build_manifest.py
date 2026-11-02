"""Stage 0 Q4 (pre-registration docs/design/Stage0_prereg_v1.md): question-grouped manifest + benchmark audit table.

Grouping rule (round 75): word set = re.findall('[a-z0-9]+', question.lower()); two questions are linked when the word-set
Jaccard >= 0.3 (also reported at 0.5 / 0.7); groups = connected components (union-find). Identical word sets share one
node; empty questions stay singletons. Candidate pairs come from an AllPairs prefix filter (exact, no approximation).

Items: Who&When 184 and TraceElephant groupchat (OAT loader ids), TracerTraj tt_ww train / val / test (by domain), every
public mas-traj/1 run (by dataset), every medical-aegis anchor NORMAL run, and the 600 MAA questions. MAA stems exist only
in the sandbox, so `maa-edges` (sandbox) writes the MAA <-> anchor and MAA <-> MAA links (stem vs stem, both cut with
data_tools.maa_exclusion.norm_stem) and `build` adds them; MAA is compared with anchors and itself only (medical stems; no
non-medical set is compared with MAA).
Training sources: corpora tapt / S / R / full (rows {"dataset","run_id"} -> mas-traj runs; text-only rows, e.g. the TAPT
training file, are resolved through their chunk header = question level; NC_shuf = R's runs, NC_irr has no MAS question), TracerTraj train / val, each public dataset (traceelephant without its groupchat family = the evaluation
set; who_and_when is the evaluation set itself), anchors.
Overlap of an evaluation item with a source: "group" = the item's component (prereg rule) contains a member of the
source; "direct" = some member of the source has Jaccard >= thr with the item itself (round-75 / eval_overlap_filter rule).

Audit (needs e4 feats_base.pt step metadata): candidates = model steps (index >= 1, step_is_model), label = mistake_step
+ 1; evaluable = label among candidates and >= 2 candidates (as E4). Trivial baselines with hgfm.e4.e4_eval (raw and
controlled), so the numbers are comparable with results/e4/README.md.

Usage:
  # sandbox: MAA links (needs docs/interfaces/maa_exclusion_v1.json and the anchor exports)
  python -m data_tools.build_manifest maa-edges --maa_exclusion docs/interfaces/maa_exclusion_v1.json \
      --anchor anchor_export_4fw.jsonl.gz [...] --out maa_edges.json
  # Linux #2
  python -m data_tools.build_manifest build --oat <mht_work/e1e3/oat_src> --tt_ww <mht_work/e4/tt_ww> \
      --feats <mht_work/e4/feats_base.pt> --public_dir <mas_traj> --anchor <anchor normal runs .jsonl.gz> \
      --maa_edges maa_edges.json --corpus tapt=<tapt.jsonl> S=<S.jsonl> R=<R.jsonl> full=<full.jsonl> --out <dir>
Outputs (build): overlap.json, eval_clean_keys.json, audit.json, manifest.jsonl.gz (all groups),
manifest_eval.jsonl.gz (groups with >= 1 evaluation item), build.log.
"""
import argparse, bisect, glob, gzip, json, math, os, re, sys, time
from collections import Counter, defaultdict

WORD = re.compile(r"[a-z0-9]+")
THRS = (0.3, 0.5, 0.7)
EVAL_SETS = ("WW", "WW_HC", "WW_AG", "TEgc", "WW+TEgc", "TT_test", "TT_test_agentic", "TT_test_coding", "TT_test_math")
CLEAN_SOURCES = ("tapt", "S", "R", "full", "TT_train")


def words(q): return frozenset(WORD.findall((q or "").lower()))


def read(p):
    with (gzip.open if p.endswith(".gz") else open)(p, "rt", encoding="utf-8") as f:
        for l in f:
            if l.strip(): yield json.loads(l)


def allpairs(sets, thr):
    """All index pairs (i, j, jaccard) with jaccard >= thr; prefix filter on a rare-first global token order (exact)."""
    df = Counter(t for s in sets for t in s)
    order = sorted(range(len(sets)), key=lambda i: (len(sets[i]), i))
    index = defaultdict(list); isz = defaultdict(list); out = []   # posting lists in increasing set size (processing order)
    for i in order:
        s = sets[i]; n = len(s)
        if not n: continue
        lo = math.ceil(thr * n - 1e-9); p = n - lo + 1      # size filter |s_j| >= thr*|s_i|; prefix length
        toks = sorted(s, key=lambda t: (df[t], t))[:p]
        cand = set()
        for t in toks:
            cand.update(index[t][bisect.bisect_left(isz[t], lo):])
        for j in cand:
            inter = len(s & sets[j]); jac = inter / max(1, n + len(sets[j]) - inter)
            if jac >= thr: out.append((j, i, jac))
        for t in toks: index[t].append(i); isz[t].append(n)
    return out


class UF:
    def __init__(self, n): self.p = list(range(n))
    def find(self, x):
        while self.p[x] != x: self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b: self.p[max(a, b)] = min(a, b)


# ---------------------------------------------------------------- maa-edges (sandbox)
def cmd_maa_edges(a):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from data_tools.maa_exclusion import norm_stem
    ex = json.load(open(a.maa_exclusion))
    maa = [(e["question_id"], e.get("dataset"), frozenset(WORD.findall(e["norm_stem"]))) for e in ex["entries"]]
    anc = {}
    for p in a.anchor:
        for r in read(p):
            if r.get("run_mode") == "normal":
                q = r["task"].get("query") or ""; anc.setdefault(r["question_id"], (words(norm_stem(q)), words(q)))
    am = []
    for aq, (ws, wr) in sorted(anc.items()):
        for mq, _, mw in maa:
            js = len(ws & mw) / max(1, len(ws | mw)); jr = len(wr & mw) / max(1, len(wr | mw))
            if max(js, jr) >= a.thr: am.append([aq, mq, js, jr])
    mm = []
    for i, j, x in allpairs([m[2] for m in maa], a.thr):
        it = len(maa[i][2] & maa[j][2]); mm.append([i, j, it, len(maa[i][2]) + len(maa[j][2]) - it])   # Jaccard = inter / union
    out = {"rule": "anchor query and MAA stem both cut with maa_exclusion.norm_stem; word-set Jaccard; j_raw = uncut anchor query",
           "thr": a.thr, "maa": [[m[0], m[1]] for m in maa], "n_anchor_questions": len(anc), "anchor_maa": am,
           "maa_maa_idx": mm, "extra_exclusions": ex.get("extra_exclusions", [])}
    json.dump(out, open(a.out, "w")); print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in out.items()}))


# ---------------------------------------------------------------- build (Linux #2)
def load_items(a, log):
    """-> list of item dicts {src, split, id, q, ...}."""
    items = []
    sys.path.insert(0, a.oat); cwd = os.getcwd(); os.chdir(a.oat)
    import data_pipeline as dp
    for ds, nm in (("who_and_when", "WW"), ("traceelephant_gc", "TEgc")):
        for t in dp.load_raw_trajectories(ds):
            items.append({"src": nm, "split": t["id"].split("/")[0] if nm == "WW" else "", "id": t["id"], "key": f"{ds}|{t['id']}",
                          "q": t.get("question") or ""})
    os.chdir(cwd)
    for sp in ("train", "val", "test"):
        for f in sorted(glob.glob(os.path.join(a.tt_ww, sp, "*", "*.json"))):
            d = json.load(open(f)); rel = os.path.relpath(f, os.path.join(a.tt_ww, sp))
            items.append({"src": "TT", "split": sp, "dom": d.get("domain"), "id": rel, "key": f"tt_{sp}|{rel}", "q": d.get("question") or ""})
    for p in sorted(glob.glob(os.path.join(a.public_dir, "*.jsonl.gz"))):
        ds = os.path.basename(p).split(".")[0]
        for r in read(p):
            items.append({"src": "public", "split": ds, "fam": r.get("framework_family"), "id": r["run_id"], "ck": (ds, r["run_id"]),
                          "hk": (f"Task ({(r.get('task') or {}).get('dataset')}, framework {r['framework']}):", ((r.get("task") or {}).get("query") or "").strip()),
                          "q": (r.get("task") or {}).get("query") or ""})
    seen = set()
    for p in a.anchor:
        for r in read(p):
            if r.get("run_mode") != "normal" or r["run_id"] in seen: continue
            seen.add(r["run_id"])
            items.append({"src": "anchor", "split": r["framework"], "id": r["run_id"], "qid": r.get("question_id"),
                          "ck": ("anchor_" + r["framework"], r["run_id"]), "q": r["task"].get("query") or "",
                          "hk": (f"Task ({r['task'].get('dataset')}, framework {r['framework']}):", (r["task"].get("query") or "").strip())})
    log(f"items {Counter(i['src'] for i in items)}")
    return items


def source_names(it):
    s, sp = it["src"], it["split"]
    if s == "TT": return {f"TT_{sp}", "TT_trainfile"} if sp in ("train", "val") else {"TT_test"}
    if s == "public":
        if sp == "who_and_when" or (sp == "traceelephant" and it.get("fam") == "groupchat"): return set()
        return {"public_" + ("traceelephant_nongc" if sp == "traceelephant" else sp)}
    if s == "anchor": return {"anchors"}
    if s in ("WW", "TEgc"): return {s}
    return set()


def eval_sets_of(it):
    s = it["src"]
    if s == "WW": return {"WW", "WW_" + ("HC" if it["split"] == "Hand-Crafted" else "AG"), "WW+TEgc"}
    if s == "TEgc": return {"TEgc", "WW+TEgc"}
    if s == "TT" and it["split"] == "test": return {"TT_test", "TT_test_" + str(it.get("dom"))}
    return set()


def cmd_build(a):
    os.makedirs(a.out, exist_ok=True); t0 = time.time(); logf = open(os.path.join(a.out, "build.log"), "w")
    def log(m): s = f"[{time.time() - t0:7.1f}s] {m}"; print(s, flush=True); logf.write(s + "\n"); logf.flush()
    items = load_items(a, log)
    # corpus membership
    corp = {}; byck = {it["ck"]: k for k, it in enumerate(items) if "ck" in it}; cstats = {}
    byhk = defaultdict(list)
    for k, it in enumerate(items):
        if "hk" in it: byhk[it["hk"]].append(k)
    byline = defaultdict(set)
    for line, q in byhk: byline[line].add(q)
    def from_header(t):
        """Text-only corpus rows: the chunk header is 'Task (<task dataset>, framework <fw>):\n<query>\n\n[<step id>] ...'
        (build_corpus.py) -> all runs with that framework, task dataset and query (question-level membership)."""
        line, rest = t.split("\n", 1)
        for m in re.finditer(r"\n\n\[[^\]\n]+\] ", rest):
            ks = byhk.get((line, rest[:m.start()].strip()))
            if ks: return ks
        # fallback (chunks whose step text was cut away, e.g. very long queries): longest query that prefixes the text
        best = max((q for q in byline.get(line, ()) if rest.startswith(q + "\n")), key=len, default=None)
        return byhk[(line, best)] if best is not None else []
    for spec in a.corpus:
        nm, p = spec.split("=", 1); keys = set(); rows = 0; hdr = Counter(); unres = []
        for r in read(p):
            rows += 1
            if "run_id" in r:
                keys.add((r["dataset"], r["run_id"]))
                if "text" in r:   # validate the header rule on corpora that carry run ids
                    hdr["header_check_" + ("ok" if (r["dataset"], r["run_id"]) in {items[k]["ck"] for k in from_header(r["text"])} else "fail")] += 1
                continue
            ks = from_header(r["text"]); hdr["rows_by_header"] += 1
            if not ks: hdr["rows_unresolved"] += 1; unres.append(r["text"][:120]); continue
            for k in ks: keys.add(items[k]["ck"])
        miss = [k for k in keys if k not in byck]
        cstats[nm] = {"rows": rows, "runs": len(keys), "unmapped_runs": len(miss), "unmapped_examples": [list(k) for k in miss[:5]],
                      "runs_by_dataset": dict(Counter(k[0] for k in keys)), **dict(hdr), "unresolved_examples": unres[:3]}
        if hdr: cstats[nm]["membership"] = "question-level: text-only rows resolved through the chunk header; every run with the same framework, task dataset and query is marked"
        for k in keys:
            if k in byck: items[byck[k]].setdefault("corp", set()).add(nm)
        corp[nm] = keys; log(f"corpus {nm}: {rows} rows, {len(keys)} runs, {len(miss)} unmapped, {dict(hdr)}")
    for it in items:
        it["srcs"] = source_names(it) | it.get("corp", set()); it["evals"] = eval_sets_of(it)
    # nodes
    node_of = {}; nodes = []; item_node = []
    for k, it in enumerate(items):
        w = words(it["q"])
        if not w: nodes.append(w); item_node.append(len(nodes) - 1); continue   # empty question: own singleton node
        if w not in node_of: node_of[w] = len(nodes); nodes.append(w)
        item_node.append(node_of[w])
    n_text = len(nodes)
    mx = json.load(open(a.maa_edges)) if a.maa_edges else None
    maa_node = {}
    if mx:
        for qid, ds in mx["maa"]:
            maa_node[qid] = len(nodes); nodes.append(None)
            items.append({"src": "MAA", "split": ds, "id": qid, "q": None, "srcs": {"MAA"}, "evals": set()}); item_node.append(maa_node[qid])
    log(f"nodes: {n_text} text nodes ({sum(1 for w in nodes[:n_text] if not w)} empty) + {len(maa_node)} MAA; items {len(items)}")
    edges = allpairs(nodes[:n_text], min(THRS)); log(f"text edges >= {min(THRS)}: {len(edges)}")
    if mx:
        anc_node = {}
        for k, it in enumerate(items):
            if it["src"] == "anchor": anc_node.setdefault(it["qid"], item_node[k])
        for aq, mq, js, jr in mx["anchor_maa"]:
            if js >= min(THRS) and aq in anc_node: edges.append((anc_node[aq], maa_node[mq], js))
        mq = [q for q, _ in mx["maa"]]
        edges += [(maa_node[mq[i]], maa_node[mq[j]], it / max(1, un)) for i, j, it, un in mx["maa_maa_idx"]]
    # components per threshold
    comp = {}
    for thr in THRS:
        uf = UF(len(nodes))
        for i, j, x in edges:
            if x >= thr: uf.union(i, j)
        comp[thr] = [uf.find(i) for i in range(len(nodes))]
    nbr = defaultdict(list)
    for i, j, x in edges: nbr[i].append((j, x)); nbr[j].append((i, x))
    node_items = defaultdict(list)
    for k, n in enumerate(item_node): node_items[n].append(k)
    node_cnt = {n: Counter(s for k in ks for s in items[k]["srcs"]) for n, ks in node_items.items()}
    comp_cnt = {thr: defaultdict(Counter) for thr in THRS}
    for thr in THRS:
        for n, c in node_cnt.items(): comp_cnt[thr][comp[thr][n]].update(c)
    def mates(k):
        """-> {('group'|'direct', thr): sources with >= 1 OTHER item in the item's component / linked to the item}."""
        n = item_node[k]; own = items[k]["srcs"]; out = {}
        same = {s for s, c in node_cnt[n].items() if c - (s in own) > 0}
        for thr in THRS:
            out[("group", thr)] = {s for s, c in comp_cnt[thr][comp[thr][n]].items() if c - (s in own) > 0}
            d = set(same)
            for j, x in nbr[n]:
                if x >= thr: d |= set(node_cnt.get(j, ()))
            out[("direct", thr)] = d
        return out
    # evaluable keys from feats
    import torch
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from hgfm.e4 import e4_eval as EV
    F = torch.load(a.feats, weights_only=False, map_location="cpu")["rows"]; meta = {}
    for r in F:
        cand = [j for j in range(1, len(r["step_is_model"])) if r["step_is_model"][j]]
        meta[f"{r['dataset']}|{r['id']}"] = {"cand": cand, "label": int(r["mistake_step"]) + 1, "ntok": list(r["step_ntok"]),
                                              "code": list(r["step_has_code"]), "n_steps": len(r["step_is_model"]) - 1}
    del F
    evaluable = {k for k, m in meta.items() if m["label"] in m["cand"] and len(m["cand"]) >= 2}
    log(f"feats meta {len(meta)}, evaluable {len(evaluable)}")
    srcs_all = sorted(set().union(*[it["srcs"] for it in items]))
    ov = {"group": {}, "direct": {}, "group_evaluable": {}, "direct_evaluable": {}}; per_item = {}
    ev_items = [k for k, it in enumerate(items) if it["evals"]]
    for k in ev_items: per_item[k] = mates(k)
    for kind in ("group", "direct"):
        for thr in THRS:
            for suf, keep in (("", lambda k: True), ("_evaluable", lambda k: items[k]["key"] in evaluable)):
                tab = {}
                for es in EVAL_SETS:
                    ks = [k for k in ev_items if es in items[k]["evals"] and keep(k)]
                    row = {"n": len(ks)}
                    for s in srcs_all + ["any_midtrain", "clean_union"]:
                        if s == "any_midtrain": f = lambda m: bool(m & {"tapt", "S", "R", "full"})
                        elif s == "clean_union": f = lambda m: bool(m & set(CLEAN_SOURCES))
                        else: f = lambda m, s=s: s in m
                        row[s] = sum(1 for k in ks if f(per_item[k][(kind, thr)]))
                    tab[es] = row
                ov[kind + suf][str(thr)] = tab
    # checks: round 75 (direct, TT train file, 358 loader items), full filter
    chk = {}
    for thr in THRS:
        ks = [k for k in ev_items if items[k]["src"] in ("WW", "TEgc")]
        chk[f"r75_direct_TT_trainfile_{thr}"] = {"WW": sum(1 for k in ks if items[k]["src"] == "WW" and "TT_trainfile" in per_item[k][("direct", thr)]),
                                                 "TEgc": sum(1 for k in ks if items[k]["src"] == "TEgc" and "TT_trainfile" in per_item[k][("direct", thr)])}
    pub_gc = [k for k, it in enumerate(items) if it["src"] == "public" and it["split"] in ("who_and_when", "traceelephant") and (it["split"] == "who_and_when" or it.get("fam") == "groupchat")]
    loader_nodes = {item_node[k] for k in ev_items if items[k]["src"] in ("WW", "TEgc")}
    chk["public_eval_runs_not_on_loader_nodes"] = [items[k]["id"] for k in pub_gc if item_node[k] not in loader_nodes]
    # component stats
    cstat = {}
    for thr in THRS:
        sizes = Counter();
        for k in range(len(items)): sizes[comp[thr][item_node[k]]] += 1
        top = sorted(sizes, key=lambda c: -sizes[c])[:3]
        comp_of = {c: Counter() for c in top}
        for k in range(len(items)):
            c = comp[thr][item_node[k]]
            if c in comp_of: comp_of[c][items[k]["src"] + ("" if items[k]["src"] in ("WW", "TEgc", "MAA", "anchor") else "/" + str(items[k]["split"]))] += 1
        cstat[str(thr)] = {"n_groups": len(sizes), "largest": sorted(sizes.values(), reverse=True)[:5], "singletons": sum(1 for v in sizes.values() if v == 1),
                           "largest_composition": [dict(comp_of[c].most_common()) for c in top]}
    srcinfo = {s: {"items": sum(1 for it in items if s in it["srcs"]), "nodes": sum(1 for c in node_cnt.values() if s in c)} for s in srcs_all}
    out = {"rule": "word set re.findall('[a-z0-9]+', q.lower()); Jaccard >= thr; connected components (group) or pairwise (direct)",
           "thresholds": list(THRS), "eval_sets": list(EVAL_SETS), "sources": srcinfo, "corpora": cstats,
           "notes": {"NC_shuf": "same runs as R", "NC_irr": "WikiText-103, no MAS question (no overlap by construction)",
                     "MAA": "compared with anchors and MAA only (stem vs stem); not compared with non-medical sets",
                     "public_who_and_when / traceelephant groupchat": "are the evaluation sets themselves; not a training source",
                     "counts": "number of evaluation items with >= 1 mate in the source; *_evaluable = among E4-evaluable trajectories"},
           "components": cstat, "n_text_edges": len(edges), "checks": chk, **ov}
    # MAA / anchor summary
    if mx:
        maa_items = [k for k, it in enumerate(items) if it["src"] == "MAA"]
        out["maa"] = {"n": len(maa_items), "anchor_maa_edges_ge_thr": {str(t): sum(1 for e in mx["anchor_maa"] if e[2] >= t) for t in THRS},
                      "maa_with_anchor_groupmate": {str(t): sum(1 for k in maa_items if comp_cnt[t][comp[t][item_node[k]]]["anchors"] > 0) for t in THRS},
                      "maa_with_corpus_groupmate": {str(t): {c: sum(1 for k in maa_items if comp_cnt[t][comp[t][item_node[k]]][c] > 0) for c in ("tapt", "S", "R", "full")} for t in THRS}}
    # clean keys
    rel = CLEAN_SOURCES + ("TT_val",)
    ck = {"rule": "WW / TEgc trajectories (OAT loader ids; key 'dataset|id' as in E4 feats_base.pt) whose question has no mate in any of "
                  f"{list(CLEAN_SOURCES)}; 'clean' = prereg rule (no group-mate, Jaccard >= 0.3 components); 'clean_direct' = no source "
                  "question with pairwise Jaccard >= 0.3 (round-75 / eval_overlap_filter rule)",
          "clean_sources": list(CLEAN_SOURCES), "n_keys": {}, "clean": {}, "clean_direct": {}, "clean_incl_TT_val": {}, "per_key": {}}
    for es in ("WW", "TEgc"):
        ks = sorted((k for k in ev_items if items[k]["src"] == es), key=lambda k: items[k]["key"])
        ck["n_keys"][es] = {"all": len(ks), "evaluable": sum(1 for k in ks if items[k]["key"] in evaluable)}
        ck["clean"][es] = [items[k]["key"] for k in ks if not (per_item[k][("group", 0.3)] & set(CLEAN_SOURCES))]
        ck["clean_direct"][es] = [items[k]["key"] for k in ks if not (per_item[k][("direct", 0.3)] & set(CLEAN_SOURCES))]
        ck["clean_incl_TT_val"][es] = [items[k]["key"] for k in ks if not (per_item[k][("group", 0.3)] & (set(CLEAN_SOURCES) | {"TT_val"}))]
        for k in ks:
            ck["per_key"][items[k]["key"]] = {"evaluable": items[k]["key"] in evaluable,
                                              **{f"{kind}_{t}": sorted(per_item[k][(kind, t)] & set(rel)) for kind in ("group", "direct") for t in THRS}}
    json.dump(ck, open(os.path.join(a.out, "eval_clean_keys.json"), "w"), separators=(",", ":"))
    # direct 0.3 overlap by corpus x dataset (which part of a corpus carries the near-duplicates)
    bd = {}
    for es in ("WW+TEgc", "TT_test_agentic", "TT_test_coding", "TT_test_math"):
        ks = [k for k in ev_items if es in items[k]["evals"] and items[k]["key"] in evaluable]; c = Counter()
        for k in ks:
            n = item_node[k]; hit = set()
            for nn in [n] + [j for j, x in nbr[n] if x >= 0.3]:
                for kk in node_items[nn]:
                    if kk != k:
                        hit |= {f"{cc}:{items[kk]['ck'][0]}" for cc in items[kk].get("corp", ())}
            c.update(hit)
        bd[es] = {"n": len(ks), **dict(sorted(c.items()))}
    out["direct_0.3_by_corpus_dataset"] = bd
    json.dump(out, open(os.path.join(a.out, "overlap.json"), "w"), separators=(",", ":"))
    # audit
    import numpy as np
    sets = {"WW_HC": [], "WW_AG": [], "WW": [], "TEgc": [], "WW+TEgc": [], "TT_test_agentic": [], "TT_test_coding": [], "TT_test_math": [], "TT_test": []}
    for k in ev_items:
        for es in items[k]["evals"]:
            if es in sets and items[k]["key"] in evaluable: sets[es].append(items[k]["key"])
    keys = sorted(evaluable & {items[k]["key"] for k in ev_items})
    tk = {k: tuple(k.split("|", 1)) for k in keys}   # e4_eval expects (dataset, id) keys: it fits the control per k[0]
    m = {k: meta[k] for k in keys}
    base = EV.baselines({tk[k]: m[k] for k in keys}, [tk[k] for k in keys])
    R = {kind: {b: {k: v[tk[k]] for k in keys} for b, v in EV.per_traj(base, {tk[k]: m[k] for k in keys}, kind).items() if b != "random"} for kind in ("raw", "resid")}
    rnd = {k: {"acc1": 1 / len(m[k]["cand"]), "hit3": min(3, len(m[k]["cand"])) / len(m[k]["cand"]), "rauc": 0.5} for k in keys}
    key_item = {items[k]["key"]: k for k in ev_items}
    aud = {}
    for es, ks in sets.items():
        nc = np.array([len(m[k]["cand"]) for k in ks]); T = np.array([m[k]["n_steps"] for k in ks])
        pos = np.array([m[k]["cand"].index(m[k]["label"]) / (len(m[k]["cand"]) - 1) for k in ks])
        rp = np.array([(m[k]["label"] - 1) / max(m[k]["n_steps"] - 1, 1) for k in ks])
        row = {"n": len(ks), "cand_median": float(np.median(nc)), "cand_iqr": [float(np.percentile(nc, 25)), float(np.percentile(nc, 75))],
               "steps_median": float(np.median(T)), "label_relpos_cand_mean": float(pos.mean()), "label_relpos_cand_median": float(np.median(pos)),
               "label_relpos_step_mean": float(rp.mean()),
               "share_label_first_cand": float(np.mean([m[k]["cand"][0] == m[k]["label"] for k in ks])),
               "share_label_last_cand": float(np.mean([m[k]["cand"][-1] == m[k]["label"] for k in ks])),
               "share_label_longest_cand": float(np.mean([max(m[k]["cand"], key=lambda j: (m[k]["ntok"][j], -j)) == m[k]["label"] for k in ks])),
               "baselines": {}}
        for kind in ("raw", "resid"):
            for b in ("first_step", "last_step", "longest_step"):
                row["baselines"][f"{b}/{kind}"] = {mm: float(np.mean([R[kind][b][k][mm] for k in ks])) for mm in ("acc1", "rauc")}
        row["baselines"]["random"] = {mm: float(np.mean([rnd[k][mm] for k in ks])) for mm in ("acc1", "rauc")}
        row["overlap_group_0.3"] = {s: sum(1 for k in ks if s in per_item[key_item[k]][("group", 0.3)]) for s in CLEAN_SOURCES + ("TT_val", "anchors")}
        row["overlap_group_0.3"]["clean_union"] = sum(1 for k in ks if per_item[key_item[k]][("group", 0.3)] & set(CLEAN_SOURCES))
        row["overlap_direct_0.3"] = {s: sum(1 for k in ks if s in per_item[key_item[k]][("direct", 0.3)]) for s in CLEAN_SOURCES + ("TT_val",)}
        row["overlap_direct_0.3"]["clean_union"] = sum(1 for k in ks if per_item[key_item[k]][("direct", 0.3)] & set(CLEAN_SOURCES))
        aud[es] = row
    json.dump({"candidates": "model steps (index >= 1); evaluable = label among candidates and >= 2 candidates",
               "relpos_cand": "index of the label among candidates / (n_cand - 1)", "relpos_step": "(label - 1) / (n_steps - 1) (E4 covariate)",
               "sets": aud}, open(os.path.join(a.out, "audit.json"), "w"), separators=(",", ":"))
    # manifest
    groups = defaultdict(list)
    for k, it in enumerate(items): groups[comp[0.3][item_node[k]]].append(k)
    order = sorted(groups.values(), key=lambda ks: min(f"{items[k]['src']}|{items[k]['split']}|{items[k]['id']}" for k in ks))
    n_eval = 0
    with gzip.open(os.path.join(a.out, "manifest.jsonl.gz"), "wt") as fa, gzip.open(os.path.join(a.out, "manifest_eval.jsonl.gz"), "wt") as fe:
        for gi, ks in enumerate(order):
            mem = [[items[k]["src"], items[k]["split"] if items[k]["src"] != "TT" else f"{items[k]['split']}/{items[k].get('dom')}", items[k]["id"],
                    sorted(items[k].get("corp", ()))] for k in sorted(ks, key=lambda k: (items[k]["src"], items[k]["split"], items[k]["id"]))]
            row = json.dumps({"group": f"g{gi:05d}", "n": len(ks), "sources": dict(Counter(s for k in ks for s in items[k]["srcs"])), "members": mem}, ensure_ascii=False)
            fa.write(row + "\n")
            if any(items[k]["evals"] for k in ks): fe.write(row + "\n"); n_eval += 1
    log(f"groups {len(order)} ({n_eval} with evaluation items); done")


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("maa-edges"); m.add_argument("--maa_exclusion"); m.add_argument("--anchor", nargs="+"); m.add_argument("--out"); m.add_argument("--thr", type=float, default=0.3)
    b = sub.add_parser("build")
    for x in ("oat", "tt_ww", "feats", "public_dir", "maa_edges", "out"): b.add_argument("--" + x)
    b.add_argument("--anchor", nargs="*", default=[]); b.add_argument("--corpus", nargs="*", default=[])
    a = ap.parse_args()
    (cmd_maa_edges if a.cmd == "maa-edges" else cmd_build)(a)


if __name__ == "__main__":
    main()
