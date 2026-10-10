import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= SCRATCH CARDS ($sc) =================
try:
    from scratch_art import ART as SC_ART
except Exception as _e:
    print("scratch_art.py not loaded, scratch cards disabled:", repr(_e))
    SC_ART = {}

SC_WIDTH = 560
SC_PAY_TO = "bank"

# the order here is the order of the menu and of the kiosk picture
SC_CARDS = {
    "club": {
        "name": "הקלף", "emoji": "♣️", "min": 50_000_000, "total": 50, "cols": 4,
        "wins": {1.5: 5, 2: 5, 7: 2, 60: 1},
        "orig": (1289, 1580), "spots": [(640, 640, 120), (440, 930, 120), (840, 930, 120), (640, 1140, 85)],
    },
    "casino": {
        "name": "קזינו גלגל הרולטה", "emoji": "🎰", "min": 25_000_000, "total": 200, "cols": 4,
        "wins": {3.5: 5, 1.3: 50, 5: 10, 45: 1, 1.1: 20},
        "orig": (1289, 1542),
        "spots": [(x, y, 67) for y in (1138, 1340) for x in (1068, 898, 733, 567, 396, 228)],
    },
    "safe": {
        "name": "כספת", "emoji": "🔐", "min": 5_000_000, "total": 350, "cols": 3,
        "wins": {1.2: 136, 1.5: 50, 2: 25, 30: 1},
        "orig": (1289, 1526),
        "spots": [(x, y, 68) for y in (1035, 1340) for x in (935, 665, 395)],
    },
    "queen": {
        "name": "מלכת הלבבות", "emoji": "♥️", "min": 2_500_000, "total": 350, "cols": 5,
        "wins": {2.3: 50, 1.7: 25, 1.5: 90, 0.5: 25, 25: 1},
        "orig": (800, 950), "spots": [(412, 612, 102), (622, 612, 102), (195, 835, 102), (405, 835, 102), (620, 835, 102)],
    },
}
SC_EN = {"queen": "Queen of Hearts", "casino": "Casino Roulette Wheel", "safe": "Safe", "club": "Club"}
SC_DECOYS = [0.3, 0.5, 0.8, 1.1, 1.3, 1.5, 1.7, 2, 2.3, 3, 3.5, 4, 5, 7, 10, 15, 25]

def sc_short(n):
    return f"{n / 1_000_000:g}M"

def sc_stock(key):
    c = SC_CARDS[key]
    store = DB.setdefault("sc_stock", {})
    st = store.get(key)
    if st is None:
        pool = [m for m, n in c["wins"].items() for _ in range(n)]
        pool += [0] * (c["total"] - len(pool))
        random.shuffle(pool)
        st = store[key] = {"left": pool, "sold": 0}
        save()
    return st

def return_card(key, mult):
    st, c = DB.get("sc_stock", {}).get(key), SC_CARDS.get(key)
    if not st or not c or len(st["left"]) >= c["total"]:
        return
    st["left"].insert(random.randint(0, len(st["left"])), mult)
    st["sold"] = max(0, st["sold"] - 1)

def sc_labels(n, mult):
    decoys = [d for d in SC_DECOYS if d != mult]
    out, counts = ([mult] * 3 if mult else []), {}
    while len(out) < n:
        d = random.choice(decoys)
        if counts.get(d, 0) < 2:
            counts[d] = counts.get(d, 0) + 1
            out.append(d)
    random.shuffle(out)
    return out

# --- render start ---
@lru_cache(maxsize=None)
def sc_base(key):
    c = SC_CARDS[key]
    im = Image.open(io.BytesIO(base64.b64decode(SC_ART[key]))).convert("RGB")
    return im.resize((SC_WIDTH, round(SC_WIDTH * c["orig"][1] / c["orig"][0])), Image.LANCZOS)

@lru_cache(maxsize=None)
def sc_disc(r):
    S = r * 2 + 2
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i in range(r, 0, -1):
        g = int(125 + 105 * (1 - i / r) ** 0.8)
        d.ellipse([r + 1 - i, r + 1 - i, r + 1 + i, r + 1 + i], fill=(g, g, g + 8, 255))
    rng = random.Random(r)
    for _ in range(16):
        a, b = rng.uniform(-0.6, 0.6) * r, rng.uniform(-0.6, 0.6) * r
        L = rng.uniform(0.15, 0.4) * r
        d.line([(r + a, r + b), (r + a + L, r + b - L * 0.5)], fill=(245, 245, 250, 150), width=2)
    d.ellipse([1, 1, S - 2, S - 2], outline=(70, 70, 80, 255), width=3)
    return im

