import discord, time
from discord.ext import commands, tasks
from core import *

# ================= SHOP ROLE POWERS =================
ROLE = {name: rid for name, rid, _ in SHOP_ITEMS}

PCT_MINES = 0.05            # High Roller: +5% profit in regular $mines
PCT_GM = 0.075              # Action Junkie: +7.5% profit in gm
WHALE_LUCK = 0.10           # Whale Player: 10% luck in blackjack / poker
LUCK_GAMES = ("bj", "blackjack", "poker")
ROB_COOLDOWN_PERK = 300     # Poker Royale: rob cooldown of 5 minutes
APEX_DAILY = 1_500_000_000  # APEX Gambling: paid into the bank every day at 00:00
PCT_BONUS = 0.25            # Royale Flush: Bonus button
BONUS_SECONDS = 600         # lasts 10 minutes
BONUS_COOLDOWN = 86400      # once every 24 hours per player

PERKS_REGISTERED = False


def has_role(uid, role_id):
    if not role_id:
        return False
    for g in bot.guilds:
        m = g.get_member(uid)
        if m and m.get_role(role_id):
            return True
    return False


def bonus_state(uid):
    return DB.setdefault("bonus", {}).get(str(uid), {})


def bonus_active(uid):
    return bonus_state(uid).get("until", 0) > time.time()


# ---------- hooks used by the games ----------
def perk_extra(uid, game, net):
    """Extra winnings on top of a win. net = profit of the win. game: 'mines', 'gm', ..."""
    if net <= 0:
        return 0
    pct = 0.0
    if game == "mines" and has_role(uid, ROLE.get("High Roller")):
        pct += PCT_MINES
    if game == "gm" and has_role(uid, ROLE.get("Action Junkie")):
        pct += PCT_GM
    if bonus_active(uid):
        pct += PCT_BONUS
    return int(net * pct)


def perk_luck(uid, game):
    """Chance (0-1) of an extra attempt in this game."""
    if game in LUCK_GAMES and has_role(uid, ROLE.get("Whale Player")):
        return WHALE_LUCK
    return 0.0


def rob_cooldown(ctx):
    """Use with @commands.dynamic_cooldown(rob_cooldown, commands.BucketType.user)."""
    secs = ROB_COOLDOWN_PERK if has_role(ctx.author.id, ROLE.get("Poker Royale")) else ROB_COOLDOWN
    return commands.Cooldown(1, secs)


# ---------- APEX Gambling: daily payout ----------
@tasks.loop(seconds=30)
async def apex_loop():
    await loaded.wait()
    key = today_key()
    last = DB.get("apex_day")
    if last is None:                    # first run: start counting from today, no payout
        DB["apex_day"] = key
        save()
        return
    if last == key:
        return
    DB["apex_day"] = key
    role_id = ROLE.get("APEX Gambling")
    for g in bot.guilds:
        role = g.get_role(role_id)
        if role is None:
            continue
        for m in role.members:
            if m.bot:
                continue
            user_data(m.id)["bank"] += APEX_DAILY
            log_money(m, "APEX DAILY", f"Daily payout: +{fmt(APEX_DAILY)} {cur()}", GREEN)
    save()


# ---------- Royale Flush: one shared Bonus message ----------
class BonusButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.success, label="Bonus 25%", custom_id="perks:bonus")

    async def callback(self, interaction):
        member = interaction.user
        rid = ROLE.get("Royale Flush")
        if not isinstance(member, discord.Member) or not rid or not member.get_role(rid):
            return await interaction.response.send_message(
                f"Only <@&{rid}> holders can use this.", ephemeral=True)
        if loaded is None or not loaded.is_set():
            return await interaction.response.send_message(
                "The bot is still starting. Try again in a few seconds.", ephemeral=True)

        st = bonus_state(member.id)
        now = time.time()
        if st.get("until", 0) > now:
            return await interaction.response.send_message(
                f"Your bonus is already active until <t:{int(st['until'])}:R>.", ephemeral=True)
        if st.get("next", 0) > now:
            return await interaction.response.send_message(
                f"You can use the bonus again <t:{int(st['next'])}:R>.", ephemeral=True)

        DB.setdefault("bonus", {})[str(member.id)] = {"until": now + BONUS_SECONDS, "next": now + BONUS_COOLDOWN}
        save()
        await interaction.response.send_message(
            f"**Bonus 25% is active.**\n+25% on all your profits until <t:{int(now + BONUS_SECONDS)}:R>.",
            ephemeral=True)


class BonusLayout(discord.ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        rid = ROLE.get("Royale Flush")
        self.add_item(discord.ui.Container(
            discord.ui.TextDisplay(f"## Royale Flush Bonus\nExclusive to <@&{rid}> holders."),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            discord.ui.Section(
                "### +25% profit\nOn every win, for **10 minutes**.\n-# Once every 24 hours",
                accessory=BonusButton()),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay("-# Press the button to activate your bonus."),
            accent_colour=discord.Colour(SHOP_COLOR)))


@bot.listen("on_ready")
async def perks_start():
    global PERKS_REGISTERED
    if not apex_loop.is_running():
        apex_loop.start()
    if not PERKS_REGISTERED:
        bot.add_view(BonusLayout())       # keeps the Bonus button working 24/7, even after a restart
        PERKS_REGISTERED = True


@bot.command(name="bonus", usage="bonus")
async def bonus(ctx):
    if ctx.author.id not in OWNER_IDS:
        return await reply(ctx, "Use the pinned **Bonus** message.", RED)
    await ctx.send(view=BonusLayout())
