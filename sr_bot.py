import discord
from discord.ext import commands
import sqlite3
import os
from dotenv import load_dotenv
import json

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Hard-coded super owner (replace with your Discord ID)
SUPER_OWNER_ID = 'your_discord_id_here'  # e.g., '123456789012345678'

# Database setup
def setup_db():
    conn = sqlite3.connect('sr_stats.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    discord_id TEXT UNIQUE,
                    username TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
                    user_id INTEGER PRIMARY KEY,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    draws INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0.0,
                    optional_counters TEXT DEFAULT '{}',
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    event_name TEXT,
                    result TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS roles (
                    user_id INTEGER PRIMARY KEY,
                    role TEXT DEFAULT 'user',
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )''')
    conn.commit()
    conn.close()

def get_user_id(discord_id, username):
    conn = sqlite3.connect('sr_stats.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (discord_id, username) VALUES (?, ?)', (discord_id, username))
    c.execute('SELECT id FROM users WHERE discord_id = ?', (discord_id,))
    user_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return user_id

def get_role(user_id):
    conn = sqlite3.connect('sr_stats.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO roles (user_id, role) VALUES (?, ?)', (user_id, 'user'))
    c.execute('SELECT role FROM roles WHERE user_id = ?', (user_id,))
    role = c.fetchone()[0]
    conn.commit()
    conn.close()
    return role

def set_role(user_id, role):
    conn = sqlite3.connect('sr_stats.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO roles (user_id, role) VALUES (?, ?)', (user_id, role))
    conn.commit()
    conn.close()

def update_stats(user_id):
    conn = sqlite3.connect('sr_stats.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM events WHERE user_id = ? AND result = "win"', (user_id,))
    wins = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM events WHERE user_id = ? AND result = "loss"', (user_id,))
    losses = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM events WHERE user_id = ? AND result = "draw"', (user_id,))
    draws = c.fetchone()[0]
    total = wins + losses + draws
    win_rate = (wins / total * 100) if total > 0 else 0.0
    c.execute('UPDATE stats SET wins = ?, losses = ?, draws = ?, win_rate = ? WHERE user_id = ?',
              (wins, losses, draws, win_rate, user_id))
    conn.commit()
    conn.close()

def add_event(user_id, event_name, result):
    conn = sqlite3.connect('sr_stats.db')
    c = conn.cursor()
    c.execute('INSERT INTO events (user_id, event_name, result) VALUES (?, ?, ?)', (user_id, event_name, result))
    c.execute('INSERT OR IGNORE INTO stats (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()
    update_stats(user_id)

def delete_event(event_id):
    conn = sqlite3.connect('sr_stats.db')
    c = conn.cursor()
    c.execute('DELETE FROM events WHERE id = ?', (event_id,))
    conn.commit()
    conn.close()

def update_counters(user_id, counters):
    conn = sqlite3.connect('sr_stats.db')
    c = conn.cursor()
    c.execute('UPDATE stats SET optional_counters = ? WHERE user_id = ?', (json.dumps(counters), user_id))
    conn.commit()
    conn.close()

def get_stats(user_id):
    conn = sqlite3.connect('sr_stats.db')
    c = conn.cursor()
    c.execute('SELECT wins, losses, draws, win_rate, optional_counters FROM stats WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    wins, losses, draws, win_rate, counters = row
    c.execute('SELECT id, event_name, result FROM events WHERE user_id = ? ORDER BY timestamp DESC LIMIT 5', (user_id,))
    events = c.fetchall()
    conn.close()
    return wins, losses, draws, win_rate, json.loads(counters), events

def is_admin(ctx):
    user_id = get_user_id(str(ctx.author.id), ctx.author.name)
    role = get_role(user_id)
    return role in ['admin', 'owner'] or str(ctx.author.id) == SUPER_OWNER_ID

def is_owner(ctx):
    user_id = get_user_id(str(ctx.author.id), ctx.author.name)
    role = get_role(user_id)
    return role == 'owner' or str(ctx.author.id) == SUPER_OWNER_ID

# Bot setup
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    setup_db()
    print(f'Logged in as {bot.user}')

@bot.slash_command(name='sr', description='View stats for a user')
async def sr(ctx, user: discord.Member = None):
    if user is None:
        user = ctx.author
    user_id = get_user_id(str(user.id), user.name)
    stats = get_stats(user_id)
    if not stats:
        embed = discord.Embed(title='No Stats', description=f'{user.mention} has no recorded stats.', color=0x000000)
    else:
        wins, losses, draws, win_rate, counters, events = stats
        played = wins + losses + draws
        embed = discord.Embed(title=f'{user.name}\'s Event Stats', color=0x0099ff)
        embed.add_field(name='Played', value=played, inline=True)
        embed.add_field(name='Wins', value=wins, inline=True)
        embed.add_field(name='Losses', value=losses, inline=True)
        embed.add_field(name='Draws', value=draws, inline=True)
        embed.add_field(name='Win Rate', value=f'{win_rate:.1f}%', inline=True)
        if counters:
            for key, value in counters.items():
                embed.add_field(name=key, value=value, inline=True)
        recent = '\n'.join([f'• {event[1]} — {event[2].capitalize()}' for event in events])
        embed.add_field(name='Recent Events', value=recent if recent else 'None', inline=False)
    await ctx.respond(embed=embed)

@bot.slash_command(name='sr_edit', description='Edit stats for a user (admin only)')
async def sr_edit(ctx, user: discord.Member):
    if not is_admin(ctx):
        await ctx.respond(embed=discord.Embed(title='Error', description='You need admin permissions.', color=0xff0000))
        return
    user_id = get_user_id(str(user.id), user.name)
    stats = get_stats(user_id)
    if not stats:
        await ctx.respond(embed=discord.Embed(title='No Stats', description=f'{user.mention} has no stats to edit.', color=0xff0000))
        return
    wins, losses, draws, win_rate, counters, events = stats
    embed = discord.Embed(title=f'Editing {user.name}\'s Stats', description='Use buttons to edit.', color=0x00ff00)
    embed.add_field(name='Wins', value=wins, inline=True)
    embed.add_field(name='Losses', value=losses, inline=True)
    embed.add_field(name='Draws', value=draws, inline=True)
    embed.add_field(name='Counters', value=json.dumps(counters), inline=False)
    view = EditStatsView(user_id, embed)
    await ctx.respond(embed=embed, view=view)

@bot.slash_command(name='add_role', description='Add admin or owner role to a user (owner/super only)')
async def add_role(ctx, user: discord.Member, role: str):
    if not is_owner(ctx):
        await ctx.respond(embed=discord.Embed(title='Error', description='You need owner permissions.', color=0xff0000))
        return
    if role not in ['admin', 'owner']:
        await ctx.respond(embed=discord.Embed(title='Error', description='Role must be admin or owner.', color=0xff0000))
        return
    user_id = get_user_id(str(user.id), user.name)
    set_role(user_id, role)
    await ctx.respond(embed=discord.Embed(title='Role Added', description=f'{user.mention} is now {role}.', color=0x00ff00))

@bot.slash_command(name='admin', description='Open admin panel (admin only)')
async def admin(ctx):
    if not is_admin(ctx):
        await ctx.respond(embed=discord.Embed(title='Error', description='You need admin permissions.', color=0xff0000))
        return
    embed = discord.Embed(title='Admin Panel', description='Select an action.', color=0x0099ff)
    view = AdminPanelView()
    await ctx.respond(embed=embed, view=view)

# Views for buttons and selects
class EditStatsView(discord.ui.View):
    def __init__(self, user_id, embed):
        super().__init__()
        self.user_id = user_id
        self.embed = embed

    @discord.ui.button(label='Add Event', style=discord.ButtonStyle.primary)
    async def add_event_button(self, interaction, button):
        await interaction.response.send_modal(AddEventModal(self.user_id))

    @discord.ui.button(label='Delete Event', style=discord.ButtonStyle.danger)
    async def delete_event_button(self, interaction, button):
        events = get_stats(self.user_id)[5]
        if not events:
            await interaction.response.send_message('No events to delete.', ephemeral=True)
            return
        options = [discord.SelectOption(label=f'{e[1]} — {e[2]}', value=str(e[0])) for e in events]
        select = DeleteEventSelect(options, self.user_id)
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message('Select event to delete:', view=view, ephemeral=True)

    @discord.ui.button(label='Edit Counters', style=discord.ButtonStyle.secondary)
    async def edit_counters_button(self, interaction, button):
        await interaction.response.send_modal(EditCountersModal(self.user_id))

class AddEventModal(discord.ui.Modal):
    def __init__(self, user_id):
        super().__init__(title='Add Event')
        self.user_id = user_id
        self.event_name = discord.ui.TextInput(label='Event Name')
        self.result = discord.ui.TextInput(label='Result (win/loss/draw)')
        self.add_item(self.event_name)
        self.add_item(self.result)

    async def on_submit(self, interaction):
        if self.result.value.lower() not in ['win', 'loss', 'draw']:
            await interaction.response.send_message('Invalid result.', ephemeral=True)
            return
        add_event(self.user_id, self.event_name.value, self.result.value.lower())
        await interaction.response.send_message('Event added.', ephemeral=True)

class DeleteEventSelect(discord.ui.Select):
    def __init__(self, options, user_id):
        super().__init__(placeholder='Select event', options=options)
        self.user_id = user_id

    async def callback(self, interaction):
        delete_event(int(self.values[0]))
        update_stats(self.user_id)
        await interaction.response.send_message('Event deleted.', ephemeral=True)

class EditCountersModal(discord.ui.Modal):
    def __init__(self, user_id):
        super().__init__(title='Edit Counters')
        self.user_id = user_id
        self.counters = discord.ui.TextInput(label='Counters (JSON, e.g. {"Aquila Bearer": 3})')
        self.add_item(self.counters)

    async def on_submit(self, interaction):
        try:
            counters = json.loads(self.counters.value)
            update_counters(self.user_id, counters)
            await interaction.response.send_message('Counters updated.', ephemeral=True)
        except json.JSONDecodeError:
            await interaction.response.send_message('Invalid JSON.', ephemeral=True)

class AdminPanelView(discord.ui.View):
    @discord.ui.button(label='Add Result', style=discord.ButtonStyle.primary)
    async def add_result_button(self, interaction, button):
        await interaction.response.send_modal(AdminAddResultModal())

    @discord.ui.button(label='View All Users', style=discord.ButtonStyle.secondary)
    async def view_users_button(self, interaction, button):
        conn = sqlite3.connect('sr_stats.db')
        c = conn.cursor()
        c.execute('SELECT username FROM users')
        users = [row[0] for row in c.fetchall()]
        conn.close()
        embed = discord.Embed(title='All Users', description='\n'.join(users), color=0x0099ff)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='Reset Stats', style=discord.ButtonStyle.danger)
    async def reset_stats_button(self, interaction, button):
        await interaction.response.send_modal(ResetStatsModal())

class AdminAddResultModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title='Add Result')
        self.user_id = discord.ui.TextInput(label='User ID')
        self.event_name = discord.ui.TextInput(label='Event Name')
        self.result = discord.ui.TextInput(label='Result (win/loss/draw)')
        self.add_item(self.user_id)
        self.add_item(self.event_name)
        self.add_item(self.result)

    async def on_submit(self, interaction):
        try:
            user_id = int(self.user_id.value)
            if self.result.value.lower() not in ['win', 'loss', 'draw']:
                await interaction.response.send_message('Invalid result.', ephemeral=True)
                return
            add_event(user_id, self.event_name.value, self.result.value.lower())
            await interaction.response.send_message('Result added.', ephemeral=True)
        except ValueError:
            await interaction.response.send_message('Invalid user ID.', ephemeral=True)

class ResetStatsModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title='Reset Stats')
        self.user_id = discord.ui.TextInput(label='User ID to Reset')
        self.add_item(self.user_id)

    async def on_submit(self, interaction):
        try:
            user_id = int(self.user_id.value)
            conn = sqlite3.connect('sr_stats.db')
            c = conn.cursor()
            c.execute('DELETE FROM events WHERE user_id = ?', (user_id,))
            c.execute('UPDATE stats SET wins=0, losses=0, draws=0, win_rate=0.0, optional_counters="{}" WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            await interaction.response.send_message('Stats reset.', ephemeral=True)
        except ValueError:
            await interaction.response.send_message('Invalid user ID.', ephemeral=True)

bot.run(TOKEN)