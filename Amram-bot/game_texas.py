"""game_holdem.py - Texas Hold'em, 2-6 players.

Usage:  $holdem <buy-in>     (the first player sets the buy-in, everyone pays the same)
Add 'game_holdem' to MODULES in main.py, right after 'game_poker'.
"""
import asyncio
import itertools
import sys
import random
from collections import Counter

import discord
from discord.ext import commands

# ============================================================
#  CONSTANTS
# ============================================================

MAX_PLAYERS = 6
MIN_BUYIN = MIN_BET          # from core
TURN_SECONDS = 45
NEXT_HAND_DELAY = 8
COLOR = 0x1B5E3A

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


_BJ_RANK = {11: "J", 12: "Q", 13: "K", 14: "A"}
_BJ_SUIT = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}


def cs(card):
    """Card emoji. Uses the blackjack card emojis (read live, they are created after the bot starts)."""
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
    return ", ".join(out) if out else "—"


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

    def player_of(self, uid):
        return next((p for p in self.players if p.user.id == uid), None)

    # ---------------- embeds ----------------
    def lobby_embed(self):
        e = discord.Embed(title="♠ Texas Hold'em ♥", color=COLOR)
        e.description = (f"**Buy-in:** {self.buyin:,}\n**Blinds:** {self.sb:,} / {self.bb:,}\n"
                         f"**Host:** {self.host.display_name}")
        e.add_field(name=f"Players ({len(self.players)}/{MAX_PLAYERS})",
                    value="\n".join(f"• {p.name}" for p in self.players) or "—", inline=False)
        e.set_footer(text="Buy-in is taken from your cash. Your chips return to your cash when you leave or win.")
        return e

    def table_embed(self):
        pot = sum(p.total for p in self.players)
        e = discord.Embed(title="♠ Texas Hold'em ♥", color=COLOR)
        e.description = f"**Board**\n{cards_str(self.board, 5)}\n\n**Pot:** {pot:,}"
        lines = []
        for i, p in enumerate(self.players):
            tags = []
            if i == self.dealer % len(self.players):
                tags.append("D")
            if p is self.sb_p:
                tags.append("SB")
            if p is self.bb_p:
                tags.append("BB")
            tag = f" `{'/'.join(tags)}`" if tags else ""
            mark = "▶ " if self.in_hand and i == self.cur else "▫ "
            if p.folded:
                lines.append(f"{mark}~~{p.name}~~{tag} — Folded")
            elif p.allin:
                lines.append(f"{mark}**{p.name}**{tag} — All-in ({p.total:,})")
            else:
                bet = f" · bet {p.bet:,}" if p.bet else ""
                lines.append(f"{mark}**{p.name}**{tag} — {p.stack:,}{bet}")
        e.add_field(name="Players", value="\n".join(lines), inline=False)
        if self.in_hand:
            p = self.players[self.cur]
            to_call = max(0, self.current_bet - p.bet)
            act = f"**Action on:** {p.user.mention} — " + ("check or bet" if to_call == 0 else f"{min(to_call, p.stack):,} to call")
            e.add_field(name="\u200b", value=(f"{self.log}\n\n" if self.log else "") + act, inline=False)
        e.set_footer(text=f"Hand #{self.hand_no} · {self.street.capitalize()} · Blinds {self.sb:,}/{self.bb:,} · {TURN_SECONDS}s per turn")
        return e

    def result_embed(self, lines, reveal):
        e = discord.Embed(title=f"Hand #{self.hand_no} — Result", color=COLOR)
        e.description = f"**Board**\n{cards_str(self.board, 5)}"
        if reveal:
            show = []
            for p in self.players:
                if not p.folded:
                    sc = best_score(p.hole + self.board)
                    show.append(f"**{p.name}** {cards_str(p.hole)} — {hand_name(sc)}")
            e.add_field(name="Showdown", value="\n".join(show), inline=False)
        e.add_field(name="Winners", value="\n".join(lines), inline=False)
        return e

    async def render(self):
        try:
            await self.message.edit(embed=self.table_embed(), view=TableView(self) if self.in_hand else None)
        except discord.HTTPException:
            pass

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
        self.log = f"Blinds posted: {self.sb_p.name} {self.sb:,} · {self.bb_p.name} {self.bb:,}"
        self.cur = first
        self.message = await self.channel.send(embed=self.table_embed(), view=None)
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
                return await inter.response.send_message("You're not seated at this table.", ephemeral=True)
            if not self.in_hand or self.players[self.cur] is not p:
                return await inter.response.send_message("It's not your turn.", ephemeral=True)
            err = self._do(p, kind, amount)
            if err:
                return await inter.response.send_message(err, ephemeral=True)
            await inter.response.defer()
            await self._proceed((self.cur + 1) % len(self.players))

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
        await self._finish_hand(self.result_embed([f"**{w.name}** wins **{pot:,}** — everyone else folded."], False))

    async def _showdown(self):
        n = len(self.players)
        scores = {id(p): best_score(p.hole + self.board) for p in self.players if not p.folded}
        lines = []
        for i, (amt, elig) in enumerate(self._side_pots()):
            top = max(scores[id(p)] for p in elig)
            winners = [p for p in elig if scores[id(p)] == top]
            winners.sort(key=lambda p: (self.players.index(p) - self.dealer - 1) % n)
            share, rem = divmod(amt, len(winners))
            for j, w in enumerate(winners):
                w.stack += share + (1 if j < rem else 0)
            label = "Main pot" if i == 0 else f"Side pot {i}"
            lines.append(f"{label} **{amt:,}** → {', '.join(w.name for w in winners)} ({hand_name(top)})")
        await self._finish_hand(self.result_embed(lines, True))

    async def _finish_hand(self, embed):
        self.in_hand = False
        if self.timer:
            self.timer.cancel()
            self.timer = None
        try:
            await self.message.edit(embed=embed, view=None)
        except discord.HTTPException:
            pass
        notes = []
        for p in self.players:
            _track(p)
        for p in list(self.players):
            if p.leaving:
                await self.cashout(p)
                notes.append(f"{p.name} left with {p.stack:,}.")
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
            e = discord.Embed(title="♠ Table closed", color=COLOR,
                              description=f"**{w.name}** takes the table and cashes out **{w.stack:,}**.")
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
    def __init__(self, table):
        super().__init__(timeout=None)
        self.t = table
        p = table.players[table.cur]
        to_call = max(0, table.current_bet - p.bet)
        self.call_btn.label = "Check" if to_call == 0 else f"Call {min(to_call, p.stack):,}"

    @discord.ui.button(label="Check", style=discord.ButtonStyle.success, row=0)
    async def call_btn(self, inter, button):
        await self.t.handle(inter, "call")

    @discord.ui.button(label="Raise", style=discord.ButtonStyle.primary, row=0)
    async def raise_btn(self, inter, button):
        t = self.t
        p = t.player_of(inter.user.id)
        if not p or not t.in_hand or t.players[t.cur] is not p:
            return await inter.response.send_message("It's not your turn.", ephemeral=True)
        if p.bet + p.stack <= t.current_bet:
            return await inter.response.send_message("You can only call or fold.", ephemeral=True)
        await inter.response.send_modal(RaiseModal(t, p))

    @discord.ui.button(label="Fold", style=discord.ButtonStyle.danger, row=0)
    async def fold_btn(self, inter, button):
        await self.t.handle(inter, "fold")

    @discord.ui.button(label="All-in", style=discord.ButtonStyle.secondary, row=0)
    async def allin_btn(self, inter, button):
        await self.t.handle(inter, "allin")

    @discord.ui.button(label="My Cards", style=discord.ButtonStyle.secondary, row=1)
    async def cards_btn(self, inter, button):
        t = self.t
        p = t.player_of(inter.user.id)
        if not p or not t.in_hand:
            return await inter.response.send_message("You're not in this hand.", ephemeral=True)
        e = discord.Embed(title="Your cards", color=COLOR, description=cards_str(p.hole))
        if t.board:
            e.add_field(name="Board", value=cards_str(t.board, 5), inline=False)
            if len(p.hole + t.board) >= 5:
                e.add_field(name="You have", value=hand_name(best_score(p.hole + t.board)), inline=False)
        e.set_footer(text="Only you can see this message.")
        await inter.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary, row=1)
    async def leave_btn(self, inter, button):
        t = self.t
        async with t.lock:
            p = t.player_of(inter.user.id)
            if not p:
                return await inter.response.send_message("You're not seated at this table.", ephemeral=True)
            p.leaving = True
            await inter.response.send_message("You'll fold and cash out your chips when this hand ends.", ephemeral=True)
            if t.in_hand and t.players[t.cur] is p:
                t._do(p, "fold")
                await t._proceed((t.cur + 1) % len(t.players))


