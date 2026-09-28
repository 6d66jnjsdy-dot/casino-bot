import discord, random, json, os, asyncio, io, signal, math, time
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands, tasks
from aiohttp import web

# ================= CONFIG =================
TOKEN = (os.environ.get("DISCORD_TOKEN") or os.environ.get("TOKEN") or "").strip().strip('"').strip("'")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(HERE, "data"))   # point this to a persistent volume if your host has one
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "economy.json")
CHANNELS = {1541567870591443026, 1502311424808980690}
OWNER_ID = 1537816435370229820
# The backup keeps everybody's money safe when the host wipes its disk (Render free, etc).
# By default the bot keeps ONE backup message in the OWNER's DMs (never in the game channels) and edits it.
# Set the BACKUP_CHANNEL_ID env var if you prefer a private channel instead.
BACKUP_CHANNEL_ID = int(os.environ.get("BACKUP_CHANNEL_ID") or 0)
MIN_BET = 150
EARN_MIN, EARN_MAX = 6500, 16000
DEALER_STANDS_ON = 13
EMPTY = "\u200e"   # blank button label
GREEN, RED, BLUE, YELLOW = 0x77B255, 0xC0392B, 0x3B82F6, 0xF1C40F   # GREEN = the green bar of the win message

EMOJI = {"bomb": "💣", "map": "🗺️", "diamond": "💎", "coin": "🪙", "stone": "🪨", "bag": "💰", "urn": "🏮"}
MULT = {"diamond": 3.5, "urn": 25, "stone": 1.1, "coin": 2, "bag": 5.5, "map": 1}
MINES_MULT = [1.1, 1.3, 1.6, 2, 2.2, 4.6, 7.6, 10.2]
MINES_COMPOUND = True   # True: every diamond multiplies the current total. False: the list is the total multiplier per click
SMINES_COMPOUND = False   # S$mines: False = the numbers are the total multiplier per click (True would multiply them together)
SMINES = {   # key: (columns, rows, mines, multiplier per click)   (one entry per safe cell)
    "2x2": (2, 2, 1, [1.4, 2.3, 4.3]),
    "4x4": (4, 4, 3, [1.2, 1.4, 1.5, 1.7, 2, 2.5, 2.8, 4.5, 5.7, 5.8, 6, 7, 12.3]),
    "5x4": (5, 4, 5, [1.2, 1.5, 1.8, 2, 2.3, 2.6, 2.9, 3.4, 3.6, 3.8, 3.9, 4, 4.2, 5.4, 19]),
}
CF_MIN, CF_MAX = 50, 84   # chicken fight win chance: starts at 50%, +1% per win, capped at 84%
ROB_FROM, ROB_PERCENT, ROB_FAIL, ROB_COOLDOWN = ("cash", "bank"), 0.8, 0.45, 360   # ROB_FAIL = 45% chance to get caught
SLOTS = ["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"]
SLOT_PAY = dict(zip(SLOTS, [3, 4, 5, 8, 15, 30]))
SLOTS_BOOST = 0.035    # +3.5 percentage points win chance in slots
BJ_WIN_NERF = 0.09     # blackjack: chance the dealer gets a re-draw when the player would win (about -2.5 points of win rate; raise/lower to tune)

# ================= DATABASE =================
def load():
    try:
        with open(DB_FILE) as f:
            return json.load(f)
    except Exception:
        return {"currency": "💸", "users": {}}

DB = load()
dirty = False        # the Discord backup needs an upload
disk_dirty = False   # the local file needs a write
backup_msg = None
loaded = None     # asyncio.Event, created in setup_hook
backup_lock = asyncio.Lock()
synced = False   # backups stay off until the restore finished, so an empty DB can never overwrite the backup

def _write_text(text):
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, DB_FILE)

def write_db():
    """Synchronous write (only used at restore time)."""
    _write_text(json.dumps(DB))

def save():
    """Marks the data as changed. The disk loop writes it (in a thread, never blocking the games)
    and the backup loop uploads it (only if the backup is available)."""
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
        return int(float(t) * mult)   # float() already understands 1e5 / 5e6 / 2.5e3
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
    if track:   # remember the running game, so the bet is refunded if the bot restarts mid-game
        DB.setdefault("pending", {})[str(ctx.message.id)] = {"uid": str(ctx.author.id), "bet": bet}
    save()
    return bet

def pending_done(token):
    """The game is settled: forget its pending bet (the caller saves right after)."""
    if token:
        DB.get("pending", {}).pop(token, None)

def pending_bump(token, amount):
    if token and token in DB.get("pending", {}):
        DB["pending"][token]["bet"] += amount

