#!/bin/sh
# 固定项目入口：WSL 显式挂载 GPU 设备；Linux 使用标准 NVIDIA runtime。
set -eu
qq_deploy_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
qq_gateway=${QQ_GATEWAY:-}
if [ -z "$qq_gateway" ]; then
    if [ -f "$qq_deploy_dir/gateway.local" ]; then
        IFS= read -r qq_gateway < "$qq_deploy_dir/gateway.local"
    else
        qq_gateway=snowluma
    fi
fi
case "$qq_gateway" in
    snowluma|napcat) ;;
    *) echo "QQ_GATEWAY must be snowluma or napcat" >&2; exit 2 ;;
esac
if [ -c /dev/dxg ] && [ -d /usr/lib/wsl/lib ]; then
    exec docker compose --profile "$qq_gateway" -f "$qq_deploy_dir/compose.yaml" -f "$qq_deploy_dir/qwen.wsl.yaml" "$@"
fi
exec docker compose --profile "$qq_gateway" -f "$qq_deploy_dir/compose.yaml" "$@"
