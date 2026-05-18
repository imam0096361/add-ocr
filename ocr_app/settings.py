from __future__ import annotations

import json
import os
from pathlib import Path

from .storage import DATA_DIR, ROOT


SETTINGS_PATH = DATA_DIR / "settings.json"
ENV_LOCAL_PATH = ROOT / ".env.local"
ENV_PATH = ROOT / ".env"


def get_api_key() -> str | None:
    env_key = os.getenv("GEMINI_API_KEY")
    if env_key:
        return env_key.strip()
    for _, values in read_env_files():
        file_key = values.get("GEMINI_API_KEY")
        if file_key:
            return file_key.strip()
    settings = read_settings()
    api_key = settings.get("gemini_api_key")
    return api_key.strip() if isinstance(api_key, str) and api_key.strip() else None


def api_key_source() -> str | None:
    if os.getenv("GEMINI_API_KEY"):
        return "environment"
    for path, values in read_env_files():
        if values.get("GEMINI_API_KEY"):
            return path.name
    if read_settings().get("gemini_api_key"):
        return "local settings"
    return None


def has_api_key() -> bool:
    return bool(get_api_key())


def read_settings() -> dict[str, str]:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def read_env_local() -> dict[str, str]:
    return read_env_file(ENV_LOCAL_PATH)


def read_env_files() -> list[tuple[Path, dict[str, str]]]:
    return [(path, read_env_file(path)) for path in (ENV_LOCAL_PATH, ENV_PATH)]


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def save_api_key(api_key: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps({"gemini_api_key": api_key.strip()}, indent=2), encoding="utf-8")


def clear_api_key() -> None:
    if SETTINGS_PATH.exists():
        SETTINGS_PATH.unlink()


def masked_api_key() -> str | None:
    api_key = get_api_key()
    if not api_key:
        return None
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}...{api_key[-4:]}"
