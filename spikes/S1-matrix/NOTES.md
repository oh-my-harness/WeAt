# S1 — Matrix + Synapse + matrix-nio

## 目标

验证 D7：用用户 access token 发的消息，在 Matrix 协议层 sender 就是用户 ID，群里其他人看不到 bot 痕迹。

## 步骤（本地 Synapse，无需 Docker）

```bash
# 安装 Synapse
uv add matrix-synapse

# 生成配置
mkdir -p /tmp/synapse-test
uv run python3 -m synapse.app.homeserver \
  --server-name localhost \
  --config-path /tmp/synapse-test/homeserver.yaml \
  --generate-config --report-stats=no

# 启动
uv run python3 -m synapse.app.homeserver \
  --config-path /tmp/synapse-test/homeserver.yaml &

# 注册用户
uv run register_new_matrix_user -c /tmp/synapse-test/homeserver.yaml \
  -u alice -p alice123 --no-admin http://localhost:8008
uv run register_new_matrix_user -c /tmp/synapse-test/homeserver.yaml \
  -u mybot -p bot123 --no-admin http://localhost:8008

# 跑 spike
MATRIX_HOMESERVER=http://localhost:8008 \
MATRIX_USERNAME=@alice:localhost \
MATRIX_TOKEN=<alice_token> \
MATRIX_ROOM_ID=<room_id> \
uv run python spikes/S1-matrix/test_matrix_nio.py
```

## 通过标准

- [x] whoami 验证 token 有效
- [x] room_messages 返回消息 timeline
- [x] room_send 成功，event_id 返回，sender = @alice:localhost（用户身份）
- [x] D7 假设验证：用 token 发消息 = 用户本人发消息，无任何 bot 标识

## 关键发现

- **直接用 REST API**（aiohttp）比 matrix-nio AsyncClient 更可靠，无需先 sync
- matrix-nio 的 `room_messages` 在未 sync 情况下会阻塞；生产代码的 Matrix MCP Server 需要先做一次 sync 或改用 REST
- matrix.org 在国内网络下被 GFW 屏蔽，本地 Synapse 是开发测试的最佳选择

## 版本

matrix-synapse 1.141.0 / Python 3.12

