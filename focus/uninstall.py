import os
import shutil
from pathlib import Path

from prompt_toolkit import prompt
from prompt_toolkit.document import Document
from prompt_toolkit.validation import ValidationError, Validator
from rich.console import Console

from focus import blocker, messages, service

console = Console()

CONFIG_DIR = Path.home() / ".config" / "focus"
BRIGHTNESS_BACKUP = CONFIG_DIR / ".brightness_backup"


class YesNoValidator(Validator):
    def validate(self, document: Document) -> None:
        text = document.text.strip().lower()
        if text not in ("y", "n", ""):
            raise ValidationError(message="Please enter y or n.")


def _check_sudo() -> bool:
    if os.geteuid() != 0:
        console.print(
            "[bold yellow]Warning:[/] Not running as root. "
            "Some operations (hosts, systemd) may fail."
        )
        console.print(
            "[dim]Tip: re-run with [bold]sudo focus --uninstall[/bold][/]"
        )
        console.print()
        return False
    return True


def _confirm(message: str) -> bool:
    console.print(f"[bold]{message}[/]", end=" ")
    answer = prompt("", validator=YesNoValidator(), validate_while_typing=False)
    return answer.strip().lower() == "y"


def _step_restore_hosts() -> bool:
    if not blocker.is_blocked() and not blocker.BACKUP_PATH.exists():
        console.print("[dim]No hosts backup found, skipping.[/]")
        return True
    try:
        blocker.restore_hosts()
        console.print("[green]✓[/] Restored /etc/hosts from backup")
        return True
    except Exception as exc:
        console.print(f"[red]✗[/] Failed to restore /etc/hosts: {exc}")
        messages.restore_failed()
        return False


def _step_unblock_apps() -> bool:
    blocked = blocker.get_blocked_apps()
    if not blocked:
        console.print("[dim]No blocked apps to restore.[/]")
        return True
    try:
        blocker.unblock_apps()
        console.print(f"[green]✓[/] Unblocked {len(blocked)} app(s): {', '.join(blocked)}")
        return True
    except Exception as exc:
        console.print(f"[red]✗[/] Failed to unblock apps: {exc}")
        return False


def _step_remove_service() -> bool:
    if not service.is_service_installed():
        console.print("[dim]No systemd service installed, skipping.[/]")
        return True
    try:
        if service.uninstall_service():
            console.print("[green]✓[/] Stopped and removed systemd service")
            return True
        console.print("[red]✗[/] Service removal reported failure")
        return False
    except Exception as exc:
        console.print(f"[red]✗[/] Failed to remove service: {exc}")
        return False


def _step_remove_config() -> bool:
    if not CONFIG_DIR.exists():
        console.print("[dim]No config directory found, skipping.[/]")
        return True
    if not _confirm("Delete config data and stats? (y/N)"):
        console.print("[dim]Keeping config data.[/]")
        return True
    try:
        shutil.rmtree(CONFIG_DIR)
        console.print(f"[green]✓[/] Removed {CONFIG_DIR}")
        return True
    except Exception as exc:
        console.print(f"[red]✗[/] Failed to remove config: {exc}")
        messages.uninstall_error(str(exc))
        return False


def _step_remove_brightness() -> bool:
    if not BRIGHTNESS_BACKUP.exists():
        console.print("[dim]No brightness backup found, skipping.[/]")
        return True
    try:
        BRIGHTNESS_BACKUP.unlink()
        console.print("[green]✓[/] Removed brightness backup")
        return True
    except Exception as exc:
        console.print(f"[red]✗[/] Failed to remove brightness backup: {exc}")
        return False


def uninstall() -> bool:
    console.print()
    console.print(
        "[bold red on black] ⚠️  This will completely remove focus from your system [/]"
    )
    console.print()

    if not _confirm("Are you sure? This cannot be undone. (y/N)"):
        console.print("[dim]Uninstall cancelled.[/]")
        return False

    console.print()
    _check_sudo()
    console.print("[bold]Cleaning up:[/]")
    console.print()

    results: list[bool] = []
    results.append(_step_restore_hosts())
    results.append(_step_unblock_apps())
    results.append(_step_remove_service())
    results.append(_step_remove_config())
    results.append(_step_remove_brightness())

    console.print()
    if all(results):
        console.print(
            "[bold green]Focus has been removed. Good luck staying focused! 👋[/]"
        )
        return True

    console.print(
        "[bold yellow]Focus uninstall completed with errors.[/]"
    )
    console.print("[dim]Some items may require manual cleanup.[/]")
    return False
