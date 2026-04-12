import discord
from discord.ext import commands
from discord import app_commands
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
        await ctx.send(embed=self._build_uptime_embed())

    @app_commands.command(name="uptime", description="Shows how long the bot has been online.")
    async def uptime_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self._build_uptime_embed())

    def _build_uptime_embed(self):
        """Helper to build the uptime embed."""
        delta = datetime.now(timezone.utc) - self.bot.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        embed = discord.Embed(
            title="⏱️ Bot Uptime",
            description=f"`{days}d {hours}h {minutes}m {seconds}s`",
            color=discord.Color.blurple()
        )
        return embed

    @commands.command()
    async def afk(self, ctx, *, reason="AFK"):
        """Sets your AFK status."""
        embed = await self._set_afk(ctx.author, reason)
        if embed:
            self.recent_afk_triggers[ctx.author.id] = datetime.now(timezone.utc)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to set AFK status.")

    @app_commands.command(name="afk", description="Sets your AFK status.")
    @app_commands.describe(reason="The reason you are going AFK.")
    async def afk_slash(self, interaction: discord.Interaction, reason: str = "AFK"):
        embed = await self._set_afk(interaction.user, reason)
        if embed:
            self.recent_afk_triggers[interaction.user.id] = datetime.now(timezone.utc)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Failed to set AFK status.", ephemeral=True)

    async def _set_afk(self, user: discord.User | discord.Member, reason: str):
        """Helper to insert/update AFK in the database."""
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
            """, (user.id, reason, datetime.now(timezone.utc)))
            conn.commit()

            embed = discord.Embed(
                description=f"💤 {user.mention} is now AFK: {reason}",
                color=discord.Color.yellow()
            )
            return embed

        except Exception as e:
            print(f"AFK Error: {e}")
            return None
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
            elapsed = (
                datetime.now(timezone.utc) - self.recent_afk_triggers[message.author.id]
            ).total_seconds()
            if elapsed < 5:
                return

        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT reason FROM afk_users WHERE user_id = %s",
                (message.author.id,)
            )
            if cursor.fetchone():
                cursor.execute(
                    "DELETE FROM afk_users WHERE user_id = %s",
                    (message.author.id,)
                )
                conn.commit()
                self.recent_afk_triggers.pop(message.author.id, None)
                await message.channel.send(
                    f"✅ Welcome back {message.author.mention}! Your AFK status has been removed.",
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
                            f"💤 **{user.display_name}** is currently AFK\n"
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
        await ctx.send(embed=self._build_userinfo_embed(member, ctx.author))

    @userinfo.error
    async def userinfo_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.")

    @app_commands.command(name="userinfo", description="Shows information about a user.")
    @app_commands.describe(member="The member to get info about. Defaults to yourself.")
    async def userinfo_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        member = member or interaction.user
        await interaction.response.send_message(
            embed=self._build_userinfo_embed(member, interaction.user)
        )

    def _build_userinfo_embed(
        self,
        member: discord.Member,
        requester: discord.Member | discord.User
    ):
        """Helper to build the userinfo embed."""
        roles = [role.mention for role in member.roles[1:]]
        roles_display = ", ".join(roles) if roles else "None"

        embed = discord.Embed(
            title=f"👤 {member.display_name}",
            color=member.color if member.color.value else discord.Color.blurple()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🆔 User ID", value=member.id, inline=True)
        embed.add_field(name="🤖 Bot", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(
            name="📅 Account Created",
            value=member.created_at.strftime("%Y-%m-%d"),
            inline=True
        )
        embed.add_field(
            name="📥 Joined Server",
            value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "Unknown",
            inline=True
        )
        embed.add_field(name="🏆 Top Role", value=member.top_role.mention, inline=True)
        embed.add_field(
            name=f"🎭 Roles ({len(roles)})",
            value=roles_display[:1024],
            inline=False
        )
        embed.set_footer(text=f"Requested by {requester.display_name}")
        return embed

    @commands.command()
    async def serverinfo(self, ctx):
        """Shows information about the server."""
        await ctx.send(embed=self._build_serverinfo_embed(ctx.guild, ctx.author))

    @app_commands.command(name="serverinfo", description="Shows information about the server.")
    async def serverinfo_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=self._build_serverinfo_embed(interaction.guild, interaction.user)
        )

    def _build_serverinfo_embed(
        self,
        guild: discord.Guild,
        requester: discord.Member | discord.User
    ):
        """Helper to build the serverinfo embed."""
        embed = discord.Embed(
            title=f"🏠 {guild.name}",
            color=0x3498DB
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="🆔 Server ID", value=guild.id, inline=True)
        embed.add_field(name="👥 Members", value=guild.member_count, inline=True)
        embed.add_field(name="📢 Channels", value=len(guild.channels), inline=True)
        embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
        embed.add_field(
            name="📅 Created",
            value=guild.created_at.strftime("%Y-%m-%d"),
            inline=True
        )
        embed.set_footer(text=f"Requested by {requester.display_name}")
        return embed

    @commands.command()
    async def photo(self, ctx):
        """Sends a random photo from the photo.json file."""
        embed = self._build_photo_embed()
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ No photos found or error loading photos.")

    @app_commands.command(name="photo", description="Sends a random photo.")
    async def photo_slash(self, interaction: discord.Interaction):
        embed = self._build_photo_embed()
        if embed:
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "❌ No photos found or error loading photos.",
                ephemeral=True
            )

    def _build_photo_embed(self):
        """Helper to pick a random photo and build an embed."""
        try:
            with open('photo.json', 'r') as f:
                photos = json.load(f)
            if not photos:
                return None

            link = random.choice(list(photos.values()))
            embed = discord.Embed(title="🖼️ Random Photo")
            embed.set_image(url=link)
            return embed
        except Exception as e:
            print(f"Photo command error: {e}")
            return None

    @commands.command()
    async def social(self, ctx):
        """Shows social media links."""
        await ctx.send(embed=self._build_social_embed())

    @app_commands.command(name="social", description="Shows social media links.")
    async def social_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self._build_social_embed())

    def _build_social_embed(self):
        """Helper to build the social embed."""
        embed = discord.Embed(
            title="🌐 Socials",
            description=(
                "🌍 [Website](https://hutcch.neocities.org/html/Links-Page)\n"
                "▶ [YouTube](https://www.youtube.com/channel/UCbhfUDBi3YEXRTJGI5EXtQQ)"
            ),
            color=0x3498DB
        )
        return embed

async def setup(bot):
    await bot.add_cog(Utility(bot))
