"""National Insurance (ביטוח לאומי) panel.
Command: $ביטוח-לאומי  (owners only)
Add 'bituach_leumi' to MODULES in main.py (after 'owner'), and put bituach_leumi.jpeg next to this file.
"""
import os, re, sys, io, time, asyncio, base64, discord
from discord.ext import commands, tasks

BL_DIR = os.path.dirname(os.path.abspath(__file__))
BL_IMAGE = os.path.join(BL_DIR, "bituach_leumi.jpeg")
BL_LOGO_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/4RNSRXhpZgAATU0AKgAAAAgABQEaAAUAAAABAAAASgEbAAUAAAABAAAAUgEoAAMAAAABAAIA"
    "AAITAAMAAAABAAEAAIdpAAQAAAABAAAAWgAAALQAAABIAAAAAQAAAEgAAAABAAeQAAAHAAAABDAyMjGRAQAHAAAABAECAwCgAAAH"
    "AAAABDAxMDCgAQADAAAAAQABAACgAgAEAAAAAQAAARSgAwAEAAAAAQAAALekBgADAAAAAQAAAAAAAAAAAAYBAwADAAAAAQAGAAAB"
    "GgAFAAAAAQAAAQIBGwAFAAAAAQAAAQoBKAADAAAAAQACAAACAQAEAAAAAQAAARICAgAEAAAAAQAAEjYAAAAAAAAASAAAAAEAAABI"
    "AAAAAf/Y/9sAhAABAQEBAQECAQECAwICAgMEAwMDAwQFBAQEBAQFBgUFBQUFBQYGBgYGBgYGBwcHBwcHCAgICAgJCQkJCQkJCQkJ"
    "AQEBAQICAgQCAgQJBgUGCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQn/3QAEAAr/wAAR"
    "CABqAKADASIAAhEBAxEB/8QBogAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoLEAACAQMDAgQDBQUEBAAAAX0BAgMABBEFEiEx"
    "QQYTUWEHInEUMoGRoQgjQrHBFVLR8CQzYnKCCQoWFxgZGiUmJygpKjQ1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZmdoaWpzdHV2"
    "d3h5eoOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4eLj5OXm5+jp6vHy8/T19vf4"
    "+foBAAMBAQEBAQEBAQEAAAAAAAABAgMEBQYHCAkKCxEAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHB"
    "CSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOU"
    "lZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD+"
    "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"
    "oOiV938uznKGDB7QiuluZP8A2q1+r6yPHxFrtmZYpTShTUuWiiP4qiC8IxXr6s3lmdDWIwps7ujOpTjhqLccS6vfdY+z9mfkpeZI"
    "+zns0nOSytQrcYQl+Dx5LrNp+1Yv1d10XmVtkiv6r9/hMV3xDzdmHZ9PIlXm5SlHHg1OivqpXST3U36Q/wAl4HWMUkklsl0SXgl6"
    "HY8zLltktuXRWsVgABmsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACBdo/H8NPi6KOWebNeHjGhPwnL3+iKy569ZjtJwq1eMdoy"
    "6Rq1BJey/S33+Z4+0r87Zv7xfVR6dJwoYGHXqlsVZfdY68Gt9a65xT3vs9Wtnsj1MeOtMcTHcua1pmfZFLqpQlKE4yjZCW0oveM4"
    "ST/syZ4upV6vVXiZtihn1LlwsuXs279e4ufv26P/ANmOGTXrEVXfKFeqxXLTc9o15q/2rNukbPRkRycedU5V2RlCyt8s4SW0oSRv"
    "9/E8WhTr+jJn4VuPbOm6EoXVS2lF+Ka6pp/3TLb7Mu0bvOTCzp/hPZovk/xnkoTb/S9/mQ7ScmGrRrwcp7ZsYuOFl+Llst1Rd6rp"
    "0l5ERy6JVTnXPpZVNwls/CUXs9n8UVtSMseNu4WifGdw+t0DScE2ynp2FKcnKUsatyk3u2+RdWzdnjzGp06oAAQAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAABGuMOMsfTO57+Nsu/clHkSe3Ltvvu/eTWs2nUImdKO7Sfztm/vV9VGy4i/MGk/SbfqyPLxFm6ZmZV2U7"
    "8yDulzcix62o9Ntt+bqejUNX0y7AxMHvcxLEslYrO4r3nzJrbbm6eJ62p1SNTx/pzcbl6+xbTab86yVsFJ0UqyrfwjNy25tvN7Es"
    "7btEoeKs3k2yYWQr51054Se20l5+4iXA/Eem6XdbdGzLtdtar2dMI7bPfffmNvxn2gadqWK8Z/Kq05xnzqqEn8177bNmV63nPFoi"
    "dLRMeGkL7O/zrg/vv+rNdxN+W5v0q77Rm74fy9MxMqnJV+ZN0T51B49aUujW2/N08SPavkq7IyLY78t11lkU/FKUnJJ+/qdUbm+/"
    "ZT0fSfAn5swPotf1Eb0rLgXtDwu6wMDa7v8Akrx9+T5nPtt47+BZp4+Wlq2ncOmsxMcAAM1gAAAAAAAAAAAAAAAAAAAAAAAADcAA"
    "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"
    "AAAAAAAAAAAAAAAAAAAAAAB//9k="
)
BL_BLUE = 0x1F3A8A
BL_LONG = "\u3164" * 8 + "בחירת אופציה" + "\u3164" * 8   # makes the button look long
DAY = 86400

