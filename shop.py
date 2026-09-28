"""
shop.py - Casino role shop ($shop).
Place this file next to the main bot file and add these 2 lines right before `bot.run(TOKEN)`:

    import shop
    shop.install(bot, globals())
"""
import discord

# ================= SETTINGS =================
SHOP_TITLE = "TheCohen Casino Shop"
FOOTER = "Developed By zoharos_ & jx.liran"
COLOR = 0xDDC9A3
THUMBNAIL_URL = None   # put an image link here for the picture on the right; None = server icon

# (name, emoji, role id, price) - cheapest at the top, most expensive at the bottom
ITEMS = [
    ("Casino professional", "🏅", 1554242301927104643, 185_000_000),
    ("Casino Summer",       "🏝️", 1554242805071876116, 285_000_000),
    ("Casino Star",         "🌟", 1554241846165766225, 375_000_000),
    ("Casino Elite",        "🗽", 1554239763006099487, 500_000_000),
    ("Casino Emperor",      "⚜️", 1554240949213724854, 575_000_000),
    ("Casino VIP",          "💎", 1554242535369482371, 650_000_000),
]


def install(bot, g):
    """g = globals() of the main file (DB, user_data, save, fmt, cur, log_money ... are read live from it)."""

    async def say(interaction, text):
        await interaction.response.send_message(text, ephemeral=True)

    async def buy(interaction, item):
        name, emoji, role_id, price = item
        member = interaction.user
        if interaction.guild is None or not isinstance(member, discord.Member):
            return await say(interaction, "This only works inside the server.")
        loaded = g.get("loaded")
        if loaded is not None and not loaded.is_set():
            return await say(interaction, "The bot is still starting, try again in a few seconds.")
        role = interaction.guild.get_role(role_id)
        if role is None:
            return await say(interaction, "This role doesn't exist anymore, tell an admin.")

        fmt, cur = g["fmt"], g["cur"]
        owned = g["DB"].setdefault("shop", {}).setdefault(str(member.id), [])
        if role_id in owned or role in member.roles:
            return await say(interaction, f"You already own **{name}**. Each role can be bought only once.")

        u = g["user_data"](member.id)
        if u["bank"] < price:
            return await say(
                interaction,
                f"You need **{fmt(price)}** {cur()} **in your bank** for {role.mention}.\n"
                f"You have {fmt(u['bank'])} {cur()} in the bank. (`$dep` to deposit)")

        # no awaits between the check and the payment, so a double click can't charge twice
        u["bank"] -= price
        owned.append(role_id)
        g["save"]()
        try:
            await member.add_roles(role, reason="Casino shop")
        except Exception as ex:
            u["bank"] += price
            if role_id in owned:
                owned.remove(role_id)
            g["save"]()
            print("Shop: add_roles failed:", repr(ex))
            return await say(interaction, "I couldn't give you the role (my role must be above it). You were not charged.")

        g["log_money"](member, f"🛒 **shop** — bought **{name}** for **{fmt(price)}** {cur()}", g["YELLOW"])
        await say(interaction, f"✅ You bought {role.mention} for **{fmt(price)}** {cur()} (from your bank).")

    class ShopButton(discord.ui.Button):
        def __init__(self, item, row):
            super().__init__(style=discord.ButtonStyle.secondary, label=item[0], emoji=item[1],
                             custom_id=f"shop:{item[2]}", row=row)
            self.item = item

        async def callback(self, interaction):
            await buy(interaction, self.item)

    class ShopView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)   # persistent: the buttons keep working after a restart
            for i, item in enumerate(ITEMS):
                self.add_item(ShopButton(item, i // 2))

    bot.add_view(ShopView())

    @bot.command(name="shop", usage="shop")
    async def shop(ctx):
        fmt, cur = g["fmt"], g["cur"]
        lines = [f"<@&{rid}> - {fmt(price)} {cur()}" for _, _, rid, price in ITEMS]
        e = discord.Embed(description="\n".join(lines), color=COLOR)
        icon = ctx.guild.icon.url if ctx.guild and ctx.guild.icon else None
        e.set_author(name=SHOP_TITLE, icon_url=icon)
        thumb = THUMBNAIL_URL or icon
        if thumb:
            e.set_thumbnail(url=thumb)
        e.set_footer(text=FOOTER)
        await ctx.send(embed=e, view=ShopView())
