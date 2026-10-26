"""MAST-Data (mcemri/MAST-Data) -> mas-traj/1.

1642 raw framework logs (7 MAS). The raw string also holds config dumps, pip / docker output, HTTP and
token-usage lines; we keep only agent messages (LLM outputs) and tool / execution outputs, parsed per log
format (detected from the text, not from mas_name: 2 "HyperAgent" rows are ChatDev logs):

  ag2_dict      {'content': [...], 'role': ..., 'name': ...} records    AG2 MathChat (GSM Claude, Olympiad), AG2 GroupChat (MMLU)
  ag2_yaml      instance_id / problem_statement / other_data / trajectory (YAML-like)   AG2 MathChat GSM-Plus GPT-4o
  chatdev       "[ts INFO] Speaker: **A<->B on : Phase, turn k**" utterances
  metagpt       "NEW MESSAGES:\\n\\nRole: content" blocks
  magentic      "---------- Agent ----------" console blocks (AutoGen 0.4 MagenticOneGroupChat)
  hyperagent    "HyperAgent_<id> - INFO - <Agent>'s Response:" / "<Intern>->Planner:" log records
  openmanus     loguru lines (plan creation, "Manus's thoughts", tool arguments, tool results)
  appworld      "Response from Supervisor Agent" / "Message to <app> Agent" / ... blocks

No per-step inputs: sources by protocol (README "MAST-Data"). Labels: mast_annotation -> labels.external.
AG2 GSM-Plus rows carry other_data (correct / answer / seed solution): labels only, never in steps or task.
"""
import ast
import os
import re
from collections import Counter

import pandas as pd

from .common import cli, make_record, make_step, med_heuristic, merge_sources, nws, proto, question_id, slug, src, tool_call

DATASET = "mast_data"


# ======================================================================= format detection
def detect(s):
    if re.search(r"\*\*\[Start Chat\]\*\*", s):
        return "chatdev"
    if s.lstrip().startswith("{'content':"):
        return "ag2_dict"
    if re.search(r"^trajectory:\s*$", s, re.M) and "HyperAgent_" in s:
        return "hyperagent"
    if re.search(r"^trajectory:\s*$", s, re.M):
        return "ag2_yaml"
    if "NEW MESSAGES:" in s:
        return "metagpt"
    if re.search(r"^-{10} \S+ -{10}$", s, re.M):
        return "magentic"
    if "app.agent.toolcall:think" in s or "app.flow.planning" in s:
        return "openmanus"
    if "Response from Supervisor Agent" in s:
        return "appworld"
    return None


# a message: dict(speaker, text, kind, phase, conv, extra...)
def M(speaker, text, kind="llm", phase="unknown", **kw):
    d = dict(speaker=speaker, text=text, kind=kind, phase=phase)
    d.update(kw)
    return d


# ======================================================================= AG2
def parse_ag2_dict(s):
    parts = re.split(r"(?<=\}) (?=\{'content')", s.strip())
    msgs, buf = [], ""
    for p in parts:
        buf = (buf + " " + p) if buf else p
        try:
            d = ast.literal_eval(buf)
        except Exception:
            continue
        buf = ""
        c = d.get("content")
        msgs.append((d.get("name") or d.get("role"), "\n".join(c) if isinstance(c, list) else str(c or "")))
    assert not buf, "unparsed AG2 dict tail"
    return msgs


