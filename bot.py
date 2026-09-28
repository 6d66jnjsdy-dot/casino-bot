import discord, random, json, os, asyncio, io, signal, math
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont
from discord.ext import commands, tasks

# ================= CONFIG =================
TOKEN = (os.environ.get("DISCORD_TOKEN") or os.environ.get("TOKEN") or "").strip().strip('"').strip("'")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(HERE, "data"))   # point this to a persistent volume if your host has one
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE = os.path.join(DATA_DIR, "economy.json")
CHANNELS = {1541567870591443026, 1502311424808980690}
OWNER_ID = 1537816435370229820
BACKUP_CHANNEL_ID = int(os.environ.get("BACKUP_CHANNEL_ID") or 1541567870591443026)
MIN_BET = 150
EARN_MIN, EARN_MAX = 6500, 16000
DEALER_STANDS_ON = 13
CLICK_DELAY = 0.3
EMPTY = "\u200e"   # blank button label
GREEN, RED, BLUE, YELLOW = 0x43B581, 0xC0392B, 0x3B82F6, 0xF1C40F

EMOJI = {"bomb": "💣", "map": "🗺️", "diamond": "💎", "coin": "🪙", "stone": "🪨", "bag": "💰", "urn": "🏮"}
MULT = {"diamond": 3.5, "urn": 25, "stone": 1.1, "coin": 2, "bag": 5.5, "map": 1}
MINES_MULT = [1.1, 1.3, 1.6, 2, 2.2, 4.6, 7.6, 10.2]
MINES_COMPOUND = True   # True: every diamond multiplies the current total. False: the list is the total multiplier per click
SMINES_COMPOUND = False   # S$mines: False = the numbers are the total multiplier per click (True would multiply them together)
SMINES = {   # key: (columns, rows, mines, multiplier per click)
    "2x2": (2, 2, 1, [1.4, 2.3, 4.3]),
    "4x4": (4, 4, 2, [1.2, 1.4, 1.5, 1.7, 2, 2.5, 2.8, 4.5, 5.7, 5.8, 6, 6.4, 7, 12.3]),
    "5x4": (5, 4, 3, [1.2, 1.5, 1.8, 2, 2.3, 2.6, 2.9, 3.4, 3.6, 3.8, 3.9, 4, 4.2, 4.6, 5.4, 19]),
}
ROB_FROM, ROB_PERCENT, ROB_FAIL, ROB_COOLDOWN = ("cash", "bank"), 0.8, 0.45, 360
SLOTS = ["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"]
SLOT_PAY = dict(zip(SLOTS, [3, 4, 5, 8, 15, 30]))

# ================= DATABASE =================
def load():
    try:
        with open(DB_FILE) as f:
            return json.load(f)
    except Exception:
        return {"currency": "💸", "users": {}}

DB = load()
dirty = False
backup_msg = None
loaded = None     # asyncio.Event, created in setup_hook
backup_lock = asyncio.Lock()
synced = False   # backups stay off until the restore finished, so an empty DB can never overwrite the backup

def write_db():
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(DB, f)
    os.replace(tmp, DB_FILE)

def save():
    global dirty
    write_db()
    dirty = True   # the backup loop uploads it (one edit of the same message, never a new one)

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
    if t[-1:] in ("k", "m"):
        mult, t = (1000 if t[-1] == "k" else 1_000_000), t[:-1]
    try:
        return int(float(t) * mult)
    except ValueError:
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

async def take_bet(ctx, amount, usage):
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
    save()
    return bet

# ================= BOT =================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=("$", "S$", "s$"), intents=intents, help_command=None)   # "S$mines" = the board-size game

def cmd_key(ctx):
    return "s$mines" if ctx.command.name == "mines" and ctx.prefix.lower() == "s$" else ctx.command.name

@bot.check
async def only_allowed_channels(ctx):
    await loaded.wait()
    if ctx.channel.id not in CHANNELS:
        return False
    if cmd_key(ctx) in DB.get("disabled", []) and ctx.author.id != OWNER_ID:
        raise commands.DisabledCommand()
    return True

# ================= BACKUP =================
def backup_file():
    return discord.File(io.BytesIO(json.dumps(DB).encode()), filename="economy.json")

