import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= OWNER =================
def resolve_key(name):
    name = name.lower().lstrip("$")
    if name in ("s$mines", "smines"):
        return "s$mines"
    cmd = bot.get_command(name)
    return cmd.name if cmd else None

@bot.command(name="disable", usage="disable <command>")
@owner_only
async def disable(ctx, name: str = None):
    off = DB.setdefault("disabled", [])
    if name is None:
        return await reply(ctx, "Disabled: " + (", ".join(f"`{k}`" for k in off) or "none"), BLUE)
    key = resolve_key(name)
    if key is None:
        return await reply(ctx, "Unknown command.", RED)
    if key in ("disable", "enable"):
        return await reply(ctx, "You can't disable this command.", RED)
    if key not in off:
        off.append(key)
        save()
    await reply(ctx, f"`{key}` is now disabled. The bot will not answer to it anymore.", GREEN)

@bot.command(name="enable", aliases=["undisable"], usage="undisable <command | all>")
@owner_only
async def enable(ctx, name: str):
    off = DB.setdefault("disabled", [])
    key = "all" if name.lower() == "all" else resolve_key(name)
    if key == "all":
        off.clear()
    elif key in off:
        off.remove(key)
    else:
        return await reply(ctx, "This command isn't disabled.", RED)
    save()
    await reply(ctx, "All commands are enabled." if key == "all" else f"`{key}` is enabled again.", GREEN)

@bot.command(name="setaddmoney", usage="setaddmoney <max | off>")
@owner_only
async def setaddmoney(ctx, amount: str = None):
    cap = DB.get("add_max")
    if amount is None:
        return await reply(ctx, f"Add-money limit: {fmt(cap) + ' ' + cur() if cap else 'no limit'}\nSet it with `$setaddmoney <max>` (or `off`)", BLUE)
    if amount.lower() in ("off", "none", "no"):
        DB.pop("add_max", None)
        save()
        return await reply(ctx, "The add-money limit was removed.", GREEN)
    amt = parse_amount(amount, 0)
    if amt is None or amt <= 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    DB["add_max"] = amt
    save()
    await reply(ctx, f"Staff can now add at most {fmt(amt)} {cur()} per command.", GREEN)

@bot.command(name="setlimit", usage="setlimit <additions per day>")
@owner_only
async def setlimit(ctx, amount: str = None):
    cap = DB.get("add_limit")
    if amount is None:
        return await reply(ctx, f"Daily add limit: {cap if cap else 'no limit'}\nSet it with `$setlimit <number>`", BLUE)
    if not amount.isdigit() or int(amount) < 1:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    DB["add_limit"] = int(amount)
    save()
    await reply(ctx, f"Each staff member can now use the add-money commands **{int(amount)}** time(s) per day. It resets at 00:00.", GREEN)

@bot.command(name="unsetlimit", usage="unsetlimit")
@owner_only
async def unsetlimit(ctx):
    DB.pop("add_limit", None)
    DB.pop("add_used", None)
    DB.pop("add_max", None)
    save()
    await reply(ctx, "All add-money limits were removed (daily limit and the per-command maximum).", GREEN)

