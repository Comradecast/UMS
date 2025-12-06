"""
core-bot/ui/brand.py — UMS Core Brand Kit v1
=============================================
Centralized brand constants for all UI elements.

All embeds, buttons, and views MUST use these constants.
"""

import discord

# -----------------------------------------------------------------------------
# VERSION
# -----------------------------------------------------------------------------

from core_version import CORE_VERSION

FOOTER_TEXT = f"UMS Bot Core v{CORE_VERSION}"

# -----------------------------------------------------------------------------
# COLOR PALETTE
# -----------------------------------------------------------------------------

# Primary colors
PRIMARY_BLUE = 0x2A6FDB
SUCCESS_GREEN = 0x3BA55D
WARNING_YELLOW = 0xFAA61A
ERROR_RED = 0xED4245

# Neutral colors (for reference, not typically used in embeds)
NEUTRAL_DARK = 0x2F3136
NEUTRAL_DARKER = 0x23272A
NEUTRAL_LIGHT = 0x99AAB5


# -----------------------------------------------------------------------------
# DISCORD COLOR OBJECTS
# -----------------------------------------------------------------------------


class Colors:
    """Discord Color objects for embeds."""

    PRIMARY = discord.Color(PRIMARY_BLUE)
    SUCCESS = discord.Color(SUCCESS_GREEN)
    WARNING = discord.Color(WARNING_YELLOW)
    ERROR = discord.Color(ERROR_RED)

    # Aliases
    DEFAULT = PRIMARY
    INFO = PRIMARY
    DANGER = ERROR


# -----------------------------------------------------------------------------
# EMBED HELPERS
# -----------------------------------------------------------------------------


def create_embed(
    title: str,
    description: str = None,
    color: discord.Color = None,
    include_footer: bool = True,
) -> discord.Embed:
    """
    Create a brand-compliant embed.

    Args:
        title: Embed title (bold, functional, no decorative emoji)
        description: Short summary (max 1-2 sentences)
        color: Embed color (defaults to PRIMARY)
        include_footer: Whether to include the standard footer

    Returns:
        discord.Embed with brand styling applied
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color or Colors.PRIMARY,
    )

    if include_footer:
        embed.set_footer(text=FOOTER_TEXT)

    return embed


def error_embed(title: str, description: str = None) -> discord.Embed:
    """Create an error embed with brand styling."""
    return create_embed(title, description, Colors.ERROR)


def success_embed(title: str, description: str = None) -> discord.Embed:
    """Create a success embed with brand styling."""
    return create_embed(title, description, Colors.SUCCESS)


def warning_embed(title: str, description: str = None) -> discord.Embed:
    """Create a warning embed with brand styling."""
    return create_embed(title, description, Colors.WARNING)
