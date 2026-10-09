"""
Bridge our medical MAS error dataset -> the exact sample schema that your
AEGIS_Reproduce/evaluate-v3.py + aegis_common.py expect, so your trained SFT
checkpoint can be evaluated on our medical trajectories with the SAME code and
the SAME Pair/Agent/Error Micro/Macro-F1 metrics as the paper.

Confirmed from your repo (aegis_common.py):
  * SFT target format is DIRECT JSON  {"faulty_agents":[{"agent_name","error_type"}]}
    (7146/7146 training targets are single-line JSON; NOT chain-of-thought).
    -> run evaluate WITHOUT --use_cot.
  * The task is MULTI-LABEL faulty (agent,error) pairs; there is NO step prediction
    and NO fixed-step target. So the SFT baseline is scored at Agent / Error / Pair
    level only (step-level is out of scope for this baseline, by construction).

Output sample schema (matches data/eval/whowhen.jsonl):
  {
    "id": str,
    "metadata": {"framework","benchmark","num_agents","num_injected_agents",...},
    "input": {"query": str,
              "conversation_history": [{"step":int,"agent_name":str,"content":str}, ...],
              "final_output": str},
    "output": {"faulty_agents": [{"agent_name": str, "error_type": "FM-x.y"}, ...]}
  }

Usage (produces jsonl consumable by your evaluate-v3.py):
  python bridge_to_aegis_eval.py --out /tmp/med_eval
Then on your GPU box, inside AEGIS_Reproduce/:
  python evaluate-v3.py \
      --model_path outputs/global_step_110/huggingface_merged \
      --bench_jsonl /tmp/med_eval/med_mdagents.jsonl \
      --whowhen_jsonl /tmp/med_eval/med_llm_debate.jsonl \
      --output_dir outputs/med_eval_results
  # (evaluate-v3 takes two jsonls; pass any two of our files, or run it 3x.
  #  It applies compute_metrics -> Pair/Agent/Error Micro/Macro-F1.)

IMPORTANT — agent-name matching: aegis_common._norm_agent lowercases and strips,
and compute_metrics matches on agent_name string. Our faulty labels use the ROLE
name (e.g. "Expert", "Aggregator"), and conversation turns carry the same
agent_name, so predictions and GT share the same surface forms. For frameworks
where a role is replicated (mdagents Expert x k), see --agent_key below.
"""
from __future__ import annotations

import os as _os, sys as _sys
_r = _os.path.dirname(_os.path.abspath(__file__))
while _r != '/' and not _os.path.isdir(_os.path.join(_r, 'common')):
    _r = _os.path.dirname(_r)
if _r not in _sys.path:
    _sys.path.insert(0, _r)


import argparse
import json
import os
import sys

from common.data import load_jsonl, Trajectory  # our unified parser

from common.paths import FILES, SPLITS_JSON


def agent_surface(agent_name: str, role_index: int, agent_key: str) -> str:
    """How a faulty agent's name appears in BOTH the conversation log and the GT,
    so the model's prediction can match. 'role' = collapse replicated roles to the
    bare role name; 'instance' = disambiguate replicas as 'Expert 0', 'Expert 1'."""
    if agent_key == "instance":
        return f"{agent_name} {role_index}"
    return agent_name


def to_aegis_sample(t: Trajectory, agent_key: str) -> dict:
    acting = [s for s in t.steps if not s.is_input]
    conv = [{"step": s.turn,
             "agent_name": agent_surface(s.agent_name, s.role_index, agent_key),
             "content": s.content}
            for s in acting]
    faulty = [{"agent_name": agent_surface(a, ri, agent_key), "error_type": fm}
              for (a, ri), fms in t.labels.instance_fms.items()
              for fm in sorted(fms)]
    return {
        "id": t.id,
        "metadata": {
            "framework": t.framework, "benchmark": t.framework,
            "num_agents": len(t.instances),
            "num_injected_agents": len(t.labels.faulty_instances),
            "task_type": "medical",
        },
        "input": {
            "query": t.query,
            "conversation_history": conv,
            "final_output": t.final_response,
        },
        "output": {"faulty_agents": faulty},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/med_eval")
    ap.add_argument("--agent_key", choices=["role", "instance"], default="role",
                    help="'role' (default): faulty agent = bare role name (matches "
                         "how the SFT model was trained on general data). 'instance': "
                         "disambiguate replicated roles like 'Expert 0/1/2'.")
    ap.add_argument("--test_only", action="store_true",
                    help="Emit only the fixed test-set task ids (splits.json) so the "
                         "SFT baseline is scored on the SAME test set as our models.")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    test_ids = None
    if args.test_only:
        with open(SPLITS_JSON) as f:
            sp = json.load(f)
        test_ids = {k: set(v["test_task_ids"]) for k, v in sp.items()}

    for name, path in FILES.items():
        trajs = load_jsonl(path)
        if test_ids is not None:
            trajs = [t for t in trajs if t.id in test_ids[name]]
        rows = [to_aegis_sample(t, args.agent_key) for t in trajs]
        outp = os.path.join(args.out, f"med_{name}.jsonl")
        with open(outp, "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        npairs = sum(len(r["output"]["faulty_agents"]) for r in rows)
        print(f"[{name}] wrote {len(rows)} samples ({npairs} faulty pairs) -> {outp}")


if __name__ == "__main__":
    main()
