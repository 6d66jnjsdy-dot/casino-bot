import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web

# ================= CONFIG =================
try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Asia/Jerusalem")      # "00:00" resets happen at midnight Israel time
except Exception:
    LOCAL_TZ = datetime.timezone(datetime.timedelta(hours=3))

def today_key():
    return datetime.datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")

TOKEN = (os.environ.get("DISCORD_TOKEN") or os.environ.get("TOKEN") or "").strip().strip('"').strip("'")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(HERE, "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "economy.json")
ALLOWED_CHANNELS = {
    1554650314546618480,
    1541567870591443026,
    1554652227963060364,
    1554657850067001405,
    1554651913994117170,
    1554650281663537172,
    1554844436632969347,
    1554845002637508738,
    1554651968478122135,
    1555486192559202334,
}
OWNER_ID = 1537816435370229820
OWNER_IDS = {OWNER_ID, 1292041341618094173}   # everyone here has full owner permissions
BACKUP_CHANNEL_ID = int(os.environ.get("BACKUP_CHANNEL_ID") or 0)
MIN_BET = 150
EARN_MIN, EARN_MAX = 6500, 16000
DEALER_STANDS_ON = 13
EMPTY = "\u200e"
GREEN, RED, BLUE, YELLOW = 0x77B255, 0xC0392B, 0x3B82F6, 0xF1C40F
BUSY_MSG = "You already have an active game! Finish it first."

EMOJI = {"bomb": "💣", "map": "🗺️", "diamond": "💎", "coin": "🪙", "stone": "🪨", "bag": "💰", "urn": "🏺"}
MULT = {"diamond": 3, "urn": 15, "stone": 1.1, "coin": 2, "bag": 4.5, "map": 1}
MAP_FINDS = ("diamond", "stone", "coin")   # the map can only point at these (never the urn or the bag)
URN_CHANCE = (3, 10)
MINES_MULT = [1.1, 1.2, 1.4, 1.9, 2.3, 4.3, 6.1, 8.1]
# S$mines: (columns, rows, mines, multiplier of every click). There is one multiplier for EVERY safe tile
# (2x2 = 3, 4x4 = 14, 5x4 = 17), so the profit grows on every single click, all the way to the last diamond.
SMINES = {
    "2x2": (2, 2, 1, [1.3, 2, 3.9]),
    "4x4": (4, 4, 2, [1.2, 1.4, 1.6, 1.8, 2, 2.4, 2.76, 3.2, 3.4, 3.7, 4.1, 6.4, 8.6, 10.5]),
    "5x4": (5, 4, 3, [1.2, 1.5, 1.8, 2, 2.3, 2.4, 2.6, 3, 3.2, 3.4, 3.9, 4, 4.2, 5.4, 9.85, 12, 15]),
}
MT_MULT = [1.3, 1.7, 2.2, 2.9, 4.5]
MT_SAFE = "💲"

MULTI_MAX = 5
MULTI_GAMES = ("gm", "mines", "s$mines", "mt", "bj", "slots", "roulette", "ht", "cf", "hl", "scratch")

CF_MIN, CF_MAX = 50, 84
CF_HIDDEN = 1
ROB_FROM, ROB_PERCENT, ROB_COOLDOWN = ("cash",), 0.8, 360
SLOTS = ["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"]
SLOT_PAY = dict(zip(SLOTS, [3, 4, 5, 8, 15, 30]))
SLOT_BUFF = 1.065 * 1.15 * 1.15 * 0.85   # multipliers lowered by 15%
SLOT_WIN_CUT = 0.10                      # 10% of the winning spins are turned into losses (win chance -10%)
SLOT_WAIT = 5
LOAD_BUFFER = 1.5
SLOTS_BOOST = 0.075
BJ_WIN_NERF = 0.09

# ================= DATABASE =================
def load():
    try:
        with open(DB_FILE) as f:
            return json.load(f)
    except Exception:
        return {"currency": "💸", "users": {}}

DB = load()
dirty = disk_dirty = synced = False
backup_msg = loaded = None
backup_lock = asyncio.Lock()

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
LUCK_MAX = 10

def parse_duration(text):
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

def multi_extra(game, net):
    m = DB.get("multi", {}).get(game)
    until = DB.get("multi_until", {}).get(game)
    if m and until and time.time() >= until:
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
            return_card(*rec["scratch"])
    if pend:
        print(f"Refunded {len(pend)} unfinished game(s)")
    DB["pending"] = {}
    save()

# ---------- game logs (professional embeds) ----------
_log_tasks = set()
LOG_FOOTER = "Amram Casino  •  Activity Log"

def bg(coro):
    t = asyncio.create_task(coro)
    _log_tasks.add(t)
    t.add_done_callback(_log_tasks.discard)

GAME_NAMES = {"gm": "Gold Mines", "mines": "Mines", "money tower": "Money Tower", "blackjack": "Blackjack",
              "slots": "Slots", "roulette": "Roulette", "heads or tail": "Heads or Tail",
              "chicken fight": "Chicken Fight", "higher or lower": "Higher or Lower"}
GAME_ICONS = (("s$mines", "💣"), ("mines", "💣"), ("gm", "⛏️"), ("money tower", "🗼"), ("blackjack", "🃏"),
              ("slots", "🎰"), ("roulette", "🎡"), ("heads", "🪙"), ("chicken", "🐓"), ("higher", "🎲"),
              ("scratch", "🎟️"), ("rob", "🦹"))
LOG_TITLES = {
    "DEP": "🏦 Deposit", "WITH": "🏧 Withdrawal", "WORK": "🔨 Work", "CRIME": "🕵️ Crime", "PAY": "🤝 Transfer",
    "SHOP": "🛒 Shop Purchase", "ADD MONEY": "➕ Money Added", "REMOVE MONEY": "➖ Money Removed",
    "RESET MONEY": "♻️ Money Reset", "ADD MONEY TO ROLE": "👥 Money Added To Role", "LOG CHANNEL SET": "📋 Log Channel Set",
}

def pretty(text):
    text = text.strip()
    return text.title() if text.isupper() else text[:1].upper() + text[1:]

def game_icon(game):
    g = game.lower()
    for key, icon in GAME_ICONS:
        if g.startswith(key):
            return icon
    return "🎮"

def log_head(title):
    parts = [p.strip() for p in title.split("|")]
    base = LOG_TITLES.get(parts[0].upper())
    if base is None:
        low = parts[0].lower()
        base = f"{game_icon(low)} {GAME_NAMES.get(low) or pretty(parts[0])}"
    return base + "".join(f"  •  {pretty(p)}" for p in parts[1:])

async def send_log(user, head, desc, color, fields):
    try:
        cid = DB.get("log_channel")
        ch = bot.get_channel(cid) or await bot.fetch_channel(cid)
        e = discord.Embed(title=head, description=desc or None, color=color, timestamp=discord.utils.utcnow())
        e.set_author(name=user.name, icon_url=user.display_avatar.url)
        e.set_thumbnail(url=user.display_avatar.url)
        for name, value in fields or []:
            e.add_field(name=name, value=value, inline=True)
        e.set_footer(text=f"{LOG_FOOTER}  •  ID {user.id}")
        await ch.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
    except Exception as ex:
        print("Log failed:", repr(ex))

def log_event(user, title, desc, color, fields=None):
    if DB.get("log_channel"):
        bg(send_log(user, log_head(title), desc, color, fields))

def log_game(user, game, bet, net, detail=None):
    if not DB.get("log_channel"):
        return
    u, c = user_data(user.id), cur()
    if net > 0:
        tag, color, dot, amt = "WIN", GREEN, "🟢", f"+{fmt(net)}"
    elif net < 0:
        tag, color, dot, amt = "LOSS", RED, "🔴", f"-{fmt(-net)}"
    else:
        tag, color, dot, amt = "PUSH", YELLOW, "🟡", "±0"
    low = game.lower()
    desc = f"{dot} **{tag}**  ·  `{amt}` {c}" + (f"\n{detail}" if detail else "")
    fields = []
    if bet:
        fields.append(("💵 Bet", f"`{fmt(bet)}` {c}"))
    fields.append(("📊 Net", f"`{amt}` {c}"))
    if low.startswith("scratch"):
        fields.append(("🏦 Bank", f"`{fmt(u['bank'])}` {c}"))
    else:
        fields.append(("💰 Cash", f"`{fmt(u['cash'])}` {c}"))
    head = f"{game_icon(game)} {GAME_NAMES.get(low) or pretty(game)}"
    bg(send_log(user, head, desc, color, fields))

def log_money(user, title, desc, color=BLUE):
    u, c = user_data(user.id), cur()
    log_event(user, title, desc, color, [("💵 Cash", f"`{fmt(u['cash'])}` {c}"), ("🏦 Bank", f"`{fmt(u['bank'])}` {c}"),
                                         ("💎 Total", f"`{fmt(u['cash'] + u['bank'])}` {c}")])

# ---------- owner tools ($predict / $touch) ----------
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
    bg(dm_owner(discord.Embed(color=BLUE, title=f"🔮 {view.game_name}", timestamp=discord.utils.utcnow(), description=(
        f"**{view.user.name}** ({view.user.id}) — bet **{fmt(view.bet)}** {cur()}\n\n{board_text(view)}{note}"))))

def may_play(interaction, game_owner_id):
    return interaction.user.id == game_owner_id or (interaction.user.id in OWNER_IDS and bool(DB.get("touch")))

# ================= BOT =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=("$", "S$", "s$"), intents=intents, help_command=None, case_insensitive=True)

USER_LOCKS = {}     # (user id, channel id) -> lock: a user's commands run in order, but only inside the same channel
USER_PENDING = {}   # (user id, channel id) -> commands waiting or running
MAX_QUEUE = 3       # spam beyond this many waiting commands in one channel is ignored, so a queue can never build up
CMD_PREFIXES = ("$", "s$")

@bot.event
async def on_message(message):
    if message.author.bot or not message.content.lower().startswith(CMD_PREFIXES):
        return
    key = (message.author.id, message.channel.id)
    if USER_PENDING.get(key, 0) >= MAX_QUEUE:
        return
    USER_PENDING[key] = USER_PENDING.get(key, 0) + 1
    try:
        async with USER_LOCKS.setdefault(key, asyncio.Lock()):
            try:
                await bot.process_commands(message)
            except Exception as ex:
                print("Command crashed (isolated to this channel):", repr(ex))
    finally:
        USER_PENDING[key] -= 1
        if USER_PENDING[key] <= 0:
            USER_PENDING.pop(key, None)
            USER_LOCKS.pop(key, None)

def cmd_key(ctx):
    return "s$mines" if ctx.command.name == "mines" and ctx.prefix.lower() == "s$" else ctx.command.name

@bot.check
async def only_allowed_channels(ctx):
    await loaded.wait()
    if ctx.channel.id not in ALLOWED_CHANNELS:
        return False
    if cmd_key(ctx) in DB.get("disabled", []) and ctx.author.id not in OWNER_IDS:
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
    sc_daily_loop.start()
    bot.add_view(ShopView())
    try:
        await bot.load_extension("extras")
    except Exception as ex:
        print("extras.py failed to load:", repr(ex))
    try:
        asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(graceful_shutdown()))
    except (NotImplementedError, RuntimeError):
        pass

