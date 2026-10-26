"""ARIA (Edlison/ARIA) -> mas-traj/1.

24,468 episodes (train / validation / test, kept as provenance.split) of AG2, Magentic-One, MetaGPT and
OpenManus on GAIA, GSM-Plus, HumanEval, MMLU, OlympiadBench, SWE-bench-Lite; natural failures and successes
(outcome.source_success -> labels.is_correct).
Removed: MMLU episodes whose subject is a core medical subject (same list as measure_r53.MED_CORE).
Dropped events: empty bookkeeping events (launch / process_completed / task_result / before_think /
model_call / run_completed) and OpenManus `agent_run_completed` roll-ups that re-concatenate >= 80 % of the
step texts (as measure_r53). The first user / Python-Assistant message is the task (task.query), not a step.
No per-step inputs: sources by protocol (README "ARIA"). Localization / attribution / outcome ->
labels.external (event ids mapped to step ids); repair replacement events are NOT exported (counterfactual
text), only the repair cut point.
"""
import json
import os
import re
from collections import Counter

import numpy as np
import pandas as pd

from .common import cli, make_record, make_step, merge_sources, proto, question_id, slug, src, tool_call
from .mast import magentic_msg, magentic_sources

DATASET = "aria"
FW = {"ag2": "ag2_student_verifier", "magentic-one": "magentic_one", "metagpt": "metagpt", "openmanus": "openmanus"}
MED_CORE = {"clinical_knowledge", "college_medicine", "medical_genetics", "professional_medicine", "anatomy", "virology",
            "nutrition", "college_biology", "high_school_biology", "human_aging"}   # = measure_r53.MED_CORE
SUBJ_RE = re.compile(r"^Subject:\s*([A-Za-z_]+)", re.M)
SWE_REPOS = ["astropy/astropy", "django/django", "matplotlib/matplotlib", "mwaskom/seaborn", "pallets/flask",
             "psf/requests", "pydata/xarray", "pylint-dev/pylint", "pytest-dev/pytest", "scikit-learn/scikit-learn",
             "sphinx-doc/sphinx", "sympy/sympy"]
METAGPT_ROLES = ["product_manager", "architect", "engineer", "qa_engineer"]
METAGPT_READS = {"architect": ["product_manager"], "engineer": ["product_manager", "architect"],
                 "qa_engineer": ["product_manager", "engineer"]}


def py(x):
    if isinstance(x, np.ndarray):
        return [py(v) for v in x.tolist()]
    if isinstance(x, (list, tuple)):
        return [py(v) for v in x]
    if isinstance(x, dict):
        return {k: py(v) for k, v in x.items()}
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def native_id(bench, task_id, host):
    if bench == "gaia":
        return task_id, None
    tail = task_id.split(host + "-", 1)[1] if host in task_id else task_id
    if bench == "humaneval":
        m = re.search(r"humaneval-(\d+)$", tail)
        return (m.group(1), None) if m else (None, None)
    if bench == "swe-bench-lite":
        variant = None
        if tail.startswith("full-"):
            tail, variant = tail[5:], "full"
        for repo in SWE_REPOS:
            key = repo.replace("/", "-") + "-"
            if tail.startswith(key) and tail[len(key):].isdigit():
                return f"{repo.replace('/', '__')}-{tail[len(key):]}", variant
        return None, variant
    return None, None


def tc_list(tcs):
    out = []
    for t in tcs or []:
        if isinstance(t, str):
            try:
                t = json.loads(t)
            except Exception:
                out.append(tool_call(None, t))
                continue
        if isinstance(t, dict):
            f = t.get("function") or {}
            a = t.get("arguments", f.get("arguments"))
            try:
                a = json.loads(a) if isinstance(a, str) else a
            except Exception:
                pass
            out.append(dict(tool_call(t.get("name") or f.get("name"), py(a)), id=t.get("id")))
    return out


def ev_text(e):
    c = e.get("content") or ""
    trs = [x for x in py(e.get("tool_results")) or [] if isinstance(x, str) and x.strip()]
    if trs and not (c == "\n".join(trs) or (c.strip() and all(x in c for x in trs))):
        c = "\n".join(([c] if c.strip() else []) + trs)
    return c


