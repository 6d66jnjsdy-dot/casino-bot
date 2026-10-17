import discord, asyncio
from core import *

# ================= SHOP =================
SHOP_TITLE = "Amram Casino Shop"
SHOP_COLOR = 0xDDC9A3
RECEIPT_COLOR = 0x57F287

# (name, role_id, price)
SHOP_ITEMS = [
    ("High Roller",   1554242301927104643, 175_000_000),
    ("Poker Royale",  1554242805071876116, 225_000_000),
    ("Whale Player",  1554241846165766225, 350_000_000),
    ("Action Junkie", 1554239763006099487, 425_000_000),
    ("APEX Gambling", 1554240949213724854, 500_000_000),
    ("Royale Flush",  1554242535369482371, 675_000_000),
]

# what each role gives (shown under the role in the shop)
SHOP_PERKS = {
    "High Roller":   "+5% profit in Mines",
    "Poker Royale":  "Rob cooldown reduced to 5 minutes",
    "Whale Player":  "10% extra luck in Blackjack and Poker",
    "Action Junkie": "+7.5% profit in Gold Mines (gm)",
    "APEX Gambling": "1.5B paid into your bank every day at 00:00",
    "Royale Flush":  "$bonus: +25% profit for 10 minutes, every 24 hours",
}

SHOP_BUSY = set()
SHOP_REGISTERED = False


async def shop_say(interaction, text):
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


class ReceiptLayout(discord.ui.LayoutView):
    def __init__(self, role, price, bank_after):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay(f"## Purchase Complete\n{role.mention}"),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                f"**Price**\n{fmt(price)} {cur()}\n\n"
                f"**Bank balance**\n{fmt(bank_after)} {cur()}"),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay("-# The role is yours permanently."),
            accent_colour=discord.Colour(RECEIPT_COLOR)))


async def shop_buy(interaction, item):
    name, role_id, price = item
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
    await interaction.followup.send(view=ReceiptLayout(role, price, bank_after), ephemeral=True)
    return True


class ShopButton(discord.ui.Button):
    def __init__(self, item):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="Buy",
            custom_id=f"shop:buy:{item[1]}")
        self.item = item

    async def callback(self, interaction):
        await shop_buy(interaction, self.item)


class ShopLayout(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)

        parts = [
            discord.ui.TextDisplay(f"## {SHOP_TITLE}\nBuy a role once, paid from your **bank**."),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        ]

        for item in SHOP_ITEMS:
            name, rid, price = item
            perk = SHOP_PERKS.get(name, "")
            parts.append(discord.ui.Section(
                f"### <@&{rid}>\n**{fmt(price)}** {cur()}\n-# {perk}",
                accessory=ShopButton(item)))

        parts.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small))
        parts.append(discord.ui.TextDisplay("-# Roles are permanent and paid from your bank. Use $dep to deposit."))

        self.add_item(discord.ui.Container(*parts, accent_colour=discord.Colour(SHOP_COLOR)))


@bot.listen("on_ready")
async def shop_register_view():
    """Registers the shop buttons once so they keep working 24/7, even after a restart."""
    global SHOP_REGISTERED
    if not SHOP_REGISTERED:
        bot.add_view(ShopLayout())
        SHOP_REGISTERED = True


@bot.command(name="shop", usage="shop")
async def shop(ctx):
    try:
        await ctx.send(view=ShopLayout())
    except Exception as ex:
        await ctx.send(f"Shop error: `{type(ex).__name__}: {ex}`"[:1900])
