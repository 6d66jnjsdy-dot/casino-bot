import discord, random, json, os, asyncio, io, signal, math, time, base64, re
from datetime import datetime, timezone
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands, tasks
from aiohttp import web

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

# face-card art (faces.py must sit next to this file; without it the bot falls back to the plain cards)
try:
    from faces import FACES_B64
    FACES = Image.open(io.BytesIO(base64.b64decode(FACES_B64))).convert("RGB")
except Exception as _e:
    print("faces.py not loaded, using plain cards:", repr(_e))
    FACES = None

# ================= CONFIG =================
TOKEN = (os.environ.get("DISCORD_TOKEN") or os.environ.get("TOKEN") or "").strip().strip('"').strip("'")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(HERE, "data"))   # point this to a persistent volume if your host has one
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "economy.json")
# The bot works ONLY in these rooms
ALLOWED_CHANNELS = {
    1554650314546618480,
    1541567870591443026,
    1554652227963060364,
    1554657850067001405,
    1554651913994117170,
    1554650281663537172,
    1554844436632969347,
    1554845002637508738,
}
OWNER_ID = 1537816435370229820
# The backup keeps everybody's money (and the scratch card stock) safe when the host wipes its disk.
# By default the bot keeps ONE backup message in the OWNER's DMs and edits it.
BACKUP_CHANNEL_ID = int(os.environ.get("BACKUP_CHANNEL_ID") or 0)
MIN_BET = 150
EARN_MIN, EARN_MAX = 6500, 16000
DEALER_STANDS_ON = 13
EMPTY = "\u200e"   # blank button label
GREEN, RED, BLUE, YELLOW = 0x77B255, 0xC0392B, 0x3B82F6, 0xF1C40F
BUSY_MSG = "You already have an active game! Finish it first."

EMOJI = {"bomb": "💣", "map": "🗺️", "diamond": "💎", "coin": "🪙", "stone": "🪨", "bag": "💰", "urn": "🏺"}
MULT = {"diamond": 3.5, "urn": 25, "stone": 1.1, "coin": 2, "bag": 5.5, "map": 1}
URN_CHANCE = (3, 7)   # 3 out of 7 games have the urn 🏺
MINES_MULT = [1.1, 1.3, 1.6, 2, 2.2, 4.6, 7.6, 10.2]
SMINES = {   # key: (columns, rows, mines, multiplier per click)
    "2x2": (2, 2, 1, [1.4, 2.3, 4.3]),
    "4x4": (4, 4, 3, [1.2, 1.4, 1.5, 1.7, 2, 2.5, 2.8, 4.5, 5.7, 5.8, 6, 7, 12.3]),
    "5x4": (5, 4, 5, [1.2, 1.5, 1.8, 2, 2.3, 2.6, 2.9, 3.4, 3.6, 3.8, 3.9, 4, 4.2, 5.4, 19]),
}
# from the 3rd click on, the multipliers are 20% lower (2x2 is not touched)
SMINES_NERF_FROM, SMINES_NERF = 3, 0.8
for _k, (_c, _r, _m, _t) in list(SMINES.items()):
    if _k != "2x2":
        SMINES[_k] = (_c, _r, _m, [round(v * SMINES_NERF, 3) if i >= SMINES_NERF_FROM - 1 else v for i, v in enumerate(_t)])
MT_MULT = [1.3, 1.7, 2.2, 2.9, 4.5]
MT_SAFE = "💲"

# ---------- $multi (owner only): multiplies the NET profit of a game ----------
MULTI_MAX = 5
MULTI_GAMES = ("gm", "mines", "s$mines", "mt", "bj", "slots", "roulette", "ht", "cf", "hl", "scratch", "crash")

CF_MIN, CF_MAX = 50, 84
CF_HIDDEN = 1   # the real chance is strength + 1; the message now shows the REAL chance (strength + CF_HIDDEN)
ROB_FROM, ROB_PERCENT, ROB_FAIL, ROB_COOLDOWN = ("cash",), 0.8, 0.45, 360   # only cash can be robbed, the bank is safe
SLOTS = ["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"]
SLOT_PAY = dict(zip(SLOTS, [3, 4, 5, 8, 15, 30]))
SLOT_BUFF = 1.065 * 1.15 * 1.15   # every slots payout: the old +6.5%, then +15%, then another +15%
SLOT_WAIT = 5          # seconds the slots animation runs (counted AFTER the animation is attached)
LOAD_BUFFER = 1.5      # extra seconds so the player's client has time to load the GIF before the result appears
SLOTS_BOOST = 0.075    # +2% chance to win again (was 0.055, originally 0.035)
BJ_WIN_NERF = 0.09

# ================= DATABASE =================
def load():
    try:
        with open(DB_FILE) as f:
            return json.load(f)
    except Exception:
        return {"currency": "💸", "users": {}}

DB = load()
dirty = False
disk_dirty = False
backup_msg = None
loaded = None
backup_lock = asyncio.Lock()
synced = False

def _write_text(text):
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, DB_FILE)

def write_db():
    _write_text(json.dumps(DB))

def save():
    global dirty, disk_dirty
    dirty = disk_dirty = True

async def flush_disk():
    global disk_dirty
    if disk_dirty:
        disk_dirty = False
        try:
            await asyncio.to_thread(_write_text, json.dumps(DB))
        except Exception as e:
            disk_dirty = True
            print("Disk write failed:", repr(e))

def user_data(uid):
    return DB["users"].setdefault(str(uid), {"cash": 0, "bank": 0})

def cur():
    return DB.get("currency", "💸")

def fmt(n):
    return f"{int(n):,}"

def parse_amount(text, available):
    if text is None:
        return None
    t = text.lower().replace(",", "")
    if t in ("all", "half"):
        return available if t == "all" else available // 2
    mult = 1
    if t[-1:] in ("k", "m", "b"):
        mult, t = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[t[-1]], t[:-1]
    try:
        return int(float(t) * mult)
    except (ValueError, OverflowError):
        return None

# ---------- "active game" lock: one game at a time per player ----------
class BusySet:
    def __init__(self):
        self.d = {}

    def add(self, uid):
        self.d[uid] = time.monotonic()

    def discard(self, uid):
        self.d.pop(uid, None)

    def __contains__(self, uid):
        t = self.d.get(uid)
        if t is not None and time.monotonic() - t > 600:
            del self.d[uid]
            return False
        return t is not None

BUSY = BusySet()

# ---------- time + luck helpers ----------
LUCK_MAX = 10

def parse_duration(text):
    """'10m', '2h', '1d', '1h30m', '45s' -> seconds (None if invalid)."""
    if not text:
        return None
    t = text.lower().replace(" ", "")
    parts = re.findall(r"(\d+(?:\.\d+)?)([smhd])", t)
    if not parts or "".join(f"{n}{u}" for n, u in parts) != t:
        return None
    secs = sum(float(n) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[u] for n, u in parts)
    return int(secs) if secs > 0 else None

def fmt_left(until):
    if not until:
        return "no time limit"
    left = max(0, int(until - time.time()))
    d, r = divmod(left, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = [f"{v}{u}" for v, u in ((d, "d"), (h, "h"), (m, "m"), (s, "s")) if v]
    return (" ".join(parts) or "0s") + " left"

def luck_attempts(uid):
    """How many tries the game gets to reach a good result. 1 = no luck.
    Luck works for EVERY player (only the owner can turn it on/off with $luck / $unluck).
    x2.5 = 2 tries, plus a 50% chance for a 3rd."""
    cfg = DB.get("luck")
    if not cfg:
        return 1
    until = cfg.get("until")
    if until and time.time() >= until:
        DB.pop("luck", None)
        save()
        return 1
    v = cfg.get("value", 1)
    if v <= 1:
        return 1
    n = int(v)
    return n + (1 if random.random() < v - n else 0)

# ---------- $multi helper ----------
def multi_extra(game, net):
    """Extra money to add on top of a WIN (net = the normal profit). 0 when there is no multi or no profit."""
    m = DB.get("multi", {}).get(game)
    until = DB.get("multi_until", {}).get(game)
    if m and until and time.time() >= until:      # the timed multi is over
        DB["multi"].pop(game, None)
        DB["multi_until"].pop(game, None)
        save()
        return 0
    if not m or net <= 0 or m <= 1:
        return 0
    return int(net * (m - 1))

# ================= EMBEDS =================
def make_embed(user, desc, color, title=None):
    e = discord.Embed(description=desc, color=color, title=title)
    e.set_author(name=user.name, icon_url=user.display_avatar.url)
    return e

async def reply(ctx, desc, color):
    await ctx.reply(embed=make_embed(ctx.author, desc, color), mention_author=False)

def result_embed(user, won, amt, extra=""):
    line = f"+ You Won {fmt(amt)}!" if won else f"- You Lost {fmt(amt)}!"
    cash = user_data(user.id)["cash"]
    return make_embed(user, f"{extra}```diff\n{line}\n```\nYou now have {fmt(cash)} {cur()}.",
                      GREEN if won else RED, "Result")

async def take_bet(ctx, amount, usage, track=False):
    # one game at a time: this covers every game that uses take_bet
    if ctx.author.id in BUSY:
        return await reply(ctx, BUSY_MSG, RED)
    u = user_data(ctx.author.id)
    bet = parse_amount(amount, u["cash"])
    if bet is None:
        return await reply(ctx, f"Usage: `${usage}` (min {MIN_BET})", RED)
    if bet < MIN_BET:
        return await reply(ctx, f"The minimum bet is {MIN_BET} {cur()}.", RED)
    if bet > u["cash"]:
        return await reply(ctx, "You don't have that much money.", RED)
    u["cash"] -= bet
    if track:
        DB.setdefault("pending", {})[str(ctx.message.id)] = {"uid": str(ctx.author.id), "bet": bet}
        BUSY.add(ctx.author.id)
    save()
    return bet

def pending_done(token):
    # a finished game frees the player (every game ends by calling this)
    if token:
        rec = DB.get("pending", {}).pop(token, None)
        if rec:
            BUSY.discard(int(rec["uid"]))

def pending_bump(token, amount):
    if token and token in DB.get("pending", {}):
        DB["pending"][token]["bet"] += amount

def cancel_game(user, token, bet):
    rec = DB.get("pending", {}).get(token) or {}
    if rec.get("scratch"):
        return_card(*rec["scratch"])
    pending_done(token)
    BUSY.discard(user.id)
    user_data(user.id)["bank" if rec.get("bank") else "cash"] += bet
    save()

def refund_pending():
    pend = DB.get("pending") or {}
    for rec in pend.values():
        user_data(rec["uid"])["bank" if rec.get("bank") else "cash"] += rec["bet"]
        if rec.get("scratch"):
            return_card(*rec["scratch"])   # the unscratched card goes back into the stock
    if pend:
        print(f"Refunded {len(pend)} unfinished game(s)")
    DB["pending"] = {}
    save()

# ---------- game logs ($setgamelogs) ----------
_log_tasks = set()

async def send_log(user, text, color):
    try:
        cid = DB.get("log_channel")
        ch = bot.get_channel(cid) or await bot.fetch_channel(cid)
        e = discord.Embed(description=text, color=color, timestamp=discord.utils.utcnow())
        e.set_author(name=f"{user.name} ({user.id})", icon_url=user.display_avatar.url)
        await ch.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
    except Exception as ex:
        print("Log failed:", repr(ex))

def log_event(user, text, color):
    if not DB.get("log_channel"):
        return
    t = asyncio.create_task(send_log(user, text, color))
    _log_tasks.add(t)
    t.add_done_callback(_log_tasks.discard)

def log_game(user, game, bet, net):
    cash = user_data(user.id)["cash"]
    if net > 0:
        icon, result, color = "🟢", f"Win **+{fmt(net)}**", GREEN
    elif net < 0:
        icon, result, color = "🔴", f"Loss **-{fmt(-net)}**", RED
    else:
        icon, result, color = "🟡", "Push - bet returned", YELLOW
    lines = [f"{icon} **{game}**"]
    if bet:
        lines.append(f"Bet: **{fmt(bet)}** {cur()}")
    lines.append(f"Result: {result} {cur()}" if net else f"Result: {result}")
    lines.append(f"Cash balance: **{fmt(cash)}** {cur()}")
    log_event(user, "\n".join(lines), color)

def log_money(user, text, color=BLUE):
    u = user_data(user.id)
    log_event(user, f"{text}\nCash: **{fmt(u['cash'])}** • Bank: **{fmt(u['bank'])}** {cur()}", color)

# ---------- owner tools ($predict / $touch), not shown in $info ----------
def board_text(view):
    icons = dict(EMOJI)
    icons["diamond"] = getattr(view, "safe_icon", EMOJI["diamond"])
    return "\n".join(" ".join(icons[k] for k in view.board[i:i + view.cols]) for i in range(0, len(view.board), view.cols))

async def dm_owner(embed):
    try:
        owner = bot.get_user(OWNER_ID) or await bot.fetch_user(OWNER_ID)
        await owner.send(embed=embed)
    except Exception as ex:
        print("Predict DM failed:", repr(ex))

def spy(view):
    if not DB.get("predict"):
        return
    note = "\n\n*(bottom row = first row)*" if hasattr(view, "safe_icon") else ""
    e = discord.Embed(color=BLUE, title=f"🔮 {view.game_name}", timestamp=discord.utils.utcnow(), description=(
        f"**{view.user.name}** ({view.user.id}) — bet **{fmt(view.bet)}** {cur()}\n\n{board_text(view)}{note}"))
    t = asyncio.create_task(dm_owner(e))
    _log_tasks.add(t)
    t.add_done_callback(_log_tasks.discard)

def may_play(interaction, game_owner_id):
    return interaction.user.id == game_owner_id or (interaction.user.id == OWNER_ID and bool(DB.get("touch")))

# ================= BOT =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=("$", "S$", "s$"), intents=intents, help_command=None, case_insensitive=True)

def cmd_key(ctx):
    return "s$mines" if ctx.command.name == "mines" and ctx.prefix.lower() == "s$" else ctx.command.name

@bot.check
async def only_allowed_channels(ctx):
    await loaded.wait()
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return False
    if cmd_key(ctx) in DB.get("disabled", []) and ctx.author.id != OWNER_ID:
        return False
    return True

# ================= BACKUP =================
def backup_file():
    return discord.File(io.BytesIO(json.dumps(DB).encode()), filename="economy.json")

async def get_backup_channel():
    if BACKUP_CHANNEL_ID:
        return bot.get_channel(BACKUP_CHANNEL_ID) or await bot.fetch_channel(BACKUP_CHANNEL_ID)
    return await (await bot.fetch_user(OWNER_ID)).create_dm()

async def backup_candidates(ch):
    pins = ch.pins()
    if hasattr(pins, "__aiter__"):
        async for m in pins:
            yield m
    else:
        for m in await pins:
            yield m
    async for m in ch.history(limit=300):
        yield m

async def restore_backup():
    global backup_msg, synced
    try:
        async for m in backup_candidates(await get_backup_channel()):
            att = next((a for a in m.attachments if a.filename == "economy.json"), None)
            if att and m.author.id == bot.user.id:
                backup_msg = m
                data = json.loads(await att.read())
                if data.get("users"):
                    DB.clear()
                    DB.update(data)
                    write_db()
                    print(f"Restored {len(DB['users'])} players from backup")
                break
        synced = True
    except Exception as e:
        print("Backup restore failed (backups disabled to protect data). Are the owner's DMs open to the bot?", repr(e))

async def backup_now():
    global backup_msg, dirty
    if not (dirty and synced):
        return
    async with backup_lock:
        if not dirty:
            return
        dirty = False
        try:
            if backup_msg:
                try:
                    backup_msg = await backup_msg.edit(attachments=[backup_file()])
                    return
                except discord.NotFound:
                    backup_msg = None
            backup_msg = await (await get_backup_channel()).send("💾 Database backup - do not delete this message", file=backup_file())
            try:
                await backup_msg.pin()
            except Exception:
                pass
        except Exception as e:
            dirty = True
            print("Backup failed:", repr(e))

@tasks.loop(seconds=10)
async def backup_loop():
    await backup_now()

@tasks.loop(seconds=2)
async def disk_loop():
    await flush_disk()

async def graceful_shutdown():
    await flush_disk()
    await backup_now()
    await bot.close()

async def start_web():
    app = web.Application()
    app.router.add_get("/", lambda request: web.Response(text="Bot is alive"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000))).start()