bot.setup_hook = setup_hook

@bot.event
async def on_ready():
    if not loaded.is_set():
        await restore_backup()
        refund_pending()
        loaded.set()
        bg(refresh_banner())
        bg(setup_card_emojis())
        bg(warm_animations())
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
        import traceback
        print("Error:", repr(err))
        traceback.print_exception(type(err), err, err.__traceback__)

# ================= BOARDS =================
def shuffled(**parts):
    board = [k for kind, n in parts.items() for k in [kind] * n]
    random.shuffle(board)
    return board

def gm_board():
    tiles = ["map"] + ["bomb"] * 12 + ["stone"] * 2 + ["coin"] * 2 + ["bag"] + ["diamond"] * 2
    if random.randint(1, URN_CHANCE[1]) <= URN_CHANCE[0]:
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
        self.dirty = self.flushing = False
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
        if all(k == "bomb" or i in self.revealed for i, k in enumerate(self.board)):
            return          # every safe tile is already found: the leftover tiles stay the same colour and a click on them does nothing
        self.luck_fix(idx)
        kind = self.board[idx]
        self.reveal(idx)
        if kind == "bomb":
            return await self.finish(interaction, True)
        self.after(kind)
        await self.push(interaction)

    async def edit_ui(self, interaction, **kw):
        # fast clicking can make Discord reject an edit: retry (alternating interaction / message) until it goes through
        for i in range(8):
            try:
                if i % 2 == 0 or not self.message:
                    return await interaction.edit_original_response(**kw)
                return await self.message.edit(**kw)
            except discord.HTTPException:
                await asyncio.sleep(0.3 * (i + 1))

    async def push(self, interaction):
        # clicks that arrive while an edit is running only mark the board as dirty, the loop then draws the LATEST board
        self.dirty = True
        if self.flushing:
            return
        self.flushing = True
        try:
            while self.dirty and not self.done:
                self.dirty = False
                async with self.edit_lock:
                    if self.done:
                        break
                    await self.edit_ui(interaction, content=self.header, view=self)
        finally:
            self.flushing = False

    def payout(self):
        base = int(self.profit)
        self.profit = base + multi_extra(self.multi_key, base)
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
            await self.edit_ui(interaction, **kw)

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

    def __init__(self, user, bet, token=None):
        self.marked = set()   # tiles the map pointed at (shown as ✅), waiting to be clicked
        super().__init__(user, bet, token)

    def make_board(self):
        return take(self.user.id, "gm")

    def earn(self, kind):
        self.profit += self.bet * (MULT[kind] - 1)

    def luck_pool(self, idx):
        return [i for i in super().luck_pool(idx) if i not in self.marked]

    async def click(self, interaction, idx):
        self.marked.discard(idx)
        await super().click(interaction, idx)

    def after(self, kind):
        if kind != "map":
            return
        pool = [i for i, k in enumerate(self.board) if k in MAP_FINDS and i not in self.revealed and i not in self.marked]
        for i in random.sample(pool, min(3, len(pool))):
            self.marked.add(i)
            self.tiles[i].emoji, self.tiles[i].style = "✅", discord.ButtonStyle.success

class Mines(BoardView):
    cols = 3
    reveal_on_cashout = False
    game_name = "mines"
    multi_key = "mines"

    def make_board(self):
        return take(self.user.id, "mines")

    def earn(self, kind):
        self.profit = self.bet * (MINES_MULT[len(self.revealed) - 1] - 1)

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
        # one multiplier per safe tile, exactly as written in SMINES (no reductions)
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
        if self.climbed >= 5:
            return await self.finish(interaction, False)
        await self.push(interaction)

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
        log_money(self.user, "S$MINES | TIMEOUT", f"Bet of {fmt(self.bet)} {cur()} was returned", YELLOW)
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
SUIT_EMOJI = {"♣": "♣️", "♠": "♠️", "♥": "♥️", "♦": "♦️"}

def card_value(rank):
    return 11 if rank == "A" else 10 if rank in "JQK" else int(rank)

def hand_value(cards):
    total, aces = sum(card_value(r) for r, _ in cards), sum(r == "A" for r, _ in cards)
    while total > 21 and aces:
        total, aces = total - 10, aces - 1
    return total

# ---------- real playing cards, drawn in code, uploaded once as bot emojis (never sent as images) ----------
SW, SH = 96, 134          # card size in pixels
_CK = 4                   # supersampling (drawn big, scaled down = smooth edges)
_CRED = (200, 24, 40, 255)
_CBLACK = (24, 24, 30, 255)
_CGOLD = (236, 184, 48, 255)
_CGOLD_D = (150, 105, 15, 255)
_CSKIN = (250, 218, 178, 255)
_CINK = (40, 30, 30, 255)
SUIT_COLOR = {"♣": _CBLACK, "♠": _CBLACK, "♥": _CRED, "♦": _CRED}
SUIT_LETTER = {"♣": "C", "♠": "S", "♥": "H", "♦": "D"}

def _ccircle(cx, cy, r, n=48):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]

def _cnorm(polys):
    pts = [p for poly in polys for p in poly]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    cx, cy, s = (x0 + x1) / 2, (y0 + y1) / 2, 2 / max(x1 - x0, y1 - y0)
    return [[((x - cx) * s, (y - cy) * s) for x, y in poly] for poly in polys]

def _cheart():
    pts = []
    for i in range(160):
        t = 2 * math.pi * i / 160
        pts.append((16 * math.sin(t) ** 3,
                    -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))))
    return pts

SUIT_POLYS = {
    "♥": _cnorm([_cheart()]),
    "♦": _cnorm([[(0, -1), (0.66, 0), (0, 1), (-0.66, 0)]]),
    "♠": _cnorm([[(x, -y) for x, y in _cheart()], [(-1.8, 5), (1.8, 5), (5.5, 16), (-5.5, 16)]]),
    "♣": _cnorm([_ccircle(0, -6, 5.6), _ccircle(-6.3, 3, 5.6), _ccircle(6.3, 3, 5.6), _ccircle(0, 0.5, 3.4),
                 [(-1.8, 2), (1.8, 2), (5.5, 14), (-5.5, 14)]]),
}

def draw_suit(d, suit, cx, cy, s, flip=False):
    color = SUIT_COLOR[suit]
    for poly in SUIT_POLYS[suit]:
        d.polygon([(cx + x * s, cy + (-y if flip else y) * s) for x, y in poly], fill=color)

_PT = 1 / 3
CARD_PIPS = {   # (column 0 / .5 / 1, row 0..1)
    "2": [(.5, 0), (.5, 1)],
    "3": [(.5, 0), (.5, .5), (.5, 1)],
    "4": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "5": [(0, 0), (1, 0), (.5, .5), (0, 1), (1, 1)],
    "6": [(0, 0), (1, 0), (0, .5), (1, .5), (0, 1), (1, 1)],
    "7": [(0, 0), (1, 0), (.5, .25), (0, .5), (1, .5), (0, 1), (1, 1)],
    "8": [(0, 0), (1, 0), (.5, .25), (0, .5), (1, .5), (.5, .75), (0, 1), (1, 1)],
    "9": [(0, 0), (1, 0), (0, _PT), (1, _PT), (.5, .5), (0, 2 * _PT), (1, 2 * _PT), (0, 1), (1, 1)],
    "10": [(0, 0), (1, 0), (.5, 1 / 6), (0, _PT), (1, _PT), (0, 2 * _PT), (1, 2 * _PT), (.5, 5 / 6), (0, 1), (1, 1)],
}

