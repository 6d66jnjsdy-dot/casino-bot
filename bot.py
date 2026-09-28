import discord
import random
import json
import os
import asyncio
import io
import signal

from functools import lru_cache
from PIL import Image, ImageDraw
from discord.ext import commands, tasks


# ============================================================
# CONFIG
# ============================================================

TOKEN = (
    os.environ.get("DISCORD_TOKEN")
    or os.environ.get("TOKEN")
    or ""
).strip().strip('"').strip("'")

DB_FILE = os.environ.get("DB_FILE", "economy.json")

MIN_BET = 150
EARN_MIN = 6500
EARN_MAX = 16000
DEALER_STANDS_ON = 13
CLICK_DELAY = 0.3

GREEN = 0x43B581
RED = 0xC0392B
BLUE = 0x3B82F6
YELLOW = 0xF1C40F

EMOJI = {
    "bomb": "💣",
    "map": "🗺️",
    "diamond": "💎",
    "coin": "🪙",
    "stone": "🪨",
    "bag": "💰",
    "urn": "🏮"
}

MULT = {
    "diamond": 3.5,
    "urn": 25,
    "stone": 1.1,
    "coin": 2,
    "bag": 5.5,
    "map": 1
}


# ============================================================
# DATABASE
# ============================================================

def load():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "currency": "💸",
        "users": {}
    }


DB = load()
dirty = False
backup_msg = None
restored = False

BACKUP_CHANNEL_ID = int(
    os.environ.get("BACKUP_CHANNEL_ID", "0") or 0
)


def save():
    global dirty

    tmp = DB_FILE + ".tmp"

    with open(tmp, "w") as f:
        json.dump(DB, f)

    os.replace(tmp, DB_FILE)

    dirty = True

    if bot.is_ready() and BACKUP_CHANNEL_ID:
        asyncio.create_task(backup_now())


def user_data(uid):
    return DB["users"].setdefault(
        str(uid),
        {
            "cash": 0,
            "bank": 0
        }
    )


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
        mult = 1000
        t = t[:-1]

    elif t.endswith("m"):
        mult = 1_000_000
        t = t[:-1]

    try:
        return int(float(t) * mult)
    except ValueError:
        return None


# ============================================================
# EMBEDS
# ============================================================

def make_embed(user, desc, color, title=None):
    e = discord.Embed(
        description=desc,
        color=color
    )

    if title:
        e.title = title

    e.set_author(
        name=user.display_name,
        icon_url=user.display_avatar.url
    )

    return e


async def reply(ctx, desc, color):
    await ctx.reply(
        embed=make_embed(ctx.author, desc, color),
        mention_author=False
    )


# ============================================================
# MINES / GM
# ============================================================

def make_board():
    tiles = (
        ["map"]
        + ["bomb"] * 11
        + ["stone"] * 3
        + ["coin"] * 2
        + ["bag"]
        + ["diamond"] * 2
    )

    if random.randint(1, 7) == 1:
        tiles[tiles.index("stone")] = "urn"

    random.shuffle(tiles)

    return tiles


class Tile(discord.ui.Button):

    def __init__(self, idx):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="\u200b",
            row=idx // 5
        )

        self.idx = idx

    async def callback(self, interaction):
        await self.view.click(interaction, self.idx)


class CashoutButton(discord.ui.Button):

    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Cashout",
            row=4
        )

    async def callback(self, interaction):
        await self.view.finish(
            interaction,
            lost=False
        )


