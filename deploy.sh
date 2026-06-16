#!/bin/bash
# 在服务器上执行：bash deploy.sh <服务器IP或域名>
# 例如: bash deploy.sh 124.221.2.9
set -e

SERVER_NAME="${1:?用法: bash deploy.sh <IP或域名>}"

echo "=== 安装 Docker ==="
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

echo "=== 安装 Node.js ==="
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

echo "=== 构建前端 ==="
cd frontend
npm ci
npm run build
cd ..

echo "=== 生成 .env ==="
echo "SERVER_NAME=${SERVER_NAME}" > .env

echo "=== 启动服务 ==="
docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "=== 部署完成 ==="
echo "访问地址: http://${SERVER_NAME}"
