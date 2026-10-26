"""Shared conventions for converting public MAS failure-attribution datasets to mas-traj/1 (round 57).

Everything that the partner (medical-aegis) might still change is implemented HERE, once:
  * record / step layout (mirrors medical-aegis scripts/export_schema_v1.convert())
  * question_id, run_index, run_id
  * source items  {"step_id", "how", "inferred"}  and provenance.sources_recorded = False
  * framework / framework_family from framework_registry_public.yaml
  * output_tokens_est tokenizer
  * text-match source inference for datasets with per-step inputs
  * deterministic jsonl.gz writing

Conventions agreed with medical-aegis (issue #1, reply to our round 57):
  how in {verbatim, excerpt, structured_field, summary, control}; inferred in {text_match, protocol};
  sources None = unknown, [] = reads no earlier step; run_mode "normal" for every non-injected run;
  dataset annotations only in labels.external; a public framework with the same architecture as one of
  the partner's medical families takes THAT family name (registry field family_reason records why).
"""
import gzip
import hashlib
import importlib.util
import io
import json
import os
import re
from collections import Counter, defaultdict

import yaml

from data_tools.maa_exclusion import norm_stem

SCHEMA = "mas-traj/1"
HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(HERE, "framework_registry_public.yaml")
PARTNER_EXPORT = "/home/claude/medical-aegis/scripts/export_schema_v1.py"
HOWS = ("verbatim", "excerpt", "structured_field", "summary", "control")
INFERRED = ("text_match", "protocol")

# ------------------------------------------------------------------ tokenizer
try:   # same fixed tokenizer as the partner's exporter
    import tiktoken
    _ENC = tiktoken.get_encoding("o200k_base")
    TOKENIZER = "tiktoken:o200k_base"
except Exception:      # offline: the partner's own fallback
    _ENC = None
    TOKENIZER = "regex:words+punct"


def count_tokens(text):
    text = text or ""
    if _ENC is not None:
        return len(_ENC.encode(text, disallowed_special=()))
    return len(re.findall(r"\w+|[^\w\s]", text))


# ------------------------------------------------------------------ registry
_REG = None


def registry():
    global _REG
    if _REG is None:
        _REG = (yaml.safe_load(open(REGISTRY_PATH, encoding="utf-8")) or {}).get("frameworks", {})
    return _REG


def fw_meta(fw):
    reg = registry()
    if fw not in reg:
        raise KeyError(f"framework {fw!r} missing from framework_registry_public.yaml")
    return reg[fw]


# ------------------------------------------------------------------ ids
def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s or "agent").lower()).strip("_") or "agent"


# benchmark prefix used in question_id, normalised so that the same task gets the same id in every public
# dataset (task.dataset keeps each dataset's own benchmark name). SWE-bench Lite / full share instance ids.
QID_BENCH = {"GSM": "GSM-Plus", "gsm-plus": "GSM-Plus", "Olympiad": "OlympiadBench", "olympiadbench": "OlympiadBench",
             "mmlu": "MMLU", "humaneval": "HumanEval", "gaia": "GAIA", "SWE-Bench-Lite": "SWE-bench",
             "swe-bench-lite": "SWE-bench", "assistantbench": "AssistantBench"}


def question_id(benchmark, native_id=None, question=None):
    """'<benchmark>/<native id>' or '<benchmark>/q_<sha1(norm_stem(question))[:12]>'."""
    benchmark = QID_BENCH.get(benchmark, benchmark)
    if native_id not in (None, ""):
        return f"{benchmark}/{native_id}"
    h = hashlib.sha1(norm_stem(question or "").encode()).hexdigest()[:12]
    return f"{benchmark}/q_{h}"


def make_run_id(dataset, framework, model, qid, run_mode, run_index):
    # partner's own format is <framework>|<model>|<benchmark>|<id>|<mode>|r<k>; we prefix the source
    # dataset because the same (framework, question, model) occurs in several public datasets.
    return f"{dataset}|{framework}|{model or 'unknown-model'}|{qid}|{run_mode}|r{run_index}"


def assign_run_ids(records, dataset):
    """run_index = index among runs of the same (framework, question_id, model) in source order;
    run_id unique (asserted)."""
    k = Counter()
    for r in records:
        key = (r["framework"], r["question_id"], r["model"].get("name"))
        r["run_index"] = k[key]
        k[key] += 1
        r["run_id"] = make_run_id(dataset, r["framework"], r["model"].get("name"), r["question_id"],
                                  r["run_mode"], r["run_index"])
    ids = [r["run_id"] for r in records]
    dup = [x for x, n in Counter(ids).items() if n > 1]
    assert not dup, f"duplicate run_ids: {dup[:3]}"


