# SR Discord Bot

A stats-tracking bot for Discord games/events.

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Add your bot token to `.env`
3. Run: `python sr_bot.py`

## Commands
- `/sr [user]` to view stats
- `/sr_edit <user>` (admin) to edit stats
- `/add_role <user> <role>` (owner) to add roles
- `/admin` (admin) to open admin panel

## Features
- SQLite database for persistence
- Embed displays with stats and recent events
- Admin permissions for editing
- Interactive buttons and modals for management
