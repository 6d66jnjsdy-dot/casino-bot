"""National Insurance (ביטוח לאומי) panel.
Command: $ביטוח-לאומי  (owners only)
Add 'bituach_leumi' to MODULES in main.py (after 'owner'), and put bituach_leumi.jpeg next to this file.
"""
import os, re, sys, time, asyncio, discord
from discord.ext import commands, tasks

BL_DIR = os.path.dirname(os.path.abspath(__file__))
BL_IMAGE = os.path.join(BL_DIR, "bituach_leumi.jpeg")
BL_BLUE = 0x1F3A8A
BL_LONG = "\u3164" * 8 + "בחירת אופציה" + "\u3164" * 8   # makes the button look long
DAY = 86400

KINDS = {
    "unemp": {
        "title": "דמי אבטלה", "emoji": "💼", "slug": "unemployment", "sign": "חתום אבטלה",
        "info": ("**דמי אבטלה**\nהכנסה יומית קבועה שמגיעה לחשבון שלך בכל יום (00:00 שעון ישראל) לטווח זמן שהצוות מאשר.\n\n"
                 "• פותחים חדר אישי עם העוזר האישי\n• הצוות חותם ומאשר: סכום יומי, טווח זמן וכמה תצטרך לשלם לנו\n"
                 "• התשלום לצוות מנוכה מהחשבון שלך (ומה שחסר מנוכה מהתשלומים הראשונים)"),
    },
    "capital": {
        "title": "מסלול הוני", "emoji": "📈", "slug": "capital", "sign": "חתום מסלול הוני",
        "info": ("**מסלול הוני**\nבמשך תקופה שהצוות מאשר, בכל משחק שתנצח בו תקבל בונוס נוסף של 25% מהרווח (ברירת מחדל, הצוות יכול לשנות).\n\n"
                 "• פותחים חדר אישי עם העוזר האישי\n• הצוות חותם ומאשר: אחוז, טווח זמן וכמה תצטרך לשלם לנו"),
    },
    "monthly": {
        "title": "קצבה חודשית", "emoji": "🗓️", "slug": "monthly", "sign": "חתום קצבה",
        "info": ("**קצבה חודשית**\nסכום קבוע שמגיע לחשבון שלך פעם בחודש (כל 30 יום) למספר חודשים שהצוות מאשר.\n\n"
                 "• פותחים חדר אישי עם העוזר האישי\n• הצוות חותם ומאשר: סכום חודשי, מספר חודשים וכמה תצטרך לשלם לנו"),
    },
}


# ================= helpers =================
def bl_db():
    d = DB.setdefault("bl", {})
    d.setdefault("tickets", {})     # channel id -> {uid, kind, signed, status}
    d.setdefault("plans", {})       # user id -> {kind: plan}
    return d


def is_staff(member):
    if member.id in OWNER_IDS:
        return True
    try:
        if member.guild_permissions.administrator:
            return True
        rid = DB.get("staff_role") or DB.get("staff_role_id")
        if rid and any(r.id == int(rid) for r in member.roles):
            return True
    except Exception:
        pass
    return False


def charge_fee(uid, fee):
    """Takes the fee from cash, then bank. Returns what is still owed (deducted later from payouts)."""
    u = user_data(uid)
    take = min(u["cash"], fee)
    u["cash"] -= take
    rest = fee - take
    take_b = min(u["bank"], rest)
    u["bank"] -= take_b
    return rest - take_b


def pay_user(uid, kind, gross):
    p = bl_db()["plans"].get(str(uid), {}).get(kind)
    cut = 0
    if p and p.get("fee_left", 0) > 0:
        cut = min(p["fee_left"], gross)
        p["fee_left"] -= cut
    user_data(uid)["cash"] += gross - cut
    save()
    return gross - cut


def info_embed(kind):
    k = KINDS[kind]
    e = discord.Embed(title=f"{k['emoji']} {k['title']}", description=k["info"], color=BL_BLUE)
    e.set_footer(text="המוסד לביטוח לאומי")
    return e


def num(text):
    v = parse_amount(text, 0)
    return v if v is not None and v >= 0 else None


# ================= panel =================
class BLPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label=BL_LONG, style=discord.ButtonStyle.primary, emoji="📋", custom_id="bl:panel")
    async def choose(self, interaction: discord.Interaction, button: discord.ui.Button):
        e = discord.Embed(title="בחירת אופציה", description="בחר את המסלול שמעניין אותך:", color=BL_BLUE)
        await interaction.response.send_message(embed=e, view=OptionsView(), ephemeral=True)


class OptionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        for kind, k in KINDS.items():
            b = discord.ui.Button(label=k["title"], emoji=k["emoji"], style=discord.ButtonStyle.secondary)
            b.callback = self._make(kind)
            self.add_item(b)

    @staticmethod
    def _make(kind):
        async def cb(interaction: discord.Interaction):
            await interaction.response.edit_message(embed=info_embed(kind), view=OpenView(kind))
        return cb


class OpenView(discord.ui.View):
    def __init__(self, kind):
        super().__init__(timeout=300)
        self.kind = kind

    @discord.ui.button(label="פתיחת שיחה עם העוזר האישי שלך", emoji="💬", style=discord.ButtonStyle.success)
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        await open_ticket(interaction, self.kind)

    @discord.ui.button(label="חזרה", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        e = discord.Embed(title="בחירת אופציה", description="בחר את המסלול שמעניין אותך:", color=BL_BLUE)
        await interaction.response.edit_message(embed=e, view=OptionsView())


async def open_ticket(interaction, kind):
    await interaction.response.defer(ephemeral=True)
    g, user, d = interaction.guild, interaction.user, bl_db()
    if not g:
        return await interaction.followup.send("אפשר להשתמש בזה רק בשרת.", ephemeral=True)
    for cid, t in d["tickets"].items():
        if t["uid"] == user.id and t["kind"] == kind and g.get_channel(int(cid)):
            return await interaction.followup.send(f"כבר יש לך חדר פתוח: <#{cid}>", ephemeral=True)
    if kind in d["plans"].get(str(user.id), {}):
        return await interaction.followup.send("המסלול הזה כבר פעיל אצלך.", ephemeral=True)

    see = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    ow = {g.default_role: discord.PermissionOverwrite(view_channel=False), user: see, g.me: see}
    for oid in OWNER_IDS:
        m = g.get_member(oid)
        if m:
            ow[m] = see
    try:
        rid = DB.get("staff_role") or DB.get("staff_role_id")
        role = g.get_role(int(rid)) if rid else None
        if role:
            ow[role] = see
    except Exception:
        pass
    name = re.sub(r"[^a-z0-9]+", "-", user.name.lower()).strip("-") or str(user.id)[-4:]
    try:
        ch = await g.create_text_channel(f"{KINDS[kind]['slug']}-{name}"[:90], category=interaction.channel.category,
                                         overwrites=ow, reason="National Insurance ticket")
    except discord.Forbidden:
        return await interaction.followup.send("אין לי הרשאה ליצור חדרים (Manage Channels).", ephemeral=True)

    d["tickets"][str(ch.id)] = {"uid": user.id, "kind": kind, "signed": None, "status": "open"}
    save()
    e = discord.Embed(title=f"{KINDS[kind]['emoji']} {KINDS[kind]['title']} - העוזר האישי", color=BL_BLUE,
                      description=f"שלום {user.mention}, הבקשה שלך נפתחה.\n\n**יש להמתין למענה של הצוות.**")
    e.set_footer(text="המוסד לביטוח לאומי")
    tags = " ".join(f"<@{o}>" for o in OWNER_IDS)
    await ch.send(content=f"{user.mention} {tags}", embed=e, view=TicketView(kind),
                  allowed_mentions=discord.AllowedMentions(users=True))
    await interaction.followup.send(f"החדר שלך נפתח: {ch.mention}", ephemeral=True)


# ================= ticket (inside the private room) =================
class SignModal(discord.ui.Modal):
    def __init__(self, kind):
        super().__init__(title=KINDS[kind]["sign"])
        self.name = discord.ui.TextInput(label="שם באנגלית", placeholder="John Cohen", min_length=2, max_length=40)
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction):
        t = bl_db()["tickets"].get(str(interaction.channel_id))
        val = self.name.value.strip()
        if not t:
            return await interaction.response.send_message("החדר לא נמצא במערכת.", ephemeral=True)
        if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,39}", val):
            return await interaction.response.send_message("יש לכתוב את השם באנגלית בלבד.", ephemeral=True)
        t["signed"] = val
        save()
        e = discord.Embed(title="✍️ נחתם", color=GREEN, description=f"חתימה: **{val}**\nממתין לאישור הצוות.")
        await interaction.response.send_message(embed=e)


