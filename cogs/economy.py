import discord
from discord.ext import commands, tasks
import random
from datetime import datetime, timedelta

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.coin_value = 50
        self.lottery_tickets = {}
        self.lottery_pot = 0
        self.lottery_price = 100
        self.market_fluctuation.start()

    def get_db(self):
        return self.bot.db_pool.get_connection()

    async def get_user(self, user_id):
        conn = self.get_db()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                cursor.execute("INSERT INTO users (user_id, money, coins) VALUES (%s, 1000, 0)", (user_id,))
                conn.commit()
                return {'user_id': user_id, 'money': 1000, 'coins': 0, 'xp': 0}
            return user
        finally:
            cursor.close()
            conn.close()

    @tasks.loop(minutes=10)
    async def market_fluctuation(self):
        change = random.randint(-15, 15)
        self.coin_value = max(1, min(self.coin_value + change, 250))

    @commands.command()
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user = await self.get_user(member.id)
        embed = discord.Embed(title=f"💰 {member.display_name}'s Balance", color=0x2ecc71)
        embed.add_field(name="Cash", value=f"${user['money']:,}")
        embed.add_field(name="Coins", value=f"🪙 {user['coins']:,}")
        embed.set_footer(text=f"Current Coin Value: ${self.coin_value}")
        await ctx.send(embed=embed)

    @commands.command()
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def work(self, ctx):
        amount = random.randint(50, 200)
        conn = self.get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET money = money + %s WHERE user_id = %s", (amount, ctx.author.id))
            conn.commit()
            await ctx.send(f"✅ You worked and earned **${amount}**!")
        finally:
            cursor.close()
            conn.close()

    @commands.command()
    async def coinvalue(self, ctx):
        await ctx.send(f"📈 The current coin value is **${self.coin_value}**.")

    @commands.command()
    async def buycoin(self, ctx, amount: int):
        user = await self.get_user(ctx.author.id)
        cost = amount * self.coin_value
        if user['money'] < cost:
            return await ctx.send("❌ Not enough money!")
        
        conn = self.get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET money = money - %s, coins = coins + %s WHERE user_id = %s", (cost, amount, ctx.author.id))
            conn.commit()
            await ctx.send(f"✅ Bought {amount} coins for ${cost}!")
        finally:
            cursor.close()
            conn.close()

    @commands.command()
    async def sellcoin(self, ctx, amount: int):
        user = await self.get_user(ctx.author.id)
        if user['coins'] < amount:
            return await ctx.send("❌ Not enough coins!")
        
        gain = amount * self.coin_value
        conn = self.get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET money = money + %s, coins = coins - %s WHERE user_id = %s", (gain, amount, ctx.author.id))
            conn.commit()
            await ctx.send(f"✅ Sold {amount} coins for ${gain}!")
        finally:
            cursor.close()
            conn.close()

    @commands.command()
    async def leaderboard(self, ctx):
        conn = self.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT 10")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        lb = "**🏆 Top 10 Coin Holders**\n"
        for i, (uid, coins) in enumerate(rows, 1):
            lb += f"{i}. <@{uid}> - {coins} coins\n"
        await ctx.send(lb)

    @commands.group(invoke_without_command=True)
    async def lottery(self, ctx):
        embed = discord.Embed(title="🎟️ Current Lottery", color=0x3498db)
        embed.add_field(name="Pot", value=f"{self.lottery_pot} coins")
        embed.add_field(name="Ticket Price", value=f"{self.lottery_price} coins")
        embed.set_footer(text="Use !lottery buy <amount>")
        await ctx.send(embed=embed)

    @lottery.command(name="buy")
    async def lottery_buy(self, ctx, amount: int = 1):
        user = await self.get_user(ctx.author.id)
        cost = amount * self.lottery_price
        if user['coins'] < cost: return await ctx.send("❌ Not enough coins!")

        conn = self.get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET coins = coins - %s WHERE user_id = %s", (cost, ctx.author.id))
        conn.commit()
        cursor.close()
        conn.close()

        self.lottery_tickets[ctx.author.id] = self.lottery_tickets.get(ctx.author.id, 0) + amount
        self.lottery_pot += cost
        await ctx.send(f"🎟️ Bought {amount} tickets!")
        
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.content.startswith('!'):
            return

        user_id = message.author.id
        xp_gain = random.randint(5, 15)

        conn = self.bot.db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                INSERT INTO users (user_id, xp) VALUES (%s, %s) 
                ON DUPLICATE KEY UPDATE xp = xp + %s
            """, (user_id, xp_gain, xp_gain))
            
            cursor.execute("SELECT xp FROM users WHERE user_id = %s", (user_id,))
            res = cursor.fetchone()
            
            new_level = int((res['xp'] / 100) ** 0.5)
            old_level = int(((res['xp'] - xp_gain) / 100) ** 0.5)

            if new_level > old_level:
                await message.channel.send(f"🎊 {message.author.mention} leveled up to **Level {new_level}**!")
            
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    @commands.command()
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user = await self.get_user(member.id)
        
        level = int((user['xp'] / 100) ** 0.5)
        
        embed = discord.Embed(title=f"💰 {member.display_name}'s Profile", color=0x2ecc71)
        embed.add_field(name="Cash", value=f"${user['money']:,}")
        embed.add_field(name="Coins", value=f"🪙 {user['coins']:,}")
        embed.add_field(name="Level", value=f"⭐ {level} ({user['xp']} XP)", inline=False)
        embed.set_footer(text=f"Market Price: ${self.coin_value}")
        await ctx.send(embed=embed)
        
    @commands.command()
    async def xp(self, ctx, member: discord.Member = None):
        """Check your current level and XP progress."""
        member = member or ctx.author
        user = await self.get_user(member.id)
        
        current_xp = user['xp']
        current_level = int((current_xp / 100) ** 0.5)
        
        next_level = current_level + 1
        xp_needed_for_next = (next_level ** 2) * 100
        xp_to_go = xp_needed_for_next - current_xp

        embed = discord.Embed(
            title=f"⭐ {member.display_name}'s Leveling Progress", 
            color=0x3498db
        )
        embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(name="Current Level", value=f"**{current_level}**", inline=True)
        embed.add_field(name="Total XP", value=f"**{current_xp:,}**", inline=True)
        embed.add_field(
            name="Next Level Progress", 
            value=f"You need **{xp_to_go:,}** more XP to reach **Level {next_level}**!", 
            inline=False
        )
        
        percentage = min(100, int((current_xp / xp_needed_for_next) * 100))
        bar_length = 10
        filled_blocks = int(percentage / 10)
        bar = "🟦" * filled_blocks + "⬜" * (bar_length - filled_blocks)
        
        embed.add_field(name="Progress Bar", value=f"{bar} ({percentage}%)", inline=False)
        
        await ctx.send(embed=embed)  

async def setup(bot):
    await bot.add_cog(Economy(bot))
