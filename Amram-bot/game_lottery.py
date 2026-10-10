import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= LOTTERY ($lottery) =================
LOTTO_CHANNEL_ID = 1556503844567916665       # the only room where the lottery lives
LOTTO_MIN_PRICE = 5_000_000                  # the cheapest ticket
LOTTO_MAX_TICKETS = 2                        # tickets per player in one draw
LOTTO_PICK, LOTTO_RANGE, LOTTO_STRONG = 5, 37, 7     # 5 numbers out of 37 + one strong number out of 7
LOTTO_DRAWN = 6                              # the draw takes 6 numbers (5=6 system)
LOTTO_MULT = {5: 25, 4: 7.5, 3: 5, 2: 2.5, 1: 1.5}   # hits -> prize as a multiple of the ticket price
LOTTO_STRONG_BONUS = 0.5                     # a correct strong number adds this part of the prize
LOTTO_PRESETS = (5_000_000, 7_500_000, 10_000_000, 25_000_000, 50_000_000, 100_000_000, 250_000_000, 500_000_000, 1_000_000_000)
LOTTO_RED, LOTTO_BLUE_C = 0xE3242B, 0x1D4E9E
LOTTO_LOCK = asyncio.Lock()

LOTTO_RULES = (
    "פעם בשבוע יש הגרלה, ביום שבת ב-00:00 (זה הלילה שבין שישי לשבת). התוצאות מתפרסמות כאן בחדר.\n\n"
    "**איך משחקים**\n"
    "לוחצים על \"מלא טופס\". בוחרים 5 מספרים מתוך 37 ומספר חזק אחד מ-1 עד 7. "
    "אחרי זה קובעים כמה כסף לשים על הטופס, מינימום 5 מיליון, והסכום באחריותכם. אפשר לקנות עד 2 טפסים.\n\n"
    "**איך זוכים**\n"
    "בהגרלה יוצאים 6 מספרים ומספר חזק אחד. סופרים כמה מהמספרים שלכם יצאו, והפרס הוא הסכום שלכם כפול:\n"
    "5 פגיעות פי 25\n"
    "4 פגיעות פי 7.5\n"
    "3 פגיעות פי 5\n"
    "2 פגיעות פי 2.5\n"
    "פגיעה אחת פי 1.5\n"
    "אם גם המספר החזק נכון, מקבלים עוד חצי מהפרס.\n\n"
    "**הקופה**\n"
    "כל הכסף שנכנס מהטפסים נצבר בקופה. מי שפגע הכי הרבה מספרים לוקח את כולה, גם אם זה רק 1 או 2. "
    "אם כמה טפסים פגעו אותו דבר, קודם מי שפגע גם בחזק, ואם עדיין שווה מחלקים ביניהם. "
    "אם אף אחד לא פגע בשום מספר, הקופה עוברת להגרלה הבאה.\n\n"
    "דוגמה: שמתם 10 מיליון ופגעתם ב-3 מספרים, אתם מקבלים 50 מיליון. אם זה היה הכי הרבה פגיעות בהגרלה, אתם לוקחים גם את הקופה."
)

def heb(s):
    """Hebrew for PIL: the bot's own helper reverses it only when this Pillow has no RTL support."""
    return he(s)