def parse_ag2_yaml(s):
    head, traj = re.split(r"^trajectory:\s*$", s, maxsplit=1, flags=re.M)
    meta = {}
    m = re.search(r"^instance_id:\s*(.*)$", head, re.M)
    meta["instance_id"] = m.group(1).strip() if m else None
    m = re.search(r"^problem_statement:\s*(.*?)\n(?=\S)", head, re.M | re.S)
    meta["problem"] = m.group(1).strip() if m else None
    for k in ("correct", "answer", "given", "perturbation_type", "seed_answer"):
        m = re.search(rf"^  {k}:\s*(.*)$", head, re.M)
        meta[k] = m.group(1).strip() if m else None
    msgs, cur, field = [], None, None
    for line in traj.split("\n"):
        m = re.match(r"^      (content|role|name):\s?(.*)$", line)
        if m:
            k, v = m.groups()
            if k == "content":
                if cur:
                    msgs.append(cur)
                cur = {"content": [v] if v.strip() else [], "role": None, "name": None}
                field = "content"
            else:
                cur[k] = v.strip()
                field = None
            continue
        if cur is not None and field == "content":
            cur["content"].append(line[12:] if line.startswith(" " * 12) else line.strip())
    if cur:
        msgs.append(cur)
    out = [(c["name"] or c["role"], "\n".join(c["content"]).strip("\n")) for c in msgs]
    return out, meta


def ag2_messages(raw_msgs, groupchat):
    """first message = the task (not a step); code-execution replies -> tool steps."""
    task = raw_msgs[0][1] if raw_msgs else ""
    out = []
    for name, text in raw_msgs[1:]:
        if groupchat:
            if name == "chat_manager" and text.startswith("Hello everyone. We have assembled"):
                out.append(M(name, text, "tool", "groupchat_introduction"))
            elif text.startswith("exitcode:"):
                out.append(M(name, text, "tool", "code_execution"))
            else:
                out.append(M(name, text, "llm", "agent_turn"))
        else:
            if name == "mathproxyagent":
                out.append(M(name, text, "tool", "code_execution"))
            else:
                out.append(M(name, text, "llm", "assistant_turn"))
    return task, out


def math_problem(task):
    m = re.search(r"Problem:\s*\n(.*)$", task, re.S)
    return m.group(1).strip() if m else task


# ======================================================================= ChatDev
_CD = re.compile(r"^\[[^\]\n]+ INFO\] (?P<spk>[^:\n]+): \*\*(?P<a>[^*\n]+?)<->(?P<b>[^*\n]+?) on : (?P<ph>\w+), turn (?P<t>\d+)\*\*\s*$", re.M)
_LOGLINE = re.compile(r"^\[\d{4}-\d{2}-\d{2} [\d:]+ INFO\]", re.M)


def parse_chatdev(s):
    m = re.search(r"\*\*task_prompt\*\*:\s*(.*)", s)
    task = m.group(1).strip() if m else None
    # phase instances: each "[chatting]" table starts a new chat
    starts = [(mm.start(), (re.search(r"\*\*phase_name\*\* \| (\w+)", s[mm.start(): mm.start() + 20000]) or [None, None])[1])
              for mm in re.finditer(r"System: \*\*\[chatting\]\*\*", s)]
    out = []
    for mm in _CD.finditer(s):
        body_start = mm.end()
        nxt = _LOGLINE.search(s, body_start)
        body = s[body_start: nxt.start() if nxt else len(s)].strip("\n")
        if body.lstrip().startswith("["):         # the role's system prompt is echoed in brackets first
            k = body.find("]\n\n")
            if k != -1:
                body = body[k + 3:]
        inst = sum(1 for p, _ in starts if p < mm.start())
        out.append(M(mm.group("spk").strip(), body.strip(), "llm", mm.group("ph"), inst=inst,
                     turn=int(mm.group("t"))))
    return task, out


# ======================================================================= MetaGPT
def parse_metagpt(s):
    m = re.search(r"FROM: Human.*?CONTENT:\n(.*?)\n-{20,}", s, re.S)
    task = m.group(1).strip() if m else None
    out = []
    for mm in re.finditer(r"NEW MESSAGES:\n\n(\w+): ?(.*?)\n-{20,}", s, re.S):
        out.append(M(mm.group(1), mm.group(2).strip("\n"), "llm", mm.group(1)))
    return task, out


