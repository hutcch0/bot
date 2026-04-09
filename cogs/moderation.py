import discord
from discord.ext import commands
from datetime import datetime, timezone

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_mod_log(self, ctx, action: str, target, reason: str, color=discord.Color.red()):
        """Sends a log message to the mod log channel."""
        try:
            import json
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            log_channel_id = config.get("MOD_LOG_CHANNEL_ID")
            if not log_channel_id:
                return

            log_channel = self.bot.get_channel(log_channel_id)
            if not log_channel:
                return

            embed = discord.Embed(
                title=f"🔨 {action}",
                color=color,
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="👤 Target",
                value=f"{target.mention} (`{target.id}`)",
                inline=False
            )
            embed.add_field(
                name="🛡️ Moderator",
                value=f"{ctx.author.mention} (`{ctx.author.id}`)",
                inline=False
            )
            embed.add_field(
                name="📝 Reason",
                value=reason or "No reason provided",
                inline=False
            )
            embed.add_field(
                name="📍 Channel",
                value=ctx.channel.mention,
                inline=True
            )
            embed.set_footer(text=f"Action performed in {ctx.guild.name}")

            await log_channel.send(embed=embed)

        except Exception as e:
            print(f"Failed to send mod log: {e}")

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
                        f"🚫 You have been automatically banned from "
                        f"**{member.guild.name}**.\n"
                        f"**Reason:** Global Ban - {row[0]}"
                    )
                except discord.Forbidden:
                    pass
                
                await member.ban(reason=f"Global Ban: {row[0]}")
                print(f"🚫 Auto-banned {member} in {member.guild.name} - Global Ban")

                await self.send_mod_log(
                    ctx=None,  
                    action="Auto-Ban (Global)",
                    target=member,
                    reason=row[0],
                    color=discord.Color.dark_red()
                )

        except Exception as e:
            print(f"Error in on_member_join ban check: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    @commands.is_owner()
    async def globalban(self, ctx, user: discord.User, *, reason="No reason provided"):
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
                await ctx.send(f"⚠️ `{user.name}` is already globally banned.")
                return

            cursor.execute(
                "INSERT INTO bans (user_id, reason, banned_by) VALUES (%s, %s, %s)",
                (user.id, reason, ctx.author.id)
            )
            conn.commit()

            try:
                embed = discord.Embed(
                    title="🚫 You Have Been Globally Banned",
                    color=discord.Color.red()
                )
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Banned By", value=str(ctx.author), inline=False)
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
                    print(f"No permission to ban in {guild.name}")
                    failed_in += 1
                except discord.HTTPException as e:
                    print(f"HTTP error banning in {guild.name}: {e}")
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
            embed.add_field(name="📝 Reason", value=reason, inline=False)
            embed.add_field(
                name="📊 Results",
                value=f"✅ Banned from {banned_from} server(s)\n❌ Failed in {failed_in} server(s)",
                inline=False
            )
            embed.set_footer(text=f"Banned by {ctx.author}")
            await ctx.send(embed=embed)

            await self.send_mod_log(ctx, "Global Ban", user, reason)

        except Exception as e:
            if conn:
                conn.rollback()
            await ctx.send(f"❌ Failed to execute global ban: {e}")
            print(f"Global ban error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    @commands.is_owner()
    async def globalunban(self, ctx, user: discord.User, *, reason="No reason provided"):
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
                await ctx.send(f"⚠️ `{user.name}` is not globally banned.")
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
                    print(f"No permission to unban in {guild.name}")
                    failed_in += 1
                except discord.HTTPException as e:
                    print(f"HTTP error unbanning in {guild.name}: {e}")
                    failed_in += 1

            embed = discord.Embed(
                title="✅ Global Unban Executed",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(
                name="👤 User",
                value=f"{user.mention} (`{user.id}`)",
                inline=False
            )
            embed.add_field(name="📝 Reason", value=reason, inline=False)
            embed.add_field(
                name="📊 Results",
                value=f"✅ Unbanned from {unbanned_from} server(s)\n❌ Failed in {failed_in} server(s)",
                inline=False
            )
            embed.set_footer(text=f"Unbanned by {ctx.author}")
            await ctx.send(embed=embed)

            await self.send_mod_log(ctx, "Global Unban", user, reason, discord.Color.green())

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
                await ctx.send("✅ No globally banned users.")
                return

            description = ""
            for user_id, reason, timestamp in rows:
                description += f"<@{user_id}> (`{user_id}`)\n📝 {reason}\n\n"

            embed = discord.Embed(
                title=f"🚫 Global Bans ({len(rows)})",
                description=description[:4096],
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Failed to fetch ban list: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="No reason provided"):
        if member.id == ctx.author.id:
            await ctx.send("❌ You cannot kick yourself.")
            return
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ You cannot kick someone with an equal or higher role.")
            return

        try:
            await member.send(
                f"👢 You have been kicked from **{ctx.guild.name}**.\n"
                f"**Reason:** {reason}"
            )
        except discord.Forbidden:
            pass

        await member.kick(reason=f"Kicked by {ctx.author}: {reason}")

        embed = discord.Embed(
            title="👢 Member Kicked",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name="👤 Member",
            value=f"{member.mention} (`{member.id}`)",
            inline=False
        )
        embed.add_field(name="📝 Reason", value=reason, inline=False)
        embed.set_footer(text=f"Kicked by {ctx.author}")
        await ctx.send(embed=embed)

        await self.send_mod_log(ctx, "Kick", member, reason, discord.Color.orange())

    @kick.error
    async def kick_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to kick members.")

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, minutes: int, *, reason="No reason provided"):
        if member.id == ctx.author.id:
            await ctx.send("❌ You cannot timeout yourself.")
            return
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ You cannot timeout someone with an equal or higher role.")
            return
        if minutes < 1 or minutes > 40320:
            await ctx.send("❌ Timeout must be between 1 and 40320 minutes (28 days).")
            return

        until = discord.utils.utcnow() + __import__('datetime').timedelta(minutes=minutes)
        await member.timeout(until, reason=f"Timed out by {ctx.author}: {reason}")

        embed = discord.Embed(
            title="⏱️ Member Timed Out",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name="👤 Member",
            value=f"{member.mention} (`{member.id}`)",
            inline=False
        )
        embed.add_field(name="⏱️ Duration", value=f"{minutes} minute(s)", inline=False)
        embed.add_field(name="📝 Reason", value=reason, inline=False)
        embed.set_footer(text=f"Timed out by {ctx.author}")
        await ctx.send(embed=embed)

        await self.send_mod_log(ctx, "Timeout", member, reason, discord.Color.orange())

    @timeout.error
    async def timeout_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to timeout members.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Usage: `!timeout @user <minutes> <reason>`")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        """Delete a number of messages from the channel."""
        if amount <= 0:
            await ctx.send("❌ Amount must be greater than 0.")
            return
        if amount > 100:
            await ctx.send("❌ You can only delete up to 100 messages at once.")
            return

        try:
            deleted = await ctx.channel.purge(limit=amount + 1)
            actual_deleted = len(deleted) - 1

            confirm = await ctx.send(
                f"🗑️ Deleted **{actual_deleted}** message(s).",
                delete_after=3
            )

            await self.send_mod_log(
                ctx,
                "Purge",
                ctx.channel,
                f"Deleted {actual_deleted} messages",
                discord.Color.dark_gray()
            )

        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to delete messages.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to delete messages: {e}")

    @purge.error
    async def purge_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to manage messages.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!purge <amount>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Amount must be a whole number.")

    @commands.command()
    async def report(self, ctx, member: discord.Member, *, reason: str):
        if member.id == ctx.author.id:
            await ctx.send("❌ You cannot report yourself.")
            return
        if member.bot:
            await ctx.send("❌ You cannot report a bot.")
            return

        import json
        with open('config.json', 'r') as f:
            config = json.load(f)

        report_channel = self.bot.get_channel(config["REPORT_CHANNEL_ID"])

        if not report_channel:
            await ctx.send("❌ Report channel not found, please contact an admin.")
            return

        embed = discord.Embed(
            title="🚨 New Report",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="🎯 Reported User", value=f"{member.mention} (`{member.id}`)", inline=False)
        embed.add_field(name="👤 Reported By", value=f"{ctx.author.mention} (`{ctx.author.id}`)", inline=False)
        embed.add_field(name="📝 Reason", value=reason, inline=False)
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
            await ctx.send("❌ Member not found.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!report @user <reason>`")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
