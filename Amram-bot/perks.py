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
PCT_BONUS = 0.25            # Royale Flush: $bonus
BONUS_SECONDS = 600         # lasts 10 minutes
BONUS_COOLDOWN = 86400      # once every 24 hours


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


@bot.listen("on_ready")
async def perks_start():
    if not apex_loop.is_running():
        apex_loop.start()


# ---------- Royale Flush: $bonus ----------
class BonusView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=120)
        self.user = user
        self.message = None

    @discord.ui.button(label="Bonus 25%", style=discord.ButtonStyle.success)
    async def activate(self, interaction, button):
        uid = self.user.id
        st = bonus_state(uid)
        now = time.time()
        if st.get("next", 0) > now:
            return await interaction.response.send_message(
                f"Available again <t:{int(st['next'])}:R>.", ephemeral=True)
        DB["bonus"][str(uid)] = {"until": now + BONUS_SECONDS, "next": now + BONUS_COOLDOWN}
        save()
        self.stop()
        await interaction.response.edit_message(
            embed=make_embed(self.user,
                             f"**Bonus 25% is active**\n+25% on all your profits until <t:{int(now + BONUS_SECONDS)}:R>.",
                             GREEN, "Bonus"),
            view=None)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your bonus. Type `$bonus`.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for b in self.children:
            b.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


@bot.command(name="bonus", usage="bonus")
async def bonus(ctx):
    uid = ctx.author.id
    if not (has_role(uid, ROLE.get("Royale Flush")) or uid in OWNER_IDS):
        return await reply(ctx, "This command is for **Royale Flush** holders.", RED)
    st = bonus_state(uid)
    now = time.time()
    if st.get("until", 0) > now:
        return await reply(ctx, f"Your bonus is active until <t:{int(st['until'])}:R>.", GREEN)
    if st.get("next", 0) > now:
        return await reply(ctx, f"Your next bonus is available <t:{int(st['next'])}:R>.", RED)
    view = BonusView(ctx.author)
    view.message = await ctx.reply(
        embed=make_embed(ctx.author, "Activate **+25% profit** for **10 minutes**.\nUsable once every 24 hours.",
                         GREEN, "Bonus"),
        view=view, mention_author=False)
