import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *

# ================= HEADS OR TAIL / CHICKEN FIGHT =================
async def refund_timeout(view, name):
    view.settled = True
    pending_done(view.token)
    user_data(view.user.id)["cash"] += view.bet
    save()
    log_money(view.user, f"{name.upper()} | TIMEOUT", f"Bet of {fmt(view.bet)} {cur()} was returned", YELLOW)
    BUSY.discard(view.user.id)
    if view.message:
        await view.message.edit(embed=make_embed(view.user, "Timed out, your bet was returned.", RED), view=None)

class CoinFlip(OwnedView):
    def __init__(self, user, bet, token=None):
        super().__init__(timeout=60)
        self.user, self.bet, self.token, self.message, self.settled = user, bet, token, None, False

    async def flip(self, interaction, pick):
        if self.settled:
            return await interaction.response.defer()
        self.settled = True
        won = any(random.choice(("Head", "Tail")) == pick for _ in range(luck_attempts(self.user.id)))
        land = pick if won else ("Tail" if pick == "Head" else "Head")
        extra = multi_extra("ht", self.bet) if won else 0
        pending_done(self.token)
        if won:
            user_data(self.user.id)["cash"] += self.bet * 2 + extra
        save()
        log_game(self.user, "heads or tail", self.bet, self.bet + extra if won else -self.bet)
        BUSY.discard(self.user.id)
        self.stop()
        await interaction.response.edit_message(
            embed=result_embed(self.user, won, self.bet + extra, f"You chose **{pick}**, the coin landed on **{land}**.\n"), view=None)

    @discord.ui.button(label="Head", style=discord.ButtonStyle.primary)
    async def head(self, interaction, button):
        await self.flip(interaction, "Head")

    @discord.ui.button(label="Tail", style=discord.ButtonStyle.success)
    async def tail(self, interaction, button):
        await self.flip(interaction, "Tail")

    async def on_timeout(self):
        if not self.settled:
            await refund_timeout(self, "heads or tail")

@bot.command(name="ht", usage="ht <amount | half | all>")
async def ht(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "ht <amount | half | all>", track=True)
    if not bet:
        return
    BUSY.add(ctx.author.id)
    view = CoinFlip(ctx.author, bet, str(ctx.message.id))
    e = make_embed(ctx.author, f"🍀 **CoinFlip** 🍀\n\n**Betting Amount:** `{fmt(bet)}`\n\nChoose head or tail (עץ או פאלי)", YELLOW)
    try:
        view.message = await ctx.reply(embed=e, view=view, mention_author=False)
    except Exception:
        cancel_game(ctx.author, view.token, bet)
        BUSY.discard(ctx.author.id)
        raise

@bot.command(name="cf", usage="cf <amount | half | all>")
async def cf(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "cf <amount | half | all>")
    if not bet:
        return
    u, c = user_data(ctx.author.id), cur()
    strength = max(CF_MIN, min(CF_MAX, u.get("chicken", CF_MIN)))
    won = any(random.randint(1, 100) <= strength + CF_HIDDEN for _ in range(luck_attempts(ctx.author.id)))
    
    if won:
        profit = bet + multi_extra("cf", bet)
        u["cash"] += bet + profit
        u["chicken"] = strength = min(CF_MAX, strength + 1)
        
        # השורה הראשונה נשארת גדולה בתוך ה-Description
        e = make_embed(ctx.author, f"Your chicken won the fight, you won {fmt(profit)} {c}🐓!", GREEN)
        
        # שאר הכתוביות נכנסות כשדה (Field) - מה שגורם להן להיות קטנות יותר ומודגשות בדיוק כמו בתמונה
        e.add_field(
            name=ctx.author.name,
            value=f"**Your chicken's strength (chance of winning): {strength}%**\n**You now have {fmt(u['cash'])} {c}**",
            inline=False
        )
    else:
        profit = -bet
        u["chicken"] = strength = CF_MIN
        e = make_embed(ctx.author, f"Your chicken lost the fight... You lost {fmt(bet)} {c} 🐓.", RED)
        
    save()
    log_game(ctx.author, "chicken fight", bet, profit, detail=f"Chicken strength after the fight: {strength}%")
    
    # שליחה רגילה לחלוטין ללא reply כדי שלא יופיע סרגל הציטוט מעל שם הבוט
    await ctx.send(embed=e)
