#!/usr/bin/env bash
# WeAt Web — 开发环境启动脚本
#
# 使用方法:
#   ./dev.sh              # 启动全部（Matrix + 后端 + 前端）
#   ./dev.sh backend      # 只启动后端
#   ./dev.sh frontend     # 只启动前端
#   ./dev.sh stop         # 停止全部

set -e
set -o pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }

# ── 检测依赖 ────────────────────────────────────────────────────────────────

check_deps() {
  if ! command -v docker &>/dev/null; then
    warn "docker 未安装，跳过 Matrix 服务启动"
    return 1
  fi
  if ! docker compose version &>/dev/null 2>&1; then
    warn "docker compose 不可用，跳过 Matrix 服务启动"
    return 1
  fi
  return 0
}

# ── 启动 Matrix ─────────────────────────────────────────────────────────────

start_matrix() {
  info "启动 Tuwunel (Matrix server)…"
  cd "$ROOT"
  docker compose up -d matrix
  ok "Tuwunel 已启动 → http://localhost:8008"

  # 等待就绪
  for i in $(seq 1 10); do
    if curl -sf http://localhost:8008/_matrix/client/versions >/dev/null 2>&1; then
      ok "Tuwunel 就绪"
      return 0
    fi
    sleep 1
  done
  warn "Tuwunel 启动超时"
}

# ── 启动后端 ────────────────────────────────────────────────────────────────

start_backend() {
  if [ ! -d "$ROOT/backend" ]; then
    warn "backend/ 不存在，跳过"
    return
  fi

  # 如果端口占用，先提示
  if lsof -ti :8000 &>/dev/null; then
    warn "端口 8000 被占用，跳过后端启动"
    warn "  执行 ./dev.sh stop 后重试"
    return
  fi

  info "启动 WeAt 后端…"
  cd "$ROOT"

  # 确保虚拟环境存在
  if [ ! -d "$ROOT/.venv" ]; then
    info "创建 Python 虚拟环境…"
    uv venv
    uv pip install -r backend/requirements.txt
  fi

  mkdir -p "$ROOT/tmp"
  PYTHONPATH="$ROOT" nohup uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 \
    > "$ROOT/tmp/backend.log" 2>&1 &
  BACKEND_PID=$!
  echo "$BACKEND_PID" > /tmp/weat_backend.pid
  ok "后端已启动 → http://localhost:8000 (PID: $BACKEND_PID, 日志: tmp/backend.log)"
}

# ── 启动前端 ────────────────────────────────────────────────────────────────

start_frontend() {
  if [ ! -d "$ROOT/frontend" ]; then
    warn "frontend/ 不存在，跳过"
    return
  fi

  if lsof -ti :5173 &>/dev/null; then
    warn "端口 5173 被占用，跳过后端启动"
    warn "  执行 ./dev.sh stop 后重试"
    return
  fi

  info "启动 WeAt 前端…"
  cd "$ROOT/frontend"

  if [ ! -d node_modules ]; then
    info "安装前端依赖…"
    npm install
  fi

  nohup npx vite --host 0.0.0.0 --port 5173 \
    > "$ROOT/tmp/frontend.log" 2>&1 &
  FRONTEND_PID=$!
  echo "$FRONTEND_PID" > /tmp/weat_frontend.pid
  ok "前端已启动 → http://localhost:5173 (PID: $FRONTEND_PID, 日志: tmp/frontend.log)"
}

# ── 停止全部 ────────────────────────────────────────────────────────────────

stop_all() {
  info "停止…"
  cd "$ROOT"

  # 杀 PID 文件记录的进程
  for pidfile in /tmp/weat_backend.pid /tmp/weat_frontend.pid; do
    if [ -f "$pidfile" ]; then
      pid=$(cat "$pidfile")
      kill "$pid" 2>/dev/null && ok "进程 $pid 已停止" || true
      rm -f "$pidfile"
    fi
  done

  # 额外清理：杀残留的 uvicorn / vite（以防 PID 文件丢失）
  lsof -ti :8000 2>/dev/null | xargs kill 2>/dev/null || true
  lsof -ti :5173 2>/dev/null | xargs kill 2>/dev/null || true

  if check_deps; then
    docker compose stop matrix && ok "Matrix 已停止" || true
  fi
}

# ── 主逻辑 ──────────────────────────────────────────────────────────────────

case "${1:-all}" in
  all)
    info "启动 WeAt Web 开发环境…"
    if check_deps; then
      start_matrix
    fi
    start_backend
    start_frontend
    ok "全部已启动："
    echo -e "  ${GREEN}后端${NC}:  http://localhost:8000  (API + Swagger: /docs)"
    echo -e "  ${GREEN}前端${NC}:  http://localhost:5173"
    echo -e "  ${GREEN}Matrix${NC}: http://localhost:8008"
    echo ""
    echo -e "  登录用户名: alice (由管理员创建)"
    echo -e "  按 ${YELLOW}Ctrl+C${NC} 或 ${BLUE}./dev.sh stop${NC} 停止"
    ;;
  backend)
    start_backend
    ;;
  frontend)
    start_frontend
    ;;
  stop)
    stop_all
    ;;
  *)
    echo "用法: $0 [all|backend|frontend|stop]"
    exit 1
    ;;
esac
