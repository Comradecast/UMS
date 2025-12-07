<!--
  UMS Bot Core — README
  The canonical open-source home for UMS Bot Core
  Repo: https://github.com/Comradecast/UMS
-->

<div align="center">

  <img src="assets/branding/UMSBotCore.png" alt="UMS Bot Core Mascot" width="120" />

  # UMS Bot Core

  **Minimal. Stable. Production-Ready.**

  [![Version](https://img.shields.io/badge/version-v1.0.0--core-blue.svg)](https://github.com/Comradecast/UMS/releases)
  [![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
  [![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
  [![Discord.py](https://img.shields.io/badge/discord.py-2.0+-blueviolet.svg)](https://discordpy.readthedocs.io/)

  *A lean, predictable Discord bot for running Single Elimination tournaments.*

  [Getting Started](#-getting-started) •
  [Features](#-features) •
  [Commands](#-commands) •
  [Documentation](#-documentation) •
  [Roadmap](#-roadmap)

</div>

---

## 🎯 What Is UMS Bot Core?

**UMS Bot Core** is the minimal edition of the Unified Match System — designed to be boring, predictable, and hard to break.

Perfect for:
- **Small/medium Discord servers** that want clean tournament hosting
- **Community organizers** who need something that "just works"
- **Server owners** who want a stable base before adding premium features

> 💡 **One tournament per guild. Dashboard-driven. Zero clutter.**

---

## ⚡ Features

### For Players

| Feature | Description |
|---------|-------------|
| 🎮 **One-Click Onboarding** | Set region and rank in ~30 seconds |
| 📊 **Live Dashboard** | See current status and match info |
| 🏆 **Clean Brackets** | Single Elimination, no confusion |

### For Admins

| Feature | Description |
|---------|-------------|
| ⚙️ **Quick Setup** | Guided flow creates channels and config |
| 🧭 **Onboarding Flow** | Standardized entry path for players |
| 🔧 **Override Wizard** | Fix match results with ephemeral UI |
| 📢 **Announcement Wizard** | Templates for releases, patches, events |
| 🔄 **Factory Reset** | Clean wipe when you want a fresh start |

### For Developers

| Feature | Description |
|---------|-------------|
| 🧪 **Dev Tools Hub** | Tools for dummy brackets and fast iteration |
| 🎨 **Brand Kit** | Centralized colors, embeds, and footer |
| 📖 **Documentation** | Architecture, UX standards, specs |

---

## 🚀 Getting Started

### Prerequisites
- Python **3.11+**
- A Discord **Bot Token** ([create one here](https://discord.com/developers/applications))
- A Discord server where you have **Admin** permissions

### 1. Clone the Repository

```bash
git clone https://github.com/Comradecast/UMS.git
cd UMS/core-bot
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env and set:
# DISCORD_TOKEN=your_bot_token_here
```

### 5. Run the Bot

```bash
python bot.py
```

### 6. Invite the Bot

Use this invite link:

```
https://discord.com/oauth2/authorize?client_id=1446358626066501703&permissions=2147559440&integration_type=0&scope=bot+applications.commands
```

Recommended permissions:
- Manage Channels
- Manage Roles
- Send Messages
- Embed Links
- Read Message History
- Use Slash Commands

### 7. First-Time Setup

1. Run `/setup` in your server
2. Click **Quick Setup** to auto-create channels
3. You're ready to host tournaments! 🎉

---

## 📋 Commands

### Player Commands

| Command | Description |
|---------|-------------|
| `/onboard` | Set up your player profile |
| `/dashboard` | View your current tournament status |

### Admin Commands

| Command | Description |
|---------|-------------|
| `/setup` | Configure UMS Bot for your server |
| `/config` | View current configuration |
| `/ums-help` | Get help and command overview |
| `/post_onboarding_panel` | Post the onboarding panel to a channel |
| `/tournament_create` | Create a new Single Elimination tournament |
| `/tournament_open_registration` | Open registration |
| `/tournament_close_registration` | Close registration |
| `/tournament_start` | Generate bracket and start |
| `/ums_report_result` | Admin Override Wizard |
| `/ums_announce` | Announcement wizard with templates |
| `/admin_reset_player` | Reset a player's profile |
| `/ums_factory_reset` | Wipe all UMS data for this server |

### Dev Commands (Gated by `DEV_USER_IDS`)

| Command | Description |
|---------|-------------|
| `/ums_dev_tools` | Dev Tools Hub |
| `/ums_dev_bracket_tools` | Bracket manipulation tools |
| `/ums_dev_fill_dummies` | Add dummy entries for testing |
| `/ums_dev_auto_resolve` | Auto-resolve dummy matches |

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Architecture](ARCHITECTURE_NOW.md) | Current system architecture |
| [Admin UX Standard](ADMIN_UX_STANDARD.md) | UX rules and patterns |
| [Product Spec](CORE_PRODUCT_SPEC.md) | Feature specification |
| [Dev Tools Reference](DEV_TOOLS_REFERENCE.md) | Developer tool docs |
| [Release Notes](RELEASE_NOTES_v1.0.0.md) | v1.0.0-core changelog |
| [Privacy Policy](PRIVACY_POLICY.md) | Data handling policy |
| [Terms of Service](TERMS_OF_SERVICE.md) | Usage terms |

---

## 🗺️ Roadmap

### ✅ Core v1.0.0 (Current)
- Single Elimination tournaments
- Player onboarding and dashboard
- Admin setup flow and override tools
- Announcement wizard
- Dev tools hub for bracket simulation

### 🔜 UMS Premium (Future, Separate Project)

UMS Premium will be developed as separate closed-source or hosted services:

- Double Elimination brackets
- Swiss / Round Robin
- Solo Queue matchmaking
- Elo + leaderboards
- Recurring tournaments and seasons
- Web dashboard + analytics
- Clans, teams, and advanced flows

> Core will always remain **free**, **self-hostable**, and **minimal**. Premium extends, not replaces, Core.

---

## 🧪 Development

### Running Tests

```bash
python -m pytest tests/test_core.py -v
```

### Project Structure

```
UMS/
├── docs/                   # Documentation (at repo root)
├── core-bot/               # Bot code
│   ├── bot.py              # Entry point
│   ├── database.py         # Schema + migrations
│   ├── core_version.py     # Version constant
│   ├── constants.py        # Shared constants
│   ├── cogs/               # Discord command handlers
│   │   ├── server_setup.py
│   │   ├── onboarding_view.py
│   │   ├── tournaments.py
│   │   └── ...
│   ├── services/           # Business logic layer
│   ├── ui/                 # Views, embeds, brand kit
│   ├── tests/              # Test suite
│   ├── assets/             # Branding assets
│   └── requirements.txt    # Dependencies
├── README.md
├── LICENSE
└── CONTRIBUTING.md
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-change`
3. Make your changes
4. Run tests: `pytest`
5. Open a Pull Request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

---

## 🧾 License & Future Premium Features

UMS Bot Core is open source and released under the [MIT License](LICENSE).

Core will always remain:
- Free to use
- Self-hostable
- Minimal and stable

Future **UMS Premium** features (such as Solo Queue, Elo, advanced stats, clans, and automation) will be developed as separate, closed-source components and/or hosted services that build on top of Core.

---

<div align="center">

  **Built with ❤️ for competitive communities**

  [👉 Invite UMS Bot Core](https://discord.com/oauth2/authorize?client_id=1446358626066501703&permissions=2147559440&integration_type=0&scope=bot+applications.commands) •
  [🐙 GitHub](https://github.com/Comradecast/UMS) •
  [🐛 Report Bug](https://github.com/Comradecast/UMS/issues)

</div>
