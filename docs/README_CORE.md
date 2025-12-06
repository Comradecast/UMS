# Core-Bot README

This is the **minimal external version** of the tournament bot.

## Scope

**Included:**
- Player onboarding / profiles
- Single Elimination tournaments ONLY
- Basic Elo-based ratings / leaderboard
- Minimal server setup/config
- Health/diagnostics
- UMS/global match logging

**Excluded:**
- Double Elimination
- Solo Queue / matchmaking queues
- Clans / Teams
- Casual matches
- Recurring tournaments / scheduler panels
- Dashboards / portals
- Dev/debug tools

## Getting Started

```bash
cd tournament-bot
python core-bot/bot.py
```

## Structure

```
core-bot/
├── bot.py              # Main entry point
├── database.py         # DB init + migrations
├── constants.py        # Shared constants
├── cogs/               # Discord command layer
├── services/           # Business logic
├── utils/              # Utilities
├── config/             # Configuration
├── migrations/         # DB migrations
├── docs/               # Documentation
└── tests/              # Test suite
```