def _face_layer(rank, suit, W, H):
    """Court card: framed panel with a figure in the top half, mirrored (rotated 180) into the bottom half."""
    K = _CK
    col = SUIT_COLOR[suit]
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    px0, px1, py0, py1 = .25 * W, .75 * W, .10 * H, .90 * H
    d.rounded_rectangle([px0, py0, px1, py1], radius=4 * K, fill=(255, 247, 224, 255), outline=_CGOLD_D, width=2 * K)
    d.line([(px0, H / 2), (px1, H / 2)], fill=(225, 200, 150, 255), width=K)
    w = 2 * K
    d.polygon([(.27 * W, .5 * H), (.33 * W, .37 * H), (.67 * W, .37 * H), (.73 * W, .5 * H)], fill=col, outline=_CINK)
    d.polygon([(.42 * W, .37 * H), (.5 * W, .45 * H), (.58 * W, .37 * H)], fill=_CGOLD, outline=_CGOLD_D)
    for bx in (.36, .64):
        d.ellipse([bx * W - 2 * K, .455 * H - 2 * K, bx * W + 2 * K, .455 * H + 2 * K], fill=_CGOLD)
    hair = (120, 70, 25, 255) if rank != "K" else (170, 170, 175, 255)
    if rank == "Q":
        hair = (205, 150, 40, 255)
        d.ellipse([.34 * W, .22 * H, .66 * W, .42 * H], fill=hair, outline=_CINK, width=K)
    elif rank == "J":
        d.ellipse([.36 * W, .2 * H, .64 * W, .36 * H], fill=hair, outline=_CINK, width=K)
    d.ellipse([.405 * W, .225 * H, .595 * W, .375 * H], fill=_CSKIN, outline=_CINK, width=w // 2)
    for ex in (.46, .54):
        d.ellipse([ex * W - K, .29 * H - K, ex * W + K, .29 * H + K], fill=_CINK)
    d.arc([.46 * W, .3 * H, .54 * W, .35 * H], 20, 160, fill=(150, 50, 50, 255), width=K)
    if rank == "K":
        d.polygon([(.4 * W, .335 * H), (.43 * W, .375 * H), (.5 * W, .385 * H), (.57 * W, .375 * H), (.6 * W, .335 * H),
                   (.56 * W, .36 * H), (.5 * W, .37 * H), (.44 * W, .36 * H)], fill=hair, outline=_CINK)
        d.polygon([(.395 * W, .245 * H), (.38 * W, .15 * H), (.44 * W, .2 * H), (.5 * W, .13 * H), (.56 * W, .2 * H),
                   (.62 * W, .15 * H), (.605 * W, .245 * H)], fill=_CGOLD, outline=_CGOLD_D)
        for jx in (.4, .5, .6):
            d.ellipse([jx * W - 1.5 * K, .22 * H - 1.5 * K, jx * W + 1.5 * K, .22 * H + 1.5 * K], fill=_CRED)
    elif rank == "Q":
        d.polygon([(.41 * W, .245 * H), (.4 * W, .17 * H), (.455 * W, .21 * H), (.5 * W, .15 * H), (.545 * W, .21 * H),
                   (.6 * W, .17 * H), (.59 * W, .245 * H)], fill=_CGOLD, outline=_CGOLD_D)
        d.ellipse([.5 * W - 1.5 * K, .2 * H - 1.5 * K, .5 * W + 1.5 * K, .2 * H + 1.5 * K], fill=col)
    else:
        d.pieslice([.38 * W, .15 * H, .62 * W, .31 * H], 180, 360, fill=col, outline=_CINK)
        d.rectangle([.38 * W, .23 * H, .62 * W, .25 * H], fill=_CGOLD, outline=_CGOLD_D)
        d.polygon([(.6 * W, .2 * H), (.74 * W, .12 * H), (.68 * W, .24 * H)], fill=(235, 235, 240, 255), outline=_CINK)
    draw_suit(d, suit, .33 * W, .2 * H, .05 * H)
    return Image.alpha_composite(lay, lay.rotate(180))

@lru_cache(maxsize=None)
def get_card(card):
    r, s = card
    K = _CK
    W, H = SW * K, SH * K
    col = SUIT_COLOR[s]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=9 * K, fill=(255, 255, 255, 255), outline=(170, 170, 176, 255), width=K)
    d.rounded_rectangle([5 * K, 5 * K, W - 1 - 5 * K, H - 1 - 5 * K], radius=6 * K, outline=(235, 235, 238, 255), width=K)
    if r in ("J", "Q", "K"):
        im = Image.alpha_composite(im, _face_layer(r, s, W, H))
        d = ImageDraw.Draw(im)
    elif r == "A":
        draw_suit(d, s, W / 2, H / 2, .21 * H)
    else:
        for cx, cy in CARD_PIPS[r]:
            draw_suit(d, s, (.33 + .34 * cx) * W, (.2 + .6 * cy) * H, .075 * H, flip=cy > .5)
    idx = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    di = ImageDraw.Draw(idx)
    di.text((.14 * W, .1 * H), r, font=get_font(int(H * (.13 if len(r) == 2 else .165))), fill=col, anchor="mm")
    draw_suit(di, s, .14 * W, .205 * H, .042 * H)
    im = Image.alpha_composite(Image.alpha_composite(im, idx), idx.rotate(180))
    return im.resize((SW, SH), Image.LANCZOS)

@lru_cache(maxsize=1)
def get_back():
    K = _CK
    W, H = SW * K, SH * K
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=9 * K, fill=(255, 255, 255, 255), outline=(170, 170, 176, 255), width=K)
    m = 7 * K
    inner = Image.new("RGBA", (W - 2 * m, H - 2 * m), (150, 24, 44, 255))
    di = ImageDraw.Draw(inner)
    step = 12 * K
    for k in range(-inner.height, inner.width + inner.height, step):
        di.line([(k, 0), (k + inner.height, inner.height)], fill=(215, 90, 105, 255), width=K)
        di.line([(k, inner.height), (k + inner.height, 0)], fill=(215, 90, 105, 255), width=K)
    cx, cy = inner.width / 2, inner.height / 2
    di.ellipse([cx - 16 * K, cy - 16 * K, cx + 16 * K, cy + 16 * K], fill=(150, 24, 44, 255), outline=_CGOLD, width=2 * K)
    di.polygon([(cx, cy - 10 * K), (cx + 7 * K, cy), (cx, cy + 10 * K), (cx - 7 * K, cy)], fill=_CGOLD)
    mask = Image.new("L", inner.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, inner.width - 1, inner.height - 1], radius=5 * K, fill=255)
    im.paste(inner, (m, m), mask)
    return im.resize((SW, SH), Image.LANCZOS)

try:
    from cards_art import get_card      # real card pictures (cards_art.py next to this file)
except Exception as _e:
    print("cards_art.py not loaded, using the drawn cards:", repr(_e))

# --- the 52 cards + the card back become application emojis of the bot (created once, reused after every restart) ---
CARD_EMOJI = {}
CARD_BACK = None

def _emoji_png(card):
    im = get_back() if card is None else get_card(card)
    buf = io.BytesIO()
    im.resize((130, 186), Image.LANCZOS).save(buf, "PNG")    # card-shaped emoji, no empty padding
    return buf.getvalue()

async def setup_card_emojis():
    global CARD_BACK
    try:
        if not hasattr(bot, "create_application_emoji"):
            print("Card emojis need discord.py 2.5 or newer (pip install -U discord.py). Using text cards.")
            return
        allem = await bot.fetch_application_emojis()
        for e in allem:
            if e.name.startswith(("c_", "k_", "d_")):  # older versions of the cards: remove them
                try:
                    await e.delete()
                except Exception:
                    pass
        have = {e.name: e for e in allem}
        todo = [(None, "p_back")] + [((r, s), f"p_{r}{SUIT_LETTER[s]}") for r in RANKS for s in SUITS]
        made = 0
        for card, name in todo:
            e = have.get(name)
            if e is None:
                data = await asyncio.to_thread(_emoji_png, card)
                e = await bot.create_application_emoji(name=name, image=data)
                made += 1
                await asyncio.sleep(0.3)
            if card is None:
                CARD_BACK = str(e)
            else:
                CARD_EMOJI[card] = str(e)
        print(f"Card emojis ready ({made} created)")
    except Exception as ex:
        print("Card emojis failed, using text cards:", repr(ex))

def card_text(card):
    return CARD_EMOJI.get(card) or f"**{card[0]}**{SUIT_EMOJI[card[1]]}"

def back_text():
    return CARD_BACK or "❓"

CARD_HEADER = "# "   # cards are written on a heading line so Discord shows the emojis BIG. "## " = smaller, "" = small.

def cards_text(cards):
    return "".join(card_text(c) for c in cards)

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

class BlackjackView(discord.ui.View):
    def __init__(self, user, bet, token=None):
        super().__init__(timeout=120)
        self.user, self.token = user, token
        self.deck = [(r, s) for r in RANKS for s in SUITS]
        random.shuffle(self.deck)
        self.hands = [{"cards": [self.deck.pop(), self.deck.pop()], "bet": bet, "bust": False}]
        self.dealer = [self.deck.pop(), self.deck.pop()]
        self.active = self.net = 0
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
        returned += multi_extra("bj", returned - staked)
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

    def redeal(self):
        up = self.dealer[0]
        self.deck.extend(self.dealer[1:])
        random.shuffle(self.deck)
        self.dealer = [up, self.deck.pop()]
        self.dealer_play()

    def finalize(self):
        if any(not h["bust"] for h in self.hands):
            self.dealer_play()
            if self.player_wins() and random.random() < BJ_WIN_NERF:
                for _ in range(5):
                    self.redeal()
                    if not self.player_wins():
                        break
            for _ in range(luck_attempts(self.user.id) - 1):
                if self.player_wins():
                    break
                self.redeal()
        dv, returned = hand_value(self.dealer), 0
        for h in self.hands:
            pv = hand_value(h["cards"])
            if not h["bust"] and (pv > dv or dv > 21):
                returned += h["bet"] * 2
            elif not h["bust"] and pv == dv:
                returned += h["bet"]
        self.pay(returned, sum(h["bet"] for h in self.hands))

    def render(self):
        """Text-only embed (no image): instant to build and to send."""
        c, color, head = cur(), YELLOW, None
        if self.done:
            color, head = ((GREEN, f"You Won! +{fmt(self.net)} {c}") if self.net > 0 else
                           (RED, f"You Lost! -{fmt(-self.net)} {c}") if self.net < 0 else
                           (YELLOW, f"Push! +0 {c}"))
        lines = ["🃏 **Blackjack** 🃏", ""] + ([f"**{head}**", ""] if head else [])
        multi = len(self.hands) > 1
        for i, h in enumerate(self.hands):
            mark = " ◀" if multi and not self.done and i == self.active else ""
            lines.append(f"**Your Hand{f' {i + 1}' if multi else ''}**{mark}")
            lines.append(CARD_HEADER + cards_text(h["cards"]))
            lines.append(f"Value: **{hand_value(h['cards'])}**")
        if self.done:
            dealer_cards, dealer_val = cards_text(self.dealer), hand_value(self.dealer)
        else:
            dealer_cards, dealer_val = f"{card_text(self.dealer[0])}{back_text()}", card_value(self.dealer[0][0])
        lines += ["**Dealer**", CARD_HEADER + dealer_cards, f"Value: **{dealer_val}**"]
        e = discord.Embed(description="\n".join(lines), color=color)
        e.set_author(name=f"{self.user.name}'s Game", icon_url=self.user.display_avatar.url)
        return e

    async def update(self, interaction):
        self.refresh_buttons()
        e = self.render()
        # answer the click directly with the new message: no defer, no upload = instant
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=e, view=self)
        else:
            await interaction.edit_original_response(embed=e, view=self)

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
            await self.message.edit(embed=self.render(), view=self)

