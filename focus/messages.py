"""User-friendly error messages with suggestions to fix problems."""

from __future__ import annotations

from rich.console import Console

console = Console()


def _show(message: str, suggestion: str) -> None:
    console.print(f"[bold red]{message}[/]")
    console.print(f"[dim yellow]Suggestion: {suggestion}[/]")


def _cmd(command: str) -> str:
    return f"[cyan]{command}[/]"


def sudo_required() -> None:
    _show(
        "This operation requires sudo privileges.",
        f"Re-run the command with {_cmd('sudo focus ...')}.",
    )


def host_block_failed(path: str) -> None:
    _show(
        f"Failed to modify {_cmd(path)}.",
        f"Check that you have write permissions and try again with {_cmd('sudo')}.",
    )


def app_block_failed(app: str) -> None:
    _show(
        f"Failed to block app {_cmd(app)}.",
        f"Verify the app name is correct and that you have permission to block it.",
    )


def restore_failed() -> None:
    _show(
        "Failed to restore /etc/hosts.",
        "Restore it manually by removing the host entries added by focus. "
        f"See {_cmd('focus --help')} for details.",
    )


def config_not_found() -> None:
    _show(
        "Config file not found.",
        "A new config file will be created with default settings on the next run.",
    )


def config_corrupt(path: str) -> None:
    _show(
        f"Config file is corrupt: {_cmd(path)}.",
        "Delete the file and let focus recreate it with defaults. "
        f"Run {_cmd('rm ' + path)} to remove it.",
    )


def invalid_duration(duration: str) -> None:
    _show(
        f"Invalid time format: {_cmd(duration)}.",
        "Use formats like 1h30m, 45m, or 2h. For example: "
        f"{_cmd('focus start 45m')} or {_cmd('focus start 2h30m')}.",
    )


def session_already_active() -> None:
    _show(
        "A session is already running.",
        f"Stop the current session first with {_cmd('focus stop')}.",
    )


def no_active_session() -> None:
    _show(
        "No session is currently running.",
        f"Start a new session with {_cmd('focus start')}.",
    )


def dunst_not_found() -> None:
    _show(
        "dunstctl was not found.",
        "Install dunst to enable notifications. "
        f"On Debian/Ubuntu run {_cmd('sudo apt install dunst')} "
        f"or on Fedora run {_cmd('sudo dnf install dunst')}.",
    )


def systemd_error(detail: str) -> None:
    _show(
        f"systemd error: {detail}",
        "Check that the service is enabled and running. "
        f"Try {_cmd('systemctl status focus')} and {_cmd('systemctl start focus')}.",
    )


def uninstall_error(detail: str) -> None:
    _show(
        f"Uninstall error: {detail}",
        "Clean up manually by removing the focus config directory and "
        f"any {_cmd('/etc/hosts')} entries added by focus.",
    )


def confirmation_wrong() -> None:
    _show(
        "Wrong confirmation phrase.",
        "The phrase did not match. Try again with the exact phrase, "
        "or check your config for the correct one.",
    )


def python_version_error() -> None:
    _show(
        "Python 3.11 or higher is required.",
        f"Upgrade Python, e.g. {_cmd('sudo apt install python3.11')} on Debian/Ubuntu "
        f"or {_cmd('sudo dnf install python3.11')} on Fedora.",
    )


def permission_denied(path: str) -> None:
    _show(
        f"Permission denied for {_cmd(path)}.",
        f"Fix permissions with {_cmd('chmod')} or run the command with {_cmd('sudo')}.",
    )