# ----------------------------------------------------------------------------- per framework
def steps_ag2(evs):
    msgs, chat = [], 1
    for e in evs:
        c = ev_text(e)
        if e["kind"] == "workspace_artifact":
            msgs.append(dict(spk="host", text=c, kind="tool", phase="workspace_artifact", chat=chat, ev=e["event_id"]))
        elif e["role"] == "Python Assistant":
            if c.startswith("Review and finalize"):
                chat = 2
                msgs.append(dict(spk="Python Assistant", text=c, kind="tool", phase="review_request", chat=2, ev=e["event_id"]))
            else:
                msgs.append(dict(spk="Python Assistant", text=c, kind="tool", phase="code_execution", chat=chat, ev=e["event_id"]))
        else:
            msgs.append(dict(spk=e["role"], text=c, kind="llm", phase=f"{slug(e['role'])}_turn", chat=chat, ev=e["event_id"]))
    srcs = []
    for i, m in enumerate(msgs):
        if m["phase"] == "review_request":       # embeds the Student / Python Assistant transcript
            srcs.append(proto([f"#{j}" for j in range(i)]))
        elif m["kind"] == "tool":
            prev = [j for j in range(i) if msgs[j]["kind"] == "llm"]
            srcs.append(proto([f"#{prev[-1]}"], "excerpt") if prev else [])
        else:
            srcs.append(proto([f"#{j}" for j in range(i) if msgs[j]["chat"] == m["chat"]]))
    return msgs, srcs


def steps_magentic(evs):
    msgs = []
    for e in evs:
        c = ev_text(e)
        if e["kind"] == "workspace_artifact":
            msgs.append(dict(speaker="host", text=c, kind="tool", phase="workspace_artifact", ev=e["event_id"]))
            continue
        m = magentic_msg(e["role"], c)
        m["ev"] = e["event_id"]
        msgs.append(m)
    srcs = magentic_sources(msgs)
    for m in msgs:
        m["spk"] = m.pop("speaker")
    return msgs, srcs


def steps_metagpt(evs):
    msgs, k = [], 0
    for e in evs:
        c = ev_text(e)
        if e["kind"] == "workspace_artifact":
            msgs.append(dict(spk="host", text=c, kind="tool", phase="workspace_artifact", ev=e["event_id"]))
            continue
        role = METAGPT_ROLES[k] if k < len(METAGPT_ROLES) else "assistant"
        k += 1
        msgs.append(dict(spk=role, text=c, kind="llm", phase=role, ev=e["event_id"]))
    srcs = []
    for i, m in enumerate(msgs):
        if m["kind"] == "tool":
            prev = [j for j in range(i) if msgs[j]["kind"] == "llm"]
            srcs.append(proto([f"#{prev[-1]}"], "excerpt") if prev else [])
        elif m["phase"] == "product_manager":
            srcs.append([])
        elif m["phase"] in METAGPT_READS:
            srcs.append(proto([f"#{j}" for j in range(i) if msgs[j]["phase"] in METAGPT_READS[m["phase"]]]))
        else:
            srcs.append(proto([f"#{j}" for j in range(i)]))
    return msgs, srcs


def steps_openmanus(evs, rep):
    acts = [e["content"] for e in evs if e["kind"] == "after_act" and (e.get("content") or "").strip()]
    msgs = []
    for e in evs:
        c = ev_text(e)
        k = e["kind"]
        if k == "after_think":
            msgs.append(dict(spk="Manus", text=e.get("content") or "", kind="llm", phase="think",
                             calls=tc_list(py(e.get("tool_calls"))), ev=e["event_id"]))
        elif k == "after_act":
            msgs.append(dict(spk="tool", text=c, kind="tool", phase="tool_result", ev=e["event_id"]))
        elif k == "agent_run_completed" and c.strip():
            cov = sum(len(a) for a in set(acts) if a in c)
            if cov >= 0.8 * len(c):
                rep["openmanus_rollups_dropped"] += 1
                continue
            msgs.append(dict(spk="agent", text=c, kind="tool", phase="run_summary", ev=e["event_id"]))
        elif k == "workspace_artifact":
            msgs.append(dict(spk="host", text=c, kind="tool", phase="workspace_artifact", ev=e["event_id"]))
    srcs = []
    for i, m in enumerate(msgs):
        if m["kind"] == "tool":
            prev = [j for j in range(i) if msgs[j]["kind"] == "llm"]
            how = "structured_field" if m["phase"] == "tool_result" else "excerpt"
            srcs.append(proto([f"#{prev[-1]}"], how) if prev else [])
            if m["phase"] == "run_summary":
                srcs[-1] = proto([f"#{j}" for j in range(i)], "summary")
        else:
            srcs.append(proto([f"#{j}" for j in range(i)]))
    # tool name of a result = the issuing think's (first) call
    last = None
    for m in msgs:
        if m["kind"] == "llm":
            last = m
        elif m["phase"] == "tool_result":
            nm = (last or {}).get("calls") or [{}]
            m["tool"] = nm[0].get("name") or "tool"
    return msgs, srcs


