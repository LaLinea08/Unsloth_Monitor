"""Only non-secret preferences are persisted; bearer tokens are session-only."""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path

from unsloth_monitor.integration.client import validate_base_url


@dataclass(frozen=True)
class Settings:
    base_url: str = "http://127.0.0.1:8888/v1"
    interval: int = 5


def load_settings(path: Path) -> Settings:
    try:
        if path.stat().st_size > 8192:
            return Settings()
        data = json.loads(path.read_text(encoding="utf-8"))
        url = data.get("base_url", Settings().base_url)
        validate_base_url(url)
        interval = data.get("interval", 5)
        if type(interval) is not int or interval not in (2, 5, 10, 15):
            interval = 5
        return Settings(url, interval)
    except (OSError, ValueError, TypeError, AttributeError):
        return Settings()


def save_settings(path: Path, settings: Settings):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
