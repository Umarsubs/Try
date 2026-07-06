import os
import datetime
from threading import Thread
from flask import Flask
import discord
from discord.ext import commands

# ==========================================
# 1. FLASK WEB SERVER (For Render Free Tier)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is online and monitoring security!"

def run_server():
    # Render maps internal traffic to port 8080 by default
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_server)
    t.start()

# ==========================================
# 2. DISCORD BOT & ANTI-SPAM LOGIC
# ==========================================
intents = discord.Intents.default()
intents.message_content = True  # Required to read message contents
intents.members = True          # Required to manage/kick members

bot = commands.Bot(command_prefix="!", intents=intents)

# Security Configuration
SPAM_WINDOW_SECONDS = 10
MAX_MENTIONS_ALLOWED = 2

# Tracks user mention history: {user_id: [timestamp1, timestamp2, ...]}
user_mention_tracker = {}

@bot.event
async def on_ready():
    print(f"Logged in successfully as {bot.user.name} ({bot.user.id})")

@bot.event
async def on_message(message):
    # Ignore bots and webhooks to prevent loops
    if message.author.bot or message.webhook_id:
        return

    # Check if the message contains @everyone or @here
    if message.mention_everyone:
        user_id = message.author.id
        now = datetime.datetime.utcnow()

        if user_id not in user_mention_tracker:
            user_mention_tracker[user_id] = []

        # Record current mention and clean up timestamps older than the window
        user_mention_tracker[user_id].append(now)
        user_mention_tracker[user_id] = [
            t for t in user_mention_tracker[user_id] 
            if (now - t).total_seconds() < SPAM_WINDOW_SECONDS
        ]

        # Trigger security action if threshold is breached
        if len(user_mention_tracker[user_id]) > MAX_MENTIONS_ALLOWED:
            await quarantine_compromised_user(message.guild, message.author, message.channel)

    await bot.process_commands(message)

async def quarantine_compromised_user(guild, member, channel):
    try:
        # Strip all roles instantly to remove "Send Messages" permission
        await member.edit(roles=[], reason="Token compromise / @everyone spam wave detected")
        
        # Public confirmation alert
        await channel.send(
            f"⚠️ **Security Action**: {member.mention} has been instantly stripped of all roles "
            f"due to suspected token-compromise spam patterns."
        )
        
        # Clean tracker history for this user
        if member.id in user_mention_tracker:
            del user_mention_tracker[member.id]
            
    except discord.Forbidden:
        await channel.send(
            f"❌ **Security Failure**: I lack permission to moderate {member.name}. "
            f"Ensure my bot role is dragged above their roles in Server Settings."
        )
    except Exception as e:
        print(f"Error handling mitigation: {e}")

# ==========================================
# 3. EXECUTION
# ==========================================
if __name__ == "__main__":
    # Start the web server thread first
    keep_alive()
    
    # Start the Discord bot using the token stored in Render's environment variables
    token = os.environ.get('DISCORD_TOKEN')
    if token:
        bot.run(token)
    else:
        print("CRITICAL ERROR: 'DISCORD_TOKEN' environment variable is missing!")
