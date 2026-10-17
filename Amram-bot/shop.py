import discord, asyncio
from core import *

# ================= SHOP =================
SHOP_TITLE = "Amram Casino Shop"
SHOP_COLOR = 0xDDC9A3
RECEIPT_COLOR = 0x57F287

SHOP_ITEMS = [
    ("Casino Joker",   "🃏", 1554242301927104643, 175_000_000),
    ("Casino Master",  "💎", 1554242805071876116, 225_000_000),
    ("Casino Dealer",  "🤵", 1554241846165766225, 350_000_000),
    ("Casino Legend",  "🗽", 1554239763006099487, 425_000_000),
    ("Casino Royalty", "🌟", 1554240949213724854, 500_000_000),
    ("Casino Emperor", "👑", 1554242535369482371, 675_000_000),
]

SHOP_BUSY = set()


def header_text():
    return f"# 🎰 {SHOP_TITLE}\n-# Exclusive roles · permanent · paid from your bank"


def balance_text(bank):
    return f"**💰 Bank balance**\n## {fmt(bank)} {cur()}"


def item_text(item, owned, bank):
    name, emoji, rid, price = item
    if owned:
        status = "-# ✅ Owned"
    elif bank >= price:
        status = "-# 🟢 Ready to buy"
    else:
        pct = bank / price
        filled = int(pct * 10)
        bar = "▰" * filled + "▱" * (10 - filled)
        status = f"-# {bar} {int(pct * 100)}% · {fmt(price - bank)} {cur()} to go"
    return f"### {emoji}  <@&{rid}>\n**{fmt(price)}** {cur()}\n{status}"


async def shop_say(interaction, text):
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


class ReceiptLayout(discord.ui.LayoutView):
    def __init__(self, emoji, role, price, bank_after):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay("# ✅ Purchase Complete"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(f"### {emoji}  {role.mention}"),
            discord.ui.TextDisplay(
                f"**Paid**\n{fmt(price)} {cur()}\n\n"
                f"**Remaining in bank**\n{fmt(bank_after)} {cur()}"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay("-# The role is yours permanently. Thank you for shopping!"),
            accent_colour=discord.Colour(RECEIPT_COLOR)))


async def shop_buy(interaction, item):
    """Returns True only if the purchase succeeded."""
    name, emoji, role_id, price = item
    member = interaction.user

    if interaction.guild is None or not isinstance(member, discord.Member):
        return await shop_say(interaction, "The shop only works inside the server.")
    if loaded is None or not loaded.is_set():
        return await shop_say(interaction, "The bot is still starting. Try again in a few seconds.")

    role = interaction.guild.get_role(role_id)
    if role is None:
        return await shop_say(interaction, "This role no longer exists. Please contact an admin.")
    if role in member.roles:
        return await shop_say(interaction, f"You already own **{name}**.")
    if role >= interaction.guild.me.top_role:
        return await shop_say(interaction, "I can't assign this role because it's above my highest role. Please contact an admin.")

    key = (member.id, role_id)
    if key in SHOP_BUSY:
        return await shop_say(interaction, "Your purchase is already being processed.")

    u = user_data(member.id)
    if u["bank"] < price:
        return await shop_say(
            interaction,
            f"Insufficient funds for {role.mention}.\n"
            f"**Price:** {fmt(price)} {cur()}\n"
            f"**Your bank:** {fmt(u['bank'])} {cur()}\n"
            f"Use `$dep` to deposit.")

    SHOP_BUSY.add(key)
    try:
        await interaction.response.defer(ephemeral=True)

        u = user_data(member.id)
        if u["bank"] < price:
            return await shop_say(interaction, "Your bank balance is no longer sufficient.")

        u["bank"] -= price
        save()
        try:
            await member.add_roles(role, reason="Casino shop")
        except BaseException as ex:
            u["bank"] += price
            save()
            if not isinstance(ex, Exception):
                raise
            print("Shop: add_roles failed:", repr(ex))
            return await shop_say(interaction, "I couldn't assign the role. You were not charged.")
        bank_after = u["bank"]
    finally:
        SHOP_BUSY.discard(key)

    log_money(member, "SHOP", f"Bought {name} for {fmt(price)} {cur()}", YELLOW)
    await interaction.followup.send(view=ReceiptLayout(emoji, role, price, bank_after), ephemeral=True)
    return True


class ShopButton(discord.ui.Button):
    def __init__(self, item):
        super().__init__(style=discord.ButtonStyle.primary, label="Buy")
        self.item = item
        self.layout = None

    async def callback(self, interaction):
        if await shop_buy(interaction, self.item):
            try:
                self.layout.owned.add(self.item[2])
                self.layout.refresh(user_data(interaction.user.id)["bank"])
                await interaction.message.edit(view=self.layout)
            except Exception as ex:
                print("Shop: refresh failed:", repr(ex))


class ShopLayout(discord.ui.LayoutView):
    def __init__(self, owner_id, owned_ids, bank):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.owned = set(owned_ids)
        self.message = None
        self.rows = []  # (item, text_display, button)

        self.balance = discord.ui.TextDisplay(balance_text(bank))
        parts = [
            discord.ui.TextDisplay(header_text()),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            self.balance,
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        ]

        for i, item in enumerate(SHOP_ITEMS):
            text = discord.ui.TextDisplay("-")
            btn = ShopButton(item)
            btn.layout = self
            self.rows.append((item, text, btn))
            parts.append(discord.ui.Section(text, accessory=btn))
            if i < len(SHOP_ITEMS) - 1:
                parts.append(discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small))

        parts.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large))
        parts.append(discord.ui.TextDisplay("-# Need more funds? Use $dep to deposit your cash into the bank."))

        self.add_item(discord.ui.Container(*parts, accent_colour=discord.Colour(SHOP_COLOR)))
        self.refresh(bank)

    def refresh(self, bank):
        self.balance.content = balance_text(bank)
        for item, text, btn in self.rows:
            owned = item[2] in self.owned
            text.content = item_text(item, owned, bank)
            if owned:
                btn.style = discord.ButtonStyle.secondary
                btn.label = "Owned"
                btn.disabled = True
            elif bank >= item[3]:
                btn.style = discord.ButtonStyle.success
                btn.label = "Buy"
                btn.disabled = False
            else:
                btn.style = discord.ButtonStyle.secondary
                btn.label = "Buy"
                btn.disabled = False

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This isn't your shop. Type `$shop` to open your own.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for _, _, b in self.rows:
            b.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


@bot.command(name="shop", usage="shop")
async def shop(ctx):
    try:
        owned = {r.id for r in ctx.author.roles} if isinstance(ctx.author, discord.Member) else set()
        bank = user_data(ctx.author.id)["bank"]
        view = ShopLayout(ctx.author.id, owned, bank)
        view.message = await ctx.send(view=view)
    except Exception as ex:
        await ctx.send(f"Shop error: `{type(ex).__name__}: {ex}`"[:1900])
