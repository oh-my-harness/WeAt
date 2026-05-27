"""
First-run configuration wizard.

Runs a small FastAPI/uvicorn server on localhost:8080 to collect:
  - Matrix homeserver URL
  - User's Matrix username + password (exchanges for access_token)
  - Bot's Matrix username + password
  - Vault path
  - opencode model (optional)

Saves config to weat.json and exits.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import webbrowser
from pathlib import Path

import nio
import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .settings import Config

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("weat.json")

HTML_FORM = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>WeAt 初次配置</title>
<style>
body{font-family:system-ui,sans-serif;max-width:560px;margin:60px auto;padding:0 20px;color:#222}
h1{font-size:1.4rem;margin-bottom:4px}
p.sub{color:#666;font-size:.9rem;margin-top:0}
label{display:block;margin-top:18px;font-weight:600;font-size:.9rem}
input[type=text],input[type=password],input[type=url]{width:100%;padding:8px 10px;border:1px solid #ccc;border-radius:6px;font-size:.95rem;box-sizing:border-box;margin-top:4px}
button{margin-top:28px;width:100%;padding:10px;background:#2563eb;color:#fff;border:none;border-radius:8px;font-size:1rem;cursor:pointer}
button:hover{background:#1d4ed8}
.section{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px 20px;margin-top:24px}
.section h2{font-size:1rem;margin:0 0 2px}
.hint{font-size:.82rem;color:#64748b;margin-top:2px}
</style>
</head>
<body>
<h1>WeAt — 初次配置</h1>
<p class="sub">配置完成后会自动关闭此页面。</p>

<form method="post" action="/setup">
  <div class="section">
    <h2>Matrix 服务器</h2>
    <label>Homeserver URL <span class="hint">如 https://matrix.org</span>
      <input type="url" name="homeserver" required value="https://matrix.org">
    </label>
  </div>

  <div class="section">
    <h2>你的 Matrix 账号（副驾驶以此身份发消息）</h2>
    <label>用户名 <span class="hint">如 @alice:matrix.org</span>
      <input type="text" name="user_id" required placeholder="@you:matrix.org">
    </label>
    <label>密码
      <input type="password" name="user_password" required>
    </label>
  </div>

  <div class="section">
    <h2>Bot 账号（用于接收你的私信指令）</h2>
    <label>Bot 用户名 <span class="hint">如 @myassistant:matrix.org</span>
      <input type="text" name="bot_user_id" required placeholder="@myassistant:matrix.org">
    </label>
    <label>Bot 密码
      <input type="password" name="bot_password" required>
    </label>
  </div>

  <div class="section">
    <h2>本地 Obsidian Vault</h2>
    <label>Vault 目录（绝对路径）<span class="hint">如 /Users/alice/Documents/Notes</span>
      <input type="text" name="vault_path" required placeholder="/Users/you/Documents/Notes">
    </label>
  </div>

  <div class="section">
    <h2>AI 模型（可选）</h2>
    <label>opencode 模型 <span class="hint">留空使用 opencode 默认值，或填 anthropic/claude-sonnet-4-5</span>
      <input type="text" name="opencode_model" placeholder="anthropic/claude-sonnet-4-5">
    </label>
  </div>

  <button type="submit">保存配置并启动</button>
</form>
</body>
</html>
"""

DONE_HTML = """<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>WeAt 配置完成</title>
<style>body{font-family:system-ui;max-width:400px;margin:80px auto;text-align:center;color:#222}</style>
</head>
<body>
<h1>✅ 配置完成</h1>
<p>WeAt bridge 已启动，可以关闭此窗口。</p>
<p style="color:#666;font-size:.9rem">在 Element 里找到你的 bot，发送 <code>/help</code> 开始。</p>
</body>
</html>
"""


async def _login(homeserver: str, user_id: str, password: str) -> str:
    client = nio.AsyncClient(homeserver, user_id)
    resp = await client.login(password)
    await client.close()
    if isinstance(resp, nio.LoginError):
        raise ValueError(f"Login failed for {user_id}: {resp.message}")
    return resp.access_token


app = FastAPI()
_shutdown_event = asyncio.Event()


@app.get("/", response_class=HTMLResponse)
async def get_form():
    return HTML_FORM


@app.post("/setup", response_class=HTMLResponse)
async def post_setup(
    homeserver: str = Form(...),
    user_id: str = Form(...),
    user_password: str = Form(...),
    bot_user_id: str = Form(...),
    bot_password: str = Form(...),
    vault_path: str = Form(...),
    opencode_model: str = Form(""),
):
    try:
        user_token, bot_token = await asyncio.gather(
            _login(homeserver, user_id, user_password),
            _login(homeserver, bot_user_id, bot_password),
        )
    except ValueError as e:
        return HTMLResponse(f"<p style='color:red'>{e}</p><a href='/'>返回</a>", status_code=400)

    config = Config(
        homeserver=homeserver,
        user_id=user_id,
        access_token=user_token,
        bot_user_id=bot_user_id,
        bot_access_token=bot_token,
        vault_path=vault_path,
        opencode_model=opencode_model,
    )
    config.save(CONFIG_PATH)
    logger.info("Config saved to %s", CONFIG_PATH)

    _shutdown_event.set()
    return HTMLResponse(DONE_HTML)


def main():
    logging.basicConfig(level=logging.INFO)
    if CONFIG_PATH.exists():
        print(f"Config already exists at {CONFIG_PATH}. Delete it to re-run setup.")
        sys.exit(0)

    port = int(os.environ.get("WEAT_WIZARD_PORT", "8080"))
    url = f"http://localhost:{port}"
    print(f"Opening setup wizard at {url} ...")
    webbrowser.open(url)

    config = uvicorn.Config(app, host="localhost", port=port, log_level="warning")
    server = uvicorn.Server(config)

    async def run():
        task = asyncio.create_task(server.serve())
        await _shutdown_event.wait()
        server.should_exit = True
        await task

    asyncio.run(run())
    print("Setup complete. Run `weat-bridge` to start.")


if __name__ == "__main__":
    main()
