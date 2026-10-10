import discord, random, sys
from collections import Counter
from core import *

# ================= 5-CARD DRAW POKER =================
MAX_DRAWS = 2                   # כמה פעמים אפשר להחליף קלפים
POKER_SEP = " "                 # מה בין הקלפים. " " = כמו בתמונות שלך, ", " = כמו בבלאק ג'ק
POKER_PLAYING_COLOR = 0x4A90D9  # הפס הכחול בזמן משחק
POKER_WIN_NERF = 0.05           # כשהשחקן ניצח, סיכוי לתת לדילר יד חדשה (עד 2 ניסיונות). גבוה יותר = הבית מנצח יותר
POKER_BONUS = {}                # בונוס על ניצחון עם יד חזקה (פעמים ההימור), למשל {7: 2.0, 8: 4.0}. ריק = אין בונוסים, רק 1:1

# ---- האחוזים שביקשת (משקלים יחסיים, הקוד מנרמל אותם ל-100%) ----
# 0 קלף גבוה | 1 זוג | 2 שני זוגות | 3 שלשה | 4 רצף | 5 צבע | 6 פול האוס | 7 רביעייה | 8 רצף צבע
START_W = {0: 51.1, 1: 39.1, 2: 13, 3: 8, 4: 2, 5: 1.6, 6: 1.2, 7: 1, 8: 0.5}   # יד ההתחלה
FINAL_W = {0: 15, 1: 47, 2: 35, 3: 14, 4: 6.5, 5: 5, 6: 5, 7: 4, 8: 3}            # אחרי החלפות
# הדילר משתמש באותם אחוזים בדיוק, כדי שהמשחק יישאר הוגן (בערך 50/50)

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♣", "♠", "♥", "♦"]
SUIT_EMOJI = {"♣": "♣️", "♠": "♠️", "♥": "♥️", "♦": "♦️"}
RV = {r: i for i, r in enumerate(["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"], 2)}
VR = {v: r for r, v in RV.items()}
FULL_DECK = [(r, s) for r in RANKS for s in SUITS]
_LOG_FILE = "poker_log.txt"

# ---------- הקלפים: לוקח אותם מקובץ הבלאק ג'ק לבד (בלי לדעת את שם הקובץ), בלי לשנות אותו ----------
_BJ = None

def _bj():
    global _BJ
    if _BJ is None:
        for m in list(sys.modules.values()):
            try:
                if m is not None and m.__name__ != __name__ and hasattr(m, "card_text") and hasattr(m, "CARD_EMOJI"):
                    _BJ = m
                    break
            except Exception:
                pass
    return _BJ

def card_text(card):
    m = _bj()
    if m is not None:
        return m.card_text(card)
    return f"**{card[0]}**{SUIT_EMOJI[card[1]]}"

def next_log():
    try:
        with open(_LOG_FILE) as f:
            n = int(f.read().strip())
    except Exception:
        n = 3000
    n += 1
    try:
        with open(_LOG_FILE, "w") as f:
            f.write(str(n))
    except Exception:
        pass
    return n

