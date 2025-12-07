# UMS Bot Core

**UMS Bot Core** is the minimal, stable edition of Unified Match System.

It's designed to be **boring, predictable, and hard to break** — perfect for small and medium Discord servers that just want to run clean Single Elimination tournaments.

## Features

- **Single Elimination tournaments** — Create, manage, and complete brackets
- **Simple server setup** (`/setup`) — Quick Setup or manual channel selection
- **Player onboarding panel** — Region and rank self-registration
- **Admin Override Wizard** (`/ums_report_result`) — Modern ephemeral UI for result overrides
- **Safe factory reset** (`/ums_factory_reset`) — Wipe everything and start fresh

## What's NOT Included

Core intentionally excludes:
- Solo Queue / matchmaking queues
- Double Elimination, Swiss, round robin
- Clans, teams, recurring tournaments
- Advanced rating systems

These belong in the full UMS Bot or Premium tiers.

## Running Core Locally

```bash
git clone https://github.com/Comradecast/UMS.git
cd UMS/core-bot
python -m venv venv
venv\Scripts\activate  # on Windows (or source venv/bin/activate on Linux/Mac)
pip install -r requirements.txt

# Set DISCORD_TOKEN in a .env file or your environment
python bot.py
```

## Quick Start (Once Online)

1. Run `/setup` in your server and use **Quick Setup**
2. Players register via the **Onboarding Panel**
3. Create a tournament with `/tournament_create`
4. Open registration with `/tournament_open_registration`
5. Close registration with `/tournament_close_registration`
6. Start the bracket with `/tournament_start`
7. Override results with `/ums_report_result` (Admin Override Wizard)
8. If you need to wipe everything, use `/ums_factory_reset`

## Core Commands

| Command | Description |
|---------|-------------|
| `/setup` | Configure UMS Bot Core for your server |
| `/config` | View current configuration |
| `/ums-help` | Get help and command overview |
| `/tournament_create` | Create a new tournament |
| `/tournament_open_registration` | Open signups |
| `/tournament_close_registration` | Close signups |
| `/tournament_start` | Generate bracket and start |
| `/ums_report_result` | Admin Override Wizard |
| `/ums_announce` | Announcement Wizard |
| `/admin_reset_player` | Reset a player's onboarding |
| `/ums_factory_reset` | Wipe all bot data for this server |

## Dev Commands (DEV_USER_IDS only)

| Command | Description |
|---------|-------------|
| `/ums_dev_tools` | Dev Tools Hub panel |
| `/ums_dev_bracket_tools` | Dev Bracket Tools panel |
| `/ums_dev_fill_dummies` | Add dummy entries to tournament |
| `/ums_dev_auto_resolve` | Auto-resolve dummy matches |

## Project Structure

```
UMS/
├── docs/               # Documentation (at repo root)
├── core-bot/           # Bot code
│   ├── bot.py          # Main entry point
│   ├── database.py     # DB init + migrations
│   ├── cogs/           # Discord command layer
│   ├── services/       # Business logic
│   ├── ui/             # Views, embeds, brand kit
│   └── tests/          # Test suite
├── README.md
├── LICENSE
└── CONTRIBUTING.md
```

## Documentation

- [`ARCHITECTURE_NOW.md`](./ARCHITECTURE_NOW.md) — Current architecture overview
- [`ADMIN_UX_STANDARD.md`](./ADMIN_UX_STANDARD.md) — Admin/Dev UX rules
- [`CORE_PRODUCT_SPEC.md`](./CORE_PRODUCT_SPEC.md) — Product specification
- [`CORE_RELEASE_CHECKLIST.md`](./CORE_RELEASE_CHECKLIST.md) — Release verification checklist
