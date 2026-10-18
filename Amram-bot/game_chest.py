import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= CHEST =================
CHEST = "🪎"                 # the chest emoji on the buttons
CHEST_FALLBACK = "🧰"        # used automatically if Discord rejects the emoji above (it is a very new emoji)
CHEST_DEAD = "⚰️"
CHEST_MULTS = [2.5, 1.3, 0, 0, 0]        # one chest x2.5, one x1.3, the other three are dead
CHEST_LUCKY_MULT = 10                    # the lucky chest that replaces the x2.5 one
CHEST_LUCKY_ODDS = 20                    # 1 game out of 20 the x2.5 chest becomes the lucky x10 chest
CHEST_ICONS = {2.5: "💰", 1.3: "🪙", 10: "🍀"}
CHEST_SPY_KEY = {0: "bomb", 1.3: "coin", 2.5: "bag", 10: "urn"}   # only used by the owner's $predict

def chest_layout():
    mults = list(CHEST_MULTS)
    if random.randrange(CHEST_LUCKY_ODDS) == 0:
        mults[mults.index(2.5)] = CHEST_LUCKY_MULT
    random.shuffle(mults)
    return mults

class ChestView(discord.ui.View):
    def __init__(self, user, bet, token=None):
        super().__init__(timeout=120)
        self.user, self.bet, self.token = user, bet, token
        self.game_name, self.cols = "Chest", 5
        self.layout = chest_layout()
        self.board = [CHEST_SPY_KEY[m] for m in self.layout]
        self.done, self.net, self.returned, self.picked = False, 0, 0, None
        self.message = None
        for i in range(5):
            b = discord.ui.Button(label=str(i + 1), emoji=CHEST, style=discord.ButtonStyle.primary, row=0)
            b.callback = self.make_callback(i)
            self.add_item(b)

    def make_callback(self, idx):
        async def cb(interaction):
            await self.pick(interaction, idx)
        return cb

    async def interaction_check(self, interaction):
        if not may_play(interaction, self.user.id):
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        if self.done:
            if not interaction.response.is_done():
                await interaction.response.defer()
            return False
        return True

    def pay(self, returned):
        returned += multi_extra("chest", returned - self.bet)
        self.done, self.returned, self.net = True, returned, returned - self.bet
        pending_done(self.token)
        user_data(self.user.id)["cash"] += returned
        save()
        log_game(self.user, "chest", self.bet, self.net)
        BUSY.discard(self.user.id)

    def reveal(self):
        for i, b in enumerate(self.children):
            m = self.layout[i]
            b.disabled = True
            b.emoji = CHEST_ICONS.get(m, CHEST_DEAD)
            b.label = f"x{m:g}"
            b.style = (discord.ButtonStyle.success if m > 0 else discord.ButtonStyle.danger) if i == self.picked \
                else discord.ButtonStyle.secondary

    def render(self):
        if not self.done:
            return discord.Embed(description="choose one chest 🤫", color=BLUE)
        m, c = self.layout[self.picked], cur()
        amt = f"{fmt(self.returned)} {c}"
        if m == CHEST_LUCKY_MULT:
            return discord.Embed(description=f"🍀 You Got Lucky One🍀\nYou got {amt}", color=YELLOW)
        if m == 2.5:
            return discord.Embed(description=f"You choose the best chest and got {amt}", color=GREEN)
        if m > 0:
            return discord.Embed(description=f"You choose a chest and got {amt}", color=GREEN)
        return discord.Embed(description="Looser☠️", color=RED)

    async def pick(self, interaction, idx):
        # luck: a losing chest is re-rolled (same idea as the blackjack luck)
        for _ in range(luck_attempts(self.user.id) - 1):
            if self.layout[idx] > 0:
                break
            self.layout = chest_layout()
        self.picked = idx
        self.pay(int(self.bet * self.layout[idx]))
        self.reveal()
        await interaction.response.edit_message(embed=self.render(), view=self)
        self.stop()

    async def on_timeout(self):
        if self.done:
            return
        self.done = True
        cancel_game(self.user, self.token, self.bet)      # nothing was revealed, so the bet just goes back
        for b in self.children:
            b.disabled = True
        if self.message:
            try:
                await self.message.edit(embed=discord.Embed(description="Time's up, your bet was returned.", color=YELLOW), view=self)
            except Exception:
                pass

@bot.command(name="chest", aliases=["chests"], usage="chest <amount | half | all>")
async def chest(ctx, amount: str = None):
    global CHEST
    bet = await take_bet(ctx, amount, "chest <amount | half | all>", track=True)
    if not bet:
        return
    BUSY.add(ctx.author.id)
    view = ChestView(ctx.author, bet, str(ctx.message.id))
    try:
        try:
            msg = await ctx.send(embed=view.render(), view=view)
        except discord.HTTPException as ex:
            print("Chest send failed, retrying with the fallback emoji:", repr(ex))
            CHEST = CHEST_FALLBACK
            view = ChestView(ctx.author, bet, str(ctx.message.id))
            msg = await ctx.send(embed=view.render(), view=view)
    except Exception:
        cancel_game(ctx.author, view.token, bet)
        BUSY.discard(ctx.author.id)
        raise
    view.message = msg
    spy(view)
