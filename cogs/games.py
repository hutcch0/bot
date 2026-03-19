import discord
from discord.ext import commands
import random

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.blackjack_games = {}

    def draw_card(self):
        return random.choice(['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'])

    def calculate_score(self, cards):
        values = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10, 'A': 11}
        score = sum(values[card] for card in cards)
        aces = cards.count('A')
        while score > 21 and aces:
            score -= 10
            aces -= 1
        return score

    @commands.command()
    async def blackjack(self, ctx):
        if ctx.author.id in self.blackjack_games: return await ctx.send("Finish your current game!")
        player = [self.draw_card(), self.draw_card()]
        dealer = [self.draw_card()]
        self.blackjack_games[ctx.author.id] = {'player': player, 'dealer': dealer}
        await ctx.send(f"🃏 **Hand:** {player} ({self.calculate_score(player)})\n**Dealer shows:** {dealer}")

    @commands.command()
    async def hit(self, ctx):
        game = self.blackjack_games.get(ctx.author.id)
        if not game: return await ctx.send("No game started.")
        game['player'].append(self.draw_card())
        score = self.calculate_score(game['player'])
        if score > 21:
            await ctx.send(f"💥 Busted! {game['player']} ({score})")
            del self.blackjack_games[ctx.author.id]
        else:
            await ctx.send(f"🃏 New Hand: {game['player']} ({score})")

    @commands.command()
    async def stand(self, ctx):
        game = self.blackjack_games.get(ctx.author.id)
        if not game: return await ctx.send("No game started.")
        while self.calculate_score(game['dealer']) < 17:
            game['dealer'].append(self.draw_card())
        
        ps, ds = self.calculate_score(game['player']), self.calculate_score(game['dealer'])
        result = "Tie!" if ps == ds else ("Win!" if ds > 21 or ps > ds else "Lost!")
        await ctx.send(f"Player: {ps}, Dealer: {ds}. **{result}**")
        del self.blackjack_games[ctx.author.id]

    @commands.command()
    async def slots(self, ctx, bet: int):
        econ = self.bot.get_cog('Economy')
        user = await econ.get_user(ctx.author.id)
        if user['coins'] < bet: return await ctx.send("❌ Not enough coins!")

        symbols = ['🍒', '🍋', '🔔', '🍉', '⭐', '7️⃣']
        res = [random.choice(symbols) for _ in range(3)]
        mult = 5 if len(set(res)) == 1 else (2 if len(set(res)) == 2 else 0)
        
        conn = self.bot.db_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET coins = coins + %s WHERE user_id = %s", ((bet*mult)-bet, ctx.author.id))
        conn.commit()
        cursor.close()
        conn.close()

        await ctx.send(f"🎰 | {' | '.join(res)} | \nResult: {mult}x payout!")

    @commands.command()
    async def mine(self, ctx, bet: int, row: int, col: int):
        econ = self.bot.get_cog('Economy')
        user = await econ.get_user(ctx.author.id)
        if user['coins'] < bet: return await ctx.send("Not enough coins!")
        
        bomb = (random.randint(1,3), random.randint(1,3))
        win = (row, col) != bomb
        change = bet if win else -bet

        conn = self.bot.db_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET coins = coins + %s WHERE user_id = %s", (change, ctx.author.id))
        conn.commit()
        cursor.close()
        conn.close()

        await ctx.send(f"{'🎉 Safe!' if win else '💣 BOOM!'} Reward: {change} coins.")

async def setup(bot):
    await bot.add_cog(Games(bot))
