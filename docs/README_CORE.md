# UMS Bot Core

**UMS Bot Core** is the minimal, stable edition of Unified Match System.

It's designed to be **boring, predictable, and hard to break** — perfect for small and medium Discord servers that just want to run clean Single Elimination tournaments.

## Features

- **Single Elimination tournaments** — Create, manage, and complete brackets
- **Simple server setup** (`/setup`) — Quick Setup or manual channel selection
- **Player onboarding panel** — Region and rank self-registration
- **Safe factory reset** (`/ums_factory_reset`) — Wipe everything and start fresh

## What's NOT Included

Core intentionally excludes:
- Solo Queue / matchmaking queues
- Double Elimination, Swiss, round robin
- Clans, teams, recurring tournaments
- Advanced rating systems
- Dev/debug tools

These belong in the full UMS Bot or Premium tiers.

## Running Core Locally

```bash
git clone https://github.com/Comradecast/tournament-bot.git
cd tournament-bot
python -m venv venv
venv\Scripts\activate  # on Windows (or source venv/bin/activate on Linux/Mac)
pip install -r requirements-all.txt

# Set DISCORD_TOKEN in a .env file or your environment
python core-bot\bot.py
```

## Quick Start (Once Online)

1. Run `/setup` in your server and use **Quick Setup**
2. Players register via the **Onboarding Panel**
3. Create a tournament with `/tournament_create`
4. Open registration with `/tournament_open_registration`
5. Close registration with `/tournament_close_registration`
6. Start the bracket with `/tournament_start`
7. Report results with `/ums_report_result`
8. If you need to wipe everything, use `/ums_factory_reset`

## Core Commands

| Command | Description |
|---------|-------------|
| `/setup` | Configure UMS Bot Core for your server |
| `/config` | View current configuration |
| `/ums-help` | Get help and command overview |
| `/post_onboarding_panel` | Post player registration panel |
| `/tournament_create` | Create a new tournament |
| `/tournament_open_registration` | Open signups |
| `/tournament_close_registration` | Close signups |
| `/tournament_start` | Generate bracket and start |
| `/ums_report_result` | Report match results |
| `/ums_factory_reset` | Wipe all bot data for this server |

## Project Structure

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

## Documentation

- [`CORE_PRODUCT_SPEC.md`](./CORE_PRODUCT_SPEC.md) — Product specification
- [`CORE_RELEASE_CHECKLIST.md`](./CORE_RELEASE_CHECKLIST.md) — Release verification checklist
