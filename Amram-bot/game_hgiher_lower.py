import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= HIGHER OR LOWER =================
HL_MIN, HL_MAX = 1, 10
HL_RTP = 0.95
HL_FLOOR = 1.05
HL_CAP = 25
HL_SAME = 8
HL_COLOR = 0x9B8CD6

HL_FIXED = {
    (9, "higher"): 4, (9, "lower"): 1.2,
    (2, "lower"): 4.2, (2, "higher"): 1.1,
}

def hl_mult(first, choice):
    if choice == "same":
        return HL_SAME
    if (first, choice) in HL_FIXED:
        return HL_FIXED[(first, choice)]
    p = (HL_MAX - first if choice == "higher" else first - HL_MIN) / (HL_MAX - HL_MIN + 1)
    if p <= 0:
        return None
    return round(min(HL_CAP, max(HL_FLOOR, HL_RTP / p)), 2)

def hl_text(m):
    return "-" if m is None else f"{m:g}x"

class HigherLower(OwnedView):
    def __init__(self, user, bet, token=None):
        super().__init__(timeout=60)
        self.user, self.bet, self.token, self.message, self.settled = user, bet, token, None, False
        self.first = random.randint(HL_MIN, HL_MAX)
        self.mults = {c: hl_mult(self.first, c) for c in ("higher", "same", "lower")}
        self.higher.disabled = self.mults["higher"] is None
        self.lower.disabled = self.mults["lower"] is None

    def embed(self):
        m = self.mults
        return discord.Embed(color=HL_COLOR, title="🎲 Higher or Lower 🎲", description=(
            f"**Betting Amount:** `{fmt(self.bet)}`\n"
            f"1️⃣: `{self.first}`\n2️⃣: `❓`\n\n"
            f"**Higher:** `{hl_text(m['higher'])}`\n**Same:** `{hl_text(m['same'])}`\n**Lower:** `{hl_text(m['lower'])}`"))

    async def guess(self, interaction, choice):
        if self.settled:
            return await interaction.response.defer()
        self.settled = True

        def hit(s):
            return (s > self.first and choice == "higher") or (s < self.first and choice == "lower") \
                or (s == self.first and choice == "same")

        second = random.randint(HL_MIN, HL_MAX)
        for _ in range(luck_attempts(self.user.id) - 1):
            if hit(second):
                break
            second = random.randint(HL_MIN, HL_MAX)
        won = hit(second)
        win = int(self.bet * self.mults[choice]) if won else 0
        if win > self.bet:
            win += multi_extra("hl", win - self.bet)
        pending_done(self.token)
        user_data(self.user.id)["cash"] += win
        save()
        net = win - self.bet
        log_game(self.user, "higher or lower", self.bet, net)
        BUSY.discard(self.user.id)
        self.stop()
        cash = user_data(self.user.id)["cash"]
        head = f"You won {fmt(net)} {cur()}!" if net > 0 else f"You lost {fmt(self.bet)} {cur()}."
        e = discord.Embed(color=GREEN if won else RED, description=(
            f"🎲 Game Over 🎲\n\n"
            f"**{head}**\n"
            f"**Your Choice:** `{choice}`\n\n"
            f"1️⃣: `{self.first}`\n"
            f"2️⃣: `{second}`\n\n"
            f"**Balance:** `{fmt(cash)} {cur()}`"))
        await interaction.response.edit_message(embed=e, view=None)

    @discord.ui.button(label="Higher", style=discord.ButtonStyle.primary)
    async def higher(self, interaction, button):
        await self.guess(interaction, "higher")

    @discord.ui.button(label="Same", style=discord.ButtonStyle.primary)
    async def same(self, interaction, button):
        await self.guess(interaction, "same")

    @discord.ui.button(label="Lower", style=discord.ButtonStyle.primary)
    async def lower(self, interaction, button):
        await self.guess(interaction, "lower")

    async def on_timeout(self):
        if not self.settled:
            await refund_timeout(self, "higher or lower")

@bot.command(name="hl", aliases=["high-low", "highlow"], usage="hl <amount | half | all>")
async def hl(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "hl <amount | half | all>", track=True)
    if not bet:
        return
    BUSY.add(ctx.author.id)
    view = HigherLower(ctx.author, bet, str(ctx.message.id))
    try:
        view.message = await ctx.reply(embed=view.embed(), view=view, mention_author=False)
    except Exception:
        cancel_game(ctx.author, view.token, bet)
        BUSY.discard(ctx.author.id)
        raise