@bot.command(name="multi", usage="multi <game | all> <amount | off> [time: 10m, 2h, 1d]")
@owner_only
async def multi(ctx, game: str = None, amount: str = None, duration: str = None):
    cfg = DB.setdefault("multi", {})
    until = DB.setdefault("multi_until", {})
    for k in [k for k, t in until.items() if t and time.time() >= t]:
        cfg.pop(k, None)
        until.pop(k, None)
    games = ", ".join(f"`{g}`" for g in MULTI_GAMES)
    if game is None:
        active = "\n".join(f"• `{k}` → **x{v:g}** ({fmt_left(until.get(k))})" for k, v in cfg.items()) or "No active multipliers."
        return await reply(ctx, f"**🔥 Multi (owner)**\n{active}\n\nUsage: `${ctx.command.usage}` (amount 1-{MULTI_MAX})\nGames: {games}", BLUE)
    g = game.lower().lstrip("$")
    if g in ("off", "reset", "clear") and amount is None:
        cfg.clear()
        until.clear()
        save()
        return await reply(ctx, "All multipliers were removed.", GREEN)
    if g == "all":
        keys = list(MULTI_GAMES)
    else:
        key = resolve_key(g)
        if key not in MULTI_GAMES:
            return await reply(ctx, f"Unknown game. Games: {games}", RED)
        keys = [key]
    if amount is None:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    if amount.lower() in ("off", "none", "no"):
        value = None
    else:
        try:
            value = float(amount.lower().strip("x"))
        except ValueError:
            return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
        if not (1 <= value <= MULTI_MAX):
            return await reply(ctx, f"The multiplier must be between 1 and {MULTI_MAX}.", RED)
    secs = None
    if duration is not None:
        secs = parse_duration(duration)
        if secs is None:
            return await reply(ctx, f"Invalid time. Examples: `30s`, `10m`, `2h`, `1d`, `1h30m`\nUsage: `${ctx.command.usage}`", RED)
    end_at = int(time.time() + secs) if secs else None
    for k in keys:
        if value is None or value == 1:
            cfg.pop(k, None)
            until.pop(k, None)
        else:
            cfg[k] = value
            if end_at:
                until[k] = end_at
            else:
                until.pop(k, None)
    save()
    names = "all games" if g == "all" else f"`{keys[0]}`"
    if value is None or value == 1:
        return await reply(ctx, f"Multi removed from {names}.", GREEN)
    await reply(ctx, f"🔥 Multi **x{value:g}** is now active on {names} ({fmt_left(end_at)}). "
                     f"Every win pays x{value:g} of the normal profit.", GREEN)

async def luck_say(ctx, text):
    await ctx.reply(text, mention_author=False)

@bot.command(name="luck", usage="luck <2.5x | off> [time: 10m, 2h, 1d]")
@owner_only
async def luck(ctx, amount: str = None, duration: str = None):
    cfg = DB.get("luck")
    if cfg and cfg.get("until") and time.time() >= cfg["until"]:
        DB.pop("luck", None)
        cfg = None
        save()
    if amount is None:
        if not cfg:
            return await luck_say(ctx, f"🍀 Luck is OFF. Usage: `${ctx.command.usage}` (1-{LUCK_MAX})")
        return await luck_say(ctx, f"🍀 Luck is **x{cfg['value']:g}** for everyone ({fmt_left(cfg.get('until'))}).")
    if amount.lower() in ("off", "none", "no", "reset"):
        DB.pop("luck", None)
        save()
        return await luck_say(ctx, "🍀 Luck is OFF.")
    try:
        value = float(amount.lower().strip("x"))
    except ValueError:
        return await luck_say(ctx, f"Usage: `${ctx.command.usage}`")
    if not (1 <= value <= LUCK_MAX):
        return await luck_say(ctx, f"Luck must be between 1 and {LUCK_MAX}.")
    secs = None
    if duration is not None:
        secs = parse_duration(duration)
        if secs is None:
            return await luck_say(ctx, "Invalid time. Examples: `30s`, `10m`, `2h`, `1d`, `1h30m`")
    if value == 1:
        DB.pop("luck", None)
        save()
        return await luck_say(ctx, "🍀 Luck is OFF.")
    end_at = int(time.time() + secs) if secs else None
    DB["luck"] = {"value": value, "until": end_at}
    save()
    await luck_say(ctx, f"🍀 Luck **x{value:g}** is ON for everyone ({fmt_left(end_at)}).")

@bot.command(name="unluck", usage="unluck")
@owner_only
async def unluck(ctx):
    DB.pop("luck", None)
    save()
    await luck_say(ctx, "🍀 Luck is OFF.")

