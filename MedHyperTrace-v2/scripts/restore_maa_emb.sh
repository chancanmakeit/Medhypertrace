#!/usr/bin/env bash
# Restore the cached MiniLM embeddings of the MAA corpus (saves ~50 min of CPU embedding).
#   bash scripts/restore_maa_emb.sh <emb_dir>      (run from MedHyperTrace-v2/)
# Rows are keyed by sha1 of the embedded text (index.json), so they match any re-run of
# data_tools/maa_to_mas_traj.py on the same MedAgentAudit release.
set -euo pipefail
OUT=${1:?emb dir}; S="$(dirname "$0")/../data/maa_emb_minilm"; mkdir -p "$OUT"
cat "$S"/emb.npy.gz.part* | gunzip > "$OUT/emb.npy"
gunzip -c "$S/index.json.gz" > "$OUT/index.json"
(cd "$OUT" && sha256sum -c "$(cd - >/dev/null; cd "$S"; pwd)/SHA256SUMS")
