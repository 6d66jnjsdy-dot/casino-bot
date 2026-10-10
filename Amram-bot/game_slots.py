import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= SLOTS =================
SLOT_ICON = 50
SLOT_NAMES = dict(zip(SLOTS, ["cherry", "lemon", "grape", "bell", "diamond", "seven"]))

@lru_cache(maxsize=None)
def slot_icon(sym):
    S = 256
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    name = SLOT_NAMES[sym]
    if name == "cherry":
        leaf, dark = (60, 150, 70, 255), (120, 10, 25, 255)
        d.line([(82, 170), (140, 40)], fill=leaf, width=12)
        d.line([(178, 180), (140, 40)], fill=leaf, width=12)
        d.ellipse([140, 20, 222, 70], fill=leaf)
        for cx, cy in ((80, 190), (176, 200)):
            d.ellipse([cx - 50, cy - 50, cx + 50, cy + 50], fill=(215, 30, 50, 255), outline=dark, width=6)
            d.ellipse([cx - 28, cy - 32, cx - 6, cy - 10], fill=(255, 150, 160, 255))
    elif name == "lemon":
        d.ellipse([12, 98, 52, 158], fill=(225, 190, 40, 255))
        d.ellipse([204, 98, 244, 158], fill=(225, 190, 40, 255))
        d.ellipse([28, 58, 228, 198], fill=(252, 226, 60, 255), outline=(200, 160, 20, 255), width=6)
        d.ellipse([70, 82, 130, 112], fill=(255, 246, 165, 255))
    elif name == "grape":
        for cx, cy in ((64, 100), (128, 100), (192, 100), (96, 152), (160, 152), (128, 204)):
            d.ellipse([cx - 32, cy - 32, cx + 32, cy + 32], fill=(140, 60, 180, 255), outline=(80, 30, 110, 255), width=5)
            d.ellipse([cx - 18, cy - 20, cx - 6, cy - 8], fill=(210, 160, 235, 255))
        d.line([(128, 70), (128, 26)], fill=(90, 60, 30, 255), width=10)
        d.ellipse([128, 14, 208, 54], fill=(60, 150, 70, 255))
    elif name == "bell":
        gold, edge = (245, 190, 40, 255), (160, 105, 10, 255)
        d.ellipse([56, 28, 200, 172], fill=gold, outline=edge, width=6)
        d.polygon([(58, 100), (198, 100), (232, 190), (24, 190)], fill=gold)
        d.line([(58, 100), (24, 190)], fill=edge, width=6)
        d.line([(198, 100), (232, 190)], fill=edge, width=6)
        d.line([(24, 190), (232, 190)], fill=edge, width=8)
        d.ellipse([106, 196, 150, 240], fill=gold, outline=edge, width=5)
        d.ellipse([84, 52, 122, 112], fill=(255, 232, 140, 255))
    elif name == "diamond":
        pts = [(70, 50), (186, 50), (236, 108), (128, 226), (20, 108)]
        d.polygon(pts, fill=(90, 200, 255, 255))
        d.line(pts + [pts[0]], fill=(20, 110, 170, 255), width=6, joint="curve")
        light = (215, 245, 255, 255)
        d.line([(20, 108), (236, 108)], fill=light, width=5)
        d.line([(70, 50), (96, 108), (128, 226)], fill=light, width=5)
        d.line([(186, 50), (160, 108), (128, 226)], fill=light, width=5)
        d.line([(96, 108), (128, 50), (160, 108)], fill=light, width=5)
    else:
        d.text((128, 132), "7", font=get_font(230), fill=(225, 30, 40, 255), anchor="mm",
               stroke_width=10, stroke_fill=(255, 215, 80, 255))
    return im.resize((SLOT_ICON, SLOT_ICON), Image.LANCZOS)

