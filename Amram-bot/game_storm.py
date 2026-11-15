import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime, sys
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= STORM (frozen event games) =================
# Owner:    $stormset on [duration]   /   $stormset off
#           - with a duration: players can play once every STORM_COOLDOWN
#           - WITHOUT a duration: the Storm never ends and nobody has any limit
# Players:  $storm  -> a panel opens, pick the game with a button
# The owner never has a limit. Everything you may want to tune is in the CONFIG block below.

# ---------- CONFIG ----------
STORM_COLOR = 0x8FD3F4
EMOJI.setdefault("ice", "🧊")
SNOW = "❄️"

STORM_COOLDOWN = 3 * 3600                                   # one Storm game every 3 hours per player
STORM_LIMITED = {"roulette", "mines", "keno", "mt", "gm"}   # games that count for the limit (remove one to make it free)

STORM_INFO = {                                              # key: (emoji, button label, title)
    "roulette": ("🎰", "Roulette", "Roulette - Frozen Rescue"),
    "mines": ("💣", "Mines", "Mines Frozen"),
    "keno": ("🎯", "Keno", "Keno Snow"),
    "mt": ("🥶", "Money Tower", "Money Tower Frozen"),
    "gm": ("⛏️", "Gold Mines", "Gold Mines Snow"),
}

# Roulette - Frozen Rescue: (weight, kind, label). The bet is ALWAYS returned, the bonus comes on top of it.
ROUL_RESCUE = [(50, "x2", "Bet doubled"), (30, "cash", "Cash bonus"), (20, "gift", "Random gift")]

# Mines Frozen: 3x4 (like $mines), 1 bomb, 2 frozen tiles (always diamonds, each hides a bonus).
# One multiplier per diamond (11). The first 2 are the frozen ones, so they are tiny.
STORM_MINES_MULT = [1.01, 1.02, 1.05, 1.15, 1.31, 1.53, 1.84, 2.3, 3.07, 4.6, 9.2]

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

def storm_limited(uid, game=None):
    """True when this player is under the Storm limit (the owner and a Storm without an end time are never limited)."""
    if uid in OWNER_IDS:
        return False
    s = DB.get("storm") or {}
    if not s.get("until"):
        return False
    return game is None or game in STORM_LIMITED

def storm_limit_left(uid, game=None):
    if not storm_limited(uid, game):
        return 0
    last = DB.get("storm_last", {}).get(str(uid), 0)
    return max(0, int(last + STORM_COOLDOWN - time.time()))

def storm_mark(uid, game):
    if storm_limited(uid, game):
        DB.setdefault("storm_last", {})[str(uid)] = int(time.time())
        save()

def storm_wait_text(seconds):
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    return " ".join(f"{v}{u}" for v, u in ((h, "h"), (m, "m"), (s, "s")) if v) or "0s"

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

def storm_take_bet(user, amount_text, token, busy=True):
    """Same rules as take_bet, but for a modal. Returns (bet, error_text)."""
    if busy and user.id in BUSY:
        return None, BUSY_MSG
    u = user_data(user.id)
    bet = parse_amount((amount_text or "").strip(), u["cash"])
    if bet is None:
        return None, f"Enter a valid amount (min {MIN_BET})."
    if bet < MIN_BET:
        return None, f"The minimum bet is {MIN_BET}{cur()}!"
    if bet > u["cash"]:
        return None, "You don't have that much money."
    u["cash"] -= bet
    DB.setdefault("pending", {})[token] = {"uid": str(user.id), "bet": bet}
    if busy:
        BUSY.add(user.id)
    save()
    return bet, None

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

# ---------- animation ----------
def snow_art(rows=3, cols=9):
    return "\n".join(" ".join(random.choice((SNOW, "⠀", "⠀", "✦")) for _ in range(cols)) for _ in range(rows))

async def storm_anim(interaction, title, steps=("Gathering the clouds...", "Freezing the board...", "The Storm arrives...")):
    """Short snowfall on the panel message. The first frame is the answer to the interaction."""
    first = True
    for s in steps:
        e = discord.Embed(color=STORM_COLOR, description=f"{snow_art()}\n\n**{SNOW} {title}**\n{s}")
        try:
            if first:
                await interaction.response.edit_message(content=None, embed=e, view=None)
            else:
                await interaction.edit_original_response(embed=e)
        except discord.HTTPException:
            pass
        first = False
        await asyncio.sleep(0.6)

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

