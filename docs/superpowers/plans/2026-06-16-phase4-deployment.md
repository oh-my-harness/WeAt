# Phase 4: 部署 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一键部署到服务器：docker-compose（Tuwunel + WeAt 后端 + Nginx 前端）+ 安装脚本 + HTTPS。

**Architecture:** Nginx 作为反向代理：`/api/*` 和 `/ws` 代理到 FastAPI 后端 (8000)，`/` 服务前端静态文件 (dist/)。docker-compose 编排 3 个服务（matrix / backend / nginx）。前端在镜像构建阶段完成 `npm run build`。

**Tech Stack:** Nginx (Alpine), Docker Compose v3, Shell 脚本

---

### Task 1: 前端多阶段 Dockerfile

**Files:**
- Create: `frontend/Dockerfile`

前端 Docker 镜像：Node 构建阶段 + Nginx 运行阶段。构建产物通过 volume 或 COPY 供 Nginx 使用。

- [ ] **Step 1: 编写前端 Dockerfile**

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
# 构建产物复制到 Nginx 静态目录
COPY --from=builder /app/dist /usr/share/nginx/html
# 自定义 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

> 注：此 Dockerfile 也可通过 docker-compose 中的 `build` 直接引用前端目录来构建，使 nginx 镜像内置前端静态文件。

- [ ] **Step 2: Commit**

```bash
git add frontend/Dockerfile
git commit -m "build: add frontend Dockerfile (multi-stage Node + Nginx)"
```

---

### Task 2: Nginx 配置

**Files:**
- Create: `nginx.conf` (项目根目录)

Nginx 作为统一入口：静态文件 + API 反向代理 + WebSocket 升级。

- [ ] **Step 1: 编写 nginx.conf**

```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # 前端 SPA — 所有非 /api /ws 路径 fallback 到 index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理到 WeAt 后端
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket 反向代理
    location /ws {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # Gzip 静态资源
    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;
    gzip_min_length 256;
    gzip_vary on;
}
```

- [ ] **Step 2: 验证 Nginx 配置语法（需在容器内或本地安装 nginx）**

```bash
docker run --rm -v $(pwd)/nginx.conf:/etc/nginx/conf.d/default.conf:ro nginx:alpine nginx -t 2>&1
```

Expected: `syntax is ok` / `test is successful`

- [ ] **Step 3: Commit**

```bash
git add nginx.conf
git commit -m "feat: add Nginx config — reverse proxy + SPA fallback + WS upgrade"
```

---

### Task 3: 生产 docker-compose.yml

**Files:**
- Modify: `docker-compose.yml` (项目根目录)

在现有 matrix + backend 基础上，改为 nginx 统一入口（构建自前端目录 + nginx.conf）。替换现有 docker-compose.yml 内容。

- [ ] **Step 1: 重写 docker-compose.yml**

```yaml
# WeAt Web — 生产部署
# docker compose up -d → Matrix + Backend + Nginx 全栈
#
# 使用方法:
#   1. ./install.sh          # 首次安装（创建 admin 用户）
#   2. docker compose up -d  # 启动
#   3. 浏览器打开 http://localhost

services:
  # ── Matrix 服务 ──────────────────────────────────────────────
  matrix:
    image: ghcr.io/matrix-construct/tuwunel:latest
    container_name: weat_matrix
    restart: unless-stopped
    expose:
      - "8008"
    volumes:
      - matrix-data:/var/lib/tuwunel
    environment:
      TUWUNEL_SERVER_NAME: localhost
      TUWUNEL_ADDRESS: 0.0.0.0
      TUWUNEL_PORT: 8008
      TUWUNEL_ALLOW_REGISTRATION: "false"
      TUWUNEL_ALLOW_FEDERATION: "false"
      TUWUNEL_LOG: info

  # ── WeAt 后端 ──────────────────────────────────────────────
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: weat_backend
    restart: unless-stopped
    expose:
      - "8000"
    environment:
      MATRIX_BASE: http://matrix:8008
    depends_on:
      - matrix

  # ── Nginx (前端静态 + 反向代理) ─────────────────────────────
  nginx:
    build:
      context: .
      dockerfile: frontend/Dockerfile
      # Dockerfile 从根目录构建以便 COPY nginx.conf
      # 注意：需要在 docker-compose build context 中有 nginx.conf 和 frontend/
    container_name: weat_nginx
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  matrix-data:
```

> 注：`frontend/Dockerfile` 的 COPY 路径需要调整 — COPY nginx.conf 需要从项目根目录获取。需要在 docker-compose build context 设置中支持。

- [ ] **Step 2: 调整 frontend/Dockerfile 以适配 docker-compose build context**

