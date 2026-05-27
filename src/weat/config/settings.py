"""
Configuration dataclass loaded from environment variables or config file.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    # Matrix credentials
    homeserver: str = ""
    user_id: str = ""
    access_token: str = ""
    bot_user_id: str = ""          # @BotName:server  (the bot account)
    bot_access_token: str = ""     # bot's token for listening to private DMs

    # Paths
    vault_path: str = ""           # absolute path to user's markdown vault
    db_path: str = "weat.db"       # SQLite database path
    osb_dist_path: str = ""        # path to obsidian-second-brain dist/opencode/

    # opencode settings
    opencode_model: str = ""       # e.g. "anthropic/claude-sonnet-4-5"
    opencode_extra_args: list[str] = field(default_factory=list)

    # Session settings
    session_timeout_minutes: int = 30

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            homeserver=os.environ.get("WEAT_MATRIX_HOMESERVER", ""),
            user_id=os.environ.get("WEAT_MATRIX_USER_ID", ""),
            access_token=os.environ.get("WEAT_MATRIX_ACCESS_TOKEN", ""),
            bot_user_id=os.environ.get("WEAT_BOT_USER_ID", ""),
            bot_access_token=os.environ.get("WEAT_BOT_ACCESS_TOKEN", ""),
            vault_path=os.environ.get("WEAT_VAULT_PATH", ""),
            db_path=os.environ.get("WEAT_DB_PATH", "weat.db"),
            osb_dist_path=os.environ.get("WEAT_OSB_DIST_PATH", ""),
            opencode_model=os.environ.get("WEAT_OPENCODE_MODEL", ""),
            session_timeout_minutes=int(os.environ.get("WEAT_SESSION_TIMEOUT_MINUTES", "30")),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "Config":
        data = json.loads(Path(path).read_text())
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(
                {k: v for k, v in self.__dict__.items()},
                indent=2,
                ensure_ascii=False,
            )
        )

    def validate(self) -> list[str]:
        errors = []
        if not self.homeserver:
            errors.append("homeserver is required")
        if not self.user_id:
            errors.append("user_id is required")
        if not self.access_token:
            errors.append("access_token is required")
        if not self.bot_user_id:
            errors.append("bot_user_id is required")
        if not self.bot_access_token:
            errors.append("bot_access_token is required")
        if not self.vault_path:
            errors.append("vault_path is required")
        return errors
