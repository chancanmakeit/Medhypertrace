"""Hyperedge-level features for HGFM v0.2 (round 35): slots (C1), relation keys and
relation texts (C2), hyperedge instructions (C3), on top of data_maa's node features.

Every hyperedge is undirected at the incidence level; direction lives in the slots
(read_head vs read_tail_<how>), so edge->node delivers to heads and tails alike.
Texts are kept generic (phase / how / round, never specialty names) so the vocabulary is
small and transfers across MAS; relation embeddings come from the text, so a relation
never seen in training still gets an embedding.
"""
import collections, hashlib
import numpy as np

SLOTS = ["read_head", "read_tail_matched", "read_tail_protocol", "read_tail_verbatim", "read_tail_excerpt",
         "read_tail_structured_field", "read_tail_control", "event_member", "agent_member"]
S2I = {s: i for i, s in enumerate(SLOTS)}
N_PAIR = len(SLOTS) * len(SLOTS)


def edges_of(r):
    """Returns list of dict(members=[(step_idx, slot)], rel_key, rel_text, instr)."""
    st = r["steps"]; sid = {s["step_id"]: i for i, s in enumerate(st)}; out = []
    for i, s in enumerate(st):
        src = [(sid[x["step_id"]], x.get("how") or "verbatim") for x in s["sources"] if x["step_id"] in sid]
        if not src: continue
        hows = sorted({h for _, h in src}); tph = sorted({st[j]["phase"] for j, _ in src})
        mem = [(i, S2I["read_head"])] + [(j, S2I.get(f"read_tail_{h}", S2I["read_tail_verbatim"])) for j, h in src]
        out.append({"members": mem, "rel_key": f"read->{s['phase']}",
                    "rel_text": f"a {s['phase']} step reads the outputs of earlier steps",
                    "instr": f"In round {s['round']}, a {s['phase']} step read {min(len(src), 6)} earlier outputs from {', '.join(tph)} steps ({', '.join(hows)})."})
    ev = collections.defaultdict(list); ag = collections.defaultdict(list)
    for i, s in enumerate(st):
        ev[(s["round"], s["phase"])].append(i); ag[s["agent_id"]].append(i)
    for (rd, ph), m in ev.items():
        if len(m) > 1:
            out.append({"members": [(i, S2I["event_member"]) for i in m], "rel_key": f"event:{ph}",
                        "rel_text": f"several {ph} steps taken in the same round", "instr": f"{min(len(m), 6)} {ph} steps in round {rd}."})
    for a, m in ag.items():
        if len(m) > 1:
            phs = sorted({st[i]["phase"] for i in m})
            out.append({"members": [(i, S2I["agent_member"]) for i in m], "rel_key": "agent",
                        "rel_text": "all steps taken by one agent", "instr": f"One agent acted {min(len(m), 6)} times across {', '.join(phs)}."})
    return out


def relation_graph(edges):
    """Relations present + (rho_a, rho_b, slot pair) links when two relations share a node."""
    rels = sorted({e["rel_key"] for e in edges}); ri = {k: i for i, k in enumerate(rels)}
    at = collections.defaultdict(set)
    for e in edges:
        for v, s in e["members"]: at[v].add((ri[e["rel_key"]], s))
    links = set()
    for v, lst in at.items():
        lst = list(lst)
        for a, sa in lst:
            for b, sb in lst:
                if a != b: links.add((a, b, sa * len(SLOTS) + sb))
    return rels, sorted(links)


class TextEmb:
    """Small cache for relation / instruction texts (MiniLM, same model as node texts)."""
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.m = SentenceTransformer(__import__("os").environ.get("MHT_MINILM", "sentence-transformers/all-MiniLM-L6-v2"), device="cpu"); self.c = {}

    def __call__(self, texts):
        new = [t for t in set(texts) if t not in self.c]
        if new:
            for t, v in zip(new, self.m.encode(new, batch_size=128, normalize_embeddings=True)): self.c[t] = v.astype(np.float32)
        return np.stack([self.c[t] for t in texts]) if texts else np.zeros((0, 384), np.float32)
