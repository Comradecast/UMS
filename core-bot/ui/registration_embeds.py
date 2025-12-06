"""
ui/registration_embeds.py — Registration Embed Builders
========================================================
Embed construction for registration panels (public and admin).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Any, Set

import discord

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


def build_public_registration_embed(state: Dict[str, Any]) -> discord.Embed:
    """
    Create a public embed from tournament state.

    Args:
        state: Tournament state dictionary with keys like 'name', 'region', 'format', etc.

    Returns:
        discord.Embed for the public registration panel.
    """
    name = state.get("name", "Unknown")
    region = state.get("region", "N/A")
    match_length = state.get("match_length", "Bo3")
    fmt = state.get("format", "N/A")
    size = state.get("size", "N/A")
    start = state.get("start_time", "N/A")
    is_open = bool(state.get("is_open", False))
    participants = state.get("participants") or set()
    count = len(participants)

    e = discord.Embed(title=f"🏆 {name}", color=discord.Color.gold())
    e.add_field(name="Region", value=region, inline=True)
    e.add_field(name="Format", value=fmt, inline=True)
    e.add_field(name="Size", value=size, inline=True)
    e.add_field(name="Match Length", value=match_length, inline=True)

    # Add rank restriction if set
    rank_restriction = state.get("rank_restriction", "")
    if rank_restriction and rank_restriction.lower() not in ["", "none", "n/a"]:
        e.add_field(name="🎖️ Rank Restriction", value=rank_restriction, inline=True)

    # Add region restriction if set
    region_restriction = state.get("region_restriction", "")
    if region_restriction and region_restriction.lower() not in ["", "none", "n/a"]:
        e.add_field(name="🌍 Region Restriction", value=region_restriction, inline=True)

    # Add Team Size info if applicable
    team_size = state.get("team_size", 1)
    if team_size > 1:
        e.add_field(name="🛡️ Team Size", value=f"{team_size}v{team_size}", inline=True)

    e.add_field(name="Start Time", value=start, inline=False)
    e.add_field(
        name="Status", value=("✅ Open" if is_open else "⛔ Closed"), inline=True
    )
    e.add_field(name="Registered", value=str(count), inline=True)
    return e


def build_admin_registration_embed(state: Dict[str, Any]) -> discord.Embed:
    """
    Create an admin embed from tournament state.

    Args:
        state: Tournament state dictionary.

    Returns:
        discord.Embed for the admin control panel.
    """
    name = state.get("name", "Unknown")
    is_open = bool(state.get("is_open", False))
    participants = state.get("participants") or set()
    count = len(participants)
    match_length = state.get("match_length", "Bo3")

    e = discord.Embed(title=f"⚙️ Admin Panel — {name}", color=discord.Color.dark_grey())
    e.description = (
        f"**Key**: `{state.get('key')}`\n**Role**: <@&{state.get('role_id')}>"
    )
    e.add_field(
        name="Status", value=("✅ Open" if is_open else "⛔ Closed"), inline=True
    )
    e.add_field(name="Players", value=str(count), inline=True)
    e.add_field(name="Match Length", value=match_length, inline=True)
    return e


def build_region_mismatch_embed(
    tournament_region: str, player_regions: list
) -> discord.Embed:
    """
    Create an embed for region mismatch warning.

    Args:
        tournament_region: The tournament's region restriction.
        player_regions: List of region roles the player has.

    Returns:
        discord.Embed warning about region mismatch.
    """
    embed = discord.Embed(title="⚠️ Region Mismatch", color=discord.Color.yellow())
    if not player_regions:
        embed.description = (
            f"This tournament is for **{tournament_region}**.\n"
            "You don't have any region roles assigned.\n\n"
            "Consider selecting your region in the roles channel."
        )
    else:
        embed.description = (
            f"This tournament is for **{tournament_region}**.\n"
            f"Your region role(s): **{', '.join(player_regions)}**\n\n"
            "Playing outside your region may cause high ping."
        )
    return embed