async def setup_hook():
    global loaded
    loaded = asyncio.Event()
    await start_web()
    disk_loop.start()
    backup_loop.start()
    bot.add_view(ShopView())   # shop buttons keep working after a restart
    try:
        await bot.load_extension("extras")   # extras.py: !set-role-member, !clear, anti-bot protection
    except Exception as ex:
        print("extras.py failed to load:", repr(ex))
    try:
        asyncio.get_running_loop().add_signal_handler(
            signal.SIGTERM, lambda: asyncio.create_task(graceful_shutdown()))
    except (NotImplementedError, RuntimeError):
        pass

bot.setup_hook = setup_hook

@bot.event
async def on_ready():
    if not loaded.is_set():
        await restore_backup()
        refund_pending()
        loaded.set()
        _t = asyncio.create_task(warm_animations())
        _log_tasks.add(_t)
        _t.add_done_callback(_log_tasks.discard)
    print("Logged in as", bot.user)

class ReplyPingOff(commands.CommandError):
    pass

@bot.event
async def on_command_error(ctx, err):
    if isinstance(err, NotStaff):
        return await reply(ctx, "You need Administrator permission or the staff role to use this command.", RED)
    if isinstance(err, commands.MissingPermissions):
        return await reply(ctx, "You need Administrator permission to use this command.", RED)
    if isinstance(err, ReplyPingOff):
        return await reply(ctx, "Turn the reply ping **ON** (@ON) so I know who you mean.", RED)
    if isinstance(err, commands.CommandOnCooldown):
        m, s = divmod(int(err.retry_after) + 1, 60)
        t = f"{m} minutes and {s} seconds" if m else f"{s} seconds"
        icon = "⏳" if ctx.command.name == "rob" else "⏰"
        return await reply(ctx, f"You cannot use this command for **{t}**. {icon}", RED)
    if isinstance(err, (commands.MissingRequiredArgument, commands.BadArgument)):
        return await reply(ctx, f"Usage: `${ctx.command.usage or ctx.command.name}`", RED)
    if not isinstance(err, (commands.CommandNotFound, commands.CheckFailure)):
        print("Error:", repr(err))

# ================= BOARDS =================
def shuffled(**parts):
    board = [k for kind, n in parts.items() for k in [kind] * n]
    random.shuffle(board)
    return board

def gm_board():
    tiles = ["map"] + ["bomb"] * 10 + ["stone"] * 4 + ["coin"] * 2 + ["bag"] + ["diamond"] * 2
    if random.randint(1, URN_CHANCE[1]) <= URN_CHANCE[0]:   # 3 out of 7 games
        tiles[tiles.index("stone")] = "urn"
    random.shuffle(tiles)
    return tiles

BUILDERS = {"gm": gm_board, "mines": lambda: shuffled(bomb=1, diamond=8)}
for _k, (_w, _h, _m, _) in SMINES.items():
    BUILDERS[f"s{_k}"] = lambda m=_m, n=_w * _h: shuffled(bomb=m, diamond=n - m)

LAST_BOMBS = {}

def take(uid, key):
    prev = LAST_BOMBS.get((uid, key), set())
    for _ in range(30):
        board = BUILDERS[key]()
        bombs = {i for i, k in enumerate(board) if k == "bomb"}
        if not prev or len(prev & bombs) <= len(bombs) / 2:
            break
    LAST_BOMBS[(uid, key)] = bombs
    return board

# ================= MINES / GM / MONEY TOWER =================
class OwnedView(discord.ui.View):
    touch = False

    async def interaction_check(self, interaction):
        if interaction.user.id == self.user.id or (self.touch and may_play(interaction, self.user.id)):
            return True
        await interaction.response.send_message("This is not your game!", ephemeral=True)
        return False

class Tile(discord.ui.Button):
    def __init__(self, idx, cols):
        super().__init__(style=discord.ButtonStyle.secondary, label=EMPTY, row=idx // cols)
        self.idx = idx

    async def callback(self, interaction):
        await self.view.click(interaction, self.idx)

class BoardView(OwnedView):
    touch = True
    cols, header = 5, "\u200b"
    reveal_on_cashout = True
    game_name = "game"
    multi_key = None
    cash_row = None

    def __init__(self, user, bet, token=None):
        super().__init__(timeout=120)
        self.user, self.bet, self.token = user, bet, token
        self.board = self.make_board()
        self.revealed, self.profit = set(), 0
        self.done = False
        self.version = 0
        self.edit_lock = asyncio.Lock()
        self.message = None
        self.tiles = [Tile(i, self.cols) for i in range(len(self.board))]
        row = self.cash_row if self.cash_row is not None else len(self.tiles) // self.cols
        self.cash_btn = discord.ui.Button(style=discord.ButtonStyle.success, label="Cashout", row=row)
        self.cash_btn.callback = self.cashout
        self.profit_btn = discord.ui.Button(style=discord.ButtonStyle.primary, disabled=True,
                                            row=row, label="Profit: 0", emoji=cur())
        for b in (*self.tiles, self.cash_btn, self.profit_btn):
            self.add_item(b)
        spy(self)

    async def cashout(self, interaction):
        # cashing out is allowed even before opening any tile (the bet is simply returned)
        await self.finish(interaction, False)

    def reveal(self, i):
        kind, t = self.board[i], self.tiles[i]
        self.revealed.add(i)
        t.emoji, t.disabled = EMOJI[kind], True
        if kind == "bomb":
            t.style = discord.ButtonStyle.danger
        else:
            t.style = discord.ButtonStyle.success
            self.earn(kind)
            self.profit_btn.label = f"Profit: {fmt(self.profit)}"

    def after(self, kind):
        pass

    def luck_pool(self, idx):
        return [i for i in range(len(self.board)) if i not in self.revealed and i != idx]

    def luck_fix(self, idx):
        """Luck: a bomb can be swapped with a safe tile (one try per luck attempt)."""
        if self.board[idx] != "bomb":
            return
        pool = self.luck_pool(idx)
        for _ in range(luck_attempts(self.user.id) - 1):
            if not pool:
                return
            j = random.choice(pool)
            if self.board[j] != "bomb":
                self.board[idx], self.board[j] = self.board[j], "bomb"
                return

    async def click(self, interaction, idx):
        if not interaction.response.is_done():
            await interaction.response.defer()
        if self.done or idx in self.revealed:
            return
        self.luck_fix(idx)
        kind = self.board[idx]
        self.reveal(idx)
        if kind == "bomb":
            return await self.finish(interaction, True)
        self.after(kind)
        if all(k == "bomb" or i in self.revealed for i, k in enumerate(self.board)):
            for i, t in enumerate(self.tiles):
                if i not in self.revealed:
                    t.disabled = True
        self.version += 1
        v = self.version
        async with self.edit_lock:
            if v != self.version or self.done:
                return
            await interaction.edit_original_response(content=self.header, view=self)

    def payout(self):
        base = int(self.profit)
        self.profit = base + multi_extra(self.multi_key, base)   # $multi bonus (0 when off)
        user_data(self.user.id)["cash"] += self.bet + self.profit
        save()

    def reveal_all(self, show):
        for i, kind in enumerate(self.board):
            t = self.tiles[i]
            t.disabled = True
            if show:
                t.emoji = EMOJI[kind]
                if kind == "bomb":
                    t.style = discord.ButtonStyle.danger
        self.cash_btn.disabled = True

    def final_view(self, lost):
        """When the game ends, hidden-board games (mines, S$mines, mt) remove the board and the buttons
        (both after a loss and after a cashout). Only games that reveal the board (gm) keep the view."""
        return self if self.reveal_on_cashout else None

    def embed(self, lost):
        got = self.bet + int(self.profit)
        line = f"-You lost {fmt(self.bet)} {cur()}" if lost else f"+You won and got {fmt(got)} {cur()}"
        found = sum(1 for i in self.revealed if self.board[i] != "bomb")
        cash = user_data(self.user.id)["cash"]
        return make_embed(self.user, f"```\n{line}\n```\nYou found {found} {EMOJI['diamond']}\nYou now have: {fmt(cash)} {cur()}",
                          RED if lost else GREEN)

    async def finish(self, interaction, lost):
        if not interaction.response.is_done():
            await interaction.response.defer()
        if self.done:
            return
        self.done = True
        pending_done(self.token)
        if not lost:
            self.payout()
        else:
            save()
        log_game(self.user, self.game_name, self.bet, -self.bet if lost else int(self.profit))
        self.reveal_all(lost or self.reveal_on_cashout)
        kw = dict(content=self.header, embed=self.embed(lost), view=self.final_view(lost))
        async with self.edit_lock:
            await interaction.edit_original_response(**kw)

    async def on_timeout(self):
        if self.done:
            return
        self.done = True
        pending_done(self.token)
        self.payout()
        log_game(self.user, self.game_name, self.bet, int(self.profit))
        self.reveal_all(self.reveal_on_cashout)
        if self.message:
            await self.message.edit(content=self.header, embed=self.embed(False), view=self.final_view(False))

class GoldMines(BoardView):
    game_name = "gm"
    multi_key = "gm"
    @property
    def header(self):
        return f"**{self.user.name}'s Game**"

    def make_board(self):
        return take(self.user.id, "gm")

    def earn(self, kind):
        self.profit += self.bet * (MULT[kind] - 1)

    def after(self, kind):
        if kind == "map":
            safe = [i for i, k in enumerate(self.board) if k != "bomb" and i not in self.revealed]
            for i in random.sample(safe, min(3, len(safe))):
                self.reveal(i)

class Mines(BoardView):
    cols = 3
    reveal_on_cashout = False
    game_name = "mines"
    multi_key = "mines"

    def make_board(self):
        return take(self.user.id, "mines")

    def earn(self, kind):
        n = len(self.revealed)
        self.profit = self.bet * (MINES_MULT[n - 1] - 1)

class SMines(BoardView):
    reveal_on_cashout = False
    multi_key = "s$mines"

    def __init__(self, user, bet, key, token=None):
        self.key = key
        self.game_name = f"S$mines {key}"
        self.cols, _, _, self.table = SMINES[key]
        super().__init__(user, bet, token)

    def make_board(self):
        return take(self.user.id, f"s{self.key}")

    def earn(self, kind):
        n = min(len(self.revealed), len(self.table))
        self.profit = self.bet * (self.table[n - 1] - 1)

class MoneyTower(BoardView):
    cols = 3
    cash_row = 4
    reveal_on_cashout = False
    game_name = "money tower"
    multi_key = "mt"
    safe_icon = MT_SAFE

    @property
    def header(self):
        return f"**{self.user.name}'s Game**"

    def __init__(self, user, bet, token=None):
        self.climbed = 0
        super().__init__(user, bet, token)
        for i, t in enumerate(self.tiles):
            t.disabled = i // 3 != 4

    def luck_pool(self, idx):
        row = idx // 3
        return [i for i in range(row * 3, row * 3 + 3) if i != idx and i not in self.revealed]

    def make_board(self):
        board = []
        for _ in range(5):
            board += shuffled(bomb=1, diamond=2)
        return board

    def earn(self, kind):
        self.profit = self.bet * (MT_MULT[self.climbed - 1] - 1)

    def embed(self, lost):
        got = self.bet + int(self.profit)
        line = f"-You lost {fmt(self.bet)} {cur()}" if lost else f"+You won and got {fmt(got)} {cur()}"
        return make_embed(self.user, f"```\n{line}\n```\nYou climbed {self.climbed} rows.",
                          RED if lost else GREEN, None if lost else "💰 You cashed out!")

    def reveal(self, i):
        kind, t = self.board[i], self.tiles[i]
        self.revealed.add(i)
        t.disabled = True
        if kind == "bomb":
            t.emoji, t.style = EMOJI["bomb"], discord.ButtonStyle.danger
        else:
            t.emoji, t.style = MT_SAFE, discord.ButtonStyle.success
            self.climbed += 1
            self.earn(kind)
            self.profit_btn.label = f"Profit: {fmt(self.profit)}"

    async def click(self, interaction, idx):
        if not interaction.response.is_done():
            await interaction.response.defer()
        row = idx // 3
        if self.done or idx in self.revealed or row != 4 - self.climbed:
            return
        self.luck_fix(idx)
        kind = self.board[idx]
        self.reveal(idx)
        if kind == "bomb":
            return await self.finish(interaction, True)
        for j in range(row * 3, row * 3 + 3):     # the row is locked, and its bomb stays hidden
            self.tiles[j].disabled = True
        if self.climbed >= 5:
            return await self.finish(interaction, False)
        for j in range((row - 1) * 3, (row - 1) * 3 + 3):
            self.tiles[j].disabled = False
        self.version += 1
        v = self.version
        async with self.edit_lock:
            if v != self.version or self.done:
                return
            await interaction.edit_original_response(content=self.header, view=self)

    def reveal_all(self, show):
        for i, kind in enumerate(self.board):
            t = self.tiles[i]
            t.disabled = True
            if show and kind == "bomb":
                t.emoji, t.style = EMOJI["bomb"], discord.ButtonStyle.danger
        self.cash_btn.disabled = True

class SizeView(OwnedView):
    touch = True

    def __init__(self, user, bet, token=None):
        super().__init__(timeout=60)
        self.user, self.bet, self.token, self.message, self.chosen = user, bet, token, None, False
        for key, (_, _, m, _) in SMINES.items():
            b = discord.ui.Button(style=discord.ButtonStyle.primary, label=f"{key} ({m} mine{'s' * (m > 1)})")
            b.callback = self.pick(key)
            self.add_item(b)

    def embed(self):
        rows = "\n".join(f"• {k}: {m} mine{'s' * (m > 1)}, {w * h - m} diamonds" for k, (w, h, m, _) in SMINES.items())
        return discord.Embed(color=BLUE, description=(
            f"**Choose Board Size**\n\nYou bet **{fmt(self.bet)}** {cur()}.\n\n{rows}\n\nClick a button below to start!"))

    def pick(self, key):
        async def cb(interaction):
            if self.chosen:
                if not interaction.response.is_done():
                    await interaction.response.defer()
                return
            self.chosen = True
            self.stop()
            try:
                game = SMines(self.user, self.bet, key, self.token)
                game.message = interaction.message
                await interaction.response.edit_message(content=game.header, embed=None, view=game)
            except Exception:
                cancel_game(self.user, self.token, self.bet)
                raise
        return cb

    async def on_timeout(self):
        if self.chosen:
            return
        pending_done(self.token)
        user_data(self.user.id)["cash"] += self.bet
        save()
        log_money(self.user, f"🟡 **S$mines** — timed out, bet **{fmt(self.bet)}** {cur()} returned", YELLOW)
        if self.message:
            await self.message.edit(embed=discord.Embed(description="Timed out, your bet was returned.", color=RED), view=None)

async def start_board(ctx, cls, amount, usage):
    bet = await take_bet(ctx, amount, usage, track=True)
    if bet:
        view = cls(ctx.author, bet, str(ctx.message.id))
        try:
            view.message = await ctx.reply(view.header, view=view, mention_author=False)
        except Exception:
            cancel_game(ctx.author, view.token, bet)
            raise

@bot.command(name="gm", usage="gm <amount | half | all>")
async def gm(ctx, amount: str = None):
    await start_board(ctx, GoldMines, amount, "gm <amount | half | all>")

@bot.command(name="mines", usage="mines <amount | half | all>")
async def mines(ctx, amount: str = None):
    usage = "mines <amount | half | all>"
    if ctx.prefix.lower() != "s$":
        return await start_board(ctx, Mines, amount, usage)
    bet = await take_bet(ctx, amount, usage, track=True)
    if bet:
        view = SizeView(ctx.author, bet, str(ctx.message.id))
        try:
            view.message = await ctx.reply(embed=view.embed(), view=view, mention_author=False)
        except Exception:
            cancel_game(ctx.author, view.token, bet)
            raise

@bot.command(name="mt", aliases=["moneytower"], usage="mt <amount | half | all>")
async def mt(ctx, amount: str = None):
    await start_board(ctx, MoneyTower, amount, "mt <amount | half | all>")

# ================= BLACKJACK =================
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♣", "♠", "♥", "♦"]

def card_value(rank):
    return 11 if rank == "A" else 10 if rank in "JQK" else int(rank)

def hand_value(cards):
    total, aces = sum(card_value(r) for r, _ in cards), sum(r == "A" for r, _ in cards)
    while total > 21 and aces:
        total, aces = total - 10, aces - 1
    return total

# ---------- card images: every card is cut from the deck picture (faces.py); plain colored cards are only a fallback ----------
SW, SH = 68, 120
TABLE_W = 960
MASK = Image.new("L", (SW, SH), 0)
ImageDraw.Draw(MASK).rounded_rectangle([0, 0, SW - 1, SH - 1], radius=6, fill=255)
SUIT_COLORS = {"♣": (34, 139, 34), "♠": (40, 40, 40), "♥": (205, 30, 30), "♦": (30, 100, 215)}
FACE_W, FACE_H = 52, 92   # size of one piece in faces.py (rows: ♣ ♠ ♥ ♦, columns: J Q K)

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

@lru_cache(maxsize=None)
def get_card(card):
    r, s = card
    if FACES is not None:
        x, y = RANKS.index(r) * FACE_W, SUITS.index(s) * FACE_H
        im = FACES.crop((x, y, x + FACE_W, y + FACE_H)).resize((SW, SH), Image.LANCZOS).convert("RGBA")
        ImageDraw.Draw(im).rectangle([0, 0, SW - 1, SH - 1], outline=(170, 170, 170, 255), width=1)
        im.putalpha(MASK)
        return im
    im = Image.new("RGBA", (SW, SH), (255, 255, 255, 255))
    inner = Image.new("RGBA", (SW - 8, SH - 8), SUIT_COLORS[s] + (255,))
    m = Image.new("L", inner.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, inner.width - 1, inner.height - 1], radius=7, fill=255)
    im.paste(inner, (4, 4), m)
    ImageDraw.Draw(im).text((SW // 2, SH // 2), r, font=get_font(66 if len(r) == 1 else 52),
                            fill=(255, 255, 255, 255), anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0, 120))
    im.putalpha(MASK)
    return im

