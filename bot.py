import discord, random, json, os, asyncio, io, signal, math, time, base64
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
CHANNELS = {1541567870591443026, 1502311424808980690}
OWNER_ID = 1537816435370229820
# The backup keeps everybody's money (and the scratch card stock) safe when the host wipes its disk.
# By default the bot keeps ONE backup message in the OWNER's DMs and edits it.
BACKUP_CHANNEL_ID = int(os.environ.get("BACKUP_CHANNEL_ID") or 0)
MIN_BET = 150
EARN_MIN, EARN_MAX = 6500, 16000
DEALER_STANDS_ON = 13
EMPTY = "\u200e"   # blank button label
GREEN, RED, BLUE, YELLOW = 0x77B255, 0xC0392B, 0x3B82F6, 0xF1C40F

EMOJI = {"bomb": "💣", "map": "🗺️", "diamond": "💎", "coin": "🪙", "stone": "🪨", "bag": "💰", "urn": "🏺"}
MULT = {"diamond": 3.5, "urn": 25, "stone": 1.1, "coin": 2, "bag": 5.5, "map": 1}
URN_CHANCE = (3, 7)   # 3 out of 7 games have the urn 🏺
MINES_MULT = [1.1, 1.3, 1.6, 2, 2.2, 4.6, 7.6, 10.2]
MINES_COMPOUND = False
SMINES_COMPOUND = False
SMINES = {   # key: (columns, rows, mines, multiplier per click)
    "2x2": (2, 2, 1, [1.4, 2.3, 4.3]),
    "4x4": (4, 4, 3, [1.2, 1.4, 1.5, 1.7, 2, 2.5, 2.8, 4.5, 5.7, 5.8, 6, 7, 12.3]),
    "5x4": (5, 4, 5, [1.2, 1.5, 1.8, 2, 2.3, 2.6, 2.9, 3.4, 3.6, 3.8, 3.9, 4, 4.2, 5.4, 19]),
}
MT_MULT = [1.3, 1.7, 2.2, 2.9, 4.5]
MT_SAFE = "💲"

# ---------- SCRATCH CARDS (a real, limited stock) ----------
SCRATCH_CARDS = {
    "deadsea": {
        "name": "🏜️ ים המלח", "total": 750, "weekly": False, "price": (5_000_000, 45_000_000),
        "wins": {15: 1, 1.7: 20, 1.3: 50, 1.2: 50, 0.5: 80, 0.2: 150},
        "symbols": {15: "💎", 1.7: "🐪", 1.3: "⛰️", 1.2: "🧂", 0.5: "🌵", 0.2: "🌊"},
        "duds": ["🪨", "☀️"],
    },
    "independence": {
        "name": "🇮🇱 יום העצמאות", "total": 250, "weekly": False, "price": (20_000_000, 100_000_000),
        "wins": {28.5: 1, 1.6: 20, 0.5: 20},
        "symbols": {28.5: "🇮🇱", 1.6: "🎆", 0.5: "🍖"},
        "duds": ["🥁", "🔥", "🎈", "🎇"],
    },
    "falafel": {
        "name": "🧆 פלאפל בפיתה", "total": 375, "weekly": True, "price": (5_000_000, 650_000_000),
        "wins": {50: 1, 1.7: 75, 0.6: 20},
        "symbols": {50: "🧆", 1.7: "🥙", 0.6: "🥒"},
        "duds": ["🌶️", "🍅", "🧂", "🥕"],
    },
    "league": {
        "name": "⚽ ליגת העל", "total": 5, "weekly": True, "price": (1_000_000, 5_000_000),
        "wins": {85: 1},
        "symbols": {85: "🏆"},
        "duds": ["📣", "🧤", "🥅", "🟨", "⚽"],
    },
}

CF_MIN, CF_MAX = 50, 84
ROB_FROM, ROB_PERCENT, ROB_FAIL, ROB_COOLDOWN = ("cash",), 0.8, 0.45, 360   # only cash can be robbed, the bank is safe
SLOTS = ["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"]
SLOT_PAY = dict(zip(SLOTS, [3, 4, 5, 8, 15, 30]))
SLOT_BUFF = 1.065      # every slots payout (pairs, triples, jackpot) is +6.5%
SLOT_WAIT = 5          # seconds the slots animation runs (counted AFTER the animation is attached)
LOAD_BUFFER = 1.5      # extra seconds so the player's client has time to load the GIF before the result appears
SLOTS_BOOST = 0.035
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
    """Understands: 500, 1,000, 5k, 2.5m, 1b, 1e5, 5e6, all, half."""
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
    """Parses + validates the bet and takes it from cash. Returns the bet or None."""
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
    save()
    return bet

def pending_done(token):
    if token:
        DB.get("pending", {}).pop(token, None)

def pending_bump(token, amount):
    if token and token in DB.get("pending", {}):
        DB["pending"][token]["bet"] += amount

def cancel_game(user, token, bet):
    """The game could not even be shown to the player: give the bet back (and the scratch card, if any)."""
    rec = DB.get("pending", {}).get(token) or {}
    if rec.get("scratch"):
        return_card(*rec["scratch"])
    pending_done(token)
    user_data(user.id)["cash"] += bet
    save()

def refund_pending():
    """Games that were running when the bot stopped can't continue (buttons die): give the bets back."""
    pend = DB.get("pending") or {}
    for rec in pend.values():
        user_data(rec["uid"])["cash"] += rec["bet"]
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
        text, color = f"🟢 **{game}** — won **+{fmt(net)}**" + (f" (bet {fmt(bet)})" if bet else ""), GREEN
    elif net < 0:
        text, color = f"🔴 **{game}** — lost **{fmt(-net)}**", RED
    else:
        text, color = f"🟡 **{game}** — push (bet {fmt(bet)} returned)", YELLOW
    log_event(user, f"{text}\nBalance: {fmt(cash)} {cur()}", color)

