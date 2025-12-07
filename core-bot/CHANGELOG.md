# Changelog

All notable changes to UMS Bot Core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0-core] - 2025-12-06

### Added
- **Premium Integration** — Optional connection to UMS Premium Service backend
  - `premium_cogs/premium_client.py` — Async HTTP client for Premium API
  - `premium_cogs/solo_queue_ui.py` — Premium Solo Queue panel and match UI
  - `config/premium_config.py` — Environment-based configuration
- **Premium Solo Queue**:
  - `/premium_post_solo_panel` — Post ranked queue panel (admin)
  - `/premium_matchmaking_tick` — Manual matchmaking trigger (admin/dev)
  - Join 1v1/2v2 Ranked buttons
  - My Status button for queue position and Elo ratings
  - Match result buttons (I Won / Opponent Won / Cancel)
- Environment variables for Premium:
  - `PREMIUM_ENABLED` — Toggle Premium features (default: 0)
  - `PREMIUM_API_URL` — Backend URL (e.g., http://localhost:8000)
  - `PREMIUM_API_KEY` — Shared secret for authentication
- Dependency: `aiohttp>=3.9.0` for Premium HTTP client

### Changed
- Bot startup now includes optional Premium phase
- Shutdown gracefully closes Premium client session

---

## [1.0.0-core] - 2025-12-06
- **UMS Bot Core** — Minimal, stable edition of Unified Match System
- **Server Setup**:
  - `/setup` — Quick Setup wizard with channel creation
  - `/config` — View current configuration
  - Auto-creates `#ums-admin` with bot permissions if needed
- **Player Onboarding** (Option A):
  - Single "Start Onboarding" button on public panel
  - Ephemeral session view with Region/Rank dropdowns
  - One-shot completion — read-only summary after
  - `/onboard` command for direct access
- **Admin Tools**:
  - `/admin_reset_player @user` — Reset player's onboarding
  - `/ums_factory_reset` — Wipe all bot data for a guild
  - `/ums_report_result` — Admin Override Wizard (ephemeral select + buttons)
  - `/ums_announce` — Announcement Wizard (ephemeral, templates + custom)
- **Single Elimination Tournaments**:
  - `/tournament_create` — Create a new tournament
  - `/tournament_open_registration` — Open signups
  - `/tournament_close_registration` — Close signups
  - `/tournament_start` — Generate bracket and begin
  - Dashboard auto-updates after each match
- **Dev Tools** (gated by `DEV_USER_IDS`):
  - `/ums_dev_tools` — Dev Tools Hub panel
  - `/ums_dev_bracket_tools` — Dev Bracket Tools panel
  - `/ums_dev_fill_dummies` — Add dummy entries to tournament
  - `/ums_dev_auto_resolve` — Auto-resolve dummy matches
- **UI/Branding**:
  - `ui/brand.py` — Centralized color palette and embed helpers
  - Brand-compliant embeds across all commands
  - Footer: "UMS Bot Core v1.0.0-core"
- **Bot Presence** — Status shows "/ums-help for info"
- **Core Test Suite** — 16 tests covering factory reset, onboarding, tournaments

### Fixed
- Quick Setup now handles permission errors gracefully
- Factory Reset handles 404 when channel was deleted
- Pytest no longer hangs (fixed aiosqlite connection cleanup)

### Documentation
- `ARCHITECTURE_NOW.md` — Current architecture overview
- `ADMIN_UX_STANDARD.md` — Admin/Dev UX rules
- `CORE_PRODUCT_SPEC.md` — Product specification and scope
- `CORE_RELEASE_CHECKLIST.md` — Release verification checklist
- `README_CORE.md` — Setup and usage guide
