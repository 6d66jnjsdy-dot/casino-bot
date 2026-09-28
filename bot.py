import discord
from discord.ext import commands

@bot.command()
@commands.has_permissions(administrator=True)
async def nuke(ctx):
    guild = ctx.guild

    # מחיקת כל החדרים
    for channel in guild.channels:
        try:
            await channel.delete()
        except:
            pass

    # מחיקת כל הרולים
    for role in guild.roles:
        if role.is_default():
            continue

        try:
            await role.delete()
        except:
            pass