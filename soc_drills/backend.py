"""
Backend actions for Basic SOC Drills.

Every action funnels through `run_command`, which:
  - checks the underlying tool actually exists before trying to run it
  - respects "Simulation Mode" (dry_run) by only logging the command
  - never uses shell=True (arguments are passed as a list, so there is no
    shell-injection surface even when a field comes from a text entry)
  - captures stdout/stderr and streams it to the on-screen console instead
    of the terminal the old CLI version printed to
  - never hard-codes credentials; add_user() prompts for a password and
    pipes it directly into `chpasswd` instead of putting it on the command
    line (where it would be visible to any other user via `ps`)

`log` is a callable: log(level, message) -> None, e.g. Console.log
"""

from __future__ import annotations

import shutil
import subprocess
import re
from pathlib import Path
from typing import Callable, Optional

Logger = Callable[[str, str], None]

DEFAULT_TIMEOUT = 90


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------
def tool_available(binary: str) -> bool:
    return shutil.which(binary) is not None


def run_command(
    log: Logger,
    dry_run: bool,
    cmd: list[str],
    *,
    needs_root: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
    input_text: Optional[str] = None,
    success_msg: Optional[str] = None,
) -> bool:
    """Run `cmd` (a list, never a shell string) with safety rails."""
    display_cmd = " ".join(cmd)
    binary = cmd[1] if (needs_root and cmd and cmd[0] == "sudo" and len(cmd) > 1) else (cmd[0] if cmd else "")

    if binary and not tool_available(binary):
        log("ERROR", f"'{binary}' is not installed or not on PATH. Install it first (see README).")
        return False

    full_cmd = (["sudo"] + cmd) if (needs_root and (not cmd or cmd[0] != "sudo")) else cmd

    if dry_run:
        log("SIM", f"Would run: {display_cmd}")
        return True

    try:
        result = subprocess.run(
            full_cmd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        log("ERROR", f"Command not found: {display_cmd}")
        return False
    except subprocess.TimeoutExpired:
        log("WARN", f"Timed out after {timeout}s: {display_cmd}")
        return False
    except Exception as exc:  # noqa: BLE001 - surface anything unexpected to the console
        log("ERROR", f"Unexpected failure running '{display_cmd}': {exc}")
        return False

    for line in (result.stdout or "").splitlines():
        log("INFO", line)
    for line in (result.stderr or "").splitlines():
        log("WARN", line)

    if result.returncode == 0:
        log("SUCCESS", success_msg or f"Completed: {display_cmd}")
        return True

    log("ERROR", f"Exited with code {result.returncode}: {display_cmd}")
    return False


# ---------------------------------------------------------------------------
# Network & recon
# ---------------------------------------------------------------------------
def change_mac_address(log: Logger, dry_run: bool, interface: str) -> None:
    interface = interface.strip() or "eth0"
    run_command(
        log, dry_run,
        ["macchanger", "-r", interface],
        success_msg=f"MAC address of {interface} randomized.",
    )


def search_vulnerabilities(log: Logger, dry_run: bool, target: str) -> None:
    target = target.strip()
    if not target:
        log("ERROR", "Enter a target host/IP/CIDR before scanning.")
        return
    run_command(
        log, dry_run,
        ["nmap", "-sV", target],
        timeout=300,
        success_msg=f"Vulnerability scan of {target} finished.",
    )


def start_intrusion_detection(log: Logger, dry_run: bool, interface: str) -> Optional[subprocess.Popen]:
    """Starts Suricata in the foreground. Returns the Popen handle so the GUI
    can stop it later, or None if it wasn't started (e.g. dry run / missing)."""
    interface = interface.strip() or "eth0"
    cmd = ["suricata", "-c", "/etc/suricata/suricata.yaml", "-i", interface]
    if dry_run:
        log("SIM", f"Would run: sudo {' '.join(cmd)} (foreground IDS/IPS)")
        return None
    if not tool_available("suricata"):
        log("ERROR", "'suricata' is not installed. Run: sudo apt install suricata")
        return None
    try:
        proc = subprocess.Popen(
            ["sudo"] + cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        log("SUCCESS", f"Suricata IDS/IPS starting on {interface}...")
        return proc
    except Exception as exc:  # noqa: BLE001
        log("ERROR", f"Failed to start Suricata: {exc}")
        return None


def stop_intrusion_detection(log: Logger, dry_run: bool) -> None:
    run_command(
        log, dry_run,
        ["pkill", "-f", "suricata -c"],
        success_msg="Suricata IDS/IPS stopped.",
    )


def tail_suricata_alerts(log: Logger, dry_run: bool, log_path: str, lines: int = 50) -> None:
    log_path = log_path.strip() or "/var/log/suricata/fast.log"
    if not dry_run and not Path(log_path).exists():
        log("ERROR", f"No Suricata log found at {log_path} yet.")
        return
    run_command(
        log, dry_run,
        ["tail", "-n", str(lines), log_path],
        needs_root=False,
        success_msg="Fetched recent Suricata alerts.",
    )


# ---------------------------------------------------------------------------
# System hygiene
# ---------------------------------------------------------------------------
def clear_caches(log: Logger, dry_run: bool) -> None:
    if not run_command(log, dry_run, ["apt-get", "clean"], success_msg="Package cache cleaned."):
        return
    run_command(log, dry_run, ["apt-get", "autoremove", "-y"], success_msg="Unused packages removed.")


def update_antivirus(log: Logger, dry_run: bool) -> None:
    run_command(log, dry_run, ["freshclam"], success_msg="ClamAV definitions updated.")


def log_management(log: Logger, dry_run: bool, config_path: str) -> None:
    config_path = config_path.strip() or "/etc/logrotate.conf"
    run_command(
        log, dry_run,
        ["logrotate", "-f", config_path],
        success_msg="Log rotation forced successfully.",
    )


def backup_and_recovery(log: Logger, dry_run: bool, source: str, destination: str) -> None:
    source = source.strip()
    destination = destination.strip()
    if not source or not destination:
        log("ERROR", "Both a source and destination path are required for backup.")
        return
    run_command(
        log, dry_run,
        ["rsync", "-av", source, destination],
        needs_root=False,
        timeout=600,
        success_msg=f"Backup of {source} -> {destination} complete.",
    )


# ---------------------------------------------------------------------------
# Threat intel / detection / compliance
# ---------------------------------------------------------------------------
def threat_intelligence_pull(log: Logger, dry_run: bool, feed_url: str) -> None:
    feed_url = feed_url.strip()
    if not feed_url:
        log("ERROR", "Enter a threat-feed URL first (configure your provider in the Threat Intel tab).")
        return
    run_command(
        log, dry_run,
        ["curl", "-s", "--max-time", "20", feed_url],
        needs_root=False,
        timeout=30,
        success_msg="Threat intelligence feed retrieved.",
    )


def security_event_correlation(log: Logger, dry_run: bool) -> None:
    run_command(
        log, dry_run,
        ["ossec-logtest"],
        input_text="",
        success_msg="Security event correlation pass complete.",
    )


def user_behavior_analytics(log: Logger, dry_run: bool) -> None:
    run_command(
        log, dry_run,
        ["ausearch", "-m", "USER_LOGIN"],
        success_msg="User login audit trail retrieved.",
    )


def compliance_monitoring(log: Logger, dry_run: bool) -> None:
    run_command(
        log, dry_run,
        ["lynis", "audit", "system", "--quiet"],
        timeout=900,
        success_msg="Compliance / hardening audit complete. See /var/log/lynis.log for the full report.",
    )


def security_awareness_training(log: Logger, dry_run: bool, path: str) -> None:
    path = path.strip() or "/usr/share/security-training/index.html"
    if dry_run:
        log("SIM", f"Would open training material: {path}")
        return
    if not Path(path).exists():
        log("ERROR", f"Training material not found at {path}. Set the correct path in the Training tab.")
        return
    run_command(log, False, ["xdg-open", path], needs_root=False, success_msg="Training material opened.")


def check_uploads(log: Logger, dry_run: bool, upload_dir: str) -> None:
    upload_dir = upload_dir.strip() or "/var/www/html/uploads"
    if not dry_run and not Path(upload_dir).exists():
        log("ERROR", f"Directory does not exist: {upload_dir}")
        return
    run_command(
        log, dry_run,
        ["find", upload_dir, "-type", "f"],
        needs_root=False,
        success_msg=f"Listed files under {upload_dir}.",
    )


def monitor_system_events(log: Logger, dry_run: bool, lines: int = 200) -> None:
    run_command(
        log, dry_run,
        ["journalctl", "-n", str(lines), "--no-pager"],
        success_msg="Recent system events retrieved.",
    )


def suggest_defense_implementations(log: Logger, dry_run: bool) -> None:
    if dry_run:
        log("SIM", "Would run: lscpu / free -h / df -h and print hardening recommendations.")
        return
    for label, cmd in (("CPU", ["lscpu"]), ("Memory", ["free", "-h"]), ("Disk", ["df", "-h"])):
        try:
            output = subprocess.check_output(cmd, text=True, timeout=15)
            log("INFO", f"--- {label} ---")
            for line in output.splitlines():
                log("INFO", line)
        except Exception as exc:  # noqa: BLE001
            log("WARN", f"Could not read {label} info: {exc}")

    log("SUCCESS", "System specs collected.")
    for tip in (
        "Keep the system patched with the latest security updates.",
        "Run a firewall (ufw / iptables) with a default-deny inbound policy.",
        "Schedule regular backups and actually test restoring them.",
        "Enforce strong passwords and multi-factor authentication.",
        "Run an IDS/IPS (e.g. Suricata) and review alerts routinely.",
    ):
        log("INFO", f"  - {tip}")


# ---------------------------------------------------------------------------
# Incident response
# ---------------------------------------------------------------------------
_SERVICE_NAME_RE = re.compile(r"^[a-zA-Z0-9_.@-]+$")
_IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}(/\d{1,2})?$")


def incident_response_restart_service(log: Logger, dry_run: bool, service: str) -> None:
    service = service.strip()
    if not service or not _SERVICE_NAME_RE.match(service):
        log("ERROR", "Enter a valid systemd service name, e.g. 'nginx' or 'apache2'.")
        return
    run_command(
        log, dry_run,
        ["systemctl", "restart", service],
        success_msg=f"Service '{service}' restarted.",
    )


def quarantine_interactions(log: Logger, dry_run: bool, ip: str) -> None:
    ip = ip.strip()
    if not ip or not _IP_RE.match(ip):
        log("ERROR", "Enter a valid IPv4 address or CIDR to quarantine, e.g. 192.168.1.100.")
        return
    run_command(
        log, dry_run,
        ["ufw", "deny", "from", ip],
        success_msg=f"Traffic from {ip} is now denied.",
    )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------
_USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")


def add_user(log: Logger, dry_run: bool, username: str, password: str) -> None:
    username = username.strip()
    if not username or not _USERNAME_RE.match(username):
        log("ERROR", "Invalid username. Use lowercase letters, numbers, - or _, starting with a letter/underscore.")
        return
    if not password:
        log("ERROR", "A password is required.")
        return

    if dry_run:
        log("SIM", f"Would run: sudo useradd -m -s /bin/bash {username}")
        log("SIM", f"Would set a password for '{username}' via chpasswd (never shown in the console).")
        return

    if not run_command(
        log, False,
        ["useradd", "-m", "-s", "/bin/bash", username],
        success_msg=f"User '{username}' created.",
    ):
        return

    # Password is piped straight into chpasswd's stdin so it never appears
    # on the command line / in `ps` output / in the on-screen log.
    run_command(
        log, False,
        ["chpasswd"],
        input_text=f"{username}:{password}\n",
        success_msg=f"Password set for '{username}'.",
    )


def remove_user(log: Logger, dry_run: bool, username: str) -> None:
    username = username.strip()
    if not username or not _USERNAME_RE.match(username):
        log("ERROR", "Invalid username.")
        return
    run_command(
        log, dry_run,
        ["userdel", "-r", username],
        success_msg=f"User '{username}' removed.",
    )
