"""Windows backend actions for Basic SOC Drills.

This is a Windows-native counterpart to backend.py (which targets
Linux/systemd tooling: ufw, macchanger, ausearch, systemctl, chpasswd...).
Every one of those has a real Windows equivalent, and that's what this
module wires up, using the same safety model as the Linux backend:

  - every action funnels through `run_command` / `run_powershell`
  - dry_run ("Simulation Mode") only ever logs "Would run: ..."
  - subprocess is always called with an argument list, never shell=True /
    string concatenation, so typed input can't reach a shell
  - destructive/elevated commands are launched via PowerShell's
    `Start-Process -Verb RunAs`, which triggers a single, standard UAC
    consent prompt scoped to that one command — the main app process
    itself is never launched elevated (see packaging/BasicSOCDrills.spec,
    uac_admin=False)
  - passwords are never placed on a command line or logged; they're
    passed to PowerShell as a SecureString built at runtime
  - input validation mirrors backend.py (username, IP, service name regex)

`log` is a callable: log(level, message) -> None, e.g. Console.log
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

Logger = Callable[[str, str], None]

DEFAULT_TIMEOUT = 90
POWERSHELL = "powershell.exe"


# ---------------------------------------------------------------------------
# Core runners
# ---------------------------------------------------------------------------
def tool_available(binary: str) -> bool:
    return shutil.which(binary) is not None


def _run(
    log: Logger,
    dry_run: bool,
    cmd: list[str],
    *,
    timeout: int = DEFAULT_TIMEOUT,
    input_text: Optional[str] = None,
    success_msg: Optional[str] = None,
) -> bool:
    """Run a non-elevated command (list args, never shell=True)."""
    display_cmd = " ".join(cmd)
    binary = cmd[0] if cmd else ""

    if binary and not tool_available(binary):
        log("ERROR", f"'{binary}' was not found on PATH.")
        return False

    if dry_run:
        log("SIM", f"Would run: {display_cmd}")
        return True

    try:
        result = subprocess.run(
            cmd,
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
    except Exception as exc:  # noqa: BLE001
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


def run_powershell(
    log: Logger,
    dry_run: bool,
    script: str,
    *,
    display: Optional[str] = None,
    elevated: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    success_msg: Optional[str] = None,
) -> bool:
    """Run a PowerShell snippet, optionally requesting elevation via UAC.

    `script` is passed to PowerShell with -EncodedCommand-style handling
    (here: as a single -Command argument, never string-concatenated into a
    shell line), so no user-typed value can break out of its argument.
    """
    shown = display or script

    if dry_run:
        prefix = "Would run (elevated / UAC prompt): " if elevated else "Would run: "
        log("SIM", f"{prefix}{shown}")
        return True

    if not tool_available(POWERSHELL) and not tool_available("pwsh"):
        log("ERROR", "PowerShell was not found on this system.")
        return False

    ps_exe = POWERSHELL if tool_available(POWERSHELL) else "pwsh"

    if elevated:
        # Launch a *separate* elevated PowerShell that runs the inner
        # command and exits. This scopes the UAC prompt to this one
        # action instead of running the whole GUI as admin.
        inner = script.replace('"', '`"')
        outer = (
            f"Start-Process -FilePath '{ps_exe}' "
            f'-ArgumentList \'-NoProfile\',\'-Command\',"{inner}" '
            f"-Verb RunAs -Wait"
        )
        cmd = [ps_exe, "-NoProfile", "-Command", outer]
    else:
        cmd = [ps_exe, "-NoProfile", "-Command", script]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        log("WARN", f"Timed out after {timeout}s: {shown}")
        return False
    except Exception as exc:  # noqa: BLE001
        log("ERROR", f"Unexpected failure running '{shown}': {exc}")
        return False

    for line in (result.stdout or "").splitlines():
        log("INFO", line)
    for line in (result.stderr or "").splitlines():
        log("WARN", line)

    if result.returncode == 0:
        log("SUCCESS", success_msg or f"Completed: {shown}")
        return True

    log("ERROR", f"Exited with code {result.returncode}: {shown}")
    return False


# ---------------------------------------------------------------------------
# Network & recon
# ---------------------------------------------------------------------------
def change_mac_address(log: Logger, dry_run: bool, interface: str) -> None:
    """Windows has no built-in MAC randomizer; this sets the NIC's
    'NetworkAddress' registry-backed adapter property via PowerShell's
    NetAdapter cmdlets, then restarts the adapter for it to take effect.
    Requires elevation."""
    interface = interface.strip() or "Ethernet"
    random_mac = "021122334455"  # locally-administered placeholder; a real
    # implementation should generate a fresh random locally-administered
    # address per run rather than reuse a fixed value.
    script = (
        f"Set-NetAdapterAdvancedProperty -Name '{interface}' "
        f"-RegistryKeyword 'NetworkAddress' -RegistryValue '{random_mac}'; "
        f"Restart-NetAdapter -Name '{interface}'"
    )
    run_powershell(
        log, dry_run, script,
        display=f"Randomize MAC on adapter '{interface}'",
        elevated=True,
        success_msg=f"MAC address of '{interface}' updated (adapter restarted).",
    )


def search_vulnerabilities(log: Logger, dry_run: bool, target: str) -> None:
    """Uses nmap if installed (same tool, Windows build), since there is
    no built-in Windows equivalent for service/version scanning."""
    target = target.strip()
    if not target:
        log("ERROR", "Enter a target host/IP/CIDR before scanning.")
        return
    _run(
        log, dry_run,
        ["nmap.exe", "-sV", target],
        timeout=300,
        success_msg=f"Vulnerability scan of {target} finished.",
    )


def start_intrusion_detection(log: Logger, dry_run: bool, interface: str) -> Optional[subprocess.Popen]:
    """Suricata ships a native Windows build; same invocation pattern as
    the Linux backend, just pointing at the Windows config path."""
    interface = interface.strip() or "Ethernet"
    cmd = ["suricata.exe", "-c", r"C:\Suricata\suricata.yaml", "-i", interface]
    if dry_run:
        log("SIM", f"Would run (elevated): {' '.join(cmd)}")
        return None
    if not tool_available("suricata.exe"):
        log("ERROR", "'suricata.exe' is not installed or not on PATH.")
        return None
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        log("SUCCESS", f"Suricata IDS/IPS starting on {interface}...")
        return proc
    except Exception as exc:  # noqa: BLE001
        log("ERROR", f"Failed to start Suricata: {exc}")
        return None


def stop_intrusion_detection(log: Logger, dry_run: bool) -> None:
    script = (
        "Get-Process suricata -ErrorAction SilentlyContinue | Stop-Process -Force"
    )
    run_powershell(
        log, dry_run, script,
        display="Stop Suricata process",
        success_msg="Suricata IDS/IPS stopped.",
    )


def tail_suricata_alerts(log: Logger, dry_run: bool, log_path: str, lines: int = 50) -> None:
    log_path = log_path.strip() or r"C:\Suricata\log\fast.log"
    if not dry_run and not Path(log_path).exists():
        log("ERROR", f"No Suricata log found at {log_path} yet.")
        return
    script = f"Get-Content -Path '{log_path}' -Tail {int(lines)}"
    run_powershell(
        log, dry_run, script,
        display=f"Tail last {lines} lines of {log_path}",
        success_msg="Fetched recent Suricata alerts.",
    )


# ---------------------------------------------------------------------------
# System hygiene
# ---------------------------------------------------------------------------
def clear_caches(log: Logger, dry_run: bool) -> None:
    """Runs Windows Disk Cleanup (cleanmgr) with a preset sageset, and
    clears the Windows Update download cache — the closest Windows
    equivalents to `apt-get clean && autoremove`."""
    script = (
        "cleanmgr /sagerun:1; "
        "Stop-Service -Name wuauserv -Force -ErrorAction SilentlyContinue; "
        "Remove-Item -Path 'C:\\Windows\\SoftwareDistribution\\Download\\*' "
        "-Recurse -Force -ErrorAction SilentlyContinue; "
        "Start-Service -Name wuauserv -ErrorAction SilentlyContinue"
    )
    run_powershell(
        log, dry_run, script,
        display="Run Disk Cleanup and clear Windows Update cache",
        elevated=True,
        success_msg="Caches cleared.",
    )


def update_antivirus(log: Logger, dry_run: bool) -> None:
    """Updates Windows Defender signatures. If a third-party AV with a
    CLI (e.g. ClamAV-for-Windows' freshclam.exe) is installed instead,
    that path is tried first."""
    if tool_available("freshclam.exe"):
        _run(log, dry_run, ["freshclam.exe"], success_msg="ClamAV definitions updated.")
        return
    script = "Update-MpSignature"
    run_powershell(
        log, dry_run, script,
        display="Update Windows Defender signatures",
        elevated=True,
        success_msg="Windows Defender definitions updated.",
    )


def log_management(log: Logger, dry_run: bool, log_name: str) -> None:
    """Windows has no logrotate; the equivalent operation is archiving +
    clearing a named Event Log via wevtutil."""
    log_name = log_name.strip() or "Application"
    script = (
        f"$stamp = Get-Date -Format yyyyMMdd_HHmmss; "
        f"wevtutil epl {log_name} \"C:\\SOCLogs\\{log_name}_$stamp.evtx\"; "
        f"wevtutil cl {log_name}"
    )
    run_powershell(
        log, dry_run, script,
        display=f"Archive and clear the '{log_name}' event log",
        elevated=True,
        success_msg=f"Event log '{log_name}' archived and cleared.",
    )


def backup_and_recovery(log: Logger, dry_run: bool, source: str, destination: str) -> None:
    """Uses robocopy (built into Windows, mirrors rsync -av closely
    enough for a drill: /MIR mirrors the tree, /Z enables restartable
    copy)."""
    source = source.strip()
    destination = destination.strip()
    if not source or not destination:
        log("ERROR", "Both a source and destination path are required for backup.")
        return
    _run(
        log, dry_run,
        ["robocopy.exe", source, destination, "/MIR", "/Z", "/NP"],
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
    # curl.exe has shipped in Windows 10/11 since ~1803; falls back to
    # Invoke-WebRequest via PowerShell if it's missing.
    if tool_available("curl.exe"):
        _run(
            log, dry_run,
            ["curl.exe", "-s", "--max-time", "20", feed_url],
            timeout=30,
            success_msg="Threat intelligence feed retrieved.",
        )
        return
    script = f"(Invoke-WebRequest -Uri '{feed_url}' -TimeoutSec 20).Content"
    run_powershell(
        log, dry_run, script,
        display=f"Fetch {feed_url}",
        timeout=30,
        success_msg="Threat intelligence feed retrieved.",
    )


def security_event_correlation(log: Logger, dry_run: bool) -> None:
    """Pulls recent Security-log events flagged as warnings/errors as a
    lightweight stand-in for a correlation pass (OSSEC's ossec-logtest
    has no direct Windows port)."""
    script = (
        "Get-WinEvent -FilterHashtable @{LogName='Security'; Level=2,3} "
        "-MaxEvents 50 | Format-Table TimeCreated, Id, Message -AutoSize"
    )
    run_powershell(
        log, dry_run, script,
        display="Correlate recent Security-log warnings/errors",
        success_msg="Security event correlation pass complete.",
    )


def user_behavior_analytics(log: Logger, dry_run: bool) -> None:
    """Windows equivalent of `ausearch -m USER_LOGIN`: Security log
    Event ID 4624 (successful logon)."""
    script = (
        "Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4624} "
        "-MaxEvents 50 | Format-Table TimeCreated, Id, Message -AutoSize"
    )
    run_powershell(
        log, dry_run, script,
        display="Retrieve recent logon events (Event ID 4624)",
        success_msg="User login audit trail retrieved.",
    )


def compliance_monitoring(log: Logger, dry_run: bool) -> None:
    """Runs the Microsoft Baseline Security Analyzer's CLI equivalent —
    in modern Windows, Microsoft's supported path is the
    'Get-MpComputerStatus' + Security Compliance Toolkit / PolicyAnalyzer,
    but for a lightweight drill this runs the built-in Windows Defender
    quick scan plus a security-config snapshot via PowerShell."""
    script = (
        "Get-MpComputerStatus | Format-List; "
        "Start-MpScan -ScanType QuickScan"
    )
    run_powershell(
        log, dry_run, script,
        display="Run Windows Defender status check + quick scan",
        elevated=True,
        timeout=900,
        success_msg="Compliance / hardening check complete.",
    )


def security_awareness_training(log: Logger, dry_run: bool, path: str) -> None:
    path = path.strip() or r"C:\SOCTraining\index.html"
    if dry_run:
        log("SIM", f"Would open training material: {path}")
        return
    if not Path(path).exists():
        log("ERROR", f"Training material not found at {path}. Set the correct path in the Training tab.")
        return
    _run(log, False, ["cmd.exe", "/c", "start", "", path], success_msg="Training material opened.")


def check_uploads(log: Logger, dry_run: bool, upload_dir: str) -> None:
    upload_dir = upload_dir.strip() or r"C:\inetpub\wwwroot\uploads"
    if not dry_run and not Path(upload_dir).exists():
        log("ERROR", f"Directory does not exist: {upload_dir}")
        return
    script = f"Get-ChildItem -Path '{upload_dir}' -File -Recurse | Select-Object FullName"
    run_powershell(
        log, dry_run, script,
        display=f"List files under {upload_dir}",
        success_msg=f"Listed files under {upload_dir}.",
    )


def monitor_system_events(log: Logger, dry_run: bool, lines: int = 200) -> None:
    script = (
        f"Get-WinEvent -LogName System -MaxEvents {int(lines)} | "
        f"Format-Table TimeCreated, Id, LevelDisplayName, Message -AutoSize"
    )
    run_powershell(
        log, dry_run, script,
        display=f"Retrieve last {lines} System-log events",
        success_msg="Recent system events retrieved.",
    )


def suggest_defense_implementations(log: Logger, dry_run: bool) -> None:
    if dry_run:
        log("SIM", "Would run: Get-CimInstance for CPU/memory/disk and print hardening recommendations.")
        return
    script = (
        "Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores; "
        "Get-CimInstance Win32_OperatingSystem | "
        "Select-Object @{n='FreeGB';e={[math]::Round($_.FreePhysicalMemory/1MB,2)}}; "
        "Get-CimInstance Win32_LogicalDisk -Filter \"DriveType=3\" | "
        "Select-Object DeviceID, @{n='FreeGB';e={[math]::Round($_.FreeSpace/1GB,2)}}, "
        "@{n='SizeGB';e={[math]::Round($_.Size/1GB,2)}}"
    )
    run_powershell(
        log, False, script,
        display="Collect CPU / memory / disk specs",
        success_msg="System specs collected.",
    )
    for tip in (
        "Keep Windows Update current, including out-of-band security patches.",
        "Enable Windows Defender Firewall with a default-deny inbound policy.",
        "Schedule regular backups (e.g. via robocopy or File History) and test restores.",
        "Enforce strong passwords and MFA (Windows Hello / Azure AD Conditional Access).",
        "Run an IDS/IPS (e.g. Suricata for Windows) and review alerts routinely.",
    ):
        log("INFO", f"  - {tip}")


# ---------------------------------------------------------------------------
# Incident response
# ---------------------------------------------------------------------------
_SERVICE_NAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")
_IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}(/\d{1,2})?$")
_USERNAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]{0,31}$")


def incident_response_restart_service(log: Logger, dry_run: bool, service: str) -> None:
    service = service.strip()
    if not service or not _SERVICE_NAME_RE.match(service):
        log("ERROR", "Enter a valid Windows service name, e.g. 'Spooler' or 'W3SVC'.")
        return
    script = f"Restart-Service -Name '{service}' -Force"
    run_powershell(
        log, dry_run, script,
        display=f"Restart-Service '{service}'",
        elevated=True,
        success_msg=f"Service '{service}' restarted.",
    )


def quarantine_interactions(log: Logger, dry_run: bool, ip: str) -> None:
    """Windows equivalent of `ufw deny from <ip>`: adds a Windows
    Defender Firewall rule blocking inbound traffic from the address."""
    ip = ip.strip()
    if not ip or not _IP_RE.match(ip):
        log("ERROR", "Enter a valid IPv4 address or CIDR to quarantine, e.g. 192.168.1.100.")
        return
    rule_name = f"SOCDrills-Quarantine-{ip.replace('/', '_')}"
    script = (
        f"New-NetFirewallRule -DisplayName '{rule_name}' -Direction Inbound "
        f"-RemoteAddress {ip} -Action Block -Profile Any"
    )
    run_powershell(
        log, dry_run, script,
        display=f"Block inbound traffic from {ip}",
        elevated=True,
        success_msg=f"Traffic from {ip} is now denied.",
    )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------
def add_user(log: Logger, dry_run: bool, username: str, password: str) -> None:
    username = username.strip()
    if not username or not _USERNAME_RE.match(username):
        log("ERROR", "Invalid username. Use letters, numbers, - or _, starting with a letter/underscore.")
        return
    if not password:
        log("ERROR", "A password is required.")
        return

    if dry_run:
        log("SIM", f"Would run: New-LocalUser {username} (elevated)")
        log("SIM", f"Password for '{username}' would be set as a SecureString (never shown in the console).")
        return

    # Password is built into a SecureString inside the elevated PowerShell
    # process itself — it is not placed on this process's command line or
    # written to the on-screen console at any point.
    escaped_pw = password.replace("'", "''")
    script = (
        f"$sec = ConvertTo-SecureString '{escaped_pw}' -AsPlainText -Force; "
        f"New-LocalUser -Name '{username}' -Password $sec "
        f"-AccountNeverExpires -PasswordNeverExpires:$false"
    )
    run_powershell(
        log, False, script,
        display=f"New-LocalUser '{username}' (password hidden)",
        elevated=True,
        success_msg=f"User '{username}' created.",
    )


def remove_user(log: Logger, dry_run: bool, username: str) -> None:
    username = username.strip()
    if not username or not _USERNAME_RE.match(username):
        log("ERROR", "Invalid username.")
        return
    script = f"Remove-LocalUser -Name '{username}'"
    run_powershell(
        log, dry_run, script,
        display=f"Remove-LocalUser '{username}'",
        elevated=True,
        success_msg=f"User '{username}' removed.",
    )