@lru_cache(maxsize=None)
def get_back():
    im = Image.new("RGBA", (SW, SH), (250, 250, 250, 255))
    inner = Image.new("RGBA", (SW - 10, SH - 10), (170, 30, 50, 255))
    d = ImageDraw.Draw(inner)
    for k in range(-SH, SW, 12):
        d.line([(k, 0), (k + SH, SH)], fill=(205, 75, 90, 255), width=2)
    m = Image.new("L", inner.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, inner.width - 1, inner.height - 1], radius=5, fill=255)
    im.paste(inner, (5, 5), m)
    im.putalpha(MASK)
    return im

def render_table(dealer, hands, hide_dealer):
    rows = [("YOUR HAND" + (f" {i + 1}" if len(hands) > 1 else ""), list(h)) for i, h in enumerate(hands)]
    rows.append(("DEALER HAND", [dealer[0], None] if hide_dealer else list(dealer)))
    PAD, LABEL_H, GAP, GAPX = 16, 46, 16, 10
    step = lambda n: SW + GAPX if n <= 1 else min(SW + GAPX, (TABLE_W - 2 * PAD - SW) / (n - 1))
    height = 2 * PAD + len(rows) * (LABEL_H + SH) + (len(rows) - 1) * GAP
    img = Image.new("RGBA", (TABLE_W, height), (0, 0, 0, 0))
    d, y = ImageDraw.Draw(img), PAD
    for label, cards in rows:
        d.text((PAD, y), label, font=get_font(32), fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(255, 255, 255, 255))
        y += LABEL_H
        for i, c in enumerate(cards):
            im = get_back() if c is None else get_card(c)
            img.paste(im, (int(PAD + i * step(len(cards))), y), im)
        y += SH + GAP
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

class BlackjackView(discord.ui.View):
    def __init__(self, user, bet, token=None):
        super().__init__(timeout=120)
        self.user, self.token = user, token
        self.deck = [(r, s) for r in RANKS for s in SUITS]
        random.shuffle(self.deck)
        self.hands = [{"cards": [self.deck.pop(), self.deck.pop()], "bet": bet, "bust": False}]
        self.dealer = [self.deck.pop(), self.deck.pop()]
        self.active = self.net = self.render_n = 0
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
        returned += multi_extra("bj", returned - staked)   # $multi bonus on a win (0 when off)
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

    def finalize(self):
        if any(not h["bust"] for h in self.hands):
            self.dealer_play()
            if self.player_wins() and random.random() < BJ_WIN_NERF:
                up = self.dealer[0]
                for _ in range(5):
                    self.deck.extend(self.dealer[1:])
                    random.shuffle(self.deck)
                    self.dealer = [up, self.deck.pop()]
                    self.dealer_play()
                    if not self.player_wins():
                        break
            for _ in range(luck_attempts(self.user.id) - 1):   # luck: the dealer gets a new hand when the player isn't winning
                if self.player_wins():
                    break
                up = self.dealer[0]
                self.deck.extend(self.dealer[1:])
                random.shuffle(self.deck)
                self.dealer = [up, self.deck.pop()]
                self.dealer_play()
        dv, returned = hand_value(self.dealer), 0
        for h in self.hands:
            pv = hand_value(h["cards"])
            if not h["bust"] and (pv > dv or dv > 21):
                returned += h["bet"] * 2
            elif not h["bust"] and pv == dv:
                returned += h["bet"]
        self.pay(returned, sum(h["bet"] for h in self.hands))

    def render(self):
        self.render_n += 1
        filename = f"bj{self.render_n}.png"
        file = discord.File(render_table(self.dealer, [h["cards"] for h in self.hands], not self.done), filename=filename)
        c, color, head = cur(), YELLOW, None
        if self.done:
            color, head = ((GREEN, f"You Won! +{fmt(self.net)} {c}") if self.net > 0 else
                           (RED, f"You Lost! -{fmt(-self.net)} {c}") if self.net < 0 else
                           (YELLOW, f"Push! +0 {c}"))
        lines = ["🃏 **Blackjack** 🃏", ""] + ([f"**{head}**", ""] if head else [])
        multi = len(self.hands) > 1
        for i, h in enumerate(self.hands):
            mark = " ◀" if multi and not self.done and i == self.active else ""
            lines.append(f"Your Value{f' (Hand {i + 1})' if multi else ''}: **{hand_value(h['cards'])}**{mark}")
        lines.append(f"Dealer Value: **{hand_value(self.dealer) if self.done else card_value(self.dealer[0][0])}**")
        e = discord.Embed(description="\n".join(lines), color=color)
        e.set_author(name=f"{self.user.name}'s Game", icon_url=self.user.display_avatar.url)
        e.set_image(url=f"attachment://{filename}")
        return e, file

    async def update(self, interaction):
        self.refresh_buttons()
        if not interaction.response.is_done():
            await interaction.response.defer()
        e, f = self.render()
        await interaction.edit_original_response(embed=e, attachments=[f], view=self)

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
            e, f = self.render()
            await self.message.edit(embed=e, attachments=[f], view=self)

@bot.command(name="bj", aliases=["blackjack"], usage="bj <amount | half | all>")
async def bj(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "bj <amount | half | all>", track=True)
    if not bet:
        return
    BUSY.add(ctx.author.id)
    view = BlackjackView(ctx.author, bet, str(ctx.message.id))
    try:
        natural = view.check_naturals()
        e, f = view.render()
        msg = await ctx.send(embed=e, file=f, view=view)
    except Exception:
        if not view.done:
            cancel_game(ctx.author, view.token, bet)
        BUSY.discard(ctx.author.id)
        raise
    if not natural:
        view.message = msg

# ================= SLOTS (animated GIF: 3 reels that spin and stop one by one) =================
SLOT_ICON = 50
SLOT_NAMES = dict(zip(SLOTS, ["cherry", "lemon", "grape", "bell", "diamond", "seven"]))

@lru_cache(maxsize=None)
def slot_icon(sym):
    S = 256
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    name = SLOT_NAMES[sym]
    if name == "cherry":
        leaf, dark = (60, 150, 70, 255), (120, 10, 25, 255)
        d.line([(82, 170), (140, 40)], fill=leaf, width=12)
        d.line([(178, 180), (140, 40)], fill=leaf, width=12)
        d.ellipse([140, 20, 222, 70], fill=leaf)
        for cx, cy in ((80, 190), (176, 200)):
            d.ellipse([cx - 50, cy - 50, cx + 50, cy + 50], fill=(215, 30, 50, 255), outline=dark, width=6)
            d.ellipse([cx - 28, cy - 32, cx - 6, cy - 10], fill=(255, 150, 160, 255))
    elif name == "lemon":
        d.ellipse([12, 98, 52, 158], fill=(225, 190, 40, 255))
        d.ellipse([204, 98, 244, 158], fill=(225, 190, 40, 255))
        d.ellipse([28, 58, 228, 198], fill=(252, 226, 60, 255), outline=(200, 160, 20, 255), width=6)
        d.ellipse([70, 82, 130, 112], fill=(255, 246, 165, 255))
    elif name == "grape":
        for cx, cy in ((64, 100), (128, 100), (192, 100), (96, 152), (160, 152), (128, 204)):
            d.ellipse([cx - 32, cy - 32, cx + 32, cy + 32], fill=(140, 60, 180, 255), outline=(80, 30, 110, 255), width=5)
            d.ellipse([cx - 18, cy - 20, cx - 6, cy - 8], fill=(210, 160, 235, 255))
        d.line([(128, 70), (128, 26)], fill=(90, 60, 30, 255), width=10)
        d.ellipse([128, 14, 208, 54], fill=(60, 150, 70, 255))
    elif name == "bell":
        gold, edge = (245, 190, 40, 255), (160, 105, 10, 255)
        d.ellipse([56, 28, 200, 172], fill=gold, outline=edge, width=6)
        d.polygon([(58, 100), (198, 100), (232, 190), (24, 190)], fill=gold)
        d.line([(58, 100), (24, 190)], fill=edge, width=6)
        d.line([(198, 100), (232, 190)], fill=edge, width=6)
        d.line([(24, 190), (232, 190)], fill=edge, width=8)
        d.ellipse([106, 196, 150, 240], fill=gold, outline=edge, width=5)
        d.ellipse([84, 52, 122, 112], fill=(255, 232, 140, 255))
    elif name == "diamond":
        pts = [(70, 50), (186, 50), (236, 108), (128, 226), (20, 108)]
        d.polygon(pts, fill=(90, 200, 255, 255))
        d.line(pts + [pts[0]], fill=(20, 110, 170, 255), width=6, joint="curve")
        light = (215, 245, 255, 255)
        d.line([(20, 108), (236, 108)], fill=light, width=5)
        d.line([(70, 50), (96, 108), (128, 226)], fill=light, width=5)
        d.line([(186, 50), (160, 108), (128, 226)], fill=light, width=5)
        d.line([(96, 108), (128, 50), (160, 108)], fill=light, width=5)
    else:   # seven
        d.text((128, 132), "7", font=get_font(230), fill=(225, 30, 40, 255), anchor="mm",
               stroke_width=10, stroke_fill=(255, 215, 80, 255))
    return im.resize((SLOT_ICON, SLOT_ICON), Image.LANCZOS)