def render_slots(final, win):
    cell, rw, gap, pad = 62, 84, 8, 12
    W, H = pad * 2 + rw * 3 + gap * 2, pad * 2 + cell * 3
    cycle = random.sample(SLOTS, len(SLOTS))
    n = len(cycle)
    stops, total = (26, 34, 42), 46
    targets = [(2 + i) * n + cycle.index(final[i]) for i in range(3)]
    shade = Image.new("RGBA", (rw, cell), (0, 0, 0, 110))

    def frame(f, last=False):
        im = Image.new("RGB", (W, H), (60, 12, 24))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, W - 1, H - 1], outline=(235, 190, 60), width=4)
        for i in range(3):
            p = min(1.0, f / stops[i])
            pos = targets[i] * (1 - (1 - p) ** 3)
            reel = Image.new("RGBA", (rw, cell * 3), (250, 248, 240, 255))
            base = int(pos)
            for k in range(base - 2, base + 3):
                icon = slot_icon(cycle[k % n])
                yc = cell * 1.5 + (pos - k) * cell
                reel.paste(icon, ((rw - SLOT_ICON) // 2, int(yc - SLOT_ICON / 2)), icon)
            reel.paste(shade, (0, 0), shade)
            reel.paste(shade, (0, cell * 2), shade)
            im.paste(reel.convert("RGB"), (pad + i * (rw + gap), pad))
        d.line([(pad - 8, H // 2), (W - pad + 8, H // 2)], fill=(230, 40, 40), width=2)
        if last and win:
            d.rectangle([pad - 3, pad + cell - 2, W - pad + 3, pad + cell * 2 + 2], outline=(90, 255, 120), width=3)
        return im

    frames = [frame(f) for f in range(total - 1)] + [frame(total - 1, last=True)]
    gif, png = io.BytesIO(), io.BytesIO()
    pal = [fr.quantize(colors=64, method=Image.MEDIANCUT) for fr in frames]
    pal[0].save(gif, "GIF", save_all=True, append_images=pal[1:], duration=[100] * (len(pal) - 1) + [6000], loop=0, optimize=False)
    frames[-1].save(png, "PNG")
    return gif.getvalue(), png.getvalue()

SLOT_CACHE = {}

async def get_slots_anim(final):
    key = tuple(final)
    if key not in SLOT_CACHE:
        win = max(final.count(s) for s in SLOTS) >= 2
        SLOT_CACHE[key] = await asyncio.to_thread(render_slots, list(final), win)
    return SLOT_CACHE[key]

async def warm_animations():
    try:
        for a in SLOTS:
            for b in SLOTS:
                for c in SLOTS:
                    await get_slots_anim([a, b, c])
                    await asyncio.sleep(0.25)
        print("Animations are ready")
    except Exception as ex:
        print("Warm-up failed:", repr(ex))

async def finish_slots(ctx, token, bet, win, mult, final, png, msg):
    try:
        await asyncio.sleep(SLOT_WAIT + LOAD_BUFFER)
    finally:
        pending_done(token)
        user_data(ctx.author.id)["cash"] += win
        save()
        BUSY.discard(ctx.author.id)
    line = "🎰  ┃ " + " ┃ ".join(final) + " ┃  🎰"
    extra = f"{line}\n" + (f"**x{mult:.2f}**\n\n" if win else "\n")
    result = result_embed(ctx.author, win > 0, win - bet if win else bet, extra)
    result.set_image(url="attachment://slots_result.png")
    if msg:
        try:
            await msg.edit(embed=result, attachments=[discord.File(io.BytesIO(png), "slots_result.png")])
        except discord.HTTPException:
            pass
    log_game(ctx.author, "slots", bet, win - bet)

@bot.command(name="slots", aliases=["slot"], usage="slots <amount | half | all>")
async def slots(ctx, amount: str = None):
    bet = await take_bet(ctx, amount, "slots <amount | half | all>", track=True)
    if not bet:
        return
    token = str(ctx.message.id)
    BUSY.add(ctx.author.id)
    try:
        final = [random.choice(SLOTS) for _ in range(3)]
        if len(set(final)) == 3 and random.random() < SLOTS_BOOST / (120 / 216):
            final[1] = final[0]
        if max(final.count(s) for s in SLOTS) >= 2 and random.random() < SLOT_WIN_CUT:
            final = random.sample(SLOTS, 3)
        for _ in range(luck_attempts(ctx.author.id) - 1):
            if max(final.count(s) for s in SLOTS) >= 2:
                break
            final = [random.choice(SLOTS) for _ in range(3)]
        top = max(final.count(s) for s in SLOTS)
        mult = (SLOT_PAY[final[0]] if top == 3 else 1.5 if top == 2 else 0) * SLOT_BUFF
        win = int(bet * mult)
        if win > bet:
            win += multi_extra("slots", win - bet)
            mult = win / bet
        try:
            gif, png = await get_slots_anim(final)
        except Exception:
            cancel_game(ctx.author, token, bet)
            raise
        e = make_embed(ctx.author, f"🎰 **Slots**\n\nYou bet **{fmt(bet)}** {cur()}\n\n⏳ Spinning...", YELLOW)
        e.set_image(url="attachment://slots.gif")
        msg = None
        try:
            msg = await ctx.reply(embed=e, file=discord.File(io.BytesIO(gif), "slots.gif"), mention_author=False)
        except discord.HTTPException:
            pass
    except Exception:
        BUSY.discard(ctx.author.id)
        raise
    bg(finish_slots(ctx, token, bet, win, mult, final, png, msg))
