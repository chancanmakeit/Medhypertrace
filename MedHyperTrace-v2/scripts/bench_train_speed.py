"""Training-speed benchmark on one A6000 (round 72): Qwen3-8B + LoRA r64 (TAPT recipe), flash-attn 2, with / without
Liger kernel and gradient checkpointing, for the LM objective (TAPT) and for a headless step-scoring forward (E4).

  CUDA_VISIBLE_DEVICES=2 python bench_train_speed.py --model <Qwen3-8B dir> --liger 0|1 --gc 0|1 --mode lm|head \
      --lens 4096 8192 16384 --out <json>

One configuration per process (Liger patches the Qwen3 classes at import time). For every length: 1 warm-up step, then
the mean of 3 fwd+bwd steps (seconds), tokens/s, peak memory (GiB), the loss and the LoRA-gradient L2 norm of the first
measured step (to check that Liger gives the same numbers). OOM is recorded, not raised. Same random token ids
(seed 0) in every configuration.
  mode lm   : loss = causal LM cross-entropy (labels = input ids), as in TAPT.
  mode head : last hidden state -> mean over 64-token blocks -> linear head -> cross-entropy against block 0 (a stand-in
              for E4's step-scoring head; no vocabulary logits are computed).
"""
import argparse, json, time
import torch


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--model"); ap.add_argument("--liger", type=int, default=0)
    ap.add_argument("--gc", type=int, default=1); ap.add_argument("--mode", default="lm")
    ap.add_argument("--lens", nargs="*", type=int, default=[4096, 8192, 16384]); ap.add_argument("--out")
    a = ap.parse_args()
    if a.liger:
        from liger_kernel.transformers import apply_liger_kernel_to_qwen3
        apply_liger_kernel_to_qwen3(rope=True, rms_norm=True, swiglu=True, fused_linear_cross_entropy=(a.mode == "lm"), cross_entropy=False)
    from transformers import AutoModelForCausalLM
    from peft import LoraConfig, get_peft_model
    m = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16, attn_implementation="flash_attention_2").cuda()
    m.config.use_cache = False
    if a.gc:
        m.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False}); m.enable_input_require_grads()
    torch.manual_seed(0)   # same LoRA A init and head init in every configuration, so loss / grad norms are comparable
    pm = get_peft_model(m, LoraConfig(r=64, lora_alpha=128, lora_dropout=0.0, target_modules="all-linear", task_type="CAUSAL_LM"))
    pm.train(); head = torch.nn.Linear(m.config.hidden_size, 1, dtype=torch.bfloat16).cuda()
    g = torch.Generator().manual_seed(0); ids_all = torch.randint(1000, 100000, (1, max(a.lens)), generator=g)
    res = {"liger": a.liger, "gc": a.gc, "mode": a.mode, "lens": {}}

    def step(ids):
        if a.mode == "lm":
            loss = pm(input_ids=ids, labels=ids).loss
        else:
            h = pm.base_model.model.model(input_ids=ids).last_hidden_state[0]
            blk = h[: h.shape[0] // 64 * 64].view(-1, 64, h.shape[-1]).mean(1)
            loss = torch.nn.functional.cross_entropy(head(blk).float().view(1, -1), torch.zeros(1, dtype=torch.long, device=ids.device))
        loss.backward(); return loss

    for L in a.lens:
        ids = ids_all[:, :L].cuda(); r = {}
        try:
            pm.zero_grad(set_to_none=True); step(ids); torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats(); ts = []
            for k in range(3):
                pm.zero_grad(set_to_none=True); t = time.time(); loss = step(ids); torch.cuda.synchronize(); ts.append(time.time() - t)
                if k == 0:
                    r["loss"] = float(loss)
                    r["lora_grad_norm"] = float(torch.sqrt(sum((p.grad.float() ** 2).sum() for n, p in pm.named_parameters() if p.grad is not None and "lora" in n)))
            r["step_s"] = sum(ts) / len(ts); r["tok_per_s"] = L / r["step_s"]; r["peak_GiB"] = torch.cuda.max_memory_allocated() / 2**30
        except torch.OutOfMemoryError:
            r["oom"] = True
        pm.zero_grad(set_to_none=True); torch.cuda.empty_cache(); res["lens"][str(L)] = r
        print(L, r, flush=True)
    json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