# ================= 💣 MINES FROZEN =================
class StormMines(StormMixin, BoardView):
    cols = 3                         # 3 columns x 4 rows = 12 tiles, like $mines
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
        board = ["diamond"] * 12
        board[random.choice([i for i in range(12) if i not in self.frozen])] = "bomb"   # never under a freeze
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

# ================= 🎰 ROULETTE - FROZEN RESCUE (the normal 30 second round) =================
# A Storm bet joins the SAME round as every other roulette bet (ROUNDS / ROUL_WAIT from game_roulette.py).
# The only difference: the bet carries "frozen" numbers. This runner replaces run_roulette (patched below),
# it behaves exactly like the original for normal bets.
def rescue_bonus(bet):
    _, kind, label = random.choices(ROUL_RESCUE, weights=[p[0] for p in ROUL_RESCUE])[0]
    extra = {"x2": bet, "cash": int(bet * random.uniform(0.25, 0.75)), "gift": int(bet * random.uniform(1.0, 2.0))}[kind]
    return max(1, extra), label

async def storm_run_roulette(cid, rnd):
    try:
        await asyncio.sleep(max(0, rnd["end"] - time.time()))
        if ROUNDS.get(cid) is rnd:
            ROUNDS.pop(cid, None)
        bets = rnd["bets"]
        winner = random.randint(0, 36)
        for _ in range(luck_attempts(0) - 1):
            if any(b["pick"][1](winner) for b in bets):
                break
            winner = random.randint(0, 36)
        color_name = roul_color(winner)
        lines = []
        for b in bets:
            hit = b["pick"][1](winner)
            fr = b.get("frozen")
            rescued = (not hit) and bool(fr) and winner in fr
            extra = 0
            if hit:
                win = b["per"] * b["pick"][2]
            elif rescued:
                extra, _ = rescue_bonus(b["per"])
                win = b["per"] + extra
            else:
                win = 0
            net = win - b["per"]
            if hit and net > 0:
                win += multi_extra("roulette", net)
                net = win - b["per"]
            DB.get("pending", {}).pop(b["token"], None)
            user_data(b["user"].id)["cash"] += win
            log_game(b["user"], "Storm Roulette" if fr else "roulette", b["per"], net)
            if hit:
                lines.append(f"🏆 {b['user'].mention} Won - {fmt(win)} {cur()}")
            elif rescued:
                lines.append(f"{SNOW} {b['user'].mention} Frozen Rescue - {fmt(win)} {cur()} (+{fmt(extra)})")
            else:
                lines.append(f"❌ {b['user'].mention} Lost")
        save()
        frozen_all = sorted({n for b in bets for n in (b.get("frozen") or [])})
        frozen_line = f"\n{SNOW} Frozen numbers: {', '.join(map(str, frozen_all))}" if frozen_all else ""
        e = discord.Embed(color=ROUL_COLOR, title="Roulette Results", description=(
            f"The ball landed on **{winner} ({color_name.capitalize()})**{frozen_line}\n\n**Results**\n" + "\n".join(lines)))
        await rnd["channel"].send(embed=e, allowed_mentions=discord.AllowedMentions.none())
    except Exception as ex:
        print("Roulette failed:", repr(ex))
        if ROUNDS.get(cid) is rnd:
            ROUNDS.pop(cid, None)
        for b in rnd["bets"]:
            if DB.get("pending", {}).pop(b["token"], None) is not None:
                user_data(b["user"].id)["cash"] += b["per"]
        save()

try:
    sys.modules["game_roulette"].run_roulette = storm_run_roulette
except Exception as _ex:
    print("Storm: could not patch run_roulette:", repr(_ex))

# ================= PANEL ($storm) =================
def storm_limit_text(uid):
    left = storm_limit_left(uid)
    if not storm_limited(uid):
        return "✨ No limit for you right now."
    return f"⏳ Your next Storm game in **{storm_wait_text(left)}**." if left else "✅ Your Storm is ready."

