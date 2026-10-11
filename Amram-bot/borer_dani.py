"""Bulk emoji creator: random character images -> server (or application) emojis.

Usage (owner only):
    $makeemojis 20                 -> 20 random characters, all styles
    $makeemojis 15 pixel-art       -> a specific style
    $makeemojis 10 folder          -> images from the emoji_images/ folder
    add "app" at the end           -> create application emojis instead of server emojis
"""
import os, io, re, random, asyncio
import aiohttp
import discord

STYLES = ['adventurer', 'big-ears', 'bottts', 'fun-emoji', 'lorelei', 'micah',
          'notionists', 'open-peeps', 'pixel-art', 'thumbs', 'avataaars', 'croodles']
FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emoji_images")
DELAY = 2.0  # seconds between creations (Discord rate limit)


def _clean_name(text, fallback):
    name = re.sub(r"[^a-zA-Z0-9_]", "_", text).strip("_")
    if len(name) < 2:
        name = fallback
    return name[:32]


def _shrink(data):
    """Make sure the image is <=128x128 and <256KB (needs Pillow; skipped if missing)."""
    try:
        from PIL import Image
    except ImportError:
        return data
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    img.thumbnail((128, 128))
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


async def _fetch_random(session, style):
    seed = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=10))
    url = f"https://api.dicebear.com/9.x/{style}/png?seed={seed}&size=128&radius=0"
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status}")
        return seed, await r.read()


async def _is_owner(ctx):
    try:
        if await ctx.bot.is_owner(ctx.author):
            return True
    except Exception:
        pass
    oid = globals().get("OWNER_ID")
    return oid is not None and ctx.author.id == int(oid)


async def _create(ctx, target, name, data):
    if target == "app":
        await ctx.bot.create_application_emoji(name=name, image=data)
    else:
        await ctx.guild.create_custom_emoji(name=name, image=data, reason="emoji_maker")


@bot.command(name="makeemojis", aliases=["emojis_create", "createemojis"])
async def makeemojis(ctx, count: int = 10, *args):
    """$makeemojis [count] [style|random|folder] [app]"""
    if not await _is_owner(ctx):
        return
    if ctx.guild is None:
        return

    mode = "random"
    target = "server"
    for a in args:
        a = a.lower()
        if a == "app":
            target = "app"
        elif a == "folder":
            mode = "folder"
        elif a in STYLES:
            mode = a

    if target == "server":
        used = len([e for e in ctx.guild.emojis if not e.animated])
        free = ctx.guild.emoji_limit - used
        if free <= 0:
            return await ctx.send("אין מקום פנוי לאימוג'ים בשרת.")
        count = min(count, free)
    count = max(1, min(count, 50))

    msg = await ctx.send(f"⏳ יוצר {count} אימוג'ים...")
    ok, fail = [], 0

    items = []  # list of (name, bytes)
    async with aiohttp.ClientSession() as session:
        if mode == "folder":
            os.makedirs(FOLDER, exist_ok=True)
            files = [f for f in os.listdir(FOLDER) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))]
            random.shuffle(files)
            for f in files[:count]:
                with open(os.path.join(FOLDER, f), "rb") as fh:
                    items.append((_clean_name(os.path.splitext(f)[0], "emoji"), _shrink(fh.read())))
            if not items:
                return await msg.edit(content=f"אין תמונות בתיקייה `{FOLDER}`.")
        else:
            for i in range(count):
                style = random.choice(STYLES) if mode == "random" else mode
                try:
                    seed, data = await _fetch_random(session, style)
                    items.append((_clean_name(f"{style.replace('-', '_')}_{seed[:5]}", f"char_{i}"), _shrink(data)))
                except Exception:
                    fail += 1

    for name, data in items:
        try:
            await _create(ctx, target, name, data)
            ok.append(name)
        except discord.Forbidden:
            return await msg.edit(content="❌ לבוט אין הרשאת **Manage Expressions**.")
        except Exception:
            fail += 1
        await asyncio.sleep(DELAY)

    await msg.edit(content=f"✅ נוצרו **{len(ok)}** אימוג'ים" + (f" | ❌ נכשלו **{fail}**" if fail else ""))