def next_saturday():
    """The coming Saturday at 00:00 (Israel time) as a timestamp. That is the night between Friday and Saturday."""
    now = datetime.datetime.now(LOCAL_TZ)
    t = (now + datetime.timedelta(days=(5 - now.weekday()) % 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    if t <= now:
        t += datetime.timedelta(days=7)
    return int(t.timestamp())

def lotto():
    return DB.get("lotto")

def lotto_open_now(r=None):
    r = r or lotto()
    return bool(r) and not r.get("done") and time.time() < r["end"]

def lotto_pot(r):
    return r.get("carry", 0) + sum(t["price"] for t in r["tickets"])

def lotto_mine(r, uid):
    return [t for t in r["tickets"] if t["uid"] == str(uid)]

def lotto_prize(price, hits, strong_hit):
    m = LOTTO_MULT.get(hits, 0)
    if not m:
        return 0
    return int(price * m * ((1 + LOTTO_STRONG_BONUS) if strong_hit else 1))

def lotto_grid(nums):
    """The form as text: the numbers 1-37 in rows of seven, a chosen number looks like [07]."""
    cells = [f"[{n:02d}]" if n in nums else f" {n:02d} " for n in range(1, LOTTO_RANGE + 1)]
    return "```\n" + "\n".join("".join(cells[i:i + 7]) for i in range(0, LOTTO_RANGE, 7)) + "\n```"

# ---------- pictures ----------
@lru_cache(maxsize=64)
def lotto_ticket_art(nums, strong, idx, price, draw_text):
    """A filled-in betting slip in the style of the real one: red and blue, pink table, chosen ovals are filled."""
    S, W, H = 2, 620, 800
    RED, BLUE, PINK = (227, 36, 43), (29, 78, 158), (252, 221, 221)
    im = Image.new("RGB", (W * S, H * S), (255, 255, 255))
    d = ImageDraw.Draw(im)

    def X(v):
        return int(v * S)

    def box(x0, y0, x1, y1, fill=None, outline=None, r=10, w=2):
        d.rounded_rectangle([X(x0), X(y0), X(x1), X(y1)], radius=X(r), fill=fill, outline=outline, width=X(w) if outline else 0)

    def text(x, y, t, size, fill, anchor="mm"):
        d.text((X(x), X(y)), t, font=get_font(int(size * S)), fill=fill, anchor=anchor)

    box(30, 24, 310, 92, fill=BLUE)
    box(310, 24, 590, 92, fill=RED)
    text(170, 58, heb("שיטתי"), 40, (255, 255, 255))
    text(450, 58, heb("לוטו"), 40, (255, 255, 255))
    box(30, 104, 590, 214, fill=RED)
    d.ellipse([X(130), X(108), X(490), X(210)], fill=BLUE)
    text(310, 160, heb("חזק"), 72, (255, 255, 255))

    box(30, 236, 590, 716, fill=PINK, r=8)
    text(255, 262, heb("בחרו 5 מספרים"), 17, RED)
    text(530, 262, heb("חזק"), 17, RED)
    x0, y0, pitch_x, pitch_y = 74, 296, 60, 62
    chosen = set(nums)
    for n in range(1, LOTTO_RANGE + 1):
        r_, c_ = divmod(n - 1, 7)
        cx, cy = x0 + c_ * pitch_x, y0 + r_ * pitch_y
        text(cx, cy, str(n), 19, RED)
        box(cx - 22, cy + 14, cx + 22, cy + 38, fill=BLUE if n in chosen else (255, 255, 255), outline=BLUE if n in chosen else RED, r=12)
    d.line([X(494), X(276), X(494), X(700)], fill=RED, width=X(2))
    for n in range(1, LOTTO_STRONG + 1):
        cx, cy = 542, y0 + (n - 1) * pitch_y
        text(cx, cy, str(n), 19, RED)
        box(cx - 22, cy + 14, cx + 22, cy + 38, fill=BLUE if n == strong else (255, 255, 255), outline=BLUE if n == strong else RED, r=12)

    box(30, 732, 590, 782, fill=(255, 255, 255), outline=BLUE, r=10)
    text(60, 757, f"TICKET {idx}/{LOTTO_MAX_TICKETS}", 17, BLUE, "lm")
    text(310, 757, f"{price:,}", 20, RED)
    text(560, 757, f"DRAW {draw_text}", 17, BLUE, "rm")
    out = io.BytesIO()
    im.resize((W, H), Image.LANCZOS).save(out, "PNG")
    return out.getvalue()

@lru_cache(maxsize=16)
def lotto_balls_art(drawn=None, strong=None):
    """The banner: six white balls and a gold strong ball. Without numbers (drawn=None) the balls show a question mark."""
    S, W, H = 2, 900, 230
    im = Image.new("RGB", (W * S, H * S))
    d = ImageDraw.Draw(im)
    for x in range(W * S):
        k = x / (W * S - 1)
        d.line([(x, 0), (x, H * S)], fill=tuple(int(a + (b - a) * k) for a, b in zip((196, 28, 38), (22, 58, 128))))
    f = get_font

    def X(v):
        return int(v * S)

    d.text((X(450), X(52)), heb("לוטו שיטתי חזק"), font=f(int(46 * S)), fill=(255, 255, 255), anchor="mm")
    vals = list(drawn) if drawn else [None] * LOTTO_DRAWN
    xs = [105 + i * 112 for i in range(LOTTO_DRAWN)] + [105 + LOTTO_DRAWN * 112 + 10]
    for i, cx in enumerate(xs):
        gold = i == LOTTO_DRAWN
        v = (strong if gold else vals[i]) if drawn else None
        cy, r = 150, 44
        d.ellipse([X(cx - r + 4), X(cy - r + 8), X(cx + r + 4), X(cy + r + 8)], fill=(0, 0, 0))
        d.ellipse([X(cx - r), X(cy - r), X(cx + r), X(cy + r)], fill=(240, 196, 25) if gold else (255, 255, 255),
                  outline=(150, 110, 10) if gold else (210, 210, 220), width=X(3))
        d.ellipse([X(cx - r * 0.55), X(cy - r * 0.62), X(cx - r * 0.1), X(cy - r * 0.25)], fill=(255, 236, 150) if gold else (245, 245, 252))
        d.text((X(cx), X(cy + 2)), "?" if v is None else str(v), font=f(int(40 * S)), fill=(120, 80, 0) if gold else (29, 78, 158), anchor="mm")
    out = io.BytesIO()
    im.resize((W, H), Image.LANCZOS).save(out, "PNG")
    return out.getvalue()

def lotto_file(png, name):
    return discord.File(io.BytesIO(png), name)

# ---------- the public panel ----------
def lotto_embed(r, art=True):
    end, pot = r["end"], lotto_pot(r)
    e = discord.Embed(color=LOTTO_RED, title="לוטו שבועי | שיטתי חזק", description=(
        "בוחרים 5 מספרים מתוך 37 ומספר חזק אחד מ-1 עד 7, וקובעים כמה לשים על הטופס. "
        "ההגרלה ביום שבת ב-00:00, ומי שפגע הכי הרבה לוקח את כל הקופה."))
    e.add_field(name="הקופה", value=f"**{fmt(pot)}** {cur()}")
    e.add_field(name="טפסים שנמכרו", value=str(len(r["tickets"])))
    e.add_field(name="ההגרלה", value=f"<t:{end}:F>\n<t:{end}:R>")
    e.add_field(name="פרסים לפי פגיעות (פי הסכום שבטופס)", value=(
        "\n".join(f"{h} פגיעות: פי {m:g}" if h > 1 else f"פגיעה אחת: פי {m:g}" for h, m in LOTTO_MULT.items())
        + f"\nמספר חזק נכון: עוד {int(LOTTO_STRONG_BONUS * 100)}% על הפרס"), inline=False)
    e.set_footer(text=f"עד {LOTTO_MAX_TICKETS} טפסים לשחקן  |  מינימום {fmt(LOTTO_MIN_PRICE)} לטופס")
    if art:
        e.set_image(url="attachment://lotto_banner.png")
    return e

async def lotto_refresh_panel():
    r = lotto()
    if not r or not r.get("message"):
        return
    try:
        ch = bot.get_channel(r["channel"]) or await bot.fetch_channel(r["channel"])
        await ch.get_partial_message(r["message"]).edit(embed=lotto_embed(r))
    except Exception as ex:
        print("Lotto panel refresh failed:", repr(ex))

async def lotto_open(channel, carry=0):
    """Open a new round that ends on the coming Saturday at 00:00 and post its panel."""
    r = {"id": int(time.time()), "end": next_saturday(), "tickets": [], "carry": int(carry),
         "channel": channel.id, "message": 0, "done": False}
    DB["lotto"] = r
    save()
    kw = {}
    try:
        kw["file"] = lotto_file(lotto_balls_art(), "lotto_banner.png")
        art = True
    except Exception as ex:
        print("Lotto banner failed:", repr(ex))
        art = False
    msg = await channel.send(embed=lotto_embed(r, art), view=LottoPanel(), **kw)
    r["message"] = msg.id
    save()
    return msg

class LottoPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="מלא טופס", emoji="🎟️", style=discord.ButtonStyle.success, custom_id="lotto:buy")
    async def buy(self, interaction, button):
        r = lotto()
        say = lambda t: interaction.response.send_message(t, ephemeral=True)
        if not lotto_open_now(r):
            return await say("אין הגרלה פתוחה כרגע. ההגרלה הבאה תיפתח אחרי ההכרזה.")
        if len(lotto_mine(r, interaction.user.id)) >= LOTTO_MAX_TICKETS:
            return await say(f"כבר קנית {LOTTO_MAX_TICKETS} טפסים בהגרלה הזו.")
        if user_data(interaction.user.id)["cash"] < LOTTO_MIN_PRICE:
            return await say(f"טופס עולה לפחות {fmt(LOTTO_MIN_PRICE)} {cur()} ואין לך מספיק כסף במזומן.")
        form = LottoForm(interaction.user, r["id"])
        await interaction.response.send_message(embed=form.embed(), view=form, ephemeral=True)

    @discord.ui.button(label="הטפסים שלי", emoji="📋", style=discord.ButtonStyle.secondary, custom_id="lotto:mine")
    async def mine(self, interaction, button):
        r = lotto()
        mine = lotto_mine(r, interaction.user.id) if r else []
        if not mine:
            return await interaction.response.send_message("אין לך טפסים בהגרלה הזו.", ephemeral=True)
        embeds, files = [], []
        draw_text = datetime.datetime.fromtimestamp(r["end"], LOCAL_TZ).strftime("%d/%m")
        for i, t in enumerate(mine, 1):
            e = discord.Embed(color=LOTTO_BLUE_C, description=f"טופס {i}: סכום **{fmt(t['price'])}** {cur()}")
            try:
                files.append(lotto_file(lotto_ticket_art(tuple(t["nums"]), t["strong"], i, t["price"], draw_text), f"ticket{i}.png"))
                e.set_image(url=f"attachment://ticket{i}.png")
            except Exception as ex:
                print("Lotto ticket art failed:", repr(ex))
                e.description += f"\nמספרים: {' '.join(map(str, t['nums']))}  |  חזק: {t['strong']}"
            embeds.append(e)
        await interaction.response.send_message(embeds=embeds, files=files, ephemeral=True)

    @discord.ui.button(label="הסבר", emoji="📖", style=discord.ButtonStyle.secondary, custom_id="lotto:help")
    async def help(self, interaction, button):
        await interaction.response.send_message(embed=discord.Embed(color=LOTTO_BLUE_C, title="איך הלוטו עובד", description=LOTTO_RULES), ephemeral=True)

# ---------- the form (private) ----------
class LottoAmountModal(discord.ui.Modal):
    def __init__(self, form):
        super().__init__(title="סכום לטופס")
        self.form = form
        self.amount = discord.ui.TextInput(label=f"כמה לשים על הטופס? (מינימום {fmt(LOTTO_MIN_PRICE)})",
                                           placeholder="לדוגמה 12m או 15000000", max_length=20)
        self.add_item(self.amount)

    async def on_submit(self, interaction):
        cash = user_data(interaction.user.id)["cash"]
        v = parse_amount(self.amount.value.strip().lower(), cash)
        if v is None or v < LOTTO_MIN_PRICE:
            self.form.note = f"הסכום חייב להיות לפחות {fmt(LOTTO_MIN_PRICE)}."
        elif v > cash:
            self.form.note = "אין לך מספיק כסף במזומן לסכום הזה."
        else:
            self.form.price, self.form.note = v, ""
        self.form.rebuild()
        await interaction.response.edit_message(embed=self.form.embed(), view=self.form)

class LottoForm(discord.ui.View):
    def __init__(self, user, round_id):
        super().__init__(timeout=900)
        self.user, self.round_id = user, round_id
        self.nums, self.strong, self.price = set(), None, LOTTO_MIN_PRICE
        self.mode, self.page, self.note = "numbers", 0, ""
        self.rebuild()

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("זה לא הטופס שלך. לחץ על \"מלא טופס\" בהודעה הראשית.", ephemeral=True)
            return False
        return True

    def btn(self, label, cb, style=discord.ButtonStyle.secondary, row=0, emoji=None, disabled=False):
        b = discord.ui.Button(label=label, style=style, row=row, emoji=emoji, disabled=disabled)
        b.callback = cb
        self.add_item(b)

    def ready(self):
        return len(self.nums) == LOTTO_PICK and self.strong is not None and self.price >= LOTTO_MIN_PRICE

    def rebuild(self):
        self.clear_items()
        if self.mode == "numbers":
            lo, hi = (1, 20) if self.page == 0 else (21, LOTTO_RANGE)
            for i, n in enumerate(range(lo, hi + 1)):
                self.btn(str(n), self.toggle(n), discord.ButtonStyle.success if n in self.nums else discord.ButtonStyle.secondary, row=i // 5)
            self.btn("21-37 ▶" if self.page == 0 else "◀ 1-20", self.flip, row=4)
            self.btn("אקראי", self.random_nums, row=4, emoji="🎲")
            self.btn("נקה", self.clear_nums, row=4, emoji="🧹")
            self.btn("המשך", self.go_finish, discord.ButtonStyle.primary, row=4, emoji="➡️", disabled=len(self.nums) < LOTTO_PICK)
            return
        for n in range(1, LOTTO_STRONG + 1):
            self.btn(str(n), self.pick_strong(n), discord.ButtonStyle.success if n == self.strong else discord.ButtonStyle.secondary, row=0 if n <= 5 else 1)
        self.btn("חזק אקראי", self.random_strong, row=1, emoji="🎲")
        prices = list(LOTTO_PRESETS)
        if self.price not in prices:
            prices = sorted(prices + [self.price])
        sel = discord.ui.Select(placeholder="בחר סכום לטופס", row=2, options=[
            discord.SelectOption(label=fmt(p), value=str(p), default=p == self.price) for p in prices[:25]])
        sel.callback = self.pick_price
        self.add_item(sel)
        self.btn("חזרה למספרים", self.go_numbers, row=3, emoji="⬅️")
        self.btn("סכום אחר", self.custom_price, row=3, emoji="💳")
        self.btn("קנה טופס", self.purchase, discord.ButtonStyle.success, row=3, emoji="✅", disabled=not self.ready())

    def embed(self):
        r = lotto()
        note = f"\n\n> {self.note}" if self.note else ""
        if self.mode == "numbers":
            e = discord.Embed(color=LOTTO_RED, title="טופס לוטו | שלב 1 מתוך 2: בחירת מספרים", description=(
                f"בחרו {LOTTO_PICK} מספרים. מספר שבחרתם נראה כך: [07]. לחיצה נוספת עליו מסירה אותו.\n"
                f"{lotto_grid(self.nums)}\nנבחרו **{len(self.nums)}** מתוך {LOTTO_PICK}" + note))
            return e
        mine = len(lotto_mine(r, self.user.id)) + 1 if r else 1
        nums = " ".join(f"`{n:02d}`" for n in sorted(self.nums))
        table = "\n".join(f"{h} פגיעות: **{fmt(int(self.price * m))}**" if h > 1 else f"פגיעה אחת: **{fmt(int(self.price * m))}**"
                          for h, m in LOTTO_MULT.items())
        e = discord.Embed(color=LOTTO_RED, title=f"טופס לוטו {mine} | שלב 2 מתוך 2: מספר חזק וסכום", description=(
            "בחרו מספר חזק אחד מ-1 עד 7 (חובה), ואת הסכום שתשימו על הטופס.\n\n"
            f"המספרים שלכם: {nums}\n"
            f"המספר החזק: **{self.strong if self.strong else 'לא נבחר'}**\n"
            f"הסכום: **{fmt(self.price)}** {cur()}" + note))
        e.add_field(name="מה תקבלו אם תפגעו (לפי הסכום הזה)", value=table + f"\nמספר חזק נכון: עוד {int(LOTTO_STRONG_BONUS * 100)}%")
        if r:
            e.add_field(name="הקופה עכשיו", value=f"{fmt(lotto_pot(r))} {cur()}")
        e.set_footer(text=f"במזומן יש לך {fmt(user_data(self.user.id)['cash'])}")
        return e

    async def show(self, interaction):
        self.rebuild()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    def toggle(self, n):
        async def cb(interaction):
            if n in self.nums:
                self.nums.discard(n)
                self.note = ""
            elif len(self.nums) >= LOTTO_PICK:
                self.note = f"כבר בחרת {LOTTO_PICK} מספרים. לחץ על מספר שבחרת כדי להסיר אותו."
            else:
                self.nums.add(n)
                self.note = ""
            await self.show(interaction)
        return cb

    async def flip(self, interaction):
        self.page = 1 - self.page
        await self.show(interaction)

    async def random_nums(self, interaction):
        self.nums = set(random.sample(range(1, LOTTO_RANGE + 1), LOTTO_PICK))
        self.note = ""
        await self.show(interaction)

    async def clear_nums(self, interaction):
        self.nums, self.note = set(), ""
        await self.show(interaction)

    async def go_finish(self, interaction):
        self.mode, self.note = "finish", ""
        await self.show(interaction)

    async def go_numbers(self, interaction):
        self.mode, self.note = "numbers", ""
        await self.show(interaction)

    def pick_strong(self, n):
        async def cb(interaction):
            self.strong, self.note = n, ""
            await self.show(interaction)
        return cb

    async def random_strong(self, interaction):
        self.strong, self.note = random.randint(1, LOTTO_STRONG), ""
        await self.show(interaction)

    async def pick_price(self, interaction):
        self.price, self.note = int(interaction.data["values"][0]), ""
        await self.show(interaction)

    async def custom_price(self, interaction):
        await interaction.response.send_modal(LottoAmountModal(self))

    async def purchase(self, interaction):
        r, uid = lotto(), interaction.user.id
        u = user_data(uid)

        async def refuse(text):
            self.note = text
            await self.show(interaction)

        if not lotto_open_now(r) or r["id"] != self.round_id:
            self.stop()
            return await interaction.response.edit_message(embed=discord.Embed(color=RED, description="ההגרלה הזו כבר נסגרה."), view=None)
        if not self.ready():
            return await refuse("חסר מספר חזק או סכום תקין.")
        if len(lotto_mine(r, uid)) >= LOTTO_MAX_TICKETS:
            return await refuse(f"כבר קנית {LOTTO_MAX_TICKETS} טפסים.")
        if u["cash"] < self.price:
            return await refuse("אין לך מספיק כסף במזומן לסכום הזה.")
        u["cash"] -= self.price                      # no await between the check and the payment
        ticket = {"uid": str(uid), "nums": sorted(self.nums), "strong": self.strong, "price": self.price, "ts": int(time.time())}
        r["tickets"].append(ticket)
        save()
        self.stop()
        idx = len(lotto_mine(r, uid))
        log_money(interaction.user, "LOTTERY | TICKET", f"Bought ticket {idx}/{LOTTO_MAX_TICKETS} for {fmt(self.price)} {cur()}: "
                  f"{' '.join(map(str, ticket['nums']))} | strong {ticket['strong']}", BLUE)
        bg(lotto_refresh_panel())
        e = discord.Embed(color=GREEN, title="הטופס נקלט", description=(
            f"שילמת **{fmt(self.price)}** {cur()}. התוצאות בשבת ב-00:00, <t:{r['end']}:R>.\n"
            + (f"אפשר לקנות עוד טופס אחד." if idx < LOTTO_MAX_TICKETS else "קנית את כל הטפסים שמותר.")))
        kw = {}
        try:
            draw_text = datetime.datetime.fromtimestamp(r["end"], LOCAL_TZ).strftime("%d/%m")
            kw["attachments"] = [lotto_file(lotto_ticket_art(tuple(ticket["nums"]), ticket["strong"], idx, ticket["price"], draw_text), "ticket.png")]
            e.set_image(url="attachment://ticket.png")
        except Exception as ex:
            print("Lotto ticket art failed:", repr(ex))
            e.description += f"\nמספרים: {' '.join(map(str, ticket['nums']))}  |  חזק: {ticket['strong']}"
        await interaction.response.edit_message(embed=e, view=None, **kw)

# ---------- the draw ----------
async def lotto_announce(r, drawn, strong, rows, pot, top, carry):
    ch = bot.get_channel(r["channel"]) or await bot.fetch_channel(r["channel"])
    nums = "  ".join(f"`{n:02d}`" for n in drawn)
    e = discord.Embed(color=LOTTO_RED, title="תוצאות הלוטו השבועי", description=(
        f"המספרים שיצאו: {nums}\nהמספר החזק: **{strong}**\n\n"
        f"נמכרו **{len(r['tickets'])}** טפסים, והקופה הייתה **{fmt(pot)}** {cur()}."))
    if top:
        who = "\n".join(f"<@{x['t']['uid']}>: {x['hits']} פגיעות" + (" + חזק" if x["sh"] else "") + f" | {fmt(x['pot'])} {cur()}" for x in top)
        e.add_field(name="לקחו את הקופה", value=who, inline=False)
    else:
        e.add_field(name="הקופה", value=f"אף אחד לא פגע בשום מספר, **{fmt(carry)}** {cur()} עוברים להגרלה הבאה." if rows
                    else f"לא נמכרו טפסים, **{fmt(carry)}** {cur()} עוברים להגרלה הבאה.", inline=False)
    wins = [x for x in rows if x["prize"] > 0]
    if wins:
        wins.sort(key=lambda x: -x["prize"])
        lines = [f"<@{x['t']['uid']}>: {x['hits']} פגיעות" + (" + חזק" if x["sh"] else "") + f" | **{fmt(x['prize'])}** {cur()}" for x in wins[:15]]
        if len(wins) > 15:
            lines.append(f"ועוד {len(wins) - 15} טפסים")
        e.add_field(name="פרסים על הפגיעות", value="\n".join(lines), inline=False)
    kw = {}
    try:
        kw["file"] = lotto_file(lotto_balls_art(tuple(drawn), strong), "lotto_result.png")
        e.set_image(url="attachment://lotto_result.png")
    except Exception as ex:
        print("Lotto result art failed:", repr(ex))
    winners = sorted({x["t"]["uid"] for x in rows if x["prize"] or x["pot"]})[:10]
    content = ("מזל טוב " + " ".join(f"<@{u}>" for u in winners)) if winners else None
    await ch.send(content=content, embed=e, allowed_mentions=discord.AllowedMentions(users=True), **kw)

async def lotto_finish(force=False):
    """Draw the numbers, pay everybody, announce, and open the next round. It can never run twice for the same round."""
    async with LOTTO_LOCK:
        r = DB.get("lotto")
        if not r or r.get("done") or (not force and time.time() < r["end"]):
            return
        r["done"] = True
        save()
        drawn = sorted(random.sample(range(1, LOTTO_RANGE + 1), LOTTO_DRAWN))
        strong = random.randint(1, LOTTO_STRONG)
        pot = lotto_pot(r)
        rows = []
        for t in r["tickets"]:
            hits, sh = len(set(t["nums"]) & set(drawn)), t["strong"] == strong
            rows.append({"t": t, "hits": hits, "sh": sh, "prize": lotto_prize(t["price"], hits, sh), "pot": 0})
        best = max(((x["hits"], x["sh"]) for x in rows), default=(0, False))
        top, carry = [], pot
        if rows and best[0] >= 1:
            top = [x for x in rows if (x["hits"], x["sh"]) == best]
            share = pot // len(top)
            for x in top:
                x["pot"] = share
            carry = pot - share * len(top)
        totals = {}
        for x in rows:
            totals[x["t"]["uid"]] = totals.get(x["t"]["uid"], 0) + x["prize"] + x["pot"]
        for uid, amount in totals.items():
            if amount:
                user_data(int(uid))["bank"] += amount
        DB["lotto_last"] = {"id": r["id"], "drawn": drawn, "strong": strong, "pot": pot, "carry": carry,
                            "tickets": len(r["tickets"]), "paid": sum(totals.values())}
        save()
        for uid, amount in totals.items():
            if amount:
                try:
                    user = bot.get_user(int(uid)) or await bot.fetch_user(int(uid))
                    log_money(user, "LOTTERY | WIN", f"Won {fmt(amount)} {cur()} in the weekly lottery (paid to the bank)", GREEN)
                except Exception as ex:
                    print("Lotto log failed:", repr(ex))
        try:
            await lotto_announce(r, drawn, strong, rows, pot, top, carry)
        except Exception as ex:
            print("Lotto announce failed:", repr(ex))
        try:
            ch = bot.get_channel(r["channel"]) or await bot.fetch_channel(r["channel"])
            await lotto_open(ch, carry)          # a new round for the next Saturday
        except Exception as ex:
            print("Lotto next round failed:", repr(ex))

@tasks.loop(seconds=30)
async def lotto_loop():
    if loaded is None or not loaded.is_set():
        return
    r = DB.get("lotto")
    if r and not r.get("done") and time.time() >= r["end"]:
        try:
            await lotto_finish()
        except Exception as ex:
            print("Lotto draw failed:", repr(ex))

@bot.command(name="lottery", usage="lottery [draw | cancel]")
@owner_only
async def lottery(ctx, sub: str = None):
    if ctx.channel.id != LOTTO_CHANNEL_ID:
        return await reply(ctx, f"The lottery can only be managed in <#{LOTTO_CHANNEL_ID}>.", RED)
    r, sub = lotto(), (sub or "").lower()
    if sub == "draw":
        if not r or r.get("done"):
            return await reply(ctx, "There is no open lottery.", RED)
        return await lotto_finish(force=True)
    if sub == "cancel":
        if not r or r.get("done"):
            return await reply(ctx, "There is no open lottery.", RED)
        async with LOTTO_LOCK:
            for t in r["tickets"]:
                user_data(int(t["uid"]))["cash"] += t["price"]
            n = len(r["tickets"])
            r["done"] = True
            DB["lotto"] = None
            save()
        try:
            ch = bot.get_channel(r["channel"]) or await bot.fetch_channel(r["channel"])
            await ch.get_partial_message(r["message"]).edit(embed=discord.Embed(color=RED, title="הלוטו בוטל", description="כל הטפסים הוחזרו למזומן."), view=None)
        except Exception:
            pass
        return await reply(ctx, f"The lottery was cancelled and {n} tickets were refunded. Use `$lottery` to open a new one.", GREEN)
    if r and not r.get("done"):
        if not lotto_open_now(r):             # the time is over, the draw is just about to run
            await reply(ctx, "The draw time has passed, the draw is running now.", BLUE)
            return await lotto_finish()
        await reply(ctx, f"A lottery is already open (ends <t:{r['end']}:R>). Here is its panel again.", BLUE)
        try:
            kw = {"file": lotto_file(lotto_balls_art(), "lotto_banner.png")}
            art = True
        except Exception:
            kw, art = {}, False
        msg = await ctx.channel.send(embed=lotto_embed(r, art), view=LottoPanel(), **kw)
        r["channel"], r["message"] = ctx.channel.id, msg.id
        save()
        return
    await lotto_open(ctx.channel, 0)
    await reply(ctx, "The lottery is open. It ends on Saturday at 00:00.", GREEN)

@bot.command(name="staff-role", usage="staff-role @role")
@admin_only
async def staff_role(ctx, role: discord.Role = None):
    if role is None:
        current = ctx.guild.get_role(DB.get("staff_role") or 0)
        return await reply(ctx, f"Staff role: {current.mention if current else 'not set'}\nSet it with `$staff-role @role`", BLUE)
    DB["staff_role"] = role.id
    save()
    await reply(ctx, f"Staff role set to {role.mention}. Members with this role can now use the staff commands.", GREEN)

# ---------- immunity (nobody can rob an immune player) ----------
NOLIMIT_WORDS = ("nolimit", "no-limit", "forever", "unlimited", "permanent")

def immunity_until(member):
    """None = not immune, 0 = immune without a time limit, otherwise the time it ends."""
    rid = DB.get("immunity_role")
    has_role = bool(rid) and any(r.id == rid for r in getattr(member, "roles", []))
    rec = DB.get("immunity", {}).get(str(member.id))
    if rec is not None:                              # given with $immunity: the time decides, the role only follows it
        return rec if rec == 0 or rec > time.time() else None
    return 0 if has_role else None                   # the role was given by hand

@tasks.loop(seconds=20)
async def immunity_loop():
    """When a timed immunity ends: the record is deleted and the immunity role is taken back."""
    if loaded is None or not loaded.is_set():
        return
    rec = DB.get("immunity", {})
    expired = [uid for uid, t in rec.items() if t and t <= time.time()]
    if not expired:
        return
    rid = DB.get("immunity_role")
    for uid in expired:
        rec.pop(uid, None)
        for g in bot.guilds:
            role, m = g.get_role(rid or 0), g.get_member(int(uid))
            if role and m and role in m.roles:
                try:
                    await m.remove_roles(role, reason="Immunity ended")
                except Exception as ex:
                    print("Immunity role removal failed:", repr(ex))
    save()

@bot.command(name="setimmunity", usage="setimmunity @role | off")
@staff_only
async def setimmunity(ctx, role: str = None):
    current = ctx.guild.get_role(DB.get("immunity_role") or 0)
    if role is None:
        return await reply(ctx, f"Immunity role: {current.mention if current else 'not set'}\n"
                                f"Everyone with this role cannot be robbed.\nSet it with `$setimmunity @role` (or `$setimmunity off`).", BLUE)
    if role.lower() in ("off", "none", "remove"):
        DB.pop("immunity_role", None)
        save()
        return await reply(ctx, "The immunity role was removed.", GREEN)
    try:
        r = await commands.RoleConverter().convert(ctx, role)
    except commands.BadArgument:
        return await reply(ctx, "Usage: `$setimmunity @role | off`", RED)
    DB["immunity_role"] = r.id
    save()
    await reply(ctx, f"Immunity role set to {r.mention}. Members with this role cannot be robbed.", GREEN)

@bot.command(name="immunity", usage="immunity <user> <time | nolimit>")
@staff_only
async def immunity(ctx, target: str = None, duration: str = None):
    member = await resolve_target(ctx, target) if target else None
    if member is None or duration is None:
        return await reply(ctx, "Usage: `$immunity <user> <time | nolimit>`", RED)
    if member.bot:
        return await reply(ctx, "Please enter a valid user.", RED)
    if duration.lower() in NOLIMIT_WORDS:
        until = 0
    else:
        secs = parse_duration(duration)
        if secs is None:
            return await reply(ctx, "Invalid time. Use `30m`, `2h`, `1d` or `nolimit`.", RED)
        until = int(time.time()) + secs
    DB.setdefault("immunity", {})[str(member.id)] = until
    save()
    note = ""
    role = ctx.guild.get_role(DB.get("immunity_role") or 0)
    if role and role not in member.roles:
        try:
            await member.add_roles(role, reason=f"Immunity by {ctx.author}")
            note = f"\n{member.name} received {role.mention}."
        except discord.Forbidden:
            note = "\nI could not give the immunity role (my role must be above it). The immunity still works."
    await reply(ctx, f"{member.name} is now immune from robbery ({fmt_left(until)}).{note}", GREEN)

@bot.command(name="rimmunity", usage="rimmunity <user>")
@staff_only
async def rimmunity(ctx, target: str = None):
    member = await resolve_target(ctx, target) if target else None
    if member is None:
        return await reply(ctx, "Usage: `$rimmunity <user>`", RED)
    rec = DB.get("immunity", {}).pop(str(member.id), None)
    role = ctx.guild.get_role(DB.get("immunity_role") or 0)
    had_role = bool(role) and role in member.roles
    if rec is None and not had_role:
        return await reply(ctx, f"{member.name} has no immunity.", RED)
    save()
    if had_role:
        try:
            await member.remove_roles(role, reason=f"Immunity removed by {ctx.author}")
        except discord.Forbidden:
            return await reply(ctx, "I could not take the immunity role (my role must be above it). Remove it by hand.", RED)
    await reply(ctx, f"The immunity of {member.name} was removed.", GREEN)

@bot.command(name="setgamelogs", usage="setgamelogs #channel")
@admin_only
async def setgamelogs(ctx, channel: discord.TextChannel = None):
    if channel is None:
        current = DB.get("log_channel")
        return await reply(ctx, f"Log channel: {f'<#{current}>' if current else 'not set'}\nSet it with `$setgamelogs #channel`", BLUE)
    perms = channel.permissions_for(ctx.guild.me)
    if not (perms.view_channel and perms.send_messages and perms.embed_links):
        return await reply(ctx, f"I can't send embeds in {channel.mention}. Give me permission there first.", RED)
    DB["log_channel"] = channel.id
    save()
    await reply(ctx, f"Game logs will now be sent to {channel.mention}.", GREEN)
    log_event(ctx.author, "LOG CHANNEL SET", "This channel is now the game log (wins, losses and money changes).", BLUE)

async def parse_money_args(ctx, args):
    where = member = amount = None
    for a in args:
        low = a.lower()
        if where is None and low in ("bank", "cash", "all"):
            where = low
        elif member is None and (re.fullmatch(r"<@!?\d+>", a) or (a.isdigit() and len(a) >= 15)):
            member = await commands.MemberConverter().convert(ctx, a)
        elif amount is None and parse_amount(a, 0) is not None:
            amount = a
        elif member is None:
            member = await commands.MemberConverter().convert(ctx, a)
        else:
            raise commands.BadArgument()
    return where, member, amount

def _add_used():
    used = DB.setdefault("add_used", {})
    if used.get("date") != today_key():          # new day (00:00): counters start from zero
        used.clear()
        used["date"] = today_key()
        used["users"] = {}
    return used["users"]

def add_limit_error(ctx):
    cap = DB.get("add_limit")
    if ctx.author.id in OWNER_IDS or not cap:
        return None
    if _add_used().get(str(ctx.author.id), 0) >= cap:
        return "You have used all of your daily additions for today."
    return None

def add_limit_count(ctx):
    if ctx.author.id in OWNER_IDS or not DB.get("add_limit"):
        return
    users = _add_used()
    users[str(ctx.author.id)] = users.get(str(ctx.author.id), 0) + 1

def add_cap_error(ctx, amt):
    cap = DB.get("add_max")
    if ctx.author.id not in OWNER_IDS and cap and amt > cap:
        return f"You can add at most **{fmt(cap)}** {cur()} per command."
    return None

@bot.command(name="addmoney", usage="addmoney <bank|cash> @user <amount>")
@staff_only
async def addmoney(ctx, *args: str):
    where, member, amount = await parse_money_args(ctx, args)
    amt = parse_amount(amount, 0)
    if where not in ("bank", "cash") or member is None or amt is None or amt <= 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    err = add_cap_error(ctx, amt) or add_limit_error(ctx)
    if err:
        return await reply(ctx, err, RED)
    add_limit_count(ctx)
    user_data(member.id)[where] += amt
    save()
    log_event(ctx.author, "ADD MONEY", f"Added **{fmt(amt)}** {cur()} to the {where} of {member.name} (`{member.id}`)", BLUE)
    await reply(ctx, f"Added {fmt(amt)} {cur()} to {member.name}'s {where}.", GREEN)

@bot.command(name="removemoney", usage="removemoney <bank|cash> @user <amount>")
@staff_only
async def removemoney(ctx, *args: str):
    where, member, amount = await parse_money_args(ctx, args)
    if where not in ("bank", "cash") or member is None or amount is None:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    u = user_data(member.id)
    amt = parse_amount(amount, u[where])
    if amt is None or amt <= 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    taken = min(amt, u[where])
    u[where] -= taken
    save()
    log_event(ctx.author, "REMOVE MONEY", f"Removed **{fmt(taken)}** {cur()} from the {where} of {member.name} (`{member.id}`)", BLUE)
    await reply(ctx, f"Removed {fmt(taken)} {cur()} from {member.name}'s {where}.", GREEN)

@bot.command(name="resetmoney", usage="resetmoney <bank|cash|all> @user [amount]")
@staff_only
async def resetmoney(ctx, *args: str):
    where, member, amount = await parse_money_args(ctx, args)
    amt = 0 if amount is None else parse_amount(amount, 0)
    if where not in ("bank", "cash", "all") or member is None or amt is None or amt < 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    u = user_data(member.id)
    if where == "all":
        u["cash"] = u["bank"] = 0
    else:
        u[where] = amt
    save()
    log_event(ctx.author, "RESET MONEY", f"{member.name} (`{member.id}`): {where} " +
              ("reset to 0" if where == "all" else f"set to **{fmt(amt)}**"), BLUE)
    await reply(ctx, f"{member.name}'s {where} " + ("was reset to 0." if where == "all" else f"was set to {fmt(amt)} {cur()}."), GREEN)

@bot.command(name="addmoneyrole", usage="addmoneyrole <bank|cash> @role <amount>")
@staff_only
async def addmoneyrole(ctx, where: str, role: discord.Role, amount: str):
    where = where.lower()
    amt = parse_amount(amount, 0)
    if where not in ("bank", "cash") or amt is None or amt <= 0:
        return await reply(ctx, f"Usage: `${ctx.command.usage}`", RED)
    err = add_cap_error(ctx, amt) or add_limit_error(ctx)
    if err:
        return await reply(ctx, err, RED)
    if not ctx.guild.chunked:
        await ctx.guild.chunk()
    members = [m for m in role.members if not m.bot]
    if not members:
        return await reply(ctx, "No members found in that role.", RED)
    add_limit_count(ctx)
    for m in members:
        user_data(m.id)[where] += amt
    save()
    log_event(ctx.author, "ADD MONEY TO ROLE", f"Added **{fmt(amt)}** {cur()} to the {where} of {len(members)} members of {role.name}", BLUE)
    await reply(ctx, f"Added {fmt(amt)} {cur()} to the {where} of each of the {len(members)} members of {role.mention}.", GREEN)

@bot.command(name="set-currency", aliases=["currency"], usage="set-currency <emoji>")
@staff_only
async def currency(ctx, symbol: str = None):
    if symbol is None:
        return await reply(ctx, f"Current currency: {cur()}\nChange it with `$set-currency <emoji>`", BLUE)
    DB["currency"] = symbol
    save()
    await reply(ctx, f"Currency changed to {symbol}", GREEN)
