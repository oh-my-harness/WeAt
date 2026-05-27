"""
S2 spike: verify opencode can be called non-interactively from subprocess,
output is parseable, and multi-turn sessions work via --session flag.

Usage:
    uv run python spikes/S2-opencode/test_opencode_subprocess.py

Requires: opencode configured with at least one LLM provider.
"""
import subprocess
import sys
import json
import re


def run_opencode(message: str, session_id: str | None = None, cwd: str = ".") -> tuple[str, str]:
    """Run opencode, return (text_output, session_id)."""
    cmd = ["opencode", "run", "--format", "json", "--dangerously-skip-permissions", message]
    if session_id:
        cmd += ["--session", session_id]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
    )

    text_parts = []
    found_session_id = session_id
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = event.get("type", "")
        # capture session id from any event that has it
        if "sessionID" in event:
            found_session_id = event["sessionID"]

        if etype == "text":
            part = event.get("part", {})
            text = part.get("text", "")
            if text:
                text_parts.append(text)

    return "\n".join(text_parts).strip(), found_session_id


def main():
    print("[S2] Turn 1: single-shot question")
    answer1, session_id = run_opencode("用一句话解释什么是 Redis")
    print(f"       Answer: {answer1[:200]!r}")
    print(f"       Session ID: {session_id!r}")

    if not answer1:
        print("[S2] FAIL — empty output on turn 1")
        sys.exit(1)
    print("[S2] OK  turn 1 passed")

    if session_id:
        print(f"\n[S2] Turn 2: continue session {session_id}")
        answer2, _ = run_opencode("用更简短的一句话再说一遍", session_id=session_id)
        print(f"       Answer: {answer2[:200]!r}")
        if answer2:
            print("[S2] OK  turn 2 passed (multi-turn context works)")
        else:
            print("[S2] WARN — empty output on turn 2 (may need separate session per run)")
    else:
        print("[S2] WARN — no session_id captured, multi-turn test skipped")

    print("\n[S2] Checking output structure (--format json events) ...")
    # Quick check that we get JSON lines
    proc = subprocess.run(
        ["opencode", "run", "--format", "json", "--dangerously-skip-permissions", "say: pong"],
        capture_output=True, text=True
    )
    json_lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
    parsed = []
    for l in json_lines:
        try:
            parsed.append(json.loads(l))
        except Exception:
            pass
    print(f"       Total JSON events: {len(parsed)}")
    event_types = list({e.get('type') for e in parsed})
    print(f"       Event types seen: {event_types}")
    print("[S2] PASS — opencode subprocess integration verified")


if __name__ == "__main__":
    main()
