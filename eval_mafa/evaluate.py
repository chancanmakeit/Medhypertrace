"""Unified evaluation harness for MAFA labels (human version: import_review_labels.py -> attribution.jsonl;
also works on the LLM eval sets for dry runs). One command scores every method and every trivial baseline on
every label layer, overall / per framework / per split / without leaked traces, using MAFA's OWN scorer code
(scripts/eval_attribution.py: score, apply_layer) so both projects compute identical numbers.

    python eval_mafa/evaluate.py --labels <attribution.jsonl> --pred mht=eval_mafa/out_pkg/medhypertrace_pred.jsonl \
        [--subset dev] [--source human] [--out report.json --md report.md]

Label files: MAFA hands out attribution_dev.jsonl (dev rows only) for development and keeps the test labels until
the final evaluation (MAFA 0.7.53). TEST GUARD (pre-registered split, MAFA interface doc §8): --subset test needs --final, and every test run is
appended to eval_mafa/test_runs.jsonl (git-tracked: commit, pred/label/split hashes). A method name that already
has a test run is refused unless --repeat_reason "<why>" is given (also logged). Develop on dev only.

Label sources: --source human (default) keeps rows whose `source` (or `provenance.kind`) is "human"; LLM labels
(human-like v1/v2) need --source llm|any and must never be reported as results.

Built-in baselines (no label used): first_step, last_step, always_none (defect layer: "no defect"),
structure_prior (content-free: P(earliest injected step | position, role) and P(agent injected | uid) counted on
the AEGIS synthetic TRAIN split), plus MAFA's two annotator models from the review packages (reference only:
LLM-labelled sets were made after seeing them).
"""
import argparse
import collections
import datetime
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _R)
LAYERS = ["defect", "responsibility", "responsibility_any"]
METRICS = ["who_earliest", "who_any", "when_exact", "when_pm1"]
GUARD_LOG = os.path.join(_R, "eval_mafa", "test_runs.jsonl")


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_scorer(mafa_root):
    spec = importlib.util.spec_from_file_location("mafa_eval", os.path.join(mafa_root, "scripts", "eval_attribution.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def src_of(L):
    return L.get("source") or (L.get("provenance") or {}).get("kind")


def read_preds(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        out[(d.get("taxonomy"), d["trace_id"])] = d
    return out


def structure_prior(items):
    """Content-free baseline from the synthetic TRAIN split (no MAFA label involved)."""
    from common.data import load_jsonl
    from common.paths import FILES, SPLITS_JSON
    sp = json.load(open(SPLITS_JSON))
    preds = {}
    for fw in sorted({it["framework"] for it in items}):
        tr = set(sp[fw]["train_task_ids"])
        hit, tot, ag_hit, ag_tot = (collections.Counter() for _ in range(4))
        for t in load_jsonl(FILES[fw]):
            if t.id not in tr:
                continue
            acting = [s for s in t.steps if not s.is_input]
            for i, s in enumerate(acting):
                tot[(i, s.orig_agent_name)] += 1
                hit[(i, s.orig_agent_name)] += s.turn == t.labels.earliest_error_turn
            orig = {s.instance: f"{s.orig_agent_name}-{s.role_index}" for s in acting}
            for inst, uid in orig.items():
                ag_tot[uid] += 1
                ag_hit[uid] += inst in t.labels.faulty_instances
        for it in items:
            if it["framework"] != fw:
                continue
            steps = it["steps"]
            role = lambda st: st["agent"].rsplit("-", 1)[0]  # noqa: E731
            ss = {st["id"]: (hit[(i, role(st))] + .5) / (tot[(i, role(st))] + 1) for i, st in enumerate(steps)}
            best = max(steps, key=lambda st: (ss[st["id"]], -int(st["id"][1:])))
            agents = {a["uid"]: (ag_hit[a["uid"]] + .5) / (ag_tot[a["uid"]] + 1) for a in it["agents"]}
            preds[(None, it["id"])] = {"step_scores": ss, "pred_step": best["id"], "pred_agent": best["agent"],
                                       "agent_scores": agents}
    return preds


def trivial(items):
    first, last, none = {}, {}, {}
    for it in items:
        s = it["steps"]
        first[(None, it["id"])] = {"pred_step": s[0]["id"], "pred_agent": s[0]["agent"]}
        last[(None, it["id"])] = {"pred_step": s[-1]["id"], "pred_agent": s[-1]["agent"]}
        none[(None, it["id"])] = {"pred_step": "none"}
    return {"first_step": first, "last_step": last, "always_none": none}


def guard(a, pred_paths, label_path, split_sha):
    if a.subset != "test":
        return
    if not a.final:
        sys.exit("refused: --subset test is the one-shot final evaluation; add --final (dev is for development)")
    prior = [json.loads(x) for x in open(GUARD_LOG)] if os.path.exists(GUARD_LOG) else []
    seen = {m for r in prior for m in r["methods"]}
    again = sorted(set(pred_paths) & seen)
    if again and not a.repeat_reason:
        sys.exit(f"refused: {again} already scored on test (see {GUARD_LOG}); pass --repeat_reason to override (logged)")
    head = subprocess.run(["git", "-C", _R, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    entry = {"time": datetime.datetime.now(datetime.timezone.utc).isoformat(), "medhypertrace_commit": head,
             "methods": {n: sha256(p) for n, p in pred_paths.items()}, "labels_sha256": sha256(label_path),
             "split_sha256": split_sha, "repeat_reason": a.repeat_reason, "argv": sys.argv[1:]}
    with open(GUARD_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[test guard] logged to {GUARD_LOG}")


def compact(r, layer="defect"):
    out = {k: (f"{r[k]['k']}/{r[k]['n']}" if r[k]["n"] else "-") for k in METRICS if k in r}
    out["agent_auroc"] = r["agent_auroc"]["mean"]
    out["auroc_n"] = r["agent_auroc"]["n_traces"]
    if layer == "defect" and r.get("code_micro_f1") is not None:   # codes are defect-layer judgments
        out["code_micro_f1"] = r["code_micro_f1"]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mafa_root", default="/home/claude/mafa-human-ai-annotation")
    ap.add_argument("--labels", required=True, help="attribution.jsonl or an eval-set labels_*.jsonl")
    ap.add_argument("--pred", action="append", default=[], help="name=path (repeatable)")
    ap.add_argument("--subset", choices=("dev", "test"), default="dev")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--repeat_reason", default=None)
    ap.add_argument("--source", choices=("human", "llm", "any"), default="human")
    ap.add_argument("--leakage", default=os.path.join(_R, "eval_mafa", "out_v2", "leakage_package.json"))
    ap.add_argument("--no_structure_prior", action="store_true", help="skip (needs MHT_DATA_DIR)")
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args()
    E = load_scorer(a.mafa_root)
    lp = a.labels if os.path.isabs(a.labels) else os.path.join(a.mafa_root, a.labels)
    labels = [json.loads(x) for x in open(lp, encoding="utf-8")]
    if a.source != "any":
        labels = [L for L in labels if src_of(L) == a.source]
        if not labels:
            sys.exit(f"no labels with source={a.source} (LLM eval sets need --source llm and are never results)")
    split = json.load(open(os.path.join(a.mafa_root, "review_packages", "eval_split_v1.json")))
    keep = set(split[a.subset])
    other = sum(L["trace_id"] not in keep for L in labels)
    labels = [L for L in labels if L["trace_id"] in keep]
    if not labels:
        sys.exit(f"no label rows in subset={a.subset} ({other} rows belong to the other side). MAFA hands out "
                 f"attribution_dev.jsonl for development; test labels are released by MAFA only for the final run")
    pred_paths = dict(p.split("=", 1) for p in a.pred)
    guard(a, pred_paths, lp, split["sha256"])

    pk_paths = [os.path.join(a.mafa_root, "review_packages", f) for f in ("mast_v1.json", "medagentaudit_v1.json")]
    items = json.load(open(pk_paths[0]))["items"]
    methods = {n: read_preds(p) for n, p in pred_paths.items()}
    methods.update(trivial(items))
    if not a.no_structure_prior:
        methods["structure_prior"] = structure_prior(items)
    methods.update({k: v for k, v in E.baselines(labels, [dict(it, trace_id=it["id"]) for it in items], pk_paths).items()
                    if k.startswith("mafa_")})

    leak = {r["trace_id"]: r["same_framework_train"] for r in json.load(open(a.leakage))["rows"]}
    groups = {"all": lambda L: True, "no_leak": lambda L: not leak.get(L["trace_id"], False)}
    for fw in sorted({L["framework"] for L in labels}):
        groups[f"fw={fw}"] = (lambda f: lambda L: L["framework"] == f)(fw)
    for sp_ in ("clean", "faulty"):
        groups[f"split={sp_}"] = (lambda s: lambda L: L.get("split") == s)(sp_)

    report = {"subset": a.subset, "source": a.source, "labels": lp, "labels_sha256": sha256(lp),
              "split_sha256": split["sha256"], "n_label_rows": len(labels), "layers": {}}
    for layer in LAYERS:
        Ls = E.apply_layer(labels, layer)
        report["layers"][layer] = {}
        for g, f in groups.items():
            sub = [L for L in Ls if f(L)]
            if not sub:
                continue
            report["layers"][layer][g] = {"n_rows": len(sub),
                                          "methods": {n: E.score(sub, p) for n, p in methods.items()}}
    if a.out:
        json.dump(report, open(a.out, "w"), indent=1, ensure_ascii=False)
    lines = [f"# MAFA evaluation · subset={a.subset} · source={a.source} · rows={len(labels)}",
             f"labels `{os.path.relpath(lp, a.mafa_root)}` sha256 {report['labels_sha256'][:12]} · split {split['sha256'][:12]}", ""]
    for layer, gs in report["layers"].items():
        for g, blk in gs.items():
            if g not in ("all", "no_leak") and not g.startswith("fw="):
                if not (layer == "defect" and g.startswith("split=")):
                    continue
            lines += [f"## {layer} · {g} (rows={blk['n_rows']})", "",
                      "| method | " + " | ".join(METRICS) + " | agent_auroc (n) | code_micro_f1 |", "|---" * (len(METRICS) + 3) + "|"]
            for n, r in blk["methods"].items():
                c = compact(r, layer)
                au = f"{c['agent_auroc']:.3f} ({c['auroc_n']})" if c["agent_auroc"] is not None else "-"
                lines.append(f"| {n} | " + " | ".join(c.get(k, "-") for k in METRICS) +
                             f" | {au} | {c.get('code_micro_f1', '-')} |")
            lines.append("")
    md = "\n".join(lines)
    if a.md:
        open(a.md, "w").write(md)
    print(md if len(md) < 6000 else md[:6000] + "\n... (truncated; see --md)")


if __name__ == "__main__":
    main()
