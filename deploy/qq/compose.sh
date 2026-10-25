#!/bin/sh
# 固定项目入口：WSL 显式挂载 GPU 设备；Linux 使用标准 NVIDIA runtime。
set -eu
qq_deploy_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -c /dev/dxg ] && [ -d /usr/lib/wsl/lib ]; then
    exec docker compose -f "$qq_deploy_dir/compose.yaml" -f "$qq_deploy_dir/qwen.wsl.yaml" "$@"
fi
exec docker compose -f "$qq_deploy_dir/compose.yaml" "$@"
