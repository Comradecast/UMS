"""
services/server_config_service.py

Service layer for server configuration (server_configs table).
Provides read access to v3 server configuration including feature flags and channel mappings.
"""

from __future__ import annotations

import logging
from typing import Optional
from dataclasses import dataclass

import aiosqlite

log = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Server configuration from server_configs table."""

    guild_id: int
    tournament_requests_channel: Optional[int] = None
    admin_review_channel: Optional[int] = None
    registration_channel: Optional[int] = None
    results_channel: Optional[int] = None
    casual_match_channel: Optional[int] = None
    rank_channel: Optional[int] = None
    clan_channel: Optional[int] = None
    audit_channel: Optional[int] = None
    admin_role: Optional[int] = None
    organizer_role: Optional[int] = None
    enabled: int = 1
    setup_completed: int = 0
    setup_date: Optional[int] = None
    enable_leaderboard: int = 1
    enable_player_profiles: int = 1
    enable_casual_matches: int = 1
    created_at: Optional[int] = None
    updated_at: Optional[int] = None


class ServerConfigService:
    """Service for reading server configuration from v3 tables."""

    def __init__(self, db: aiosqlite.Connection):
        self.db = db
        self.db.row_factory = aiosqlite.Row

    async def get_for_guild(self, guild_id: int) -> Optional[ServerConfig]:
        """Get server configuration for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            ServerConfig object if exists, None otherwise
        """
        try:
            async with self.db.execute(
                "SELECT * FROM server_configs WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return ServerConfig(**dict(row))
                return None
        except Exception as e:
            log.error(
                f"Failed to get server config for guild {guild_id}: {e}", exc_info=True
            )
            return None

    async def is_feature_enabled(self, guild_id: int, feature: str) -> bool:
        """Check if a specific feature is enabled for a guild.

        Args:
            guild_id: Discord guild ID
            feature: Feature name ('leaderboard', 'player_profiles', 'casual_matches')

        Returns:
            True if enabled, False otherwise (defaults to False if config missing)
        """
        config = await self.get_for_guild(guild_id)
        if not config:
            return False

        feature_map = {
            "leaderboard": config.enable_leaderboard,
            "player_profiles": config.enable_player_profiles,
            "casual_matches": config.enable_casual_matches,
        }

        return bool(feature_map.get(feature, False))

    async def get_channel_id(self, guild_id: int, channel_type: str) -> Optional[int]:
        """Get a channel ID for a specific purpose.

        Args:
            guild_id: Discord guild ID
            channel_type: Channel type (e.g., 'admin_review', 'registration', 'results')

        Returns:
            Channel ID if configured, None otherwise
        """
        config = await self.get_for_guild(guild_id)
        if not config:
            return None

        return getattr(config, f"{channel_type}_channel", None)
