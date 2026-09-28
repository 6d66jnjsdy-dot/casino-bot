import discord, random, json, os
from discord.ext import commands

TOKEN = os.environ.get("DISCORD_TOKEN") or os.environ.get("TOKEN") or ""
TOKEN = TOKEN.strip().strip('"').strip("'")
print("TOKEN LEN:", len(TOKEN), "START:", TOKEN[:4])

MONEY = "💸"
MIN_BET = 150
START_BALANCE = 5000
DB_FILE = "balances.json"

EMOJI = {"bomb": "💣", "map": "🗺️", "diamond": "💎", "coin": "🪙",
         "stone": "🪨", "bag": "💰", "urn": "🏮"}
MULT = {"diamond": 3.5, "urn": 25, "stone": 1.1, "coin": 2, "bag": 5.5, "map": 1}

# ---------- database ----------
def load():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f:
            return json.load(f)
    return {}

def save(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f)

def get_bal(uid):
    return load().get(str(uid), START_BALANCE)

def set_bal(uid, amount):
    db = load()
    db[str(uid)] = int(amount)
    save(db)

# ---------- board ----------
def make_board():
    tiles = (["map"] + ["bomb"] * 11 + ["stone"] * 3 +
             ["coin"] * 2 + ["bag"] + ["diamond"] * 2)
    if random.randint(1, 7) == 1:
        tiles[tiles.index("stone")] = "urn"
    random.shuffle(tiles)
    return tiles

# ---------- UI ----------
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
        self.message = None
        self.tiles = [Tile(i) for i in range(20)]
        for t in self.tiles:
            self.add_item(t)
        self.cash_btn = CashoutButton()
        self.profit_btn = discord.ui.Button(
            style=discord.ButtonStyle.primary, disabled=True, row=4,
            label="Profit: 0", emoji="💸")
        self.add_item(self.cash_btn)
        self.add_item(self.profit_btn)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "זה לא המשחק שלך!", ephemeral=True)
            return False
        return True

    def reveal_tile(self, i):
        kind = self.board[i]
        self.revealed.add(i)
        t = self.tiles[i]
        t.emoji = EMOJI[kind]
        t.disabled = True
        if kind == "bomb":
            t.style = discord.ButtonStyle.danger
        else:
            self.profit += self.bet * (MULT[kind] - 1)
            self.profit_btn.label = f"Profit: {int(self.profit):,}"

    async def click(self, interaction, idx):
        if self.done:
            return
        kind = self.board[idx]
        self.reveal_tile(idx)
        if kind == "bomb":
            return await self.finish(interaction, lost=True)
        if kind == "map":
            safe = [i for i, k in enumerate(self.board)
                    if k != "bomb" and i not in self.revealed]
            for i in random.sample(safe, min(3, len(safe))):
                self.reveal_tile(i)
        if all(k == "bomb" or i in self.revealed
               for i, k in enumerate(self.board)):
            return await self.finish(interaction, lost=False)
        await interaction.response.edit_message(view=self)

    def reveal_all(self):
        for i, kind in enumerate(self.board):
            t = self.tiles[i]
            t.emoji = EMOJI[kind]
            t.disabled = True
            if kind == "bomb":
                t.style = discord.ButtonStyle.danger
        self.cash_btn.disabled = True

    def result_embed(self, lost):
        bal = get_bal(self.user.id)
        if lost:
            e = discord.Embed(color=discord.Color.red())
            block = f"```diff\n- You Lost {self.bet:,}! {MONEY}\n```"
        else:
            e = discord.Embed(color=discord.Color.green())
            block = f"```diff\n+ You Won {int(self.profit):,}! {MONEY}\n```"
        e.set_author(name=self.user.display_name,
                     icon_url=self.user.display_avatar.url)
        e.title = "Result"
        e.description = f"{block}\nYou now have **{bal:,}** {MONEY}."
        return e

    async def finish(self, interaction, lost):
        if self.done:
            return
        self.done = True
        if not lost:
            set_bal(self.user.id, get_bal(self.user.id) + self.bet + int(self.profit))
        self.reveal_all()
        self.stop()
        await interaction.response.edit_message(
            embed=self.result_embed(lost), view=self)

    async def on_timeout(self):
        if self.done:
            return
        self.done = True
        set_bal(self.user.id, get_bal(self.user.id) + self.bet + int(self.profit))
        self.reveal_all()
        if self.message:
            await self.message.edit(embed=self.result_embed(False), view=self)

# ---------- bot ----------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents)

@bot.event
async def on_ready():
    print("Logged in as", bot.user)

@bot.command(name="gm")
async def gm(ctx, amount: str = None):
    if amount is None:
        return await ctx.send(f"שימוש: `$gm <סכום | half | all>` (מינימום {MIN_BET})")
    bal = get_bal(ctx.author.id)
    a = amount.lower().replace(",", "")
    if a == "all":
        bet = bal
    elif a == "half":
        bet = bal // 2
    elif a.isdigit():
        bet = int(a)
    else:
        return await ctx.send("סכום לא תקין.")
    if bet < MIN_BET:
        return await ctx.send(f"ההימור המינימלי הוא {MIN_BET} {MONEY}")
    if bet > bal:
        return await ctx.send(f"אין לך מספיק כסף. יש לך {bal:,} {MONEY}")

    set_bal(ctx.author.id, bal - bet)
    view = GameView(ctx.author, bet)
    view.message = await ctx.send(f"**{ctx.author.display_name}'s Game**", view=view)

bot.run(TOKEN)
