import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone
import random

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.coin_value = 50
        self.lottery_price = 100
        self.market_fluctuation.start()

    def cog_unload(self):
        self.market_fluctuation.cancel()

    def get_level(self, xp: int) -> int:
        """Single source of truth for level calculation."""
        return int((xp / 100) ** 0.5)

    def xp_for_next_level(self, level: int) -> int:
        """XP required to reach the next level."""
        return ((level + 1) ** 2) * 100

    async def get_user(self, user_id: int) -> dict:
        """Gets a user from DB, creates them if they don't exist."""
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM users WHERE user_id = %s",
                (user_id,)
            )
            user = cursor.fetchone()
            if not user:
                cursor.execute(
                    "INSERT INTO users (user_id, money, coins, xp) VALUES (%s, 1000, 0, 0)",
                    (user_id,)
                )
                conn.commit()
                return {'user_id': user_id, 'money': 1000, 'coins': 0, 'xp': 0}
            return user
        except Exception as e:
            print(f"❌ get_user error: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    async def get_lottery_state(self) -> tuple[int, dict]:
        """Gets current lottery pot and tickets from DB."""
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT pot FROM lottery_state WHERE id = 1")
            row = cursor.fetchone()
            pot = row['pot'] if row else 0

            cursor.execute("SELECT user_id, tickets FROM lottery_tickets")
            tickets = {r['user_id']: r['tickets'] for r in cursor.fetchall()}

            return pot, tickets
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _build_balance_embed(
        self,
        member: discord.Member | discord.User,
        user: dict
    ) -> discord.Embed:
        """Builds the balance embed. Shared between prefix and slash."""
        level = self.get_level(user['xp'])
        xp_needed = self.xp_for_next_level(level)
        xp_to_go = xp_needed - user['xp']

        embed = discord.Embed(
            title=f"💰 {member.display_name}'s Profile",
            color=0x2ECC71
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="💵 Cash", value=f"${user['money']:,}", inline=True)
        embed.add_field(name="🪙 Coins", value=f"{user['coins']:,}", inline=True)
        embed.add_field(
            name="⭐ Level",
            value=f"Level {level} ({user['xp']:,} XP)\n{xp_to_go:,} XP to next level",
            inline=False
        )
        embed.set_footer(text=f"Market Price: ${self.coin_value} per coin")
        return embed

    def _build_xp_embed(
        self,
        member: discord.Member | discord.User,
        user: dict
    ) -> discord.Embed:
        """Builds the XP embed. Shared between prefix and slash."""
        current_xp = user['xp']
        current_level = self.get_level(current_xp)
        xp_needed = self.xp_for_next_level(current_level)
        xp_to_go = xp_needed - current_xp
        percentage = min(100, int((current_xp / xp_needed) * 100))

        filled = int(percentage / 10)
        bar = "🟦" * filled + "⬜" * (10 - filled)

        embed = discord.Embed(
            title=f"⭐ {member.display_name}'s Progress",
            color=0x3498DB
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🏅 Level", value=f"**{current_level}**", inline=True)
        embed.add_field(name="✨ Total XP", value=f"**{current_xp:,}**", inline=True)
        embed.add_field(
            name="🎯 Next Level",
            value=f"**{xp_to_go:,}** XP needed to reach Level **{current_level + 1}**",
            inline=False
        )
        embed.add_field(
            name="📊 Progress",
            value=f"{bar} ({percentage}%)",
            inline=False
        )
        return embed

    @tasks.loop(minutes=10)
    async def market_fluctuation(self):
        change = random.randint(-15, 15)
        self.coin_value = max(1, min(self.coin_value + change, 250))

    @market_fluctuation.before_loop
    async def before_market(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.content.startswith('!'):
            return

        xp_gain = random.randint(5, 15)
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                INSERT INTO users (user_id, xp) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE xp = xp + %s
            """, (message.author.id, xp_gain, xp_gain))

            cursor.execute(
                "SELECT xp FROM users WHERE user_id = %s",
                (message.author.id,)
            )
            res = cursor.fetchone()
            conn.commit()

            new_level = self.get_level(res['xp'])
            old_level = self.get_level(res['xp'] - xp_gain)

            if new_level > old_level:
                embed = discord.Embed(
                    description=f"🎊 {message.author.mention} leveled up to **Level {new_level}**!",
                    color=discord.Color.gold()
                )
                await message.channel.send(embed=embed)

        except Exception as e:
            print(f"❌ XP gain error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    async def balance(self, ctx, member: discord.Member = None):
        """Shows your balance and level."""
        member = member or ctx.author
        try:
            user = await self.get_user(member.id)
        except Exception:
            await ctx.send("❌ Failed to fetch balance.")
            return
        await ctx.send(embed=self._build_balance_embed(member, user))

    @balance.error
    async def balance_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.")

    @app_commands.command(name="balance", description="Shows your balance and level.")
    @app_commands.describe(member="The member to check. Defaults to yourself.")
    async def balance_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        member = member or interaction.user
        try:
            user = await self.get_user(member.id)
        except Exception:
            await interaction.response.send_message(
                "❌ Failed to fetch balance.",
                ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=self._build_balance_embed(member, user)
        )

    @commands.command()
    async def xp(self, ctx, member: discord.Member = None):
        """Shows your XP and level progress."""
        member = member or ctx.author
        try:
            user = await self.get_user(member.id)
        except Exception:
            await ctx.send("❌ Failed to fetch XP.")
            return
        await ctx.send(embed=self._build_xp_embed(member, user))

    @xp.error
    async def xp_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.")

    @app_commands.command(name="xp", description="Shows your XP and level progress.")
    @app_commands.describe(member="The member to check. Defaults to yourself.")
    async def xp_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        member = member or interaction.user
        try:
            user = await self.get_user(member.id)
        except Exception:
            await interaction.response.send_message(
                "❌ Failed to fetch XP.",
                ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=self._build_xp_embed(member, user)
        )

    @commands.command()
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def work(self, ctx):
        """Work to earn money once per day."""
        embed, error = await self._do_work(ctx.author.id)
        if error:
            await ctx.send(error)
        else:
            await ctx.send(embed=embed)

    @work.error
    async def work_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            hours, remainder = divmod(int(error.retry_after), 3600)
            minutes, seconds = divmod(remainder, 60)
            await ctx.send(
                f"⏳ You already worked today!\n"
                f"Try again in `{hours}h {minutes}m {seconds}s`"
            )

    @app_commands.command(name="work", description="Work to earn money once per day.")
    async def work_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed, error = await self._do_work(interaction.user.id)
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed)

    async def _do_work(self, user_id: int) -> tuple[discord.Embed | None, str | None]:
        """Shared work logic. Returns (embed, None) or (None, error)."""
        amount = random.randint(50, 200)
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (user_id, money) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE money = money + %s
            """, (ctx.author.id, 1000 + amount, amount))
            conn.commit()

            embed = discord.Embed(
                description=f"✅ You worked and earned **${amount}**!",
                color=discord.Color.green()
            )
            return embed, None

        except Exception as e:
            print(f"Work error: {e}")
            return None, "❌ Failed to process work earnings."
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    async def coinvalue(self, ctx):
        """Check the current coin market value."""
        await ctx.send(embed=self._build_coinvalue_embed())

    @app_commands.command(name="coinvalue", description="Check the current coin market value.")
    async def coinvalue_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self._build_coinvalue_embed())

    def _build_coinvalue_embed(self) -> discord.Embed:
        """Builds the coin value embed."""
        return discord.Embed(
            description=f"📈 Current coin value: **${self.coin_value}**",
            color=0x3498DB
        )

    @commands.command()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def buycoin(self, ctx, amount: int):
        """Buy coins with your cash."""
        if amount <= 0:
            await ctx.send("❌ Amount must be greater than 0.")
            return

        embed, error = await self._buy_coin(ctx.author.id, amount)
        if error:
            await ctx.send(error)
        else:
            await ctx.send(embed=embed)

    @buycoin.error
    async def buycoin_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!buycoin <amount>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Amount must be a whole number.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Slow down! Try again in {error.retry_after:.1f}s.")

    @app_commands.command(name="buycoin", description="Buy coins with your cash.")
    @app_commands.describe(amount="How many coins to buy.")
    async def buycoin_slash(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            await interaction.response.send_message(
                "❌ Amount must be greater than 0.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        embed, error = await self._buy_coin(interaction.user.id, amount)
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed)

    async def _buy_coin(
        self,
        user_id: int,
        amount: int
    ) -> tuple[discord.Embed | None, str | None]:
        """Shared buy coin logic. Returns (embed, None) or (None, error)."""
        cost = amount * self.coin_value
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET money = money - %s, coins = coins + %s
                WHERE user_id = %s AND money >= %s
            """, (cost, amount, user_id, cost))
            conn.commit()

            if cursor.rowcount == 0:
                return None, "❌ Not enough money!"

            embed = discord.Embed(
                description=f"✅ Bought **{amount:,}** coins for **${cost:,}**!",
                color=discord.Color.green()
            )
            return embed, None

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Buycoin error: {e}")
            return None, "❌ Failed to buy coins."
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def sellcoin(self, ctx, amount: int):
        """Sell coins for cash."""
        if amount <= 0:
            await ctx.send("❌ Amount must be greater than 0.")
            return

        embed, error = await self._sell_coin(ctx.author.id, amount)
        if error:
            await ctx.send(error)
        else:
            await ctx.send(embed=embed)

    @sellcoin.error
    async def sellcoin_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!sellcoin <amount>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Amount must be a whole number.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Slow down! Try again in {error.retry_after:.1f}s.")

    @app_commands.command(name="sellcoin", description="Sell your coins for cash.")
    @app_commands.describe(amount="How many coins to sell.")
    async def sellcoin_slash(self, interaction: discord.Interaction, amount: int):
        if amount <= 0:
            await interaction.response.send_message(
                "❌ Amount must be greater than 0.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        embed, error = await self._sell_coin(interaction.user.id, amount)
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed)

    async def _sell_coin(
        self,
        user_id: int,
        amount: int
    ) -> tuple[discord.Embed | None, str | None]:
        """Shared sell coin logic. Returns (embed, None) or (None, error)."""
        gain = amount * self.coin_value
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET money = money + %s, coins = coins - %s
                WHERE user_id = %s AND coins >= %s
            """, (gain, amount, user_id, amount))
            conn.commit()

            if cursor.rowcount == 0:
                return None, "❌ Not enough coins!"

            embed = discord.Embed(
                description=f"✅ Sold **{amount:,}** coins for **${gain:,}**!",
                color=discord.Color.green()
            )
            return embed, None

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Sellcoin error: {e}")
            return None, "❌ Failed to sell coins."
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    async def leaderboard(self, ctx):
        """Shows the top 10 coin holders."""
        embed, error = await self._fetch_leaderboard(ctx.author.display_name)
        if error:
            await ctx.send(error)
        else:
            await ctx.send(embed=embed)

    @app_commands.command(name="leaderboard", description="Shows the top 10 coin holders.")
    async def leaderboard_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed, error = await self._fetch_leaderboard(interaction.user.display_name)
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed)

    async def _fetch_leaderboard(
        self,
        requester_name: str
    ) -> tuple[discord.Embed | None, str | None]:
        """Shared leaderboard logic. Returns (embed, None) or (None, error)."""
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, coins, money FROM users ORDER BY coins DESC LIMIT 10"
            )
            rows = cursor.fetchall()

            if not rows:
                return discord.Embed(
                    description="⚠️ No users found.",
                    color=discord.Color.yellow()
                ), None

            medals = ["🥇", "🥈", "🥉"]
            description = ""
            for i, (uid, coins, money) in enumerate(rows, 1):
                medal = medals[i - 1] if i <= 3 else f"`#{i}`"
                description += f"{medal} <@{uid}> — 🪙 {coins:,} coins\n"

            embed = discord.Embed(
                title="🏆 Top 10 Coin Holders",
                description=description,
                color=discord.Color.gold()
            )
            embed.set_footer(text=f"Requested by {requester_name}")
            return embed, None

        except Exception as e:
            print(f"Leaderboard error: {e}")
            return None, "❌ Failed to fetch leaderboard."
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.group(invoke_without_command=True)
    async def lottery(self, ctx):
        """Shows current lottery info."""
        embed, error = await self._fetch_lottery_info()
        if error:
            await ctx.send(error)
        else:
            await ctx.send(embed=embed)

    @lottery.command(name="buy")
    async def lottery_buy(self, ctx, amount: int = 1):
        """Buy lottery tickets."""
        if amount <= 0:
            await ctx.send("❌ Amount must be greater than 0.")
            return

        embed, error = await self._buy_tickets(ctx.author.id, amount)
        if error:
            await ctx.send(error)
        else:
            await ctx.send(embed=embed)

    @lottery.command(name="draw")
    @commands.is_owner()
    async def lottery_draw(self, ctx):
        """Draws a lottery winner. Owner only."""
        embed, error = await self._draw_lottery()
        if error:
            await ctx.send(error)
        else:
            await ctx.send(embed=embed)

    lottery_group = app_commands.Group(
        name="lottery",
        description="Lottery commands."
    )

    @lottery_group.command(name="info", description="Shows the current lottery pot and ticket info.")
    async def lottery_info_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed, error = await self._fetch_lottery_info()
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed)

    @lottery_group.command(name="buy", description="Buy lottery tickets with coins.")
    @app_commands.describe(amount="How many tickets to buy. Defaults to 1.")
    async def lottery_buy_slash(self, interaction: discord.Interaction, amount: int = 1):
        if amount <= 0:
            await interaction.response.send_message(
                "❌ Amount must be greater than 0.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        embed, error = await self._buy_tickets(interaction.user.id, amount)
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed)

    @lottery_group.command(name="draw", description="Draw a lottery winner. Owner only.")
    async def lottery_draw_slash(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                "❌ Only the bot owner can draw the lottery.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        embed, error = await self._draw_lottery()
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed)

    async def _fetch_lottery_info(self) -> tuple[discord.Embed | None, str | None]:
        """Shared lottery info logic. Returns (embed, None) or (None, error)."""
        try:
            pot, tickets = await self.get_lottery_state()
        except Exception:
            return None, "❌ Failed to fetch lottery info."

        total_tickets = sum(tickets.values())

        embed = discord.Embed(title="🎟️ Current Lottery", color=0x3498DB)
        embed.add_field(name="🪙 Pot", value=f"{pot:,} coins", inline=True)
        embed.add_field(
            name="🎫 Ticket Price",
            value=f"{self.lottery_price:,} coins",
            inline=True
        )
        embed.add_field(
            name="🎟️ Total Tickets Sold",
            value=f"{total_tickets:,}",
            inline=True
        )
        embed.set_footer(text="Use /lottery buy to enter")
        return embed, None

    async def _buy_tickets(
        self,
        user_id: int,
        amount: int
    ) -> tuple[discord.Embed | None, str | None]:
        """Shared ticket buying logic. Returns (embed, None) or (None, error)."""
        cost = amount * self.lottery_price
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE users SET coins = coins - %s
                WHERE user_id = %s AND coins >= %s
            """, (cost, user_id, cost))

            if cursor.rowcount == 0:
                conn.commit()
                return None, "❌ Not enough coins!"

            cursor.execute("""
                INSERT INTO lottery_tickets (user_id, tickets)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE tickets = tickets + %s
            """, (user_id, amount, amount))

            cursor.execute("""
                INSERT INTO lottery_state (id, pot) VALUES (1, %s)
                ON DUPLICATE KEY UPDATE pot = pot + %s
            """, (cost, cost))

            conn.commit()

            embed = discord.Embed(
                description=f"🎟️ Bought **{amount}** ticket(s) for **{cost:,}** coins!",
                color=discord.Color.green()
            )
            return embed, None

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Lottery buy error: {e}")
            return None, "❌ Failed to buy tickets."
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    async def _draw_lottery(self) -> tuple[discord.Embed | None, str | None]:
        """Shared lottery draw logic. Returns (embed, None) or (None, error)."""
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT user_id, tickets FROM lottery_tickets")
            ticket_rows = cursor.fetchall()

            if not ticket_rows:
                return None, "⚠️ No tickets have been bought yet."

            cursor.execute("SELECT pot FROM lottery_state WHERE id = 1")
            pot_row = cursor.fetchone()
            pot = pot_row['pot'] if pot_row else 0

            if pot == 0:
                return None, "⚠️ The lottery pot is empty."

            pool = []
            for row in ticket_rows:
                pool.extend([row['user_id']] * row['tickets'])

            winner_id = random.choice(pool)

            cursor.execute(
                "UPDATE users SET coins = coins + %s WHERE user_id = %s",
                (pot, winner_id)
            )
            cursor.execute("DELETE FROM lottery_tickets")
            cursor.execute("UPDATE lottery_state SET pot = 0 WHERE id = 1")
            conn.commit()

            winner = self.bot.get_user(winner_id)
            winner_name = winner.mention if winner else f"<@{winner_id}>"

            embed = discord.Embed(
                title="🎉 Lottery Draw!",
                description=(
                    f"🏆 Winner: {winner_name}\n"
                    f"🪙 Prize: **{pot:,}** coins"
                ),
                color=discord.Color.gold()
            )
            return embed, None

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Lottery draw error: {e}")
            return None, "❌ Failed to draw lottery."
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily(self, ctx):
        """Claim your daily reward."""
        embed, error = await self._claim_daily(ctx.author.id)
        if error:
            await ctx.send(error)
        else:
            await ctx.send(embed=embed)

    @daily.error
    async def daily_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            hours = int(error.retry_after // 3600)
            minutes = int((error.retry_after % 3600) // 60)
            await ctx.send(
                f"⏳ You've already claimed your daily reward today.\n"
                f"Come back in **{hours}h {minutes}m**."
            )

    @app_commands.command(name="daily", description="Claim your daily reward.")
    async def daily_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed, error = await self._claim_daily(interaction.user.id)
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed)

    async def _claim_daily(
        self,
        user_id: int
    ) -> tuple[discord.Embed | None, str | None]:
        """Shared daily claim logic. Returns (embed, None) or (None, error)."""
        reward_money = random.randint(150, 400)
        reward_coins = random.randint(8, 25)
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (user_id, money, coins)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    money = money + %s,
                    coins = coins + %s
            """, (user_id, reward_money, reward_coins, reward_money, reward_coins))
            conn.commit()

            embed = discord.Embed(
                title="🎁 Daily Reward Claimed!",
                description=(
                    f"You received **${reward_money:,}** and **{reward_coins}** coins!"
                ),
                color=discord.Color.gold()
            )
            return embed, None

        except Exception as e:
            print(f"Daily error: {e}")
            return None, "❌ Failed to claim daily reward."
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def pay(self, ctx, member: discord.Member, amount: int):
        """Pay another user some money."""
        if member.id == ctx.author.id:
            await ctx.send("❌ You cannot pay yourself.")
            return
        if amount <= 0:
            await ctx.send("❌ Amount must be greater than 0.")
            return
        if amount > 100000:
            await ctx.send("❌ Maximum transfer is $100,000.")
            return

        embed, error = await self._transfer_money(ctx.author, member, amount)
        if error:
            await ctx.send(error)
        else:
            await ctx.send(embed=embed)

    @app_commands.command(name="pay", description="Pay another user some money.")
    @app_commands.describe(
        member="The member to pay.",
        amount="Amount of money to transfer."
    )
    async def pay_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int
    ):
        if member.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You cannot pay yourself.",
                ephemeral=True
            )
            return
        if amount <= 0:
            await interaction.response.send_message(
                "❌ Amount must be greater than 0.",
                ephemeral=True
            )
            return
        if amount > 100000:
            await interaction.response.send_message(
                "❌ Maximum transfer is $100,000.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        embed, error = await self._transfer_money(interaction.user, member, amount)
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed)

    async def _transfer_money(
        self,
        sender: discord.Member | discord.User,
        receiver: discord.Member | discord.User,
        amount: int
    ) -> tuple[discord.Embed | None, str | None]:
        """Shared pay logic. Returns (embed, None) or (None, error)."""
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE users SET money = money - %s
                WHERE user_id = %s AND money >= %s
            """, (amount, sender.id, amount))

            if cursor.rowcount == 0:
                return None, "❌ You don't have enough money!"

            cursor.execute("""
                INSERT INTO users (user_id, money)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE money = money + %s
            """, (receiver.id, amount, amount))

            conn.commit()

            embed = discord.Embed(
                title="💸 Money Transferred",
                color=discord.Color.green()
            )
            embed.add_field(name="📤 From", value=sender.mention, inline=True)
            embed.add_field(name="📥 To", value=receiver.mention, inline=True)
            embed.add_field(name="💵 Amount", value=f"${amount:,}", inline=False)
            return embed, None

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Pay error: {e}")
            return None, "❌ Transfer failed."
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


async def setup(bot):
    await bot.add_cog(Economy(bot))
