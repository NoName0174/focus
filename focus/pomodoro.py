from dataclasses import dataclass


@dataclass
class PomodoroConfig:
    work_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 20
    long_break_after: int = 4


@dataclass
class PomodoroState:
    current_pomodoro: int = 0
    total_pomodoros: int = 0
    is_break: bool = False
    break_is_long: bool = False
    time_remaining_seconds: int = 0
    total_work_seconds: int = 0


def create_pomodoro_timer(config: PomodoroConfig) -> PomodoroState:
    return PomodoroState(
        current_pomodoro=0,
        total_pomodoros=0,
        is_break=False,
        break_is_long=False,
        time_remaining_seconds=config.work_minutes * 60,
        total_work_seconds=0,
    )


def tick(state: PomodoroState, elapsed_seconds: int = 1) -> PomodoroState:
    return PomodoroState(
        current_pomodoro=state.current_pomodoro,
        total_pomodoros=state.total_pomodoros,
        is_break=state.is_break,
        break_is_long=state.break_is_long,
        time_remaining_seconds=max(0, state.time_remaining_seconds - elapsed_seconds),
        total_work_seconds=state.total_work_seconds + (0 if state.is_break else elapsed_seconds),
    )


def is_completed(state: PomodoroState) -> bool:
    return state.time_remaining_seconds <= 0


def advance(state: PomodoroState, config: PomodoroConfig) -> PomodoroState:
    if not state.is_break:
        current_pomodoro = state.current_pomodoro + 1
        total_pomodoros = state.total_pomodoros + 1
        total_work_seconds = state.total_work_seconds

        if current_pomodoro >= config.long_break_after:
            return PomodoroState(
                current_pomodoro=0,
                total_pomodoros=total_pomodoros,
                is_break=True,
                break_is_long=True,
                time_remaining_seconds=config.long_break_minutes * 60,
                total_work_seconds=total_work_seconds,
            )

        return PomodoroState(
            current_pomodoro=current_pomodoro,
            total_pomodoros=total_pomodoros,
            is_break=True,
            break_is_long=False,
            time_remaining_seconds=config.short_break_minutes * 60,
            total_work_seconds=total_work_seconds,
        )

    return PomodoroState(
        current_pomodoro=state.current_pomodoro,
        total_pomodoros=state.total_pomodoros,
        is_break=False,
        break_is_long=False,
        time_remaining_seconds=config.work_minutes * 60,
        total_work_seconds=state.total_work_seconds,
    )


def get_current_phase(state: PomodoroState) -> str:
    if not state.is_break:
        return "work"
    return "long_break" if state.break_is_long else "short_break"


def format_time(seconds: int) -> str:
    if seconds < 0:
        seconds = 0
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def get_progress(state: PomodoroState, config: PomodoroConfig) -> float:
    phase = get_current_phase(state)
    if phase == "work":
        total = config.work_minutes * 60
    elif phase == "long_break":
        total = config.long_break_minutes * 60
    else:
        total = config.short_break_minutes * 60

    if total == 0:
        return 1.0

    return (total - state.time_remaining_seconds) / total


def get_session_summary(state: PomodoroState) -> str:
    total_seconds = state.total_work_seconds
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    time_parts: list[str] = []
    if hours > 0:
        time_parts.append(f"{hours}h")
    if minutes > 0 or not time_parts:
        time_parts.append(f"{minutes}m")
    time_str = " ".join(time_parts)

    count = state.total_pomodoros
    noun = "pomodoro" if count == 1 else "pomodoros"
    return f"{count} {noun} completed ({time_str} focus time)"