因为 docker-compose `build.context` 需要是项目根目录（才能 COPY nginx.conf），修改 frontend/Dockerfile：

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

同时更新 docker-compose.yml 中 nginx 服务的 context：

```yaml
  nginx:
    build:
      context: .
      dockerfile: frontend/Dockerfile
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml frontend/Dockerfile
git commit -m "build: production docker-compose with Nginx unified entry"
```

---

### Task 4: 后端 CORS 生产配置

**Files:**
- Modify: `backend/main.py:61-67`

当前 CORS 仅允许 `localhost:5173`（开发环境）。生产环境需要允许实际域名或 Nginx 同源。

- [ ] **Step 1: 更新 CORS 允许生产地址**

```python
# 在 backend/main.py 中修改 CORS 配置

import os

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost,http://127.0.0.1"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

实际上，当 Nginx 反向代理时，前端和后端同域（都通过 Nginx），不需 CORS。但为了兼容直接访问后端的场景，通过环境变量配置。

- [ ] **Step 2: Commit**

```bash
git add backend/main.py
git commit -m "fix: make CORS origins configurable via env var"
```

---

### Task 5: 安装脚本

**Files:**
- Create: `install.sh` (项目根目录)

一键安装部署脚本：检查依赖 → 启动 docker compose → 创建 admin 用户。

- [ ] **Step 1: 编写 install.sh**

```bash
#!/usr/bin/env bash
# WeAt Web — 一键安装部署脚本
#
# 支持的操作系统：Linux (amd64/arm64), macOS
# 前提：安装 Docker + Docker Compose
#
# 使用方法：
#   chmod +x install.sh
#   ./install.sh
#
# 可选环境变量：
#   WEAT_DOMAIN=chat.example.com    # 生产域名（用于 SSL 提示）
#   WEAT_ADMIN_USER=admin           # 管理员用户名
#   WEAT_ADMIN_PASS=                # 管理员密码（留空自动生成）
#   WEAT_PORT=80                    # HTTP 端口

set -e
set -o pipefail

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

ROOT="$(cd "$(dirname "$0")" && pwd)"
WEAT_PORT="${WEAT_PORT:-80}"

echo -e "${BOLD}WeAt Web 安装脚本${NC}"
echo "=============================="
echo ""

# ── Step 1: 检查依赖 ──────────────────────────────────────────

info "检查依赖..."

if ! command -v docker &>/dev/null; then
    err "未安装 Docker。请先安装: https://docs.docker.com/engine/install/"
    exit 1
fi

COMPOSE_CMD=""
if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    err "未安装 Docker Compose。"
    exit 1
fi

ok "Docker + Compose 可用"

# ── Step 2: 生成配置 ──────────────────────────────────────────

info "准备配置..."

cd "$ROOT"

# 如果指定了端口，更新 docker-compose nginx 端口映射
if [ "$WEAT_PORT" != "80" ]; then
    warn "使用自定义端口: $WEAT_PORT"
    # 通过 docker compose override 处理
    cat > docker-compose.override.yml <<EOF
services:
  nginx:
    ports:
      - "${WEAT_PORT}:80"
EOF
fi

ok "配置就绪"

# ── Step 3: 启动服务 ──────────────────────────────────────────

info "构建并启动服务..."
$COMPOSE_CMD up -d --build

# 等待 Matrix 就绪
info "等待 Tuwunel 就绪..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8008/_matrix/client/versions >/dev/null 2>&1; then
        ok "Tuwunel 就绪"
        break
    fi
    if [ "$i" -eq 30 ]; then
        err "Tuwunel 启动超时。请检查日志: $COMPOSE_CMD logs matrix"
        exit 1
    fi
    sleep 2
done

# 等待后端就绪
info "等待后端就绪..."
for i in $(seq 1 15); do
    if curl -sf http://localhost:8000/docs >/dev/null 2>&1; then
        ok "后端就绪"
        break
    fi
    if [ "$i" -eq 15 ]; then
        err "后端启动超时。请检查日志: $COMPOSE_CMD logs backend"
        exit 1
    fi
    sleep 2
done

# ── Step 4: 创建管理员用户 ────────────────────────────────────

ADMIN_USER="${WEAT_ADMIN_USER:-admin}"
ADMIN_PASS="${WEAT_ADMIN_PASS:-$(openssl rand -base64 12 2>/dev/null || head -c 12 /dev/urandom | base64)}"

info "创建管理员用户: $ADMIN_USER"

docker exec weat_backend uv run python -m backend.admin_cli add-user "$ADMIN_USER" "$ADMIN_PASS" 2>/dev/null || {
    warn "用户 $ADMIN_USER 可能已存在，跳过创建"
}

