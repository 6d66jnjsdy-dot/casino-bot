"""game_holdem.py - Texas Hold'em, 2-6 players, clean embed design.

Usage:  $texas <amount>     (amount is required; everyone at the table pays the same amount to sit down)
Needs 'game_holdem' in MODULES in main.py, after 'game_blackjack' (card emojis come from there).
"""
import asyncio
import itertools
import random
import sys
import time
import traceback
from collections import Counter

import discord

# ============================================================
#  CONSTANTS
# ============================================================
MAX_PLAYERS = 6
MIN_BUYIN = MIN_BET          # from core
TURN_SECONDS = 45
NEXT_HAND_DELAY = 15         # time between hands: players can press Leave during it
CASHOUT_SECONDS = 120        # the last player standing has this long to press Cash out (then it is automatic)
START_BB = 1_000_000         # starting big blind (small blind is half of it)
LEVEL_HANDS = 5              # blinds go up every this many hands
BLIND_LEVELS = (1, 1.5, 2, 3, 4, 6, 8, 12, 16, 24, 32)   # multipliers of the starting big blind
HDR_BOARD = "## "           # board cards are shown big ("# " = huge, "" = normal size)
HDR_HAND = "# "             # your two cards in My Cards
LOBBY_SECONDS = 600          # an open table that nobody starts closes after this
COLOR = 0xB19CD9             # soft purple side bar (change this one line to recolor everything)
GOLD = 0xF1C40F              # gold side bar, used when the money goes back to cash

SYM = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
RANKS = "23456789TJQKA"
SING = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine",
        10: "Ten", 11: "Jack", 12: "Queen", 13: "King", 14: "Ace"}
PLUR = {2: "Twos", 3: "Threes", 4: "Fours", 5: "Fives", 6: "Sixes", 7: "Sevens", 8: "Eights",
        9: "Nines", 10: "Tens", 11: "Jacks", 12: "Queens", 13: "Kings", 14: "Aces"}

GAME_NAMES["holdem"] = "Texas Hold'em"      # nice name in the game log

REFUND_TEXT = "**Everyone got their money back to cash.**"
PING = discord.AllowedMentions(users=True, everyone=False, roles=False)


# ---------- economy (uses core: user_data / save / pending) ----------
async def cash_get(uid):
    return user_data(uid)["cash"]


async def cash_add(uid, amount):
    user_data(uid)["cash"] += amount
    save()


def _track(p):
    """Chips on the table are stored as a 'pending' game, so a restart refunds them to cash."""
    DB.setdefault("pending", {})[p.token] = {"uid": str(p.user.id), "bet": p.stack}
    save()


def _short(n):
    for v, u in ((10 ** 9, "B"), (10 ** 6, "M"), (10 ** 4, "K")):
        if n >= v:
            return f"{n / v:.2f}".rstrip("0").rstrip(".") + u
    return f"{n:,}"


# ---------- cards (the blackjack card emojis, read live because they are created after the bot starts) ----------
_BJ_RANK = {11: "J", 12: "Q", 13: "K", 14: "A"}
_BJ_SUIT = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}


def cs(card):
    r, s = card
    bj = sys.modules.get("game_blackjack")
    if bj:
        e = bj.CARD_EMOJI.get((_BJ_RANK.get(r, str(r)), _BJ_SUIT[s]))
        if e:
            return e
    return f"`{'10' if r == 10 else RANKS[r - 2]}{SYM[s]}`"


def card_back():
    bj = sys.modules.get("game_blackjack")
    return (bj.CARD_BACK if bj and bj.CARD_BACK else None) or "🂠"


def cards_str(cards, total=None):
    out = [cs(c) for c in cards]
    if total:
        out += [card_back()] * (total - len(cards))
    return " ".join(out) if out else "—"


# ============================================================
#  Hand evaluation (best 5 of 7)
# ============================================================
def score5(cards):
    ranks = sorted((r for r, _ in cards), reverse=True)
    groups = sorted(Counter(ranks).items(), key=lambda x: (x[1], x[0]), reverse=True)
    flush = len({s for _, s in cards}) == 1
    uniq = sorted(set(ranks), reverse=True)
    high = 0
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            high = uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:
            high = 5
    if high and flush:
        return (8, high)
    if groups[0][1] == 4:
        return (7, groups[0][0], groups[1][0])
    if groups[0][1] == 3 and groups[1][1] == 2:
        return (6, groups[0][0], groups[1][0])
    if flush:
        return (5, *ranks)
    if high:
        return (4, high)
    if groups[0][1] == 3:
        return (3, groups[0][0], *[g[0] for g in groups[1:]])
    if groups[0][1] == 2 and groups[1][1] == 2:
        return (2, groups[0][0], groups[1][0], groups[2][0])
    if groups[0][1] == 2:
        return (1, groups[0][0], *[g[0] for g in groups[1:]])
    return (0, *ranks)


def best_score(cards):
    return max(score5(c) for c in itertools.combinations(cards, 5))


