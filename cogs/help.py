import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.remove_command('help')

    @commands.command()
    async def help(self, ctx, category: str = None):
        """Shows all commands and categories."""

        if category is None:
            embed = discord.Embed(
                title="📖 Bot Help",
                description=(
                    "Use `!help <category>` to see commands.\n\n"
                    "**Categories:**"
                ),
                color=0x3498db
            )
            embed.add_field(
                name="🔨 Moderation",
                value="`!help mod`",
                inline=True
            )
            embed.add_field(
                name="🛠️ Utility",
                value="`!help utility`",
                inline=True
            )
            embed.add_field(
                name="💰 Economy",
                value="`!help economy`",
                inline=True
            )
            embed.add_field(
                name="🎮 Games",
                value="`!help games`",
                inline=True
            )
            embed.add_field(
                name="⚙️ Management",
                value="`!help manage`",
                inline=True
            )
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")
            await ctx.send(embed=embed)
            return

        category = category.lower()

        if category in ['mod', 'moderation']:
            embed = discord.Embed(
                title="🔨 Moderation Commands",
                color=discord.Color.red()
            )
            embed.add_field(
                name="`!globalban @user [reason]`",
                value="Globally ban a user across all servers",
                inline=False
            )
            embed.add_field(
                name="`!globalunban @user [reason]`",
                value="Globally unban a user across all servers",
                inline=False
            )
            embed.add_field(
                name="`!bans`",
                value="Show the global ban list",
                inline=False
            )
            embed.add_field(
                name="`!kick @user [reason]`",
                value="Kick a user from the server",
                inline=False
            )
            embed.add_field(
                name="`!timeout @user <minutes> [reason]`",
                value="Timeout a user (max 40320 minutes / 28 days)",
                inline=False
            )
            embed.add_field(
                name="`!purge <amount>`",
                value="Delete messages (max 100)",
                inline=False
            )
            embed.add_field(
                name="`!report @user <reason>`",
                value="Report a user to the staff team",
                inline=False
            )
            embed.set_footer(text="🔒 Staff commands require permissions")

        elif category in ['utility', 'util']:
            embed = discord.Embed(
                title="🛠️ Utility Commands",
                color=discord.Color.blurple()
            )
            embed.add_field(
                name="`!uptime`",
                value="Show how long the bot has been online",
                inline=False
            )
            embed.add_field(
                name="`!afk [reason]`",
                value="Set yourself as AFK - removed when you next send a message",
                inline=False
            )
            embed.add_field(
                name="`!userinfo [@user]`",
                value="Show info about a user",
                inline=False
            )
            embed.add_field(
                name="`!serverinfo`",
                value="Show info about the server",
                inline=False
            )
            embed.add_field(
                name="`!social`",
                value="Show community social links",
                inline=False
            )
            embed.add_field(
                name="`!photo`",
                value="Get a random photo",
                inline=False
            )
            embed.set_footer(text="✅ All utility commands are available to everyone")

        elif category in ['economy', 'eco']:
            embed = discord.Embed(
                title="💰 Economy Commands",
                color=discord.Color.green()
            )
            embed.add_field(
                name="`!balance [@user]`",
                value="Show your or another users balance and level",
                inline=False
            )
            embed.add_field(
                name="`!work`",
                value="Work to earn money (once per day)",
                inline=False
            )
            embed.add_field(
                name="`!buycoin <amount>`",
                value="Buy coins with your cash (3s cooldown)",
                inline=False
            )
            embed.add_field(
                name="`!sellcoin <amount>`",
                value="Sell coins for cash (3s cooldown)",
                inline=False
            )
            embed.add_field(
                name="`!coinvalue`",
                value="Check the current coin market value",
                inline=False
            )
            embed.add_field(
                name="`!leaderboard`",
                value="Show the top 10 coin holders",
                inline=False
            )
            embed.add_field(
                name="`!xp [@user]`",
                value="Show your or another users level and XP progress",
                inline=False
            )
            embed.add_field(
                name="`!lottery`",
                value="Show the current lottery pot and ticket price",
                inline=False
            )
            embed.add_field(
                name="`!lottery buy <amount>`",
                value="Buy lottery tickets - more tickets means better odds",
                inline=False
            )
            embed.add_field(
                name="`!daily`",
                value="Claim your daily reward (money, coins, and XP)",
                inline=False
            )
            embed.add_field(
                name="`!pay @user <amount>`",
                value="Send money to another user",
                inline=False
            )
            embed.set_footer(text="💡 Coin value changes every 10 minutes!")

        elif category in ['games', 'game']:
            embed = discord.Embed(
                title="🎮 Games Commands",
                color=discord.Color.purple()
            )
            embed.add_field(
                name="`!blackjack [bet]`",
                value="Start a game of blackjack with an optional coin bet",
                inline=False
            )
            embed.add_field(
                name="`!hit`",
                value="Draw another card in your blackjack game",
                inline=False
            )
            embed.add_field(
                name="`!stand`",
                value="Hold your hand and let the dealer play",
                inline=False
            )
            embed.add_field(
                name="`!slots <bet>`",
                value=(
                    "Spin the slot machine\n"
                    "```\n"
                    "Three of a kind = 5x\n"
                    "Two of a kind   = 2x\n"
                    "No match        = 0x\n"
                    "```"
                ),
                inline=False
            )
            embed.add_field(
                name="`!mine <bet> <row> <col>`",
                value=(
                    "Pick a cell on a 3x3 grid and avoid the bombs\n"
                    "```\n"
                    "Bet under 100  = 1 bomb\n"
                    "Bet under 500  = 2 bombs\n"
                    "Bet 500+       = 3 bombs\n"
                    "```"
                ),
                inline=False
            )
            embed.set_footer(text="⏳ Games have cooldowns to prevent spam")

        elif category in ['manage', 'management', 'admin']:
            if not await self.bot.is_owner(ctx.author):
                await ctx.send("❌ You do not have permission to view this category.")
                return

            embed = discord.Embed(
                title="⚙️ Management Commands",
                color=discord.Color.dark_gray()
            )
            embed.add_field(
                name="`!reload <cog>`",
                value="Reload a specific cog without restarting",
                inline=False
            )
            embed.add_field(
                name="`!load <cog>`",
                value="Load a cog that is not currently loaded",
                inline=False
            )
            embed.add_field(
                name="`!unload <cog>`",
                value="Unload a currently loaded cog",
                inline=False
            )
            embed.add_field(
                name="`!cogs`",
                value="List all currently loaded cogs",
                inline=False
            )
            embed.add_field(
                name="`!stop`",
                value="Safely shut down the bot",
                inline=False
            )
            embed.set_footer(text="🔒 Owner only commands")

        else:
            await ctx.send(
                "❌ Unknown category. Use `!help` to see all categories.\n"
                "Valid categories: `mod`, `utility`, `economy`, `games`, `manage`"
            )
            return

        embed.set_author(
            name=self.bot.user.display_name,
            icon_url=self.bot.user.display_avatar.url
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
