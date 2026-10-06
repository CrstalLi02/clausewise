"""In-memory fixed-window rate limiter.

Effective within a single process; replace with Redis counters for multi-replica deployments (the login endpoint currently runs in a single backend process, which is sufficient).
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict


class MemoryRateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        return [t for t in self._attempts[key] if now - t < self.window_seconds]

    def check(self, key: str) -> bool:
        """Whether the attempt is currently allowed (limit not exceeded)."""
        now = time.monotonic()
        with self._lock:
            return len(self._recent(key, now)) < self.max_attempts

    def hit(self, key: str) -> None:
        """Record an attempt (call on failure)."""
        now = time.monotonic()
        with self._lock:
            recent = self._recent(key, now)
            recent.append(now)
            self._attempts[key] = recent

    def clear(self, key: str) -> None:
        """Clear the record after success."""
        with self._lock:
            self._attempts.pop(key, None)

    def remaining(self, key: str) -> int:
        """Remaining attempts within the window (useful for response headers)."""
        now = time.monotonic()
        with self._lock:
            return max(0, self.max_attempts - len(self._recent(key, now)))
