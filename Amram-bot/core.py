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
MINES_MULT = [1.1, 1.3, 1.6, 1.85, 2.2, 4.3, 6.2, 8.35]
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
MULTI_GAMES = ("gm", "mines", "s$mines", "mt", "bj", "slots", "roulette", "ht", "cf", "hl", "scratch", "heist", "poker")

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
backup_msg = None
loaded = asyncio.Event()   # created once here, so every module shares the same object
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
    if amount is None:              # just "$bj" with no amount: same answer as a bet that is too small
        await ctx.reply(f"The minimum bet is {MIN_BET}{cur()}!")
        return None
    bet = parse_amount(amount, u["cash"])
    if bet is None:
        return await reply(ctx, f"Usage: `${usage}` (min {MIN_BET})", RED)
    if bet < MIN_BET:
        await ctx.reply(f"The minimum bet is {MIN_BET}{cur()}!")
        return None
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
LOG_FOOTER = "Amram Casino | Activity Log"
BIG_WIN = 25_000_000          # a win/loss of this size or more is highlighted in the log

def bg(coro):
    t = asyncio.create_task(coro)
    _log_tasks.add(t)
    t.add_done_callback(_log_tasks.discard)

GAME_NAMES = {"gm": "Gold Mines", "mines": "Mines", "money tower": "Money Tower", "blackjack": "Blackjack",
              "slots": "Slots", "roulette": "Roulette", "heads or tail": "Heads or Tail",
              "chicken fight": "Chicken Fight", "higher or lower": "Higher or Lower", "heist": "Bank Heist",
              "rob": "Rob", "poker": "5-Card Draw Poker"}
LOG_TITLES = {
    "DEP": "Deposit", "WITH": "Withdrawal", "WORK": "Work", "CRIME": "Crime", "PAY": "Transfer",
    "SHOP": "Shop Purchase", "ADD MONEY": "Money Added", "REMOVE MONEY": "Money Removed",
    "RESET MONEY": "Money Reset", "ADD MONEY TO ROLE": "Money Added To Role", "LOG CHANNEL SET": "Log Channel Set",
}

def pretty(text):
    text = text.strip()
    return text.title() if text.isupper() else text[:1].upper() + text[1:]

def log_head(title):
    parts = [p.strip() for p in title.split("|")]
    base = LOG_TITLES.get(parts[0].upper()) or GAME_NAMES.get(parts[0].lower()) or pretty(parts[0])
    return " - ".join([base] + [pretty(p) for p in parts[1:]])

async def log_channel():
    cid = DB.get("log_channel")
    return bot.get_channel(cid) or await bot.fetch_channel(cid)

async def send_log(user, title, desc, color, fields=None, footer=None):
    """One log entry: title, optional description, a row of fields, user in the author line."""
    try:
        ch = await log_channel()
        e = discord.Embed(title=title, description=desc or None, color=color, timestamp=discord.utils.utcnow())
        e.set_author(name=f"{user.name} ({user.id})", icon_url=user.display_avatar.url)
        for name, value, inline in fields or []:
            e.add_field(name=name, value=value, inline=inline)
        e.set_footer(text=footer or LOG_FOOTER)
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
    scratch = game.lower().startswith("scratch")
    after = u["bank"] if scratch else u["cash"]
    before = after - net
    color = GREEN if net > 0 else RED if net < 0 else YELLOW
    outcome = "Win" if net > 0 else "Loss" if net < 0 else "Push"
    big = abs(net) >= BIG_WIN or (bet and abs(net) >= bet * 5 and abs(net) >= 1_000_000)
    name = GAME_NAMES.get(game.lower()) or pretty(game)
    fields = [("Outcome", f"{outcome} ({net:+,} {c})", True)]
    if bet:
        fields.append(("Bet", f"{fmt(bet)} {c}", True))
        fields.append(("Payout", f"x{(bet + net) / bet:.2f}", True))
    fields.append(("Bank" if scratch else "Cash", f"{fmt(before)} -> {fmt(after)} {c}", True))
    fields.append(("Net worth", f"{fmt(u['cash'] + u['bank'])} {c}", True))
    footer = LOG_FOOTER + (" | High stakes" if big else "")
    bg(send_log(user, name, detail, color, fields, footer))

def log_money(user, title, desc, color=BLUE):
    if not DB.get("log_channel"):
        return
    u, c = user_data(user.id), cur()
    fields = [("Cash", f"{fmt(u['cash'])} {c}", True), ("Bank", f"{fmt(u['bank'])} {c}", True)]
    bg(send_log(user, log_head(title), desc, color, fields))

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

def predict_access(uid):
    """Owners always have predict. Anyone else only while a $setpredict grant is active."""
    if uid in OWNER_IDS:
        return True
    grants = DB.get("predict_access", {})
    until = grants.get(str(uid))
    if until is None:
        return False
    if until == 0 or until > time.time():
        return True
    grants.pop(str(uid), None)                       # expired: remove the grant and switch his predict off
    DB.get("predict_on", {}).pop(str(uid), None)
    save()
    return False

async def dm_user(user, embed):
    try:
        await user.send(embed=embed)
    except Exception as ex:
        print("Predict DM failed:", repr(ex))

def spy(view):
    uid = view.user.id
    to_owner = bool(DB.get("predict"))
    to_player = uid not in OWNER_IDS and str(uid) in DB.get("predict_on", {}) and predict_access(uid)
    if not (to_owner or to_player):
        return
    note = "\n\n*(bottom row = first row)*" if hasattr(view, "safe_icon") else ""
    board = f"{board_text(view)}{note}"
    if to_owner:
        bg(dm_owner(discord.Embed(color=BLUE, title=f"🔮 {view.game_name}", timestamp=discord.utils.utcnow(), description=(
            f"**{view.user.name}** ({view.user.id}) | bet **{fmt(view.bet)}** {cur()}\n\n{board}"))))
    if to_player:       # a granted player only ever sees the boards of his own games
        bg(dm_user(view.user, discord.Embed(color=BLUE, title=f"🔮 {view.game_name}", timestamp=discord.utils.utcnow(), description=(
            f"Bet **{fmt(view.bet)}** {cur()}\n\n{board}"))))

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
    if ctx.channel.id not in ALLOWED_CHANNELS and not (ctx.command and ctx.command.name == "lottery" and ctx.channel.id == LOTTO_CHANNEL_ID):
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
    await start_web()
    disk_loop.start()
    backup_loop.start()
    sc_daily_loop.start()
    immunity_loop.start()
    lotto_loop.start()
    bot.add_view(LottoPanel())
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
