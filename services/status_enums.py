"""
Status Enums for Tournament Engine (Epic 5.1.3)

Canonical definitions for tournament and match lifecycle states.
All cogs and services should import from here.
"""

from enum import Enum


class TournamentStatus(str, Enum):
    """Tournament lifecycle states."""

    DRAFT = "draft"  # Created but not yet published
    OPEN = "open"  # Registration open, accepting players
    STARTED = "started"  # Tournament running, matches in progress
    RUNNING = "running"  # Tournament actively running (same as STARTED)
    COMPLETED = "completed"  # Tournament finished, results posted
    CANCELLED = "cancelled"  # Tournament cancelled/abandoned
    ARCHIVED = "archived"  # Tournament archived after completion


class MatchStatus(str, Enum):
    """Match lifecycle states (applies to tournament matches and solo queue)."""

    PENDING = "pending"  # Match created, waiting for result
    IN_PROGRESS = "in_progress"  # Match actively being played
    COMPLETED = "completed"  # Result reported and confirmed
    CANCELLED = "cancelled"  # Match cancelled/voided


class UMSMatchStatus(str, Enum):
    """Unified Match System status values.

    Separate from MatchStatus to avoid coupling with legacy tournament system.
    UMS uses uppercase values for consistency with Phase 1 implementation.
    """

    PENDING = "PENDING"
    LIVE = "LIVE"
    REPORTED = "REPORTED"
    CONFIRMED = "CONFIRMED"
    NO_SHOW = "NO_SHOW"
    CANCELED = "CANCELED"
    DISPUTED = "DISPUTED"
    COMPLETED = "COMPLETED"