KINDS = {
    "unemp": {
        "title": "דמי אבטלה", "emoji": "💼", "slug": "unemployment", "sign": "חתום אבטלה",
        "info": ("**דמי אבטלה**\nהכנסה יומית קבועה שמגיעה לחשבון שלך בכל יום (00:00 שעון ישראל) לטווח זמן שהצוות מאשר.\n\n"
                 "• פותחים חדר אישי עם העוזר האישי\n• הצוות חותם ומאשר: סכום יומי, טווח זמן וכמה תצטרך לשלם לנו\n"
                 "• התשלום לצוות בסוף התקופה: תקבל תזכורת יום לפני, ואחרי שהתקופה נגמרת יש לך 24 שעות לשלם. אם לא תשלם תיקנס באותו סכום ותהיה במינוס"),
    },
    "capital": {
        "title": "מסלול הוני", "emoji": "📈", "slug": "capital", "sign": "חתום מסלול הוני",
        "info": ("**מסלול הוני**\nבמשך תקופה שהצוות מאשר, בכל משחק שתנצח בו תקבל בונוס נוסף של 25% מהרווח (ברירת מחדל, הצוות יכול לשנות).\n\n"
                 "• פותחים חדר אישי עם העוזר האישי\n• הצוות חותם ומאשר: אחוז, טווח זמן וכמה תצטרך לשלם לנו\n• התשלום לצוות בסוף התקופה: תקבל תזכורת יום לפני, ואחרי שהתקופה נגמרת יש לך 24 שעות לשלם. אם לא תשלם תיקנס באותו סכום ותהיה במינוס"),
    },
    "monthly": {
        "title": "קצבה חודשית", "emoji": "🗓️", "slug": "monthly", "sign": "חתום קצבה",
        "info": ("**קצבה חודשית**\nסכום קבוע שמגיע לחשבון שלך פעם בחודש (כל 30 יום) למספר חודשים שהצוות מאשר.\n\n"
                 "• פותחים חדר אישי עם העוזר האישי\n• הצוות חותם ומאשר: סכום חודשי, מספר חודשים וכמה תצטרך לשלם לנו\n• התשלום לצוות בסוף התקופה: תקבל תזכורת יום לפני, ואחרי שהתקופה נגמרת יש לך 24 שעות לשלם. אם לא תשלם תיקנס באותו סכום ותהיה במינוס"),
    },
}


# ================= helpers =================
def bl_db():
    d = DB.setdefault("bl", {})
    d.setdefault("tickets", {})     # channel id -> {uid, kind, signed, status}
    d.setdefault("plans", {})       # user id -> {kind: plan}
    return d


def is_staff(member):
    """Owners and server administrators only."""
    if member.id in OWNER_IDS:
        return True
    try:
        return bool(member.guild_permissions.administrator)
    except Exception:
        return False


def total_money(uid):
    u = user_data(uid)
    return max(u["cash"], 0) + max(u["bank"], 0)


def take_money(uid, amount):
    """Takes from cash, then bank. Returns the part that could not be taken."""
    u = user_data(uid)
    take = min(max(u["cash"], 0), amount)
    u["cash"] -= take
    rest = amount - take
    take_b = min(max(u["bank"], 0), rest)
    u["bank"] -= take_b
    return rest - take_b


def penalize(uid, fee):
    """Did not pay in time: the fee + a fine of the same amount. Cash may go negative."""
    short = take_money(uid, fee * 2)
    user_data(uid)["cash"] -= short
    save()