def cancel_game(user, token, bet):
    """The game could not even be shown to the player: give the bet back."""
    pending_done(token)
    user_data(user.id)["cash"] += bet
    save()

def refund_pending():
    """Games that were running when the bot stopped can't continue (buttons die): give the bets back."""
    pend = DB.get("pending") or {}
    for rec in pend.values():
        user_data(rec["uid"])["cash"] += rec["bet"]
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
    """Fire-and-forget: a slow / broken log channel can never slow down or break a game."""
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

# ================= BOT =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True   # needed by $addmoneyrole (enable "Server Members Intent" in the Developer Portal)
bot = commands.Bot(command_prefix=("$", "S$", "s$"), intents=intents, help_command=None)   # "S$mines" = the board-size game

def cmd_key(ctx):
    return "s$mines" if ctx.command.name == "mines" and ctx.prefix.lower() == "s$" else ctx.command.name

@bot.check
async def only_allowed_channels(ctx):
    await loaded.wait()
    if ctx.channel.id not in CHANNELS:
        return False
    if cmd_key(ctx) in DB.get("disabled", []) and ctx.author.id != OWNER_ID:
        return False   # disabled command: the bot stays completely silent
    return True

# ================= BACKUP =================
def backup_file():
    return discord.File(io.BytesIO(json.dumps(DB).encode()), filename="economy.json")

async def get_backup_channel():
    if BACKUP_CHANNEL_ID:
        return bot.get_channel(BACKUP_CHANNEL_ID) or await bot.fetch_channel(BACKUP_CHANNEL_ID)
    return await (await bot.fetch_user(OWNER_ID)).create_dm()   # default: the owner's DMs

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
                await backup_msg.pin()   # pinned = always found again after a restart
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
    """Tiny web page so a free host (Render) + an uptime pinger keep the bot awake."""
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
    if random.randint(1, 7) == 1:
        tiles[tiles.index("stone")] = "urn"
    random.shuffle(tiles)
    return tiles

BUILDERS = {"gm": gm_board, "mines": lambda: shuffled(bomb=1, diamond=8)}
for _k, (_w, _h, _m, _) in SMINES.items():
    BUILDERS[f"s{_k}"] = lambda m=_m, n=_w * _h: shuffled(bomb=m, diamond=n - m)

LAST_BOMBS = {}   # (user id, game) -> bomb positions of that user's previous board

def take(uid, key):
    """New board whose bombs are NOT in (mostly) the same places as the player's previous board."""
    prev = LAST_BOMBS.get((uid, key), set())
    for _ in range(30):
        board = BUILDERS[key]()
        bombs = {i for i, k in enumerate(board) if k == "bomb"}
        if not prev or len(prev & bombs) <= len(bombs) / 2:
            break
    LAST_BOMBS[(uid, key)] = bombs
    return board

