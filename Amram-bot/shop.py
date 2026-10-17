import discord, asyncio
from core import *
from shop_art import render_shop

# ================= SHOP =================
SHOP_TITLE = "AMRAM CASINO"
SHOP_SUBTITLE = "ROLE SHOP"

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
    # אחרי defer חייבים followup, לפני זה send_message
    if interaction.response.is_done():
        await interaction.followup.send(text, ephemeral=True)
    else:
        await interaction.response.send_message(text, ephemeral=True)


async def shop_buy(interaction, item):
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
        # עונים לדיסקורד מיד כדי לא לפספס את חלון ה-3 שניות
        await interaction.response.defer(ephemeral=True)

        # בדיקה חוזרת אחרי ה-await, למקרה שהיתרה השתנתה
        u = user_data(member.id)
        if u["bank"] < price:
            return await shop_say(interaction, "You don't have enough in your bank anymore.")

        u["bank"] -= price
        save()
        try:
            await member.add_roles(role, reason="Casino shop")
        except BaseException as ex:
            # החזר כסף גם בביטול (CancelledError) וגם בשגיאה רגילה
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


class ShopButton(discord.ui.Button):
    def __init__(self, item, row):
        super().__init__(style=discord.ButtonStyle.secondary,
                         label=f"{item[0]} · {item[3] // 1_000_000}M",
                         emoji=item[1], custom_id=f"shop:{item[2]}", row=row)
        self.item = item

    async def callback(self, interaction):
        await shop_buy(interaction, self.item)


class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i, item in enumerate(SHOP_ITEMS):
            self.add_item(ShopButton(item, i // 2))


# הכפתורים ימשיכו לעבוד גם אחרי ריסטארט של הבוט
_shop_view_added = False

@bot.listen("on_ready")
async def _shop_register_view():
    global _shop_view_added
    if not _shop_view_added:
        bot.add_view(ShopView())
        _shop_view_added = True


@bot.command(name="shop", usage="shop")
async def shop(ctx):
    try:
        colors = []
        for _, _, rid, _ in SHOP_ITEMS:
            role = ctx.guild.get_role(rid) if ctx.guild else None
            colors.append((role.color.r, role.color.g, role.color.b)
                          if role and role.color.value else None)

        owned = ({r.id for r in ctx.author.roles}
                 if isinstance(ctx.author, discord.Member) else set())

        buf = await asyncio.to_thread(
            render_shop, SHOP_ITEMS, SHOP_TITLE, SHOP_SUBTITLE, colors, owned)
        await ctx.send(file=discord.File(buf, "shop.png"), view=ShopView())
    except Exception as ex:
        await ctx.send(f"Shop error: `{type(ex).__name__}: {ex}`"[:1900])
