# r53: schema peek of Leoxx/whowhen_pro image/image_gui splits via HTTP Range (first 32 KB only; not downloaded)
import os, re, json, requests
from huggingface_hub import hf_hub_url
os.environ.pop("HF_TOKEN", None)
out = {}
for f in ["data/image.jsonl", "data/image_gui.jsonl"]:
    u = hf_hub_url("Leoxx/whowhen_pro", f, repo_type="dataset")
    r = requests.get(u, headers={"Range": "bytes=0-32767"}, timeout=60, allow_redirects=True)
    b = r.content.decode("utf-8", "replace")
    keys = re.findall(r'"([A-Za-z_]{2,30})"\s*:', b)
    seen = []
    [seen.append(k) for k in keys if k not in seen]
    m = re.search(r'"framework"\s*:\s*"([^"]+)".*?"benchmark"\s*:\s*"([^"]+)"', b, re.S)
    out[f] = dict(status=r.status_code, bytes=len(r.content), first_keys=seen[:40], framework_benchmark=(m.groups() if m else None),
                  has_base64_image=("base64" in b or "data:image" in b))
    print(f, out[f])
json.dump(out, open("/home/claude/public_mas/wwp_image_peek_r53.json", "w"), indent=1)
