from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from prompt_toolkit import PromptSession

from focus.config import (
    BlockingConfig,
    Config,
    DailyConfig,
    DisplayConfig,
    GeneralConfig,
    PomodoroConfig,
    save_config,
)

console = Console()
_prompt: PromptSession[str] = PromptSession()


def _ask_bool(question: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    raw = _prompt.prompt(f"{question} {suffix} ")
    text = raw.strip().lower()
    if not text:
        return default
    return text in ("y", "yes")


def _ask_int(question: str, default: int) -> int:
    while True:
        raw = _prompt.prompt(f"{question} [dim yellow][{default}][/dim yellow] ")
        text = raw.strip()
        if not text:
            return default
        try:
            value = int(text)
            if value > 0:
                return value
            console.print("[bold red]Please enter a positive number.[/bold red]")
        except ValueError:
            console.print("[bold red]Invalid number, try again.[/bold red]")


def _ask_float(question: str, default: float) -> float:
    while True:
        raw = _prompt.prompt(f"{question} [dim yellow][{default}][/dim yellow] ")
        text = raw.strip()
        if not text:
            return default
        try:
            value = float(text)
            if value > 0:
                return value
            console.print("[bold red]Please enter a positive number.[/bold red]")
        except ValueError:
            console.print("[bold red]Invalid number, try again.[/bold red]")


def _ask_string(question: str, default: str = "") -> str:
    suffix = f" [dim yellow][{default}][/dim yellow]" if default else ""
    raw = _prompt.prompt(f"{question}{suffix} ")
    text = raw.strip()
    if not text and default:
        return default
    return text


def _ask_choice(question: str, options: list[str]) -> int:
    console.print(f"[bold green]{question}[/bold green]")
    for i, option in enumerate(options, 1):
        console.print(f"  [cyan]{i}.[/cyan] {option}")
    console.print()
    while True:
        raw = _prompt.prompt("Choice [1]: ")
        text = raw.strip()
        if not text:
            return 0
        try:
            value = int(text)
            if 1 <= value <= len(options):
                return value - 1
        except ValueError:
            pass
        console.print(f"[bold red]Enter a number between 1 and {len(options)}.[/bold red]")


def _build_config(
    strict: bool,
    phrase: str,
    mode: str,
    extra_domains: str,
    use_pomodoro: bool,
    pomodoro_cfg: PomodoroConfig,
    use_daily: bool,
    daily_hours: float,
    dim_screen: bool,
    autostart: bool,
) -> Config:
    blocking_domains: list[str] = []
    if mode == "blacklist":
        blocking_domains = list(BlockingConfig().domains)
    if extra_domains:
        for d in extra_domains.split(","):
            d = d.strip()
            if d:
                blocking_domains.append(d)

    return Config(
        general=GeneralConfig(
            mode=mode,
            strict=strict,
            confirmation_phrase=phrase,
            autostart=autostart,
        ),
        pomodoro=pomodoro_cfg if use_pomodoro else PomodoroConfig(),
        daily=DailyConfig(enabled=use_daily, goal_hours=daily_hours if use_daily else 4.0),
        blocking=BlockingConfig(domains=blocking_domains),
        display=DisplayConfig(dim_brightness=dim_screen, dark_mode=dim_screen),
    )


def _show_summary(
    strict: bool,
    phrase: str,
    mode: str,
    extra_domains: str,
    use_pomodoro: bool,
    pomodoro_cfg: PomodoroConfig,
    use_daily: bool,
    daily_hours: float,
    dim_screen: bool,
    autostart: bool,
) -> None:
    table = Table(title="Configuration Summary", border_style="green", show_header=False)
    table.add_column("Setting", style="bold")
    table.add_column("Value")

    table.add_row("Strict Mode", "Yes" if strict else "No")
    if strict:
        table.add_row("  Confirmation Phrase", phrase)
    table.add_row("Blocking Mode", mode.capitalize())
    if mode == "whitelist" and extra_domains:
        table.add_row("  Extra Domains", extra_domains)
    table.add_row("Pomodoro", "Yes" if use_pomodoro else "No")
    if use_pomodoro:
        table.add_row("  Work", f"{pomodoro_cfg.work_minutes} min")
        table.add_row("  Short Break", f"{pomodoro_cfg.short_break_minutes} min")
        table.add_row("  Long Break", f"{pomodoro_cfg.long_break_minutes} min")
        table.add_row("  Long Break After", f"{pomodoro_cfg.long_break_after} pomodoros")
    table.add_row("Daily Goal", "Yes" if use_daily else "No")
    if use_daily:
        table.add_row("  Hours/Day", f"{daily_hours}")
    table.add_row("Dim Screen + Dark Mode", "Yes" if dim_screen else "No")
    table.add_row("Autostart", "Yes" if autostart else "No")

    console.print()
    console.print(Panel(table, border_style="green"))


def run_wizard() -> Config:
    console.print()
    console.print(
        Panel(
            "[bold white]Welcome to focus! 🎯[/bold white]",
            border_style="green",
            padding=(1, 2),
        )
    )
    console.print(
        "[dim]A study mode for Linux that blocks distracting websites and apps.\n"
        "Stay on task with optional pomodoro timers, daily goals, and\n"
        "strict mode to keep you honest. Let's set things up.[/dim]"
    )
    console.print()

    console.print("[bold green]--- Strict Mode ---[/bold green]")
    strict = _ask_bool(
        "Enable Strict Mode? (requires sudo + a confirmation phrase to stop a session)"
    )
    phrase = "I am choosing to stop studying"
    if strict:
        phrase = _ask_string("Confirmation phrase to stop a session", phrase)
    console.print()

    console.print("[bold green]--- Blocking Mode ---[/bold green]")
    mode_choice = _ask_choice("How should focus block content?", [
        "Blacklist: Block specific sites/apps (recommended)",
        "Whitelist: Block everything, allow only what I list",
    ])
    mode = "blacklist" if mode_choice == 0 else "whitelist"
    extra_domains = ""
    if mode == "whitelist":
        extra_domains = _ask_string(
            "Allow any specific domains besides defaults? (comma-separated)"
        )
    console.print()

    console.print("[bold green]--- Pomodoro Timer ---[/bold green]")
    use_pomodoro = _ask_bool("Use Pomodoro timer with breaks?")
    pomodoro_cfg = PomodoroConfig()
    if use_pomodoro:
        work = _ask_int("Work minutes", 25)
        short = _ask_int("Short break minutes", 5)
        long = _ask_int("Long break minutes", 20)
        long_after = _ask_int("Long break after how many pomodoros", 4)
        pomodoro_cfg = PomodoroConfig(
            work_minutes=work,
            short_break_minutes=short,
            long_break_minutes=long,
            long_break_after=long_after,
        )
    console.print()

    console.print("[bold green]--- Daily Goal ---[/bold green]")
    use_daily = _ask_bool("Set a daily study goal?")
    daily_hours = 4.0
    if use_daily:
        daily_hours = _ask_float("How many hours per day", 4.0)
    console.print()

    console.print("[bold green]--- Screen Settings ---[/bold green]")
    dim_screen = _ask_bool("Dim screen + enable dark mode during sessions?")
    console.print()

    console.print("[bold green]--- Autostart ---[/bold green]")
    autostart = _ask_bool("Start focus mode automatically when you log in?")
    console.print()

    _show_summary(
        strict, phrase, mode, extra_domains, use_pomodoro, pomodoro_cfg,
        use_daily, daily_hours, dim_screen, autostart,
    )
    console.print()

    if _ask_bool("Save configuration?"):
        config = _build_config(
            strict, phrase, mode, extra_domains, use_pomodoro, pomodoro_cfg,
            use_daily, daily_hours, dim_screen, autostart,
        )
        save_config(config)
        console.print()
        console.print("[bold green]✓ Configuration saved![/bold green]")
    else:
        config = _build_config(
            strict, phrase, mode, extra_domains, use_pomodoro, pomodoro_cfg,
            use_daily, daily_hours, dim_screen, autostart,
        )
        console.print()
        console.print("[dim]Configuration discarded.[/dim]")

    console.print()
    return config
