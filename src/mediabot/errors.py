"""Base exception carrying an error code from docs/PLAN.md §8.2."""

from __future__ import annotations


class MediabotError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message
