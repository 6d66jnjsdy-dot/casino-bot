import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime, sys
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= STORM (frozen event games) =================
# Owner:    $stormset on [duration]   /   $stormset off
#           - with a duration: every player can use the Storm once every STORM_COOLDOWN
#           - WITHOUT a duration: the Storm never ends and nobody has any limit
# Player:   $storm -> press a game button. The player's NEXT normal command of that game ($mines / $mt / $gm /
#           $roulette) becomes the Storm game. After it, the Storm is locked for 3 hours.
# The owner never has a limit. Everything you may want to tune is in the CONFIG block below.

# ---------- CONFIG ----------
EMOJI.setdefault("ice", "🧊")

STORM_COOLDOWN = 3 * 3600                          # one Storm game every 3 hours per player
STORM_LIMITED = {"roulette", "mines", "mt", "gm"}  # games that count for the limit (remove one to make it free)

# Roulette - Frozen Rescue: (weight, kind, label). The bet is ALWAYS returned, the bonus comes on top of it.
ROUL_RESCUE = [(50, "x2", "Bet doubled"), (30, "cash", "Cash bonus"), (20, "gift", "Random gift")]

# Mines Frozen: 3x4 (like $mines), 1 bomb, 2 frozen tiles (always diamonds, each hides a bonus).
# One multiplier per diamond (11). The first 2 are the frozen ones, so they are tiny.
STORM_MINES_MULT = [1.01, 1.02, 1.05, 1.15, 1.31, 1.53, 1.84, 2.3, 3.07, 4.6, 9.2]

# Money Tower: the small bonus for a frozen bomb, as a fraction of the bet.
TOWER_FREEZE_BONUS = 0.15

# Gold Mines: 2 bombs become snow tiles (random prize multiplier), 1 more bomb becomes a guaranteed item.
GM_ICE_MULT = [(1.5, 50), (2.0, 35), (3.0, 15)]
GM_GUARANTEED = [("stone", 45), ("diamond", 30), ("coin", 15), ("bag", 10)]   # coin and bag are rarer

# Bonus pool for frozen diamonds in Mines: (weight, kind, label, value)
# "mult"   = multiplier on the player's NEXT normal $mines game (applied to the profit)
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
    """Called when a Storm game really starts: the 3 hour wait begins and the armed Storm is used up."""
    DB.get("storm_armed", {}).pop(str(uid), None)
    if storm_limited(uid, game):
        DB.setdefault("storm_last", {})[str(uid)] = int(time.time())
    save()

def storm_wait_text(seconds):
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    return " ".join(f"{v}{u}" for v, u in ((h, "h"), (m, "m"), (s, "s")) if v) or "0s"

def storm_arm(uid, game, **data):
    DB.setdefault("storm_armed", {})[str(uid)] = {"game": game, **data}
    save()

