import discord, random, json, os, asyncio
from discord.ext import commands

# ================= CONFIG =================
TOKEN = os.environ.get("DISCORD_TOKEN") or os.environ.get("TOKEN") or ""
TOKEN = TOKEN.strip().strip('"').strip("'")

DB_FILE = os.environ.get("DB_FILE", "economy.json")  # on Render use /data/economy.json with a Disk
MIN_BET = 150
EARN_MIN, EARN_MAX = 6500, 16000       # $crime / $work
CLICK_DELAY = 0.3                       # loading delay between clicks (seconds)

GREEN = 0x43B581
RED = 0xC0392B
BLUE = 0x3B82F6

EMOJI = {"bomb": "💣", "map": "🗺️", "diamond": "💎", "coin": "🪙",
         "stone": "🪨", "bag": "💰", "urn": "🏮"}
# every hit adds bet * (mult - 1) to profit (it does NOT multiply the previous profit)
MULT = {"diamond": 3.5, "urn": 25, "stone": 1.1, "coin": 2, "bag": 5.5, "map": 1}

# ================= DATABASE =================
def load():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"currency": "💸", "users": {}}

DB = load()

def save():
    with open(DB_FILE, "w") as f:
        json.dump(DB, f)

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
    if t == "all":
        return available
    if t == "half":
        return available // 2
    mult = 1
    if t.endswith("k"):
        mult, t = 1000, t[:-1]
    elif t.endswith("m"):
        mult, t = 1_000_000, t[:-1]
    try:
        return int(float(t) * mult)
    except ValueError:
        return None

# ================= EMBEDS =================
def make_embed(user, desc, color, title=None):
    e = discord.Embed(description=desc, color=color)
    if title:
        e.title = title
    e.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    return e

async def reply(ctx, desc, color):
    await ctx.reply(embed=make_embed(ctx.author, desc, color), mention_author=False)

# ================= GAME =================
def make_board():
    tiles = (["map"] + ["bomb"] * 11 + ["stone"] * 3 +
             ["coin"] * 2 + ["bag"] + ["diamond"] * 2)
    if random.randint(1, 7) == 1:                # 1 in 7: urn replaces one stone
        tiles[tiles.index("stone")] = "urn"
    random.shuffle(tiles)
    return tiles

class Tile(discord.ui.Button):
    def __init__(self, idx):
        super().__init__(style=discord.ButtonStyle.secondary,
                         label="\u200b", row=idx // 5)
        self.idx = idx

    async def callback(self, interaction: discord.Interaction):
        await self.view.click(interaction, self.idx)

class CashoutButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.success,
                         label="Cashout", row=4)

    async def callback(self, interaction: discord.Interaction):
        await self.view.finish(interaction, lost=False)

