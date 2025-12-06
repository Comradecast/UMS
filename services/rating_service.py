# services/rating_service.py
from __future__ import annotations

from enum import Enum
from math import pow
from typing import Optional

import aiosqlite

from .player_service import Player


class Mode(str, Enum):
    ONES = "1v1"
    TWOS = "2v2"
    THREES = "3v3"


PROVISIONAL_GAMES = 10


def expected_score(rating_a: int, rating_b: int) -> float:
    return 1.0 / (1.0 + pow(10, (rating_b - rating_a) / 400.0))


def k_factor(games_played: int) -> int:
    if games_played < PROVISIONAL_GAMES:
        return 80
    elif games_played < 30:
        return 40
    return 20


def default_seed_rating() -> int:
    return 1000


def seed_mode_rating(global_rating: Optional[int]) -> int:
    if global_rating is None:
        return default_seed_rating()
    return max(800, global_rating - 200)


def mode_fields(mode: Mode) -> tuple[str, str]:
    if mode == Mode.ONES:
        return "elo_1v1", "provisional_games_1v1"
    if mode == Mode.TWOS:
        return "elo_2v2", "provisional_games_2v2"
    return "elo_3v3", "provisional_games_3v3"


class RatingService:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def get_global_rating(self, player: Player) -> Optional[int]:
        ratings = [
            r for r in (player.elo_1v1, player.elo_2v2, player.elo_3v3) if r is not None
        ]
        return max(ratings) if ratings else None

    async def _ensure_mode_seeded(
        self,
        player: Player,
        mode: Mode,
    ) -> tuple[int, int]:
        """
        Ensure the player has Elo + provisional games seeded for a given mode.

        Returns (elo, provisional_games) for that mode.
        """
        elo_field, prov_field = mode_fields(mode)
        user_id = player.user_id

        # Query players table
        cur = await self.db.execute(
            f"SELECT {elo_field}, {prov_field} FROM players WHERE discord_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        await cur.close()

        # If row doesn't exist, create it (PlayerService usually handles this, but safe fallback)
        if row is None:
            await self.db.execute(
                "INSERT OR IGNORE INTO players (discord_id, created_at) VALUES (?, datetime('now'))",
                (user_id,),
            )
            await self.db.commit()
            # Re-query or assume defaults
            return 1000, 0

        elo, prov_games = row

        # Seed if elo is None (should be 1000 default, but just in case)
        if elo is None:
            global_rating = await self.get_global_rating(player)
            elo = seed_mode_rating(global_rating)
            await self.db.execute(
                f"UPDATE players SET {elo_field} = ? WHERE discord_id = ?",
                (elo, user_id),
            )
            await self.db.commit()

        return int(elo if elo is not None else 1000), int(prov_games or 0)

    async def apply_match_result(
        self,
        player_a: Player,
        player_b: Player,
        mode: Mode,
        score_a: int,
        score_b: int,
    ) -> tuple[int, int]:
        elo_field, prov_field = mode_fields(mode)

        # Seed missing ratings
        elo_a, games_a = await self._ensure_mode_seeded(player_a, mode)
        elo_b, games_b = await self._ensure_mode_seeded(player_b, mode)

        exp_a = expected_score(elo_a, elo_b)
        exp_b = 1.0 - exp_a

        if score_a == score_b:
            # You can add draws later if you want; for now treat as no-change or pick a rule
            result_a = result_b = 0.5
        else:
            result_a = 1.0 if score_a > score_b else 0.0
            result_b = 1.0 - result_a

        k_a = k_factor(games_a)
        k_b = k_factor(games_b)

        new_elo_a = round(elo_a + k_a * (result_a - exp_a))
        new_elo_b = round(elo_b + k_b * (result_b - exp_b))

        games_a = min(PROVISIONAL_GAMES, games_a + 1)
        games_b = min(PROVISIONAL_GAMES, games_b + 1)

        # Persist using discord_id and players table
        await self.db.execute(
            f"UPDATE players SET {elo_field} = ?, {prov_field} = ? WHERE discord_id = ?",
            (new_elo_a, games_a, player_a.user_id),
        )
        await self.db.execute(
            f"UPDATE players SET {elo_field} = ?, {prov_field} = ? WHERE discord_id = ?",
            (new_elo_b, games_b, player_b.user_id),
        )
        await self.db.commit()

        return new_elo_a, new_elo_b