def log_money(user, text, color=BLUE):
    u = user_data(user.id)
    log_event(user, f"{text}\nCash: {fmt(u['cash'])} | Bank: {fmt(u['bank'])} {cur()}", color)

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
    if ctx.channel.id not in CHANNELS:
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

@bot.event
async def on_command_error(ctx, err):
    if isinstance(err, NotStaff):
        return await reply(ctx, "You need Administrator permission or the staff role to use this command.", RED)
    if isinstance(err, commands.MissingPermissions):
        return await reply(ctx, "You need Administrator permission to use this command.", RED)
    if isinstance(err, commands.CommandOnCooldown):
        m, s = divmod(int(err.retry_after) + 1, 60)
        return await reply(ctx, f"Try again in **{f'{m}m ' if m else ''}{s}s**.", RED)
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
class Tile(discord.ui.Button):
    def __init__(self, idx, cols):
        super().__init__(style=discord.ButtonStyle.secondary, label=EMPTY, row=idx // cols)
        self.idx = idx

    async def callback(self, interaction):
        await self.view.click(interaction, self.idx)

class BoardView(discord.ui.View):
    cols, header = 5, "\u200b"
    reveal_on_cashout = True
    mines_style = True         # every board game uses the same cash out / lost message
    game_name = "game"
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

    async def interaction_check(self, interaction):
        if not may_play(interaction, self.user.id):
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True

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

    async def click(self, interaction, idx):
        if not interaction.response.is_done():
            await interaction.response.defer()
        if self.done or idx in self.revealed:
            return
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
        user_data(self.user.id)["cash"] += self.bet + int(self.profit)
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
        """After a cashout of a hidden-board game (mines, S$mines, mt) the board and the buttons disappear."""
        return self if (lost or self.reveal_on_cashout) else None

    def embed(self, lost):
        """Same message in every board game (gm, mines, S$mines)."""
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

    def make_board(self):
        return take(self.user.id, "mines")

    def earn(self, kind):
        n = len(self.revealed)
        self.profit = self.bet * ((math.prod(MINES_MULT[:n]) if MINES_COMPOUND else MINES_MULT[n - 1]) - 1)

class SMines(BoardView):
    reveal_on_cashout = False

    def __init__(self, user, bet, key, token=None):
        self.key = key
        self.game_name = f"S$mines {key}"
        self.cols, rows, self.mines, self.table = SMINES[key]
        self.cells = self.cols * rows
        super().__init__(user, bet, token)

    def make_board(self):
        return take(self.user.id, f"s{self.key}")

    def earn(self, kind):
        n = min(len(self.revealed), len(self.table))
        self.profit = self.bet * ((math.prod(self.table[:n]) if SMINES_COMPOUND else self.table[n - 1]) - 1)

class MoneyTower(BoardView):
    """5 rows x 3 tiles (1 bomb per row). Climb from the bottom row up; climbing all 5 rows = automatic cashout."""
    cols = 3
    cash_row = 4
    reveal_on_cashout = False
    game_name = "money tower"
    safe_icon = MT_SAFE

    @property
    def header(self):
        return f"**{self.user.name}'s Game**"

    def __init__(self, user, bet, token=None):
        self.climbed = 0
        super().__init__(user, bet, token)
        for i, t in enumerate(self.tiles):
            t.disabled = i // 3 != 4

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

class SizeView(discord.ui.View):
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

    async def interaction_check(self, interaction):
        if not may_play(interaction, self.user.id):
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True

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
    if ctx.author.id in BUSY:
        return await reply(ctx, "You already have a Blackjack game running.", RED)
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
    """Draws a symbol as a vector-style icon (no emoji font needed on the host)."""
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
    """Returns (gif_bytes, png_bytes). The 3 reels spin and stop one after the other on `final`."""
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

# ---------- pre-rendered animations: the game message is sent with the animation already attached ----------
SLOT_CACHE = {}    # (sym, sym, sym) -> (gif, png)   all 216 combinations are prepared in the background
ROUL_POOL = {n: [] for n in range(37)}   # winner -> ready animations (a new one is prepared after each use)
ROUL_POOL_SIZE = 1

async def get_slots_anim(final):
    key = tuple(final)
    if key not in SLOT_CACHE:
        win = max(final.count(s) for s in SLOTS) >= 2
        SLOT_CACHE[key] = await asyncio.to_thread(render_slots, list(final), win)
    return SLOT_CACHE[key]

async def refill_roul(n):
    try:
        while len(ROUL_POOL[n]) < ROUL_POOL_SIZE:
            ROUL_POOL[n].append(await asyncio.to_thread(render_roulette, n))
            await asyncio.sleep(0.1)
    except Exception as ex:
        print("Roulette prepare failed:", repr(ex))

async def get_roul_anim(winner):
    if ROUL_POOL[winner]:
        anim = ROUL_POOL[winner].pop(0)
    else:
        anim = await asyncio.to_thread(render_roulette, winner)
    t = asyncio.create_task(refill_roul(winner))
    _log_tasks.add(t)
    t.add_done_callback(_log_tasks.discard)
    return anim

async def warm_animations():
    """Runs once in the background after the bot starts, so the first players don't wait for the rendering."""
    try:
        for n in range(37):
            await refill_roul(n)
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
    if ctx.author.id in BUSY:
        return await reply(ctx, "You already have a game running.", RED)
    bet = await take_bet(ctx, amount, "slots <amount | half | all>", track=True)
    if not bet:
        return
    token = str(ctx.message.id)
    BUSY.add(ctx.author.id)
    try:
        final = [random.choice(SLOTS) for _ in range(3)]
        if len(set(final)) == 3 and random.random() < SLOTS_BOOST / (120 / 216):
            final[1] = final[0]
        top = max(final.count(s) for s in SLOTS)
        mult = (SLOT_PAY[final[0]] if top == 3 else 1.5 if top == 2 else 0) * SLOT_BUFF
        win = int(bet * mult)
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
        extra = f"{line}\n" + (f"**x{mult:g}**\n\n" if win else "\n")
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

# ================= ROULETTE (animated GIF of a real European wheel) =================
ROUL_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
ROUL_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
ROUL_COOLDOWN = 10
ROUL_WAIT = 10                     # seconds the animation runs (counted AFTER the animation is attached)
ROUL_SIZE, ROUL_FRAMES, ROUL_FRAME_MS = 270, 70, 130
ROUL_USAGE = "roulette <amount | half | all> <red|black|even|odd|1-12|13-24|25-36|1-18|19-36|0-36>"

def roul_color(n):
    return "green" if n == 0 else "red" if n in ROUL_RED else "black"

def parse_roul_pick(text):
    """Returns (label, test, payout multiplier) or None."""
    if text is None:
        return None
    t = text.lower().strip().replace(" ", "").replace("–", "-").replace("־", "-")
    red = ("🔴 Red", lambda n: n in ROUL_RED, 2)
    black = ("⚫ Black", lambda n: n != 0 and n not in ROUL_RED, 2)
    even = ("Even", lambda n: n != 0 and n % 2 == 0, 2)
    odd = ("Odd", lambda n: n % 2 == 1, 2)
    d1 = ("1-12", lambda n: 1 <= n <= 12, 3)
    d2 = ("13-24", lambda n: 13 <= n <= 24, 3)
    d3 = ("25-36", lambda n: 25 <= n <= 36, 3)
    h1 = ("1-18", lambda n: 1 <= n <= 18, 2)
    h2 = ("19-36", lambda n: 19 <= n <= 36, 2)
    names = {
        "red": red, "r": red, "אדום": red,
        "black": black, "b": black, "שחור": black,
        "even": even, "זוגי": even,
        "odd": odd, "אי-זוגי": odd, "איזוגי": odd,
        "1-12": d1, "1st": d1, "13-24": d2, "2nd": d2, "25-36": d3, "3rd": d3,
        "1-18": h1, "19-36": h2,
    }
    if t in names:
        return names[t]
    if t.isdigit() and 0 <= int(t) <= 36:
        k = int(t)
        return (f"Number {k}", lambda n: n == k, 36)
    return None

def render_roulette(winner):
    """Returns (gif_bytes, png_bytes). The wheel spins, the ball circles the other way, slows down and drops into `winner`."""
    S = ROUL_SIZE
    k = S / 380
    c, R = S / 2, S / 2 - 6
    step = 360 / 37
    idx = ROUL_ORDER.index(winner)
    spin = 360 * random.choice((3, 4)) + random.uniform(0, 360)
    ball_laps = random.choice((6, 7))
    start = random.uniform(0, 360)
    font = get_font(max(8, int(13 * k)))
    cols = {"red": (192, 28, 34), "black": (24, 24, 24), "green": (0, 140, 70)}
    br_px = max(4, int(8 * k))

    def frame(p, final=False):
        e = 1 - (1 - p) ** 3                        # wheel slows down
        wheel = start + spin * e                    # rotation (degrees, clockwise from the top)
        im = Image.new("RGB", (S, S), (14, 40, 30))
        d = ImageDraw.Draw(im)
        d.ellipse([c - R, c - R, c + R, c + R], fill=(92, 52, 22))                        # wooden rim
        g = 8 * k
        d.ellipse([c - R + g, c - R + g, c + R - g, c + R - g], fill=(200, 160, 60))      # gold ring
        rp = R - 12 * k
        for i, n in enumerate(ROUL_ORDER):
            a0 = wheel + i * step - step / 2 - 90
            d.pieslice([c - rp, c - rp, c + rp, c + rp], a0, a0 + step, fill=cols[roul_color(n)], outline=(215, 190, 110))
        rin = rp * 0.66
        d.ellipse([c - rin, c - rin, c + rin, c + rin], fill=(46, 30, 16))                # inner disc
        for i, n in enumerate(ROUL_ORDER):
            a = math.radians(wheel + i * step - 90)
            x, y = c + rp * 0.84 * math.cos(a), c + rp * 0.84 * math.sin(a)
            d.text((x, y), str(n), font=font, fill=(255, 255, 255), anchor="mm")
        rin2 = rin * 0.72
        d.ellipse([c - rin2, c - rin2, c + rin2, c + rin2], fill=(120, 80, 30), outline=(215, 190, 110), width=2)
        hub = 10 * k
        d.ellipse([c - hub, c - hub, c + hub, c + hub], fill=(215, 190, 110))
        for j in range(4):                                                                 # hub spokes
            a = math.radians(wheel * 1.0 + j * 90)
            d.line([c, c, c + rin2 * 0.9 * math.cos(a), c + rin2 * 0.9 * math.sin(a)], fill=(215, 190, 110), width=3)
        # the ball: circles against the wheel, then falls into the winning pocket and travels with it
        ball_deg = wheel + idx * step - 90 - ball_laps * 360 * (1 - p) ** 2
        drop = min(1, max(0, (p - 0.55) / 0.35))
        br = (R - 8 * k) * (1 - drop) + rp * 0.95 * drop if not final else rp * 0.95
        if final:
            ball_deg = wheel + idx * step - 90
        bx, by = c + br * math.cos(math.radians(ball_deg)), c + br * math.sin(math.radians(ball_deg))
        d.ellipse([bx - br_px, by - br_px, bx + br_px, by + br_px], fill=(250, 250, 250), outline=(150, 150, 150), width=1)
        return im

    frames = [frame(i / (ROUL_FRAMES - 1)) for i in range(ROUL_FRAMES)]
    frames[-1] = frame(1.0, final=True)
    gif, png = io.BytesIO(), io.BytesIO()
    pal = [f.quantize(colors=64, method=Image.MEDIANCUT) for f in frames]
    pal[0].save(gif, "GIF", save_all=True, append_images=pal[1:], duration=[ROUL_FRAME_MS] * (len(pal) - 1) + [6000], loop=0, optimize=False)
    frames[-1].save(png, "PNG")
    return gif.getvalue(), png.getvalue()

@bot.command(name="roulette", aliases=["rl"], usage=ROUL_USAGE, cooldown_after_parsing=True)
@commands.cooldown(1, ROUL_COOLDOWN, commands.BucketType.user)
async def roulette(ctx, amount: str = None, pick: str = None):
    choice = parse_roul_pick(pick)
    if choice is None or ctx.author.id in BUSY:
        ctx.command.reset_cooldown(ctx)
        return await reply(ctx, "You already have a game running." if choice else f"Usage: `${ROUL_USAGE}`", RED)
    bet = await take_bet(ctx, amount, ROUL_USAGE, track=True)
    if not bet:
        return ctx.command.reset_cooldown(ctx)
    token = str(ctx.message.id)
    BUSY.add(ctx.author.id)
    try:
        label, test, mult = choice
        winner = random.randint(0, 36)          # European wheel: 37 pockets (0-36), every pocket 1/37
        won = bool(test(winner))
        win = bet * mult if won else 0
        # the animation is ready (pre-rendered), so the message is sent WITH it, straight away
        try:
            gif, png = await get_roul_anim(winner)
        except Exception:
            cancel_game(ctx.author, token, bet)
            ctx.command.reset_cooldown(ctx)
            raise
        e = make_embed(ctx.author, f"🎡 **Roulette**\n\nYou bet **{fmt(bet)}** {cur()} on **{label}**\n\n⏳ Spinning...", YELLOW)
        e.set_image(url="attachment://roulette.gif")
        msg = None
        try:
            msg = await ctx.reply(embed=e, file=discord.File(io.BytesIO(gif), "roulette.gif"), mention_author=False)
            await asyncio.sleep(ROUL_WAIT + LOAD_BUFFER)
        except discord.HTTPException:
            pass
        # 3) the money moves, the result is shown, and THEN the log is written
        pending_done(token)
        user_data(ctx.author.id)["cash"] += win
        save()
        emoji = {"red": "🔴", "black": "⚫", "green": "🟢"}[roul_color(winner)]
        result = result_embed(ctx.author, won, win - bet if won else bet, f"The ball landed on {emoji} **{winner}**\nYour bet: **{label}**\n\n")
        result.set_image(url="attachment://roulette_result.png")
        if msg:
            try:
                await msg.edit(embed=result, attachments=[discord.File(io.BytesIO(png), "roulette_result.png")])
            except discord.HTTPException:
                pass
        log_game(ctx.author, "roulette", bet, win - bet)
    finally:
        BUSY.discard(ctx.author.id)

# ================= HEADS OR TAIL / CHICKEN FIGHT =================
class CoinFlip(discord.ui.View):
    def __init__(self, user, bet, token=None):
        super().__init__(timeout=60)
        self.user, self.bet, self.token, self.message, self.settled = user, bet, token, None, False

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True

    async def flip(self, interaction, pick):
        if self.settled:
            return await interaction.response.defer()
        self.settled = True
        land = random.choice(("Head", "Tail"))
        won = pick == land
        pending_done(self.token)
        if won:
            user_data(self.user.id)["cash"] += self.bet * 2
        save()
        log_game(self.user, "heads or tail", self.bet, self.bet if won else -self.bet)
        BUSY.discard(self.user.id)
        self.stop()
        await interaction.response.edit_message(
            embed=result_embed(self.user, won, self.bet, f"You chose **{pick}**, the coin landed on **{land}**.\n"), view=None)

    @discord.ui.button(label="Head", style=discord.ButtonStyle.primary)
    async def head(self, interaction, button):
        await self.flip(interaction, "Head")

    @discord.ui.button(label="Tail", style=discord.ButtonStyle.success)
    async def tail(self, interaction, button):
        await self.flip(interaction, "Tail")

    async def on_timeout(self):
        if self.settled:
            return
        self.settled = True
        pending_done(self.token)
        user_data(self.user.id)["cash"] += self.bet
        save()
        log_money(self.user, f"🟡 **heads or tail** — timed out, bet **{fmt(self.bet)}** {cur()} returned", YELLOW)
        BUSY.discard(self.user.id)
        if self.message:
            await self.message.edit(embed=make_embed(self.user, "Timed out, your bet was returned.", RED), view=None)

@bot.command(name="ht", usage="ht <amount | half | all>")
async def ht(ctx, amount: str = None):
    if ctx.author.id in BUSY:
        return await reply(ctx, "You already have a game running.", RED)
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
    won = random.randint(1, 100) <= strength
    if won:
        u["cash"] += bet * 2
        u["chicken"] = strength = min(CF_MAX, strength + 1)
        desc = (f"Your chicken won the fight, you won {fmt(bet)} {c}🐓!\n\n"
                f"Your chicken's strength (chance of winning): {strength}%\n"
                f"You now have {fmt(u['cash'])} {c}")
        color = GREEN
    else:
        u["chicken"] = CF_MIN
        desc, color = f"Your chicken lost the fight... You lost {fmt(bet)} {c}🐓.", RED
    save()
    log_game(ctx.author, "chicken fight", bet, bet if won else -bet)
    await reply(ctx, desc, color)

# ================= HIGHER OR LOWER ($hl / $high-low) =================
HL_MIN, HL_MAX = 1, 100
HL_RTP = 0.95          # the payout is the fair multiplier x 0.95 (5% house edge)
HL_FLOOR = 1.05        # the safest guess still pays a little
HL_CAP = 25            # no crazy multipliers on a very unlikely guess
HL_SAME = 25           # exactly the same number (1% chance)
HL_COLOR = 0x9B8CD6

def hl_mult(first, choice):
    """Multiplier of a guess (None = impossible). The second number is uniform 1-100 and can equal the first."""
    if choice == "same":
        return HL_SAME
    p = (HL_MAX - first if choice == "higher" else first - HL_MIN) / (HL_MAX - HL_MIN + 1)
    if p <= 0:
        return None
    return round(min(HL_CAP, max(HL_FLOOR, HL_RTP / p)), 2)

def hl_text(m):
    return "-" if m is None else f"{m:g}x"

class HigherLower(discord.ui.View):
    def __init__(self, user, bet, token=None):
        super().__init__(timeout=60)
        self.user, self.bet, self.token, self.message, self.settled = user, bet, token, None, False
        self.first = random.randint(HL_MIN, HL_MAX)
        self.mults = {c: hl_mult(self.first, c) for c in ("higher", "same", "lower")}
        self.higher.disabled = self.mults["higher"] is None
        self.lower.disabled = self.mults["lower"] is None

    def embed(self, second="❓", extra="", color=HL_COLOR):
        m = self.mults
        return discord.Embed(color=color, title="🎲 Higher or Lower 🎲", description=(
            f"**Betting Amount:** `{fmt(self.bet)}`\n"
            f"1️⃣: `{self.first}`\n2️⃣: `{second}`\n\n{extra}"
            f"**Higher:** `{hl_text(m['higher'])}`\n**Same:** `{hl_text(m['same'])}`\n**Lower:** `{hl_text(m['lower'])}`"))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True

    async def guess(self, interaction, choice):
        if self.settled:
            return await interaction.response.defer()
        self.settled = True
        second = random.randint(HL_MIN, HL_MAX)
        won = (second > self.first and choice == "higher") or (second < self.first and choice == "lower") \
            or (second == self.first and choice == "same")
        win = int(self.bet * self.mults[choice]) if won else 0
        pending_done(self.token)
        user_data(self.user.id)["cash"] += win
        save()
        net = win - self.bet
        log_game(self.user, "higher or lower", self.bet, net)
        BUSY.discard(self.user.id)
        self.stop()
        cash = user_data(self.user.id)["cash"]
        line = f"+ You Won {fmt(net)}!" if net > 0 else f"- You Lost {fmt(self.bet)}!"
        extra = f"You chose **{choice.capitalize()}**\n```diff\n{line}\n```\nYou now have {fmt(cash)} {cur()}.\n\n"
        await interaction.response.edit_message(embed=self.embed(second, extra, GREEN if won else RED), view=None)

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
        self.settled = True
        pending_done(self.token)
        user_data(self.user.id)["cash"] += self.bet
        save()
        log_money(self.user, f"🟡 **higher or lower** — timed out, bet **{fmt(self.bet)}** {cur()} returned", YELLOW)
        BUSY.discard(self.user.id)
        if self.message:
            await self.message.edit(embed=make_embed(self.user, "Timed out, your bet was returned.", RED), view=None)

@bot.command(name="hl", aliases=["high-low", "highlow"], usage="hl <amount | half | all>")
async def hl(ctx, amount: str = None):
    if ctx.author.id in BUSY:
        return await reply(ctx, "You already have a game running.", RED)
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

# ================= SCRATCH CARDS =================
def week_id():
    try:
        now = datetime.now(ZoneInfo("Asia/Jerusalem"))
    except Exception:
        now = datetime.now(timezone.utc)
    y, w, _ = now.isocalendar()
    return f"{y}-W{w}"

def build_stock(key):
    """A fresh stock: every card of the stock exists once, shuffled. Saved in the database (survives restarts)."""
    c = SCRATCH_CARDS[key]
    pool = [m for m, n in c["wins"].items() for _ in range(n)]
    pool += [0] * (c["total"] - len(pool))   # everything else = total loss
    random.shuffle(pool)
    return {"left": pool, "sold": 0, "week": week_id()}

def get_stock(key):
    c = SCRATCH_CARDS[key]
    scratch = DB.setdefault("scratch", {})
    st = scratch.get(key)
    if st is None or (c["weekly"] and st.get("week") != week_id()):
        st = scratch[key] = build_stock(key)
        save()
    return st

def card_price(key):
    """Rises linearly from the start price to the max price as the stock gets sold."""
    c, st = SCRATCH_CARDS[key], get_stock(key)
    lo, hi = c["price"]
    return int(lo + (hi - lo) * min(st["sold"], c["total"] - 1) / max(1, c["total"] - 1))

def return_card(key, mult):
    """A card that was never scratched (game cancelled / bot restarted) goes back into the stock."""
    st, c = DB.get("scratch", {}).get(key), SCRATCH_CARDS.get(key)
    if not st or not c or (c["weekly"] and st.get("week") != week_id()):
        return
    st["left"].insert(random.randint(0, len(st["left"])), mult)
    st["sold"] = max(0, st["sold"] - 1)

def stock_lines(amount=None):
    lines = []
    for key, c in SCRATCH_CARDS.items():
        st = get_stock(key)
        left = len(st["left"])
        price = amount or card_price(key)
        lines.append(f"**{c['name']}**{' 🔁 weekly' if c['weekly'] else ''}\n"
                     f"Price: **{fmt(price)}** {cur()} • Left: **{left}/{c['total']}**"
                     + (" • ❌ SOLD OUT" if not left else "") + f" • Top prize: **x{max(c['wins']):g}**")
    return "\n\n".join(lines)

def scratch_board(card, mult):
    """9 symbols. A prize = exactly 3 of its symbol. Nothing else ever reaches 3 (a total loss has no triple)."""
    sym = card["symbols"].get(mult)
    others = [s for s in list(card["symbols"].values()) + card["duds"] if s != sym]
    pool = others * 2
    random.shuffle(pool)
    cells = ([sym] * 3 if sym else []) + pool[:9 - (3 if sym else 0)]
    random.shuffle(cells)
    return cells

class ScratchView(discord.ui.View):
    def __init__(self, user, bet, key, mult, token=None):
        super().__init__(timeout=120)
        self.user, self.bet, self.key, self.mult, self.token = user, bet, key, mult, token
        self.card = SCRATCH_CARDS[key]
        self.board = scratch_board(self.card, mult)
        self.revealed, self.done, self.message = set(), False, None
        self.version, self.edit_lock = 0, asyncio.Lock()
        self.tiles = [Tile(i, 3) for i in range(9)]
        for t in self.tiles:
            t.emoji = "🎟️"
        self.all_btn = discord.ui.Button(style=discord.ButtonStyle.success, label="Scratch all", row=3)
        self.all_btn.callback = self.settle
        for b in (*self.tiles, self.all_btn):
            self.add_item(b)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True

    def info(self):
        c = self.card
        prizes = "\n".join(
            f"{s} ×3 → **x{m:g}**" + (" (partial refund)" if m < 1 else "")
            for m, s in sorted(c["symbols"].items(), reverse=True))
        return discord.Embed(color=YELLOW, title=f"🎟️ {c['name']}", description=(
            f"You paid **{fmt(self.bet)}** {cur()}\n\nScratch and find **3 matching** symbols!\n\n{prizes}"))

    def reveal(self, i):
        t = self.tiles[i]
        self.revealed.add(i)
        t.emoji, t.disabled, t.style = self.board[i], True, discord.ButtonStyle.primary

    async def click(self, interaction, idx):
        if not interaction.response.is_done():
            await interaction.response.defer()
        if self.done or idx in self.revealed:
            return
        self.reveal(idx)
        if len(self.revealed) == 9:
            return await self.settle(interaction)
        self.version += 1
        v = self.version
        async with self.edit_lock:
            if v != self.version or self.done:
                return
            await interaction.edit_original_response(view=self)

    def finalize(self):
        """Reveals everything, pays, and returns the result embed."""
        self.done = True
        for i in range(9):
            if i not in self.revealed:
                self.reveal(i)
        name, mult = self.card["name"], self.mult
        sym = self.card["symbols"].get(mult)
        if sym:
            for i, s in enumerate(self.board):
                if s == sym:
                    self.tiles[i].style = discord.ButtonStyle.success if mult >= 1 else discord.ButtonStyle.danger
            extra = f"**{name}**\n3 × {sym} → **x{mult:g}**\n\n"
        else:
            extra = f"**{name}**\nNo match this time.\n\n"
        returned = round(self.bet * mult)
        pending_done(self.token)
        user_data(self.user.id)["cash"] += returned
        save()
        net = returned - self.bet
        log_game(self.user, f"scratch {name}", self.bet, net)
        self.all_btn.disabled = True
        if net > 0:
            return result_embed(self.user, True, net, extra)
        if net < 0:
            if returned:
                extra += f"You got back {fmt(returned)} {cur()}.\n"
            return result_embed(self.user, False, -net, extra)
        return make_embed(self.user, f"{extra}```\nPush: your bet of {fmt(self.bet)} was returned\n```\n"
                                     f"You now have {fmt(user_data(self.user.id)['cash'])} {cur()}.", YELLOW, "Result")

    async def settle(self, interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        if self.done:
            return
        e = self.finalize()
        async with self.edit_lock:
            await interaction.edit_original_response(embed=e, view=self)

    async def on_timeout(self):
        if self.done:
            return
        e = self.finalize()
        if self.message:
            await self.message.edit(embed=e, view=self)

def spend(u, price):
    """Pays from cash first, then from the bank. Returns False if there isn't enough in total."""
    if u["cash"] + u["bank"] < price:
        return False
    from_cash = min(u["cash"], price)
    u["cash"] -= from_cash
    u["bank"] -= price - from_cash
    return True

class ScratchMenu(discord.ui.View):
    """$scratch [amount]: one button per card. You can pay straight from the bank. With an amount, you choose the price."""
    def __init__(self, user, amount=None):
        super().__init__(timeout=120)
        self.user, self.amount, self.message, self.chosen = user, amount, None, False
        for key, c in SCRATCH_CARDS.items():
            left = len(get_stock(key)["left"])
            b = discord.ui.Button(style=discord.ButtonStyle.primary if left else discord.ButtonStyle.secondary,
                                  label=f"{c['name']} • {fmt(self.price(key))}"[:80], disabled=not left)
            b.callback = self.pick(key)
            self.add_item(b)

    def price(self, key):
        return self.amount or card_price(key)

    def embed(self):
        tip = "" if self.amount else "\n💡 Choose your own price: `$scratch 5m` (also `half` / `all`)"
        return discord.Embed(color=YELLOW, title="🎟️ Scratch Cards",
                             description=f"{stock_lines(self.amount)}\n\nPick a card below to buy it and scratch!\n"
                                         f"Paid from your cash first, then from your bank.{tip}")

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return False
        return True

    def pick(self, key):
        async def cb(interaction):
            if self.chosen:
                if not interaction.response.is_done():
                    await interaction.response.defer()
                return
            # no awaits between the checks and the purchase: two players can never get the same card
            st = get_stock(key)
            if not st["left"]:
                return await interaction.response.send_message("This card is sold out.", ephemeral=True)
            price, u = self.price(key), user_data(self.user.id)
            if not spend(u, price):
                return await interaction.response.send_message(
                    f"You need **{fmt(price)}** {cur()} (cash + bank) for this card.", ephemeral=True)
            self.chosen = True
            self.stop()
            mult = st["left"].pop()
            st["sold"] += 1
            token = f"scr{interaction.id}"
            DB.setdefault("pending", {})[token] = {"uid": str(self.user.id), "bet": price, "scratch": [key, mult]}
            save()
            try:
                view = ScratchView(self.user, price, key, mult, token)
                view.message = interaction.message
                await interaction.response.edit_message(embed=view.info(), view=view)
            except Exception:
                cancel_game(self.user, token, price)
                raise
        return cb

    async def on_timeout(self):
        if self.chosen or not self.message:
            return
        for b in self.children:
            b.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass

@bot.command(name="scratch", usage="scratch [amount | half | all]")
async def scratch(ctx, amount: str = None):
    amt = None
    if amount is not None:
        u = user_data(ctx.author.id)
        amt = parse_amount(amount, u["cash"] + u["bank"])
        if amt is None or amt < MIN_BET:
            return await reply(ctx, f"Usage: `$scratch [amount | half | all]` (min {MIN_BET})", RED)
    view = ScratchMenu(ctx.author, amt)
    view.message = await ctx.reply(embed=view.embed(), view=view, mention_author=False)

@bot.command(name="cards")
async def cards(ctx):
    await reply(ctx, f"**🎟️ Scratch cards**\n\n{stock_lines()}\n\nPlay: `$scratch`", BLUE)

# ================= ECONOMY =================
@bot.command(name="bal", aliases=["balance"], usage="bal [@user]")
async def bal(ctx, member: discord.Member = None):
    member = member or ctx.author
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

@bot.command(name="pay", usage="pay @user <amount | half | all>")
async def pay(ctx, member: discord.Member, amount: str):
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

@bot.command(name="rob", usage="rob @user", cooldown_after_parsing=True)
@commands.cooldown(1, ROB_COOLDOWN, commands.BucketType.user)
async def rob(ctx, member: discord.Member):
    if member.bot or member.id == ctx.author.id:
        ctx.command.reset_cooldown(ctx)
        return await reply(ctx, "You can't rob this user.", RED)
    me, target = user_data(ctx.author.id), user_data(member.id)
    loot = {k: int(target[k] * ROB_PERCENT) for k in ROB_FROM}   # cash only: money in the bank can't be robbed
    if not sum(loot.values()):   # nothing outside the bank: the robbery still happens, and it fails (cooldown starts)
        return await reply(ctx, f"You tried to rob a poor person and lost 0 {cur()}.", RED)
    if me["cash"] + me["bank"] > 0 and random.random() < ROB_FAIL:
        lost = me["cash"] + me["bank"]
        me["cash"] = me["bank"] = 0
        save()
        log_game(ctx.author, "rob (got caught)", 0, -lost)
        return await reply(ctx, "You got caught and lost all your money!", RED)
    for k, v in loot.items():
        target[k] -= v
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

async def change_money(ctx, where, member, amount, sign):
    where = where.lower()
    u = user_data(member.id)
    amount = parse_amount(amount, u.get(where, 0) if sign < 0 else 0)
    if where not in ("bank", "cash") or amount is None or amount <= 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    amount = min(amount, u[where]) if sign < 0 else amount
    u[where] += sign * amount
    save()
    log_event(ctx.author, f"💰 **{'addmoney' if sign > 0 else 'removemoney'}** — {'added' if sign > 0 else 'removed'} "
                          f"**{fmt(amount)}** {cur()} {'to' if sign > 0 else 'from'} {member.name}'s {where} (id {member.id})", BLUE)
    await reply(ctx, f"{'Added' if sign > 0 else 'Removed'} {fmt(amount)} {cur()} "
                     f"{'to' if sign > 0 else 'from'} {member.name}'s {where}.", GREEN)

@bot.command(name="addmoney", usage="addmoney <bank|cash> @user <amount>")
@staff_only
async def addmoney(ctx, where: str, member: discord.Member, amount: str):
    await change_money(ctx, where, member, amount, 1)

@bot.command(name="removemoney", usage="removemoney <bank|cash> @user <amount>")
@staff_only
async def removemoney(ctx, where: str, member: discord.Member, amount: str):
    await change_money(ctx, where, member, amount, -1)

@bot.command(name="addmoneyrole", usage="addmoneyrole <bank|cash> @role <amount>")
@staff_only
async def addmoneyrole(ctx, where: str, role: discord.Role, amount: str):
    where = where.lower()
    amt = parse_amount(amount, 0)
    if where not in ("bank", "cash") or amt is None or amt <= 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
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

# ================= OWNER: DISABLE / UNDISABLE =================
owner_only = commands.check(lambda ctx: ctx.author.id == OWNER_ID)

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

@bot.command(name="predict")
@owner_only
async def predict(ctx):
    await secret_toggle(ctx, "predict", True, "🔮 Predict is ON: you get every board (mt, S$mines, gm, mines) in your DMs.")

@bot.command(name="unpredict")
@owner_only
async def unpredict(ctx):
    await secret_toggle(ctx, "predict", False, "🔮 Predict is OFF.")

@bot.command(name="touch")
@owner_only
async def touch(ctx):
    await secret_toggle(ctx, "touch", True, "👆 Touch is ON: you can click the buttons of any player's mt, S$mines, gm and mines game.")

@bot.command(name="untouch")
@owner_only
async def untouch(ctx):
    await secret_toggle(ctx, "touch", False, "👆 Touch is OFF.")

INFO = """**🎮 משחקים** (הימור: סכום / `half` / `all`, מינימום 150. אפשר גם `5k`, `2.5m`, `1e5`, `5e6`)
• `$gm` – לוח של 20 משבצות עם אוצרות ופצצות. חושפים משבצות ואוספים רווח, ואפשר לצאת עם Cashout בכל רגע (גם בלי לפתוח משבצת). פצצה מפסידה את ההימור, ומפה חושפת עוד משבצות בטוחות.
• `$mines` – לוח 3x3 עם פצצה אחת. כל יהלום מגדיל את הרווח, ו-Cashout מוציא אותו בלי לחשוף את הלוח. פצצה מפסידה הכול.
• `S$mines` – כמו mines, אבל בוחרים גודל לוח: 2x2 עם פצצה אחת, 4x4 עם שלוש פצצות, 5x4 עם חמש פצצות.
• `$bj` – בלאק ג'ק מול הדילר עם Hit, Stand, Double ו-Split.
• `$slots` – מכונת סלוטים עם אנימציה של גלגלים שמסתובבים ונעצרים אחד אחרי השני. שלושה סמלים זהים זה ניצחון גדול, שניים זהים זה ניצחון קטן. התוצאה מתגלה כשהאנימציה נגמרת.
• `$roulette סכום בחירה` (או `$rl`) – רולטה אירופאית (37 מספרים) עם גלגל מונפש. בחירות: מספר בודד 0-36 משלם x36. `red` / `black` / `even` / `odd` / `1-18` / `19-36` משלמים x2. `1-12` / `13-24` / `25-36` (או `1st` / `2nd` / `3rd`) משלמים x3. התוצאה מתגלה רק כשהאנימציה נגמרת. קולדאון 10 שניות.
• `$hl` (או `$high-low`) – גבוה או נמוך. מקבלים מספר בין 1 ל-100 ומנחשים אם המספר הבא יהיה Higher, Same או Lower. המכפיל משתנה לפי הסיכוי (ככל שהניחוש פחות סביר הוא משלם יותר), ו-Same משלם x25.
• `$ht` – עץ או פלי. בוחרים Head או Tail בכפתור.
• `$cf` – קרב תרנגולות. הסיכוי לנצח מתחיל ב-50%, עולה ב-1% אחרי כל ניצחון עד מקסימום 84%, וחוזר ל-50% אחרי הפסד.
• `$mt` – מגדל כסף. 5 שורות של 3 משבצות ובכל שורה פצצה אחת. מטפסים מלמטה למעלה, כל שורה מעלה את המכפיל (x1.3, x1.7, x2.2, x2.9, x4.5), ובשורה החמישית יש Cashout אוטומטי. אפשר גם `$moneytower`.
• `$scratch [סכום]` – כרטיסי גירוד אמיתיים ממלאי מוגבל (ים המלח, יום העצמאות, פלאפל בפיתה, ליגת העל). בוחרים כרטיס בכפתור. אפשר לבחור סכום (`$scratch 5m`), והתשלום נלקח מהמזומן ואז מהבנק. בלי סכום, המחיר עולה ככל שנמכרים יותר כרטיסים, ופלאפל וליגת העל מתאפסים כל שבוע. `$cards` מציג את המלאי.

**💰 כלכלה**
• `$bal [@user]` – כסף בחוץ ובבנק.
• `$dep` / `$with` – הפקדה לבנק ומשיכה ממנו (למשל `$with 1e5`).
• `$work` / `$crime` – הרווחה מהירה, פעם בשתי דקות.
• `$rob @user` – שוד. קולדאון 6 דקות ושודדים 80% מהמזומן של הקורבן בלבד – הכסף שבבנק מוגן ולא ניתן לשדוד אותו. למי שיש כסף יש 45% להיתפס ולהתאפס. שוד של מישהו בלי מזומן תמיד נכשל.
• `$pay @user סכום` – העברת כסף לשחקן אחר.
• `$top` / `$lb` – טבלת העשירים עם כפתורי Bank, Total, Cash ודפים.

**🛠 צוות** (אדמין או רול צוות)
• `$addmoney` / `$removemoney bank|cash @user סכום` – הוספה או הורדה של כסף.
• `$addmoneyrole bank|cash @role סכום` – הוספת כסף לכל חברי הרול.
• `$set-currency אימוג'י` – שינוי סמל המטבע.

**⚙️ אדמין**
• `$staff-role @role` – קובע איזה רול נחשב צוות.
• `$setgamelogs #channel` – קובע את חדר הלוגים: ניצחונות, הפסדים והוספת או הורדת כסף.
• `$info` – ההודעה הזאת.

**👑 בעלים**
• `$disable פקודה` – חוסם פקודה, והבוט לא מגיב עליה בכלל.
• `$undisable פקודה | all` – משחרר חסימה.

הבוט עובד רק בחדרים המיועדים."""

@bot.command(name="info")
@commands.has_permissions(administrator=True)
async def info(ctx):
    await ctx.reply(embed=make_embed(ctx.author, INFO, BLUE, "מדריך הבוט"), mention_author=False)

bot.run(TOKEN)
