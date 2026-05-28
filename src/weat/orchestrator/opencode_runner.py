"""
opencode subprocess runner — wraps `opencode run --format json` for the orchestrator.

Key design decisions:
- Each run returns (text, session_id) where session_id is used for multi-turn continuation.
- MCP server config and AGENTS.md are written to ~/.local/share/weat/agent/ — a dedicated
  working directory that is isolated from the user's vault. The vault's own AGENTS.md
  (e.g. obsidian-second-brain) would otherwise confuse the model.
- Agent prompts include the vault path explicitly so Read/Grep can access notes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shlex
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

UV_BIN = shutil.which("uv") or "uv"
OPENCODE_BIN = shutil.which("opencode") or "opencode"
WEAT_PACKAGE_DIR = Path(__file__).parent.parent

AGENT_DIR = Path.home() / ".local" / "share" / "weat" / "agent"
MCP_DIR = Path.home() / ".local" / "share" / "weat" / "mcp"

AGENTS_MD = """\
# WeAt Agent

You are a personal AI copilot for Matrix messaging. Your job:
1. Read Matrix room history with the `weat-matrix` MCP tools (list_rooms, get_recent_messages, search_messages).
2. Read the user's Obsidian vault with your built-in Read / Grep / Glob tools.
3. Draft replies or meeting notes based on what you find.
4. NEVER send Matrix messages directly — only draft text for human review.

Always respond in the same language the user used in their instruction.
"""


class OpenCodeRunner:
    def __init__(
        self,
        vault_path: str,
        model: str = "",
        provider: dict | None = None,
        extra_args: list[str] | None = None,
    ) -> None:
        self.vault_path = Path(vault_path)
        self.model = model
        self.provider = provider or {}
        self.extra_args = extra_args or []

    def write_opencode_config(
        self,
        homeserver: str,
        user_id: str,
        access_token: str,
    ) -> None:
        """Write opencode.jsonc + AGENTS.md into the WeAt agent directory."""
        mcp_server_path = str(WEAT_PACKAGE_DIR / "matrix_mcp" / "server.py")
        project_root = str(WEAT_PACKAGE_DIR.parent.parent)

        AGENT_DIR.mkdir(parents=True, exist_ok=True)
        MCP_DIR.mkdir(parents=True, exist_ok=True)
        MCP_DIR.chmod(0o700)

        # Wrapper lives outside AGENT_DIR so the agent's Read tool cannot discover
        # the plaintext access_token from its working directory.
        wrapper_path = MCP_DIR / "weat_matrix_mcp.sh"
        wrapper_path.write_text(
            "#!/bin/sh\n"
            f"export WEAT_MATRIX_HOMESERVER={shlex.quote(homeserver)}\n"
            f"export WEAT_MATRIX_USER_ID={shlex.quote(user_id)}\n"
            f"export WEAT_MATRIX_ACCESS_TOKEN={shlex.quote(access_token)}\n"
            f"exec {shlex.quote(UV_BIN)} run --project {shlex.quote(project_root)} python {shlex.quote(mcp_server_path)}\n"
        )
        wrapper_path.chmod(0o700)

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
        if self.provider:
            provider_id = self.provider.get("id")
            if not provider_id:
                raise ValueError("opencode_provider missing 'id' field")
            block = {k: v for k, v in self.provider.items() if k != "id"}
            config["provider"] = {provider_id: block}
        if self.model:
            config["model"] = self.model

        config_path = AGENT_DIR / "opencode.jsonc"
        config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))
        # API key lives in this file → tighten perms.
        config_path.chmod(0o600)
        (AGENT_DIR / "AGENTS.md").write_text(AGENTS_MD)

    async def run(
        self,
        prompt: str,
        session_id: str | None = None,
    ) -> tuple[str, str]:
        """
        Run opencode with `prompt`, optionally continuing a prior session.
        Returns (answer_text, session_id).
        """
        full_prompt = f"[Vault path: {self.vault_path}]\n\n{prompt}"

        cmd = [
            OPENCODE_BIN, "run",
            "--format", "json",
            "--dangerously-skip-permissions",
            "--dir", str(AGENT_DIR),
        ]
        if self.model:
            cmd += ["--model", self.model]
        if session_id:
            cmd += ["--session", session_id]
        cmd += self.extra_args
        cmd.append(full_prompt)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.info("opencode started (pid=%d, model=%s)", proc.pid, self.model or "default")
        stdout, stderr = await proc.communicate()
        logger.info("opencode finished (pid=%d, exit=%d)", proc.pid, proc.returncode)

        raw = stdout.decode("utf-8", errors="replace")
        err = stderr.decode("utf-8", errors="replace").strip()

        if err:
            for line in err.splitlines():
                logger.warning("opencode stderr: %s", line)
        if proc.returncode != 0:
            logger.warning("opencode exited %d", proc.returncode)
        if not raw.strip():
            logger.warning("opencode returned empty stdout (exit=%d)", proc.returncode)
        else:
            import tempfile, os
            dump = tempfile.NamedTemporaryFile(
                mode="w", suffix=".ndjson", prefix="opencode_", delete=False
            )
            dump.write(raw)
            dump.close()
            logger.debug("opencode stdout (%d bytes) → %s", len(raw), dump.name)
            types_seen: set[str] = set()
            for line in raw.splitlines():
                try:
                    ev = json.loads(line.strip())
                    if "type" in ev:
                        types_seen.add(ev["type"])
                except json.JSONDecodeError:
                    pass
            logger.debug("opencode event types: %s", sorted(types_seen))

        return self._parse_output(raw)

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
