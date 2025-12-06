"""
add ums_match_id to solo_matches

Revision ID: 006
Revises: 005
Create Date: 2025-12-03 20:11:00

NOTE(core-bot): This migration is a NO-OP in core-bot.
solo_matches table is for Solo Queue which is not part of core-bot.
"""

import aiosqlite

MIGRATION_VERSION = "006_add_ums_match_id_to_solo_matches"


async def apply(db: aiosqlite.Connection):
    """NO-OP in core-bot - solo_matches table doesn't exist."""
    pass


async def rollback(db: aiosqlite.Connection):
    """NO-OP in core-bot."""
    pass


async def run(db: aiosqlite.Connection) -> None:
    """Entry point for migration runner - NO-OP in core-bot."""
    # NOTE(core-bot): solo_matches is not part of core-bot schema
    pass
