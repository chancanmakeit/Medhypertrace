"""Parallel ranged downloader for a Hugging Face model repo through hf-mirror (round 97; both Linux machines limit each
connection to ~0.5 MB/s). Every file is fetched in 64 MB byte ranges by a thread pool, then checked against the LFS sha256
(or the size for small files). Resumable: finished chunks are kept in <out>/.parts/.

  python pdl.py Qwen/Qwen3-8B-Base <out_dir> [--threads 32] [--endpoint https://hf-mirror.com] [--noproxy]
Prints "done <out_dir>" at the end.
"""
import argparse, concurrent.futures as cf, hashlib, json, os, sys, time, urllib.request

CHUNK = 64 << 20


class R308(urllib.request.HTTPRedirectHandler):   # Python 3.10 urllib does not follow 308 (hf-mirror uses it)
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if code in (307, 308):   # keep method and headers (Range) on a 307/308 redirect
            newurl = newurl.replace(" ", "%20")
            hdrs = {k: v for k, v in req.header_items() if k.lower() not in ("content-length", "content-type", "host")}
            return urllib.request.Request(newurl, headers=hdrs, origin_req_host=req.origin_req_host, unverifiable=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)
    http_error_308 = urllib.request.HTTPRedirectHandler.http_error_302


def opener(noproxy):
    if noproxy: return urllib.request.build_opener(urllib.request.ProxyHandler({}), R308)
    if os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY"): return urllib.request.build_opener(R308)   # HTTP CONNECT proxy from env
    px = os.environ.get("all_proxy") or os.environ.get("ALL_PROXY")
    if px and px.startswith("socks"):
        import socks, socket   # PySocks
        from urllib.parse import urlparse
        u = urlparse(px); socks.set_default_proxy(socks.SOCKS5, u.hostname, u.port, rdns=px.startswith("socks5h")); socket.socket = socks.socksocket
        return urllib.request.build_opener(urllib.request.ProxyHandler({}), R308)
    return urllib.request.build_opener(R308)


def get(op, url, rng=None, tries=8):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={rng[0]}-{rng[1]}"} if rng else {})
            with op.open(req, timeout=120) as r: return r.read()
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(3 * (i + 1))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("repo"); ap.add_argument("out"); ap.add_argument("--threads", type=int, default=32)
    ap.add_argument("--endpoint", default="https://hf-mirror.com"); ap.add_argument("--noproxy", action="store_true")
    ap.add_argument("--url_tmpl", default="{endpoint}/{repo}/resolve/main/{path}",
                    help="e.g. https://www.modelscope.cn/models/{repo}/resolve/master/{path} (fast direct route on Linux #1)")
    ap.add_argument("--meta", help="local JSON [[path,size,sha256|null],...] instead of the huggingface.co API"); a = ap.parse_args()
    op = opener(a.noproxy); os.makedirs(os.path.join(a.out, ".parts"), exist_ok=True)
    if a.meta: files = [tuple(x) for x in json.load(open(a.meta))]
    else:
        info = json.loads(get(op, f"https://huggingface.co/api/models/{a.repo}?blobs=true"))   # metadata from the origin (hf-mirror redirects its API there)
        files = [(x["rfilename"], x["size"], (x.get("lfs") or {}).get("sha256")) for x in info["siblings"]]
    jobs = []
    for path, size, oid in files:
        dst = os.path.join(a.out, path)
        if os.path.exists(dst) and os.path.getsize(dst) == size: continue
        for k, s in enumerate(range(0, max(size, 1), CHUNK)):
            jobs.append((path, k, s, min(s + CHUNK, size) - 1))
    url = lambda p: a.url_tmpl.format(endpoint=a.endpoint, repo=a.repo, path=p)

    def work(j):
        path, k, s, e = j; pf = os.path.join(a.out, ".parts", f"{path.replace('/', '__')}.{k:05d}")
        if os.path.exists(pf) and os.path.getsize(pf) == e - s + 1: return 0
        b = get(op, url(path), (s, e) if e >= s else None)
        if len(b) != e - s + 1 and e >= s: raise IOError(f"short read {path} {k}: {len(b)} vs {e - s + 1}")
        open(pf + ".tmp", "wb").write(b); os.replace(pf + ".tmp", pf); return len(b)

    t0 = time.time(); got = 0
    with cf.ThreadPoolExecutor(a.threads) as ex:
        for i, n in enumerate(ex.map(work, jobs)):
            got += n
            if i % 20 == 0: print(f"{i + 1}/{len(jobs)} chunks, {got / 1e9:.2f} GB, {got / 1e6 / max(time.time() - t0, 1):.1f} MB/s", flush=True)
    for path, size, oid in files:
        dst = os.path.join(a.out, path)
        if os.path.exists(dst) and os.path.getsize(dst) == size: continue
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True); h = hashlib.sha256()
        with open(dst + ".tmp", "wb") as f:
            for k in range(len(range(0, max(size, 1), CHUNK))):
                pf = os.path.join(a.out, ".parts", f"{path.replace('/', '__')}.{k:05d}"); b = open(pf, "rb").read(); f.write(b); h.update(b)
        if oid and h.hexdigest() != oid: raise SystemExit(f"sha256 mismatch {path}")
        if os.path.getsize(dst + ".tmp") != size: raise SystemExit(f"size mismatch {path}")
        os.replace(dst + ".tmp", dst); print("ok", path, flush=True)
    print("done", a.out, flush=True)


if __name__ == "__main__":
    main()