# ---------- דירוג יד ----------
def evaluate(cards):
    """(category, tiebreakers). Higher tuple = better hand."""
    vals = sorted((RV[r] for r, _ in cards), reverse=True)
    flush = len({s for _, s in cards}) == 1
    uniq = sorted(set(vals), reverse=True)
    straight_high = 0
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight_high = uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:
            straight_high = 5
    groups = sorted(Counter(vals).items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    shape, order = [c for _, c in groups], [v for v, _ in groups]
    if straight_high and flush:
        return (8, [straight_high])
    if shape[0] == 4:
        return (7, order)
    if shape == [3, 2]:
        return (6, order)
    if flush:
        return (5, vals)
    if straight_high:
        return (4, [straight_high])
    if shape[0] == 3:
        return (3, order)
    if shape == [2, 2, 1]:
        return (2, order)
    if shape[0] == 2:
        return (1, order)
    return (0, vals)

def _straight_draw(vals):
    u = sorted(set(vals))
    if len(u) != 4:
        return False
    if u[-1] - u[0] <= 4:
        return True
    low = sorted(1 if v == 14 else v for v in u)
    return low[-1] - low[0] <= 4

def dealer_discards(cards):
    """Basic draw-poker strategy: which positions to throw away."""
    cat, _ = evaluate(cards)
    vals = [RV[r] for r, _ in cards]
    cnt = Counter(vals)
    if cat >= 4:
        return []
    if cat in (1, 2, 3, 7):
        keep = {v for v, c in cnt.items() if c >= 2}
        return [i for i, v in enumerate(vals) if v not in keep]
    suits = Counter(s for _, s in cards)
    s4 = next((s for s, c in suits.items() if c == 4), None)
    if s4:
        return [i for i, (_, s) in enumerate(cards) if s != s4]
    for i in range(5):
        if _straight_draw([v for j, v in enumerate(vals) if j != i]):
            return [i]
    top = sorted(range(5), key=lambda i: vals[i], reverse=True)[:2]
    return [i for i in range(5) if i not in top]

# ---------- יצירת ידיים לפי האחוזים ----------
def _pick_cat(weights):
    return random.choices(list(weights), weights=list(weights.values()))[0]

def _build(cat):
    rk = lambda n: random.sample(RANKS, n)
    ss = lambda n: random.sample(SUITS, n)
    rs = lambda: random.choice(SUITS)
    if cat == 0:
        return [(r, rs()) for r in rk(5)]
    if cat == 1:
        a, b, c, d = rk(4)
        return [(a, s) for s in ss(2)] + [(x, rs()) for x in (b, c, d)]
    if cat == 2:
        a, b, c = rk(3)
        return [(a, s) for s in ss(2)] + [(b, s) for s in ss(2)] + [(c, rs())]
    if cat == 3:
        a, b, c = rk(3)
        return [(a, s) for s in ss(3)] + [(b, rs()), (c, rs())]
    if cat in (4, 8):
        top = random.randint(5, 14)
        vals = [14, 5, 4, 3, 2] if top == 5 else [top - i for i in range(5)]
        suit = rs()
        return [(VR[v], suit if cat == 8 else rs()) for v in vals]
    if cat == 5:
        suit = rs()
        return [(r, suit) for r in rk(5)]
    if cat == 6:
        a, b = rk(2)
        return [(a, s) for s in ss(3)] + [(b, s) for s in ss(2)]
    a, b = rk(2)
    return [(a, s) for s in SUITS] + [(b, rs())]

def make_hand(cat, avoid=()):
    avoid = set(avoid)
    for _ in range(300):
        h = _build(cat)
        if len(set(h)) == 5 and not (set(h) & avoid) and evaluate(h)[0] == cat:
            random.shuffle(h)
            return h
    d = [c for c in FULL_DECK if c not in avoid]
    random.shuffle(d)
    return d[:5]

def biased_draw(hand, idxs, out):
    """Replace the cards at idxs. The result aims at a category taken from FINAL_W
    (it can only get as close as the cards you kept allow)."""
    target = _pick_cat(FINAL_W)
    pool = [c for c in FULL_DECK if c not in out]
    best, best_key = None, None
    for _ in range(150):
        new = list(hand)
        for i, c in zip(idxs, random.sample(pool, len(idxs))):
            new[i] = c
        cat = evaluate(new)[0]
        if cat == target:
            return new
        key = (abs(cat - target), cat > target)
        if best_key is None or key < best_key:
            best, best_key = new, key
    return best

class _Btn(discord.ui.Button):
    def __init__(self, handler, **kw):
        super().__init__(**kw)
        self.handler = handler

    async def callback(self, interaction):
        await self.handler(interaction)

class PokerView(discord.ui.View):
    def __init__(self, user, bet, token=None):
        super().__init__(timeout=120)
        self.user, self.bet, self.token = user, bet, token
        self.log = next_log()
        self.hand = make_hand(_pick_cat(START_W))
        self.out = set(self.hand)          # קלפים שכבר יצאו (לא יחזרו)
        self.dealer = []
        self.selected = set()
        self.draws_left = MAX_DRAWS
        self.done = False
        self.net = 0
        self.message = None
        self.rebuild()

    # ---------- buttons ----------
    def rebuild(self):
        self.clear_items()
        for i, (r, s) in enumerate(self.hand):
            self.add_item(_Btn(lambda inter, ix=i: self.toggle(inter, ix), label=r, emoji=SUIT_EMOJI[s], row=0,
                               style=discord.ButtonStyle.primary if i in self.selected else discord.ButtonStyle.secondary,
                               disabled=self.done))
        self.add_item(_Btn(self.do_draw, label="Draw", style=discord.ButtonStyle.primary, row=1, disabled=self.done))
        self.add_item(_Btn(self.do_finish, label="Finish", style=discord.ButtonStyle.danger, row=1, disabled=self.done))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        if self.done:
            if not interaction.response.is_done():
                await interaction.response.defer()
            return False
        return True

    # ---------- game logic ----------
    def make_dealer(self):
        hand = make_hand(_pick_cat(START_W), avoid=self.hand)
        out = set(self.hand) | set(hand)
        for rnd in range(2):
            if rnd == 1 and evaluate(hand)[0] >= 1:
                break
            idx = dealer_discards(hand)
            if not idx:
                break
            hand = biased_draw(hand, idx, out)
            out |= set(hand)
        return hand

    def player_wins(self):
        return evaluate(self.hand) > evaluate(self.dealer)      # אין תיקו: תיקו מוחלט = הבית

    def pay(self, returned, staked):
        if returned > staked:
            try:
                returned += multi_extra("poker", returned - staked)
            except Exception:
                pass
        self.done, self.net = True, returned - staked
        pending_done(self.token)
        user_data(self.user.id)["cash"] += returned
        save()
        log_game(self.user, "poker", staked, self.net)
        BUSY.discard(self.user.id)

    def finish(self):
        self.dealer = self.make_dealer()
        if self.player_wins() and random.random() < POKER_WIN_NERF:
            for _ in range(2):
                self.dealer = self.make_dealer()
                if not self.player_wins():
                    break
        for _ in range(luck_attempts(self.user.id) - 1):
            if self.player_wins():
                break
            self.dealer = self.make_dealer()
        returned = 0
        if self.player_wins():
            cat, tb = evaluate(self.hand)
            key = 9 if cat == 8 and tb[0] == 14 else cat
            returned = self.bet * 2 + int(self.bet * POKER_BONUS.get(key, 0))
        self.pay(returned, self.bet)
        self.selected = set()
        self.rebuild()
        self.stop()

    # ---------- message ----------
    def render(self):
        c = cur()
        if self.done:
            color = GREEN if self.net > 0 else RED
            head = f"You Won! +{fmt(self.net)} {c}" if self.net > 0 else f"You Lost! -{fmt(-self.net)} {c}"
        else:
            color = discord.Color(POKER_PLAYING_COLOR)
            head = f"Click on cards to swap (max {MAX_DRAWS} times). Draws left: {self.draws_left}"
        lines = ["**5-Card Draw Poker**", "", head, "", "**Your Hand**", POKER_SEP.join(card_text(x) for x in self.hand)]
        if self.done:
            lines += ["", "**Dealer Hand**", POKER_SEP.join(card_text(x) for x in self.dealer)]
        e = discord.Embed(description="\n".join(lines), color=color)
        e.set_author(name=f"{self.user.name}'s Game", icon_url=self.user.display_avatar.url)
        e.set_footer(text=f"Poker Log: {self.log}")
        return e

    async def update(self, interaction):
        self.rebuild()
        e = self.render()
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=e, view=self)
        else:
            await interaction.edit_original_response(embed=e, view=self)

    # ---------- clicks ----------
    async def toggle(self, interaction, ix):
        self.selected ^= {ix}
        await self.update(interaction)

    async def do_draw(self, interaction):
        if not self.selected:
            return await interaction.response.send_message("Click on the cards you want to swap first.", ephemeral=True)
        idxs = sorted(self.selected)
        self.hand = biased_draw(self.hand, idxs, self.out)
        self.out |= set(self.hand)
        self.selected = set()
        self.draws_left -= 1
        if self.draws_left <= 0:
            self.finish()
        await self.update(interaction)

    async def do_finish(self, interaction):
        self.finish()
        await self.update(interaction)

    async def on_timeout(self):
        if self.done:
            return
        self.finish()
        if self.message:
            await self.message.edit(embed=self.render(), view=self)