@bot.command(name="bj", aliases=["blackjack"], usage="bj <amount | half | all>")
async def bj(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "bj <amount | half | all>", track=True)
    if not bet:
        return
    BUSY.add(ctx.author.id)
    view = BlackjackView(ctx.author, bet, str(ctx.message.id))
    try:
        natural = view.check_naturals()
        msg = await ctx.send(embed=view.render(), view=view)
    except Exception:
        if not view.done:
            cancel_game(ctx.author, view.token, bet)
        BUSY.discard(ctx.author.id)
        raise
    if not natural:
        view.message = msg

# ================= SLOTS =================
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
    else:
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

SLOT_CACHE = {}

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
                    await asyncio.sleep(0.25)
        print("Animations are ready")
    except Exception as ex:
        print("Warm-up failed:", repr(ex))

async def finish_slots(ctx, token, bet, win, mult, final, png, msg):
    try:
        await asyncio.sleep(SLOT_WAIT + LOAD_BUFFER)
    finally:
        pending_done(token)
        user_data(ctx.author.id)["cash"] += win
        save()
        BUSY.discard(ctx.author.id)
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
        if max(final.count(s) for s in SLOTS) >= 2 and random.random() < SLOT_WIN_CUT:
            final = random.sample(SLOTS, 3)
        for _ in range(luck_attempts(ctx.author.id) - 1):
            if max(final.count(s) for s in SLOTS) >= 2:
                break
            final = [random.choice(SLOTS) for _ in range(3)]
        top = max(final.count(s) for s in SLOTS)
        mult = (SLOT_PAY[final[0]] if top == 3 else 1.5 if top == 2 else 0) * SLOT_BUFF
        win = int(bet * mult)
        if win > bet:
            win += multi_extra("slots", win - bet)
            mult = win / bet
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
        except discord.HTTPException:
            pass
    except Exception:
        BUSY.discard(ctx.author.id)
        raise
    bg(finish_slots(ctx, token, bet, win, mult, final, png, msg))

# ================= ROULETTE =================
ROUL_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
ROUL_WAIT = 30
ROUL_COLOR = 0x9B8CD6
ROUL_USAGE = "roulette <amount | half | all> <bet: 0-36, red, black, even, odd, 1-12...>"
ROUL_JOIN = "roulette <amount> <bet>"

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

ROUNDS = {}   # channel id -> the open roulette round of that channel (everyone can join it, as many bets as they want)

def roul_embed(rnd):
    first = rnd["bets"][0]
    names = ", ".join(b["pick"][0] for b in rnd["bets"] if b["user"].id == first["user"].id and b["token"].split(":")[0] == first["token"].split(":")[0])
    each = f" ({fmt(first['per'])} each)" if "," in names else ""
    return discord.Embed(color=ROUL_COLOR, title="🎰 Roulette Round Opened", description=(
        f"Roulette round opened by {first['user'].mention}.\n\n"
        f"**Bet:** {fmt(first['per'])} {cur()} on **{names}**{each}\n\n"
        f"Place a `${ROUL_JOIN}` to join before it closes.\n"
        f"Betting closes <t:{rnd['end']}:R>."))

async def run_roulette(cid, rnd):
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
            win = b["per"] * b["pick"][2] if hit else 0
            net = win - b["per"]
            if net > 0:
                win += multi_extra("roulette", net)
                net = win - b["per"]
            DB.get("pending", {}).pop(b["token"], None)
            user_data(b["user"].id)["cash"] += win
            log_game(b["user"], "roulette", b["per"], net)
            if win > 0:
                lines.append(f"🏆 {b['user'].mention} Won - {fmt(win)} {cur()}")
            else:
                lines.append(f"❌ {b['user'].mention} Lost")
        save()
        e = discord.Embed(color=ROUL_COLOR, title="Roulette Results", description=(
            f"The ball landed on **{winner} ({color_name.capitalize()})**\n\n**Results**\n" + "\n".join(lines)))
        none = discord.AllowedMentions.none()
        await rnd["channel"].send(embed=e, allowed_mentions=none)
    except Exception as ex:
        print("Roulette failed:", repr(ex))
        if ROUNDS.get(cid) is rnd:
            ROUNDS.pop(cid, None)
        for b in rnd["bets"]:
            if DB.get("pending", {}).pop(b["token"], None) is not None:
                user_data(b["user"].id)["cash"] += b["per"]
        save()

@bot.command(name="roulette", usage=ROUL_USAGE)
async def roulette(ctx, amount: str = None, *, picks: str = None):
    choices = roul_pick_list(picks)
    if choices is None or amount is None:
        return await reply(ctx, f"Usage: `${ROUL_USAGE}`", RED)
    u = user_data(ctx.author.id)
    n = len(choices)
    total = parse_amount(amount, u["cash"])
    if total is None:
        return await reply(ctx, f"Usage: `${ROUL_USAGE}` (min {MIN_BET})", RED)
    per = total // n if amount.lower() in ("all", "half") else total
    if per < MIN_BET:
        return await reply(ctx, f"The minimum bet is {MIN_BET} {cur()}.", RED)
    if per * n > u["cash"]:
        return await reply(ctx, "You don't have that much money.", RED)
    u["cash"] -= per * n
    base = str(ctx.message.id)
    new = []
    for i, c in enumerate(choices):
        tok = f"{base}:{i}"
        DB.setdefault("pending", {})[tok] = {"uid": str(ctx.author.id), "bet": per}
        new.append({"user": ctx.author, "per": per, "pick": c, "token": tok})
    save()
    rnd = ROUNDS.get(ctx.channel.id)
    opened = rnd is None or rnd["end"] <= time.time()
    if opened:
        rnd = {"end": int(time.time()) + ROUL_WAIT, "bets": [], "channel": ctx.channel}
        ROUNDS[ctx.channel.id] = rnd
    rnd["bets"].extend(new)
    none = discord.AllowedMentions.none()
    try:
        if opened:
            await ctx.reply(embed=roul_embed(rnd), mention_author=False, allowed_mentions=none)
        else:
            names = ", ".join(c[0] for c in choices)
            await ctx.reply(embed=make_embed(ctx.author, (
                f"**Bet Placed**\n\nYour roulette bet for {fmt(per)} {cur()} on **{names}** has been added."), GREEN),
                mention_author=False)
    except Exception:
        for b in new:
            DB.get("pending", {}).pop(b["token"], None)
            rnd["bets"].remove(b)
        u["cash"] += per * n
        save()
        if opened:
            ROUNDS.pop(ctx.channel.id, None)
        raise
    if opened:
        bg(run_roulette(ctx.channel.id, rnd))

# ================= HEADS OR TAIL / CHICKEN FIGHT =================
async def refund_timeout(view, name):
    view.settled = True
    pending_done(view.token)
    user_data(view.user.id)["cash"] += view.bet
    save()
    log_money(view.user, f"{name.upper()} | TIMEOUT", f"Bet of {fmt(view.bet)} {cur()} was returned", YELLOW)
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
        won = any(random.choice(("Head", "Tail")) == pick for _ in range(luck_attempts(self.user.id)))
        land = pick if won else ("Tail" if pick == "Head" else "Head")
        extra = multi_extra("ht", self.bet) if won else 0
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
        if not self.settled:
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
    won = any(random.randint(1, 100) <= strength + CF_HIDDEN for _ in range(luck_attempts(ctx.author.id)))
    if won:
        profit = bet + multi_extra("cf", bet)
        u["cash"] += bet + profit
        u["chicken"] = strength = min(CF_MAX, strength + 1)
        e = make_embed(ctx.author, f"Your chicken won the fight, you won {fmt(profit)} {c}🐓!", GREEN)
    else:
        profit = -bet
        u["chicken"] = strength = CF_MIN
        e = make_embed(ctx.author, f"Your chicken lost the fight... You lost {fmt(bet)} {c} 🐓.", RED)
    if won:
        e.add_field(name=f"Your chicken's strength (chance of winning): {strength}%",
                    value=f"**You now have {fmt(u['cash'])} {c}**", inline=False)
    save()
    log_game(ctx.author, "chicken fight", bet, profit)
    await ctx.reply(embed=e, mention_author=False)

# ================= HIGHER OR LOWER =================
HL_MIN, HL_MAX = 1, 100
HL_RTP = 0.95
HL_FLOOR = 1.05
HL_CAP = 25
HL_SAME = 25
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
        for _ in range(luck_attempts(self.user.id) - 1):
            if hit(second):
                break
            second = random.randint(HL_MIN, HL_MAX)
        won = hit(second)
        win = int(self.bet * self.mults[choice]) if won else 0
        if win > self.bet:
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
        if not self.settled:
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

# ================= SCRATCH CARDS ($sc) =================
try:
    from scratch_art import ART as SC_ART
except Exception as _e:
    print("scratch_art.py not loaded, scratch cards disabled:", repr(_e))
    SC_ART = {}

SC_WIDTH = 560
SC_PAY_TO = "bank"

