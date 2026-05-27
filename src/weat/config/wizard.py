"""
First-run configuration wizard — interactive CLI.

Steps:
  1. Matrix homeserver + login (username + password)
  2. Vault path
  3. LLM provider + API key  →  writes ~/.local/share/opencode/auth.json
  4. Creates a private WeAt command room
  5. Writes weat.json
"""
from __future__ import annotations

import asyncio
import getpass
import json
import sys
from pathlib import Path

import aiohttp

from .settings import Config

PROVIDERS = {
    "1": ("deepseek", "DeepSeek（推荐，便宜）", "deepseek/deepseek-chat"),
    "2": ("anthropic", "Anthropic (Claude)", "anthropic/claude-sonnet-4-5"),
    "3": ("openai", "OpenAI", "openai/gpt-4o"),
}


def _opencode_auth_path() -> Path:
    return Path.home() / ".local" / "share" / "opencode" / "auth.json"


def _prompt(label: str, default: str = "", secret: bool = False) -> str:
    suffix = f"（回车用 {default}）" if default else ""
    prompt_str = f"  {label}{suffix}: "
    val = getpass.getpass(prompt_str) if secret else input(prompt_str).strip()
    return val or default


async def _login(session: aiohttp.ClientSession, homeserver: str, user_id: str, password: str) -> str:
    timeout = aiohttp.ClientTimeout(total=15)
    async with session.post(
        f"{homeserver}/_matrix/client/v3/login",
        json={"type": "m.login.password", "user": user_id, "password": password},
        timeout=timeout,
    ) as r:
        data = await r.json()
        if "access_token" in data:
            return data["access_token"]
        raise ValueError(data.get("error", "Login failed"))


async def _create_weat_room(session: aiohttp.ClientSession, homeserver: str, token: str) -> str:
    timeout = aiohttp.ClientTimeout(total=15)
    async with session.post(
        f"{homeserver}/_matrix/client/v3/createRoom",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "WeAt",
            "topic": "AI 副驾驶指令室 — 在这里发命令，草稿回复也在这里",
            "preset": "private_chat",
            "invite": [],
        },
        timeout=timeout,
    ) as r:
        data = await r.json()
        room_id = data.get("room_id", "")
        if not room_id:
            raise RuntimeError(f"服务器返回错误：{data}")
        return room_id


def _write_opencode_auth(provider_key: str, api_key: str) -> None:
    path = _opencode_auth_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except Exception:
            pass
    existing[provider_key] = {"type": "api", "key": api_key}
    path.write_text(json.dumps(existing, indent=2))


async def run_wizard(config_path: Path) -> None:
    print()
    print("WeAt 配置向导")
    print("══════════════════════════════════════")
    print()

    # ── Step 1: Matrix login ──────────────────────────────────────────────────
    homeserver = _prompt("Matrix 服务器", default="https://matrix.org").rstrip("/")

    username = _prompt("用户名（如 alice，不用加 @）")
    server_name = homeserver.split("://")[-1]
    user_id = f"@{username}:{server_name}"

    print()
    print("  登录方式：")
    print("    1. 密码登录")
    print("    2. 粘贴 Access Token（用 Google/Apple 等 SSO 登录时选此项）")
    print("       取 Token：Element → Settings → Help & About → 最底部 Access Token")
    login_choice = _prompt("选择", default="1")

    async with aiohttp.ClientSession() as http:
        if login_choice == "2":
            print("  在 Element 里取 Token：Settings → Help & About → 滚到底部 → Access Token")
            token = _prompt("Access Token（明文显示，方便确认）")
            if not token:
                print("  ❌ Token 不能为空。")
                sys.exit(1)
            print(f"  ✅ 使用已提供的 Token")
        else:
            password = _prompt("密码", secret=True)
            print(f"  正在登录 {user_id}...", end="", flush=True)
            try:
                token = await _login(http, homeserver, user_id, password)
            except ValueError as e:
                print(f"\n  ❌ 登录失败：{e}")
                print(f"  如果你用 Google/Apple 登录，请选登录方式 2（粘贴 Token）。")
                sys.exit(1)
            print(" ✅")

        # ── Step 2: Vault path ────────────────────────────────────────────────
        print()
        default_vault = str(Path.home() / "Documents" / "Notes")
        vault_path = _prompt("Obsidian Vault 路径", default=default_vault)
        vault = Path(vault_path)
        if not vault.exists():
            ans = _prompt(f"  路径不存在，是否自动创建？", default="y")
            if ans.lower().startswith("y"):
                vault.mkdir(parents=True, exist_ok=True)
                print(f"  已创建 {vault_path}")
            else:
                print("  请先创建 vault 目录后重新运行向导。")
                sys.exit(1)

        # ── Step 3: LLM API key ───────────────────────────────────────────────
        print()
        print("  选择 AI 提供商：")
        for k, (_, label, _) in PROVIDERS.items():
            print(f"    {k}. {label}")
        choice = _prompt("选择", default="1")
        provider_key, _, default_model = PROVIDERS.get(choice, PROVIDERS["1"])

        api_key = _prompt(f"  API Key", secret=True)
        if not api_key:
            print("  ❌ API Key 不能为空。")
            sys.exit(1)
        _write_opencode_auth(provider_key, api_key)
        print(f"  ✅ opencode 配置完成（{_opencode_auth_path()}）")

        # ── Step 4: WeAt room ─────────────────────────────────────────────────
        print()
        print("  WeAt 指令室 Room ID（在 Element 里创建一个私密房间，然后粘贴 Room ID）：")
        print("    Element → 左侧「+」→「New room」→ 创建后进房间")
        print("    → ⚙️ Room settings → Room addresses → 底部 Internal room ID")
        print("  留空则自动创建（需要网络能访问服务器）")
        weat_room_id = _prompt("Room ID（以 ! 开头，或回车自动创建）")

        if weat_room_id and not weat_room_id.startswith("!"):
            print("  ❌ Room ID 应以 ! 开头，请检查后重试。")
            sys.exit(1)

        if not weat_room_id:
            print("  正在自动创建 WeAt 指令室...", end="", flush=True)
            try:
                weat_room_id = await _create_weat_room(http, homeserver, token)
                print(f" ✅ ({weat_room_id})")
            except Exception as e:
                print(f"\n  ❌ 自动创建失败（{e}）")
                print("  请在 Element 手动创建后重新运行向导，粘贴 Room ID。")
                sys.exit(1)
        else:
            print(f"  ✅ 使用已有房间 {weat_room_id}")

    # ── Step 5: Write config ──────────────────────────────────────────────────
    config = Config(
        homeserver=homeserver,
        user_id=user_id,
        access_token=token,
        weat_room_id=weat_room_id,
        vault_path=vault_path,
        opencode_model=default_model,
    )
    config.save(config_path)

    print()
    print("══════════════════════════════════════")
    print(f"✅ 配置写入 {config_path}")
    print()
    print("下一步：")
    print(f"  1. 打开 Element，登录 {user_id}")
    print(f"  2. 找到「WeAt」房间（房间 ID：{weat_room_id}）")
    print(f"  3. 发送 /help 开始使用")
    print()


def main() -> None:
    config_path = Path("weat.json")
    if config_path.exists():
        print(f"配置文件已存在：{config_path}")
        print("如需重新配置，请先删除：rm weat.json")
        sys.exit(0)
    asyncio.run(run_wizard(config_path))
    print("启动 bridge：uv run weat-bridge")
    print()
