"""Main application window for Basic SOC Drills."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox

import platform as _platform

from .platform_backend import backend
from . import theme
from .console import Console

if _platform.system() == "Windows":
    TOOL_CHECKS = [
        ("powershell.exe", "Elevated actions (UAC-scoped)"),
        ("nmap.exe", "Vulnerability scan (optional, not bundled)"),
        ("suricata.exe", "IDS / IPS (optional, not bundled)"),
        ("robocopy.exe", "Backups"),
        ("curl.exe", "Threat intel"),
        ("wevtutil.exe", "Event log management"),
    ]
else:
    TOOL_CHECKS = [
        ("macchanger", "MAC randomization"),
        ("nmap", "Vulnerability scan"),
        ("suricata", "IDS / IPS"),
        ("freshclam", "Antivirus updates"),
        ("logrotate", "Log rotation"),
        ("rsync", "Backups"),
        ("curl", "Threat intel"),
        ("ausearch", "User behavior audit"),
        ("lynis", "Compliance audit"),
        ("ufw", "Firewall / quarantine"),
        ("systemctl", "Service control"),
    ]


class Field:
    """Declarative description of one input on a card."""

    def __init__(self, key, label, default="", secret=False, width=28):
        self.key = key
        self.label = label
        self.default = default
        self.secret = secret
        self.width = width


class Card:
    """Declarative description of one action card."""

    def __init__(self, title, desc, action, fields=None, button_text="Run",
                 style="Action.TButton", confirm=None):
        self.title = title
        self.desc = desc
        self.action = action  # callable(log, dry_run, values: dict)
        self.fields = fields or []
        self.button_text = button_text
        self.style = style
        self.confirm = confirm  # optional confirmation message


class App(ttk.Frame):
    def __init__(self, root: tk.Tk):
        super().__init__(root)
        self.root = root
        self.dry_run = tk.BooleanVar(value=True)
        self._suricata_proc = None

        root.title("Basic SOC Drills")
        root.geometry("1220x780")
        root.minsize(980, 640)
        theme.apply_theme(root)

        self.pack(fill="both", expand=True)
        self._build_header()

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        self._build_sidebar(body)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        paned = tk.PanedWindow(
            right, orient="vertical", bg=theme.BG_DARKEST,
            sashwidth=6, bd=0, relief="flat",
        )
        paned.pack(fill="both", expand=True, padx=(0, 12), pady=12)

        self.content_container = ttk.Frame(paned)
        paned.add(self.content_container, minsize=260, stretch="always")

        self.console = Console(paned)
        paned.add(self.console, minsize=160)

        self._categories = self._build_categories()
        self._nav_buttons = {}
        self._build_nav(self._categories)
        self._select_category(self._categories[0]["name"])

        self.console.log("SYSTEM", "Basic SOC Drills ready. Simulation Mode is ON by default.")
        self._probe_tools()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    def _build_header(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=16, pady=(14, 6))

        title_box = ttk.Frame(header)
        title_box.pack(side="left")
        ttk.Label(title_box, text="BASIC SOC DRILLS", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_box,
            text="Analyst drill console  //  local defensive tooling",
            style="Subtitle.TLabel",
        ).pack(anchor="w")

        controls = ttk.Frame(header)
        controls.pack(side="right")

        self.status_label = ttk.Label(controls, text="\u25CF SIMULATION", style="StatusOff.TLabel")
        self.status_label.pack(side="right", padx=(16, 0))

        sim_check = ttk.Checkbutton(
            controls,
            text="Simulation Mode (safe / no changes made)",
            variable=self.dry_run,
            command=self._on_toggle_dry_run,
        )
        sim_check.pack(side="right")
        self._on_toggle_dry_run()

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16, pady=(4, 0))

    def _on_toggle_dry_run(self):
        if self.dry_run.get():
            self.status_label.configure(text="\u25CF SIMULATION", style="StatusOff.TLabel")
        else:
            self.status_label.configure(text="\u25CF LIVE - CHANGES WILL BE MADE", style="StatusOn.TLabel")

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    def _build_sidebar(self, parent):
        sidebar = ttk.Frame(parent, style="Sidebar.TFrame", width=210)
        sidebar.pack(side="left", fill="y", padx=(12, 12), pady=12)
        sidebar.pack_propagate(False)
        self._sidebar = sidebar

    def _build_nav(self, categories):
        for cat in categories:
            btn = ttk.Button(
                self._sidebar,
                text=cat["name"],
                style="Nav.TButton",
                command=lambda c=cat["name"]: self._select_category(c),
            )
            btn.pack(fill="x", padx=6, pady=2)
            self._nav_buttons[cat["name"]] = btn

    def _select_category(self, name):
        for cat_name, btn in self._nav_buttons.items():
            btn.configure(style="NavSelected.TButton" if cat_name == name else "Nav.TButton")

        for child in self.content_container.winfo_children():
            child.destroy()

        category = next(c for c in self._categories if c["name"] == name)

        canvas = tk.Canvas(self.content_container, bg=theme.BG_DARKEST, highlightthickness=0)
        scroll = ttk.Scrollbar(self.content_container, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=1)
        canvas.configure(yscrollcommand=scroll.set)

        def _resize(event):
            canvas.itemconfigure(canvas.find_all()[0], width=event.width)

        canvas.bind("<Configure>", _resize)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        def _wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _wheel)

        if category.get("extra"):
            category["extra"](inner)

        for card in category["cards"]:
            self._render_card(inner, card)

    # ------------------------------------------------------------------
    # Card rendering
    # ------------------------------------------------------------------
    def _render_card(self, parent, card: Card):
        wrapper = ttk.Frame(parent, style="Panel.TFrame")
        wrapper.pack(fill="x", padx=4, pady=6)

        pad = ttk.Frame(wrapper, style="Panel.TFrame")
        pad.pack(fill="x", padx=14, pady=12)

        ttk.Label(pad, text=card.title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(pad, text=card.desc, style="CardDesc.TLabel", wraplength=760, justify="left").pack(
            anchor="w", pady=(2, 8)
        )

        entries = {}
        if card.fields:
            fields_row = ttk.Frame(pad, style="Panel.TFrame")
            fields_row.pack(fill="x", pady=(0, 8))
            for field in card.fields:
                col = ttk.Frame(fields_row, style="Panel.TFrame")
                col.pack(side="left", padx=(0, 14))
                ttk.Label(col, text=field.label, style="CardDesc.TLabel").pack(anchor="w")
                var = tk.StringVar(value=field.default)
                entry = ttk.Entry(col, textvariable=var, width=field.width,
                                   show="*" if field.secret else "")
                entry.pack(anchor="w")
                entries[field.key] = var

        btn = ttk.Button(
            pad,
            text=card.button_text,
            style=card.style,
            command=lambda: self._run_card(card, entries),
        )
        btn.pack(anchor="e")

    def _run_card(self, card: Card, entries: dict):
        values = {key: var.get() for key, var in entries.items()}

        if card.confirm and not self.dry_run.get():
            if not messagebox.askyesno("Confirm action", card.confirm):
                self.console.log("SYSTEM", f"Cancelled: {card.title}")
                return

        dry_run = self.dry_run.get()
        self.console.log("SYSTEM", f"Running: {card.title}" + ("  [SIMULATION]" if dry_run else ""))

        def worker():
            try:
                card.action(self.console.log, dry_run, values)
            except Exception as exc:  # noqa: BLE001
                self.console.log("ERROR", f"'{card.title}' crashed: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Startup tool probe
    # ------------------------------------------------------------------
    def _probe_tools(self):
        def worker():
            missing = [name for name, _ in TOOL_CHECKS if not backend.tool_available(name)]
            if missing:
                self.console.log(
                    "WARN",
                    f"Not installed on this system: {', '.join(missing)}. "
                    "Related drills will report an error until installed (see README).",
                )
            else:
                self.console.log("SUCCESS", "All expected security tools were found on PATH.")

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Category / card definitions
    # ------------------------------------------------------------------
    def _build_categories(self):
        return [
            self._category_overview(),
            self._category_network(),
            self._category_detection(),
            self._category_hygiene(),
            self._category_threat_intel(),
            self._category_incident_response(),
            self._category_user_mgmt(),
            self._category_monitoring(),
            self._category_training(),
        ]

    def _category_overview(self):
        def extra(parent):
            box = ttk.Frame(parent, style="Panel.TFrame")
            box.pack(fill="x", padx=4, pady=(0, 10))
            inner = ttk.Frame(box, style="Panel.TFrame")
            inner.pack(fill="x", padx=14, pady=12)
            ttk.Label(inner, text="Tool availability on this system", style="CardTitle.TLabel").pack(anchor="w")
            grid = ttk.Frame(inner, style="Panel.TFrame")
            grid.pack(fill="x", pady=(8, 0))
            for i, (binary, purpose) in enumerate(TOOL_CHECKS):
                ok = backend.tool_available(binary)
                dot = "\u25CF"
                lbl = ttk.Label(
                    grid,
                    text=f"{dot} {binary}  ({purpose})",
                    style="Panel.TLabel",
                    foreground=theme.GREEN if ok else theme.RED,
                    background=theme.BG_PANEL,
                )
                lbl.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 24), pady=2)

        return {
            "name": "Overview",
            "extra": extra,
            "cards": [
                Card(
                    "System Health Check",
                    "Collects CPU / memory / disk info and prints baseline hardening recommendations. "
                    "Read-only, safe to run any time.",
                    lambda log, dry, v: backend.suggest_defense_implementations(log, dry),
                ),
            ],
        }

    def _category_network(self):
        return {
            "name": "Network & Recon",
            "cards": [
                Card(
                    "Randomize MAC Address",
                    "Runs macchanger -r on the chosen interface. This changes real network identity - "
                    "expect the interface to briefly drop.",
                    lambda log, dry, v: backend.change_mac_address(log, dry, v["iface"]),
                    fields=[Field("iface", "Interface", "eth0", width=14)],
                    button_text="Randomize MAC",
                    style="Warn.TButton",
                    confirm="This will change the MAC address of the selected interface. Continue?",
                ),
                Card(
                    "Vulnerability Scan (nmap)",
                    "Runs `nmap -sV` against a target you own or are authorized to test. "
                    "Only scan systems you have permission to scan.",
                    lambda log, dry, v: backend.search_vulnerabilities(log, dry, v["target"]),
                    fields=[Field("target", "Target host / IP / CIDR", "127.0.0.1", width=22)],
                    button_text="Scan Target",
                ),
            ],
        }

    def _category_detection(self):
        def start_ids(log, dry, values):
            if dry:
                backend.start_intrusion_detection(log, True, values["iface"])
                return
            if self._suricata_proc and self._suricata_proc.poll() is None:
                log("WARN", "Suricata already appears to be running.")
                return
            proc = backend.start_intrusion_detection(log, False, values["iface"])
            self._suricata_proc = proc
            if proc is None:
                return

            def pump():
                for line in proc.stdout:
                    log("INFO", line.rstrip())
                log("SYSTEM", "Suricata process ended.")

            threading.Thread(target=pump, daemon=True).start()

        def stop_ids(log, dry, values):
            backend.stop_intrusion_detection(log, dry)
            self._suricata_proc = None

        return {
            "name": "Threat Detection",
            "cards": [
                Card(
                    "Start IDS / IPS (Suricata)",
                    "Starts Suricata in the foreground on the chosen interface and streams its output "
                    "to the console below. Requires suricata.yaml to already be configured.",
                    start_ids,
                    fields=[Field("iface", "Interface", "eth0", width=14)],
                    button_text="Start Suricata",
                ),
                Card(
                    "Stop IDS / IPS",
                    "Stops any running Suricata process started by this app (or elsewhere on the system).",
                    stop_ids,
                    button_text="Stop Suricata",
                    style="Danger.TButton",
                    confirm="Stop the running Suricata IDS/IPS process?",
                ),
                Card(
                    "View Recent Alerts",
                    "Tails the last lines of the Suricata fast log - a quick, read-only way to check for "
                    "recent alerts without leaving the app.",
                    lambda log, dry, v: backend.tail_suricata_alerts(log, dry, v["path"], int(v["lines"] or 50)),
                    fields=[
                        Field("path", "Log path", "/var/log/suricata/fast.log", width=30),
                        Field("lines", "Lines", "50", width=6),
                    ],
                    button_text="Tail Alerts",
                ),
            ],
        }

    def _category_hygiene(self):
        return {
            "name": "System Hygiene",
            "cards": [
                Card(
                    "Clear Package Caches",
                    "Runs `apt-get clean` and `apt-get autoremove -y`. This will remove cached package "
                    "files and unused dependencies.",
                    lambda log, dry, v: backend.clear_caches(log, dry),
                    button_text="Clear Caches",
                    style="Warn.TButton",
                    confirm="Clean apt caches and remove unused packages?",
                ),
                Card(
                    "Update Antivirus Definitions",
                    "Runs `freshclam` to pull the latest ClamAV virus definitions.",
                    lambda log, dry, v: backend.update_antivirus(log, dry),
                ),
                Card(
                    "Force Log Rotation",
                    "Runs `logrotate -f` against the given config file.",
                    lambda log, dry, v: backend.log_management(log, dry, v["config"]),
                    fields=[Field("config", "Config path", "/etc/logrotate.conf", width=30)],
                    button_text="Rotate Logs",
                ),
                Card(
                    "Backup a Directory",
                    "Runs `rsync -av` from source to destination. Does not need root if both paths are "
                    "writable by your user.",
                    lambda log, dry, v: backend.backup_and_recovery(log, dry, v["src"], v["dst"]),
                    fields=[
                        Field("src", "Source", "/home/user/", width=22),
                        Field("dst", "Destination", "/backup/user_backup/", width=24),
                    ],
                    button_text="Run Backup",
                ),
            ],
        }

    def _category_threat_intel(self):
        return {
            "name": "Threat Intel & Compliance",
            "cards": [
                Card(
                    "Pull Threat Intel Feed",
                    "Fetches a threat feed URL you provide (curl). Point this at your provider's feed - "
                    "no feed is queried by default.",
                    lambda log, dry, v: backend.threat_intelligence_pull(log, dry, v["url"]),
                    fields=[Field("url", "Feed URL", "", width=40)],
                    button_text="Pull Feed",
                ),
                Card(
                    "Security Event Correlation",
                    "Runs `ossec-logtest` to sanity-check log correlation rules.",
                    lambda log, dry, v: backend.security_event_correlation(log, dry),
                ),
                Card(
                    "User Behavior Audit",
                    "Runs `ausearch -m USER_LOGIN` to review recent login activity from the audit log.",
                    lambda log, dry, v: backend.user_behavior_analytics(log, dry),
                ),
                Card(
                    "Compliance Audit (Lynis)",
                    "Runs a full Lynis hardening/compliance audit. This can take several minutes.",
                    lambda log, dry, v: backend.compliance_monitoring(log, dry),
                    button_text="Run Audit",
                ),
            ],
        }

    def _category_incident_response(self):
        return {
            "name": "Incident Response",
            "cards": [
                Card(
                    "Restart a Service",
                    "Runs `systemctl restart <service>`. Use for a compromised or hung service during "
                    "an active drill or incident.",
                    lambda log, dry, v: backend.incident_response_restart_service(log, dry, v["service"]),
                    fields=[Field("service", "Service name", "apache2", width=18)],
                    button_text="Restart Service",
                    style="Warn.TButton",
                    confirm="This will restart the specified service now. Continue?",
                ),
                Card(
                    "Quarantine an IP",
                    "Adds a `ufw deny from <ip>` rule to block traffic from a suspicious address.",
                    lambda log, dry, v: backend.quarantine_interactions(log, dry, v["ip"]),
                    fields=[Field("ip", "IP / CIDR", "192.168.1.100", width=18)],
                    button_text="Quarantine",
                    style="Danger.TButton",
                    confirm="This will add a firewall rule blocking this address. Continue?",
                ),
                Card(
                    "Check Upload Directory",
                    "Lists files under a web upload directory - useful for spotting webshells dropped "
                    "during an incident.",
                    lambda log, dry, v: backend.check_uploads(log, dry, v["dir"]),
                    fields=[Field("dir", "Directory", "/var/www/html/uploads", width=30)],
                    button_text="List Files",
                ),
            ],
        }

    def _category_user_mgmt(self):
        return {
            "name": "User Management",
            "cards": [
                Card(
                    "Add User",
                    "Creates a local user account and sets its password. The password is piped directly "
                    "into `chpasswd` - it is never shown in the console or command history.",
                    lambda log, dry, v: backend.add_user(log, dry, v["username"], v["password"]),
                    fields=[
                        Field("username", "Username", "", width=16),
                        Field("password", "Password", "", secret=True, width=16),
                    ],
                    button_text="Create User",
                    style="Warn.TButton",
                    confirm="Create this local user account with the given password?",
                ),
                Card(
                    "Remove User",
                    "Deletes a local user account and its home directory (`userdel -r`). This cannot be "
                    "undone.",
                    lambda log, dry, v: backend.remove_user(log, dry, v["username"]),
                    fields=[Field("username", "Username", "", width=16)],
                    button_text="Delete User",
                    style="Danger.TButton",
                    confirm="This permanently deletes the user and their home directory. Continue?",
                ),
            ],
        }

    def _category_monitoring(self):
        return {
            "name": "Monitoring",
            "cards": [
                Card(
                    "Recent System Events",
                    "Runs `journalctl -n <lines> --no-pager` to pull the most recent system log entries.",
                    lambda log, dry, v: backend.monitor_system_events(log, dry, int(v["lines"] or 200)),
                    fields=[Field("lines", "Lines", "200", width=8)],
                    button_text="Fetch Events",
                ),
            ],
        }

    def _category_training(self):
        return {
            "name": "Training",
            "cards": [
                Card(
                    "Open Security Awareness Material",
                    "Opens a local HTML/PDF training document in your default viewer.",
                    lambda log, dry, v: backend.security_awareness_training(log, dry, v["path"]),
                    fields=[Field("path", "File path", "/usr/share/security-training/index.html", width=36)],
                    button_text="Open Material",
                ),
            ],
        }


def launch():
    root = tk.Tk()
    App(root)
    root.mainloop()
