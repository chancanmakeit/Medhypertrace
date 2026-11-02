"""E4 stage B (pre-registration E4 v1): BEFT -- train only injected value-projection biases b_v (+ the step-scoring head)
on TracerTraj, then score WW / TEgc / TT test. One initialisation per run (base or TAPT).

  torchrun --nproc_per_node 2 -m hgfm.e4.e4_beft --oat <OAT dir> --model <dir> --data_dir <tt_ww dir> --out <dir> \
      [--epochs 2 --accum 16 --lr 1e-3 --max_train_tokens 16384 --liger 1]

- Model: Qwen3-8B bf16, flash-attn 2, gradient checkpointing (non-reentrant), optional Liger (RMSNorm / RoPE / SwiGLU; no
  fused CE -- no vocabulary logits are computed). All weights frozen. Every layer's self_attn.v_proj gets a zero-initialised
  fp32 bias, added by a forward hook (Qwen3 has no q/k/v biases). Head: LayerNorm(H) -> Linear(H, 1), fp32.
- Input / step representation exactly as stage A (OAT serialisation, mean of the last hidden state over the step's tokens).
- Loss: cross-entropy over candidate (model) steps. Training trajectories <= --max_train_tokens only (pre-registered
  16,384, memory). Data parallel over GPUs (manual all-reduce of the ~41k trainable values at every optimizer step), one trajectory per GPU per micro-step, gradient accumulation --accum (effective batch
  accum x world size trajectories). AdamW (bias: no weight decay; head: 1e-2), constant LR after 10 warm-up steps.
- Validation (rank-AUROC on tt_val, trajectories <= 32,768 tokens) every half epoch; best state kept (biases + head, a few MB).
- Final scoring with the best state on who_and_when, traceelephant_gc, tt_test: native <= 32k, YaRN x4 for 32k-131k (as E1).
Outputs: <out>/best_state.pt, <out>/log.jsonl, <out>/scores.json ({"dataset|id": [candidate scores]}).
"""
import argparse, json, math, os, sys, time
import numpy as np
import torch
import torch.distributed as dist

from hgfm.e4.e4_features import step_token_ranges


def build(model_dir, yarn, liger, gc):
    if liger:
        from liger_kernel.transformers import apply_liger_kernel_to_qwen3
        apply_liger_kernel_to_qwen3(rope=True, rms_norm=True, swiglu=True, fused_linear_cross_entropy=False, cross_entropy=False)
    from transformers import AutoModelForCausalLM
    kw = {"dtype": torch.bfloat16, "attn_implementation": "flash_attention_2"}
    if yarn:
        kw["rope_scaling"] = {"rope_type": "yarn", "factor": 4.0, "original_max_position_embeddings": 32768}; kw["max_position_embeddings"] = 131072
    m = AutoModelForCausalLM.from_pretrained(model_dir, **kw)
    m.config.use_cache = False
    for p in m.parameters(): p.requires_grad_(False)
    if gc:
        m.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False}); m.enable_input_require_grads()
    return m


class Beft(torch.nn.Module):
    """Holds the trainable parameters: one fp32 bias per v_proj + the head; hooks add the biases."""
    def __init__(self, lm):
        super().__init__()
        layers = lm.model.layers
        self.bv = torch.nn.ParameterList([torch.nn.Parameter(torch.zeros(l.self_attn.v_proj.out_features)) for l in layers])
        H = lm.config.hidden_size; self.head = torch.nn.Sequential(torch.nn.LayerNorm(H), torch.nn.Linear(H, 1))
        self.hooks = [l.self_attn.v_proj.register_forward_hook(self._hook(i)) for i, l in enumerate(layers)]

    def _hook(self, i):
        def f(mod, inp, out): return out + self.bv[i].to(out.dtype)
        return f


def step_scores(lm, beft, enc, ranges, cand, dev):
    h = lm.model(input_ids=enc["input_ids"].to(dev), use_cache=False, return_dict=True).last_hidden_state[0]
    reps = torch.stack([h[ranges[j][0]: ranges[j][1] + 1].float().mean(0) for j in cand])
    return beft.head(reps).squeeze(-1)