def sc_render(key, labels, revealed, final=False, mult=0):
    c = SC_CARDS[key]
    base = sc_base(key).copy().convert("RGBA")
    k = base.width / c["orig"][0]
    d = ImageDraw.Draw(base)
    for i, (x, y, r) in enumerate(c["spots"]):
        cx, cy, rr = int(x * k), int(y * k), int(r * k)
        if i in revealed:
            win = bool(final and mult and labels[i] == mult)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(18, 18, 26, 235),
                      outline=(90, 255, 120, 255) if win else (235, 190, 60, 255), width=5 if win else 3)
            text = f"x{labels[i]:g}"
            fs = int(rr * (0.7 if len(text) <= 3 else 0.55))
            d.text((cx, cy), text, font=get_font(fs), anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0, 255),
                   fill=(90, 255, 120, 255) if win else (255, 255, 255, 255))
        else:
            base.alpha_composite(sc_disc(rr), (cx - rr - 1, cy - rr - 1))
            d.text((cx, cy), str(i + 1), font=get_font(int(rr * 0.9)), fill=(60, 60, 72, 255), anchor="mm")
    buf = io.BytesIO()
    base.convert("RGB").save(buf, "JPEG", quality=88)
    buf.seek(0)
    return buf

def he(text):
    """Hebrew for PIL: reversed only when this Pillow has no RTL support (raqm)."""
    return text if features.check("raqm") else text[::-1]

SC_BANNER = {"key": None, "data": None}
_banner_lock = asyncio.Lock()

def sc_key():
    return tuple(len(sc_stock(k)["left"]) for k in SC_CARDS)

def sc_banner_build(key):
    if SC_BANNER["key"] != key:
        data = sc_banner_render()
        SC_BANNER["key"], SC_BANNER["data"] = key, data
    return SC_BANNER["data"]

async def refresh_banner():
    """Draws the menu picture in the background, so $sc never waits for it."""
    if not SC_ART:
        return
    try:
        async with _banner_lock:
            key = sc_key()
            if SC_BANNER["key"] != key:
                for k in SC_CARDS:
                    await asyncio.to_thread(sc_base, k)
                await asyncio.to_thread(sc_banner_build, key)
    except Exception as ex:
        print("Scratch banner failed:", repr(ex))

