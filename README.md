# UMS Bot Core

**Minimal. Stable. Production-Ready.**

A lean, predictable Discord bot for running Single Elimination tournaments.

---

## What is UMS Bot Core?

UMS Bot Core is the minimal edition of the Unified Match System — designed to be boring, predictable, and hard to break.

It focuses on **one thing**: clean Single Elimination tournament hosting for Discord servers. One tournament per guild. Dashboard-driven. Zero clutter.

Perfect for small/medium communities that want reliable tournament operations without complexity.

---

## Key Features

### For Players
- 🎮 One-click onboarding (region + rank)
- 📊 Live dashboard with match status
- 🏆 Clean Single Elimination brackets

### For Admins
- ⚙️ Quick Setup wizard
- 🔧 Match override tools
- 📢 Announcement templates
- 🔄 Factory reset

### For Developers
- 🧪 Dev Tools Hub for testing
- 🎨 Centralized brand kit
- 📖 Full documentation

---

## Quick Start

**Requirements:** Python 3.11+

```bash
git clone https://github.com/Comradecast/UMS.git
cd UMS/core-bot
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt

cp .env.example .env
# Edit .env → DISCORD_TOKEN=your_token_here

python bot.py
```

Then run `/setup` in your Discord server.

---

## Premium Integration (Optional)

UMS Core supports an optional connection to **UMS Premium Service** for advanced Solo Queue features.

### What Premium Adds
- ⚔️ Ranked Solo Queue with Elo-based matchmaking
- 📈 Per-mode ratings (1v1, 2v2, 3v3)
- 📊 Match history and rating tracking

### Setup

1. Start the Premium backend:
   ```bash
cd path/to/ums-premium-service
.\venv\Scripts\Activate.ps1      # Windows
# source venv/bin/activate       # Linux/Mac
uvicorn main:app --reload --port 8000
   ```

2. Add to your core-bot `.env`:
   ```
   PREMIUM_ENABLED=1
   PREMIUM_API_URL=http://localhost:8000
   PREMIUM_API_KEY=your-secret-key
   ```

3. Start core-bot — Premium will auto-load

4. Run `/premium_post_solo_panel` in Discord

### Premium Commands
| Command | Description |
|---------|-------------|
| `/premium_post_solo_panel` | Post Solo Queue panel (admin) |
| `/premium_matchmaking_tick` | Manual matchmaking (admin) |

---

## Documentation

👉 **[Full Documentation](docs/UMS_README.md)**

---

## License

MIT License — see [LICENSE](LICENSE)

---

<div align="center">

[Invite Bot](https://discord.com/oauth2/authorize?client_id=1446358626066501703&permissions=2147559440&integration_type=0&scope=bot+applications.commands) •
[Report Bug](https://github.com/Comradecast/UMS/issues)

</div>
