import discord
from discord.ext import commands
from discord import app_commands
import random


class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.blackjack_games = {}

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

    def build_blackjack_embed(
        self,
        display_name: str,
        game: dict,
        title: str,
        color,
        result_text: str = None,
        footer_text: str = None
    ) -> discord.Embed:
        """Builds a blackjack embed. Works for both prefix and slash commands."""
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
            embed.add_field(name="📊 Result", value=result_text, inline=False)

        embed.set_footer(text=footer_text or f"Player: {display_name}")
        return embed

    async def _deduct_bet(self, user_id: int, bet: int) -> bool:
        """
        Deducts bet from the user's coins.
        Returns True on success, False if insufficient funds or error.
        """
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET coins = coins - %s
                WHERE user_id = %s AND coins >= %s
            """, (bet, user_id, bet))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Deduct bet error: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    async def _payout(self, user_id: int, amount: int) -> bool:
        """
        Adds coins to the user's account.
        Returns True on success, False on error.
        """
        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET coins = coins + %s WHERE user_id = %s",
                (amount, user_id)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"Payout error: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    async def _start_blackjack_game(
        self,
        user: discord.Member | discord.User,
        bet: int
    ) -> tuple[bool, str]:
        """
        Shared logic to start a blackjack game.
        Returns (success: bool, error_message: str)
        """
        if user.id in self.blackjack_games:
            return False, "⚠️ You already have a game running! Use `hit` or `stand`."

        if bet < 0:
            return False, "❌ Bet cannot be negative."

        if bet > 0:
            success = await self._deduct_bet(user.id, bet)
            if not success:
                return False, "❌ Not enough coins to place that bet."

        player = [self.draw_card(), self.draw_card()]
        dealer = [self.draw_card()]

        self.blackjack_games[user.id] = {
            'player': player,
            'dealer': dealer,
            'bet': bet
        }
        return True, ""

    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def blackjack(self, ctx, bet: int = 0):
        """Start a game of blackjack. Optionally bet coins."""
        success, error = await self._start_blackjack_game(ctx.author, bet)
        if not success:
            await ctx.send(error)
            return

        game = self.blackjack_games[ctx.author.id]

        if self.calculate_score(game['player']) == 21:
            winnings = int(bet * 1.5) if bet > 0 else 0
            await self._end_blackjack_prefix(ctx, win=True, winnings=winnings, reason="Blackjack! 🎉")
            return

        embed = self.build_blackjack_embed(
            ctx.author.display_name,
            game,
            "Your Turn",
            discord.Color.blurple(),
            footer_text="Use !hit to draw or !stand to hold"
        )
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
            result = (
                f"You busted with **{score}**! Lost **{game['bet']:,}** coins."
                if game['bet'] > 0
                else f"You busted with **{score}**!"
            )
            embed = self.build_blackjack_embed(
                ctx.author.display_name,
                game,
                "Busted! 💥",
                discord.Color.red(),
                result_text=result
            )
            await ctx.send(embed=embed)
            del self.blackjack_games[ctx.author.id]

        elif score == 21:
            await ctx.invoke(self.stand)

        else:
            embed = self.build_blackjack_embed(
                ctx.author.display_name,
                game,
                "Your Turn",
                discord.Color.blurple(),
                footer_text="Use !hit to draw or !stand to hold"
            )
            await ctx.send(embed=embed)

    @commands.command()
    async def stand(self, ctx):
        """Hold your hand and let the dealer play."""
        game = self.blackjack_games.get(ctx.author.id)
        if not game:
            await ctx.send("❌ No active blackjack game. Use `!blackjack` to start.")
            return

        embed, winnings = await self._resolve_blackjack(ctx.author.display_name, game, ctx.author.id)
        await ctx.send(embed=embed)
        del self.blackjack_games[ctx.author.id]

    async def _end_blackjack_prefix(self, ctx, win: bool, winnings: int, reason: str):
        """Ends a blackjack game early (e.g. natural blackjack) for prefix commands."""
        game = self.blackjack_games.pop(ctx.author.id, None)
        if not game:
            return

        if winnings > 0:
            await self._payout(ctx.author.id, winnings)

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

    @app_commands.command(name="blackjack", description="Start a game of blackjack. Optionally bet coins.")
    @app_commands.describe(bet="Amount of coins to bet. Defaults to 0.")
    async def blackjack_slash(self, interaction: discord.Interaction, bet: int = 0):
        success, error = await self._start_blackjack_game(interaction.user, bet)
        if not success:
            await interaction.response.send_message(error, ephemeral=True)
            return

        game = self.blackjack_games[interaction.user.id]

        if self.calculate_score(game['player']) == 21:
            winnings = int(bet * 1.5) if bet > 0 else 0
            await self._end_blackjack_slash(interaction, win=True, winnings=winnings, reason="Blackjack! 🎉")
            return

        embed = self.build_blackjack_embed(
            interaction.user.display_name,
            game,
            "Your Turn",
            discord.Color.blurple(),
            footer_text="Use /hit to draw or /stand to hold"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="hit", description="Draw another card in your blackjack game.")
    async def hit_slash(self, interaction: discord.Interaction):
        game = self.blackjack_games.get(interaction.user.id)
        if not game:
            await interaction.response.send_message(
                "❌ No active blackjack game. Use `/blackjack` to start.",
                ephemeral=True
            )
            return

        game['player'].append(self.draw_card())
        score = self.calculate_score(game['player'])

        if score > 21:
            result = (
                f"You busted with **{score}**! Lost **{game['bet']:,}** coins."
                if game['bet'] > 0
                else f"You busted with **{score}**!"
            )
            embed = self.build_blackjack_embed(
                interaction.user.display_name,
                game,
                "Busted! 💥",
                discord.Color.red(),
                result_text=result
            )
            await interaction.response.send_message(embed=embed)
            del self.blackjack_games[interaction.user.id]

        elif score == 21:
            embed, _ = await self._resolve_blackjack(
                interaction.user.display_name, game, interaction.user.id
            )
            await interaction.response.send_message(embed=embed)
            del self.blackjack_games[interaction.user.id]

        else:
            embed = self.build_blackjack_embed(
                interaction.user.display_name,
                game,
                "Your Turn",
                discord.Color.blurple(),
                footer_text="Use /hit to draw or /stand to hold"
            )
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stand", description="Hold your hand and let the dealer play.")
    async def stand_slash(self, interaction: discord.Interaction):
        game = self.blackjack_games.get(interaction.user.id)
        if not game:
            await interaction.response.send_message(
                "❌ No active blackjack game. Use `/blackjack` to start.",
                ephemeral=True
            )
            return

        embed, _ = await self._resolve_blackjack(
            interaction.user.display_name, game, interaction.user.id
        )
        await interaction.response.send_message(embed=embed)
        del self.blackjack_games[interaction.user.id]

    async def _end_blackjack_slash(
        self,
        interaction: discord.Interaction,
        win: bool,
        winnings: int,
        reason: str
    ):
        """Ends a blackjack game early (e.g. natural blackjack) for slash commands."""
        game = self.blackjack_games.pop(interaction.user.id, None)
        if not game:
            return

        if winnings > 0:
            await self._payout(interaction.user.id, winnings)

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
        await interaction.response.send_message(embed=embed)

    async def _resolve_blackjack(
        self,
        display_name: str,
        game: dict,
        user_id: int
    ) -> tuple[discord.Embed, int]:
        """
        Shared dealer logic and payout for both prefix and slash stand.
        Returns (embed, winnings).
        """
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
            await self._payout(user_id, winnings)

        embed = self.build_blackjack_embed(
            display_name,
            game,
            "Result",
            color,
            result_text=result_text
        )
        return embed, winnings

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def slots(self, ctx, bet: int):
        """Spin the slots. Bet coins to win big."""
        if bet <= 0:
            await ctx.send("❌ Bet must be greater than 0.")
            return

        embed, error = await self._play_slots(ctx.author.id, bet)
        if error:
            await ctx.send(error)
        else:
            await ctx.send(embed=embed)

    @slots.error
    async def slots_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!slots <bet>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Bet must be a whole number.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Slow down! Try again in {error.retry_after:.1f}s.")

    @app_commands.command(name="slots", description="Spin the slots. Bet coins to win big.")
    @app_commands.describe(bet="Amount of coins to bet.")
    async def slots_slash(self, interaction: discord.Interaction, bet: int):
        if bet <= 0:
            await interaction.response.send_message(
                "❌ Bet must be greater than 0.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        embed, error = await self._play_slots(interaction.user.id, bet)
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed)

    async def _play_slots(self, user_id: int, bet: int) -> tuple[discord.Embed | None, str | None]:
        """
        Shared slots logic.
        Returns (embed, None) on success or (None, error_message) on failure.
        """
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
            """, (net_change, user_id, bet))
            conn.commit()

            if cursor.rowcount == 0:
                return None, "❌ Not enough coins!"

            embed = discord.Embed(title="🎰 Slots", color=color)
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
            return embed, None

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Slots error: {e}")
            return None, "❌ Failed to process slots."
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

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

        embed, error = await self._play_mine(ctx.author.id, bet, row, col)
        if error:
            await ctx.send(error)
        else:
            await ctx.send(embed=embed)

    @mine.error
    async def mine_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!mine <bet> <row> <col>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ All values must be whole numbers.")
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Slow down! Try again in {error.retry_after:.1f}s.")

    @app_commands.command(name="mine", description="Pick a cell on a 3x3 grid. Avoid the bombs!")
    @app_commands.describe(
        bet="Amount of coins to bet.",
        row="Row to pick (1–3).",
        col="Column to pick (1–3)."
    )
    async def mine_slash(
        self,
        interaction: discord.Interaction,
        bet: int,
        row: int,
        col: int
    ):
        if bet <= 0:
            await interaction.response.send_message(
                "❌ Bet must be greater than 0.",
                ephemeral=True
            )
            return
        if not (1 <= row <= 3 and 1 <= col <= 3):
            await interaction.response.send_message(
                "❌ Row and column must both be between 1 and 3.",
                ephemeral=True
            )
            return

        await interaction.response.defer()
        embed, error = await self._play_mine(interaction.user.id, bet, row, col)
        if error:
            await interaction.followup.send(error, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed)

    async def _play_mine(
        self,
        user_id: int,
        bet: int,
        row: int,
        col: int
    ) -> tuple[discord.Embed | None, str | None]:
        """
        Shared mine game logic.
        Returns (embed, None) on success or (None, error_message) on failure.
        """
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
            """, (change, user_id, bet))
            conn.commit()

            if cursor.rowcount == 0:
                return None, "❌ Not enough coins!"

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
                name="💣 Bombs",
                value=f"{num_bombs} hidden on the grid",
                inline=True
            )
            embed.add_field(
                name="📍 Your Pick",
                value=f"Row {row}, Col {col}",
                inline=True
            )
            embed.set_footer(text=f"Bet: {bet:,} coins")
            return embed, None

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Mine error: {e}")
            return None, "❌ Failed to process game."
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


async def setup(bot):
    await bot.add_cog(Games(bot))
