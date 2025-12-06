"""
services/request_service.py — Tournament Request Service
---------------------------------------------------------
Manages tournament request lifecycle: create, approve, decline.
Implements rate-limiting, duplicate detection, and atomic state transitions.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple, List

import aiosqlite

log = logging.getLogger(__name__)

# Default rate limit: 1 request per hour
DEFAULT_COOLDOWN_SECONDS = 3600


@dataclass
class TournamentRequest:
    """Tournament request from tournament_requests table."""

    id: int
    guild_id: int
    requester_id: int
    name: str
    region: Optional[str] = None
    format: Optional[str] = None
    size: Optional[str] = None
    match_length: Optional[str] = None
    start_time: Optional[str] = None
    scheduled_start: Optional[int] = None
    rank_restriction: Optional[str] = None
    region_restriction: Optional[str] = None
    status: str = "pending"
    admin_message_id: Optional[int] = None
    resolved_by: Optional[int] = None
    resolved_at: Optional[int] = None
    decline_reason: Optional[str] = None
    tournament_key: Optional[str] = None
    created_at: Optional[int] = None

    @property
    def is_pending(self) -> bool:
        return self.status == "pending"

    @property
    def is_resolved(self) -> bool:
        return self.status in ("approved", "declined")


class RequestService:
    """
    Service for tournament request management.

    Provides:
    - Request creation with rate-limiting
    - Duplicate detection
    - Atomic approve/decline operations
    - Status queries
    """

    def __init__(self, db: aiosqlite.Connection):
        self.db = db
        self.db.row_factory = aiosqlite.Row
        self.cooldown_seconds = DEFAULT_COOLDOWN_SECONDS

    # -------------------------------------------------------------------------
    # CREATE
    # -------------------------------------------------------------------------

    async def create_request(
        self,
        guild_id: int,
        requester_id: int,
        name: str,
        region: Optional[str] = None,
        format: Optional[str] = None,
        size: Optional[str] = None,
        match_length: Optional[str] = None,
        start_time: Optional[str] = None,
        scheduled_start: Optional[int] = None,
        rank_restriction: Optional[str] = None,
        region_restriction: Optional[str] = None,
    ) -> Tuple[Optional[TournamentRequest], Optional[str]]:
        """
        Create a new tournament request.

        Returns: (request, error_message)
        - On success: (TournamentRequest, None)
        - On failure: (None, "error reason")
        """
        try:
            # Check rate limit
            can_create, reason = await self.check_rate_limit(requester_id)
            if not can_create:
                return None, reason

            # Check for duplicate pending request
            is_dupe = await self.check_duplicate(guild_id, name)
            if is_dupe:
                return None, f"A pending request named '{name}' already exists."

            # Create request
            cursor = await self.db.execute(
                """
                INSERT INTO tournament_requests (
                    guild_id, requester_id, name, region, format, size,
                    match_length, start_time, scheduled_start,
                    rank_restriction, region_restriction, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    guild_id,
                    requester_id,
                    name,
                    region,
                    format,
                    size,
                    match_length,
                    start_time,
                    scheduled_start,
                    rank_restriction,
                    region_restriction,
                ),
            )
            await self.db.commit()

            request_id = cursor.lastrowid
            log.info(
                f"[REQUEST-SERVICE] Created request #{request_id}: '{name}' "
                f"by user {requester_id} in guild {guild_id}"
            )

            # Set cooldown
            await self._set_cooldown(requester_id)

            # Fetch and return the created request
            request = await self.get_by_id(request_id)
            return request, None

        except Exception as e:
            log.error(f"[REQUEST-SERVICE] Create failed: {e}", exc_info=True)
            return None, f"Failed to create request: {str(e)}"

    # -------------------------------------------------------------------------
    # READ
    # -------------------------------------------------------------------------

    async def get_by_id(self, request_id: int) -> Optional[TournamentRequest]:
        """Get request by ID."""
        try:
            async with self.db.execute(
                "SELECT * FROM tournament_requests WHERE id = ?", (request_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return TournamentRequest(**dict(row))
            return None
        except Exception as e:
            log.error(f"[REQUEST-SERVICE] Get by ID failed: {e}")
            return None

    async def get_pending_by_id(self, request_id: int) -> Optional[TournamentRequest]:
        """Get pending request by ID. Returns None if not pending."""
        request = await self.get_by_id(request_id)
        if request and request.is_pending:
            return request
        return None

    async def get_pending_for_guild(self, guild_id: int) -> List[TournamentRequest]:
        """Get all pending requests for a guild."""
        try:
            async with self.db.execute(
                """
                SELECT * FROM tournament_requests
                WHERE guild_id = ? AND status = 'pending'
                ORDER BY created_at DESC
                """,
                (guild_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [TournamentRequest(**dict(row)) for row in rows]
        except Exception as e:
            log.error(f"[REQUEST-SERVICE] Get pending failed: {e}")
            return []

    async def get_recent_for_guild(
        self, guild_id: int, limit: int = 10
    ) -> List[TournamentRequest]:
        """Get recent requests for a guild (all statuses)."""
        try:
            async with self.db.execute(
                """
                SELECT * FROM tournament_requests
                WHERE guild_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (guild_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
                return [TournamentRequest(**dict(row)) for row in rows]
        except Exception as e:
            log.error(f"[REQUEST-SERVICE] Get recent failed: {e}")
            return []

    # -------------------------------------------------------------------------
    # APPROVE / DECLINE
    # -------------------------------------------------------------------------

    async def approve_request(
        self,
        request_id: int,
        admin_id: int,
        tournament_key: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Atomically approve a pending request.

        Returns: (success, error_message)
        - On success: (True, None)
        - On failure: (False, "reason")
        """
        try:
            # Fetch current state
            request = await self.get_by_id(request_id)
            if not request:
                return False, "Request not found."

            if request.status != "pending":
                return False, f"Request already {request.status}."

            # Atomically update
            now = int(time.time())
            result = await self.db.execute(
                """
                UPDATE tournament_requests
                SET status = 'approved', resolved_by = ?, resolved_at = ?, tournament_key = ?
                WHERE id = ? AND status = 'pending'
                """,
                (admin_id, now, tournament_key, request_id),
            )
            await self.db.commit()

            if result.rowcount == 0:
                return False, "Request was modified by another action."

            log.info(
                f"[REQUEST-SERVICE] Approved request #{request_id} by admin {admin_id}"
            )
            return True, None

        except Exception as e:
            log.error(f"[REQUEST-SERVICE] Approve failed: {e}", exc_info=True)
            return False, f"Failed to approve: {str(e)}"

    async def decline_request(
        self,
        request_id: int,
        admin_id: int,
        reason: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Atomically decline a pending request.

        Returns: (success, error_message)
        """
        try:
            # Fetch current state
            request = await self.get_by_id(request_id)
            if not request:
                return False, "Request not found."

            if request.status != "pending":
                return False, f"Request already {request.status}."

            # Atomically update
            now = int(time.time())
            result = await self.db.execute(
                """
                UPDATE tournament_requests
                SET status = 'declined', resolved_by = ?, resolved_at = ?, decline_reason = ?
                WHERE id = ? AND status = 'pending'
                """,
                (admin_id, now, reason, request_id),
            )
            await self.db.commit()

            if result.rowcount == 0:
                return False, "Request was modified by another action."

            log.info(
                f"[REQUEST-SERVICE] Declined request #{request_id} by admin {admin_id}"
                + (f" - {reason}" if reason else "")
            )
            return True, None

        except Exception as e:
            log.error(f"[REQUEST-SERVICE] Decline failed: {e}", exc_info=True)
            return False, f"Failed to decline: {str(e)}"

    async def set_admin_message_id(self, request_id: int, message_id: int) -> bool:
        """Store the admin channel message ID for a request."""
        try:
            await self.db.execute(
                "UPDATE tournament_requests SET admin_message_id = ? WHERE id = ?",
                (message_id, request_id),
            )
            await self.db.commit()
            return True
        except Exception as e:
            log.error(f"[REQUEST-SERVICE] Set message ID failed: {e}")
            return False

    # -------------------------------------------------------------------------
    # RATE LIMITING
    # -------------------------------------------------------------------------

    async def check_rate_limit(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if user can submit a request.

        Returns: (can_submit, reason_if_not)
        """
        try:
            # Check ban first
            async with self.db.execute(
                "SELECT reason FROM organizer_bans WHERE user_id = ?", (user_id,)
            ) as cursor:
                ban = await cursor.fetchone()
                if ban:
                    return (
                        False,
                        f"You are banned from creating tournaments: {ban['reason']}",
                    )

            # Check cooldown
            async with self.db.execute(
                "SELECT cooldown_until FROM organizer_cooldowns WHERE user_id = ?",
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    cooldown_until = row["cooldown_until"]
                    now = int(time.time())
                    if now < cooldown_until:
                        remaining = cooldown_until - now
                        minutes = remaining // 60
                        if minutes > 0:
                            return (
                                False,
                                f"Please wait {minutes} more minute(s) before submitting another request.",
                            )
                        else:
                            return (
                                False,
                                f"Please wait {remaining} more seconds before submitting another request.",
                            )

            return True, None

        except Exception as e:
            log.error(f"[REQUEST-SERVICE] Rate limit check failed: {e}")
            # Fail open - allow request if check fails
            return True, None

    async def _set_cooldown(self, user_id: int) -> None:
        """Set cooldown after creating a request."""
        cooldown_until = int(time.time()) + self.cooldown_seconds
        try:
            await self.db.execute(
                "INSERT OR REPLACE INTO organizer_cooldowns (user_id, cooldown_until) VALUES (?, ?)",
                (user_id, cooldown_until),
            )
            await self.db.commit()
        except Exception as e:
            log.error(f"[REQUEST-SERVICE] Set cooldown failed: {e}")

    async def clear_cooldown(self, user_id: int) -> bool:
        """Clear cooldown for a user (e.g., on declined request)."""
        try:
            await self.db.execute(
                "DELETE FROM organizer_cooldowns WHERE user_id = ?", (user_id,)
            )
            await self.db.commit()
            return True
        except Exception as e:
            log.error(f"[REQUEST-SERVICE] Clear cooldown failed: {e}")
            return False

    # -------------------------------------------------------------------------
    # DUPLICATE DETECTION
    # -------------------------------------------------------------------------

    async def check_duplicate(self, guild_id: int, name: str) -> bool:
        """Check if a pending request with same name exists in guild."""
        try:
            async with self.db.execute(
                """
                SELECT 1 FROM tournament_requests
                WHERE guild_id = ? AND LOWER(name) = LOWER(?) AND status = 'pending'
                """,
                (guild_id, name),
            ) as cursor:
                return await cursor.fetchone() is not None
        except Exception as e:
            log.error(f"[REQUEST-SERVICE] Duplicate check failed: {e}")
            return False

    # -------------------------------------------------------------------------
    # STATS
    # -------------------------------------------------------------------------

    async def get_stats(self, guild_id: int) -> dict:
        """Get request statistics for a guild."""
        try:
            stats = {"pending": 0, "approved": 0, "declined": 0, "total": 0}

            async with self.db.execute(
                """
                SELECT status, COUNT(*) as count
                FROM tournament_requests
                WHERE guild_id = ?
                GROUP BY status
                """,
                (guild_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    stats[row["status"]] = row["count"]
                    stats["total"] += row["count"]

            return stats
        except Exception as e:
            log.error(f"[REQUEST-SERVICE] Get stats failed: {e}")
            return {"pending": 0, "approved": 0, "declined": 0, "total": 0}
