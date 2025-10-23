"""Configuration path utilities for withings2weeks.

Centralizes logic for locating and loading application config (``app_config.toml``)
and persisted OAuth token file (``.withings_tokens.json``).

Default location follows the XDG base directory spec using
``$XDG_CONFIG_HOME/withings2weeks`` or ``~/.config/withings2weeks`` when the
environment variable is not set.

Environment overrides:
    * ``WITHINGS2WEEKS_CONFIG_DIR``: override the config directory root (useful for tests)

Backward compatibility / migration:
If legacy files exist in the current working directory and the new config
directory does not yet contain them, they are copied over on first access.
This is intentionally minimal and silent (prints only when a migration occurs).
"""

import os
import shutil
import tomllib  # Python 3.11+ (assumed >=3.11 per project requirements)
from collections.abc import Mapping
from pathlib import Path
from typing import Any

__all__ = [
    "get_config_dir",
    "ensure_config_dir",
    "get_app_config_path",
    "get_token_path",
    "load_app_config",
]


def get_config_dir() -> Path:
    override = os.environ.get("WITHINGS2WEEKS_CONFIG_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "withings2weeks"


def ensure_config_dir() -> Path:
    cfg = get_config_dir()
    cfg.mkdir(parents=True, exist_ok=True)
    return cfg


def _migrate_legacy_file(target: Path, legacy_name: str) -> None:
    if target.exists():  # Already present; nothing to do
        return
    legacy = Path(legacy_name)
    if legacy.exists() and legacy.is_file():
        try:
            shutil.copy2(legacy, target)
            print(f"Migrated legacy '{legacy_name}' to new config dir: {target}")
        except Exception:  # pragma: no cover - non-critical
            pass


def get_app_config_path() -> Path:
    ensure_config_dir()
    path = get_config_dir() / "app_config.toml"
    _migrate_legacy_file(path, "app_config.toml")
    return path


def get_token_path() -> Path:
    ensure_config_dir()
    path = get_config_dir() / ".withings_tokens.json"
    _migrate_legacy_file(path, ".withings_tokens.json")
    return path


def load_app_config(path: Path | None = None) -> Mapping[str, Any]:
    if path is None:
        path = get_app_config_path()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    return tomllib.loads(path.read_text())
