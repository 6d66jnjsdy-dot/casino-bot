import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= ROULETTE =================
ROUL_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
ROUL_WAIT = 30
ROUL_COLOR = 0x9B8CD6
ROUL_USAGE = "roulette <amount | half | all> <bet: 0-36, red, black, even, odd, 1-12...>"
ROUL_JOIN = "roulette <amount> <bet>"

def roul_color(n):
    return "green" if n == 0 else "red" if n in ROUL_RED else "black"

def parse_roul_pick(text):
    if not text:
        return None
    t = text.lower().strip().replace(" ", "").replace("–", "-").replace("־", "-")
    red = ("Red", lambda n: n in ROUL_RED, 2)
    black = ("Black", lambda n: n != 0 and n not in ROUL_RED, 2)
    even = ("Even", lambda n: n != 0 and n % 2 == 0, 2)
    odd = ("Odd", lambda n: n % 2 == 1, 2)
    d1 = ("1-12", lambda n: 1 <= n <= 12, 3)
    d2 = ("13-24", lambda n: 13 <= n <= 24, 3)
    d3 = ("25-36", lambda n: 25 <= n <= 36, 3)
    h1 = ("1-18", lambda n: 1 <= n <= 18, 2)
    h2 = ("19-36", lambda n: 19 <= n <= 36, 2)
    c1 = ("1st", lambda n: n != 0 and n % 3 == 1, 3)
    c2 = ("2nd", lambda n: n != 0 and n % 3 == 2, 3)
    c3 = ("3rd", lambda n: n != 0 and n % 3 == 0, 3)
    names = {
        "red": red, "r": red, "אדום": red,
        "black": black, "b": black, "שחור": black,
        "even": even, "זוגי": even,
        "odd": odd, "אי-זוגי": odd, "איזוגי": odd,
        "1-12": d1, "13-24": d2, "25-36": d3,
        "1-18": h1, "19-36": h2,
        "1st": c1, "2nd": c2, "3rd": c3,
    }
    if t in names:
        return names[t]
    if t.isdigit() and 0 <= int(t) <= 36:
        k = int(t)
        return (str(k), lambda n, k=k: n == k, 36)
    return None

def roul_pick_list(text):
    if not text:
        return None
    picks, seen = [], set()
    for part in re.split(r"[,\s]+", text.strip()):
        if not part:
            continue
        c = parse_roul_pick(part)
        if c is None:
            return None
        if c[0] not in seen:
            seen.add(c[0])
            picks.append(c)
    return picks or None

ROUNDS = {}   # channel id -> the open roulette round of that channel (everyone can join it, as many bets as they want)

def roul_embed(rnd):
    first = rnd["bets"][0]
    names = ", ".join(b["pick"][0] for b in rnd["bets"] if b["user"].id == first["user"].id and b["token"].split(":")[0] == first["token"].split(":")[0])
    each = f" ({fmt(first['per'])} each)" if "," in names else ""
    return discord.Embed(color=ROUL_COLOR, title="🎰 Roulette Round Opened", description=(
        f"Roulette round opened by {first['user'].mention}.\n\n"
        f"**Bet:** {fmt(first['per'])} {cur()} on **{names}**{each}\n\n"
        f"Place a `${ROUL_JOIN}` to join before it closes.\n"
        f"Betting closes <t:{rnd['end']}:R>."))

async def run_roulette(cid, rnd):
    try:
        await asyncio.sleep(max(0, rnd["end"] - time.time()))
        if ROUNDS.get(cid) is rnd:
            ROUNDS.pop(cid, None)
        bets = rnd["bets"]
        winner = random.randint(0, 36)
        for _ in range(luck_attempts(0) - 1):
            if any(b["pick"][1](winner) for b in bets):
                break
            winner = random.randint(0, 36)
        color_name = roul_color(winner)
        lines = []
        for b in bets:
            hit = b["pick"][1](winner)
            win = b["per"] * b["pick"][2] if hit else 0
            net = win - b["per"]
            if net > 0:
                win += multi_extra("roulette", net)
                net = win - b["per"]
            DB.get("pending", {}).pop(b["token"], None)
            user_data(b["user"].id)["cash"] += win
            log_game(b["user"], "roulette", b["per"], net)
            if win > 0:
                lines.append(f"🏆 {b['user'].mention} Won - {fmt(win)} {cur()}")
            else:
                lines.append(f"❌ {b['user'].mention} Lost")
        save()
        e = discord.Embed(color=ROUL_COLOR, title="Roulette Results", description=(
            f"The ball landed on **{winner} ({color_name.capitalize()})**\n\n**Results**\n" + "\n".join(lines)))
        none = discord.AllowedMentions.none()
        await rnd["channel"].send(embed=e, allowed_mentions=none)
    except Exception as ex:
        print("Roulette failed:", repr(ex))
        if ROUNDS.get(cid) is rnd:
            ROUNDS.pop(cid, None)
        for b in rnd["bets"]:
            if DB.get("pending", {}).pop(b["token"], None) is not None:
                user_data(b["user"].id)["cash"] += b["per"]
        save()

@bot.command(name="roulette", usage=ROUL_USAGE)
async def roulette(ctx, amount: str = None, *, picks: str = None):
    choices = roul_pick_list(picks)
    if amount is None:
        return await ctx.reply(f"The minimum bet is {MIN_BET}{cur()}!")
    if choices is None:
        return await reply(ctx, f"Usage: `${ROUL_USAGE}`", RED)
    u = user_data(ctx.author.id)
    n = len(choices)
    total = parse_amount(amount, u["cash"])
    if total is None:
        return await reply(ctx, f"Usage: `${ROUL_USAGE}` (min {MIN_BET})", RED)
    per = total // n if amount.lower() in ("all", "half") else total
    if per < MIN_BET:
        return await ctx.reply(f"The minimum bet is {MIN_BET}{cur()}!")
    if per * n > u["cash"]:
        return await reply(ctx, "You don't have that much money.", RED)
    u["cash"] -= per * n
    base = str(ctx.message.id)
    new = []
    for i, c in enumerate(choices):
        tok = f"{base}:{i}"
        DB.setdefault("pending", {})[tok] = {"uid": str(ctx.author.id), "bet": per}
        new.append({"user": ctx.author, "per": per, "pick": c, "token": tok})
    save()
    rnd = ROUNDS.get(ctx.channel.id)
    opened = rnd is None or rnd["end"] <= time.time()
    if opened:
        rnd = {"end": int(time.time()) + ROUL_WAIT, "bets": [], "channel": ctx.channel}
        ROUNDS[ctx.channel.id] = rnd
    rnd["bets"].extend(new)
    none = discord.AllowedMentions.none()
    try:
        if opened:
            await ctx.reply(embed=roul_embed(rnd), mention_author=False, allowed_mentions=none)
        else:
            names = ", ".join(c[0] for c in choices)
            await ctx.reply(embed=make_embed(ctx.author, (
                f"**Bet Placed**\n\nYour roulette bet for {fmt(per)} {cur()} on **{names}** has been added."), GREEN),
                mention_author=False)
    except Exception:
        for b in new:
            DB.get("pending", {}).pop(b["token"], None)
            rnd["bets"].remove(b)
        u["cash"] += per * n
        save()
        if opened:
            ROUNDS.pop(ctx.channel.id, None)
        raise
    if opened:
        bg(run_roulette(ctx.channel.id, rnd))
