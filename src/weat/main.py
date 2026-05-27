"""
WeAt bridge entry point.

Usage:
  weat-bridge                   # auto-runs setup wizard on first launch
  weat-bridge --config path     # custom config path
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path

from .config.settings import Config
from .orchestrator.orchestrator import Orchestrator
from .vault.setup import setup_vault

logger = logging.getLogger(__name__)


def _load_config(config_path: str | None) -> Config:
    path = Path(config_path) if config_path else Path("weat.json")

    if path.exists():
        cfg = Config.from_file(path)
    else:
        cfg = Config.from_env()

    errors = cfg.validate()
    if errors:
        for e in errors:
            print(f"  • {e}", file=sys.stderr)
        sys.exit(1)

    return cfg


async def _run(config: Config) -> None:
    vault = Path(config.vault_path)
    if not (vault / "AGENTS.md").exists():
        logger.info("Installing obsidian-second-brain opencode adapter into vault ...")
        ok = setup_vault(config.vault_path, osb_path=config.osb_dist_path or None)
        if not ok:
            logger.warning("Vault setup failed — vault commands will be unavailable")

    orchestrator = Orchestrator(config)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(orchestrator.stop()))

    logger.info("WeAt bridge starting (user=%s, room=%s)", config.user_id, config.weat_room_id)
    try:
        await orchestrator.start()
    finally:
        await orchestrator.stop()


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="WeAt bridge")
    parser.add_argument("--config", default=None)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    config_path = Path(args.config) if args.config else Path("weat.json")

    # First-run: launch wizard automatically if no config and no env vars
    if not config_path.exists() and Config.from_env().validate():
        from .config.wizard import run_wizard
        print("未找到配置文件，启动初次配置向导…")
        asyncio.run(run_wizard(config_path))

    config = _load_config(args.config)
    asyncio.run(_run(config))


if __name__ == "__main__":
    main()
