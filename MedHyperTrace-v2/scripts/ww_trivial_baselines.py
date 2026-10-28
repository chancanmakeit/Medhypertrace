"""Trivial baselines on Who&When in the metric the 2025-26 papers report (round 70).

  python ww_trivial_baselines.py --oat <patched OAT dir>

Step-level accuracy = predicted step index == mistake_step; agent-level accuracy = predicted agent == mistake_agent
(exact string match after strip/lower). Per subset (Hand-Crafted, Algorithm-Generated). Candidates:
  "all"   = every history step;  "model" = OAT's model steps only (step_is_model).
Baselines: random step (expected 1/n), first step, longest step (characters), most frequent agent (by number of turns,
non-model steps excluded), agent of the longest model step. No labels are used except for scoring.
"""
import argparse, json, os, sys
from collections import Counter


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--oat"); a = ap.parse_args()
    sys.path.insert(0, a.oat); os.chdir(a.oat)
    import data_pipeline as dp
    out = {}
    for t in dp.load_raw_trajectories("who_and_when"):
        sub = t["id"].split("/")[0]
        m = int(t["mistake_step"]); n = t["num_steps"]; ism = t["step_is_model"]; agent = t.get("mistake_agent", "")
        name = lambda i: (t["step_agents"][i] or "").strip().lower()
        ln = [e - b for b, e in t["step_char_boundaries"]]
        model = [i for i in range(n) if ism[i]] or list(range(n))
        r = out.setdefault(sub, Counter()); r["n"] += 1
        r["step_random_all"] += 1 / n; r["step_random_model"] += 1 / len(model)
        r["step_first_all"] += (m == 0); r["step_first_model"] += (m == model[0])
        r["step_longest_all"] += (m == max(range(n), key=lambda i: ln[i]))
        lm = max(model, key=lambda i: ln[i]); r["step_longest_model"] += (m == lm)
        cnt = Counter(name(i) for i in model)
        ag = agent.strip().lower()
        r["agent_most_frequent"] += (cnt.most_common(1)[0][0] == ag)
        r["agent_of_longest_model_step"] += (name(lm) == ag)
        r["agent_random_expected"] += (1 / len(cnt)) if ag in cnt else 0
    res = {s: {k: (v / c["n"] if k != "n" else v) for k, v in c.items()} for s, c in out.items()}
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
