"""
Visual theme for Basic SOC Drills.

Palette is pulled straight from the crest artwork:
  - near-black gunmetal background
  - matrix / radar green for "safe" and primary UI
  - warning orange for "drills" / destructive or attention actions
  - blood red for critical alerts
"""

import tkinter as tk
from tkinter import ttk

# ---- Palette --------------------------------------------------------------
BG_DARKEST = "#05080a"      # window background
BG_PANEL = "#0b1310"        # cards / sidebar
BG_PANEL_ALT = "#101a15"    # hovered / alt rows
BORDER = "#1f3a26"

GREEN = "#39ff6a"           # primary accent (radar green)
GREEN_DIM = "#1f8a3d"
GREEN_TEXT = "#8fffb0"

ORANGE = "#ff8a1e"          # "drills" accent
ORANGE_DIM = "#c9640a"

RED = "#ff3b3b"             # critical / destructive
RED_DIM = "#8a1f1f"

TEXT = "#d7ffe0"
TEXT_MUTED = "#6f9c7c"
WHITE = "#f2fff5"

FONT_FAMILY = "Consolas" if tk.TkVersion else "Courier"


def apply_theme(root: tk.Misc) -> ttk.Style:
    """Configure ttk styles for the whole app and return the Style object."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root.configure(bg=BG_DARKEST)

    style.configure(
        "TFrame",
        background=BG_DARKEST,
    )
    style.configure(
        "Panel.TFrame",
        background=BG_PANEL,
        relief="flat",
        borderwidth=0,
    )
    style.configure(
        "Sidebar.TFrame",
        background=BG_PANEL,
    )

    style.configure(
        "TLabel",
        background=BG_DARKEST,
        foreground=TEXT,
        font=(FONT_FAMILY, 10),
    )
    style.configure(
        "Panel.TLabel",
        background=BG_PANEL,
        foreground=TEXT,
        font=(FONT_FAMILY, 10),
    )
    style.configure(
        "Title.TLabel",
        background=BG_DARKEST,
        foreground=GREEN,
        font=(FONT_FAMILY, 20, "bold"),
    )
    style.configure(
        "Subtitle.TLabel",
        background=BG_DARKEST,
        foreground=ORANGE,
        font=(FONT_FAMILY, 12, "bold"),
    )
    style.configure(
        "Muted.TLabel",
        background=BG_DARKEST,
        foreground=TEXT_MUTED,
        font=(FONT_FAMILY, 9),
    )
    style.configure(
        "SectionHeader.TLabel",
        background=BG_DARKEST,
        foreground=ORANGE,
        font=(FONT_FAMILY, 13, "bold"),
    )
    style.configure(
        "CardTitle.TLabel",
        background=BG_PANEL,
        foreground=WHITE,
        font=(FONT_FAMILY, 11, "bold"),
    )
    style.configure(
        "CardDesc.TLabel",
        background=BG_PANEL,
        foreground=TEXT_MUTED,
        font=(FONT_FAMILY, 9),
    )
    style.configure(
        "StatusOn.TLabel",
        background=BG_DARKEST,
        foreground=GREEN,
        font=(FONT_FAMILY, 9, "bold"),
    )
    style.configure(
        "StatusOff.TLabel",
        background=BG_DARKEST,
        foreground=RED,
        font=(FONT_FAMILY, 9, "bold"),
    )

    # Buttons
    style.configure(
        "Nav.TButton",
        background=BG_PANEL,
        foreground=TEXT,
        borderwidth=0,
        focusthickness=0,
        padding=(14, 10),
        font=(FONT_FAMILY, 10, "bold"),
        anchor="w",
    )
    style.map(
        "Nav.TButton",
        background=[("active", BG_PANEL_ALT), ("selected", BG_PANEL_ALT)],
        foreground=[("active", GREEN)],
    )
    style.configure(
        "NavSelected.TButton",
        background=BG_PANEL_ALT,
        foreground=GREEN,
        borderwidth=0,
        padding=(14, 10),
        font=(FONT_FAMILY, 10, "bold"),
        anchor="w",
    )

    style.configure(
        "Action.TButton",
        background=GREEN_DIM,
        foreground=WHITE,
        borderwidth=0,
        padding=(10, 8),
        font=(FONT_FAMILY, 9, "bold"),
    )
    style.map("Action.TButton", background=[("active", GREEN)])

    style.configure(
        "Danger.TButton",
        background=RED_DIM,
        foreground=WHITE,
        borderwidth=0,
        padding=(10, 8),
        font=(FONT_FAMILY, 9, "bold"),
    )
    style.map("Danger.TButton", background=[("active", RED)])

    style.configure(
        "Warn.TButton",
        background=ORANGE_DIM,
        foreground=WHITE,
        borderwidth=0,
        padding=(10, 8),
        font=(FONT_FAMILY, 9, "bold"),
    )
    style.map("Warn.TButton", background=[("active", ORANGE)])

    style.configure(
        "TEntry",
        fieldbackground=BG_PANEL_ALT,
        foreground=TEXT,
        insertcolor=GREEN,
        borderwidth=1,
    )

    style.configure(
        "TCheckbutton",
        background=BG_DARKEST,
        foreground=TEXT,
        font=(FONT_FAMILY, 9, "bold"),
    )
    style.map("TCheckbutton", background=[("active", BG_DARKEST)])

    style.configure("TSeparator", background=BORDER)

    style.configure(
        "Vertical.TScrollbar",
        background=BG_PANEL,
        troughcolor=BG_DARKEST,
        arrowcolor=GREEN,
        borderwidth=0,
    )

    return style
