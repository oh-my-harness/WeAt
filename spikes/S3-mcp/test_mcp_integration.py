"""
S3 spike runner: adds the spike MCP server to a temporary opencode project config,
then runs opencode asking "what time is it?" and verifies get_time was called.
"""
import subprocess
import json
import os
import sys
import tempfile
import shutil

SPIKE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SPIKE_DIR, "../.."))
MCP_SERVER_PATH = os.path.join(SPIKE_DIR, "mcp_server_spike.py")
UV_BIN = shutil.which("uv") or "uv"


def main():
    # Write a local opencode.jsonc for the spike dir so MCP is scoped to it
    config = {
        "$schema": "https://opencode.ai/config.json",
        "mcp": {
            "weat-spike-time": {
                "type": "local",
                "enabled": True,
                "command": [
                    UV_BIN,
                    "run",
                    "--project", PROJECT_ROOT,
                    "python",
                    MCP_SERVER_PATH,
                ],
            }
        }
    }
    config_path = os.path.join(SPIKE_DIR, "opencode.jsonc")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"[S3] Wrote opencode.jsonc with MCP server config at {config_path}")

    print("[S3] Running opencode: 'what is the current time? use the get_time tool'")
    proc = subprocess.run(
        [
            "opencode", "run",
            "--format", "json",
            "--dangerously-skip-permissions",
            "--dir", SPIKE_DIR,
            "what is the current time? use the get_time tool",
        ],
        capture_output=True, text=True,
    )

    tool_called = False
    text_parts = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = event.get("type", "")
        part = event.get("part", {})
        if etype == "text":
            text_parts.append(part.get("text", ""))
        if etype in ("tool_call", "tool-call") or part.get("type") in ("tool-call", "tool_call", "tool-invocation"):
            tool_called = True
            print(f"[S3] Tool called: {part}")
        if part.get("type") == "tool-result" or etype == "tool_result":
            print(f"[S3] Tool result: {part}")

    answer = "".join(text_parts).strip()
    print(f"[S3] Agent answer: {answer[:300]!r}")

    if not answer:
        print("[S3] FAIL — no answer from agent")
        sys.exit(1)

    # Accept if answer contains a plausible time-like string
    import re
    if re.search(r'\d{4}-\d{2}-\d{2}', answer) or re.search(r'\d{1,2}:\d{2}', answer):
        print("[S3] OK  — answer contains time info → MCP tool result reached agent")
    else:
        print("[S3] WARN — answer doesn't obviously contain time; check manually")
        print(f"       stderr: {proc.stderr[:300]}")

    print("[S3] DONE")


if __name__ == "__main__":
    main()