def sc_banner_render():
    """Menu picture: a lottery-style kiosk (lit sign box, glass window with acrylic card dispensers, price tags, counter).
    Drawn at 2x and scaled down so every edge is smooth."""
    S, W, H = 2, 1100, 820
    keys = list(SC_CARDS)
    im = Image.new("RGBA", (W * S, H * S))
    d = ImageDraw.Draw(im)

    def X(v):
        return int(v * S)

    def B(b):
        return [X(v) for v in b]

    def vgrad(b, c1, c2):
        x0, y0, x1, y1 = B(b)
        for y in range(y0, y1):
            k = (y - y0) / max(1, y1 - y0 - 1)
            d.line([(x0, y), (x1, y)], fill=tuple(int(p + (q - p) * k) for p, q in zip(c1, c2)))

    def hgrad(b, c1, c2):
        x0, y0, x1, y1 = B(b)
        for x in range(x0, x1):
            k = (x - x0) / max(1, x1 - x0 - 1)
            d.line([(x, y0), (x, y1)], fill=tuple(int(p + (q - p) * k) for p, q in zip(c1, c2)))

    def over(fn, blur=0):
        layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
        fn(ImageDraw.Draw(layer))
        bb = layer.getbbox()
        if not bb:
            return
        pad = blur * S * 3
        x0, y0 = max(0, bb[0] - pad), max(0, bb[1] - pad)
        x1, y1 = min(im.width, bb[2] + pad), min(im.height, bb[3] + pad)
        part = layer.crop((x0, y0, x1, y1))
        if blur:
            part = part.filter(ImageFilter.GaussianBlur(blur * S))
        im.alpha_composite(part, (x0, y0))

    def F(size):
        return get_font(int(size * S))

    def fit(text, size, maxw):
        while size > 10 and d.textlength(he(text), font=F(size)) > maxw * S:
            size -= 1
        return F(size)

    def pair(cx, y, num, label, size, fill, sp=7):
        """'<label> <num>' centred on cx; the number is drawn on its own so it never gets flipped."""
        f, lab = F(size), he(label)
        wl, wn = d.textlength(lab, font=f), d.textlength(num, font=f)
        x = X(cx) - (wl + X(sp) + wn) / 2
        d.text((x, X(y)), num, font=f, fill=fill, anchor="lt")
        d.text((x + wn + X(sp), X(y)), lab, font=f, fill=fill, anchor="lt")

    def spade(cx, cy, s, fill, draw=None):
        """Vector spade, centred on (cx, cy), about 2*s tall."""
        g = draw or d
        g.polygon([(X(cx), X(cy - s)), (X(cx - 0.92 * s), X(cy + 0.14 * s)), (X(cx + 0.92 * s), X(cy + 0.14 * s))], fill=fill)
        for sx in (-0.44, 0.44):
            r = 0.5 * s
            g.ellipse([X(cx + sx * s - r), X(cy + 0.14 * s - r), X(cx + sx * s + r), X(cy + 0.14 * s + r)], fill=fill)
        g.polygon([(X(cx), X(cy + 0.1 * s)), (X(cx - 0.34 * s), X(cy + 1.0 * s)), (X(cx + 0.34 * s), X(cy + 1.0 * s))], fill=fill)

    rnd = random.Random(7)
    CHAMP = (222, 205, 160)        # soft champagne used for thin accents
    CHAMP_D = (150, 132, 96)

    # ---- evening street background with soft lights ----
    vgrad((0, 0, W, 700), (8, 12, 30), (40, 52, 96))
    pal = [(190, 210, 255, 60), (130, 190, 255, 60), (255, 150, 190, 40), (200, 230, 255, 40)]
    over(lambda g: [g.ellipse(B((x - r, y - r, x + r, y + r)), fill=rnd.choice(pal))
                    for x, y, r in ((rnd.uniform(0, W), rnd.uniform(0, 600), rnd.uniform(10, 40)) for _ in range(46))], blur=5)
    vgrad((0, 700, W, H), (62, 64, 78), (22, 22, 32))
    for yy in (722, 752, 792):
        d.line(B((0, yy, W, yy)), fill=(40, 42, 54), width=S)
    for xx in range(-500, 1600, 120):
        d.line(B((W / 2 + (xx - W / 2) * 0.5, 700, xx, H)), fill=(40, 42, 54), width=S)
    over(lambda g: g.ellipse(B((120, 726, 980, 812)), fill=(190, 215, 255, 40)), blur=22)       # light spilling on the floor
    over(lambda g: g.ellipse(B((30, 712, 1070, 772)), fill=(0, 0, 0, 190)), blur=12)            # shadow under the kiosk

    # ---- back wall inside the kiosk ----
    vgrad((110, 206, 990, 600), (52, 70, 108), (28, 40, 70))
    for yy in range(222, 600, 22):
        d.line(B((110, yy, 990, yy)), fill=(24, 34, 60), width=S)
        d.line(B((110, yy + 1, 990, yy + 1)), fill=(66, 88, 128), width=1)
    over(lambda g: g.rectangle(B((130, 206, 970, 300)), fill=(225, 238, 255, 90)), blur=26)      # light from the LED strip
    vgrad((110, 206, 990, 221), (250, 252, 255), (214, 226, 246))

    # shelf
    vgrad((110, 478, 990, 494), (244, 247, 252), (186, 193, 206))
    d.line(B((110, 478, 990, 478)), fill=(255, 255, 255), width=S)
    over(lambda g: g.rectangle(B((110, 494, 990, 508)), fill=(0, 0, 0, 110)), blur=5)

    # ---- decks in acrylic holders ----
    cw, ch, bw = 168, 210, 188
    gap = (880 - 4 * bw) / 5
    for i, key in enumerate(keys):
        c = SC_CARDS[key]
        left = len(sc_stock(key)["left"])
        bx = int(110 + gap + i * (bw + gap))
        cx0, base_y = bx + (bw - cw) // 2, 478 - 8 - ch
        n = 0 if not left else max(2, round(left / c["total"] * 10))
        rng = random.Random(key)
        over(lambda g: g.rounded_rectangle(B((bx + 12, 244, bx + bw + 12, 482)), radius=10, fill=(0, 0, 0, 120)), blur=8)
        over(lambda g: g.rounded_rectangle(B((bx, 228, bx + bw, 478)), radius=8, fill=(190, 215, 240, 26),
                                           outline=(200, 225, 250, 150), width=2 * S))
        for j in range(n - 1, 0, -1):
            jx = rng.randint(-1, 1)
            d.rounded_rectangle(B((cx0 + jx, base_y - j * 3, cx0 + jx + cw, base_y - j * 3 + ch)), radius=X(8),
                                fill=(246, 246, 250), outline=(150, 150, 162), width=S)
        b = sc_base(key)
        k = max(cw * S / b.width, ch * S / b.height)
        art = b.resize((max(cw * S, round(b.width * k)), max(ch * S, round(b.height * k))), Image.LANCZOS).crop((0, 0, cw * S, ch * S))
        if not left:
            art = Image.blend(art.convert("L").convert("RGB"), Image.new("RGB", art.size, (20, 20, 20)), 0.55)
        m = Image.new("L", (cw * S, ch * S), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, cw * S - 1, ch * S - 1], radius=X(8), fill=255)
        im.paste(art.convert("RGBA"), (X(cx0), X(base_y)), m)
        d.rounded_rectangle(B((cx0, base_y, cx0 + cw, base_y + ch)), radius=X(8),
                            outline=(240, 240, 246) if left else (110, 110, 112), width=2 * S)
        if not left:
            tag = Image.new("RGBA", (X(220), X(60)), (0, 0, 0, 0))
            ImageDraw.Draw(tag).text((X(110), X(30)), "SOLD OUT", font=F(34), fill=(255, 80, 80, 255), anchor="mm",
                                     stroke_width=3 * S, stroke_fill=(0, 0, 0, 255))
            tag = tag.rotate(14, expand=True, resample=Image.BICUBIC)
            im.alpha_composite(tag, (X(bx + bw / 2 - 110) - (tag.width - X(220)) // 2, X(base_y + ch / 2 - 30) - (tag.height - X(60)) // 2))
        # acrylic front: lip, glare, steel base
        over(lambda g: g.rounded_rectangle(B((bx + 2, 442, bx + bw - 2, 476)), radius=6, fill=(220, 235, 250, 46),
                                           outline=(230, 242, 255, 120), width=S))
        over(lambda g: g.polygon(B((bx + 18, 230, bx + 58, 230, bx + 24, 440, bx + 6, 440)), fill=(255, 255, 255, 52)))
        hgrad((bx - 4, 470, bx + bw + 4, 480), (150, 156, 170), (232, 236, 244))

    # ---- price tags under the shelf ----
    for i, key in enumerate(keys):
        c = SC_CARDS[key]
        left = len(sc_stock(key)["left"])
        bx = int(110 + gap + i * (bw + gap))
        cx, ty = bx + bw / 2, 512
        over(lambda g: g.rounded_rectangle(B((bx + 3, ty + 4, bx + bw + 3, ty + 80)), radius=6, fill=(0, 0, 0, 120)), blur=4)
        d.rounded_rectangle(B((bx, ty, bx + bw, ty + 76)), radius=X(6), fill=(250, 251, 254), outline=(170, 178, 194), width=S)
        d.rounded_rectangle(B((bx, ty, bx + bw, ty + 26)), radius=X(6), fill=(0, 84, 170))
        d.rectangle(B((bx, ty + 16, bx + bw, ty + 26)), fill=(0, 84, 170))
        d.text((X(cx), X(ty + 13)), he(c["name"]), font=fit(c["name"], 19, bw - 16), fill=(255, 255, 255), anchor="mm")
        pair(cx, ty + 31, sc_short(c["min"]), "סכום התחלתי", 17, (0, 58, 128))
        ratio = left / c["total"]
        col = (24, 130, 58) if ratio > 0.5 else (196, 112, 8) if ratio > 0.2 else (200, 36, 36)
        if left:
            pair(cx, ty + 52, f"{left}/{c['total']}", "נותרו", 17, col)
        else:
            d.text((X(cx), X(ty + 52)), he("אזל המלאי"), font=F(17), fill=col, anchor="lt")
        for px in (bx + 8, bx + bw - 8):
            d.ellipse(B((px - 2, ty + 4, px + 2, ty + 8)), fill=(150, 156, 170))

    # ---- glass in front of the window ----
    over(lambda g: g.rectangle(B((110, 206, 990, 600)), fill=(150, 200, 255, 12)))
    over(lambda g: (g.polygon(B((130, 222, 330, 222, 205, 598, 110, 598)), fill=(255, 255, 255, 24)),
                    g.polygon(B((372, 222, 424, 222, 300, 598, 250, 598)), fill=(255, 255, 255, 15)),
                    g.polygon(B((770, 222, 900, 222, 780, 598, 690, 598)), fill=(255, 255, 255, 18))))

    # ---- pillars + header beam ----
    for x0 in (70, 988):
        hgrad((x0, 196, x0 + 42, 722), (186, 194, 210), (246, 248, 252))
        d.rectangle(B((x0 + 15, 210, x0 + 27, 598)), fill=(0, 84, 170))
        d.line(B((x0 + 15, 210, x0 + 15, 598)), fill=(70, 150, 230), width=S)
        d.rectangle(B((x0, 196, x0 + 42, 722)), outline=(110, 118, 136), width=S)
    vgrad((70, 196, 1030, 210), (230, 235, 244), (150, 158, 176))
    over(lambda g: g.rectangle(B((110, 210, 990, 224)), fill=(0, 0, 0, 90)), blur=4)

    # ---- counter ----
    vgrad((54, 598, 1046, 620), (240, 244, 250), (180, 187, 202))
    d.line(B((54, 598, 1046, 598)), fill=(255, 255, 255), width=2 * S)
    d.line(B((54, 620, 1046, 620)), fill=(120, 128, 146), width=S)
    vgrad((62, 620, 1038, 716), (238, 242, 248), (206, 212, 224))
    vgrad((62, 636, 1038, 676), (0, 98, 192), (0, 62, 134))
    d.rectangle(B((62, 676, 1038, 680)), fill=CHAMP)                                       # thin accent line (was a thick yellow bar)
    d.rectangle(B((62, 680, 1038, 686)), fill=(0, 46, 108))
    d.line(B((62, 636, 1038, 636)), fill=(90, 160, 235), width=S)
    d.text((X(550), X(656)), he("מצאו צירוף של שלושה מכפילים"), font=F(26), fill=(255, 255, 255), anchor="mm")
    vgrad((62, 716, 1038, 738), (70, 74, 90), (30, 32, 42))
    # card terminal and pen cup on the counter
    over(lambda g: g.rounded_rectangle(B((992, 566, 1036, 600)), radius=6, fill=(0, 0, 0, 120)), blur=4)
    d.rounded_rectangle(B((992, 560, 1034, 598)), radius=X(6), fill=(26, 28, 36), outline=(90, 96, 110), width=S)
    d.rectangle(B((998, 566, 1028, 578)), fill=(40, 140, 230))
    for r in range(2):
        for cc in range(3):
            d.rectangle(B((999 + cc * 10, 583 + r * 7, 1005 + cc * 10, 587 + r * 7)), fill=(120, 126, 142))
    hgrad((74, 570, 98, 598), (150, 156, 170), (232, 236, 244))
    for px, py, col in ((80, 556, (200, 40, 40)), (86, 552, (30, 90, 200)), (92, 558, (30, 30, 34))):
        d.line(B((px + 6, 572, px, py)), fill=col, width=2 * S)

    # ---- roof ----
    over(lambda g: g.rectangle(B((50, 86, 1050, 104)), fill=(0, 0, 0, 110)), blur=6)
    d.polygon(B((36, 36, 1064, 36, 1046, 62, 54, 62)), fill=(238, 242, 250))
    vgrad((50, 62, 1050, 86), (250, 252, 255), (190, 198, 216))
    d.line(B((50, 86, 1050, 86)), fill=(120, 128, 146), width=S)

    # ---- sign: dark glass panel with a thin champagne frame, spades on both sides ----
    d.rounded_rectangle(B((90, 90, 1010, 192)), radius=X(10), fill=(40, 46, 62), outline=(110, 118, 136), width=S)
    over(lambda g: g.rounded_rectangle(B((98, 98, 1002, 184)), radius=6, fill=(90, 130, 230, 90)), blur=10)
    vgrad((98, 98, 1002, 184), (18, 26, 58), (6, 10, 28))
    over(lambda g: g.ellipse(B((250, 96, 850, 200)), fill=(70, 110, 220, 70)), blur=24)       # soft glow behind the title
    d.rounded_rectangle(B((98, 98, 1002, 184)), radius=X(6), outline=CHAMP_D, width=S)
    d.rounded_rectangle(B((104, 104, 996, 178)), radius=X(4), outline=(70, 80, 112), width=1)
    d.text((X(550), X(134)), he("כרטיסי גירוד"), font=F(60), fill=(248, 244, 232), anchor="mm",
           stroke_width=2 * S, stroke_fill=(4, 8, 24))
    # subtitle with thin rules on both sides
    sub = "A M R A M   C A S I N O"
    sw = d.textlength(sub, font=F(17))
    d.text((X(550), X(168)), sub, font=F(17), fill=CHAMP, anchor="mm")
    for sgn in (-1, 1):
        x_in = 550 + sgn * (sw / S / 2 + 16)
        x_out = 550 + sgn * (sw / S / 2 + 110)
        d.line(B((min(x_in, x_out), 168, max(x_in, x_out), 168)), fill=CHAMP_D, width=S)
    for sx in (172, 928):
        d.ellipse(B((sx - 38, 103, sx + 38, 179)), fill=(10, 16, 40), outline=CHAMP_D, width=2 * S)
        d.ellipse(B((sx - 33, 108, sx + 33, 174)), outline=(60, 70, 104), width=1)
        spade(sx, 138, 22, (240, 236, 224))

    # ---- photo feel: vignette + fine grain (done on the small image: much faster) ----
    out = im.convert("RGB").resize((W, H), Image.LANCZOS)
    vig = Image.new("L", (W // 4, H // 4), 0)
    ImageDraw.Draw(vig).ellipse([-W // 16, -H // 12, W // 4 + W // 16, H // 4 + H // 12], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(30)).resize((W, H), Image.BILINEAR)
    out = Image.composite(out, Image.new("RGB", (W, H), (4, 8, 18)), vig)
    out = Image.blend(out, Image.effect_noise((W, H), 26).convert("RGB"), 0.03)
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=90)
    return buf.getvalue()
# --- render end ---

class SpotButton(discord.ui.Button):
    def __init__(self, idx, row):
        super().__init__(style=discord.ButtonStyle.secondary, label=str(idx + 1), row=row)
        self.idx = idx

    async def callback(self, interaction):
        await self.view.click(interaction, self.idx)

class ScratchView(OwnedView):
    touch = True

    def __init__(self, user, bet, key, mult, token=None):
        super().__init__(timeout=180)
        self.user, self.bet, self.key, self.mult, self.token = user, bet, key, mult, token
        self.card = SC_CARDS[key]
        self.n = len(self.card["spots"])
        self.labels = sc_labels(self.n, mult)
        self.revealed, self.done, self.message, self.render_n = set(), False, None, 0
        self.version, self.edit_lock = 0, asyncio.Lock()
        cols = self.card["cols"]
        self.spot_btns = [SpotButton(i, i // cols) for i in range(self.n)]
        self.all_btn = discord.ui.Button(style=discord.ButtonStyle.success, label="גרד הכל", row=math.ceil(self.n / cols))
        self.all_btn.callback = self.settle
        for b in (*self.spot_btns, self.all_btn):
            self.add_item(b)

    def image(self, final=False):
        self.render_n += 1
        name = f"sc{self.render_n}.jpg"
        return discord.File(sc_render(self.key, self.labels, self.revealed, final, self.mult), name), name

    def embed(self, name):
        c = self.card
        prizes = " • ".join(f"x{m:g}" for m in sorted(c["wins"], reverse=True))
        e = discord.Embed(color=YELLOW, title=f"🎟️ {c['name']}", description=(
            f"שילמת **{fmt(self.bet)}** {cur()} מהבנק\n\n"
            f"מצאו צירוף של **שלושה מכפילים** כדי לזכות!\n"
            f"מכפילים אפשריים: {prizes}\n\nנגרדו {len(self.revealed)}/{self.n}"))
        e.set_author(name=self.user.name, icon_url=self.user.display_avatar.url)
        e.set_image(url=f"attachment://{name}")
        return e

    def reveal(self, i):
        self.revealed.add(i)
        b = self.spot_btns[i]
        b.label, b.disabled, b.style = f"x{self.labels[i]:g}", True, discord.ButtonStyle.primary

    async def click(self, interaction, idx):
        if not interaction.response.is_done():
            await interaction.response.defer()
        if self.done or idx in self.revealed:
            return
        self.reveal(idx)
        if len(self.revealed) == self.n:
            return await self.settle(interaction)
        self.version += 1
        v = self.version
        async with self.edit_lock:
            if v != self.version or self.done:
                return
            f, name = self.image()
            await interaction.edit_original_response(embed=self.embed(name), attachments=[f], view=self)

    def finalize(self):
        self.done = True
        for i in range(self.n):
            if i not in self.revealed:
                self.reveal(i)
        mult = self.mult
        if mult:
            for i, l in enumerate(self.labels):
                if l == mult:
                    self.spot_btns[i].style = discord.ButtonStyle.success if mult >= 1 else discord.ButtonStyle.danger
        returned = round(self.bet * mult)
        if returned > self.bet:
            returned += multi_extra("scratch", returned - self.bet)
        pending_done(self.token)
        u = user_data(self.user.id)
        u[SC_PAY_TO] += returned
        save()
        net = returned - self.bet
        log_game(self.user, f"scratch {SC_EN.get(self.key, self.key)}", self.bet, net)
        self.all_btn.disabled = True
        f, name = self.image(final=True)
        if net > 0:
            line, color = f"+ זכית ב-{fmt(net)}!", GREEN
        elif net < 0:
            line = f"- הפסדת {fmt(-net)}!" + (f" (קיבלת בחזרה {fmt(returned)})" if returned else "")
            color = RED
        else:
            line, color = "הימור הוחזר", YELLOW
        found = f"3 × x{mult:g}" if mult else "אין התאמה הפעם"
        e = discord.Embed(color=color, title=f"🎟️ {self.card['name']}", description=(
            f"{found}\n```diff\n{line}\n```\nיתרה בבנק: {fmt(u['bank'])} {cur()}"))
        e.set_author(name=self.user.name, icon_url=self.user.display_avatar.url)
        e.set_image(url=f"attachment://{name}")
        return e, f

    async def settle(self, interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        if self.done:
            return
        e, f = self.finalize()
        self.stop()
        async with self.edit_lock:
            await interaction.edit_original_response(embed=e, attachments=[f], view=self)

    async def on_timeout(self):
        if self.done:
            return
        e, f = self.finalize()
        if self.message:
            try:
                await self.message.edit(embed=e, attachments=[f], view=self)
            except Exception:
                pass

class ScratchAmountModal(discord.ui.Modal):
    def __init__(self, menu, key):
        c = SC_CARDS[key]
        super().__init__(title=f"{c['name']} - כמה כסף?"[:45])
        self.menu, self.key = menu, key
        self.amount = discord.ui.TextInput(label=f"סכום מהבנק (סכום התחלתי {sc_short(c['min'])})"[:45],
                                           placeholder="למשל: 5m או 2500000 או half או all", max_length=20)
        self.add_item(self.amount)

    async def on_submit(self, interaction):
        menu, key, c, user = self.menu, self.key, SC_CARDS[self.key], self.menu.user
        say = lambda t: interaction.response.send_message(t, ephemeral=True)
        if menu.chosen:
            return await say("כבר בחרת כרטיס.")
        if user.id in BUSY:
            return await say(BUSY_MSG)
        st = sc_stock(key)
        if not st["left"]:
            return await say("הכרטיס הזה אזל מהמלאי ❌")
        u = user_data(user.id)
        price = parse_amount(self.amount.value.strip(), u["bank"])
        if price is None or price <= 0:
            return await say("סכום לא תקין. למשל: `5m`, `2500000`, `half` או `all`")
        if price < c["min"]:
            return await say(f"הסכום ההתחלתי לכרטיס הזה הוא **{fmt(c['min'])}** {cur()}.")
        if price > u["bank"]:
            return await say(f"אין לך מספיק כסף **בבנק**. יש לך {fmt(u['bank'])} {cur()} (`$dep` להפקדה).")
        u["bank"] -= price
        menu.chosen = True
        menu.stop()
        mult = st["left"].pop()
        for _ in range(luck_attempts(user.id) - 1):
            if st["left"]:
                j = random.randrange(len(st["left"]))
                if st["left"][j] > mult:
                    st["left"][j], mult = mult, st["left"][j]
        st["sold"] += 1
        bg(refresh_banner())
        token = f"scr{interaction.id}"
        DB.setdefault("pending", {})[token] = {"uid": str(user.id), "bet": price, "scratch": [key, mult], "bank": True}
        BUSY.add(user.id)
        save()
        try:
            view = ScratchView(user, price, key, mult, token)
            view.message = interaction.message or menu.message
            f, name = view.image()
            await interaction.response.edit_message(embed=view.embed(name), attachments=[f], view=view)
        except Exception:
            cancel_game(user, token, price)
            raise

class ScratchSelect(discord.ui.Select):
    def __init__(self):
        opts = []
        for key, c in SC_CARDS.items():
            left = len(sc_stock(key)["left"])
            desc = (f"התחלה {sc_short(c['min'])} • פרס ראשי x{max(c['wins']):g} • נותרו {left}/{c['total']}" if left else "אזל המלאי")
            opts.append(discord.SelectOption(label=c["name"], value=key, emoji=c["emoji"], description=desc))
        super().__init__(placeholder="בחירת כרטיס גירוד", options=opts)

    async def callback(self, interaction):
        menu, key = self.view, self.values[0]
        if menu.chosen:
            return await interaction.response.defer()
        if interaction.user.id in BUSY:
            return await interaction.response.send_message(BUSY_MSG, ephemeral=True)
        if not sc_stock(key)["left"]:
            return await interaction.response.send_message("הכרטיס הזה אזל מהמלאי ❌", ephemeral=True)
        await interaction.response.send_modal(ScratchAmountModal(menu, key))
        try:
            await interaction.message.edit(view=menu)
        except Exception:
            pass

class ScratchMenu(OwnedView):
    touch = True

    def __init__(self, user):
        super().__init__(timeout=120)
        self.user, self.message, self.chosen = user, None, False
        self.add_item(ScratchSelect())

    def embed(self, image=True):
        bank = user_data(self.user.id)["bank"]
        e = discord.Embed(color=0x1F2A44, title="כרטיסי גירוד", description=(
            f"\u200f**יתרה בבנק:** {fmt(bank)} {cur()}\n"
            "\u200fבחרו כרטיס מהתפריט שמתחת והקלידו כמה לשלם."))
        e.set_author(name=self.user.name, icon_url=self.user.display_avatar.url)
        e.set_footer(text="התשלום יורד מהבנק בלבד")
        if image:
            e.set_image(url="attachment://sc_menu.jpg")
        return e

    async def on_timeout(self):
        if self.chosen or not self.message:
            return
        for b in self.children:
            b.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass

@tasks.loop(seconds=30)
async def sc_daily_loop():
    """Every day at 00:00 all scratch cards go back to the stock."""
    if loaded is None or not loaded.is_set():
        return
    today = today_key()
    last = DB.get("sc_reset_day")
    if last is None:
        DB["sc_reset_day"] = today
        save()
    elif last != today:
        DB["sc_stock"] = {}
        for k in SC_CARDS:
            sc_stock(k)
        DB["sc_reset_day"] = today
        save()
        bg(refresh_banner())
        print("Scratch cards restocked (00:00)")

@bot.command(name="scratch", aliases=["sc"], usage="sc")
async def scratch(ctx, sub: str = None):
    if sub and sub.lower() in ("restart", "reset"):
        if ctx.author.id not in OWNER_IDS:
            return
        DB["sc_stock"] = {}
        for k in SC_CARDS:
            sc_stock(k)
        save()
        bg(refresh_banner())
        return await reply(ctx, "🎟️ כל כרטיסי הגירוד אופסו: כל הכרטיסים חזרו למלאי.", GREEN)
    if ctx.author.id in BUSY:
        return await reply(ctx, BUSY_MSG, RED)
    if not SC_ART:
        return await reply(ctx, "scratch_art.py is missing next to the bot file.", RED)
    view = ScratchMenu(ctx.author)
    data = SC_BANNER["data"]          # the menu opens instantly with the last picture, a fresh one is drawn in the background
    if data:
        view.message = await ctx.reply(embed=view.embed(), file=discord.File(io.BytesIO(data), "sc_menu.jpg"),
                                       view=view, mention_author=False)
    else:
        view.message = await ctx.reply(embed=view.embed(image=False), view=view, mention_author=False)
    if SC_BANNER["key"] != sc_key():
        bg(update_menu_picture(view))

async def update_menu_picture(view):
    await refresh_banner()
    data = SC_BANNER["data"]
    if not data or view.chosen or not view.message:
        return
    try:
        await view.message.edit(embed=view.embed(), attachments=[discord.File(io.BytesIO(data), "sc_menu.jpg")])
    except Exception:
        pass