def render_slots(final, win):
    cell, rw, gap, pad = 62, 84, 8, 12
    W, H = pad * 2 + rw * 3 + gap * 2, pad * 2 + cell * 3
    cycle = random.sample(SLOTS, len(SLOTS))
    n = len(cycle)
    stops, total = (26, 34, 42), 46
    targets = [(2 + i) * n + cycle.index(final[i]) for i in range(3)]
    shade = Image.new("RGBA", (rw, cell), (0, 0, 0, 110))

    def frame(f, last=False):
        im = Image.new("RGB", (W, H), (60, 12, 24))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, W - 1, H - 1], outline=(235, 190, 60), width=4)
        for i in range(3):
            p = min(1.0, f / stops[i])
            pos = targets[i] * (1 - (1 - p) ** 3)
            reel = Image.new("RGBA", (rw, cell * 3), (250, 248, 240, 255))
            base = int(pos)
            for k in range(base - 2, base + 3):
                icon = slot_icon(cycle[k % n])
                yc = cell * 1.5 + (pos - k) * cell
                reel.paste(icon, ((rw - SLOT_ICON) // 2, int(yc - SLOT_ICON / 2)), icon)
            reel.paste(shade, (0, 0), shade)
            reel.paste(shade, (0, cell * 2), shade)
            im.paste(reel.convert("RGB"), (pad + i * (rw + gap), pad))
        d.line([(pad - 8, H // 2), (W - pad + 8, H // 2)], fill=(230, 40, 40), width=2)
        if last and win:
            d.rectangle([pad - 3, pad + cell - 2, W - pad + 3, pad + cell * 2 + 2], outline=(90, 255, 120), width=3)
        return im

    frames = [frame(f) for f in range(total - 1)] + [frame(total - 1, last=True)]
    gif, png = io.BytesIO(), io.BytesIO()
    pal = [fr.quantize(colors=64, method=Image.MEDIANCUT) for fr in frames]
    pal[0].save(gif, "GIF", save_all=True, append_images=pal[1:], duration=[100] * (len(pal) - 1) + [6000], loop=0, optimize=False)
    frames[-1].save(png, "PNG")
    return gif.getvalue(), png.getvalue()

# ---------- pre-rendered slot animations: the game message is sent with the animation already attached ----------
SLOT_CACHE = {}    # (sym, sym, sym) -> (gif, png)   all 216 combinations are prepared in the background

async def get_slots_anim(final):
    key = tuple(final)
    if key not in SLOT_CACHE:
        win = max(final.count(s) for s in SLOTS) >= 2
        SLOT_CACHE[key] = await asyncio.to_thread(render_slots, list(final), win)
    return SLOT_CACHE[key]

async def warm_animations():
    try:
        for a in SLOTS:
            for b in SLOTS:
                for c in SLOTS:
                    await get_slots_anim([a, b, c])
                    await asyncio.sleep(0.05)
        print("Animations are ready")
    except Exception as ex:
        print("Warm-up failed:", repr(ex))

@bot.command(name="slots", aliases=["slot"], usage="slots <amount | half | all>")
async def slots(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "slots <amount | half | all>", track=True)
    if not bet:
        return
    token = str(ctx.message.id)
    BUSY.add(ctx.author.id)
    try:
        final = [random.choice(SLOTS) for _ in range(3)]
        if len(set(final)) == 3 and random.random() < SLOTS_BOOST / (120 / 216):
            final[1] = final[0]
        for _ in range(luck_attempts(ctx.author.id) - 1):   # luck: re-spin until there is a win
            if max(final.count(s) for s in SLOTS) >= 2:
                break
            final = [random.choice(SLOTS) for _ in range(3)]
        top = max(final.count(s) for s in SLOTS)
        mult = (SLOT_PAY[final[0]] if top == 3 else 1.5 if top == 2 else 0) * SLOT_BUFF
        win = int(bet * mult)
        if win > bet:                                   # $multi bonus on a win (0 when off)
            win += multi_extra("slots", win - bet)
            mult = win / bet
        # the animation is ready (pre-rendered), so the message is sent WITH it, straight away
        try:
            gif, png = await get_slots_anim(final)
        except Exception:
            cancel_game(ctx.author, token, bet)
            raise
        e = make_embed(ctx.author, f"🎰 **Slots**\n\nYou bet **{fmt(bet)}** {cur()}\n\n⏳ Spinning...", YELLOW)
        e.set_image(url="attachment://slots.gif")
        msg = None
        try:
            msg = await ctx.reply(embed=e, file=discord.File(io.BytesIO(gif), "slots.gif"), mention_author=False)
            await asyncio.sleep(SLOT_WAIT + LOAD_BUFFER)
        except discord.HTTPException:
            pass
        # 3) the money moves, the result is shown, and THEN the log is written
        pending_done(token)
        user_data(ctx.author.id)["cash"] += win
        save()
        line = "🎰  ┃ " + " ┃ ".join(final) + " ┃  🎰"
        extra = f"{line}\n" + (f"**x{mult:.2f}**\n\n" if win else "\n")
        result = result_embed(ctx.author, win > 0, win - bet if win else bet, extra)
        result.set_image(url="attachment://slots_result.png")
        if msg:
            try:
                await msg.edit(embed=result, attachments=[discord.File(io.BytesIO(png), "slots_result.png")])
            except discord.HTTPException:
                pass
        log_game(ctx.author, "slots", bet, win - bet)
    finally:
        BUSY.discard(ctx.author.id)

# ================= ROULETTE (multiplayer round, no animation) =================
ROUL_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
ROUL_WAIT = 15          # seconds people can join a round
ROUL_ALLOWED_PICKS = (1, 2, 4)   # the amount is split equally: 100% / 50% each / 25% each
ROUL_COLOR = 0x9B8CD6
ROUL_USAGE = "roulette <amount | half | all> <1, 2 or 4 options: 0,red,6,odd>"

def roul_color(n):
    return "green" if n == 0 else "red" if n in ROUL_RED else "black"

def parse_roul_pick(text):
    if not text:
        return None
    t = text.lower().strip().replace(" ", "").replace("–", "-").replace("־", "-")
    red = ("Red", lambda n: n in ROUL_RED, 2)
    black = ("Black", lambda n: n != 0 and n not in ROUL_RED, 2)
    even = ("Even", lambda n: n != 0 and n % 2 == 0, 2)
    odd = ("Odd", lambda n: n % 2 == 1, 2)
    d1 = ("1-12", lambda n: 1 <= n <= 12, 3)
    d2 = ("13-24", lambda n: 13 <= n <= 24, 3)
    d3 = ("25-36", lambda n: 25 <= n <= 36, 3)
    h1 = ("1-18", lambda n: 1 <= n <= 18, 2)
    h2 = ("19-36", lambda n: 19 <= n <= 36, 2)
    c1 = ("1st", lambda n: n != 0 and n % 3 == 1, 3)
    c2 = ("2nd", lambda n: n != 0 and n % 3 == 2, 3)
    c3 = ("3rd", lambda n: n != 0 and n % 3 == 0, 3)
    names = {
        "red": red, "r": red, "אדום": red,
        "black": black, "b": black, "שחור": black,
        "even": even, "זוגי": even,
        "odd": odd, "אי-זוגי": odd, "איזוגי": odd,
        "1-12": d1, "13-24": d2, "25-36": d3,
        "1-18": h1, "19-36": h2,
        "1st": c1, "2nd": c2, "3rd": c3,
    }
    if t in names:
        return names[t]
    if t.isdigit() and 0 <= int(t) <= 36:
        k = int(t)
        return (str(k), lambda n, k=k: n == k, 36)
    return None

def roul_pick_list(text):
    if not text:
        return None
    picks, seen = [], set()
    for part in re.split(r"[,\s]+", text.strip()):
        if not part:
            continue
        c = parse_roul_pick(part)
        if c is None:
            return None
        if c[0] not in seen:
            seen.add(c[0])
            picks.append(c)
    return picks or None

def roul_embed(bet):
    names = ", ".join(p[0] for p in bet["picks"])
    each = f" ({fmt(bet['per'])} each)" if len(bet["picks"]) > 1 else ""
    return discord.Embed(color=ROUL_COLOR, title="🎰 Roulette Round Opened", description=(
        f"Roulette round opened by {bet['user'].mention}.\n\n"
        f"**Bet:** {fmt(bet['stake'])}{cur()} on **{names}**{each}\n\n"
        f"The wheel spins <t:{bet['end']}:R>."))

async def run_roulette(msg, bet):
    try:
        await asyncio.sleep(max(0, bet["end"] - time.time()))
        winner = random.randint(0, 36)          # European wheel: 37 pockets (0-36), every pocket 1/37
        for _ in range(luck_attempts(bet["user"].id) - 1):   # luck: the wheel is spun again until a pick hits
            if any(t(winner) for _, t, _ in bet["picks"]):
                break
            winner = random.randint(0, 36)
        emoji = {"red": "🔴", "black": "⚫", "green": "🟢"}[roul_color(winner)]
        user = bet["user"]
        hits = [(l, m) for l, t, m in bet["picks"] if t(winner)]
        win = sum(bet["per"] * m for _, m in hits)
        net = win - bet["stake"]
        if net > 0:                                     # $multi bonus on a win (0 when off)
            win += multi_extra("roulette", net)
            net = win - bet["stake"]
        pending_done(bet["token"])
        user_data(user.id)["cash"] += win
        save()
        log_game(user, "roulette", bet["stake"], net)
        hit_txt = f" (hit: {', '.join(l for l, _ in hits)})" if hits else ""
        if net > 0:
            line, color = f"🟢 You won **+{fmt(net)}** {cur()}{hit_txt}", GREEN
        elif net < 0:
            line, color = f"🔴 You lost **{fmt(-net)}** {cur()}{hit_txt}", RED
        else:
            line, color = f"🟡 You got your bet back{hit_txt}", YELLOW
        e = discord.Embed(color=color, title="🎰 Roulette Round Closed", description=(
            f"Roulette round opened by {user.mention}.\n\n"
            f"The ball landed on {emoji} **{winner}**\n\n{line}\n"
            f"You now have {fmt(user_data(user.id)['cash'])} {cur()}."))
        none = discord.AllowedMentions.none()
        try:
            await msg.edit(embed=e, allowed_mentions=none)
        except Exception:
            await msg.channel.send(embed=e, allowed_mentions=none)
    except Exception as ex:
        print("Roulette failed:", repr(ex))
        BUSY.discard(bet["user"].id)

@bot.command(name="roulette", aliases=["rl"], usage=ROUL_USAGE)
async def roulette(ctx, amount: str = None, *, picks: str = None):
    if ctx.author.id in BUSY:
        return await reply(ctx, BUSY_MSG, RED)
    choices = roul_pick_list(picks)
    if choices is None:
        return await reply(ctx, f"Usage: `${ROUL_USAGE}`", RED)
    if len(choices) not in ROUL_ALLOWED_PICKS:
        return await reply(ctx, "Choose 1, 2 or 4 options (the amount is split equally between them).", RED)
    u = user_data(ctx.author.id)
    total = parse_amount(amount, u["cash"])
    if total is None:
        return await reply(ctx, f"Usage: `${ROUL_USAGE}` (min {MIN_BET})", RED)
    if total < MIN_BET:
        return await reply(ctx, f"The minimum bet is {MIN_BET} {cur()}.", RED)
    if total > u["cash"]:
        return await reply(ctx, "You don't have that much money.", RED)
    per = total // len(choices)                 # the amount is split equally between the options
    stake = per * len(choices)
    if per < 1:
        return await reply(ctx, f"Usage: `${ROUL_USAGE}`", RED)
    token = str(ctx.message.id)
    u["cash"] -= stake
    DB.setdefault("pending", {})[token] = {"uid": str(ctx.author.id), "bet": stake}
    BUSY.add(ctx.author.id)
    save()
    bet = {"user": ctx.author, "per": per, "stake": stake, "picks": choices, "token": token,
           "end": int(time.time()) + ROUL_WAIT}
    try:
        msg = await ctx.reply(embed=roul_embed(bet), mention_author=False,
                              allowed_mentions=discord.AllowedMentions.none())
    except Exception:
        cancel_game(ctx.author, token, stake)
        raise
    t = asyncio.create_task(run_roulette(msg, bet))
    _log_tasks.add(t)
    t.add_done_callback(_log_tasks.discard)

# ================= HEADS OR TAIL / CHICKEN FIGHT =================
async def refund_timeout(view, name):
    view.settled = True
    pending_done(view.token)
    user_data(view.user.id)["cash"] += view.bet
    save()
    log_money(view.user, f"🟡 **{name}** — timed out, bet **{fmt(view.bet)}** {cur()} returned", YELLOW)
    BUSY.discard(view.user.id)
    if view.message:
        await view.message.edit(embed=make_embed(view.user, "Timed out, your bet was returned.", RED), view=None)

class CoinFlip(OwnedView):
    def __init__(self, user, bet, token=None):
        super().__init__(timeout=60)
        self.user, self.bet, self.token, self.message, self.settled = user, bet, token, None, False

    async def flip(self, interaction, pick):
        if self.settled:
            return await interaction.response.defer()
        self.settled = True
        won = any(random.choice(("Head", "Tail")) == pick for _ in range(luck_attempts(self.user.id)))   # luck = more tries
        land = pick if won else ("Tail" if pick == "Head" else "Head")
        extra = multi_extra("ht", self.bet) if won else 0   # $multi bonus on a win (0 when off)
        pending_done(self.token)
        if won:
            user_data(self.user.id)["cash"] += self.bet * 2 + extra
        save()
        log_game(self.user, "heads or tail", self.bet, self.bet + extra if won else -self.bet)
        BUSY.discard(self.user.id)
        self.stop()
        await interaction.response.edit_message(
            embed=result_embed(self.user, won, self.bet + extra, f"You chose **{pick}**, the coin landed on **{land}**.\n"), view=None)

    @discord.ui.button(label="Head", style=discord.ButtonStyle.primary)
    async def head(self, interaction, button):
        await self.flip(interaction, "Head")

    @discord.ui.button(label="Tail", style=discord.ButtonStyle.success)
    async def tail(self, interaction, button):
        await self.flip(interaction, "Tail")

    async def on_timeout(self):
        if self.settled:
            return
        await refund_timeout(self, "heads or tail")

@bot.command(name="ht", usage="ht <amount | half | all>")
async def ht(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "ht <amount | half | all>", track=True)
    if not bet:
        return
    BUSY.add(ctx.author.id)
    view = CoinFlip(ctx.author, bet, str(ctx.message.id))
    e = make_embed(ctx.author, f"🍀 **CoinFlip** 🍀\n\n**Betting Amount:** `{fmt(bet)}`\n\nChoose head or tail (עץ או פאלי)", YELLOW)
    try:
        view.message = await ctx.reply(embed=e, view=view, mention_author=False)
    except Exception:
        cancel_game(ctx.author, view.token, bet)
        BUSY.discard(ctx.author.id)
        raise

@bot.command(name="cf", usage="cf <amount | half | all>")
async def cf(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "cf <amount | half | all>")
    if not bet:
        return
    u, c = user_data(ctx.author.id), cur()
    strength = max(CF_MIN, min(CF_MAX, u.get("chicken", CF_MIN)))
    won = any(random.randint(1, 100) <= strength + CF_HIDDEN for _ in range(luck_attempts(ctx.author.id)))   # the real chance = strength + CF_HIDDEN (luck = more tries)
    profit = bet
    if won:
        profit = bet + multi_extra("cf", bet)               # $multi bonus on a win (0 when off)
        u["cash"] += bet + profit
        u["chicken"] = strength = min(CF_MAX, strength + 1)
        # the % shown is the REAL chance of the next fight
        desc = (f"Your chicken won the fight, you won {fmt(profit)} {c}🐓!\n\n"
                f"**Your chicken's strength (chance of winning): {strength + CF_HIDDEN}%**\n"
                f"**You now have {fmt(u['cash'])} {c}**")
        color = GREEN
    else:
        u["chicken"] = CF_MIN
        desc, color = f"Your chicken lost the fight... You lost {fmt(bet)} {c}🐓.", RED
    save()
    log_game(ctx.author, "chicken fight", bet, profit if won else -bet)
    await reply(ctx, desc, color)

# ================= HIGHER OR LOWER ($hl / $high-low) =================
HL_MIN, HL_MAX = 1, 100
HL_RTP = 0.95          # the payout is the fair multiplier x 0.95 (5% house edge)
HL_FLOOR = 1.05        # the safest guess still pays a little
HL_CAP = 25            # no crazy multipliers on a very unlikely guess
HL_SAME = 25           # exactly the same number (1% chance)
HL_COLOR = 0x9B8CD6

def hl_mult(first, choice):
    if choice == "same":
        return HL_SAME
    p = (HL_MAX - first if choice == "higher" else first - HL_MIN) / (HL_MAX - HL_MIN + 1)
    if p <= 0:
        return None
    return round(min(HL_CAP, max(HL_FLOOR, HL_RTP / p)), 2)

def hl_text(m):
    return "-" if m is None else f"{m:g}x"

class HigherLower(OwnedView):
    def __init__(self, user, bet, token=None):
        super().__init__(timeout=60)
        self.user, self.bet, self.token, self.message, self.settled = user, bet, token, None, False
        self.first = random.randint(HL_MIN, HL_MAX)
        self.mults = {c: hl_mult(self.first, c) for c in ("higher", "same", "lower")}
        self.higher.disabled = self.mults["higher"] is None
        self.lower.disabled = self.mults["lower"] is None

    def embed(self):
        m = self.mults
        return discord.Embed(color=HL_COLOR, title="🎲 Higher or Lower 🎲", description=(
            f"**Betting Amount:** `{fmt(self.bet)}`\n"
            f"1️⃣: `{self.first}`\n2️⃣: `❓`\n\n"
            f"**Higher:** `{hl_text(m['higher'])}`\n**Same:** `{hl_text(m['same'])}`\n**Lower:** `{hl_text(m['lower'])}`"))

    async def guess(self, interaction, choice):
        if self.settled:
            return await interaction.response.defer()
        self.settled = True

        def hit(s):
            return (s > self.first and choice == "higher") or (s < self.first and choice == "lower") \
                or (s == self.first and choice == "same")

        second = random.randint(HL_MIN, HL_MAX)
        for _ in range(luck_attempts(self.user.id) - 1):   # luck: the second number is drawn again until it fits
            if hit(second):
                break
            second = random.randint(HL_MIN, HL_MAX)
        won = hit(second)
        win = int(self.bet * self.mults[choice]) if won else 0
        if win > self.bet:                               # $multi bonus on a win (0 when off)
            win += multi_extra("hl", win - self.bet)
        pending_done(self.token)
        user_data(self.user.id)["cash"] += win
        save()
        net = win - self.bet
        log_game(self.user, "higher or lower", self.bet, net)
        BUSY.discard(self.user.id)
        self.stop()
        cash = user_data(self.user.id)["cash"]
        head = f"You won {fmt(net)} {cur()}!" if net > 0 else f"You lost {fmt(self.bet)} {cur()}."
        e = discord.Embed(color=GREEN if won else RED, description=(
            f"🎲 Game Over 🎲\n\n"
            f"**{head}**\n"
            f"**Your Choice:** `{choice}`\n\n"
            f"1️⃣: `{self.first}`\n"
            f"2️⃣: `{second}`\n\n"
            f"**Balance:** `{fmt(cash)} {cur()}`"))
        await interaction.response.edit_message(embed=e, view=None)

    @discord.ui.button(label="Higher", style=discord.ButtonStyle.primary)
    async def higher(self, interaction, button):
        await self.guess(interaction, "higher")

    @discord.ui.button(label="Same", style=discord.ButtonStyle.primary)
    async def same(self, interaction, button):
        await self.guess(interaction, "same")

    @discord.ui.button(label="Lower", style=discord.ButtonStyle.primary)
    async def lower(self, interaction, button):
        await self.guess(interaction, "lower")

    async def on_timeout(self):
        if self.settled:
            return
        await refund_timeout(self, "higher or lower")

@bot.command(name="hl", aliases=["high-low", "highlow"], usage="hl <amount | half | all>")
async def hl(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "hl <amount | half | all>", track=True)
    if not bet:
        return
    BUSY.add(ctx.author.id)
    view = HigherLower(ctx.author, bet, str(ctx.message.id))
    try:
        view.message = await ctx.reply(embed=view.embed(), view=view, mention_author=False)
    except Exception:
        cancel_game(ctx.author, view.token, bet)
        BUSY.discard(ctx.author.id)
        raise

# ================= CRASH ($crash) =================
# A real-time game: the multiplier climbs and can crash at any moment. The message is edited with a NEW picture
# every tick (no GIF, nothing pre-rendered, the game starts the second the command is sent). Cashout uses the
# real server time of the click, so the player gets the true multiplier of that moment.
CRASH_RATE = 0.1        # m(t) = e^(0.1 * t)  ->  x2 after ~7s, x5 after ~16s, x10 after ~23s
CRASH_TICK = 1.0        # seconds between picture updates (Discord allows ~5 edits per 5s per channel)
CRASH_EDGE = 0.04       # 4% house edge: P(crash >= x) = 0.96 / x   (4% of games crash instantly at x1.00)
CRASH_CAP = 100.0       # highest possible crash point
CRASH_AUTO_MIN = 1.01
CRASH_USAGE = "crash <amount | half | all> [auto-cashout, e.g. 2.5x]"
CR_W, CR_H, CR_S = 640, 300, 2   # picture size, and the supersampling factor (drawn 2x bigger, then shrunk = smooth lines)

def crash_mult(t):
    return math.exp(CRASH_RATE * t)

def crash_time(m):
    return math.log(m) / CRASH_RATE

def crash_point(uid):
    """The point where the round crashes. Luck = the best of several rolls."""
    best = 1.0
    for _ in range(max(1, luck_attempts(uid))):
        r = random.random()
        p = math.floor(100 * (1 - CRASH_EDGE) / (1 - r)) / 100
        best = max(best, min(CRASH_CAP, p))
    return best

@lru_cache(maxsize=1)
def crash_bg():
    W, H = CR_W * CR_S, CR_H * CR_S
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):          # the same dark casino red as the slots machine
        k = y / H
        d.line([(0, y), (W, y)], fill=(int(74 - 34 * k), int(14 - 6 * k), int(30 - 12 * k)))
    return im

@lru_cache(maxsize=1)
def crash_rocket():
    im = Image.new("RGBA", (200, 88), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(6, 44), (48, 28), (48, 60)], fill=(255, 140, 30, 255))          # flame
    d.polygon([(22, 44), (48, 34), (48, 54)], fill=(255, 235, 120, 255))
    d.polygon([(58, 26), (42, 2), (92, 26)], fill=(200, 35, 50, 255))            # fins
    d.polygon([(58, 62), (42, 86), (92, 62)], fill=(200, 35, 50, 255))
    d.rounded_rectangle([44, 24, 152, 64], radius=18, fill=(238, 238, 244, 255), outline=(150, 150, 165, 255), width=3)
    d.polygon([(150, 24), (194, 44), (150, 64)], fill=(220, 40, 50, 255))        # nose
    d.ellipse([100, 33, 124, 55], fill=(90, 200, 255, 255), outline=(40, 110, 170, 255), width=3)   # window
    return im.resize((150, 66), Image.LANCZOS)

def crash_boom(d, cx, cy, r):
    pts = []
    for i in range(24):
        a = math.pi * 2 * i / 24
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    d.polygon(pts, fill=(255, 150, 30, 255))
    d.polygon([(cx + (x - cx) * 0.55, cy + (y - cy) * 0.55) for x, y in pts], fill=(255, 235, 110, 255))

def crash_step(span, target=4):
    raw = span / target
    for s in (0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 50, 100):
        if s >= raw:
            return s
    return 100

def render_crash(t, state, m):
    """One picture of the graph. state: 'run' (rocket flying), 'crash' (explosion) or 'cash' (cashed out)."""
    S = CR_S
    W, H = CR_W * S, CR_H * S
    im = crash_bg().copy().convert("RGBA")
    d = ImageDraw.Draw(im)
    L, R, T, B = 78 * S, W - 26 * S, 26 * S, H - 40 * S
    tmax, mmax = max(8.0, t * 1.15), max(2.0, m * 1.2)
    grid, label = (112, 40, 56, 255), (205, 170, 175, 255)
    ystep, k = crash_step(mmax - 1), 0
    while 1 + k * ystep <= mmax:                       # horizontal lines = multipliers
        val = 1 + k * ystep
        py = B - (val - 1) / (mmax - 1) * (B - T)
        d.line([(L, py), (R, py)], fill=grid, width=S)
        d.text((L - 8 * S, py), f"x{val:g}", font=get_font(14 * S), fill=label, anchor="rm")
        k += 1
    xstep, x = crash_step(tmax, 5), 0.0
    while x <= tmax:                                   # vertical lines = seconds
        px = L + x / tmax * (R - L)
        d.line([(px, T), (px, B)], fill=grid, width=S)
        d.text((px, B + 8 * S), f"{x:g}s", font=get_font(14 * S), fill=label, anchor="mt")
        x += xstep
    col = {"run": (235, 190, 60), "crash": (230, 60, 60), "cash": (90, 255, 120)}[state]
    N = 70
    pts = []
    for i in range(N + 1):
        tt = t * i / N
        pts.append((L + tt / tmax * (R - L), B - (crash_mult(tt) - 1) / (mmax - 1) * (B - T)))
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))      # soft fill under the curve
    ImageDraw.Draw(ov).polygon(pts + [(pts[-1][0], B), (pts[0][0], B)], fill=col + (60,))
    im.alpha_composite(ov)
    d = ImageDraw.Draw(im)
    d.line(pts, fill=col + (255,), width=5 * S, joint="curve")
    ex, ey = pts[-1]
    if state == "run":                                 # the rocket points along the curve
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        ang = math.degrees(math.atan2(-(y2 - y1), x2 - x1)) if (x1, y1) != (x2, y2) else 10
        rk = crash_rocket().rotate(ang, expand=True, resample=Image.BICUBIC)
        im.paste(rk, (int(ex - rk.width / 2), int(ey - rk.height / 2)), rk)
    elif state == "crash":
        crash_boom(d, ex, ey, 40 * S)
    else:
        d.ellipse([ex - 9 * S, ey - 9 * S, ex + 9 * S, ey + 9 * S], fill=(90, 255, 120, 255), outline=(255, 255, 255, 255), width=3 * S)
    big = {"run": (255, 255, 255), "crash": (255, 90, 90), "cash": (110, 255, 140)}[state]
    d.text((W / 2, H * 0.38), f"x{m:.2f}", font=get_font(70 * S), fill=big + (255,), anchor="mm",
           stroke_width=4 * S, stroke_fill=(0, 0, 0, 255))
    if state != "run":
        d.text((W / 2, H * 0.38 + 62 * S), "CRASHED" if state == "crash" else "CASHED OUT", font=get_font(26 * S),
               fill=big + (255,), anchor="mm", stroke_width=2 * S, stroke_fill=(0, 0, 0, 255))
    d.rectangle([0, 0, W - 1, H - 1], outline=(235, 190, 60, 255), width=4 * S)
    buf = io.BytesIO()
    im.convert("RGB").resize((CR_W, CR_H), Image.LANCZOS).save(buf, "JPEG", quality=88)
    return buf.getvalue()

def crash_t(m):
    return crash_time(m) if m > 1 else 0.0

async def crash_pre(*args):
    try:
        return await asyncio.to_thread(render_crash, *args)
    except Exception:
        return None

class CrashView(OwnedView):
    def __init__(self, user, bet, token, crash, auto=None):
        super().__init__(timeout=180)
        self.user, self.bet, self.token, self.crash, self.auto = user, bet, token, crash, auto
        self.message = self.t0 = self.last_name = None
        self.shown_m = 1.0          # the multiplier of the last picture the player really received
        self.done, self.render_n = False, 0
        self.edit_lock = asyncio.Lock()
        # the two pictures we already know in advance (the crash and the auto-cashout) are drawn BEFORE they are needed,
        # so when the moment comes there is nothing left to render, it only has to be uploaded
        self.pre_crash = asyncio.create_task(crash_pre(crash_t(crash), "crash", crash))
        self.pre_auto = asyncio.create_task(crash_pre(crash_t(auto), "cash", auto)) if auto and auto < crash else None

    def file_of(self, data):
        self.render_n += 1
        name = f"crash{self.render_n}.jpg"
        return discord.File(io.BytesIO(data), name), name

    async def frame(self, t, state, m):
        return self.file_of(await asyncio.to_thread(render_crash, t, state, m))

    def embed_run(self, m, name):
        lines = [f"**Bet:** `{fmt(self.bet)}` {cur()}",
                 f"**Multiplier:** `x{m:.2f}`",
                 f"**Cashout now:** `{fmt(int(self.bet * m))}` {cur()}"]
        if self.auto:
            lines.append(f"**Auto cashout:** `x{self.auto:g}`")
        e = make_embed(self.user, "\n".join(lines), YELLOW, "🚀 Crash")
        e.set_image(url=f"attachment://{name}")
        return e

    async def settle(self, kind, m, interaction=None):
        # everything up to the first await is synchronous: the round can only be settled once
        if self.done:
            if interaction is not None and not interaction.response.is_done():
                await interaction.response.defer()
            return
        self.done = True
        pending_done(self.token)
        returned = int(self.bet * m) if kind == "cash" else 0
        if returned > self.bet:                                    # $multi bonus on a win (0 when off)
            returned += multi_extra("crash", returned - self.bet)
        user_data(self.user.id)["cash"] += returned
        save()
        net = returned - self.bet
        log_game(self.user, f"crash (cashed out x{m:.2f})" if kind == "cash" else f"crash (crashed at x{self.crash:.2f})", self.bet, net)
        BUSY.discard(self.user.id)
        self.stop()
        shown = m if kind == "cash" else self.crash
        extra = f"✅ You cashed out at **x{m:.2f}**\n" if kind == "cash" else f"💥 Crashed at **x{self.crash:.2f}**\n"
        if net == 0:
            e = make_embed(self.user, f"{extra}Your bet was returned.\nYou now have {fmt(user_data(self.user.id)['cash'])} {cur()}.", YELLOW, "Result")
        else:
            e = result_embed(self.user, net > 0, abs(net), extra)
        async with self.edit_lock:      # waits for a frame that is still being uploaded, so it can never land AFTER the result
            if interaction is not None:
                # 1) INSTANT: the result text answers the click right away (the old picture stays for a split second)
                if self.last_name:
                    e.set_image(url=f"attachment://{self.last_name}")
                try:
                    await interaction.response.edit_message(embed=e, view=None)
                except discord.HTTPException:
                    pass
            # 2) the final picture (already drawn for crash / auto-cashout, drawn now only for a manual cashout)
            data = None
            if kind == "crash":
                data = await self.pre_crash
            elif self.pre_auto is not None and m == self.auto:
                data = await self.pre_auto
            if data is None:
                data = await asyncio.to_thread(render_crash, crash_t(shown), kind, shown)
            f, name = self.file_of(data)
            e.set_image(url=f"attachment://{name}")
            try:
                await self.message.edit(embed=e, attachments=[f], view=None)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="Cashout", style=discord.ButtonStyle.success)
    async def cashout(self, interaction, button):
        if self.done or self.t0 is None:
            if not interaction.response.is_done():
                await interaction.response.defer()
            return
        if time.monotonic() - self.t0 >= crash_time(self.crash) - 0.005:
            await self.settle("crash", self.crash, interaction)      # the rocket was already gone
        else:
            # what you see is what you get: you are paid the multiplier of the last picture you received
            await self.settle("cash", max(1.0, self.shown_m), interaction)

    async def run(self):
        try:
            tc = crash_time(self.crash)
            ta = crash_time(self.auto) if self.auto else math.inf
            nxt = CRASH_TICK
            while not self.done:
                target = min(nxt, tc, ta)                # wake up exactly at the crash / auto-cashout moment
                await asyncio.sleep(max(0.0, self.t0 + target - time.monotonic()))
                if self.done:
                    return
                t = time.monotonic() - self.t0
                if t >= tc - 0.005:
                    return await self.settle("crash", self.crash)
                if t >= ta - 0.005:
                    return await self.settle("cash", self.auto)
                m = math.floor(crash_mult(t) * 100) / 100
                f, name = await self.frame(t, "run", m)
                async with self.edit_lock:
                    if self.done:
                        return
                    try:
                        await self.message.edit(embed=self.embed_run(m, name), attachments=[f])
                        self.last_name = name
                        self.shown_m = m
                    except discord.HTTPException:
                        pass
                el = time.monotonic() - self.t0
                nxt = max(nxt + CRASH_TICK, el + 0.3)    # if Discord is slow, skip frames instead of falling behind
        except Exception as ex:
            print("Crash failed:", repr(ex))
            if not self.done:
                self.done = True
                cancel_game(self.user, self.token, self.bet)
                try:
                    await self.message.edit(embed=make_embed(self.user, "Something went wrong, your bet was returned.", RED), attachments=[], view=None)
                except Exception:
                    pass

