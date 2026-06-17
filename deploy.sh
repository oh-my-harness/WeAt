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
read -sp "设置管理员令牌（留空则跳过）: " ADMIN_TOKEN_VAL
echo ""
read -sp "设置邀请码（留空则禁用自助注册）: " INVITE_CODE_VAL
echo ""
read -sp "设置 Matrix 管理员用户名（一般为 admin，留空则跳过）: " MATRIX_ADMIN_USER_VAL
echo ""
read -sp "设置 Matrix 管理员密码: " MATRIX_ADMIN_PASSWORD_VAL
echo ""

echo "SERVER_NAME=${DOMAIN}" > .env
if [ -n "$ADMIN_TOKEN_VAL" ]; then
  echo "ADMIN_TOKEN=${ADMIN_TOKEN_VAL}" >> .env
fi
if [ -n "$INVITE_CODE_VAL" ]; then
  echo "INVITE_CODE=${INVITE_CODE_VAL}" >> .env
fi
if [ -n "$MATRIX_ADMIN_USER_VAL" ]; then
  echo "MATRIX_ADMIN_USER=${MATRIX_ADMIN_USER_VAL}" >> .env
fi
if [ -n "$MATRIX_ADMIN_PASSWORD_VAL" ]; then
  echo "MATRIX_ADMIN_PASSWORD=${MATRIX_ADMIN_PASSWORD_VAL}" >> .env
fi

echo ""
echo "=== 数据初始化 ==="
read -p "是否清除已有数据（用户、聊天记录）并重新开始？(y/n): " RESET_DATA
if [ "$RESET_DATA" = "y" ] || [ "$RESET_DATA" = "Y" ]; then
    echo "停止服务并清除数据..."
    docker compose -f docker-compose.prod.yml down -v 2>/dev/null || true
    rm -f backend/users.json
    echo "数据已清除"
else
    # 如果用户已启用，但 admin 用户名变了，更新 users.json
    if [ -n "$MATRIX_ADMIN_USER_VAL" ]; then
        OLD_USER=$(jq -r '.[0].name' backend/users.json 2>/dev/null | cut -d@ -f2 | cut -d: -f1 || true)
        if [ -n "$OLD_USER" ] && [ "$OLD_USER" != "$MATRIX_ADMIN_USER_VAL" ]; then
            echo "检测到管理员用户名变更（$OLD_USER → $MATRIX_ADMIN_USER_VAL），更新 users.json..."
            python3 -c "
import json
try:
    with open('backend/users.json') as f:
        users = json.load(f)
    domain = '${DOMAIN}'
    old = '@${OLD_USER}:localhost'
    new = '@${MATRIX_ADMIN_USER_VAL}:${DOMAIN}'
    for u in users:
        if u.get('name') == old:
            u['name'] = new
    with open('backend/users.json', 'w') as f:
        json.dump(users, f, indent=2)
    print('已更新')
except FileNotFoundError:
    pass
"
        fi
    fi
fi

echo ""
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
