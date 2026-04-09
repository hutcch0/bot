import discord
from discord.ext import commands
import random

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.blackjack_games = {}

    def get_economy(self):
        econ = self.bot.get_cog('Economy')
        if not econ:
            raise RuntimeError("Economy cog is not loaded.")
        return econ

    def draw_card(self) -> str:
        return random.choice([
            'A', '2', '3', '4', '5', '6', '7',
            '8', '9', '10', 'J', 'Q', 'K'
        ])

    def calculate_score(self, cards: list) -> int:
        values = {
            '2': 2, '3': 3, '4': 4, '5': 5, '6': 6,
            '7': 7, '8': 8, '9': 9, '10': 10,
            'J': 10, 'Q': 10, 'K': 10, 'A': 11
        }
        score = sum(values[card] for card in cards)
        aces = cards.count('A')
        while score > 21 and aces:
            score -= 10
            aces -= 1
        return score

    def hand_display(self, cards: list) -> str:
        return " | ".join(f"`{c}`" for c in cards)

    def build_blackjack_embed(self, ctx, game: dict, title: str, color, result_text: str = None) -> discord.Embed:
        player_score = self.calculate_score(game['player'])
        dealer_score = self.calculate_score(game['dealer'])

        embed = discord.Embed(title=f"🃏 Blackjack — {title}", color=color)
        embed.add_field(
            name=f"Your Hand ({player_score})",
            value=self.hand_display(game['player']),
            inline=False
        )
        embed.add_field(
            name=f"Dealer's Hand ({dealer_score})",
            value=self.hand_display(game['dealer']),
            inline=False
        )
        if game.get('bet', 0) > 0:
            embed.add_field(
                name="💰 Bet",
                value=f"{game['bet']:,} coins",
                inline=True
            )
        if result_text:
            embed.add_field(name="Result", value=result_text, inline=False)
        embed.set_footer(text=f"Player: {ctx.author.display_name}")
        return embed

    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def blackjack(self, ctx, bet: int = 0):
        """Start a game of blackjack. Optionally bet coins."""
        if ctx.author.id in self.blackjack_games:
            await ctx.send("⚠️ You already have a game running! Use `!hit` or `!stand`.")
            return

        if bet < 0:
            await ctx.send("❌ Bet cannot be negative.")
            return

        if bet > 0:
            conn = None
            cursor = None
            try:
                conn = self.bot.db_pool.get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users SET coins = coins - %s
                    WHERE user_id = %s AND coins >= %s
                """, (bet, ctx.author.id, bet))
                conn.commit()

                if cursor.rowcount == 0:
                    await ctx.send("❌ Not enough coins to place that bet.")
                    return
            except Exception as e:
                if conn:
                    conn.rollback()
                await ctx.send("❌ Failed to place bet.")
                print(f"Blackjack bet error: {e}")
                return
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()

        player = [self.draw_card(), self.draw_card()]
        dealer = [self.draw_card()]

        self.blackjack_games[ctx.author.id] = {
            'player': player,
            'dealer': dealer,
            'bet': bet
        }

        if self.calculate_score(player) == 21:
            winnings = int(bet * 1.5) if bet > 0 else 0
            await self._end_blackjack(ctx, win=True, winnings=winnings, reason="Blackjack! 🎉")
            return

        embed = self.build_blackjack_embed(
            ctx,
            self.blackjack_games[ctx.author.id],
            "Your Turn",
            discord.Color.blurple()
        )
        embed.set_footer(text="Use !hit to draw or !stand to hold")
        await ctx.send(embed=embed)

    @commands.command()
    async def hit(self, ctx):
        """Draw another card in blackjack."""
        game = self.blackjack_games.get(ctx.author.id)
        if not game:
            await ctx.send("❌ No active blackjack game. Use `!blackjack` to start.")
            return

        game['player'].append(self.draw_card())
        score = self.calculate_score(game['player'])

        if score > 21:
            embed = self.build_blackjack_embed(
                ctx, game, "Busted! 💥",
                discord.Color.red(),
                f"You busted with **{score}**! Lost **{game['bet']:,}** coins." if game['bet'] > 0 else f"You busted with **{score}**!"
            )
            await ctx.send(embed=embed)
            del self.blackjack_games[ctx.author.id]
        elif score == 21:
            await ctx.invoke(self.stand)
        else:
            embed = self.build_blackjack_embed(
                ctx, game, "Your Turn",
                discord.Color.blurple()
            )
            embed.set_footer(text="Use !hit to draw or !stand to hold")
            await ctx.send(embed=embed)

    @commands.command()
    async def stand(self, ctx):
        """Hold your hand and let the dealer play."""
        game = self.blackjack_games.get(ctx.author.id)
        if not game:
            await ctx.send("❌ No active blackjack game. Use `!blackjack` to start.")
            return

        while self.calculate_score(game['dealer']) < 17:
            game['dealer'].append(self.draw_card())

        ps = self.calculate_score(game['player'])
        ds = self.calculate_score(game['dealer'])
        bet = game['bet']

        if ps == ds:
            result_text = "🤝 It's a tie! Bet returned."
            color = discord.Color.yellow()
            winnings = bet 
        elif ds > 21 or ps > ds:
            winnings = bet * 2
            result_text = f"🎉 You win! **+{bet:,}** coins!" if bet > 0 else "🎉 You win!"
            color = discord.Color.green()
        else:
            winnings = 0
            result_text = f"😔 Dealer wins! **-{bet:,}** coins." if bet > 0 else "😔 Dealer wins!"
            color = discord.Color.red()

        if bet > 0 and winnings > 0:
            conn = None
            cursor = None
            try:
                conn = self.bot.db_pool.get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET coins = coins + %s WHERE user_id = %s",
                    (winnings, ctx.author.id)
                )
                conn.commit()
            except Exception as e:
                print(f"Blackjack payout error: {e}")
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()

        embed = self.build_blackjack_embed(ctx, game, "Result", color, result_text)
        await ctx.send(embed=embed)
        del self.blackjack_games[ctx.author.id]

    async def _end_blackjack(self, ctx, win: bool, winnings: int, reason: str):
        """Helper to end a blackjack game and pay out."""
        game = self.blackjack_games.pop(ctx.author.id, None)
        if not game:
            return

        if winnings > 0:
            conn = None
            cursor = None
            try:
                conn = self.bot.db_pool.get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET coins = coins + %s WHERE user_id = %s",
                    (winnings, ctx.author.id)
                )
                conn.commit()
            except Exception as e:
                print(f"Blackjack end payout error: {e}")
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()

        embed = discord.Embed(
            title=f"🃏 Blackjack — {reason}",
            color=discord.Color.green() if win else discord.Color.red()
        )
        if game:
            embed.add_field(
                name="Your Hand",
                value=self.hand_display(game['player']),
                inline=False
            )
        if winnings > 0:
            embed.add_field(
                name="💰 Winnings",
                value=f"{winnings:,} coins",
                inline=False
            )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def slots(self, ctx, bet: int):
        """Spin the slots. Bet coins to win big."""
        if bet <= 0:
            await ctx.send("❌ Bet must be greater than 0.")
            return

        symbols = ['🍒', '🍋', '🔔', '🍉', '⭐', '7️⃣']
        result = [random.choice(symbols) for _ in range(3)]
        unique = len(set(result))

        if unique == 1:
            multiplier = 5
            outcome = "Jackpot! 🎉"
            color = discord.Color.gold()
        elif unique == 2:
            multiplier = 2
            outcome = "Two of a kind! 🎊"
            color = discord.Color.green()
        else:
            multiplier = 0
            outcome = "No match. Better luck next time!"
            color = discord.Color.red()

        net_change = (bet * multiplier) - bet 

        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE users
                SET coins = coins + %s
                WHERE user_id = %s AND coins >= %s
            """, (net_change, ctx.author.id, bet))
            conn.commit()

            if cursor.rowcount == 0:
                await ctx.send("❌ Not enough coins!")
                return

            embed = discord.Embed(
                title="🎰 Slots",
                color=color
            )
            embed.add_field(
                name="Result",
                value=f"[ {' | '.join(result)} ]",
                inline=False
            )
            embed.add_field(name="Outcome", value=outcome, inline=True)
            embed.add_field(
                name="Payout",
                value=f"`{multiplier}x` — {'+' if net_change >= 0 else ''}{net_change:,} coins",
                inline=True
            )
            embed.set_footer(text=f"Bet: {bet:,} coins")
            await ctx.send(embed=embed)

        except Exception as e:
            if conn:
                conn.rollback()
            await ctx.send("❌ Failed to process slots.")
            print(f"Slots error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @slots.error
    async def slots_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!slots <bet>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Bet must be a whole number.")

    @commands.command()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def mine(self, ctx, bet: int, row: int, col: int):
        """Pick a cell on a 3x3 grid. Avoid the bombs!"""
        if bet <= 0:
            await ctx.send("❌ Bet must be greater than 0.")
            return

        if not (1 <= row <= 3 and 1 <= col <= 3):
            await ctx.send("❌ Row and column must both be between 1 and 3.")
            return

        if bet < 100:
            num_bombs = 1 
        elif bet < 500:
            num_bombs = 2
        else:
            num_bombs = 3

        all_cells = [(r, c) for r in range(1, 4) for c in range(1, 4)]
        bombs = set(map(tuple, random.sample(all_cells, num_bombs)))

        hit_bomb = (row, col) in bombs

        grid = ""
        for r in range(1, 4):
            for c in range(1, 4):
                cell = (r, c)
                if cell == (row, col):
                    grid += "💣 " if hit_bomb else "✅ "
                elif cell in bombs:
                    grid += "💣 "
                else:
                    grid += "⬜ "
            grid += "\n"

        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()

            change = -bet if hit_bomb else bet

            cursor.execute("""
                UPDATE users
                SET coins = coins + %s
                WHERE user_id = %s AND coins >= %s
            """, (change, ctx.author.id, bet))
            conn.commit()

            if cursor.rowcount == 0:
                await ctx.send("❌ Not enough coins!")
                return

            if hit_bomb:
                embed = discord.Embed(
                    title="💣 BOOM!",
                    description=f"You hit a bomb! Lost **{bet:,}** coins.\n\n{grid}",
                    color=discord.Color.red()
                )
            else:
                embed = discord.Embed(
                    title="✅ Safe!",
                    description=f"You avoided the bombs! Won **{bet:,}** coins.\n\n{grid}",
                    color=discord.Color.green()
                )

            embed.add_field(
                name="Bombs",
                value=f"{num_bombs} hidden on the grid",
                inline=True
            )
            embed.add_field(
                name="Your Pick",
                value=f"Row {row}, Col {col}",
                inline=True
            )
            embed.set_footer(text=f"Bet: {bet:,} coins")
            await ctx.send(embed=embed)

        except Exception as e:
            if conn:
                conn.rollback()
            await ctx.send("❌ Failed to process game.")
            print(f"Mine error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @mine.error
    async def mine_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!mine <bet> <row> <col>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ All values must be whole numbers.")


async def setup(bot):
    await bot.add_cog(Games(bot))
