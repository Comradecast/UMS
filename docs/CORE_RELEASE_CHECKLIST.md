# UMS Bot Core – Release Checklist

Target version: `v1.0.0-core`

---

## A. Repo & Branch

- [ ] Branch is up to date with main development branch
- [ ] `core-bot/` contains all Core specific entry points and config
- [ ] No experimental or Premium features are imported in Core

Notes:
- Branch:
- Commit:

---

## B. Startup & Migrations

### Fresh DB

- [ ] Delete existing DB file
- [ ] Run `python core-bot/bot.py`
- [ ] Migrations complete successfully
- [ ] No unexpected warnings or tracebacks
- [ ] Log clearly shows:
  - [ ] Starting Core Bot
  - [ ] Migration summary
  - [ ] Core services loaded

### Existing DB

- [ ] Run `python core-bot/bot.py` with an existing DB
- [ ] Legacy tables are skipped or migrated without errors
- [ ] No destructive changes to non Core tables

---

## C. Core Flows

### 1. Quick Setup

In a fresh guild:

- [ ] Run Quick Setup from the Admin Setup Panel
- [ ] Admin channel is created and logged
- [ ] Registration channel is created and logged
- [ ] Results channel is created and logged
- [ ] `guild_config` row contains:
  - [ ] Channel IDs
  - [ ] `*_channel_created` flags set correctly

### 2. Player Onboarding

- [ ] Open Onboarding Panel
- [ ] Complete onboarding as a test player
- [ ] `players` table updated as expected
- [ ] No errors in logs

### 3. Tournament Lifecycle

- [ ] Use `/tournament_create` to create a Single Elimination tournament
- [ ] Tournament row created with:
  - [ ] `tournament_code` set
  - [ ] Guild and channel references populated
- [ ] Bracket generated successfully
- [ ] Match reporting works end to end
- [ ] Tournament completes without errors

---

## D. Factory Reset

- [ ] Run `/ums_factory_reset`
- [ ] Bot created channels are deleted
- [ ] `guild_config` row removed or reset
- [ ] Tournament, entry, and match tables cleared for that guild
- [ ] Quick Setup can be run again from a clean state

---

## E. Tests

- [ ] `pytest` passes locally
- [ ] Core related tests exist for:
  - [ ] Guild setup
  - [ ] Tournament lifecycle
  - [ ] Factory reset behavior

Command used:

```bash
pytest
```

---

## F. Documentation & Branding

- [ ] `docs/CORE_PRODUCT_SPEC.md` updated for this release
- [ ] `README.md` contains:
  - [ ] Short description of UMS Bot Core
  - [ ] Basic setup instructions
- [ ] Bot presence:
  - [ ] Name: UMS Bot (or agreed branding)
  - [ ] Status message references `/ums_help` or similar
- [ ] `CHANGELOG.md` (or section in README) includes `v1.0.0-core` entry

---

## G. Final Sanity Check

- [ ] Invite the bot to a completely new test guild
- [ ] Follow the README instructions step by step
- [ ] Confirm that:
  - [ ] You never need to touch the database manually
  - [ ] All errors that occur are understandable and recoverable
  - [ ] The experience feels stable and predictable

**Sign-off:**

- Core behavior verified by: ____________
- Date: ____________
