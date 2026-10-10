import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= BLACKJACK =================
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♣", "♠", "♥", "♦"]
SUIT_EMOJI = {"♣": "♣️", "♠": "♠️", "♥": "♥️", "♦": "♦️"}

def card_value(rank):
    return 11 if rank == "A" else 10 if rank in "JQK" else int(rank)

def hand_value(cards):
    total, aces = sum(card_value(r) for r, _ in cards), sum(r == "A" for r, _ in cards)
    while total > 21 and aces:
        total, aces = total - 10, aces - 1
    return total

# ---------- real playing cards, drawn in code, uploaded once as bot emojis (never sent as images) ----------
SW, SH = 148, 186         # card size in pixels (width / height like the reference cards)
_CK = 4                   # supersampling (drawn big, scaled down = smooth edges)
_CRED = (200, 24, 40, 255)
_CBLACK = (24, 24, 30, 255)
_CGOLD = (236, 184, 48, 255)
_CGOLD_D = (150, 105, 15, 255)
_CSKIN = (250, 218, 178, 255)
_CINK = (40, 30, 30, 255)
SUIT_COLOR = {"♣": _CBLACK, "♠": _CBLACK, "♥": _CRED, "♦": _CRED}
SUIT_LETTER = {"♣": "C", "♠": "S", "♥": "H", "♦": "D"}

# Emoji name prefix. Bump this number whenever the card drawing / size changes:
# the bot then deletes every older card emoji and uploads fresh ones, so you never see stale / differently-sized cards.
CARD_VERSION = 2
CARD_PREFIX = f"bj{CARD_VERSION}_"

def _ccircle(cx, cy, r, n=48):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]

def _cnorm(polys):
    pts = [p for poly in polys for p in poly]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    cx, cy, s = (x0 + x1) / 2, (y0 + y1) / 2, 2 / max(x1 - x0, y1 - y0)
    return [[((x - cx) * s, (y - cy) * s) for x, y in poly] for poly in polys]

def _cheart():
    pts = []
    for i in range(160):
        t = 2 * math.pi * i / 160
        pts.append((16 * math.sin(t) ** 3,
                    -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))))
    return pts

SUIT_POLYS = {
    "♥": _cnorm([_cheart()]),
    "♦": _cnorm([[(0, -1), (0.66, 0), (0, 1), (-0.66, 0)]]),
    "♠": _cnorm([[(x, -y) for x, y in _cheart()], [(-1.8, 5), (1.8, 5), (5.5, 16), (-5.5, 16)]]),
    "♣": _cnorm([_ccircle(0, -6, 5.6), _ccircle(-6.3, 3, 5.6), _ccircle(6.3, 3, 5.6), _ccircle(0, 0.5, 3.4),
                 [(-1.8, 2), (1.8, 2), (5.5, 14), (-5.5, 14)]]),
}

def draw_suit(d, suit, cx, cy, s, flip=False):
    color = SUIT_COLOR[suit]
    for poly in SUIT_POLYS[suit]:
        d.polygon([(cx + x * s, cy + (-y if flip else y) * s) for x, y in poly], fill=color)

_PT = 1 / 3
CARD_PIPS = {   # (column 0 / .5 / 1, row 0..1)
    "2": [(.5, 0), (.5, 1)],
    "3": [(.5, 0), (.5, .5), (.5, 1)],
    "4": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "5": [(0, 0), (1, 0), (.5, .5), (0, 1), (1, 1)],
    "6": [(0, 0), (1, 0), (0, .5), (1, .5), (0, 1), (1, 1)],
    "7": [(0, 0), (1, 0), (.5, .25), (0, .5), (1, .5), (0, 1), (1, 1)],
    "8": [(0, 0), (1, 0), (.5, .25), (0, .5), (1, .5), (.5, .75), (0, 1), (1, 1)],
    "9": [(0, 0), (1, 0), (0, _PT), (1, _PT), (.5, .5), (0, 2 * _PT), (1, 2 * _PT), (0, 1), (1, 1)],
    "10": [(0, 0), (1, 0), (.5, 1 / 6), (0, _PT), (1, _PT), (0, 2 * _PT), (1, 2 * _PT), (.5, 5 / 6), (0, 1), (1, 1)],
}

