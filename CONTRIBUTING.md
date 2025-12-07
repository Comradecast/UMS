# Contributing to UMS Bot Core

Thanks for your interest in contributing! UMS Bot Core is intentionally minimal and stable — contributions that preserve that philosophy are welcome.

## Project Layout

```
UMS/
├── docs/               # Documentation (at repo root)
├── core-bot/
│   ├── bot.py          # Entry point
│   ├── cogs/           # Feature modules (commands)
│   ├── services/       # Business logic layer
│   ├── ui/             # Views, embeds, dashboards
│   └── tests/          # Test suite
└── README.md, LICENSE, etc.
```

## Getting Started

1. **Fork & Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/UMS.git
   cd UMS/core-bot
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Linux/Mac
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   # Add your DISCORD_TOKEN
   ```

5. **Run the Bot**
   ```bash
   python bot.py
   ```

## Running Tests

```bash
pytest
# or
python -m pytest tests/ -v
```

## Coding Guidelines

- **Keep it minimal** — Less is more. Don't add complexity.
- **Be explicit** — Prefer clarity over cleverness.
- **Follow existing style** — Type hints, logging patterns, etc.
- **Test your changes** — Add tests for new functionality.
- **Update docs** — If behavior changes, update documentation.

## How to Submit Changes

1. **Open an issue first** for significant changes
2. **Create a feature branch**: `git checkout -b feature/my-change`
3. **Make focused commits** with clear messages
4. **Run tests** before submitting
5. **Open a Pull Request** with a clear description

## Philosophy

UMS Bot Core prioritizes **stability over features**. Big ideas (Solo Queue, Elo, clans, etc.) are planned for UMS Premium, not Core.

Keep contributions focused on:
- Bug fixes
- Documentation improvements
- Performance optimizations
- Code clarity

Thank you for helping keep UMS Bot Core stable and reliable!
