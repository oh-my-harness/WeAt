# S1 — Matrix + Synapse + matrix-nio

## 目标

验证 D7：matrix-nio 发的消息在 Element 里对其他成员显示为「用户本人」的消息，无 bot 图标/额外字段。

## 步骤

```bash
# 有现成 Matrix 账号的快捷方式（用 matrix.org 公共服务器）
export MATRIX_HOMESERVER=https://matrix.org
export MATRIX_USERNAME=@youruser:matrix.org
export MATRIX_PASSWORD=yourpassword
export MATRIX_ROOM_ID='!roomid:matrix.org'

uv run python spikes/S1-matrix/test_matrix_nio.py
```

如果想本地起 Synapse（需要 Docker）：
```bash
# 需要先安装 Docker Desktop
docker run -d --name synapse \
  -v ./data:/data \
  -p 8008:8008 \
  matrixdotorg/synapse:latest generate
docker run -d --name synapse \
  -v ./data:/data \
  -p 8008:8008 \
  matrixdotorg/synapse:latest
# 然后 homeserver = http://localhost:8008
```

## 通过标准

- [ ] matrix-nio login 成功，拿到 access_token
- [ ] room_messages 返回 timeline 消息
- [ ] room_send 成功，Element 里消息显示为「用户本人」，无任何 bot 标识

## 结论

> TODO: 跑完后填写

## 踩坑

> TODO
