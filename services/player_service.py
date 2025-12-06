"""
services/player_service.py — Player Service for UMS Core
---------------------------------------------------------
Minimal player management for onboarding and basic profile.

UMS Core uses simplified players table with only essential fields:
- discord_id, display_name, region, primary_mode, claimed_rank, has_onboarded
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import aiosqlite

log = logging.getLogger(__name__)


@dataclass
class Player:
    """Player data for UMS Core (minimal profile)."""

    user_id: int
    discord_id: Optional[int] = None
    display_name: Optional[str] = None
    region: Optional[str] = None
    primary_mode: Optional[str] = None
    claimed_rank: Optional[str] = None
    has_onboarded: int = 0
    created_at: Optional[int] = None
    updated_at: Optional[int] = None

    @property
    def id(self) -> int:
        """Alias for compatibility."""
        return self.user_id


class PlayerService:
    """
    Service for player management in UMS Core.

    Provides:
    - get_or_create: Ensure player exists
    - complete_onboarding: Set profile data
    - update_region/rank: Profile updates
    """

    def __init__(self, db: aiosqlite.Connection):
        self.db = db
        self.db.row_factory = aiosqlite.Row

    async def get_by_discord_id(self, discord_id: int) -> Optional[Player]:
        """Get player by Discord ID."""
        try:
            async with self.db.execute(
                "SELECT * FROM players WHERE discord_id = ?", (discord_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_player(row)
            return None
        except Exception as e:
            log.error(f"[PLAYER-SERVICE] Get failed: {e}")
            return None

    async def get_by_id(self, player_id: int) -> Optional[Player]:
        """Get player by user_id."""
        try:
            async with self.db.execute(
                "SELECT * FROM players WHERE user_id = ?", (player_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return self._row_to_player(row)
            return None
        except Exception as e:
            log.error(f"[PLAYER-SERVICE] Get by ID failed: {e}")
            return None

    async def get_or_create(
        self, discord_id: int, display_name: Optional[str] = None
    ) -> Player:
        """Get existing player or create new one."""
        player = await self.get_by_discord_id(discord_id)
        if player:
            return player

        # Create new player
        now = int(time.time())
        try:
            await self.db.execute(
                """
                INSERT INTO players (user_id, discord_id, display_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (discord_id, discord_id, display_name, now, now),
            )
            await self.db.commit()

            player = await self.get_by_discord_id(discord_id)
            if player:
                log.info(f"[PLAYER-SERVICE] Created player: {discord_id}")
                return player

            # Fallback
            return Player(user_id=discord_id, discord_id=discord_id)

        except Exception as e:
            log.error(f"[PLAYER-SERVICE] Create failed: {e}")
            return Player(user_id=discord_id, discord_id=discord_id)

    async def complete_onboarding(
        self,
        discord_id: int,
        region: str,
        claimed_rank: str,
        primary_mode: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> bool:
        """
        Complete player onboarding.

        Idempotent: safe to call multiple times, just updates profile.
        """
        try:
            # Ensure player exists
            await self.get_or_create(discord_id, display_name)

            now = int(time.time())
            await self.db.execute(
                """
                UPDATE players SET
                    region = ?,
                    claimed_rank = ?,
                    primary_mode = ?,
                    display_name = COALESCE(?, display_name),
                    has_onboarded = 1,
                    updated_at = ?
                WHERE discord_id = ?
                """,
                (region, claimed_rank, primary_mode, display_name, now, discord_id),
            )
            await self.db.commit()

            log.info(
                f"[PLAYER-SERVICE] Onboarding complete: {discord_id} "
                f"region={region} rank={claimed_rank}"
            )
            return True

        except Exception as e:
            log.error(f"[PLAYER-SERVICE] Onboarding failed: {e}")
            return False

    async def update_region(self, discord_id: int, region: str) -> bool:
        """Update player region."""
        try:
            now = int(time.time())
            await self.db.execute(
                "UPDATE players SET region = ?, updated_at = ? WHERE discord_id = ?",
                (region, now, discord_id),
            )
            await self.db.commit()
            return True
        except Exception as e:
            log.error(f"[PLAYER-SERVICE] Update region failed: {e}")
            return False

    async def update_rank(self, discord_id: int, rank: str) -> bool:
        """Update player claimed rank."""
        try:
            now = int(time.time())
            await self.db.execute(
                "UPDATE players SET claimed_rank = ?, updated_at = ? WHERE discord_id = ?",
                (rank, now, discord_id),
            )
            await self.db.commit()
            return True
        except Exception as e:
            log.error(f"[PLAYER-SERVICE] Update rank failed: {e}")
            return False

    async def is_onboarded(self, discord_id: int) -> bool:
        """Check if player has completed onboarding."""
        player = await self.get_by_discord_id(discord_id)
        return player is not None and player.has_onboarded == 1

    async def get_all_players(self, limit: int = 100) -> list[Player]:
        """Get all players (limited)."""
        try:
            async with self.db.execute(
                "SELECT * FROM players ORDER BY created_at DESC LIMIT ?", (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_player(row) for row in rows]
        except Exception as e:
            log.error(f"[PLAYER-SERVICE] Get all failed: {e}")
            return []

    async def count_players(self) -> int:
        """Count total players."""
        try:
            async with self.db.execute("SELECT COUNT(*) FROM players") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            log.error(f"[PLAYER-SERVICE] Count failed: {e}")
            return 0

    def _row_to_player(self, row) -> Player:
        """Convert database row to Player object."""
        if hasattr(row, "keys"):
            data = dict(row)
        else:
            # Fallback for tuple rows
            data = {
                "user_id": row[0],
                "discord_id": row[1],
                "display_name": row[2] if len(row) > 2 else None,
                "region": row[3] if len(row) > 3 else None,
                "primary_mode": row[4] if len(row) > 4 else None,
                "claimed_rank": row[5] if len(row) > 5 else None,
                "has_onboarded": row[6] if len(row) > 6 else 0,
                "created_at": row[7] if len(row) > 7 else None,
                "updated_at": row[8] if len(row) > 8 else None,
            }

        return Player(
            user_id=data.get("user_id") or data.get("discord_id"),
            discord_id=data.get("discord_id"),
            display_name=data.get("display_name"),
            region=data.get("region"),
            primary_mode=data.get("primary_mode"),
            claimed_rank=data.get("claimed_rank"),
            has_onboarded=data.get("has_onboarded", 0) or 0,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