class ConfirmReset(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=30)
        self.user, self.message = user, None

    async def interaction_check(self, interaction):
        if interaction.user.id not in OWNER_IDS:
            await interaction.response.send_message("Only the owner can do this.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Yes, reset everyone", style=discord.ButtonStyle.danger)
    async def yes(self, interaction, button):
        n = 0
        for d in DB["users"].values():
            if d.get("cash") or d.get("bank"):
                n += 1
            d["cash"] = d["bank"] = 0
        save()
        self.stop()
        await interaction.response.edit_message(
            embed=make_embed(self.user, f"✅ The economy was reset: cash and bank of {n} players are now 0.", GREEN), view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def no(self, interaction, button):
        self.stop()
        await interaction.response.edit_message(embed=make_embed(self.user, "Cancelled.", BLUE), view=None)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(embed=make_embed(self.user, "Timed out, nothing was reset.", BLUE), view=None)
            except Exception:
                pass

@bot.command(name="reset-economy", aliases=["reset-economey", "reseteconomy"], usage="reset-economy")
@owner_only
async def reset_economy(ctx):
    view = ConfirmReset(ctx.author)
    view.message = await ctx.reply(embed=make_embed(
        ctx.author, "⚠️ This sets the **cash and bank of every player** to 0. It can't be undone.", RED),
        view=view, mention_author=False)

async def secret_toggle(ctx, key, on, text):
    if on:
        DB[key] = True
    else:
        DB.pop(key, None)
    save()
    try:
        await ctx.message.delete()
    except Exception:
        pass
    try:
        await ctx.author.send(text)
    except Exception:
        await reply(ctx, text, BLUE)

def secret_cmd(key, on, text):
    async def cmd(ctx):
        await secret_toggle(ctx, key, on, text)
    return cmd

for _n, _k, _on, _t in (
        ("touch", "touch", True, "👆 Touch is ON: you can click the buttons of any player's mt, S$mines, gm and mines game."),
        ("untouch", "touch", False, "👆 Touch is OFF.")):
    bot.command(name=_n)(owner_only(secret_cmd(_k, _on, _t)))

async def secret_say(ctx, text):
    """Delete the command message and answer in the author's DMs, so nobody sees the command being used."""
    try:
        await ctx.message.delete()
    except Exception:
        pass
    try:
        await ctx.author.send(text)
    except Exception:
        await reply(ctx, "I can't DM you. Open your DMs for this server and try again.", RED)

async def predict_check(ctx):
    return predict_access(ctx.author.id)          # everyone else is ignored silently, like a command that does not exist

@bot.command(name="predict")
@commands.check(predict_check)
async def predict(ctx):
    if ctx.author.id in OWNER_IDS:
        return await secret_toggle(ctx, "predict", True, "🔮 Predict is ON: you get every board (mt, S$mines, gm, mines) in your DMs.")
    DB.setdefault("predict_on", {})[str(ctx.author.id)] = True
    save()
    left = fmt_left(DB.get("predict_access", {}).get(str(ctx.author.id)))
    await secret_say(ctx, f"🔮 Predict is ON ({left}): you get the board of every game you start (mt, S$mines, gm, mines) in your DMs.")

@bot.command(name="unpredict")
@commands.check(predict_check)
async def unpredict(ctx):
    if ctx.author.id in OWNER_IDS:
        return await secret_toggle(ctx, "predict", False, "🔮 Predict is OFF.")
    DB.get("predict_on", {}).pop(str(ctx.author.id), None)
    save()
    await secret_say(ctx, "🔮 Predict is OFF.")

@bot.command(name="setpredict", usage="setpredict <user> <time | nolimit | off>")
@owner_only
async def setpredict(ctx, target: str = None, duration: str = None):
    member = await resolve_target(ctx, target) if target else None
    if member is None or duration is None:
        return await secret_say(ctx, "Usage: `$setpredict <user> <time | nolimit | off>`  (time: 30m, 2h, 1d)")
    if member.bot:
        return await secret_say(ctx, "Please enter a valid user.")
    grants = DB.setdefault("predict_access", {})
    if duration.lower() in ("off", "none", "remove"):
        grants.pop(str(member.id), None)
        DB.get("predict_on", {}).pop(str(member.id), None)
        save()
        return await secret_say(ctx, f"Predict access of {member.name} was removed.")
    if duration.lower() in NOLIMIT_WORDS:
        until = 0
    else:
        secs = parse_duration(duration)
        if secs is None:
            return await secret_say(ctx, "Invalid time. Use `30m`, `2h`, `1d`, `nolimit` or `off`.")
        until = int(time.time()) + secs
    grants[str(member.id)] = until
    save()
    await secret_say(ctx, f"{member.name} can now use `$predict` ({fmt_left(until)}). "
                          "He gets only the boards of his own games, and his DMs must be open.")
