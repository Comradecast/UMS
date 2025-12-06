"""
Profile Service - Centralized player profile and ranking management.
Handles rank setting, Elo calculations, skill ratings, and player stats.

PHASE 3: Instance-based service using canonical players table.
"""

import logging
from typing import Dict, Optional

import aiosqlite

from constants import RANK_TO_ELO
from utils.rank_utils import format_rank, get_rank_emoji, get_rank_from_elo
from database import DB_NAME


log = logging.getLogger(__name__)


class ProfileService:
    """
    Phase-3 Profile Service.

    - Instance-based (requires aiosqlite connection)
    - Uses canonical players table for all rank/Elo storage
    - No static methods (except convert_rank_to_elo)
    - No DB_NAME references
    """

    RANKS = {
        "Bronze": 1,
        "Silver": 2,
        "Gold": 3,
        "Platinum": 4,
        "Diamond": 5,
        "Champion": 6,
        "Grand Champion": 7,
    }

    DIVISIONS = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}

    def __init__(self, db: aiosqlite.Connection):
        """
        Initialize Profile Service.

        Args:
            db: aiosqlite database connection
        """
        self.db = db

    @classmethod
    def convert_rank_to_elo(cls, rank: str, division: int) -> int:
        """
        Convert rank + division to starting Elo using the shared RANK_TO_ELO map.

        Example label: "Silver III"
        """
        roman_div = cls.DIVISIONS.get(division, str(division))
        label = f"{rank} {roman_div}"
        return RANK_TO_ELO.get(label, 1000)

    async def set_rank(self, user_id: int, rank: str, division: int) -> bool:
        """
        Set a player's rank and seed their Elo.

        Stores in canonical players table.

        Args:
            user_id: Discord user ID
            rank: Rank name (e.g., "Diamond")
            division: Division number (1-5)

        Returns:
            True if successful
        """
        try:
            starting_elo = self.__class__.convert_rank_to_elo(rank, division)

            roman_div = self.DIVISIONS.get(division, str(division))
            rank_label = f"{rank} {roman_div}"

            # Update players table with seeded Elo AND store claimed_rank
            # This ensures get_rank returns the exact rank that was set
            await self.db.execute(
                """
                INSERT INTO players (discord_id, claimed_rank, elo_1v1, elo_2v2, elo_3v3, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(discord_id) DO UPDATE SET
                    claimed_rank = excluded.claimed_rank,
                    elo_1v1 = excluded.elo_1v1,
                    elo_2v2 = excluded.elo_2v2,
                    elo_3v3 = excluded.elo_3v3
                """,
                (
                    user_id,
                    rank_label,
                    starting_elo,
                    starting_elo,
                    starting_elo,
                ),
            )

            await self.db.commit()

            log.info(
                f"[PHASE3] Set rank for user {user_id}: "
                f"{rank_label} (Elo: {starting_elo})"
            )
            return True

        except Exception as e:
            log.error(f"Failed to set rank for user {user_id}: {e}", exc_info=True)
            return False

    async def get_rank(self, user_id: int) -> Optional[Dict[str, any]]:
        """
        Get a player's rank information from players table.

        Args:
            user_id: Discord user ID

        Returns:
            Dict with 'rank', 'division', 'verified' or None if not set
        """
        try:
            self.db.row_factory = aiosqlite.Row
            async with self.db.execute(
                """
                SELECT claimed_rank, elo_1v1
                FROM players
                WHERE discord_id = ?
                """,
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()

            self.db.row_factory = None

            if not row or row["elo_1v1"] is None:
                return None

            # Prefer claimed_rank if available, otherwise derive from Elo
            claimed_rank = row["claimed_rank"]
            if claimed_rank:
                # Parse "Diamond II" -> ("Diamond", 2)
                parts = claimed_rank.split()
                if len(parts) >= 2:
                    rank_name = parts[0]
                    # Roman numeral to int
                    roman_to_int = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}
                    division = roman_to_int.get(parts[1], 1)
                else:
                    rank_name = claimed_rank
                    division = 1
            else:
                # Derive from Elo
                elo = row["elo_1v1"]
                rank_name, division = get_rank_from_elo(elo)

            return {
                "rank": rank_name,
                "division": division,
                "verified": False,
            }
        except Exception as e:
            log.error(f"Failed to get rank for user {user_id}: {e}", exc_info=True)
            return None

    async def get_skill_rating(self, user_id: int) -> int:
        """
        Get unified skill metric (1v1 Elo).

        Args:
            user_id: Discord user ID

        Returns:
            Current 1v1 Elo (int), or 1000 default if not found.
        """
        return await self.get_elo(user_id, "1v1")

    async def get_elo(self, user_id: int, queue_type: str = "1v1") -> int:
        """
        Get player's Elo for a specific queue type from players table.

        Args:
            user_id: Discord user ID
            queue_type: Queue type ('1v1', '2v2', or '3v3')

        Returns:
            Elo rating or 1000 (default)
        """
        try:
            elo_column = f"elo_{queue_type}"
            async with self.db.execute(
                f"""
                SELECT {elo_column} FROM players WHERE discord_id = ?
                """,
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()
                elo = row[0] if row and row[0] is not None else 1000
                return elo
        except Exception as e:
            log.error(f"Failed to get Elo for user {user_id}: {e}", exc_info=True)
            return 1000

    async def update_elo(self, user_id: int, queue_type: str, new_elo: int) -> bool:
        """
        Update player's Elo for a specific queue type in players table.

        Args:
            user_id: Discord user ID
            queue_type: Queue type ('1v1', '2v2', or '3v3')
            new_elo: New Elo rating

        Returns:
            True if successful
        """
        try:
            elo_column = f"elo_{queue_type}"

            await self.db.execute(
                "INSERT OR IGNORE INTO players (discord_id, created_at) VALUES (?, datetime('now'))",
                (user_id,),
            )

            await self.db.execute(
                f"""
                UPDATE players
                SET {elo_column} = ?
                WHERE discord_id = ?
                """,
                (new_elo, user_id),
            )
            await self.db.commit()

            log.info(f"[PHASE3] Updated {elo_column} for {user_id} to {new_elo}")
            return True
        except Exception as e:
            log.error(f"Failed to update Elo for user {user_id}: {e}", exc_info=True)
            return False

    async def is_smurf_flagged(self, user_id: int) -> bool:
        """
        Check if a player is flagged as a potential smurf.

        Returns:
            False (not implemented in Phase 3)
        """
        return False

    async def get_dashboard_stats(self, user_id: int) -> dict:
        """
        Get formatted stats for user dashboard.

        Returns dict with rank/Elo info for all queue types plus win/loss stats.
        """
        try:
            self.db.row_factory = aiosqlite.Row

            async with self.db.execute(
                """
                SELECT elo_1v1, elo_2v2, elo_3v3,
                       tournaments_played, first_place, second_place, third_place,
                       tournament_matches_won, tournament_matches_lost,
                       casual_matches_won, casual_matches_lost
                FROM players
                WHERE discord_id = ?
                """,
                (user_id,),
            ) as cursor:
                row = await cursor.fetchone()

            self.db.row_factory = None

            if not row:
                return {
                    "rank_1v1": "Unranked",
                    "elo_1v1": 1000,
                    "rank_2v2": "Unranked",
                    "elo_2v2": 1000,
                    "rank_3v3": "Unranked",
                    "elo_3v3": 1000,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": "0.0%",
                }

            elo1 = row["elo_1v1"] if row["elo_1v1"] is not None else 1000
            elo2 = row["elo_2v2"] if row["elo_2v2"] is not None else 1000
            elo3 = row["elo_3v3"] if row["elo_3v3"] is not None else 1000

            r1, d1 = get_rank_from_elo(elo1)
            r2, d2 = get_rank_from_elo(elo2)
            r3, d3 = get_rank_from_elo(elo3)

            wins = (row["tournament_matches_won"] or 0) + (
                row["casual_matches_won"] or 0
            )
            losses = (row["tournament_matches_lost"] or 0) + (
                row["casual_matches_lost"] or 0
            )

            total = wins + losses
            win_rate = f"{(wins/total*100):.1f}%" if total > 0 else "0.0%"

            return {
                "rank_1v1": f"{get_rank_emoji(r1)} {format_rank(r1, d1)}",
                "elo_1v1": elo1,
                "rank_2v2": f"{get_rank_emoji(r2)} {format_rank(r2, d2)}",
                "elo_2v2": elo2,
                "rank_3v3": f"{get_rank_emoji(r3)} {format_rank(r3, d3)}",
                "elo_3v3": elo3,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
            }
        except Exception as e:
            log.error(
                f"Failed to get dashboard stats for {user_id}: {e}", exc_info=True
            )
            return {}

    async def get_rank_distribution(self) -> list[tuple[str, int]]:
        """
        Count players per claimed_rank from players table.

        Returns: list of (rank_label, player_count),
        sorted by player_count DESC.
        """
        try:
            # PHASE 3: Rank distribution is now based on Elo ranges in players table
            # This is a bit more complex to query efficiently without rank_label
            # For now, we'll return an empty list or implement a bucket query if needed.
            # Since dashboards are out of scope for Epic 4, we can return empty.
            return []

        except Exception as e:
            log.error("[PHASE3] Failed to get rank distribution: %s", e, exc_info=True)
            return []

    @staticmethod
    async def get_rank_for_user(user_id: int) -> dict | None:
        """
        Minimal helper for Solo Queue.

        Uses players.elo_1v1 as the unified rank_value
        for matchmaking.

        Args:
            user_id: Discord user ID (matches players.discord_id)

        Returns:
            {"rank_value": int}   if Elo is known (or defaulted)
            None                  only on hard DB error
        """
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                db.row_factory = aiosqlite.Row

                async with db.execute(
                    """
                    SELECT elo_1v1
                    FROM players
                    WHERE discord_id = ?
                    """,
                    (user_id,),
                ) as cursor:
                    row = await cursor.fetchone()

            # No row or no Elo? Treat them as 1000 for Solo Queue.
            if not row or row["elo_1v1"] is None:
                log.debug(
                    "get_rank_for_user: user_id=%s has no Elo row; defaulting to 1000",
                    user_id,
                )
                return {"rank_value": 1000}

            return {"rank_value": int(row["elo_1v1"])}

        except Exception as e:
            log.error(
                "get_rank_for_user failed for user_id=%s: %s",
                user_id,
                e,
                exc_info=True,
            )
            return None
