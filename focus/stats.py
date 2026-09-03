import json
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table
from rich.text import Text

from .config import load_config

console = Console()

STATS_DIR = Path.home() / ".config" / "focus" / "stats"


def _get_stats_path(target_date: date | None = None) -> Path:
    if target_date is None:
        target_date = date.today()
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    return STATS_DIR / f"{target_date.isoformat()}.json"


def _load_day(target_date: date) -> dict:
    path = _get_stats_path(target_date)
    config = load_config()
    daily_goal_minutes = int(config.daily.goal_hours * 60)

    if not path.exists():
        return {
            "date": target_date.isoformat(),
            "sessions": [],
            "total_minutes": 0,
            "total_pomodoros": 0,
            "daily_goal_minutes": daily_goal_minutes,
            "daily_goal_met": False,
        }

    with open(path, "r") as f:
        data = json.load(f)
    data["daily_goal_minutes"] = daily_goal_minutes
    data["daily_goal_met"] = data["total_minutes"] >= daily_goal_minutes
    return data


def _save_day(data: dict) -> None:
    path = _get_stats_path()
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def start_session(target_minutes: int, blocked_domains: int, blocked_apps: int) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now()

    data = _load_day(now.date())
    data["sessions"].append({
        "id": session_id,
        "start": now.isoformat(timespec="seconds"),
        "end": None,
        "duration_minutes": 0,
        "pomodoros_completed": 0,
        "target_duration_minutes": target_minutes,
        "completed": False,
        "blocked_domains": blocked_domains,
        "blocked_apps": blocked_apps,
    })

    _save_day(data)
    return session_id


def end_session(session_id: str, pomodoros_completed: int) -> None:
    now = datetime.now()
    data = _load_day(now.date())

    for session in data["sessions"]:
        if session["id"] == session_id and not session["completed"]:
            session["end"] = now.isoformat(timespec="seconds")
            start = datetime.fromisoformat(session["start"])
            session["duration_minutes"] = int((now - start).total_seconds() / 60)
            session["pomodoros_completed"] = pomodoros_completed
            session["completed"] = True

            data["total_minutes"] += session["duration_minutes"]
            data["total_pomodoros"] += pomodoros_completed
            data["daily_goal_met"] = data["total_minutes"] >= data["daily_goal_minutes"]

            _save_day(data)
            return


def get_today_stats() -> dict:
    return _load_day(date.today())


def get_stats_range(start_date: str, end_date: str) -> list[dict]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    results: list[dict] = []
    current = start
    while current <= end:
        results.append(_load_day(current))
        current += timedelta(days=1)
    return results


def get_streak() -> int:
    streak = 0
    current = date.today()

    while True:
        data = _load_day(current)
        if not data["daily_goal_met"]:
            break
        streak += 1
        current -= timedelta(days=1)

    return streak


def get_total_stats() -> dict:
    total_minutes = 0
    total_pomodoros = 0
    total_sessions = 0
    days_tracked = 0

    if not STATS_DIR.exists():
        return {
            "total_hours": 0.0,
            "total_pomodoros": 0,
            "total_sessions": 0,
            "average_daily_minutes": 0.0,
        }

    for path in sorted(STATS_DIR.glob("*.json")):
        with open(path, "r") as f:
            data = json.load(f)
        day_minutes = data.get("total_minutes", 0)
        if day_minutes > 0:
            days_tracked += 1
        total_minutes += day_minutes
        total_pomodoros += data.get("total_pomodoros", 0)
        total_sessions += len(data.get("sessions", []))

    avg = total_minutes / days_tracked if days_tracked > 0 else 0.0

    return {
        "total_hours": round(total_minutes / 60, 1),
        "total_pomodoros": total_pomodoros,
        "total_sessions": total_sessions,
        "average_daily_minutes": round(avg, 1),
    }


def get_weekly_average() -> float:
    today = date.today()
    total = 0.0
    days = 0

    for i in range(7):
        d = today - timedelta(days=i)
        data = _load_day(d)
        if data["total_minutes"] > 0:
            total += data["total_minutes"]
            days += 1

    return round(total / 7, 1)


def render_dashboard() -> None:
    today_data = get_today_stats()
    streak = get_streak()
    weekly_avg = get_weekly_average()
    totals = get_total_stats()
    config = load_config()

    goal = today_data["daily_goal_minutes"]
    done = today_data["total_minutes"]
    pct = min(done / goal, 1.0) if goal > 0 else 0.0

    progress = Progress(
        TextColumn("[bold blue]Today"),
        BarColumn(bar_width=40),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn(f"[bold]{done}/{goal}m"),
    )
    task = progress.add_task("progress", total=goal, completed=done)

    stats_items = Text()
    stats_items.append(f"  Streak:       {streak} days\n", style="bold green" if streak > 0 else "dim")
    stats_items.append(f"  Weekly Avg:   {weekly_avg:.0f} min/day\n", style="cyan")
    stats_items.append(f"  Total Hours:  {totals['total_hours']}\n", style="yellow")
    stats_items.append(f"  Sessions:     {totals['total_sessions']}\n", style="magenta")
    stats_items.append(f"  Pomodoros:    {totals['total_pomodoros']}", style="red")

    progress_panel = Panel(progress, title="[bold]Daily Progress", border_style="blue", expand=True)
    stats_panel = Panel(stats_items, title="[bold]All-Time Stats", border_style="yellow", expand=True)

    table = Table(
        title="Recent Sessions (7 days)",
        box=box.ROUNDED,
        show_lines=True,
        title_style="bold",
        header_style="bold cyan",
    )
    table.add_column("Date", style="dim")
    table.add_column("Duration")
    table.add_column("Pomodoros", justify="center")
    table.add_column("Target", justify="center")
    table.add_column("Done", justify="center")

    today = date.today()
    for i in range(7):
        d = today - timedelta(days=i)
        data = _load_day(d)
        for s in data["sessions"]:
            start_str = s["start"][:10] if s["start"] else ""
            dur = f"{s['duration_minutes']}m"
            pom = str(s["pomodoros_completed"])
            tgt = f"{s['target_duration_minutes']}m"
            status = Text.from_markup("[green]✓[/]") if s["completed"] else Text.from_markup("[red]✗[/]")
            table.add_row(start_str, dur, pom, tgt, status)

    console.print()
    console.print(Columns([progress_panel, stats_panel], equal=True, expand=True))
    console.print()
    console.print(table)
    console.print()
