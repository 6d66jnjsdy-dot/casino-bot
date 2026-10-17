import discord, asyncio, io
from core import *
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ================= SHOP =================

# ---------- Shop image renderer ----------
# ---- אם יש לך פונט משלך (למשל ב-assets), שים אותו ראשון ברשימה ----
SHOP_FONT_BOLD = ["assets/font_bold.ttf", "arialbd.ttf", "Arial Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"]
SHOP_FONT_REG = ["assets/font.ttf", "arial.ttf", "Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf"]

SHOP_GOLD = (221, 201, 163)
SHOP_PALETTE = [(205, 127, 50), (80, 200, 220), (160, 120, 255),
           (255, 170, 60), (255, 90, 120), (255, 215, 90)]
SHOP_ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]


def _shop_font(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _shop_short(n):
    if n >= 1_000_000_000:
        v = n / 1_000_000_000
        return f"{v:g}B"
    if n >= 1_000_000:
        v = n / 1_000_000
        return f"{v:g}M"
    if n >= 1_000:
        return f"{n / 1_000:g}K"
    return str(n)


def _shop_gradient(w, h, top, bottom):
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(w):
            px[x, y] = c
    return img


def _shop_center(d, cx, y, text, font, fill):
    w = d.textlength(text, font=font)
    d.text((cx - w / 2, y), text, font=font, fill=fill)


def render_shop_image(items, title="AMRAM CASINO", subtitle="ROLE SHOP", colors=None, owned=None):
    """items: [(name, emoji, role_id, price)]  colors: [(r,g,b)] לפי הסדר (אופציונלי)
    owned: set של role_id שהמשתמש כבר קנה (אופציונלי)"""
    S = 2  # supersampling לחדות
    cols = 2
    rows = (len(items) + cols - 1) // cols
    W, pad, gap = 1000, 48, 26
    head_h = 190
    card_w = (W - pad * 2 - gap * (cols - 1)) // cols
    card_h = 170
    foot_h = 80
    H = head_h + rows * card_h + (rows - 1) * gap + foot_h + pad

    W, H, pad, gap, card_w, card_h, head_h, foot_h = [v * S for v in (W, H, pad, gap, card_w, card_h, head_h, foot_h)]

    bg = _shop_gradient(W, H, (22, 18, 28), (10, 9, 14)).convert("RGBA")

    # זוהר רך בראש התמונה
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((W * 0.2, -H * 0.18, W * 0.8, H * 0.16), fill=SHOP_GOLD + (70,))
    glow = glow.filter(ImageFilter.GaussianBlur(90 * S))
    bg = Image.alpha_composite(bg, glow)

    d = ImageDraw.Draw(bg)
    f_title = _shop_font(SHOP_FONT_BOLD, 64 * S)
    f_sub = _shop_font(SHOP_FONT_BOLD, 22 * S)
    f_name = _shop_font(SHOP_FONT_BOLD, 34 * S)
    f_price = _shop_font(SHOP_FONT_BOLD, 40 * S)
    f_small = _shop_font(SHOP_FONT_REG, 20 * S)
    f_num = _shop_font(SHOP_FONT_BOLD, 28 * S)

    # מסגרת חיצונית דקה
    d.rounded_rectangle((14 * S, 14 * S, W - 14 * S, H - 14 * S), radius=28 * S, outline=SHOP_GOLD + (90,), width=2 * S)

    # כותרת
    _shop_center(d, W // 2, 46 * S, title, f_title, SHOP_GOLD)
    sub_y = 128 * S
    sub_w = d.textlength(subtitle, font=f_sub)
    d.text((W / 2 - sub_w / 2, sub_y), subtitle, font=f_sub, fill=(150, 142, 130))
    ly = sub_y + 13 * S
    d.line((pad + 40 * S, ly, W / 2 - sub_w / 2 - 24 * S, ly), fill=SHOP_GOLD + (110,), width=2 * S)
    d.line((W / 2 + sub_w / 2 + 24 * S, ly, W - pad - 40 * S, ly), fill=SHOP_GOLD + (110,), width=2 * S)

    # כרטיסים
    for i, (name, _emoji, rid, price) in enumerate(items):
        r, c = divmod(i, cols)
        x0 = pad + c * (card_w + gap)
        y0 = head_h + r * (card_h + gap)
        x1, y1 = x0 + card_w, y0 + card_h
        acc = (colors[i] if colors and i < len(colors) and colors[i] else SHOP_PALETTE[i % len(SHOP_PALETTE)])

        # צל
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + 8 * S, x1, y1 + 8 * S), radius=24 * S, fill=(0, 0, 0, 120))
        bg = Image.alpha_composite(bg, sh.filter(ImageFilter.GaussianBlur(14 * S)))
        d = ImageDraw.Draw(bg)

        # גוף הכרטיס
        d.rounded_rectangle((x0, y0, x1, y1), radius=24 * S, fill=(30, 27, 38, 255), outline=(255, 255, 255, 22), width=S)
        # פס צבע בצד
        bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(bar).rounded_rectangle((x0, y0, x0 + 14 * S, y1), radius=24 * S, fill=acc + (255,))
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).rounded_rectangle((x0, y0, x1, y1), radius=24 * S, fill=255)
        clip = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        clip.paste(bar, (0, 0), mask)
        # חותכים את הפס שיהיה צר
        strip = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        strip.paste(clip.crop((x0, y0, x0 + 12 * S, y1)), (x0, y0))
        bg = Image.alpha_composite(bg, strip)
        d = ImageDraw.Draw(bg)

        # תג דרגה (עיגול עם מספר רומי)
        cx, cy, rad = x0 + 70 * S, y0 + card_h // 2, 34 * S
        halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(halo).ellipse((cx - rad - 8 * S, cy - rad - 8 * S, cx + rad + 8 * S, cy + rad + 8 * S), fill=acc + (70,))
        bg = Image.alpha_composite(bg, halo.filter(ImageFilter.GaussianBlur(10 * S)))
        d = ImageDraw.Draw(bg)
        d.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=(20, 18, 26, 255), outline=acc + (255,), width=3 * S)
        rn = SHOP_ROMAN[i % len(SHOP_ROMAN)]
        rw = d.textlength(rn, font=f_num)
        d.text((cx - rw / 2, cy - 17 * S), rn, font=f_num, fill=acc)

        # שם + מחיר
        tx = x0 + 132 * S
        d.text((tx, y0 + 34 * S), name.replace("Casino ", ""), font=f_name, fill=(245, 240, 230))
        d.text((tx, y0 + 76 * S), "CASINO", font=f_small, fill=(130, 124, 116))
        d.text((tx, y0 + 108 * S), _shop_short(price), font=f_price, fill=SHOP_GOLD)
        pw = d.textlength(_shop_short(price), font=f_price)
        d.text((tx + pw + 12 * S, y0 + 124 * S), "coins", font=f_small, fill=(130, 124, 116))

        # תג "OWNED"
        if owned and rid in owned:
            d.rounded_rectangle((x1 - 130 * S, y0 + 22 * S, x1 - 22 * S, y0 + 56 * S), radius=14 * S, fill=acc + (255,))
            _shop_center(d, x1 - 76 * S, y0 + 28 * S, "OWNED", f_small, (15, 14, 20))

    # פוטר
    _shop_center(d, W // 2, H - pad - 34 * S, "Paid from your bank  •  use $dep to deposit", f_small, (130, 124, 116))

    out = bg.convert("RGB").resize((W // S, H // S), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf

# ---------- Shop logic ----------
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
            render_shop_image, SHOP_ITEMS, SHOP_TITLE, SHOP_SUBTITLE, colors, owned)
        await ctx.send(file=discord.File(buf, "shop.png"), view=ShopView())
    except Exception as ex:
        await ctx.send(f"Shop error: `{type(ex).__name__}: {ex}`"[:1900])
