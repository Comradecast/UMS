# Dev Tools Reference (Core v1.0.0)

> **Warning:** These tools are for development/testing only. They can break tournament state and are strictly gated by `DEV_USER_IDS`.

---

## Commands

### `/ums_dev_tools`
**Dev Tools Hub** — Central panel for all dev utilities.

| Button | Action |
|--------|--------|
| Bracket Tools | Opens Dev Bracket Tools panel |
| Add Dummy Entries | Fills tournament with dummy players |
| Auto-resolve All | Resolves all dummy vs dummy matches |
| Close | Closes the hub |

---

### `/ums_dev_bracket_tools`
**Dev Bracket Tools** — Fine-grained bracket control.

| Button | Action |
|--------|--------|
| Advance One Match | Select dropdown → random winner |
| Advance Current Round | Resolves all matches in lowest round |
| Auto-resolve All | Resolves all dummy vs dummy matches |
| Close | Closes the panel |

---

### `/ums_dev_fill_dummies`
**Fill Tournament with Dummy Entries** — Standalone command.

| Parameter | Description |
|-----------|-------------|
| `tournament` | Optional tournament code or ID |
| `count` | Optional number of entries (default: fill remaining) |

---

### `/ums_dev_auto_resolve`
**Auto-Resolve Dummy Matches** — Standalone command.

| Parameter | Description |
|-----------|-------------|
| `tournament` | Optional tournament code or ID |

---

## Access Control

All dev commands check:
```python
if not is_dev_user(interaction.user):
    # Ephemeral error: "This command is for development use only."
```

`DEV_USER_IDS` is defined in environment/config and should contain only developer Discord user IDs.

---

## Logging

Dev actions log with `[DEV]` prefix:
```
[DEV] User 123456789 opened Dev Tools Hub in guild 987654321
[DEV] Added 32 dummy entries to tournament 5 (code=ABC12345)
[DEV] Auto-resolved 15 matches in tournament 5 (code=ABC12345)
[DEV] Manually advanced match 42 in tournament 5
```

---

## Safety Notes

1. **Not for production servers** — Only use for testing
2. **Can corrupt state** — Auto-resolve and dummy entries bypass normal validation
3. **Keep gated** — Never add admin/organizer IDs to `DEV_USER_IDS`
4. **Build-time removal** — Consider stripping from production builds

---

_See also: [ADMIN_UX_STANDARD.md](./ADMIN_UX_STANDARD.md), [ARCHITECTURE_NOW.md](./ARCHITECTURE_NOW.md)_
