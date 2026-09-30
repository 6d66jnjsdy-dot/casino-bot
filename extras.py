"""
extras.py  -  קובץ נפרד שיושב באותה תיקייה של bot.py

מה בפנים:
  !set-role-member   פאנל עם כפתור לקבלת רול (עובד רק בחדר שהוגדר)
  !clear <כמות>      מוחק עד 350 הודעות (רק למי שיש את הרול שהוגדר)
  הגנה מבוטים       מי שמוסיף בוט לשרת נזרק (kick) והבוט נזרק איתו

הבוט (bot.py) טוען את הקובץ הזה אוטומטית.
"""
import asyncio
import discord
from discord.ext import commands

# ================= הגדרות =================
OWNER_ID = 1537816435370229820
PANEL_CHANNEL_ID = 1554654227471532122      # החדר שבו מותר לכתוב !set-role-member
MEMBER_ROLE_ID = 1554653683869028392        # הרול שהכפתור נותן
CLEAR_ROLE_ID = 1554640813798203442         # מי שיש לו את הרול הזה יכול להשתמש ב-!clear
CLEAR_MAX = 350                             # מקסימום הודעות למחיקה בפקודה אחת
LOG_CHANNEL_ID = 0                          # חדר להתראות הגנה (0 = בלי התראה בחדר)
BOT_ADD_ALLOWED = {OWNER_ID}                # מי שמותר לו להוסיף בוטים (בעל הבוט). רוקנו את הסט כדי לחסום גם אותו

GOLD = 0xF1C40F
GREEN = 0x2ECC71
RED = 0xE74C3C
BLURPLE = 0x5865F2


def is_admin_or_owner(member):
    return member.id == OWNER_ID or member.guild_permissions.administrator


# ================= כפתור הרול =================
class RoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)   # קבוע: הכפתור ממשיך לעבוד גם אחרי ריסטארט

    @discord.ui.button(label="לחץ לקבלת גישה", emoji="🔓", style=discord.ButtonStyle.success,
                       custom_id="extras:member_role")
    async def get_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        member, guild = interaction.user, interaction.guild
        role = guild.get_role(MEMBER_ROLE_ID) if guild else None
        if role is None:
            return await interaction.response.send_message("❌ הרול לא נמצא, פנה למנהל.", ephemeral=True)
        if role in member.roles:
            return await interaction.response.send_message(f"✅ כבר יש לך את הרול {role.mention}.", ephemeral=True)
        try:
            await member.add_roles(role, reason="Role panel button")
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ אין לי הרשאה לתת את הרול (הרול של הבוט חייב להיות מעליו).", ephemeral=True)
        except discord.HTTPException:
            return await interaction.response.send_message("❌ משהו השתבש, נסה שוב.", ephemeral=True)
        await interaction.response.send_message(f"🎉 קיבלת את הרול {role.mention}! עכשיו אפשר לראות את כל החדרים.",
                                                ephemeral=True)


def panel_embed(guild):
    e = discord.Embed(
        title="🔓 גישה מלאה לשרת",
        description=(f"לקבלת הרול <@&{MEMBER_ROLE_ID}> ולראות את כל החדרים יש ללחוץ על הכפתור למטה."),
        color=GOLD)
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)
    return e


