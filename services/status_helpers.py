# services/status_helpers.py
from __future__ import annotations

from typing import Iterable

from services.status_enums import TournamentStatus, MatchStatus


# ── Tournament status helpers ──────────────────────────────────────────────


def is_tournament_open(status: str) -> bool:
    return status == TournamentStatus.OPEN.value


def is_tournament_running(status: str) -> bool:
    return status in (
        TournamentStatus.STARTED.value,
        TournamentStatus.RUNNING.value,
    )


def is_tournament_finished(status: str) -> bool:
    return status in (
        TournamentStatus.COMPLETED.value,
        TournamentStatus.CANCELLED.value,
    )


def tournament_status_in(status: str, statuses: Iterable[TournamentStatus]) -> bool:
    return status in {s.value for s in statuses}


# ── Match status helpers ───────────────────────────────────────────────────


def is_match_pending(status: str) -> bool:
    return status == MatchStatus.PENDING.value


def is_match_completed(status: str) -> bool:
    return status == MatchStatus.COMPLETED.value


def is_match_active(status: str) -> bool:
    """Pending or in-progress."""
    return status in (
        MatchStatus.PENDING.value,
        MatchStatus.IN_PROGRESS.value,
    )


def is_match_finished(status: str) -> bool:
    """Completed or cancelled."""
    return status in (
        MatchStatus.COMPLETED.value,
        MatchStatus.CANCELLED.value,
    )


def match_status_in(status: str, statuses: Iterable[MatchStatus]) -> bool:
    return status in {s.value for s in statuses}