# the order here is the order of the menu and of the kiosk picture
SC_CARDS = {
    "club": {
        "name": "הקלף", "emoji": "♣️", "min": 50_000_000, "total": 50, "cols": 4,
        "wins": {1.5: 5, 2: 5, 7: 2, 60: 1},
        "orig": (1289, 1580), "spots": [(640, 640, 120), (440, 930, 120), (840, 930, 120), (640, 1140, 85)],
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
    "queen": {
        "name": "מלכת הלבבות", "emoji": "♥️", "min": 2_500_000, "total": 350, "cols": 5,
        "wins": {2.3: 50, 1.7: 25, 1.5: 90, 0.5: 25, 25: 1},
        "orig": (800, 950), "spots": [(412, 612, 102), (622, 612, 102), (195, 835, 102), (405, 835, 102), (620, 835, 102)],
    },
}
SC_EN = {"queen": "Queen of Hearts", "casino": "Casino Roulette Wheel", "safe": "Safe", "club": "Club"}
SC_DECOYS = [0.3, 0.5, 0.8, 1.1, 1.3, 1.5, 1.7, 2, 2.3, 3, 3.5, 4, 5, 7, 10, 15, 25]

def sc_short(n):
    return f"{n / 1_000_000:g}M"

def sc_stock(key):
    c = SC_CARDS[key]
    store = DB.setdefault("sc_stock", {})
    st = store.get(key)
    if st is None:
        pool = [m for m, n in c["wins"].items() for _ in range(n)]
        pool += [0] * (c["total"] - len(pool))
        random.shuffle(pool)
        st = store[key] = {"left": pool, "sold": 0}
        save()
    return st

def return_card(key, mult):
    st, c = DB.get("sc_stock", {}).get(key), SC_CARDS.get(key)
    if not st or not c or len(st["left"]) >= c["total"]:
        return
    st["left"].insert(random.randint(0, len(st["left"])), mult)
    st["sold"] = max(0, st["sold"] - 1)

def sc_labels(n, mult):
    decoys = [d for d in SC_DECOYS if d != mult]
    out, counts = ([mult] * 3 if mult else []), {}
    while len(out) < n:
        d = random.choice(decoys)
        if counts.get(d, 0) < 2:
            counts[d] = counts.get(d, 0) + 1
            out.append(d)
    random.shuffle(out)
    return out

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

def he(text):
    """Hebrew for PIL: reversed only when this Pillow has no RTL support (raqm)."""
    return text if features.check("raqm") else text[::-1]

SC_BANNER = {"key": None, "data": None}
_banner_lock = asyncio.Lock()

def sc_key():
    return tuple(len(sc_stock(k)["left"]) for k in SC_CARDS)

def sc_banner_build(key):
    if SC_BANNER["key"] != key:
        data = sc_banner_render()
        SC_BANNER["key"], SC_BANNER["data"] = key, data
    return SC_BANNER["data"]

async def refresh_banner():
    """Draws the menu picture in the background, so $sc never waits for it."""
    if not SC_ART:
        return
    try:
        async with _banner_lock:
            key = sc_key()
            if SC_BANNER["key"] != key:
                for k in SC_CARDS:
                    await asyncio.to_thread(sc_base, k)
                await asyncio.to_thread(sc_banner_build, key)
    except Exception as ex:
        print("Scratch banner failed:", repr(ex))

def sc_banner_render():
    """Menu picture: a lottery-style kiosk (lit sign box, glass window with acrylic card dispensers, price tags, counter).
    Drawn at 2x and scaled down so every edge is smooth."""
    S, W, H = 2, 1100, 820
    keys = list(SC_CARDS)
    im = Image.new("RGBA", (W * S, H * S))
    d = ImageDraw.Draw(im)

    def X(v):
        return int(v * S)

    def B(b):
        return [X(v) for v in b]

    def vgrad(b, c1, c2):
        x0, y0, x1, y1 = B(b)
        for y in range(y0, y1):
            k = (y - y0) / max(1, y1 - y0 - 1)
            d.line([(x0, y), (x1, y)], fill=tuple(int(p + (q - p) * k) for p, q in zip(c1, c2)))

    def hgrad(b, c1, c2):
        x0, y0, x1, y1 = B(b)
        for x in range(x0, x1):
            k = (x - x0) / max(1, x1 - x0 - 1)
            d.line([(x, y0), (x, y1)], fill=tuple(int(p + (q - p) * k) for p, q in zip(c1, c2)))

    def over(fn, blur=0):
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
        fn(ImageDraw.Draw(layer))
        bb = layer.getbbox()
        if not bb:
            return
        pad = blur * S * 3
        x0, y0 = max(0, bb[0] - pad), max(0, bb[1] - pad)
        x1, y1 = min(im.width, bb[2] + pad), min(im.height, bb[3] + pad)
        part = layer.crop((x0, y0, x1, y1))
        if blur:
            part = part.filter(ImageFilter.GaussianBlur(blur * S))
        im.alpha_composite(part, (x0, y0))

    def F(size):
        return get_font(int(size * S))

    def fit(text, size, maxw):
        while size > 10 and d.textlength(he(text), font=F(size)) > maxw * S:
            size -= 1
        return F(size)

    def pair(cx, y, num, label, size, fill, sp=7):
        """'<label> <num>' centred on cx; the number is drawn on its own so it never gets flipped."""
        f, lab = F(size), he(label)
        wl, wn = d.textlength(lab, font=f), d.textlength(num, font=f)
        x = X(cx) - (wl + X(sp) + wn) / 2
        d.text((x, X(y)), num, font=f, fill=fill, anchor="lt")
        d.text((x + wn + X(sp), X(y)), lab, font=f, fill=fill, anchor="lt")

    def spade(cx, cy, s, fill, draw=None):
        """Vector spade, centred on (cx, cy), about 2*s tall."""
        g = draw or d
        g.polygon([(X(cx), X(cy - s)), (X(cx - 0.92 * s), X(cy + 0.14 * s)), (X(cx + 0.92 * s), X(cy + 0.14 * s))], fill=fill)
        for sx in (-0.44, 0.44):
            r = 0.5 * s
            g.ellipse([X(cx + sx * s - r), X(cy + 0.14 * s - r), X(cx + sx * s + r), X(cy + 0.14 * s + r)], fill=fill)
        g.polygon([(X(cx), X(cy + 0.1 * s)), (X(cx - 0.34 * s), X(cy + 1.0 * s)), (X(cx + 0.34 * s), X(cy + 1.0 * s))], fill=fill)

    rnd = random.Random(7)
    CHAMP = (222, 205, 160)        # soft champagne used for thin accents
    CHAMP_D = (150, 132, 96)

    # ---- evening street background with soft lights ----
    vgrad((0, 0, W, 700), (8, 12, 30), (40, 52, 96))
    pal = [(190, 210, 255, 60), (130, 190, 255, 60), (255, 150, 190, 40), (200, 230, 255, 40)]
    over(lambda g: [g.ellipse(B((x - r, y - r, x + r, y + r)), fill=rnd.choice(pal))
                    for x, y, r in ((rnd.uniform(0, W), rnd.uniform(0, 600), rnd.uniform(10, 40)) for _ in range(46))], blur=5)
    vgrad((0, 700, W, H), (62, 64, 78), (22, 22, 32))
    for yy in (722, 752, 792):
        d.line(B((0, yy, W, yy)), fill=(40, 42, 54), width=S)
    for xx in range(-500, 1600, 120):
        d.line(B((W / 2 + (xx - W / 2) * 0.5, 700, xx, H)), fill=(40, 42, 54), width=S)
    over(lambda g: g.ellipse(B((120, 726, 980, 812)), fill=(190, 215, 255, 40)), blur=22)       # light spilling on the floor
    over(lambda g: g.ellipse(B((30, 712, 1070, 772)), fill=(0, 0, 0, 190)), blur=12)            # shadow under the kiosk

    # ---- back wall inside the kiosk ----
    vgrad((110, 206, 990, 600), (52, 70, 108), (28, 40, 70))
    for yy in range(222, 600, 22):
        d.line(B((110, yy, 990, yy)), fill=(24, 34, 60), width=S)
        d.line(B((110, yy + 1, 990, yy + 1)), fill=(66, 88, 128), width=1)
    over(lambda g: g.rectangle(B((130, 206, 970, 300)), fill=(225, 238, 255, 90)), blur=26)      # light from the LED strip
    vgrad((110, 206, 990, 221), (250, 252, 255), (214, 226, 246))

    # shelf
    vgrad((110, 478, 990, 494), (244, 247, 252), (186, 193, 206))
    d.line(B((110, 478, 990, 478)), fill=(255, 255, 255), width=S)
    over(lambda g: g.rectangle(B((110, 494, 990, 508)), fill=(0, 0, 0, 110)), blur=5)

    # ---- decks in acrylic holders ----
    cw, ch, bw = 168, 210, 188
    gap = (880 - 4 * bw) / 5
    for i, key in enumerate(keys):
        c = SC_CARDS[key]
        left = len(sc_stock(key)["left"])
        bx = int(110 + gap + i * (bw + gap))
        cx0, base_y = bx + (bw - cw) // 2, 478 - 8 - ch
        n = 0 if not left else max(2, round(left / c["total"] * 10))
        rng = random.Random(key)
        over(lambda g: g.rounded_rectangle(B((bx + 12, 244, bx + bw + 12, 482)), radius=10, fill=(0, 0, 0, 120)), blur=8)
        over(lambda g: g.rounded_rectangle(B((bx, 228, bx + bw, 478)), radius=8, fill=(190, 215, 240, 26),
                                           outline=(200, 225, 250, 150), width=2 * S))
        for j in range(n - 1, 0, -1):
            jx = rng.randint(-1, 1)
            d.rounded_rectangle(B((cx0 + jx, base_y - j * 3, cx0 + jx + cw, base_y - j * 3 + ch)), radius=X(8),
                                fill=(246, 246, 250), outline=(150, 150, 162), width=S)
        b = sc_base(key)
        k = max(cw * S / b.width, ch * S / b.height)
        art = b.resize((max(cw * S, round(b.width * k)), max(ch * S, round(b.height * k))), Image.LANCZOS).crop((0, 0, cw * S, ch * S))
        if not left:
            art = Image.blend(art.convert("L").convert("RGB"), Image.new("RGB", art.size, (20, 20, 20)), 0.55)
        m = Image.new("L", (cw * S, ch * S), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, cw * S - 1, ch * S - 1], radius=X(8), fill=255)
        im.paste(art.convert("RGBA"), (X(cx0), X(base_y)), m)
        d.rounded_rectangle(B((cx0, base_y, cx0 + cw, base_y + ch)), radius=X(8),
                            outline=(240, 240, 246) if left else (110, 110, 112), width=2 * S)
        if not left:
            tag = Image.new("RGBA", (X(220), X(60)), (0, 0, 0, 0))
            ImageDraw.Draw(tag).text((X(110), X(30)), "SOLD OUT", font=F(34), fill=(255, 80, 80, 255), anchor="mm",
                                     stroke_width=3 * S, stroke_fill=(0, 0, 0, 255))
            tag = tag.rotate(14, expand=True, resample=Image.BICUBIC)
            im.alpha_composite(tag, (X(bx + bw / 2 - 110) - (tag.width - X(220)) // 2, X(base_y + ch / 2 - 30) - (tag.height - X(60)) // 2))
        # acrylic front: lip, glare, steel base
        over(lambda g: g.rounded_rectangle(B((bx + 2, 442, bx + bw - 2, 476)), radius=6, fill=(220, 235, 250, 46),
                                           outline=(230, 242, 255, 120), width=S))
        over(lambda g: g.polygon(B((bx + 18, 230, bx + 58, 230, bx + 24, 440, bx + 6, 440)), fill=(255, 255, 255, 52)))
        hgrad((bx - 4, 470, bx + bw + 4, 480), (150, 156, 170), (232, 236, 244))

    # ---- price tags under the shelf ----
    for i, key in enumerate(keys):
        c = SC_CARDS[key]
        left = len(sc_stock(key)["left"])
        bx = int(110 + gap + i * (bw + gap))
        cx, ty = bx + bw / 2, 512
        over(lambda g: g.rounded_rectangle(B((bx + 3, ty + 4, bx + bw + 3, ty + 80)), radius=6, fill=(0, 0, 0, 120)), blur=4)
        d.rounded_rectangle(B((bx, ty, bx + bw, ty + 76)), radius=X(6), fill=(250, 251, 254), outline=(170, 178, 194), width=S)
        d.rounded_rectangle(B((bx, ty, bx + bw, ty + 26)), radius=X(6), fill=(0, 84, 170))
        d.rectangle(B((bx, ty + 16, bx + bw, ty + 26)), fill=(0, 84, 170))
        d.text((X(cx), X(ty + 13)), he(c["name"]), font=fit(c["name"], 19, bw - 16), fill=(255, 255, 255), anchor="mm")
        pair(cx, ty + 31, sc_short(c["min"]), "סכום התחלתי", 17, (0, 58, 128))
        ratio = left / c["total"]
        col = (24, 130, 58) if ratio > 0.5 else (196, 112, 8) if ratio > 0.2 else (200, 36, 36)
        if left:
            pair(cx, ty + 52, f"{left}/{c['total']}", "נותרו", 17, col)
        else:
            d.text((X(cx), X(ty + 52)), he("אזל המלאי"), font=F(17), fill=col, anchor="lt")
        for px in (bx + 8, bx + bw - 8):
            d.ellipse(B((px - 2, ty + 4, px + 2, ty + 8)), fill=(150, 156, 170))

    # ---- glass in front of the window ----
    over(lambda g: g.rectangle(B((110, 206, 990, 600)), fill=(150, 200, 255, 12)))
    over(lambda g: (g.polygon(B((130, 222, 330, 222, 205, 598, 110, 598)), fill=(255, 255, 255, 24)),
                    g.polygon(B((372, 222, 424, 222, 300, 598, 250, 598)), fill=(255, 255, 255, 15)),
                    g.polygon(B((770, 222, 900, 222, 780, 598, 690, 598)), fill=(255, 255, 255, 18))))

    # ---- pillars + header beam ----
    for x0 in (70, 988):
        hgrad((x0, 196, x0 + 42, 722), (186, 194, 210), (246, 248, 252))
        d.rectangle(B((x0 + 15, 210, x0 + 27, 598)), fill=(0, 84, 170))
        d.line(B((x0 + 15, 210, x0 + 15, 598)), fill=(70, 150, 230), width=S)
        d.rectangle(B((x0, 196, x0 + 42, 722)), outline=(110, 118, 136), width=S)
    vgrad((70, 196, 1030, 210), (230, 235, 244), (150, 158, 176))
    over(lambda g: g.rectangle(B((110, 210, 990, 224)), fill=(0, 0, 0, 90)), blur=4)

    # ---- counter ----
    vgrad((54, 598, 1046, 620), (240, 244, 250), (180, 187, 202))
    d.line(B((54, 598, 1046, 598)), fill=(255, 255, 255), width=2 * S)
    d.line(B((54, 620, 1046, 620)), fill=(120, 128, 146), width=S)
    vgrad((62, 620, 1038, 716), (238, 242, 248), (206, 212, 224))
    vgrad((62, 636, 1038, 676), (0, 98, 192), (0, 62, 134))
    d.rectangle(B((62, 676, 1038, 680)), fill=CHAMP)                                       # thin accent line (was a thick yellow bar)
    d.rectangle(B((62, 680, 1038, 686)), fill=(0, 46, 108))
    d.line(B((62, 636, 1038, 636)), fill=(90, 160, 235), width=S)
    d.text((X(550), X(656)), he("מצאו צירוף של שלושה מכפילים"), font=F(26), fill=(255, 255, 255), anchor="mm")
    vgrad((62, 716, 1038, 738), (70, 74, 90), (30, 32, 42))
    # card terminal and pen cup on the counter
    over(lambda g: g.rounded_rectangle(B((992, 566, 1036, 600)), radius=6, fill=(0, 0, 0, 120)), blur=4)
    d.rounded_rectangle(B((992, 560, 1034, 598)), radius=X(6), fill=(26, 28, 36), outline=(90, 96, 110), width=S)
    d.rectangle(B((998, 566, 1028, 578)), fill=(40, 140, 230))
    for r in range(2):
        for cc in range(3):
            d.rectangle(B((999 + cc * 10, 583 + r * 7, 1005 + cc * 10, 587 + r * 7)), fill=(120, 126, 142))
    hgrad((74, 570, 98, 598), (150, 156, 170), (232, 236, 244))
    for px, py, col in ((80, 556, (200, 40, 40)), (86, 552, (30, 90, 200)), (92, 558, (30, 30, 34))):
        d.line(B((px + 6, 572, px, py)), fill=col, width=2 * S)

    # ---- roof ----
    over(lambda g: g.rectangle(B((50, 86, 1050, 104)), fill=(0, 0, 0, 110)), blur=6)
    d.polygon(B((36, 36, 1064, 36, 1046, 62, 54, 62)), fill=(238, 242, 250))
    vgrad((50, 62, 1050, 86), (250, 252, 255), (190, 198, 216))
    d.line(B((50, 86, 1050, 86)), fill=(120, 128, 146), width=S)

    # ---- sign: dark glass panel with a thin champagne frame, spades on both sides ----
    d.rounded_rectangle(B((90, 90, 1010, 192)), radius=X(10), fill=(40, 46, 62), outline=(110, 118, 136), width=S)
    over(lambda g: g.rounded_rectangle(B((98, 98, 1002, 184)), radius=6, fill=(90, 130, 230, 90)), blur=10)
    vgrad((98, 98, 1002, 184), (18, 26, 58), (6, 10, 28))
    over(lambda g: g.ellipse(B((250, 96, 850, 200)), fill=(70, 110, 220, 70)), blur=24)       # soft glow behind the title
    d.rounded_rectangle(B((98, 98, 1002, 184)), radius=X(6), outline=CHAMP_D, width=S)
    d.rounded_rectangle(B((104, 104, 996, 178)), radius=X(4), outline=(70, 80, 112), width=1)
    d.text((X(550), X(134)), he("כרטיסי גירוד"), font=F(60), fill=(248, 244, 232), anchor="mm",
           stroke_width=2 * S, stroke_fill=(4, 8, 24))
    # subtitle with thin rules on both sides
    sub = "A M R A M   C A S I N O"
    sw = d.textlength(sub, font=F(17))
    d.text((X(550), X(168)), sub, font=F(17), fill=CHAMP, anchor="mm")
    for sgn in (-1, 1):
        x_in = 550 + sgn * (sw / S / 2 + 16)
        x_out = 550 + sgn * (sw / S / 2 + 110)
        d.line(B((min(x_in, x_out), 168, max(x_in, x_out), 168)), fill=CHAMP_D, width=S)
    for sx in (172, 928):
        d.ellipse(B((sx - 38, 103, sx + 38, 179)), fill=(10, 16, 40), outline=CHAMP_D, width=2 * S)
        d.ellipse(B((sx - 33, 108, sx + 33, 174)), outline=(60, 70, 104), width=1)
        spade(sx, 138, 22, (240, 236, 224))

    # ---- photo feel: vignette + fine grain (done on the small image: much faster) ----
    out = im.convert("RGB").resize((W, H), Image.LANCZOS)
    vig = Image.new("L", (W // 4, H // 4), 0)
    ImageDraw.Draw(vig).ellipse([-W // 16, -H // 12, W // 4 + W // 16, H // 4 + H // 12], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(30)).resize((W, H), Image.BILINEAR)
    out = Image.composite(out, Image.new("RGB", (W, H), (4, 8, 18)), vig)
    out = Image.blend(out, Image.effect_noise((W, H), 26).convert("RGB"), 0.03)
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=90)
    return buf.getvalue()
# --- render end ---

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
            f"מצאו צירוף של **שלושה מכפילים** כדי לזכות!\n"
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
        if returned > self.bet:
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

class AmountModal(discord.ui.Modal):
    def __init__(self, menu, key):
        c = SC_CARDS[key]
        super().__init__(title=f"{c['name']} - כמה כסף?"[:45])
        self.menu, self.key = menu, key
        self.amount = discord.ui.TextInput(label=f"סכום מהבנק (סכום התחלתי {sc_short(c['min'])})"[:45],
                                           placeholder="למשל: 5m או 2500000 או half או all", max_length=20)
        self.add_item(self.amount)

    async def on_submit(self, interaction):
        menu, key, c, user = self.menu, self.key, SC_CARDS[self.key], self.menu.user
        say = lambda t: interaction.response.send_message(t, ephemeral=True)
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
            return await say(f"הסכום ההתחלתי לכרטיס הזה הוא **{fmt(c['min'])}** {cur()}.")
        if price > u["bank"]:
            return await say(f"אין לך מספיק כסף **בבנק**. יש לך {fmt(u['bank'])} {cur()} (`$dep` להפקדה).")
        u["bank"] -= price
        menu.chosen = True
        menu.stop()
        mult = st["left"].pop()
        for _ in range(luck_attempts(user.id) - 1):
            if st["left"]:
                j = random.randrange(len(st["left"]))
                if st["left"][j] > mult:
                    st["left"][j], mult = mult, st["left"][j]
        st["sold"] += 1
        bg(refresh_banner())
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
            desc = (f"התחלה {sc_short(c['min'])} • פרס ראשי x{max(c['wins']):g} • נותרו {left}/{c['total']}" if left else "אזל המלאי")
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
            await interaction.message.edit(view=menu)
        except Exception:
            pass

class ScratchMenu(OwnedView):
    touch = True

    def __init__(self, user):
        super().__init__(timeout=120)
        self.user, self.message, self.chosen = user, None, False
        self.add_item(ScratchSelect())

    def embed(self, image=True):
        bank = user_data(self.user.id)["bank"]
        e = discord.Embed(color=0x1F2A44, title="כרטיסי גירוד", description=(
            f"\u200f**יתרה בבנק:** {fmt(bank)} {cur()}\n"
            "\u200fבחרו כרטיס מהתפריט שמתחת והקלידו כמה לשלם."))
        e.set_author(name=self.user.name, icon_url=self.user.display_avatar.url)
        e.set_footer(text="התשלום יורד מהבנק בלבד")
        if image:
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

@tasks.loop(seconds=30)
async def sc_daily_loop():
    """Every day at 00:00 all scratch cards go back to the stock."""
    if loaded is None or not loaded.is_set():
        return
    today = today_key()
    last = DB.get("sc_reset_day")
    if last is None:
        DB["sc_reset_day"] = today
        save()
    elif last != today:
        DB["sc_stock"] = {}
        for k in SC_CARDS:
            sc_stock(k)
        DB["sc_reset_day"] = today
        save()
        bg(refresh_banner())
        print("Scratch cards restocked (00:00)")

@bot.command(name="scratch", aliases=["sc"], usage="sc")
async def scratch(ctx, sub: str = None):
    if sub and sub.lower() in ("restart", "reset"):
        if ctx.author.id not in OWNER_IDS:
            return
        DB["sc_stock"] = {}
        for k in SC_CARDS:
            sc_stock(k)
        save()
        bg(refresh_banner())
        return await reply(ctx, "🎟️ כל כרטיסי הגירוד אופסו: כל הכרטיסים חזרו למלאי.", GREEN)
    if ctx.author.id in BUSY:
        return await reply(ctx, BUSY_MSG, RED)
    if not SC_ART:
        return await reply(ctx, "scratch_art.py is missing next to the bot file.", RED)
    view = ScratchMenu(ctx.author)
    data = SC_BANNER["data"]          # the menu opens instantly with the last picture, a fresh one is drawn in the background
    if data:
        view.message = await ctx.reply(embed=view.embed(), file=discord.File(io.BytesIO(data), "sc_menu.jpg"),
                                       view=view, mention_author=False)
    else:
        view.message = await ctx.reply(embed=view.embed(image=False), view=view, mention_author=False)
    if SC_BANNER["key"] != sc_key():
        bg(update_menu_picture(view))

async def update_menu_picture(view):
    await refresh_banner()
    data = SC_BANNER["data"]
    if not data or view.chosen or not view.message:
        return
    try:
        await view.message.edit(embed=view.embed(), attachments=[discord.File(io.BytesIO(data), "sc_menu.jpg")])
    except Exception:
        pass

# ================= ECONOMY =================
ID_RE = re.compile(r"<@!?(\d{15,25})>|(\d{15,25})")

async def resolve_target(ctx, arg):
    """Reply target ("a"), a mention, a raw user ID, or a name."""
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
        if not any(m.id == author.id for m in ctx.message.mentions):
            raise ReplyPingOff()
        return ctx.guild.get_member(author.id) or await ctx.guild.fetch_member(author.id)
    m = ID_RE.fullmatch(arg.strip())
    if m:
        uid = int(m.group(1) or m.group(2))
        member = ctx.guild.get_member(uid) if ctx.guild else None
        if member:
            return member
        try:
            return await ctx.guild.fetch_member(uid)
        except discord.HTTPException:
            pass
        try:
            return await bot.fetch_user(uid)
        except discord.HTTPException:
            raise commands.BadArgument("Unknown user ID")
    return await commands.MemberConverter().convert(ctx, arg)

@bot.command(name="bal", aliases=["balance"], usage="bal [@user | user ID | a (reply)]")
async def bal(ctx, target: str = None):
    if target is None:
        member = ctx.author
    else:
        member = await resolve_target(ctx, target)
        if member is None:
            return await reply(ctx, "Usage: `$bal [@user | user ID]` — or reply to a player (ping ON) and type `$bal a`", RED)
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
    log_money(ctx.author, ctx.command.name.upper(), f"{verb.capitalize()} {fmt(amt)} {cur()}", BLUE)
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
    log_money(ctx.author, ctx.command.name.upper(), f"Earned {fmt(amt)} {cur()}", GREEN)
    await reply(ctx, text.format(f"{fmt(amt)} {cur()}"), GREEN)

@bot.command(name="crime", cooldown_after_parsing=True)
@commands.cooldown(1, 120, commands.BucketType.user)
async def crime(ctx):
    await earn(ctx, "You successfully committed a crime and got {}!")

@bot.command(name="work", cooldown_after_parsing=True)
@commands.cooldown(1, 120, commands.BucketType.user)
async def work(ctx):
    await earn(ctx, "You worked hard and got {}!")

@bot.command(name="pay", usage="pay @user | user ID <amount | half | all>  (or reply + ping ON: pay a <amount>)")
async def pay(ctx, target: str = None, amount: str = None):
    member = await resolve_target(ctx, target)
    if member is None or amount is None:
        return await reply(ctx, "Usage: `$pay @user | user ID <amount | half | all>` — or reply to a player (ping ON) and type `$pay a <amount>`", RED)
    if member.bot or member.id == ctx.author.id:
        return await reply(ctx, "You can't pay this user.", RED)
    u = user_data(ctx.author.id)
    amt = parse_amount(amount, u["cash"])
    if amt is None or amt <= 0:
        return await reply(ctx, "Usage: `$pay @user | user ID <amount | half | all>`", RED)
    if amt > u["cash"]:
        return await reply(ctx, "You don't have that much money.", RED)
    u["cash"] -= amt
    user_data(member.id)["cash"] += amt
    save()
    log_money(ctx.author, "PAY", f"Paid {fmt(amt)} {cur()} to {member.name} (`{member.id}`)", BLUE)
    await reply(ctx, f"You paid {fmt(amt)} {cur()} to {member.name}.", GREEN)

@bot.command(name="rob", usage="rob @user | user ID  (or reply + ping ON: rob a)", cooldown_after_parsing=True)
@commands.cooldown(1, ROB_COOLDOWN, commands.BucketType.user)
async def rob(ctx, target: str = None):
    try:
        member = await resolve_target(ctx, target)
    except Exception:
        ctx.command.reset_cooldown(ctx)
        raise
    if member is None:
        ctx.command.reset_cooldown(ctx)
        return await reply(ctx, "Usage: `$rob @user | user ID` — or reply to a player (ping ON) and type `$rob a`", RED)
    if member.bot or member.id == ctx.author.id:
        ctx.command.reset_cooldown(ctx)
        return await reply(ctx, "You can't rob this user.", RED)
    me, tgt = user_data(ctx.author.id), user_data(member.id)
    loot = {k: int(tgt[k] * ROB_PERCENT) for k in ROB_FROM}
    total = sum(loot.values())
    if not total:
        return await reply(ctx, f"You tried to rob a poor person and lost 0 {cur()}.", RED)
    for k, v in loot.items():
        tgt[k] -= v
    me["cash"] += total
    save()
    log_game(ctx.author, "rob", 0, total, detail=f"Robbed {member.name} (`{member.id}`)")
    await reply(ctx, f"You robbed {fmt(total)} {cur()} from {member.name}!", GREEN)

# ---------- leaderboard ----------
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
    view.message = await ctx.reply(embed=view.build(), view=view, mention_author=False)

# ================= SHOP =================
SHOP_TITLE = "Amram Casino Shop"
SHOP_COLOR = 0xDDC9A3
SHOP_THUMBNAIL = None

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

SHOP_BUSY = set()

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
    if role in member.roles:
        return await shop_say(interaction, f"You already have **{name}**.")
    key = (member.id, role_id)
    if key in SHOP_BUSY:
        return await shop_say(interaction, "Your purchase is already being processed.")
    u = user_data(member.id)
    if u["bank"] < price:
        return await shop_say(
            interaction,
            f"You need **{fmt(price)}** {cur()} **in your bank** for {role.mention}.\n"
            f"You have {fmt(u['bank'])} {cur()} in the bank. (`$dep` to deposit)")
    SHOP_BUSY.add(key)
    u["bank"] -= price
    save()
    try:
        await member.add_roles(role, reason="Casino shop")
    except Exception as ex:
        u["bank"] += price
        save()
        print("Shop: add_roles failed:", repr(ex))
        return await shop_say(interaction, "I couldn't give you the role (my role must be above it). You were not charged.")
    finally:
        SHOP_BUSY.discard(key)
    log_money(member, "SHOP", f"Bought {name} for {fmt(price)} {cur()}", YELLOW)
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
        super().__init__(timeout=None)
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
    if ctx.author.id in OWNER_IDS or ctx.author.guild_permissions.administrator:
        return True
    raise commands.MissingPermissions(["administrator"])

def is_staff(ctx):
    if ctx.author.id in OWNER_IDS or ctx.author.guild_permissions.administrator:
        return True
    rid = DB.get("staff_role")
    if rid and any(r.id == rid for r in ctx.author.roles):
        return True
    raise NotStaff()

admin_only = commands.check(admin_or_owner)
staff_only = commands.check(is_staff)
owner_only = commands.check(lambda ctx: ctx.author.id in OWNER_IDS)

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
    log_event(ctx.author, "LOG CHANNEL SET", "This channel is now the game log (wins, losses and money changes).", BLUE)

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

def _add_used():
    used = DB.setdefault("add_used", {})
    if used.get("date") != today_key():          # new day (00:00): counters start from zero
        used.clear()
        used["date"] = today_key()
        used["users"] = {}
    return used["users"]

def add_limit_error(ctx):
    cap = DB.get("add_limit")
    if ctx.author.id in OWNER_IDS or not cap:
        return None
    if _add_used().get(str(ctx.author.id), 0) >= cap:
        return "You have used all of your daily additions for today."
    return None

def add_limit_count(ctx):
    if ctx.author.id in OWNER_IDS or not DB.get("add_limit"):
        return
    users = _add_used()
    users[str(ctx.author.id)] = users.get(str(ctx.author.id), 0) + 1

def add_cap_error(ctx, amt):
    cap = DB.get("add_max")
    if ctx.author.id not in OWNER_IDS and cap and amt > cap:
        return f"You can add at most **{fmt(cap)}** {cur()} per command."
    return None

@bot.command(name="addmoney", usage="addmoney <bank|cash> @user <amount>")
@staff_only
async def addmoney(ctx, *args: str):
    where, member, amount = await parse_money_args(ctx, args)
    amt = parse_amount(amount, 0)
    if where not in ("bank", "cash") or member is None or amt is None or amt <= 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    err = add_cap_error(ctx, amt) or add_limit_error(ctx)
    if err:
        return await reply(ctx, err, RED)
    add_limit_count(ctx)
    user_data(member.id)[where] += amt
    save()
    log_event(ctx.author, "ADD MONEY", f"Added **{fmt(amt)}** {cur()} to the {where} of {member.name} (`{member.id}`)", BLUE)
    await reply(ctx, f"Added {fmt(amt)} {cur()} to {member.name}'s {where}.", GREEN)

@bot.command(name="removemoney", usage="removemoney <bank|cash> @user <amount>")
@staff_only
async def removemoney(ctx, *args: str):
    where, member, amount = await parse_money_args(ctx, args)
    if where not in ("bank", "cash") or member is None or amount is None:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    u = user_data(member.id)
    amt = parse_amount(amount, u[where])
    if amt is None or amt <= 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    taken = min(amt, u[where])
    u[where] -= taken
    save()
    log_event(ctx.author, "REMOVE MONEY", f"Removed **{fmt(taken)}** {cur()} from the {where} of {member.name} (`{member.id}`)", BLUE)
    await reply(ctx, f"Removed {fmt(taken)} {cur()} from {member.name}'s {where}.", GREEN)

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
    log_event(ctx.author, "RESET MONEY", f"{member.name} (`{member.id}`): {where} " +
              ("reset to 0" if where == "all" else f"set to **{fmt(amt)}**"), BLUE)
    await reply(ctx, f"{member.name}'s {where} " + ("was reset to 0." if where == "all" else f"was set to {fmt(amt)} {cur()}."), GREEN)

@bot.command(name="addmoneyrole", usage="addmoneyrole <bank|cash> @role <amount>")
@staff_only
async def addmoneyrole(ctx, where: str, role: discord.Role, amount: str):
    where = where.lower()
    amt = parse_amount(amount, 0)
    if where not in ("bank", "cash") or amt is None or amt <= 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    err = add_cap_error(ctx, amt) or add_limit_error(ctx)
    if err:
        return await reply(ctx, err, RED)
    if not ctx.guild.chunked:
        await ctx.guild.chunk()
    members = [m for m in role.members if not m.bot]
    if not members:
        return await reply(ctx, "No members found in that role.", RED)
    add_limit_count(ctx)
    for m in members:
        user_data(m.id)[where] += amt
    save()
    log_event(ctx.author, "ADD MONEY TO ROLE", f"Added **{fmt(amt)}** {cur()} to the {where} of {len(members)} members of {role.name}", BLUE)
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

@bot.command(name="setlimit", usage="setlimit <additions per day>")
@owner_only
async def setlimit(ctx, amount: str = None):
    cap = DB.get("add_limit")
    if amount is None:
        return await reply(ctx, f"Daily add limit: {cap if cap else 'no limit'}\nSet it with `$setlimit <number>`", BLUE)
    if not amount.isdigit() or int(amount) < 1:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    DB["add_limit"] = int(amount)
    save()
    await reply(ctx, f"Each staff member can now use the add-money commands **{int(amount)}** time(s) per day. It resets at 00:00.", GREEN)

@bot.command(name="unsetlimit", usage="unsetlimit")
@owner_only
async def unsetlimit(ctx):
    DB.pop("add_limit", None)
    DB.pop("add_used", None)
    DB.pop("add_max", None)
    save()
    await reply(ctx, "All add-money limits were removed (daily limit and the per-command maximum).", GREEN)

@bot.command(name="multi", usage="multi <game | all> <amount | off> [time: 10m, 2h, 1d]")
@owner_only
async def multi(ctx, game: str = None, amount: str = None, duration: str = None):
    cfg = DB.setdefault("multi", {})
    until = DB.setdefault("multi_until", {})
    for k in [k for k, t in until.items() if t and time.time() >= t]:
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

async def luck_say(ctx, text):
    await ctx.reply(text, mention_author=False)

@bot.command(name="luck", usage="luck <2.5x | off> [time: 10m, 2h, 1d]")
@owner_only
async def luck(ctx, amount: str = None, duration: str = None):
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
        if interaction.user.id not in OWNER_IDS:
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

# ================= INFO =================
INFO_COLOR = 0x1F2A44

def info_embed(user, title, description, sections, footer=None):
    e = discord.Embed(title=title, description=description, color=INFO_COLOR)
    e.set_author(name=user.name, icon_url=user.display_avatar.url)
    for name, rows in sections:
        width = max(len(cmd) for cmd, _ in rows)
        body = "\n".join(f"{cmd.ljust(width)}  {desc}" for cmd, desc in rows)
        e.add_field(name=name, value=f"```\n{body}\n```", inline=False)
    if footer:
        e.set_footer(text=footer)
    return e

INFO_SECTIONS = [
    ("BOARD GAMES", [
        ("$gm <bet>", "Find treasure, avoid bombs, cash out any time"),
        ("$mines <bet>", "One bomb, every diamond raises the profit"),
        ("S$mines <bet>", "Mines with a choice of board size"),
        ("$mt <bet>", "Money Tower, climb row by row"),
    ]),
    ("CARDS AND LUCK", [
        ("$bj <bet>", "Blackjack"),
        ("$slots <bet>", "Slot machine"),
        ("$hl <bet>", "Higher or lower"),
        ("$ht <bet>", "Heads or tail"),
        ("$cf <bet>", "Chicken fight"),
    ]),
    ("ROULETTE", [
        ("$roulette <amount> <bet>", "Join the open round, any number of bets"),
        ("Example", "$roulette 500 red   /   $roulette 150 0,6,odd"),
        ("Picks", "0-36, red, black, even, odd, 1-18, 19-36, 1-12, 13-24, 25-36, 1st, 2nd, 3rd"),
    ]),
    ("SCRATCH CARDS", [
        ("$sc", "Pick a card, enter an amount (bank only) and scratch"),
    ]),
    ("ECONOMY", [
        ("$bal [user]", "Cash and bank balance"),
        ("$dep / $with", "Deposit to or withdraw from the bank"),
        ("$work / $crime", "Quick earnings"),
        ("$rob <user>", "Rob another player's cash"),
        ("$pay <user> <amt>", "Send money to another player"),
        ("$top / $lb", "Leaderboard"),
        ("$shop", "Role shop"),
    ]),
]
INFO_FOOTER = "Amounts: number, half, all, 5k, 2.5m, 1b  |  <user> can be a mention, a user ID, or a reply with ping ON and the word 'a'"

AINFO_SECTIONS = [
    ("STAFF", [
        ("$addmoney <bank|cash> <user> <amt>", "Add money to a player"),
        ("$addmoneyrole <bank|cash> <role> <amt>", "Add money to every member of a role"),
        ("$resetmoney <bank|cash|all> <user> [amt]", "Set or reset a player's money"),
        ("$removemoney <bank|cash> <user> <amt>", "Remove money from a player"),
        ("$set-currency <emoji>", "Change the currency symbol"),
    ]),
    ("ADMIN", [
        ("$staff-role <role>", "Set which role counts as staff"),
        ("$setgamelogs <channel>", "Set the log channel"),
    ]),
    ("OWNER", [
        ("$setaddmoney <max|off>", "Limit how much staff can add per command"),
        ("$multi <game|all> <1-5|off> [time]", "Profit multiplier on wins"),
        ("$luck <1-10>x [time]", "Luck for every player"),
        ("$unluck", "Turn luck off"),
        ("$setlimit <number>", "Daily limit of add-money uses per staff member"),
        ("$unsetlimit", "Remove the daily limit"),
        ("$sc restart", "Restock all scratch cards (they also restock every day at 00:00)"),
        ("$reset-economy", "Reset everyone's money (asks for confirmation)"),
        ("$disable / $undisable <cmd|all>", "Block or unblock a command"),
    ]),
    ("BANG COMMANDS", [
        ("!set-role-member", "Role button panel (admin)"),
        ("!clear <amount>", "Delete up to 350 messages (clear role only)"),
    ]),
]

@bot.command(name="info")
async def info(ctx):
    await ctx.reply(embed=info_embed(ctx.author, "AMRAM CASINO  |  COMMAND GUIDE",
                                     "All commands start with `$`.", INFO_SECTIONS, INFO_FOOTER),
                    mention_author=False)

@bot.command(name="ainfo")
@staff_only
async def ainfo(ctx):
    await ctx.reply(embed=info_embed(ctx.author, "AMRAM CASINO  |  STAFF GUIDE",
                                     "Management commands.", AINFO_SECTIONS), mention_author=False)

bot.run(TOKEN)