class GameView(discord.ui.View):

    def __init__(self, user, bet):
        super().__init__(timeout=120)

        self.user = user
        self.bet = bet
        self.board = make_board()

        self.revealed = set()
        self.profit = 0
        self.done = False
        self.busy = False
        self.message = None

        self.tiles = [
            Tile(i)
            for i in range(20)
        ]

        for t in self.tiles:
            self.add_item(t)

        self.cash_btn = CashoutButton()

        self.profit_btn = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            disabled=True,
            row=4,
            label="Profit: 0",
            emoji=cur()
        )

        self.add_item(self.cash_btn)
        self.add_item(self.profit_btn)

    @property
    def header(self):
        return f"**{self.user.display_name}'s Game**"

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "This is not your game!",
                ephemeral=True
            )
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
            t.style = discord.ButtonStyle.danger

        else:
            t.style = discord.ButtonStyle.success

            self.profit += self.bet * (
                MULT[kind] - 1
            )

            self.profit_btn.label = (
                f"Profit: {fmt(self.profit)}"
            )

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
            return await self.finish(
                interaction,
                lost=True
            )

        if kind == "map":
            safe = [
                i
                for i, k in enumerate(self.board)
                if k != "bomb"
                and i not in self.revealed
            ]

            for i in random.sample(
                safe,
                min(3, len(safe))
            ):
                self.reveal_tile(i)

        if all(
            k == "bomb" or i in self.revealed
            for i, k in enumerate(self.board)
        ):
            self.busy = False

            return await self.finish(
                interaction,
                lost=False
            )

        for i, t in enumerate(self.tiles):
            t.disabled = i in self.revealed

        self.cash_btn.disabled = False

        self.busy = False

        await interaction.edit_original_response(
            content=self.header,
            view=self
        )

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
            block = (
                f"```diff\n"
                f"- You Lost {fmt(self.bet)}! {c}\n"
                f"```"
            )

            color = RED

        else:
            block = (
                f"```diff\n"
                f"+ You Won {fmt(self.profit)}! {c}\n"
                f"```"
            )

            color = GREEN

        cash = user_data(self.user.id)["cash"]

        return make_embed(
            self.user,
            f"{block}\n"
            f"You now have **{fmt(cash)}** {c}.",
            color,
            title="Result"
        )

    def pay_out(self):
        user_data(self.user.id)["cash"] += (
            self.bet + int(self.profit)
        )

        save()

    async def finish(self, interaction, lost):
        if self.done:
            return

        self.done = True

        if not lost:
            self.pay_out()

        self.reveal_all()
        self.stop()

        await self._edit(
            interaction,
            content=self.header,
            embed=self.result_embed(lost),
            view=self
        )

    async def on_timeout(self):
        if self.done:
            return

        self.done = True

        self.pay_out()
        self.reveal_all()

        if self.message:
            await self.message.edit(
                content=self.header,
                embed=self.result_embed(False),
                view=self
            )


# ============================================================
# BOT
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = False

bot = commands.Bot(
    command_prefix="$",
    intents=intents,
    help_command=None
)


# ============================================================
# BACKUP
# ============================================================

def backup_file():
    return discord.File(
        io.BytesIO(
            json.dumps(DB).encode()
        ),
        filename="economy.json"
    )


async def get_backup_channel():
    return (
        bot.get_channel(BACKUP_CHANNEL_ID)
        or await bot.fetch_channel(BACKUP_CHANNEL_ID)
    )


async def restore_backup():
    global backup_msg

    if not BACKUP_CHANNEL_ID:
        print(
            "BACKUP_CHANNEL_ID is not set - backup disabled!"
        )
        return

    try:
        ch = await get_backup_channel()

        async for m in ch.history(limit=50):

            att = next(
                (
                    a
                    for a in m.attachments
                    if a.filename == "economy.json"
                ),
                None
            )

            if (
                not att
                or not bot.user
                or m.author.id != bot.user.id
            ):
                continue

            backup_msg = m

            data = json.loads(
                await att.read()
            )

            if data.get("users"):
                DB.clear()
                DB.update(data)

                tmp = DB_FILE + ".tmp"

                with open(tmp, "w") as f:
                    json.dump(DB, f)

                os.replace(
                    tmp,
                    DB_FILE
                )

                print(
                    f"Restored "
                    f"{len(DB['users'])} players "
                    f"from backup"
                )

            break

    except Exception as e:
        print(
            "Backup restore failed:",
            repr(e)
        )


