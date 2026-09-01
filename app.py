#!/usr/bin/env python3
"""
Basic SOC Drills - themed desktop GUI
=====================================

Run with:
    python3 app.py

See README.md for tool prerequisites (nmap, suricata, clamav, etc).
The app works even if some tools are missing - it will just report that
a given drill's underlying tool isn't installed instead of crashing.

Simulation Mode is ON by default: every action is logged as "would run"
without touching the system. Turn it off in the top bar once you're ready
to execute real commands (most of which require sudo and will prompt for
your password in the terminal you launched this from).
"""

import sys

try:
    from soc_drills.consent import run_gate
    from soc_drills.gui import launch
except ModuleNotFoundError as exc:
    if "tkinter" in str(exc):
        sys.stderr.write(
            "\nTkinter is not installed for this Python interpreter.\n"
            "On Debian/Kali/Ubuntu, install it with:\n"
            "    sudo apt install python3-tk\n\n"
        )
        sys.exit(1)
    raise

if __name__ == "__main__":
    # Shown once per install (or once per user profile). Cancelling here
    # exits immediately, before soc_drills.backend (the module that shells
    # out to sudo/UAC-requiring commands) is ever imported or used.
    run_gate()
    launch()
