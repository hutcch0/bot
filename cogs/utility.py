import discord
from discord.ext import commands
from datetime import datetime, timezone
import json
import random

with open('config.json', 'r') as f:
    config = json.load(f)

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.recent_afk_triggers = {}

    @commands.command()
    async def uptime(self, ctx):
        """Shows how long the bot has been online."""
        delta = datetime.now(timezone.utc) - self.bot.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        await ctx.send(
            f" **Uptime:** "
            f"`{days}d {hours}h {minutes}m {seconds}s`"
        )

    @commands.command()
    async def afk(self, ctx, *, reason="AFK"):
        """Sets your AFK status."""
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO afk_users (user_id, reason, timestamp)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    reason = VALUES(reason),
                    timestamp = VALUES(timestamp)
            """, (ctx.author.id, reason, datetime.now(timezone.utc)))
            conn.commit()
            
            self.recent_afk_triggers[ctx.author.id] = datetime.now(timezone.utc)

            embed = discord.Embed(
                description=f" {ctx.author.mention} is now AFK: {reason}",
                color=discord.Color.yellow()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(" Failed to set AFK status.")
            print(f"AFK Error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.author.id in self.recent_afk_triggers:
            elapsed = (datetime.now(timezone.utc) - self.recent_afk_triggers[message.author.id]).total_seconds()
            if elapsed < 5:
                return

        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT reason FROM afk_users WHERE user_id = %s", (message.author.id,))
            if cursor.fetchone():
                cursor.execute("DELETE FROM afk_users WHERE user_id = %s", (message.author.id,))
                conn.commit()
                await message.channel.send(
                    f"✅ Welcome back {message.author.mention}! AFK status removed.",
                    delete_after=5
                )

            for user in message.mentions:
                cursor.execute(
                    "SELECT reason, timestamp FROM afk_users WHERE user_id = %s",
                    (user.id,)
                )
                row = cursor.fetchone()
                if row:
                    reason, timestamp = row
                    embed = discord.Embed(
                        description=(
                            f" **{user.display_name}** is AFK\n"
                            f"**Reason:** {reason}\n"
                            f"**Since:** {timestamp.strftime('%Y-%m-%d %H:%M')} UTC"
                        ),
                        color=discord.Color.yellow()
                    )
                    await message.channel.send(embed=embed)

        except Exception as e:
            print(f"AFK on_message Error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        """Shows information about a user."""
        member = member or ctx.author

        roles = [role.mention for role in member.roles[1:]]
        roles_display = ", ".join(roles) if roles else "None"

        embed = discord.Embed(
            title=f" {member.display_name}",
            color=member.color if member.color.value else discord.Color.blurple()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name=" User ID",
            value=member.id,
            inline=True
        )
        embed.add_field(
            name="🤖 Bot",
            value="Yes" if member.bot else "No",
            inline=True
        )
        embed.add_field(
            name=" Account Created",
            value=member.created_at.strftime("%Y-%m-%d"),
            inline=True
        )
        embed.add_field(
            name=" Joined Server",
            value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "Unknown",
            inline=True
        )
        embed.add_field(
            name=" Top Role",
            value=member.top_role.mention,
            inline=True
        )
        embed.add_field(
            name=f" Roles ({len(roles)})",
            value=roles_display[:1024],
            inline=False
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @userinfo.error
    async def userinfo_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send(" Member not found.")

    @commands.command()
    async def serverinfo(self, ctx):
        """Shows information about the server."""
        guild = ctx.guild

        embed = discord.Embed(
            title=f" {guild.name}",
            color=0x3498db
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name=" Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name=" Server ID", value=guild.id, inline=True)
        embed.add_field(name=" Members", value=guild.member_count, inline=True)
        embed.add_field(name=" Channels", value=len(guild.channels), inline=True)
        embed.add_field(name=" Roles", value=len(guild.roles), inline=True)
        embed.add_field(
            name=" Created",
            value=guild.created_at.strftime("%Y-%m-%d"),
            inline=True
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.command()
    async def photo(self, ctx):
        """Sends a random photo."""
        try:
            with open('photo.json', 'r') as f:
                photos = json.load(f)

            if not photos:
                await ctx.send(" No photos available.")
                return

            await ctx.send(random.choice(list(photos.values())))

        except FileNotFoundError:
            await ctx.send(" Photo list not found.")
        except json.JSONDecodeError:
            await ctx.send(" Photo list is corrupted.")

    @commands.command()
    async def social(self, ctx):
        """Shows social media links."""
        embed = discord.Embed(
            title=" Socials",
            description=(
                " [Website](https://hutcch.neocities.org/html/Links-Page)\n"
                "▶ [YouTube](https://www.youtube.com/channel/UCbhfUDBi3YEXRTJGI5EXtQQ)"
            ),
            color=0x3498db
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def report(self, ctx, member: discord.Member, *, reason: str):
        """Reports a user to the moderators."""

        if member.id == ctx.author.id:
            await ctx.send(" You cannot report yourself.")
            return

        if member.bot:
            await ctx.send(" You cannot report a bot.")
            return

        report_channel = self.bot.get_channel(config["REPORT_CHANNEL_ID"])

        if not report_channel:
            await ctx.send(" Report channel not found, please contact an admin.")
            return

        embed = discord.Embed(
            title=" New Report",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name=" Reported User", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.add_field(name=" Reported By", value=f"{ctx.author.mention} (`{ctx.author.id}`)", inline=False)
        embed.add_field(name=" Reason", value=reason, inline=False)
        embed.set_footer(text=f"Report from #{ctx.channel.name}")

        await report_channel.send(embed=embed)

        confirm = discord.Embed(
            description="✅ Your report has been submitted.",
            color=discord.Color.green()
        )
        await ctx.send(embed=confirm)

    @report.error
    async def report_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send(" Member not found.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!report @user <reason>`")


async def setup(bot):
    await bot.add_cog(Utility(bot))
