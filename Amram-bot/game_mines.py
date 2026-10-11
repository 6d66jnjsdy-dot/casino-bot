import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
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