class GameView(discord.ui.View):
    def __init__(self, user, bet):
        super().__init__(timeout=120)
        self.user, self.bet = user, bet
        self.board = make_board()
        self.revealed = set()
        self.profit = 0
        self.done = False
        self.busy = False
        self.message = None
        self.tiles = [Tile(i) for i in range(20)]
        for t in self.tiles:
            self.add_item(t)
        self.cash_btn = CashoutButton()
        self.profit_btn = discord.ui.Button(
            style=discord.ButtonStyle.primary, disabled=True, row=4,
            label="Profit: 0", emoji=cur())
        self.add_item(self.cash_btn)
        self.add_item(self.profit_btn)

    @property
    def header(self):
        return f"**{self.user.display_name}'s Game**"

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "This is not your game!", ephemeral=True)
            return False
        return True

    async def _edit(self, interaction, **kw):
        if interaction.response.is_done():
            await interaction.edit_original_response(**kw)
        else:
            await interaction.response.edit_message(**kw)

    def reveal_tile(self, i):
        kind = self.board[i]
        self.revealed.add(i)
        t = self.tiles[i]
        t.emoji = EMOJI[kind]
        t.disabled = True
        if kind == "bomb":
            t.style = discord.ButtonStyle.danger      # red outline
        else:
            t.style = discord.ButtonStyle.success     # green outline
            self.profit += self.bet * (MULT[kind] - 1)
            self.profit_btn.label = f"Profit: {fmt(self.profit)}"

    async def click(self, interaction, idx):
        if self.done or self.busy:
            if not interaction.response.is_done():
                await interaction.response.defer()
            return
        self.busy = True

        await interaction.response.defer()
        await asyncio.sleep(CLICK_DELAY)

        kind = self.board[idx]
        self.reveal_tile(idx)
        if kind == "bomb":
            self.busy = False
            return await self.finish(interaction, lost=True)
        if kind == "map":                             # reveals 3 safe tiles at once
            safe = [i for i, k in enumerate(self.board)
                    if k != "bomb" and i not in self.revealed]
            for i in random.sample(safe, min(3, len(safe))):
                self.reveal_tile(i)
        if all(k == "bomb" or i in self.revealed
               for i, k in enumerate(self.board)):
            self.busy = False
            return await self.finish(interaction, lost=False)

        for i, t in enumerate(self.tiles):
            t.disabled = i in self.revealed
        self.cash_btn.disabled = False
        self.busy = False
        await interaction.edit_original_response(content=self.header, view=self)

    def reveal_all(self):
        for i, kind in enumerate(self.board):
            t = self.tiles[i]
            t.emoji = EMOJI[kind]
            t.disabled = True
            if kind == "bomb":
                t.style = discord.ButtonStyle.danger
        self.cash_btn.disabled = True

    def result_embed(self, lost):
        c = cur()
        if lost:
            block = f"```diff\n- You Lost {fmt(self.bet)}! {c}\n```"
            color = RED
        else:
            block = f"```diff\n+ You Won {fmt(self.profit)}! {c}\n```"
            color = GREEN
        cash = user_data(self.user.id)["cash"]
        return make_embed(self.user, f"{block}\nYou now have **{fmt(cash)}** {c}.",
                          color, title="Result")

    def pay_out(self):
        user_data(self.user.id)["cash"] += self.bet + int(self.profit)
        save()

    async def finish(self, interaction, lost):
        if self.done:
            return
        self.done = True
        if not lost:
            self.pay_out()
        self.reveal_all()
        self.stop()
        await self._edit(interaction, content=self.header,
                         embed=self.result_embed(lost), view=self)

    async def on_timeout(self):
        if self.done:
            return
        self.done = True
        self.pay_out()
        self.reveal_all()
        if self.message:
            await self.message.edit(content=self.header,
                                    embed=self.result_embed(False), view=self)

# ================= BOT =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = False
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)

@bot.event
async def on_ready():
    print("Logged in as", bot.user)

@bot.event
async def on_command_error(ctx, err):
    if isinstance(err, commands.CommandNotFound):
        return
    if isinstance(err, commands.MissingPermissions):
        return await reply(ctx, "You need Administrator permission to use this command.", RED)
    if isinstance(err, (commands.MissingRequiredArgument, commands.BadArgument)):
        usage = ctx.command.usage or ctx.command.name
        return await reply(ctx, f"Usage: `${usage}`", RED)
    print("Error:", repr(err))

# ---------- $gm ----------
@bot.command(name="gm", usage="gm <amount | half | all>")
async def gm(ctx, amount: str = None):
    u = user_data(ctx.author.id)
    bet = parse_amount(amount, u["cash"])
    if bet is None:
        return await reply(ctx, f"Usage: `$gm <amount | half | all>` (min {MIN_BET})", RED)
    if bet < MIN_BET:
        return await reply(ctx, f"The minimum bet is {MIN_BET} {cur()}.", RED)
    if bet > u["cash"]:
        return await reply(ctx, "You don't have that much money.", RED)

    u["cash"] -= bet
    save()
    view = GameView(ctx.author, bet)
    view.message = await ctx.send(view.header, view=view)