def panel_embed(uid):
    return discord.Embed(color=STORM_COLOR, title=f"{SNOW} The Storm {SNOW}", description=(
        "Choose a game below. Every game has a frozen twist.\n\n"
        "🎰 **Roulette** - freeze 2 numbers and get rescued if the ball lands on one\n"
        "💣 **Mines** - freeze 2 tiles, they hide bonuses\n"
        "🎯 **Keno** - 6 clicks and 4 random freezes\n"
        "🥶 **Money Tower** - freeze 2 tiles in one row\n"
        "⛏️ **Gold Mines** - snow tiles instead of bombs\n\n"
        f"{storm_limit_text(uid)}"))

class StormModal(discord.ui.Modal):
    def __init__(self, panel, game):
        super().__init__(title=STORM_INFO[game][2])
        self.panel, self.game = panel, game
        self.amount = discord.ui.TextInput(label="Bet amount (or all / half)", placeholder="1000", max_length=15)
        self.add_item(self.amount)
        if game == "roulette":
            self.pick = discord.ui.TextInput(label="Your bet: 0-36, red, black, even, odd", placeholder="red", max_length=20)
            self.frozen = discord.ui.TextInput(label="Freeze 2 numbers (0-36)", placeholder="3 7", max_length=12)
            self.add_item(self.pick)
            self.add_item(self.frozen)

    async def on_submit(self, interaction):
        await self.panel.submit(interaction, self)

class StormPanel(OwnedView):
    touch = False

    def __init__(self, user):
        super().__init__(timeout=120)
        self.user, self.started, self.message = user, False, None
        for key, (emoji, label, _) in STORM_INFO.items():
            b = discord.ui.Button(style=discord.ButtonStyle.primary, label=label, emoji=emoji)
            b.callback = self.opener(key)
            self.add_item(b)

    def opener(self, game):
        async def cb(interaction):
            if self.started:
                return await interaction.response.send_message("Already started.", ephemeral=True)
            if not storm_active():
                return await interaction.response.send_message(f"{SNOW} The Storm is not active right now.", ephemeral=True)
            left = storm_limit_left(self.user.id, game)
            if left:
                return await interaction.response.send_message(
                    f"{SNOW} You can play again in **{storm_wait_text(left)}**.", ephemeral=True)
            await interaction.response.send_modal(StormModal(self, game))
        return cb

    async def on_timeout(self):
        if self.started or not self.message:
            return
        try:
            await self.message.edit(view=None)
        except discord.HTTPException:
            pass

    async def submit(self, interaction, modal):
        game, user = modal.game, self.user

        async def no(text):
            await interaction.response.send_message(text, ephemeral=True)

        if self.started:
            return await no("Already started.")
        if not storm_active():
            return await no(f"{SNOW} The Storm is not active right now.")
        left = storm_limit_left(user.id, game)
        if left:
            return await no(f"{SNOW} You can play again in **{storm_wait_text(left)}**.")
        pick = nums = None
        if game == "roulette":
            pick = parse_roul_pick(modal.pick.value)
            nums = [int(x) for x in re.findall(r"\d+", modal.frozen.value)]
            if pick is None:
                return await no("Invalid bet. Use 0-36, red, black, even, odd, 1-12...")
            if len(nums) != 2 or nums[0] == nums[1] or any(n > 36 for n in nums):
                return await no("Freeze 2 different numbers between 0 and 36.")
            if pick[0].isdigit() and int(pick[0]) in nums:
                return await no("You can't freeze the number you bet on.")
        token = str(interaction.id) + (":0" if game == "roulette" else "")
        bet, err = storm_take_bet(user, modal.amount.value, token, busy=(game != "roulette"))
        if err:
            return await no(err)
        self.started = True
        self.stop()
        storm_mark(user.id, game)
        title = STORM_INFO[game][2]
        if game == "roulette":
            return await self.start_roulette(interaction, bet, pick, nums, token, title)
        try:
            await storm_anim(interaction, title)
            if game in ("gm", "keno"):
                view = (StormGM if game == "gm" else StormKeno)(user, bet, token)
                view.message = await interaction.original_response()
                await interaction.edit_original_response(content=view.header, embed=None, view=view)
            else:
                mines = game == "mines"
                hint = ("Tap **2 tiles** to freeze them. Frozen tiles are always diamonds and hide a bonus. "
                        "The bomb is somewhere else." if mines else
                        "Tap **2 tiles in one row** to freeze them (the bottom row is the first). "
                        "If the bomb is under a freeze it gets frozen: you keep climbing without a multiplier, "
                        "with a small bonus.")
                picker = FreezePick(user, bet, token, title, hint, 3, 4 if mines else 5, not mines,
                                    _launch_mines if mines else _launch_tower)
                picker.message = await interaction.original_response()
                await interaction.edit_original_response(embed=picker.embed(), view=picker)
        except Exception:
            cancel_game(user, token, bet)
            raise

    async def start_roulette(self, interaction, bet, pick, nums, token, title):
        user, cid = self.user, interaction.channel.id
        rnd = ROUNDS.get(cid)
        opened = rnd is None or rnd["end"] <= time.time()
        if opened:
            rnd = {"end": int(time.time()) + ROUL_WAIT, "bets": [], "channel": interaction.channel}
            ROUNDS[cid] = rnd
        entry = {"user": user, "per": bet, "pick": pick, "token": token, "frozen": nums}
        rnd["bets"].append(entry)
        none = discord.AllowedMentions.none()
        try:
            await storm_anim(interaction, title)
            await interaction.edit_original_response(embed=discord.Embed(color=ROUL_COLOR, title=f"🎰 {title} {SNOW}", description=(
                f"Bet: **{fmt(bet)}** {cur()} on **{pick[0]}**\n{SNOW} Frozen: **{nums[0]}, {nums[1]}**\n\n"
                f"The ball rolls <t:{rnd['end']}:R>.")), view=None)
            if opened:
                e = roul_embed(rnd)
                e.description += f"\n{SNOW} Frozen Rescue is on: numbers can be frozen for a second chance."
                await interaction.followup.send(embed=e, allowed_mentions=none)
        except Exception:
            if entry in rnd["bets"]:
                rnd["bets"].remove(entry)
            if DB.get("pending", {}).pop(token, None) is not None:
                user_data(user.id)["cash"] += bet
            save()
            if opened and ROUNDS.get(cid) is rnd:
                ROUNDS.pop(cid, None)
            raise
        if opened:
            bg(storm_run_roulette(cid, rnd))

