"""flash-attn 2 vs SDPA on Qwen3-8B (round 68): numerical agreement and speed of forward and of LoRA forward+backward.

  CUDA_VISIBLE_DEVICES=0 python bench_flash_attn.py --model <Qwen3-8B dir> [--lens 4096 16384]
"""
import argparse, json, time
import torch


def run(model_dir, impl, lens, ids_all):
    from transformers import AutoModelForCausalLM
    from peft import LoraConfig, get_peft_model
    m = AutoModelForCausalLM.from_pretrained(model_dir, dtype=torch.bfloat16, attn_implementation=impl).cuda()
    m.gradient_checkpointing_enable(); m.config.use_cache = False
    out = {}
    with torch.inference_mode():
        for L in lens:
            ids = ids_all[:, :L].cuda()
            m.model(input_ids=ids); torch.cuda.synchronize(); t = time.time()
            h = m.model(input_ids=ids).last_hidden_state; torch.cuda.synchronize()
            out[f"fwd_{L}_s"] = time.time() - t; out[f"h_{L}"] = h[0, :: max(L // 512, 1)].float().cpu()
    pm = get_peft_model(m, LoraConfig(r=16, lora_alpha=32, target_modules="all-linear", task_type="CAUSAL_LM")); pm.train()
    for L in lens:
        ids = ids_all[:, :L].cuda(); torch.cuda.reset_peak_memory_stats()
        pm(input_ids=ids, labels=ids).loss.backward(); torch.cuda.synchronize(); t = time.time()
        for _ in range(2): pm(input_ids=ids, labels=ids).loss.backward()
        torch.cuda.synchronize(); out[f"fwdbwd_{L}_s"] = (time.time() - t) / 2; out[f"fwdbwd_{L}_peakGiB"] = torch.cuda.max_memory_allocated() / 2**30
    del pm, m; torch.cuda.empty_cache()
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--model"); ap.add_argument("--lens", nargs="*", type=int, default=[4096, 16384])
    a = ap.parse_args(); torch.manual_seed(0)
    from flash_attn import flash_attn_func
    q, k, v = (torch.randn(1, 2048, 32, 128, device="cuda", dtype=torch.bfloat16) for _ in range(3))
    o1 = flash_attn_func(q, k, v, causal=True)
    o2 = torch.nn.functional.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2), is_causal=True).transpose(1, 2)
    res = {"kernel_max_abs_diff": float((o1 - o2).abs().max())}
    ids = torch.randint(1000, 100000, (1, max(a.lens)))
    S = run(a.model, "sdpa", a.lens, ids); F = run(a.model, "flash_attention_2", a.lens, ids)
    for L in a.lens:
        hs, hf = S.pop(f"h_{L}"), F.pop(f"h_{L}")
        res[f"hidden_cos_{L}"] = float(torch.nn.functional.cosine_similarity(hs, hf, dim=-1).mean())
        res[f"hidden_rel_err_{L}"] = float((hs - hf).norm() / hs.norm())
    res["sdpa"] = S; res["flash_attention_2"] = F
    for kk in S:
        if kk.endswith("_s"): res[f"speedup_{kk}"] = S[kk] / F[kk]
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
