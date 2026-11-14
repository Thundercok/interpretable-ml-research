"""Unified navigation stack and state tracking for QuickDesk screens."""
from __future__ import annotations

from typing import List, Optional


class QuickNavigationStack:
    """Manages screen navigation history, return paths, and Esc unwinding."""

    def __init__(self) -> None:
        self._history: List[str] = []

    def push(self, view: str) -> None:
        if not self._history or self._history[-1] != view:
            self._history.append(view)

    def pop(self) -> Optional[str]:
        if len(self._history) > 1:
            self._history.pop()
            return self._history[-1]
        elif self._history:
            return self._history[0]
        return None

    def clear(self) -> None:
        self._history.clear()

    @property
    def current(self) -> str:
        return self._history[-1] if self._history else "none"