# ======================================================================= Magentic (AutoGen 0.4 console)
def parse_magentic_console(s, start_marker="SCENARIO.PY STARTING"):
    k = s.find(start_marker)
    body = s[k:] if k != -1 else s
    end = body.find("SCENARIO.PY COMPLETE")
    body = body[:end] if end != -1 else body
    blocks = re.split(r"^-{10} (\S+) -{10}\n", body, flags=re.M)
    task, out = None, []
    for name, text in zip(blocks[1::2], blocks[2::2]):
        text = text.strip("\n")
        if name == "user" and task is None:
            task = text
            continue
        out.append(magentic_msg(name, text))
    return task, out


def magentic_msg(name, text):
    if name in ("MagenticOneOrchestrator", "Orchestrator"):
        t = text.lstrip()
        if t.startswith("We are working to address the following user request"):
            return M(name, text, "llm", "task_ledger")
        if t.startswith("FINAL ANSWER") or t.startswith("FINAL_ANSWER"):
            return M(name, text, "llm", "final_answer")
        if re.fullmatch(r"\[\s*'[^']+'\s*\]", t):
            return M(name, text, "llm", "speaker_selection")
        return M(name, text, "llm", "instruction")
    if name == "ComputerTerminal":
        return M(name, text, "tool", "code_execution")
    return M(name, text, "llm", "agent_response")


def magentic_sources(msgs):
    """broadcast-thread protocol (also used for ARIA magentic-one)."""
    steps_src, thread, last_sel = [], [], None
    for i, m in enumerate(msgs):
        ph = m["phase"]
        if ph == "task_ledger":
            srcs = proto(thread) if thread else []
        elif ph == "speaker_selection":
            prev = [j for j in range(i) if msgs[j]["phase"] == "instruction"]
            srcs = proto([f"#{prev[-1]}"], "structured_field") if prev else proto(thread)
        elif m["kind"] == "tool":
            prev = [j for j in thread if msgs[int(j[1:])]["kind"] == "llm"]
            srcs = proto(prev[-1:], "excerpt")
        else:
            srcs = proto(thread)
            if ph == "agent_response" and last_sel is not None:
                srcs = merge_sources(srcs, proto([f"#{last_sel}"], "control"))
        steps_src.append(srcs)
        if ph == "task_ledger":
            thread = [f"#{i}"]
        elif ph == "speaker_selection":
            last_sel = i
        else:
            thread.append(f"#{i}")
    return steps_src


# ======================================================================= HyperAgent
_HA = re.compile(r"^  HyperAgent_\S+ - [A-Z]+ - (.*)$", re.M)


def parse_hyperagent(s):
    head, traj = re.split(r"^trajectory:\s*$", s, maxsplit=1, flags=re.M)
    m = re.search(r"^instance_id:\s*(.*)$", head, re.M)
    iid = m.group(1).strip() if m else None
    m = re.search(r"^problem_statement:\n(.*?)\n(?=\S)", head, re.S | re.M)
    task = "\n".join(l[2:] if l.startswith("  ") else l for l in (m.group(1) if m else "").split("\n")).strip()
    recs = [(mm.start(), mm.end(), mm.group(1)) for mm in _HA.finditer(traj)]
    out = []
    for k, (a, b, first) in enumerate(recs):
        cont = traj[b: recs[k + 1][0] if k + 1 < len(recs) else len(traj)]
        lines = [l[2:] if l.startswith("  ") else l for l in cont.split("\n")]
        mm = re.match(r"(Planner|Inner-(\w+)-Assistant)'s Response: ?(.*)$", first, re.S)
        mr = re.match(r"(\w+)->Planner: ?(.*)$", first, re.S)
        if mm:
            text = (mm.group(3) + "\n" + "\n".join(lines)).strip()
            if mm.group(1) == "Planner":
                out.append(M("Planner", text, "llm", "planner"))
            else:
                out.append(M(mm.group(2), text, "llm", "inner_step", intern=mm.group(2)))
        elif mr:
            text = (mr.group(2) + "\n" + "\n".join(lines)).strip()
            out.append(M(mr.group(1), text, "llm", "report_to_planner", intern=mr.group(1)))
    return iid, task, out