# ================= הקוג =================
class Extras(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- פקודות עם ! ----------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        text = message.content.strip()
        if not text.startswith("!"):
            return
        parts = text[1:].split()
        if not parts:
            return
        name, args = parts[0].lower(), parts[1:]
        if name in ("set-role-member", "setrole", "set-role"):
            await self.cmd_setrole(message)
        elif name == "clear":
            await self.cmd_clear(message, args)

    async def cmd_setrole(self, message):
        if not is_admin_or_owner(message.author):
            return
        if message.channel.id != PANEL_CHANNEL_ID:
            return await message.reply(f"הפקודה עובדת רק בחדר <#{PANEL_CHANNEL_ID}>.", delete_after=8,
                                       mention_author=False)
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        await message.channel.send(embed=panel_embed(message.guild), view=RoleView())

    async def cmd_clear(self, message, args):
        author = message.author
        if not any(r.id == CLEAR_ROLE_ID for r in author.roles):
            return
        channel = message.channel
        if not args or not args[0].isdigit() or int(args[0]) < 1:
            return await channel.send(embed=discord.Embed(
                description=f"שימוש: `!clear <כמות>` (עד {CLEAR_MAX})", color=RED), delete_after=8)
        amount = min(int(args[0]), CLEAR_MAX)
        if not channel.permissions_for(message.guild.me).manage_messages:
            return await channel.send(embed=discord.Embed(
                description="❌ אין לי הרשאת **Manage Messages** בחדר הזה.", color=RED), delete_after=8)
        try:
            await message.delete()
        except discord.HTTPException:
            pass
        try:
            deleted = await channel.purge(limit=amount, check=lambda m: not m.pinned)
        except discord.HTTPException as ex:
            return await channel.send(embed=discord.Embed(description=f"❌ המחיקה נכשלה: `{ex}`", color=RED),
                                      delete_after=8)
        note = f"\nהוגבל למקסימום של {CLEAR_MAX}." if int(args[0]) > CLEAR_MAX else ""
        await channel.send(embed=discord.Embed(
            description=f"🧹 נמחקו **{len(deleted)}** הודעות על ידי {author.mention}.{note}", color=GREEN),
            delete_after=5, allowed_mentions=discord.AllowedMentions.none())

    # ---------- הגנה: אי אפשר להוסיף בוטים ----------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot or member.id == self.bot.user.id:
            return
        guild = member.guild

        # מחפשים ביומן הפעולות מי הוסיף את הבוט (לפעמים לוקח רגע שהרשומה תופיע)
        adder = None
        for _ in range(4):
            try:
                async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.bot_add):
                    if entry.target and entry.target.id == member.id:
                        adder = entry.user
                        break
            except discord.Forbidden:
                break
            if adder:
                break
            await asyncio.sleep(1.5)

        if adder and adder.id in BOT_ADD_ALLOWED:
            return

        results = []
        try:
            await member.kick(reason="Anti-bot protection: bots cannot be added")
            results.append(f"🤖 הבוט **{member.name}** הוסר")
        except discord.HTTPException:
            results.append(f"⚠️ לא הצלחתי להסיר את הבוט **{member.name}**")

        if adder is None:
            results.append("❓ לא הצלחתי לזהות מי הוסיף אותו (חסרה הרשאת View Audit Log)")
        elif adder.id == guild.owner_id or adder.id == self.bot.user.id:
            results.append(f"👑 {adder.mention} הוא בעל השרת, אי אפשר להעיף אותו")
        else:
            target = guild.get_member(adder.id)
            try:
                if target is None:
                    raise discord.NotFound
                await target.kick(reason=f"Anti-bot protection: added bot {member.name}")
                results.append(f"👢 {adder.mention} הועף מהשרת")
            except (discord.HTTPException, AttributeError):
                results.append(f"⚠️ לא הצלחתי להעיף את {adder.mention} (הרול שלו גבוה משלי)")

        await self.report(guild, member, adder, results)

    async def report(self, guild, bot_member, adder, results):
        if not LOG_CHANNEL_ID:
            return
        channel = guild.get_channel(LOG_CHANNEL_ID)
        if channel is None:
            return
        e = discord.Embed(title="🛡️ הגנה מבוטים הופעלה", description="\n".join(results), color=RED,
                          timestamp=discord.utils.utcnow())
        e.add_field(name="הבוט", value=f"{bot_member.name} (`{bot_member.id}`)", inline=True)
        e.add_field(name="הוסיף", value=f"{adder.name} (`{adder.id}`)" if adder else "לא ידוע", inline=True)
        try:
            await channel.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            pass


async def setup(bot):
    bot.add_view(RoleView())
    await bot.add_cog(Extras(bot))
