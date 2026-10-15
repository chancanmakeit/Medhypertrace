"""Adapter: MAFA human-like eval set (traces_v1.jsonl) -> MedHyperTrace Trajectory objects.

Each eval trace is rebuilt from its ORIGINAL AEGIS record (located by source.file +
source.line_index, never by record id, which is not unique) and parsed with the SAME
parser MedHyperTrace is trained with (common.data.parse_record). This keeps the input
distribution identical to training (raw step order, role_index, is_input, input_messages).

ID mapping (MAFA doc §2):
  MAFA step  sNN  == record["injection_log"]["conversation_history"][NN-1]
  MAFA agent uid  == f"{agent_name}-{role_index}"   (agent_name BEFORE our mdagents
                     specialist refinement, i.e. Step.orig_agent_name)
"""
import hashlib
import json
import os
import sys

_r = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _r not in sys.path:
    sys.path.insert(0, _r)

from common.data import parse_record, parse_step  # noqa: E402


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()


def load_raw(mafa_root: str, source: dict) -> dict:
    path = os.path.join(mafa_root, source["file"])
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == source["line_index"]:
                rec = json.loads(line)
                break
        else:
            raise IndexError(f"{path} has no line {source['line_index']}")
    if str(rec.get("id")) != str(source["record_id"]):
        raise ValueError(f"{path}#{source['line_index']}: id {rec.get('id')} != {source['record_id']}")
    return rec


def source_from_id(mafa_root: str, trace_id: str) -> dict:
    """Package items carry no `source`; the trace id is <framework>::<file stem>#<line5>#<record id> (interface doc §2).
    The stem names a file under data/faulty or data/clean (run scripts/fetch_data.sh in the MAFA root first)."""
    body = trace_id.split("::", 1)[1]
    stem, line, rid = body.rsplit("#", 2)
    hits = [os.path.join(d, stem + ".jsonl") for d in ("data/faulty", "data/clean")
            if os.path.exists(os.path.join(mafa_root, d, stem + ".jsonl"))]
    if len(hits) != 1:
        raise FileNotFoundError(f"{trace_id}: source file for stem {stem!r} found {len(hits)} times")
    return {"file": hits[0], "line_index": int(line), "record_id": rid}


def build(trace: dict, mafa_root: str):
    """Return (Trajectory, mapping) for one MAFA trace.

    mapping = {
      "turn2sid":  our Step.turn -> MAFA 'sNN' (via position in conversation_history),
      "inst2uid":  our (agent_name, role_index) instance -> MAFA uid,
      "align":     per-step sha1 check results,
    }
    """
    trace.setdefault("trace_id", trace.get("id"))
    rec = load_raw(mafa_root, trace.get("source") or source_from_id(mafa_root, trace["trace_id"]))
    traj = parse_record(rec, framework_override=trace["framework"])
    ch = rec["injection_log"]["conversation_history"]

    # position k in the raw list is MAFA s{k+1}; our parser sorts by `turn`, so map by turn
    raw_steps = [parse_step(s, traj.framework) for s in ch]
    turn2sid = {}
    for k, s in enumerate(raw_steps):
        if s.turn in turn2sid:
            raise ValueError(f"{trace['trace_id']}: duplicate turn {s.turn}")
        turn2sid[s.turn] = f"s{k + 1:02d}"

    # alignment self-check (MAFA doc §2): our k-th step content vs MAFA steps[k].content_sha1,
    # in BOTH orders: raw-list order (what MAFA indexes) and our parser's sorted order
    mafa = trace["steps"]
    align = {"n_mafa": len(mafa), "n_ours": len(traj.steps),
             "raw_order_match": 0, "parser_order_match": 0, "mismatch_ids": []}
    for k, ms in enumerate(mafa):
        ref = ms.get("content_sha1") or sha1(ms["content"] or "")   # package items carry the content itself
        ok_raw = k < len(raw_steps) and sha1(raw_steps[k].content) == ref
        ok_par = k < len(traj.steps) and sha1(traj.steps[k].content) == ref
        align["raw_order_match"] += ok_raw
        align["parser_order_match"] += ok_par
        if not ok_raw:
            align["mismatch_ids"].append(ms["id"])
    align["ok"] = (len(mafa) == len(raw_steps) == len(traj.steps)
                   and align["raw_order_match"] == len(mafa))

    # agent uid mapping via the PRE-refinement name
    inst2uid = {}
    for s in traj.steps:
        if s.is_input:
            continue
        uid = f"{s.orig_agent_name}-{s.role_index}"
        prev = inst2uid.setdefault(s.instance, uid)
        if prev != uid:
            raise ValueError(f"{trace['trace_id']}: instance {s.instance} maps to {prev} and {uid}")
    known = {a["uid"] for a in trace["agents"]}
    unknown = sorted(set(inst2uid.values()) - known)
    if unknown:
        raise ValueError(f"{trace['trace_id']}: uids not in MAFA agent list: {unknown}")
    return traj, {"turn2sid": turn2sid, "inst2uid": inst2uid, "align": align}


def load_eval(mafa_root: str, traces_rel: str = "results/human_like_eval/traces_v1.jsonl"):
    """traces_rel: an evaluation-set traces_*.jsonl, or a review package (*.json with "items") -- the latter covers
    all 360 package traces, i.e. everything the human-version labels can refer to."""
    path = os.path.join(mafa_root, traces_rel)
    if path.endswith(".json"):
        traces = [dict(it, trace_id=it["id"]) for it in json.load(open(path, encoding="utf-8"))["items"]]
    else:
        traces = [json.loads(l) for l in open(path, encoding="utf-8")]
    return [(t, *build(t, mafa_root)) for t in traces]


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/mafa-human-ai-annotation"
    rows = load_eval(root, *(sys.argv[2:3] or []))
    n_ok = 0
    for t, traj, m in rows:
        a = m["align"]
        n_ok += a["ok"]
        print(f"{'OK ' if a['ok'] else 'BAD'} {t['trace_id'][:70]:<70} steps mafa={a['n_mafa']} "
              f"ours={a['n_ours']} raw-order sha1 {a['raw_order_match']}/{a['n_mafa']} "
              f"parser-order {a['parser_order_match']}/{a['n_mafa']}  agents={len(m['inst2uid'])}")
    print(f"\nalignment: {n_ok}/{len(rows)} traces fully sha1-aligned")