async def get_backup_channel():
    return bot.get_channel(BACKUP_CHANNEL_ID) or await bot.fetch_channel(BACKUP_CHANNEL_ID)

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
    if not BACKUP_CHANNEL_ID:
        return print("BACKUP_CHANNEL_ID is not set - backup disabled!")
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
        print("Backup restore failed (backups disabled to protect data):", repr(e))

async def backup_now():
    global backup_msg, dirty
    if not (BACKUP_CHANNEL_ID and dirty and synced):
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

async def graceful_shutdown():
    await backup_now()
    await bot.close()

async def setup_hook():
    global loaded
    loaded = asyncio.Event()
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
        loaded.set()
    print("Logged in as", bot.user)

@bot.event
async def on_command_error(ctx, err):
    if isinstance(err, commands.DisabledCommand):
        return await reply(ctx, "This command is currently disabled.", RED)
    if isinstance(err, commands.MissingPermissions):
        return await reply(ctx, "You need Administrator permission to use this command.", RED)
    if isinstance(err, commands.CommandOnCooldown):
        m, s = divmod(int(err.retry_after) + 1, 60)
        return await reply(ctx, f"Try again in **{f'{m}m ' if m else ''}{s}s**.", RED)
    if isinstance(err, (commands.MissingRequiredArgument, commands.BadArgument)):
        return await reply(ctx, f"Usage: `${ctx.command.usage or ctx.command.name}`", RED)
    if not isinstance(err, (commands.CommandNotFound, commands.CheckFailure)):
        print("Error:", repr(err))

# ================= BOARDS (+ owner predictions) =================
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

PREDICT = {}   # (user id, game) -> the board that user's next game will use

def take(uid, key):
    return PREDICT.pop((uid, key), None) or BUILDERS[key]()

