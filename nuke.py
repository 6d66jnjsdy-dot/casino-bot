from discord.ext import commands

def setup(bot):

    @bot.command()
    @commands.has_permissions(administrator=True)
    async def nuke(ctx):
        guild = ctx.guild

        for channel in guild.channels:
            try:
                await channel.delete()
            except:
                pass

        for role in guild.roles:
            if role.is_default():
                continue

            try:
                await role.delete()
            except:
                pass