"""SAMT encoder wrapper (round 64), shared by the swift plugin, the probe and the MAA token export (no swift import).

GraphEncoder = HGFM v0.2 (hgfm.model_v02.HGFMv02, C1-C4) without its step / run heads; forward(B) -> (node states h,
hyperedge states m) with B from hgfm.midtrain.samt_graph.collate_graphs. graph_states() turns the states referenced by
the <graph> placeholders into the [G, d+2] vectors that the projector reads (same layout as hgfm.llm.model.graph_vectors:
state + [1,0] for a node, [0,1] for an edge).
"""
from typing import Any, Dict, List

import torch
from hgfm.data_v02 import SLOTS, N_PAIR
from hgfm.model_v02 import HGFMv02
from hgfm.midtrain.samt_graph import collate_graphs

D_IN = 777


class GraphEncoder(HGFMv02):
    """HGFM v0.2 (C1-C4) without the step / run heads; forward returns (node states, hyperedge states)."""

    def __init__(self, d_in=D_IN, d=192, **kw):
        super().__init__(d_in, len(SLOTS), N_PAIR, d=d, **kw)
        del self.step_head, self.run_head

    def forward(self, B):
        q_node = B['q'][B['node_run']]
        h = self.inp(torch.cat([B['X'], q_node], 1))
        r = self.rel(B['rel_txt'], B['q'][B['rel_run']], B['rg_src'], B['rg_dst'], B['rg_pair'])
        erv = r[B['edge_rel']]; q_edge = B['q'][B['edge_run']]
        for L in self.layers:
            h = L(h, q_node, q_edge, B['inc_e'], B['inc_v'], B['inc_s'], B['n_edges'], erv, B['edge_instr'])
        return h, self.layers[-1].last_m


def graph_states(enc, B, kind, idx):
    """Vectors [G, d+2] in placeholder order: node / edge state + flag ([1,0] node, [0,1] edge), as graph_vectors."""
    with torch.autocast(device_type=B['X'].device.type, enabled=False):
        h, m = enc({k: (v.float() if torch.is_tensor(v) and v.is_floating_point() else v) for k, v in B.items()})
        V = torch.zeros(len(idx), h.shape[1], device=h.device, dtype=h.dtype)
        isn = kind == 0
        if isn.any():
            V[isn] = h[idx[isn]]
        if (~isn).any():
            V[~isn] = m[idx[~isn]]
        flag = torch.stack([isn.float(), (~isn).float()], 1).to(h.dtype)
        return torch.cat([V, flag], 1)


def batch_graph(runs: List[str], refs: List[List], cache) -> Dict[str, Any]:
    """Batched hypergraph of the rows' runs + global (kind, index) of every placeholder, row-major."""
    B, v_off, e_off = collate_graphs([cache[r] for r in runs])
    kind, idx = [], []
    for i, rr in enumerate(refs):
        for k, j in rr:
            kind.append(0 if k == 'node' else 1); idx.append((v_off[i] if k == 'node' else e_off[i]) + int(j))
    return {'samt_graph': B, 'samt_kind': torch.tensor(kind, dtype=torch.long), 'samt_idx': torch.tensor(idx, dtype=torch.long)}