@bot.command(name="crash", usage=CRASH_USAGE)
async def crash_cmd(ctx, amount: str = None, auto: str = None):
    auto_m = None
    if auto is not None:                                   # check the auto-cashout BEFORE taking the money
        try:
            auto_m = float(auto.lower().strip("x"))
        except ValueError:
            return await reply(ctx, f"Usage: `${CRASH_USAGE}`", RED)
        if not (CRASH_AUTO_MIN <= auto_m <= CRASH_CAP):
            return await reply(ctx, f"The auto-cashout must be between x{CRASH_AUTO_MIN:g} and x{CRASH_CAP:g}.", RED)
    bet = await take_bet(ctx, amount, CRASH_USAGE, track=True)
    if not bet:
        return
    view = CrashView(ctx.author, bet, str(ctx.message.id), crash_point(ctx.author.id), auto_m)
    try:
        f, name = await view.frame(0.0, "run", 1.0)
        view.message = await ctx.reply(embed=view.embed_run(1.0, name), file=f, view=view, mention_author=False)
        view.last_name = name
    except Exception:
        cancel_game(ctx.author, view.token, bet)
        raise
    view.t0 = time.monotonic()                             # the clock starts when the player can see the game
    t = asyncio.create_task(view.run())
    _log_tasks.add(t)
    t.add_done_callback(_log_tasks.discard)

# ================= SCRATCH CARDS ($sc) =================
# pictures live in scratch_art.py (must sit next to this file)
try:
    from scratch_art import ART as SC_ART
except Exception as _e:
    print("scratch_art.py not loaded, scratch cards disabled:", repr(_e))
    SC_ART = {}

SC_WIDTH = 560
SC_PAY_TO = "bank"     # where the winnings go ("bank" or "cash"). The purchase is ALWAYS taken from the bank.

# spots = (x, y, radius) on the ORIGINAL picture ("orig" = width, height of the picture used)
SC_CARDS = {
    "queen": {
        "name": "מלכת הלבבות", "emoji": "♥️", "min": 2_500_000, "total": 350, "cols": 5,
        "wins": {2.3: 50, 1.7: 25, 1.5: 90, 0.5: 25, 25: 1},
        "orig": (800, 950), "spots": [(412, 612, 102), (622, 612, 102), (195, 835, 102), (405, 835, 102), (620, 835, 102)],
    },
    "casino": {
        "name": "קזינו גלגל הרולטה", "emoji": "🎰", "min": 25_000_000, "total": 200, "cols": 4,
        "wins": {3.5: 5, 1.3: 50, 5: 10, 45: 1, 1.1: 20},
        "orig": (1289, 1542),
        "spots": [(x, y, 67) for y in (1138, 1340) for x in (1068, 898, 733, 567, 396, 228)],
    },
    "safe": {
        "name": "כספת", "emoji": "🔐", "min": 5_000_000, "total": 350, "cols": 3,
        "wins": {1.2: 136, 1.5: 50, 2: 25, 30: 1},
        "orig": (1289, 1526),
        "spots": [(x, y, 68) for y in (1035, 1340) for x in (935, 665, 395)],
    },
    "club": {
        "name": "הקלף", "emoji": "♣️", "min": 50_000_000, "total": 50, "cols": 4,
        "wins": {1.5: 5, 2: 5, 7: 2, 60: 1},
        "orig": (1289, 1580), "spots": [(640, 640, 120), (440, 930, 120), (840, 930, 120), (640, 1140, 85)],
    },
}
SC_EN = {"queen": "Queen of Hearts", "casino": "Casino Roulette Wheel", "safe": "Safe", "club": "Club"}   # card names for the English logs
SC_DECOYS = [0.3, 0.5, 0.8, 1.1, 1.3, 1.5, 1.7, 2, 2.3, 3, 3.5, 4, 5, 7, 10, 15, 25]