def hyperagent_sources(msgs):
    res, last_plan = [], None
    for i, m in enumerate(msgs):
        if m["phase"] == "planner":
            srcs = proto([f"#{j}" for j in range(i) if msgs[j]["phase"] in ("planner", "report_to_planner")])
            last_plan = i
        else:
            lo = last_plan + 1 if last_plan is not None else 0
            inner = [f"#{j}" for j in range(lo, i) if msgs[j]["phase"] == "inner_step" and msgs[j].get("intern") == m["intern"]]
            if m["phase"] == "inner_step":
                srcs = merge_sources(proto([f"#{last_plan}"], "excerpt") if last_plan is not None else [], proto(inner))
            else:
                srcs = proto(inner, "summary")
        res.append(srcs)
    return res


# ======================================================================= OpenManus
_LG = re.compile(r"^\d{4}-\d\d-\d\d [\d:.]+ \| (\w+)\s*\| ([\w.]+):(\w+):\d+ - (.*)$")


def parse_openmanus(s):
    entries = []
    for line in s.split("\n"):
        mm = _LG.match(line)
        if mm:
            entries.append([mm.group(2) + ":" + mm.group(3), mm.group(4)])
        elif entries:
            entries[-1][1] += "\n" + line
    task, out, cur = None, [], None
    for where, text in entries:
        if where == "__main__:run_flow" and text.startswith("Read prompt from task.txt:"):
            task = text.split(":", 1)[1].strip()
        elif where == "app.flow.planning:_create_initial_plan" and text.startswith("Plan creation result:"):
            out.append(M("planner", text.split(":", 1)[1].strip(), "llm", "plan"))
        elif where == "app.agent.toolcall:think" and text.startswith("✨ Manus's thoughts:"):
            cur = M("Manus", text.split(":", 1)[1].strip(), "llm", "think", calls=[])
            out.append(cur)
        elif where == "app.agent.toolcall:think" and text.startswith("🧰 Tools being prepared:") and cur is not None:
            try:
                cur["calls"] = [{"name": n, "arguments": None} for n in ast.literal_eval(text.split(":", 1)[1].strip())]
            except Exception:
                pass
        elif where == "app.agent.toolcall:think" and text.startswith("🔧 Tool arguments:") and cur is not None:
            a = text.split(":", 1)[1].strip()
            for c in cur["calls"]:
                if c["arguments"] is None:
                    c["arguments"] = a
                    break
            else:
                cur["calls"].append({"name": None, "arguments": a})
        elif where == "app.agent.toolcall:act" and text.startswith("🎯 Tool '"):
            mm = re.match(r"🎯 Tool '([^']+)' completed its mission! Result: ?(.*)$", text, re.S)
            name, res = (mm.group(1), mm.group(2)) if mm else ("tool", text)
            out.append(M(f"tool:{name}", res.strip(), "tool", "tool_result", tool=name))
    return task, out


def memory_sources(msgs, plan_phase="plan"):
    """agent memory: every earlier step (verbatim); the plan as structured_field; a tool result reads the
    latest call."""
    res = []
    for i, m in enumerate(msgs):
        if m["kind"] == "tool":
            prev = [j for j in range(i) if msgs[j]["kind"] == "llm"]
            res.append(proto([f"#{prev[-1]}"], "structured_field") if prev else [])
        else:
            res.append(merge_sources(proto([f"#{j}" for j in range(i) if msgs[j]["phase"] == plan_phase], "structured_field"),
                                     proto([f"#{j}" for j in range(i)])))
    return res


# ======================================================================= AppWorld
_AW = re.compile(r"^( *)(Response from (\w+) Agent|Code Execution Output|Message to (\w+) Agent|"
                 r"Reply from (\w+) Agent to Supervisor|Response from send_message API|"
                 r"Entering (\w+) Agent message loop|Exiting (\w+) Agent message loop)\s*$", re.M)


