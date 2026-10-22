# list repo files / metadata for r53 datasets. HF token only used for gated repos, read from file at runtime, never printed.
import os, sys, json
os.environ.pop("HF_TOKEN", None)
from huggingface_hub import HfApi
TOKF = "/tmp/claude-0/-home-claude/46a27293-f675-561b-8e02-299a32e1c69e/scratchpad/hf_read_token"
api = HfApi()
REPOS = ["microsoft/AgentRx", "yifanyu/CORRECT-Error", "ZBox008003/AFTraj", "Edlison/ARIA", "Leoxx/whowhen_pro",
         "davide221/agenterrorbench", "mascope/mascope-bench", "RogerYao/RAISER", "AI45Research/ATBench"]
out = {}
for r in REPOS:
    e = {}
    for tok in [False, "TOK"]:
        t = open(TOKF).read().strip() if tok == "TOK" else False
        try:
            info = api.dataset_info(r, token=t, files_metadata=True)
            e["gated"] = getattr(info, "gated", None); e["license"] = (info.card_data or {}).get("license") if info.card_data else None
            e["files_main"] = [(s.rfilename, s.size) for s in info.siblings]
            e["auth_used"] = tok == "TOK"
            try:
                e["files_parquet"] = [(f.path, f.size) for f in api.list_repo_tree(r, repo_type="dataset", revision="refs/convert/parquet", recursive=True, token=t) if hasattr(f, "size")]
            except Exception as ex: e["files_parquet_err"] = f"{type(ex).__name__}: {str(ex)[:200]}"
            break
        except Exception as ex:
            e[f"err_{tok}"] = f"{type(ex).__name__}: {str(ex)[:200]}"
    out[r] = e
    print(r, json.dumps(e)[:3000], flush=True)
json.dump(out, open(sys.argv[1], "w"), indent=1)
