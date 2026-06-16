#!/bin/bash
# 在服务器上执行：bash deploy.sh <域名>
# 例如: bash deploy.sh oh-my-harness.site
set -e

DOMAIN="${1:?用法: bash deploy.sh <域名>}"

echo "=== 安装 Docker ==="
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# 检测 Docker Hub 是否可访问，不行则配国内镜像
if ! docker pull --quiet nginx:alpine > /dev/null 2>&1; then
    echo "Docker Hub 不可达，配置国内镜像加速..."
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": ["https://mirror.ccs.tencentyun.com"]
}
EOF
    systemctl daemon-reload && systemctl restart docker
fi

echo "=== 安装 Node.js ==="
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

echo "=== 安装 certbot ==="
if ! command -v certbot &> /dev/null; then
    apt-get install -y certbot
fi

echo "=== 构建前端 ==="
cd frontend
npm ci
npm run build
cd ..

echo "=== 生成 .env ==="
echo "SERVER_NAME=${DOMAIN}" > .env

echo "=== 第一阶段：HTTP 模式启动 nginx（用于申请证书）==="
mkdir -p /var/www/certbot
docker rm -f weat_nginx_init 2>/dev/null || true
docker run -d --name weat_nginx_init \
    -p 80:80 \
    -v "$(pwd)/frontend/dist:/usr/share/nginx/html:ro" \
    -v "/var/www/certbot:/var/www/certbot:ro" \
    -v "$(pwd)/nginx/nginx-init.conf:/etc/nginx/conf.d/default.conf:ro" \
    nginx:alpine

echo "=== 申请 SSL 证书 ==="
certbot certonly --webroot \
    -w /var/www/certbot \
    -d "${DOMAIN}" \
    --non-interactive \
    --agree-tos \
    --email "admin@${DOMAIN}"

echo "=== 停止临时 nginx ==="
docker rm -f weat_nginx_init

echo "=== 启动全部服务（HTTPS 模式）==="
docker compose -f docker-compose.prod.yml up -d --build

echo "=== 配置证书自动续期 ==="
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && docker exec weat_nginx nginx -s reload") | crontab -

echo ""
echo "=== 部署完成 ==="
echo "访问地址: https://${DOMAIN}"