def hand_name(sc):
    c = sc[0]
    if c == 8:
        return "Royal Flush" if sc[1] == 14 else f"Straight Flush, {SING[sc[1]]} high"
    if c == 7:
        return f"Four of a Kind, {PLUR[sc[1]]}"
    if c == 6:
        return f"Full House, {PLUR[sc[1]]} full of {PLUR[sc[2]]}"
    if c == 5:
        return f"Flush, {SING[sc[1]]} high"
    if c == 4:
        return f"Straight, {SING[sc[1]]} high"
    if c == 3:
        return f"Three of a Kind, {PLUR[sc[1]]}"
    if c == 2:
        return f"Two Pair, {PLUR[sc[1]]} and {PLUR[sc[2]]}"
    if c == 1:
        return f"Pair of {PLUR[sc[1]]}"
    return f"High Card, {SING[sc[1]]}"


# what each hand means (shown in My Cards)
HAND_INFO = {
    0: "No pair yet. Only your highest card counts.",
    1: "Beats High Card. Loses to Two Pair or better.",
    2: "Beats One Pair. Loses to Three of a Kind or better.",
    3: "Beats Two Pair. Loses to a Straight or better.",
    4: "Five cards in a row. Beats Three of a Kind.",
    5: "Five cards of the same suit. Beats a Straight.",
    6: "Three of a kind plus a pair. Beats a Flush.",
    7: "Four of the same rank. Only a Straight Flush beats it.",
    8: "The strongest hand there is.",
}


def _draws(cards):
    """Draw hints (only before the river)."""
    out = []
    suits = Counter(s for _, s in cards)
    if max(suits.values()) == 4:
        out.append("🃏 **Flush draw:** 4 cards of one suit, one more makes a Flush.")
    rs = {r for r, _ in cards}
    if 14 in rs:
        rs.add(1)
    if any(len(rs & set(range(a, a + 5))) == 4 for a in range(1, 11)):
        out.append("🃏 **Straight draw:** 4 cards in a row, one more makes a Straight.")
    return out


def explain(hole, board):
    """Full text for My Cards: what you have right now and what it means."""
    if not board:
        a, b = sorted((hole[0][0], hole[1][0]), reverse=True)
        if a == b:
            return [f"### Pocket {PLUR[a]}", "A pair already in your hand. It only gets better from here."]
        suited = hole[0][1] == hole[1][1]
        title = f"### {SING[a]} and {SING[b]}" + (" (suited)" if suited else "")
        notes = ["No pair yet. Pair one of your cards with the board to make a hand."]
        if suited:
            notes.append("Same suit: you can build a Flush.")
        if a - b == 1:
            notes.append("Cards next to each other: you can build a Straight.")
        return [title] + notes
    cards = hole + list(board)
    sc = best_score(cards)
    cat = sc[0]
    lines = [f"### {hand_name(sc)}", HAND_INFO[cat]]
    mine = Counter(r for r, _ in hole)
    if cat == 1:
        n = mine.get(sc[1], 0)
        if n == 2:
            lines.append("**Pocket pair:** both cards are yours.")
        elif n == 1:
            lines.append("**You hit the board:** one card is yours, one is on the table.")
        else:
            lines.append("**The pair is on the table.** Everyone shares it, so the kicker decides.")
    elif cat == 2:
        n = mine.get(sc[1], 0) + mine.get(sc[2], 0)
        if n == 0:
            lines.append("**Both pairs are on the table.** Everyone shares them.")
        else:
            lines.append("**Your cards are part of it:** this hand is yours, not just the table's.")
    elif cat == 3:
        n = mine.get(sc[1], 0)
        if n == 2:
            lines.append("**Set:** pocket pair plus one on the table. Strong and hidden.")
        elif n == 1:
            lines.append("**Trips:** one card is yours, two are on the table.")
        else:
            lines.append("**All three are on the table.** Everyone shares them.")
    elif cat == 0:
        lines.append(f"Your best card: **{SING[max(r for r, _ in hole)]}**.")
    if len(board) < 5 and cat < 5:
        lines += _draws(cards)
    return lines


# ============================================================
#  Table state
# ============================================================
TABLES = {}  # channel id -> Table


def closed_embed(text, color=COLOR):
    return discord.Embed(description=f"## ♠ Texas Hold'em\n-# poker\n\n{text}", color=color)


def refund_embed(text=REFUND_TEXT):
    """Gold embed shown whenever the table closes and the money goes back to cash."""
    return closed_embed(text, GOLD)


async def _view_error(inter, error):
    """Never fail silently: print the traceback and tell the player what went wrong."""
    traceback.print_exception(type(error), error, error.__traceback__)
    try:
        msg = f"Something went wrong: `{error!r}`"
        if inter.response.is_done():
            await inter.followup.send(msg, ephemeral=True)
        else:
            await inter.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


async def _say(inter, text):
    """Ephemeral reply that works whether or not the interaction was already acknowledged."""
    if inter.response.is_done():
        await inter.followup.send(text, ephemeral=True)
    else:
        await inter.response.send_message(text, ephemeral=True)


def _busy(uid, on):
    """Uses the bot's own BUSY set, so a seated player cannot start other games (same limit as every other game)."""
    try:
        (BUSY.add if on else BUSY.discard)(uid)
    except NameError:
        pass


def _is_busy(uid):
    try:
        return uid in BUSY
    except NameError:
        return False


