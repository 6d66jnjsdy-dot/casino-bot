import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="$",
    intents=intents
)

import nuke
nuke.setup(bot)


@bot.event
async def on_ready():
    print(f"Bot is online: {bot.user}")


token = os.getenv("DISCORD_TOKEN")

if not token:
    raise RuntimeError("DISCORD_TOKEN is missing")

bot.run(token)