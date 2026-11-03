#!/usr/bin/env bash
# Downloads the two quantised models used in the evaluation (about 1.6 GB in total) into ./models
# and checks them against the SHA-256 of the files used for the committed results.
set -euo pipefail
mkdir -p models
base=https://huggingface.co/Qwen
curl -L -o models/qwen2.5-1.5b-instruct-q4_k_m.gguf "$base/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
curl -L -o models/qwen2.5-0.5b-instruct-q4_k_m.gguf "$base/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
cd models
sha256sum -c <<'SUMS'
6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e  qwen2.5-1.5b-instruct-q4_k_m.gguf
74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db  qwen2.5-0.5b-instruct-q4_k_m.gguf
SUMS
