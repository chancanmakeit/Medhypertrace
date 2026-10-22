# r53 downloads. HF token read from file at runtime ONLY for gated repos; never printed or written.
import os, time, json, sys
os.environ.pop("HF_TOKEN", None)
from huggingface_hub import hf_hub_download
R = "/home/claude/public_mas/raw"
TOKF = "/tmp/claude-0/-home-claude/46a27293-f675-561b-8e02-299a32e1c69e/scratchpad/hf_read_token"
GATED = {"microsoft/AgentRx"}
jobs = [("microsoft/AgentRx", f, "main") for f in ["README.md", "magentic_dataset.jsonl", "magentic_one.jsonl", "tau_retail.jsonl", "tau_retail_dataset.jsonl"]]
jobs += [("yifanyu/CORRECT-Error", f, "main") for f in ["README.md", "data/test-00000-of-00001.parquet"]]
jobs += [("ZBox008003/AFTraj", f, "main") for f in ["README.md", "aftraj_safe.parquet", "aftraj_unsafe.parquet", "splits_test.json"]]
jobs += [("Edlison/ARIA", f, "main") for f in ["README.md", "data/train.parquet", "data/validation.parquet", "data/test.parquet"]]
jobs += [("Leoxx/whowhen_pro", f, "main") for f in ["README.md", "taxonomy.yaml", "data/text.jsonl", "data/video.jsonl"]]
jobs += [("davide221/agenterrorbench", f, "main") for f in ["README.md", "data/train-00000-of-00001.parquet", "data/validation-00000-of-00001.parquet", "data/test-00000-of-00001.parquet"]]
jobs += [("mascope/mascope-bench", f, "main") for f in ["README.md", "LICENSE", "CITATION.bib", "Inject-Mix.jsonl", "LG-Ctrl.jsonl", "MAST-clean.jsonl", "lofo_splits.json"]]
jobs += [("RogerYao/RAISER", f, "main") for f in ["README.md", "DATA_STATEMENT.md", "LICENSE_DATA.md", "PROVENANCE.md", "SCHEMA.md", "data/event_source/broad_cross_annotation.csv",
        "data/human_gold/mv_cv_test.jsonl", "data/model_benchmark/consensus_gold.jsonl", "data/model_benchmark/model_silver.jsonl", "data/repair_evaluation/component_1200.csv",
        "data/repair_evaluation/native_checkpoint_150.csv", "data/repair_evaluation/untouched_346.csv", "metadata/inventory.csv", "metadata/release_manifest.json", "metadata/source_datasets.csv"]]
jobs += [("AI45Research/ATBench", f, "main") for f in ["README.md", "ATBench/test.json", "ATBench500/test.json", "test.json"]]
if len(sys.argv) > 1: jobs = [j for j in jobs if sys.argv[1] in j[0]]
res = []
for repo, f, rev in jobs:
    ld = os.path.join(R, repo.replace("/", "__"))
    tok = open(TOKF).read().strip() if repo in GATED else False
    for attempt in range(3):
        t = time.time()
        try:
            p = hf_hub_download(repo, f, repo_type="dataset", revision=rev, local_dir=ld, token=tok)
            dt = time.time() - t; sz = os.path.getsize(p)
            print(f"OK {repo} {f} {sz/1e6:.1f}MB {dt:.1f}s", flush=True)
            res.append(dict(repo=repo, file=f, mb=sz/1e6, sec=dt, attempts=attempt+1, auth=bool(tok))); break
        except Exception as e:
            msg = str(e)[:300]
            print(f"FAIL {repo} {f} a{attempt}: {type(e).__name__}: {msg}", flush=True)
            if "403" in msg or "401" in msg or "gated" in msg.lower(): res.append(dict(repo=repo, file=f, failed=True, err=type(e).__name__ + ": " + msg)); break
            time.sleep(5)
    else: res.append(dict(repo=repo, file=f, failed=True))
    del tok
json.dump(res, open("/home/claude/public_mas/download_log_r53.json", "w"), indent=1)
print("DONE", flush=True)
