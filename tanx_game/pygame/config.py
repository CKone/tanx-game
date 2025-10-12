"""Persistent configuration helpers for the pygame client."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

_SETTINGS_PATH = Path(__file__).resolve().parent / "user_settings.json"


def load_user_settings() -> Dict[str, Any]:
    """Load persisted user settings from disk."""
    try:
        with _SETTINGS_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}
    except OSError:
        return {}
    return {}


def save_user_settings(settings: Dict[str, Any]) -> None:
    """Persist user settings to disk, ignoring filesystem errors."""
    try:
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _SETTINGS_PATH.open("w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2, sort_keys=True)
    except OSError:
        # Persistence errors are non-fatal for gameplay; ignore quietly.
        pass


__all__ = ["load_user_settings", "save_user_settings"]
