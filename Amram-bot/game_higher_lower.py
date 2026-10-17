
# ================= HIGHER OR LOWER =================

HL_MIN, HL_MAX = 1, 10
HL_RTP = 0.95
HL_FLOOR = 1.05
HL_CAP = 25
HL_SAME = 8
HL_COLOR = 0x9B8CD6

HL_FIXED = {
    (9, "higher"): 4,
    (9, "lower"): 1.2,
    (2, "lower"): 4.2,
    (2, "higher"): 1.1,
}


def hl_mult(first, choice):
    if choice == "same":
        return HL_SAME

    if (first, choice) in HL_FIXED:
        return HL_FIXED[(first, choice)]

    p = (
        HL_MAX - first if choice == "higher"
        else first - HL_MIN
    ) / (HL_MAX - HL_MIN + 1)

    if p <= 0:
        return None

    return round(
        min(HL_CAP, max(HL_FLOOR, HL_RTP / p)), 2
    )


def hl_text(m):
    return "-" if m is None else f"{m:g}x"


def hl_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold else
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]

    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass

    return ImageFont.load_default()


def hl_image(view, second=None, choice=None,
             won=None, net=None, cash=None):

    W, H = 900, 560

    img = Image.new("RGB", (W, H), "#100D1D")
    draw = ImageDraw.Draw(img)

    # Background gradient
    for y in range(H):
        ratio = y / H
        r = int(24 + ratio * 5)
        g = int(16 + ratio * 2)
        b = int(43 + ratio * 12)
        draw.line((0, y, W, y), fill=(r, g, b))

    # Border and header
    draw.rounded_rectangle(
        (12, 12, W - 12, H - 12),
        radius=24,
        outline="#8D70BD",
        width=2
    )

    gold = "#F1D58A"
    white = "#FFFFFF"
    muted = "#B6A8CB"

    draw.text(
        (W // 2, 38),
        "HIGHER OR LOWER",
        font=hl_font(34, True),
        fill=gold,
        anchor="mt"
    )

    draw.text(
        (W // 2, 84),
        "THE MAIN DEALER",
        font=hl_font(15, True),
        fill=muted,
        anchor="mt"
    )

    draw.line((45, 120, W - 45, 120),
              fill="#49365F", width=2)

    # YOUR BET at the top
    draw.text(
        (W // 2, 137),
        "YOUR BET",
        font=hl_font(17, True),
        fill=muted,
        anchor="mt"
    )

    draw.text(
        (W // 2, 162),
        f"{fmt(view.bet)} {cur()}",
        font=hl_font(29, True),
        fill=gold,
        anchor="mt"
    )

    # Number cards
    cards = [
        (85, 225, 410, 365),
        (490, 225, 815, 365)
    ]

    for box in cards:
        draw.rounded_rectangle(
            box,
            radius=20,
            fill="#211832",
            outline="#76589B",
            width=2
        )

    draw.text(
        (247, 240),
        "FIRST NUMBER",
        font=hl_font(15, True),
        fill=muted,
        anchor="mt"
    )

    draw.text(
        (247, 275),
        str(view.first),
        font=hl_font(66, True),
        fill=white,
        anchor="mt"
    )

    draw.text(
        (652, 240),
        "NEXT NUMBER",
        font=hl_font(15, True),
        fill=muted,
        anchor="mt"
    )

    second_text = "?" if second is None else str(second)

    draw.text(
        (652, 275),
        second_text,
        font=hl_font(66, True),
        fill=gold if second is None else white,
        anchor="mt"
    )

    # Result or selection prompt
    if second is None:
        prompt = "PREDICT THE NEXT NUMBER"
        prompt_color = muted
    else:
        prompt = "YOU WON!" if won else "YOU LOST"
        prompt_color = "#75E0A0" if won else "#FF858D"

    draw.text(
        (W // 2, 385),
        prompt,
        font=hl_font(20, True),
        fill=prompt_color,
        anchor="mt"
    )

    # Three multiplier panels
    panels = [
        (35, 435, 295, 510, "HIGHER", "higher", "#65DDA0"),
        (320, 435, 580, 510, "SAME", "same", gold),
        (605, 435, 865, 510, "LOWER", "lower", "#FF9299"),
    ]

    for x1, y1, x2, y2, label, key, color in panels:
        draw.rounded_rectangle(
            (x1, y1, x2, y2),
            radius=14,
            fill="#211832",
            outline=color,
            width=2
        )

        draw.text(
            ((x1 + x2) // 2, y1 + 8),
            label,
            font=hl_font(15, True),
            fill=color,
            anchor="mt"
        )

        draw.text(
            ((x1 + x2) // 2, y1 + 35),
            hl_text(view.mults[key]),
            font=hl_font(20, True),
            fill=white,
            anchor="mt"
        )

    # Result balance
    if second is not None:
        draw.rounded_rectangle(
            (225, 518, 675, 548),
            radius=10,
            fill="#302044"
        )

        draw.text(
            (W // 2, 521),
            f"BALANCE: {fmt(cash)} {cur()}",
            font=hl_font(14, True),
            fill=gold,
            anchor="mt"
        )

    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)

    return discord.File(output, filename="higher_lower.png")


class HigherLower(OwnedView):
    def __init__(self, user, bet, token=None):
        super().__init__(timeout=60)

        self.user = user
        self.bet = bet
        self.token = token
        self.message = None
        self.settled = False

        self.first = random.randint(HL_MIN, HL_MAX)

        self.mults = {
            c: hl_mult(self.first, c)
            for c in ("higher", "same", "lower")
        }

        self.higher.disabled = self.mults["higher"] is None
        self.lower.disabled = self.mults["lower"] is None

    def embed(self):
        e = discord.Embed(
            color=HL_COLOR,
            title="🎲 Higher or Lower"
        )

        e.set_image(url="attachment://higher_lower.png")
        return e

    async def guess(self, interaction, choice):
        if self.settled:
            return await interaction.response.defer()

        self.settled = True

        def hit(number):
            return (
                (number > self.first and choice == "higher")
                or (number < self.first and choice == "lower")
                or (number == self.first and choice == "same")
            )

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

        log_game(
            self.user,
            "higher or lower",
            self.bet,
            net
        )

        BUSY.discard(self.user.id)
        self.stop()

        cash = user_data(self.user.id)["cash"]

        head = (
            f"You won {fmt(net)} {cur()}!"
            if net > 0
            else f"You lost {fmt(self.bet)} {cur()}."
        )

        e = discord.Embed(
            color=GREEN if won else RED,
            title="🎲 Higher or Lower",
            description=(
                f"**{head}**\n\n"
                f"Your choice: `{choice.title()}`\n"
                f"First number: `{self.first}`\n"
                f"Second number: `{second}`\n\n"
                f"**Balance:** `{fmt(cash)} {cur()}`"
            )
        )

        file = hl_image(
            self,
            second=second,
            choice=choice,
            won=won,
            net=net,
            cash=cash
        )

        e.set_image(url="attachment://higher_lower.png")

        await interaction.response.edit_message(
            embed=e,
            attachments=[file],
            view=None
        )

    @discord.ui.button(
        label="Higher",
        style=discord.ButtonStyle.primary
    )
    async def higher(self, interaction, button):
        await self.guess(interaction, "higher")

    @discord.ui.button(
        label="Same",
        style=discord.ButtonStyle.primary
    )
    async def same(self, interaction, button):
        await self.guess(interaction, "same")

    @discord.ui.button(
        label="Lower",
        style=discord.ButtonStyle.primary
    )
    async def lower(self, interaction, button):
        await self.guess(interaction, "lower")

    async def on_timeout(self):
        if not self.settled:
            await refund_timeout(self, "higher or lower")


@bot.command(
    name="hl",
    aliases=["high-low", "highlow"],
    usage="hl <amount | half | all>"
)
async def hl(ctx, amount: str = None):
    bet = await take_bet(
        ctx,
        amount,
        "hl <amount | half | all>",
        track=True
    )

    if not bet:
        return

    BUSY.add(ctx.author.id)

    view = HigherLower(
        ctx.author,
        bet,
        str(ctx.message.id)
    )

    try:
        file = hl_image(view)

        view.message = await ctx.reply(
            embed=view.embed(),
            file=file,
            view=view,
            mention_author=False
        )

    except Exception:
        cancel_game(ctx.author, view.token, bet)
        BUSY.discard(ctx.author.id)
        raise