# ================= BLACKJACK =================
YELLOW = 0xF1C40F
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["♠", "♥", "♦", "♣"]
HIDDEN_CARD = "🂠"
# Optional: upload card emojis to your server and map them here to get real card images, e.g.
# CARD_EMOJI["A♠"] = "<:As:123456789012345678>"
CARD_EMOJI = {}
ACTIVE_BJ = set()

def card_value(rank):
    if rank == "A":
        return 11
    if rank in ("J", "Q", "K"):
        return 10
    return int(rank)

def hand_value(cards):
    total = sum(card_value(r) for r, s in cards)
    aces = sum(1 for r, s in cards if r == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def show_card(card):
    r, s = card
    return CARD_EMOJI.get(r + s, f"**{r}{s}**")

def show_cards(cards):
    return ", ".join(show_card(c) for c in cards)

class BlackjackView(discord.ui.View):
    def __init__(self, user, bet):
        super().__init__(timeout=120)
        self.user = user
        self.deck = [(r, s) for r in RANKS for s in SUITS]
        random.shuffle(self.deck)
        self.hands = [{"cards": [self.deck.pop(), self.deck.pop()],
                       "bet": bet, "bust": False}]
        self.dealer = [self.deck.pop(), self.deck.pop()]
        self.active = 0
        self.done = False
        self.net = 0
        self.split_used = False
        self.message = None
        self.refresh_buttons()

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "This is not your game!", ephemeral=True)
            return False
        return True

    # ----- helpers -----
    def refresh_buttons(self):
        cash = user_data(self.user.id)["cash"]
        h = None if self.done else self.hands[self.active]
        two = h is not None and len(h["cards"]) == 2
        self.hit.disabled = self.done
        self.stand.disabled = self.done
        self.double.disabled = not (two and cash >= h["bet"])
        self.split.disabled = not (
            two and not self.split_used and cash >= h["bet"]
            and card_value(h["cards"][0][0]) == card_value(h["cards"][1][0]))

    def pay(self, returned):
        user_data(self.user.id)["cash"] += returned
        save()
        ACTIVE_BJ.discard(self.user.id)

    def check_naturals(self):
        p = hand_value(self.hands[0]["cards"]) == 21
        d = hand_value(self.dealer) == 21
        if not (p or d):
            return False
        bet = self.hands[0]["bet"]
        self.done = True
        if p and d:
            returned = bet
        elif p:
            returned = int(bet * 2.5)
        else:
            returned = 0
        self.net = returned - bet
        self.pay(returned)
        self.refresh_buttons()
        return True

    def finalize(self):
        self.done = True
        if any(not h["bust"] for h in self.hands):
            while hand_value(self.dealer) < 17:
                self.dealer.append(self.deck.pop())
        dv = hand_value(self.dealer)
        staked = sum(h["bet"] for h in self.hands)
        returned = 0
        for h in self.hands:
            if h["bust"]:
                continue
            pv = hand_value(h["cards"])
            if pv > dv or dv > 21:
                returned += h["bet"] * 2
            elif pv == dv:
                returned += h["bet"]
        self.net = returned - staked
        self.pay(returned)
        self.refresh_buttons()

    def build_embed(self):
        c = cur()
        color = YELLOW
        head = None
        if self.done:
            if self.net > 0:
                color, head = GREEN, f"You Won! +{fmt(self.net)} {c}"
            elif self.net < 0:
                color, head = RED, f"You Lost! -{fmt(-self.net)} {c}"
            else:
                head = f"Push! +0 {c}"
        lines = ["🃏 **Blackjack** 🃏", ""]
        if head:
            lines += [f"**{head}**", ""]
        multi = len(self.hands) > 1
        for i, h in enumerate(self.hands):
            title = "Your Hand" + (f" {i + 1}" if multi else "")
            if multi and not self.done and i == self.active:
                title += " ◀"
            lines += [f"**{title}**", show_cards(h["cards"]), "",
                      f"Value: **{hand_value(h['cards'])}**"]
        if self.done:
            dcards, dval = show_cards(self.dealer), hand_value(self.dealer)
        else:
            dcards = f"{show_card(self.dealer[0])}, {HIDDEN_CARD}"
            dval = card_value(self.dealer[0][0])
        lines += ["**Dealer**", dcards, "", f"Value: **{dval}**"]
        e = discord.Embed(description="\n".join(lines), color=color)
        e.set_author(name=f"{self.user.display_name}'s Game",
                     icon_url=self.user.display_avatar.url)
        return e

    async def update(self, interaction):
        self.refresh_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def advance(self, interaction):
        self.active += 1
        if self.active >= len(self.hands):
            self.active = len(self.hands) - 1
            self.finalize()
            self.stop()
        await self.update(interaction)

    # ----- buttons -----
    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction, button):
        h = self.hands[self.active]
        h["cards"].append(self.deck.pop())
        v = hand_value(h["cards"])
        if v > 21:
            h["bust"] = True
            await self.advance(interaction)
        elif v == 21:
            await self.advance(interaction)
        else:
            await self.update(interaction)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.success)
    async def stand(self, interaction, button):
        await self.advance(interaction)

    @discord.ui.button(label="Double", style=discord.ButtonStyle.danger)
    async def double(self, interaction, button):
        u = user_data(self.user.id)
        h = self.hands[self.active]
        if len(h["cards"]) != 2 or u["cash"] < h["bet"]:
            return await interaction.response.send_message(
                "You can't double right now.", ephemeral=True)
        u["cash"] -= h["bet"]
        save()
        h["bet"] *= 2
        h["cards"].append(self.deck.pop())
        if hand_value(h["cards"]) > 21:
            h["bust"] = True
        await self.advance(interaction)

    @discord.ui.button(label="Split", style=discord.ButtonStyle.secondary)
    async def split(self, interaction, button):
        u = user_data(self.user.id)
        h = self.hands[self.active]
        if self.split_used or len(h["cards"]) != 2 or u["cash"] < h["bet"]:
            return await interaction.response.send_message(
                "You can't split right now.", ephemeral=True)
        u["cash"] -= h["bet"]
        save()
        c1, c2 = h["cards"]
        bet = h["bet"]
        self.hands = [
            {"cards": [c1, self.deck.pop()], "bet": bet, "bust": False},
            {"cards": [c2, self.deck.pop()], "bet": bet, "bust": False},
        ]
        self.split_used = True
        self.active = 0
        await self.update(interaction)

    async def on_timeout(self):
        if self.done:
            return
        for h in self.hands:
            if hand_value(h["cards"]) > 21:
                h["bust"] = True
        self.finalize()
        if self.message:
            await self.message.edit(embed=self.build_embed(), view=self)

