"""Proposed fix for MAFA scripts/eval_attribution.py apply_layer (MAFA cc1606f).

Problem: on the responsibility layers every non-responsible agent becomes a NEGATIVE ("ok") for agent_auroc,
including (1) agents of a present defect whose contrib is "unsure" (the tool clears `instances` for
unsure, so only the code's `agents` are known), and (2) on the coded layer, agents responsible only through
the `_uncoded` row. Both are undecided / responsible, not "not responsible"; mirroring the defect layer
(where "unsure" is excluded), they should be excluded from AUROC.
"""


def apply_layer(labels, layer):
    if layer == "defect":
        return labels
    sfx = "_any" if layer == "responsibility_any" else ""
    out = []
    for L in labels:
        if L.get("split") != "faulty" or "escape" not in L or L.get("escape") in (None, "unsure"):
            continue
        L = dict(L)
        resp = list(L.get("responsible_agents" + sfx) or [])
        undecided = set()
        defects = dict(L.get("codes") or {})
        if L.get("uncoded"):
            defects["_uncoded"] = L["uncoded"]
        for c, cl in defects.items():
            if (cl or {}).get("decision") == "present" and ((cl.get("contrib") or {}).get("decision") == "unsure"):
                undecided.update(cl.get("agents") or [])
        if not sfx:                                   # coded layer: responsible only via the uncoded row
            undecided.update(set(L.get("responsible_agents_any") or []) - set(resp))
        L["earliest_step"] = L.get("earliest_responsible_step" + sfx)
        L["earliest_step_agent"] = L.get("earliest_responsible_agent" + sfx)
        L["faulty_agents"] = resp
        L["agents"] = {u: ("fault" if u in resp else "unsure" if u in undecided else "ok")
                       for u in (L.get("all_agents") or list(L.get("agents") or {}))}
        L["label_layer"] = layer
        out.append(L)
    return out