def _face_layer(rank, suit, W, H):
    """Court card: framed panel with a figure in the top half, mirrored (rotated 180) into the bottom half."""
    K = _CK
    col = SUIT_COLOR[suit]
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    px0, px1, py0, py1 = .25 * W, .75 * W, .10 * H, .90 * H
    d.rounded_rectangle([px0, py0, px1, py1], radius=4 * K, fill=(255, 247, 224, 255), outline=_CGOLD_D, width=2 * K)
    d.line([(px0, H / 2), (px1, H / 2)], fill=(225, 200, 150, 255), width=K)
    w = 2 * K
    d.polygon([(.27 * W, .5 * H), (.33 * W, .37 * H), (.67 * W, .37 * H), (.73 * W, .5 * H)], fill=col, outline=_CINK)
    d.polygon([(.42 * W, .37 * H), (.5 * W, .45 * H), (.58 * W, .37 * H)], fill=_CGOLD, outline=_CGOLD_D)
    for bx in (.36, .64):
        d.ellipse([bx * W - 2 * K, .455 * H - 2 * K, bx * W + 2 * K, .455 * H + 2 * K], fill=_CGOLD)
    hair = (120, 70, 25, 255) if rank != "K" else (170, 170, 175, 255)
    if rank == "Q":
        hair = (205, 150, 40, 255)
        d.ellipse([.34 * W, .22 * H, .66 * W, .42 * H], fill=hair, outline=_CINK, width=K)
    elif rank == "J":
        d.ellipse([.36 * W, .2 * H, .64 * W, .36 * H], fill=hair, outline=_CINK, width=K)
    d.ellipse([.405 * W, .225 * H, .595 * W, .375 * H], fill=_CSKIN, outline=_CINK, width=w // 2)
    for ex in (.46, .54):
        d.ellipse([ex * W - K, .29 * H - K, ex * W + K, .29 * H + K], fill=_CINK)
    d.arc([.46 * W, .3 * H, .54 * W, .35 * H], 20, 160, fill=(150, 50, 50, 255), width=K)
    if rank == "K":
        d.polygon([(.4 * W, .335 * H), (.43 * W, .375 * H), (.5 * W, .385 * H), (.57 * W, .375 * H), (.6 * W, .335 * H),
                   (.56 * W, .36 * H), (.5 * W, .37 * H), (.44 * W, .36 * H)], fill=hair, outline=_CINK)
        d.polygon([(.395 * W, .245 * H), (.38 * W, .15 * H), (.44 * W, .2 * H), (.5 * W, .13 * H), (.56 * W, .2 * H),
                   (.62 * W, .15 * H), (.605 * W, .245 * H)], fill=_CGOLD, outline=_CGOLD_D)
        for jx in (.4, .5, .6):
            d.ellipse([jx * W - 1.5 * K, .22 * H - 1.5 * K, jx * W + 1.5 * K, .22 * H + 1.5 * K], fill=_CRED)
    elif rank == "Q":
        d.polygon([(.41 * W, .245 * H), (.4 * W, .17 * H), (.455 * W, .21 * H), (.5 * W, .15 * H), (.545 * W, .21 * H),
                   (.6 * W, .17 * H), (.59 * W, .245 * H)], fill=_CGOLD, outline=_CGOLD_D)
        d.ellipse([.5 * W - 1.5 * K, .2 * H - 1.5 * K, .5 * W + 1.5 * K, .2 * H + 1.5 * K], fill=col)
    else:
        d.pieslice([.38 * W, .15 * H, .62 * W, .31 * H], 180, 360, fill=col, outline=_CINK)
        d.rectangle([.38 * W, .23 * H, .62 * W, .25 * H], fill=_CGOLD, outline=_CGOLD_D)
        d.polygon([(.6 * W, .2 * H), (.74 * W, .12 * H), (.68 * W, .24 * H)], fill=(235, 235, 240, 255), outline=_CINK)
    draw_suit(d, suit, .33 * W, .2 * H, .05 * H)
    return Image.alpha_composite(lay, lay.rotate(180))

@lru_cache(maxsize=None)
def get_card(card):
    """White card, big rank in the middle, small suit in the top-left and bottom-right corners."""
    r, s = card
    K = _CK
    W, H = SW * K, SH * K
    col = SUIT_COLOR[s]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=14 * K, fill=(255, 255, 255, 255),
                        outline=(150, 150, 158, 255), width=2 * K)
    d.text((W * .5, H * .49), r, font=get_font(int(H * (.47 if len(r) == 2 else .62))), fill=col, anchor="mm")
    idx = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    di = ImageDraw.Draw(idx)
    draw_suit(di, s, .18 * W, .14 * H, .075 * H)      # top-left
    draw_suit(di, s, .82 * W, .86 * H, .075 * H)      # bottom-right (upright, so hearts never look like spades)
    im = Image.alpha_composite(im, idx)
    return im.resize((SW, SH), Image.LANCZOS)