def parse_appworld(s):
    m = re.search(r"\*{10,} Task \d+/\d+ \(([^)]*)\)\s*\*{10,}\n(.*?)\n", s)
    tid, task = (m.group(1).strip(), m.group(2).strip()) if m else (None, None)
    hs = list(_AW.finditer(s))
    out, conv, ninst = [], "supervisor", 0
    for k, h in enumerate(hs):
        ind = len(h.group(1)) + 4
        body = s[h.end(): hs[k + 1].start() if k + 1 < len(hs) else len(s)]
        text = "\n".join(l[ind:] if l.startswith(" " * ind) else l.strip() for l in body.split("\n")).strip()
        g = h.group(2)
        if g.startswith("Entering"):
            ninst += 1
            conv = f"{h.group(6).lower()}#{ninst}"
            continue
        if g.startswith("Exiting"):
            conv = "supervisor"
            continue
        if h.group(3):           # Response from X Agent
            who = h.group(3)
            out.append(M(f"{who} Agent", text, "llm", "agent_code", conv="supervisor" if who == "Supervisor" else conv))
        elif g == "Code Execution Output":
            out.append(M("tool:code_execution", text, "tool", "code_execution", conv=conv))
        elif h.group(4):         # Message to X Agent (delivered message / execution feedback)
            out.append(M(f"tool:message_to_{h.group(4).lower()}", text, "tool", "message_delivery",
                         conv="supervisor" if h.group(4) == "Supervisor" else conv))
        elif h.group(5):
            out.append(M(f"tool:reply_from_{h.group(5).lower()}", text, "tool", "reply_to_supervisor", conv="supervisor",
                         from_conv=conv))
        else:
            out.append(M("tool:send_message", text, "tool", "api_response", conv="supervisor"))
    return tid, task, out


def appworld_sources(msgs):
    res = []
    for i, m in enumerate(msgs):
        same = [f"#{j}" for j in range(i) if msgs[j]["conv"] == m["conv"]]
        if m["kind"] == "llm":
            res.append(proto(same))
        elif m["phase"] == "reply_to_supervisor":
            prev = [f"#{j}" for j in range(i) if msgs[j]["conv"] == m.get("from_conv") and msgs[j]["kind"] == "llm"]
            res.append(proto(prev[-1:], "excerpt"))
        else:
            prev = [f"#{j}" for j in range(i) if msgs[j]["kind"] == "llm" and
                    (msgs[j]["conv"] == m["conv"] or m["phase"] == "message_delivery")]
            res.append(proto(prev[-1:], "structured_field"))
    return res


# ======================================================================= protocols for the rest
def thread_sources(msgs):
    """shared thread / two-agent chat: llm steps read every earlier step; tool (execution) steps read the
    latest llm step (the code they run)."""
    res = []
    for i, m in enumerate(msgs):
        if m["kind"] == "tool":
            prev = [j for j in range(i) if msgs[j]["kind"] == "llm"]
            res.append(proto([f"#{prev[-1]}"], "excerpt") if prev and m["phase"] == "code_execution" else [])
        else:
            res.append(proto([f"#{j}" for j in range(i)]))
    return res


def chatdev_sources(msgs):
    res = []
    for i, m in enumerate(msgs):
        same = [f"#{j}" for j in range(i) if msgs[j]["inst"] == m["inst"]]
        concl = {}
        for j in range(i):
            if msgs[j]["inst"] != m["inst"]:
                concl[msgs[j]["phase"]] = f"#{j}"         # last utterance of the latest instance of each phase
        res.append(merge_sources(proto(same), proto(sorted(concl.values(), key=lambda x: int(x[1:])), "structured_field")))
    return res


METAGPT_WATCH = {"SimpleCoder": set(), "SimpleTester": {"SimpleCoder", "SimpleReviewer"},
                 "SimpleReviewer": {"SimpleTester"}}


