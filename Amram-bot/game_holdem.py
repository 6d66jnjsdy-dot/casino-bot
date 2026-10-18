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
NEXT_HAND_DELAY = 8
LOBBY_SECONDS = 600          # an open table that nobody starts closes after this
COLOR = 0xB19CD9             # soft purple side bar (change this one line to recolor everything)
GOLD = COLOR

SYM = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
RANKS = "23456789TJQKA"
SING = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine",
        10: "Ten", 11: "Jack", 12: "Queen", 13: "King", 14: "Ace"}
PLUR = {2: "Twos", 3: "Threes", 4: "Fours", 5: "Fives", 6: "Sixes", 7: "Sevens", 8: "Eights",
        9: "Nines", 10: "Tens", 11: "Jacks", 12: "Queens", 13: "Kings", 14: "Aces"}

GAME_NAMES["holdem"] = "Texas Hold'em"      # nice name in the game log


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


# ============================================================
#  Table state
# ============================================================
TABLES = {}  # channel id -> Table


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
        self.bb = max(2, buyin // 50)
        self.sb = max(1, self.bb // 2)
        self.players = []
        self.state = "lobby"
        self.message = None
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

    def can_raise(self, p):
        """A raise is only possible if the player has chips beyond the current bet AND someone can still respond."""
        others = [o for o in self.players if o is not p and not o.folded and not o.allin]
        return bool(others) and p.bet + p.stack > self.current_bet

    # ---------------- embeds ----------------
    def lobby_embed(self, started=False):
        c = cur()
        n = len(self.players)
        icon = getattr(getattr(self.host, "display_avatar", None), "url", None)
        e = discord.Embed(title="♠  TEXAS HOLD'EM  ♥", color=COLOR)
        e.set_author(name=f"{self.host.display_name}'s table", icon_url=icon)
        if started:
            e.description = "**The game has started. Good luck!**\nEveryone sat down with the same stack."
        else:
            e.description = ("**A new table is open.**\n"
                             "Take a seat and play with the same stack as everyone else.\n\n"
                             f"⏳ Closes <t:{self.expires}:R>")
        e.add_field(name="💰 Buy-in", value=f"**{self.buyin:,}** {c}", inline=True)
        e.add_field(name="🎯 Blinds", value=f"**{self.sb:,}** / **{self.bb:,}**", inline=True)
        e.add_field(name="🏆 Prize pool", value=f"**{self.buyin * n:,}** {c}", inline=True)
        seats = []
        for i in range(MAX_PLAYERS):
            if i < n:
                p = self.players[i]
                seats.append(f"`{i + 1}`  {'👑 ' if p.user.id == self.host.id else ''}{p.user.mention}" + ("  ·  host" if p.user.id == self.host.id else ""))
            else:
                seats.append(f"`{i + 1}`  ▫️ *open seat*")
        e.add_field(name=f"Seats  ·  {n} / {MAX_PLAYERS}", value="\n".join(seats), inline=False)
        if not started:
            if n < 2:
                status = "⏳ Waiting for at least one more player…"
            else:
                status = "✅ Ready — the host can press **Start**."
            e.add_field(name="\u200b", value=status, inline=False)
        e.set_footer(text="Your buy-in goes back to your cash if you leave or the table closes.")
        return e

    def table_embed(self):
        c = cur()
        pot = sum(p.total for p in self.players)
        e = discord.Embed(color=COLOR)
        e.set_author(name=f"Texas Hold'em  ·  Hand #{self.hand_no}")
        lines = [f"**{self.street.capitalize()}**", cards_str(self.board, 5), "",
                 f"**Pot:** {pot:,} {c}"]
        if self.in_hand:
            act = self.players[self.cur]
            to_call = max(0, self.current_bet - act.bet)
            lines.append(f"**Current bet:** {self.current_bet:,} {c}" if self.current_bet else "**Current bet:** —")
        lines.append("")
        if self.log:
            lines.append(f"*{self.log}*")
        if self.in_hand:
            lines.append(f"▶ {act.user.mention} to act — " + ("**check** or bet" if to_call == 0 else f"**{min(to_call, act.stack):,}** to call"))
        e.description = "\n".join(lines)
        for i, p in enumerate(self.players):
            active = self.in_hand and i == self.cur
            tags = []
            if i == self.dealer % len(self.players):
                tags.append("`D`")
            if p is self.sb_p:
                tags.append("`SB`")
            if p is self.bb_p:
                tags.append("`BB`")
            if p.left:
                status = "Left the table"
            elif p.folded:
                status = "Folded"
            elif p.allin:
                status = "**ALL-IN**"
            elif p.bet:
                status = f"Bet {p.bet:,}"
            else:
                status = "—"
            e.add_field(name=f"{'▶ ' if active else ''}{p.name}",
                        value=f"{p.stack:,} {c}\n{status}" + (f"  {' '.join(tags)}" if tags else ""), inline=True)
        e.set_footer(text=f"Blinds {self.sb:,} / {self.bb:,}  ·  {TURN_SECONDS}s per turn")
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
        if log:
            log_game(p.user, "holdem", p.buyin, p.stack - p.buyin)

    def seat(self, user):
        p = Player(user, self.buyin, f"holdem:{self.channel.id}:{user.id}")
        self.players.append(p)
        _track(p)
        return p

    # ---------------- hand flow ----------------
    async def start_hand(self):
        self.players = [p for p in self.players if p.stack > 0]
        if len(self.players) < 2:
            return await self.end_game()
        n = len(self.players)
        self.hand_no += 1
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
        self.log = f"Blinds: {self.sb_p.name} {self.sb:,} · {self.bb_p.name} {self.bb:,}"
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
        async with self.lock:
            p = self.player_of(inter.user.id)
            if not p:
                return await inter.response.send_message(self.nope(inter.user.id), ephemeral=True)
            if not self.in_hand or self.players[self.cur] is not p:
                return await inter.response.send_message("It's not your turn.", ephemeral=True)
            err = self._do(p, kind, amount)
            if err:
                return await inter.response.send_message(err, ephemeral=True)
            await inter.response.defer()
            await self._proceed((self.cur + 1) % len(self.players))

    async def leave_now(self, inter, p):
        """Leave button: fold right away and send the chips back to cash (all-in players wait for the hand to end)."""
        if p.left:
            return await inter.response.send_message("You already left this table.", ephemeral=True)
        if self.in_hand and p.allin and not p.folded:
            p.leaving = True
            return await inter.response.send_message("You're all-in, so your chips go back to your cash when this hand ends.", ephemeral=True)
        was_turn = self.in_hand and self.players[self.cur] is p
        back = p.stack
        p.leaving = p.left = True
        if self.in_hand and not p.folded:
            p.folded = True
            self.log = f"{p.name} left the table."
        await self.cashout(p)           # chips that are not in the pot go straight back to cash
        p.stack = 0
        await inter.response.send_message(f"You left the table. **{back:,}** {cur()} went back to your cash.", ephemeral=True)
        if self.in_hand:
            await self._proceed((self.cur + 1) % len(self.players) if was_turn else self.cur)

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
        e = discord.Embed(color=GOLD)
        e.set_author(name=f"Texas Hold'em  ·  Hand #{self.hand_no}  ·  Result")
        e.description = f"**Board**\n{cards_str(self.board, 5)}\n\n" + "\n".join(lines)
        if reveal:
            for p in self.players:
                if not p.folded:
                    e.add_field(name=f"{'🏆 ' if id(p) in winset else ''}{p.name}",
                                value=f"{cards_str(p.hole)}\n{labels.get(id(p), '')}", inline=True)
        e.set_footer(text="Next hand starts in a few seconds")
        await self.post(e, None)
        notes = []
        for p in self.players:
            if not p.left:
                _track(p)
        for p in list(self.players):
            if p.left:
                self.players.remove(p)
            elif p.leaving:
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
                await self.start_hand()

    async def end_game(self):
        self.closed = True
        TABLES.pop(self.channel.id, None)
        if self.players:
            w = self.players[0]
            await self.cashout(w)
            e = discord.Embed(title="♠ Table closed", color=GOLD,
                              description=f"🏆 **{w.name}** takes the table and cashes out **{w.stack:,}** {cur()}.")
            await self.channel.send(embed=e)


# ============================================================
#  UI
# ============================================================
class RaiseModal(discord.ui.Modal, title="Raise"):
    amount = discord.ui.TextInput(label="Raise to (total bet this round)", placeholder="e.g. 400")

    def __init__(self, table, p):
        super().__init__()
        self.t = table
        self.maxamt = p.bet + p.stack
        self.amount.placeholder = f"min {min(table.current_bet + table.min_raise, p.bet + p.stack):,} · max {p.bet + p.stack:,}"

    async def on_submit(self, inter):
        v = parse_amount(str(self.amount.value), self.maxamt)
        if v is None:
            return await inter.response.send_message("Enter a valid number.", ephemeral=True)
        await self.t.handle(inter, "raise", v)


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
        cards = p.hole + list(t.board)
        lines = ["**Your hand**", cards_str(p.hole), ""]
        if t.board:
            lines += ["**Board**", cards_str(t.board, 5), ""]
        lines.append(f"**{hand_name(best_score(cards))}**" if len(cards) >= 5 else "*Waiting for the flop*")
        e = discord.Embed(color=COLOR, description="\n".join(lines))
        e.set_footer(text="Only you can see this message.")
        await inter.response.send_message(embed=e, ephemeral=True)

    async def _leave(self, inter):
        t = self.t
        async with t.lock:
            p = t.player_of(inter.user.id)
            if not p:
                return await inter.response.send_message(t.nope(inter.user.id), ephemeral=True)
            await t.leave_now(inter, p)


class LobbyView(discord.ui.View):
    def __init__(self, table):
        super().__init__(timeout=LOBBY_SECONDS)
        self.t = table

    async def _refresh(self):
        await self.t.message.edit(embed=self.t.lobby_embed(), view=self)

    @discord.ui.button(label="Join", style=discord.ButtonStyle.success)
    async def join_btn(self, inter, button):
        t = self.t
        async with t.lock:
            if t.state != "lobby":
                return await inter.response.send_message("This game already started.", ephemeral=True)
            if t.player_of(inter.user.id):
                return await inter.response.send_message("You already joined.", ephemeral=True)
            if len(t.players) >= MAX_PLAYERS:
                return await inter.response.send_message("The table is full.", ephemeral=True)
            if await cash_get(inter.user.id) < t.buyin:
                return await inter.response.send_message(f"You need {t.buyin:,} in cash to join.", ephemeral=True)
            await cash_add(inter.user.id, -t.buyin)
            t.seat(inter.user)
            left = user_data(inter.user.id)["cash"]
            await inter.response.send_message(
                f"✅ You're in. **{t.buyin:,}** {cur()} was taken from your cash and is now your stack. Cash left: **{left:,}** {cur()}.",
                ephemeral=True)
            await self._refresh()
            if len(t.players) == MAX_PLAYERS:
                await self._start()

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary)
    async def leave_btn(self, inter, button):
        t = self.t
        async with t.lock:
            p = t.player_of(inter.user.id)
            if t.state != "lobby" or not p:
                return await inter.response.send_message("You're not in the lobby.", ephemeral=True)
            await t.cashout(p, log=False)           # the buy-in goes straight back to cash
            t.players.remove(p)
            if not t.players:
                t.state, t.closed = "closed", True
                TABLES.pop(t.channel.id, None)
                self.stop()
                return await inter.response.edit_message(
                    embed=discord.Embed(title="♠ Table cancelled", description="Everyone left. The buy-in was returned to your cash.", color=COLOR),
                    view=None)
            if inter.user.id == t.host.id:
                t.host = t.players[0]               # the host can leave too: the next player becomes host
            await inter.response.defer()
            await self._refresh()

    @discord.ui.button(label="Start", style=discord.ButtonStyle.primary)
    async def start_btn(self, inter, button):
        t = self.t
        async with t.lock:
            if inter.user.id != t.host.id:
                return await inter.response.send_message("Only the host can start the game.", ephemeral=True)
            if t.state != "lobby" or len(t.players) < 2:
                return await inter.response.send_message("You need at least 2 players.", ephemeral=True)
            await inter.response.defer()
            await self._start()

    async def _start(self):
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
            t.state, t.closed = "closed", True
            TABLES.pop(t.channel.id, None)
            try:
                await t.message.edit(embed=discord.Embed(title="♠ Table expired", description="Nobody started the game. Everyone's buy-in was returned to their cash.", color=COLOR), view=None)
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


print("game_holdem loaded: command $texas registered")