@lru_cache(maxsize=1)
def get_back():
    K = _CK
    W, H = SW * K, SH * K
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=9 * K, fill=(255, 255, 255, 255), outline=(170, 170, 176, 255), width=K)
    m = 7 * K
    inner = Image.new("RGBA", (W - 2 * m, H - 2 * m), (150, 24, 44, 255))
    di = ImageDraw.Draw(inner)
    step = 12 * K
    for k in range(-inner.height, inner.width + inner.height, step):
        di.line([(k, 0), (k + inner.height, inner.height)], fill=(215, 90, 105, 255), width=K)
        di.line([(k, inner.height), (k + inner.height, 0)], fill=(215, 90, 105, 255), width=K)
    cx, cy = inner.width / 2, inner.height / 2
    di.ellipse([cx - 16 * K, cy - 16 * K, cx + 16 * K, cy + 16 * K], fill=(150, 24, 44, 255), outline=_CGOLD, width=2 * K)
    di.polygon([(cx, cy - 10 * K), (cx + 7 * K, cy), (cx, cy + 10 * K), (cx - 7 * K, cy)], fill=_CGOLD)
    mask = Image.new("L", inner.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, inner.width - 1, inner.height - 1], radius=5 * K, fill=255)
    im.paste(inner, (m, m), mask)
    return im.resize((SW, SH), Image.LANCZOS)

# --- the 52 cards + the card back become application emojis of the bot (created once, reused after every restart) ---
CARD_EMOJI = {}
CARD_BACK = None

def _emoji_png(card):
    im = get_back() if card is None else get_card(card)
    buf = io.BytesIO()
    im.save(buf, "PNG")    # card-shaped emoji, no empty padding
    return buf.getvalue()

async def setup_card_emojis():
    global CARD_BACK
    try:
        if not hasattr(bot, "create_application_emoji"):
            print("Card emojis need discord.py 2.5 or newer (pip install -U discord.py). Using text cards.")
            return
        allem = await bot.fetch_application_emojis()
        # remove EVERY older card emoji (any previous prefix / version) so stale cards with a different size/shape never get reused
        for e in allem:
            old = e.name.startswith(("c_", "k_", "d_", "p_", "q_")) or (e.name.startswith("bj") and not e.name.startswith(CARD_PREFIX))
            if old:
                try:
                    await e.delete()
                except Exception:
                    pass
                await asyncio.sleep(0.2)
        have = {e.name: e for e in allem if e.name.startswith(CARD_PREFIX)}
        todo = [(None, f"{CARD_PREFIX}back")] + [((r, s), f"{CARD_PREFIX}{r}{SUIT_LETTER[s]}") for r in RANKS for s in SUITS]
        made = 0
        for card, name in todo:
            e = have.get(name)
            if e is None:
                data = await asyncio.to_thread(_emoji_png, card)
                e = await bot.create_application_emoji(name=name, image=data)
                made += 1
                await asyncio.sleep(0.3)
            if card is None:
                CARD_BACK = str(e)
            else:
                CARD_EMOJI[card] = str(e)
        print(f"Card emojis ready ({made} created)")
    except Exception as ex:
        print("Card emojis failed, using text cards:", repr(ex))

