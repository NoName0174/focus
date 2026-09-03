from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

QUEUE_FILE = Path.home() / ".config" / "focus" / "queue.json"


@dataclass
class QueueItem:
    name: str
    duration_minutes: int
    is_break: bool = False


def parse_duration(duration_str: str) -> int:
    duration_str = duration_str.strip().lower()
    if not duration_str:
        raise ValueError("Duration string is empty")

    match = re.fullmatch(r"(\d+(?:\.\d+)?)h(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?", duration_str)
    if match:
        hours = float(match.group(1))
        minutes = float(match.group(2) or 0)
        seconds = float(match.group(3) or 0)
        total = int(hours * 3600 + minutes * 60 + seconds)
        if total <= 0:
            raise ValueError(f"Duration must be positive, got '{duration_str}'")
        return max(total // 60, 1)

    match = re.fullmatch(r"(\d+(?:\.\d+)?)m(?:(\d+(?:\.\d+)?)s)?", duration_str)
    if match:
        minutes = float(match.group(1))
        seconds = float(match.group(2) or 0)
        total_sec = int(minutes * 60 + seconds)
        if total_sec <= 0:
            raise ValueError(f"Duration must be positive, got '{duration_str}'")
        return max(total_sec // 60, 1)

    match = re.fullmatch(r"(\d+(?:\.\d+)?)s", duration_str)
    if match:
        total_sec = int(float(match.group(1)))
        if total_sec <= 0:
            raise ValueError(f"Duration must be positive, got '{duration_str}'")
        return max(total_sec // 60, 1)

    if re.fullmatch(r"\d+(?:\.\d+)?", duration_str):
        total = int(float(duration_str))
        if total <= 0:
            raise ValueError(f"Duration must be positive, got '{duration_str}'")
        return total

    raise ValueError(
        f"Invalid duration format: '{duration_str}'. "
        "Use formats like '90s', '25m', '2h', '1h30m', or a plain number for minutes."
    )


def format_duration(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    remaining = minutes % 60
    if remaining == 0:
        return f"{hours}h"
    return f"{hours}h {remaining}m"


def _save_queue(items: list[QueueItem]) -> None:
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"items": [asdict(item) for item in items]}
    QUEUE_FILE.write_text(json.dumps(data, indent=2) + "\n")


def _load_queue() -> list[QueueItem]:
    if not QUEUE_FILE.exists():
        return []
    data = json.loads(QUEUE_FILE.read_text())
    return [
        QueueItem(
            name=item["name"],
            duration_minutes=item["duration_minutes"],
            is_break=item.get("is_break", False),
        )
        for item in data.get("items", [])
    ]


def add_to_queue(name: str, duration_str: str, is_break: bool = False) -> QueueItem:
    duration = parse_duration(duration_str)
    item = QueueItem(name=name, duration_minutes=duration, is_break=is_break)
    items = _load_queue()
    items.append(item)
    _save_queue(items)
    return item


def get_queue() -> list[QueueItem]:
    return _load_queue()


def clear_queue() -> None:
    _save_queue([])


def remove_first() -> QueueItem | None:
    items = _load_queue()
    if not items:
        return None
    first = items.pop(0)
    _save_queue(items)
    return first


def peek_next() -> QueueItem | None:
    items = _load_queue()
    return items[0] if items else None


def queue_length() -> int:
    return len(_load_queue())


def is_empty() -> bool:
    return len(_load_queue()) == 0