@bot.command(name="bj", aliases=["blackjack"], usage="bj <amount | half | all>")
async def bj(ctx, amount: str = None):
    if ctx.author.id in ACTIVE_BJ:
        return await reply(ctx, "You already have a Blackjack game running.", RED)
    u = user_data(ctx.author.id)
    bet = parse_amount(amount, u["cash"])
    if bet is None:
        return await reply(ctx, f"Usage: `$bj <amount | half | all>` (min {MIN_BET})", RED)
    if bet < MIN_BET:
        return await reply(ctx, f"The minimum bet is {MIN_BET} {cur()}.", RED)
    if bet > u["cash"]:
        return await reply(ctx, "You don't have that much money.", RED)

    u["cash"] -= bet
    save()
    ACTIVE_BJ.add(ctx.author.id)
    view = BlackjackView(ctx.author, bet)
    if view.check_naturals():                 # instant blackjack (player or dealer)
        return await ctx.send(embed=view.build_embed(), view=view)
    view.message = await ctx.send(embed=view.build_embed(), view=view)

# ---------- $bal ----------
@bot.command(name="bal", aliases=["balance"], usage="bal [@user]")
async def bal(ctx, member: discord.Member = None):
    member = member or ctx.author
    u = user_data(member.id)
    c = cur()
    desc = ("Use the `top` command to view your rank.\n\n"
            f"• **Money Out:** {fmt(u['cash'])} {c}\n"
            f"• **Bank Money:** {fmt(u['bank'])} {c}\n"
            f"• **Total Money:** {fmt(u['cash'] + u['bank'])} {c}")
    await ctx.reply(embed=make_embed(member, desc, BLUE), mention_author=False)

