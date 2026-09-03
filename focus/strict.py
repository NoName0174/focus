import os
import subprocess

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style


dim_style = Style.from_dict({"dim": "ansibrightblack"})


def is_sudo_cached() -> bool:
    result = subprocess.run(
        ["sudo", "-n", "true"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def validate_sudo() -> bool:
    """Ensure sudo access is available/cached using the system's native prompt."""
    if is_sudo_cached():
        return True
    # `sudo -v` shows the system prompt (e.g. fingerprint / password) and caches creds.
    result = subprocess.run(["sudo", "-v"])
    return result.returncode == 0


def prompt_sudo_password() -> bool:
    """Use the system's native sudo prompt (no custom prompt_toolkit input)."""
    if is_sudo_cached():
        return True
    result = subprocess.run(["sudo", "-v"])
    return result.returncode == 0


def prompt_confirmation_phrase(phrase: str) -> bool:
    session = PromptSession(
        style=dim_style,
    )
    user_input = session.prompt(
        f"Type '{phrase}' to confirm: ",
    )
    return user_input == phrase


def verify_strict_stop(confirmation_phrase: str) -> bool:
    if os.getuid() != 0:
        if not prompt_sudo_password():
            return False

    return prompt_confirmation_phrase(confirmation_phrase)


def check_strict_mode(strict_enabled: bool, confirmation_phrase: str) -> bool:
    if not strict_enabled:
        return True

    return verify_strict_stop(confirmation_phrase)