# ================= COMMANDS =================
@bot.command(name="storm", usage="storm")
async def storm(ctx):
    if not storm_active():
        return await reply(ctx, f"{SNOW} The Storm is not active right now.", BLUE)
    view = StormPanel(ctx.author)
    msg = await ctx.reply(embed=discord.Embed(color=STORM_COLOR, description=(
        f"{snow_art()}\n\n**{SNOW} The Storm is rising...**")), mention_author=False)
    await asyncio.sleep(1.0)
    view.message = await msg.edit(embed=panel_embed(ctx.author.id), view=view)

@bot.command(name="stormset", usage="stormset <on [duration] | off>")
async def stormset(ctx, mode: str = None, *, duration: str = None):
    if ctx.author.id not in OWNER_IDS:
        return
    mode = (mode or "").lower()
    if mode == "on":
        secs = parse_duration(duration) if duration else None
        if duration and secs is None:
            return await reply(ctx, "Usage: `$stormset on [duration]` (for example `2h`, `1d`, `30m`)", RED)
        DB["storm"] = {"until": int(time.time() + secs) if secs else 0}
        save()
        note = f"{fmt_left(DB['storm']['until'])}, one game every 3 hours per player" if secs else "no end time, no limits for anyone"
        return await reply(ctx, f"{SNOW} **Storm is ON** ({note}).", BLUE)
    if mode == "off":
        DB.pop("storm", None)
        save()
        return await reply(ctx, f"{SNOW} Storm is OFF.", BLUE)
    state = f"ON ({fmt_left(DB['storm']['until'])})" if storm_active() else "OFF"
    await reply(ctx, f"{SNOW} Storm is **{state}**. Usage: `$stormset on [duration]` / `$stormset off`", BLUE)