def pay_user(uid, kind, gross):
    user_data(uid)["cash"] += gross
    save()
    return gross


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
            fields = [("סכום יומי", "50000"), ("טווח זמן (בימים)", "7"), ("תשלום לצוות בסוף התקופה", "0")]
        elif kind == "capital":
            fields = [("אחוז בונוס", "25"), ("טווח זמן בימים (0 = ללא הגבלה)", "7"), ("תשלום לצוות בסוף התקופה", "0")]
        else:
            fields = [("סכום חודשי", "500000"), ("מספר חודשים", "3"), ("תשלום לצוות בסוף התקופה", "0")]
        for label, ph in fields:
            self.add_item(discord.ui.TextInput(label=label, placeholder=ph, max_length=20))

    async def on_submit(self, interaction: discord.Interaction):
        d = bl_db()
        t = d["tickets"].get(str(interaction.channel_id))
        if not t or t["status"] != "open":
            return await interaction.response.send_message("הבקשה כבר טופלה.", ephemeral=True)
        a, b, fee = (num(i.value) for i in self.children)
        if a is None or b is None or fee is None or a <= 0 or (b <= 0 and (self.kind != "capital" or fee > 0)):
            return await interaction.response.send_message(
                "ערכים לא תקינים. חייב טווח זמן (ובמסלול הוני אי אפשר לגבות תשלום בלי טווח זמן).", ephemeral=True)
        uid, now = t["uid"], time.time()
        if self.kind == "unemp":
            end = now + b * DAY
            plan = {"amount": a, "last_day": None}
            terms = f"סכום יומי: **{fmt(a)}** {cur()}\nטווח זמן: **{b}** ימים"
        elif self.kind == "capital":
            end = now + b * DAY if b else 0
            plan = {"percent": min(a, 500)}
            terms = f"בונוס: **{plan['percent']}%** על כל רווח\nטווח זמן: **{b if b else 'ללא הגבלה'}**" + (" ימים" if b else "")
        else:
            end = now + b * 30 * DAY
            plan = {"amount": a, "months_left": b, "next": now + 30 * DAY}
            terms = f"סכום חודשי: **{fmt(a)}** {cur()}\nחודשים: **{b}**"
        plan.update({"end": end, "fee": fee, "state": "active", "reminded": False, "deadline": 0})
        d["plans"].setdefault(str(uid), {})[self.kind] = plan
        t["status"] = "approved"
        save()
        pay_line = ""
        if fee > 0:
            pay_line = (f"\nתשלום לצוות: **{fmt(fee)}** {cur()}\nהמסלול מסתיים <t:{int(end)}:F>. תקבל תזכורת יום לפני, "
                        f"ויהיו לך 24 שעות לשלם אחרי הסיום. אם לא תשלם תיקנס באותו סכום ותהיה במינוס.")
        e = discord.Embed(title="✅ הבקשה אושרה", color=GREEN,
                          description=f"{terms}{pay_line}\nחתימה: **{t.get('signed')}**")
        kw = {"view": PayView(self.kind)} if fee > 0 else {}
        await interaction.response.send_message(content=f"<@{uid}>", embed=e,
                                                allowed_mentions=discord.AllowedMentions(users=True), **kw)
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
        if interaction.user.id not in OWNER_IDS:
            return await interaction.response.send_message("מחיקת החדר לבעלים בלבד.", ephemeral=True)
        t = bl_db()["tickets"].get(str(interaction.channel_id))
        if not t:
            return await interaction.response.send_message("החדר לא נמצא במערכת.", ephemeral=True)
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
    # the logo is embedded in this file (base64), so no separate image file is needed
    data = open(BL_IMAGE, "rb").read() if os.path.exists(BL_IMAGE) else base64.b64decode("".join(BL_LOGO_B64))
    file = discord.File(io.BytesIO(data), filename="bituach_leumi.jpeg")
    e.set_image(url="attachment://bituach_leumi.jpeg")
    await ctx.send(embed=e, file=file, view=BLPanel())


# ================= payouts + 25% bonus =================
class PayView(discord.ui.View):
    """Persistent 'pay now' button (used in the room and in reminders)."""
    def __init__(self, kind):
        super().__init__(timeout=None)
        b = discord.ui.Button(label="שלם עכשיו", emoji="💳", style=discord.ButtonStyle.success, custom_id=f"bl:pay:{kind}")
        b.callback = self._make(kind)
        self.add_item(b)

    @staticmethod
    def _make(kind):
        async def cb(interaction: discord.Interaction):
            d, uid = bl_db(), interaction.user.id
            kinds = d["plans"].get(str(uid), {})
            p = kinds.get(kind)
            if not p or p.get("fee", 0) <= 0:
                return await interaction.response.send_message("אין לך חוב פתוח במסלול הזה.", ephemeral=True)
            fee = p["fee"]
            if total_money(uid) < fee:
                return await interaction.response.send_message(
                    f"אין לך מספיק כסף (מזומן + בנק). נדרש: {fmt(fee)} {cur()}", ephemeral=True)
            take_money(uid, fee)
            p["fee"] = 0
            if p.get("state") == "due":
                kinds.pop(kind, None)
                if not kinds:
                    d["plans"].pop(str(uid), None)
            save()
            await interaction.response.send_message(embed=discord.Embed(
                title="✅ התשלום התקבל", color=GREEN, description=f"שולמו {fmt(fee)} {cur()}. תודה!"))
            try:
                log_money(interaction.user, f"National Insurance | {KINDS[kind]['title']}", f"Paid {fmt(fee)}")
            except Exception:
                pass
        return cb


