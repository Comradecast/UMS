"""
Ranking utilities for Elo-based rank calculation
Matches Rocket League Sideswipe ranking system
"""


def get_rank_from_elo(elo: int) -> tuple[str, int]:
    """
    Convert Elo to rank name and division.
    Returns (rank_name, division) where division is 1-5 or 0 for GC

    Rank Brackets:
    - Bronze I-V: 0-799
    - Silver I-V: 800-999
    - Gold I-V: 1000-1199
    - Platinum I-V: 1200-1399
    - Diamond I-V: 1400-1599
    - Champion I-V: 1600-1799
    - Grand Champion: 1800+
    """
    if elo >= 1800:
        return "Grand Champion", 0
    elif elo >= 1600:
        division = min(5, max(1, 5 - ((elo - 1600) // 40)))
        return "Champion", division
    elif elo >= 1400:
        division = min(5, max(1, 5 - ((elo - 1400) // 40)))
        return "Diamond", division
    elif elo >= 1200:
        division = min(5, max(1, 5 - ((elo - 1200) // 40)))
        return "Platinum", division
    elif elo >= 1000:
        division = min(5, max(1, 5 - ((elo - 1000) // 40)))
        return "Gold", division
    elif elo >= 800:
        division = min(5, max(1, 5 - ((elo - 800) // 40)))
        return "Silver", division
    else:
        division = min(5, max(1, 5 - (elo // 160)))
        return "Bronze", division


def format_rank(rank_name: str, division: int) -> str:
    """Format rank as display string."""
    if rank_name == "Grand Champion":
        return "Grand Champion"

    roman_numerals = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
    div_str = roman_numerals.get(division, "I")
    return f"{rank_name} {div_str}"


def get_starting_elo_from_rank(rank_str: str) -> int:
    """
    Convert a rank string to starting Elo.
    Used when player first sets their rank.

    Examples:
    - "Bronze 3" -> 480 (mid Bronze III)
    - "Diamond 1" -> 1580 (mid Diamond I)
    - "Grand Champion" -> 1850
    """
    rank_str = rank_str.lower().strip()

    # Handle Grand Champion
    if "grand" in rank_str or "gc" in rank_str:
        return 1850

    # Parse rank and division
    parts = rank_str.split()
    if len(parts) < 2:
        return 1000  # Default to Gold I

    rank_name = parts[0].capitalize()
    division_str = parts[1]

    # Convert division
    division_map = {
        "1": 1,
        "2": 2,
        "3": 3,
        "4": 4,
        "5": 5,
        "i": 1,
        "ii": 2,
        "iii": 3,
        "iv": 4,
        "v": 5,
    }
    division = division_map.get(division_str.lower(), 3)  # Default to III

    # Base Elos for each rank
    base_elos = {
        "bronze": 0,
        "silver": 800,
        "gold": 1000,
        "platinum": 1200,
        "diamond": 1400,
        "champion": 1600,
    }

    base = base_elos.get(rank_name.lower(), 1000)

    # Each division is 40 Elo wide, start in the middle
    # Division 5 (highest) = base + 20
    # Division 1 (lowest) = base + 180
    elo = base + (200 - (division * 40)) + 20

    return elo


def get_rank_emoji(rank_name: str) -> str:
    """Get emoji for rank display."""
    emojis = {
        "Bronze": "🥉",
        "Silver": "🥈",
        "Gold": "🥇",
        "Platinum": "💎",
        "Diamond": "💠",
        "Champion": "👑",
        "Grand Champion": "🏆",
    }
    return emojis.get(rank_name, "⭐")