# ── Step 5: 完成 ──────────────────────────────────────────────

echo ""
echo -e "${GREEN}${BOLD}✅ WeAt Web 安装完成！${NC}"
echo ""
echo -e "  ${BOLD}访问地址:${NC}  http://localhost${WEAT_PORT != "80" && ":"$WEAT_PORT || ""}"
echo -e "  ${BOLD}管理员:${NC}    $ADMIN_USER"
echo -e "  ${BOLD}密码:${NC}      $ADMIN_PASS"
echo ""
echo -e "  创建更多用户:"
echo -e "    docker exec weat_backend uv run python -m backend.admin_cli add-user <用户名> <密码>"
echo ""
echo -e "  查看日志:"
echo -e "    $COMPOSE_CMD logs -f"
echo ""
echo -e "  ⚠️  请立即记录上述管理员密码！"
echo ""

# ── HTTPS 提示 ────────────────────────────────────────────────

echo -e "${YELLOW}生产部署建议:${NC}"
echo -e "  1. 配置 HTTPS: 使用 Cloudflare Tunnel / Tailscale Funnel / Caddy"
echo -e "  2. 设置 Caddy 反向代理示例:"
echo -e "     ${BLUE}caddy reverse-proxy --from your.domain.com --to localhost:${WEAT_PORT}${NC}"
echo -e "  3. 关闭 Tuwunel 开放注册（已默认关闭）"
echo ""
```

- [ ] **Step 2: 赋予执行权限**

```bash
chmod +x install.sh
```

- [ ] **Step 3: Commit**

```bash
git add install.sh
git commit -m "feat: add one-command install script"
```

---

### Task 6: .gitignore 更新

**Files:**
- Modify: `.gitignore` (项目根目录)

确保 docker-compose.override.yml 和构建产物被忽略。

- [ ] **Step 1: 检查并更新 .gitignore**

```bash
cat .gitignore
```

确认有以下条目（缺失则追加）:

```gitignore
docker-compose.override.yml
frontend/dist/
*.tsbuildinfo
tmp/
```

- [ ] **Step 2: Commit (如有变更)**

```bash
git add .gitignore
git commit -m "chore: update .gitignore for production artifacts"
```

---

### Task 7: 端到端部署验证

- [ ] **Step 1: 在干净环境测试安装脚本**

```bash
# 停止现有开发服务
./dev.sh stop 2>/dev/null || true
docker compose down -v 2>/dev/null || true

# 运行安装
./install.sh
```

- [ ] **Step 2: 验证服务可用**

```bash
# Matrix
curl -s http://localhost:8008/_matrix/client/versions | head -c 100

# Backend (通过 Nginx)
curl -s http://localhost/api/me?token=invalid 2>&1 | head -c 100

# Frontend (通过 Nginx)
curl -s http://localhost/ | head -c 200
```

Expected: Matrix 返回 JSON 版本信息。Backend 返回 401 (invalid token)。Frontend 返回 HTML (index.html)。

- [ ] **Step 3: 浏览器验证**

1. 打开 http://localhost → 看到 WeAt 登录页
2. 用安装脚本输出的管理员用户登录
3. 进入聊天 → 正常收发消息

- [ ] **Step 4: 创建房间验证**

```bash
docker exec weat_backend uv run python -m backend.admin_cli add-user bob pass456
```

- [ ] **Step 5: 验证 HTTPS 反向代理（可选）**

如使用 Caddy：
```bash
caddy reverse-proxy --from chat.example.com --to :80
```
访问 https://chat.example.com → 应正常加载

- [ ] **Step 6: Commit (如有修复)**

```bash
git add -A
git commit -m "fix: production deployment verification fixes"
```

---

## Self-Review

**1. Spec coverage:**

| Phase 4 需求 | 任务 |
|------|------|
| docker-compose（Tuwunel + WeAt + Nginx） | Task 3 — 重写 docker-compose.yml |
| Nginx 配置 | Task 2 — nginx.conf |
| HTTPS（Let's Encrypt） | Task 5 + Task 7 — install.sh 中含 Caddy/Cloudflare Tunnel 指引（docker-compose 不直接处理证书） |
| 安装脚本 | Task 5 — install.sh |

**2. Placeholder scan:** 无 TBD/TODO。所有步骤均有完整配置和命令。

**3. Type consistency:**
- 环境变量命名一致：`MATRIX_BASE`, `ALLOWED_ORIGINS`, `WEAT_*`
- 端口映射一致：Matrix 8008, Backend 8000, Nginx 80
- Docker 服务名与 Nginx proxy_pass 引用一致（`http://backend:8000`）
