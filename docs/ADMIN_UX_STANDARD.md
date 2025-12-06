# UMS Bot — Admin UX Standard (Core & Premium)

> Authoritative specification for all administrative UI/UX decisions in the Unified Match System ecosystem.

---

## Purpose

This document defines the interaction model for all administrative, destructive, and development actions in UMS Bot. It ensures:

- **Safety** — Destructive actions require explicit intent
- **Clarity** — Users always know what will happen
- **Consistency** — Same patterns across Core and Premium
- **Auditability** — Discord logs capture all admin actions

---

## Categories & Rules

### 1. Dev / Debug Tools — Slash Only

**Rule:** Development commands are slash-only, never exposed in panels or menus.

| Requirement | Implementation |
|-------------|----------------|
| Access | Gated by `DEV_USER_IDS` environment variable |
| Visibility | Hidden from all user-facing UI |
| Naming | Prefix with `ums_dev_` |
| Labeling | Must clearly indicate "Development Only" in description |

**Core v1.0.0 Dev Commands:**
- `/ums_dev_tools` — Dev Tools Hub panel
- `/ums_dev_bracket_tools` — Dev Bracket Tools panel
- `/ums_dev_fill_dummies` — Add dummy entries to tournament
- `/ums_dev_auto_resolve` — Auto-resolve dummy matches

**Rationale:** Dev tools can break state and should never be accidentally triggered.

---

### 2. Destructive Admin Actions — Slash Only

**Rule:** Guild-wide or irreversible actions are slash-only. No buttons, no panels.

| Requirement | Implementation |
|-------------|----------------|
| Invocation | Slash command with confirmation modal |
| Visibility | May be referenced in panels, never executed from panels |
| Logging | Should log to admin channel when possible |

**Core Commands:**
- `/ums_factory_reset` — Wipe all bot data for guild
- `/admin_reset_player @user` — Reset player's onboarding

**Future/Premium:**
- `/ums_wipe_tournaments`
- `/ums_rebuild_schema`
- `/ums_clear_ratings`

**Rationale:**
- Accidental button clicks must be impossible
- Discord audit logs capture slash command usage
- Mental friction reduces mistakes

**UI Reference Pattern:**
Panels may say: _"Run `/ums_factory_reset` if you need to start over."_
But panels must NOT have a button that executes it.

---

### 3. Tournament-Local Admin Actions — Panel Buttons (Primary)

**Rule:** Actions scoped to a single tournament use buttons in the dashboard/panel.

| Requirement | Implementation |
|-------------|----------------|
| Primary UX | Buttons in Admin Control Panel or Tournament Dashboard |
| Secondary UX | Optional slash command equivalents for power users |
| Context | Dashboard/panel provides tournament context |

**Actions:**
- Create tournament
- Open/close registration
- Start bracket
- Override match result
- Replay/reset match
- Advance bracket
- Archive tournament

**Rationale:**
- Admin is looking at that tournament's dashboard
- Fewer clicks, faster operations
- Clear context prevents "wrong tournament" mistakes

**Slash Equivalents (Optional):**
```
/ums_override_result tournament:8N7A8YWR match:3 winner:@Player
```

---

### 4. Player Management — Slash-First

**Rule:** Player management actions are slash commands, with optional panel access in future.

| Requirement | Implementation |
|-------------|----------------|
| Primary UX | Slash command |
| Future UX | Optional "Player Tools" button → ephemeral toolbox |
| Confirmation | Required for destructive player actions |
| Logging | Log to #ums-admin |

**Core Commands:**
- `/admin_reset_player @user` — Reset player onboarding

**Future Pattern (Optional):**
- Admin panel "Player Tools" button
- Opens ephemeral admin-only toolbox
- Contains "Reset Player Onboarding" with modal confirmation
- Calls same underlying service logic

**Rationale:** Player resets are rare. Buttons would add clutter for infrequent actions.

---

## Safety Guarantees

1. **No destructive action can be triggered by a single click**
2. **All slash commands log to Discord audit trail**
3. **Confirmation modals for irreversible operations**
4. **Admin-only decorators enforce permissions at command level**
5. **Ephemeral responses prevent public confusion**

---

## Summary Table

| Category | Primary UX | Buttons Allowed | Slash Required |
|----------|------------|-----------------|----------------|
| Dev tools | Slash | ❌ Never | ✅ Always |
| Destructive admin | Slash | ❌ Never | ✅ Always |
| Tournament actions | Buttons | ✅ Yes | Optional |
| Player tools | Slash | ⚠️ Future | ✅ Always |

---

## Implementation in Core v1.0.0

| Standard | Status |
|----------|--------|
| Dev commands gated by `DEV_USER_IDS` | ✅ |
| `/ums_factory_reset` is slash-only | ✅ |
| `/admin_reset_player` is slash-only | ✅ |
| Tournament actions in Admin Control Panel | ✅ |
| Confirmation modals for destructive actions | ✅ |
| Admin Override Wizard (`/ums_report_result`) | ✅ |
| Dev Tools Hub (`/ums_dev_tools`) | ✅ |
| Dev Bracket Tools (`/ums_dev_bracket_tools`) | ✅ |

---

## Dev Tools (Core v1.0.0)

### Dev Tools Hub (`/ums_dev_tools`)

Single entry point for all dev utilities:

| Button | Action |
|--------|--------|
| Bracket Tools | Opens Dev Bracket Tools panel |
| Add Dummy Entries | Fills tournament with dummy players |
| Auto-resolve All | Resolves all dummy vs dummy matches |
| Close | Closes the hub |

### Dev Bracket Tools (`/ums_dev_bracket_tools`)

Fine-grained bracket control:

| Button | Action |
|--------|--------|
| Advance One Match | Select dropdown → random winner |
| Advance Current Round | Resolves all matches in lowest round |
| Auto-resolve All | Resolves all dummy vs dummy matches |
| Close | Closes the panel |

---

## Future Extensions (Premium)

Premium edition will inherit these rules and extend with:

- `/ums_wipe_tournaments` — Clear all tournament data
- `/ums_rebuild_schema` — Force schema migration
- `/ums_clear_ratings` — Reset all Elo data
- "Player Tools" ephemeral panel
- "Organizer Tools" for non-admin tournament staff

All extensions follow the same category rules defined above.

---

_Last updated: 2024-12-06_
