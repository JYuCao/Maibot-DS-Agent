#!/bin/sh
# 先验证实际 CUDA 设备，禁止在驱动失效时悄悄转成 CPU 推理。
set -eu
/app/llama-server --list-devices > /tmp/qwen-cuda-devices.log 2>&1
cat /tmp/qwen-cuda-devices.log
if ! grep -Eq 'CUDA[0-9]+:' /tmp/qwen-cuda-devices.log; then
    echo 'No CUDA GPU detected; refusing to start CPU inference.' >&2
    exit 1
fi
exec /app/llama-server "$@"
