"""Line 2 (PostTrain pre-registration v1): LoRA post-training of Qwen3-8B as a step scorer with counterfactual labels.

  torchrun --nproc_per_node 2 -m hgfm.posttrain.lora_score --oat <OAT dir> --model <dir> --out <dir> \
      --train tt --tt_dir <tt_ww dir> --med_ww <med_to_ww dir>                     # P-TT
  torchrun ... --train med --fold <unit> --med_ww <dir> [--init_state <P-TT>/best_state.pt]   # P-MED / P-MED/TT

Model: Qwen3-8B bf16, flash-attn 2, gradient checkpointing; peft LoRA r16 / alpha 32 / dropout 0.05 on all linear
projections (q k v o gate up down); head LayerNorm(H) -> Linear(H, 1) (fp32). Step representation = mean of the
last hidden state over the step's tokens in the OAT serialisation (same as E4 / BEFT). Only LoRA + head train.
Loss: tt = cross-entropy over candidate (model) steps, single label; med = mean over positives of -log softmax over the
parent's labelled points (hgfm.icpt.med_eval.build rules: A1 positives, last-call-only positives dropped, evaluable parents).
Optimiser: AdamW (LoRA lr 1e-4 wd 0; head lr 1e-3 wd 1e-2), 10 warm-up steps then constant; effective batch 32
trajectories (accum x world size); training trajectories <= 16,384 tokens. Data parallel with a manual gradient all-reduce.
Validation twice per epoch, best state kept: tt -> tt_val rank-AUROC; med -> mean AUROC on a question-grouped 10% hold-out
of the training parents (seed 12345, as med_eval). Epochs: tt 2, med 3 (pre-registered).
Scoring with the best state (native <= 32k, YaRN x4 <= 131k): tt -> who_and_when, traceelephant_gc, tt_test and every
evaluable medical parent (zero-shot); med -> the evaluable parents of the held-out unit only.
Outputs: best_state.pt, log.jsonl, scores.json {"<ds>|<id>": [candidate scores]} (public) and {"med|<run_id>": {row: score}}.
"""
import argparse, json, os, sys, time
import numpy as np
import torch
import torch.distributed as dist

from hgfm.e4.e4_beft import load_trajs, encode
from hgfm.icpt.med_eval import UNIT


def med_points(ww):
    """{basename: {run_id, unit, q, rows, y}} for evaluable parents, same rules as med_eval.build (pooled)."""
    man = {os.path.basename(m["id"]): m for m in json.load(open(os.path.join(ww, "manifest.json")))}
    lab = {}
    for l in open(os.path.join(ww, "labels.jsonl")):
        x = json.loads(l); lab.setdefault(x["run_id"], {})[x["step_id"]] = x
    out = {}
    for b, m in man.items():
        if m["framework"] not in UNIT: continue
        L = lab.get(m["run_id"], {}); rows, y = [], []
        for i, f in enumerate(m["is_llm"]):
            x = L.get(m["step_ids"][i]) if f else None
            if x is None or (x["positive"] and x["last_call_only"]): continue
            rows.append(i + 1); y.append(bool(x["positive"]))
        if any(y) and not all(y): out[b] = {"run_id": m["run_id"], "unit": UNIT[m["framework"]], "q": m["question_id"], "rows": rows, "y": y}
    return out


