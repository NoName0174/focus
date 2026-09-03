from __future__ import annotations

import argparse
from typing import Callable

from rich.console import Console
from rich.table import Table

from . import applist
from . import blocker, config, display, messages, notifications, queue, service, stats, strict

console = Console()

try:
    from . import tui
except ImportError:
    tui = None  # type: ignore[assignment]

try:
    from . import wizard
except ImportError:
    wizard = None  # type: ignore[assignment]

try:
    from . import uninstall
except ImportError:
    uninstall = None  # type: ignore[assignment]

VERSION = "1.0.0"


# ── session helpers ──

def _format_duration_label(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes}m"
    hours, rem = divmod(minutes, 60)
    if rem == 0:
        return f"{hours}h"
    return f"{hours}h {rem}m"


def _setup_blocking(cfg: config.Config) -> tuple[int, int]:
    allowed = set(cfg.blocking.allowed_apps) | applist.ESSENTIAL_APPS
    blocker.backup_hosts()
    blocker.block_domains(cfg.blocking.domains)
    blocker.block_apps(cfg.blocking.apps, allowed=allowed)
    return len(cfg.blocking.domains), len(cfg.blocking.apps)


def _teardown_blocking() -> None:
    try:
        blocker.unblock_domains()
    except PermissionError:
        messages.sudo_required()
    try:
        blocker.unblock_apps()
    except PermissionError:
        messages.sudo_required()


def _ensure_service() -> None:
    if service.is_service_running():
        return
    if not service.install_service():
        messages.systemd_error("Failed to install and start the focus service.")


def _apply_study_env(cfg: config.Config) -> None:
    notifications.silence_notifications()
    display.apply_study_display(
        dim=cfg.display.dim_brightness,
        dark=cfg.display.dark_mode,
        brightness_percent=cfg.display.brightness_percent,
    )


def _restore_study_env() -> None:
    notifications.unsilence_notifications()
    try:
        display.restore_display()
    except Exception:
        pass


def _record_stats(
    duration_minutes: int,
    blocked_domains: int,
    blocked_apps: int,
    pomodoros: int,
) -> None:
    session_id = stats.start_session(duration_minutes, blocked_domains, blocked_apps)
    stats.end_session(session_id, pomodoros)


def _handle_start(args: argparse.Namespace) -> None:
    cfg = config.load_config()

    duration_str: str | None = args.duration
    duration_minutes: int

    if duration_str:
        try:
            duration_minutes = queue.parse_duration(duration_str)
        except ValueError:
            messages.invalid_duration(duration_str)
            return
    else:
        duration_minutes = cfg.pomodoro.work_minutes * 4
        console.print(
            f"[dim]No duration specified. Defaulting to {_format_duration_label(duration_minutes)}.[/]"
        )

    if not strict.validate_sudo():
        messages.sudo_required()
        return

    try:
        _ensure_service()
    except PermissionError:
        messages.sudo_required()
        return

    try:
        domain_count, app_count = _setup_blocking(cfg)
    except PermissionError:
        messages.sudo_required()
        return

    _apply_study_env(cfg)

    pomodoros = 0
    try:
        if tui is not None:
            tui.run_session_interactive(duration_minutes * 60)
        else:
            notifications.notify_session_start(_format_duration_label(duration_minutes))
            console.print(
                f"[bold green]Session started: {_format_duration_label(duration_minutes)}[/]"
            )
            console.print("[dim]Press Ctrl+C to stop the session.[/]")
            try:
                import time

                time.sleep(duration_minutes * 60)
            except KeyboardInterrupt:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        _teardown_blocking()
        _restore_study_env()
        _record_stats(duration_minutes, domain_count, app_count, pomodoros)
        notifications.notify_session_end(f"{_format_duration_label(duration_minutes)} session complete")
        console.print("[bold green]Session ended. All restrictions lifted.[/]")


def _handle_stop(args: argparse.Namespace) -> None:
    cfg = config.load_config()

    if cfg.general.strict:
        if not blocker.is_blocked() and not notifications.are_notifications_silenced():
            messages.no_active_session()
            return
        if not strict.check_strict_mode(cfg.general.strict, cfg.general.confirmation_phrase):
            messages.confirmation_wrong()
            return

    _teardown_blocking()
    _restore_study_env()
    notifications.send_notification("Session stopped", "All restrictions lifted.")
    console.print("[bold green]Session stopped. All restrictions lifted.[/]")


def _handle_stats(args: argparse.Namespace) -> None:
    stats.render_dashboard()


def _handle_queue_add(args: argparse.Namespace) -> None:
    name: str = args.name
    duration_str: str = args.duration

    try:
        item = queue.add_to_queue(name, duration_str)
    except ValueError:
        messages.invalid_duration(duration_str)
        return

    console.print(f"[green]Added:[/] {item.name} ({_format_duration_label(item.duration_minutes)})")


def _handle_queue_list(args: argparse.Namespace) -> None:
    items = queue.get_queue()
    if not items:
        console.print("[dim]Queue is empty.[/]")
        return

    table = Table(title="Study Queue", show_lines=True)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Duration", justify="right")

    for i, item in enumerate(items, 1):
        table.add_row(str(i), item.name, _format_duration_label(item.duration_minutes))

    console.print(table)


