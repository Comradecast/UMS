import aiosqlite
import time
import logging
from services.status_enums import UMSMatchStatus

log = logging.getLogger(__name__)


class GlobalMatchService:
    """Service for unified match logging across all game modes and sources."""

    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def log_match(
        self,
        guild_id: int,
        mode: str,
        source: str,
        team1_score: int,
        team2_score: int,
        winner_team: int | None,
        status: str | UMSMatchStatus = UMSMatchStatus.COMPLETED,
    ) -> int:
        """Insert a match into matches_unified.

        Args:
            guild_id: Discord guild ID
            mode: '1v1', '2v2', '3v3', 'tournament_se', 'tournament_de'
            source: 'solo_queue', 'tournament_se', 'tournament_de'
            team1_score: Team 1 final score
            team2_score: Team 2 final score
            winner_team: 1, 2, or None for draw
            status: Match status (str or UMSMatchStatus enum), defaults to COMPLETED

        Returns:
            ID of the newly created match
        """
        # Normalize status to string
        if isinstance(status, UMSMatchStatus):
            status_value = status.value
        else:
            status_value = status

        created_at = int(time.time())
        completed_at = created_at if status_value == "COMPLETED" else None

        cursor = await self.db.execute(
            """
            INSERT INTO matches_unified (
                guild_id, mode, source,
                team1_score, team2_score, winner_team,
                created_at, completed_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                mode,
                source,
                team1_score,
                team2_score,
                winner_team,
                created_at,
                completed_at,
                status_value,
            ),
        )
        await self.db.commit()
        match_id = cursor.lastrowid

        log.info(
            f"[UMS] Logged {mode} {source} match {match_id} (status: {status_value}) for guild {guild_id}"
        )
        return match_id

    async def update_match_status(
        self, match_id: int, new_status: str | UMSMatchStatus
    ) -> None:
        """Update the status of an existing match.

        Args:
            match_id: ID of the match in matches_unified
            new_status: New status value (str or UMSMatchStatus enum)
        """
        # Normalize status to string
        if isinstance(new_status, UMSMatchStatus):
            status_value = new_status.value
        else:
            status_value = new_status

        await self.db.execute(
            "UPDATE matches_unified SET status = ? WHERE id = ?",
            (status_value, match_id),
        )
        await self.db.commit()
        log.info(f"[UMS] Updated match {match_id} status to: {status_value}")

    async def finalize_match(
        self,
        match_id: int,
        winner_team: int | None,
        team1_score: int,
        team2_score: int,
        final_status: str | UMSMatchStatus = UMSMatchStatus.COMPLETED,
    ) -> None:
        """Finalize a PENDING match with scores and completion status.

        Args:
            match_id: ID of the match in matches_unified
            winner_team: 1, 2, or None for draw
            team1_score: Final score for team 1
            team2_score: Final score for team 2
            final_status: Final status (str or UMSMatchStatus enum), defaults to COMPLETED
        """
        # Normalize status to string
        if isinstance(final_status, UMSMatchStatus):
            status_value = final_status.value
        else:
            status_value = final_status

        completed_at = int(time.time())

        await self.db.execute(
            """
            UPDATE matches_unified
            SET team1_score = ?, team2_score = ?, winner_team = ?,
                status = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                team1_score,
                team2_score,
                winner_team,
                status_value,
                completed_at,
                match_id,
            ),
        )
        await self.db.commit()
        log.info(
            f"[UMS] Finalized match {match_id}: {team1_score}-{team2_score}, winner_team={winner_team}, status={status_value}"
        )

    async def log_participants(
        self,
        match_id: int,
        players_team1: list[int],
        players_team2: list[int],
    ) -> None:
        """Log participants for a match.

        Args:
            match_id: ID of the match from matches_unified
            players_team1: List of player IDs on team 1
            players_team2: List of player IDs on team 2
        """
        # Insert team 1 participants
        for player_id in players_team1:
            await self.db.execute(
                """
                INSERT INTO match_participants (match_id, player_id, team_number)
                VALUES (?, ?, ?)
                """,
                (match_id, player_id, 1),
            )

        # Insert team 2 participants
        for player_id in players_team2:
            await self.db.execute(
                """
                INSERT INTO match_participants (match_id, player_id, team_number)
                VALUES (?, ?, ?)
                """,
                (match_id, player_id, 2),
            )

        await self.db.commit()
        log.info(
            f"[UMS] Logged {len(players_team1) + len(players_team2)} participants for match {match_id}"
        )

    async def get_recent_matches_for_player(
        self,
        player_id: int,
        limit: int = 5,
    ) -> list[dict]:
        """Get recent matches for a player from UMS.

        Args:
            player_id: Discord user ID
            limit: Max number of matches to return

        Returns:
            List of dicts with keys: match_id, mode, source, result, score_str, played_at
        """
        query = """
            SELECT
                m.id as match_id,
                m.mode,
                m.source,
                m.team1_score,
                m.team2_score,
                m.winner_team,
                m.created_at,
                m.completed_at,
                mp.team_number
            FROM matches_unified m
            JOIN match_participants mp ON m.id = mp.match_id
            WHERE mp.player_id = ?
            AND m.status = 'COMPLETED'
            ORDER BY COALESCE(m.completed_at, m.created_at) DESC
            LIMIT ?
        """

        matches = []
        async with self.db.execute(query, (player_id, limit)) as cursor:
            async for row in cursor:
                # Determine result
                if row["winner_team"] is None:
                    result = "D"
                elif row["winner_team"] == row["team_number"]:
                    result = "W"
                else:
                    result = "L"

                # Format score
                score_str = f"{row['team1_score']}-{row['team2_score']}"

                matches.append(
                    {
                        "match_id": row["match_id"],
                        "mode": row["mode"],
                        "source": row["source"],
                        "result": result,
                        "score_str": score_str,
                        "played_at": row["completed_at"] or row["created_at"],
                    }
                )

        return matches

    async def get_lifetime_record_for_player(
        self,
        player_id: int,
    ) -> dict:
        """Get lifetime W/L/D record for a player from UMS.

        Args:
            player_id: Discord user ID

        Returns:
            Dict with keys: total_wins, total_losses, total_draws, last_played_at
        """
        query = """
            SELECT
                m.winner_team,
                mp.team_number,
                COALESCE(m.completed_at, m.created_at) as played_at
            FROM matches_unified m
            JOIN match_participants mp ON m.id = mp.match_id
            WHERE mp.player_id = ?
            AND m.status = 'COMPLETED'
        """

        wins = 0
        losses = 0
        draws = 0
        last_played_at = 0

        async with self.db.execute(query, (player_id,)) as cursor:
            async for row in cursor:
                if row["winner_team"] is None:
                    draws += 1
                elif row["winner_team"] == row["team_number"]:
                    wins += 1
                else:
                    losses += 1

                if row["played_at"] and row["played_at"] > last_played_at:
                    last_played_at = row["played_at"]

        return {
            "total_wins": wins,
            "total_losses": losses,
            "total_draws": draws,
            "last_played_at": last_played_at if last_played_at > 0 else None,
        }