# ================= MINES / GM =================
class Tile(discord.ui.Button):
    def __init__(self, idx, cols):
        super().__init__(style=discord.ButtonStyle.secondary, label=EMPTY, row=idx // cols)
        self.idx = idx

    async def callback(self, interaction):
        await self.view.click(interaction, self.idx)

class BoardView(discord.ui.View):
    cols, header = 5, "\u200b"

    def __init__(self, user, bet):
        super().__init__(timeout=120)
        self.user, self.bet = user, bet
        self.board = self.make_board()
        self.revealed, self.profit = set(), 0
        self.done = self.busy = False
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
        if self.done or self.busy:
            if not interaction.response.is_done():
                await interaction.response.defer()
            return
        self.busy = True
        await interaction.response.defer()
        await asyncio.sleep(CLICK_DELAY)
        kind = self.board[idx]
        self.reveal(idx)
        self.busy = False
        if kind == "bomb":
            return await self.finish(interaction, True)
        self.after(kind)
        if all(k == "bomb" or i in self.revealed for i, k in enumerate(self.board)):
            return await self.finish(interaction, False)
        await interaction.edit_original_response(content=self.header, view=self)

    def payout(self):
        user_data(self.user.id)["cash"] += self.bet + int(self.profit)
        save()

    def reveal_all(self):
        for i, kind in enumerate(self.board):
            t = self.tiles[i]
            t.emoji, t.disabled = EMOJI[kind], True
            if kind == "bomb":
                t.style = discord.ButtonStyle.danger
        self.cash_btn.disabled = True

    def embed(self, lost):
        return result_embed(self.user, not lost, self.bet if lost else self.profit)

    async def finish(self, interaction, lost):
        if self.done:
            return
        self.done = True
        if not lost:
            self.payout()
        self.reveal_all()
        self.stop()
        kw = dict(content=self.header, embed=self.embed(lost), view=self)
        if interaction.response.is_done():
            await interaction.edit_original_response(**kw)
        else:
            await interaction.response.edit_message(**kw)

    async def on_timeout(self):
        if self.done:
            return
        self.done = True
        self.payout()
        self.reveal_all()
        if self.message:
            await self.message.edit(content=self.header, embed=self.embed(False), view=self)

class GoldMines(BoardView):
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

    def make_board(self):
        return take(self.user.id, "mines")

    def earn(self, kind):
        n = len(self.revealed)
        self.profit = self.bet * ((math.prod(MINES_MULT[:n]) if MINES_COMPOUND else MINES_MULT[n - 1]) - 1)

class SMines(BoardView):
    def __init__(self, user, bet, key):
        self.key = key
        self.cols, rows, self.mines, self.table = SMINES[key]
        self.cells = self.cols * rows
        super().__init__(user, bet)

    def make_board(self):
        return take(self.user.id, f"s{self.key}")

    def earn(self, kind):
        n = min(len(self.revealed), len(self.table))
        self.profit = self.bet * ((math.prod(self.table[:n]) if SMINES_COMPOUND else self.table[n - 1]) - 1)

class SizeView(discord.ui.View):
    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user, self.bet, self.message, self.chosen = user, bet, None, False
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
            self.chosen = True
            self.stop()
            game = SMines(self.user, self.bet, key)
            game.message = interaction.message
            await interaction.response.edit_message(content=game.header, embed=None, view=game)
        return cb

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.chosen:
            return
        user_data(self.user.id)["cash"] += self.bet
        save()
        if self.message:
            await self.message.edit(embed=discord.Embed(description="Timed out, your bet was returned.", color=RED), view=None)

async def start_board(ctx, cls, amount, usage):
    bet = await take_bet(ctx, amount, usage)
    if bet:
        view = cls(ctx.author, bet)
        view.message = await ctx.reply(view.header, view=view, mention_author=False)

@bot.command(name="gm", usage="gm <amount | half | all>")
async def gm(ctx, amount: str = None):
    await start_board(ctx, GoldMines, amount, "gm <amount | half | all>")

@bot.command(name="mines", usage="mines <amount | half | all>")
async def mines(ctx, amount: str = None):
    usage = "mines <amount | half | all>"
    if ctx.prefix.lower() != "s$":
        return await start_board(ctx, Mines, amount, usage)
    bet = await take_bet(ctx, amount, usage)
    if bet:
        view = SizeView(ctx.author, bet)
        view.message = await ctx.reply(embed=view.embed(), view=view, mention_author=False)

# ================= BLACKJACK =================
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♣", "♠", "♥", "♦"]          # same row order as cards.png
BUSY = set()

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
TABLE_W = 800
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
    def __init__(self, user, bet):
        super().__init__(timeout=120)
        self.user = user
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
        user_data(self.user.id)["cash"] += returned
        save()
        BUSY.discard(self.user.id)
        self.refresh_buttons()

    def check_naturals(self):
        p, d = hand_value(self.hands[0]["cards"]) == 21, hand_value(self.dealer) == 21
        if not (p or d):
            return False
        bet = self.hands[0]["bet"]
        self.pay(bet if p and d else int(bet * 2.5) if p else 0, bet)
        return True

    def finalize(self):
        if any(not h["bust"] for h in self.hands):
            while hand_value(self.dealer) < DEALER_STANDS_ON:
                self.dealer.append(self.deck.pop())
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
        e, f = self.render()
        await interaction.response.edit_message(embed=e, attachments=[f], view=self)

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
    bet = await take_bet(ctx, amount, "bj <amount | half | all>")
    if not bet:
        return
    BUSY.add(ctx.author.id)
    view = BlackjackView(ctx.author, bet)
    natural = view.check_naturals()
    e, f = view.render()
    msg = await ctx.send(embed=e, file=f, view=view)
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
        machine = lambda reels: "🎰  ┃ " + " ┃ ".join(reels) + " ┃  🎰"
        # reel 1 stops at 3s, reel 2 at 4s, reel 3 at 5s
        frame = lambda t: make_embed(
            ctx.author,
            f"**Slots**\n\n{machine([final[i] if t >= 3 + i else random.choice(SLOTS) for i in range(3)])}\n\n⏳ **{5 - t}s**",
            YELLOW)
        msg = await ctx.reply(embed=frame(0), mention_author=False)
        for t in range(1, 5):
            await asyncio.sleep(1)
            await msg.edit(embed=frame(t))
        await asyncio.sleep(1)

        top = max(final.count(s) for s in SLOTS)
        mult = SLOT_PAY[final[0]] if top == 3 else 1.5 if top == 2 else 0
        win = int(bet * mult)
        user_data(ctx.author.id)["cash"] += win
        save()
        await msg.edit(embed=result_embed(ctx.author, win > 0, win - bet if win else bet, f"{machine(final)}\n\n"))
    finally:
        BUSY.discard(ctx.author.id)

# ================= HEADS OR TAIL / CHICKEN FIGHT =================
class CoinFlip(discord.ui.View):
    def __init__(self, user, bet):
        super().__init__(timeout=60)
        self.user, self.bet, self.message = user, bet, None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True

    async def flip(self, interaction, pick):
        land = random.choice(("Head", "Tail"))
        won = pick == land
        if won:
            user_data(self.user.id)["cash"] += self.bet * 2
            save()
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
        user_data(self.user.id)["cash"] += self.bet
        save()
        BUSY.discard(self.user.id)
        if self.message:
            await self.message.edit(embed=make_embed(self.user, "Timed out, your bet was returned.", RED), view=None)

@bot.command(name="ht", usage="ht <amount | half | all>")
async def ht(ctx, amount: str = None):
    if ctx.author.id in BUSY:
        return await reply(ctx, "You already have a game running.", RED)
    bet = await take_bet(ctx, amount, "ht <amount | half | all>")
    if not bet:
        return
    BUSY.add(ctx.author.id)
    view = CoinFlip(ctx.author, bet)
    e = make_embed(ctx.author, f"🍀 **CoinFlip** 🍀\n\n**Betting Amount:** `{fmt(bet)}`\n\nChoose head or tail (עץ או פאלי)", YELLOW)
    view.message = await ctx.reply(embed=e, view=view, mention_author=False)

@bot.command(name="cf", usage="cf <amount | half | all>")
async def cf(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "cf <amount | half | all>")
    if not bet:
        return
    u, c = user_data(ctx.author.id), cur()
    strength = u.get("chicken", 50)
    if random.randint(1, 100) <= strength:
        u["cash"] += bet * 2
        u["chicken"] = strength = min(75, strength + 1)
        desc = (f"Your chicken won the fight, you won {fmt(bet)} {c}🐓!\n\n"
                f"Your chicken's strength (chance of winning): {strength}%\n"
                f"You now have {fmt(u['cash'])} {c}")
        color = GREEN
    else:
        u["chicken"] = 50
        desc, color = f"Your chicken lost the fight... You lost {fmt(bet)} {c}🐓.", RED
    save()
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
    if me["cash"] + me["bank"] > 0 and random.random() < ROB_FAIL:
        me["cash"] = me["bank"] = 0
        save()
        return await reply(ctx, "You got caught and lost all your money!", RED)
    for k, v in loot.items():
        target[k] -= v
    me["cash"] += sum(loot.values())
    save()
    await reply(ctx, f"You robbed {fmt(sum(loot.values()))} {cur()} from {member.name}!", GREEN)

@bot.command(name="top", aliases=["lb"])
async def top(ctx):
    ranked = sorted(DB["users"].items(), key=lambda kv: kv[1]["cash"] + kv[1]["bank"], reverse=True)[:10]
    lines = []
    for n, (uid, d) in enumerate(ranked, 1):
        m = bot.get_user(int(uid))
        lines.append(f"**{n}.** {m.name if m else f'<@{uid}>'} — {fmt(d['cash'] + d['bank'])} {cur()}")
    await reply(ctx, "\n".join(lines) or "Nobody has any money yet.", BLUE)

# ================= ADMIN =================
async def change_money(ctx, where, member, amount, sign):
    where = where.lower()
    if where not in ("bank", "cash"):
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    u = user_data(member.id)
    amount = min(amount, u[where]) if sign < 0 else amount
    u[where] += sign * amount
    save()
    await reply(ctx, f"{'Added' if sign > 0 else 'Removed'} {fmt(amount)} {cur()} "
                     f"{'to' if sign > 0 else 'from'} {member.name}'s {where}.", GREEN)

@bot.command(name="addmoney", usage="addmoney <bank|cash> @user <amount>")
@commands.has_permissions(administrator=True)
async def addmoney(ctx, where: str, member: discord.Member, amount: int):
    await change_money(ctx, where, member, amount, 1)

@bot.command(name="removemoney", usage="removemoney <bank|cash> @user <amount>")
@commands.has_permissions(administrator=True)
async def removemoney(ctx, where: str, member: discord.Member, amount: int):
    await change_money(ctx, where, member, amount, -1)

@bot.command(name="currency", usage="currency <emoji>")
@commands.has_permissions(administrator=True)
async def currency(ctx, symbol: str = None):
    if symbol is None:
        return await reply(ctx, f"Current currency: {cur()}\nChange it with `$currency <emoji>`", BLUE)
    DB["currency"] = symbol
    save()
    await reply(ctx, f"Currency changed to {symbol}", GREEN)

# ================= OWNER: DISABLE / ENABLE =================
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
    if key in ("disable", "enable"):
        return await reply(ctx, "You can't disable this command.", RED)
    if key not in off:
        off.append(key)
        save()
    await reply(ctx, f"`{key}` is now disabled.", GREEN)

@bot.command(name="enable", usage="enable <command | all>")
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

@bot.command(name="predict")
@owner_only
async def predict(ctx):
    grid = lambda key, cols: "\n".join(
        " ".join(EMOJI[k] for k in PREDICT[(ctx.author.id, key)][i:i + cols])
        for i in range(0, len(PREDICT[(ctx.author.id, key)]), cols))
    for key, build in BUILDERS.items():
        PREDICT.setdefault((ctx.author.id, key), build())
    parts = [f"**$gm**\n{grid('gm', 5)}\n" + " · ".join(f"{EMOJI[k]} x{v:g}" for k, v in MULT.items() if k != "map") + " · 🗺️ map",
             f"**$mines**\n{grid('mines', 3)}"]
    parts += [f"**S$mines {k}**\n{grid(f's{k}', w)}" for k, (w, _, _, _) in SMINES.items()]
    try:
        await ctx.author.send(embed=make_embed(ctx.author, "\n\n".join(parts) + "\n\n*Used by your next game of each type.*", BLUE, "Predict"))
    except discord.Forbidden:
        return await reply(ctx, "I can't DM you. Open your DMs first.", RED)
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass

INFO = """**🎮 משחקים** (הימור: סכום / `half` / `all`, מינימום 150)
• `$gm` – לוח של 20 משבצות עם אוצרות ופצצות. חושפים משבצות ואוספים רווח, ואפשר לצאת עם Cashout בכל רגע. פצצה מפסידה את ההימור, ומפה חושפת עוד משבצות בטוחות.
• `$mines` – לוח 3x3 עם פצצה אחת. כל יהלום מגדיל את הרווח, ו-Cashout מוציא אותו. פצצה מפסידה הכול.
• `S$mines` – כמו mines, אבל בוחרים גודל לוח: 2x2 עם פצצה אחת, 4x4 עם שתיים, 5x4 עם שלוש. יותר פצצות, יותר סיכון ורווח.
• `$bj` – בלאק ג'ק מול הדילר עם Hit, Stand, Double ו-Split.
• `$slots` – מכונת מזל עם אנימציה. שלושה סמלים זהים זה ניצחון גדול, שניים זהים זה ניצחון קטן.
• `$ht` – עץ או פלי. בוחרים Head או Tail בכפתור.
• `$cf` – קרב תרנגולות. הסיכוי לנצח עולה כשמנצחים ברצף וחוזר להתחלה אחרי הפסד.

**💰 כלכלה**
• `$bal [@user]` – כסף בחוץ ובבנק.
• `$dep` / `$with` – הפקדה לבנק ומשיכה ממנו.
• `$work` / `$crime` – הרווחה מהירה, פעם בשתי דקות.
• `$rob @user` – שוד. קולדאון 6 דקות ושודדים את רוב הכסף של הקורבן. למי שיש כסף יש סיכוי גבוה להיתפס ולהתאפס.
• `$pay @user סכום` – העברת כסף לשחקן אחר.
• `$top` / `$lb` – טבלת העשירים.

**🛠 אדמין**
• `$addmoney` / `$removemoney bank|cash @user סכום` – הוספה או הורדה של כסף.
• `$currency אימוג'י` – שינוי סמל המטבע.
• `$info` – ההודעה הזאת.
• `$disable` / `$enable` – חסימה ושחרור של פקודה (רק לבעלים).

הבוט עובד רק בחדרים המיועדים."""

@bot.command(name="info")
@commands.has_permissions(administrator=True)
async def info(ctx):
    await ctx.reply(embed=make_embed(ctx.author, INFO, BLUE, "מדריך הבוט"), mention_author=False)

bot.run(TOKEN)