async def bl_notify(uid, kind, embed):
    """Sends to the user's private room (if it still exists) and to DMs."""
    for cid, t in list(bl_db()["tickets"].items()):
        if t["uid"] == uid and t["kind"] == kind:
            ch = bot.get_channel(int(cid))
            if ch:
                try:
                    await ch.send(content=f"<@{uid}>", embed=embed, view=PayView(kind),
                                  allowed_mentions=discord.AllowedMentions(users=True))
                except Exception as ex:
                    print("BL notify (room) failed:", repr(ex))
    try:
        user = bot.get_user(uid) or await bot.fetch_user(uid)
        await user.send(embed=embed, view=PayView(kind))
    except Exception:
        pass


async def _bl_tick(uid, kinds, kind, p, now, today):
    state, fee, end = p.get("state", "active"), p.get("fee", 0), p.get("end", 0)
    title = KINDS[kind]["title"]
    if state == "active":
        if kind == "unemp" and now < end and p["last_day"] != today:
            p["last_day"] = today
            pay_user(uid, kind, p["amount"])
        elif kind == "monthly" and p["months_left"] > 0 and now >= p["next"]:
            pay_user(uid, kind, p["amount"])
            p["months_left"] -= 1
            p["next"] += 30 * DAY
        if not end:
            return
        if fee > 0 and not p.get("reminded") and now >= end - DAY:
            p["reminded"] = True
            await bl_notify(uid, kind, discord.Embed(
                title=f"⏰ תזכורת - {title}", color=YELLOW,
                description=(f"המסלול מסתיים <t:{int(end)}:R>.\nאחרי הסיום יש לך **24 שעות** לשלם **{fmt(fee)}** {cur()}.\n"
                             f"אם לא תשלם, תיקנס באותו סכום ותהיה במינוס.")))
        if now >= end:
            if fee > 0:
                p["state"] = "due"
                p["deadline"] = max(end, now) + DAY
                await bl_notify(uid, kind, discord.Embed(
                    title=f"💳 הגיע זמן התשלום - {title}", color=RED,
                    description=(f"המסלול הסתיים. יש לך עד <t:{int(p['deadline'])}:F> לשלם **{fmt(fee)}** {cur()}.\n"
                                 f"אם לא תשלם, תיקנס באותו סכום ({fmt(fee)}) ותהיה במינוס.")))
            else:
                kinds.pop(kind, None)
    elif state == "due" and now >= p["deadline"]:
        if fee > 0:
            penalize(uid, fee)
            bal = user_data(uid)["cash"]
            await bl_notify(uid, kind, discord.Embed(
                title=f"⛔ קנס - {title}", color=RED,
                description=(f"לא שילמת בזמן. נגבו **{fmt(fee * 2)}** {cur()} (התשלום + קנס באותו סכום).\n"
                             f"היתרה במזומן: **{fmt(bal)}** {cur()}")))
        kinds.pop(kind, None)


@tasks.loop(minutes=5)
async def bl_loop():
    await loaded.wait()
    now, today = time.time(), today_key()
    plans = bl_db()["plans"]
    for uid, kinds in list(plans.items()):
        for kind, p in list(kinds.items()):
            try:
                await _bl_tick(int(uid), kinds, kind, p, now, today)
            except Exception as ex:
                print("BL loop error:", repr(ex))
        if not kinds:
            plans.pop(uid, None)
    save()


def _bonus(user, net):
    p = bl_db()["plans"].get(str(user.id), {}).get("capital")
    if not p or net <= 0:
        return
    if p.get("state", "active") != "active" or (p["end"] and time.time() >= p["end"]):
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
    for k in KINDS:
        bot.add_view(PayView(k))
    _install_bonus_hook()
    if not bl_loop.is_running():
        bl_loop.start()
if not bl.loop.start() ("on_ready") wrapped._bl d["log_game"] = wrapped is orig if bl.loop
if not bl.loop.is_runnin():add_view(BlPanel()) = True 
                                                  return - True Log mame = wrapped if orig if bal.loop
 for k in KINDS:
bot.add_view(TicketView)(() = def as "on ready" is not 
if not orig or KINDS: 
and bonus_hook() - View: + add or orig or KINDS: if share link 
create or add if not 