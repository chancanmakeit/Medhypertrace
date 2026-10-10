"""Shortcut audit on the AEGIS synthetic data: how much of MedHyperTrace's in-distribution step accuracy
comes from injection TEMPLATE lines (sentences the injector appends, never produced by un-injected agents)?

Template set: normalised step-tail lines seen >= MIN_COUNT times in injected steps and NEVER in
non-injected steps, learned on the TRAIN split only.
Reports, on the fixed TEST split:
  first_step          always the first acting step
  template_detector   first acting step containing a template line (else first step)
  mht_orig            MedHyperTrace (default config) trained on train, evaluated on test as is
  mht_stripped_test   same model, test steps with template lines deleted (symmetric: every step)
  mht_stripped_both   retrained on stripped train, evaluated on stripped test (clean-data capacity)
Usage: python analysis/artifact_audit.py [framework ...]
"""
import collections
import copy
import json
import os
import random
import re
import sys

_r = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _r)
import numpy as np  # noqa: E402
import torch  # noqa: E402

from common.data import load_jsonl  # noqa: E402
from common.paths import FILES, SPLITS_JSON  # noqa: E402
from ours import train_hgnn as T  # noqa: E402

MIN_COUNT = 10


def norm(line):
    return re.sub(r"\s+", " ", re.sub(r"\b[A-J]\b", "X", re.sub(r"[0-9]+(\.[0-9]+)?", "N", line.strip())))[:120]


def lines(txt):
    return [l for l in (txt or "").split("\n") if l.strip()]


def learn_templates(trajs):
    inj, non = collections.Counter(), collections.Counter()
    for t in trajs:
        for s in t.steps:
            if s.is_input:
                continue
            ls = {norm(l) for l in lines(s.content)}
            (inj if s.injection_applied else non).update(ls)
    return {l for l, c in inj.items() if c >= MIN_COUNT and non[l] == 0 and len(l) > 3}


def has_tpl(s, tpl):
    return any(norm(l) in tpl for l in lines(s.content))


def strip(trajs, tpl):
    out = []
    for t in trajs:
        t2 = copy.copy(t)
        t2.steps = []
        for s in t.steps:
            s2 = copy.copy(s)
            s2.content = "\n".join(l for l in lines(s.content) if norm(l) not in tpl)
            t2.steps.append(s2)
        out.append(t2)
    return out


def step_acc(preds, trajs):
    ok = n = 0
    for p, t in zip(preds, trajs):
        if t.labels.earliest_error_turn is None:
            continue
        n += 1; ok += p == t.labels.earliest_error_turn
    return round(ok / n, 3), n


def acting(t):
    return [s for s in t.steps if not s.is_input]


def train_eval(train, test_sets, args):
    random.seed(0); np.random.seed(0); torch.manual_seed(0)
    fz = T.make_featurizer("tfidf", train, None)
    tr, va = T.split_val(train)
    model, thr, fd = T.train_model(tr, va, fz, args)
    res = {}
    for name, te in test_sets.items():
        samples = [T.build_sample(t, fz, args.struct, None) for t in te]
        res[name] = round(T.evaluate_steps(model, samples, fd)[0], 3)
    return res


def main(fws):
    sp = json.load(open(SPLITS_JSON))
    args = T.get_args(["x"])
    report = {}
    for fw in fws:
        trajs = load_jsonl(FILES[fw])
        tr_ids, te_ids = set(sp[fw]["train_task_ids"]), set(sp[fw]["test_task_ids"])
        train = [t for t in trajs if t.id in tr_ids]
        test = [t for t in trajs if t.id in te_ids]
        tpl = learn_templates(train)
        inj_steps = [s for t in test for s in acting(t) if s.injection_applied]
        non_steps = [s for t in test for s in acting(t) if not s.injection_applied]
        cov_inj = sum(has_tpl(s, tpl) for s in inj_steps) / max(1, len(inj_steps))
        cov_non = sum(has_tpl(s, tpl) for s in non_steps) / max(1, len(non_steps))
        first = [acting(t)[0].turn for t in test]
        det = [next((s.turn for s in acting(t) if has_tpl(s, tpl)), acting(t)[0].turn) for t in test]
        det_fire = sum(any(has_tpl(s, tpl) for s in acting(t)) for t in test) / len(test)
        stripped_test = strip(test, tpl)
        print(f"== {fw}: {len(tpl)} templates; test coverage injected {cov_inj:.1%} vs non-injected "
              f"{cov_non:.1%}; detector fires on {det_fire:.0%} of test trajectories", flush=True)
        r = {"n_templates": len(tpl), "test_template_rate_injected_steps": round(cov_inj, 3),
             "test_template_rate_non_injected_steps": round(cov_non, 3),
             "detector_fires_on_traj": round(det_fire, 3),
             "first_step": step_acc(first, test), "template_detector": step_acc(det, test)}
        r.update({f"mht_{k}": v for k, v in train_eval(train, {"orig": test, "stripped_test": stripped_test},
                                                       args).items()})
        r["mht_stripped_both"] = train_eval(strip(train, tpl), {"x": stripped_test}, args)["x"]
        report[fw] = r
        print(json.dumps(r), flush=True)
    out = os.path.join(_r, "analysis", "artifact_audit.json")
    json.dump(report, open(out, "w"), indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1:] or ["mdagents", "dylan", "clinical_agent"])