def build(model_dir, yarn, gc, r=16, alpha=32):
    from transformers import AutoModelForCausalLM
    from peft import LoraConfig, get_peft_model
    kw = {"dtype": torch.bfloat16, "attn_implementation": "flash_attention_2"}
    if yarn:
        kw["rope_scaling"] = {"rope_type": "yarn", "factor": 4.0, "original_max_position_embeddings": 32768}; kw["max_position_embeddings"] = 131072
    m = AutoModelForCausalLM.from_pretrained(model_dir, **kw); m.config.use_cache = False
    if gc:
        m.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False}); m.enable_input_require_grads()
    m = get_peft_model(m, LoraConfig(r=r, lora_alpha=alpha, lora_dropout=0.05, bias="none",
                                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
    for n, p in m.named_parameters():
        if "lora_" in n: p.data = p.data.float()
    H = m.config.hidden_size; head = torch.nn.Sequential(torch.nn.LayerNorm(H), torch.nn.Linear(H, 1))
    return m, head


def lora_state(m): return {n: p.detach().cpu().clone() for n, p in m.named_parameters() if "lora_" in n}


def load_state(m, head, st):
    own = dict(m.named_parameters())
    for n, v in st["lora"].items(): own[n].data.copy_(v.to(own[n].dtype))
    head.load_state_dict(st["head"])


def reps(m, enc, ranges, idx, dev):
    with torch.autocast("cuda", dtype=torch.bfloat16):
        h = m.base_model.model.model(input_ids=enc["input_ids"].to(dev), use_cache=False, return_dict=True).last_hidden_state[0]
    return torch.stack([h[ranges[j][0]: ranges[j][1] + 1].float().mean(0) for j in idx])


def scores_for(m, head, T, k, idx, tok, dev):
    enc, rg = encode(tok, T[k]); return head(reps(m, enc, rg, idx, dev)).squeeze(-1)


def auc(s, y):
    s = np.asarray(s); y = np.asarray(y, bool); p, n = s[y], s[~y]
    return float(((p[:, None] > n[None]).sum() + 0.5 * (p[:, None] == n[None]).sum()) / (len(p) * len(n)))


def main():
    ap = argparse.ArgumentParser()
    for k in ("oat", "model", "out", "tt_dir", "med_ww", "fold", "init_state"): ap.add_argument("--" + k, default=None)
    ap.add_argument("--train", choices=["tt", "med"], required=True); ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--accum", type=int, default=16); ap.add_argument("--max_train_tokens", type=int, default=16384)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--max_train", type=int, default=0, help="smoke test")
    a = ap.parse_args(); epochs = a.epochs or (2 if a.train == "tt" else 3)
    dist.init_process_group("nccl"); rk, ws = dist.get_rank(), dist.get_world_size(); dev = torch.device("cuda", int(os.environ["LOCAL_RANK"]))
    torch.cuda.set_device(dev); torch.manual_seed(a.seed); os.makedirs(a.out, exist_ok=True)
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.model)
    MP = med_points(a.med_ww); MT = load_trajs(a.oat, {"med": a.med_ww})
    MT = {k: v for k, v in MT.items() if os.path.basename(k[1]) in MP}
    if a.train == "tt":
        T = load_trajs(a.oat, {"tt_train": os.path.join(a.tt_dir, "train"), "tt_val": os.path.join(a.tt_dir, "val")})
        lens = {k: len(tok(v["text"])["input_ids"]) for k, v in T.items()}
        ok = lambda k: T[k]["label"] in T[k]["cand"]
        train = sorted(k for k in T if k[0] == "tt_train" and lens[k] <= a.max_train_tokens and ok(k))
        val = sorted(k for k in T if k[0] == "tt_val" and lens[k] <= 32768 and ok(k))
        item = lambda k: (T[k]["cand"], [j == T[k]["label"] for j in T[k]["cand"]])
    else:
        T = MT; lens = {k: len(tok(v["text"])["input_ids"]) for k, v in T.items()}
        pool = sorted(k for k in T if MP[os.path.basename(k[1])]["unit"] != a.fold)
        qs = sorted({MP[os.path.basename(k[1])]["q"] for k in pool}); hold = set(np.random.default_rng(12345).permutation(qs)[: max(1, len(qs) // 10)])
        train = [k for k in pool if MP[os.path.basename(k[1])]["q"] not in hold and lens[k] <= a.max_train_tokens]
        val = [k for k in pool if MP[os.path.basename(k[1])]["q"] in hold and lens[k] <= 32768]
        item = lambda k: (MP[os.path.basename(k[1])]["rows"], MP[os.path.basename(k[1])]["y"])
    if a.max_train: train = train[: a.max_train]; val = val[: max(8, a.max_train // 4)]
    m, head = build(a.model, False, True); m.to(dev); head.to(dev)
    if a.init_state: load_state(m, head, torch.load(a.init_state, weights_only=False))
    params = [p for n, p in m.named_parameters() if "lora_" in n]
    for p_ in params + list(head.parameters()): dist.broadcast(p_.data, 0)
    opt = torch.optim.AdamW([{"params": params, "lr": 1e-4, "weight_decay": 0.0},
                             {"params": list(head.parameters()), "lr": 1e-3, "weight_decay": 1e-2}])
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 10))
    log = open(os.path.join(a.out, "log.jsonl"), "a") if rk == 0 else None
    if rk == 0:
        log.write(json.dumps({"n_train": len(train), "n_val": len(val), "n_trainable": sum(p.numel() for p in params), "args": vars(a)}) + "\n"); log.flush()

    def validate():
        m.eval(); s = []
        with torch.no_grad():
            for k in val[rk::ws]:
                idx, y = item(k); sc = scores_for(m, head, T, k, idx, tok, dev).float().cpu().numpy()
                if a.train == "tt":
                    mi = y.index(True)
                    if len(sc) > 1: s.append(((sc < sc[mi]).sum() + 0.5 * ((sc == sc[mi]).sum() - 1)) / (len(sc) - 1))
                else: s.append(auc(sc, y))
        v = torch.tensor([sum(s), len(s)], dtype=torch.float64, device=dev); dist.all_reduce(v); m.train(); return float(v[0] / max(v[1], 1))

    rng = np.random.default_rng(a.seed); best, step, t0 = -1.0, 0, time.time()
    per_rank = len(train) // ws; half = max(1, per_rank // 2)
    for ep in range(epochs):
        order = [train[i] for i in rng.permutation(len(train))][: per_rank * ws]; mine = order[rk::ws]; m.train()
        for i, k in enumerate(mine):
            idx, y = item(k); sc = scores_for(m, head, T, k, idx, tok, dev); lp = torch.log_softmax(sc, 0)
            loss = -lp[torch.tensor(y, device=dev)].mean() / a.accum; loss.backward()
            if (i + 1) % a.accum == 0 or i + 1 == len(mine):
                for p_ in params + list(head.parameters()):
                    if p_.grad is None: p_.grad = torch.zeros_like(p_)
                    dist.all_reduce(p_.grad); p_.grad /= ws
                opt.step(); sched.step(); opt.zero_grad(set_to_none=True); step += 1
                if rk == 0 and step % 5 == 0:
                    log.write(json.dumps({"epoch": ep, "opt_step": step, "loss": float(loss) * a.accum, "elapsed_s": time.time() - t0}) + "\n"); log.flush()
            if (i + 1) % half == 0 or i + 1 == len(mine):
                v = validate()
                if rk == 0:
                    log.write(json.dumps({"epoch": ep, "at": i + 1, "val": v, "elapsed_s": time.time() - t0}) + "\n"); log.flush()
                    if v > best: best = v; torch.save({"lora": lora_state(m), "head": head.state_dict(), "val": v}, os.path.join(a.out, "best_state.pt"))
                dist.barrier()
    dist.barrier(); del m, head, opt; torch.cuda.empty_cache()
    # scoring with the best state
    E = {}
    if a.train == "tt":
        E.update(load_trajs(a.oat, {"who_and_when": "who_and_when", "traceelephant_gc": "traceelephant_gc", "tt_test": os.path.join(a.tt_dir, "test")}))
        E.update(MT)
    else:
        E.update({k: v for k, v in MT.items() if MP[os.path.basename(k[1])]["unit"] == a.fold})
    if a.max_train:
        keep = set(); [keep.update(sorted(k for k in E if k[0] == ds)[:6]) for ds in {k[0] for k in E}]; E = {k: v for k, v in E.items() if k in keep}
    st = torch.load(os.path.join(a.out, "best_state.pt"), weights_only=False); out = {}
    elen = {k: len(tok(v["text"])["input_ids"]) for k, v in E.items()}
    for yarn in (False, True):
        ks = sorted(k for k in E if (elen[k] > 32768) == yarn and elen[k] <= 131072)
        if not ks: continue
        m, head = build(a.model, yarn, False); m.to(dev).eval(); head.to(dev); load_state(m, head, st)
        with torch.no_grad():
            for k in ks[rk::ws]:
                if k[0] == "med":
                    b = os.path.basename(k[1]); rows = MP[b]["rows"]
                    out[f"med|{MP[b]['run_id']}"] = dict(zip(map(str, rows), scores_for(m, head, E, k, rows, tok, dev).float().cpu().tolist()))
                else:
                    out[f"{k[0]}|{k[1]}"] = scores_for(m, head, E, k, E[k]["cand"], tok, dev).float().cpu().tolist()
        del m, head; torch.cuda.empty_cache()
    json.dump(out, open(os.path.join(a.out, f"scores_rank{rk}.json"), "w")); dist.barrier()
    if rk == 0:
        allsc = {}
        for r in range(ws): allsc.update(json.load(open(os.path.join(a.out, f"scores_rank{r}.json"))))
        json.dump(allsc, open(os.path.join(a.out, "scores.json"), "w"))
        log.write(json.dumps({"done": True, "best_val": best, "n_scored": len(allsc), "skipped_over_131072": sum(1 for k in E if elen[k] > 131072)}) + "\n"); log.flush()
    dist.destroy_process_group()


if __name__ == "__main__":
    main()
