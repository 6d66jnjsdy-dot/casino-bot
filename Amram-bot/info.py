import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= INFO =================
INFO_COLOR = 0x1F2A44

SECTION_ICONS = {
    "BOARD GAMES": "🎯", "CARDS AND LUCK": "🃏", "ROULETTE": "🎡", "SCRATCH CARDS": "🎟️", "TEAM GAME": "🏦", "ECONOMY": "💰",
    "STAFF": "🛡️", "ADMIN": "⚙️", "OWNER": "👑", "BANG COMMANDS": "❗",
}

def info_embed(user, title, description, sections, footer=None):
    """One tidy message: every command on its own line (command in code, description after it),
    so nothing gets cut or wrapped badly on mobile like the old wide code blocks did."""
    e = discord.Embed(title=title, description=description, color=INFO_COLOR)
    e.set_author(name=user.name, icon_url=user.display_avatar.url)
    for name, rows in sections:
        body = "\n".join(f"`{cmd}`\n⠀└ {desc}" if len(cmd) + len(desc) > 38 else f"`{cmd}` ┃ {desc}" for cmd, desc in rows)
        e.add_field(name=f"{SECTION_ICONS.get(name, '▪️')}  {name.title()}", value=body, inline=False)
    if footer:
        e.set_footer(text=footer)
    return e

INFO_SECTIONS = [
    ("BOARD GAMES", [
        ("$gm <bet>", "Find treasure, avoid bombs, cash out any time"),
        ("$mines <bet>", "One bomb, every diamond raises the profit"),
        ("S$mines <bet>", "Mines with a choice of board size"),
        ("$mt <bet>", "Money Tower, climb row by row"),
    ]),
    ("CARDS AND LUCK", [
        ("$bj <bet>", "Blackjack"),
        ("$slots <bet>", "Slot machine"),
        ("$hl <bet>", "Higher or lower"),
        ("$ht <bet>", "Heads or tail"),
        ("$cf <bet>", "Chicken fight"),
    ]),
    ("ROULETTE", [
        ("$roulette <amount> <bet>", "Join the open round, any number of bets"),
        ("Example", "$roulette 500 red   /   $roulette 150 0,6,odd"),
        ("Picks", "0-36, red, black, even, odd, 1-18, 19-36, 1-12, 13-24, 25-36, 1st, 2nd, 3rd"),
    ]),
    ("SCRATCH CARDS", [
        ("$sc", "Pick a card, enter an amount (bank only) and scratch"),
    ]),
    ("TEAM GAME", [
        ("$heist [2-5]", "Bank heist (2.5M entry per player), 2 to 5 players, one heist per day per creator"),
    ]),
    ("ECONOMY", [
        ("$bal [user]", "Cash and bank balance"),
        ("$dep / $with", "Deposit to or withdraw from the bank"),
        ("$work / $crime", "Quick earnings"),
        ("$rob <user>", "Rob another player's cash"),
        ("$pay <user> <amt>", "Send money to another player"),
        ("$top / $lb", "Leaderboard"),
        ("$shop", "Role shop"),
    ]),
]
INFO_FOOTER = "Amounts: number, half, all, 5k, 2.5m, 1b  |  <user> can be a mention, a user ID, or a reply with ping ON and the word 'a'"

AINFO_SECTIONS = [
    ("STAFF", [
        ("$addmoney <bank|cash> <user> <amt>", "Add money to a player"),
        ("$addmoneyrole <bank|cash> <role> <amt>", "Add money to every member of a role"),
        ("$resetmoney <bank|cash|all> <user> [amt]", "Set or reset a player's money"),
        ("$removemoney <bank|cash> <user> <amt>", "Remove money from a player"),
        ("$set-currency <emoji>", "Change the currency symbol"),
        ("$setimmunity <role|off>", "Members of this role cannot be robbed"),
        ("$immunity <user> <time|nolimit>", "Make a player immune from robbery"),
        ("$rimmunity <user>", "Remove a player's immunity"),
    ]),
    ("ADMIN", [
        ("$staff-role <role>", "Set which role counts as staff"),
        ("$setgamelogs <channel>", "Set the log channel"),
    ]),
    ("OWNER", [
        ("$setaddmoney <max|off>", "Limit how much staff can add per command"),
        ("$multi <game|all> <1-5|off> [time]", "Profit multiplier on wins"),
        ("$luck <1-10>x [time]", "Luck for every player"),
        ("$unluck", "Turn luck off"),
        ("$setlimit <number>", "Daily limit of add-money uses per staff member"),
        ("$unsetlimit", "Remove the daily limit"),
        ("$sc restart", "Restock all scratch cards (they also restock every day at 00:00)"),
        ("$reset-economy", "Reset everyone's money (asks for confirmation)"),
        ("$disable / $undisable <cmd|all>", "Block or unblock a command"),
        ("$lottery [draw|cancel]", "Open the weekly lottery (works only in the lottery room, ends Saturday 00:00)"),
    ]),
    ("BANG COMMANDS", [
        ("!set-role-member", "Role button panel (admin)"),
        ("!clear <amount>", "Delete up to 350 messages (clear role only)"),
    ]),
]

@bot.command(name="info")
async def info(ctx):
    await ctx.reply(embed=info_embed(ctx.author, "AMRAM CASINO  |  COMMAND GUIDE",
                                     "All commands start with `$`.", INFO_SECTIONS, INFO_FOOTER),
                    mention_author=False)

@bot.command(name="ainfo")
@staff_only
async def ainfo(ctx):
    await ctx.reply(embed=info_embed(ctx.author, "AMRAM CASINO  |  STAFF GUIDE",
                                     "Management commands.", AINFO_SECTIONS), mention_author=False)
