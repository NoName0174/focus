import shutil
import subprocess


def is_dunst_available() -> bool:
    return shutil.which("dunstctl") is not None


def silence_notifications() -> None:
    if not is_dunst_available():
        return
    try:
        subprocess.run(["dunstctl", "set-paused", "true"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


def unsilence_notifications() -> None:
    if not is_dunst_available():
        return
    try:
        subprocess.run(["dunstctl", "set-paused", "false"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


def are_notifications_silenced() -> bool:
    if not is_dunst_available():
        return False
    try:
        result = subprocess.run(
            ["dunstctl", "is-paused"], capture_output=True
        )
        return result.returncode == 0 and result.stdout.strip().lower() == "true"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _find_notify_command() -> str | None:
    if shutil.which("dunstify"):
        return "dunstify"
    if shutil.which("notify-send"):
        return "notify-send"
    return None


def send_notification(summary: str, body: str, urgency: str = "normal") -> None:
    cmd = _find_notify_command()
    if cmd is None:
        return
    args = [cmd]
    if cmd == "dunstify":
        args.extend(["-u", urgency, summary, body])
    else:
        args.extend(["-u", urgency, summary, body])
    try:
        subprocess.run(args, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


def notify_session_start(duration_str: str) -> None:
    send_notification("🎯 Focus session started", duration_str)


def notify_session_end(stats_summary: str) -> None:
    send_notification("✅ Session complete!", stats_summary)


def notify_break_start(break_type: str, duration_str: str) -> None:
    send_notification("☕ Break time!", f"{break_type} — {duration_str}")


def notify_break_end() -> None:
    send_notification("⚡ Back to work!", "Let's continue!")


def notify_pomodoro_complete(count: int, total: int) -> None:
    send_notification(f"🍅 Pomodoro {count}/{total} complete!", "Keep going!")
