"""First-run privilege / consent warning.

Basic SOC Drills is a real system-administration tool: many of its cards
shell out to commands that require elevated (sudo / Administrator) rights
- creating or deleting local user accounts, restarting services, changing
firewall rules, changing the network interface's MAC address, and so on.

Before the main window ever appears, this dialog makes that explicit and
gives the user an unambiguous way to back out. It is shown once per
installation (tracked via a marker file next to the user's config
directory) and can always be re-triggered by deleting that marker.

Cancelling here quits the application immediately without importing or
touching the backend module, so no elevated action can occur.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from . import theme

MARKER_DIR = Path.home() / ".basic_soc_drills"
MARKER_FILE = MARKER_DIR / "consent_accepted"

WARNING_TEXT = (
    "Basic SOC Drills is a system administration and SOC-training tool.\n\n"
    "Many of its actions run with elevated privileges "
    "(Administrator on Windows, sudo on Linux/macOS) as soon as you "
    "disable Simulation Mode and click Run. Depending on which card you "
    "use, that can include:\n\n"
    "  \u2022 Creating or deleting local user accounts\n"
    "  \u2022 Starting, stopping, or restarting system services\n"
    "  \u2022 Changing firewall rules and quarantining IP addresses\n"
    "  \u2022 Changing your network interface's MAC address\n"
    "  \u2022 Running antivirus, IDS, and system-audit tools\n\n"
    "Simulation Mode is ON by default and every action is previewed "
    "(\"Would run: ...\") until you turn it off yourself. Nothing above "
    "happens automatically or in the background.\n\n"
    "Only continue if you understand this tool will request elevated "
    "privileges when you use it, and only run it against systems and "
    "accounts you own or are explicitly authorized to test.\n\n"
    "If you are not comfortable granting elevation when prompted, "
    "click Cancel Install below to close now without changing anything "
    "on this system."
)


def _center(win: tk.Tk, w: int, h: int) -> None:
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")


def has_prior_consent() -> bool:
    return MARKER_FILE.exists()


def _record_consent() -> None:
    try:
        MARKER_DIR.mkdir(parents=True, exist_ok=True)
        MARKER_FILE.write_text("accepted\n", encoding="utf-8")
    except OSError:
        # Non-fatal: worst case the dialog reappears next launch.
        pass


def show_consent_dialog() -> bool:
    """Block until the user accepts or cancels. Returns True to proceed."""
    if has_prior_consent():
        return True

    accepted = {"value": False}

    win = tk.Tk()
    win.title("Basic SOC Drills - Privilege Notice")
    win.resizable(False, False)
    theme.apply_theme(win)
    win.configure(bg=theme.BG_DARKEST)

    frame = ttk.Frame(win, padding=24, style="Panel.TFrame")
    frame.pack(fill="both", expand=True)

    heading = ttk.Label(
        frame,
        text="\u26a0  This tool can request elevated privileges",
        style="Title.TLabel",
        wraplength=520,
        justify="left",
    )
    heading.pack(anchor="w", pady=(0, 12))

    body = tk.Text(
        frame,
        width=64,
        height=18,
        wrap="word",
        bg=theme.BG_PANEL,
        fg=theme.TEXT,
        relief="flat",
        padx=12,
        pady=12,
        font=(theme.FONT_FAMILY, 10),
        borderwidth=0,
    )
    body.insert("1.0", WARNING_TEXT)
    body.configure(state="disabled")
    body.pack(fill="both", expand=True, pady=(0, 16))

    btn_row = ttk.Frame(frame)
    btn_row.pack(fill="x")

    def on_cancel():
        accepted["value"] = False
        win.destroy()

    def on_accept():
        accepted["value"] = True
        _record_consent()
        win.destroy()

    cancel_btn = ttk.Button(
        btn_row, text="Cancel Install / Quit", command=on_cancel,
        style="Danger.TButton",
    )
    cancel_btn.pack(side="left")

    accept_btn = ttk.Button(
        btn_row, text="I Understand - Continue", command=on_accept,
        style="Action.TButton",
    )
    accept_btn.pack(side="right")

    win.protocol("WM_DELETE_WINDOW", on_cancel)
    _center(win, 600, 480)
    win.mainloop()

    return accepted["value"]


def run_gate() -> None:
    """Entry point used by app.py. Exits the process on cancel."""
    if not show_consent_dialog():
        sys.exit(0)