def storm_armed(uid, game):
    a = DB.get("storm_armed", {}).get(str(uid))
    if a and a.get("game") == game and storm_active() and not storm_limit_left(uid, game):
        return a
    return None

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
        bg(dm_owner(discord.Embed(color=BLUE, title="Storm reward to give", description=(
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
# The chosen tiles are only marked (blue) while the player is choosing. Inside the game NOTHING shows where they are.
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
        return discord.Embed(color=BLUE, description=(
            f"**{self.ttl}**\n\nYou bet **{fmt(self.bet)}** {cur()}.\n\n{self.hint}"))

    def mark(self, i, on):
        self.btns[i].style = discord.ButtonStyle.primary if on else discord.ButtonStyle.secondary

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

async def start_picker(ctx, amount, usage, game, ttl, hint, cols, rows, same_row, launch):
    bet = await take_bet(ctx, amount, usage, track=True)
    if not bet:
        return
    storm_mark(ctx.author.id, game)
    view = FreezePick(ctx.author, bet, str(ctx.message.id), ttl, hint, cols, rows, same_row, launch)
    try:
        view.message = await ctx.reply(embed=view.embed(), view=view, mention_author=False)
    except Exception:
        cancel_game(ctx.author, view.token, bet)
        raise

async def start_storm_board(ctx, cls, amount, usage, game):
    bet = await take_bet(ctx, amount, usage, track=True)
    if not bet:
        return
    storm_mark(ctx.author.id, game)
    view = cls(ctx.author, bet, str(ctx.message.id))
    try:
        view.message = await ctx.reply(content=view.header, view=view, mention_author=False)
    except Exception:
        cancel_game(ctx.author, view.token, bet)
        raise

# ================= 💣 MINES FROZEN =================
class StormMines(StormMixin, BoardView):
    cols = 3                         # 3 columns x 4 rows = 12 tiles, like $mines
    game_name = "Storm Mines"
    multi_key = "mines"

    @property
    def header(self):
        return f"**{self.user.name}'s Game**"

    def __init__(self, user, bet, token, frozen):
        self.frozen, self.bonus_lines = set(frozen), []
        super().__init__(user, bet, token)

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

# ================= 🥶 MONEY TOWER FROZEN =================
class StormTower(StormMixin, MoneyTower):
    game_name = "Storm Money Tower"

    def __init__(self, user, bet, token, frozen):
        self.frozen, self.rows_done, self.extra, self.bonus_lines = set(frozen), 0, 0, []
        super().__init__(user, bet, token)

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

    def __init__(self, user, bet, token=None):
        self.ice_hits = []
        super().__init__(user, bet, token)

    def make_board(self):
        board = take(self.user.id, "gm")
        a, b, c = random.sample([i for i, k in enumerate(board) if k == "bomb"], 3)
        board[a] = board[b] = "ice"            # 2 random bombs become snow tiles (hidden like every other tile)
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
# A Storm bet is a normal roulette bet (same round, same 30 seconds) that carries "frozen" numbers.
# This runner replaces run_roulette (patched below), it behaves exactly like the original for normal bets.
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
                lines.append(f"🧊 {b['user'].mention} Frozen Rescue - {fmt(win)} {cur()}")
            else:
                lines.append(f"❌ {b['user'].mention} Lost")
        save()
        frozen_all = sorted({n for b in bets for n in (b.get("frozen") or [])})
        frozen_line = f"\nFrozen numbers: {', '.join(map(str, frozen_all))}" if frozen_all else ""
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

# ================= HOOKS: the normal commands become the Storm game when the player armed it =================
def install_storm_hooks():
    mines_cmd, gm_cmd, mt_cmd, roul_cmd = (bot.get_command(n) for n in ("mines", "gm", "mt", "roulette"))
    o_mines, o_gm, o_mt, o_roul = mines_cmd.callback, gm_cmd.callback, mt_cmd.callback, roul_cmd.callback

    async def mines_hook(ctx, amount: str = None):
        if ctx.prefix.lower() != "s$" and storm_armed(ctx.author.id, "mines"):
            return await start_picker(
                ctx, amount, "mines <amount | half | all>", "mines", "Choose 2 tiles to freeze",
                "Frozen tiles are safe diamonds and each hides a bonus. The bomb is somewhere else.",
                3, 4, False, _launch_mines)
        return await o_mines(ctx, amount)

    async def gm_hook(ctx, amount: str = None):
        if storm_armed(ctx.author.id, "gm"):
            return await start_storm_board(ctx, StormGM, amount, "gm <amount | half | all>", "gm")
        return await o_gm(ctx, amount)

    async def mt_hook(ctx, amount: str = None):
        if storm_armed(ctx.author.id, "mt"):
            return await start_picker(
                ctx, amount, "mt <amount | half | all>", "mt", "Choose 2 tiles in one row to freeze",
                "The bottom row is the first row. If the bomb is under a frozen tile, you keep climbing "
                "without a multiplier and get a small bonus.", 3, 5, True, _launch_tower)
        return await o_mt(ctx, amount)

    async def roul_hook(ctx, amount: str = None, *, picks: str = None):
        arm = storm_armed(ctx.author.id, "roulette")
        if not arm:
            return await o_roul(ctx, amount, picks=picks)
        nums = arm["frozen"]
        choices = roul_pick_list(picks) or []
        if any(c[0].isdigit() and int(c[0]) in nums for c in choices):
            return await reply(ctx, "You can't bet on a number you froze.", RED)
        await o_roul(ctx, amount, picks=picks)
        base = str(ctx.message.id)
        rnd = ROUNDS.get(ctx.channel.id)
        mine = [b for b in (rnd["bets"] if rnd else []) if b["token"].split(":")[0] == base]
        if mine:                                   # the bet was really placed: it carries the frozen numbers
            for b in mine:
                b["frozen"] = list(nums)
            storm_mark(ctx.author.id, "roulette")

    mines_cmd.callback, gm_cmd.callback, mt_cmd.callback, roul_cmd.callback = mines_hook, gm_hook, mt_hook, roul_hook

try:
    install_storm_hooks()
except Exception as _ex:
    print("Storm: could not install command hooks:", repr(_ex))

# ================= PANEL ($storm) =================
STORM_GAMES = (("roulette", "🎰", "Roulette", "$roulette <amount> <bet>"),
               ("mines", "💣", "Mines", "$mines <amount>"),
               ("mt", "🥶", "Money Tower", "$mt <amount>"),
               ("gm", "⛏️", "Gold Mines", "$gm <amount>"))

class FreezeNumbers(discord.ui.Modal, title="Roulette - Frozen Rescue"):
    nums = discord.ui.TextInput(label="Freeze 2 numbers (0-36)", placeholder="3 7", max_length=12)

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction):
        found = [int(x) for x in re.findall(r"\d+", str(self.nums.value))]
        if len(found) != 2 or found[0] == found[1] or any(n > 36 for n in found):
            return await interaction.response.send_message("Choose 2 different numbers between 0 and 36.", ephemeral=True)
        await self.panel.arm(interaction, "roulette", frozen=found)

class StormPanel(OwnedView):
    touch = False

    def __init__(self, user):
        super().__init__(timeout=120)
        self.user, self.message = user, None
        for key, emoji, label, _ in STORM_GAMES:
            b = discord.ui.Button(style=discord.ButtonStyle.primary, label=label, emoji=emoji)
            b.callback = self.opener(key)
            self.add_item(b)

    def opener(self, game):
        async def cb(interaction):
            if not storm_active():
                return await interaction.response.send_message("The Storm is not active right now.", ephemeral=True)
            left = storm_limit_left(self.user.id, game)
            if left:
                return await interaction.response.send_message(
                    f"You can use the Storm again in {storm_wait_text(left)}.", ephemeral=True)
            if game == "roulette":
                return await interaction.response.send_modal(FreezeNumbers(self))
            await self.arm(interaction, game)
        return cb

    async def arm(self, interaction, game, **data):
        storm_arm(self.user.id, game, **data)
        self.stop()
        name, cmd = next((l, c) for k, _, l, c in STORM_GAMES if k == game)
        extra = f" Frozen numbers: **{data['frozen'][0]}, {data['frozen'][1]}**." if game == "roulette" else ""
        await interaction.response.edit_message(view=None, embed=make_embed(
            self.user, f"**{name}** is ready.{extra}\nYour next `{cmd}` is the Storm game.", BLUE))

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass

# ================= COMMANDS =================
@bot.command(name="storm", usage="storm")
async def storm(ctx):
    if not storm_active():
        return await reply(ctx, "The Storm is not active right now.", BLUE)
    left = storm_limit_left(ctx.author.id)
    if left:
        return await reply(ctx, f"You can use the Storm again in **{storm_wait_text(left)}**.", RED)
    view = StormPanel(ctx.author)
    view.message = await ctx.reply(embed=make_embed(
        ctx.author, "**Storm**\nChoose a game. Your next game of that type will be a Storm game.", BLUE),
        view=view, mention_author=False)

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
        return await reply(ctx, f"**Storm is ON** ({note}).", BLUE)
    if mode == "off":
        DB.pop("storm", None)
        save()
        return await reply(ctx, "Storm is OFF.", BLUE)
    state = f"ON ({fmt_left(DB['storm']['until'])})" if storm_active() else "OFF"
    await reply(ctx, f"Storm is **{state}**. Usage: `$stormset on [duration]` / `$stormset off`", BLUE)