# ================= MINES / GM =================
class Tile(discord.ui.Button):
    def __init__(self, idx, cols):
        super().__init__(style=discord.ButtonStyle.secondary, label=EMPTY, row=idx // cols)
        self.idx = idx

    async def callback(self, interaction):
        await self.view.click(interaction, self.idx)

class BoardView(discord.ui.View):
    cols, header = 5, "\u200b"
    reveal_on_cashout = True   # False = a cash out does NOT show where the bombs / diamonds were
    mines_style = False        # True = result message like the mines screenshot
    game_name = "game"

    def __init__(self, user, bet, token=None):
        super().__init__(timeout=120)
        self.user, self.bet, self.token = user, bet, token
        self.board = self.make_board()
        self.revealed, self.profit = set(), 0
        self.done = False
        self.version = 0                  # bumps on every click, so only the newest board gets drawn
        self.edit_lock = asyncio.Lock()   # edits go out one at a time, in order
        self.message = None
        self.tiles = [Tile(i, self.cols) for i in range(len(self.board))]
        row = len(self.tiles) // self.cols
        self.cash_btn = discord.ui.Button(style=discord.ButtonStyle.success, label="Cashout", row=row)
        self.cash_btn.callback = lambda i: self.finish(i, False)
        self.profit_btn = discord.ui.Button(style=discord.ButtonStyle.primary, disabled=True,
                                            row=row, label="Profit: 0", emoji=cur())
        for b in (*self.tiles, self.cash_btn, self.profit_btn):
            self.add_item(b)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True

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
        # acknowledge instantly (Discord gives only 3 seconds), then update the state with no awaits in between
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
            # everything found: lock the bombs but keep Cashout open, the player collects it themselves
            # (if they wait too long the game times out and pays out automatically)
            for i, t in enumerate(self.tiles):
                if i not in self.revealed:
                    t.disabled = True
        self.version += 1
        v = self.version
        async with self.edit_lock:
            if v != self.version or self.done:
                return   # a newer click will draw the latest board
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

    def embed(self, lost):
        if not self.mines_style:
            return result_embed(self.user, not lost, self.bet if lost else self.profit)
        amt = self.bet if lost else int(self.profit)
        line = f"-You lost {fmt(amt)} {cur()}" if lost else f"+You won and got {fmt(amt)} {cur()}"
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
        kw = dict(content=self.header, embed=self.embed(lost), view=self)
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
            await self.message.edit(content=self.header, embed=self.embed(False), view=self)

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
    mines_style = True
    game_name = "mines"

    def make_board(self):
        return take(self.user.id, "mines")

    def earn(self, kind):
        n = len(self.revealed)
        self.profit = self.bet * ((math.prod(MINES_MULT[:n]) if MINES_COMPOUND else MINES_MULT[n - 1]) - 1)

class SMines(BoardView):
    reveal_on_cashout = False
    mines_style = True

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
            if self.chosen:   # double click: never start two games
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
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.chosen:
            return
        pending_done(self.token)
        user_data(self.user.id)["cash"] += self.bet
        save()
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

# ================= BLACKJACK =================
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♣", "♠", "♥", "♦"]          # same row order as cards.png
class BusySet:
    """Players that are in a game. A lock older than 10 minutes is stale (a game never lasts that long) and frees itself."""
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

# ---------- card images ----------
# Cards are drawn at full size on a wide canvas. Discord shrinks the wide image to fit the message,
# so the cards look small but stay sharp. TABLE_W: bigger number = smaller cards on screen.
SHEET = Image.open(os.path.join(HERE, "cards.png")).convert("RGBA")
SW, SH = 66, 93
TABLE_W = 960
MASK = Image.new("L", (SW, SH), 0)
ImageDraw.Draw(MASK).rounded_rectangle([0, 0, SW - 1, SH - 1], radius=7, fill=255)

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
    x, y = RANKS.index(r) * SW, SUITS.index(s) * SH
    im = SHEET.crop((x, y, x + SW, y + SH))
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
        if self.done:   # a late / double click after the game ended must never pay twice
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
            # lower the player's win rate: sometimes the dealer re-draws his hidden card + hits
            if self.player_wins() and random.random() < BJ_WIN_NERF:
                up = self.dealer[0]   # the visible card never changes
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
        # the state is already changed by the caller. Acknowledge at once (3s limit), then draw + upload the image
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
    except Exception:   # never leave the player locked out / without the bet
        if not view.done:
            cancel_game(ctx.author, view.token, bet)
        BUSY.discard(ctx.author.id)
        raise
    if not natural:
        view.message = msg

# ================= SLOTS =================
@bot.command(name="slots", aliases=["slot"], usage="slots <amount | half | all>")
async def slots(ctx, amount: str = None):
    if ctx.author.id in BUSY:
        return await reply(ctx, "You already have a game running.", RED)
    bet = await take_bet(ctx, amount, "slots <amount | half | all>")
    if not bet:
        return
    BUSY.add(ctx.author.id)
    try:
        final = [random.choice(SLOTS) for _ in range(3)]
        # 3 different symbols = loss (120/216 of spins). Turn some of those into a pair to raise the win chance by SLOTS_BOOST
        if len(set(final)) == 3 and random.random() < SLOTS_BOOST / (120 / 216):
            final[1] = final[0]
        top = max(final.count(s) for s in SLOTS)
        mult = SLOT_PAY[final[0]] if top == 3 else 1.5 if top == 2 else 0
        win = int(bet * mult)
        user_data(ctx.author.id)["cash"] += win   # paid BEFORE the animation: a Discord error can never eat the bet
        save()
        log_game(ctx.author, "slots", bet, win - bet)
        machine = lambda reels: "🎰  ┃ " + " ┃ ".join(reels) + " ┃  🎰"
        # reel 1 stops at 3s, reel 2 at 4s, reel 3 at 5s
        frame = lambda t: make_embed(
            ctx.author,
            f"**Slots**\n\n{machine([final[i] if t >= 3 + i else random.choice(SLOTS) for i in range(3)])}\n\n⏳ **{5 - t}s**",
            YELLOW)
        result = result_embed(ctx.author, win > 0, win - bet if win else bet, f"{machine(final)}\n\n")
        try:
            msg = await ctx.reply(embed=frame(0), mention_author=False)
            for t in range(1, 5):
                await asyncio.sleep(1)
                await msg.edit(embed=frame(t))
            await asyncio.sleep(1)
            await msg.edit(embed=result)
        except discord.HTTPException:
            pass   # money is already settled
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
        if self.settled:   # double click: never pay twice
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
    await reply(ctx, f"You paid {fmt(amt)} {cur()} to {member.name}.", GREEN)

@bot.command(name="rob", usage="rob @user", cooldown_after_parsing=True)
@commands.cooldown(1, ROB_COOLDOWN, commands.BucketType.user)
async def rob(ctx, member: discord.Member):
    me, target = user_data(ctx.author.id), user_data(member.id)
    loot = {k: int(target[k] * ROB_PERCENT) for k in ROB_FROM}
    if member.bot or member.id == ctx.author.id or not sum(loot.values()):
        ctx.command.reset_cooldown(ctx)
        return await reply(ctx, "You can't rob this user." if member.bot or member.id == ctx.author.id
                           else f"{member.name} has nothing to rob.", RED)
    if me["cash"] + me["bank"] > 0 and random.random() < ROB_FAIL:   # 45% to get caught if you have any money
        lost = me["cash"] + me["bank"]
        me["cash"] = me["bank"] = 0
        save()
        log_game(ctx.author, "rob (got caught)", 0, -lost)
        return await reply(ctx, "You got caught and lost all your money!", RED)
    for k, v in loot.items():
        target[k] -= v
    me["cash"] += sum(loot.values())
    save()
    log_game(ctx.author, f"rob {member.name}", 0, sum(loot.values()))
    await reply(ctx, f"You robbed {fmt(sum(loot.values()))} {cur()} from {member.name}!", GREEN)

@bot.command(name="top", aliases=["lb"])
async def top(ctx):
    ranked = sorted(DB["users"].items(), key=lambda kv: kv[1]["cash"] + kv[1]["bank"], reverse=True)[:10]
    lines = []
    for n, (uid, d) in enumerate(ranked, 1):
        m = bot.get_user(int(uid))
        lines.append(f"**{n}.** {m.name if m else f'<@{uid}>'} — {fmt(d['cash'] + d['bank'])} {cur()}")
    await reply(ctx, "\n".join(lines) or "Nobody has any money yet.", BLUE)

# ================= STAFF / ADMIN =================
class NotStaff(commands.CheckFailure):
    pass

def admin_or_owner(ctx):
    if ctx.author.id == OWNER_ID or ctx.author.guild_permissions.administrator:
        return True
    raise commands.MissingPermissions(["administrator"])

def is_staff(ctx):
    """Owner, Administrators, or anyone with the role set by $staff-role."""
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
    amount = parse_amount(amount, u.get(where, 0) if sign < 0 else 0)   # 1e5 / 5k / 2m all work
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
owner_only = commands.check(lambda ctx: ctx.author.id == OWNER_ID)   # anyone else is ignored silently

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
    if key in ("disable", "enable"):   # "enable" is also "undisable"
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

INFO = """**🎮 משחקים** (הימור: סכום / `half` / `all`, מינימום 150. אפשר גם `5k`, `2.5m`, `1e5`, `5e6`)
• `$gm` – לוח של 20 משבצות עם אוצרות ופצצות. חושפים משבצות ואוספים רווח, ואפשר לצאת עם Cashout בכל רגע. פצצה מפסידה את ההימור, ומפה חושפת עוד משבצות בטוחות.
• `$mines` – לוח 3x3 עם פצצה אחת. כל יהלום מגדיל את הרווח, ו-Cashout מוציא אותו בלי לחשוף את הלוח. פצצה מפסידה הכול.
• `S$mines` – כמו mines, אבל בוחרים גודל לוח: 2x2 עם פצצה אחת, 4x4 עם שלוש פצצות, 5x4 עם חמש פצצות.
• `$bj` – בלאק ג'ק מול הדילר עם Hit, Stand, Double ו-Split.
• `$slots` – מכונת מזל עם אנימציה. שלושה סמלים זהים זה ניצחון גדול, שניים זהים זה ניצחון קטן.
• `$ht` – עץ או פלי. בוחרים Head או Tail בכפתור.
• `$cf` – קרב תרנגולות. הסיכוי לנצח מתחיל ב-50%, עולה ב-1% אחרי כל ניצחון עד מקסימום 84%, וחוזר ל-50% אחרי הפסד.

**💰 כלכלה**
• `$bal [@user]` – כסף בחוץ ובבנק.
• `$dep` / `$with` – הפקדה לבנק ומשיכה ממנו (למשל `$with 1e5`).
• `$work` / `$crime` – הרווחה מהירה, פעם בשתי דקות.
• `$rob @user` – שוד. קולדאון 6 דקות ושודדים את רוב הכסף של הקורבן. למי שיש כסף יש 45% להיתפס ולהתאפס.
• `$pay @user סכום` – העברת כסף לשחקן אחר.
• `$top` / `$lb` – טבלת העשירים.

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
