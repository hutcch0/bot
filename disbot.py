import discord
from discord.ext import commands, tasks
import random
import os
from datetime import datetime
import json
import mysql.connector

# ========== CONFIGURATION ==========
TOKEN = '...123'

MYSQL_HOST = '123'
MYSQL_PORT = 123
MYSQL_USER = '123'
MYSQL_PASSWORD = '123'
MYSQL_DB = '123'

def get_db():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB
    )

intents = discord.Intents.default()
intents.members = True  
intents.message_content = True  

bot = commands.Bot(command_prefix='!', intents=intents, application_id="1306388199387697265")

afk_users = {}
blackjack_games = {}

log_dir = './discordbot'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

user_data_file = 'user_data.json'

if os.path.exists(user_data_file):
    with open(user_data_file, 'r') as f:
        user_data = json.load(f)
else:
    user_data = {}

coin_value = 50
startup_time = datetime.utcnow()

def save_user_data():
    with open(user_data_file, 'w') as f:
        json.dump(user_data, f)

# ========== blackjack ==========
def draw_card():
    return random.choice(['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K'])

def calculate_score(cards):
    values = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10, 'A': 11}
    score = sum(values[card] for card in cards)
    aces = cards.count('A')
    while score > 21 and aces:
        score -= 10
        aces -= 1
    return score

# ========== market ==========
coin_trend = 0  # -1 for down, 0 for stable, 1 for up

@tasks.loop(minutes=10)
async def market_fluctuation():
    global coin_value, coin_trend
    if random.random() < 0.7:
        if coin_trend == 0:
            coin_trend = random.choice([-1, 1])
    else:
        coin_trend *= -1 if coin_trend != 0 else random.choice([-1, 1])
    change = random.randint(5, 15) * coin_trend
    coin_value = max(1, min(coin_value + change, 250))
    print(f"Coin value changed! New value: {coin_value} (trend: {coin_trend})")

# ========== on ready ==========
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    market_fluctuation.start()
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bans (
            user_id BIGINT PRIMARY KEY,
            reason TEXT,
            banned_by BIGINT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    cursor.close()
    db.close()

# ========== GLOBAL BAN SYSTEM ==========

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, user: discord.User, *, reason="No reason provided"):
    """Globally ban a user and add to the global ban database."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "REPLACE INTO bans (user_id, reason, banned_by) VALUES (%s, %s, %s)",
        (user.id, reason, ctx.author.id)
    )
    db.commit()
    cursor.close()
    db.close()

    for guild in bot.guilds:
        member = guild.get_member(user.id)
        if member:
            try:
                await guild.ban(member, reason=f"Global ban: {reason}")
            except Exception as e:
                print(f"Failed to ban in {guild.name}: {e}")
    await ctx.send(f"{user} has been globally banned for: {reason}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user: discord.User):
    """Globally unban a user and remove from the global ban database."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM bans WHERE user_id = %s", (user.id,))
    db.commit()
    cursor.close()
    db.close()
    for guild in bot.guilds:
        try:
            await guild.unban(user)
        except Exception:
            pass
    await ctx.send(f"{user} has been globally unbanned.")

