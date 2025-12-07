# UMS Bot — Admin UX Standard

> Authoritative specification for all administrative UI/UX decisions in UMS Bot Core.

---

## Purpose

This document defines the interaction model for all administrative, destructive, and development actions in UMS Bot. It ensures:

- **Safety** — Destructive actions require explicit intent
- **Clarity** — Users always know what will happen
- **Consistency** — Same patterns across all features
- **Auditability** — Discord logs capture all admin actions

---

## Core Principle: Slash Commands as Entry Points

All administrative actions in UMS Bot Core are invoked via **slash commands**. Some slash commands open **ephemeral UI panels** with buttons for convenience, but the entry point is always a slash command.

This ensures:
- Discord audit logs capture command invocation
- No accidental triggers from public panels
- Clear permission boundaries

---

## Categories & Rules

### 1. Dev / Debug Tools

**Rule:** Development commands are slash-only entry points, gated by `DEV_USER_IDS`.

| Requirement | Implementation |
|-------------|----------------|
| Entry Point | Slash command (e.g., `/ums_dev_tools`) |
| UI After Invocation | Ephemeral panel with buttons (dev-only) |
| Access | Gated by `DEV_USER_IDS` environment variable |
| Visibility | Hidden from all public/player-facing UI |
| Naming | Prefix with `ums_dev_` |

**Core v1.0.0 Dev Commands:**
| Command | What It Opens |
|---------|---------------|
| `/ums_dev_tools` | Dev Tools Hub (ephemeral panel with buttons) |
| `/ums_dev_bracket_tools` | Dev Bracket Tools (ephemeral panel with buttons) |
| `/ums_dev_fill_dummies` | Direct action (adds dummy entries) |
| `/ums_dev_auto_resolve` | Direct action (resolves dummy matches) |

**Rationale:** Slash command entry ensures audit trail and prevents accidental activation. Ephemeral buttons after invocation are fine because access is already gated.

---

### 2. Destructive Admin Actions

**Rule:** Guild-wide or irreversible actions require slash command + confirmation modal.

| Requirement | Implementation |
|-------------|----------------|
| Entry Point | Slash command with confirmation modal |
| Buttons | ❌ Never (no button should trigger these) |
| Logging | Should log to admin channel when possible |

**Core Commands:**
| Command | Action |
|---------|--------|
| `/ums_factory_reset` | Wipe all bot data for guild (confirmation required) |
| `/admin_reset_player @user` | Reset player's onboarding status |

**UI Reference Pattern:**
Panels may reference these commands textually:
> _"Run `/ums_factory_reset` if you need to start over."_

But panels must **never** have a button that executes destructive actions.

**Rationale:**
- Accidental button clicks must be impossible
- Discord audit logs capture slash command usage
- Mental friction reduces mistakes

---

### 3. Admin Override Actions

**Rule:** Actions that modify tournament state use slash commands that open ephemeral wizard UIs.

| Requirement | Implementation |
|-------------|----------------|
| Entry Point | Slash command |
| UI After Invocation | Ephemeral wizard with select menus and buttons |
| Confirmation | Built into wizard flow |

**Core Commands:**
| Command | What It Opens |
|---------|---------------|
| `/ums_report_result` | Admin Override Wizard (select match → select winner → confirm) |
| `/ums_announce` | Announcement Wizard (select template → preview → publish) |

**Rationale:** These actions need context (which match? which template?) so a wizard UI guides the admin through the decision, but the entry point is always a slash command for auditability.

---

### 4. Tournament Lifecycle Actions

**Rule:** Tournament lifecycle actions can be invoked via slash commands OR via Admin Control Panel buttons.

| Requirement | Implementation |
|-------------|----------------|
| Primary UX | Buttons in Admin Control Panel |
| Alternative UX | Slash command equivalents |
| Context | Panel provides tournament context |

**Actions (Both Slash and Panel):**
| Action | Slash Command | Panel Button |
|--------|---------------|--------------|
| Create tournament | `/tournament_create` | ✅ |
| Open registration | `/tournament_open_registration` | ✅ |
| Close registration | `/tournament_close_registration` | ✅ |
| Start bracket | `/tournament_start` | ✅ |

**Rationale:**
- Admin is often looking at the dashboard/panel
- Buttons reduce friction for common operations
- Slash commands available for power users or automation

---

### 5. Player Management

**Rule:** Player management actions are slash commands.

| Requirement | Implementation |
|-------------|----------------|
| Entry Point | Slash command |
| Confirmation | Required for state changes |

**Core Commands:**
| Command | Action |
|---------|--------|
| `/admin_reset_player @user` | Reset player onboarding status |

**Rationale:** Player resets are rare. Adding buttons would create clutter for infrequent actions.

---

## Safety Guarantees

1. **No destructive action can be triggered by a single button click**
2. **All slash commands log to Discord audit trail**
3. **Confirmation modals for irreversible operations**
4. **Admin-only decorators enforce permissions at command level**
5. **Ephemeral responses prevent public confusion**

---

## Summary Table

| Category | Entry Point | Ephemeral UI | Public Panel Buttons |
|----------|-------------|--------------|---------------------|
| Dev tools | Slash | ✅ (buttons after invoke) | ❌ Never |
| Destructive admin | Slash + Modal | ❌ | ❌ Never |
| Admin overrides | Slash | ✅ (wizard) | ❌ Never |
| Tournament lifecycle | Slash or Panel | Optional | ✅ Allowed |
| Player tools | Slash | Optional | ❌ Rare use |

---

## Dev Tools Reference (Core v1.0.0)

### `/ums_dev_tools` — Dev Tools Hub

Opens an ephemeral panel with these buttons:

| Button | Action |
|--------|--------|
| Bracket Tools | Opens Dev Bracket Tools panel |
| Add Dummy Entries | Fills tournament with dummy players |
| Auto-resolve All | Resolves all dummy vs dummy matches |
| Close | Closes the hub |

### `/ums_dev_bracket_tools` — Dev Bracket Tools

Opens an ephemeral panel for fine-grained bracket control:

| Button | Action |
|--------|--------|
| Advance One Match | Select dropdown → random winner |
| Advance Current Round | Resolves all matches in lowest round |
| Auto-resolve All | Resolves all dummy vs dummy matches |
| Close | Closes the panel |

---

## Implementation Status (Core v1.0.0)

| Standard | Status |
|----------|--------|
| Dev commands gated by `DEV_USER_IDS` | ✅ |
| `/ums_factory_reset` requires confirmation modal | ✅ |
| `/admin_reset_player` is slash-only | ✅ |
| `/ums_report_result` opens ephemeral wizard | ✅ |
| `/ums_announce` opens ephemeral wizard | ✅ |
| Tournament lifecycle in Admin Control Panel | ✅ |
| Dev Tools Hub (`/ums_dev_tools`) | ✅ |
| Dev Bracket Tools (`/ums_dev_bracket_tools`) | ✅ |

---

_Last updated: 2025-12-06_
