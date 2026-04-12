import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.remove_command('help')

    @commands.hybrid_command(name="help", description="Shows all commands and categories.")
    async def help(self, ctx, category: str = None):
        """Shows all commands and categories."""

        if category is None:
            embed = discord.Embed(
                title="📖 Bot Help",
                description=(
                    "Use `/help <category>` to see commands.\n\n"
                    "**Categories:**"
                ),
                color=0x3498db
            )
            embed.add_field(
                name="🔨 Moderation",
                value="`/help mod`",
                inline=True
            )
            embed.add_field(
                name="🛠️ Utility",
                value="`/help utility`",
                inline=True
            )
            embed.add_field(
                name="💰 Economy",
                value="`/help economy`",
                inline=True
            )
            embed.add_field(
                name="🎮 Games",
                value="`/help games`",
                inline=True
            )
            embed.add_field(
                name="⚙️ Management",
                value="`/help manage`",
                inline=True
            )
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")
            await ctx.send(embed=embed)
            return

        category = category.lower()

        if category == 'mod':
            embed = discord.Embed(title="🔨 Moderation Commands", color=discord.Color.red())
            embed.add_field(name="`/kick`", value="Kick a member", inline=False)
            embed.add_field(name="`/ban`", value="Ban a member", inline=False)
            embed.add_field(name="`/clear`", value="Delete messages", inline=False)
            embed.add_field(name="`/report`", value="Report a user to staff", inline=False)

        elif category == 'utility':
            embed = discord.Embed(title="🛠️ Utility Commands", color=discord.Color.blue())
            embed.add_field(name="`/uptime`", value="Check bot online time", inline=False)
            embed.add_field(name="`/afk`", value="Set an AFK status", inline=False)
            embed.add_field(name="`/photo`", value="Get a random photo", inline=False)

        elif category == 'economy':
            embed = discord.Embed(title="💰 Economy Commands", color=discord.Color.green())
            embed.add_field(name="`/balance`", value="Check your money", inline=False)
            embed.add_field(name="`/work`", value="Earn money", inline=False)
            embed.add_field(name="`/pay`", value="Give money to someone", inline=False)

        elif category == 'games':
            embed = discord.Embed(title="🎮 Games", color=discord.Color.purple())
            embed.add_field(name="`/blackjack`", value="Play blackjack", inline=False)
            embed.add_field(name="`/mine`", value="Play the mines game", inline=False)

        elif category == 'manage':
            embed = discord.Embed(
                title="⚙️ Management Commands",
                color=discord.Color.dark_gray()
            )
            embed.add_field(
                name="`!sync`",
                value="Push new slash commands to Discord",
                inline=False
            )
            embed.add_field(
                name="`!reload <cog>`",
                value="Reload a specific cog file",
                inline=False
            )
            embed.add_field(
                name="`!load <cog>`",
                value="Load a new cog file",
                inline=False
            )
            embed.add_field(
                name="`!unload <cog>`",
                value="Stop a cog from running",
                inline=False
            )
            embed.set_footer(text="🔒 Owner only commands")

        else:
            await ctx.send("❌ Unknown category! Use `/help` for a list.")
            return

        embed.set_author(
            name=self.bot.user.display_name,
            icon_url=self.bot.user.display_avatar.url
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))
