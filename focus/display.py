import os
import glob
import subprocess
from pathlib import Path

BACKUP_DIR = Path.home() / ".config" / "focus"
BACKUP_FILE = BACKUP_DIR / ".brightness_backup"
THEME_BACKUP_FILE = BACKUP_DIR / ".theme_backup"
COLOR_SCHEME_BACKUP_FILE = BACKUP_DIR / ".color_scheme_backup"

DESKTOP_PROCESS_MAP: dict[str, list[str]] = {
    "gnome": ["gnome-shell", "gnome-session"],
    "kde": ["plasmashell", "plasma-desktop"],
    "xfce": ["xfce4-session"],
    "cinnamon": ["cinnamon", "cinnamon-session"],
    "mate": ["mate-session", "mate-panel"],
}


def detect_de() -> str:
    xdg = os.environ.get("XDG_CURRENT_DESKTOP", "").strip().lower()
    if xdg:
        for name in DESKTOP_PROCESS_MAP:
            if name in xdg:
                return name
        if "kde" in xdg or "plasma" in xdg:
            return "kde"

    session = os.environ.get("DESKTOP_SESSION", "").strip().lower()
    if session:
        for name in DESKTOP_PROCESS_MAP:
            if name in session:
                return name

    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            lower = line.lower()
            for de, procs in DESKTOP_PROCESS_MAP.items():
                for proc in procs:
                    if proc in lower:
                        return de
    except (subprocess.SubprocessError, OSError):
        pass

    return "unknown"


def get_brightness() -> int:
    try:
        result = subprocess.run(
            ["brightnessctl", "get"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            current = int(result.stdout.strip())
            result_max = subprocess.run(
                ["brightnessctl", "max"], capture_output=True, text=True, timeout=5
            )
            if result_max.returncode == 0:
                maximum = int(result_max.stdout.strip())
                if maximum > 0:
                    return max(0, min(100, round(current * 100 / maximum)))
    except (subprocess.SubprocessError, OSError, ValueError):
        pass

    try:
        files = glob.glob("/sys/class/backlight/*/brightness")
        max_files = glob.glob("/sys/class/backlight/*/max_brightness")
        if files and max_files:
            with open(files[0]) as f:
                current = int(f.read().strip())
            with open(max_files[0]) as f:
                maximum = int(f.read().strip())
            if maximum > 0:
                return max(0, min(100, round(current * 100 / maximum)))
    except (OSError, ValueError):
        pass

    return -1


def set_brightness(percent: int) -> None:
    percent = max(0, min(100, percent))

    try:
        result = subprocess.run(
            ["brightnessctl", "set", f"{percent}%"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return
    except (subprocess.SubprocessError, OSError):
        pass

    try:
        result = subprocess.run(
            ["xrandr", "--verbose"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            output = None
            for line in result.stdout.splitlines():
                if " connected" in line:
                    output = line.split()[0]
                    break
            if output:
                brightness_value = percent / 100
                result2 = subprocess.run(
                    [
                        "xrandr", "--output", output,
                        "--brightness", str(brightness_value),
                    ],
                    capture_output=True, text=True, timeout=5,
                )
                if result2.returncode == 0:
                    return
    except (subprocess.SubprocessError, OSError):
        pass

    raise RuntimeError("Unable to set brightness: no supported method found")


def dim_screen(dim: bool, target_percent: int = 30) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if dim:
        current = get_brightness()
        if current >= 0:
            BACKUP_FILE.write_text(str(current))
        set_brightness(target_percent)
    else:
        if BACKUP_FILE.exists():
            try:
                original = int(BACKUP_FILE.read_text().strip())
                set_brightness(original)
            except ValueError:
                pass
            finally:
                BACKUP_FILE.unlink(missing_ok=True)


def is_dimmed() -> bool:
    return BACKUP_FILE.exists()


def enable_dark_mode(de: str) -> None:
    _backup_theme(de)
    _backup_color_scheme(de)

    if de == "gnome":
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "prefer-dark"],
            capture_output=True, timeout=5,
        )
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", "Adwaita-dark"],
            capture_output=True, timeout=5,
        )
    elif de == "kde":
        subprocess.run(
            [
                "kwriteconfig5", "--file", "kdeglobals",
                "--group", "General", "--key", "ColorScheme",
                "--type", "string", "BreezeDark",
            ],
            capture_output=True, timeout=5,
        )
        subprocess.run(
            [
                "kwriteconfig5", "--file", "kdeglobals",
                "--group", "General", "--key", "Name",
                "--type", "string", "Breeze Dark",
            ],
            capture_output=True, timeout=5,
        )
        subprocess.run(
            [
                "qdbus", "org.kde.kglobalaccel",
                "/component/kglobalaccel", "loadConfiguration",
            ],
            capture_output=True, timeout=5,
        )
    elif de == "xfce":
        subprocess.run(
            [
                "xfconf-query", "-c", "xsettings",
                "-p", "/Net/ThemeName", "-s", "Adwaita-dark",
            ],
            capture_output=True, timeout=5,
        )
    else:
        os.environ["GTK_THEME"] = "Adwaita:dark"
        _set_gtk_env("Adwaita:dark")


def enable_light_mode(de: str) -> None:
    if de == "gnome":
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", "Adwaita"],
            capture_output=True, timeout=5,
        )
    elif de == "kde":
        subprocess.run(
            [
                "kwriteconfig5", "--file", "kdeglobals",
                "--group", "General", "--key", "ColorScheme",
                "--type", "string", "Breeze",
            ],
            capture_output=True, timeout=5,
        )
        subprocess.run(
            [
                "kwriteconfig5", "--file", "kdeglobals",
                "--group", "General", "--key", "Name",
                "--type", "string", "Breeze",
            ],
            capture_output=True, timeout=5,
        )
        subprocess.run(
            [
                "qdbus", "org.kde.kglobalaccel",
                "/component/kglobalaccel", "loadConfiguration",
            ],
            capture_output=True, timeout=5,
        )
    elif de == "xfce":
        subprocess.run(
            [
                "xfconf-query", "-c", "xsettings",
                "-p", "/Net/ThemeName", "-s", "Adwaita",
            ],
            capture_output=True, timeout=5,
        )
    else:
        _restore_gtk_env()

    _restore_theme(de)
    _restore_color_scheme(de)


def is_dark_mode(de: str) -> bool:
    if de == "gnome":
        try:
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True, text=True, timeout=5,
            )
            return "prefer-dark" in result.stdout
        except (subprocess.SubprocessError, OSError):
            return False

    if de == "kde":
        try:
            result = subprocess.run(
                [
                    "kreadconfig5", "--file", "kdeglobals",
                    "--group", "General", "--key", "ColorScheme",
                ],
                capture_output=True, text=True, timeout=5,
            )
            return "dark" in result.stdout.lower()
        except (subprocess.SubprocessError, OSError):
            return False

    if de == "xfce":
        try:
            result = subprocess.run(
                [
                    "xfconf-query", "-c", "xsettings",
                    "-p", "/Net/ThemeName",
                ],
                capture_output=True, text=True, timeout=5,
            )
            return "dark" in result.stdout.lower()
        except (subprocess.SubprocessError, OSError):
            return False

    theme = os.environ.get("GTK_THEME", "")
    return "dark" in theme.lower()


def apply_study_display(dim: bool = True, dark: bool = True, brightness_percent: int = 30) -> None:
    de = detect_de()
    if dim:
        dim_screen(True, target_percent=brightness_percent)
    if dark:
        enable_dark_mode(de)


def restore_display() -> None:
    de = detect_de()
    dim_screen(False)
    enable_light_mode(de)


def _backup_theme(de: str) -> None:
    if THEME_BACKUP_FILE.exists():
        return

    theme_name = _get_current_theme(de)
    if theme_name:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        THEME_BACKUP_FILE.write_text(theme_name)


def _restore_theme(de: str) -> None:
    if not THEME_BACKUP_FILE.exists():
        return

    theme_name = THEME_BACKUP_FILE.read_text().strip()

    if de == "gnome":
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", theme_name],
            capture_output=True, timeout=5,
        )
    elif de == "kde":
        subprocess.run(
            [
                "kwriteconfig5", "--file", "kdeglobals",
                "--group", "General", "--key", "Name",
                "--type", "string", theme_name,
            ],
            capture_output=True, timeout=5,
        )
    elif de == "xfce":
        subprocess.run(
            [
                "xfconf-query", "-c", "xsettings",
                "-p", "/Net/ThemeName", "-s", theme_name,
            ],
            capture_output=True, timeout=5,
        )

    THEME_BACKUP_FILE.unlink(missing_ok=True)


