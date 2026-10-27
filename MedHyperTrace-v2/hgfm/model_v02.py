"""HGFM v0.2 encoder: C1-C4 of docs/design/HGFM_design_v0.2.md (round 35).

Incidence entries are (edge, node, slot); every edge has a relation id rho and an
instruction embedding. Per trajectory a relation graph is built over the relations
present (two relations are linked by a (slot_i, slot_j) edge when they share a node).

C2 relation encoder (HYPER / ULTRA, semantics from REEF / IHP):
   r_rho^0 = MLP([emb(relation text) ; q]);  L_r layers of message passing on the
   relation graph, messages modulated by a learned embedding of the (slot_i, slot_j) pair.
C1 + C3 + C4 entity encoder, per layer:
   node -> edge (query-aware attention within each edge, HyperG PHL):
       a_{v,e} = softmax_v( w . tanh(W_h (h_v * pos(slot_v)) + W_q q) )
       m_e = sum_v a_{v,e} * W_m (h_v * pos(slot_v))  +  gamma * W_p instr_e      (IHP)
       m_e = m_e * phi(r_rho(e))                                                (HYPER-style modulation)
   edge -> node (query as key, HyperG):
       b_{e,u} = softmax_e( (W_k m_e) . (W_qq [h_u ; q]) / sqrt(d) ) over edges incident to u
       h_u <- LN(h_u + GELU(W_0 h_u + sum_e b_{e,u} * W_o (m_e * pos(slot_u))))
   read hyperedges are added in both directions (tail->head, head->tails) as separate relations.
Heads as in v0 (step x code, run-level).  gamma=0 / no relation graph / no positions /
query concatenation instead of attention are the component ablations.
Round 64: every tensor is created on the input's device / dtype, so the encoder also runs on GPU (SAMT);
CPU results are bit-identical to the previous version.
"""
import math, torch, torch.nn as nn


def scatter_softmax(score, group, n_groups):
    mx = torch.full((n_groups,), -1e9, dtype=score.dtype, device=score.device).scatter_reduce(0, group, score, reduce="amax", include_self=True)
    ex = torch.exp(score - mx[group])
    den = torch.zeros(n_groups, dtype=ex.dtype, device=ex.device).index_add_(0, group, ex).clamp(min=1e-9)
    return ex / den[group]


class RelEncoder(nn.Module):
    def __init__(self, d, d_txt, d_q, n_pair, layers=2):
        super().__init__()
        self.inp = nn.Sequential(nn.Linear(d_txt + d_q, d), nn.GELU(), nn.Linear(d, d))
        self.pair = nn.Embedding(n_pair, d)
        self.W = nn.ModuleList([nn.Linear(d, d) for _ in range(layers)]); self.ln = nn.ModuleList([nn.LayerNorm(d) for _ in range(layers)])

    def forward(self, rel_txt, rel_q, rg_src, rg_dst, rg_pair):
        r = self.inp(torch.cat([rel_txt, rel_q], 1))
        for W, ln in zip(self.W, self.ln):
            if len(rg_src):
                msg = W(r[rg_src] * self.pair(rg_pair))
                agg = torch.zeros_like(r).index_add_(0, rg_dst, msg)
                cnt = torch.zeros(r.shape[0], dtype=r.dtype, device=r.device).index_add_(0, rg_dst, torch.ones(len(rg_dst), dtype=r.dtype, device=r.device)).clamp(min=1)
                r = ln(r + nn.functional.gelu(agg / cnt[:, None]))
        return r


