"""
WeAt bridge entry point.

Usage:
  weat-bridge                         # load config from weat.json
  weat-bridge --config /path/to.json  # custom config path
  WEAT_* environment variables        # override any config field

First-run: `weat-setup` to generate weat.json, then `weat-bridge` to start.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from .config.settings import Config
from .orchestrator.orchestrator import Orchestrator
from .vault.setup import setup_vault

logger = logging.getLogger(__name__)


def _load_config(config_path: str | None = None) -> Config:
    if config_path and Path(config_path).exists():
        return Config.from_file(config_path)

    default_path = Path("weat.json")
    if default_path.exists():
        cfg = Config.from_file(default_path)
    else:
        cfg = Config.from_env()

    errors = cfg.validate()
    if errors:
        print("Config errors:", file=sys.stderr)
        for e in errors:
            print(f"  • {e}", file=sys.stderr)
        print("\nRun `weat-setup` to configure, or set WEAT_* environment variables.", file=sys.stderr)
        sys.exit(1)

    return cfg


async def _run(config: Config) -> None:
    # Install obsidian-second-brain adapter if AGENTS.md is missing
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

    logger.info("WeAt bridge starting (bot=%s, user=%s)", config.bot_user_id, config.user_id)
    try:
        await orchestrator.start()
    finally:
        await orchestrator.stop()


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="WeAt bridge")
    parser.add_argument("--config", default=None, help="Path to weat.json config file")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    config = _load_config(args.config)
    asyncio.run(_run(config))


if __name__ == "__main__":
    main()
