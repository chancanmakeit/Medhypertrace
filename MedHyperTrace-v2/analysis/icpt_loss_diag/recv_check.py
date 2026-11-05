# Round 93 sanity check of the loss_diag "recv" rendering: per-position NLL profile for a few items, base model.
import sys, json, gzip, glob, random, torch
sys.path.insert(0, "/data1/ekyang/cgh/CODE/Medhypertrace/MedHyperTrace-v2")
from hgfm.icpt.loss_diag import sample, contexts
from transformers import AutoModelForCausalLM, AutoTokenizer
BASE = "/data1/ekyang/cgh/cache/huggingface_hub/hub/models--Qwen--Qwen3-8B"
runs = sample(sorted(glob.glob("/data1/ekyang/cgh/CODE/mht_work/icpt/hf/icpt/loss_runs.jsonl.gz")), 60, 0)
tok = AutoTokenizer.from_pretrained(BASE); rng = random.Random(0)
m = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16, attn_implementation="flash_attention_2").cuda().eval()
def nll(ids):
    ids = torch.tensor([ids], device="cuda")
    with torch.inference_mode():
        lp = torch.log_softmax(m(input_ids=ids).logits[0, :-1].float(), -1)
    return (-lp.gather(1, ids[0, 1:, None])[:, 0]).tolist()
for r in runs[::30][:8]:
    ts = [i for i, s in enumerate(r["steps"]) if s["kind"] == "llm" and (s.get("output") or "").strip() and s.get("sources") is not None]
    t = ts[len(ts) // 2]; tgt = tok(r["steps"][t]["output"].strip(), add_special_tokens=False)["input_ids"][:512]
    pre = contexts(r, t)["recv"][0]
    s = tok.apply_chat_template([{"role": "system", "content": pre["system"]}, {"role": "user", "content": pre["user"]}],
                                tokenize=False, add_generation_prompt=True, enable_thinking=False)
    hid = tok(s, add_special_tokens=False)["input_ids"]; trunc = len(hid) > 4096 - len(tgt)
    hid = hid[-(4096 - len(tgt)):]; L = len(hid); x = nll(hid + tgt)
    tail_txt = tok.decode(hid[-12:]); head = x[L - 8:L - 1]; tg = x[L - 1:]
    # alt: same messages, target placed as the assistant turn via the template itself (no manual append)
    full = tok.apply_chat_template([{"role": "system", "content": pre["system"]}, {"role": "user", "content": pre["user"]},
                                    {"role": "assistant", "content": tok.decode(tgt)}], tokenize=False, enable_thinking=False)
    print(json.dumps({"fw": r["framework"], "ctx_len": len(hid), "truncated": trunc, "n_tgt": len(tgt),
                      "ctx_tail": tail_txt, "head_tok_nll": [round(v, 2) for v in head],
                      "tgt_first10": [round(v, 2) for v in tg[:10]], "tgt_mean": round(sum(tg) / len(tg), 3),
                      "tgt_mean_after10": round(sum(tg[10:]) / max(1, len(tg) - 10), 3),
                      "first_tgt_text": tok.decode(tgt[:15]), "template_assistant_tail": full[-60:]}, ensure_ascii=False), flush=True)