def sc_short(n):
    return f"{n / 1_000_000:g}M"

# ---------- the real, limited stock ----------
def sc_stock(key):
    c = SC_CARDS[key]
    store = DB.setdefault("sc_stock", {})
    st = store.get(key)
    if st is None:
        pool = [m for m, n in c["wins"].items() for _ in range(n)]
        pool += [0] * (c["total"] - len(pool))      # everything else = total loss
        random.shuffle(pool)
        st = store[key] = {"left": pool, "sold": 0}
        save()
    return st

def return_card(key, mult):
    """An unscratched card goes back into the stock (used by cancel_game / refund_pending)."""
    st, c = DB.get("sc_stock", {}).get(key), SC_CARDS.get(key)
    if not st or not c or len(st["left"]) >= c["total"]:
        return
    st["left"].insert(random.randint(0, len(st["left"])), mult)
    st["sold"] = max(0, st["sold"] - 1)

def sc_labels(n, mult):
    """Winning card: exactly 3 equal multipliers. Losing card: no multiplier appears more than twice."""
    decoys = [d for d in SC_DECOYS if d != mult]
    out, counts = ([mult] * 3 if mult else []), {}
    while len(out) < n:
        d = random.choice(decoys)
        if counts.get(d, 0) < 2:
            counts[d] = counts.get(d, 0) + 1
            out.append(d)
    random.shuffle(out)
    return out

# ---------- pictures ----------
# --- render start ---
@lru_cache(maxsize=None)
def sc_base(key):
    c = SC_CARDS[key]
    im = Image.open(io.BytesIO(base64.b64decode(SC_ART[key]))).convert("RGB")
    return im.resize((SC_WIDTH, round(SC_WIDTH * c["orig"][1] / c["orig"][0])), Image.LANCZOS)

@lru_cache(maxsize=None)
def sc_disc(r):
    S = r * 2 + 2
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i in range(r, 0, -1):
        g = int(125 + 105 * (1 - i / r) ** 0.8)
        d.ellipse([r + 1 - i, r + 1 - i, r + 1 + i, r + 1 + i], fill=(g, g, g + 8, 255))
    rng = random.Random(r)
    for _ in range(16):
        a, b = rng.uniform(-0.6, 0.6) * r, rng.uniform(-0.6, 0.6) * r
        L = rng.uniform(0.15, 0.4) * r
        d.line([(r + a, r + b), (r + a + L, r + b - L * 0.5)], fill=(245, 245, 250, 150), width=2)
    d.ellipse([1, 1, S - 2, S - 2], outline=(70, 70, 80, 255), width=3)
    return im

def sc_render(key, labels, revealed, final=False, mult=0):
    c = SC_CARDS[key]
    base = sc_base(key).copy().convert("RGBA")
    k = base.width / c["orig"][0]
    d = ImageDraw.Draw(base)
    for i, (x, y, r) in enumerate(c["spots"]):
        cx, cy, rr = int(x * k), int(y * k), int(r * k)
        if i in revealed:
            win = bool(final and mult and labels[i] == mult)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(18, 18, 26, 235),
                      outline=(90, 255, 120, 255) if win else (235, 190, 60, 255), width=5 if win else 3)
            text = f"x{labels[i]:g}"
            fs = int(rr * (0.7 if len(text) <= 3 else 0.55))
            d.text((cx, cy), text, font=get_font(fs), anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0, 255),
                   fill=(90, 255, 120, 255) if win else (255, 255, 255, 255))
        else:
            base.alpha_composite(sc_disc(rr), (cx - rr - 1, cy - rr - 1))
            d.text((cx, cy), str(i + 1), font=get_font(int(rr * 0.9)), fill=(60, 60, 72, 255), anchor="mm")
    buf = io.BytesIO()
    base.convert("RGB").save(buf, "JPEG", quality=88)
    buf.seek(0)
    return buf

@lru_cache(maxsize=1)
def sc_banner():
    tw, th = 220, 250
    im = Image.new("RGB", (tw * 4 + 6, th), (24, 24, 28))
    for i, key in enumerate(SC_CARDS):
        b = sc_base(key)
        t = b.resize((tw, round(b.height * tw / b.width)), Image.LANCZOS).crop((0, 0, tw, th))
        im.paste(t, (i * (tw + 2), 0))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()
# --- render end ---

# ---------- the game ----------
class SpotButton(discord.ui.Button):
    def __init__(self, idx, row):
        super().__init__(style=discord.ButtonStyle.secondary, label=str(idx + 1), row=row)
        self.idx = idx

    async def callback(self, interaction):
        await self.view.click(interaction, self.idx)

