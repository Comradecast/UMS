"""
Constants for the tournament bot.
Centralized definitions for regions, ranks, and other shared values.
"""

# Region definitions - used throughout the bot for matchmaking and organization
REGIONS = {
    "USE": "US-East",
    "USW": "US-West",
    "USC": "US-Central",
    "EU": "Europe",
    "ASC": "Asia SE-Mainland",
    "ASM": "Asia SE-Maritime",
    "ME": "Middle East",
    "JPN": "Asia East",
    "OCE": "Oceania",
    "SAF": "South Africa",
    "SAM": "South America",
    "IND": "India",
}

# Region codes in display order
REGION_CODES = [
    "USE",
    "USW",
    "USC",
    "EU",
    "ASC",
    "ASM",
    "ME",
    "JPN",
    "OCE",
    "SAF",
    "SAM",
    "IND",
]

# Rank definitions
RANKS = {
    "Bronze": 1,
    "Silver": 2,
    "Gold": 3,
    "Platinum": 4,
    "Diamond": 5,
    "Champion": 6,
    "Grand Champion": 7,
}

# Detailed Elo mappings for each rank-division combination
# Based on https://rocketleague.tracker.network/rocket-league/distribution
# Each rank has 5 divisions (V=lowest, I=highest), each ~30-40 Elo wide
RANK_TO_ELO = {
    # Bronze: 500-799
    "Bronze V": 500,
    "Bronze IV": 570,
    "Bronze III": 640,
    "Bronze II": 710,
    "Bronze I": 780,
    # Silver: 800-1099
    "Silver V": 800,
    "Silver IV": 870,
    "Silver III": 940,
    "Silver II": 1010,
    "Silver I": 1080,
    # Gold: 1100-1549
    "Gold V": 1100,
    "Gold IV": 1190,
    "Gold III": 1280,
    "Gold II": 1370,
    "Gold I": 1570,
    # Platinum: 1550-1849
    "Platinum V": 1550,
    "Platinum IV": 1610,
    "Platinum III": 1710,
    "Platinum II": 1770,
    "Platinum I": 1830,
    # Diamond: 1850-2149
    "Diamond V": 1850,
    "Diamond IV": 1930,
    "Diamond III": 1990,
    "Diamond II": 2050,
    "Diamond I": 2130,
    # Champion: 2150-2449
    "Champion V": 2150,
    "Champion IV": 2230,
    "Champion III": 2290,
    "Champion II": 2350,
    "Champion I": 2430,
    # Grand Champion: 2450+
    "Grand Champion": 2450,
}