class EntLayer(nn.Module):
    def __init__(self, d, d_q, d_txt, n_slot, use_pos=True, use_instr=True, use_rel=True, query_attn=True):
        super().__init__()
        self.use_pos, self.use_instr, self.use_rel, self.query_attn = use_pos, use_instr, use_rel, query_attn
        self.pos = nn.Embedding(n_slot, d); nn.init.normal_(self.pos.weight, 1.0, 0.02)
        self.Wh, self.Wq, self.w = nn.Linear(d, d), nn.Linear(d_q, d), nn.Linear(d, 1)
        self.Wm, self.Wp = nn.Linear(d, d), nn.Linear(d_txt, d)
        self.gamma = nn.Parameter(torch.tensor(0.5))
        self.phi = nn.Linear(d, d)
        self.Wk, self.Wqq, self.Wo, self.W0 = nn.Linear(d, d), nn.Linear(d + d_q, d), nn.Linear(d, d), nn.Linear(d, d)
        self.ln = nn.LayerNorm(d)

    def forward(self, h, q_node, q_edge, inc_e, inc_v, inc_s, n_edges, edge_rel_vec, edge_instr):
        d = h.shape[1]
        hv = h[inc_v] * (self.pos(inc_s) if self.use_pos else 1.0)
        if self.query_attn:
            a = scatter_softmax(self.w(torch.tanh(self.Wh(hv) + self.Wq(q_edge[inc_e]))).squeeze(1), inc_e, n_edges)
        else:
            cnt = torch.zeros(n_edges, dtype=h.dtype, device=h.device).index_add_(0, inc_e, torch.ones(len(inc_e), dtype=h.dtype, device=h.device)).clamp(min=1); a = 1.0 / cnt[inc_e]
        m = torch.zeros(n_edges, d, dtype=h.dtype, device=h.device).index_add_(0, inc_e, a[:, None] * self.Wm(hv))
        if self.use_instr: m = m + self.gamma * self.Wp(edge_instr)
        if self.use_rel: m = m * torch.sigmoid(self.phi(edge_rel_vec))
        msg = self.Wo(m[inc_e] * (self.pos(inc_s) if self.use_pos else 1.0))
        if self.query_attn:
            key = (self.Wk(m)[inc_e] * self.Wqq(torch.cat([h, q_node], 1))[inc_v]).sum(1) / math.sqrt(d)
            b = scatter_softmax(key, inc_v, h.shape[0])
        else:
            cnt = torch.zeros(h.shape[0], dtype=h.dtype, device=h.device).index_add_(0, inc_v, torch.ones(len(inc_v), dtype=h.dtype, device=h.device)).clamp(min=1); b = 1.0 / cnt[inc_v]
        agg = torch.zeros_like(h).index_add_(0, inc_v, b[:, None] * msg)
        self.last_m = m                     # hyperedge representations, read by HGFMv02.encode
        return self.ln(h + nn.functional.gelu(self.W0(h) + agg))


class HGFMv02(nn.Module):
    def __init__(self, d_in, n_slot, n_pair, d_q=384, d_txt=384, d=192, layers=2, rel_layers=2, n_codes=9, drop=0.1,
                 use_pos=True, use_instr=True, use_rel=True, query_attn=True):
        super().__init__()
        self.use_rel = use_rel
        self.inp = nn.Sequential(nn.Linear(d_in + d_q, d), nn.GELU(), nn.Dropout(drop), nn.Linear(d, d))
        self.rel = RelEncoder(d, d_txt, d_q, n_pair, rel_layers)
        self.layers = nn.ModuleList([EntLayer(d, d_q, d_txt, n_slot, use_pos, use_instr, use_rel, query_attn) for _ in range(layers)])
        self.step_head = nn.Sequential(nn.Linear(d + d_q, d), nn.GELU(), nn.Dropout(drop), nn.Linear(d, n_codes))
        self.run_head = nn.Sequential(nn.Linear(2 * d + d_q, d), nn.GELU(), nn.Dropout(drop), nn.Linear(d, 2))

    @torch.no_grad()
    def encode(self, B):
        """Node states h [N, d], hyperedge states m [E, d] (last layer) and logits,
        for exporting graph tokens to the LLM layer (C6)."""
        sl, rl = self.forward(B)
        return self._h, self.layers[-1].last_m, sl, rl

    def forward(self, B):
        q_node = B["q"][B["node_run"]]
        h = self.inp(torch.cat([B["X"], q_node], 1))
        r = self.rel(B["rel_txt"], B["q"][B["rel_run"]], B["rg_src"], B["rg_dst"], B["rg_pair"])
        erv = r[B["edge_rel"]]; q_edge = B["q"][B["edge_run"]]
        for L in self.layers:
            h = L(h, q_node, q_edge, B["inc_e"], B["inc_v"], B["inc_s"], B["n_edges"], erv, B["edge_instr"])
        self._h = h
        step_logits = self.step_head(torch.cat([h, q_node], 1))
        R = B["q"].shape[0]
        pooled = torch.zeros(R, h.shape[1], dtype=h.dtype, device=h.device).index_add_(0, B["node_run"], h) / B["n_nodes"][:, None]
        return step_logits, self.run_head(torch.cat([pooled, h[B["last"]], B["q"]], 1))
