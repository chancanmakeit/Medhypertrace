"""Assemble medhypertrace_report.json from the scorer outputs (scripts/eval_attribution.py,
run by eval_mafa/run_eval.sh) plus alignment, leakage, seeds and context numbers."""
import json
import os
import subprocess
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "eval_mafa/out"
MAFA = sys.argv[2] if len(sys.argv) > 2 else "/home/claude/mafa-human-ai-annotation"
K = ["who_earliest", "who_any", "when_exact", "when_pm1"]


def J(p):
    return json.load(open(os.path.join(OUT, p), encoding="utf-8"))


def compact(m):
    d = {k: f"{m[k]['k']}/{m[k]['n']} [{m[k]['ci95'][0]:.2f}, {m[k]['ci95'][1]:.2f}]" for k in K}
    d["agent_auroc"] = f"{m['agent_auroc']['mean']} (n={m['agent_auroc']['n_traces']} traces)"
    if m.get("code_micro_f1") is not None:
        d["code_micro_f1"] = m["code_micro_f1"]
    return d


def git(root, *a):
    return subprocess.check_output(["git", "-C", root, *a], text=True).strip()


root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
leak = J("leakage.json")
base = json.load(open(os.path.join(MAFA, "results/human_like_eval/baselines_report.json")))
rep = {
    "method": "MedHyperTrace",
    "version": {"medhypertrace_commit": git(root, "rev-parse", "--short", "HEAD"),
                "method_code_note": "common/ and ours/ unchanged since the 2026-10-08 handoff package",
                "mafa_commit": git(MAFA, "rev-parse", "--short", "HEAD")},
    "eval_set": "human-like-v1 (n=20 rows / 17 traces, faulty only, LLM labels)",
    "setting": ("no checkpoint existed: one model per framework (mdagents, dylan, clinical_agent) "
                "trained with train_hgnn.py DEFAULT hyperparameters on the fixed AEGIS synthetic-"
                "injection train split; MAFA labels never used for training, selection or thresholds. "
                "Primary seed 0; seeds 1-2 reported for robustness only."),
    "alignment": "17/17 traces sha1-aligned (every step, raw order and parser order)",
    "leakage": {"summary": leak["summary"],
                "note": ("0/17 by file+line and 0/17 by whole-trace sha1. 1/17 "
                         "(dylan mmlu_pro_health_5badfa1f) shares 2 step contents and its task with "
                         "the dylan/llm_debate TEST splits only (not used in training). 0/17 tasks "
                         "appear in the same framework's train split.")},
    "decision_rules": {"pred_step": "argmax step head",
                       "pred_agent_primary": "agent executing pred_step (step-owner)",
                       "pred_agent_secondary": "argmax agent head (agent-head)",
                       "pred_codes": "MAST rows only; max over agents of pair head, rescaled so the "
                                     "val-calibrated threshold maps to 0.5"},
    "results_primary_seed0": {t: compact(J(f"report_{t}.json")["method"])
                              for t in ["ALL", "MAST", "MedAgentAudit"]},
    "results_secondary_agent_head_seed0": {t: compact(J(f"report_agenthead_{t}.json")["method"])
                                           for t in ["ALL", "MAST", "MedAgentAudit"]},
    "seeds_ALL": {f"seed{s}": {r: compact(J(f"report{'' if r == 'step-owner' else '_agenthead'}_ALL"
                                              f"{'' if s == 0 else f'_seed{s}'}.json")["method"])
                               for r in ["step-owner", "agent-head"]} for s in [0, 1, 2]},
    "reference_baselines_ALL": {n: compact(base[n]) if base[n]["agent_auroc"]["mean"] is not None
                                else {k: f"{base[n][k]['k']}/{base[n][k]['n']}" for k in K}
                                for n in ["first_step", "last_step", "mafa_primary", "mafa_secondary"]},
    "context": {
        "trivial_code_baseline": "all MAST codes present: code_micro_f1 0.478 (13 MAST rows)",
        "in_distribution_step_top1_seed0_vs_first_step": J("context_in_distribution.json"),
    },
}
json.dump(rep, open(os.path.join(OUT, "medhypertrace_report.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(rep["results_primary_seed0"]["ALL"], indent=1))
