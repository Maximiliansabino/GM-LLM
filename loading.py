"""
loading.py
─────────────────────────────────────────────────────────────
Animated loading bar displayed while waiting for LLM response.
Runs in a background thread so it doesn't block the request.

Usage:
    with spinner("Thinking..."):
        result = call_llm(...)
─────────────────────────────────────────────────────────────
"""

import sys
import time
import threading
from contextlib import contextmanager


# ── Frames ───────────────────────────────────────────────────

_FRAMES_BAR = [
    "  [■□□□□□□□□□□□□□□□□□□□]",
    "  [■■□□□□□□□□□□□□□□□□□□]",
    "  [■■■■□□□□□□□□□□□□□□□□]",
    "  [■■■■■■□□□□□□□□□□□□□□]",
    "  [■■■■■■■■□□□□□□□□□□□□]",
    "  [■■■■■■■■■■□□□□□□□□□□]",
    "  [■■■■■■■■■■■■□□□□□□□□]",
    "  [■■■■■■■■■■■■■■□□□□□□]",
    "  [■■■■■■■■■■■■■■■■□□□□]",
    "  [■■■■■■■■■■■■■■■■■■□□]",
    "  [■■■■■■■■■■■■■■■■■■■■]",
    "  [□■■■■■■■■■■■■■■■■■■■]",
    "  [□□□■■■■■■■■■■■■■■■■■]",
    "  [□□□□□■■■■■■■■■■■■■■■]",
    "  [□□□□□□□■■■■■■■■■■■■■]",
    "  [□□□□□□□□□■■■■■■■■■■■]",
    "  [□□□□□□□□□□□■■■■■■■■■]",
    "  [□□□□□□□□□□□□□■■■■■■■]",
    "  [□□□□□□□□□□□□□□□■■■■■]",
    "  [□□□□□□□□□□□□□□□□□■■■]",
    "  [□□□□□□□□□□□□□□□□□□□□]",
]


class _Spinner:
    def __init__(self, label: str):
        self.label   = label
        self._stop   = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join()
        # Clear the line
        sys.stdout.write("\r" + " " * (len(self.label) + 28) + "\r")
        sys.stdout.flush()

    def _run(self):
        i = 0
        while not self._stop.is_set():
            frame = _FRAMES_BAR[i % len(_FRAMES_BAR)]
            sys.stdout.write(f"\r\033[36m{frame}\033[0m  {self.label}")
            sys.stdout.flush()
            time.sleep(0.09)
            i += 1


@contextmanager
def spinner(label: str = "..."):
    """Context manager: shows animated bar while block executes."""
    s = _Spinner(label)
    s.start()
    try:
        yield
    finally:
        s.stop()