async def backup_now():
    global backup_msg, dirty

    if not BACKUP_CHANNEL_ID or not dirty:
        return

    dirty = False

    try:
        if backup_msg:
            try:
                backup_msg = await backup_msg.edit(
                    attachments=[backup_file()]
                )

                return

            except discord.NotFound:
                backup_msg = None

        ch = await get_backup_channel()

        backup_msg = await ch.send(
            "💾 Database backup - do not delete this message",
            file=backup_file()
        )

    except Exception as e:
        dirty = True

        print(
            "Backup failed:",
            repr(e)
        )


@tasks.loop(seconds=15)
async def backup_loop():
    await backup_now()


async def graceful_shutdown():
    await backup_now()
    await bot.close()


async def setup_hook():
    backup_loop.start()

    try:
        asyncio.get_running_loop().add_signal_handler(
            signal.SIGTERM,
            lambda: asyncio.create_task(
                graceful_shutdown()
            )
        )

    except (
        NotImplementedError,
        RuntimeError
    ):
        pass


bot.setup_hook = setup_hook


@bot.event
async def on_ready():
    global restored

    if not restored:
        restored = True
        await restore_backup()

    print(
        "Logged in as",
        bot.user
    )


@bot.event
async def on_command_error(ctx, err):

    if isinstance(
        err,
        commands.CommandNotFound
    ):
        return

    if isinstance(
        err,
        commands.CommandOnCooldown
    ):
        remaining = int(
            err.retry_after
        ) + 1

        minutes, seconds = divmod(
            remaining,
            60
        )

        if minutes:
            text = (
                f"Try again in "
                f"**{minutes}m {seconds}s**."
            )

        else:
            text = (
                f"Try again in "
                f"**{seconds}s**."
            )

        return await reply(
            ctx,
            text,
            RED
        )

    if isinstance(
        err,
        commands.MissingPermissions
    ):
        return await reply(
            ctx,
            "You need Administrator permission "
            "to use this command.",
            RED
        )

    if isinstance(
        err,
        (
            commands.MissingRequiredArgument,
            commands.BadArgument
        )
    ):
        usage = (
            ctx.command.usage
            or ctx.command.name
        )

        return await reply(
            ctx,
            f"Usage: `${usage}`",
            RED
        )

    print(
        "Error:",
        repr(err)
    )


# ============================================================
# GM
# ============================================================

@bot.command(
    name="gm",
    usage="gm <amount | half | all>"
)
async def gm(ctx, amount: str = None):

    u = user_data(ctx.author.id)

    bet = parse_amount(
        amount,
        u["cash"]
    )

    if bet is None:
        return await reply(
            ctx,
            f"Usage: `$gm <amount | half | all>` "
            f"(min {MIN_BET})",
            RED
        )

    if bet < MIN_BET:
        return await reply(
            ctx,
            f"The minimum bet is "
            f"{MIN_BET} {cur()}.",
            RED
        )

    if bet > u["cash"]:
        return await reply(
            ctx,
            "You don't have that much money.",
            RED
        )

    u["cash"] -= bet

    save()

    view = GameView(
        ctx.author,
        bet
    )

    view.message = await ctx.send(
        view.header,
        view=view
    )


# ============================================================
# BLACKJACK
# ============================================================

RANKS = [
    "A", "2", "3", "4", "5", "6",
    "7", "8", "9", "10", "J", "Q", "K"
]

SUITS = [
    "♠",
    "♥",
    "♦",
    "♣"
]

HIDDEN_CARD = "🂠"

CARD_EMOJI = {}

ACTIVE_BJ = set()


def card_value(rank):
    if rank == "A":
        return 11

    if rank in ("J", "Q", "K"):
        return 10

    return int(rank)


def hand_value(cards):
    total = sum(
        card_value(r)
        for r, s in cards
    )

    aces = sum(
        1
        for r, s in cards
        if r == "A"
    )

    while total > 21 and aces:
        total -= 10
        aces -= 1

    return total


