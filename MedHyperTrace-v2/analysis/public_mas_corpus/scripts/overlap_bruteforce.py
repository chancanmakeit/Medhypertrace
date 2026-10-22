# independent check: does the first 60 normalized chars of any MAA query occur anywhere in each public dataset's text?
import json, re, zipfile, glob, pandas as pd, time
def norm(s): return re.sub(r"\s+"," ",s).strip().lower()
R="/home/claude/public_mas/raw"
maa=set()
for l in open("/home/claude/data_maa_v2/maa_mas_traj.jsonl"):
    q=json.loads(l)["task"]["query"]
    if isinstance(q,str) and q.strip(): maa.add(norm(q))
probes=sorted({q[:60] for q in maa if len(q)>=40})
texts={}
texts["AEGIS"]=[norm(x) for sp in ["train","validation","test"] for x in pd.read_parquet(f"{R}/Fancylalala__AEGIS/default/{sp}/0000.parquet")["input"]]
texts["MAST"]=[norm(t["trajectory"]) for t in pd.read_parquet(f"{R}/mcemri__MAST-Data/default/train/0000.parquet")["trace"]]
texts["Who&When"]=[norm(json.dumps(list(h),ensure_ascii=False,default=str)+" "+q) for c in ["Algorithm-Generated","Hand-Crafted"] for h,q in pd.read_parquet(f"{R}/Kevin355__Who_and_When/{c}/train/0000.parquet")[["history","question"]].values]
z=zipfile.ZipFile(f"{R}/TraceElephant__TraceElephant/data.zip")
texts["TraceElephant"]=[norm(json.loads(z.read(n)).__repr__()) for n in z.namelist() if n.endswith(".json")]
texts["Who&When-Pro"]=[norm(open(f).read()) for f in glob.glob(f"{R}/wwp_json/*.json")]
# positive control: plant one MAA query
ctrl=list(maa)[0]
for ds,ts in texts.items():
    big="\x00".join(ts); t=time.time()
    hits=[p for p in probes if p in big]
    print(ds,"probes",len(probes),"hits",len(hits),hits[:3],"chars",len(big),f"{time.time()-t:.0f}s",flush=True)
big="\x00".join(texts["Who&When"]+[ "xx "+ctrl+" yy"]); print("positive control hit:", ctrl[:60] in big)
