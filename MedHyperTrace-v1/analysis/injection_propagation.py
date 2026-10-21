"""Answer-level propagation proxy on the AEGIS synthetic-injection data (MAFA question b).

For each trajectory (all are is_correct=False) and each agent instance that gives an answer,
compare the agent's LAST stated answer with the system's final (wrong) answer and with gold:
  aligned   agent answer == final wrong answer   (consistent with the defect reaching the answer)
  gold      agent answer == gold                 (the agent's own stance stayed correct:
                                                  its defect did not reach the answer through it)
  other     a different wrong answer
  none      no extractable answer (e.g. a recruiter/planner that only plans)
Injected agents are compared with NON-injected agents of the same trajectories (control):
answer agreement is a proxy, not causal propagation, and is only informative relative to it.

MCQ frameworks: letter answers. ClinicalAgent(5): <final_result>p</final_result>, label p>=0.5,
system label from injection_log.predicted_probability (gold label = the other one, since
every trajectory is wrong).

Extractor validation (printed): coverage, and how often the extracted final answer equals
gold (should be ~0, since all trajectories are wrong) or the dataset's regex_extracted.
"""
import collections
import json
import os
import re
import sys

_r = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _r)
from common.data import load_jsonl  # noqa: E402
from common.paths import FILES  # noqa: E402

PATS = [
    r"final answer\s*(?:is)?\s*[:：]?\s*\**\s*\(?\s*([A-J])\b",
    r"answer\s*(?:is|:)\s*\**\s*\(?\s*([A-J])\b",
    r"best option is\s*\**\s*\(?\s*([A-J])\b",
    r"\*\*\(?([A-J])[\.\)\*]",
]
ALONE = re.compile(r"^\s*\(?([A-J])\)?\.?\s*$")
PROB = re.compile(r"<final_result>\s*([0-9]*\.?[0-9]+)\s*</final_result>")
MCQ = {"mdagents", "dylan", "llm_debate"}
# the role that WRITES the final answer is trivially aligned with it: reported separately, in neither group
PRODUCER = {"mdagents": "Aggregator", "llm_debate": "Aggregator", "clinical_agent": "Reasoner"}


def letter(text):
    if not text:
        return None
    m = ALONE.match(text)
    if m:
        return m.group(1).upper()
    best = None
    for p in PATS:
        for m in re.finditer(p, text, flags=re.I):
            if best is None or m.start() > best[0]:
                best = (m.start(), m.group(1).upper())
    return best[1] if best else None


def prob_label(text):
    ms = PROB.findall(text or "")
    return None if not ms else int(float(ms[-1]) >= 0.5)


def gold_letter(rec):
    g = (rec.get("verification") or {}).get("gold") or (rec.get("ground_truth") or {}).get("correct_answer")
    m = re.match(r"\s*\(?([A-J])\b", str(g or ""))
    return m.group(1).upper() if m else None


def main(out_path):
    res, val = {}, {}
    for fw, path in FILES.items():
        trajs = load_jsonl(path)
        C = {"inj": collections.Counter(), "non": collections.Counter(), "producer": collections.Counter()}
        traj_c = collections.Counter()
        v = collections.Counter()
        for t in trajs:
            rec = t.raw
            if fw in MCQ:
                final = letter(rec.get("response") or "")
                gold = gold_letter(rec)
                rx = (rec.get("verification") or {}).get("regex_extracted")
                v["n"] += 1; v["final_extracted"] += final is not None
                v["final_eq_gold"] += final is not None and final == gold
                if final and rx:
                    v["both"] += 1; v["agree_regex_extracted"] += final == str(rx).strip().upper()[:1]
                ans = lambda s: letter(s.content)
                if final is not None and ((rx and final != str(rx).strip().upper()[:1]) or final == gold):
                    traj_c["dropped_invalid_final"] += 1
                    continue
            else:
                pp = rec["injection_log"].get("predicted_probability")
                final = None if pp is None else int(float(pp) >= 0.5)
                gold = None if final is None else 1 - final
                v["n"] += 1; v["final_extracted"] += final is not None
                ans = lambda s: prob_label(s.content)
            if final is None:
                traj_c["no_final"] += 1
                continue
            last = {}
            for s in t.steps:
                if s.is_input:
                    continue
                a = ans(s)
                last.setdefault(s.instance, None)
                if a is not None:
                    last[s.instance] = a
            inj = t.labels.faulty_instances
            any_aligned = False
            for inst, a in last.items():
                cat = ("none" if a is None else "aligned" if a == final
                       else "gold" if a == gold else "other")
                grp = ("producer" if inst[0] == PRODUCER.get(fw) else
                       "inj" if inst in inj else "non")
                C[grp][cat] += 1
                C[grp][f"{inst[0] if fw != 'mdagents' or inst[0] in ('Recruiter', 'Aggregator') else 'Expert'}:{cat}"] += 1
                any_aligned |= grp == "inj" and cat == "aligned"
                traj_c["inj_answering"] += grp == "inj" and a is not None
            traj_c["n"] += 1
            traj_c["some_injected_aligned"] += any_aligned
            answered_inj = [last[i] for i in inj if i in last and last[i] is not None and i[0] != PRODUCER.get(fw)]
            if answered_inj and all(a == gold for a in answered_inj):
                traj_c["all_answering_injected_say_gold"] += 1
        res[fw] = {"agents": {g: dict(c) for g, c in C.items()}, "trajectories": dict(traj_c)}
        val[fw] = dict(v)
    json.dump({"propagation": res, "extractor_validation": val}, open(out_path, "w"), indent=1)

    for fw in FILES:
        r, v = res[fw], val[fw]
        print(f"\n== {fw}  extractor: final {v['final_extracted']}/{v['n']}"
              + (f", final==gold {v['final_eq_gold']} (should be ~0), agrees with regex_extracted "
                 f"{v['agree_regex_extracted']}/{v['both']}" if 'both' in v else ""))
        for g in ("inj", "non", "producer"):
            c = r["agents"][g]; ans = c.get("aligned", 0) + c.get("gold", 0) + c.get("other", 0)
            tot = ans + c.get("none", 0)
            if not tot:
                continue
            print(f"  {g}: agents {tot}, answering {ans}; of answering: aligned {c.get('aligned',0)/ans:.0%}, "
                  f"gold {c.get('gold',0)/ans:.0%}, other {c.get('other',0)/ans:.0%}")
        tc = r["trajectories"]
        print(f"  dropped (final disagrees with regex_extracted or equals gold): {tc.get('dropped_invalid_final',0)}")
        print(f"  trajectories {tc['n']}: >=1 injected agent aligned {tc['some_injected_aligned']/tc['n']:.0%}; "
              f"every answering injected agent says gold {tc.get('all_answering_injected_say_gold',0)/tc['n']:.0%}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "analysis/injection_propagation.json")