def _handle_queue_clear(args: argparse.Namespace) -> None:
    queue.clear_queue()
    console.print("[green]Queue cleared.[/]")


def _handle_config(args: argparse.Namespace) -> None:
    cfg = config.load_config()

    table = Table(title="Current Configuration", show_lines=True, box=None)
    table.add_column("Section", style="bold cyan")
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("general", "mode", cfg.general.mode)
    table.add_row("general", "strict", str(cfg.general.strict))
    table.add_row("general", "autostart", str(cfg.general.autostart))
    table.add_row("general", "confirmation_phrase", cfg.general.confirmation_phrase)
    table.add_row("pomodoro", "work_minutes", str(cfg.pomodoro.work_minutes))
    table.add_row("pomodoro", "short_break_minutes", str(cfg.pomodoro.short_break_minutes))
    table.add_row("pomodoro", "long_break_minutes", str(cfg.pomodoro.long_break_minutes))
    table.add_row("pomodoro", "long_break_after", str(cfg.pomodoro.long_break_after))
    table.add_row("daily", "enabled", str(cfg.daily.enabled))
    table.add_row("daily", "goal_hours", str(cfg.daily.goal_hours))
    table.add_row("display", "dim_brightness", str(cfg.display.dim_brightness))
    table.add_row("display", "brightness_percent", str(cfg.display.brightness_percent))
    table.add_row("display", "dark_mode", str(cfg.display.dark_mode))
    table.add_row("blocking", "domains", f"{len(cfg.blocking.domains)} domains")
    table.add_row("blocking", "apps", f"{len(cfg.blocking.apps)} apps")

    console.print(table)


def _handle_setup(args: argparse.Namespace) -> None:
    if wizard is None:
        console.print("[bold red]Setup wizard is not yet available.[/]")
        return
    wizard.run_wizard()


def _handle_autostart(args: argparse.Namespace) -> None:
    cfg = config.load_config()

    if args.state is None:
        status = "on" if cfg.general.autostart else "off"
        console.print(f"Autostart is currently [bold]{status}[/].")
        console.print("[dim]Usage: focus autostart [on|off][/]")
        return

    state = args.state.lower()
    if state == "on":
        cfg.general.autostart = True
    elif state == "off":
        cfg.general.autostart = False
    else:
        console.print("[red]Invalid argument. Use 'on' or 'off'.[/]")
        return

    config.save_config(cfg)
    console.print(f"[green]Autostart set to {state}.[/]")


def _handle_uninstall(args: argparse.Namespace) -> None:
    if uninstall is None:
        console.print("[bold red]Uninstaller is not yet available.[/]")
        return
    uninstall.uninstall()


def _handle_no_command(args: argparse.Namespace) -> None:
    if tui is not None:
        tui.render_main_menu()
    else:
        console.print("[bold cyan]focus[/] — Study mode for Linux")
        console.print("[dim]Run [bold]focus --help[/bold] for available commands. [/]")


# ── command line interface ──

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="focus",
        description="Study mode for Linux — block distractions, track progress, stay focused.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {VERSION}"
    )

    subparsers = parser.add_subparsers(dest="command")

    p_start = subparsers.add_parser("start", help="Start a study session")
    p_start.add_argument("duration", nargs="?", default=None, help="Duration (e.g. 2h, 90m, 45)")

    subparsers.add_parser("stop", help="Stop the current session")

    subparsers.add_parser("stats", help="Show stats dashboard")

    p_queue = subparsers.add_parser("queue", help="Manage the study queue")
    queue_sub = p_queue.add_subparsers(dest="queue_command")
    p_q_add = queue_sub.add_parser("add", help="Add an item to the queue")
    p_q_add.add_argument("name", help="Name of the task")
    p_q_add.add_argument("duration", help="Duration (e.g. 45m, 2h)")
    queue_sub.add_parser("list", help="Show queue items")
    queue_sub.add_parser("clear", help="Clear the queue")

    subparsers.add_parser("config", help="Show current configuration")

    subparsers.add_parser("setup", help="Run the first-run wizard")

    p_autostart = subparsers.add_parser("autostart", help="Toggle autostart")
    p_autostart.add_argument("state", nargs="?", choices=["on", "off"], default=None)

    subparsers.add_parser("uninstall", help="Uninstall focus")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch: dict[str, Callable] = {
        "start": _handle_start,
        "stop": _handle_stop,
        "stats": _handle_stats,
        "queue": lambda a: _handle_queue_dispatch(a),
        "config": _handle_config,
        "setup": _handle_setup,
        "autostart": _handle_autostart,
        "uninstall": _handle_uninstall,
    }

    if args.command is None:
        _handle_no_command(args)
        return

    handler = dispatch.get(args.command)
    if handler:
        try:
            handler(args)
        except PermissionError:
            messages.sudo_required()
        except Exception as exc:
            messages.systemd_error(str(exc))


def _handle_queue_dispatch(args: argparse.Namespace) -> None:
    cmd = getattr(args, "queue_command", None)

    if cmd == "add":
        _handle_queue_add(args)
    elif cmd == "list":
        _handle_queue_list(args)
    elif cmd == "clear":
        _handle_queue_clear(args)
    else:
        console.print("[dim]Usage: focus queue {add|list|clear}[/]")