@bot.command()
@commands.has_permissions(ban_members=True)
async def banlist(ctx):
    """Show the global ban list."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT user_id, reason FROM bans")
    rows = cursor.fetchall()
    cursor.close()
    db.close()
    if not rows:
        await ctx.send("No users are globally banned.")
        return
    msg = "\n".join([f"<@{row[0]}>: {row[1]}" for row in rows])
    await ctx.send(f"**Global Ban List:**\n{msg}")

@bot.event
async def on_member_join(member):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT reason FROM bans WHERE user_id = %s", (member.id,))
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if row:
        try:
            await member.guild.ban(member, reason=f"Global ban: {row[0]}")
            print(f"Auto-banned {member} in {member.guild.name}")
        except Exception as e:
            print(f"Failed to auto-ban {member} in {member.guild.name}: {e}")

# ========== END GLOBAL BAN SYSTEM ==========

# ========== report ==========
REPORT_CHANNEL_ID = 1309979922319540305

@bot.command()
async def report(ctx, member: discord.Member, *, reason: str):
    """Allows users to report someone."""
    report_channel = bot.get_channel(REPORT_CHANNEL_ID)
    if not report_channel:
        await ctx.send("Error: Could not find the report channel.")
        return

    embed = discord.Embed(
        title="New Report",
        description=f"**Reported User:** {member.mention}\n**Reported by:** {ctx.author.mention}\n**Reason:** {reason}\n**Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}",
        color=discord.Color.red()
    )
    embed.set_footer(text="React with ✅ to claim, ❌ to close.")

    report_msg = await report_channel.send(embed=embed)
    await report_msg.add_reaction("✅")
    await report_msg.add_reaction("❌")

    await ctx.send(f"Thank you for your report, {ctx.author.mention}. The moderation team will review it shortly.")

@bot.event
async def on_raw_reaction_add(payload):
    if payload.channel_id != REPORT_CHANNEL_ID:
        return
    channel = bot.get_channel(payload.channel_id)
    if not channel:
        return
    try:
        message = await channel.fetch_message(payload.message_id)
    except Exception:
        return
    if payload.user_id == bot.user.id:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not member or not member.guild_permissions.kick_members:
        return

    if payload.emoji.name == "✅":
        embed = message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "Report Claimed"
        embed.set_footer(text=f"Claimed by {member.display_name}")
        await message.edit(embed=embed)
        await channel.send(f"Report claimed by {member.mention}.")
    elif payload.emoji.name == "❌":
        embed = message.embeds[0]
        embed.color = discord.Color.dark_grey()
        embed.title = "Report Closed"
        embed.set_footer(text=f"Closed by {member.display_name}")
        await message.edit(embed=embed)
        await channel.send(f"Report closed by {member.mention}. Deleting in 5 seconds...")
        await message.clear_reactions()
        await asyncio.sleep(5)
        await message.delete()

# ========== uptime ==========
@bot.command()
async def uptime(ctx):
    uptime_duration = datetime.utcnow() - startup_time
    days = uptime_duration.days
    hours = uptime_duration.seconds // 3600
    minutes = (uptime_duration.seconds // 60) % 60
    seconds = uptime_duration.seconds % 60
    await ctx.send(f"The bot has been online for {days} days, {hours} hours, {minutes} minutes, and {seconds} seconds.")

# ========== coin stuff ==========
@bot.command()
async def coinvalue(ctx):
    await ctx.send(f"The current coin value is {coin_value}.")

@bot.command()
async def sellcoin(ctx, amount: int):
    user_id = str(ctx.author.id)
    coins = user_data.get(user_id, {}).get('coins', 0)
    if coins < amount:
        await ctx.send(f"{ctx.author.mention}, you don't have enough coins to sell.")
        return
    total_value = amount * coin_value
    user_data[user_id]['coins'] -= amount
    user_data[user_id]['money'] = user_data.get(user_id, {}).get('money', 1000) + total_value
    save_user_data()
    await ctx.send(f"{ctx.author.mention} sold {amount} coins for ${total_value}. You now have {user_data[user_id]['coins']} coins and ${user_data[user_id]['money']}.")

# ========== kill command ==========
@bot.command()
@commands.is_owner()  
async def stop(ctx):
    await ctx.send("Stopping the bot...")
    await bot.close()

# ========== mod commands ==========
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f'{member.mention} has been kicked.')

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, limit: int):
    await ctx.channel.purge(limit=limit + 1)  
    await ctx.send(f'Deleted {limit} messages.', delete_after=5)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *, reason=None):
    muted_role = discord.utils.get(ctx.guild.roles, name='Muted')
    await member.add_roles(muted_role, reason=reason)
    await ctx.send(f'{member.mention} has been muted.')

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member, *, reason=None):
    muted_role = discord.utils.get(ctx.guild.roles, name='Muted')
    await member.remove_roles(muted_role, reason=reason)
    await ctx.send(f'{member.mention} has been unmuted.')

# ========== info stuff ==========
@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f'{member}', color=member.color)
    embed.set_thumbnail(url=member.avatar.url)
    embed.add_field(name='ID', value=member.id)
    embed.add_field(name='Nickname', value=member.nick)
    embed.add_field(name='Joined Server', value=member.joined_at.strftime('%Y-%m-%d %H:%M:%S'))
    embed.add_field(name='Joined Discord', value=member.created_at.strftime('%Y-%m-%d %H:%M:%S'))
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f'{guild.name}', color=discord.Color.blue())
    embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name='Owner', value=guild.owner)
    embed.add_field(name='Members', value=guild.member_count)
    embed.add_field(name='Text Channels', value=len(guild.text_channels))
    embed.add_field(name='Voice Channels', value=len(guild.voice_channels))
    embed.add_field(name='Created', value=guild.created_at.strftime('%Y-%m-%d %H:%M:%S'))
    await ctx.send(embed=embed)

# ========== leaderboard ==========
@bot.command()
async def leaderboard(ctx):
    sorted_users = sorted(user_data.items(), key=lambda x: x[1].get('coins', 0), reverse=True)
    leaderboard_message = "**Leaderboard**\n"
    for idx, (user_id, data) in enumerate(sorted_users[:10], 1):  
        try:
            user = await bot.fetch_user(int(user_id))
            coins = data.get('coins', 0)
            leaderboard_message += f"{idx}. {user.name} - {coins} coins\n"
        except Exception:
            continue
    if len(sorted_users) == 0:
        await ctx.send("No users found with coin data.")
    else:
        await ctx.send(leaderboard_message)

# ========== coin stuff ==========
@bot.command()
async def balance(ctx):
    user_id = str(ctx.author.id)
    coins = user_data.get(user_id, {}).get('coins', 0)
    money = user_data.get(user_id, {}).get('money', 1000)  
    await ctx.send(f"{ctx.author.mention}, you have {coins} coins and ${money}.")

@bot.command()
async def buycoin(ctx, amount: int):
    user_id = str(ctx.author.id)
    money = user_data.get(user_id, {}).get('money', 1000) 
    total_cost = amount * coin_value
    if money >= total_cost:
        user_data.setdefault(user_id, {})['money'] = money - total_cost
        user_data.setdefault(user_id, {})['coins'] = user_data.get(user_id, {}).get('coins', 0) + amount
        save_user_data()
        await ctx.send(f"{ctx.author.mention} bought {amount} coins for ${total_cost}.")
    else:
        await ctx.send(f"{ctx.author.mention}, you don't have enough money to buy {amount} coins.")

# ========== afk ==========
@bot.command()
async def afk(ctx, *, reason="AFK"): 
    afk_users[ctx.author.id] = reason
    await ctx.send(f"{ctx.author.mention} is now AFK: {reason}")

@bot.command()
async def back(ctx):
    if ctx.author.id in afk_users:
        del afk_users[ctx.author.id]
        await ctx.send(f"{ctx.author.mention} is back!")
    else:
        await ctx.send("You're not AFK.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.author.id in afk_users:
        del afk_users[message.author.id]
        await message.channel.send(f"{message.author.mention} is back!")
    
    mentioned_afk = set()
    for user in message.mentions:
        if user.id in afk_users and user.id not in mentioned_afk:
            await message.channel.send(f"{user.mention} is AFK: {afk_users[user.id]}")
            mentioned_afk.add(user.id)

    await bot.process_commands(message)

# ========== blackjack ==========
@bot.command()
async def blackjack(ctx):
    user = ctx.author.id
    if user in blackjack_games:
        await ctx.send("You already have a game in progress!")
        return
    player_hand = [draw_card(), draw_card()]
    dealer_hand = [draw_card()]
    blackjack_games[user] = {'player': player_hand, 'dealer': dealer_hand}
    await ctx.send(f"{ctx.author.mention}, your hand: {player_hand} ({calculate_score(player_hand)}). Dealer's hand: {dealer_hand}")

@bot.command()
async def hit(ctx):
    user = ctx.author.id
    if user not in blackjack_games:
        await ctx.send("Start a game first using !blackjack!")
        return
    blackjack_games[user]['player'].append(draw_card())
    score = calculate_score(blackjack_games[user]['player'])
    if score > 21:
        await ctx.send(f"{ctx.author.mention}, you busted! Your hand: {blackjack_games[user]['player']} ({score})")
        del blackjack_games[user]
    else:
        await ctx.send(f"{ctx.author.mention}, your new hand: {blackjack_games[user]['player']} ({score})")

@bot.command()
async def stand(ctx):
    user = ctx.author.id
    if user not in blackjack_games:
        await ctx.send("Start a game first using !blackjack!")
        return
    dealer_hand = blackjack_games[user]['dealer']
    while calculate_score(dealer_hand) < 17:
        dealer_hand.append(draw_card())
    player_score = calculate_score(blackjack_games[user]['player'])
    dealer_score = calculate_score(dealer_hand)
    if dealer_score > 21 or player_score > dealer_score:
        result = "You win!"
    elif player_score < dealer_score:
        result = "You lose!"
    else:
        result = "It's a tie!"
    await ctx.send(f"{ctx.author.mention}, your hand: {blackjack_games[user]['player']} ({player_score}). Dealer's hand: {dealer_hand} ({dealer_score}). {result}")
    del blackjack_games[user]

# ========== slots ==========
@bot.command()
async def slots(ctx, bet: int):
    user_id = str(ctx.author.id)
    coins = user_data.get(user_id, {}).get('coins', 0)
    if bet <= 0:
        await ctx.send("Bet must be positive.")
        return
    if coins < bet:
        await ctx.send(f"{ctx.author.mention}, you don't have enough coins to bet.")
        return

    symbols = ['🍒', '🍋', '🔔', '🍉', '⭐', '7️⃣']
    result = [random.choice(symbols) for _ in range(3)]
    await ctx.send(f"{ctx.author.mention} spun: {' | '.join(result)}")

    if len(set(result)) == 1:
        winnings = bet * 5
        user_data[user_id]['coins'] = coins + winnings
        await ctx.send(f"JACKPOT! You won {winnings} coins!")
    elif len(set(result)) == 2:
        winnings = bet * 2
        user_data[user_id]['coins'] = coins + winnings
        await ctx.send(f"Nice! You won {winnings} coins!")
    else:
        user_data[user_id]['coins'] = coins - bet
        await ctx.send(f"You lost {bet} coins. Try again!")
    save_user_data()

# ========== MINES GAME ==========
@bot.command()
async def mine(ctx, bet: int, row: int, col: int):
    """Play the Mines game! Pick a spot in a 3x3 grid and avoid the bomb."""
    user_id = str(ctx.author.id)
    coins = user_data.get(user_id, {}).get('coins', 0)

    if bet <= 0:
        await ctx.send("Bet must be positive.")
        return
    if coins < bet:
        await ctx.send(f"{ctx.author.mention}, you don't have enough coins to bet.")
        return
    if not (1 <= row <= 3 and 1 <= col <= 3):
        await ctx.send("Row and column must be between 1 and 3.")
        return

    bomb_row = random.randint(1, 3)
    bomb_col = random.randint(1, 3)

    grid = ""
    for r in range(1, 4):
        for c in range(1, 4):
            if r == row and c == col:
                grid += "🔲" 
            else:
                grid += "⬜"
        grid += "\n"
        
    if (row, col) == (bomb_row, bomb_col):
        user_data[user_id]['coins'] = coins - bet
        save_user_data()
        await ctx.send(f"{ctx.author.mention} picked:\n{grid}\n💣 **BOOM! You hit the bomb and lost {bet} coins!**\nThe bomb was at row {bomb_row}, column {bomb_col}.")
    else:
        winnings = bet * 2
        user_data[user_id]['coins'] = coins + bet
        save_user_data()
        await ctx.send(f"{ctx.author.mention} picked:\n{grid}\n🎉 **Safe! You win {bet} coins!**\nThe bomb was at row {bomb_row}, column {bomb_col}.")
        
# ========== photos ==========       
@bot.command()
async def photo(ctx):
    """Sends a random photo from the photo.json file."""
    try:
        with open('photo.json', 'r') as f:
            photos = json.load(f)
        if not photos:
            await ctx.send("No photos found!")
            return

        link = random.choice(list(photos.values()))
        embed = discord.Embed(title="Random Photo")
        embed.set_image(url=link)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send("Error loading photos.")
        print(f"Photo command error: {e}")

# ========== error handler ==========     
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Missing arguments for this command.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    else:
        await ctx.send("An error occurred.")
        print(f"Error: {error}")

# ========== SOCIAL LINKS EMBED ==========
@bot.command()
async def social(ctx):
    """Show social media and other links."""
    embed = discord.Embed(
        title="🌐 Social Links",
        description="Check out our pages and communities!",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Website", value="[my website](https://hutcch.neocities.org/html/Links-Page)", inline=False)
    embed.add_field(name="YouTube", value="[YouTube Channel](https://www.youtube.com/channel/UCbhfUDBi3YEXRTJGI5EXtQQ)", inline=False)
    embed.add_field(name="Twitter", value="[Twitter](https://x.com/Hutcch2)", inline=False)
    embed.add_field(name="Instagram", value="[Instagram](https://www.instagram.com/huttch0/)", inline=False)
    embed.add_field(name="Discord", value="[Join our Discord](https://discord.gg/dMT8gtc5U8)", inline=False)
    await ctx.send(embed=embed)

bot.run(TOKEN)
