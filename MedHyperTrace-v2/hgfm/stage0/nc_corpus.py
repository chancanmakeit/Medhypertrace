"""Stage 0 (round 79) negative-control mid-training corpora, both matched to the E2 R corpus (6.09M tokens).

  shuf : python -m hgfm.stage0.nc_corpus shuf --src R.jsonl --out NC_shuf.jsonl [--tokenizer DIR]
         Every R chunk keeps its task header and its step blocks, but the blocks are put in a random order (seed 0) and the
         step ids are renumbered s0, s1, ... in the new order, so the text carries no trace of the original order.
         Same tokens (up to the renumbering), same chunks, same dataset mix -> isolates trajectory ORDER / causal structure.
  lens : python -m hgfm.stage0.nc_corpus lens --src R.jsonl --out R_lens.json   (token length of every R chunk, Qwen3)
  irr  : python -m hgfm.stage0.nc_corpus irr --lens R_lens.json --wiki <parquet> [...] --out NC_irr.jsonl
         Generic encyclopedic text (WikiText-103 raw train, articles in file order) cut into consecutive windows whose
         token lengths are exactly the R chunk lengths -> same number of chunks / optimizer steps and the same token count,
         no MAS content at all. Isolates "any continued pre-training of this size".
"""
import argparse, json, random, re, sys

BLOCK = re.compile(r"\n(?=\[s\d+\] [^\n]*\| [^\n]*\n)")


def split_chunk(text):
    """-> (header, [blocks]); header = everything before the first step block."""
    m = re.search(r"(^|\n)\[s\d+\] [^\n]*\| [^\n]*\n", text)
    if not m: return text, []
    start = m.start() + (1 if text[m.start()] == "\n" else 0)
    head, body = text[:start], text[start:]
    return head, [b for b in BLOCK.split(body) if b.strip()]


def shuf(a):
    rng = random.Random(0); n = n_single = 0
    with open(a.out, "w", encoding="utf-8") as fo:
        for l in open(a.src, encoding="utf-8"):
            r = json.loads(l); head, blocks = split_chunk(r["text"]); n += 1
            if len(blocks) < 2: n_single += 1
            rng.shuffle(blocks)
            blocks = [re.sub(r"^\[s\d+\]", f"[s{i}]", b) for i, b in enumerate(blocks)]
            r["text"] = head + "\n".join(b.rstrip("\n") + "\n" for b in blocks).rstrip("\n") + "\n"
            fo.write(json.dumps({"text": r["text"], "dataset": r.get("dataset"), "run_id": r.get("run_id"), "chunk": r.get("chunk"), "nc": "shuf"}, ensure_ascii=False) + "\n")
    print(json.dumps({"chunks": n, "single_block_chunks_unchanged_order": n_single}))


def tokenizer(name):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(name)


def lens(a):
    tok = tokenizer(a.tokenizer)
    L = [len(tok(json.loads(l)["text"], add_special_tokens=False)["input_ids"]) for l in open(a.src, encoding="utf-8")]
    json.dump(L, open(a.out, "w")); print(json.dumps({"chunks": len(L), "tokens": sum(L)}))


def irr(a):
    import pyarrow.parquet as pq
    tok = tokenizer(a.tokenizer); L = json.load(open(a.lens)); need = sum(L) + 1000
    ids = []
    for p in a.wiki:
        for t in pq.read_table(p, columns=["text"]).column("text").to_pylist():
            if t.strip(): ids += tok(t, add_special_tokens=False)["input_ids"]
            if len(ids) >= need: break
        if len(ids) >= need: break
    assert len(ids) >= sum(L), (len(ids), sum(L))
    pos = 0
    with open(a.out, "w", encoding="utf-8") as fo:
        for i, n in enumerate(L):
            fo.write(json.dumps({"text": tok.decode(ids[pos: pos + n]), "dataset": "wikitext103", "chunk": i, "nc": "irr"}, ensure_ascii=False) + "\n"); pos += n
    print(json.dumps({"chunks": len(L), "tokens_target": sum(L), "tokens_used": pos}))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["shuf", "lens", "irr"])
    ap.add_argument("--src"); ap.add_argument("--out"); ap.add_argument("--lens"); ap.add_argument("--wiki", nargs="*")
    ap.add_argument("--tokenizer", default="Qwen/Qwen3-8B"); a = ap.parse_args()
    {"shuf": shuf, "lens": lens, "irr": irr}[a.mode](a)


if __name__ == "__main__":
    main()