class ApproveModal(discord.ui.Modal):
    def __init__(self, kind):
        super().__init__(title=f"אישור - {KINDS[kind]['title']}")
        self.kind = kind
        if kind == "unemp":
            fields = [("סכום יומי", "50000"), ("טווח זמן (בימים)", "7"), ("כמה הוא צריך לשלם לנו", "0")]
        elif kind == "capital":
            fields = [("אחוז בונוס", "25"), ("טווח זמן בימים (0 = ללא הגבלה)", "7"), ("כמה הוא צריך לשלם לנו", "0")]
        else:
            fields = [("סכום חודשי", "500000"), ("מספר חודשים", "3"), ("כמה הוא צריך לשלם לנו", "0")]
        for label, ph in fields:
            self.add_item(discord.ui.TextInput(label=label, placeholder=ph, max_length=20))

    async def on_submit(self, interaction: discord.Interaction):
        d = bl_db()
        t = d["tickets"].get(str(interaction.channel_id))
        if not t or t["status"] != "open":
            return await interaction.response.send_message("הבקשה כבר טופלה.", ephemeral=True)
        a, b, fee = (num(i.value) for i in self.children)
        if a is None or b is None or fee is None or a <= 0 or (b <= 0 and self.kind != "capital"):
            return await interaction.response.send_message("ערכים לא תקינים, נסה שוב.", ephemeral=True)
        uid, now = t["uid"], time.time()
        if self.kind == "unemp":
            plan = {"amount": a, "end": now + b * DAY, "last_day": None}
            terms = f"סכום יומי: **{fmt(a)}** {cur()}\nטווח זמן: **{b}** ימים"
        elif self.kind == "capital":
            plan = {"percent": min(a, 500), "end": now + b * DAY if b else 0}
            terms = f"בונוס: **{plan['percent']}%** על כל רווח\nטווח זמן: **{b if b else 'ללא הגבלה'}**" + (" ימים" if b else "")
        else:
            plan = {"amount": a, "months_left": b, "next": now + 30 * DAY}
            terms = f"סכום חודשי: **{fmt(a)}** {cur()}\nחודשים: **{b}**"
        plan["fee_left"] = charge_fee(uid, fee)
        d["plans"].setdefault(str(uid), {})[self.kind] = plan
        t["status"] = "approved"
        save()
        e = discord.Embed(title="✅ הבקשה אושרה", color=GREEN,
                          description=f"{terms}\nתשלום לצוות: **{fmt(fee)}** {cur()}\nחתימה: **{t.get('signed')}**")
        await interaction.response.send_message(content=f"<@{uid}>", embed=e,
                                                allowed_mentions=discord.AllowedMentions(users=True))
        m = interaction.guild.get_member(uid)
        if m:
            try:
                log_money(m, f"National Insurance | {KINDS[self.kind]['title']}", terms.replace("**", ""))
            except Exception:
                pass


