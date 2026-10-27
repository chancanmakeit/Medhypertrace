"""Graph inputs for structure-aware mid-training (SAMT, round 64) — label-free version of the MAA featurisation.

`featurise(r, node_emb, text_emb)` returns the encoder inputs of one mas-traj/1 run with EXACTLY the layout HGFM v0.2
was built on for MedAgentAudit (hgfm.data_maa.Featuriser.run + hgfm.train_v02.attach_edges, gold=False):
  X  [n, 777] = MiniLM(output[:2000]) | MiniLM(f"{phase} | {agent_role}") | 9 scalars
                (has_answer, answer==final, answer==round majority, agree, round/R, order/n, is_last, |sources|/5, readers/5)
  q  [384]    = MiniLM(query[:2000]) + 0.5 * MiniLM(framework_description)
  e_inc / e_rel / e_instr / r_txt / r_links from hgfm.data_v02.edges_of / relation_graph (raw `phase`, as for MAA).
No labels are read, so it works for public datasets without audit items / gold answers (answer scalars are then 0).
node_emb(text) -> fp16-rounded 384-d vector (as the MAA emb.npy table); text_emb(list) -> fp32 [k, 384] (as TextEmb).
`check_against_maa.py`-style verification: tests/test_samt_graph.py compares with the MAA graphs_v02 cache.
`collate_graphs(gs)` = the graph part of hgfm.train_v02.collate (same field names and order), float32, no targets.
"""
import collections
import numpy as np
import torch
from hgfm.data_v02 import edges_of, relation_graph

N_SCAL = 9


def node_texts(r):
    """Texts embedded with the node table (fp16), as hgfm.embed_maa.texts_of."""
    yield (r["task"].get("query") or "")[:2000]
    for s in r["steps"]:
        yield (s.get("output") or "")[:2000]
        yield f"{s['phase']} | {s['agent_role']}"


def edge_texts(r):
    """Texts embedded with TextEmb (fp32): edge instructions, relation texts, framework description."""
    E = edges_of(r)
    for e in E:
        yield e["instr"]; yield e["rel_text"]
    yield r.get("framework_description") or ""


def featurise(r, node_emb, text_emb):
    st = r["steps"]; n = len(st)
    if n == 0:
        return None
    sid = {s["step_id"]: i for i, s in enumerate(st)}
    final = (r.get("final") or {}).get("answer")
    rounds = [s.get("round") or 1 for s in st]; R = max(rounds)
    sa = [(s.get("structured") or {}) for s in st]
    maj = {}
    for rr in set(rounds):
        a = [str(x.get("answer")) for x, ro in zip(sa, rounds) if ro == rr and x.get("answer") is not None]
        maj[rr] = collections.Counter(a).most_common(1)[0][0] if a else None
    readers = collections.Counter(sid[x["step_id"]] for s in st for x in (s.get("sources") or []) if x["step_id"] in sid)
    X = np.zeros((n, 384 * 2 + N_SCAL), dtype=np.float32)
    for i, s in enumerate(st):
        a = sa[i].get("answer"); ag = sa[i].get("agree")
        X[i, :384] = node_emb((s.get("output") or "")[:2000]); X[i, 384:768] = node_emb(f"{s['phase']} | {s['agent_role']}")
        X[i, 768:768 + N_SCAL] = [a is not None, a is not None and str(a) == str(final), a is not None and str(a) == maj[rounds[i]],
                                  0 if ag is None else (1 if str(ag).lower() in ("true", "yes", "1") else -1),
                                  rounds[i] / R, i / max(n - 1, 1), i == n - 1, len(s.get("sources") or []) / 5, readers[i] / 5]
    E = edges_of(r); rels, links = relation_graph(E); ri = {k: i for i, k in enumerate(rels)}
    rel_text = {e["rel_key"]: e["rel_text"] for e in E}
    q = node_emb((r["task"].get("query") or "")[:2000]).astype(np.float32) + 0.5 * text_emb([r.get("framework_description") or ""])[0]
    return {"run_id": r["run_id"], "X": X, "q": q.astype(np.float32),
            "e_inc": [(k, v, s) for k, e in enumerate(E) for v, s in e["members"]],
            "e_rel": [ri[e["rel_key"]] for e in E],
            "e_instr": text_emb([e["instr"] for e in E]).astype(np.float32),
            "r_txt": text_emb([rel_text[k] for k in rels]).astype(np.float32), "r_links": links}


def collate_graphs(gs):
    """Graph fields of hgfm.train_v02.collate (same names / order / offsets), float32 tensors, no targets.
    Also returns node and edge offsets per graph."""
    X, NR, last, nn_, inc_e, inc_v, inc_s, e_rel, e_run, e_instr, r_txt, r_run, rg_s, rg_d, rg_p = ([] for _ in range(15))
    v_off, e_off = [], []
    vo = eo = ro = 0
    for k, g in enumerate(gs):
        n = g["X"].shape[0]; X.append(torch.as_tensor(np.asarray(g["X"], dtype=np.float32)))
        NR += [k] * n; last.append(vo + n - 1); nn_.append(n)
        ne = len(g["e_rel"]); nr = len(g["r_txt"])
        v_off.append(vo); e_off.append(eo)
        for e, v, s in g["e_inc"]:
            inc_e.append(eo + e); inc_v.append(vo + v); inc_s.append(s)
        e_rel += [ro + x for x in g["e_rel"]]; e_run += [k] * ne
        e_instr.append(torch.as_tensor(np.asarray(g["e_instr"], dtype=np.float32)).reshape(-1, 384))
        r_txt.append(torch.as_tensor(np.asarray(g["r_txt"], dtype=np.float32)).reshape(-1, 384)); r_run += [k] * nr
        for a, b, p in g["r_links"]:
            rg_s.append(ro + a); rg_d.append(ro + b); rg_p.append(p)
        vo += n; eo += ne; ro += nr
    L = lambda x: torch.tensor(x, dtype=torch.long)
    return {"X": torch.cat(X), "node_run": L(NR), "last": L(last), "n_nodes": torch.tensor(nn_, dtype=torch.float32),
            "q": torch.as_tensor(np.stack([np.asarray(g["q"], dtype=np.float32) for g in gs])),
            "inc_e": L(inc_e), "inc_v": L(inc_v), "inc_s": L(inc_s), "n_edges": eo, "edge_rel": L(e_rel), "edge_run": L(e_run),
            "edge_instr": torch.cat(e_instr) if e_instr else torch.zeros(0, 384), "rel_txt": torch.cat(r_txt), "rel_run": L(r_run),
            "rg_src": L(rg_s), "rg_dst": L(rg_d), "rg_pair": L(rg_p)}, v_off, e_off


def to_device(B, device):
    return {k: (v.to(device) if torch.is_tensor(v) else v) for k, v in B.items()}
