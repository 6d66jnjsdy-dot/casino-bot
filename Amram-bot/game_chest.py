import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= CHEST =================
# Discord does not know the 🪎 emoji yet, so the chest is drawn in code and uploaded once as a bot emoji
# (same idea as the blackjack cards).
CHEST_EMOJI_NAME = "chest_btn"
CHEST_FALLBACK = "🧰"        # only used if the bot emoji could not be created
CHEST_EMOJI = None           # filled by ensure_chest_emoji()
_chest_tried = False
CHEST_DEAD = "⚰️"
CHEST_MULTS = [2.5, 1.3, 0, 0, 0]        # one chest x2.5, one x1.3, the other three are dead
CHEST_LUCKY_MULT = 10                    # the lucky chest that replaces the x2.5 one
CHEST_LUCKY_ODDS = 20                    # 1 game out of 20 the x2.5 chest becomes the lucky x10 chest
CHEST_ICONS = {2.5: "💰", 1.3: "💰", 10: "💰"}   # every winning chest shows only 💰, the dead ones show ⚰️
CHEST_SPY_KEY = {0: "bomb", 1.3: "coin", 2.5: "bag", 10: "urn"}   # only used by the owner's $predict
CHEST_WIDTH = 16             # invisible padding on the title line = how wide the embed is (lower it if the title wraps on a phone)
CHEST_STEP = 0.9             # seconds between the opening frames (3 frames, so about 2.7s of suspense). Lower = faster.
CHEST_OPENING = [            # the opening frames, {n} = the chest number
    "🔑 Opening chest {n}...",
    "🥁 Drum roll... 🥁",
    "👀 Let's see what's inside... 👀",
]

def _chest_png():
    K, S = 4, 128 * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    brown, dark = (150, 92, 44, 255), (88, 50, 22, 255)
    gold, gold_d = (246, 196, 64, 255), (160, 110, 20, 255)
    d.rounded_rectangle([14 * K, 58 * K, 114 * K, 108 * K], radius=6 * K, fill=brown, outline=dark, width=3 * K)
    d.pieslice([14 * K, 20 * K, 114 * K, 100 * K], 180, 360, fill=brown, outline=dark, width=3 * K)
    d.line([(14 * K, 60 * K), (114 * K, 60 * K)], fill=dark, width=2 * K)
    for x0 in (32, 86):
        d.rectangle([x0 * K, 31 * K, (x0 + 10) * K, 107 * K], fill=gold, outline=gold_d, width=K)
    d.rounded_rectangle([54 * K, 52 * K, 74 * K, 76 * K], radius=4 * K, fill=gold, outline=gold_d, width=2 * K)
    d.ellipse([60 * K, 58 * K, 68 * K, 66 * K], fill=dark)
    d.rectangle([62 * K, 63 * K, 66 * K, 72 * K], fill=dark)
    buf = io.BytesIO()
    im.resize((128, 128), Image.LANCZOS).save(buf, "PNG")
    return buf.getvalue()

async def ensure_chest_emoji():
    global CHEST_EMOJI, _chest_tried
    if CHEST_EMOJI or _chest_tried:
        return
    _chest_tried = True
    try:
        if not hasattr(bot, "create_application_emoji"):
            print("Chest emoji needs discord.py 2.5 or newer. Using the fallback emoji.")
            return
        have = next((e for e in await bot.fetch_application_emojis() if e.name == CHEST_EMOJI_NAME), None)
        if have is None:
            have = await bot.create_application_emoji(name=CHEST_EMOJI_NAME, image=await asyncio.to_thread(_chest_png))
        CHEST_EMOJI = str(have)
    except Exception as ex:
        print("Chest emoji failed, using the fallback emoji:", repr(ex))

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
            b = discord.ui.Button(label=str(i + 1), emoji=CHEST_EMOJI or CHEST_FALLBACK,
                                  style=discord.ButtonStyle.primary, row=0)
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

    def title(self):
        return "💰 **Treasure Chests** 💰" + "⠀" * CHEST_WIDTH

    def reveal(self):
        for i, b in enumerate(self.children):
            m = self.layout[i]
            b.disabled = True
            b.emoji = CHEST_ICONS.get(m, CHEST_DEAD)
            b.label = f"x{m:g}"
            b.style = (discord.ButtonStyle.success if m > 0 else discord.ButtonStyle.danger) if i == self.picked \
                else discord.ButtonStyle.secondary

    def opening(self, idx, step):
        text = CHEST_OPENING[step].format(n=idx + 1)
        return discord.Embed(description=f"{self.title()}\n\n**{text}**\n\n-# Bet: {fmt(self.bet)} {cur()}", color=BLUE)

    def render(self):
        c = cur()
        if not self.done:
            return discord.Embed(description=f"{self.title()}\n\nchoose one chest 🤫\n\n-# Bet: {fmt(self.bet)} {c}", color=BLUE)
        m = self.layout[self.picked]
        amt = f"{fmt(self.returned)} {c}"
        sub = f"-# Bet: {fmt(self.bet)} {c}  ·  x{m:g}"
        if m == CHEST_LUCKY_MULT:
            text, color = f"🍀 You Got Lucky One🍀\nYou got {amt}", YELLOW
        elif m == 2.5:
            text, color = f"You choose the best chest and got {amt}", GREEN
        elif m > 0:
            text, color = f"You choose a chest and got {amt}", GREEN
        else:
            text, color = "Looser☠️", RED
        return discord.Embed(description=f"{self.title()}\n\n**{text}**\n\n{sub}", color=color)

    async def edit(self, interaction, embed):
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.edit_original_response(embed=embed, view=self)

    async def pick(self, interaction, idx):
        # luck: a losing chest is re-rolled (same idea as the blackjack luck)
        for _ in range(luck_attempts(self.user.id) - 1):
            if self.layout[idx] > 0:
                break
            self.layout = chest_layout()
        self.picked = idx
        self.pay(int(self.bet * self.layout[idx]))       # paid right away, so a second click can never double-play
        for i, b in enumerate(self.children):            # lock every button, only the chosen one stays blue
            b.disabled = True
            b.style = discord.ButtonStyle.primary if i == idx else discord.ButtonStyle.secondary
        try:
            for step in range(len(CHEST_OPENING)):       # the suspense: a few quick frames before the reveal
                await self.edit(interaction, self.opening(idx, step))
                await asyncio.sleep(CHEST_STEP)
        except Exception as ex:
            print("Chest animation failed:", repr(ex))
        self.reveal()
        try:
            await self.edit(interaction, self.render())
        except Exception as ex:
            print("Chest reveal failed:", repr(ex))
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
    global CHEST_EMOJI
    bet = await take_bet(ctx, amount, "chest <amount | half | all>", track=True)
    if not bet:
        return
    BUSY.add(ctx.author.id)
    view = None
    try:
        await ensure_chest_emoji()
        view = ChestView(ctx.author, bet, str(ctx.message.id))
        try:
            msg = await ctx.send(embed=view.render(), view=view)
        except discord.HTTPException as ex:
            print("Chest send failed, retrying with the fallback emoji:", repr(ex))
            CHEST_EMOJI = None
            view = ChestView(ctx.author, bet, str(ctx.message.id))
            msg = await ctx.send(embed=view.render(), view=view)
    except Exception as ex:
        cancel_game(ctx.author, str(ctx.message.id), bet)
        BUSY.discard(ctx.author.id)
        try:
            await reply(ctx, f"Chest error: `{ex}`", RED)      # shows the real reason in the channel
        except Exception:
            pass
        raise
    view.message = msg
    spy(view)