class TicketView(discord.ui.View):
    def __init__(self, kind=None):
        super().__init__(timeout=None)
        if kind:
            self.sign.label = KINDS[kind]["sign"]

    async def _staff(self, interaction):
        t = bl_db()["tickets"].get(str(interaction.channel_id))
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message("הכפתור הזה לצוות בלבד.", ephemeral=True)
            return None
        if not t:
            await interaction.response.send_message("החדר לא נמצא במערכת.", ephemeral=True)
            return None
        return t

    @discord.ui.button(label="חתום", emoji="✍️", style=discord.ButtonStyle.primary, custom_id="bl:sign")
    async def sign(self, interaction: discord.Interaction, button: discord.ui.Button):
        t = await self._staff(interaction)
        if t:
            if t["status"] != "open":
                return await interaction.response.send_message("הבקשה כבר טופלה.", ephemeral=True)
            await interaction.response.send_modal(SignModal(t["kind"]))

    @discord.ui.button(label="אשר", emoji="✅", style=discord.ButtonStyle.success, custom_id="bl:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        t = await self._staff(interaction)
        if t:
            if t["status"] != "open":
                return await interaction.response.send_message("הבקשה כבר טופלה.", ephemeral=True)
            if not t.get("signed"):
                return await interaction.response.send_message("קודם צריך ללחוץ על כפתור החתימה.", ephemeral=True)
            await interaction.response.send_modal(ApproveModal(t["kind"]))

    @discord.ui.button(label="דחה", emoji="⛔", style=discord.ButtonStyle.danger, custom_id="bl:reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        t = await self._staff(interaction)
        if t:
            if t["status"] != "open":
                return await interaction.response.send_message("הבקשה כבר טופלה.", ephemeral=True)
            t["status"] = "rejected"
            save()
            await interaction.response.send_message(embed=discord.Embed(title="⛔ הבקשה נדחתה", color=RED))

    @discord.ui.button(label="מחיקת חדר", emoji="🗑️", style=discord.ButtonStyle.secondary, custom_id="bl:delete")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        t = await self._staff(interaction)
        if t:
            await interaction.response.send_message("החדר יימחק בעוד 3 שניות...")
            bl_db()["tickets"].pop(str(interaction.channel_id), None)
            save()
            await asyncio.sleep(3)
            try:
                await interaction.channel.delete(reason="National Insurance ticket closed")
            except Exception as ex:
                print("BL delete failed:", repr(ex))


# ================= command (owners only) =================
@bot.command(name="ביטוח-לאומי", aliases=["ביטוחלאומי", "ביטוח_לאומי"])
async def bituach_leumi(ctx):
    if ctx.author.id not in OWNER_IDS:
        return
    e = discord.Embed(title="המוסד לביטוח לאומי", color=BL_BLUE,
                      description="ברוכים הבאים למוסד לביטוח לאומי.\nלחצו על הכפתור כדי לבחור אופציה: "
                                  "דמי אבטלה, מסלול הוני או קצבה חודשית.")
    e.set_footer(text="Amram Casino | המוסד לביטוח לאומי")
    file = None
    if os.path.exists(BL_IMAGE):
        file = discord.File(BL_IMAGE, filename="bituach_leumi.jpeg")
        e.set_image(url="attachment://bituach_leumi.jpeg")
    await ctx.send(embed=e, file=file, view=BLPanel()) if file else await ctx.send(embed=e, view=BLPanel())


# ================= payouts + 25% bonus =================
@tasks.loop(minutes=5)
async def bl_loop():
    await loaded.wait()
    now, today = time.time(), today_key()
    plans = bl_db()["plans"]
    for uid, kinds in list(plans.items()):
        try:
            p = kinds.get("unemp")
            if p:
                if now >= p["end"]:
                    kinds.pop("unemp")
                elif p["last_day"] != today:
                    p["last_day"] = today
                    pay_user(uid, "unemp", p["amount"])
            p = kinds.get("monthly")
            if p and now >= p["next"]:
                pay_user(uid, "monthly", p["amount"])
                p["months_left"] -= 1
                p["next"] += 30 * DAY
                if p["months_left"] <= 0:
                    kinds.pop("monthly")
            p = kinds.get("capital")
            if p and p["end"] and now >= p["end"]:
                kinds.pop("capital")
            if not kinds:
                plans.pop(uid, None)
        except Exception as ex:
            print("BL loop error:", repr(ex))
    save()


def _bonus(user, net):
    p = bl_db()["plans"].get(str(user.id), {}).get("capital")
    if not p or net <= 0:
        return
    if p["end"] and time.time() >= p["end"]:
        return
    extra = int(net * p["percent"] / 100)
    if extra > 0:
        pay_user(user.id, "capital", extra)


def _install_bonus_hook():
    """Wraps log_game (called after every finished game) so capital-track users get their bonus."""
    orig = globals().get("log_game")
    if not orig or getattr(orig, "_bl", False):
        return

    def wrapped(user, game, bet, net, detail=None):
        orig(user, game, bet, net, detail)
        try:
            _bonus(user, net)
        except Exception as ex:
            print("BL bonus error:", repr(ex))
    wrapped._bl = True
    for m in list(sys.modules.values()):
        d = getattr(m, "__dict__", None)
        if d is not None and d.get("log_game") is orig:
            d["log_game"] = wrapped


@bot.listen("on_ready")
async def bl_ready():
    if getattr(bot, "_bl_ready", False):
        return
    bot._bl_ready = True
    bot.add_view(BLPanel())
    bot.add_view(TicketView())
    _install_bonus_hook()
    if not bl_loop.is_running():
        bl_loop.start()
