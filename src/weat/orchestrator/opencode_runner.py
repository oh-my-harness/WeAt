"""
opencode subprocess runner — wraps `opencode run --format json` for the orchestrator.

Key design decisions:
- Each run returns (text, session_id) where session_id is used for multi-turn continuation.
- MCP server config is written as opencode.jsonc into the vault directory so opencode
  auto-loads it on startup.
- Agent runs with CWD = vault_path so AGENTS.md is auto-picked up.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path


UV_BIN = shutil.which("uv") or "uv"
OPENCODE_BIN = shutil.which("opencode") or "opencode"
WEAT_PACKAGE_DIR = Path(__file__).parent.parent


class OpenCodeRunner:
    def __init__(
        self,
        vault_path: str,
        model: str = "",
        extra_args: list[str] | None = None,
    ) -> None:
        self.vault_path = Path(vault_path)
        self.model = model
        self.extra_args = extra_args or []

    def write_opencode_config(
        self,
        homeserver: str,
        user_id: str,
        access_token: str,
    ) -> None:
        """Write opencode.jsonc with the Matrix MCP server configured."""
        mcp_server_path = str(WEAT_PACKAGE_DIR / "matrix_mcp" / "server.py")
        project_root = str(WEAT_PACKAGE_DIR.parent.parent)  # WeAt project root

        # opencode does not pass `env` fields to local MCP servers (≤1.15.x),
        # so write a wrapper shell script that sets env vars before launching.
        wrapper_path = self.vault_path / ".opencode" / "weat_matrix_mcp.sh"
        wrapper_path.parent.mkdir(parents=True, exist_ok=True)
        wrapper_path.write_text(
            "#!/bin/sh\n"
            f"export WEAT_MATRIX_HOMESERVER={homeserver!r}\n"
            f"export WEAT_MATRIX_USER_ID={user_id!r}\n"
            f"export WEAT_MATRIX_ACCESS_TOKEN={access_token!r}\n"
            f"exec {UV_BIN} run --project {project_root!r} python {mcp_server_path!r}\n"
        )
        wrapper_path.chmod(0o755)

        config: dict = {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {
                "weat-matrix": {
                    "type": "local",
                    "enabled": True,
                    "command": [str(wrapper_path)],
                }
            },
        }
        if self.model:
            config["model"] = self.model

        config_path = self.vault_path / "opencode.jsonc"
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    async def run(
        self,
        prompt: str,
        session_id: str | None = None,
    ) -> tuple[str, str]:
        """
        Run opencode with `prompt`, optionally continuing a prior session.
        Returns (answer_text, session_id).
        """
        cmd = [
            OPENCODE_BIN, "run",
            "--format", "json",
            "--dangerously-skip-permissions",
            "--dir", str(self.vault_path),
        ]
        if self.model:
            cmd += ["--model", self.model]
        if session_id:
            cmd += ["--session", session_id]
        cmd += self.extra_args
        cmd.append(prompt)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        return self._parse_output(stdout.decode("utf-8", errors="replace"))

    @staticmethod
    def _parse_output(raw: str) -> tuple[str, str]:
        text_parts: list[str] = []
        session_id = ""

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not session_id and "sessionID" in event:
                session_id = event["sessionID"]

            if event.get("type") == "text":
                part = event.get("part", {})
                text = part.get("text", "")
                if text:
                    text_parts.append(text)

        return "".join(text_parts).strip(), session_id
