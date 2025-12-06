"""
Helper functions for tournament and match queries.
"""

import time
from typing import List, Optional, Tuple

import aiosqlite

from database import DB_NAME


async def get_next_match_for_user(user_id: int) -> Optional[dict]:
    """
    Find user's next pending/in-progress match.

    Args:
        user_id: Discord user ID

    Returns:
        Dictionary with match details or None if no pending match:
        {
            'match_id': int,
            'tournament_key': str,
            'tournament_name': str,
            'opponent_names': list[str],
            'opponent_ids': list[int],
            'scheduled_time': int | None,
            'channel_id': int | None,
            'team_size': int
        }
    """
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row

        # Find teams user belongs to
        cursor = await db.execute(
            "SELECT DISTINCT team_id FROM team_members WHERE user_id = ?", (user_id,)
        )
        user_teams = [row[0] for row in await cursor.fetchall()]

        # Build query for matches
        # Check both 1v1 matches (p1_id/p2_id as user) and team matches
        query = """
            SELECT
                m.id as match_id,
                m.tournament_key,
                m.p1_id,
                m.p2_id,
                m.scheduled_time,
                m.channel_id,
                m.round,
                t.name as tournament_name,
                t.team_size
            FROM matches m
            JOIN tournaments t ON t.key = m.tournament_key
            WHERE m.status IN ('pending', 'in_progress')
              AND t.status IN ('open', 'started')
        """

        # Add conditions: user is either p1/p2 (1v1) OR user's team is p1/p2
        params = []
        conditions = []

        # For 1v1 tournaments
        conditions.append("(t.team_size = 1 AND (m.p1_id = ? OR m.p2_id = ?))")
        params.extend([str(user_id), str(user_id)])

        # For team tournaments
        if user_teams:
            placeholders = ",".join("?" for _ in user_teams)
            conditions.append(
                f"(t.team_size > 1 AND (m.p1_id IN ({placeholders}) OR m.p2_id IN ({placeholders})))"
            )
            params.extend(user_teams)
            params.extend(user_teams)

        query += f" AND ({' OR '.join(conditions)})"
        query += " ORDER BY m.scheduled_time ASC NULLS LAST, m.id ASC LIMIT 1"

        cursor = await db.execute(query, params)
        row = await cursor.fetchone()

        if not row:
            return None

        # Determine opponent
        user_entity = (
            str(user_id)
            if row["team_size"] == 1
            else (user_teams[0] if user_teams else None)
        )
        if not user_entity:
            return None

        opponent_id = row["p2_id"] if row["p1_id"] == user_entity else row["p1_id"]

        # Get opponent names
        opponent_names = []
        opponent_ids = []

        if row["team_size"] == 1:
            # 1v1 - opponent is a user
            try:
                opp_user_id = int(opponent_id)
                opponent_ids.append(opp_user_id)
                # Name will be fetched from Discord, just store ID for now
                opponent_names.append(f"User {opponent_id}")
            except:
                opponent_names.append("Unknown")
        else:
            # Team match - get team members
            cursor = await db.execute(
                "SELECT user_id FROM team_members WHERE team_id = ?", (opponent_id,)
            )
            members = await cursor.fetchall()
            opponent_ids = [m[0] for m in members]
            # Names will be fetched from Discord
            if opponent_ids:
                opponent_names = [f"User {uid}" for uid in opponent_ids]
            else:
                opponent_names = ["Unknown Team"]

        return {
            "match_id": row["match_id"],
            "tournament_key": row["tournament_key"],
            "tournament_name": row["tournament_name"],
            "opponent_names": opponent_names,
            "opponent_ids": opponent_ids,
            "scheduled_time": row["scheduled_time"],
            "channel_id": row["channel_id"],
            "team_size": row["team_size"],
        }


async def get_upcoming_user_tournaments(
    user_id: int, window_seconds: int = 86400
) -> List[Tuple[str, str, int]]:
    """
    Get tournaments user is registered for that start within window.

    Args:
        user_id: Discord user ID
        window_seconds: Time window in seconds (default: 24 hours)

    Returns:
        List of tuples: (tournament_key, tournament_name, scheduled_start)
    """
    now = int(time.time())
    upper = now + window_seconds

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """
            SELECT t.key, t.name, t.scheduled_start
            FROM tournaments t
            JOIN tournament_participants tp ON tp.tournament_key = t.key
            WHERE tp.user_id = ?
              AND t.scheduled_start IS NOT NULL
              AND t.scheduled_start BETWEEN ? AND ?
              AND t.status IN ('open', 'started')
            ORDER BY t.scheduled_start ASC
        """,
            (user_id, now, upper),
        )

        return await cursor.fetchall()


async def schedule_tournament_reminder(
    user_id: int, tournament_key: str, start_time: int, offset_minutes: int = 10
) -> bool:
    """
    NOTE(core-bot): Scheduler/notifications feature not in core-bot.
    This is a no-op stub.
    """
    # TODO(core-bot): tournament_notifications table not in core schema
    return False