def show_card(card):
    r, s = card

    return CARD_EMOJI.get(
        r + s,
        f"**{r}{s}**"
    )


def show_cards(cards):
    return ", ".join(
        show_card(c)
        for c in cards
    )


# ============================================================
# BLACKJACK DECK.PNG CARD SYSTEM
# ============================================================

DECK_PATH = "deck.png"

CARD_W = 34
CARD_H = 48


def extract_cards(deck_path):
    """
    מפרק את תמונת החפיסה ל-52 קלפים.
    13 עמודות × 4 שורות.
    """

    deck = Image.open(
        deck_path
    ).convert("RGBA")

    w, h = deck.size

    card_w = w / 13
    card_h = h / 4

    suits = [
        "clubs",
        "spades",
        "hearts",
        "diamonds"
    ]

    cards = {}

    for row, suit in enumerate(suits):

        for col in range(13):

            left = col * card_w
            top = row * card_h

            crop_box = (
                left,
                top,
                left + card_w,
                top + card_h
            )

            cards[
                (suit, col + 1)
            ] = deck.crop(crop_box)

    return cards


@lru_cache(maxsize=1)
def get_card_library():
    return extract_cards(
        DECK_PATH
    )


def blackjack_suit_name(suit):
    return {
        "♣": "clubs",
        "♠": "spades",
        "♥": "hearts",
        "♦": "diamonds"
    }[suit]


def blackjack_rank_number(rank):
    return {
        "A": 1,
        "2": 2,
        "3": 3,
        "4": 4,
        "5": 5,
        "6": 6,
        "7": 7,
        "8": 8,
        "9": 9,
        "10": 10,
        "J": 11,
        "Q": 12,
        "K": 13
    }[rank]


@lru_cache(maxsize=None)
def get_card(card):

    rank, suit = card

    library = get_card_library()

    suit_name = blackjack_suit_name(
        suit
    )

    rank_number = blackjack_rank_number(
        rank
    )

    card_img = library[
        (suit_name, rank_number)
    ].resize(
        (32, 46),
        Image.Resampling.LANCZOS
    )

    # מסגרת לבנה
    bordered_card = Image.new(
        "RGBA",
        (34, 48),
        "white"
    )

    bordered_card.paste(
        card_img,
        (1, 1)
    )

    return bordered_card


@lru_cache(maxsize=1)
def get_back():

    # קלף הפוך אדום
    bordered_card = Image.new(
        "RGBA",
        (34, 48),
        "white"
    )

    red_back = Image.new(
        "RGBA",
        (32, 46),
        "#e03e3e"
    )

    bordered_card.paste(
        red_back,
        (1, 1)
    )

    return bordered_card


