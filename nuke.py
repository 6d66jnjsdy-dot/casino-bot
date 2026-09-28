import discord
from discord.ext import commands


def setup(bot):

    @bot.command()
    @commands.has_permissions(administrator=True)
    async def nuke(ctx):
        await ctx.send(
            "⚠️ הפקודה הזו מיועדת לניקוי השרת. "
            "הקלד `$nuke-confirm` כדי לאשר."
        )

    @bot.command()
    @commands.has_permissions(administrator=True)
    async def nuke_confirm(ctx):

        guild = ctx.guild

        # מחיקת חדרים
        for channel in list(guild.channels):
            try:
                await channel.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

        # מחיקת רולים שהבוט רשאי למחוק
        for role in list(guild.roles):
            if role.is_default():
                continue

            try:
                await role.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass