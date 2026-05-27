"""
obsidian-second-brain integration — installs the opencode adapter into the user's vault.

Called once during bridge startup (or re-run to upgrade).
Clones/uses a pinned obsidian-second-brain snapshot and copies the generated
AGENTS.md + .opencode/ into the vault root.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

OSB_REPO_URL = "https://github.com/eugeniughelbur/obsidian-second-brain.git"
OSB_LOCAL_PATH_ENV = "WEAT_OSB_PATH"   # set to skip clone (use local copy)
OSB_PINNED_TAG = "main"               # bump to a release tag once upstream stabilises


def setup_vault(vault_path: str | Path, osb_path: str | Path | None = None) -> bool:
    """
    Install obsidian-second-brain opencode adapter into the vault.

    Args:
        vault_path: User's markdown vault directory.
        osb_path:   Path to a pre-existing obsidian-second-brain repo.
                    If None, will use WEAT_OSB_PATH env var or fallback to the
                    bundled copy at /Users/hhl/Documents/projs/obsidian-second-brain.

    Returns:
        True on success.
    """
    vault = Path(vault_path)
    if not vault.is_dir():
        vault.mkdir(parents=True, exist_ok=True)
        logger.info("Created vault directory: %s", vault)

    osb = _locate_osb(osb_path)
    if osb is None:
        logger.error("Cannot locate obsidian-second-brain repo. Set WEAT_OSB_PATH.")
        return False

    dist = _build_dist(osb)
    if dist is None:
        return False

    _copy_to_vault(dist, vault)
    logger.info("obsidian-second-brain opencode adapter installed in %s", vault)
    return True


def _locate_osb(hint: str | Path | None) -> Path | None:
    if hint:
        p = Path(hint)
        if p.is_dir():
            return p

    env_path = os.environ.get(OSB_LOCAL_PATH_ENV)
    if env_path:
        p = Path(env_path)
        if p.is_dir():
            return p

    # Well-known location used during development
    dev_path = Path("/Users/hhl/Documents/projs/obsidian-second-brain")
    if dev_path.is_dir():
        return dev_path

    # Last resort: clone into a temp dir
    clone_target = Path.home() / ".cache" / "weat" / "obsidian-second-brain"
    if clone_target.is_dir():
        return clone_target
    try:
        logger.info("Cloning obsidian-second-brain to %s ...", clone_target)
        clone_target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", OSB_PINNED_TAG, OSB_REPO_URL, str(clone_target)],
            check=True, capture_output=True,
        )
        return clone_target
    except subprocess.CalledProcessError as e:
        logger.error("git clone failed: %s", e.stderr.decode())
        return None


def _build_dist(osb: Path) -> Path | None:
    build_sh = osb / "scripts" / "build.sh"
    if not build_sh.exists():
        logger.error("build.sh not found at %s", build_sh)
        return None

    dist = osb / "dist" / "opencode"
    try:
        subprocess.run(
            ["bash", str(build_sh), "--platform", "opencode"],
            cwd=str(osb),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error("build.sh failed: %s", e.stderr.decode())
        return None

    if not dist.is_dir():
        logger.error("Expected dist/opencode/ at %s but not found", dist)
        return None

    return dist


def _copy_to_vault(dist: Path, vault: Path) -> None:
    shutil.copytree(str(dist), str(vault), dirs_exist_ok=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    vault = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    ok = setup_vault(vault)
    sys.exit(0 if ok else 1)
