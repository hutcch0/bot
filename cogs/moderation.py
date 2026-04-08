import discord
from discord.ext import commands
from datetime import datetime, timezone

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.id == self.bot.owner_id:
            return

        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT reason FROM bans WHERE user_id = %s",
                (member.id,)
            )
            row = cursor.fetchone()
            if row:
                try:
                    await member.send(
                        f" You have been automatically banned from "
                        f"**{member.guild.name}**.\n"
                        f"**Reason:** Global Ban - {row[0]}"
                    )
                except discord.Forbidden:
                    pass
                
                await member.ban(reason=f"Global Ban: {row[0]}")
                print(f"🚫 Auto-banned {member} in {member.guild.name} - Global Ban")

        except Exception as e:
            print(f" Error in on_member_join ban check: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    @commands.is_owner()
    async def globalban(self, ctx, user: discord.User, *, reason="No reason provided"):
        """Globally bans a user from all servers. Owner only."""

        if user.id == self.bot.owner_id:
            await ctx.send("❌ You cannot globally ban the bot owner.")
            return
        if user.id == self.bot.user.id:
            await ctx.send("❌ I cannot ban myself.")
            return

        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT user_id FROM bans WHERE user_id = %s",
                (user.id,)
            )
            if cursor.fetchone():
                await ctx.send(f" `{user.name}` is already globally banned.")
                return

            cursor.execute(
                "INSERT INTO bans (user_id, reason, banned_by) VALUES (%s, %s, %s)",
                (user.id, reason, ctx.author.id)
            )
            conn.commit()

            try:
                embed = discord.Embed(
                    title=" You Have Been Globally Banned",
                    color=discord.Color.red()
                )
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(
                    name="Banned By",
                    value=str(ctx.author),
                    inline=False
                )
                await user.send(embed=embed)
            except discord.Forbidden:
                pass

            banned_from = 0
            failed_in = 0

            for guild in self.bot.guilds:
                try:
                    await guild.ban(
                        user,
                        reason=f"Global Ban by {ctx.author}: {reason}"
                    )
                    banned_from += 1
                except discord.Forbidden:
                    print(f" No permission to ban in {guild.name}")
                    failed_in += 1
                except discord.HTTPException as e:
                    print(f" HTTP error banning in {guild.name}: {e}")
                    failed_in += 1

            embed = discord.Embed(
                title="🚫 Global Ban Executed",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="👤 User",
                value=f"{user.mention} (`{user.id}`)",
                inline=False
            )
            embed.add_field(name=" Reason", value=reason, inline=False)
            embed.add_field(
                name=" Results",
                value=f" Banned from {banned_from} server(s)\n Failed in {failed_in} server(s)",
                inline=False
            )
            embed.set_footer(text=f"Banned by {ctx.author}")
            await ctx.send(embed=embed)

        except Exception as e:
            if conn:
                conn.rollback()
            await ctx.send(f" Failed to execute global ban: {e}")
            print(f"Global ban error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    @commands.is_owner()
    async def globalunban(self, ctx, user: discord.User, *, reason="No reason provided"):
        """Removes a global ban. Owner only."""
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT user_id FROM bans WHERE user_id = %s",
                (user.id,)
            )
            if not cursor.fetchone():
                await ctx.send(f" `{user.name}` is not globally banned.")
                return

            cursor.execute(
                "DELETE FROM bans WHERE user_id = %s",
                (user.id,)
            )
            conn.commit()

            unbanned_from = 0
            failed_in = 0

            for guild in self.bot.guilds:
                try:
                    await guild.unban(
                        user,
                        reason=f"Global Unban by {ctx.author}: {reason}"
                    )
                    unbanned_from += 1
                except discord.NotFound:
                    pass
                except discord.Forbidden:
                    print(f" No permission to unban in {guild.name}")
                    failed_in += 1
                except discord.HTTPException as e:
                    print(f" HTTP error unbanning in {guild.name}: {e}")
                    failed_in += 1

            embed = discord.Embed(
                title="✅ Global Unban Executed",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name=" User",
                value=f"{user.mention} (`{user.id}`)",
                inline=False
            )
            embed.add_field(name=" Reason", value=reason, inline=False)
            embed.add_field(
                name=" Results",
                value=f" Unbanned from {unbanned_from} server(s)\n Failed in {failed_in} server(s)",
                inline=False
            )
            embed.set_footer(text=f"Unbanned by {ctx.author}")
            await ctx.send(embed=embed)

        except Exception as e:
            if conn:
                conn.rollback()
            await ctx.send(f"❌ Failed to execute global unban: {e}")
            print(f"Global unban error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    @commands.is_owner()
    async def bans(self, ctx):
        """Lists all globally banned users. Owner only."""
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, reason, timestamp FROM bans ORDER BY timestamp DESC"
            )
            rows = cursor.fetchall()

            if not rows:
                await ctx.send(" No globally banned users.")
                return

            description = ""
            for user_id, reason, timestamp in rows:
                description += f"<@{user_id}> (`{user_id}`)\n {reason}\n\n"

            embed = discord.Embed(
                title=f"🚫 Global Bans ({len(rows)})",
                description=description[:4096],  
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f" Failed to fetch ban list: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Kicks a member from the server."""
        if member.id == ctx.author.id:
            await ctx.send(" You cannot kick yourself.")
            return
        if member.top_role >= ctx.author.top_role:
            await ctx.send(" You cannot kick someone with an equal or higher role.")
            return

        try:
            await member.send(
                f" You have been kicked from **{ctx.guild.name}**.\n"
                f"**Reason:** {reason}"
            )
        except discord.Forbidden:
            pass

        await member.kick(reason=f"Kicked by {ctx.author}: {reason}")

        embed = discord.Embed(
            title=" Member Kicked",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name=" Member",
            value=f"{member.mention} (`{member.id}`)",
            inline=False
        )
        embed.add_field(name=" Reason", value=reason, inline=False)
        embed.set_footer(text=f"Kicked by {ctx.author}")
        await ctx.send(embed=embed)

    @kick.error
    async def kick_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send(" Member not found.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(" You don't have permission to kick members.")

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, minutes: int, *, reason="No reason provided"):
        """Times out a member for a given number of minutes."""
        if member.id == ctx.author.id:
            await ctx.send(" You cannot timeout yourself.")
            return
        if member.top_role >= ctx.author.top_role:
            await ctx.send(" You cannot timeout someone with an equal or higher role.")
            return
        if minutes < 1 or minutes > 40320:
            await ctx.send(" Timeout must be between 1 and 40320 minutes (28 days).")
            return

        until = discord.utils.utcnow() + __import__('datetime').timedelta(minutes=minutes)
        await member.timeout(until, reason=f"Timed out by {ctx.author}: {reason}")

        embed = discord.Embed(
            title="⏱ Member Timed Out",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name=" Member",
            value=f"{member.mention} (`{member.id}`)",
            inline=False
        )
        embed.add_field(name=" Duration", value=f"{minutes} minute(s)", inline=False)
        embed.add_field(name=" Reason", value=reason, inline=False)
        embed.set_footer(text=f"Timed out by {ctx.author}")
        await ctx.send(embed=embed)

    @timeout.error
    async def timeout_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to timeout members.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Usage: `!timeout @user <minutes> <reason>`")


async def setup(bot):
    await bot.add_cog(Moderation(bot))
