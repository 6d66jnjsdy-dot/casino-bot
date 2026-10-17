import discord, asyncio
from core import *

# ================= SHOP =================
SHOP_TITLE = "Amram Casino Shop"
SHOP_COLOR = 0xDDC9A3
SHOP_THUMBNAIL = None

SHOP_ITEMS = [
    ("Casino Joker",   "🃏", 1554242301927104643, 175_000_000),
    ("Casino Master",  "💎", 1554242805071876116, 225_000_000),
    ("Casino Dealer",  "🤵", 1554241846165766225, 350_000_000),
    ("Casino Legend",  "🗽", 1554239763006099487, 425_000_000),
    ("Casino Royalty", "🌟", 1554240949213724854, 500_000_000),
    ("Casino Emperor", "👑", 1554242535369482371, 675_000_000),
]

SHOP_BUSY = set()


async def shop_say(interaction, text):
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


async def shop_buy(interaction, item):
    """מחזיר True רק אם הקנייה הצליחה."""
    name, emoji, role_id, price = item
    member = interaction.user

    if interaction.guild is None or not isinstance(member, discord.Member):
        return await shop_say(interaction, "This only works inside the server.")
    if loaded is None or not loaded.is_set():
        return await shop_say(interaction, "The bot is still starting, try again in a few seconds.")

    role = interaction.guild.get_role(role_id)
    if role is None:
        return await shop_say(interaction, "This role doesn't exist anymore, tell an admin.")
    if role in member.roles:
        return await shop_say(interaction, f"You already have **{name}**.")
    if role >= interaction.guild.me.top_role:
        return await shop_say(interaction, "I can't assign this role (it's above my role), tell an admin.")

    key = (member.id, role_id)
    if key in SHOP_BUSY:
        return await shop_say(interaction, "Your purchase is already being processed.")

    u = user_data(member.id)
    if u["bank"] < price:
        return await shop_say(
            interaction,
            f"You need **{fmt(price)}** {cur()} **in your bank** for {role.mention}.\n"
            f"You have {fmt(u['bank'])} {cur()} in the bank. (`$dep` to deposit)")

    SHOP_BUSY.add(key)
    try:
        await interaction.response.defer(ephemeral=True)

        u = user_data(member.id)
        if u["bank"] < price:
            return await shop_say(interaction, "You don't have enough in your bank anymore.")

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
            return await shop_say(interaction, "I couldn't give you the role. You were not charged.")
    finally:
        SHOP_BUSY.discard(key)

    log_money(member, "SHOP", f"Bought {name} for {fmt(price)} {cur()}", YELLOW)
    await shop_say(interaction, f"✅ You bought {role.mention} for **{fmt(price)}** {cur()} (from your bank).")
    return True


class ShopButton(discord.ui.Button):
    def __init__(self, item, owned):
        super().__init__(
            style=discord.ButtonStyle.success if owned else discord.ButtonStyle.primary,
            label="Owned ✓" if owned else "Buy", disabled=owned)
        self.item = item
        self.layout = None

    async def callback(self, interaction):
        if await shop_buy(interaction, self.item):
            self.style = discord.ButtonStyle.success
            self.label = "Owned ✓"
            self.disabled = True
            try:
                await interaction.message.edit(view=self.layout)
            except Exception as ex:
                print("Shop: refresh failed:", repr(ex))


class ShopLayout(discord.ui.LayoutView):
    def __init__(self, owner_id, owned_ids, icon):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.message = None
        self.buttons = []

        parts = []
        title = f"## 🎰 {SHOP_TITLE}\nBuy a role once, paid from your **bank**. Use `$dep` to deposit."
        if icon:
            parts.append(discord.ui.Section(title, accessory=discord.ui.Thumbnail(media=icon)))
        else:
            parts.append(discord.ui.TextDisplay(title))
        parts.append(discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large))

        for item in SHOP_ITEMS:
            name, emoji, rid, price = item
            btn = ShopButton(item, rid in owned_ids)
            btn.layout = self
            self.buttons.append(btn)
            parts.append(discord.ui.Section(
                f"### {emoji} <@&{rid}>\n**{fmt(price)}** {cur()}",
                accessory=btn))

        self.add_item(discord.ui.Container(*parts, accent_colour=discord.Colour(SHOP_COLOR)))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This is not your shop, type `$shop` to open yours.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for b in self.buttons:
            b.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


@bot.command(name="shop", usage="shop")
async def shop(ctx):
    try:
        icon = ctx.guild.icon.url if ctx.guild and ctx.guild.icon else None
        icon = SHOP_THUMBNAIL or icon
        owned = {r.id for r in ctx.author.roles} if isinstance(ctx.author, discord.Member) else set()
        view = ShopLayout(ctx.author.id, owned, icon)
        view.message = await ctx.send(view=view)
    except Exception as ex:
        await ctx.send(f"Shop error: `{type(ex).__name__}: {ex}`"[:1900])
