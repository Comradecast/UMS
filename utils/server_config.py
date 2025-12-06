import logging
from typing import Any, Dict, Optional

import aiosqlite

from database import get_db_path

log = logging.getLogger(__name__)


class ServerConfigManager:
    def __init__(self):
        self.db_path = get_db_path()

    async def get_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve the configuration for a specific guild."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM server_configs WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
        return None

    async def set_config(self, guild_id: int, key: str, value: Any):
        """Update a specific configuration setting for a guild."""
        valid_keys = [
            "tournament_requests_channel",
            "admin_review_channel",
            "registration_channel",
            "results_channel",
            "casual_match_channel",
            "rank_channel",
            "clan_channel",
            "audit_channel",
            "queue_channel",
            "admin_role",
            "organizer_role",
            "enabled",
            "setup_completed",
            "setup_date",
            "enable_leaderboard",
            "enable_player_profiles",
            "enable_casual_matches",
        ]

        if key not in valid_keys:
            raise ValueError(f"Invalid configuration key: {key}")

        async with aiosqlite.connect(self.db_path) as db:
            # Check if config exists
            async with db.execute(
                "SELECT 1 FROM server_configs WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                exists = await cursor.fetchone()

            if exists:
                await db.execute(
                    f"UPDATE server_configs SET {key} = ?, updated_at = strftime('%s','now') WHERE guild_id = ?",
                    (value, guild_id),
                )
            else:
                # Create default config with this value set
                import time

                now = int(time.time())
                await db.execute(
                    f"""
                    INSERT INTO server_configs (guild_id, {key}, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                """,
                    (guild_id, value, now, now),
                )

            await db.commit()

    async def is_setup_complete(self, guild_id: int) -> bool:
        """Check if the server setup is marked as complete."""
        config = await self.get_config(guild_id)
        return bool(config and config.get("setup_completed"))

    async def get_channel_id(self, guild_id: int, channel_type: str) -> Optional[int]:
        """
        Get the channel ID for a specific purpose.
        channel_type options: 'requests', 'admin', 'registration', 'results', 'casual', 'rank', 'clan', 'audit', 'queue'
        """
        config = await self.get_config(guild_id)
        if not config:
            return None

        mapping = {
            "requests": "tournament_requests_channel",
            "admin": "admin_review_channel",
            "registration": "registration_channel",
            "results": "results_channel",
            "casual": "casual_match_channel",
            "rank": "rank_channel",
            "clan": "clan_channel",
            "audit": "audit_channel",
            "queue": "queue_channel",
        }

        key = mapping.get(channel_type)
        if key:
            return config.get(key)
        return None

    async def get_role_id(self, guild_id: int, role_type: str) -> Optional[int]:
        """
        Get the role ID for a specific purpose.
        role_type options: 'admin', 'organizer'
        """
        config = await self.get_config(guild_id)
        if not config:
            return None

        mapping = {"admin": "admin_role", "organizer": "organizer_role"}

        key = mapping.get(role_type)
        if key:
            return config.get(key)
        return None