def metagpt_sources(msgs):
    res = []
    for i, m in enumerate(msgs):
        w = METAGPT_WATCH.get(m["speaker"])
        if w is None:
            res.append(proto([f"#{j}" for j in range(i)]))
        else:
            res.append(proto([f"#{j}" for j in range(i) if msgs[j]["speaker"] in w | {m["speaker"]}]))
    return res


# ======================================================================= build
FMT_FW = {"chatdev": "chatdev", "metagpt": "metagpt", "magentic": "magentic_one", "hyperagent": "hyperagent",
          "openmanus": "openmanus", "appworld": "appworld_mas"}


def build_steps(msgs, srcs, agent_of):
    steps = []
    for i, (m, s) in enumerate(zip(msgs, srcs)):
        sources = [dict(x, step_id=f"s{int(x['step_id'][1:])}") if x["step_id"].startswith("#") else x for x in s]
        tc = None
        if m["kind"] == "tool":
            tc = [tool_call(m.get("tool") or m["phase"], None, m["text"])]
        elif m.get("calls"):
            tc = [tool_call(c["name"], c["arguments"]) for c in m["calls"]]
        ev = [f"{m['phase']}#{m['inst']}"] if "inst" in m else []
        steps.append(make_step(i, m["kind"], agent_of(m), m["speaker"], m["text"], phase=m["phase"],
                               sources=sources, tool_calls=tc, event_ids=ev))
    return steps


