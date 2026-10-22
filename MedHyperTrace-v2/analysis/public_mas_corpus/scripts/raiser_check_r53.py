# r53: verify whether RogerYao/RAISER contains any trajectory text (columns + max string length per column)
import json, glob, os, collections, pandas as pd, sys
R = "/home/claude/public_mas/raw/RogerYao__RAISER"
out = {}
for p in sorted(glob.glob(f"{R}/data/**/*.*", recursive=True)):
    df = pd.read_json(p, lines=True) if p.endswith(".jsonl") else pd.read_csv(p)
    cols = {}
    for c in df.columns:
        s = df[c]
        ml = int(s.map(lambda x: len(x) if isinstance(x, str) else 0).max())
        cols[c] = dict(dtype=str(s.dtype), max_str_len=ml, example=str(s.iloc[0])[:60])
    out[os.path.relpath(p, R)] = dict(rows=len(df), cols=cols, ds_sources=(dict(collections.Counter(df["dataset_source"])) if "dataset_source" in df else None),
                                      n_traces=(int(df[["dataset_source", "trace_id"]].drop_duplicates().shape[0]) if {"dataset_source", "trace_id"} <= set(df.columns) else None))
json.dump(out, open("/home/claude/public_mas/raiser_check_r53.json", "w"), indent=1)
for k, v in out.items():
    print(k, v["rows"], v["n_traces"], v["ds_sources"])
    print("   ", {c: (d["max_str_len"]) for c, d in v["cols"].items()})