def card_text(card):
    return CARD_EMOJI.get(card) or f"**{card[0]}**{SUIT_EMOJI[card[1]]}"

def back_text():
    return CARD_BACK or "❓"

BJ_PLAYING_COLOR = 0xFAD25A   # side-bar color while the game is running (hex, like 0xRRGGBB). Change it if the shade is not exactly the one you want.
CARD_HEADER = ""      # "" = normal inline cards (exactly like the reference screenshots). "## " = bigger, "# " = huge.
BJ_WIDTH = 14         # invisible padding on the title line. MUST stay short: if title + padding is wider than the phone screen it wraps and adds empty lines under the title.

def cards_text(cards):
    return ", ".join(card_text(c) for c in cards)

@lru_cache(maxsize=None)
def get_font(size):
    for name in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()

class BlackjackView(discord.ui.View):
    def __init__(self, user, bet, token=None):
        super().__init__(timeout=120)
        self.user, self.token = user, token
        self.deck = [(r, s) for r in RANKS for s in SUITS]
        random.shuffle(self.deck)
        self.hands = [{"cards": [self.deck.pop(), self.deck.pop()], "bet": bet, "bust": False}]
        self.dealer = [self.deck.pop(), self.deck.pop()]
        self.active = self.net = 0
        self.done = self.split_used = False
        self.message = None
        self.refresh_buttons()

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        if self.done:
            if not interaction.response.is_done():
                await interaction.response.defer()
            return False
        return True

    def refresh_buttons(self):
        cash = user_data(self.user.id)["cash"]
        h = None if self.done else self.hands[self.active]
        two = h is not None and len(h["cards"]) == 2
        self.hit.disabled = self.stand.disabled = self.done
        self.double.disabled = not (two and cash >= h["bet"])
        self.split.disabled = not (two and not self.split_used and cash >= h["bet"]
                                   and card_value(h["cards"][0][0]) == card_value(h["cards"][1][0]))

    def pay(self, returned, staked):
        returned += multi_extra("bj", returned - staked)
        self.done, self.net = True, returned - staked
        pending_done(self.token)
        user_data(self.user.id)["cash"] += returned
        save()
        log_game(self.user, "blackjack", staked, self.net)
        BUSY.discard(self.user.id)
        self.refresh_buttons()

    def check_naturals(self):
        p, d = hand_value(self.hands[0]["cards"]) == 21, hand_value(self.dealer) == 21
        if not (p or d):
            return False
        bet = self.hands[0]["bet"]
        self.pay(bet if p and d else int(bet * 2.5) if p else 0, bet)
        return True

    def dealer_play(self):
        while hand_value(self.dealer) < DEALER_STANDS_ON:
            self.dealer.append(self.deck.pop())

    def player_wins(self):
        dv = hand_value(self.dealer)
        return any(not h["bust"] and (hand_value(h["cards"]) > dv or dv > 21) for h in self.hands)

    def redeal(self):
        up = self.dealer[0]
        self.deck.extend(self.dealer[1:])
        random.shuffle(self.deck)
        self.dealer = [up, self.deck.pop()]
        self.dealer_play()

    def finalize(self):
        if any(not h["bust"] for h in self.hands):
            self.dealer_play()
            if self.player_wins() and random.random() < BJ_WIN_NERF:
                for _ in range(5):
                    self.redeal()
                    if not self.player_wins():
                        break
            for _ in range(luck_attempts(self.user.id) - 1):
                if self.player_wins():
                    break
                self.redeal()
        dv, returned = hand_value(self.dealer), 0
        for h in self.hands:
            pv = hand_value(h["cards"])
            if not h["bust"] and (pv > dv or dv > 21):
                returned += h["bet"] * 2
            elif not h["bust"] and pv == dv:
                returned += h["bet"]
        self.pay(returned, sum(h["bet"] for h in self.hands))

    def render(self):
        """Text-only embed (no image): instant to build and to send.
        Layout (line by line) matches the reference screenshots:
        title / blank / result / Your Hand / cards / blank / Value / Dealer / cards / blank / Value"""
        c, color, head = cur(), discord.Color(BJ_PLAYING_COLOR), None
        if self.done:
            color, head = ((GREEN, f"You Won! +{fmt(self.net)} {c}") if self.net > 0 else
                           (RED, f"You Lost! -{fmt(-self.net)} {c}") if self.net < 0 else
                           (YELLOW, f"Push! +0 {c}"))
        lines = ["🃏 **Blackjack** 🃏" + "⠀" * BJ_WIDTH, ""] + ([f"**{head}**"] if head else [])
        multi = len(self.hands) > 1
        for i, h in enumerate(self.hands):
            mark = " ◀" if multi and not self.done and i == self.active else ""
            if i:
                lines.append("")
            lines.append(f"**Your Hand{f' {i + 1}' if multi else ''}**{mark}")
            lines.append(CARD_HEADER + cards_text(h["cards"]))
            lines += ["", f"Value: **{hand_value(h['cards'])}**"]
        if self.done:
            dealer_cards, dealer_val = cards_text(self.dealer), hand_value(self.dealer)
        else:
            dealer_cards, dealer_val = f"{card_text(self.dealer[0])}, {back_text()}", card_value(self.dealer[0][0])
        lines += ["**Dealer**", CARD_HEADER + dealer_cards, "", f"Value: **{dealer_val}**"]
        e = discord.Embed(description="\n".join(lines), color=color)
        e.set_author(name=f"{self.user.name}'s Game", icon_url=self.user.display_avatar.url)
        return e

    async def update(self, interaction):
        self.refresh_buttons()
        e = self.render()
        # answer the click directly with the new message: no defer, no upload = instant
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=e, view=self)
        else:
            await interaction.edit_original_response(embed=e, view=self)

    async def advance(self, interaction):
        self.active += 1
        if self.active >= len(self.hands):
            self.active = len(self.hands) - 1
            self.finalize()
            self.stop()
        await self.update(interaction)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction, button):
        h = self.hands[self.active]
        h["cards"].append(self.deck.pop())
        v = hand_value(h["cards"])
        h["bust"] = v > 21
        await (self.advance if v >= 21 else self.update)(interaction)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.success)
    async def stand(self, interaction, button):
        await self.advance(interaction)

    @discord.ui.button(label="Double", style=discord.ButtonStyle.danger)
    async def double(self, interaction, button):
        u, h = user_data(self.user.id), self.hands[self.active]
        if len(h["cards"]) != 2 or u["cash"] < h["bet"]:
            return await interaction.response.send_message("You can't double right now.", ephemeral=True)
        u["cash"] -= h["bet"]
        pending_bump(self.token, h["bet"])
        save()
        h["bet"] *= 2
        h["cards"].append(self.deck.pop())
        h["bust"] = hand_value(h["cards"]) > 21
        await self.advance(interaction)

    @discord.ui.button(label="Split", style=discord.ButtonStyle.secondary)
    async def split(self, interaction, button):
        u, h = user_data(self.user.id), self.hands[self.active]
        if self.split_used or len(h["cards"]) != 2 or u["cash"] < h["bet"]:
            return await interaction.response.send_message("You can't split right now.", ephemeral=True)
        u["cash"] -= h["bet"]
        pending_bump(self.token, h["bet"])
        save()
        self.hands = [{"cards": [c, self.deck.pop()], "bet": h["bet"], "bust": False} for c in h["cards"]]
        self.split_used, self.active = True, 0
        await self.update(interaction)

    async def on_timeout(self):
        if self.done:
            return
        for h in self.hands:
            h["bust"] = hand_value(h["cards"]) > 21
        self.finalize()
        if self.message:
            await self.message.edit(embed=self.render(), view=self)

@bot.command(name="bj", aliases=["blackjack"], usage="bj <amount | half | all>")
async def bj(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "bj <amount | half | all>", track=True)
    if not bet:
        return
    BUSY.add(ctx.author.id)
    view = BlackjackView(ctx.author, bet, str(ctx.message.id))
    try:
        natural = view.check_naturals()
        msg = await ctx.send(embed=view.render(), view=view)
    except Exception:
        if not view.done:
            cancel_game(ctx.author, view.token, bet)
        BUSY.discard(ctx.author.id)
        raise
    if not natural:
        view.message = msg
