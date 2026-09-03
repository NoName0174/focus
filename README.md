# focus

Study mode for Linux — block distractions, silence notifications, and track
focus sessions. Designed to be hard to quit once a session starts.

## Features

| Feature | What it does |
|---------|-------------|
| App blocking | chmod-000s chosen apps (terminals, settings always exempt) |
| Website blocking | blacklists distracting sites via `/etc/hosts` |
| Notification silence | mutes desktop notifications (dunst) for the session |
| Focus mode | dims screen + switches to dark theme, restored afterwards |
| Pomodoro | work / short-break / long-break cycles with configurable lengths |
| Session queue | stack tasks with durations, runs them in order |
| Stats | daily JSON stats + a rich dashboard (`focus stats`) |
| Strict mode | requires a confirmation phrase to stop early |
| Process protection | runs as a systemd service so blocking survives window close |

Launch with no arguments to open the interactive TUI menu:

```
 1. Start Focus Session
 2. Session Queue
 3. Stats Dashboard
 4. Manage Blocked Apps
 5. Configuration
 6. Autostart Toggle
 7. Quit
```

## Requirements

- Python 3.11+
- Arch (pacman), Debian (dpkg), or Fedora — package detection adapts
- GNOME (`gsettings`) for display dimming, `dunst` for notifications
- `sudo` — used only for `/etc/hosts` and app chmod (prompted via your system)

Install Python deps (PEP 668 distros):

```bash
pip install --user --break-system-packages rich prompt_toolkit
```

## Install

```bash
git clone https://github.com/NoName0174/focus.git
cd focus
pip install -e . --break-system-packages
```

## Usage

```
focus                        # interactive TUI menu
focus start 45              # 45-min session
focus start 90m             # 90-min session
focus start 2h              # 2-hour session
focus stop                  # end the running session
focus stats                 # stats dashboard
focus queue add "math" 45m  # queue a task
focus queue list
focus queue clear
focus config                # show current config
focus setup                 # first-run wizard
focus autostart on          # start a session on login
focus uninstall             # remove focus
```

Session durations accept seconds too (`focus start 90s`), and the TUI queue
supports sub-pomodoro lengths.

## Config

`~/.config/focus/config.toml`:

```toml
[general]
autostart = "on"

[blocking]
apps = ["firefox", "discord"]
allowed_apps = ["kitty"]

[pomodoro]
work_minutes = 25
short_break_minutes = 5
long_break_minutes = 15
```

The first-run wizard (`focus setup`) walks through picking apps, blocking
sites, and pomodoro lengths. Newly installed apps are detected and offered
for blocking on menu launch.

## How it works

1. `focus start` triggers sudo (via your system prompt, cached for the session)
2. Escalates to block chosen apps (chmod 000) + sites (/etc/hosts)
3. Dims the screen, forces dark theme, silences notifications
4. Runs the pomodoro timer; updates stats on completion
5. On end: restores brightness, theme, notifications, and unblocks everything
6. The systemd service (`focus.service`) keeps the blockers applied even if
   the terminal window is closed

## Notes

- Essential apps (terminals, file managers, settings) are never blocked
- Blocking works by chmod'ing the binary, so only real executables appear in
  the picker — libraries and daemons are skipped automatically
- To force-quit early you must type the stop phrase (or disable strict mode)
- Config and stats live under `~/.config/focus/`
