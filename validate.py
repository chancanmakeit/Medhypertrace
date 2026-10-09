
import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)

"""Validate the unified parser + label extraction + hypergraph on the real dataset."""
import sys
from collections import Counter

from common.data import load_jsonl, build_hypergraph, fm_category, FM_TYPES

from common.paths import FILES

for name, path in FILES.items():
    trajs = load_jsonl(path)
    n = len(trajs)
    fw = Counter(t.framework for t in trajs)
    step_masked = sum(t.labels.step_masked for t in trajs)
    n_faulty_inst = [len(t.labels.faulty_instances) for t in trajs]
    n_fms = [len(t.labels.fm_set) for t in trajs]
    hedge_types = Counter()
    hedge_sizes = Counter()
    nodes = []
    ctx_hit = 0
    for t in trajs:
        hg = build_hypergraph(t)
        nodes.append(hg.num_nodes)
        for e in hg.hyperedges:
            hedge_types[e["type"]] += 1
            hedge_sizes[e["type"]] += len(e["nodes"])
        if any(e["type"] == "ctx" for e in hg.hyperedges):
            ctx_hit += 1
    fmcat = Counter(fm_category(fm) for t in trajs for fm in t.labels.fm_set)

    print("=" * 78)
    print(f"{name}  (n={n}, framework parsed as {dict(fw)})")
    print(f"  step-loss masked (no injected step): {step_masked}/{n}")
    print(f"  faulty instances / traj: min={min(n_faulty_inst)} max={max(n_faulty_inst)} "
          f"avg={sum(n_faulty_inst)/n:.2f}")
    print(f"  distinct fm types / traj: avg={sum(n_fms)/n:.2f}")
    print(f"  fm category spread (label occurrences): {dict(sorted(fmcat.items()))}")
    print(f"  avg nodes/graph: {sum(nodes)/n:.1f}")
    print(f"  hyperedges/traj by type: "
          + ", ".join(f"{k}={v/n:.2f}" for k, v in sorted(hedge_types.items())))
    print(f"  avg hyperedge size by type: "
          + ", ".join(f"{k}={hedge_sizes[k]/max(hedge_types[k],1):.1f}"
                      for k in sorted(hedge_types)))
    print(f"  trajectories with >=1 ctx edge: {ctx_hit}/{n}")

# Concrete example: show one full parsed trajectory + its labels + hypergraph
print("\n" + "#" * 78)
print("# CONCRETE EXAMPLE (mdagents[0])")
print("#" * 78)
t = load_jsonl(FILES["mdagents"])[0]
print(f"id={t.id}  framework={t.framework}  gt_answer={t.correct_answer}  correct={t.is_correct}")
print(f"instances: {t.instances}")
print(f"faulty_instances: {sorted(t.labels.faulty_instances)}")
print(f"instance_fms: { {k: sorted(v) for k,v in t.labels.instance_fms.items()} }")
print(f"earliest_error_turn (step-level GT): {t.labels.earliest_error_turn}")
print("steps:")
for s in t.steps:
    tag = f"  <<INJECTED {s.fm_error_type}/{s.injection_strategy}>>" if s.injection_applied else ""
    print(f"  turn{s.turn} [{s.agent_name}#{s.role_index}] phase={s.phase} "
          f"len={len(s.content)}{tag}")
hg = build_hypergraph(t)
print(f"hypergraph: {len(hg.step_nodes)} step + {len(hg.agent_nodes)} agent + "
      f"{len(hg.phase_nodes)} phase nodes, {len(hg.hyperedges)} hyperedges")
for e in hg.hyperedges:
    print(f"  [{e['type']}] size={len(e['nodes'])}  {sorted(e['nodes'])}")