def render_table(
    dealer,
    hands,
    hide_dealer
):
    """
    YOUR HAND למעלה
    DEALER HAND למטה
    """

    rows = []

    # -------------------------
    # YOUR HAND
    # -------------------------

    for i, h in enumerate(hands):

        rows.append(
            (
                "YOUR HAND"
                + (
                    f" {i + 1}"
                    if len(hands) > 1
                    else ""
                ),
                list(h)
            )
        )

    # -------------------------
    # DEALER HAND
    # -------------------------

    dealer_cards = (
        [dealer[0], None]
        if hide_dealer
        else list(dealer)
    )

    rows.append(
        (
            "DEALER HAND",
            dealer_cards
        )
    )

    PAD = 8
    LABEL_H = 20
    GAP = 8

    MAXW = 420

    def step(n):

        if n <= 1:
            return CARD_W + 6

        return min(
            CARD_W + 6,
            (MAXW - CARD_W) / (n - 1)
        )

    max_row_width = 0

    for _, cards in rows:

        if cards:

            max_row_width = max(
                max_row_width,
                CARD_W
                + (len(cards) - 1)
                * step(len(cards))
            )

    width = max(
        150,
        2 * PAD + max_row_width
    )

    height = (
        2 * PAD
        + len(rows)
        * (LABEL_H + CARD_H)
        + (len(rows) - 1) * GAP
    )

    img = Image.new(
        "RGBA",
        (
            int(width),
            int(height)
        ),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(img)

    y = PAD

    for label, cards in rows:

        draw.text(
            (PAD, y),
            label,
            font=get_font(13),
            fill=(255, 255, 255, 255)
        )

        y += LABEL_H

        spacing = step(
            len(cards)
        )

        for i, card in enumerate(cards):

            if card is None:
                card_img = get_back()
            else:
                card_img = get_card(card)

            x = int(
                PAD + i * spacing
            )

            img.paste(
                card_img,
                (x, y),
                card_img
            )

        y += CARD_H + GAP

    buf = io.BytesIO()

    img.save(
        buf,
        "PNG"
    )

    buf.seek(0)

    return buf


# ============================================================
# BLACKJACK VIEW
# ============================================================

class BlackjackView(discord.ui.View):

    def __init__(self, user, bet):

        super().__init__(
            timeout=120
        )

        self.user = user

        self.deck = [
            (r, s)
            for r in RANKS
            for s in SUITS
        ]

        random.shuffle(
            self.deck
        )

        self.hands = [
            {
                "cards": [
                    self.deck.pop(),
                    self.deck.pop()
                ],
                "bet": bet,
                "bust": False
            }
        ]

        self.dealer = [
            self.deck.pop(),
            self.deck.pop()
        ]

        self.active = 0
        self.done = False
        self.net = 0
        self.split_used = False
        self.message = None

        self.refresh_buttons()

    async def interaction_check(
        self,
        interaction
    ):

        if interaction.user.id != self.user.id:

            await interaction.response.send_message(
                "This is not your game!",
                ephemeral=True
            )

            return False

        return True

    def refresh_buttons(self):

        cash = user_data(
            self.user.id
        )["cash"]

        h = (
            None
            if self.done
            else self.hands[self.active]
        )

        two = (
            h is not None
            and len(h["cards"]) == 2
        )

        self.hit.disabled = self.done

        self.stand.disabled = self.done

        self.double.disabled = not (
            two
            and cash >= h["bet"]
        )

        self.split.disabled = not (
            two
            and not self.split_used
            and cash >= h["bet"]
            and card_value(
                h["cards"][0][0]
            )
            == card_value(
                h["cards"][1][0]
            )
        )

    def pay(self, returned):

        user_data(
            self.user.id
        )["cash"] += returned

        save()

        ACTIVE_BJ.discard(
            self.user.id
        )

    def check_naturals(self):

        p = (
            hand_value(
                self.hands[0]["cards"]
            ) == 21
        )

        d = (
            hand_value(
                self.dealer
            ) == 21
        )

        if not (p or d):
            return False

        bet = self.hands[0]["bet"]

        self.done = True

        if p and d:
            returned = bet

        elif p:
            returned = int(
                bet * 2.5
            )

        else:
            returned = 0

        self.net = returned - bet

        self.pay(returned)

        self.refresh_buttons()

        return True

    def finalize(self):

        self.done = True

        if any(
            not h["bust"]
            for h in self.hands
        ):

            while (
                hand_value(self.dealer)
                < DEALER_STANDS_ON
            ):
                self.dealer.append(
                    self.deck.pop()
                )

        dv = hand_value(
            self.dealer
        )

        staked = sum(
            h["bet"]
            for h in self.hands
        )

        returned = 0

        for h in self.hands:

            if h["bust"]:
                continue

            pv = hand_value(
                h["cards"]
            )

            if pv > dv or dv > 21:
                returned += h["bet"] * 2

            elif pv == dv:
                returned += h["bet"]

        self.net = returned - staked

        self.pay(returned)

        self.refresh_buttons()

    def render(self):

        self.render_n = getattr(
            self,
            "render_n",
            0
        ) + 1

        filename = (
            f"bj{self.render_n}.png"
        )

        file = discord.File(
            render_table(
                self.dealer,
                [
                    h["cards"]
                    for h in self.hands
                ],
                not self.done
            ),
            filename=filename
        )

        c = cur()

        color = YELLOW
        head = None

        if self.done:

            if self.net > 0:

                color = GREEN

                head = (
                    f"You Won! "
                    f"+{fmt(self.net)} {c}"
                )

            elif self.net < 0:

                color = RED

                head = (
                    f"You Lost! "
                    f"-{fmt(-self.net)} {c}"
                )

            else:

                head = (
                    f"Push! +0 {c}"
                )

        lines = [
            "🃏 **Blackjack** 🃏",
            ""
        ]

        if head:
            lines += [
                f"**{head}**",
                ""
            ]

        multi = len(self.hands) > 1

        for i, h in enumerate(
            self.hands
        ):

            title = "Your Value"

            if multi:
                title += (
                    f" (Hand {i + 1})"
                )

            mark = ""

            if (
                multi
                and not self.done
                and i == self.active
            ):
                mark = " ◀"

            lines.append(
                f"{title}: "
                f"**{hand_value(h['cards'])}**"
                f"{mark}"
            )

        dval = (
            hand_value(self.dealer)
            if self.done
            else card_value(
                self.dealer[0][0]
            )
        )

        lines.append(
            f"Dealer Value: **{dval}**"
        )

        e = discord.Embed(
            description="\n".join(lines),
            color=color
        )

        e.set_author(
            name=f"{self.user.display_name}'s Game",
            icon_url=self.user.display_avatar.url
        )

        e.set_image(
            url=f"attachment://{filename}"
        )

        return e, file

    async def update(self, interaction):

        self.refresh_buttons()

        e, f = self.render()

        await interaction.response.edit_message(
            embed=e,
            attachments=[f],
            view=self
        )

    async def advance(self, interaction):

        self.active += 1

        if self.active >= len(
            self.hands
        ):

            self.active = (
                len(self.hands) - 1
            )

            self.finalize()

            self.stop()

        await self.update(
            interaction
        )

    @discord.ui.button(
        label="Hit",
        style=discord.ButtonStyle.primary
    )
    async def hit(
        self,
        interaction,
        button
    ):

        h = self.hands[
            self.active
        ]

        h["cards"].append(
            self.deck.pop()
        )

        v = hand_value(
            h["cards"]
        )

        if v > 21:

            h["bust"] = True

            await self.advance(
                interaction
            )

        elif v == 21:

            await self.advance(
                interaction
            )

        else:

            await self.update(
                interaction
            )

    @discord.ui.button(
        label="Stand",
        style=discord.ButtonStyle.success
    )
    async def stand(
        self,
        interaction,
        button
    ):

        await self.advance(
            interaction
        )

    @discord.ui.button(
        label="Double",
        style=discord.ButtonStyle.danger
    )
    async def double(
        self,
        interaction,
        button
    ):

        u = user_data(
            self.user.id
        )

        h = self.hands[
            self.active
        ]

        if (
            len(h["cards"]) != 2
            or u["cash"] < h["bet"]
        ):

            return await interaction.response.send_message(
                "You can't double right now.",
                ephemeral=True
            )

        u["cash"] -= h["bet"]

        save()

        h["bet"] *= 2

        h["cards"].append(
            self.deck.pop()
        )

        if hand_value(
            h["cards"]
        ) > 21:

            h["bust"] = True

        await self.advance(
            interaction
        )

    @discord.ui.button(
        label="Split",
        style=discord.ButtonStyle.secondary
    )
    async def split(
        self,
        interaction,
        button
    ):

        u = user_data(
            self.user.id
        )

        h = self.hands[
            self.active
        ]

        if (
            self.split_used
            or len(h["cards"]) != 2
            or u["cash"] < h["bet"]
        ):

            return await interaction.response.send_message(
                "You can't split right now.",
                ephemeral=True
            )

        u["cash"] -= h["bet"]

        save()

        c1, c2 = h["cards"]

        bet = h["bet"]

        self.hands = [
            {
                "cards": [
                    c1,
                    self.deck.pop()
                ],
                "bet": bet,
                "bust": False
            },
            {
                "cards": [
                    c2,
                    self.deck.pop()
                ],
                "bet": bet,
                "bust": False
            }
        ]

        self.split_used = True
        self.active = 0

        await self.update(
            interaction
        )

    async def on_timeout(self):

        if self.done:
            return

        for h in self.hands:

            if hand_value(
                h["cards"]
            ) > 21:

                h["bust"] = True

        self.finalize()

        if self.message:

            e, f = self.render()

            await self.message.edit(
                embed=e,
                attachments=[f],
                view=self
            )


# ============================================================
# BLACKJACK COMMAND
# ============================================================

@bot.command(
    name="bj",
    aliases=["blackjack"],
    usage="bj <amount | half | all>"
)
async def bj(
    ctx,
    amount: str = None
):

    if ctx.author.id in ACTIVE_BJ:

        return await reply(
            ctx,
            "You already have a Blackjack game running.",
            RED
        )

    u = user_data(
        ctx.author.id
    )

    bet = parse_amount(
        amount,
        u["cash"]
    )

    if bet is None:

        return await reply(
            ctx,
            f"Usage: `$bj <amount | half | all>` "
            f"(min {MIN_BET})",
            RED
        )

    if bet < MIN_BET:

        return await reply(
            ctx,
            f"The minimum bet is "
            f"{MIN_BET} {cur()}.",
            RED
        )

    if bet > u["cash"]:

        return await reply(
            ctx,
            "You don't have that much money.",
            RED
        )

    u["cash"] -= bet

    save()

    ACTIVE_BJ.add(
        ctx.author.id
    )

    view = BlackjackView(
        ctx.author,
        bet
    )

    e, f = view.render()

    if view.check_naturals():

        e, f = view.render()

        return await ctx.send(
            embed=e,
            file=f,
            view=view
        )

    view.message = await ctx.send(
        embed=e,
        file=f,
        view=view
    )


# ============================================================
# BALANCE
# ============================================================

@bot.command(
    name="bal",
    aliases=["balance"],
    usage="bal [@user]"
)
async def bal(
    ctx,
    member: discord.Member = None
):

    member = member or ctx.author

    u = user_data(
        member.id
    )

    c = cur()

    desc = (
        "Use the `top` command "
        "to view your rank.\n\n"
        f"• **Money Out:** "
        f"{fmt(u['cash'])} {c}\n"
        f"• **Bank Money:** "
        f"{fmt(u['bank'])} {c}\n"
        f"• **Total Money:** "
        f"{fmt(u['cash'] + u['bank'])} {c}"
    )

    await ctx.reply(
        embed=make_embed(
            member,
            desc,
            BLUE
        ),
        mention_author=False
    )


# ============================================================
# DEPOSIT
# ============================================================

@bot.command(
    name="dep",
    aliases=["deposit"],
    usage="dep <amount | half | all>"
)
async def dep(
    ctx,
    amount: str = None
):

    u = user_data(
        ctx.author.id
    )

    amt = parse_amount(
        amount,
        u["cash"]
    )

    if amt is None:

        return await reply(
            ctx,
            "Usage: `$dep <amount | half | all>`",
            RED
        )

    if amt <= 0 or amt > u["cash"]:

        return await reply(
            ctx,
            "You don't have that much money "
            "in your bank.",
            RED
        )

    u["cash"] -= amt
    u["bank"] += amt

    save()

    await reply(
        ctx,
        f"Successfully deposited "
        f"{fmt(amt)} {cur()} "
        f"to your bank account.",
        GREEN
    )


# ============================================================
# WITHDRAW
# ============================================================

@bot.command(
    name="with",
    aliases=["withdraw"],
    usage="with <amount | half | all>"
)
async def withdraw(
    ctx,
    amount: str = None
):

    u = user_data(
        ctx.author.id
    )

    amt = parse_amount(
        amount,
        u["bank"]
    )

    if amt is None:

        return await reply(
            ctx,
            "Usage: `$with <amount | half | all>`",
            RED
        )

    if amt <= 0 or amt > u["bank"]:

        return await reply(
            ctx,
            "You don't have that much money "
            "in your bank.",
            RED
        )

    u["bank"] -= amt
    u["cash"] += amt

    save()

    await reply(
        ctx,
        f"Successfully withdrew "
        f"{fmt(amt)} {cur()} "
        f"from your bank account.",
        GREEN
    )


# ============================================================
# CRIME / WORK
# ============================================================

@bot.command(
    name="crime",
    cooldown_after_parsing=True
)
@commands.cooldown(
    1,
    120,
    commands.BucketType.user
)
async def crime(ctx):

    amt = random.randint(
        EARN_MIN,
        EARN_MAX
    )

    user_data(
        ctx.author.id
    )["cash"] += amt

    save()

    await reply(
        ctx,
        f"You successfully committed "
        f"a crime and got "
        f"{fmt(amt)} {cur()}!",
        GREEN
    )


@bot.command(
    name="work",
    cooldown_after_parsing=True
)
@commands.cooldown(
    1,
    120,
    commands.BucketType.user
)
async def work(ctx):

    amt = random.randint(
        EARN_MIN,
        EARN_MAX
    )

    user_data(
        ctx.author.id
    )["cash"] += amt

    save()

    await reply(
        ctx,
        f"You worked hard and got "
        f"{fmt(amt)} {cur()}!",
        GREEN
    )


# ============================================================
# TOP
# ============================================================

@bot.command(name="top")
async def top(ctx):

    ranked = sorted(
        DB["users"].items(),
        key=lambda kv:
            kv[1]["cash"] + kv[1]["bank"],
        reverse=True
    )[:10]

    lines = []

    for n, (uid, d) in enumerate(
        ranked,
        1
    ):

        m = (
            ctx.guild.get_member(
                int(uid)
            )
            if ctx.guild
            else None
        )

        name = (
            m.display_name
            if m
            else f"<@{uid}>"
        )

        lines.append(
            f"**{n}.** {name} — "
            f"{fmt(d['cash'] + d['bank'])} "
            f"{cur()}"
        )

    await reply(
        ctx,
        "\n".join(lines)
        or "Nobody has any money yet.",
        BLUE
    )


# ============================================================
# ADMIN ADD MONEY
# ============================================================

@bot.command(
    name="addmoney",
    usage="addmoney <bank|cash> @user <amount>"
)
@commands.has_permissions(
    administrator=True
)
async def addmoney(
    ctx,
    where: str,
    member: discord.Member,
    amount: int
):

    where = where.lower()

    if where not in (
        "bank",
        "cash"
    ):

        return await reply(
            ctx,
            "Usage: "
            "`$addmoney <bank|cash> @user <amount>`",
            RED
        )

    user_data(
        member.id
    )[where] += amount

    save()

    await reply(
        ctx,
        f"Added {fmt(amount)} {cur()} "
        f"to {member.display_name}'s {where}.",
        GREEN
    )


# ============================================================
# CURRENCY
# ============================================================

@bot.command(
    name="currency",
    usage="currency <emoji>"
)
@commands.has_permissions(
    administrator=True
)
async def currency(
    ctx,
    symbol: str = None
):

    if symbol is None:

        return await reply(
            ctx,
            f"Current currency: {cur()}\n"
            f"Change it with "
            f"`$currency <emoji>`",
            BLUE
        )

    DB["currency"] = symbol

    save()

    await reply(
        ctx,
        f"Currency changed to {symbol}",
        GREEN
    )


# ============================================================
# START
# ============================================================

bot.run(TOKEN)