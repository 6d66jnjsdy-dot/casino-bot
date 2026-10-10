import discord, random, json, os, asyncio, io, signal, math, time, base64, re, datetime
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter, features
from discord.ext import commands, tasks
from aiohttp import web
from core import *
# ================= STAFF / ADMIN =================
class NotStaff(commands.CheckFailure):
    pass

def admin_or_owner(ctx):
    if ctx.author.id in OWNER_IDS or ctx.author.guild_permissions.administrator:
        return True
    raise commands.MissingPermissions(["administrator"])

def is_staff(ctx):
    if ctx.author.id in OWNER_IDS or ctx.author.guild_permissions.administrator:
        return True
    rid = DB.get("staff_role")
    if rid and any(r.id == rid for r in ctx.author.roles):
        return True
    raise NotStaff()

admin_only = commands.check(admin_or_owner)
staff_only = commands.check(is_staff)
owner_only = commands.check(lambda ctx: ctx.author.id in OWNER_IDS)
