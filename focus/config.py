from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GeneralConfig:
    mode: str = "blacklist"
    strict: bool = False
    confirmation_phrase: str = "I am choosing to stop studying"
    autostart: bool = False


@dataclass
class PomodoroConfig:
    work_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 20
    long_break_after: int = 4


@dataclass
class DailyConfig:
    enabled: bool = False
    goal_hours: float = 4


@dataclass
class BlockingConfig:
    domains: list[str] = field(default_factory=lambda: [
        "youtube.com", "www.youtube.com",
        "tiktok.com", "www.tiktok.com",
        "instagram.com", "www.instagram.com",
        "reddit.com", "www.reddit.com", "old.reddit.com",
        "twitter.com", "www.twitter.com", "x.com", "www.x.com",
        "netflix.com", "www.netflix.com",
        "twitch.tv", "www.twitch.tv",
        "disneyplus.com", "www.disneyplus.com",
        "steam.com", "store.steampowered.com",
        "discord.com", "discord.gg",
    ])
    apps: list[str] = field(default_factory=lambda: [
        "steam", "steamwebhelper",
        "discord",
    ])
    allowed_apps: list[str] = field(default_factory=list)


@dataclass
class DisplayConfig:
    dim_brightness: bool = True
    brightness_percent: int = 30
    dark_mode: bool = True


@dataclass
class Config:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    pomodoro: PomodoroConfig = field(default_factory=PomodoroConfig)
    daily: DailyConfig = field(default_factory=DailyConfig)
    blocking: BlockingConfig = field(default_factory=BlockingConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)


def get_config_path() -> Path:
    return Path.home() / ".config" / "focus" / "config.toml"


def get_config_dir() -> Path:
    return Path.home() / ".config" / "focus"


def _config_to_dict(config: Config) -> dict[str, dict[str, object]]:
    return {
        "general": {
            "mode": config.general.mode,
            "strict": config.general.strict,
            "confirmation_phrase": config.general.confirmation_phrase,
            "autostart": config.general.autostart,
        },
        "pomodoro": {
            "work_minutes": config.pomodoro.work_minutes,
            "short_break_minutes": config.pomodoro.short_break_minutes,
            "long_break_minutes": config.pomodoro.long_break_minutes,
            "long_break_after": config.pomodoro.long_break_after,
        },
        "daily": {
            "enabled": config.daily.enabled,
            "goal_hours": config.daily.goal_hours,
        },
        "blocking": {
            "domains": config.blocking.domains,
            "apps": config.blocking.apps,
            "allowed_apps": config.blocking.allowed_apps,
        },
        "display": {
            "dim_brightness": config.display.dim_brightness,
            "brightness_percent": config.display.brightness_percent,
            "dark_mode": config.display.dark_mode,
        },
    }


def _write_config_file(config: Config) -> None:
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = _config_to_dict(config)
    lines: list[str] = []

    for section, values in data.items():
        lines.append(f"[{section}]")
        for key, value in values.items():
            if isinstance(value, bool):
                lines.append(f"{key} = {str(value).lower()}")
            elif isinstance(value, str):
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key} = "{escaped}"')
            elif isinstance(value, list):
                lines.append(f"{key} = [")
                for item in value:
                    escaped = item.replace("\\", "\\\\").replace('"', '\\"')
                    lines.append(f'    "{escaped}",')
                lines.append("]")
            else:
                lines.append(f"{key} = {value}")
        lines.append("")

    config_path.write_text("\n".join(lines), encoding="utf-8")


def _parse_config(data: dict[str, dict[str, object]]) -> Config:
    general = data.get("general", {})
    pomodoro = data.get("pomodoro", {})
    daily = data.get("daily", {})
    blocking = data.get("blocking", {})
    display = data.get("display", {})

    return Config(
        general=GeneralConfig(
            mode=str(general.get("mode", "blacklist")),
            strict=bool(general.get("strict", False)),
            confirmation_phrase=str(general.get("confirmation_phrase", "I am choosing to stop studying")),
            autostart=bool(general.get("autostart", False)),
        ),
        pomodoro=PomodoroConfig(
            work_minutes=int(pomodoro.get("work_minutes", 25)),
            short_break_minutes=int(pomodoro.get("short_break_minutes", 5)),
            long_break_minutes=int(pomodoro.get("long_break_minutes", 20)),
            long_break_after=int(pomodoro.get("long_break_after", 4)),
        ),
        daily=DailyConfig(
            enabled=bool(daily.get("enabled", False)),
            goal_hours=float(daily.get("goal_hours", 4)),
        ),
        blocking=BlockingConfig(
            domains=[str(d) for d in blocking.get("domains", BlockingConfig().domains)],
            apps=[str(a) for a in blocking.get("apps", BlockingConfig().apps)],
            allowed_apps=[str(a) for a in blocking.get("allowed_apps", BlockingConfig().allowed_apps)],
        ),
        display=DisplayConfig(
            dim_brightness=bool(display.get("dim_brightness", True)),
            brightness_percent=int(display.get("brightness_percent", 30)),
            dark_mode=bool(display.get("dark_mode", True)),
        ),
    )


def create_default_config() -> Config:
    config = Config()
    _write_config_file(config)
    return config


def save_config(config: Config) -> None:
    _write_config_file(config)


def reset_config() -> Config:
    return create_default_config()


def load_config() -> Config:
    config_path = get_config_path()

    if not config_path.exists():
        return create_default_config()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    return _parse_config(data)
