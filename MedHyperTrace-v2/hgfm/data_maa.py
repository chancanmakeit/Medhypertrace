"""Featurise converted MedAgentAudit runs into hypergraph tensors for HGFM v0 (round 33).

Per run:
  task vector  q   = emb(task.query)
  step nodes   x_i = [emb(output) | emb(phase|role) | scalars]
     scalars (no gold): has_answer, answer==final, answer==round-majority, agree (+1/-1/0),
                        round/max_round, order/n, is_last, |sources|/5, n_readers/5
     gold-aware extra (only if gold=True): answer==gold, final==gold
  hyperedges (index lists):
     read   (tail = sources, head = step)       + its reverse (head -> tails)
     event  (members = steps of one round x phase)
     agent  (members = steps of one agent_id)
Targets:
  step_y[i, c]  auditor label for code c on step i (nan = not audited)
  run_y_211     role-assignment code 2.1.1 (run level, nan if absent)
  run_wrong     final answer != gold (outcome)
"""
import json, hashlib, collections
import numpy as np

CODES = ["1.1.1", "1.2.1", "2.1.2", "2.2.1", "2.2.2", "3.1.1", "3.1.2", "3.1.3", "3.2.1"]  # step-level
C2I = {c: i for i, c in enumerate(CODES)}
N_SCAL = 9


def sha(t): return hashlib.sha1(t.encode("utf-8")).hexdigest()


class Featuriser:
    def __init__(self, emb_dir):
        self.E = np.load(f"{emb_dir}/emb.npy").astype(np.float32)
        self.ix = json.load(open(f"{emb_dir}/index.json"))

    def e(self, t):
        return self.E[self.ix[sha(t)]]

    def run(self, r, gold=False):
        st = r["steps"]; n = len(st)
        if n == 0: return None
        sid = {s["step_id"]: i for i, s in enumerate(st)}
        final = r["final"]["answer"]; g = r["labels"]["gold"]
        rounds = [s["round"] or 1 for s in st]; R = max(rounds)
        maj = {}
        for rr in set(rounds):
            a = [str(s["structured"].get("answer")) for s in st if (s["round"] or 1) == rr and s["structured"].get("answer") is not None]
            maj[rr] = collections.Counter(a).most_common(1)[0][0] if a else None
        readers = collections.Counter(sid[x["step_id"]] for s in st for x in s["sources"] if x["step_id"] in sid)
        X = np.zeros((n, 384 * 2 + N_SCAL + (2 if gold else 0)), dtype=np.float32)
        for i, s in enumerate(st):
            a = s["structured"].get("answer"); ag = s["structured"].get("agree")
            X[i, :384] = self.e((s["output"] or "")[:2000]); X[i, 384:768] = self.e(f"{s['phase']} | {s['agent_role']}")
            sc = [a is not None, a is not None and str(a) == str(final), a is not None and str(a) == maj[rounds[i]],
                  0 if ag is None else (1 if str(ag).lower() in ("true", "yes", "1") else -1),
                  rounds[i] / R, i / max(n - 1, 1), i == n - 1, len(s["sources"]) / 5, readers[i] / 5]
            X[i, 768:768 + N_SCAL] = sc
            if gold:
                X[i, 768 + N_SCAL] = a is not None and str(a) == str(g)
                X[i, 769 + N_SCAL] = str(final) == str(g)
        read = [([sid[x["step_id"]] for x in s["sources"] if x["step_id"] in sid], i) for i, s in enumerate(st)]
        ev, ag = collections.defaultdict(list), collections.defaultdict(list)
        for i, s in enumerate(st):
            ev[(rounds[i], s["phase"])].append(i); ag[s["agent_id"]].append(i)
        Y = np.full((n, len(CODES)), np.nan, dtype=np.float32); y211 = np.nan
        for it in r["labels"]["audit"]["items"]:
            if it["code"] == "2.1.1":
                y211 = max(0 if np.isnan(y211) else y211, float(it["present"])); continue
            if it["step_id"] in sid:
                i, c = sid[it["step_id"]], C2I[it["code"]]
                Y[i, c] = max(0 if np.isnan(Y[i, c]) else Y[i, c], float(it["present"]))
        return {"run_id": r["run_id"], "mas": r["framework"][4:], "qid": r["question_id"], "q": self.e(r["task"]["query"][:2000]),
                "X": X, "read": [(t, h) for t, h in read if t], "event": [m for m in ev.values() if len(m) > 1],
                "agent": [m for m in ag.values() if len(m) > 1], "Y": Y, "y211": y211,
                "wrong": float(str(final) != str(g)), "steps": [(s["agent_id"], s["phase"]) for s in st]}
