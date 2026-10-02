import math
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

SW, SH = 115, 160
K = 4

RED = (200, 24, 40, 255)
BLACK = (24, 24, 30, 255)
INK = (38, 30, 32, 255)
GOLD = (240, 190, 50, 255)
GOLD_D = (165, 115, 18, 255)
SKIN = (250, 218, 178, 255)
BLUE = (38, 106, 172, 255)
CREAM = (255, 252, 240, 255)
WHITE = (255, 255, 255, 255)
SUIT_COLOR = {"♣": BLACK, "♠": BLACK, "♥": RED, "♦": RED}
SUIT_LETTER = {"♣": "C", "♠": "S", "♥": "H", "♦": "D"}


@lru_cache(maxsize=None)
def _font(size):
    for name in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _circle(cx, cy, r, n=48):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _norm(polys):
    pts = [p for poly in polys for p in poly]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    cx, cy, s = (x0 + x1) / 2, (y0 + y1) / 2, 2 / max(x1 - x0, y1 - y0)
    return [[((x - cx) * s, (y - cy) * s) for x, y in poly] for poly in polys]


def _heart():
    pts = []
    for i in range(160):
        t = 2 * math.pi * i / 160
        pts.append((16 * math.sin(t) ** 3,
                    -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))))
    return pts


SUIT_POLYS = {
    "♥": _norm([_heart()]),
    "♦": _norm([[(0, -1), (0.62, 0), (0, 1), (-0.62, 0)]]),
    "♠": _norm([[(x, -y) for x, y in _heart()], [(-1.8, 5), (1.8, 5), (5.5, 16), (-5.5, 16)]]),
    "♣": _norm([_circle(0, -6, 5.6), _circle(-6.3, 3, 5.6), _circle(6.3, 3, 5.6), _circle(0, 0.5, 3.4),
                [(-1.8, 2), (1.8, 2), (5.5, 14), (-5.5, 14)]]),
}


def draw_suit(d, suit, cx, cy, s, flip=False, color=None):
    color = color or SUIT_COLOR[suit]
    for poly in SUIT_POLYS[suit]:
        d.polygon([(cx + x * s, cy + (-y if flip else y) * s) for x, y in poly], fill=color)


_PT = 1 / 3
CARD_PIPS = {
    "2": [(.5, 0), (.5, 1)],
    "3": [(.5, 0), (.5, .5), (.5, 1)],
    "4": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "5": [(0, 0), (1, 0), (.5, .5), (0, 1), (1, 1)],
    "6": [(0, 0), (1, 0), (0, .5), (1, .5), (0, 1), (1, 1)],
    "7": [(0, 0), (1, 0), (.5, .25), (0, .5), (1, .5), (0, 1), (1, 1)],
    "8": [(0, 0), (1, 0), (.5, .25), (0, .5), (1, .5), (.5, .75), (0, 1), (1, 1)],
    "9": [(0, 0), (1, 0), (0, _PT), (1, _PT), (.5, .5), (0, 2 * _PT), (1, 2 * _PT), (0, 1), (1, 1)],
    "10": [(0, 0), (1, 0), (.5, 1 / 6), (0, _PT), (1, _PT), (0, 2 * _PT), (1, 2 * _PT), (.5, 5 / 6), (0, 1), (1, 1)],
}


