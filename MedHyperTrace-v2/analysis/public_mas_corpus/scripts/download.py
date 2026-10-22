import os, time, json, sys
os.environ.pop("HF_TOKEN",None)
from huggingface_hub import hf_hub_download
R="/home/claude/public_mas/raw"
jobs=[("Kevin355/Who_and_When","Algorithm-Generated/train/0000.parquet","refs/convert/parquet"),
      ("Kevin355/Who_and_When","Hand-Crafted/train/0000.parquet","refs/convert/parquet"),
      ("Fancylalala/AEGIS","default/test/0000.parquet","refs/convert/parquet"),
      ("Fancylalala/AEGIS","default/validation/0000.parquet","refs/convert/parquet"),
      ("Fancylalala/AEGIS","default/train/0000.parquet","refs/convert/parquet"),
      ("mcemri/MAST-Data","default/train/0000.parquet","refs/convert/parquet"),
      ("tmpxv7/who-when-pro","README.md","main"),
      ("TraceElephant/TraceElephant","data.zip","main"),
      ("tmpxv7/who-when-pro","data_release.tar.gz","main")]
if len(sys.argv)>1: jobs=[j for j in jobs if sys.argv[1] in j[0]]
res=[]
for repo,f,rev in jobs:
    ld=os.path.join(R,repo.replace("/","__"))
    for attempt in range(5):
        t=time.time()
        try:
            p=hf_hub_download(repo,f,repo_type="dataset",revision=rev,local_dir=ld,token=False)
            dt=time.time()-t; sz=os.path.getsize(p)
            print(f"OK {repo} {f} {sz/1e6:.1f}MB {dt:.1f}s {sz/1e6/max(dt,1e-3):.2f}MB/s",flush=True)
            res.append(dict(repo=repo,file=f,mb=sz/1e6,sec=dt,attempts=attempt+1)); break
        except Exception as e:
            print(f"FAIL {repo} {f} a{attempt}: {type(e).__name__}: {str(e)[:300]}",flush=True); time.sleep(5)
    else: res.append(dict(repo=repo,file=f,failed=True))
json.dump(res,open(f"/home/claude/public_mas/download_log{('_'+sys.argv[1].replace('/','_')) if len(sys.argv)>1 else ''}.json","w"),indent=1)
print("DONE",flush=True)
