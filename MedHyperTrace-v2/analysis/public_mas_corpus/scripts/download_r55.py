# r55 downloads: the two gated sets (microsoft/AgentRx, PatronusAI/TRAIL).
# HF token read from file at runtime ONLY for gated repos; never printed or written anywhere.
# Old-5 sets: re-run download.py (+ extract_wwp.py); r53 sets: re-run download_r53.py (both unauthenticated).
import os, time, json, sys
os.environ.pop("HF_TOKEN", None)
from huggingface_hub import hf_hub_download, HfApi
R = "/home/claude/public_mas/raw"
TOKF = "/tmp/claude-0/-home-claude/9b735e89-5a87-5eae-b05f-ab9afe1203be/scratchpad/hf_read.token"
GATED = {"microsoft/AgentRx", "PatronusAI/TRAIL"}
def tokfor(repo): return open(TOKF).read().strip() if repo in GATED else False
jobs = []
for repo in ["microsoft/AgentRx", "PatronusAI/TRAIL"]:
    tok = tokfor(repo)
    try:
        files = [s.rfilename for s in HfApi().dataset_info(repo, token=tok).siblings if s.rfilename != ".gitattributes"]
    except Exception as e:
        print(f"LIST-FAIL {repo}: {type(e).__name__}: {str(e)[:300]}", flush=True); files = []
    del tok
    jobs += [(repo, f, "main") for f in files]
if len(sys.argv) > 1: jobs = [j for j in jobs if sys.argv[1] in j[0]]
res = []
for repo, f, rev in jobs:
    ld = os.path.join(R, repo.replace("/", "__"))
    tok = tokfor(repo)
    for attempt in range(3):
        t = time.time()
        try:
            p = hf_hub_download(repo, f, repo_type="dataset", revision=rev, local_dir=ld, token=tok)
            dt = time.time() - t; sz = os.path.getsize(p)
            res.append(dict(repo=repo, file=f, mb=sz / 1e6, sec=dt, attempts=attempt + 1, auth=bool(tok))); break
        except Exception as e:
            msg = str(e)[:300]
            print(f"FAIL {repo} {f} a{attempt}: {type(e).__name__}: {msg}", flush=True)
            if "403" in msg or "401" in msg or "gated" in msg.lower(): res.append(dict(repo=repo, file=f, failed=True, err=type(e).__name__ + ": " + msg)); break
            time.sleep(5)
    else: res.append(dict(repo=repo, file=f, failed=True))
    del tok
ok = [r for r in res if not r.get("failed")]
print(f"OK {len(ok)} files, {sum(r['mb'] for r in ok):.1f} MB; FAILED {len(res) - len(ok)}", flush=True)
json.dump(res, open("/home/claude/public_mas/download_log_r55.json", "w"), indent=1)
print("DONE", flush=True)
