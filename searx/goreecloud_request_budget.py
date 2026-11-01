# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bounded, log-free request admission for single-worker free Search.

This does not replace a distributed limiter for public, multiworker instances.
The free-first deployment is VPN-only, single-worker, and has no Valkey.
"""
from collections import deque
from math import ceil
from threading import Lock
from time import monotonic


class RequestBudget:
    """Global per-process sliding-window budget; stores no user/query data."""

    def __init__(self, limit: int, period: int = 60):
        if type(limit) is not int or not 1 <= limit <= 120:
            raise ValueError("request budget must be an integer between 1 and 120")
        if type(period) is not int or period < 1:
            raise ValueError("period must be a positive number of seconds")
        self.limit = limit
        self.period = period
        self._lock = Lock()
        self._recent: deque[float] = deque()

    def admit(self, *, now: float | None = None) -> tuple[bool, int]:
        when = monotonic() if now is None else now
        with self._lock:
            while self._recent and self._recent[0] <= when - self.period:
                self._recent.popleft()
            if len(self._recent) >= self.limit:
                return False, max(1, ceil(self._recent[0] + self.period - when))
            self._recent.append(when)
            return True, 0