def _court(rank, suit, W, H):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    x0, x1, y0, y1 = .2 * W, .8 * W, .04 * H, .96 * H
    ym = H / 2
    d.rounded_rectangle([x0, y0, x1, y1], radius=3 * K, fill=CREAM, outline=INK, width=K)

    fig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(fig)
    bw, bh = x1 - x0, ym - y0

    def P(u, v):
        return (x0 + u * bw, y0 + v * bh)

    def poly(pts, fill, line=INK, w=K):
        pp = [P(*p) for p in pts]
        g.polygon(pp, fill=fill)
        if line:
            g.line(pp + [pp[0]], fill=line, width=w, joint="curve")

    def ell(u0, v0, u1, v1, fill, line=INK, w=K):
        g.ellipse([*P(u0, v0), *P(u1, v1)], fill=fill, outline=line, width=w if line else 0)

    def seg(a, b, fill, w):
        g.line([P(*a), P(*b)], fill=fill, width=w)

    hair = (214, 150, 40, 255) if rank == "Q" else (120, 72, 28, 255) if rank == "J" else (205, 205, 210, 255)

    if rank == "Q":
        poly([(.31, .2), (.25, .62), (.4, .66), (.6, .66), (.75, .62), (.69, .2)], hair)

    poly([(.44, .46), (.56, .46), (.57, .62), (.43, .62)], SKIN)
    poly([(.05, 1), (.1, .66), (.3, .55), (.5, .62), (.5, 1)], RED)
    poly([(.5, .62), (.7, .55), (.9, .66), (.95, 1), (.5, 1)], BLUE)
    poly([(.465, .64), (.535, .64), (.535, 1), (.465, 1)], GOLD, GOLD_D)
    for u in (.24, .76):
        for v in (.76, .9):
            ell(u - .045, v - .05, u + .045, v + .05, GOLD, GOLD_D, K // 2 or 1)
    poly([(.1, .66), (.3, .55), (.32, .62), (.14, .72)], GOLD, GOLD_D)
    poly([(.9, .66), (.7, .55), (.68, .62), (.86, .72)], GOLD, GOLD_D)
    if rank == "J":
        poly([(.33, .55), (.5, .72), (.67, .55), (.6, .53), (.5, .62), (.4, .53)], GOLD, GOLD_D)
    else:
        poly([(.3, .56), (.5, .74), (.7, .56), (.62, .52), (.5, .62), (.38, .52)], WHITE)
        for u, v in ((.36, .56), (.43, .62), (.5, .68), (.57, .62), (.64, .56)):
            ell(u - .012, v - .012, u + .012, v + .012, INK, None)

    if rank == "K":
        poly([(.36, .24), (.34, .52), (.42, .48)], hair)
        poly([(.64, .24), (.66, .52), (.58, .48)], hair)
    elif rank == "J":
        poly([(.36, .24), (.33, .54), (.42, .5), (.41, .3)], hair)
        poly([(.64, .24), (.67, .54), (.58, .5), (.59, .3)], hair)
    ell(.38, .2, .62, .5, SKIN)
    if rank == "K":
        poly([(.38, .38), (.4, .56), (.5, .62), (.6, .56), (.62, .38), (.57, .46), (.5, .49), (.43, .46)], hair)
        poly([(.42, .4), (.5, .39), (.58, .4), (.56, .45), (.5, .43), (.44, .45)], hair)
    for ex in (.45, .55):
        ell(ex - .018, .31, ex + .018, .35, INK, None)
    seg((.5, .34), (.49, .4), (150, 100, 70, 255), K)
    if rank != "K":
        g.arc([*P(.45, .38), *P(.55, .47)], 20, 160, fill=(170, 40, 50, 255), width=K)
        ell(.37, .38, .43, .43, (245, 170, 160, 255), None)
        ell(.57, .38, .63, .43, (245, 170, 160, 255), None)

    if rank == "K":
        poly([(.36, .25), (.34, .09), (.43, .17), (.5, .04), (.57, .17), (.66, .09), (.64, .25)], GOLD, GOLD_D)
        poly([(.36, .21), (.64, .21), (.64, .27), (.36, .27)], GOLD_D, INK)
        for u in (.42, .5, .58):
            ell(u - .018, .225, u + .018, .265, RED, None)
    elif rank == "Q":
        poly([(.37, .25), (.35, .12), (.42, .18), (.46, .07), (.5, .16), (.54, .07), (.58, .18), (.65, .12), (.63, .25)], GOLD, GOLD_D)
        poly([(.37, .21), (.63, .21), (.63, .26), (.37, .26)], GOLD_D, INK)
        ell(.475, .205, .525, .265, RED, None)
    else:
        poly([(.34, .27), (.36, .13), (.5, .07), (.65, .13), (.66, .27)], RED)
        poly([(.33, .23), (.67, .23), (.67, .29), (.33, .29)], GOLD, GOLD_D)
        poly([(.6, .14), (.9, .02), (.8, .2), (.64, .22)], WHITE)

    if rank == "K":
        seg((.88, .06), (.88, 1), (215, 215, 225, 255), 3 * K)
        seg((.88, .06), (.88, 1), INK, K // 2 or 1)
        seg((.78, .62), (.98, .62), GOLD_D, 3 * K)
    elif rank == "Q":
        seg((.86, .98), (.83, .52), (60, 140, 70, 255), 2 * K)
        for dx, dy in ((0, -.07), (.07, 0), (0, .07), (-.07, 0)):
            ell(.83 + dx - .04, .45 + dy - .045, .83 + dx + .04, .45 + dy + .045, (230, 70, 90, 255), INK, K // 2 or 1)
        ell(.8, .42, .86, .48, GOLD, GOLD_D, K // 2 or 1)
    else:
        seg((.88, .0), (.88, 1), (120, 80, 40, 255), 2 * K)
        poly([(.88, .08), (.99, .02), (.99, .3), (.88, .26)], (225, 228, 238, 255))

    draw_suit(g, suit, *P(.11, .12), .04 * H)
    lay = Image.alpha_composite(lay, fig)
    lay = Image.alpha_composite(lay, fig.rotate(180))
    d = ImageDraw.Draw(lay)
    d.line([(x0, ym), (x1, ym)], fill=(205, 180, 130, 255), width=K // 2 or 1)
    return lay


@lru_cache(maxsize=None)
def get_card(card):
    r, s = card
    W, H = SW * K, SH * K
    col = SUIT_COLOR[s]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=8 * K, fill=(255, 255, 255, 255), outline=(176, 184, 200, 255), width=K)
    if r in ("J", "Q", "K"):
        im = Image.alpha_composite(im, _court(r, s, W, H))
        d = ImageDraw.Draw(im)
    elif r == "A":
        draw_suit(d, s, W / 2, H / 2, .17 * H)
    else:
        for cx, cy in CARD_PIPS[r]:
            draw_suit(d, s, (.33 + .34 * cx) * W, (.19 + .62 * cy) * H, .068 * H, flip=cy > .5)
    idx = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    di = ImageDraw.Draw(idx)
    ix = .135 * W
    di.text((ix, .095 * H), r, font=_font(int(H * (.125 if len(r) == 2 else .15))), fill=col, anchor="mm")
    draw_suit(di, s, ix, .205 * H, .036 * H)
    im = Image.alpha_composite(Image.alpha_composite(im, idx), idx.rotate(180))
    return im.resize((SW, SH), Image.LANCZOS)


@lru_cache(maxsize=1)
def get_back():
    W, H = SW * K, SH * K
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=8 * K, fill=(255, 255, 255, 255), outline=(176, 184, 200, 255), width=K)
    m = 7 * K
    inner = Image.new("RGBA", (W - 2 * m, H - 2 * m), (150, 24, 44, 255))
    di = ImageDraw.Draw(inner)
    step = 12 * K
    for k in range(-inner.height, inner.width + inner.height, step):
        di.line([(k, 0), (k + inner.height, inner.height)], fill=(215, 90, 105, 255), width=K)
        di.line([(k, inner.height), (k + inner.height, 0)], fill=(215, 90, 105, 255), width=K)
    cx, cy = inner.width / 2, inner.height / 2
    di.ellipse([cx - 18 * K, cy - 18 * K, cx + 18 * K, cy + 18 * K], fill=(150, 24, 44, 255), outline=GOLD, width=2 * K)
    di.polygon([(cx, cy - 11 * K), (cx + 8 * K, cy), (cx, cy + 11 * K), (cx - 8 * K, cy)], fill=GOLD)
    mask = Image.new("L", inner.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, inner.width - 1, inner.height - 1], radius=5 * K, fill=255)
    im.paste(inner, (m, m), mask)
    return im.resize((SW, SH), Image.LANCZOS)