@bot.command(name="poker", usage="poker <amount | half | all>")
async def poker(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "poker <amount | half | all>", track=True)
    if not bet:
        return
    BUSY.add(ctx.author.id)
    view = PokerView(ctx.author, bet, str(ctx.message.id))
    try:
        msg = await ctx.send(embed=view.render(), view=view)
    except Exception:
        cancel_game(ctx.author, view.token, bet)
        BUSY.discard(ctx.author.id)
        raise
    view.message = msg

print("poker.py IMPORTED - $poker command registered:", bot.get_command("poker"))

# ---------- דיבאג זמני: מוחקים את הבלוק הזה כשהפוקר עובד ----------
@bot.listen("on_message")
async def _poker_debug(message):
    if message.author.bot or not message.content.lower().startswith("$poker"):
        return
    try:
        ctx = await bot.get_context(message)
        try:
            ok = await bot.can_run(ctx)
        except Exception as ex:
            ok = f"CHECK FAILED: {ex!r}"
        print("POKER DEBUG | saw the message | command found:", ctx.command, "| valid:", ctx.valid,
              "| checks pass:", ok, "| channel allowed:", message.channel.id in ALLOWED_CHANNELS,
              "| disabled:", "poker" in DB.get("disabled", []), "| in BUSY:", message.author.id in BUSY)
    except Exception as ex:
        print("POKER DEBUG error:", repr(ex))

# נדרש כדי ש-core יוכל לטעון את הקובץ עם bot.load_extension("poker")
async def setup(bot):
    print("poker.py loaded OK - $poker is ready")
