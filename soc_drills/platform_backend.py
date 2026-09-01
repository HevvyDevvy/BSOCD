"""Picks the right backend module for the current OS at import time.

gui.py imports `backend` from this module instead of importing
`backend` or `backend_windows` directly, so the rest of the app (cards,
field definitions, confirmations) doesn't need to know or care which
platform it's running on — every backend module exposes the same
function names and signatures.
"""

from __future__ import annotations

import platform

if platform.system() == "Windows":
    from . import backend_windows as backend
else:
    from . import backend as backend

__all__ = ["backend"]
