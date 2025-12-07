# UMS Bot Core v1.0.0-core

> The minimal, stable edition of Unified Match System — production ready.

---

## ⚡ Highlights

**UMS Bot Core** is a lean, predictable Discord bot for running **Single Elimination tournaments**. It's designed to be boring, stable, and hard to break.

This release marks the first public, production-ready version of UMS Bot Core.

---

## ✨ What's New

### Server Setup
- `/setup` — Quick Setup wizard with automatic channel creation
- `/config` — View current configuration
- Auto-creates `#ums-admin` with proper bot permissions

### Player Onboarding
- Single "Start Onboarding" button on persistent panel
- Ephemeral session with Region/Rank dropdowns
- One-shot completion — read-only summary after

### Tournament Management
- `/tournament_create` — Create Single Elimination tournaments
- `/tournament_open_registration` — Open signups
- `/tournament_close_registration` — Close signups
- `/tournament_start` — Generate bracket and begin
- Dashboard auto-updates after each match

### Admin Tools
- `/ums_report_result` — Admin Override Wizard (ephemeral select + buttons)
- `/ums_announce` — Announcement Wizard with templates
- `/admin_reset_player @user` — Reset player onboarding
- `/ums_factory_reset` — Wipe all bot data for a guild

### Dev Tools (gated by `DEV_USER_IDS`)
- `/ums_dev_tools` — Dev Tools Hub panel
- `/ums_dev_bracket_tools` — Dev Bracket Tools panel
- `/ums_dev_fill_dummies` — Add dummy entries
- `/ums_dev_auto_resolve` — Auto-resolve dummy matches

### UI/Branding
- `ui/brand.py` — Centralized color palette and embed helpers
- Brand-compliant embeds across all commands
- Footer: "UMS Bot Core v1.0.0-core"

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| `docs/README_CORE.md` | Setup and usage guide |
| `docs/ARCHITECTURE_NOW.md` | Current architecture overview |
| `docs/ADMIN_UX_STANDARD.md` | Admin/Dev UX rules |
| `docs/CORE_PRODUCT_SPEC.md` | Product specification |
| `docs/DEV_TOOLS_REFERENCE.md` | Dev tools documentation |
| `CHANGELOG.md` | Full changelog |

---

## 🧪 Test Coverage

```
======================== 16 passed in 0.24s =========================
```

Tests cover:
- Startup preflight (token, DB, schema)
- PlayerService (create, onboarding)
- GuildConfigService (CRUD)
- Factory reset behavior
- TournamentService (create, status transitions, one-active semantics)

---

## 🚀 Getting Started

```bash
git clone https://github.com/Comradecast/UMS.git
cd UMS
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Set DISCORD_TOKEN in .env
python bot.py
```

Then run `/setup` in your Discord server.

---

## 📋 What's NOT Included (by design)

- Solo Queue / matchmaking
- Double Elimination, Swiss, Round Robin
- Clans, teams, recurring tournaments
- Elo/Rating display (internal only)
- Leaderboard UI

These are Premium/Future features.

---

## 💡 Design Philosophy

1. **Dashboard as truth** — All state visible in one place
2. **One active tournament per guild** — Latest wins
3. **Ephemeral wizards** — Complex flows use select + buttons
4. **Brand consistency** — All embeds use centralized helpers
5. **Dev tools isolated** — Gated, never in public UI

---

**Full Changelog:** See `CHANGELOG.md`

**License:** MIT
