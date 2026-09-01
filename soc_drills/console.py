"""Thread-safe, color-coded log console used across the whole app."""

import queue
import time
import tkinter as tk
from tkinter import ttk

from . import theme


class Console(ttk.Frame):
    """A scrolling text log that background worker threads can safely write to.

    Worker threads never touch the Tk widget directly - they push
    (level, message) tuples onto a thread-safe queue, and the Tk mainloop
    drains that queue on a timer via .after(). This avoids the classic
    "Tkinter is not thread-safe" crash.
    """

    LEVEL_STYLE = {
        "INFO": ("#8fffb0", "  "),
        "SUCCESS": (theme.GREEN, "OK"),
        "WARN": (theme.ORANGE, "!!"),
        "ERROR": (theme.RED, "XX"),
        "SYSTEM": (theme.TEXT_MUTED, "::"),
        "SIM": (theme.ORANGE, "SIM"),
    }

    def __init__(self, master, **kwargs):
        super().__init__(master, style="Panel.TFrame", **kwargs)
        self._queue: "queue.Queue[tuple[str, str]]" = queue.Queue()

        header = ttk.Frame(self, style="Panel.TFrame")
        header.pack(fill="x", padx=10, pady=(8, 0))
        ttk.Label(header, text="LIVE CONSOLE", style="CardTitle.TLabel").pack(side="left")
        clear_btn = ttk.Button(header, text="Clear", style="Warn.TButton", command=self.clear)
        clear_btn.pack(side="right")

        body = ttk.Frame(self, style="Panel.TFrame")
        body.pack(fill="both", expand=True, padx=10, pady=10)

        self.text = tk.Text(
            body,
            bg=theme.BG_DARKEST,
            fg=theme.TEXT,
            insertbackground=theme.GREEN,
            relief="flat",
            wrap="word",
            font=(theme.FONT_FAMILY, 9),
            state="disabled",
            padx=8,
            pady=8,
        )
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        for level, (color, _tag) in self.LEVEL_STYLE.items():
            self.text.tag_configure(level, foreground=color)
        self.text.tag_configure("timestamp", foreground=theme.TEXT_MUTED)

        self.log("SYSTEM", "Console ready. Waiting for commands...")
        self.after(120, self._drain_queue)

    # -- public API, safe to call from ANY thread ---------------------------
    def log(self, level: str, message: str) -> None:
        self._queue.put((level.upper(), message))

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    # -- internal, Tk-thread only --------------------------------------------
    def _drain_queue(self) -> None:
        drained = 0
        while drained < 200:
            try:
                level, message = self._queue.get_nowait()
            except queue.Empty:
                break
            self._append(level, message)
            drained += 1
        self.after(120, self._drain_queue)

    def _append(self, level: str, message: str) -> None:
        color_tag = level if level in self.LEVEL_STYLE else "INFO"
        _, badge = self.LEVEL_STYLE.get(level, ("#ffffff", "  "))
        ts = time.strftime("%H:%M:%S")

        self.text.configure(state="normal")
        self.text.insert("end", f"[{ts}] ", "timestamp")
        self.text.insert("end", f"{badge:>3} ", color_tag)
        self.text.insert("end", f"{message}\n", color_tag)
        self.text.configure(state="disabled")
        self.text.see("end")