def convert(raw):
    df = pd.read_parquet(os.path.join(raw, "mcemri__MAST-Data", "default", "train", "0000.parquet"))
    recs, rep = [], {"formats": Counter(), "mas_name_vs_format": Counter(), "skipped": [], "empty_steps": 0}
    for _, r in df.iterrows():
        s = r["trace"]["trajectory"]
        fmt = detect(s)
        rep["mas_name_vs_format"][f"{r['mas_name']}->{fmt}"] += 1
        rec_id = f"{r['trace']['key']}/{r['trace']['index']}"
        meta, native, gold, is_corr = {}, None, None, None
        prov_extra = {}
        try:
            if fmt in ("ag2_dict", "ag2_yaml"):
                if fmt == "ag2_dict":
                    raw_msgs = parse_ag2_dict(s)
                else:
                    raw_msgs, meta = parse_ag2_yaml(s)
                    native = meta.get("instance_id")
                    if meta.get("correct") in ("True", "False"):
                        is_corr = meta["correct"] == "True"
                    gold = None if meta.get("answer") in (None, "None") else meta.get("answer")
                gc = r["benchmark_name"] == "MMLU"
                task_msg, msgs = ag2_messages(raw_msgs, gc)
                fw = "ag2_groupchat" if gc else "ag2_mathchat"
                task = task_msg if gc else (meta.get("problem") or math_problem(task_msg))
                if not gc:
                    prov_extra["initial_prompt_template"] = "MathChat proxy prompt (problem embedded) not exported as a step"
                srcs = thread_sources(msgs)
            elif fmt == "chatdev":
                task, msgs = parse_chatdev(s)
                fw, srcs = "chatdev", chatdev_sources(msgs)
            elif fmt == "metagpt":
                task, msgs = parse_metagpt(s)
                fw, srcs = "metagpt", metagpt_sources(msgs)
            elif fmt == "magentic":
                task, msgs = parse_magentic_console(s)
                fw, srcs = "magentic_one", magentic_sources(msgs)
            elif fmt == "hyperagent":
                native, task, msgs = parse_hyperagent(s)
                fw, srcs = "hyperagent", hyperagent_sources(msgs)
            elif fmt == "openmanus":
                task, msgs = parse_openmanus(s)
                fw, srcs = "openmanus", memory_sources(msgs)
                prov_extra["task_query_truncated"] = bool(task and task.endswith("..."))
            elif fmt == "appworld":
                native, task, msgs = parse_appworld(s)
                fw, srcs = "appworld_mas", appworld_sources(msgs)
            else:
                rep["skipped"].append((rec_id, "unknown format"))
                continue
        except Exception as e:      # noqa: BLE001  (reported, never silent)
            rep["skipped"].append((rec_id, f"parse error {type(e).__name__}: {e}"))
            continue
        if not msgs:
            rep["skipped"].append((rec_id, f"no agent messages parsed ({fmt})"))
            continue
        rep["formats"][fmt] += 1

        def agent_of(m):
            if m["kind"] == "tool":
                return m["speaker"] if m["speaker"].startswith("tool:") else f"tool:{slug(m['speaker'])}"
            if fw == "hyperagent":
                return "planner" if m["phase"] == "planner" else slug(m["intern"])
            return {"magenticoneorchestrator": "orchestrator"}.get(slug(m["speaker"]), slug(m["speaker"]))
        if fw == "ag2_groupchat" and med_heuristic(task):     # round 61: same medical rule as r53 / ARIA keyword fallback
            rep["dropped_medical_ag2_groupchat"] = rep.get("dropped_medical_ag2_groupchat", 0) + 1
            continue
        steps = build_steps(msgs, srcs, agent_of)
        if fw == "chatdev":   # round 61 (spot check item E): a Reflection that repeats the previous step verbatim
            for i in range(1, len(steps)):  # forwards that phase's conclusion -> environment/template
                st, pv = steps[i], steps[i - 1]
                if st["phase"] == "Reflection" and st["kind"] == "llm" and nws(st["output"]) and nws(st["output"]) == nws(pv["output"]):
                    st.update(kind="environment", env_type="template", input_messages=None, tool_calls=[])
                    rep["chatdev_reflection_forwards"] = rep.get("chatdev_reflection_forwards", 0) + 1
        rep["empty_steps"] += sum(1 for st in steps if not (st["output"] or "").strip())
        bench = r["benchmark_name"]
        fa, fsrc = None, []
        for st in reversed(steps):
            mm = re.search(r"FINAL[ _]ANSWER:\s*(.+)", st["output"] or "") or re.search(r"\\boxed\{(.+?)\}", st["output"] or "")
            if mm and st["kind"] == "llm":
                fa, fsrc = mm.group(1).strip(), [st["step_id"]]
                break
        if not fsrc:
            fsrc = [steps[-1]["step_id"]]
        codes = {k: (None if v is None else int(v)) for k, v in (r["mast_annotation"] or {}).items()}
        ext = {"dataset": "MAST-Data", "taxonomy": "MAST-14", "codes": codes, "any_failure": any(v for v in codes.values() if v),
               "mas_name": r["mas_name"], "trace_id": int(r["trace_id"])}
        if meta:
            ext["task_meta"] = {k: meta.get(k) for k in ("correct", "answer", "given", "perturbation_type", "seed_answer")}
        if fw != FMT_FW.get(fmt, fw) or (fmt == "chatdev" and r["mas_name"] != "ChatDev"):
            ext["format_mismatch"] = f"mas_name {r['mas_name']} but log is {fmt}"
        recs.append(make_record(
            dataset=DATASET, benchmark=bench, framework=fw, model=r["llm_name"],
            qid=question_id(bench, native, task), query=task, steps=steps,
            final_answer=fa, final_source_step_ids=fsrc,
            labels={"gold": gold, "is_correct": is_corr, "external": ext,
                    "is_correct_source": "AG2 GSM-Plus other_data.correct" if is_corr is not None else "not recorded"},
            provenance=dict({"source_record_id": rec_id, "log_format": fmt}, **prov_extra)))
    rep["formats"] = dict(rep["formats"])
    rep["mas_name_vs_format"] = dict(rep["mas_name_vs_format"])
    return recs, rep


if __name__ == "__main__":
    cli(convert, DATASET)
