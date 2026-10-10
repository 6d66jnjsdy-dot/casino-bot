import discord, random
from collections import Counter
from core import *
# !!! שנה את "blackjack" לשם האמיתי של הקובץ שבו נמצא קוד הבלאק ג'ק שלך (הוא לא משתנה, רק מייבאים ממנו את הקלפים)
from blackjack import card_text, RANKS, SUITS, SUIT_EMOJI

# ================= 5-CARD DRAW POKER =================
MAX_DRAWS = 2                 # כמה פעמים אפשר להחליף קלפים
POKER_SEP = " "               # מה בין הקלפים. " " = כמו בתמונות שלך, ", " = כמו בבלאק ג'ק
POKER_PLAYING_COLOR = 0x4A90D9  # הפס הכחול בזמן משחק
POKER_START_BOOST = 0.35      # סיכוי (לכל ניסיון, עד 2 ניסיונות) לחלק יד פתיחה חדשה אם היא בלי זוג. מעלה את סיכוי הזוג+ ביד ההתחלתית מ-50% לכ-62%
POKER_WIN_NERF = 0.10         # כשהשחקן ניצח, סיכוי לתת לדילר יד חדשה (עד 2 ניסיונות). מוריד/מעלה את אחוזי הניצחון הכללי
POKER_BONUS = {               # בונוס על הניצחון (פעמים ההימור) לפי סוג יד. 1x הבסיס תמיד. מחק שורה = אין בונוס
    4: 0.25,   # straight
    5: 0.50,   # flush
    6: 0.75,   # full house
    7: 2.0,    # four of a kind
    8: 4.0,    # straight flush
    9: 9.0,    # royal flush
}

RV = {r: i for i, r in enumerate(["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"], 2)}
FULL_DECK = [(r, s) for r in RANKS for s in SUITS]
_LOG_FILE = "poker_log.txt"

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

def evaluate(cards):
    """Returns (category, tiebreakers). 0 high card, 1 pair, 2 two pair, 3 trips, 4 straight,
    5 flush, 6 full house, 7 quads, 8 straight flush. Higher tuple = better hand."""
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
    """Basic draw-poker strategy: which positions the dealer throws away."""
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
        self.deck = list(FULL_DECK)
        random.shuffle(self.deck)
        self.hand = self.deal_start()
        self.dealer = []
        self.selected = set()
        self.draws_left = MAX_DRAWS
        self.done = False
        self.net = 0
        self.message = None
        self.rebuild()

    def deal_start(self):
        hand = None
        for attempt in range(3):
            deck = list(FULL_DECK)
            random.shuffle(deck)
            hand = deck[:5]
            self.deck = deck[5:]
            # יד פתיחה בלי זוג: לפעמים מחלקים מחדש (לא תמיד, כדי לא להגזים)
            if evaluate(hand)[0] >= 1 or random.random() >= POKER_START_BOOST:
                break
        return hand

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
        deck = [c for c in FULL_DECK if c not in self.hand]
        random.shuffle(deck)
        hand = deck[:5]
        deck = deck[5:]
        for rnd in range(2):
            if rnd == 1 and evaluate(hand)[0] >= 1:     # סיבוב שני רק אם עדיין אין כלום
                break
            for i in dealer_discards(hand):
                hand[i] = deck.pop()
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
        for i in self.selected:
            self.hand[i] = self.deck.pop()
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


# נדרש כדי ש-core יוכל לטעון את הקובץ עם bot.load_extension("poker")
async def setup(bot):
    pass
