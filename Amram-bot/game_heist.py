import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= HEIST ($heist) =================
GOLD = 0xD4AF37
HEIST_ORANGE = 0xE67E22
HEIST_MAX = 5                    # the biggest crew a heist can have ($heist 5)
HEIST_DEFAULT = 3                # crew size when nobody writes a number
HEIST_MIN = 2                    # fewer players than this when the sign-up closes = the heist is cancelled and everybody gets the money back
HEIST_FEE = 2_500_000            # fixed entry fee per player (a heist has expenses), not a bet
HEIST_JOIN_WAIT = 30             # seconds to join
HEIST_ROLE_WAIT = 30             # seconds to choose a role
HEIST_OPEN_WAIT = 30             # seconds to press "המשימה שלי"
# time for a mission, counted from the moment the player opens it (we are human: +30 seconds for every role)
HEIST_TIME = {"hacker": 85, "bomber": 66, "lookout": 72, "bodyguard": 80}
HEIST_MULT = {1: 3.5, 2: 2.2, 3: 1.5, 4: 1.3, 5: 1.2}   # all 3 missions done: fee x this (a small crew is riskier, so it pays more)
HEIST_PART = 0.5                 # only 2 of 3 missions done: this part of the fee comes back
HEIST_AUTO = 0.5                 # chance that a role nobody took succeeds by itself
HEIST_SKIPS = 2                  # "התעלמות" = a new task, per player
HEIST_FUSE = 20                  # seconds the bomber has to run out
HEIST_GRACE = 1.5                # network delay allowed on the run
HEIST_LOOT_PICKS = 2             # drawers every player may open after the safes blow up
HEIST_LOOT_WAIT = 90             # seconds to open the drawers (the message can be sent again by a button until then)
HEIST_ROLES = {                  # key: (name, icon)
    "lookout": ("מנטרל שוטרים", "👮"),
    "hacker": ("מפצח קוד", "💻"),
    "bomber": ("מפוצץ כספות", "💣"),
    "bodyguard": ("שומר ראש", "🔫"),
}
HEIST_ROLE_ORDER = ("lookout", "hacker", "bomber", "bodyguard")
HEIST_CORE = ("lookout", "hacker", "bomber")      # these three always have to be done
HEIST_ROLE_CAP = {"bodyguard": 2}                 # how many players may take a role (default 1): two bodyguards are allowed
HEISTS = {}                      # channel id -> the open heist of that channel

# loot inside the drawers: (emoji, name, value in money)
LOOT_ITEMS = [
    ("👑", "כתר זהב", 75_000_000), ("💎", "יהלום", 25_000_000), ("💰", "שק כסף", 12_500_000),
    ("💍", "טבעת יהלום", 7_500_000), ("⌚", "שעון יוקרה", 5_000_000), ("💵", "צרור דולרים", 2_500_000),
    ("🪙", "מטבעות זהב", 1_000_000),
]
LOOT_DRAWERS, LOOT_EMPTY = 9, 3  # 9 drawers for every player, 3 of them are empty

HEIST_WALLS = ["צפון", "דרום", "מזרח", "מערב"]
HEIST_OPP = {"צפון": "דרום", "דרום": "צפון", "מזרח": "מערב", "מערב": "מזרח"}
HEIST_COLORS = {"🟥": ["דם", "תות", "כבאית"], "🟦": ["שמיים", "ים", "ג'ינס"],
                "🟩": ["דשא", "עלה", "צפרדע"], "🟨": ["שמש", "לימון", "בננה"]}
HEIST_RADIO = ["יחידה 4 לכל הכוחות, חשוד נראה ליד הכספת.", "כאן מוקד, ניידות בדרך אל המבנה.",
               "דיווח על סיור משטרתי בקומת הכניסה.", "אזעקה שקטה הופעלה בבנק, כל היחידות לאזור."]

HACK_DIGITS, HACK_LEN, HACK_TRIES = "123456789", 3, 10

def hack_new():
    return "".join(random.sample(HACK_DIGITS, HACK_LEN))

def hack_score(code, guess):
    """(right digit in the right place, right digit in the wrong place)"""
    exact = sum(x == y for x, y in zip(code, guess))
    return exact, len(set(code) & set(guess)) - exact

def heist_used_today(uid):
    if uid in OWNER_IDS:                 # the owners have no daily limit
        return False
    return DB.get("heist_day", {}).get(str(uid)) == today_key()

def heist_mark(uid):
    """A player can CREATE one heist per day (no matter who joins). Resets at 00:00. Owners are exempt."""
    if uid in OWNER_IDS:
        return
    today = today_key()
    days = DB.setdefault("heist_day", {})
    for k in [k for k, v in days.items() if v != today]:
        days.pop(k, None)
    days[str(uid)] = today
    save()

def heist_unmark(uid):
    DB.get("heist_day", {}).pop(str(uid), None)
    save()

