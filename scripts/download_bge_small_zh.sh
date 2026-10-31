#!/usr/bin/env bash
# Download BAAI/bge-small-zh-v1.5 for the local embedding server.
# Usage: ./download_bge_small_zh.sh [destination]
set -euo pipefail

MODEL="BAAI/bge-small-zh-v1.5"
DEST="${1:-$HOME/embedding-service/bge-small-zh-v1.5}"
MIRROR="${HF_ENDPOINT:-https://hf-mirror.com}"
OFFICIAL="https://huggingface.co"
FILES=(config.json tokenizer.json tokenizer_config.json vocab.txt special_tokens_map.json)

mkdir -p "$DEST"
cd "$DEST"

fetch() {
  local base="$1" file="$2"
  local url="$base/$MODEL/resolve/main/$file"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --retry-delay 2 --connect-timeout 15 \
      -o "$file" "$url?download=true"
  else
    wget -O "$file" "$url"
  fi
}

for file in "${FILES[@]}"; do
  echo "==> $file"
  fetch "$MIRROR" "$file" || fetch "$OFFICIAL" "$file"
done

WEIGHTS="model.safetensors"
echo "==> $WEIGHTS"
if ! fetch "$MIRROR" "$WEIGHTS"; then
  echo "model.safetensors not available; trying pytorch_model.bin"
  WEIGHTS="pytorch_model.bin"
  fetch "$MIRROR" "$WEIGHTS" || fetch "$OFFICIAL" "$WEIGHTS"
fi

for file in "${FILES[@]}" "$WEIGHTS"; do
  if [ ! -s "$file" ]; then
    echo "ERROR: missing or empty: $DEST/$file" >&2
    exit 1
  fi
done

echo
echo "OK: $DEST"
ls -lh