class Player:
    def __init__(self, user, stack, token):
        self.user = user
        self.stack = stack
        self.buyin = stack
        self.token = token
        self.leaving = False
        self.left = False
        self.reset_hand()

    def reset_hand(self):
        self.hole = []
        self.bet = 0
        self.total = 0
        self.folded = False
        self.allin = False
        self.acted = False

    @property
    def name(self):
        return self.user.display_name


class Table:
    def __init__(self, channel, host, buyin):
        self.channel, self.host, self.buyin = channel, host, buyin
        self.base_bb = START_BB                 # starting big blind (fixed)
        self.bb = self.base_bb
        self.sb = max(1, self.bb // 2)
        self.players = []
        self.state = "lobby"
        self.message = None
        self.ping_msg = None                    # the "your turn" / "winner" tag message
        self.lock = asyncio.Lock()
        self.dealer = -1
        self.hand_no = 0
        self.in_hand = False
        self.closed = False
        self.board, self.deck = [], []
        self.street = "preflop"
        self.cur = 0
        self.current_bet = 0
        self.min_raise = self.bb
        self.log = ""
        self.timer = None
        self.turn_id = 0
        self.sb_p = self.bb_p = None
        self.expires = int(time.time()) + LOBBY_SECONDS

    def player_of(self, uid):
        return next((p for p in self.players if p.user.id == uid and not p.left), None)

    def nope(self, uid):
        """Text for someone who is not (or no longer) seated."""
        if any(p.user.id == uid and p.left for p in self.players):
            return "You left this table."
        return "You're not seated at this table."

    def _set_blinds(self):
        """Blind level for the current hand (goes up every LEVEL_HANDS hands, never down)."""
        lvl = min((self.hand_no - 1) // LEVEL_HANDS, len(BLIND_LEVELS) - 1)
        bb = max(self.bb, max(2, round(self.base_bb * BLIND_LEVELS[lvl])))
        up = bb > self.bb
        self.bb, self.sb = bb, max(1, bb // 2)
        return up

    def can_raise(self, p):
        """A raise is only possible if the player has chips beyond the current bet AND someone can still respond."""
        others = [o for o in self.players if o is not p and not o.folded and not o.allin]
        return bool(others) and p.bet + p.stack > self.current_bet

    # ---------------- tag messages (these are the ones that actually notify people) ----------------
    async def _clear_ping(self):
        old, self.ping_msg = self.ping_msg, None
        if old:
            try:
                await old.delete()
            except discord.HTTPException:
                pass

    async def _ping(self, text):
        """Replace the old tag message with a new one (a new message is what sends the notification)."""
        await self._clear_ping()
        try:
            self.ping_msg = await self.channel.send(text, allowed_mentions=PING)
        except discord.HTTPException:
            traceback.print_exc()

    # ---------------- embeds ----------------
    def lobby_embed(self, started=False):
        n = len(self.players)
        c = cur()
        lines = ["## ♠ Texas Hold'em", "-# poker",
                 f"**Buy-in** {self.buyin:,} {c}  ·  **Blinds** {self.sb:,}/{self.bb:,} {c}",
                 f"-# Blinds go up every {LEVEL_HANDS} hands", ""]
        for p in self.players:
            lines.append(f"{'👑' if p.user.id == self.host.id else '🔹'} {p.user.mention}")
        lines.append("")
        if started:
            lines.append(f"{n}/{MAX_PLAYERS} seated  ·  **game started, good luck!**")
        else:
            status = "waiting for players" if n < 2 else "ready, the host can press **Start**"
            lines.append(f"{n}/{MAX_PLAYERS} seated  ·  {status}  ·  closes <t:{self.expires}:R>")
        e = discord.Embed(description="\n".join(lines), color=COLOR)
        e.set_footer(text="holdem v4")
        return e

    def _seat(self, i):
        """One player's spot at the table: only the name, an arrow for whose turn it is, and small tags."""
        p = self.players[i]
        active = self.in_hand and i == self.cur
        tags = [t for t, hit in (("D", i == self.dealer % len(self.players)), ("SB", p is self.sb_p), ("BB", p is self.bb_p)) if hit]
        if p.allin and not p.folded:
            tags.append("ALL-IN")
        tag = f" `{'/'.join(tags)}`" if tags else ""
        if p.left:
            return f"🚪 ~~{p.name}~~"
        if p.folded:
            return f"❌ ~~{p.name}~~{tag}"
        if active:
            return f"▶️ **{p.user.mention}**{tag}"
        return f"🔹 {p.user.mention}{tag}"

    def table_embed(self):
        c = cur()
        pot = sum(p.total for p in self.players)
        n = len(self.players)
        half = (n + 1) // 2
        top = [self._seat(i) for i in range(half)]                    # one side of the table
        bottom = [self._seat(i) for i in range(n - 1, half - 1, -1)]  # the other side (goes around the table)
        lines = ["   ".join(top), "",
                 f"{HDR_BOARD}{cards_str(self.board, 5)}",
                 f"**{self.street.capitalize()}**  ·  💰 Pot **{pot:,}** {c}", ""]
        if bottom:
            lines += ["   ".join(bottom), ""]
        if self.in_hand:
            act = self.players[self.cur]
            to_call = max(0, self.current_bet - act.bet)
            lines.append(f"### ➡️ {act.user.mention}  " + (f"**{min(to_call, act.stack):,}** to call" if to_call else "**check** or bet"))
        if self.log:
            lines.append(f"-# {self.log}")
        e = discord.Embed(color=COLOR, description="\n".join(lines))
        e.set_footer(text=f"Hand #{self.hand_no}  ·  Blinds {self.sb:,}/{self.bb:,}  ·  {TURN_SECONDS}s per turn")
        return e

    async def post(self, embed, view):
        """Send the table message the first time, edit it afterwards."""
        try:
            if self.message is None:
                self.message = await self.channel.send(embed=embed, view=view)
            else:
                await self.message.edit(embed=embed, view=view)
        except discord.HTTPException:
            traceback.print_exc()

    async def render(self):
        await self.post(self.table_embed(), TableView(self) if self.in_hand else None)

    # ---------------- chips ----------------
    def _put(self, p, amt):
        amt = max(0, min(amt, p.stack))
        p.stack -= amt
        p.bet += amt
        p.total += amt
        if p.stack == 0:
            p.allin = True

    async def cashout(self, p, log=True):
        pending_done(p.token)
        if p.stack > 0:
            await cash_add(p.user.id, p.stack)
        _busy(p.user.id, False)             # free again: can play other games
        if log:
            log_game(p.user, "holdem", p.buyin, p.stack - p.buyin)

    def seat(self, user):
        p = Player(user, self.buyin, f"holdem:{self.channel.id}:{user.id}")
        self.players.append(p)
        _busy(user.id, True)                # seated = in an active game
        _track(p)
        return p

    # ---------------- hand flow ----------------
    async def start_hand(self):
        self.players = [p for p in self.players if p.stack > 0]
        if len(self.players) < 2:
            return await self.end_game()
        if self.message is not None:        # take the buttons off the finished hand's message
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass
        n = len(self.players)
        self.hand_no += 1
        blinds_up = self._set_blinds()
        for p in self.players:
            p.reset_hand()
        self.dealer = (self.dealer + 1) % n
        self.deck = [(r, s) for r in range(2, 15) for s in "shdc"]
        random.shuffle(self.deck)
        for p in self.players:
            p.hole = [self.deck.pop(), self.deck.pop()]
        self.board, self.street, self.in_hand = [], "preflop", True
        if n == 2:
            sb_i, bb_i, first = self.dealer, (self.dealer + 1) % 2, self.dealer
        else:
            sb_i, bb_i, first = (self.dealer + 1) % n, (self.dealer + 2) % n, (self.dealer + 3) % n
        self.sb_p, self.bb_p = self.players[sb_i], self.players[bb_i]
        self._put(self.sb_p, self.sb)
        self._put(self.bb_p, self.bb)
        self.current_bet = max(p.bet for p in self.players)
        self.min_raise = self.bb
        self.log = (f"⬆️ Blinds up to {self.sb:,}/{self.bb:,}! " if blinds_up else "") + \
                   f"Blinds: {self.sb_p.name} {self.sb:,} · {self.bb_p.name} {self.bb:,}"
        self.cur = first
        self.message = None            # every hand gets a fresh message
        await self._proceed(first)

    def _round_done(self, active):
        if not active:
            return True
        if len(active) == 1:
            return active[0].bet >= self.current_bet
        return all(p.acted and p.bet == self.current_bet for p in active)

    def _deal_street(self):
        self.deck.pop()  # burn
        if self.street == "preflop":
            self.board += [self.deck.pop() for _ in range(3)]
            self.street = "flop"
        elif self.street == "flop":
            self.board.append(self.deck.pop())
            self.street = "turn"
        elif self.street == "turn":
            self.board.append(self.deck.pop())
            self.street = "river"

    def _pick(self, nxt):
        n = len(self.players)
        for off in range(n):
            i = (nxt + off) % n
            p = self.players[i]
            if p.folded or p.allin or (p.acted and p.bet == self.current_bet):
                continue
            return i
        return nxt % n

    async def _proceed(self, nxt):
        n = len(self.players)
        while True:
            alive = [p for p in self.players if not p.folded]
            if len(alive) == 1:
                return await self._win_by_fold(alive[0])
            active = [p for p in alive if not p.allin]
            if self._round_done(active):
                if self.street == "river":
                    return await self._showdown()
                if len(active) <= 1:
                    while self.street != "river":
                        self._deal_street()
                    return await self._showdown()
                self._deal_street()
                for p in self.players:
                    p.bet, p.acted = 0, False
                self.current_bet, self.min_raise = 0, self.bb
                self.log = f"{self.street.capitalize()} dealt."
                nxt = (self.dealer + 1) % n
                continue
            idx = self._pick(nxt)
            p = self.players[idx]
            if p.leaving:
                p.folded = True
                self.log = f"{p.name} left the table."
                nxt = idx + 1
                continue
            self.cur = idx
            await self.render()
            self._set_timer()
            to_call = max(0, self.current_bet - p.bet)
            await self._ping(f"🎯 {p.user.mention} it's your turn! " + (f"**{min(to_call, p.stack):,}** to call" if to_call else "Check or bet"))
            return

    def _set_timer(self):
        if self.timer:
            self.timer.cancel()
        self.turn_id += 1
        self.timer = asyncio.create_task(self._timeout(self.turn_id))

    async def _timeout(self, tid):
        await asyncio.sleep(TURN_SECONDS)
        async with self.lock:
            if tid != self.turn_id or not self.in_hand or self.closed:
                return
            self.timer = None
            p = self.players[self.cur]
            if p.bet >= self.current_bet:
                self._do(p, "call")
                self.log = f"{p.name} ran out of time and checks."
            else:
                self._do(p, "fold")
                self.log = f"{p.name} ran out of time and folds."
            await self._proceed((self.cur + 1) % len(self.players))

    # ---------------- actions ----------------
    def _do(self, p, kind, amount=None):
        to_call = self.current_bet - p.bet
        all_chips = p.bet + p.stack
        if kind == "fold":
            p.folded = True
            self.log = f"{p.name} folds."
            return None
        if kind == "allin":
            kind, amount = "raise", all_chips
        if kind == "raise" and (amount is None or amount <= self.current_bet) and all_chips <= self.current_bet:
            kind = "call"
        if kind == "call":
            amt = min(to_call, p.stack)
            self._put(p, amt)
            p.acted = True
            if to_call <= 0:
                self.log = f"{p.name} checks."
            else:
                self.log = f"{p.name} calls {amt:,}." + (" (all-in)" if p.allin else "")
            return None
        # raise
        target = min(amount, all_chips)
        if target <= self.current_bet:
            return "Your raise must be higher than the current bet."
        full = target - self.current_bet >= self.min_raise
        if not full and target < all_chips:
            return f"Minimum raise is to {self.current_bet + self.min_raise:,}."
        verb = "bets" if self.current_bet == 0 else "raises to"
        if full:
            self.min_raise = target - self.current_bet
        self._put(p, target - p.bet)
        self.current_bet = target
        if full:
            for o in self.players:
                if o is not p:
                    o.acted = False
        p.acted = True
        self.log = f"{p.name} {verb} {target:,}." + (" (all-in)" if p.allin else "")
        return None

    async def handle(self, inter, kind, amount=None):
        if not inter.response.is_done():
            await inter.response.defer()        # answer Discord first, so the click never times out waiting for the lock
        async with self.lock:
            p = self.player_of(inter.user.id)
            if not p:
                return await _say(inter, self.nope(inter.user.id))
            if not self.in_hand or self.players[self.cur] is not p:
                return await _say(inter, "It's not your turn.")
            err = self._do(p, kind, amount)
            if err:
                return await _say(inter, err)
            await self._proceed((self.cur + 1) % len(self.players))

    async def leave_now(self, inter, p):
        """Leave: fold right away and send the chips back to cash (all-in players wait for the hand to end).
        Also works between hands. The interaction must already be deferred (thinking) before this is called."""
        if p.left:
            return await _say(inter, "You already left this table.")
        if self.in_hand and p.allin and not p.folded:
            p.leaving = True
            return await _say(inter, "You're all-in, so your chips go back to your cash when this hand ends.")
        was_turn = self.in_hand and self.players[self.cur] is p
        back = p.stack
        p.leaving = p.left = True
        if self.in_hand and not p.folded:
            p.folded = True
            self.log = f"{p.name} left the table."
        await self.cashout(p)           # chips that are not in the pot go straight back to cash
        p.stack = 0
        await _say(inter, f"You left the table. **{back:,}** {cur()} went back to your cash.")
        if self.in_hand:
            if not any(not q.left for q in self.players):
                return await self._everyone_left()
            await self._proceed((self.cur + 1) % len(self.players) if was_turn else self.cur)
        else:
            try:
                await self.channel.send(f"🚪 **{p.name}** left the table.")
            except discord.HTTPException:
                pass

    async def _everyone_left(self):
        """Every player left mid-game: close the table and tell the channel that all money is back in cash."""
        self.closed = True
        self.in_hand = False
        if self.timer:
            self.timer.cancel()
            self.timer = None
        await self._clear_ping()
        TABLES.pop(self.channel.id, None)
        self.players.clear()
        try:
            if self.message is not None:
                await self.message.edit(embed=refund_embed(), view=None)
            else:
                await self.channel.send(embed=refund_embed())
        except discord.HTTPException:
            await self.channel.send(embed=refund_embed())

    # ---------------- ending a hand ----------------
    def _side_pots(self):
        live = [p for p in self.players if not p.folded]
        pots, prev = [], 0
        for lvl in sorted({p.total for p in live}):
            amt = sum(min(p.total, lvl) - min(p.total, prev) for p in self.players)
            elig = [p for p in live if p.total >= lvl]
            if amt > 0:
                pots.append((amt, elig))
            prev = lvl
        return pots

    async def _win_by_fold(self, w):
        pot = sum(p.total for p in self.players)
        w.stack += pot
        await self._finish_hand([f"🏆 **{w.name}** wins **{pot:,}** {cur()} — everyone else folded."], False, {}, {id(w)})

    async def _showdown(self):
        n = len(self.players)
        scores = {id(p): best_score(p.hole + self.board) for p in self.players if not p.folded}
        lines, winset = [], set()
        for i, (amt, elig) in enumerate(self._side_pots()):
            top = max(scores[id(p)] for p in elig)
            winners = [p for p in elig if scores[id(p)] == top]
            winners.sort(key=lambda p: (self.players.index(p) - self.dealer - 1) % n)
            share, rem = divmod(amt, len(winners))
            for j, w in enumerate(winners):
                w.stack += share + (1 if j < rem else 0)
                winset.add(id(w))
            label = "Main pot" if i == 0 else f"Side pot {i}"
            lines.append(f"🏆 **{label}** · {amt:,} {cur()} → **{', '.join(w.name for w in winners)}**")
        labels = {k: hand_name(v) for k, v in scores.items()}
        await self._finish_hand(lines, True, labels, winset)

    async def _finish_hand(self, lines, reveal, labels, winset):
        self.in_hand = False
        if self.timer:
            self.timer.cancel()
            self.timer = None
        head = [f"{HDR_BOARD}{cards_str(self.board, 5)}"] if self.board else []
        head.append(f"### 🏁 Hand #{self.hand_no}")
        lines = head + lines
        if reveal:
            lines.append("")
            for p in self.players:
                if not p.folded:
                    lines.append(f"{'🏆' if id(p) in winset else '▸'} **{p.name}**   {cards_str(p.hole)}   *{labels.get(id(p), '')}*")
        e = discord.Embed(color=COLOR, description="\n".join(lines))
        e.set_footer(text=f"Next hand in {NEXT_HAND_DELAY} seconds  ·  press Leave to cash out")
        winners = [p for p in self.players if id(p) in winset]
        will_continue = sum(1 for p in self.players if not p.left and not p.leaving and p.stack > 0) >= 2
        await self.post(e, HandOverView(self) if will_continue else None)
        # tag the winner(s), and tell everyone they have time to leave
        tag = " ".join(w.user.mention for w in winners)
        await self._ping(f"🏆 {tag} won the hand!" + (f"\n-# Next hand in {NEXT_HAND_DELAY} seconds. Press **Leave** if you want to cash out." if will_continue else ""))
        notes = []
        for p in self.players:
            if not p.left:
                _track(p)
        for p in list(self.players):
            if p.left:
                self.players.remove(p)
            elif p.leaving:                 # pressed Leave while all-in: now the hand is over, so cash out
                await self.cashout(p)
                notes.append(f"{p.name} left with {p.stack:,} {cur()}.")
                self.players.remove(p)
            elif p.stack == 0:
                await self.cashout(p)
                notes.append(f"{p.name} is out of chips.")
                self.players.remove(p)
        if notes:
            await self.channel.send("\n".join(notes))
        if len(self.players) < 2:
            return await self.end_game()
        asyncio.create_task(self._next_hand())

    async def _next_hand(self):
        await asyncio.sleep(NEXT_HAND_DELAY)
        async with self.lock:
            if not self.closed:
                await self._clear_ping()
                await self.start_hand()

    async def end_game(self):
        """The game is over. The last player is NOT cashed out automatically: they press Cash out
        (it happens by itself after CASHOUT_SECONDS so the money is never stuck)."""
        self.closed = True
        TABLES.pop(self.channel.id, None)
        await self._clear_ping()
        if self.message is not None:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass
        if self.players:
            w = self.players[0]
            view = CashoutView(self, w)
            embed = closed_embed(f"🏆 **{w.name}** takes the table with **{w.stack:,}** {cur()}.\n"
                                 f"Press **Cash out** to move it to your cash.\n"
                                 f"-# It goes back to your cash automatically after {CASHOUT_SECONDS // 60} minutes.")
            view.message = await self.channel.send(content=w.user.mention, embed=embed, view=view, allowed_mentions=PING)
        else:
            await self.channel.send(embed=refund_embed())


# ============================================================
#  UI
# ============================================================
async def _leave_click(t, inter):
    """Shared by the Leave button on the turn message and on the between-hands message."""
    await inter.response.defer(ephemeral=True, thinking=True)     # answer Discord first
    async with t.lock:
        if t.closed:
            return await _say(inter, "This table is closed.")
        p = t.player_of(inter.user.id)
        if not p:
            return await _say(inter, t.nope(inter.user.id))
        await t.leave_now(inter, p)


class RaiseModal(discord.ui.Modal, title="Raise"):
    def __init__(self, table, p):
        super().__init__()
        self.t = table
        self.maxamt = p.bet + p.stack
        self.amount = discord.ui.TextInput(
            label="Raise to (total bet this round)",
            placeholder=f"min {min(table.current_bet + table.min_raise, p.bet + p.stack):,} · max {p.bet + p.stack:,}")
        self.add_item(self.amount)

    async def on_submit(self, inter):
        v = parse_amount(str(self.amount.value), self.maxamt)
        if v is None:
            return await inter.response.send_message("Enter a valid number.", ephemeral=True)
        await self.t.handle(inter, "raise", v)

    async def on_error(self, inter, error):
        await _view_error(inter, error)


class TableView(discord.ui.View):
    """Buttons follow the rules: Check only when nothing to call, Call only when there is a bet,
    Bet/Raise and All-in only when a raise is possible. Fold, My Cards and Leave are always there."""

    def __init__(self, table):
        super().__init__(timeout=None)
        self.t = table
        p = table.players[table.cur]
        to_call = max(0, table.current_bet - p.bet)
        can_raise = table.can_raise(p)
        S = discord.ButtonStyle
        if to_call == 0:
            self._add("Check", S.success, 0, lambda i: table.handle(i, "call"))
        else:
            self._add(f"Call {_short(min(to_call, p.stack))}", S.success, 0, lambda i: table.handle(i, "call"))
        if can_raise:
            self._add("Bet" if table.current_bet == 0 else "Raise", S.primary, 0, self._raise)
        self._add("Fold", S.danger, 0, lambda i: table.handle(i, "fold"))
        if can_raise and p.stack > to_call:
            self._add("All-in", S.secondary, 0, lambda i: table.handle(i, "allin"))
        self._add("My Cards", S.secondary, 1, self._cards)
        self._add("Leave", S.secondary, 1, self._leave)

    async def on_error(self, inter, error, item):
        await _view_error(inter, error)

    async def interaction_check(self, inter):
        print(f"[holdem] table click by {inter.user} ({inter.data.get('custom_id', '?')[:8]})")
        return True

    def _add(self, label, style, row, fn):
        btn = discord.ui.Button(label=label, style=style, row=row)

        async def callback(inter):
            await fn(inter)
        btn.callback = callback
        self.add_item(btn)

    async def _raise(self, inter):
        t = self.t
        p = t.player_of(inter.user.id)
        if not p:
            return await inter.response.send_message(t.nope(inter.user.id), ephemeral=True)
        if not t.in_hand or t.players[t.cur] is not p:
            return await inter.response.send_message("It's not your turn.", ephemeral=True)
        if not t.can_raise(p):
            return await inter.response.send_message("You can't raise right now.", ephemeral=True)
        await inter.response.send_modal(RaiseModal(t, p))

    async def _cards(self, inter):
        t = self.t
        p = t.player_of(inter.user.id)
        if not p:
            return await inter.response.send_message(t.nope(inter.user.id), ephemeral=True)
        if not t.in_hand or p.folded:
            return await inter.response.send_message("You're not in this hand.", ephemeral=True)
        lines = [f"{HDR_HAND}{cards_str(p.hole)}", "-# Your hand"]
        if t.board:
            lines += ["", f"{HDR_BOARD}{cards_str(t.board, 5)}", "-# Board"]
        lines += [""] + explain(p.hole, t.board)
        lines += ["", f"-# Your chips: {p.stack:,} {cur()}"]
        e = discord.Embed(color=COLOR, description="\n".join(lines))
        e.set_footer(text="Only you can see this message.")
        await inter.response.send_message(embed=e, ephemeral=True)

    async def _leave(self, inter):
        await _leave_click(self.t, inter)


class HandOverView(discord.ui.View):
    """Shown on the finished hand during the pause before the next one: the time to decide to leave."""

    def __init__(self, table):
        super().__init__(timeout=None)
        self.t = table

    async def on_error(self, inter, error, item):
        await _view_error(inter, error)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary)
    async def leave_btn(self, inter, button):
        await _leave_click(self.t, inter)


class CashoutView(discord.ui.View):
    """The last player standing: they choose when to cash out (automatic after CASHOUT_SECONDS)."""

    def __init__(self, table, player):
        super().__init__(timeout=CASHOUT_SECONDS)
        self.t, self.p = table, player
        self.done = False
        self.message = None

    async def _finish(self):
        if self.done:
            return False
        self.done = True
        self.stop()
        await self.t.cashout(self.p)
        return True

    async def on_error(self, inter, error, item):
        await _view_error(inter, error)

    @discord.ui.button(label="Cash out", style=discord.ButtonStyle.success)
    async def cash_btn(self, inter, button):
        if inter.user.id != self.p.user.id:
            return await inter.response.send_message("Only the winner can cash out.", ephemeral=True)
        await inter.response.defer()
        won = self.p.stack
        if await self._finish():
            e = closed_embed(f"🏆 **{self.p.name}** cashed out **{won:,}** {cur()}.", GOLD)
            try:
                await inter.message.edit(content=None, embed=e, view=None)
            except discord.HTTPException:
                pass

    async def on_timeout(self):
        won = self.p.stack
        if await self._finish() and self.message:
            e = closed_embed(f"🏆 **{self.p.name}** cashed out **{won:,}** {cur()}.", GOLD)
            try:
                await self.message.edit(content=None, embed=e, view=None)
            except discord.HTTPException:
                pass


class LobbyView(discord.ui.View):
    def __init__(self, table):
        super().__init__(timeout=LOBBY_SECONDS)
        self.t = table

    async def on_error(self, inter, error, item):
        await _view_error(inter, error)

    async def interaction_check(self, inter):
        print(f"[holdem] lobby click by {inter.user} ({inter.data.get('custom_id', '?')[:8]})")
        return True

    # NOTE: these two used to be called _refresh / _start, which clash with internal discord.py View methods
    async def _redraw(self):
        await self.t.message.edit(embed=self.t.lobby_embed(), view=self)

    @discord.ui.button(label="Join", style=discord.ButtonStyle.success)
    async def join_btn(self, inter, button):
        t = self.t
        await inter.response.defer(ephemeral=True, thinking=True)     # answer Discord first
        async with t.lock:
            if t.state != "lobby":
                return await _say(inter, "This game already started.")
            if inter.user.id == t.host.id:
                return await _say(inter, "You are the leader.")
            if t.player_of(inter.user.id):
                return await _say(inter, "You already joined.")
            if len(t.players) >= MAX_PLAYERS:
                return await _say(inter, "The table is full.")
            if _is_busy(inter.user.id):
                return await _say(inter, "You're already in an active game. Finish it first.")
            if await cash_get(inter.user.id) < t.buyin:
                return await _say(inter, f"You need {t.buyin:,} in cash to join.")
            await cash_add(inter.user.id, -t.buyin)
            t.seat(inter.user)
            left = user_data(inter.user.id)["cash"]
            await _say(inter, f"✅ You're in. **{t.buyin:,}** {cur()} was taken from your cash and is now your stack. Cash left: **{left:,}** {cur()}.")
            await self._redraw()
            if len(t.players) == MAX_PLAYERS:
                await self._begin()

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary)
    async def leave_btn(self, inter, button):
        t = self.t
        await inter.response.defer(ephemeral=True, thinking=True)     # answer Discord first
        async with t.lock:
            p = t.player_of(inter.user.id)
            if t.state != "lobby" or not p:
                return await _say(inter, "You're not in the lobby.")
            back = p.stack
            await t.cashout(p, log=False)           # the buy-in goes straight back to cash
            t.players.remove(p)
            if not t.players:
                # the last player left: close the table (gold message: everybody got their money back)
                t.state, t.closed = "closed", True
                TABLES.pop(t.channel.id, None)
                self.stop()
                try:
                    await t.message.edit(embed=refund_embed(), view=None)
                except discord.HTTPException:
                    pass
            else:
                if p.user.id == t.host.id:          # the leader left: the next player becomes the leader
                    t.host = t.players[0].user
                await self._redraw()
            await _say(inter, f"You left the table. **{back:,}** {cur()} went back to your cash.")

    @discord.ui.button(label="Start", style=discord.ButtonStyle.primary)
    async def start_btn(self, inter, button):
        t = self.t
        await inter.response.defer()                # silent: the message stays exactly as it is
        async with t.lock:
            if inter.user.id != t.host.id:
                return await _say(inter, "Only the leader can start the game.")
            if t.state != "lobby" or len(t.players) < 2:
                return                              # not enough players: leave the message as it is
            await self._begin()

    async def _begin(self):
        t = self.t
        t.state = "playing"
        self.stop()
        await t.message.edit(embed=t.lobby_embed(started=True), view=None)
        t.message = None            # hands are posted as new messages
        await t.start_hand()

    async def on_timeout(self):
        t = self.t
        async with t.lock:
            if t.state != "lobby":
                return
            for q in t.players:
                await t.cashout(q, log=False)
            t.players.clear()
            t.state, t.closed = "closed", True
            TABLES.pop(t.channel.id, None)
            try:
                await t.message.edit(embed=refund_embed("**Table expired.**\nNobody started the game. Everyone got their money back to cash."), view=None)
            except discord.HTTPException:
                pass


# ============================================================
#  Command
# ============================================================
@bot.command(name="texas", aliases=["holdem"])
async def texas(ctx, buyin: str = None):
    try:
        await _holdem(ctx, buyin)
    except Exception as ex:      # show the real error in the channel instead of failing silently
        traceback.print_exc()
        await ctx.send(f"Hold'em error: `{ex!r}`")


async def _holdem(ctx, buyin):
    amount = parse_amount(buyin, user_data(ctx.author.id)["cash"]) if buyin else None
    if amount is None or amount < MIN_BUYIN:
        return await ctx.send(f"Usage: `{ctx.prefix}texas <amount>` - everyone at the table pays the same amount (minimum {fmt(MIN_BUYIN)})")
    if ctx.channel.id in TABLES:
        return await ctx.send("A Hold'em table is already open in this channel.")
    if _is_busy(ctx.author.id):
        return await ctx.send("You're already in an active game. Finish it first.")
    if await cash_get(ctx.author.id) < amount:
        return await ctx.send(f"You need {fmt(amount)} {cur()} in cash to open this table.")
    await cash_add(ctx.author.id, -amount)
    t = Table(ctx.channel, ctx.author, amount)
    p = t.seat(ctx.author)
    TABLES[ctx.channel.id] = t
    try:
        t.message = await ctx.send(embed=t.lobby_embed(), view=LobbyView(t))
    except Exception:
        TABLES.pop(ctx.channel.id, None)
        await t.cashout(p, log=False)
        raise


print(f"game_holdem v4 loaded (discord.py {discord.__version__}): command $texas registered")
