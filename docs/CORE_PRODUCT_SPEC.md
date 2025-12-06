# UMS Bot Core – Product Spec (v1.0)

## 1. Product Statement

UMS Bot Core is the stable, minimal version of the Unified Match System.
It lets any Discord server owner host clean, single elimination tournaments with:

- A simple onboarding panel for players
- A quick setup panel for admins
- Direct tournament creation and management commands
- A safe factory reset for when things go sideways

Core is designed to be **boring, predictable, and hard to break**.

Premium features like solo queue, double elimination, clans, and advanced ratings will live in the full UMS Bot, not in Core.

---

## 2. Core Use Cases

1. **New community server wants to run a bracket tonight**
   - Invite UMS Bot Core
   - Run Quick Setup
   - Players onboard
   - Organizer runs `/tournament_create` followed by the tournament commands
   - Matches are played and reported
   - Organizer posts results

2. **Organizer wants to wipe a broken test setup**
   - Use `/ums_factory_reset`
   - Bot removes its own channels and config
   - Run Quick Setup again to start fresh

---

## 3. Included Features (v1.0)

### 3.1 Onboarding

- Onboarding Panel entry point
- Create/update player profile:
  - Region
  - Rank / skill indicator
- Data stored in the unified `players` table and related tables

### 3.2 Server Setup

- Admin Setup Panel:
  - Quick Setup flow to:
    - Create or configure:
      - Admin channel
      - Tournament registration channel
      - Tournament results channel
    - Persist IDs and `*_channel_created` flags in `guild_config`
- Idempotent behavior:
  - Running setup again does not explode or duplicate channels

### 3.3 Tournament Basics

Core uses a direct tournament creation flow, optimized for small and medium servers.

- Admins or organizers use slash commands to manage tournaments:
  - `/tournament_create` – Create a new Single Elimination tournament
  - `/tournament_open_registration` – Open signups
  - `/tournament_close_registration` – Close signups
  - `/tournament_start` – Generate and start the bracket
  - `/ums_report_result` – Report match results

- Each tournament is stored in the database with:
  - A numeric ID
  - A human-readable name
  - Associated guild and channel IDs as needed

There is **no request/approval workflow** in Core. That is reserved for the full UMS Bot / Premium tiers.

### 3.4 Safety Tools

- `/ums_factory_reset`:
  - Deletes bot created channels where `*_channel_created = 1`
  - Clears:
    - Guild config row
    - Tournaments
    - Tournament entries
    - Matches
  - Leaves the guild in a "fresh install" state

---

## 4. Explicit Non-Goals for Core

The following are out of scope for Core v1.0:

- Solo queue or automated matchmaking queues
- Double elimination, Swiss, round robin
- Clans, persistent teams, recurring events
- Complex rating systems or provisional rank pipelines
- Developer only auto-simulation helpers

These belong in the full UMS Bot or future add-ons, not in the Core baseline.

---

## 5. Technical Boundaries

- **Runtime**: Python 3.x, discord.py
- **Database**: SQLite with migrations
- **Bot entry point**: `core-bot/bot.py`
- **Cogs / services loaded**:
  - Only the minimal set needed for Core features
  - No experimental or Premium features registered

Core must start cleanly on:

- A brand new database
- An existing database from the main bot, without corrupting data

---

## 6. Definition of Done (Core v1.0)

UMS Bot Core v1.0 is considered "done" when:

1. A fresh guild can:
   - Run Quick Setup
   - Onboard players
   - Run a Single Elimination tournament
   - Complete the tournament
2. `/ums_factory_reset` returns the guild to a clean state.
3. All Core pytest suites pass.
4. Startup logs are clear and understandable for an average admin.
5. This document and `CORE_RELEASE_CHECKLIST.md` are up to date.
