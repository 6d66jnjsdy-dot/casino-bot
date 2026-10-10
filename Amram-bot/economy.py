import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= ECONOMY =================
ID_RE = re.compile(r"<@!?(\d{15,25})>|(\d{15,25})")

async def resolve_target(ctx, arg):
    """Reply target ("a"), a mention, a raw user ID, or a name."""
    if arg is None or arg.lower() == "a":
        ref = ctx.message.reference
        if ref is None:
            return None
        msg = ref.resolved if isinstance(ref.resolved, discord.Message) else None
        if msg is None:
            try:
                msg = await ctx.channel.fetch_message(ref.message_id)
            except Exception:
                return None
        author = msg.author
        if not any(m.id == author.id for m in ctx.message.mentions):
            raise ReplyPingOff()
        return ctx.guild.get_member(author.id) or await ctx.guild.fetch_member(author.id)
    m = ID_RE.fullmatch(arg.strip())
    if m:
        uid = int(m.group(1) or m.group(2))
        member = ctx.guild.get_member(uid) if ctx.guild else None
        if member:
            return member
        try:
            return await ctx.guild.fetch_member(uid)
        except discord.HTTPException:
            pass
        try:
            return await bot.fetch_user(uid)
        except discord.HTTPException:
            raise commands.BadArgument("Unknown user ID")
    return await commands.MemberConverter().convert(ctx, arg)

@bot.command(name="bal", aliases=["balance"], usage="bal [@user | user ID | a (reply)]")
async def bal(ctx, target: str = None):
    if target is None:
        member = ctx.author
    else:
        member = await resolve_target(ctx, target)
        if member is None:
            return await reply(ctx, "Usage: `$bal [@user | user ID]` — or reply to a player (ping ON) and type `$bal a`", RED)
    u, c = user_data(member.id), cur()
    view = BalView()
    view.message = await ctx.reply(embed=make_embed(member, (
        "Use the `top` command to view your rank.\n\n"
        f"• **Money Out:** {fmt(u['cash'])} {c}\n"
        f"• **Bank Money:** {fmt(u['bank'])} {c}\n"
        f"• **Total Money:** {fmt(u['cash'] + u['bank'])} {c}"), BLUE), view=view, mention_author=False)

class BalView(discord.ui.View):
    """The 'Top' button under $bal: whoever presses it gets the full leaderboard privately (with Dismiss message)."""

    def __init__(self):
        super().__init__(timeout=600)
        self.message = None

    @discord.ui.button(label="Top", style=discord.ButtonStyle.primary)
    async def top_btn(self, interaction, button):
        view = TopView(interaction.user)
        await interaction.response.send_message(embed=view.build(), view=view, ephemeral=True)

    async def on_timeout(self):
        for b in self.children:
            b.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

async def move(ctx, amount, src, dst, usage, verb):
    u = user_data(ctx.author.id)
    amt = parse_amount(amount, u[src])
    if amt is None:
        return await reply(ctx, f"Usage: `${usage}`", RED)
    if amt <= 0 or amt > u[src]:
        return await reply(ctx, "You don't have that much money" + (" in your bank." if src == "bank" else "."), RED)
    u[src] -= amt
    u[dst] += amt
    save()
    log_money(ctx.author, ctx.command.name.upper(), f"{verb.capitalize()} {fmt(amt)} {cur()}", BLUE)
    await reply(ctx, f"Successfully {verb} {fmt(amt)} {cur()} {'to' if dst == 'bank' else 'from'} your bank account.", GREEN)

@bot.command(name="dep", aliases=["deposit"], usage="dep <amount | half | all>")
async def dep(ctx, amount: str = None):
    await move(ctx, amount, "cash", "bank", "dep <amount | half | all>", "deposited")

@bot.command(name="with", aliases=["withdraw"], usage="with <amount | half | all>")
async def withdraw(ctx, amount: str = None):
    await move(ctx, amount, "bank", "cash", "with <amount | half | all>", "withdrew")

async def earn(ctx, text):
    amt = random.randint(EARN_MIN, EARN_MAX)
    user_data(ctx.author.id)["cash"] += amt
    save()
    log_money(ctx.author, ctx.command.name.upper(), f"Earned {fmt(amt)} {cur()}", GREEN)
    await reply(ctx, text.format(f"{fmt(amt)} {cur()}"), GREEN)

@bot.command(name="crime", cooldown_after_parsing=True)
@commands.cooldown(1, 120, commands.BucketType.user)
async def crime(ctx):
    await earn(ctx, "You successfully committed a crime and got {}!")

@bot.command(name="work", cooldown_after_parsing=True)
@commands.cooldown(1, 120, commands.BucketType.user)
async def work(ctx):
    await earn(ctx, "You worked hard and got {}!")