def convert(raw):
    recs = []
    rep = Counter()
    for split in ("train", "validation", "test"):
        df = pd.read_parquet(os.path.join(raw, "Edlison__ARIA", "data", f"{split}.parquet"))
        for r in df.itertuples(index=False):
            bench, mas, task = r.benchmark, r.mas, r.task
            subj = None
            if bench == "mmlu":
                m = SUBJ_RE.search(task or "")
                subj = m.group(1) if m else None
                if subj in MED_CORE:
                    rep[f"dropped_medical_mmlu/{split}"] += 1
                    continue
            evs = [dict(e) for e in r.trajectory]
            first_task = next((i for i, e in enumerate(evs) if e["kind"] == "message" and
                               e["role"] in ("user", "Python Assistant")), None)
            body = [e for i, e in enumerate(evs) if i != first_task and
                    (e["kind"] in ("message", "after_think", "after_act", "agent_run_completed", "workspace_artifact"))
                    and (ev_text(e).strip() or py(e.get("tool_calls")))]
            if mas == "ag2":
                msgs, srcs = steps_ag2(body)
            elif mas == "magentic-one":
                msgs, srcs = steps_magentic(body)
            elif mas == "metagpt":
                msgs, srcs = steps_metagpt(body)
            else:
                msgs, srcs = steps_openmanus(body, rep)
            if not msgs:
                rep["skipped_no_steps"] += 1
                continue
            fw = FW[mas]
            steps, ev2sid = [], {}
            for i, (m, s) in enumerate(zip(msgs, srcs)):
                sources = [dict(x, step_id=f"s{int(x['step_id'][1:])}") for x in s]
                if m["kind"] == "tool":
                    aid = "host" if m["phase"] == "workspace_artifact" else (
                        "python_assistant" if m["spk"] == "Python Assistant" else
                        ("tool:" + slug(m.get("tool") or m["phase"])) if mas == "openmanus" and m["phase"] == "tool_result"
                        else "agent" if m["phase"] == "run_summary" else f"tool:{slug(m['spk'])}")
                    tc = [tool_call(m.get("tool") or m["phase"], None, m["text"])]
                else:
                    aid = {"magenticoneorchestrator": "orchestrator"}.get(slug(m["spk"]), slug(m["spk"]))
                    if mas == "openmanus":
                        aid = "manus"
                    tc = m.get("calls")
                st = make_step(i, m["kind"], aid, m["spk"], m["text"], phase=m["phase"], sources=sources, tool_calls=tc)
                steps.append(st)
                ev2sid[m["ev"]] = st["step_id"]
            o = py(r.outcome) or {}
            loc, att, rp = py(r.localization) or {}, py(r.attribution) or {}, py(r.repair)
            mp = lambda ids: [ev2sid.get(x) for x in ids or []]
            ext = {"dataset": "ARIA", "taxonomy": "ARIA RA codes (model-generated localization / attribution)",
                   "first_bad_event_ids": loc.get("first_bad_event_ids"), "first_bad_step_ids": mp(loc.get("first_bad_event_ids")),
                   "retained_frontier_ids": loc.get("retained_frontier_ids"),
                   "retained_frontier_step_ids": mp(loc.get("retained_frontier_ids")),
                   "evidence": [dict(x, step_id=ev2sid.get(x.get("event_id"))) for x in loc.get("evidence") or []],
                   "attribution": att, "outcome": o, "feedback": r.feedback,
                   "repair": None if not rp else {"cut_event_id": rp.get("cut_event_id"),
                                                  "cut_step_id": ev2sid.get(rp.get("cut_event_id")),
                                                  "replacement_events_exported": False},
                   "event_step_map": ev2sid, "aria_id": r.id, "mmlu_subject": subj}
            # round 61 (spot check item D): first-bad events with no exported step (task message / start event,
            # or a dropped roll-up event) -> flagged; such labels are excluded from step-level evaluation
            fb_ev = loc.get("first_bad_event_ids") or []
            unmapped = [e for e in fb_ev if ev2sid.get(e) is None]
            if unmapped:
                ext["first_bad_unmapped_event_ids"] = unmapped
                ext["first_bad_on_task"] = all(ev2sid.get(e) is None for e in fb_ev)
            nid, variant = native_id(bench, r.task_id, r.host_model)
            fa, fsrc = None, []
            for st in reversed(steps):
                mm = re.search(r"FINAL[ _]ANSWER:\s*(.+)", st["output"] or "")
                if mm and st["kind"] == "llm":
                    fa, fsrc = mm.group(1).strip(), [st["step_id"]]
                    break
            if not fsrc:
                fsrc = [steps[-1]["step_id"]]
            recs.append(make_record(
                dataset=DATASET, benchmark=bench, framework=fw, model=r.host_model,
                qid=question_id(bench, nid, task), query=task, steps=steps, final_answer=fa, final_source_step_ids=fsrc,
                labels={"is_correct": bool(o.get("source_success")) if "source_success" in o else None, "external": ext,
                        "is_correct_source": "ARIA outcome.source_success (public evaluator)"},
                provenance={"source_record_id": r.id, "split": split, "task_variant": variant,
                            "first_event_as_task": first_task is not None}))
            rep[f"kept/{mas}"] += 1
    return recs, dict(rep)


if __name__ == "__main__":
    cli(convert, DATASET)