def _get_current_theme(de: str) -> str:
    if de == "gnome":
        try:
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip().strip("'\"")
        except (subprocess.SubprocessError, OSError):
            pass

    if de == "kde":
        try:
            result = subprocess.run(
                [
                    "kreadconfig5", "--file", "kdeglobals",
                    "--group", "General", "--key", "Name",
                ],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            pass

    if de == "xfce":
        try:
            result = subprocess.run(
                ["xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName"],
                capture_output=True, text=True, timeout=5,
            )
            return result.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            pass

    return os.environ.get("GTK_THEME", "")


def _set_gtk_env(theme: str) -> None:
    os.environ["GTK_THEME"] = theme
    profile = Path.home() / ".profile"
    bashrc = Path.home() / ".bashrc"
    env_line = f'export GTK_THEME="{theme}"'

    for rc_file in (profile, bashrc):
        if rc_file.exists():
            try:
                content = rc_file.read_text()
                if "export GTK_THEME=" in content:
                    lines = content.splitlines()
                    new_lines = []
                    for line in lines:
                        if line.strip().startswith("export GTK_THEME="):
                            new_lines.append(env_line)
                        else:
                            new_lines.append(line)
                    rc_file.write_text("\n".join(new_lines) + "\n")
                    return
            except OSError:
                pass

    for rc_file in (profile, bashrc):
        if rc_file.exists():
            try:
                with open(rc_file, "a") as f:
                    f.write(f"\n{env_line}\n")
                return
            except OSError:
                continue


def _restore_gtk_env() -> None:
    theme_backup = THEME_BACKUP_FILE.read_text().strip() if THEME_BACKUP_FILE.exists() else "Adwaita"
    os.environ["GTK_THEME"] = theme_backup
    _set_gtk_env(theme_backup)


def _get_current_color_scheme(de: str) -> str:
    if de != "gnome":
        return ""
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip().strip("'\"")
    except (subprocess.SubprocessError, OSError):
        return ""


def _backup_color_scheme(de: str) -> None:
    if de != "gnome" or COLOR_SCHEME_BACKUP_FILE.exists():
        return
    scheme = _get_current_color_scheme(de)
    if scheme:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        COLOR_SCHEME_BACKUP_FILE.write_text(scheme)


def _restore_color_scheme(de: str) -> None:
    if de != "gnome" or not COLOR_SCHEME_BACKUP_FILE.exists():
        return
    scheme = COLOR_SCHEME_BACKUP_FILE.read_text().strip()
    if scheme:
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", scheme],
            capture_output=True, timeout=5,
        )
    COLOR_SCHEME_BACKUP_FILE.unlink(missing_ok=True)