@bot.command(name="pay", usage="pay @user | user ID <amount | half | all>  (or reply + ping ON: pay a <amount>)")
async def pay(ctx, target: str = None, amount: str = None):
    member = await resolve_target(ctx, target)
    if member is None or amount is None:
        return await reply(ctx, "Usage: `$pay @user | user ID <amount | half | all>` — or reply to a player (ping ON) and type `$pay a <amount>`", RED)
    if member.bot:
        return await reply(ctx, "Please enter a valid user.", RED)
    if member.id == ctx.author.id:
        return await reply(ctx, "You can't pay this user.", RED)
    u = user_data(ctx.author.id)
    amt = parse_amount(amount, u["cash"])
    if amt is None or amt <= 0:
        return await reply(ctx, "Usage: `$pay @user | user ID <amount | half | all>`", RED)
    if amt > u["cash"]:
        return await reply(ctx, "You don't have that much money.", RED)
    u["cash"] -= amt
    user_data(member.id)["cash"] += amt
    save()
    log_money(ctx.author, "PAY", f"Paid {fmt(amt)} {cur()} to {member.name} (`{member.id}`)", BLUE)
    await reply(ctx, f"You paid {fmt(amt)} {cur()} to {member.name}.", GREEN)

@bot.command(name="rob", usage="rob @user | user ID  (or reply + ping ON: rob a)", cooldown_after_parsing=True)
@commands.cooldown(1, ROB_COOLDOWN, commands.BucketType.user)
async def rob(ctx, target: str = None):
    try:
        member = await resolve_target(ctx, target)
    except Exception:
        ctx.command.reset_cooldown(ctx)
        raise
    if member is None:
        ctx.command.reset_cooldown(ctx)
        return await reply(ctx, "Usage: `$rob @user | user ID` — or reply to a player (ping ON) and type `$rob a`", RED)
    if member.bot:
        ctx.command.reset_cooldown(ctx)
        return await reply(ctx, "Please enter a valid user.", RED)
    if member.id == ctx.author.id:
        ctx.command.reset_cooldown(ctx)
        return await reply(ctx, "You cannot rob yourself.", RED)
    if immunity_until(member) is not None:
        ctx.command.reset_cooldown(ctx)
        return await reply(ctx, f"{member.name} is immune.", RED)
    me, tgt = user_data(ctx.author.id), user_data(member.id)
    loot = {k: int(tgt[k] * ROB_PERCENT) for k in ROB_FROM}
    total = sum(loot.values())
    if not total:
        return await reply(ctx, f"You tried to rob a poor person and lost 0 {cur()}.", RED)
    for k, v in loot.items():
        tgt[k] -= v
    me["cash"] += total
    save()
    log_game(ctx.author, "rob", 0, total, detail=f"Robbed {member.name} (`{member.id}`)")
    await reply(ctx, f"You robbed {fmt(total)} {cur()} from {member.name}!", GREEN)

# ---------- leaderboard ----------
TOP_MODES = {"bank": lambda d: d["bank"], "total": lambda d: d["cash"] + d["bank"], "cash": lambda d: d["cash"]}
TOP_PAGE = 10

class TopView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=180)
        self.user, self.mode, self.page, self.message = user, "total", 0, None
        self.mode_btns = {}
        for m in ("bank", "total", "cash"):
            b = discord.ui.Button(label=m.capitalize(), row=0)
            b.callback = self.set_mode(m)
            self.mode_btns[m] = b
            self.add_item(b)
        refresh = discord.ui.Button(emoji="🔃", style=discord.ButtonStyle.secondary, row=0)
        refresh.callback = self.refresh
        self.add_item(refresh)
        self.prev_btn = discord.ui.Button(label="Previous Page", style=discord.ButtonStyle.secondary, row=1)
        self.prev_btn.callback = self.turn(-1)
        self.page_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, disabled=True, row=1)
        self.next_btn = discord.ui.Button(label="Next Page", style=discord.ButtonStyle.secondary, row=1)
        self.next_btn.callback = self.turn(1)
        for b in (self.prev_btn, self.page_btn, self.next_btn):
            self.add_item(b)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Open your own leaderboard with `$lb`.", ephemeral=True)
            return False
        return True

    def ranked(self):
        f = TOP_MODES[self.mode]
        rows = [(int(uid), f(d)) for uid, d in DB["users"].items()]
        return sorted((r for r in rows if r[1] > 0), key=lambda r: r[1], reverse=True)

    def build(self):
        ranked = self.ranked()
        pages = max(1, math.ceil(len(ranked) / TOP_PAGE))
        self.page = max(0, min(self.page, pages - 1))
        start = self.page * TOP_PAGE
        lines = [f"{start + i}. <@{uid}> • {fmt(v)} {cur()}" for i, (uid, v) in enumerate(ranked[start:start + TOP_PAGE], 1)]
        for m, b in self.mode_btns.items():
            b.style = discord.ButtonStyle.primary if m == self.mode else discord.ButtonStyle.secondary
        self.prev_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= pages - 1
        self.page_btn.label = f"Page • {self.page + 1}/{pages}"
        e = discord.Embed(description="\n".join(lines) or "Nobody has any money yet.", color=BLUE)
        e.set_author(name=f"Top {self.mode.capitalize()} Users", icon_url=self.user.display_avatar.url)
        return e

    async def show(self, interaction):
        await interaction.response.edit_message(embed=self.build(), view=self)

    def set_mode(self, mode):
        async def cb(interaction):
            self.mode, self.page = mode, 0
            await self.show(interaction)
        return cb

    def turn(self, step):
        async def cb(interaction):
            self.page += step
            await self.show(interaction)
        return cb

    async def refresh(self, interaction):
        await self.show(interaction)

    async def on_timeout(self):
        for b in self.children:
            b.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

@bot.command(name="top", aliases=["lb"])
async def top(ctx):
    view = TopView(ctx.author)
    view.message = await ctx.reply(embed=view.build(), view=view, mention_author=False)
