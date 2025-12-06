# Core-Bot Scope Definition

**Version:** 1.0
**Date:** 2025-12-04

---

## In Scope

| Feature | Description |
|---------|-------------|
| Player Profiles | Onboarding, profile display, stats |
| Single Elimination | SE bracket tournaments only |
| Elo Ratings | Basic per-mode Elo tracking |
| Leaderboard | Server leaderboard display |
| Server Setup | Basic channel/role configuration |
| Diagnostics | Health checks, bot status |
| Global Match Logging | UMS match history |

---

## Explicitly Out of Scope

| Feature | Reason |
|---------|--------|
| Double Elimination | Advanced tournament type |
| Solo Queue | Matchmaking complexity |
| Clans | Social feature |
| Teams | Social feature |
| Casual Matches | Non-tournament feature |
| Recurring Tournaments | Scheduler complexity |
| Dashboards/Portals | UI complexity |
| Dev/Debug Tools | Internal only |

---

## Migration Path

Features can be added to core-bot by:
1. Copying the relevant cog/service from main repo
2. Updating imports
3. Adding any required migrations
4. Testing bootability