# ---------- $dep / $with ----------
@bot.command(name="dep", aliases=["deposit"], usage="dep <amount | half | all>")
async def dep(ctx, amount: str = None):
    u = user_data(ctx.author.id)
    amt = parse_amount(amount, u["cash"])
    if amt is None:
        return await reply(ctx, "Usage: `$dep <amount | half | all>`", RED)
    if amt <= 0 or amt > u["cash"]:
        return await reply(ctx, "You don't have that much money in your bank.", RED)
    u["cash"] -= amt
    u["bank"] += amt
    save()
    await reply(ctx, f"Successfully deposited {fmt(amt)} {cur()} to your bank account.", GREEN)

@bot.command(name="with", aliases=["withdraw"], usage="with <amount | half | all>")
async def withdraw(ctx, amount: str = None):
    u = user_data(ctx.author.id)
    amt = parse_amount(amount, u["bank"])
    if amt is None:
        return await reply(ctx, "Usage: `$with <amount | half | all>`", RED)
    if amt <= 0 or amt > u["bank"]:
        return await reply(ctx, "You don't have that much money in your bank.", RED)
    u["bank"] -= amt
    u["cash"] += amt
    save()
    await reply(ctx, f"Successfully withdrew {fmt(amt)} {cur()} from your bank account.", GREEN)

# ---------- $crime / $work ----------
@bot.command(name="crime")
async def crime(ctx):
    amt = random.randint(EARN_MIN, EARN_MAX)
    user_data(ctx.author.id)["cash"] += amt
    save()
    await reply(ctx, f"You successfully committed a crime and got {fmt(amt)} {cur()}!", GREEN)

@bot.command(name="work")
async def work(ctx):
    amt = random.randint(EARN_MIN, EARN_MAX)
    user_data(ctx.author.id)["cash"] += amt
    save()
    await reply(ctx, f"You worked hard and got {fmt(amt)} {cur()}!", GREEN)

# ---------- $top ----------
@bot.command(name="top")
async def top(ctx):
    ranked = sorted(DB["users"].items(),
                    key=lambda kv: kv[1]["cash"] + kv[1]["bank"], reverse=True)[:10]
    lines = []
    for n, (uid, d) in enumerate(ranked, 1):
        m = ctx.guild.get_member(int(uid)) if ctx.guild else None
        name = m.display_name if m else f"<@{uid}>"
        lines.append(f"**{n}.** {name} — {fmt(d['cash'] + d['bank'])} {cur()}")
    await reply(ctx, "\n".join(lines) or "Nobody has any money yet.", BLUE)

# ---------- admin: $addmoney / $currency ----------
@bot.command(name="addmoney", usage="addmoney <bank|cash> @user <amount>")
@commands.has_permissions(administrator=True)
async def addmoney(ctx, where: str, member: discord.Member, amount: int):
    where = where.lower()
    if where not in ("bank", "cash"):
        return await reply(ctx, "Usage: `$addmoney <bank|cash> @user <amount>`", RED)
    user_data(member.id)[where] += amount
    save()
    await reply(ctx, f"Added {fmt(amount)} {cur()} to {member.display_name}'s {where}.", GREEN)

@bot.command(name="currency", usage="currency <emoji>")
@commands.has_permissions(administrator=True)
async def currency(ctx, symbol: str = None):
    if symbol is None:
        return await reply(ctx, f"Current currency: {cur()}\nChange it with `$currency <emoji>`", BLUE)
    DB["currency"] = symbol
    save()
    await reply(ctx, f"Currency changed to {symbol}", GREEN)

bot.run(TOKEN)