@lru_cache(maxsize=None)
def heist_art(kind):
    """Banner: a gold vault on a dark wall. kind: vault (closed), win (open, glowing), fail (red alarm)."""
    S, W, H = 2, 900, 300
    fail, win = kind == "fail", kind == "win"
    top, bot = ((12, 14, 26), (30, 24, 38)) if not fail else ((30, 8, 14), (56, 14, 22))
    im = Image.new("RGBA", (W * S, H * S))
    d = ImageDraw.Draw(im)

    def X(v):
        return int(v * S)

    for y in range(H * S):
        k = y / (H * S - 1)
        d.line([(0, y), (W * S, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip(top, bot)) + (255,))

    def over(fn, blur=0):
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
        fn(ImageDraw.Draw(layer))
        if blur:
            layer = layer.filter(ImageFilter.GaussianBlur(blur * S))
        im.alpha_composite(layer)

    def disc(cx, cy, r, fill, outline=None, width=1):
        d.ellipse([X(cx - r), X(cy - r), X(cx + r), X(cy + r)], fill=fill, outline=outline, width=width * S if outline else 0)

    # wall: faint bricks
    line = (255, 255, 255, 10)
    over(lambda g: [g.line([(0, X(y)), (X(W), X(y))], fill=line, width=S) for y in range(20, H, 30)] +
         [g.line([(X(x + (15 if (y // 30) % 2 else 0)), X(y)), (X(x + (15 if (y // 30) % 2 else 0)), X(y + 30))], fill=line, width=S)
          for y in range(20, H - 30, 30) for x in range(0, W, 60)])
    # floor
    over(lambda g: g.rectangle([0, X(262), X(W), X(H)], fill=(0, 0, 0, 120)))

    cx, cy, R = 450, 142, 112
    accent = (205, 40, 50) if fail else (212, 175, 55)
    over(lambda g: g.ellipse([X(cx - 170), X(cy - 130), X(cx + 170), X(cy + 130)], fill=accent + (110 if not fail else 90,)), blur=46)
    if fail:
        over(lambda g: g.ellipse([X(20), X(60), X(220), X(260)], fill=(230, 30, 40, 150)), blur=36)
        over(lambda g: g.ellipse([X(680), X(60), X(880), X(260)], fill=(40, 100, 250, 150)), blur=36)
    if win:
        over(lambda g: [g.polygon([(X(cx), X(cy)),
                                   (X(cx + 520 * math.cos(math.radians(a - 4))), X(cy + 520 * math.sin(math.radians(a - 4)))),
                                   (X(cx + 520 * math.cos(math.radians(a + 4))), X(cy + 520 * math.sin(math.radians(a + 4))))],
                                  fill=(255, 220, 120, 34)) for a in range(0, 360, 20)], blur=2)

    over(lambda g: g.ellipse([X(cx - R + 8), X(cy + R - 14), X(cx + R + 8), X(cy + R + 18)], fill=(0, 0, 0, 160)), blur=8)
    for i in range(R, R - 18, -1):                       # steel/gold rim
        k = (R - i) / 18
        c = tuple(int(a + (b - a) * k) for a, b in zip((150, 110, 25), (250, 224, 130)))
        disc(cx, cy, i, c + (255,))
    face = (255, 226, 140) if win else (34, 37, 50)
    edge = (185, 120, 20) if win else (20, 22, 32)
    for i in range(R - 18, 0, -2):                      # door face, lighter in the middle
        k = i / (R - 18)
        c = tuple(int(a + (b - a) * k) for a, b in zip(face, edge))
        disc(cx, cy, i, c + (255,))
    disc(cx, cy, R - 34, None, outline=(222, 188, 80, 255), width=3)
    for n in range(12):                                   # bolts
        a = math.radians(n * 30 + 15)
        bx, by = cx + (R - 9) * math.cos(a), cy + (R - 9) * math.sin(a)
        disc(bx, by, 3.2, (255, 238, 170, 255), outline=(120, 85, 15, 255), width=1)
    rot = 30 if win else 90
    for n in range(3):                                    # wheel
        a = math.radians(rot + n * 120)
        ex, ey = cx + 62 * math.cos(a), cy + 62 * math.sin(a)
        d.line([(X(cx), X(cy)), (X(ex), X(ey))], fill=(150, 108, 22, 255), width=X(12))
        d.line([(X(cx), X(cy)), (X(ex), X(ey))], fill=(240, 205, 100, 255), width=X(8))
        disc(ex, ey, 10, (240, 205, 100, 255), outline=(150, 108, 22, 255), width=2)
    for i in range(24, 0, -1):
        k = i / 24
        c = tuple(int(a + (b - a) * k) for a, b in zip((255, 240, 180), (170, 120, 25)))
        disc(cx, cy, i, c + (255,))
    disc(cx, cy, 6, (90, 60, 10, 255))
    over(lambda g: g.pieslice([X(cx - R), X(cy - R), X(cx + R), X(cy + R)], 200, 250, fill=(255, 255, 255, 38)))

    def coin(x, y, rx=22, ry=8):
        for j in range(5, 0, -1):
            d.ellipse([X(x - rx), X(y - ry + j), X(x + rx), X(y + ry + j)], fill=(150, 105, 20, 255))
        d.ellipse([X(x - rx), X(y - ry), X(x + rx), X(y + ry)], fill=(245, 205, 70, 255), outline=(255, 238, 160, 255), width=S)
        d.ellipse([X(x - rx * .6), X(y - ry * .55), X(x + rx * .6), X(y + ry * .55)], outline=(190, 140, 30, 255), width=S)

    if win:
        rng = random.Random(3)
        for base_x in (170, 730):
            for row in range(4):
                for col in range(4 - row):
                    coin(base_x + (col - (3 - row) / 2) * 44 + rng.randint(-3, 3), 270 - row * 11, 22, 8)
    out = im.convert("RGB")
    vig = Image.new("L", (W // 4, H // 4), 0)
    ImageDraw.Draw(vig).ellipse([-W // 10, -H // 8, W // 4 + W // 10, H // 4 + H // 8], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(24)).resize(out.size, Image.BILINEAR)
    out = Image.composite(out, Image.new("RGB", out.size, (4, 5, 10)), vig)
    out = out.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()

class Heist:
    def __init__(self, channel, stake, size=HEIST_DEFAULT):
        self.channel, self.stake = channel, stake
        self.size = size                           # how many players the crew has when it is full
        self.token = None
        self.creator = None
        self.cancelled = False
        self.players = {}        # user id -> {"user", "token", "role"}
        self.phase = "join"      # join -> roles -> mission -> done
        self.message = self.view = None
        self.art = False
        self.results = {}        # user id -> True / False (his personal mission)
        self.opened = set()
        self.interactions = {}   # user id -> the interaction of his mission message (used to send him the loot drawers)
        self.vault_open = False
        self.vault_task = None
        self.loot = {}           # user id -> money stolen from the drawers
        self.loot_items = {}     # user id -> list of (emoji, name)
        self.loot_pending = set()
        self.loot_views = {}     # user id -> his current drawers view
        self.loot_deadline = 0
        self.full, self.roles_set, self.all_done = asyncio.Event(), asyncio.Event(), asyncio.Event()
        self.loot_done = asyncio.Event()
        self.end = int(time.time()) + HEIST_JOIN_WAIT

    def add_player(self, user, token, role=None):
        self.players[user.id] = {"user": user, "token": token, "role": role}
        if len(self.players) >= self.size:
            self.full.set()

    def holders(self, role):
        return [uid for uid, p in self.players.items() if p["role"] == role]

    def role_free(self, role):
        return len(self.holders(role)) < HEIST_ROLE_CAP.get(role, 1)

    def report(self, uid, ok):
        if self.phase != "mission" or uid in self.results:
            return
        self.results[uid] = ok
        if len(self.results) >= len(self.players):
            if all(self.results.values()) and self.vault_task is None:     # everybody succeeded: the safes open for all, at once
                self.vault_task = asyncio.create_task(vault_blown(self))
            self.all_done.set()
        bg(self.refresh())

    def embed(self):
        n = len(self.players)
        e = discord.Embed(color=GOLD, title="שוד הבנק")
        if self.phase == "join":
            e.description = (f"לחצו על כניסה כדי להצטרף. עד {self.size} שחקנים, לכל אחד משימה משלו. הצוות מרוויח רק אם המשימות מצליחות.\n"
                             f"דמי הכניסה הם סכום קבוע של **{fmt(self.stake)}** {cur()} לכל שחקן (הוצאות השוד).\n"
                             f"נדרשים לפחות {HEIST_MIN} שחקנים, אחרת השוד מתבטל והכסף חוזר למזומן. כשהצוות מלא ({self.size}), בחירת התפקידים מתחילה מיד.")
            when = "ההרשמה נסגרת"
        elif self.phase == "roles":
            e.description = "כל אחד בוחר תפקיד אחד. שני שחקנים יכולים להיות שומרי ראש. מי שלא בחר יקבל תפקיד פנוי."
            when = "הבחירה נסגרת"
        else:
            e.description = ("לחצו על המשימה שלי כדי לקבל הודעה אישית שרק אתם רואים. הזמן מתחיל לרוץ ברגע שפתחתם אותה.\n"
                             "רק כשכל הצוות מסיים את המשימה בהצלחה, כולם מקבלים הודעה ויכולים לגנוב מהמגירות.")
            when = "אפשר לפתוח עד"
            if self.vault_open:
                e.description = ("💥 כל הצוות הצליח והכספות התפוצצו! המגירות נשלחו לכולם.\n"
                                 "אם ההודעה הפרטית נעלמה, לחצו על \"המגירות שלי\" כדי לקבל אותה שוב.")
        e.add_field(name="דמי כניסה", value=f"{fmt(self.stake)} {cur()}")
        e.add_field(name="שחקנים", value=f"{n} מתוך {self.size}")
        e.add_field(name=when, value=f"<t:{self.end}:R>")
        if self.phase == "join":
            e.add_field(name="הצוות", value="\n".join(p["user"].mention for p in self.players.values()), inline=False)
        else:
            for key in HEIST_ROLE_ORDER:
                name, icon = HEIST_ROLES[key]
                parts = []
                for uid in self.holders(key):
                    t = self.players[uid]["user"].mention
                    if self.phase == "mission":
                        t += " סיים" if uid in self.results else " בביצוע" if uid in self.opened else " ממתין"
                    parts.append(t)
                e.add_field(name=f"{icon} {name}", value="\n".join(parts) or "פנוי")
        e.set_footer(text=f"הצלחה מלאה בצוות של {n}: x{HEIST_MULT[n]:g}   |   חסרה משימה אחת: מחצית מההימור חוזרת")
        if self.art:
            e.set_image(url="attachment://heist.png")
        return e

    async def refresh(self):
        if not self.message or self.phase == "done":
            return
        try:
            await self.message.edit(embed=self.embed(), view=self.view)
        except Exception as ex:
            print("Heist refresh failed:", repr(ex))

async def hz_edit(interaction, **kw):
    if not interaction.response.is_done():
        await interaction.response.edit_message(**kw)
    else:
        await interaction.edit_original_response(**kw)

class HeistView(discord.ui.View):
    def __init__(self, h):
        super().__init__(timeout=None)
        self.h = h
        self.show_join()

    def show_join(self):
        self.clear_items()
        b = discord.ui.Button(style=discord.ButtonStyle.success, label=f"כניסה למשחק ({fmt(self.h.stake)})")
        b.callback = self.join
        self.add_item(b)
        b = discord.ui.Button(style=discord.ButtonStyle.danger, label="יציאה", emoji="🚪")
        b.callback = self.leave
        self.add_item(b)

    def show_roles(self):
        self.clear_items()
        for key in HEIST_ROLE_ORDER:
            name, icon = HEIST_ROLES[key]
            taken = not self.h.role_free(key)
            b = discord.ui.Button(style=discord.ButtonStyle.secondary if taken else discord.ButtonStyle.primary,
                                  label=name, emoji=icon, disabled=taken)
            b.callback = self.pick(key)
            self.add_item(b)

    async def join(self, interaction):
        h, user = self.h, interaction.user
        say = lambda t: interaction.response.send_message(t, ephemeral=True)
        if h.phase != "join":
            return await say("ההרשמה לשוד הזה כבר נסגרה.")
        if user.id in h.players:
            return await say("אתה כבר בצוות.")
        if len(h.players) >= h.size:
            return await say("הצוות מלא.")
        if user.id in BUSY:
            return await say(BUSY_MSG)
        u = user_data(user.id)
        if u["cash"] < h.stake:
            return await say(f"אין לך מספיק כסף. דמי הכניסה הם {fmt(h.stake)} {cur()}.")
        u["cash"] -= h.stake
        token = f"{h.token}:{user.id}"
        DB.setdefault("pending", {})[token] = {"uid": str(user.id), "bet": h.stake}
        BUSY.add(user.id)
        save()
        h.add_player(user, token)
        if h.full.is_set():                   # 3 players: the role choice starts right now, run_heist updates the message
            return await interaction.response.defer()
        await interaction.response.edit_message(embed=h.embed(), view=self)

    def pick(self, role):
        async def cb(interaction):
            h = self.h
            p = h.players.get(interaction.user.id)
            say = lambda t: interaction.response.send_message(t, ephemeral=True)
            if p is None:
                return await say("אינך חלק מהצוות של השוד הזה.")
            if h.phase != "roles":
                return await interaction.response.defer()
            if p["role"]:
                return await say("כבר בחרת תפקיד.")
            if not h.role_free(role):
                return await say("התפקיד הזה כבר נתפס, בחר אחר.")
            p["role"] = role
            self.show_roles()
            await interaction.response.edit_message(embed=h.embed(), view=self)
            if all(q["role"] for q in h.players.values()):
                h.roles_set.set()
        return cb

    async def leave(self, interaction):
        """Only while the sign-up is open: the player is removed and his entry fee goes back to cash."""
        h, user = self.h, interaction.user
        say = lambda t: interaction.response.send_message(t, ephemeral=True)
        p = h.players.get(user.id)
        if p is None:
            return await say("אינך בצוות של השוד הזה.")
        if h.phase != "join" or h.full.is_set():
            return await say("אי אפשר לצאת אחרי שהשוד התחיל.")
        h.players.pop(user.id)
        if DB.get("pending", {}).pop(p["token"], None) is not None:
            user_data(user.id)["cash"] += h.stake
        BUSY.discard(user.id)
        if user.id == h.creator:
            heist_unmark(user.id)
        save()
        log_money(user, "HEIST | LEFT", f"Left the heist, entry fee of {fmt(h.stake)} {cur()} was returned to cash", YELLOW)
        if not h.players:                      # everybody left: the heist is cancelled right now
            h.cancelled, h.phase = True, "done"
            h.full.set()
            e = discord.Embed(color=YELLOW, title="השוד בוטל", description="כל השחקנים יצאו והכסף חזר למזומן.")
            return await interaction.response.edit_message(embed=e, view=None, attachments=[])
        self.show_join()
        await interaction.response.edit_message(embed=h.embed(), view=self)

    def show_loot(self):
        self.clear_items()
        b = discord.ui.Button(style=discord.ButtonStyle.primary, label="המגירות שלי", emoji="🔐")
        b.callback = self.reopen
        self.add_item(b)

    async def reopen(self, interaction):
        """The drawers message was dismissed or lost: send it again, with everything the player already opened."""
        h, uid = self.h, interaction.user.id
        say = lambda t: interaction.response.send_message(t, ephemeral=True)
        if uid not in h.players or not h.vault_open:
            return await say("אין לך מגירות בשוד הזה.")
        old = h.loot_views.get(uid)
        if old is None or old.done or uid in h.loot:
            return await say("כבר סיימת לפתוח את המגירות.")
        v = LootView(h, interaction.user, src=old)
        old.stop()
        h.loot_views[uid] = v
        await interaction.response.send_message(embed=v.embed(), view=v, ephemeral=True)
        v.message = await interaction.original_response()

    def show_mission(self):
        self.clear_items()
        b = discord.ui.Button(style=discord.ButtonStyle.primary, label="המשימה שלי", emoji="📩")
        b.callback = self.mission
        self.add_item(b)

    async def mission(self, interaction):
        h, uid = self.h, interaction.user.id
        p = h.players.get(uid)
        say = lambda t: interaction.response.send_message(t, ephemeral=True)
        if p is None:
            return await say("אינך חלק מהצוות של השוד הזה.")
        if h.phase != "mission":
            return await interaction.response.defer()
        if uid in h.opened:
            return await say("המשימה שלך כבר נשלחה אליך. חפש את ההודעה הפרטית שרק אתה רואה.")
        h.opened.add(uid)
        h.interactions[uid] = interaction
        v = MISSIONS[p["role"]](h, interaction.user, p["role"])
        await interaction.response.send_message(embed=v.embed(), view=v, ephemeral=True)
        v.start(interaction)
        bg(h.refresh())

class MissionView(discord.ui.View):
    """Personal (ephemeral) mission message. Subclasses: embed(), rebuild(), reroll(), help_text()."""
    label = "טעויות"

    def __init__(self, h, user, role):
        self.limit = HEIST_TIME[role]
        super().__init__(timeout=self.limit + 30)
        self.h, self.user, self.role = h, user, role
        self.done, self.mistakes, self.max_mistakes, self.skips, self.note = False, 0, 3, HEIST_SKIPS, ""
        self.deadline = time.time() + self.limit
        self.interaction = None

    def start(self, interaction):
        self.interaction = interaction
        bg(self.expire())

    async def expire(self):
        await asyncio.sleep(self.limit + 0.6)
        if not self.done:
            await self.time_up()

    async def time_up(self, interaction=None):
        if self.done:
            return
        self.done = True
        self.h.report(self.user.id, False)
        self.stop()
        e = discord.Embed(color=RED, title="הזמן נגמר", description="לא הספקתם לסיים את המשימה בזמן.\n-# ממתינים לשאר הצוות")
        try:
            if interaction is not None:
                await hz_edit(interaction, embed=e, view=None)
            elif self.interaction is not None:
                await self.interaction.edit_original_response(embed=e, view=None)
        except Exception as ex:
            print("Heist time_up edit failed:", repr(ex))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("זו לא המשימה שלך.", ephemeral=True)
            return False
        if self.done or self.h.phase == "done":
            if not interaction.response.is_done():
                await interaction.response.defer()
            return False
        if time.time() > self.deadline + 0.5:
            await self.time_up(interaction)
            return False
        return True

    def card(self, sub, body, extra=()):
        name, icon = HEIST_ROLES[self.role]
        text = f"-# {sub}\n{body}" + (f"\n\n> {self.note}" if self.note else "")
        e = discord.Embed(color=GOLD, title=f"{icon} {name}", description=text)
        e.add_field(name="זמן למשימה", value=f"<t:{int(self.deadline)}:R>")
        for n, v in extra:
            e.add_field(name=n, value=v)
        e.add_field(name=self.label, value=f"{self.mistakes} מתוך {self.max_mistakes}")
        e.add_field(name="התעלמויות", value=str(self.skips))
        return e

    def add_btn(self, label, cb, style=discord.ButtonStyle.secondary, emoji=None, row=0):
        b = discord.ui.Button(style=style, label=label, emoji=emoji, row=row)
        b.callback = cb
        self.add_item(b)

    def add_common(self, row):
        self.add_btn("הוראות", self.show_help, row=row)
        self.add_btn("התעלמות", self.do_skip, row=row)

    def can_skip(self):
        return True

    async def show_help(self, interaction):
        await interaction.response.send_message(self.help_text(), ephemeral=True)

    async def do_skip(self, interaction):
        if not self.can_skip():
            return await interaction.response.send_message("אי אפשר להתעלם בשלב הזה.", ephemeral=True)
        if self.skips <= 0:
            return await interaction.response.send_message("נגמרו ההתעלמויות שלך.", ephemeral=True)
        self.skips -= 1
        self.note = "התעלמת וקיבלת משימה חדשה."
        self.reroll()
        self.rebuild()
        await hz_edit(interaction, embed=self.embed(), view=self)

    async def end(self, interaction, ok, text):
        self.done = True
        self.h.report(self.user.id, ok)
        self.stop()
        e = discord.Embed(color=GREEN if ok else RED, title="המשימה הושלמה" if ok else "המשימה נכשלה",
                          description=f"{text}\n-# ממתינים לשאר הצוות, התוצאה תתפרסם בהודעה הראשית")
        await hz_edit(interaction, embed=e, view=None)

    async def mistake(self, interaction, text, fail_text):
        self.mistakes += 1
        if self.mistakes >= self.max_mistakes:
            return await self.end(interaction, False, fail_text)
        self.note = text
        await hz_edit(interaction, embed=self.embed(), view=self)

# ---------- hacker: crack the vault code (5 different digits 1-9, every guess gives a hint) ----------
class CodeModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title="ניסיון פריצה")
        self.v = view
        self.code = discord.ui.TextInput(label=f"קוד בן {HACK_LEN} ספרות (1 עד 9, בלי חזרות)", min_length=HACK_LEN,
                                         max_length=HACK_LEN, placeholder="לדוגמה 314")
        self.add_item(self.code)

    async def on_submit(self, interaction):
        await self.v.check(interaction, self.code.value.strip())

class HackerMission(MissionView):
    label = "ניסיונות"

    def __init__(self, h, user, role):
        super().__init__(h, user, role)
        self.max_mistakes = HACK_TRIES
        self.code, self.history = hack_new(), []
        self.rebuild()

    def rebuild(self):
        self.clear_items()
        self.add_btn("הזן קוד", self.enter, discord.ButtonStyle.success, "⌨️")
        self.add_common(1)

    def reroll(self):
        self.code, self.history, self.mistakes = hack_new(), [], 0

    def embed(self):
        body = (f"הכספת נעולה בקוד בן **{HACK_LEN} ספרות שונות**, כל ספרה בין 1 ל-9.\n"
                "אחרי כל ניסיון תראו כמה ספרות נכונות ובמקום הנכון, וכמה קיימות בקוד אבל במקום אחר.")
        if self.history:
            rows = [f"`{i}.` `{g}`   🟢 **{x}**   🟡 **{c}**" for i, (g, x, c) in enumerate(self.history, 1)]
            body += "\n\n" + "\n".join(rows)
        body += f"\n\n🟢 במקום הנכון   🟡 קיימת במקום אחר"
        return self.card("פריצה לכספת", body)

    def help_text(self):
        return ("צריך לנחש את הקוד של הכספת.\n"
                f"הקוד הוא {HACK_LEN} ספרות שונות מבין 1 עד 9, אף ספרה לא חוזרת.\n"
                "אחרי כל ניסיון תקבלו שני מספרים:\n"
                "🟢 כמה ספרות נכונות וגם במקום הנכון.\n"
                "🟡 כמה ספרות קיימות בקוד אבל לא במקום שניחשתם.\n"
                f"יש {HACK_TRIES} ניסיונות. התעלמות נותנת קוד חדש ומאפסת את הניסיונות.")

    async def enter(self, interaction):
        await interaction.response.send_modal(CodeModal(self))

    async def check(self, interaction, text):
        if self.done:
            return await interaction.response.defer()
        if time.time() > self.deadline + 0.5:
            return await self.time_up(interaction)
        if len(text) != HACK_LEN or any(ch not in HACK_DIGITS for ch in text) or len(set(text)) != HACK_LEN:
            self.note = f"הקוד חייב להיות {HACK_LEN} ספרות שונות בין 1 ל-9."
            return await hz_edit(interaction, embed=self.embed(), view=self)
        if text == self.code:
            return await self.end(interaction, True, f"הקוד {self.code} נפרץ והכספת נפתחה.")
        x, c = hack_score(self.code, text)
        self.history.append((text, x, c))
        await self.mistake(interaction, "", f"נגמרו הניסיונות והמערכת ננעלה. הקוד היה {self.code}.")

# ---------- bomber: 3 easy steps. place the charge, press the colors, run to the free door ----------
class BomberMission(MissionView):
    DOORS = 3

    def __init__(self, h, user, role):
        super().__init__(h, user, role)
        self.max_mistakes = 4
        self.step, self.fuse_end = "place", 0
        self.roll_wall()
        self.roll_colors()
        self.safe = random.randint(1, self.DOORS)
        self.rebuild()

    def roll_wall(self):
        self.wall = random.choice(HEIST_WALLS)

    def roll_colors(self):
        self.seq = random.sample(list(HEIST_COLORS), 3)
        self.pos = 0

    def can_skip(self):
        return self.step in ("place", "colors")

    def reroll(self):
        if self.step == "place":
            self.roll_wall()
        else:
            self.roll_colors()

    def embed(self):
        if self.step == "place":
            return self.card("שלב 1 מתוך 3, הנחת המטען",
                             f"הכספת נמצאת בקיר ה**{self.wall}**. לחצו על הקיר הזה כדי להניח שם את המטען.")
        if self.step == "colors":
            return self.card("שלב 2 מתוך 3, חיזוק המטען",
                             "לחצו על הצבעים לפי הסדר:\n\n# " + "  ".join(self.seq) +
                             f"\n\n{'▰' * self.pos}{'▱' * (3 - self.pos)}")
        blocked = [d for d in range(1, self.DOORS + 1) if d != self.safe]
        return self.card("שלב 3 מתוך 3, בריחה",
                         f"הפתיל דולק, ההתפוצצות <t:{int(self.fuse_end)}:R>.\n"
                         f"השוטרים חוסמים את דלת {blocked[0]} ואת דלת {blocked[1]}. רוצו לדלת השלישית.")

    def rebuild(self):
        self.clear_items()
        if self.step == "place":
            for w in HEIST_WALLS:
                self.add_btn(w, self.pick_wall(w))
        elif self.step == "colors":
            for c in HEIST_COLORS:
                self.add_btn("\u200e", self.pick_color(c), emoji=c)
        else:
            for n in range(1, self.DOORS + 1):
                self.add_btn(f"דלת {n}", self.door(n), discord.ButtonStyle.primary)
        if self.step != "run":
            self.add_common(1)

    def help_text(self):
        return ("המשימה היא לפוצץ את הכספת ולברוח, בשלושה שלבים קלים.\n"
                "1. מניחים את המטען בקיר שבו נמצאת הכספת.\n"
                "2. לוחצים על הצבעים לפי הסדר שמוצג.\n"
                f"3. הפתיל נשרף ({HEIST_FUSE} שניות), בורחים מהדלת היחידה שהשוטרים לא חוסמים.\n"
                "ארבע טעויות והמטען מתפוצץ מוקדם. התעלמות מחליפה את השלב הנוכחי.")

    def pick_wall(self, wall):
        async def cb(interaction):
            if wall == self.wall:
                self.step, self.note = "colors", "המטען הונח במקום הנכון."
                self.rebuild()
                return await hz_edit(interaction, embed=self.embed(), view=self)
            await self.mistake(interaction, "זה לא הקיר הנכון.", "המטען הונח במקום הלא נכון והתפוצץ עליכם.")
        return cb

    def pick_color(self, color):
        async def cb(interaction):
            if color == self.seq[self.pos]:
                self.pos += 1
                self.note = ""
                if self.pos >= 3:
                    self.step, self.note, self.fuse_end = "run", "המטען מחוזק והפתיל דולק!", time.time() + HEIST_FUSE
                    self.rebuild()
                return await hz_edit(interaction, embed=self.embed(), view=self)
            self.pos = 0
            await self.mistake(interaction, "צבע לא נכון, מתחילים את הרצף מחדש.", "החיזוק נכשל והמטען התפוצץ עליכם.")
        return cb

    def door(self, n):
        async def cb(interaction):
            if time.time() > self.fuse_end + HEIST_GRACE:
                return await self.end(interaction, False, "הפתיל נשרף והמטען התפוצץ לפני שיצאתם.")
            if n != self.safe:
                return await self.end(interaction, False, f"יצאתם מדלת {n} ונתפסתם על ידי השוטרים.")
            await self.end(interaction, True, "יצאתם בזמן והכספות התפוצצו. כשכל הצוות יסיים, תקבלו את המגירות.")
        return cb

# ---------- lookout: 3 rounds, the board stays still. press the police, never the civilians ----------
class LookoutMission(MissionView):
    label = "אזעקות"
    ROUNDS, SIZE = 3, 4
    COPS = (3, 4, 5)
    CIVS = (2, 3, 3)
    ICONS = {"cop": "👮", "civ": "🧑‍💼", "empty": "⬛"}
    SEC_PER_COP = 5

    def __init__(self, h, user, role):
        super().__init__(h, user, role)
        self.max_mistakes = 3
        self.round = 1
        self.setup_round()
        self.rebuild()

    def setup_round(self):
        self.cops, self.civs = self.COPS[self.round - 1], self.CIVS[self.round - 1]
        self.neut = 0
        self.round_end = time.time() + self.SEC_PER_COP * self.cops + 6
        self.radio = random.choice(HEIST_RADIO)
        self.new_board()

    def new_board(self):
        cells = ["cop"] * self.cops + ["civ"] * self.civs
        cells += ["empty"] * (self.SIZE ** 2 - len(cells))
        random.shuffle(cells)
        self.cells = cells

    def reroll(self):
        """'התעלמות' moves straight to the next round (on the last round it gives a new board)."""
        if self.round < self.ROUNDS:
            self.round += 1
            self.setup_round()
            self.note = f"דילגתם לסבב {self.round}."
        else:
            self.setup_round()
            self.note = "זה הסבב האחרון, קיבלתם לוח חדש."

    def rebuild(self):
        self.clear_items()
        for i, kind in enumerate(self.cells):
            self.add_btn("\u200e", self.hit(i), emoji=self.ICONS[kind], row=i // self.SIZE)
        self.add_common(self.SIZE)

    def embed(self):
        return self.card(f"סבב {self.round} מתוך {self.ROUNDS}",
                         f"*{self.radio}*\n\nלחצו על כל השוטרים 👮 כדי לנטרל אותם. אל תלחצו על אזרחים 🧑‍💼.",
                         [("זמן לסבב", f"<t:{int(self.round_end)}:R>"), ("שוטרים", f"{self.neut} מתוך {self.cops}")])

    def help_text(self):
        return ("המשימה היא לנטרל את השוטרים בלי להעיר את הבנק.\n"
                "לוחצים על כל שוטר (👮). הלוח לא זז.\n"
                "לחיצה על אזרח (🧑‍💼) היא אזעקה והסבב מתחיל מחדש. שלוש אזעקות והמשימה נכשלת.\n"
                f"יש {self.ROUNDS} סבבים. התעלמות מדלגת ישר לסבב הבא.")

    def hit(self, i):
        async def cb(interaction):
            if time.time() > self.round_end + 1.0:
                self.setup_round()
                self.rebuild()
                return await self.mistake(interaction, "הזמן נגמר והשוטרים התריעו. סבב חדש.", "השוטרים הקיפו את הבנק.")
            kind = self.cells[i]
            if kind == "civ":
                self.neut = 0
                self.new_board()
                self.rebuild()
                return await self.mistake(interaction, "לחצתם על אזרח והאזעקה הופעלה. הסבב מתחיל מחדש.", "פגעתם בעוד אזרח והמשטרה הוזעקה.")
            if kind == "empty":
                self.note = "אין שם כלום."
            else:
                self.cells[i] = "empty"
                self.neut += 1
                self.note = "שוטר מנוטרל."
                if self.neut >= self.cops:
                    if self.round >= self.ROUNDS:
                        return await self.end(interaction, True, "כל השוטרים מנוטרלים והבנק שקט לגמרי.")
                    self.round += 1
                    self.setup_round()
                    self.note = "הסבב הושלם, ממשיכים."
            self.rebuild()
            await hz_edit(interaction, embed=self.embed(), view=self)
        return cb

# ---------- bodyguard: protect the crew. shoot the police and the undercover agents, never the civilians ----------
class BodyguardMission(LookoutMission):
    label = "אזרחים שנפגעו"
    COPS = (2, 3, 3)
    AGENTS = (1, 1, 2)
    CIVS = (2, 3, 4)
    ICONS = {"cop": "👮", "agent": "🕵️", "civ": "🧑‍💼", "empty": "⬛"}
    SEC_PER_COP = 4

    def setup_round(self):
        self.agents = self.AGENTS[self.round - 1]
        self.cops = self.COPS[self.round - 1] + self.agents        # all the targets of the round
        self.civs = self.CIVS[self.round - 1]
        self.neut = 0
        self.round_end = time.time() + self.SEC_PER_COP * self.cops + 6
        self.radio = random.choice(HEIST_RADIO)
        self.new_board()

    def new_board(self):
        cells = ["cop"] * (self.cops - self.agents) + ["agent"] * self.agents + ["civ"] * self.civs
        cells += ["empty"] * (self.SIZE ** 2 - len(cells))
        random.shuffle(cells)
        self.cells = cells

    def embed(self):
        return self.card(f"סבב {self.round} מתוך {self.ROUNDS}",
                         f"*{self.radio}*\n\nאתם השומרי ראש של הצוות. ירו בשוטרים 👮 ובסוכנים החשאיים 🕵️ לפני שהם מגיעים לצוות. אל תירו באזרחים 🧑‍💼.",
                         [("זמן לסבב", f"<t:{int(self.round_end)}:R>"), ("מטרות", f"{self.neut} מתוך {self.cops}")])

    def help_text(self):
        return ("המשימה היא להגן על הצוות.\n"
                "לוחצים על כל שוטר (👮) וכל סוכן חשאי (🕵️) כדי לחסל אותם. הלוח לא זז.\n"
                "לחיצה על אזרח (🧑‍💼) מתחילה את הסבב מחדש, ושלוש פגיעות באזרחים מפילות את המשימה.\n"
                f"יש {self.ROUNDS} סבבים. התעלמות מדלגת ישר לסבב הבא.")

MISSIONS = {"lookout": LookoutMission, "hacker": HackerMission, "bomber": BomberMission, "bodyguard": BodyguardMission}

# ---------- the safes: after the explosion every player opens 2 drawers (3 of 9 are empty) ----------
def loot_value(amount):
    return int(amount)

def loot_short(n):
    return f"{n / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"

class LootView(discord.ui.View):
    """Personal (ephemeral) safe: a 3x3 wall of locked drawers. Each drawer holds jewels / dollars / cash, or nothing."""

    def __init__(self, h, user, src=None):
        super().__init__(timeout=max(5, h.loot_deadline - time.time()))
        self.h, self.user = h, user
        self.message = None
        self.btns = []
        self.opened = set()
        if src is None:
            self.drawers = [random.choice(LOOT_ITEMS) for _ in range(LOOT_DRAWERS - LOOT_EMPTY)] + [None] * LOOT_EMPTY
            random.shuffle(self.drawers)
            self.picks, self.got, self.items, self.done = 0, 0, [], False
        else:                                   # the same drawers again (the player lost his message): keep what he opened
            self.drawers, self.picks, self.got, self.items, self.done = src.drawers, src.picks, src.got, list(src.items), False
        for i in range(LOOT_DRAWERS):
            b = discord.ui.Button(style=discord.ButtonStyle.secondary, label=f"{i + 1}", emoji="🔒", row=i // 3)
            b.callback = self.opener(i)
            self.btns.append(b)
            self.add_item(b)
        for i in (src.opened if src else ()):
            self.show_open(i)

    def show_open(self, i):
        item, b = self.drawers[i], self.btns[i]
        self.opened.add(i)
        b.disabled = True
        if item is None:
            b.emoji, b.label, b.style = "🕸️", "ריק", discord.ButtonStyle.danger
        else:
            b.emoji, b.label, b.style = item[0], loot_short(loot_value(item[2])), discord.ButtonStyle.success

    def embed(self, final=False):
        left = HEIST_LOOT_PICKS - self.picks
        if final:
            if self.items:
                lines = "\n".join(f"{ic} {nm}  ·  **{fmt(v)}** {cur()}" for ic, nm, v in self.items)
            else:
                lines = "יצאתם בידיים ריקות."
            e = discord.Embed(color=GREEN if self.got else RED, title="🔐 השלל שלכם", description=(
                f"{lines}\n\n**סה\"כ:** {fmt(self.got)} {cur()}\n"
                f"-# השלל נוסף ליתרה שלכם כשהשוד מסתיים. ממתינים לשאר הצוות."))
            return e
        e = discord.Embed(color=GOLD, title="💥 הכספות התפוצצו!", description=(
            f"הדלת נפתחה והמגירות מולכם. פתחו **{left}** מגירות ותגנבו מה שיש בהן.\n"
            f"ב-{LOOT_EMPTY} מתוך {LOOT_DRAWERS} מגירות אין כלום, אז תבחרו חכם.\n"
            f"הזמן נגמר <t:{int(self.h.loot_deadline)}:R>. אם ההודעה נעלמה, לחצו על הכפתור בהודעה הראשית כדי לקבל אותה שוב.\n"
            + (f"\nעד עכשיו: **{fmt(self.got)}** {cur()}" if self.picks else "")))
        e.set_footer(text="🔒 נעול   ·   🕸️ ריק   ·   💎👑💍⌚💵💰🪙 שלל")
        return e

    def opener(self, i):
        async def cb(interaction):
            if self.done or self.btns[i].disabled:
                return await interaction.response.defer()
            item = self.drawers[i]
            if item is not None:
                ic, nm, amount = item
                val = loot_value(amount)
                self.got += val
                self.items.append((ic, nm, val))
            self.show_open(i)
            self.picks += 1
            if self.picks >= HEIST_LOOT_PICKS:
                self.finish()
                for x in self.btns:
                    x.disabled = True
                self.stop()
                return await interaction.response.edit_message(embed=self.embed(final=True), view=self)
            await interaction.response.edit_message(embed=self.embed(), view=self)
        return cb

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("אלה לא המגירות שלך.", ephemeral=True)
            return False
        return True

    def finish(self):
        if self.done:
            return
        self.done = True
        uid = self.user.id
        self.h.loot[uid] = self.got
        self.h.loot_items[uid] = list(self.items)
        self.h.loot_pending.discard(uid)
        if not self.h.loot_pending:
            self.h.loot_done.set()

    async def on_timeout(self):
        if self.done:
            return
        self.finish()
        for x in self.btns:
            x.disabled = True
        if self.message:
            try:
                await self.message.edit(embed=self.embed(final=True), view=self)
            except Exception:
                pass

async def vault_blown(h):
    """The bomber blew the safes: every player gets a small private message with his drawers, at the same moment."""
    if h.vault_open:
        return
    h.vault_open = True
    h.loot_deadline = time.time() + HEIST_LOOT_WAIT
    targets = [(uid, p) for uid, p in h.players.items() if uid in h.interactions]
    h.loot_pending = {uid for uid, _ in targets}
    for uid, p in targets:
        v = LootView(h, p["user"])
        h.loot_views[uid] = v
        try:
            v.message = await h.interactions[uid].followup.send(
                content="-# 💥 כל הצוות הצליח והכספות התפוצצו! יש לכם רגע לגנוב מהמגירות.",
                embed=v.embed(), view=v, ephemeral=True, wait=True)
        except Exception as ex:
            print("Heist loot send failed:", repr(ex))
            h.loot_pending.discard(uid)
    if not h.loot_pending:
        h.loot_done.set()
    else:
        h.view.show_loot()
        await h.refresh()

async def finish_heist(h):
    c = cur()
    h.phase = "done"
    for uid in h.players:
        h.results.setdefault(uid, False)
    outcome = {}
    for r in HEIST_ROLE_ORDER:
        who = h.holders(r)
        if who:
            outcome[r] = all(h.results[u] for u in who)
        elif r in HEIST_CORE:                 # a core role nobody took may succeed by itself
            outcome[r] = any(random.random() < HEIST_AUTO for _ in range(luck_attempts(0)))
    ok, total = sum(outcome.values()), len(outcome)
    n = len(h.players)
    lines, log_lines = [], []
    for uid, p in h.players.items():
        if ok == total:
            win = int(h.stake * HEIST_MULT[n])
            win += multi_extra("heist", win - h.stake)
        elif ok == total - 1 and h.results.get(uid):
            win = int(h.stake * HEIST_PART)      # only a player whose OWN mission worked gets part of the fee back
        else:
            win = 0                              # failing on purpose (or timing out) never gives anything back
        loot = h.loot.get(uid, 0)
        kept = loot                              # the loot is only handed out when the whole crew succeeded, so it is always paid
        win += kept
        DB.get("pending", {}).pop(p["token"], None)
        BUSY.discard(uid)
        user_data(uid)["cash"] += win
        net = win - h.stake
        loot_txt = ""
        if loot:
            icons = "".join(ic for ic, _, _ in h.loot_items.get(uid, []))
            loot_txt = f"  {icons} שלל {fmt(loot)}" + ("" if kept else " (אבד)")
        if net > 0:
            lines.append(f"{p['user'].mention}  +{fmt(net)} {c}{loot_txt}")
        elif win > 0:
            lines.append(f"{p['user'].mention}  קיבל בחזרה {fmt(win)} {c}{loot_txt}")
        else:
            lines.append(f"{p['user'].mention}  -{fmt(h.stake)} {c}{loot_txt}")
        role = HEIST_ROLES[p["role"]][0] if p["role"] else "-"
        log_lines.append((uid, p, net, role, kept))
    save()
    crew = []
    for uid, p, net, role, kept in log_lines:
        crew.append(f"{p['user'].name} | {role} | {'completed' if h.results.get(uid) else 'failed'}"
                    + (f" | loot {fmt(kept)}" if kept else ""))
    verdict = "Full success" if ok == total else "Partial success" if ok == total - 1 else "Failed"
    for uid, p, net, role, kept in log_lines:
        log_game(p["user"], "heist", h.stake, net,
                 detail=f"{verdict} | missions {ok}/{total} | crew of {n} | entry {fmt(h.stake)}\n```\n" + "\n".join(crew) + "\n```")
    if ok == total:
        title, color, kind, text = "השוד הצליח", GOLD, "win", "כל המשימות הושלמו והצוות יצא עם הכסף."
    elif ok == total - 1:
        title, color, kind, text = "הצלחה חלקית", HEIST_ORANGE, "vault", "חסרה משימה אחת. הצוות ברח עם חלק מההימור."
    else:
        title, color, kind, text = "השוד נכשל", RED, "fail", "המשימות נכשלו והמשטרה תפסה את הצוות."
    e = discord.Embed(color=color, title=title, description=text)
    for r in outcome:
        name, icon = HEIST_ROLES[r]
        names = ", ".join(h.players[u]["user"].mention for u in h.holders(r)) or "מחליף אוטומטי"
        e.add_field(name=f"{icon} {name}", value=f"{names}\n{'הצליח' if outcome[r] else 'נכשל'}")
    e.add_field(name="תוצאות", value="\n".join(lines), inline=False)
    kw = {}
    try:
        png = heist_art(kind)
        e.set_image(url="attachment://heist_result.png")
        kw["attachments"] = [discord.File(io.BytesIO(png), "heist_result.png")]
    except Exception as ex:
        print("Heist art failed:", repr(ex))
    try:
        await h.message.edit(embed=e, view=None, **kw)
    except Exception:
        e.set_image(url=None)
        await h.channel.send(embed=e, allowed_mentions=discord.AllowedMentions.none())

async def heist_abort(h, title="הזמן אזל", text="השוד בוטל והכסף חזר למזומן.", to="cash"):
    """Something went wrong: nobody loses anything. Players who were not paid yet get the entry fee back to their cash."""
    h.phase = "done"
    names = []
    for uid, p in h.players.items():
        if DB.get("pending", {}).pop(p["token"], None) is not None:
            user_data(uid)[to] += h.stake
            names.append(p["user"].mention)
            log_money(p["user"], "HEIST | CANCELLED", f"Heist cancelled, entry fee of {fmt(h.stake)} {cur()} was returned to {to}", YELLOW)
        BUSY.discard(uid)
    save()
    e = discord.Embed(color=YELLOW, title=title, description=(
        text
        + (f"\n\n{fmt(h.stake)} {cur()} הוחזרו ל: " + ", ".join(names) if names else "")))
    try:
        await h.message.edit(embed=e, view=None, attachments=[])
    except Exception:
        try:
            await h.channel.send(embed=e, allowed_mentions=discord.AllowedMentions.none())
        except Exception as ex2:
            print("Heist abort message failed:", repr(ex2))

async def run_heist(h):
    cid = h.channel.id
    view = h.view
    try:
        try:
            await asyncio.wait_for(h.full.wait(), max(0, h.end - time.time()))
        except asyncio.TimeoutError:
            pass
        if h.cancelled:
            return
        if len(h.players) < HEIST_MIN:
            heist_unmark(h.creator)                  # the creator may open a new heist today
            return await heist_abort(h, "השוד בוטל",
                                     f"לא הצטרפו מספיק שחקנים בזמן (נדרשים לפחות {HEIST_MIN}). הכסף חזר לבנק, בלי הפסד.", to="bank")
        h.phase, h.end = "roles", int(time.time()) + HEIST_ROLE_WAIT
        view.show_roles()
        await h.refresh()
        try:
            await asyncio.wait_for(h.roles_set.wait(), HEIST_ROLE_WAIT)
        except asyncio.TimeoutError:
            pass
        slots = lambda rs: [r for r in rs for _ in range(HEIST_ROLE_CAP.get(r, 1) - len(h.holders(r)))]
        free = slots(HEIST_CORE)
        random.shuffle(free)
        free += slots(r for r in HEIST_ROLE_ORDER if r not in HEIST_CORE)       # core roles are given out first
        free.reverse()
        for p in h.players.values():
            if p["role"] is None:
                p["role"] = free.pop()
        h.phase, h.end = "mission", int(time.time()) + HEIST_OPEN_WAIT      # whoever did not choose in time got a free role
        view.show_mission()
        await h.refresh()
        try:
            await asyncio.wait_for(h.all_done.wait(), HEIST_OPEN_WAIT)
        except asyncio.TimeoutError:
            for uid in h.players:           # nobody opened it in time: that mission failed
                if uid not in h.opened:
                    h.report(uid, False)
        try:
            await asyncio.wait_for(h.all_done.wait(), max(HEIST_TIME.values()) + 5)
        except asyncio.TimeoutError:
            pass
        if h.vault_task is not None:            # the drawers were sent: wait until everybody opened them
            await h.vault_task
        if h.vault_open and h.loot_pending:
            try:
                await asyncio.wait_for(h.loot_done.wait(), HEIST_LOOT_WAIT + 3)
            except asyncio.TimeoutError:
                pass
        await finish_heist(h)
    except Exception as ex:
        print("Heist failed:", repr(ex))
        await heist_abort(h)
    finally:
        HEISTS.pop(cid, None)

@bot.command(name="heist", usage="heist [2-5]")
async def heist(ctx, size: str = None):
    crew = HEIST_DEFAULT
    if size is not None:
        if not size.isdigit() or not HEIST_MIN <= int(size) <= HEIST_MAX:
            return await reply(ctx, f"Usage: `$heist [{HEIST_MIN}-{HEIST_MAX}]` (the number of players)", RED)
        crew = int(size)
    if ctx.channel.id in HEISTS:
        return await reply(ctx, "יש כבר שוד פתוח בערוץ הזה. לחצו על כניסה למשחק כדי להצטרף אליו.", RED)
    if heist_used_today(ctx.author.id):
        return await reply(ctx, "כבר יצרת שוד היום. אפשר ליצור שוד חדש מחר אחרי 00:00 (אפשר עדיין להצטרף לשוד של מישהו אחר).", RED)
    if user_data(ctx.author.id)["cash"] < HEIST_FEE:
        return await reply(ctx, f"שוד עולה {fmt(HEIST_FEE)} {cur()} לכל שחקן (הוצאות). אין לך מספיק כסף במזומן.", RED)
    bet = await take_bet(ctx, str(HEIST_FEE), "heist", track=True)
    if not bet:
        return
    heist_mark(ctx.author.id)
    h = Heist(ctx.channel, bet, crew)
    h.token = str(ctx.message.id)
    h.creator = ctx.author.id
    h.add_player(ctx.author, h.token)         # the creator is in; he chooses his role with the buttons like everybody else
    h.view = HeistView(h)
    HEISTS[ctx.channel.id] = h
    kw = {}
    try:
        kw["file"] = discord.File(io.BytesIO(heist_art("vault")), "heist.png")
        h.art = True
    except Exception as ex:
        print("Heist art failed:", repr(ex))
    try:
        h.message = await ctx.reply(embed=h.embed(), view=h.view, mention_author=False, **kw)
    except Exception:
        HEISTS.pop(ctx.channel.id, None)
        heist_unmark(ctx.author.id)
        cancel_game(ctx.author, h.token, bet)
        raise
    bg(run_heist(h))
