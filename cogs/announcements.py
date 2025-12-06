"""
Server Announcements - Post major updates to announcement channel
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)


class AnnouncementsCog(commands.Cog):
    """Post bot updates and announcements."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="post_update")
    @app_commands.default_permissions(administrator=True)
    async def post_update(self, interaction: discord.Interaction):
        """Post the latest bot update announcement."""
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="🎮 Tournament Bot - Dashboard & Notifications Update",
            description="The bot has been fully upgraded to a **dashboard-first** experience. Here's what's new:",
            color=discord.Color.gold(),
        )

        # Feature 1: Unified Player Dashboard
        embed.add_field(
            name="📊 Unified Player Dashboard (/dashboard)",
            value=(
                "**Your personal control center is now live.**\n"
                "• Type `/dashboard` anywhere in the server\n"
                "• First time: quick setup for **region** and **starting rank**\n"
                "• See your rank, Elo, win/loss, and recent matches\n"
                "• Access queues, tournaments, teams, and clans from one place"
            ),
            inline=False,
        )

        # Feature 2: Next Match & Return to Match
        embed.add_field(
            name="🎯 Next Match & Quick Navigation",
            value=(
                "**Never lose track of your matches again.**\n"
                "• Dashboard now shows your **next scheduled match**\n"
                "• See opponent names, start time, and match channel\n"
                "• One-click **Return to Match** button jumps you back to your match channel"
            ),
            inline=False,
        )

        # Feature 3: Tournament Notifications
        embed.add_field(
            name="⏰ Tournament Reminders (DM Notifications)",
            value=(
                "**Get pinged before your tournaments start.**\n"
                "• Bot can DM you a reminder before tournaments\n"
                "• Dashboard shows your **upcoming registered tournaments**\n"
                "• No more missing start times or scrambling to find info"
            ),
            inline=False,
        )

        # Feature 4: Solo Queue & Elo (Dashboard-centric)
        embed.add_field(
            name="⚔️ Solo Queue & Elo Ranking",
            value=(
                "**Solo queue is now integrated into the dashboard.**\n"
                "• Use `/dashboard` → **Quick Queue** to find matches\n"
                "• Modes: **Ranked** (Elo) or **Casual** (no Elo impact)\n"
                "• Supports 1v1, 2v2, and 3v3 formats\n"
                "• Elo updates automatically after ranked matches\n"
                "• Public panel in <#1442337092394029066> is still available as an extra way to queue"
            ),
            inline=False,
        )

        # How to Get Started (simplified, dashboard-first)
        embed.add_field(
            name="🚀 How to Get Started Now",
            value=(
                "**Step 1:** Type `/dashboard`\n"
                "• Complete the quick setup (region + starting rank)\n\n"
                "**Step 2:** Use your dashboard buttons:\n"
                "• **Quick Queue** – Find a match\n"
                "• **Browse Tournaments** – Join events\n"
                "• **Profile / History** – Check your stats and recent matches"
            ),
            inline=False,
        )

        embed.add_field(
            name="💡 What This Means For You",
            value=(
                "✅ One command (`/dashboard`) to access everything\n"
                "✅ Proactive DMs for tournaments you care about\n"
                "✅ Clear view of your next match and opponent\n"
                "✅ Solo queue and Elo fully integrated into your profile\n"
                "✅ Less channel-hopping, more playing"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Questions? Ask in the tournament channel or type /dashboard to check your status."
        )

        await interaction.channel.send(embed=embed)
        await interaction.followup.send(
            "✅ Update announcement posted!", ephemeral=True
        )

    @app_commands.command(name="post_update_v1_4_1")
    @app_commands.default_permissions(administrator=True)
    async def post_update_v1_4_1(self, interaction: discord.Interaction):
        """Post the v1.4.1 (Phase 5 Complete) announcement."""
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="📢 Tournament Bot Update — v1.4.1 (Phase 5 Complete!)",
            description=(
                "Everything is now cleaner, faster, more stable, and fully aligned with the v3 schema.\n"
                "All tests green. All raw SQL finally contained.\n"
                "**This is our most stable release ever.**"
            ),
            color=discord.Color.green(),
        )

        # 1. Major Improvements
        embed.add_field(
            name="🔧 Major Improvements",
            value=(
                "**1. TournamentService Overhaul**\n"
                "All tournament database logic now lives in one place:\n"
                "• Create / Get / Update / Delete tournaments\n"
                "• Add / Remove participants\n"
                "• Fetch participants\n"
                "No more scattered raw SQL. Cleaner, safer, easier to maintain.\n\n"
                "**2. Registration System Cleanup**\n"
                "• RegistrationCog no longer touches the database directly\n"
                "• Uses TournamentService for all insertions, updates, and lookups\n"
                "• Fully test-compatible (dummy roles/channels for MockGuild)\n\n"
                "**3. Dynamic Test DB Support**\n"
                "• All tests now correctly use a separate SQLite database\n"
                "• DB_NAME is dynamically patched\n"
                "• No cross-contamination with production data\n"
                "• Zero flaky behavior\n"
                "• Schema fully validated during test run"
            ),
            inline=False,
        )

        # 2. Test Suite Status
        embed.add_field(
            name="🧪 Test Suite Status",
            value=(
                "• **19 tests passed**, 1 skipped (legacy)\n"
                "• **100% service-layer coverage** for tournaments\n"
                "• **Schema alignment test added** (prevents future drift!)\n"
                "• All SQL-usage tests green\n"
                "• Registration and tournament commands fully validated"
            ),
            inline=False,
        )

        # 3. Schema & Architecture Updates
        embed.add_field(
            name="🗂️ Schema & Architecture Updates",
            value=(
                "• `tournaments` table updated to the true v3 shape\n"
                "• All 24 columns documented in `SCHEMA_REFERENCE.md`\n"
                "• Participant table documented with clear ownership\n"
                "• `ARCHITECTURE_NOW.md` rewritten to reflect actual system\n"
                "• Cleanup roadmap updated through Phase 6+"
            ),
            inline=False,
        )

        # 4. Repository Cleanup
        embed.add_field(
            name="🧹 Repository Cleanup",
            value=(
                "• Removed leftover legacy paths\n"
                "• Pre-commit hooks cleaned whitespace and formatting\n"
                "• Black/ruff/isort run across new files\n"
                "• **New tools added:**\n"
                "  • `repo_tree.txt` — instant snapshot of repo structure\n"
                "  • `schema_audit.py` — script to validate DB schema drift"
            ),
            inline=False,
        )

        # 5. Why This Matters
        embed.add_field(
            name="🚀 Why This Matters",
            value=(
                "Phase 5 marks the moment the bot finally has:\n"
                "✅ A unified schema\n"
                "✅ A unified service layer\n"
                "✅ A consistent test environment\n"
                "✅ No hidden legacy codepaths secretly mutating the DB\n"
                "✅ A foundation stable enough for Phase 6 & feature expansion\n\n"
                "**Everything from here forward gets easier.**"
            ),
            inline=False,
        )

        embed.set_footer(text="v1.4.1-phase5-complete • 2025-11-30")

        await interaction.channel.send(embed=embed)
        log.info(
            "Posted v1.4.1 announcement in #%s (%s)",
            getattr(interaction.channel, "name", "?"),
            interaction.channel.id,
        )
        await interaction.followup.send(
            "✅ v1.4.1 announcement posted!", ephemeral=True
        )

    @app_commands.command(name="update_dashboard_matches")
    @app_commands.default_permissions(administrator=True)
    async def post_update_dashboard_and_matches(self, interaction: discord.Interaction):
        """Post the dashboard + Unified Match System progress update."""
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="📢 Tournament Bot Update — Dashboard Upgrade + Match System Preview",
            description=(
                "We've made major improvements to the bot's dashboard system, and we're starting a brand-new "
                "**Unified Match System** that will make match history, stats, and Elo more accurate than ever."
            ),
            color=discord.Color.gold(),
        )

        # Section 1 — Dashboard-Centric Upgrade
        embed.add_field(
            name="🎛️ Dashboard System Upgrade (Epic 5 Complete)",
            value=(
                "The admin dashboard has been fully rebuilt to be cleaner and more reliable:\n"
                "• Better tracking of dashboard panels\n"
                "• More accurate server configuration\n"
                "• Smarter health checks for admins\n"
                "• Fewer hidden settings — everything in one place\n\n"
                "**For players:** this means a more stable experience when using `/dashboard`, "
                "joining tournaments, or viewing your profile."
            ),
            inline=False,
        )

        # Section 2 — Unified Match System
        embed.add_field(
            name="⚔️ Coming Soon: Unified Match System (Epic 6)",
            value=(
                "We’re beginning a full upgrade to how matches are recorded.\n\n"
                "**What this means for you:**\n"
                "• Cleaner match history across Solo Queue *and* tournaments\n"
                "• More accurate Elo updates\n"
                "• Better stats tracking long-term\n"
                "• A foundation for new features like match confirmations and dispute tools\n\n"
                "This will roll out in small steps with no disruption for players."
            ),
            inline=False,
        )

        # Section 3 — What Players Should Expect
        embed.add_field(
            name="🚀 What to Expect Next",
            value=(
                "• No changes required from players right now\n"
                "• Solo Queue and tournaments work normally during upgrades\n"
                "• You may see improvements to your **match history**, **stats**, and **Elo accuracy** over time"
            ),
            inline=False,
        )

        # Footer
        embed.set_footer(text="Thanks for playing! More updates coming soon ❤️")

        await interaction.channel.send(embed=embed)
        await interaction.followup.send("✅ Announcement posted!", ephemeral=True)

    @app_commands.command(name="post_new_user_guide")
    @app_commands.default_permissions(administrator=True)
    async def post_new_user_guide(self, interaction: discord.Interaction):
        """Post a comprehensive guide for new users."""
        await interaction.response.defer(ephemeral=True)

        # Welcome Embed
        welcome_embed = discord.Embed(
            title="👋 Welcome to Competitive Rocket League Sideswipe!",
            description=(
                "This server uses a **Tournament Bot** to run competitive events and matchmaking.\n"
                "**Never used a system like this?** No worries – this guide will get you started in a few minutes."
            ),
            color=discord.Color.blue(),
        )

        welcome_embed.add_field(
            name="📋 What This Server Offers",
            value=(
                "🏆 **Tournaments** – Organized competitive events (1v1, 2v2, 3v3)\n"
                "⚔️ **Solo Queue** – Find ranked or casual matches anytime\n"
                "📊 **Elo Rankings** – Prove your skill with a competitive rating\n"
                "👥 **Teams & Clans** – Play with friends long-term\n"
                "🎯 **Fair Matchmaking** – Play against people at your skill level"
            ),
            inline=False,
        )

        # Quick Start Guide (Dashboard-first)
        start_embed = discord.Embed(
            title="🚀 Quick Start (2 Steps)",
            description="Get up and running in under 3 minutes:",
            color=discord.Color.green(),
        )

        start_embed.add_field(
            name="Step 1️⃣: Open Your Dashboard",
            value=(
                "Type **`/dashboard`** anywhere in the server.\n"
                "• First time: you'll be asked to set your **region** and **starting rank**\n"
                "• This helps create fair matches\n"
                "• Your dashboard is your **command center** for everything"
            ),
            inline=False,
        )

        start_embed.add_field(
            name="Step 2️⃣: Play – Queue or Join a Tournament",
            value=(
                "From your dashboard, use the buttons:\n\n"
                "• **⚡ Quick Queue** – Find a 1v1/2v2/3v3 match (Ranked or Casual)\n"
                "• **📋 Browse Tournaments** – See open events and register\n"
                "• **🎯 Return to Match** – Jump back into an active match channel\n\n"
            ),
            inline=False,
        )

        # How It Works
        how_embed = discord.Embed(
            title="❓ How Does This Work?",
            description="The bot handles almost everything automatically:",
            color=discord.Color.purple(),
        )

        how_embed.add_field(
            name="🎮 Playing Tournament Matches",
            value=(
                "1. Register for a tournament (via `/dashboard` → **Browse Tournaments**)\n"
                "2. When the event starts, the bot creates your **match channel**\n"
                "3. Meet your opponent in the match channel\n"
                "4. In RL Sideswipe: **Play → Private Match → Create/Join**\n"
                "5. Play your match (Bo1/Bo3/Bo5 depending on the rules)\n"
                "6. Both players report the score in the match channel\n"
                "7. The bot updates the bracket and sets up your next match"
            ),
            inline=False,
        )

        how_embed.add_field(
            name="⚔️ Playing Solo Queue Matches",
            value=(
                "1. Type `/dashboard` and click **Quick Queue**\n"
                "2. Choose **Ranked** (Elo) or **Casual** (no Elo)\n"
                "3. Select 1v1, 2v2, or 3v3\n"
                "4. Bot finds an opponent near your skill level\n"
                "5. A private match channel is created for you\n"
                "6. Play and report your result\n"
                "7. Your Elo updates automatically (Ranked only)\n\n"
                "There's also a public panel in <#1442337092394029066> as an alternative way to queue."
            ),
            inline=False,
        )

        how_embed.add_field(
            name="📊 Understanding Ranks & Elo",
            value=(
                "**Rank** (Bronze → Grand Champion): Your visible skill tier\n"
                "**Elo** (number): Your exact rating within that tier\n\n"
                "• First time you use `/dashboard`, you'll pick a starting rank\n"
                "• Win ranked matches → Elo goes up → rank can increase\n"
                "• You have separate Elo for **1v1**, **2v2**, and **3v3**\n"
                "• View your stats anytime in `/dashboard` on the **Profile** / **History** tabs"
            ),
            inline=False,
        )

        # Tips & FAQ
        tips_embed = discord.Embed(
            title="💡 Tips for New Players", color=discord.Color.gold()
        )

        tips_embed.add_field(
            name="🎯 Getting Started Tips",
            value=(
                "✅ Start with **Casual Quick Queue** to warm up\n"
                "✅ Be honest with your starting rank – it makes matches more fun\n"
                "✅ Check tournament rules and start times before registering\n"
                "✅ Be respectful in match channels\n"
                "✅ Report scores promptly after matches\n"
                "✅ Join a team or clan if you want consistent partners"
            ),
            inline=False,
        )

        tips_embed.add_field(
            name="❔ Common Questions",
            value=(
                "**Q: What's the difference between ranked and casual?**\n"
                "A: Ranked affects your Elo/rank, casual is just for practice.\n\n"
                "**Q: Do I need a team for 2v2/3v3 tournaments?**\n"
                "A: Usually yes – check the tournament description. Queue modes may form teams for you.\n\n"
                "**Q: What if my opponent doesn't show up?**\n"
                "A: Wait 10 minutes, then follow the instructions in your match channel.\n\n"
                "**Q: Can I change my rank?**\n"
                "A: Your rank updates as you play. If it's way off, ask an admin for help."
            ),
            inline=False,
        )

        # Where to Go / Channel Guide
        nav_embed = discord.Embed(
            title="🗺️ Channel Guide",
            description="Most things start from `/dashboard`, but these channels are also useful:",
            color=discord.Color.orange(),
        )

        nav_embed.add_field(
            name="Main Channels",
            value=(
                "`/dashboard` – Your personal hub (stats, matches, tournaments)\n"
                "<#1442337092394029066> – Public solo queue panel (optional, alternative to dashboard)\n"
                "<#1443367993466945621> – Bot updates & news\n"
                "<#1441851876428480714> – Extra profile/rank tools (if enabled)"
            ),
            inline=False,
        )

        nav_embed.add_field(
            name="Need Help?",
            value=(
                "• Ask questions in the main tournament or help channel\n"
                "• Ping a moderator if you're stuck\n"
                "• Type `/dashboard` to see your current status\n"
                "• Most importantly: **have fun!** 🎮"
            ),
            inline=False,
        )

        nav_embed.set_footer(
            text="Questions? Don't be shy – everyone was new once! Ask in chat anytime."
        )

        # Send all embeds
        await interaction.channel.send(
            embeds=[welcome_embed, start_embed, how_embed, tips_embed, nav_embed]
        )
        await interaction.followup.send("✅ New user guide posted!", ephemeral=True)

    @app_commands.command(name="post_update_ums_release")
    @app_commands.default_permissions(administrator=True)
    async def post_update_ums_release(self, interaction: discord.Interaction):
        """Post the Unified Match System (UMS) announcement."""
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="⚔️ Tournament Bot Update — Unified Match System Is Live!",
            description=(
                "A massive upgrade just landed: the bot now uses a **Unified Match System (UMS)** to record "
                "every match across **Solo Queue and Tournaments** in a single, consistent format.\n\n"
                "This unlocks accurate stats, clean dashboards, and a foundation for dispute tools, cross-event "
                "history, and season-based leaderboards.\n\n"
                "**This is one of the biggest backend improvements ever shipped.**"
            ),
            color=discord.Color.purple(),
        )

        # Section 1 — What UMS Does
        embed.add_field(
            name="📘 What Is the Unified Match System?",
            value=(
                "UMS replaces the old patchwork of match tables with:\n"
                "• `matches_unified` — one table for *every* match\n"
                "• `match_participants` — who played, on which team, and how they performed\n"
                "• Cross-mode support (1v1, 2v2, 3v3)\n"
                "• Clean references for both SoloQ and tournament matches\n\n"
                "This ensures all stats come from one clean, stable source."
            ),
            inline=False,
        )

        # Section 2 — Player-Facing Improvements
        embed.add_field(
            name="👤 What This Changes for Players",
            value=(
                "• `/dashboard` → Profile now shows **accurate lifetime record**\n"
                "• Recent matches now include **SoloQ + Tournament** results\n"
                "• Elo updates happen more reliably\n"
                "• Stats roll up cleanly (W/L, last 5, streaks)\n"
                "• Duplicate or missing matches from the old system are gone\n\n"
                "**If you play games, they now show up correctly. Every time.**"
            ),
            inline=False,
        )

        # Section 3 — Admin-Level Improvements
        embed.add_field(
            name="🛠️ What This Changes for Admins",
            value=(
                "• Cleaner database structure (v3-aligned)\n"
                "• No duplicate match logic across systems\n"
                "• No raw SQL mixed across cogs\n"
                "• New tools for debugging UMS entries (`/dev_ums_*`)\n"
                "• Future-proof for match confirmations, appeals, & season resets"
            ),
            inline=False,
        )

        # Section 4 — New Developer Tools
        embed.add_field(
            name="🧪 Developer Tools Added",
            value=(
                "• **`/dev_soloq_self_match`** — create a self-match to test UMS flow\n"
                "• **`/dev_ums_sanity`** — verify UMS row counts\n"
                "• **`/dev_ums_clear`** — wipe UMS tables for clean testing\n"
                "• Backend: migrations 003–007 now enforce clean UMS schema\n"
            ),
            inline=False,
        )

        # Section 5 — What’s Next
        embed.add_field(
            name="🚀 What’s Coming Next",
            value=(
                "UMS enables several Phase 6+ features:\n"
                "• Match confirmations (both players must agree)\n"
                "• Score disputes & admin resolution tools\n"
                "• Season-based rankings and resets\n"
                "• True unified cross-event player history\n"
                "• Automatic team stats & clan stats\n"
                "• Public leaderboards built on UMS data\n\n"
                "**This is the new backbone of the bot.**"
            ),
            inline=False,
        )

        embed.set_footer(text="Unified Match System • Release Build 2025-12-03")

        await interaction.channel.send(embed=embed)
        await interaction.followup.send(
            "✅ UMS release announcement posted!", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AnnouncementsCog(bot))
