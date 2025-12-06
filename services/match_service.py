"""
Match Service - SE Tournament Elo Support for Core Bot
-------------------------------------------------------
core-bot: Solo queue functions removed; this service only supports
SE tournament Elo calculations and match recording.
"""

import logging
from typing import Optional

import aiosqlite

from database import DB_NAME
from services.status_enums import MatchStatus

log = logging.getLogger(__name__)


class MatchService:
    """Service for SE tournament match Elo calculations."""

    @staticmethod
    def calculate_elo_change(
        winner_elo: int, loser_elo: int, k_factor: int = 32
    ) -> tuple[int, int]:
        """
        Calculate Elo rating changes for winner and loser.

        Args:
            winner_elo: Current Elo of the winner
            loser_elo: Current Elo of the loser
            k_factor: K-factor for Elo calculation (default 32)

        Returns:
            Tuple of (winner_delta, loser_delta)
        """
        # Expected score calculation
        expected_winner = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
        expected_loser = 1 / (1 + 10 ** ((winner_elo - loser_elo) / 400))

        # Actual scores (winner gets 1, loser gets 0)
        winner_change = round(k_factor * (1 - expected_winner))
        loser_change = round(k_factor * (0 - expected_loser))

        return winner_change, loser_change

    @classmethod
    async def record_tournament_result(
        cls,
        tournament_key: str,
        match_id_in_tournament: int,
        p1_id: int,
        p2_id: int,
        winner_id: int,
        score: str,
        *,
        round_in_tournament: int,
        channel_id: Optional[int] = None,
    ) -> None:
        """
        Ensure there is a canonical matches row for a completed bracket match.

        - If a row with (tournament_key, match_id_in_tournament) exists,
          UPDATE winner_id, score, status, channel_id.
        - If not, INSERT a new row with status = COMPLETED.
        """
        async with aiosqlite.connect(DB_NAME) as db:
            cursor = await db.execute(
                """
                SELECT id
                FROM matches
                WHERE tournament_key = ? AND match_id_in_tournament = ?
                """,
                (tournament_key, match_id_in_tournament),
            )
            row = await cursor.fetchone()

            if row:
                await db.execute(
                    """
                    UPDATE matches
                    SET p1_id = ?,
                        p2_id = ?,
                        winner_id = ?,
                        score = ?,
                        status = ?,
                        channel_id = ?
                    WHERE tournament_key = ? AND match_id_in_tournament = ?
                    """,
                    (
                        p1_id,
                        p2_id,
                        winner_id,
                        score,
                        MatchStatus.COMPLETED.value,
                        channel_id,
                        tournament_key,
                        match_id_in_tournament,
                    ),
                )
            else:
                await db.execute(
                    """
                    INSERT INTO matches (
                        tournament_key,
                        match_id_in_tournament,
                        p1_id,
                        p2_id,
                        winner_id,
                        round,
                        score,
                        status,
                        channel_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tournament_key,
                        match_id_in_tournament,
                        p1_id,
                        p2_id,
                        winner_id,
                        round_in_tournament,
                        score,
                        MatchStatus.COMPLETED.value,
                        channel_id,
                    ),
                )

            await db.commit()
