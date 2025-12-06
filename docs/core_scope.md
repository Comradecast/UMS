# Core-Bot Scope Definition

> **Version:** 1.0.0-core
> **Updated:** 2025-12-06
> **Status:** This document reflects the current Core v1.0.0 implementation.

---

## In Scope (Core v1.0.0)

| Feature | Description |
|---------|-------------|
| Player Onboarding | Region/rank selection via ephemeral UI |
| Single Elimination | SE bracket tournaments only |
| Tournament Dashboard | Live bracket display, auto-updates |
| Server Setup | `/setup` wizard, channel creation |
| Admin Override Wizard | `/ums_report_result` (ephemeral UI) |
| Factory Reset | `/ums_factory_reset` for clean wipe |
| Dev Tools | `/ums_dev_tools`, `/ums_dev_bracket_tools` (DEV_USER_IDS only) |

---

## Explicitly Out of Scope

| Feature | Reason |
|---------|--------|
| Double Elimination | Advanced tournament type |
| Swiss / Round Robin | Advanced tournament type |
| Solo Queue | Matchmaking complexity |
| Clans | Social feature (Premium) |
| Teams (persistent) | Social feature (Premium) |
| Casual Matches | Non-tournament feature |
| Recurring Tournaments | Scheduler complexity |
| Elo Display | Internal only in Core |
| Leaderboard UI | Premium feature |

---

## Key Design Decisions

1. **One Active Tournament Per Guild** — Commands operate on the latest non-archived tournament
2. **Dashboard as Truth** — Tournament state is always visible in one place
3. **Ephemeral Wizards** — Complex flows use select + buttons, not slash params
4. **Dev Tools Gated** — All `ums_dev_*` commands require `DEV_USER_IDS`

---

## Migration to Full UMS Bot

Features can be added by:
1. Copying relevant cog/service from main repo
2. Updating imports
3. Adding required migrations
4. Testing bootability
5. Updating documentation

---

_See also: [ARCHITECTURE_NOW.md](./ARCHITECTURE_NOW.md), [CORE_PRODUCT_SPEC.md](./CORE_PRODUCT_SPEC.md)_
