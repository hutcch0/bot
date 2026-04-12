import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
import json

with open('config.json', 'r') as f:
    config = json.load(f)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_mod_log(
        self,
        action: str,
        target,
        reason: str,
        moderator: discord.Member | discord.User = None,
        channel: discord.TextChannel = None,
        guild: discord.Guild = None,
        color=discord.Color.red()
    ):
        """Sends a log message to the mod log channel."""
        try:
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
            if moderator:
                embed.add_field(
                    name="🛡️ Moderator",
                    value=f"{moderator.mention} (`{moderator.id}`)",
                    inline=False
                )
            embed.add_field(
                name="📝 Reason",
                value=reason or "No reason provided",
                inline=False
            )
            if channel:
                embed.add_field(
                    name="📍 Channel",
                    value=channel.mention,
                    inline=True
                )
            if guild:
                embed.set_footer(text=f"Action performed in {guild.name}")

            await log_channel.send(embed=embed)

        except Exception as e:
            print(f"Failed to send mod log: {e}")

    def _check_role_hierarchy(
        self,
        actor: discord.Member,
        target: discord.Member
    ) -> bool:
        """Returns True if actor outranks target or is server owner."""
        if actor.id == actor.guild.owner_id:
            return True
        return actor.top_role > target.top_role

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
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
                print(f"🚫 Auto-banned {member} in {member.guild.name}")

                await self.send_mod_log(
                    action="Auto-Ban (Global)",
                    target=member,
                    reason=row[0],
                    guild=member.guild,
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
        """Globally bans a user from all servers."""
        embed = await self._execute_globalban(user, reason, ctx.author)
        if embed:
            await ctx.send(embed=embed)
            await self.send_mod_log(
                action="Global Ban",
                target=user,
                reason=reason,
                moderator=ctx.author,
                channel=ctx.channel,
                guild=ctx.guild,
                color=discord.Color.red()
            )

    @app_commands.command(name="globalban", description="Globally bans a user from all servers.")
    @app_commands.describe(
        user="The user ID to globally ban.",
        reason="The reason for the global ban."
    )
    @app_commands.default_permissions(administrator=True)
    async def globalban_slash(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str = "No reason provided"
    ):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                "❌ Only the bot owner can use this command.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        embed = await self._execute_globalban(user, reason, interaction.user)
        if embed:
            await interaction.followup.send(embed=embed)
            await self.send_mod_log(
                action="Global Ban",
                target=user,
                reason=reason,
                moderator=interaction.user,
                channel=interaction.channel,
                guild=interaction.guild,
                color=discord.Color.red()
            )

    async def _execute_globalban(
        self,
        user: discord.User,
        reason: str,
        moderator: discord.Member | discord.User
    ):
        """Helper that performs the global ban logic."""
        if user.id == self.bot.owner_id:
            return None
        if user.id == self.bot.user.id:
            return None

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
                return discord.Embed(
                    description=f"⚠️ `{user.name}` is already globally banned.",
                    color=discord.Color.yellow()
                )

            cursor.execute(
                "INSERT INTO bans (user_id, reason, banned_by) VALUES (%s, %s, %s)",
                (user.id, reason, moderator.id)
            )
            conn.commit()

            try:
                dm_embed = discord.Embed(
                    title="🚫 You Have Been Globally Banned",
                    color=discord.Color.red()
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Banned By", value=str(moderator), inline=False)
                await user.send(embed=dm_embed)
            except discord.Forbidden:
                pass

            banned_from = 0
            failed_in = 0

            for guild in self.bot.guilds:
                try:
                    await guild.ban(
                        user,
                        reason=f"Global Ban by {moderator}: {reason}"
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
            embed.set_footer(text=f"Banned by {moderator}")
            return embed

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Global ban error: {e}")
            return discord.Embed(
                description=f"❌ Failed to execute global ban: {e}",
                color=discord.Color.red()
            )
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    @commands.is_owner()
    async def globalunban(self, ctx, user: discord.User, *, reason="No reason provided"):
        """Globally unbans a user from all servers."""
        embed = await self._execute_globalunban(user, reason, ctx.author)
        if embed:
            await ctx.send(embed=embed)
            await self.send_mod_log(
                action="Global Unban",
                target=user,
                reason=reason,
                moderator=ctx.author,
                channel=ctx.channel,
                guild=ctx.guild,
                color=discord.Color.green()
            )

    @app_commands.command(name="globalunban", description="Globally unbans a user from all servers.")
    @app_commands.describe(
        user="The user to globally unban.",
        reason="The reason for the global unban."
    )
    @app_commands.default_permissions(administrator=True)
    async def globalunban_slash(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str = "No reason provided"
    ):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                "❌ Only the bot owner can use this command.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        embed = await self._execute_globalunban(user, reason, interaction.user)
        if embed:
            await interaction.followup.send(embed=embed)
            await self.send_mod_log(
                action="Global Unban",
                target=user,
                reason=reason,
                moderator=interaction.user,
                channel=interaction.channel,
                guild=interaction.guild,
                color=discord.Color.green()
            )

    async def _execute_globalunban(
        self,
        user: discord.User,
        reason: str,
        moderator: discord.Member | discord.User
    ):
        """Helper that performs the global unban logic."""
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
                return discord.Embed(
                    description=f"⚠️ `{user.name}` is not globally banned.",
                    color=discord.Color.yellow()
                )

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
                        reason=f"Global Unban by {moderator}: {reason}"
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
            embed.set_footer(text=f"Unbanned by {moderator}")
            return embed

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Global unban error: {e}")
            return discord.Embed(
                description=f"❌ Failed to execute global unban: {e}",
                color=discord.Color.red()
            )
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    @commands.is_owner()
    async def bans(self, ctx):
        """Lists all globally banned users."""
        embed = await self._fetch_bans_embed()
        await ctx.send(embed=embed)

    @app_commands.command(name="bans", description="Lists all globally banned users.")
    @app_commands.default_permissions(administrator=True)
    async def bans_slash(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                "❌ Only the bot owner can use this command.",
                ephemeral=True
            )
            return

        embed = await self._fetch_bans_embed()
        await interaction.response.send_message(embed=embed)

    async def _fetch_bans_embed(self):
        """Helper to build the global ban list embed."""
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
                return discord.Embed(
                    description="✅ No globally banned users.",
                    color=discord.Color.green()
                )

            description = ""
            for user_id, reason, timestamp in rows:
                description += (
                    f"<@{user_id}> (`{user_id}`)\n"
                    f"📝 {reason}\n\n"
                )

            return discord.Embed(
                title=f"🚫 Global Bans ({len(rows)})",
                description=description[:4096],
                color=discord.Color.red()
            )

        except Exception as e:
            print(f"Bans fetch error: {e}")
            return discord.Embed(
                description=f"❌ Failed to fetch ban list: {e}",
                color=discord.Color.red()
            )
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
            await ctx.send("❌ You cannot kick yourself.")
            return
        if not self._check_role_hierarchy(ctx.author, member):
            await ctx.send("❌ You cannot kick someone with an equal or higher role.")
            return

        embed = await self._execute_kick(member, reason, ctx.author)
        await ctx.send(embed=embed)
        await self.send_mod_log(
            action="Kick",
            target=member,
            reason=reason,
            moderator=ctx.author,
            channel=ctx.channel,
            guild=ctx.guild,
            color=discord.Color.orange()
        )

    @kick.error
    async def kick_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to kick members.")

    @app_commands.command(name="kick", description="Kicks a member from the server.")
    @app_commands.describe(
        member="The member to kick.",
        reason="The reason for the kick."
    )
    @app_commands.default_permissions(kick_members=True)
    async def kick_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided"
    ):
        if member.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You cannot kick yourself.",
                ephemeral=True
            )
            return
        if not self._check_role_hierarchy(interaction.user, member):
            await interaction.response.send_message(
                "❌ You cannot kick someone with an equal or higher role.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        embed = await self._execute_kick(member, reason, interaction.user)
        await interaction.followup.send(embed=embed)
        await self.send_mod_log(
            action="Kick",
            target=member,
            reason=reason,
            moderator=interaction.user,
            channel=interaction.channel,
            guild=interaction.guild,
            color=discord.Color.orange()
        )

    async def _execute_kick(
        self,
        member: discord.Member,
        reason: str,
        moderator: discord.Member | discord.User
    ):
        """Helper that performs the kick logic."""
        try:
            await member.send(
                f"👢 You have been kicked from **{member.guild.name}**.\n"
                f"**Reason:** {reason}"
            )
        except discord.Forbidden:
            pass

        await member.kick(reason=f"Kicked by {moderator}: {reason}")

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
        embed.set_footer(text=f"Kicked by {moderator}")
        return embed

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, minutes: int, *, reason="No reason provided"):
        """Times out a member for a given number of minutes."""
        if member.id == ctx.author.id:
            await ctx.send("❌ You cannot timeout yourself.")
            return
        if not self._check_role_hierarchy(ctx.author, member):
            await ctx.send("❌ You cannot timeout someone with an equal or higher role.")
            return
        if minutes < 1 or minutes > 40320:
            await ctx.send("❌ Timeout must be between 1 and 40320 minutes (28 days).")
            return

        embed = await self._execute_timeout(member, minutes, reason, ctx.author)
        await ctx.send(embed=embed)
        await self.send_mod_log(
            action="Timeout",
            target=member,
            reason=f"{reason} ({minutes} minute(s))",
            moderator=ctx.author,
            channel=ctx.channel,
            guild=ctx.guild,
            color=discord.Color.orange()
        )

    @timeout.error
    async def timeout_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to timeout members.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Usage: `!timeout @user <minutes> [reason]`")

    @app_commands.command(name="timeout", description="Times out a member for a set number of minutes.")
    @app_commands.describe(
        member="The member to timeout.",
        minutes="Duration of the timeout in minutes (1–40320).",
        reason="The reason for the timeout."
    )
    @app_commands.default_permissions(moderate_members=True)
    async def timeout_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: int,
        reason: str = "No reason provided"
    ):
        if member.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You cannot timeout yourself.",
                ephemeral=True
            )
            return
        if not self._check_role_hierarchy(interaction.user, member):
            await interaction.response.send_message(
                "❌ You cannot timeout someone with an equal or higher role.",
                ephemeral=True
            )
            return
        if minutes < 1 or minutes > 40320:
            await interaction.response.send_message(
                "❌ Timeout must be between 1 and 40320 minutes (28 days).",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        embed = await self._execute_timeout(member, minutes, reason, interaction.user)
        await interaction.followup.send(embed=embed)
        await self.send_mod_log(
            action="Timeout",
            target=member,
            reason=f"{reason} ({minutes} minute(s))",
            moderator=interaction.user,
            channel=interaction.channel,
            guild=interaction.guild,
            color=discord.Color.orange()
        )

    async def _execute_timeout(
        self,
        member: discord.Member,
        minutes: int,
        reason: str,
        moderator: discord.Member | discord.User
    ):
        """Helper that performs the timeout logic."""
        until = discord.utils.utcnow() + timedelta(minutes=minutes)
        await member.timeout(until, reason=f"Timed out by {moderator}: {reason}")

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
        embed.set_footer(text=f"Timed out by {moderator}")
        return embed

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        """Deletes a number of messages from the channel."""
        if amount <= 0:
            await ctx.send("❌ Amount must be greater than 0.")
            return
        if amount > 100:
            await ctx.send("❌ You can only delete up to 100 messages at once.")
            return

        try:
            deleted = await ctx.channel.purge(limit=amount + 1)
            actual_deleted = len(deleted) - 1

            await ctx.send(
                f"🗑️ Deleted **{actual_deleted}** message(s).",
                delete_after=3
            )
            await self.send_mod_log(
                action="Purge",
                target=ctx.channel,
                reason=f"Deleted {actual_deleted} messages",
                moderator=ctx.author,
                channel=ctx.channel,
                guild=ctx.guild,
                color=discord.Color.dark_gray()
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

    @app_commands.command(name="purge", description="Deletes a number of messages from the channel.")
    @app_commands.describe(amount="Number of messages to delete (1–100).")
    @app_commands.default_permissions(manage_messages=True)
    async def purge_slash(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            await interaction.response.send_message(
                "❌ Amount must be greater than 0.",
                ephemeral=True
            )
            return
        if amount > 100:
            await interaction.response.send_message(
                "❌ You can only delete up to 100 messages at once.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await interaction.channel.purge(limit=amount)
            await interaction.followup.send(
                f"🗑️ Deleted **{len(deleted)}** message(s).",
                ephemeral=True
            )
            await self.send_mod_log(
                action="Purge",
                target=interaction.channel,
                reason=f"Deleted {len(deleted)} messages",
                moderator=interaction.user,
                channel=interaction.channel,
                guild=interaction.guild,
                color=discord.Color.dark_gray()
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to delete messages.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Failed to delete messages: {e}",
                ephemeral=True
            )

    @commands.command()
    async def report(self, ctx, member: discord.Member, *, reason: str):
        """Reports a member to the mod team."""
        if member.id == ctx.author.id:
            await ctx.send("❌ You cannot report yourself.")
            return
        if member.bot:
            await ctx.send("❌ You cannot report a bot.")
            return

        success = await self._submit_report(member, reason, ctx.author, ctx.channel)
        if success:
            await ctx.send(
                embed=discord.Embed(
                    description="✅ Your report has been submitted.",
                    color=discord.Color.green()
                )
            )
        else:
            await ctx.send("❌ Report channel not found. Please contact an admin.")

    @report.error
    async def report_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!report @user <reason>`")

    @app_commands.command(name="report", description="Reports a member to the mod team.")
    @app_commands.describe(
        member="The member you want to report.",
        reason="The reason for the report."
    )
    async def report_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str
    ):
        if member.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You cannot report yourself.",
                ephemeral=True
            )
            return
        if member.bot:
            await interaction.response.send_message(
                "❌ You cannot report a bot.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        success = await self._submit_report(member, reason, interaction.user, interaction.channel)
        if success:
            await interaction.followup.send(
                embed=discord.Embed(
                    description="✅ Your report has been submitted.",
                    color=discord.Color.green()
                ),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Report channel not found. Please contact an admin.",
                ephemeral=True
            )

    async def _submit_report(
        self,
        target: discord.Member,
        reason: str,
        reporter: discord.Member | discord.User,
        source_channel: discord.TextChannel
    ) -> bool:
        """Helper that sends the report to the report channel. Returns True on success."""
        report_channel = self.bot.get_channel(config["REPORT_CHANNEL_ID"])
        if not report_channel:
            return False

        embed = discord.Embed(
            title="🚨 New Report",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(
            name="🎯 Reported User",
            value=f"{target.mention} (`{target.id}`)",
            inline=False
        )
        embed.add_field(
            name="👤 Reported By",
            value=f"{reporter.mention} (`{reporter.id}`)",
            inline=False
        )
        embed.add_field(name="📝 Reason", value=reason, inline=False)
        embed.set_footer(text=f"Report from #{source_channel.name}")

        await report_channel.send(embed=embed)
        return True


async def setup(bot):
    await bot.add_cog(Moderation(bot))
