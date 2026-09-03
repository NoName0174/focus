import subprocess
from pathlib import Path

SERVICE_NAME = "focus.service"
SERVICE_PATH = Path("/etc/systemd/system/focus.service")

SERVICE_TEMPLATE = """\
[Unit]
Description=Focus Study Mode Service
After=graphical-session.target

[Service]
Type=simple
ExecStart=/bin/bash -c 'while true; do sleep 60; done'
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=default.target
"""


def install_service() -> bool:
    try:
        SERVICE_PATH.write_text(SERVICE_TEMPLATE)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        subprocess.run(["sudo", "systemctl", "enable", SERVICE_NAME], check=True)
        subprocess.run(["sudo", "systemctl", "start", SERVICE_NAME], check=True)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def uninstall_service() -> bool:
    try:
        subprocess.run(["sudo", "systemctl", "stop", SERVICE_NAME], check=False)
        subprocess.run(["sudo", "systemctl", "disable", SERVICE_NAME], check=False)
        if SERVICE_PATH.exists():
            SERVICE_PATH.unlink()
        subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def is_service_running() -> bool:
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "is-active", SERVICE_NAME],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() == "active"
    except (subprocess.CalledProcessError, OSError):
        return False


def is_service_installed() -> bool:
    return SERVICE_PATH.exists()


def get_service_status() -> str:
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "status", SERVICE_NAME],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except OSError:
        return "unable to retrieve status"
