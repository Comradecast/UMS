"""
Bracket Embed Builders.

Extracted from cogs/brackets.py to separate UI layer from cog logic.
These functions build Discord embeds for bracket display.

NOTE: These are pure UI functions - no database access or business logic.
"""

from typing import Any, Callable, Coroutine, List, Optional

import discord


async def build_bracket_embed(
    name: str,
    matches: List[dict],
    get_team_name: Optional[Callable[[str], Coroutine[Any, Any, str]]] = None,
) -> discord.Embed:
    """
    Render the bracket as a Discord Embed.

    Args:
        name: Tournament name.
        matches: List of match dictionaries from the bracket.
        get_team_name: Optional async callable to resolve team IDs to names.

    Returns:
        discord.Embed with bracket visualization.
    """
    embed = discord.Embed(title=f"🏆 Bracket: {name}", color=discord.Color.blue())

    if not matches:
        embed.description = "No matches generated yet."
        return embed

    # Group by Round
    rounds = {}
    for m in matches:
        r = m["round"]
        if r not in rounds:
            rounds[r] = []
        rounds[r].append(m)

    # Find current round (first round with unfinished matches)
    current_round = None
    for r in sorted(rounds.keys()):
        if any(not m.get("winner") for m in rounds[r]):
            current_round = r
            break

    # If all rounds complete, show final round
    if current_round is None:
        current_round = max(rounds.keys())

    # Build compact description
    desc = ""

    # Show round summary
    total_rounds = max(rounds.keys())
    desc += f"**Tournament Progress**: Round {current_round} of {total_rounds}\n\n"

    # Round completion status
    for r in sorted(rounds.keys()):
        round_matches = rounds[r]
        completed = sum(1 for m in round_matches if m.get("winner"))
        total = len(round_matches)

        if r < current_round:
            emoji = "✅"
        elif r == current_round:
            emoji = "▶️"
        else:
            emoji = "⏸️"

        desc += f"{emoji} Round {r}: {completed}/{total} complete"

        # Show bracket size for context
        if r == 1:
            player_count = total * 2  # Rough estimate
            desc += f" ({player_count}→{total} players)\n"
        else:
            desc += "\n"

    desc += "\n**Current Matches:**\n"

    # Show only current round matches (to stay under character limit)
    current_matches = rounds.get(current_round, [])

    # Separate into active and completed
    active = [m for m in current_matches if not m.get("winner")]
    completed = [m for m in current_matches if m.get("winner")]

    # Show active matches first
    if active:
        for m in active[:20]:  # Limit to 20 to prevent overflow
            p1_val = m["p1"]
            p2_val = m["p2"]

            p1_str = await _resolve_player_str(p1_val, get_team_name)
            p2_str = await _resolve_player_str(p2_val, get_team_name, default="BYE")

            desc += f"⚔️ `Match {m['id']}`: {p1_str} vs {p2_str}\n"

        if len(active) > 20:
            desc += f"*...and {len(active) - 20} more active matches*\n"

    # Show completed matches (compact)
    if completed:
        desc += f"\n**Completed This Round:** {len(completed)} matches\n"
        # Show first few completed matches
        for m in completed[:5]:
            p1_val = m["p1"]

            p1_str = await _resolve_player_str(p1_val, get_team_name)

            winner_emoji = "✅" if m["winner"] == m["p1"] else "❌"
            score = f" {m.get('score', '')}" if m.get("score") else ""
            desc += f"{winner_emoji} `M{m['id']}`: {p1_str}{score}\n"

        if len(completed) > 5:
            desc += f"*...and {len(completed) - 5} more*\n"

    # Final match is special - only show champion when round is fully complete
    if current_round == total_rounds and completed and not active:
        # All matches in final round are complete
        final = completed[0]
        winner_id = final.get("winner")
        if winner_id:
            winner = f"<@{winner_id}>" if winner_id > 0 else f"Dummy {abs(winner_id)}"
            desc += f"\n🏆 **CHAMPION**: {winner}!"

    e = discord.Embed(
        title=f"🏆 {name} — Round {current_round}",
        description=desc,
        color=discord.Color.blue(),
    )
    e.set_footer(text="Use submit-score channel to report results")
    return e


async def _resolve_player_str(
    player_val: Any,
    get_team_name: Optional[Callable[[str], Coroutine[Any, Any, str]]] = None,
    default: str = "Unknown",
) -> str:
    """
    Resolve a player/team ID to a display string.

    Args:
        player_val: Player ID (int) or team ID (str) or None.
        get_team_name: Optional async callable to resolve team IDs.
        default: Default string if player_val is None.

    Returns:
        Display string for the player/team.
    """
    if player_val is None:
        return default

    if isinstance(player_val, str):
        if get_team_name:
            return await get_team_name(player_val)
        return player_val

    if isinstance(player_val, int):
        if player_val > 0:
            return f"<@{player_val}>"
        return f"Dummy {abs(player_val)}"

    return default


def build_score_submit_embed() -> discord.Embed:
    """
    Build the embed for the score submission panel.

    Returns:
        discord.Embed for score submission channel.
    """
    return discord.Embed(
        title="📝 Report Match Results",
        description="Click below to report your match score.",
        color=discord.Color.green(),
    )


def build_verification_embed(
    match: dict,
    p1_str: str,
    p2_str: str,
    winner_str: str,
    score: str,
    conflict: bool = False,
    reports: dict = None,
) -> discord.Embed:
    """
    Build embed for match verification/conflict resolution.

    Args:
        match: Match dictionary.
        p1_str: Display string for player 1.
        p2_str: Display string for player 2.
        winner_str: Display string for reported winner.
        score: Score string.
        conflict: Whether this is a conflict (both players reported differently).
        reports: Dictionary of reports for conflict display.

    Returns:
        discord.Embed for verification.
    """
    title = "⚠️ Match Conflict!" if conflict else "⚖️ Match Verification"
    color = discord.Color.red() if conflict else discord.Color.orange()

    embed = discord.Embed(
        title=title,
        description=f"**Match {match['id']}**\n{p1_str} vs {p2_str}",
        color=color,
    )

    if conflict and reports:
        for uid, r in reports.items():
            user_str = f"<@{uid}>"
            embed.add_field(
                name=f"Report by {user_str}",
                value=f"Winner: {r.get('winner_str', 'Unknown')}\nScore: {r['score']}",
                inline=False,
            )
        embed.set_footer(text="Admins: Please resolve this conflict.")
    else:
        embed.add_field(name="Reported Winner", value=winner_str, inline=True)
        embed.add_field(name="Score", value=score, inline=True)
        embed.set_footer(text="Admins: Confirm if this is correct.")

    return embed


def build_standings_embed(
    name: str,
    participant_count: int,
    winner_name: Optional[str] = None,
) -> discord.Embed:
    """
    Build embed to accompany the bracket image in standings channel.

    Args:
        name: Tournament name.
        participant_count: Number of participants.
        winner_name: Champion name if tournament is complete.

    Returns:
        discord.Embed for standings header.
    """
    embed = discord.Embed(
        title=f"🏆 {name} Bracket",
        color=discord.Color.blue(),
    )
    if winner_name:
        embed.description = f"🎉 **Champion: {winner_name}**"
    else:
        embed.description = f"Tournament in progress • {participant_count} players"

    return embed
