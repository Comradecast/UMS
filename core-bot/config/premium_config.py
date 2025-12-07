"""
config/premium_config.py — Premium Feature Configuration

Loads Premium backend configuration from environment variables.
Used to connect UMS Core to the external UMS Premium Service.
"""

import os
from dataclasses import dataclass


@dataclass
class PremiumConfig:
    """Configuration for Premium backend integration.

    Attributes:
        enabled: Whether Premium features are enabled
        api_url: Base URL of the Premium Service API
        api_key: Shared secret for X-UMS-API-Key authentication
    """

    enabled: bool
    api_url: str
    api_key: str


def load_premium_config() -> PremiumConfig:
    """Load Premium configuration from environment variables.

    Environment Variables:
        PREMIUM_ENABLED: "1" to enable, "0" or unset to disable
        PREMIUM_API_URL: Base URL (e.g., "http://localhost:8000")
        PREMIUM_API_KEY: Shared secret key

    Returns:
        PremiumConfig instance
    """
    enabled_raw = os.getenv("PREMIUM_ENABLED", "0")
    enabled = enabled_raw.lower() in ("1", "true", "yes")

    return PremiumConfig(
        enabled=enabled,
        api_url=os.getenv("PREMIUM_API_URL", "").strip(),
        api_key=os.getenv("PREMIUM_API_KEY", "").strip(),
    )


# Singleton instance for import convenience
_config: PremiumConfig | None = None


def get_premium_config() -> PremiumConfig:
    """Get the Premium configuration (cached singleton).

    Returns:
        PremiumConfig instance
    """
    global _config
    if _config is None:
        _config = load_premium_config()
    return _config
