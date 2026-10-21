"""HGFM v0: query-conditioned directed hypergraph encoder (round 33, CPU-sized).

h_i^0 = MLP([x_i ; q]).  Per layer, for each hyperedge type tau in
{read (tail->head), read_rev (head->tails), event (members), agent (members)}:
   m_e = mean_{v in source(e)} h_v ;  a_i^tau = mean_{e delivering to i} W_tau m_e
   h_i <- LN(h_i + GELU(W_0 h_i + sum_tau a_i^tau))
Heads: step-level code logits (9) from [h_i ; q]; run-level logits (wrong, 2.1.1) from
[mean_i h_i ; h_last ; q].  layers=0 gives the no-structure ablation (same features).
"""
import torch, torch.nn as nn

TYPES = ("read", "read_rev", "event", "agent")


class HGLayer(nn.Module):
    def __init__(self, d):
        super().__init__()
        self.W = nn.ModuleDict({t: nn.Linear(d, d) for t in TYPES}); self.W0 = nn.Linear(d, d); self.ln = nn.LayerNorm(d)

    def forward(self, h, inc):
        out = self.W0(h)
        for t in TYPES:
            src, eid, dst, deid, ne = inc[t]
            if ne == 0: continue
            d = h.shape[1]
            m = torch.zeros(ne, d).index_add_(0, eid, h[src]); cnt = torch.zeros(ne).index_add_(0, eid, torch.ones(len(eid))).clamp(min=1)
            m = self.W[t](m / cnt[:, None])
            a = torch.zeros_like(h).index_add_(0, dst, m[deid]); c2 = torch.zeros(h.shape[0]).index_add_(0, dst, torch.ones(len(dst))).clamp(min=1)
            out = out + a / c2[:, None]
        return self.ln(h + nn.functional.gelu(out))


class HGFMv0(nn.Module):
    def __init__(self, d_in, d_q=384, d=192, layers=2, n_codes=9, drop=0.1):
        super().__init__()
        self.inp = nn.Sequential(nn.Linear(d_in + d_q, d), nn.GELU(), nn.Dropout(drop), nn.Linear(d, d))
        self.layers = nn.ModuleList([HGLayer(d) for _ in range(layers)])
        self.step_head = nn.Sequential(nn.Linear(d + d_q, d), nn.GELU(), nn.Dropout(drop), nn.Linear(d, n_codes))
        self.run_head = nn.Sequential(nn.Linear(2 * d + d_q, d), nn.GELU(), nn.Dropout(drop), nn.Linear(d, 2))

    def forward(self, B):
        q = B["q"][B["node_run"]]
        h = self.inp(torch.cat([B["X"], q], 1))
        for L in self.layers: h = L(h, B["inc"])
        step_logits = self.step_head(torch.cat([h, q], 1))
        R = B["q"].shape[0]
        pooled = torch.zeros(R, h.shape[1]).index_add_(0, B["node_run"], h) / B["n_nodes"][:, None]
        run_logits = self.run_head(torch.cat([pooled, h[B["last"]], B["q"]], 1))
        return step_logits, run_logits


def collate(graphs):
    X, NR, Y, last, nn_ = [], [], [], [], []
    inc = {t: ([], [], [], [], 0) for t in TYPES}
    inc = {t: [[], [], [], [], 0] for t in TYPES}
    off = 0
    for r, g in enumerate(graphs):
        n = g["X"].shape[0]; X.append(torch.from_numpy(g["X"])); Y.append(torch.from_numpy(g["Y"]))
        NR += [r] * n; last.append(off + n - 1); nn_.append(n)
        def add(t, srcs, dsts):
            e = inc[t][4]
            inc[t][0] += [off + s for s in srcs]; inc[t][1] += [e] * len(srcs)
            inc[t][2] += [off + d for d in dsts]; inc[t][3] += [e] * len(dsts); inc[t][4] = e + 1
        for tail, head in g["read"]:
            add("read", tail, [head]); add("read_rev", [head], tail)
        for m in g["event"]: add("event", m, m)
        for m in g["agent"]: add("agent", m, m)
        off += n
    B = {"X": torch.cat(X), "Y": torch.cat(Y), "node_run": torch.tensor(NR), "last": torch.tensor(last),
         "n_nodes": torch.tensor(nn_, dtype=torch.float32), "q": torch.from_numpy(__import__("numpy").stack([g["q"] for g in graphs])),
         "run_y": torch.tensor([[g["wrong"], g["y211"]] for g in graphs], dtype=torch.float32)}
    B["inc"] = {t: (torch.tensor(v[0], dtype=torch.long), torch.tensor(v[1], dtype=torch.long),
                    torch.tensor(v[2], dtype=torch.long), torch.tensor(v[3], dtype=torch.long), v[4]) for t, v in inc.items()}
    return B
