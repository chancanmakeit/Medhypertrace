# MAA embedding cache (round 38)

`sentence-transformers/all-MiniLM-L6-v2` embeddings (384-d, float16, L2-normalised, max_seq 256) of every unique
text in the converted MedAgentAudit corpus: task queries, step outputs (≤2000 chars), "phase | role" strings.
85,913 rows; mdagents `basic` runs excluded. Produced by `python -m hgfm.embed_maa` (≈50 min on 2 CPU cores, see `embed_log.txt`).

- `emb.npy.gz.part00/01`: gzip of `emb.npy`, split at 40 MB (GitHub file-size limit).
- `index.json.gz`: `{sha1(text): row}`.
- `SHA256SUMS`: checksums of the restored `emb.npy` / `index.json`.

Restore: `bash scripts/restore_maa_emb.sh <emb_dir>` (`prepare_maa.sh` does this automatically).
The graph caches (`graphs_*.pkl`, ~0.3–0.6 GB each) are not stored; they are rebuilt from these on first load.
