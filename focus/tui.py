from __future__ import annotations

import random
import re
import sys
import threading
import time
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.buffer import Buffer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import Config, load_config, save_config
from .pomodoro import (
    PomodoroState,
    advance,
    format_time,
    get_current_phase,
    get_progress,
    get_session_summary,
    is_completed,
    tick,
)
from . import notifications
from . import queue as queue_mod
from . import stats
from . import blocker
from . import display
from . import strict
from . import applist

console = Console()

MENU_OPTIONS = [
    "Start Focus Session",
    "Session Queue",
    "Stats Dashboard",
    "Manage Blocked Apps",
    "Configuration",
    "Autostart Toggle",
    "Quit",
]

BANNER = r"""
  ███████╗  ██████╗   ██████╗██╗   ██╗███████╗
  ██╔════╝ ██╔═══██╗ ██╔════╝██║   ██║██╔════╝
  █████╗   ██║   ██║ ██║     ██║   ██║███████╗
  ██╔══╝   ██║   ██║ ██║     ██║   ██║╚════██║
  ██║      ╚██████╔╝ ╚██████╗╚██████╔╝███████║
  ╚═╝       ╚═════╝   ╚═════╝ ╚═════╝ ╚══════╝
"""


# ── main menu ──

def render_main_menu() -> None:
    console.print(BANNER, style="bold cyan")
    console.print()
    for i, option in enumerate(MENU_OPTIONS, 1):
        console.print(f"  [bold cyan]{i}.[/] {option}")
    console.print()

    session = PromptSession()
    check_for_new_apps(cfg=None)
    while True:
        try:
            choice = session.prompt("Select option (1-7): ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/]")
            return

        if choice == "1":
            _handle_start_session()
        elif choice == "2":
            _handle_session_queue()
        elif choice == "3":
            console.print()
            stats.render_dashboard()
        elif choice == "4":
            _handle_manage_apps()
        elif choice == "5":
            _handle_configuration()
        elif choice == "6":
            _handle_autostart_toggle()
        elif choice == "7":
            console.print("\n[dim]Goodbye![/]")
            return
        else:
            console.print("[red]Invalid option.[/]")
            continue

        console.print()


