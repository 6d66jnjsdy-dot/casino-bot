import discord
from discord.ext import commands


def setup(bot):

    @bot.command()
    @commands.has_permissions(administrator=True)
    async def nuke(ctx):
        await ctx.send(
            "⚠️ פעולה מסוכנת. כתוב `$nuke-confirm` כדי לאשר."
        )

    @bot.command()
    @commands.has_permissions(administrator=True)
    async def nuke_confirm(ctx):

        guild = ctx.guild

        # מחיקת כל החדרים
        for channel in list(guild.channels):
            try:
                await channel.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

        # מחיקת רולים שהבוט יכול למחוק
        for role in list(guild.roles):
            if role.is_default():
                continue

            try:
                await role.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass