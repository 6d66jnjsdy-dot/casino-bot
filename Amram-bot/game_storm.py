import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= STORM (frozen event games) =================
# Usage:  owner:   $stormset on [duration]   /   $stormset off
#         players: $storm <roulette|mines|keno|mt|gm> <amount | half | all> [roulette bet]
# Everything you may want to tune is in the CONFIG block right below.

# ---------- CONFIG ----------
STORM_COLOR = 0x8FD3F4
EMOJI.setdefault("ice", "🧊")
SNOW = "❄️"

STORM_GAMES = {"roulette": "roulette", "mines": "mines", "keno": "keno", "mt": "mt", "tower": "mt",
               "moneytower": "mt", "gm": "gm", "goldmines": "gm"}
STORM_ONCE = {"roulette"}               # games a player can use only once per Storm activation

# Roulette - Frozen Rescue: (weight, kind, label). The bet is ALWAYS returned, the bonus comes on top of it.
ROUL_RESCUE = [(50, "x2", "Bet doubled"), (30, "cash", "Cash bonus"), (20, "gift", "Random gift")]

# Mines Frozen: 3x3, 1 bomb, 2 frozen tiles (always diamonds, each hides a bonus). One multiplier per diamond (8).
STORM_MINES_MULT = [1.02, 1.05, 1.12, 1.25, 1.5, 1.9, 2.8, 5]

# Keno Snow: 5x4 board, 6 clicks, 4 random frozen tiles (a frozen tile can be a bomb OR a diamond).
KENO_BOMBS, KENO_CLICKS, KENO_FROZEN = 5, 6, 4
KENO_MULT = [1.2, 1.5, 2, 2.8, 4, 6]

# Money Tower: the small bonus for a frozen bomb, as a fraction of the bet.
TOWER_FREEZE_BONUS = 0.15

# Gold Mines: 2 bombs become snow tiles (random prize multiplier), 1 more bomb becomes a guaranteed item.
GM_ICE_MULT = [(1.5, 50), (2.0, 35), (3.0, 15)]
GM_GUARANTEED = [("stone", 45), ("diamond", 30), ("coin", 15), ("bag", 10)]   # coin and bag are rarer

# Bonus pool for frozen diamonds (Mines / Keno): (weight, kind, label, value)
# "mult"   = multiplier on the player's NEXT $mines game (applied to the profit)
# "cash"   = cash prize, a random fraction of the bet (min, max)
# "manual" = something the bot cannot give by itself: the owner gets a DM + it is saved in DB["storm_rewards"]
STORM_REWARDS = [
    (30, "mult", "x1.2 on your next Mines game", 1.2),
    (20, "cash", "Cash prize", (0.25, 0.75)),
    (14, "manual", "Temporary goal", None),
    (10, "manual", "Private chat for 1 hour", None),
    (8, "manual", "Private chat for 2 hours", None),
    (5, "manual", "Private chat for 1 day", None),
    (2, "manual", "Private chat for 2 days", None),
    (11, "manual", "Higher streak % for a limited time", None),
]

# ---------- Storm state ----------
def storm_active():
    s = DB.get("storm")
    if not s:
        return False
    until = s.get("until")
    if until and time.time() >= until:
        DB.pop("storm", None)
        save()
        return False
    return True

def storm_used(uid, game):
    return game in DB.get("storm", {}).get("used", {}).get(str(uid), [])

def storm_mark(uid, game):
    DB.setdefault("storm", {}).setdefault("used", {}).setdefault(str(uid), []).append(game)
    save()

def storm_take_mult(uid, game):
    d = DB.get("storm_mult", {}).get(str(uid), {})
    m = d.pop(game, None)
    if m:
        save()
    return m or 1

def storm_reward(user, bet):
    """Picks one bonus for a frozen diamond. Returns the text shown to the player."""
    _, kind, label, val = random.choices(STORM_REWARDS, weights=[p[0] for p in STORM_REWARDS])[0]
    uid = str(user.id)
    if kind == "cash":
        amt = max(1, int(bet * random.uniform(*val)))
        user_data(user.id)["cash"] += amt
        text = f"{label}: **{fmt(amt)}** {cur()}"
    elif kind == "mult":
        d = DB.setdefault("storm_mult", {}).setdefault(uid, {})
        d["mines"] = max(d.get("mines", 1), val)
        text = f"**{label}**"
    else:
        DB.setdefault("storm_rewards", []).append({"uid": uid, "reward": label, "ts": int(time.time()), "done": False})
        bg(dm_owner(discord.Embed(color=STORM_COLOR, title=f"{SNOW} Storm reward to give", description=(
            f"**{user.name}** ({user.id}) won: **{label}**"))))
        text = f"**{label}** (the staff will give it to you)"
    save()
    log_event(user, "Storm | Bonus", text.replace("*", ""), BLUE)
    return f"{EMOJI['ice']} {text}"

# ---------- Mines: the "next game" multiplier from the Storm is applied here ----------
_mines_init, _mines_payout = Mines.__init__, Mines.payout

def _storm_mines_init(self, user, bet, token=None):
    _mines_init(self, user, bet, token)
    self.storm_mult = storm_take_mult(user.id, "mines")       # taken when the game starts (it is for ONE game)

def _storm_mines_payout(self):
    m = getattr(self, "storm_mult", 1)
    if m > 1 and self.profit > 0:
        self.profit = self.profit * m
    _mines_payout(self)

Mines.__init__, Mines.payout = _storm_mines_init, _storm_mines_payout

# ---------- shared embed ----------
def storm_result(view, lost, lines):
    found = sum(1 for i in view.revealed if view.board[i] != "bomb")
    extra = f"You found {found} {EMOJI['diamond']}\n" + "".join(f"{l}\n" for l in lines)
    return result_embed(view.user, not lost, view.bet if lost else int(view.profit), extra)

class StormMixin:
    """Frozen diamonds ('ice' tiles) give a bonus the moment they are revealed."""
    def after(self, kind):
        if kind == "ice":
            self.bonus_lines.append(storm_reward(self.user, self.bet))

    def embed(self, lost):
        return storm_result(self, lost, self.bonus_lines)

# ================= FREEZE PICKER (Mines / Money Tower) =================
class FreezePick(OwnedView):
    touch = True

    def __init__(self, user, bet, token, ttl, hint, cols, rows, same_row, launch):
        super().__init__(timeout=60)
        self.user, self.bet, self.token = user, bet, token
        self.ttl, self.hint, self.cols, self.same_row, self.launch = ttl, hint, cols, same_row, launch
        self.picks, self.launched, self.message, self.btns = [], False, None, []
        for i in range(cols * rows):
            b = discord.ui.Button(style=discord.ButtonStyle.secondary, label=EMPTY, row=i // cols)
            b.callback = self.pick(i)
            self.btns.append(b)
            self.add_item(b)

    def embed(self):
        return discord.Embed(color=STORM_COLOR, description=(
            f"**{SNOW} {self.ttl}**\n\nYou bet **{fmt(self.bet)}** {cur()}.\n\n{self.hint}"))

    def mark(self, i, on):
        b = self.btns[i]
        b.emoji = SNOW if on else None
        b.style = discord.ButtonStyle.primary if on else discord.ButtonStyle.secondary

    def pick(self, i):
        async def cb(interaction):
            if self.launched or i in self.picks:
                if not interaction.response.is_done():
                    await interaction.response.defer()
                return
            if self.same_row and self.picks and self.picks[0] // self.cols != i // self.cols:
                for p in self.picks:        # a tile from another row: start the choice again from this tile
                    self.mark(p, False)
                self.picks = []
            self.picks.append(i)
            self.mark(i, True)
            if len(self.picks) < 2:
                return await interaction.response.edit_message(view=self)
            self.launched = True
            self.stop()
            try:
                await self.launch(self, interaction, list(self.picks))
            except Exception:
                cancel_game(self.user, self.token, self.bet)
                raise
        return cb

    async def on_timeout(self):
        if self.launched:
            return
        pending_done(self.token)
        user_data(self.user.id)["cash"] += self.bet
        save()
        log_money(self.user, "STORM | TIMEOUT", f"Bet of {fmt(self.bet)} {cur()} was returned", YELLOW)
        if self.message:
            await self.message.edit(embed=discord.Embed(description="Timed out, your bet was returned.", color=RED), view=None)

async def start_picker(ctx, amount, usage, ttl, hint, cols, rows, same_row, launch):
    bet = await take_bet(ctx, amount, usage, track=True)
    if not bet:
        return
    view = FreezePick(ctx.author, bet, str(ctx.message.id), ttl, hint, cols, rows, same_row, launch)
    try:
        view.message = await ctx.reply(embed=view.embed(), view=view, mention_author=False)
    except Exception:
        cancel_game(ctx.author, view.token, bet)
        raise

# ================= 💣 MINES FROZEN =================
class StormMines(StormMixin, BoardView):
    cols = 3
    game_name = "Storm Mines"
    multi_key = "mines"

    @property
    def header(self):
        return f"**{self.user.name}'s Game** {SNOW}"

    def __init__(self, user, bet, token, frozen):
        self.frozen, self.bonus_lines = set(frozen), []
        super().__init__(user, bet, token)
        for i in self.frozen:
            self.tiles[i].emoji = SNOW

    def make_board(self):
        board = ["diamond"] * 9
        board[random.choice([i for i in range(9) if i not in self.frozen])] = "bomb"   # the bomb is never under a freeze
        for i in self.frozen:
            board[i] = "ice"
        return board

    def luck_pool(self, idx):
        return [i for i in super().luck_pool(idx) if i not in self.frozen]

    def earn(self, kind):
        n = min(len(self.revealed), len(STORM_MINES_MULT))
        self.profit = self.bet * (STORM_MINES_MULT[n - 1] - 1)

async def _launch_mines(pick, interaction, picks):
    game = StormMines(pick.user, pick.bet, pick.token, picks)
    game.message = interaction.message
    await interaction.response.edit_message(content=game.header, embed=None, view=game)

# ================= 🎯 KENO SNOW =================
class StormKeno(StormMixin, BoardView):
    cols = 5
    game_name = "Storm Keno"
    multi_key = "mines"

    @property
    def header(self):
        left = max(0, KENO_CLICKS - len(self.revealed))
        return f"**{self.user.name}'s Game** {SNOW} Clicks left: **{left}**"

    def __init__(self, user, bet, token=None):
        self.frozen, self.bonus_lines = set(), []
        super().__init__(user, bet, token)
        for i in self.frozen:
            self.tiles[i].emoji = SNOW

    def make_board(self):
        board = shuffled(bomb=KENO_BOMBS, diamond=20 - KENO_BOMBS)
        self.frozen = set(random.sample(range(20), KENO_FROZEN))   # random: a frozen tile can hide a bomb or a diamond
        for i in self.frozen:
            if board[i] == "diamond":       # frozen diamond = bonus prize, frozen bomb = a normal bomb
                board[i] = "ice"
        return board

    def earn(self, kind):
        n = min(len(self.revealed), len(KENO_MULT))
        self.profit = self.bet * (KENO_MULT[n - 1] - 1)

    async def click(self, interaction, idx):
        if not interaction.response.is_done():
            await interaction.response.defer()
        if self.done or idx in self.revealed or len(self.revealed) >= KENO_CLICKS:
            return
        if self.luck_fix(idx):
            spy(self)
        kind = self.board[idx]
        self.reveal(idx)
        if kind == "bomb":
            return await self.finish(interaction, True)
        self.after(kind)
        if len(self.revealed) >= KENO_CLICKS:       # last click used: cash out automatically
            return await self.finish(interaction, False)
        await self.push(interaction)

# ================= 🥶 MONEY TOWER FROZEN =================
class StormTower(StormMixin, MoneyTower):
    game_name = "Storm Money Tower"

    @property
    def header(self):
        return f"**{self.user.name}'s Game** {SNOW}"

    def __init__(self, user, bet, token, frozen):
        self.frozen, self.rows_done, self.extra, self.bonus_lines = set(frozen), 0, 0, []
        super().__init__(user, bet, token)
        for i in self.frozen:
            self.tiles[i].emoji = SNOW

    def recalc(self):
        base = self.bet * (MT_MULT[self.climbed - 1] - 1) if self.climbed else 0
        self.profit = base + self.extra
        self.profit_btn.label = f"Profit: {fmt(self.profit)}"

    def reveal(self, i):
        kind, t = self.board[i], self.tiles[i]
        self.revealed.add(i)
        t.disabled = True
        if kind == "bomb":
            t.emoji, t.style = EMOJI["bomb"], discord.ButtonStyle.danger
        else:
            t.emoji, t.style = MT_SAFE, discord.ButtonStyle.success
            self.climbed += 1
            self.rows_done += 1
            self.recalc()

    def thaw(self, i):
        """A frozen bomb: nothing is lost, the row gives no multiplier, only a small bonus."""
        t = self.tiles[i]
        self.revealed.add(i)
        t.disabled, t.emoji, t.style = True, EMOJI["ice"], discord.ButtonStyle.primary
        self.rows_done += 1
        bonus = max(1, int(self.bet * TOWER_FREEZE_BONUS))
        self.extra += bonus
        self.bonus_lines.append(f"{EMOJI['ice']} Frozen bomb: +{fmt(bonus)} {cur()}")
        self.recalc()

    async def click(self, interaction, idx):
        if not interaction.response.is_done():
            await interaction.response.defer()
        if self.done or idx in self.revealed or idx // 3 != 4 - self.rows_done:
            return
        if idx not in self.frozen and self.luck_fix(idx):
            spy(self)
        kind = self.board[idx]
        if kind == "bomb" and idx in self.frozen:
            self.thaw(idx)
            return await self.push(interaction)
        self.reveal(idx)
        if kind == "bomb":
            return await self.finish(interaction, True)
        await self.push(interaction)

    def embed(self, lost):
        lines = "" if lost else "".join(f"{l}\n" for l in self.bonus_lines)
        return result_embed(self.user, not lost, self.bet if lost else int(self.profit),
                            f"You climbed {self.rows_done} rows.\n{lines}")

async def _launch_tower(pick, interaction, picks):
    game = StormTower(pick.user, pick.bet, pick.token, picks)
    game.message = interaction.message
    await interaction.response.edit_message(content=game.header, embed=None, view=game)

# ================= ⛏️ GOLD MINES (SNOW) =================
class StormGM(GoldMines):
    game_name = "Storm Gold Mines"

    @property
    def header(self):
        return f"**{self.user.name}'s Game** {SNOW}"

    def __init__(self, user, bet, token=None):
        self.ice_hits = []
        super().__init__(user, bet, token)

    def make_board(self):
        board = take(self.user.id, "gm")
        a, b, c = random.sample([i for i, k in enumerate(board) if k == "bomb"], 3)
        board[a] = board[b] = "ice"            # 2 random bombs become snow tiles
        board[c] = random.choices([k for k, _ in GM_GUARANTEED], weights=[w for _, w in GM_GUARANTEED])[0]   # +1 guaranteed item
        return board

    def earn(self, kind):
        if kind == "ice":
            m = random.choices([m for m, _ in GM_ICE_MULT], weights=[w for _, w in GM_ICE_MULT])[0]
            self.ice_hits.append(m)
            self.profit += self.bet * (m - 1)
        else:
            super().earn(kind)

    def embed(self, lost):
        return storm_result(self, lost, [f"{EMOJI['ice']} Snow tile: x{m}" for m in self.ice_hits])

# ================= 🎰 ROULETTE - FROZEN RESCUE =================
class FreezeModal(discord.ui.Modal, title="Freeze 2 numbers"):
    nums = discord.ui.TextInput(label="Two numbers (0-36), for example: 3 7", max_length=12)

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    async def on_submit(self, interaction):
        found = [int(x) for x in re.findall(r"\d+", str(self.nums.value))]
        if len(found) != 2 or found[0] == found[1] or any(n > 36 for n in found):
            return await interaction.response.send_message("Choose 2 different numbers between 0 and 36.", ephemeral=True)
        if self.parent.pick[0].isdigit() and int(self.parent.pick[0]) in found:
            return await interaction.response.send_message("You can't freeze the number you bet on.", ephemeral=True)
        await self.parent.spin(interaction, found)

class RouletteFreeze(OwnedView):
    touch = False

    def __init__(self, user, bet, token, pick):
        super().__init__(timeout=90)
        self.user, self.bet, self.token, self.pick = user, bet, token, pick
        self.spun, self.message = False, None
        b = discord.ui.Button(style=discord.ButtonStyle.primary, label="Freeze 2 numbers", emoji=SNOW)
        b.callback = self.open_modal
        self.add_item(b)

    def embed(self):
        return discord.Embed(color=ROUL_COLOR, title=f"🎰 Roulette - Frozen Rescue {SNOW}", description=(
            f"You bet **{fmt(self.bet)}** {cur()} on **{self.pick[0]}**.\n\n"
            "Freeze **2 numbers**. If the ball lands on one of them and your bet loses, "
            "you are rescued: you get your bet back plus a bonus.\n\nTap the button to choose."))

    async def open_modal(self, interaction):
        if self.spun:
            return await interaction.response.defer()
        await interaction.response.send_modal(FreezeModal(self))

    async def spin(self, interaction, frozen):
        if self.spun:
            return await interaction.response.defer()
        self.spun = True
        self.stop()
        storm_mark(self.user.id, "roulette")
        winner = random.randint(0, 36)
        for _ in range(luck_attempts(0) - 1):
            if self.pick[1](winner) or winner in frozen:
                break
            winner = random.randint(0, 36)
        hit = self.pick[1](winner)
        bet, lines = self.bet, f"🎰 The ball landed on **{winner} ({roul_color(winner)})**\n{SNOW} Frozen: **{frozen[0]}, {frozen[1]}**\n"
        if hit:
            win = bet * self.pick[2]
            net = win - bet
            win += multi_extra("roulette", net)
            net = win - bet
        elif winner in frozen:
            _, kind, label = random.choices(ROUL_RESCUE, weights=[p[0] for p in ROUL_RESCUE])[0]
            extra = {"x2": bet, "cash": int(bet * random.uniform(0.25, 0.75)),
                     "gift": int(bet * random.uniform(1.0, 2.0))}[kind]
            win, net = bet + extra, extra
            lines += f"{SNOW} **Frozen Rescue!** {label}: +{fmt(extra)} {cur()}\n"
        else:
            win, net = 0, -bet
        pending_done(self.token)
        user_data(self.user.id)["cash"] += win
        save()
        log_game(self.user, "Storm Roulette", bet, net)
        await interaction.response.edit_message(embed=result_embed(self.user, net > 0, abs(net), lines), view=None)

    async def on_timeout(self):
        if self.spun:
            return
        pending_done(self.token)
        user_data(self.user.id)["cash"] += self.bet
        save()
        log_money(self.user, "STORM | TIMEOUT", f"Bet of {fmt(self.bet)} {cur()} was returned", YELLOW)
        if self.message:
            await self.message.edit(embed=discord.Embed(description="Timed out, your bet was returned.", color=RED), view=None)

async def storm_roulette(ctx, amount, picktext):
    usage = "storm roulette <amount | half | all> <bet: 0-36, red, black, even, odd, 1-12...>"
    if amount is None:
        return await ctx.reply(f"The minimum bet is {MIN_BET}{cur()}!")
    pick = parse_roul_pick(picktext)
    if pick is None:
        return await reply(ctx, f"Usage: `${usage}`", RED)
    if storm_used(ctx.author.id, "roulette"):
        return await reply(ctx, f"{SNOW} You already used Frozen Rescue in this Storm.", BLUE)
    bet = await take_bet(ctx, amount, usage, track=True)
    if not bet:
        return
    view = RouletteFreeze(ctx.author, bet, str(ctx.message.id), pick)
    try:
        view.message = await ctx.reply(embed=view.embed(), view=view, mention_author=False)
    except Exception:
        cancel_game(ctx.author, view.token, bet)
        raise

# ================= COMMANDS =================
@bot.command(name="stormset", usage="stormset <on [duration] | off>")
async def stormset(ctx, mode: str = None, *, duration: str = None):
    if ctx.author.id not in OWNER_IDS:
        return
    mode = (mode or "").lower()
    if mode == "on":
        secs = parse_duration(duration) if duration else None
        if duration and secs is None:
            return await reply(ctx, "Usage: `$stormset on [duration]` (for example `2h`, `1d`, `30m`)", RED)
        DB["storm"] = {"until": int(time.time() + secs) if secs else 0, "used": {}}
        save()
        return await reply(ctx, f"{SNOW} **Storm is ON** ({fmt_left(DB['storm']['until'])}).", BLUE)
    if mode == "off":
        DB.pop("storm", None)
        save()
        return await reply(ctx, f"{SNOW} Storm is OFF.", BLUE)
    state = f"ON ({fmt_left(DB['storm']['until'])})" if storm_active() else "OFF"
    await reply(ctx, f"{SNOW} Storm is **{state}**. Usage: `$stormset on [duration]` / `$stormset off`", BLUE)

@bot.command(name="storm", usage="storm <roulette | mines | keno | mt | gm> <amount | half | all>")
async def storm(ctx, game: str = None, amount: str = None, *, extra: str = None):
    usage = "storm <roulette | mines | keno | mt | gm> <amount | half | all>"
    if not storm_active():
        return await reply(ctx, f"{SNOW} The Storm is not active right now.", BLUE)
    g = STORM_GAMES.get((game or "").lower())
    if g is None:
        return await reply(ctx, f"Usage: `${usage}`", RED)
    if g == "roulette":
        return await storm_roulette(ctx, amount, extra)
    if g == "gm":
        return await start_board(ctx, StormGM, amount, usage)
    if g == "keno":
        return await start_board(ctx, StormKeno, amount, usage)
    if g == "mines":
        return await start_picker(ctx, amount, usage, "Mines Frozen",
                                  "Tap **2 tiles** to freeze them. Frozen tiles are always diamonds and hide a bonus. "
                                  "The bomb is somewhere else.", 3, 3, False, _launch_mines)
    await start_picker(ctx, amount, usage, "Money Tower Frozen",
                       "Tap **2 tiles in one row** to freeze them (the bottom row is the first). "
                       "If the bomb is under a freeze it gets frozen: you keep climbing without a multiplier, "
                       "with a small bonus.", 3, 5, True, _launch_tower)
