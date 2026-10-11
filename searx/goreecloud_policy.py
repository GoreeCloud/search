# SPDX-License-Identifier: AGPL-3.0-or-later
"""GoreeCloud Search privacy limits, applied before network dispatch.

This module deliberately has no Flask, logging or provider-transport dependency.
It never stores, emits or normalizes the user's raw search terms.
"""

from __future__ import annotations

from collections.abc import Iterable


class SearchPolicyViolation(ValueError):
    """A query was rejected before it could reach an external provider."""

    def __init__(self, message: str, http_status: int):
        super().__init__(message)
        self.http_status = http_status


def validate_transport(*, method: str, query_in_url: bool, private: bool) -> None:
    """Reject query-bearing GET requests and all URL query parameters in private mode."""
    if private and (query_in_url or method.upper() != "POST"):
        raise SearchPolicyViolation(
            "Private searches must use POST without query parameters in the URL.", 405
        )


def validate_disclosure(
    query: str,
    provider_names: Iterable[str],
    *,
    max_query_chars: int,
    max_providers: int,
) -> int:
    """Bound query size and unique provider fanout without silently truncating results.

    All checks happen *before* constructing a provider execution object.
    A zero limit means no maximum; negative settings are always invalid.
    """
    if max_query_chars < 0 or max_providers < 0:
        raise ValueError("Privacy limits must be non-negative")
    if max_query_chars and len(query) > max_query_chars:
        raise SearchPolicyViolation("Search query exceeds the configured length limit.", 413)
    unique = {name.casefold() for name in provider_names}
    if max_providers and len(unique) > max_providers:
        raise SearchPolicyViolation(
            "Too many sources for this search. Select fewer categories or engines.", 422
        )
    return len(unique)