def check_for_new_apps(cfg: Config | None) -> None:
    """On startup, detect newly installed apps and offer to block them."""
    try:
        changes = applist.detect_changes()
    except Exception:
        return

    new_apps = [a for a in changes.get("new", []) if a not in applist.ESSENTIAL_APPS]
    if not new_apps:
        applist.update_snapshot()
        return

    cfg = cfg or load_config()
    allowed = set(cfg.blocking.allowed_apps)

    console.print("\n[bold yellow]New apps detected since your last session:[/]")
    for a in new_apps:
        console.print(f"  [cyan]•[/] {a}")
    console.print()
    print("  Block any of these by default?")
    print("  (b)lock all   (n)one   or pick numbers like '1,3'")

    session = PromptSession()
    blocked_new = []
    for i, a in enumerate(new_apps, 1):
        try:
            resp = session.prompt(f"  Block {a}? [y/N]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            resp = ""
        if resp in ("y", "yes"):
            blocked_new.append(a)

    if blocked_new:
        existing = set(cfg.blocking.apps)
        cfg.blocking.apps = sorted(existing | set(blocked_new))
        save_config(cfg)
        console.print(f"[green]Added {len(blocked_new)} app(s) to the block list.[/]")

    applist.update_snapshot()


def show_start_dialog() -> tuple[int, bool]:
    """Ask for duration or queue item. Returns (seconds, use_breaks).

    Accepts: '25m', '2h', '1h30m', '90s', '45' (minutes), or 'q1', 'q2'... for queue items.
    A plain number is always minutes (never a queue index).
    """
    try:
        session = PromptSession()
        choice = session.prompt(
            "Duration (e.g. 25m, 2h, 1h30m, 90s, or minutes) | queue item 'q1': "
        ).strip()
    except (KeyboardInterrupt, EOFError):
        return (0, False)

    if not choice:
        return (0, False)

    if re.match(r"^q\d+$", choice.lower()):
        idx = int(choice.lower()[1:])
        items = queue_mod.get_queue()
        if 1 <= idx <= len(items):
            item = items[idx - 1]
            queue_mod.remove_first()
            console.print(
                f"[green]Starting from queue:[/] {item.name}"
                f" ({queue_mod.format_duration(item.duration_minutes)})"
            )
            return (item.duration_minutes * 60, False)
        else:
            console.print("[red]Invalid queue number.[/]")
            return (0, False)

    try:
        seconds = _parse_duration_seconds(choice)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        return (0, False)

    return (seconds, True)


def _parse_duration_seconds(duration_str: str) -> int:
    """Parse a user-entered duration into seconds."""
    s = duration_str.strip().lower()
    if not s:
        raise ValueError("Duration string is empty")

    si = re.fullmatch(r"(\d+(?:\.\d+)?)s", s)
    if si:
        sec = int(float(si.group(1)))
        if sec <= 0:
            raise ValueError(f"Duration must be positive, got '{duration_str}'")
        return sec

    hm = re.fullmatch(r"(\d+(?:\.\d+)?)h(?:(\d+(?:\.\d+)?)m)?", s)
    if hm:
        hours = float(hm.group(1))
        minutes = float(hm.group(2) or 0)
        sec = int(hours * 3600 + minutes * 60)
        if sec <= 0:
            raise ValueError(f"Duration must be positive, got '{duration_str}'")
        return sec

    m = re.fullmatch(r"(\d+(?:\.\d+)?)(m|h)", s)
    if m:
        value = float(m.group(1))
        if value <= 0:
            raise ValueError(f"Duration must be positive, got '{duration_str}'")
        if m.group(2) == "h":
            return int(value * 3600)
        return int(value * 60)

    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        value = float(s)
        if value <= 0:
            raise ValueError(f"Duration must be positive, got '{duration_str}'")
        return int(value * 60)

    raise ValueError(
        f"Invalid duration format: '{duration_str}'. "
        "Use formats like '25m', '2h', '1h30m', '90s', or a plain number for minutes."
    )


def _handle_start_session() -> None:
    cfg = load_config()
    duration_seconds, use_breaks = show_start_dialog()
    if duration_seconds <= 0:
        return
    _run_session(duration_seconds, cfg)


def _handle_session_queue() -> None:
    items = queue_mod.get_queue()
    if not items:
        console.print("[dim]Queue is empty.[/]")
        return

    console.print()
    for i, item in enumerate(items, 1):
        console.print(
            f"  [bold cyan]{i}.[/] {item.name}"
            f" — [dim]{queue_mod.format_duration(item.duration_minutes)}[/]"
        )
    console.print()
    console.print("  [dim]Commands: a name duration | c (clear) | q (back)[/]")

    session = PromptSession()
    while True:
        try:
            cmd = session.prompt("queue> ").strip()
        except (KeyboardInterrupt, EOFError):
            return

        if not cmd or cmd == "q":
            return

        if cmd == "c":
            queue_mod.clear_queue()
            console.print("[green]Queue cleared.[/]")
            return

        if cmd.startswith("a "):
            parts = cmd[2:].strip().split(maxsplit=1)
            if len(parts) < 2:
                console.print("[red]Usage: a <name> <duration>[/]")
                continue
            name, duration_str = parts[0], parts[1]
            try:
                item = queue_mod.add_to_queue(name, duration_str)
                console.print(
                    f"[green]Added:[/] {item.name}"
                    f" ({queue_mod.format_duration(item.duration_minutes)})"
                )
            except ValueError as e:
                console.print(f"[red]{e}[/]")
        else:
            console.print("[red]Unknown command. Use 'a name duration', 'c', or 'q'.[/]")


# ── session runner ──

def _run_session(duration_seconds: int, cfg: Config) -> None:
    console.print("[bold cyan]Session started. Press q to quit early.[/]")
    console.print()

    if not strict.validate_sudo():
        console.print("[yellow]Sudo cancelled. Blocking was skipped; session will still run.[/]")
    else:
        try:
            allowed = set(cfg.blocking.allowed_apps) | applist.ESSENTIAL_APPS
            blocker.backup_hosts()
            blocker.block_domains(cfg.blocking.domains)
            blocker.block_apps(cfg.blocking.apps, allowed=allowed)
        except PermissionError:
            console.print("[yellow]Warning: Could not apply blocks (sudo required).[/]")

    notifications.silence_notifications()
    try:
        display.apply_study_display(
            dim=cfg.display.dim_brightness,
            dark=cfg.display.dark_mode,
            brightness_percent=cfg.display.brightness_percent,
        )
    except Exception:
        pass

    try:
        result = run_session_interactive(duration_seconds, cfg)
    except KeyboardInterrupt:
        result = {"completed": False, "reason": "interrupted"}
    finally:
        try:
            blocker.unblock_domains()
        except PermissionError:
            pass
        try:
            blocker.unblock_apps()
        except PermissionError:
            pass
        notifications.unsilence_notifications()
        try:
            display.restore_display()
        except Exception:
            pass

    notifications.notify_session_end("Session complete")
    console.print("[bold green]Session ended.[/]")


def run_session_interactive(duration_seconds: int, config: Config) -> dict[str, Any]:
    target_seconds = duration_seconds
    start_time = time.time()

    work_seconds = config.pomodoro.work_minutes * 60
    short_session = target_seconds < work_seconds
    if short_session:
        work_seconds = target_seconds

    state = PomodoroState(
        current_pomodoro=0,
        total_pomodoros=0,
        is_break=False,
        break_is_long=False,
        time_remaining_seconds=work_seconds,
        phase_total_seconds=work_seconds,
        total_work_seconds=0,
    )

    done_event = threading.Event()
    phase_done = threading.Event()
    state_lock = threading.Lock()

    def tick_loop() -> None:
        nonlocal state
        while not done_event.is_set():
            done_event.wait(timeout=1.0)
            if done_event.is_set():
                break
            with state_lock:
                state = tick(state)
                if is_completed(state):
                    phase_done.set()

    notifications.notify_session_start(format_time(duration_seconds))
    thread = threading.Thread(target=tick_loop, daemon=True)
    thread.start()

    motivation = generate_motivation()
    session_id = stats.start_session(max(duration_seconds // 60, 1), 0, 0)

    kb = KeyBindings()

    @kb.add(Keys.Any)
    def _(event: Any) -> None:
        char = event.current_buffer.text
        if char.lower() == "q":
            done_event.set()
            event.app.exit()

    prompt_session = PromptSession(key_bindings=kb, input=sys.stdin)

    try:
        with Live(console=console, refresh_per_second=1, transient=True) as live:
            while not done_event.is_set():
                elapsed = time.time() - start_time
                with state_lock:
                    current_state = state
                live.update(
                    _build_live_display(current_state, config, elapsed, motivation)
                )

                if phase_done.is_set():
                    phase_done.clear()

                    with state_lock:
                        was_work = not current_state.is_break
                        if was_work and not short_session:
                            notifications.notify_pomodoro_complete(
                                current_state.total_pomodoros,
                                config.pomodoro.long_break_after,
                            )

                    if short_session:
                        done_event.set()
                        continue

                    live.stop()

                    with state_lock:
                        is_long = current_state.break_is_long
                        break_seconds = (
                            config.pomodoro.long_break_minutes * 60
                            if is_long
                            else config.pomodoro.short_break_minutes * 60
                        )
                        break_type = "Long Break" if is_long else "Short Break"
                        notifications.notify_break_start(
                            break_type, format_time(break_seconds)
                        )

                    break_choice = show_break_options()

                    if break_choice == "quit":
                        done_event.set()
                    else:
                        with state_lock:
                            state = advance(state, config.pomodoro)
                            if is_completed(state):
                                phase_done.set()
                        notifications.notify_break_end()

                    live.start()
                    continue

                try:
                    prompt_session.prompt("")
                except (KeyboardInterrupt, EOFError):
                    done_event.set()
                except Exception:
                    pass

    except KeyboardInterrupt:
        pass
    finally:
        done_event.set()
        thread.join(timeout=2)

    with state_lock:
        final_state = state

    stats.end_session(session_id, final_state.total_pomodoros)

    return {
        "completed": final_state.total_pomodoros > 0,
        "pomodoros": final_state.total_pomodoros,
        "work_seconds": final_state.total_work_seconds,
        "elapsed_seconds": time.time() - start_time,
    }


def _build_live_display(
    state: PomodoroState,
    config: Config,
    elapsed: float,
    motivation: str,
) -> Panel:
    phase = get_current_phase(state)
    phase_labels = {
        "work": "WORK",
        "short_break": "SHORT BREAK",
        "long_break": "LONG BREAK",
    }
    phase_colors = {
        "work": "bold red",
        "short_break": "bold green",
        "long_break": "bold blue",
    }

    label = phase_labels.get(phase, phase)
    color = phase_colors.get(phase, "bold white")
    pct = get_progress(state, config.pomodoro)

    body = Text()
    body.append("  Phase: ", style="dim")
    body.append(f"{label}\n", style=color)
    body.append("  Time:  ", style="dim")
    body.append(f"{format_time(state.time_remaining_seconds)}\n", style="bold white")
    body.append(f"  {progress_bar(pct)}\n", style=color)
    body.append("  Pomodoro: ", style="dim")
    body.append(
        f"{state.current_pomodoro}/{config.pomodoro.long_break_after}",
        style="bold cyan",
    )
    body.append("\n")
    body.append("  Elapsed: ", style="dim")
    body.append(f"{format_time(int(elapsed))}\n", style="dim")
    body.append(f"\n  {motivation}", style="italic yellow")

    return Panel(body, border_style=color, title="[bold]FOCUS SESSION[/]")


def show_break_options() -> str:
    console.print()
    console.print("[bold green]Pomodoro complete![/]")
    console.print()
    console.print("  [bold cyan]1.[/] Start Break")
    console.print("  [bold cyan]2.[/] Skip Break")
    console.print("  [bold cyan]3.[/] Quit Session")
    console.print()

    session = PromptSession()
    while True:
        try:
            choice = session.prompt("Break (1-3): ").strip()
        except (KeyboardInterrupt, EOFError):
            return "quit"

        if choice == "1":
            return "start"
        elif choice == "2":
            return "skip"
        elif choice == "3":
            return "quit"
        else:
            console.print("[red]Invalid option.[/]")


def generate_motivation() -> str:
    quotes = [
        "The secret of getting ahead is getting started. — Mark Twain",
        "It does not matter how slowly you go as long as you do not stop. — Confucius",
        "Focus is a matter of deciding what things you're not going to do. — John Carmack",
        "Concentrate all your thoughts upon the work at hand. — Alexander Graham Bell",
        "You don't have to be great to start, but you have to start to be great. — Zig Ziglar",
        "The only way to do great work is to love what you do. — Steve Jobs",
        "Discipline is choosing between what you want now and what you want most. — Abraham Lincoln",
        "Don't watch the clock; do what it does. Keep going. — Sam Levenson",
        "Start where you are. Use what you have. Do what you can. — Arthur Ashe",
        "Success is the sum of small efforts, repeated day in and day out. — Robert Collier",
        "The best time to plant a tree was 20 years ago. The second best time is now.",
        "Your focus determines your reality. — Qui-Gon Jinn",
        "What you get by achieving your goals is not as important as what you become. — Zig Ziglar",
        "The harder you work for something, the greater you'll feel when you achieve it.",
        "Small daily improvements are the key to staggering long-term results.",
        "Motivation is what gets you started. Habit is what keeps you going. — Jim Ryun",
        "Believe you can and you're halfway there. — Theodore Roosevelt",
        "Action is the foundational key to all success. — Pablo Picasso",
        "The mind is everything. What you think you become. — Buddha",
        "Stay focused and never give up. Your breakthrough is coming.",
        "Great things are done by a series of small things brought together. — Vincent Van Gogh",
        "No matter how small, every step counts. Keep moving forward.",
        "The future depends on what you do today. — Mahatma Gandhi",
        "Success usually comes to those who are too busy to be looking for it. — Henry David Thoreau",
        "Dreams don't work unless you do. — John C. Maxwell",
        "You are what you do, not what you say you'll do. — C.G. Jung",
        "Every accomplishment starts with the decision to try. — John F. Kennedy",
        "It always seems impossible until it's done. — Nelson Mandela",
        "The way to get started is to quit talking and begin doing. — Walt Disney",
        "If you spend too much time thinking about a thing, you'll never get it done. — Bruce Lee",
        "Make it simple, but significant. — Don Draper",
        "Success is the product of daily habits—not once-in-a-lifetime transformations.",
        "A year from now you may wish you had started today. — Karen Lamb",
        "You do not rise to the level of your goals. You fall to the level of your systems. — James Clear",
        "The secret to getting ahead is getting started. — Sally Berger",
        "Work hard in silence, let your success be your noise. — Frank Ocean",
        "Done is better than perfect. — Sheryl Sandberg",
        "Your habits shape your future more than your mood ever will.",
    ]
    return random.choice(quotes)


def progress_bar(percent: float) -> str:
    percent = max(0.0, min(1.0, percent))
    width = 40
    filled = int(percent * width)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {percent:.0%}"


# ── config & management ──

def show_inline_status(
    time_remaining: int,
    mode: str,
    pomodoro_count: int,
) -> str:
    mode_label = mode.upper().replace("_", " ")
    return (
        f"  {mode_label}  |  "
        f"{format_time(time_remaining)}  |  "
        f"Pomodoro {pomodoro_count}"
    )


def _handle_configuration() -> None:
    cfg = load_config()

    console.print()
    table = Table(title="Current Configuration", show_lines=True, box=None)
    table.add_column("Section", style="bold cyan")
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("general", "mode", cfg.general.mode)
    table.add_row("general", "strict", str(cfg.general.strict))
    table.add_row("general", "autostart", str(cfg.general.autostart))
    table.add_row("general", "confirmation_phrase", cfg.general.confirmation_phrase)
    table.add_row("pomodoro", "work_minutes", str(cfg.pomodoro.work_minutes))
    table.add_row(
        "pomodoro", "short_break_minutes", str(cfg.pomodoro.short_break_minutes)
    )
    table.add_row(
        "pomodoro", "long_break_minutes", str(cfg.pomodoro.long_break_minutes)
    )
    table.add_row(
        "pomodoro", "long_break_after", str(cfg.pomodoro.long_break_after)
    )
    table.add_row("daily", "enabled", str(cfg.daily.enabled))
    table.add_row("daily", "goal_hours", str(cfg.daily.goal_hours))
    table.add_row("display", "dim_brightness", str(cfg.display.dim_brightness))
    table.add_row(
        "display", "brightness_percent", str(cfg.display.brightness_percent)
    )
    table.add_row("display", "dark_mode", str(cfg.display.dark_mode))
    table.add_row("blocking", "domains", f"{len(cfg.blocking.domains)} domains")
    table.add_row("blocking", "apps", f"{len(cfg.blocking.apps)} apps")

    console.print(table)

    console.print()
    console.print("[dim]Edit ~/.config/focus/config.toml to change settings.[/]")


def _handle_autostart_toggle() -> None:
    cfg = load_config()
    cfg.general.autostart = not cfg.general.autostart
    save_config(cfg)
    status = "ON" if cfg.general.autostart else "OFF"
    console.print(f"[green]Autostart set to {status}.[/]")


def _handle_manage_apps() -> None:
    """Show all installed apps and let the user pick which ones to block.

    Uses a prompt_toolkit full-screen Application that redraws the page in
    place (like htop). Colours use ansi* tokens so they emit the same codes
    as the Rich menu (bold cyan numbers, dim hints, green markers).
    """
    cfg = load_config()
    apps = applist.get_app_list()
    if not apps:
        console.print("[dim]No applications detected.[/]")
        return

    display_apps = apps
    blocked = set(cfg.blocking.apps)
    allowed = set(cfg.blocking.allowed_apps) | applist.ESSENTIAL_APPS

    pages = [display_apps[i:i + 20] for i in range(0, len(display_apps), 20)] or [[]]
    state = {"page": 0, "status": ""}

    def page_body_fragments() -> list[tuple[str, str]]:
        frags: list[tuple[str, str]] = [("", "\n")]
        start = state["page"] * 20
        for i, app in enumerate(pages[state["page"]], start + 1):
            marker = "●" if app["key"] in blocked else "○"
            mark_style = "ansigreen" if app["key"] in blocked else "dim"
            src = {"desktop": "app", "flatpak": "flatpak", "package": "pkg"}.get(app["source"], "app")
            ess = "  (essential)" if app["essential"] else ""
            frags.append((mark_style, f"  {marker}  "))
            frags.append(("bold ansicyan", f"{i:>3}."))
            frags.append(("", f"  {app['name'][:26]:<28} "))
            frags.append(("dim", f"({app['key']}) [ {src} ]"))
            frags.append(("dim", f"{ess}\n"))
        return frags

    header_ctrl = FormattedTextControl(
        lambda: [
            ("bold ansicyan", f" ❯ Manage Blocked Apps  "),
            ("", f"Page {state['page'] + 1}/{len(pages)}"),
            ("dim", "   ← → page · number = toggle · a = all · c = clear · q = quit"),
            ("bold ansigreen", f"   [{len(blocked)} blocked]"),
        ]
    )
    body_ctrl = FormattedTextControl(lambda: page_body_fragments())
    status_ctrl = FormattedTextControl(lambda: [("bold ansicyan", state["status"])])

    input_buffer = Buffer()

    kb = KeyBindings()

    @kb.add(Keys.Right)
    def _(event: Any) -> None:
        if state["page"] < len(pages) - 1:
            state["page"] += 1
        event.app.invalidate()

    @kb.add(Keys.Left)
    def _(event: Any) -> None:
        if state["page"] > 0:
            state["page"] -= 1
        event.app.invalidate()

    @kb.add("c-c")
    def _(event: Any) -> None:
        event.app.exit()

    @kb.add("enter")
    def _(event: Any) -> None:
        cmd = input_buffer.text.strip().lower()
        input_buffer.text = ""
        if not cmd or cmd == "q":
            event.app.exit()
            return
        if cmd in ("a",):
            n = 0
            for app in display_apps:
                if app["key"] not in allowed and app["key"] not in applist.ESSENTIAL_APPS:
                    blocked.add(app["key"])
                    n += 1
            state["status"] = f"Marked {n} apps for blocking."
        elif cmd in ("c",):
            blocked.clear()
            state["status"] = "Cleared block list."
        else:
            for tok in cmd.split():
                if tok.isdigit():
                    idx = int(tok)
                    if 1 <= idx <= len(display_apps):
                        key = display_apps[idx - 1]["key"]
                        if key in allowed or key in applist.ESSENTIAL_APPS:
                            state["status"] = f"'{key}' is essential/allowed, can't block."
                        elif key in blocked:
                            blocked.discard(key)
                            state["status"] = f"Unblocked {key}."
                        else:
                            blocked.add(key)
                            state["status"] = f"Blocked {key}."
                    break
        event.app.invalidate()

    layout = HSplit([
        Window(content=header_ctrl, height=1),
        Window(content=body_ctrl, always_hide_cursor=True),
        Window(content=status_ctrl, height=1),
        Window(content=BufferControl(buffer=input_buffer), height=1, wrap_lines=False),
    ])

    app = Application(
        layout=Layout(layout),
        key_bindings=kb,
        full_screen=True,
        mouse_support=False,
    )
    app.run()

    cfg.blocking.apps = sorted(blocked)
    save_config(cfg)
    console.print()
    console.print(f"[green]Saved. {len(blocked)} app(s) will be blocked during sessions.[/]")
    applist.update_snapshot()