class LobbyView(discord.ui.View):
    def __init__(self, table):
        super().__init__(timeout=600)
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
            await inter.response.defer()
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
            if inter.user.id == t.host.id:
                for q in t.players:
                    await t.cashout(q, log=False)
                t.state, t.closed = "closed", True
                TABLES.pop(t.channel.id, None)
                self.stop()
                return await inter.response.edit_message(
                    embed=discord.Embed(title="♠ Table cancelled", description="The host left. Everyone was refunded.", color=COLOR),
                    view=None)
            await t.cashout(p, log=False)
            t.players.remove(p)
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
        e = self.t.lobby_embed()
        e.title = "♠ Texas Hold'em — game started ♥"
        await t.message.edit(embed=e, view=None)
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
                await t.message.edit(embed=discord.Embed(title="♠ Table expired", description="Nobody started the game. Everyone was refunded.", color=COLOR), view=None)
            except discord.HTTPException:
                pass


# ============================================================
#  Command
# ============================================================
@bot.command(name="holdem", aliases=["texas"])
async def holdem(ctx, buyin: str = None):
    amount = parse_amount(buyin, user_data(ctx.author.id)["cash"]) if buyin else None
    if amount is None or amount < MIN_BUYIN:
        return await ctx.send(f"Usage: `{ctx.prefix}holdem <buy-in>` (minimum {fmt(MIN_BUYIN)})")
    if ctx.channel.id in TABLES:
        return await ctx.send("A Hold'em table is already open in this channel.")
    if await cash_get(ctx.author.id) < amount:
        return await ctx.send(f"You need {fmt(amount)} {cur()} in cash to open this table.")
    await cash_add(ctx.author.id, -amount)
    t = Table(ctx.channel, ctx.author, amount)
    t.seat(ctx.author)
    TABLES[ctx.channel.id] = t
    t.message = await ctx.send(embed=t.lobby_embed(), view=LobbyView(t))