def load_trajs(oat, specs):
    sys.path.insert(0, oat); cwd = os.getcwd(); os.chdir(oat)
    import data_pipeline as dp, extract_states as ex
    out = {}
    for name, spec in specs.items():
        rows = dp.load_who_and_when_trajectories(data_dir=spec) if spec.startswith("/") else dp.load_raw_trajectories(spec)
        for t in rows:
            text, bounds = ex._build_input_text(t)
            cand = [j for j in range(1, len(t["step_is_model"]) + 1) if t["step_is_model"][j - 1]]
            out[(name, t["id"])] = {"text": text, "bounds": bounds, "cand": cand, "label": t["mistake_step"] + 1}
    os.chdir(cwd); return out


def encode(tok, t):
    enc = tok(t["text"], return_tensors="pt", return_offsets_mapping=True)
    return enc, step_token_ranges(enc["offset_mapping"][0].tolist(), t["bounds"])


def main():
    ap = argparse.ArgumentParser()
    for k, v in (("oat", None), ("model", None), ("data_dir", None), ("out", None)): ap.add_argument("--" + k, default=v)
    ap.add_argument("--epochs", type=int, default=2); ap.add_argument("--accum", type=int, default=16); ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--max_train_tokens", type=int, default=16384); ap.add_argument("--liger", type=int, default=1); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max_train", type=int, default=0, help="smoke test: use only this many training trajectories")
    ap.add_argument("--train_ids", default=None, help="Stage 0: json list of tt_train ids to train on (label-efficiency subset)")
    ap.add_argument("--evals_per_epoch", type=int, default=2, help="validations per epoch (E4 v1: 2)")
    a = ap.parse_args()
    dist.init_process_group("nccl"); rk, ws = dist.get_rank(), dist.get_world_size(); dev = torch.device("cuda", int(os.environ["LOCAL_RANK"]))
    torch.cuda.set_device(dev); torch.manual_seed(a.seed); os.makedirs(a.out, exist_ok=True)
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.model)
    T = load_trajs(a.oat, {"tt_train": os.path.join(a.data_dir, "train"), "tt_val": os.path.join(a.data_dir, "val")})
    lens = {k: len(tok(v["text"])["input_ids"]) for k, v in T.items()}
    train = sorted(k for k in T if k[0] == "tt_train" and lens[k] <= a.max_train_tokens and T[k]["label"] in T[k]["cand"])
    val = sorted(k for k in T if k[0] == "tt_val" and lens[k] <= 32768 and T[k]["label"] in T[k]["cand"])
    if a.train_ids: allow = set(json.load(open(a.train_ids))); train = [k for k in train if k[1] in allow]
    if a.max_train: train = train[: a.max_train]; val = val[: max(8, a.max_train // 4)]
    lm = build(a.model, False, a.liger, True).to(dev); beft = Beft(lm).to(dev)
    for p_ in beft.parameters(): dist.broadcast(p_.data, 0)   # identical head init on every rank
    opt = torch.optim.AdamW([{"params": list(beft.bv.parameters()), "weight_decay": 0.0},
                             {"params": list(beft.head.parameters()), "weight_decay": 1e-2}], lr=a.lr)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 10))
    log = open(os.path.join(a.out, "log.jsonl"), "a") if rk == 0 else None
    if rk == 0: log.write(json.dumps({"n_train": len(train), "n_val": len(val), "n_train_total": sum(1 for k in T if k[0] == "tt_train"), "args": vars(a)}) + "\n"); log.flush()

    def validate():
        lm.eval(); s = []
        with torch.no_grad():
            for k in val[rk::ws]:
                enc, rg = encode(tok, T[k]); sc = step_scores(lm, beft, enc, rg, T[k]["cand"], dev).float().cpu().numpy()
                mi = T[k]["cand"].index(T[k]["label"])
                if len(sc) > 1: s.append(((sc < sc[mi]).sum() + 0.5 * ((sc == sc[mi]).sum() - 1)) / (len(sc) - 1))
        v = torch.tensor([sum(s), len(s)], dtype=torch.float64, device=dev); dist.all_reduce(v); lm.train(); return float(v[0] / v[1])

    rng = np.random.default_rng(a.seed); best, step, t0 = -1.0, 0, time.time()
    per_rank = len(train) // ws; half = max(1, per_rank // a.evals_per_epoch)
    for ep in range(a.epochs):
        order = [train[i] for i in rng.permutation(len(train))][: per_rank * ws]; mine = order[rk::ws]; lm.train()
        for i, k in enumerate(mine):
            enc, rg = encode(tok, T[k]); sync = (i + 1) % a.accum == 0 or i + 1 == len(mine)
            sc = step_scores(lm, beft, enc, rg, T[k]["cand"], dev)
            loss = torch.nn.functional.cross_entropy(sc.view(1, -1), torch.tensor([T[k]["cand"].index(T[k]["label"])], device=dev)) / a.accum
            loss.backward()
            if sync:   # ~41k trainable values: a manual all-reduce is cheaper and simpler than DDP (whose reducer needs its own forward)
                for p_ in beft.parameters():
                    if p_.grad is None: p_.grad = torch.zeros_like(p_)
                    dist.all_reduce(p_.grad); p_.grad /= ws
                opt.step(); sched.step(); opt.zero_grad(set_to_none=True); step += 1
                if rk == 0 and step % 5 == 0:
                    log.write(json.dumps({"epoch": ep, "opt_step": step, "loss": float(loss) * a.accum, "elapsed_s": time.time() - t0,
                                          "bv_norm": float(torch.sqrt(sum((p.detach() ** 2).sum() for p in beft.bv)))}) + "\n"); log.flush()
            if (i + 1) % half == 0 or i + 1 == len(mine):
                v = validate()
                if rk == 0:
                    log.write(json.dumps({"epoch": ep, "at": i + 1, "val_rauc": v, "elapsed_s": time.time() - t0}) + "\n"); log.flush()
                    if v > best: best = v; torch.save({"bv": [p.detach().cpu() for p in beft.bv], "head": beft.head.state_dict(), "val_rauc": v}, os.path.join(a.out, "best_state.pt"))
                dist.barrier()
    dist.barrier(); del lm, beft; torch.cuda.empty_cache()
    # final scoring with the best state (every rank scores a shard; rank 0 merges)
    E = load_trajs(a.oat, {"who_and_when": "who_and_when", "traceelephant_gc": "traceelephant_gc", "tt_test": os.path.join(a.data_dir, "test")})
    if a.max_train:   # smoke test: score only a few trajectories per dataset
        keep = set(); [keep.update(sorted(k for k in E if k[0] == ds)[:6]) for ds in {k[0] for k in E}]; E = {k: v for k, v in E.items() if k in keep}
    st = torch.load(os.path.join(a.out, "best_state.pt"), weights_only=False); out = {}
    elen = {k: len(tok(v["text"])["input_ids"]) for k, v in E.items()}
    for yarn in (False, True):
        lm = build(a.model, yarn, a.liger, False).to(dev).eval(); beft = Beft(lm).to(dev)
        for p, q in zip(beft.bv, st["bv"]): p.data.copy_(q)
        beft.head.load_state_dict(st["head"])
        ks = sorted(k for k in E if (elen[k] > 32768) == yarn and elen[k] <= 131072)
        with torch.no_grad():
            for k in ks[rk::ws]:
                enc, rg = encode(tok, E[k]); out[f"{k[0]}|{k[1]}"] = step_scores(lm, beft, enc, rg, E[k]["cand"], dev).float().cpu().tolist()
        del lm, beft; torch.cuda.empty_cache()
    json.dump(out, open(os.path.join(a.out, f"scores_rank{rk}.json"), "w")); dist.barrier()
    if rk == 0:
        allsc = {}
        for r in range(ws): allsc.update(json.load(open(os.path.join(a.out, f"scores_rank{r}.json"))))
        json.dump(allsc, open(os.path.join(a.out, "scores.json"), "w"))
        log.write(json.dumps({"done": True, "best_val_rauc": best, "n_scored": len(allsc), "skipped_over_131072": sum(1 for k in E if elen[k] > 131072)}) + "\n"); log.flush()
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
