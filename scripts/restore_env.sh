#!/usr/bin/env bash
# Restore the sandbox environment in a fresh session (after cloning the private repo).
# Usage: bash scripts/restore_env.sh            # uses data/AEGIS-custom-dataset-8-13.7z from the repo
#        bash scripts/restore_env.sh <.7z|FULL handoff .zip>
# Afterwards:  export MHT_DATA_DIR=/home/claude/aegis_813/AEGIS-custom-dataset
# API keys are NOT in the repo: read the Project doc "api端点" and write /home/claude/.mht_api.env.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-$REPO/data/AEGIS-custom-dataset-8-13.7z}"
DEST=/home/claude/aegis_813

pip install py7zr matplotlib numpy scipy scikit-learn pandas --break-system-packages -q
python3 -c "import torch" 2>/dev/null || \
  pip install torch --index-url https://download.pytorch.org/whl/cpu --break-system-packages -q

if [[ "$SRC" == *.zip ]]; then
  TMP="$(mktemp -d)"
  unzip -q "$SRC" -d "$TMP"
  SEVENZ="$(find "$TMP" -name 'AEGIS-custom-dataset-8-13.7z' | head -1)"
  # data-derived files kept out of the public repo
  CODE="$(find "$TMP" -maxdepth 2 -type d -name medhypertrace | head -1)"
  if [[ -n "$CODE" ]]; then
    mkdir -p "$REPO/data" "$REPO/baselines/aegis_sft_ood"
    cp -r "$CODE/data/emb_cache" "$REPO/data/" 2>/dev/null || true
    cp -r "$CODE/baselines/aegis_sft_ood/eval_samples" "$REPO/baselines/aegis_sft_ood/" 2>/dev/null || true
  fi
else
  SEVENZ="$SRC"
fi

mkdir -p "$DEST"
python3 -c "import py7zr,sys; py7zr.SevenZipFile(sys.argv[1]).extractall(sys.argv[2])" "$SEVENZ" "$DEST"
export MHT_DATA_DIR="$DEST/AEGIS-custom-dataset"
cd "$REPO" && python3 validate.py > /tmp/mht_validate.log && grep -m1 "^instances" /tmp/mht_validate.log
echo "OK. Now run: export MHT_DATA_DIR=$MHT_DATA_DIR"
