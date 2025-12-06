# Changelog

All notable changes to UMS Bot Core will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-core] - 2025-12-06

### Added
- **UMS Bot Core** — Introduced as a minimal, stable edition of Unified Match System
- **Server Setup** (`/setup`, `/config`) — Quick Setup wizard with channel creation
- **Player Onboarding Panel** — Region and rank self-registration
- **Single Elimination Tournaments**:
  - `/tournament_create` — Create a new tournament
  - `/tournament_open_registration` — Open signups
  - `/tournament_close_registration` — Close signups
  - `/tournament_start` — Generate bracket and begin
  - `/ums_report_result` — Report match results
- **Factory Reset** (`/ums_factory_reset`) — Safe cleanup of all bot data for a guild
- **Bot Presence** — Status shows "/ums-help for info"
- **Core Test Suite** — Tests for factory reset and tournament lifecycle

### Documentation
- `CORE_PRODUCT_SPEC.md` — Product specification and scope
- `CORE_RELEASE_CHECKLIST.md` — Release verification checklist
- `README_CORE.md` — Setup and usage guide

### Excluded from Core
- Solo Queue / matchmaking queues
- Double Elimination, Swiss, round robin
- Clans, teams, recurring tournaments
- Advanced rating systems
- Developer/debug tools
