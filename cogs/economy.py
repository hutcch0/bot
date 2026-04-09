import discord
from discord.ext import commands, tasks
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
        """Gets a user from DB, creates them if they dont exist."""
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

    @tasks.loop(minutes=10)
    async def market_fluctuation(self):
        change = random.randint(-15, 15)
        self.coin_value = max(1, min(self.coin_value + change, 250))

    @market_fluctuation.before_loop
    async def before_market(self):
        await self.bot.wait_until_ready()

    @commands.command()
    async def balance(self, ctx, member: discord.Member = None):
        """Shows your balance and level."""
        member = member or ctx.author
        try:
            user = await self.get_user(member.id)
        except Exception:
            await ctx.send("❌ Failed to fetch balance.")
            return

        level = self.get_level(user['xp'])
        xp_needed = self.xp_for_next_level(level)
        xp_to_go = xp_needed - user['xp']

        embed = discord.Embed(
            title=f"💰 {member.display_name}'s Profile",
            color=0x2ecc71
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
        await ctx.send(embed=embed)

    @balance.error
    async def balance_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.")

    @commands.command()
    async def xp(self, ctx, member: discord.Member = None):
        """Shows your XP and level progress."""
        member = member or ctx.author
        try:
            user = await self.get_user(member.id)
        except Exception:
            await ctx.send("❌ Failed to fetch XP.")
            return

        current_xp = user['xp']
        current_level = self.get_level(current_xp)
        xp_needed = self.xp_for_next_level(current_level)
        xp_to_go = xp_needed - current_xp
        percentage = min(100, int((current_xp / xp_needed) * 100))

        filled = int(percentage / 10)
        bar = "🟦" * filled + "⬜" * (10 - filled)

        embed = discord.Embed(
            title=f"⭐ {member.display_name}'s Progress",
            color=0x3498db
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Level", value=f"**{current_level}**", inline=True)
        embed.add_field(name="Total XP", value=f"**{current_xp:,}**", inline=True)
        embed.add_field(
            name="Next Level",
            value=f"**{xp_to_go:,}** XP needed to reach Level **{current_level + 1}**",
            inline=False
        )
        embed.add_field(
            name="Progress",
            value=f"{bar} ({percentage}%)",
            inline=False
        )
        await ctx.send(embed=embed)

    @xp.error
    async def xp_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.")

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
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def work(self, ctx):
        """Work to earn money once per day."""
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
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send("❌ Failed to process work earnings.")
            print(f"Work error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @work.error
    async def work_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            hours, remainder = divmod(int(error.retry_after), 3600)
            minutes, seconds = divmod(remainder, 60)
            await ctx.send(
                f"⏳ You already worked today!\n"
                f"Try again in `{hours}h {minutes}m {seconds}s`"
            )

    @commands.command()
    async def coinvalue(self, ctx):
        """Check the current coin market value."""
        embed = discord.Embed(
            description=f"📈 Current coin value: **${self.coin_value}**",
            color=0x3498db
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def buycoin(self, ctx, amount: int):
        """Buy coins with your cash."""
        if amount <= 0:
            await ctx.send("❌ Amount must be greater than 0.")
            return

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
            """, (cost, amount, ctx.author.id, cost))
            conn.commit()

            if cursor.rowcount == 0:
                await ctx.send("❌ Not enough money!")
                return

            embed = discord.Embed(
                description=f"✅ Bought **{amount:,}** coins for **${cost:,}**!",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            if conn:
                conn.rollback()
            await ctx.send("❌ Failed to buy coins.")
            print(f"Buycoin error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @buycoin.error
    async def buycoin_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!buycoin <amount>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Amount must be a whole number.")

    @commands.command()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def sellcoin(self, ctx, amount: int):
        """Sell coins for cash."""
        if amount <= 0:
            await ctx.send("❌ Amount must be greater than 0.")
            return

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
            """, (gain, amount, ctx.author.id, amount))
            conn.commit()

            if cursor.rowcount == 0:
                await ctx.send("❌ Not enough coins!")
                return

            embed = discord.Embed(
                description=f"✅ Sold **{amount:,}** coins for **${gain:,}**!",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            if conn:
                conn.rollback()
            await ctx.send("❌ Failed to sell coins.")
            print(f"Sellcoin error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @sellcoin.error
    async def sellcoin_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!sellcoin <amount>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Amount must be a whole number.")

    @commands.command()
    async def leaderboard(self, ctx):
        """Shows the top 10 coin holders."""
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
                await ctx.send("⚠️ No users found.")
                return

            embed = discord.Embed(
                title="🏆 Top 10 Coin Holders",
                color=discord.Color.gold()
            )

            medals = ["🥇", "🥈", "🥉"]
            description = ""
            for i, (uid, coins, money) in enumerate(rows, 1):
                medal = medals[i - 1] if i <= 3 else f"`#{i}`"
                description += f"{medal} <@{uid}> — 🪙 {coins:,} coins\n"

            embed.description = description
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send("❌ Failed to fetch leaderboard.")
            print(f"Leaderboard error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @commands.group(invoke_without_command=True)
    async def lottery(self, ctx):
        """Shows current lottery info."""
        try:
            pot, tickets = await self.get_lottery_state()
        except Exception:
            await ctx.send("❌ Failed to fetch lottery info.")
            return

        total_tickets = sum(tickets.values())

        embed = discord.Embed(title="🎟️ Current Lottery", color=0x3498db)
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
        embed.set_footer(text="Use !lottery buy <amount> to enter")
        await ctx.send(embed=embed)

    @lottery.command(name="buy")
    async def lottery_buy(self, ctx, amount: int = 1):
        """Buy lottery tickets."""
        if amount <= 0:
            await ctx.send("❌ Amount must be greater than 0.")
            return

        cost = amount * self.lottery_price
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE users SET coins = coins - %s
                WHERE user_id = %s AND coins >= %s
            """, (cost, ctx.author.id, cost))

            if cursor.rowcount == 0:
                conn.commit()
                await ctx.send("❌ Not enough coins!")
                return

            cursor.execute("""
                INSERT INTO lottery_tickets (user_id, tickets)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE tickets = tickets + %s
            """, (ctx.author.id, amount, amount))

            cursor.execute("""
                INSERT INTO lottery_state (id, pot) VALUES (1, %s)
                ON DUPLICATE KEY UPDATE pot = pot + %s
            """, (cost, cost))

            conn.commit()

            embed = discord.Embed(
                description=f"🎟️ Bought **{amount}** ticket(s) for **{cost:,}** coins!",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            if conn:
                conn.rollback()
            await ctx.send("❌ Failed to buy tickets.")
            print(f"Lottery buy error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @lottery.command(name="draw")
    @commands.is_owner()
    async def lottery_draw(self, ctx):
        """Draws a lottery winner. Owner only."""
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT user_id, tickets FROM lottery_tickets")
            ticket_rows = cursor.fetchall()

            if not ticket_rows:
                await ctx.send("⚠️ No tickets have been bought yet.")
                return

            cursor.execute("SELECT pot FROM lottery_state WHERE id = 1")
            pot_row = cursor.fetchone()
            pot = pot_row['pot'] if pot_row else 0

            if pot == 0:
                await ctx.send("⚠️ The lottery pot is empty.")
                return

            pool = []
            for row in ticket_rows:
                pool.extend([row['user_id']] * row['tickets'])

            winner_id = random.choice(pool)

            cursor.execute("""
                UPDATE users SET coins = coins + %s WHERE user_id = %s
            """, (pot, winner_id))

            cursor.execute("DELETE FROM lottery_tickets")
            cursor.execute(
                "UPDATE lottery_state SET pot = 0 WHERE id = 1"
            )
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
            await ctx.send(embed=embed)

        except Exception as e:
            if conn:
                conn.rollback()
            await ctx.send("❌ Failed to draw lottery.")
            print(f"Lottery draw error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


async def setup(bot):
    await bot.add_cog(Economy(bot))
