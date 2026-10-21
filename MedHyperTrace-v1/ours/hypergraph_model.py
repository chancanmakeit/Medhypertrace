"""
MedHyperTrace backbone — relation-aware hypergraph convolution with three-level
attribution heads.

NAMING & LINEAGE (be precise when citing; "HGNN" below refers to the specific model
of Feng et al., not the generic category):

  * Base propagation: two-stage node -> hyperedge -> node message passing with degree
    normalization. This is the spatial (random-walk-normalized) form of the HGNN
    convolution  X' = Dv^{-1} H De^{-1} H^T X W   [Feng, Ji, Gao et al., "Hypergraph
    Neural Networks", AAAI 2019]; our two-stage view follows HGNN+ [Gao et al.,
    TPAMI 2022].
  * Relation awareness: each hyperedge TYPE (agg / ctx / role / phase) has its own
    projection W_r, fused by sum — the hyperedge-group idea of HGNN+ combined with
    R-GCN-style relation-specific parameters [Schlichtkrull et al., ESWC 2018].
  * Intra-hyperedge attention: softmax over member nodes within each hyperedge,
    in the spirit of HyperGAT [Ding et al., EMNLP 2020]. The overall two-phase
    set-function design is an instance of the AllSet framework [Chien et al.,
    ICLR 2022].
  * StandardHGNNPLayer: the ablation backbone — all hyperedges merged into one
    incidence, single shared W, mean two-stage propagation, no attention. This is
    mathematically the plain HGNN+ convolution (equivalent to DHG's HGNNPConv;
    implemented natively because the dhg wheel does not build on this Python).

Heads:
  * step head  : per-step logit; trained with a listwise softmax over each
    trajectory's steps (+ optional margin term), targets the EARLIEST injected step.
  * pair head  : coupled (agent, FM) logits  pair_logit = agent_logit ⊕ mode_logit
    (broadcast sum), so P(pair) is monotonically tied to P(agent) — hierarchical
    consistency by construction (improvement F).
  * agent head : per-agent-instance logit (also used to derive the agent-only metric).
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

EDGE_TYPES = ["agg", "ctx", "role", "phase"]
NODE_TYPES = ["step", "agent", "phase"]


class HGNNLayer(nn.Module):
    """Relation-aware hypergraph convolution (see module docstring for lineage)."""

    def __init__(self, dim: int, edge_types=EDGE_TYPES, attention: bool = True):
        super().__init__()
        self.edge_types = edge_types
        self.attention = attention
        self.W_r = nn.ModuleDict({r: nn.Linear(dim, dim, bias=False) for r in edge_types})
        self.W_self = nn.Linear(dim, dim)
        if attention:
            self.att = nn.ModuleDict({r: nn.Linear(2 * dim, 1) for r in edge_types})
        self.norm = nn.LayerNorm(dim)

    def forward(self, V, incidence):
        out = self.W_self(V)
        for r in self.edge_types:
            H = incidence.get(r)
            if H is None or H.numel() == 0 or H.shape[1] == 0:
                continue
            Vr = self.W_r[r](V)
            deg_e = H.sum(0).clamp(min=1.0)
            edge_msg = (H.t() @ Vr) / deg_e.unsqueeze(1)
            if self.attention:
                Nn, Er = H.shape
                node_ctx = Vr.unsqueeze(1).expand(Nn, Er, -1)
                edge_ctx = edge_msg.unsqueeze(0).expand(Nn, Er, -1)
                score = self.att[r](torch.cat([node_ctx, edge_ctx], -1)).squeeze(-1)
                score = score.masked_fill(H == 0, float("-inf"))
                alpha = torch.nan_to_num(torch.softmax(score, dim=0), nan=0.0)
                edge_msg = alpha.t() @ Vr
            deg_v = H.sum(1).clamp(min=1.0)
            out = out + (H @ edge_msg) / deg_v.unsqueeze(1)
        return self.norm(F.relu(out))


class StandardHGNNPLayer(nn.Module):
    """Plain HGNN+ convolution (backbone ablation): merged incidence, single W,
    mean two-stage propagation, no relation types, no attention."""

    def __init__(self, dim: int):
        super().__init__()
        self.W = nn.Linear(dim, dim, bias=False)
        self.W_self = nn.Linear(dim, dim)
        self.norm = nn.LayerNorm(dim)

    def forward(self, V, incidence):
        Hs = [H for H in incidence.values() if H is not None and H.numel() and H.shape[1]]
        out = self.W_self(V)
        if Hs:
            H = torch.cat(Hs, dim=1)
            Vw = self.W(V)
            deg_e = H.sum(0).clamp(min=1.0)
            edge_msg = (H.t() @ Vw) / deg_e.unsqueeze(1)
            deg_v = H.sum(1).clamp(min=1.0)
            out = out + (H @ edge_msg) / deg_v.unsqueeze(1)
        return self.norm(F.relu(out))


class MedHyperTrace(nn.Module):
    def __init__(self, in_dims: dict, hidden: int = 128, layers: int = 2,
                 n_fm: int = 14, attention: bool = True,
                 backbone: str = "relation"):
        super().__init__()
        self.enc = nn.ModuleDict({t: nn.Linear(in_dims[t], hidden) for t in NODE_TYPES})
        self.type_emb = nn.Embedding(len(NODE_TYPES), hidden)
        mk = (lambda: HGNNLayer(hidden, attention=attention)) if backbone == "relation" \
             else (lambda: StandardHGNNPLayer(hidden))
        self.layers = nn.ModuleList([mk() for _ in range(layers)])
        self.step_head = nn.Sequential(nn.Linear(2 * hidden, hidden), nn.ReLU(),
                                       nn.Linear(hidden, 1))
        self.agent_head = nn.Sequential(nn.Linear(2 * hidden, hidden), nn.ReLU(),
                                        nn.Linear(hidden, 1))
        self.mode_head = nn.Sequential(nn.Linear(2 * hidden, hidden), nn.ReLU(),
                                       nn.Linear(hidden, n_fm))

    def encode_nodes(self, feats, type_ids, type_slices):
        N = type_ids.shape[0]
        Hd = self.type_emb.embedding_dim
        V = torch.zeros(N, Hd, device=type_ids.device)
        for t in NODE_TYPES:
            sl = type_slices[t]
            if feats[t].shape[0] > 0:
                V[sl] = self.enc[t](feats[t])
        return V + self.type_emb(type_ids)

    def forward(self, feats, type_ids, type_slices, incidence):
        V0 = self.encode_nodes(feats, type_ids, type_slices)
        V = V0
        for layer in self.layers:
            V = layer(V, incidence)
        Vcat = torch.cat([V, V0], dim=-1)
        step_logit = self.step_head(Vcat[type_slices["step"]]).squeeze(-1)
        agent_logit = self.agent_head(Vcat[type_slices["agent"]]).squeeze(-1)
        mode_logit = self.mode_head(Vcat[type_slices["agent"]])
        # improvement F: coupled pair logits — hierarchical consistency by construction
        pair_logit = mode_logit + agent_logit.unsqueeze(1)
        return step_logit, agent_logit, pair_logit
