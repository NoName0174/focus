"""Discover installed applications and detect when the app list changes."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from .config import get_config_dir

SNAPSHOT_FILE = get_config_dir() / "app_snapshot.json"

DESKTOP_DIRS = [
    Path("/usr/share/applications"),
    Path("/usr/local/share/applications"),
    Path.home() / ".local" / "share" / "applications",
    Path("/var/lib/flatpak/exports/share/applications"),
    Path.home() / ".local" / "share" / "flatpak" / "exports" / "share" / "applications",
]

ESSENTIAL_APPS = {
    "gnome-terminal", "konsole", "xfce4-terminal", "tilix", "kitty",
    "alacritty", "wezterm", "foot", "xterm", "uxterm",
    "nautilus", "dolphin", "thunar", "nemo", "pcmanfm",
    "gnome-control-center", "systemsettings", "xfce4-settings",
    "org.gnome.Nautilus", "org.kde.dolphin", "org.wezfurlong.wezterm",
    "org.gnome.Terminal",
}


def _read_desktop_file(path: Path) -> dict[str, str | None]:
    """Extract Name, Exec, and NoDisplay from a .desktop file."""
    name: str | None = None
    exec_str: str | None = None
    no_display = False
    hidden = False
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("Name=") and name is None:
                    name = line[len("Name="):]
                elif line.startswith("Exec=") and exec_str is None:
                    exec_str = line[len("Exec="):]
                elif line == "NoDisplay=true":
                    no_display = True
                elif line == "Hidden=true":
                    hidden = True
    except OSError:
        return {}
    if no_display or hidden:
        return {}
    return {"name": name, "exec": exec_str}


def _desktop_exec_to_binary(exec_str: str | None) -> str | None:
    """Extract the actual executable name from an Exec= line."""
    if not exec_str:
        return None
    tokens = exec_str.strip().split()
    if not tokens:
        return None
    first = tokens[0]
    basename = Path(first).name
    cleaned = basename.removeprefix("env").removeprefix("flatpak")
    cleaned = re.sub(r"^%[a-zA-Z]", "", cleaned).strip()
    if not cleaned:
        return None
    return cleaned


def _scan_desktop_apps() -> dict[str, dict]:
    """Scan all .desktop files and return {binary_name: {name, sources}}."""
    apps: dict[str, dict] = {}
    seen_paths: set[str] = set()
    for d in DESKTOP_DIRS:
        if not d.is_dir():
            continue
        for path in d.glob("*.desktop"):
            key = str(path)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            info = _read_desktop_file(path)
            if not info or not info.get("exec"):
                continue
            binary = _desktop_exec_to_binary(info["exec"])
            if not binary:
                continue
            display_name = info.get("name") or binary
            if binary not in apps:
                apps[binary] = {"names": set(), "source": "desktop"}
            apps[binary]["names"].add(display_name)
    return apps


def _scan_flatpak_apps() -> dict[str, dict]:
    apps: dict[str, dict] = {}
    try:
        result = subprocess.run(
            ["flatpak", "list", "--app", "--columns=application"],
            capture_output=True, text=True, timeout=15,
        )
    except (subprocess.SubprocessError, OSError, FileNotFoundError):
        return apps
    if result.returncode != 0:
        return apps
    for line in result.stdout.splitlines():
        app_id = line.strip()
        if not app_id:
            continue
        apps[app_id] = {"names": {app_id.split(".")[-1]}, "source": "flatpak"}
    return apps


def _scan_package_apps() -> dict[str, dict]:
    """Scan installed packages (via pacman/dpkg/nix) but only keep those that
    map to a real executable in PATH (libraries/daemons are skipped)."""
    apps: dict[str, dict] = {}
    packages: set[str] = set()

    def _find_exec(exec_name: str) -> str | None:
        for d in os.environ.get("PATH", "").split(os.pathsep):
            if not d:
                continue
            candidate = Path(d) / exec_name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        return None

    for cmd in (["cat", "/etc/os-release"],):
        pass

    try:
        if os.path.exists("/usr/bin/pacman"):
            result = subprocess.run(
                ["pacman", "-Qq"], capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                packages.update(result.stdout.splitlines())
        elif os.path.exists("/usr/bin/dpkg-query"):
            result = subprocess.run(
                ["dpkg-query", "-f", "${binary:Package}\n", "-W"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                packages.update(result.stdout.splitlines())

        try:
            result = subprocess.run(
                ["nix", "profile", "list"], capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if "-> " in line:
                        name = line.split("-> ")[-1].strip().split("/")[-1]
                        name = name.split("-")[0] if name else ""
                        if name:
                            packages.add(name)
        except (subprocess.SubprocessError, OSError):
            pass
    except (subprocess.SubprocessError, OSError):
        pass

    for pkg in packages:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9+_.-]{0,63}", pkg):
            continue
        if _find_exec(pkg) is None:
            continue
        apps[pkg] = {"names": {pkg}, "source": "package"}
    return apps


def scan_installed_apps() -> dict[str, dict]:
    """Return all installed apps keyed by binary/ID, merged across sources."""
    apps: dict[str, dict] = {}
    for scanner in (_scan_desktop_apps, _scan_flatpak_apps, _scan_package_apps):
        for binary, info in scanner().items():
            if binary in apps:
                apps[binary]["names"].update(info["names"])
            else:
                apps[binary] = {
                    "names": set(info["names"]),
                    "source": info.get("source", "unknown"),
                }
    return apps


def _app_display_name(info: dict) -> str:
    names = info.get("names", set())
    if names:
        return next(iter(sorted(names)))
    return ""


def get_app_list() -> list[dict]:
    """Return a sorted list of {key, name, source} for display/picking."""
    apps = scan_installed_apps()
    result = []
    for binary, info in apps.items():
        result.append({
            "key": binary,
            "name": _app_display_name(info),
            "source": info.get("source", "unknown"),
            "essential": binary in ESSENTIAL_APPS,
        })
    result.sort(key=lambda a: (not a["essential"], a["name"].lower()))
    return result


def save_snapshot() -> None:
    apps = scan_installed_apps()
    data = {
        "apps": sorted(apps.keys()),
    }
    get_config_dir().mkdir(parents=True, exist_ok=True)
    SNAPSHOT_FILE.write_text(json.dumps(data, indent=2) + "\n")


def load_snapshot() -> set[str]:
    if not SNAPSHOT_FILE.exists():
        return set()
    try:
        data = json.loads(SNAPSHOT_FILE.read_text())
        return set(data.get("apps", []))
    except (OSError, json.JSONDecodeError):
        return set()


def detect_changes() -> dict[str, list[str]]:
    """Compare the current app list to the stored snapshot.

    Returns {'new': [...], 'removed': [...]}. A new app is one installed
    since the last snapshot that is NOT already whitelisted.
    """
    current = set(scan_installed_apps().keys())
    snapshot = load_snapshot()

    if not snapshot:
        return {"new": [], "removed": []}

    new = sorted(current - snapshot)
    removed = sorted(snapshot - current)
    return {"new": new, "removed": removed}


def update_snapshot() -> None:
    save_snapshot()
