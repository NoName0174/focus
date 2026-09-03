import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

HOSTS_PATH = Path("/etc/hosts")
BACKUP_PATH = Path("/etc/hosts.focus-backup")
BLOCK_MARKER_START = "# === FOCUS BLOCK START ==="
BLOCK_MARKER_END = "# === FOCUS BLOCK END ==="


def get_config_dir() -> Path:
    config_dir = Path.home() / ".config" / "focus"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def _get_state_path() -> Path:
    return get_config_dir() / "blocked_apps.json"


def _load_state() -> dict:
    path = _get_state_path()
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return json.load(f)


def _save_state(state: dict) -> None:
    path = _get_state_path()
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def _run_sudo(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a privileged command via sudo."""
    full = ["sudo", *cmd]
    try:
        result = subprocess.run(full, capture_output=True, text=True, timeout=30)
    except (subprocess.SubprocessError, OSError) as e:
        raise PermissionError(f"Failed to escalate privileges: {e}") from e
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise PermissionError(f"sudo command failed: {' '.join(full)}\n{detail}")
    return result


def backup_hosts() -> None:
    _run_sudo(["cp", "-f", str(HOSTS_PATH), str(BACKUP_PATH)])


def restore_hosts() -> None:
    if not is_blocked():
        return
    _run_sudo(["cp", "-f", str(BACKUP_PATH), str(HOSTS_PATH)])
    _run_sudo(["rm", "-f", str(BACKUP_PATH)])


def block_domains(domains: list[str]) -> None:
    if not domains:
        return
    current = get_original_hosts()
    lines = [line.rstrip("\n") for line in current.splitlines() if line.strip()]
    block_lines = [BLOCK_MARKER_START]
    for domain in domains:
        block_lines.append(f"127.0.0.1 {domain} {domain}.local")
    block_lines.append(BLOCK_MARKER_END)
    new_content = "\n".join(lines + block_lines) + "\n"
    _write_hosts_via_sudo(new_content)


def unblock_domains() -> None:
    if not is_blocked():
        return
    current = get_original_hosts()
    _write_hosts_via_sudo(current)


def _write_hosts_via_sudo(content: str) -> None:
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".hosts", delete=False) as f:
        f.write(content)
        tmp_path = f.name
    try:
        _run_sudo(["cp", "-f", tmp_path, str(HOSTS_PATH)])
    finally:
        os.unlink(tmp_path)


def _remove_block_section(content: str) -> str:
    lines = content.splitlines(keepends=True)
    result = []
    inside_block = False
    for line in lines:
        stripped = line.strip()
        if stripped == BLOCK_MARKER_START:
            inside_block = True
            continue
        if stripped == BLOCK_MARKER_END:
            inside_block = False
            continue
        if not inside_block:
            result.append(line)
    return "".join(result)


def is_blocked() -> bool:
    try:
        content = _run_sudo(["cat", str(HOSTS_PATH)]).stdout
    except PermissionError:
        return False
    return BLOCK_MARKER_START in content


def get_original_hosts() -> str:
    try:
        content = _run_sudo(["cat", str(HOSTS_PATH)]).stdout
    except PermissionError:
        return ""
    return _remove_block_section(content)


def block_apps(apps: list[str], allowed: set[str] | None = None) -> None:
    state = _load_state()
    allowed = allowed or frozenset()
    for app in apps:
        if app in allowed:
            print(f"[dim](skipping '{app}' — on whitelist)[/]")
            continue
        if app in state:
            print(f"App '{app}' is already blocked")
            continue
        app_path = shutil.which(app)
        if app_path is None:
            print(f"[dim](skipping '{app}' — not found in PATH)[/]")
            continue
        app_path = Path(app_path)
        if not app_path.exists():
            print(f"[dim](skipping '{app}' — executable missing)[/]")
            continue
        try:
            original_mode = _get_mode_via_sudo(app_path)
            _run_sudo(["chmod", "000", str(app_path)])
        except PermissionError as e:
            print(f"Error: {e}")
            continue
        state[app] = {
            "path": str(app_path),
            "original_mode": original_mode,
        }
        print(f"Blocked '{app}'")
    _save_state(state)


def unblock_apps() -> None:
    state = _load_state()
    if not state:
        print("No blocked apps to restore")
        return
    restored = []
    for app, info in state.items():
        app_path = Path(info["path"])
        original_mode = info["original_mode"]
        if not app_path.exists():
            print(f"Warning: '{app_path}' no longer exists, skipping")
            continue
        try:
            _run_sudo(["chmod", original_mode, str(app_path)])
            restored.append(app)
        except PermissionError as e:
            print(f"Error: {e}")
    for app in restored:
        del state[app]
    _save_state(state)


def _get_mode_via_sudo(path: Path) -> str:
    result = _run_sudo(["stat", "-c", "%a", str(path)])
    return result.stdout.strip()


def is_app_blocked(app: str) -> bool:
    state = _load_state()
    return app in state


def get_blocked_apps() -> list[str]:
    state = _load_state()
    blocked = []
    for app, info in list(state.items()):
        app_path = Path(info["path"])
        if app_path.exists() and _is_zero_mode(app_path):
            blocked.append(app)
    return blocked


def _is_zero_mode(path: Path) -> bool:
    try:
        result = _run_sudo(["stat", "-c", "%a", str(path)])
        return result.stdout.strip() == "000"
    except PermissionError:
        return False