class ScratchView(OwnedView):
    touch = True

    def __init__(self, user, bet, key, mult, token=None):
        super().__init__(timeout=180)
        self.user, self.bet, self.key, self.mult, self.token = user, bet, key, mult, token
        self.card = SC_CARDS[key]
        self.n = len(self.card["spots"])
        self.labels = sc_labels(self.n, mult)
        self.revealed, self.done, self.message, self.render_n = set(), False, None, 0
        self.version, self.edit_lock = 0, asyncio.Lock()
        cols = self.card["cols"]
        self.spot_btns = [SpotButton(i, i // cols) for i in range(self.n)]
        self.all_btn = discord.ui.Button(style=discord.ButtonStyle.success, label="גרד הכל", row=math.ceil(self.n / cols))
        self.all_btn.callback = self.settle
        for b in (*self.spot_btns, self.all_btn):
            self.add_item(b)

    def image(self, final=False):
        self.render_n += 1
        name = f"sc{self.render_n}.jpg"
        return discord.File(sc_render(self.key, self.labels, self.revealed, final, self.mult), name), name

    def embed(self, name):
        c = self.card
        prizes = " • ".join(f"x{m:g}" for m in sorted(c["wins"], reverse=True))
        e = discord.Embed(color=YELLOW, title=f"🎟️ {c['name']}", description=(
            f"שילמת **{fmt(self.bet)}** {cur()} מהבנק\n\n"
            f"גרדו ומצאו **3 מכפילים זהים** כדי לזכות!\n"
            f"מכפילים אפשריים: {prizes}\n\nנגרדו {len(self.revealed)}/{self.n}"))
        e.set_author(name=self.user.name, icon_url=self.user.display_avatar.url)
        e.set_image(url=f"attachment://{name}")
        return e

    def reveal(self, i):
        self.revealed.add(i)
        b = self.spot_btns[i]
        b.label, b.disabled, b.style = f"x{self.labels[i]:g}", True, discord.ButtonStyle.primary

    async def click(self, interaction, idx):
        if not interaction.response.is_done():
            await interaction.response.defer()
        if self.done or idx in self.revealed:
            return
        self.reveal(idx)
        if len(self.revealed) == self.n:
            return await self.settle(interaction)
        self.version += 1
        v = self.version
        async with self.edit_lock:
            if v != self.version or self.done:
                return
            f, name = self.image()
            await interaction.edit_original_response(embed=self.embed(name), attachments=[f], view=self)

    def finalize(self):
        self.done = True
        for i in range(self.n):
            if i not in self.revealed:
                self.reveal(i)
        mult = self.mult
        if mult:
            for i, l in enumerate(self.labels):
                if l == mult:
                    self.spot_btns[i].style = discord.ButtonStyle.success if mult >= 1 else discord.ButtonStyle.danger
        returned = round(self.bet * mult)
        if returned > self.bet:                          # $multi bonus on a win (0 when off)
            returned += multi_extra("scratch", returned - self.bet)
        pending_done(self.token)
        u = user_data(self.user.id)
        u[SC_PAY_TO] += returned
        save()
        net = returned - self.bet
        log_game(self.user, f"scratch {SC_EN.get(self.key, self.key)}", self.bet, net)
        self.all_btn.disabled = True
        f, name = self.image(final=True)
        if net > 0:
            line, color = f"+ זכית ב-{fmt(net)}!", GREEN
        elif net < 0:
            line = f"- הפסדת {fmt(-net)}!" + (f" (קיבלת בחזרה {fmt(returned)})" if returned else "")
            color = RED
        else:
            line, color = "הימור הוחזר", YELLOW
        found = f"3 × x{mult:g}" if mult else "אין התאמה הפעם"
        e = discord.Embed(color=color, title=f"🎟️ {self.card['name']}", description=(
            f"{found}\n```diff\n{line}\n```\nיתרה בבנק: {fmt(u['bank'])} {cur()}"))
        e.set_author(name=self.user.name, icon_url=self.user.display_avatar.url)
        e.set_image(url=f"attachment://{name}")
        return e, f

    async def settle(self, interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        if self.done:
            return
        e, f = self.finalize()
        self.stop()
        async with self.edit_lock:
            await interaction.edit_original_response(embed=e, attachments=[f], view=self)

    async def on_timeout(self):
        if self.done:
            return
        e, f = self.finalize()
        if self.message:
            try:
                await self.message.edit(embed=e, attachments=[f], view=self)
            except Exception:
                pass

# ---------- the menu: "בחירת כרטיס גירוד" -> amount window ----------
class AmountModal(discord.ui.Modal):
    def __init__(self, menu, key):
        c = SC_CARDS[key]
        super().__init__(title=f"{c['name']} - כמה כסף?"[:45])
        self.menu, self.key = menu, key
        self.amount = discord.ui.TextInput(label=f"סכום מהבנק (מינימום {sc_short(c['min'])})"[:45],
                                           placeholder="למשל: 5m או 2500000 או half או all", max_length=20)
        self.add_item(self.amount)

    async def on_submit(self, interaction):
        menu, key, c, user = self.menu, self.key, SC_CARDS[self.key], self.menu.user
        say = lambda t: interaction.response.send_message(t, ephemeral=True)
        # no awaits between the checks and the purchase: two players can never get the same card
        if menu.chosen:
            return await say("כבר בחרת כרטיס.")
        if user.id in BUSY:
            return await say(BUSY_MSG)
        st = sc_stock(key)
        if not st["left"]:
            return await say("הכרטיס הזה אזל מהמלאי ❌")
        u = user_data(user.id)
        price = parse_amount(self.amount.value.strip(), u["bank"])
        if price is None or price <= 0:
            return await say("סכום לא תקין. למשל: `5m`, `2500000`, `half` או `all`")
        if price < c["min"]:
            return await say(f"המינימום לכרטיס הזה הוא **{fmt(c['min'])}** {cur()}.")
        if price > u["bank"]:
            return await say(f"אין לך מספיק כסף **בבנק**. יש לך {fmt(u['bank'])} {cur()} (`$dep` להפקדה).")
        u["bank"] -= price
        menu.chosen = True
        menu.stop()
        mult = st["left"].pop()
        for _ in range(luck_attempts(user.id) - 1):   # luck: take the best of a few cards from the stock
            if st["left"]:
                j = random.randrange(len(st["left"]))
                if st["left"][j] > mult:
                    st["left"][j], mult = mult, st["left"][j]
        st["sold"] += 1
        token = f"scr{interaction.id}"
        DB.setdefault("pending", {})[token] = {"uid": str(user.id), "bet": price, "scratch": [key, mult], "bank": True}
        BUSY.add(user.id)
        save()
        try:
            view = ScratchView(user, price, key, mult, token)
            view.message = interaction.message or menu.message
            f, name = view.image()
            await interaction.response.edit_message(embed=view.embed(name), attachments=[f], view=view)
        except Exception:
            cancel_game(user, token, price)
            raise

class ScratchSelect(discord.ui.Select):
    def __init__(self):
        opts = []
        for key, c in SC_CARDS.items():
            left = len(sc_stock(key)["left"])
            desc = f"מינימום {sc_short(c['min'])} • נותרו {left}/{c['total']}" if left else "אזל המלאי ❌"
            opts.append(discord.SelectOption(label=c["name"], value=key, emoji=c["emoji"], description=desc))
        super().__init__(placeholder="בחירת כרטיס גירוד", options=opts)

    async def callback(self, interaction):
        menu, key = self.view, self.values[0]
        if menu.chosen:
            return await interaction.response.defer()
        if interaction.user.id in BUSY:
            return await interaction.response.send_message(BUSY_MSG, ephemeral=True)
        if not sc_stock(key)["left"]:
            return await interaction.response.send_message("הכרטיס הזה אזל מהמלאי ❌", ephemeral=True)
        await interaction.response.send_modal(AmountModal(menu, key))
        try:
            await interaction.message.edit(view=menu)   # clears the selection so the same card can be picked again
        except Exception:
            pass

class ScratchMenu(OwnedView):
    touch = True

    def __init__(self, user):
        super().__init__(timeout=120)
        self.user, self.message, self.chosen = user, None, False
        self.add_item(ScratchSelect())

    def embed(self):
        lines = []
        for key, c in SC_CARDS.items():
            left = len(sc_stock(key)["left"])
            lines.append(f"{c['emoji']} **{c['name']}** — מינימום {sc_short(c['min'])} • " + (f"נותרו {left}/{c['total']}" if left else "אזל ❌"))
        e = discord.Embed(color=YELLOW, title="🎟️ כרטיסי גירוד", description=(
            "\n".join(lines) + "\n\nבחרו כרטיס מהרשימה, ואז הקלידו כמה כסף לשלם.\nהתשלום יורד **מהבנק בלבד**."))
        e.set_image(url="attachment://sc_menu.jpg")
        return e

    async def on_timeout(self):
        if self.chosen or not self.message:
            return
        for b in self.children:
            b.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass

@bot.command(name="scratch", aliases=["sc"], usage="sc")
async def scratch(ctx, sub: str = None):
    if sub and sub.lower() in ("restart", "reset"):       # owner only: every card is back in stock
        if ctx.author.id != OWNER_ID:
            return
        DB["sc_stock"] = {}
        for k in SC_CARDS:
            sc_stock(k)
        save()
        return await reply(ctx, "🎟️ כל כרטיסי הגירוד אופסו: כל הכרטיסים חזרו למלאי.", GREEN)
    if ctx.author.id in BUSY:
        return await reply(ctx, BUSY_MSG, RED)
    if not SC_ART:
        return await reply(ctx, "scratch_art.py is missing next to the bot file.", RED)
    view = ScratchMenu(ctx.author)
    view.message = await ctx.reply(embed=view.embed(), file=discord.File(io.BytesIO(sc_banner()), "sc_menu.jpg"),
                                   view=view, mention_author=False)

# ================= ECONOMY =================
async def resolve_target(ctx, arg):
    """`a` (or nothing) + a REPLY to a player with the mention ping ON = that player.
    Anything else is a normal @mention / id / name. Returns None if there is nobody to point at."""
    if arg is None or arg.lower() == "a":
        ref = ctx.message.reference
        if ref is None:
            return None
        msg = ref.resolved if isinstance(ref.resolved, discord.Message) else None
        if msg is None:
            try:
                msg = await ctx.channel.fetch_message(ref.message_id)
            except Exception:
                return None
        author = msg.author
        if not any(m.id == author.id for m in ctx.message.mentions):   # ping OFF: the reply doesn't tag the player
            raise ReplyPingOff()
        return ctx.guild.get_member(author.id) or await ctx.guild.fetch_member(author.id)
    return await commands.MemberConverter().convert(ctx, arg)

@bot.command(name="bal", aliases=["balance"], usage="bal [@user | a (reply)]")
async def bal(ctx, target: str = None):
    if target is None:
        member = ctx.author
    else:
        member = await resolve_target(ctx, target)
        if member is None:
            return await reply(ctx, "Usage: `$bal [@user]` — or reply to a player (ping ON) and type `$bal a`", RED)
    u, c = user_data(member.id), cur()
    await ctx.reply(embed=make_embed(member, (
        "Use the `top` command to view your rank.\n\n"
        f"• **Money Out:** {fmt(u['cash'])} {c}\n"
        f"• **Bank Money:** {fmt(u['bank'])} {c}\n"
        f"• **Total Money:** {fmt(u['cash'] + u['bank'])} {c}"), BLUE), mention_author=False)

async def move(ctx, amount, src, dst, usage, verb):
    u = user_data(ctx.author.id)
    amt = parse_amount(amount, u[src])
    if amt is None:
        return await reply(ctx, f"Usage: `${usage}`", RED)
    if amt <= 0 or amt > u[src]:
        return await reply(ctx, "You don't have that much money" + (" in your bank." if src == "bank" else "."), RED)
    u[src] -= amt
    u[dst] += amt
    save()
    log_money(ctx.author, f"🏦 **{ctx.command.name}** — {verb} **{fmt(amt)}** {cur()}", BLUE)
    await reply(ctx, f"Successfully {verb} {fmt(amt)} {cur()} {'to' if dst == 'bank' else 'from'} your bank account.", GREEN)

@bot.command(name="dep", aliases=["deposit"], usage="dep <amount | half | all>")
async def dep(ctx, amount: str = None):
    await move(ctx, amount, "cash", "bank", "dep <amount | half | all>", "deposited")

@bot.command(name="with", aliases=["withdraw"], usage="with <amount | half | all>")
async def withdraw(ctx, amount: str = None):
    await move(ctx, amount, "bank", "cash", "with <amount | half | all>", "withdrew")

async def earn(ctx, text):
    amt = random.randint(EARN_MIN, EARN_MAX)
    user_data(ctx.author.id)["cash"] += amt
    save()
    log_money(ctx.author, f"🟢 **{ctx.command.name}** — earned **{fmt(amt)}** {cur()}", GREEN)
    await reply(ctx, text.format(f"{fmt(amt)} {cur()}"), GREEN)

@bot.command(name="crime", cooldown_after_parsing=True)
@commands.cooldown(1, 120, commands.BucketType.user)
async def crime(ctx):
    await earn(ctx, "You successfully committed a crime and got {}!")

@bot.command(name="work", cooldown_after_parsing=True)
@commands.cooldown(1, 120, commands.BucketType.user)
async def work(ctx):
    await earn(ctx, "You worked hard and got {}!")

@bot.command(name="pay", usage="pay @user <amount | half | all>  (or reply + ping ON: pay a <amount>)")
async def pay(ctx, target: str = None, amount: str = None):
    member = await resolve_target(ctx, target)
    if member is None or amount is None:
        return await reply(ctx, "Usage: `$pay @user <amount | half | all>` — or reply to a player (ping ON) and type `$pay a <amount>`", RED)
    if member.bot or member.id == ctx.author.id:
        return await reply(ctx, "You can't pay this user.", RED)
    u = user_data(ctx.author.id)
    amt = parse_amount(amount, u["cash"])
    if amt is None or amt <= 0:
        return await reply(ctx, "Usage: `$pay @user <amount | half | all>`", RED)
    if amt > u["cash"]:
        return await reply(ctx, "You don't have that much money.", RED)
    u["cash"] -= amt
    user_data(member.id)["cash"] += amt
    save()
    log_money(ctx.author, f"💸 **pay** — paid **{fmt(amt)}** {cur()} to {member.name} (id {member.id})", BLUE)
    await reply(ctx, f"You paid {fmt(amt)} {cur()} to {member.name}.", GREEN)

@bot.command(name="rob", usage="rob @user  (or reply + ping ON: rob a)", cooldown_after_parsing=True)
@commands.cooldown(1, ROB_COOLDOWN, commands.BucketType.user)
async def rob(ctx, target: str = None):
    try:
        member = await resolve_target(ctx, target)
    except Exception:
        ctx.command.reset_cooldown(ctx)
        raise
    if member is None:
        ctx.command.reset_cooldown(ctx)
        return await reply(ctx, "Usage: `$rob @user` — or reply to a player (ping ON) and type `$rob a`", RED)
    if member.bot or member.id == ctx.author.id:
        ctx.command.reset_cooldown(ctx)
        return await reply(ctx, "You can't rob this user.", RED)
    me, tgt = user_data(ctx.author.id), user_data(member.id)
    loot = {k: int(tgt[k] * ROB_PERCENT) for k in ROB_FROM}   # cash only: money in the bank can't be robbed
    if not sum(loot.values()):   # nothing outside the bank: the robbery still happens, and it fails (cooldown starts)
        return await reply(ctx, f"You tried to rob a poor person and lost 0 {cur()}.", RED)
    if me["cash"] + me["bank"] > 0 and random.random() < ROB_FAIL:
        lost = me["cash"] + me["bank"]
        me["cash"] = me["bank"] = 0
        save()
        log_game(ctx.author, "rob (got caught)", 0, -lost)
        return await reply(ctx, "You got caught and lost all your money!", RED)
    for k, v in loot.items():
        tgt[k] -= v
    me["cash"] += sum(loot.values())
    save()
    log_game(ctx.author, f"rob {member.name} (id {member.id})", 0, sum(loot.values()))
    await reply(ctx, f"You robbed {fmt(sum(loot.values()))} {cur()} from {member.name}!", GREEN)

# ---------- leaderboard ($top / $lb) ----------
TOP_MODES = {"bank": lambda d: d["bank"], "total": lambda d: d["cash"] + d["bank"], "cash": lambda d: d["cash"]}
TOP_PAGE = 10

class TopView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=180)
        self.user, self.mode, self.page, self.message = user, "total", 0, None
        self.mode_btns = {}
        for m in ("bank", "total", "cash"):
            b = discord.ui.Button(label=m.capitalize(), row=0)
            b.callback = self.set_mode(m)
            self.mode_btns[m] = b
            self.add_item(b)
        refresh = discord.ui.Button(emoji="🔃", style=discord.ButtonStyle.secondary, row=0)
        refresh.callback = self.refresh
        self.add_item(refresh)
        self.prev_btn = discord.ui.Button(label="Previous Page", style=discord.ButtonStyle.secondary, row=1)
        self.prev_btn.callback = self.turn(-1)
        self.page_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, disabled=True, row=1)
        self.next_btn = discord.ui.Button(label="Next Page", style=discord.ButtonStyle.secondary, row=1)
        self.next_btn.callback = self.turn(1)
        for b in (self.prev_btn, self.page_btn, self.next_btn):
            self.add_item(b)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("Open your own leaderboard with `$lb`.", ephemeral=True)
            return False
        return True

    def ranked(self):
        f = TOP_MODES[self.mode]
        rows = [(int(uid), f(d)) for uid, d in DB["users"].items()]
        return sorted((r for r in rows if r[1] > 0), key=lambda r: r[1], reverse=True)

    def build(self):
        ranked = self.ranked()
        pages = max(1, math.ceil(len(ranked) / TOP_PAGE))
        self.page = max(0, min(self.page, pages - 1))
        start = self.page * TOP_PAGE
        lines = [f"{start + i}. <@{uid}> • {fmt(v)} {cur()}" for i, (uid, v) in enumerate(ranked[start:start + TOP_PAGE], 1)]
        for m, b in self.mode_btns.items():
            b.style = discord.ButtonStyle.primary if m == self.mode else discord.ButtonStyle.secondary
        self.prev_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= pages - 1
        self.page_btn.label = f"Page • {self.page + 1}/{pages}"
        e = discord.Embed(description="\n".join(lines) or "Nobody has any money yet.", color=BLUE)
        e.set_author(name=f"Top {self.mode.capitalize()} Users", icon_url=self.user.display_avatar.url)
        return e

    async def show(self, interaction):
        await interaction.response.edit_message(embed=self.build(), view=self)

    def set_mode(self, mode):
        async def cb(interaction):
            self.mode, self.page = mode, 0
            await self.show(interaction)
        return cb

    def turn(self, step):
        async def cb(interaction):
            self.page += step
            await self.show(interaction)
        return cb

    async def refresh(self, interaction):
        await self.show(interaction)

    async def on_timeout(self):
        for b in self.children:
            b.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

@bot.command(name="top", aliases=["lb"])
async def top(ctx):
    view = TopView(ctx.author)
    # mentions inside an embed are clickable but never ping anybody
    view.message = await ctx.reply(embed=view.build(), view=view, mention_author=False)

# ================= SHOP ($shop) =================
SHOP_TITLE = "Amram Casino Shop"
SHOP_COLOR = 0xDDC9A3
SHOP_THUMBNAIL = None   # put an image link here for the picture on the right; None = server icon

# (name, emoji, role id, price in the BANK) - cheapest at the top, most expensive at the bottom
SHOP_ITEMS = [
    ("Casino Joker",   "🃏", 1554242301927104643, 175_000_000),
    ("Casino Master",  "💎", 1554242805071876116, 225_000_000),
    ("Casino Dealer",  "🤵", 1554241846165766225, 350_000_000),
    ("Casino Legend",  "🗽", 1554239763006099487, 425_000_000),
    ("Casino Royalty", "🌟", 1554240949213724854, 500_000_000),
    ("Casino Emperor", "👑", 1554242535369482371, 675_000_000),
]

async def shop_say(interaction, text):
    await interaction.response.send_message(text, ephemeral=True)

async def shop_buy(interaction, item):
    name, emoji, role_id, price = item
    member = interaction.user
    if interaction.guild is None or not isinstance(member, discord.Member):
        return await shop_say(interaction, "This only works inside the server.")
    if loaded is None or not loaded.is_set():
        return await shop_say(interaction, "The bot is still starting, try again in a few seconds.")
    role = interaction.guild.get_role(role_id)
    if role is None:
        return await shop_say(interaction, "This role doesn't exist anymore, tell an admin.")
    owned = DB.setdefault("shop", {}).setdefault(str(member.id), [])
    if role_id in owned or role in member.roles:
        return await shop_say(interaction, f"You already own **{name}**. Each role can be bought only once.")
    u = user_data(member.id)
    if u["bank"] < price:
        return await shop_say(
            interaction,
            f"You need **{fmt(price)}** {cur()} **in your bank** for {role.mention}.\n"
            f"You have {fmt(u['bank'])} {cur()} in the bank. (`$dep` to deposit)")
    # no awaits between the check and the payment, so a double click can't charge twice
    u["bank"] -= price
    owned.append(role_id)
    save()
    try:
        await member.add_roles(role, reason="Casino shop")
    except Exception as ex:
        u["bank"] += price
        if role_id in owned:
            owned.remove(role_id)
        save()
        print("Shop: add_roles failed:", repr(ex))
        return await shop_say(interaction, "I couldn't give you the role (my role must be above it). You were not charged.")
    log_money(member, f"🛒 **shop** — bought **{name}** for **{fmt(price)}** {cur()}", YELLOW)
    await shop_say(interaction, f"✅ You bought {role.mention} for **{fmt(price)}** {cur()} (from your bank).")

class ShopButton(discord.ui.Button):
    def __init__(self, item, row):
        super().__init__(style=discord.ButtonStyle.secondary, label=item[0], emoji=item[1],
                         custom_id=f"shop:{item[2]}", row=row)
        self.item = item

    async def callback(self, interaction):
        await shop_buy(interaction, self.item)

class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)   # persistent: the buttons keep working after a restart
        for i, item in enumerate(SHOP_ITEMS):
            self.add_item(ShopButton(item, i // 2))

@bot.command(name="shop", usage="shop")
async def shop(ctx):
    try:
        lines = [f"<@&{rid}> - {fmt(price)} {cur()}" for _, _, rid, price in SHOP_ITEMS]
        e = discord.Embed(description="\n".join(lines), color=SHOP_COLOR)
        icon = ctx.guild.icon.url if ctx.guild and ctx.guild.icon else None
        e.set_author(name=SHOP_TITLE, icon_url=icon)
        thumb = SHOP_THUMBNAIL or icon
        if thumb:
            e.set_thumbnail(url=thumb)
        await ctx.send(embed=e, view=ShopView())
    except Exception as ex:
        await ctx.send(f"Shop error: `{type(ex).__name__}: {ex}`"[:1900])

# ================= STAFF / ADMIN =================
class NotStaff(commands.CheckFailure):
    pass

def admin_or_owner(ctx):
    if ctx.author.id == OWNER_ID or ctx.author.guild_permissions.administrator:
        return True
    raise commands.MissingPermissions(["administrator"])

def is_staff(ctx):
    if ctx.author.id == OWNER_ID or ctx.author.guild_permissions.administrator:
        return True
    rid = DB.get("staff_role")
    if rid and any(r.id == rid for r in ctx.author.roles):
        return True
    raise NotStaff()

admin_only = commands.check(admin_or_owner)
staff_only = commands.check(is_staff)
owner_only = commands.check(lambda ctx: ctx.author.id == OWNER_ID)

@bot.command(name="staff-role", usage="staff-role @role")
@admin_only
async def staff_role(ctx, role: discord.Role = None):
    if role is None:
        current = ctx.guild.get_role(DB.get("staff_role") or 0)
        return await reply(ctx, f"Staff role: {current.mention if current else 'not set'}\nSet it with `$staff-role @role`", BLUE)
    DB["staff_role"] = role.id
    save()
    await reply(ctx, f"Staff role set to {role.mention}. Members with this role can now use the staff commands.", GREEN)

@bot.command(name="setgamelogs", usage="setgamelogs #channel")
@admin_only
async def setgamelogs(ctx, channel: discord.TextChannel = None):
    if channel is None:
        current = DB.get("log_channel")
        return await reply(ctx, f"Log channel: {f'<#{current}>' if current else 'not set'}\nSet it with `$setgamelogs #channel`", BLUE)
    perms = channel.permissions_for(ctx.guild.me)
    if not (perms.view_channel and perms.send_messages and perms.embed_links):
        return await reply(ctx, f"I can't send embeds in {channel.mention}. Give me permission there first.", RED)
    DB["log_channel"] = channel.id
    save()
    await reply(ctx, f"Game logs will now be sent to {channel.mention}.", GREEN)
    log_event(ctx.author, "✅ This channel is now the game log (wins, losses and money changes).", BLUE)

async def parse_money_args(ctx, args):
    where = member = amount = None
    for a in args:
        low = a.lower()
        if where is None and low in ("bank", "cash", "all"):
            where = low
        elif member is None and (re.fullmatch(r"<@!?\d+>", a) or (a.isdigit() and len(a) >= 15)):
            member = await commands.MemberConverter().convert(ctx, a)
        elif amount is None and parse_amount(a, 0) is not None:
            amount = a
        elif member is None:
            member = await commands.MemberConverter().convert(ctx, a)
        else:
            raise commands.BadArgument()
    return where, member, amount

def add_cap_error(ctx, amt):
    cap = DB.get("add_max")
    if ctx.author.id != OWNER_ID and cap and amt > cap:
        return f"You can add at most **{fmt(cap)}** {cur()} per command."
    return None

@bot.command(name="addmoney", usage="addmoney <bank|cash> @user <amount>")
@staff_only
async def addmoney(ctx, *args: str):
    where, member, amount = await parse_money_args(ctx, args)
    amt = parse_amount(amount, 0)
    if where not in ("bank", "cash") or member is None or amt is None or amt <= 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    err = add_cap_error(ctx, amt)
    if err:
        return await reply(ctx, err, RED)
    user_data(member.id)[where] += amt
    save()
    log_event(ctx.author, f"💰 **addmoney** — added **{fmt(amt)}** {cur()} to {member.name}'s {where} (id {member.id})", BLUE)
    await reply(ctx, f"Added {fmt(amt)} {cur()} to {member.name}'s {where}.", GREEN)

@bot.command(name="resetmoney", usage="resetmoney <bank|cash|all> @user [amount]")
@staff_only
async def resetmoney(ctx, *args: str):
    where, member, amount = await parse_money_args(ctx, args)
    amt = 0 if amount is None else parse_amount(amount, 0)
    if where not in ("bank", "cash", "all") or member is None or amt is None or amt < 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    u = user_data(member.id)
    if where == "all":
        u["cash"] = u["bank"] = 0
    else:
        u[where] = amt
    save()
    log_event(ctx.author, f"💰 **resetmoney** — {member.name}'s {where} " + ("reset to 0" if where == "all" else f"set to **{fmt(amt)}**") +
              f" (id {member.id})", BLUE)
    await reply(ctx, f"{member.name}'s {where} " + ("was reset to 0." if where == "all" else f"was set to {fmt(amt)} {cur()}."), GREEN)

@bot.command(name="addmoneyrole", usage="addmoneyrole <bank|cash> @role <amount>")
@staff_only
async def addmoneyrole(ctx, where: str, role: discord.Role, amount: str):
    where = where.lower()
    amt = parse_amount(amount, 0)
    if where not in ("bank", "cash") or amt is None or amt <= 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    err = add_cap_error(ctx, amt)
    if err:
        return await reply(ctx, err, RED)
    if not ctx.guild.chunked:
        await ctx.guild.chunk()
    members = [m for m in role.members if not m.bot]
    if not members:
        return await reply(ctx, "No members found in that role.", RED)
    for m in members:
        user_data(m.id)[where] += amt
    save()
    log_event(ctx.author, f"💰 **addmoneyrole** — added **{fmt(amt)}** {cur()} to the {where} of {len(members)} members of {role.name}", BLUE)
    await reply(ctx, f"Added {fmt(amt)} {cur()} to the {where} of each of the {len(members)} members of {role.mention}.", GREEN)

@bot.command(name="set-currency", aliases=["currency"], usage="set-currency <emoji>")
@staff_only
async def currency(ctx, symbol: str = None):
    if symbol is None:
        return await reply(ctx, f"Current currency: {cur()}\nChange it with `$set-currency <emoji>`", BLUE)
    DB["currency"] = symbol
    save()
    await reply(ctx, f"Currency changed to {symbol}", GREEN)

# ================= OWNER =================
def resolve_key(name):
    name = name.lower().lstrip("$")
    if name in ("s$mines", "smines"):
        return "s$mines"
    cmd = bot.get_command(name)
    return cmd.name if cmd else None

@bot.command(name="disable", usage="disable <command>")
@owner_only
async def disable(ctx, name: str = None):
    off = DB.setdefault("disabled", [])
    if name is None:
        return await reply(ctx, "Disabled: " + (", ".join(f"`{k}`" for k in off) or "none"), BLUE)
    key = resolve_key(name)
    if key is None:
        return await reply(ctx, "Unknown command.", RED)
    if key in ("disable", "enable"):
        return await reply(ctx, "You can't disable this command.", RED)
    if key not in off:
        off.append(key)
        save()
    await reply(ctx, f"`{key}` is now disabled. The bot will not answer to it anymore.", GREEN)

@bot.command(name="enable", aliases=["undisable"], usage="undisable <command | all>")
@owner_only
async def enable(ctx, name: str):
    off = DB.setdefault("disabled", [])
    key = "all" if name.lower() == "all" else resolve_key(name)
    if key == "all":
        off.clear()
    elif key in off:
        off.remove(key)
    else:
        return await reply(ctx, "This command isn't disabled.", RED)
    save()
    await reply(ctx, "All commands are enabled." if key == "all" else f"`{key}` is enabled again.", GREEN)

@bot.command(name="setaddmoney", usage="setaddmoney <max | off>")
@owner_only
async def setaddmoney(ctx, amount: str = None):
    cap = DB.get("add_max")
    if amount is None:
        return await reply(ctx, f"Add-money limit: {fmt(cap) + ' ' + cur() if cap else 'no limit'}\nSet it with `$setaddmoney <max>` (or `off`)", BLUE)
    if amount.lower() in ("off", "none", "no"):
        DB.pop("add_max", None)
        save()
        return await reply(ctx, "The add-money limit was removed.", GREEN)
    amt = parse_amount(amount, 0)
    if amt is None or amt <= 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    DB["add_max"] = amt
    save()
    await reply(ctx, f"Staff can now add at most {fmt(amt)} {cur()} per command.", GREEN)

@bot.command(name="multi", usage="multi <game | all> <amount | off> [time: 10m, 2h, 1d]")
@owner_only
async def multi(ctx, game: str = None, amount: str = None, duration: str = None):
    """Owner only. Multiplies the NET profit of every WIN in the chosen game (1-5), optionally for a limited time.
    `$multi gm 3`, `$multi gm 3 1h`, `$multi all 2 10m`, `$multi bj off`."""
    cfg = DB.setdefault("multi", {})
    until = DB.setdefault("multi_until", {})
    for k in [k for k, t in until.items() if t and time.time() >= t]:   # drop expired ones
        cfg.pop(k, None)
        until.pop(k, None)
    games = ", ".join(f"`{g}`" for g in MULTI_GAMES)
    if game is None:
        active = "\n".join(f"• `{k}` → **x{v:g}** ({fmt_left(until.get(k))})" for k, v in cfg.items()) or "No active multipliers."
        return await reply(ctx, f"**🔥 Multi (owner)**\n{active}\n\nUsage: `${ctx.command.usage}` (amount 1-{MULTI_MAX})\nGames: {games}", BLUE)
    g = game.lower().lstrip("$")
    if g in ("off", "reset", "clear") and amount is None:
        cfg.clear()
        until.clear()
        save()
        return await reply(ctx, "All multipliers were removed.", GREEN)
    if g == "all":
        keys = list(MULTI_GAMES)
    else:
        key = resolve_key(g)
        if key not in MULTI_GAMES:
            return await reply(ctx, f"Unknown game. Games: {games}", RED)
        keys = [key]
    if amount is None:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    if amount.lower() in ("off", "none", "no"):
        value = None
    else:
        try:
            value = float(amount.lower().strip("x"))
        except ValueError:
            return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
        if not (1 <= value <= MULTI_MAX):
            return await reply(ctx, f"The multiplier must be between 1 and {MULTI_MAX}.", RED)
    secs = None
    if duration is not None:
        secs = parse_duration(duration)
        if secs is None:
            return await reply(ctx, f"Invalid time. Examples: `30s`, `10m`, `2h`, `1d`, `1h30m`\nUsage: `${ctx.command.usage}`", RED)
    end_at = int(time.time() + secs) if secs else None
    for k in keys:
        if value is None or value == 1:
            cfg.pop(k, None)
            until.pop(k, None)
        else:
            cfg[k] = value
            if end_at:
                until[k] = end_at
            else:
                until.pop(k, None)
    save()
    names = "all games" if g == "all" else f"`{keys[0]}`"
    if value is None or value == 1:
        return await reply(ctx, f"Multi removed from {names}.", GREEN)
    await reply(ctx, f"🔥 Multi **x{value:g}** is now active on {names} ({fmt_left(end_at)}). "
                     f"Every win pays x{value:g} of the normal profit.", GREEN)

# ---------- $luck / $unluck: only the OWNER can type them, but the luck works for EVERY player ----------
async def luck_say(ctx, text):
    # a small plain message in the same chat (no DM, the command message is not deleted)
    await ctx.reply(text, mention_author=False)

@bot.command(name="luck", usage="luck <2.5x | off> [time: 10m, 2h, 1d]")
@owner_only
async def luck(ctx, amount: str = None, duration: str = None):
    """Owner only (only the owner can type it). While it is ON, every player's games get extra tries to end well:
    x2 = every game gets 2 tries, x2.5 = 2 tries + a 50% chance for a 3rd."""
    cfg = DB.get("luck")
    if cfg and cfg.get("until") and time.time() >= cfg["until"]:
        DB.pop("luck", None)
        cfg = None
        save()
    if amount is None:
        if not cfg:
            return await luck_say(ctx, f"🍀 Luck is OFF. Usage: `${ctx.command.usage}` (1-{LUCK_MAX})")
        return await luck_say(ctx, f"🍀 Luck is **x{cfg['value']:g}** for everyone ({fmt_left(cfg.get('until'))}).")
    if amount.lower() in ("off", "none", "no", "reset"):
        DB.pop("luck", None)
        save()
        return await luck_say(ctx, "🍀 Luck is OFF.")
    try:
        value = float(amount.lower().strip("x"))
    except ValueError:
        return await luck_say(ctx, f"Usage: `${ctx.command.usage}`")
    if not (1 <= value <= LUCK_MAX):
        return await luck_say(ctx, f"Luck must be between 1 and {LUCK_MAX}.")
    secs = None
    if duration is not None:
        secs = parse_duration(duration)
        if secs is None:
            return await luck_say(ctx, "Invalid time. Examples: `30s`, `10m`, `2h`, `1d`, `1h30m`")
    if value == 1:
        DB.pop("luck", None)
        save()
        return await luck_say(ctx, "🍀 Luck is OFF.")
    end_at = int(time.time() + secs) if secs else None
    DB["luck"] = {"value": value, "until": end_at}
    save()
    await luck_say(ctx, f"🍀 Luck **x{value:g}** is ON for everyone ({fmt_left(end_at)}).")

@bot.command(name="unluck", usage="unluck")
@owner_only
async def unluck(ctx):
    DB.pop("luck", None)
    save()
    await luck_say(ctx, "🍀 Luck is OFF.")

class ConfirmReset(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=30)
        self.user, self.message = user, None

    async def interaction_check(self, interaction):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("Only the owner can do this.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Yes, reset everyone", style=discord.ButtonStyle.danger)
    async def yes(self, interaction, button):
        n = 0
        for d in DB["users"].values():
            if d.get("cash") or d.get("bank"):
                n += 1
            d["cash"] = d["bank"] = 0
        save()
        self.stop()
        await interaction.response.edit_message(
            embed=make_embed(self.user, f"✅ The economy was reset: cash and bank of {n} players are now 0.", GREEN), view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def no(self, interaction, button):
        self.stop()
        await interaction.response.edit_message(embed=make_embed(self.user, "Cancelled.", BLUE), view=None)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(embed=make_embed(self.user, "Timed out, nothing was reset.", BLUE), view=None)
            except Exception:
                pass

@bot.command(name="reset-economy", aliases=["reset-economey", "reseteconomy"], usage="reset-economy")
@owner_only
async def reset_economy(ctx):
    view = ConfirmReset(ctx.author)
    view.message = await ctx.reply(embed=make_embed(
        ctx.author, "⚠️ This sets the **cash and bank of every player** to 0. It can't be undone.", RED),
        view=view, mention_author=False)

async def secret_toggle(ctx, key, on, text):
    if on:
        DB[key] = True
    else:
        DB.pop(key, None)
    save()
    try:
        await ctx.message.delete()
    except Exception:
        pass
    try:
        await ctx.author.send(text)
    except Exception:
        await reply(ctx, text, BLUE)

def secret_cmd(key, on, text):
    async def cmd(ctx):
        await secret_toggle(ctx, key, on, text)
    return cmd

for _n, _k, _on, _t in (
        ("predict", "predict", True, "🔮 Predict is ON: you get every board (mt, S$mines, gm, mines) in your DMs."),
        ("unpredict", "predict", False, "🔮 Predict is OFF."),
        ("touch", "touch", True, "👆 Touch is ON: you can click the buttons of any player's mt, S$mines, gm and mines game."),
        ("untouch", "touch", False, "👆 Touch is OFF.")):
    bot.command(name=_n)(owner_only(secret_cmd(_k, _on, _t)))

def info_embed(user, title, description, sections):
    e = discord.Embed(title=title, description=description, color=BLUE)
    e.set_author(name=user.name, icon_url=user.display_avatar.url)
    for name, lines in sections:
        e.add_field(name=name, value="\n".join(lines), inline=False)
    return e

INFO_SECTIONS = [
    ("🎮 משחקי לוח", [
        "`$gm` – חושפים אוצרות ופצצות, ואפשר לצאת עם Cashout בכל רגע",
        "`$mines` – פצצה אחת, כל יהלום מעלה את הרווח",
        "`S$mines` – כמו mines עם בחירת גודל לוח",
        "`$mt` – מגדל כסף, מטפסים שורה אחרי שורה"]),
    ("🃏 קלפים ומזל", [
        "`$bj` – בלאק ג'ק",
        "`$slots` – מכונת סלוטים",
        "`$hl` – גבוה או נמוך",
        "`$ht` – עץ או פלי",
        "`$cf` – קרב תרנגולות",
        "`$crash <סכום> [x2.5]` – מכפיל שעולה בזמן אמת, לוחצים Cashout לפני שהוא מתרסק (אפשר גם יציאה אוטומטית)"]),
    ("🎡 רולטה", [
        "`$roulette <סכום> <בחירות>` (או `$rl`)",
        "אפשר 1, 2 או 4 בחירות מופרדות בפסיק, והסכום מתחלק ביניהן",
        "דוגמה: `$roulette all 0,red,6,odd`",
        "בחירות: מספר 0-36, `red`, `black`, `even`, `odd`, `1-18`, `19-36`, `1-12`, `13-24`, `25-36`, `1st`, `2nd`, `3rd`"]),
    ("🎟️ כרטיסי גירוד", [
        "`$sc` – בוחרים כרטיס מהרשימה, מקלידים סכום (מהבנק בלבד) וגורדים",
        "מלכת הלבבות • קזינו גלגל הרולטה • כספת • הקלף"]),
    ("💰 כלכלה", [
        "`$bal [@user]` – מזומן ובנק",
        "`$dep` / `$with` – הפקדה לבנק ומשיכה",
        "`$work` / `$crime` – הרווחה מהירה",
        "`$rob @user` – שוד מזומן של שחקן אחר",
        "`$pay @user <סכום>` – העברת כסף",
        "`$top` / `$lb` – טבלת העשירים",
        "`$shop` – חנות רולים"]),
    ("💡 טיפים", [
        "סכום: מספר, `half`, `all`, או `5k` / `2.5m` / `1b`",
        "אפשר לשחק רק משחק אחד בכל פעם – צריך לסיים אותו קודם",
        "אפשר גם ריפליי לשחקן עם תיוג **ON** ואז `$rob a` / `$pay a <סכום>` / `$bal a`"]),
]

AINFO_SECTIONS = [
    ("🛠 צוות (אדמין או רול צוות)", [
        "`$addmoney <bank|cash> @user <סכום>` – הוספת כסף",
        "`$addmoneyrole <bank|cash> @role <סכום>` – כסף לכל חברי הרול",
        "`$resetmoney <bank|cash|all> @user [סכום]` – איפוס כסף של שחקן",
        "`$set-currency <אימוג'י>` – שינוי סמל המטבע"]),
    ("⚙️ אדמין", [
        "`$staff-role @role` – קובע איזה רול נחשב צוות",
        "`$setgamelogs #channel` – חדר הלוגים"]),
    ("👑 בעלים", [
        "`$setaddmoney <מקסימום>` – תקרה להוספת כסף לצוות (`off` מבטל)",
        "`$multi <משחק|all> <1-5|off> [זמן]` – מכפיל לרווח נטו בכל ניצחון (זמן: 10m, 2h, 1d)",
        "`$luck <1-10>x [זמן]` – מזל לכל השחקנים (רק הבעלים יכול להפעיל)",
        "`$unluck` – מבטל את המזל",
        "`$sc restart` – מחזיר את כל כרטיסי הגירוד למלאי",
        "`$reset-economy` – מאפס את הכסף של כולם, עם כפתור אישור",
        "`$disable <פקודה>` / `$undisable <פקודה|all>` – חסימה ושחרור של פקודה"]),
    ("🧩 פקודות עם !", [
        "`!set-role-member` – פאנל עם כפתור לקבלת רול (אדמין, בחדר שהוגדר)",
        "`!clear <כמות>` – מוחק עד 350 הודעות (רק למי שיש את רול המחיקה)",
        "🛡️ הגנה: מי שמוסיף בוט לשרת מועף, והבוט מועף איתו"]),
]

@bot.command(name="info")
async def info(ctx):
    await ctx.reply(embed=info_embed(ctx.author, "📖 מדריך הבוט", "הפקודות פועלות עם `$` בתחילת ההודעה.", INFO_SECTIONS),
                    mention_author=False)

@bot.command(name="ainfo")
@staff_only
async def ainfo(ctx):
    await ctx.reply(embed=info_embed(ctx.author, "🛠 מדריך צוות", "פקודות ניהול.", AINFO_SECTIONS),
                    mention_author=False)

bot.run(TOKEN)