# ------------------------------------------------------------------ sources
def src(step_id, how, inferred):
    assert how in HOWS, how
    assert inferred in INFERRED, inferred
    return {"step_id": step_id, "how": how, "inferred": inferred}


def proto(steps_or_ids, how="verbatim"):
    """protocol sources for a list of steps (dicts) or step ids, deduplicated, in order."""
    out, seen = [], set()
    for s in steps_or_ids:
        sid = s["step_id"] if isinstance(s, dict) else s
        if sid in seen:
            continue
        seen.add(sid)
        out.append(src(sid, how, "protocol"))
    return out


def merge_sources(*lists):
    """first occurrence of a step_id wins (callers list the strongest relation first); sorted by step order
    afterwards by finalize()."""
    out, seen = [], set()
    for lst in lists:
        for x in lst or []:
            if x["step_id"] not in seen:
                seen.add(x["step_id"])
                out.append(x)
    return out


# ------------------------------------------------------------------ steps / records
def make_step(order, kind, agent_id, agent_role, output, *, agent_label=None, phase="unknown", round_=None,
              event_ids=None, input_messages=None, sources=None, structured=None, tool_calls=None,
              finish_reason=None):
    """Field order and semantics as export_schema_v1.convert(). step_id = s<order>."""
    assert kind in ("llm", "tool")
    output = output if output is not None else ""
    return {
        "step_id": f"s{order}", "order": order, "kind": kind,
        "agent_id": agent_id, "agent_role": agent_role, "agent_label": agent_label,
        "phase": phase or "unknown", "round": round_,
        "event_ids": list(event_ids or []),
        "input_messages": None if kind == "tool" else input_messages,
        "sources": sources,
        "output": output,
        "structured": structured,
        "tool_calls": list(tool_calls or []),
        "finish_reason": finish_reason,
        "output_tokens_est": count_tokens(output) if kind == "llm" else None,
    }


def tool_call(name, arguments=None, result=None, error=None):
    return {"name": name, "arguments": arguments, "result": result, "error": error}


def finalize_sources(steps):
    """sort each step's sources by source order; drop self / later references (defensive)."""
    order = {s["step_id"]: s["order"] for s in steps}
    for s in steps:
        if s["sources"] is None:
            continue
        s["sources"] = sorted([x for x in s["sources"] if x["step_id"].startswith("task:")
                               or order.get(x["step_id"], 10 ** 9) < s["order"]],
                              key=lambda x: order.get(x["step_id"], -1))


def make_record(*, dataset, benchmark, framework, model, qid, query, steps, labels, provenance,
                images=None, observations=None, final_answer=None, final_response=None, final_source_step_ids=None,
                run_mode="normal"):
    meta = fw_meta(framework)
    finalize_sources(steps)
    has_inputs = any(s["input_messages"] is not None for s in steps if s["kind"] == "llm")
    lab = {"gold": None, "acceptable_answers": None, "is_correct": None, "is_valid": None, "status": None,
           "verification_path": None, "execution_successful": None, "injection": [], "injection_targets": [],
           "llm_meta": {}, "paired_normal_run_ids": []}
    lab.update(labels)
    prov = {"source_dataset": dataset, "source_record_id": None, "wrapper_contract": "public_dataset",
            "input_messages_clean": True if has_inputs else None,
            "sources_recorded": False, "history_alignment_ok": None, "reasoning_exported": False,
            "output_tokenizer": TOKENIZER, "converter": "data_tools.public_to_mas_traj (MHT r57)"}
    prov.update(provenance)
    return {
        "schema_version": SCHEMA,
        "run_id": None, "question_id": qid, "run_mode": run_mode, "run_index": None, "seed": None,
        "framework": framework, "framework_family": meta["family"],
        "framework_description": " ".join(str(meta.get("description") or "").split()) or None,
        "model": {"name": model or "unknown-model"},
        "task": {"dataset": benchmark, "query": query, "images": list(images or []),
                 "observations": list(observations or [])},
        "steps": steps,
        "final": {"answer": final_answer, "response": final_response,
                  "source_step_ids": list(final_source_step_ids or [])},
        "labels": lab,
        "provenance": prov,
    }


