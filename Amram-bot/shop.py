import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= SHOP =================
SHOP_TITLE = "Amram Casino Shop"
SHOP_COLOR = 0xDDC9A3
SHOP_THUMBNAIL = None

SHOP_ITEMS = [
    ("Casino Joker",   "🃏", 1554242301927104643, 175_000_000),
    ("Casino Master",  "💎", 1554242805071876116, 225_000_000),
    ("Casino Dealer",  "🤵", 1554241846165766225, 350_000_000),
    ("Casino Legend",  "🗽", 1554239763006099487, 425_000_000),
    ("Casino Royalty", "🌟", 1554240949213724854, 500_000_000),
    ("Casino Emperor", "👑", 1554242535369482371, 675_000_000),
]

async def shop_say(interaction, text):
    await interaction.response.send_message(text, ephemeral=True)

SHOP_BUSY = set()

async def shop_buy(interaction, item):
    name, emoji, role_id, price = item
    member = interaction.user
    if interaction.guild is None or not isinstance(member, discord.Member):
        return await shop_say(interaction, "This only works inside the server.")
    if loaded is None or not loaded.is_set():
        return await shop_say(interaction, "The bot is still starting, try again in a few seconds.")
    role = interaction.guild.get_role(role_id)
    if role is None:
        return await shop_say(interaction, "This role doesn't exist anymore, tell an admin.")
    if role in member.roles:
        return await shop_say(interaction, f"You already have **{name}**.")
    key = (member.id, role_id)
    if key in SHOP_BUSY:
        return await shop_say(interaction, "Your purchase is already being processed.")
    u = user_data(member.id)
    if u["bank"] < price:
        return await shop_say(
            interaction,
            f"You need **{fmt(price)}** {cur()} **in your bank** for {role.mention}.\n"
            f"You have {fmt(u['bank'])} {cur()} in the bank. (`$dep` to deposit)")
    SHOP_BUSY.add(key)
    u["bank"] -= price
    save()
    try:
        await member.add_roles(role, reason="Casino shop")
    except Exception as ex:
        u["bank"] += price
        save()
        print("Shop: add_roles failed:", repr(ex))
        return await shop_say(interaction, "I couldn't give you the role (my role must be above it). You were not charged.")
    finally:
        SHOP_BUSY.discard(key)
    log_money(member, "SHOP", f"Bought {name} for {fmt(price)} {cur()}", YELLOW)
    await shop_say(interaction, f"✅ You bought {role.mention} for **{fmt(price)}** {cur()} (from your bank).")

class ShopButton(discord.ui.Button):
    def __init__(self, item, row):
        super().__init__(style=discord.ButtonStyle.secondary, label=item[0], emoji=item[1],
                         custom_id=f"shop:{item[2]}", row=row)
        self.item = item

    async def callback(self, interaction):
        await shop_buy(interaction, self.item)

class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i, item in enumerate(SHOP_ITEMS):
            self.add_item(ShopButton(item, i // 2))

@bot.command(name="shop", usage="shop")
async def shop(ctx):
    try:
        lines = [f"<@&{rid}> - {fmt(price)} {cur()}" for _, _, rid, price in SHOP_ITEMS]
        e = discord.Embed(description="\n".join(lines), color=SHOP_COLOR)
        icon = ctx.guild.icon.url if ctx.guild and ctx.guild.icon else None
        e.set_author(name=SHOP_TITLE, icon_url=icon)
        thumb = SHOP_THUMBNAIL or icon
        if thumb:
            e.set_thumbnail(url=thumb)
        await ctx.send(embed=e, view=ShopView())
    except Exception as ex:
        await ctx.send(f"Shop error: `{type(ex).__name__}: {ex}`"[:1900])
