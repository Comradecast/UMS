"""
premium_cogs/premium_client.py — Async HTTP Client for UMS Premium Service

Production-ready client for communicating with the Premium backend.
Handles authentication, error handling, and session management.
"""

import logging
from typing import Any, Optional

import aiohttp

log = logging.getLogger(__name__)


class PremiumAPIError(Exception):
    """Raised when the Premium API returns an error status.

    Attributes:
        status: HTTP status code
        message: Error message from the API
    """

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"Premium API Error [{status}]: {message}")


class PremiumClient:
    """Async HTTP client for UMS Premium Service.

    Handles all communication with the Premium backend including:
    - Player management
    - Queue operations
    - Matchmaking
    - Match lifecycle

    All requests include the X-UMS-API-Key header for authentication.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        """Initialize the Premium client.

        Args:
            base_url: Base URL of the Premium Service (e.g., "http://localhost:8000")
            api_key: Shared secret for authentication
            session: Optional shared aiohttp session (created if not provided)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the HTTP session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the HTTP session if we own it."""
        if self._session and self._owns_session:
            await self._session.close()
            self._session = None
            log.info("[PREMIUM-CLIENT] Session closed")

    def _headers(self) -> dict[str, str]:
        """Build request headers with authentication."""
        return {
            "X-UMS-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Make an authenticated request to the Premium API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/players/123")
            json: Request body (for POST/PUT)
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            PremiumAPIError: If the API returns an error status
        """
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"

        try:
            async with session.request(
                method,
                url,
                json=json,
                params=params,
                headers=self._headers(),
            ) as resp:
                body = await resp.text()

                if resp.status >= 400:
                    log.warning(
                        f"[PREMIUM-CLIENT] {method} {endpoint} -> {resp.status}: {body}"
                    )
                    raise PremiumAPIError(resp.status, body)

                if resp.status == 204 or not body:
                    return {}

                return await resp.json()

        except aiohttp.ClientError as e:
            log.error(f"[PREMIUM-CLIENT] Network error: {e}")
            raise PremiumAPIError(503, f"Network error: {e}")

    # -------------------------------------------------------------------------
    # Player Endpoints
    # -------------------------------------------------------------------------

    async def get_or_create_player(self, discord_id: int) -> dict[str, Any]:
        """Get a player by Discord ID, creating if not found.

        Args:
            discord_id: Player's Discord user ID

        Returns:
            Player data dict with id, discord_id, elo_1v1, etc.
        """
        return await self._request("GET", f"/players/{discord_id}")

    async def update_player(
        self,
        discord_id: int,
        *,
        region: Optional[str] = None,
        claimed_rank: Optional[str] = None,
        has_onboarded: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Update a player's profile.

        Args:
            discord_id: Player's Discord user ID
            region: Player's region (optional)
            claimed_rank: Self-reported rank (optional)
            has_onboarded: Onboarding status (optional)

        Returns:
            Updated player data
        """
        body = {}
        if region is not None:
            body["region"] = region
        if claimed_rank is not None:
            body["claimed_rank"] = claimed_rank
        if has_onboarded is not None:
            body["has_onboarded"] = has_onboarded

        return await self._request("PUT", f"/players/{discord_id}", json=body)

    # -------------------------------------------------------------------------
    # Queue Endpoints
    # -------------------------------------------------------------------------

    async def join_queue(
        self,
        *,
        discord_id: int,
        guild_id: int,
        queue_type: str,
        region: Optional[str] = None,
    ) -> dict[str, Any]:
        """Join a Solo Queue.

        Args:
            discord_id: Player's Discord user ID
            guild_id: Discord guild/server ID
            queue_type: Queue mode (e.g., "1v1_ranked")
            region: Optional region for matching

        Returns:
            Dict with status, position, message
        """
        body = {
            "discord_id": discord_id,
            "guild_id": guild_id,
            "queue_type": queue_type,
        }
        if region:
            body["region"] = region

        return await self._request("POST", "/queue/join", json=body)

    async def leave_queue(
        self,
        *,
        discord_id: int,
        guild_id: int,
        queue_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """Leave a Solo Queue.

        Args:
            discord_id: Player's Discord user ID
            guild_id: Discord guild/server ID
            queue_type: Specific queue (None = leave all)

        Returns:
            Dict with success, message
        """
        body = {
            "discord_id": discord_id,
            "guild_id": guild_id,
        }
        if queue_type:
            body["queue_type"] = queue_type

        return await self._request("POST", "/queue/leave", json=body)

    async def get_queue_status(
        self,
        *,
        discord_id: int,
        guild_id: int,
    ) -> dict[str, Any]:
        """Get a player's queue status.

        Args:
            discord_id: Player's Discord user ID
            guild_id: Discord guild/server ID

        Returns:
            Dict with in_queue, queues list
        """
        return await self._request(
            "GET",
            f"/queue/status/{discord_id}",
            params={"guild_id": guild_id},
        )

    async def get_queue_stats(self, *, guild_id: int) -> dict[str, Any]:
        """Get queue statistics for a guild.

        Args:
            guild_id: Discord guild/server ID

        Returns:
            Dict with guild_id, stats
        """
        return await self._request("GET", f"/queue/stats/{guild_id}")

    # -------------------------------------------------------------------------
    # Matchmaking Endpoints
    # -------------------------------------------------------------------------

    async def matchmaking_tick(
        self,
        *,
        guild_id: int,
        queue_type: str,
        elo_range: int = 200,
    ) -> dict[str, Any]:
        """Run a matchmaking tick.

        Finds pairs of players and creates matches.

        Args:
            guild_id: Discord guild/server ID
            queue_type: Queue mode to process
            elo_range: Maximum Elo difference for matching

        Returns:
            Dict with matches_created, matches list
        """
        body = {
            "guild_id": guild_id,
            "queue_type": queue_type,
            "elo_range": elo_range,
        }
        return await self._request("POST", "/matchmaking/tick", json=body)

    # -------------------------------------------------------------------------
    # Match Endpoints
    # -------------------------------------------------------------------------

    async def get_active_match(self, *, discord_id: int) -> dict[str, Any] | None:
        """Get a player's active match.

        Args:
            discord_id: Player's Discord user ID

        Returns:
            Match data dict or None if not in a match
        """
        result = await self._request("GET", f"/matches/active/{discord_id}")
        # API returns null if no active match
        return result if result else None

    async def report_match_result(
        self,
        *,
        match_id: int,
        winner_team: int,
        team1_score: int,
        team2_score: int,
    ) -> dict[str, Any]:
        """Report a match result.

        Args:
            match_id: Match ID to report
            winner_team: Winning team (1 or 2)
            team1_score: Team 1's score
            team2_score: Team 2's score

        Returns:
            Updated match data
        """
        body = {
            "winner_team": winner_team,
            "team1_score": team1_score,
            "team2_score": team2_score,
        }
        return await self._request("POST", f"/matches/{match_id}/report", json=body)

    async def cancel_match(
        self,
        *,
        match_id: int,
        reason: Optional[str] = None,
    ) -> dict[str, Any]:
        """Cancel a match.

        Args:
            match_id: Match ID to cancel
            reason: Cancellation reason

        Returns:
            Updated match data
        """
        body = {"reason": reason or "cancelled"}
        return await self._request("POST", f"/matches/{match_id}/cancel", json=body)

    async def get_match_history(
        self,
        *,
        discord_id: int,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get a player's match history.

        Args:
            discord_id: Player's Discord user ID
            limit: Maximum matches to return

        Returns:
            List of match history items
        """
        result = await self._request(
            "GET",
            f"/matches/history/{discord_id}",
            params={"limit": limit},
        )
        return result.get("matches", [])
