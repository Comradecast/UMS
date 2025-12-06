"""
services/guild_config_service.py — Guild Configuration Service
---------------------------------------------------------------
v3 service for guild configuration management.
Uses guild_config table as source of truth, migrates from legacy server_configs.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import aiosqlite

log = logging.getLogger(__name__)


@dataclass
class GuildConfig:
    """Guild configuration from guild_config table."""

    guild_id: int
    admin_channel: Optional[int] = None
    announce_channel: Optional[int] = None
    request_channel: Optional[int] = None
    onboarding_channel: Optional[int] = None
    ums_admin_role: Optional[int] = None
    setup_completed: int = 0
    onboarding_channel_created: int = 0
    admin_channel_created: int = 0
    announce_channel_created: int = 0
    created_at: Optional[int] = None
    updated_at: Optional[int] = None

    @property
    def is_setup(self) -> bool:
        """Check if setup is complete."""
        return self.setup_completed == 1


class GuildConfigService:
    """
    Service for guild configuration management.

    Uses guild_config as v3 source of truth.
    Automatically migrates from legacy server_configs on first access.
    """

    def __init__(self, db: aiosqlite.Connection):
        self.db = db
        self.db.row_factory = aiosqlite.Row

    async def get(self, guild_id: int) -> Optional[GuildConfig]:
        """
        Get guild configuration, migrating from legacy if needed.

        Returns GuildConfig or None if not configured.
        """
        try:
            # Try guild_config first
            async with self.db.execute(
                "SELECT * FROM guild_config WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return GuildConfig(**dict(row))

            # Try migrating from legacy server_configs
            migrated = await self._migrate_legacy(guild_id)
            if migrated:
                return await self.get(guild_id)

            return None

        except Exception as e:
            log.error(f"[CONFIG-SERVICE] Error getting config for {guild_id}: {e}")
            return None

    async def _migrate_legacy(self, guild_id: int) -> bool:
        """Migrate from legacy server_configs if exists."""
        try:
            async with self.db.execute(
                "SELECT * FROM server_configs WHERE guild_id = ?", (guild_id,)
            ) as cursor:
                legacy = await cursor.fetchone()

            if not legacy:
                return False

            now = int(time.time())
            await self.db.execute(
                """
                INSERT INTO guild_config (
                    guild_id, admin_channel, announce_channel, request_channel,
                    ums_admin_role, setup_completed, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    legacy["admin_review_channel"],
                    legacy["registration_channel"],
                    legacy["tournament_requests_channel"],
                    legacy["admin_role"],
                    legacy["setup_completed"],
                    legacy["created_at"] or now,
                    now,
                ),
            )
            await self.db.commit()
            log.info(f"[CONFIG-SERVICE] Migrated legacy config for guild {guild_id}")
            return True

        except Exception as e:
            log.error(f"[CONFIG-SERVICE] Migration failed for {guild_id}: {e}")
            return False

    async def create(
        self,
        guild_id: int,
        admin_channel: Optional[int] = None,
        announce_channel: Optional[int] = None,
        request_channel: Optional[int] = None,
        onboarding_channel: Optional[int] = None,
        ums_admin_role: Optional[int] = None,
        admin_channel_created: bool = False,
        announce_channel_created: bool = False,
        onboarding_channel_created: bool = False,
    ) -> GuildConfig:
        """Create or update guild configuration."""
        now = int(time.time())

        # Check if exists
        existing = await self.get(guild_id)

        if existing:
            # Update existing
            await self.db.execute(
                """
                UPDATE guild_config SET
                    admin_channel = COALESCE(?, admin_channel),
                    announce_channel = COALESCE(?, announce_channel),
                    request_channel = COALESCE(?, request_channel),
                    onboarding_channel = COALESCE(?, onboarding_channel),
                    ums_admin_role = COALESCE(?, ums_admin_role),
                    admin_channel_created = CASE WHEN ? THEN 1 ELSE admin_channel_created END,
                    announce_channel_created = CASE WHEN ? THEN 1 ELSE announce_channel_created END,
                    onboarding_channel_created = CASE WHEN ? THEN 1 ELSE onboarding_channel_created END,
                    updated_at = ?
                WHERE guild_id = ?
                """,
                (
                    admin_channel,
                    announce_channel,
                    request_channel,
                    onboarding_channel,
                    ums_admin_role,
                    admin_channel_created,
                    announce_channel_created,
                    onboarding_channel_created,
                    now,
                    guild_id,
                ),
            )
        else:
            # Create new
            await self.db.execute(
                """
                INSERT INTO guild_config (
                    guild_id, admin_channel, announce_channel, request_channel,
                    onboarding_channel, ums_admin_role, setup_completed,
                    admin_channel_created, announce_channel_created, onboarding_channel_created,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    admin_channel,
                    announce_channel,
                    request_channel,
                    onboarding_channel,
                    ums_admin_role,
                    int(admin_channel_created),
                    int(announce_channel_created),
                    int(onboarding_channel_created),
                    now,
                    now,
                ),
            )

        await self.db.commit()
        log.info(f"[CONFIG-SERVICE] Config saved for guild {guild_id}")

        return await self.get(guild_id)

    async def mark_setup_complete(self, guild_id: int) -> bool:
        """Mark setup as complete for a guild."""
        try:
            now = int(time.time())
            await self.db.execute(
                """
                UPDATE guild_config
                SET setup_completed = 1, updated_at = ?
                WHERE guild_id = ?
                """,
                (now, guild_id),
            )
            await self.db.commit()
            log.info(f"[CONFIG-SERVICE] Setup complete for guild {guild_id}")
            return True
        except Exception as e:
            log.error(f"[CONFIG-SERVICE] Failed to mark setup complete: {e}")
            return False

    async def update_channel(
        self, guild_id: int, channel_type: str, channel_id: Optional[int]
    ) -> bool:
        """Update a specific channel configuration."""
        valid_types = {
            "admin_channel",
            "announce_channel",
            "request_channel",
            "onboarding_channel",
        }
        if channel_type not in valid_types:
            log.error(f"[CONFIG-SERVICE] Invalid channel type: {channel_type}")
            return False

        try:
            now = int(time.time())
            await self.db.execute(
                f"UPDATE guild_config SET {channel_type} = ?, updated_at = ? WHERE guild_id = ?",
                (channel_id, now, guild_id),
            )
            await self.db.commit()
            return True
        except Exception as e:
            log.error(f"[CONFIG-SERVICE] Failed to update channel: {e}")
            return False

    async def update_role(self, guild_id: int, role_id: Optional[int]) -> bool:
        """Update admin role configuration."""
        try:
            now = int(time.time())
            await self.db.execute(
                "UPDATE guild_config SET ums_admin_role = ?, updated_at = ? WHERE guild_id = ?",
                (role_id, now, guild_id),
            )
            await self.db.commit()
            return True
        except Exception as e:
            log.error(f"[CONFIG-SERVICE] Failed to update role: {e}")
            return False

    async def is_setup(self, guild_id: int) -> bool:
        """Check if a guild has completed setup."""
        config = await self.get(guild_id)
        return config is not None and config.is_setup

    async def delete(self, guild_id: int) -> bool:
        """Delete guild configuration."""
        try:
            await self.db.execute(
                "DELETE FROM guild_config WHERE guild_id = ?", (guild_id,)
            )
            await self.db.commit()
            log.info(f"[CONFIG-SERVICE] Deleted config for guild {guild_id}")
            return True
        except Exception as e:
            log.error(f"[CONFIG-SERVICE] Delete failed: {e}")
            return False
