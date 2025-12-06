"""
config/dev_flags.py

Central configuration for dev-only access control and feature flags.

Used by cogs for things like auto-simulation, experimental commands, etc.
All dev-only features should check access here for consistency.
"""

import os
from typing import Set


# =============================================================================
# DEV USERS
# =============================================================================
# Discord user IDs allowed to run dev-only tools (e.g., auto-simulation).
# Add your Discord user ID here to enable dev tools for yourself.
#
# To find your Discord user ID:
#   1. Enable Developer Mode in Discord (User Settings > App Settings > Advanced)
#   2. Right-click your username and select "Copy User ID"
#
# Example: DEV_USERS: Set[int] = {123456789012345678, 987654321098765432}
DEV_USERS: Set[int] = {
    1383507533901201449,  # Luke
}


# =============================================================================
# ENVIRONMENT FLAGS
# =============================================================================
def is_dev_mode() -> bool:
    """
    Check if the bot is running in dev mode.

    Set DEV_MODE=1 in your .env file to enable dev mode.
    This is a global kill-switch for all dev features.
    """
    return os.getenv("DEV_MODE") == "1"


# =============================================================================
# ACCESS CONTROL HELPERS
# =============================================================================
def is_dev_user(user_id: int) -> bool:
    """
    Check if a user is authorized to use dev-only tools.

    ID-only version: if the user is in DEV_USERS, dev tools work
    for them in any environment where the bot is running.

    Args:
        user_id: The Discord user ID to check.

    Returns:
        True if the user can access dev tools, False otherwise.
    """
    return user_id in DEV_USERS


# =============================================================================
# EXPERIMENTAL FEATURE FLAGS (Future Use)
# =============================================================================
# Add feature flags here as needed. Example:
#
# ENABLE_EXPERIMENTAL_MATCHMAKING = os.getenv("ENABLE_EXPERIMENTAL_MATCHMAKING") == "1"
# ENABLE_NEW_RANKING_SYSTEM = os.getenv("ENABLE_NEW_RANKING_SYSTEM") == "1"
