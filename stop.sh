#!/bin/bash
# 一键关闭 WeAt 服务（保留数据）
# 用法: bash stop.sh
set -e

echo "=== 停止 WeAt 服务 ==="
docker compose -f docker-compose.prod.yml down
echo "=== 已停止（Matrix 数据已保留） ==="
