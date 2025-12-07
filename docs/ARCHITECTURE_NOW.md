# UMS Bot Core — Architecture (v1.0.0)

> Current architecture overview for UMS Bot Core.

---

## Overview

UMS Bot Core is a minimal, stable Discord bot for running **Single Elimination tournaments**. It prioritizes:

- **Simplicity** — One tournament format, clear workflows
- **Stability** — Battle-tested service layer, unified logic paths
- **Consistency** — Brand-compliant UI, predictable UX

---

## UX Lanes

Core defines three distinct UX lanes:

### 1. Player UX
- **Onboarding** — `/onboard` or persistent panel → ephemeral session
- **Dashboard** — Single source of truth for tournament state
- **Registration** — Button-based signup flow

### 2. Admin UX
- **Setup** — `/setup` (Quick Setup or manual channel selection)
- **Control Panel** — Persistent buttons for tournament workflow
- **Admin Override Wizard** — `/ums_report_result` (ephemeral, select + buttons)
- **Destructive actions** — Slash-only (`/ums_factory_reset`, `/admin_reset_player`)

### 3. Developer UX
- **Dev Tools Hub** — `/ums_dev_tools` (ephemeral panel)
- **Bracket Tools** — `/ums_dev_bracket_tools` (ephemeral panel)
- **Utilities** — `/ums_dev_fill_dummies`, `/ums_dev_auto_resolve`
- All gated by `DEV_USER_IDS`

---

## Core Components

### Cogs
| Cog | Responsibility |
|-----|----------------|
| `server_setup.py` | Setup, config, factory reset |
| `onboarding_view.py` | Player onboarding flow |
| `tournaments.py` | Tournament CRUD, dev tools |
| `announcements.py` | Announcement wizard |

### Services
| Service | Responsibility |
|---------|----------------|
| `TournamentService` | Tournament/match CRUD, bracket generation |
| `PlayerService` | Player profiles, onboarding |
| `GuildConfigService` | Guild configuration |
| `RatingService` | Elo calculations (internal) |

### UI Package
| File | Contents |
|------|----------|
| `brand.py` | Color palette, embed helpers, footer |
| `tournament_views.py` | Dashboard, admin panel, dev tools |
| `registration_views.py` | Registration buttons |
| `match_views.py` | Match reporting |

---

## Tournament Lifecycle

```
draft → reg_open → reg_closed → in_progress → completed
                                      ↓
                                 cancelled
```

### Key Flows
1. **Create** → `/tournament_create` or Control Panel
2. **Register** → Registration panel buttons
3. **Start** → Builds bracket, creates round 1 matches
4. **Report** → Dashboard "My Match" or Admin Override Wizard
5. **Complete** → Auto-advances, updates dashboard, shows trophy

---

## Dashboard Architecture

The **Tournament Dashboard** is the single source of truth:

- Shows current bracket state
- "My Match" button for player result reporting
- Auto-updates after each match completion
- Transforms to trophy display on completion

**Update trigger:** `update_tournament_dashboard()` called after every match result.

---

## Brand Kit (v1)

All UI uses centralized constants from `ui/brand.py`:

| Color | Hex | Usage |
|-------|-----|-------|
| Primary Blue | `#2A6FDB` | Default embeds |
| Success Green | `#3BA55D` | Success messages |
| Warning Yellow | `#FAA61A` | Warnings |
| Error Red | `#ED4245` | Errors |

**Footer:** `UMS Bot Core v1.0.0-core`

---

## Dev Tools

### Dev Tools Hub (`/ums_dev_tools`)
Central panel with buttons:
- **Bracket Tools** — Opens Dev Bracket Tools
- **Add Dummy Entries** — Fills tournament
- **Auto-resolve All** — Completes dummy matches

### Dev Bracket Tools (`/ums_dev_bracket_tools`)
Fine-grained bracket control:
- **Advance One Match** — Select + random winner
- **Advance Current Round** — All matches in lowest round
- **Auto-resolve All** — All dummy vs dummy matches

---

## Database

Core uses SQLite with shared schema (compatible with full UMS Bot):

| Table | Core Usage |
|-------|------------|
| `guild_configs` | ✅ Active |
| `players` | ✅ Active |
| `tournaments` | ✅ Active |
| `tournament_entries` | ✅ Active |
| `matches` | ✅ Active |
| `player_ranks` | ⬜ Schema only |
| `ums_global_matches` | ⬜ Schema only |

---

## File Structure

```
core-bot/
├── bot.py                  # Entry point
├── database.py             # Schema + migrations
├── core_version.py         # Version constant
├── cogs/
│   ├── server_setup.py     # Setup flows
│   ├── onboarding_view.py  # Player onboarding
│   └── tournaments.py      # Tournament management
├── services/
│   ├── tournament_service.py
│   ├── player_service.py
│   ├── guild_config_service.py
│   └── rating_service.py
├── ui/
│   ├── brand.py            # Brand constants
│   ├── tournament_views.py # Views + embeds
│   ├── registration_views.py
│   └── match_views.py
└── docs/
    ├── ARCHITECTURE_NOW.md  # This file
    ├── ADMIN_UX_STANDARD.md # UX rules
    └── CORE_PRODUCT_SPEC.md # Product spec
```

---

## Active Tournament Semantics

Core supports **one active tournament per guild** at a time.

**Behavior:**
- `TournamentService.get_active_for_guild()` returns the newest tournament with status in: `draft`, `reg_open`, `reg_closed`, or `in_progress`
- All commands (`/tournament_*`, dev tools) operate on this "active" tournament
- Creating a new tournament does not cancel the old one — it just becomes the new "active"
- Old tournaments remain until manually completed, cancelled, or archived

**Implication:** If an admin creates multiple tournaments in a row, only the latest one will be targeted by commands. This is by design for simplicity.

---

## Ratings Visibility

Core includes a `RatingService` for Elo calculations, but **Elo is not displayed** to users in Core:

- `services/rating_service.py` exists and calculates Elo deltas
- Tournament matches can update Elo internally
- No leaderboard, no rank display, no Elo indicators in dashboards
- This is intentional: Elo/rating UI is a Premium feature

The service exists for schema alignment with the full UMS Bot and to enable future upgrades.

---

## Key Design Decisions

1. **Dashboard as truth** — All state visible in one place
2. **TournamentService as engine** — All business logic centralized
3. **Ephemeral wizards** — Complex flows use select + buttons, not slash params
4. **Brand consistency** — All embeds use `ui/brand.py` helpers
5. **Dev tools isolated** — Gated by `DEV_USER_IDS`, never in public UI
6. **One active tournament** — Latest active tournament per guild for simplicity

---

_Last updated: 2025-12-06_