# ------------------------------------------------------------------ text-match source inference
_WS = re.compile(r"\s+")


def nws(s):
    return _WS.sub(" ", s or "").strip()


def probes_of(text, k=50, min_len=25):
    """probes from the BODY of an output (cf. medical-aegis check_trajectory_sources.probes / our MAA
    converter): <min_len chars -> none (undetectable); < 2k -> the whole text; else 3 windows of k chars at
    20 / 50 / 80 % of the text."""
    t = nws(text)
    if len(t) < min_len:
        return []
    if len(t) < 2 * k:
        return [t]
    return [t[int(len(t) * f) - k // 2: int(len(t) * f) - k // 2 + k] for f in (0.2, 0.5, 0.8)]


def infer_text_sources(steps, input_text_of, probe_text_of, exclude_text=""):
    """For every step with per-step input text: an earlier step is a source if a probe of its output (body
    windows) occurs in this step's input. how = verbatim when the whole normalised output occurs, else excerpt.
    Probes that also occur in `exclude_text` (task query) are ignored. Transitive copies are dropped: a
    candidate i is not counted when every matched probe occurs in the input no more often than in the outputs
    of the other matched candidates (i.e. it is explained by a later step quoting it).
    Returns stats dict."""
    excl = nws(exclude_text)
    pr = {}
    full = {}
    for s in steps:
        t = nws(probe_text_of(s))
        full[s["step_id"]] = t
        pr[s["step_id"]] = [p for p in probes_of(t) if p not in excl]
    st = Counter()
    for j, s in enumerate(steps):
        inp = input_text_of(s)
        if inp is None:
            continue
        inp = nws(inp)
        cands = []
        for i in range(j):
            p = steps[i]
            ps = pr[p["step_id"]]
            if not ps:
                continue
            hits = [x for x in ps if x in inp]
            if not hits:
                continue
            how = "verbatim" if full[p["step_id"]] in inp else "excerpt"
            cands.append((p, hits, how))
        kept = []
        for p, hits, how in cands:
            others = [full[q["step_id"]] for q, _, _ in cands if q is not p and full[q["step_id"]] != full[p["step_id"]]]
            explained = all(inp.count(h) <= sum(o.count(h) for o in others) for h in hits) and others
            if explained:
                st["dropped_transitive"] += 1
                continue
            kept.append(src(p["step_id"], how, "text_match"))
        s["sources"] = merge_sources(s["sources"] or [], kept) if s["sources"] else kept
        st["steps_with_inputs"] += 1
        st["steps_zero_sources"] += not s["sources"]
    return st


# ------------------------------------------------------------------ io
def write_jsonl_gz(records, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as g:
        for r in records:
            g.write((json.dumps(r, ensure_ascii=False) + "\n").encode("utf-8"))
    with open(path, "wb") as f:
        f.write(raw.getvalue())


def read_jsonl_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def partner_module():
    spec = importlib.util.spec_from_file_location("mae_export_schema_v1", PARTNER_EXPORT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def finish(records, dataset, out, extra_report=None):
    """assign ids, run the partner's check() on every record, write, print a one-line summary."""
    assign_run_ids(records, dataset)
    chk = partner_module().check
    bad = [(r["run_id"], p[:3]) for r in records for p in [chk(r)] if p]
    write_jsonl_gz(records, out)
    by = Counter(r["framework"] for r in records)
    print(f"{dataset}: wrote {len(records)} records -> {out}; check() problems in {len(bad)} records; "
          f"frameworks {dict(sorted(by.items()))}")
    for b in bad[:5]:
        print("  !!", b)
    if extra_report:
        print("  ", json.dumps(extra_report, sort_keys=True, default=str))
    return bad


def cli(convert_fn, dataset):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="/home/claude/public_mas/raw")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    records, rep = convert_fn(a.raw)
    finish(records, dataset, a.out, rep)
    side = a.out.replace(".jsonl.gz", "") + ".convert_report.json"
    json.dump(rep, open(side, "w"), indent=1, sort_keys=True, default=str)


def msg_text(content):
    """text of an OpenAI-style message content (str or list of parts); images -> '<image>'."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for p in content:
            if isinstance(p, dict):
                if p.get("type") == "text":
                    out.append(str(p.get("text") or ""))
                elif "image" in str(p.get("type")):
                    out.append("<image>")
            elif isinstance(p, str):
                out.append(p)
        return "\n".join(out)
    return str(content)
