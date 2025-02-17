import discord
from discord.ext import commands, tasks
import random
import os
from datetime import datetime, timedelta
import json

TOKEN = '123...'

intents = discord.Intents.default()
intents.members = True  
intents.message_content = True  

bot = commands.Bot(command_prefix='!', intents=intents, application_id="")

afk_users = {}
blackjack_games = {}

log_dir = 'D:\discordbot'
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

@tasks.loop(minutes=10)
async def market_fluctuation():
    global coin_value
    change = random.randint(-100, 100)  
    coin_value = max(1, min(coin_value + change, 250)) 
    print(f"Coin value changed! New value: {coin_value}")


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    market_fluctuation.start()


@bot.command()
async def uptime(ctx):
    """Shows how long the bot has been online."""
    uptime_duration = datetime.utcnow() - startup_time
    days = uptime_duration.days
    hours = uptime_duration.seconds // 3600
    minutes = (uptime_duration.seconds // 60) % 60
    seconds = uptime_duration.seconds % 60

    await ctx.send(f"The bot has been online for {days} days, {hours} hours, {minutes} minutes, and {seconds} seconds.")

@bot.command()
async def coinvalue(ctx):
    """Shows the current coin value."""
    await ctx.send(f"The current coin value is {coin_value}.")

@bot.command()
async def sellcoin(ctx, amount: int):
    """Sell coins for money."""
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

@bot.command()
@commands.is_owner()  
async def stop(ctx):
    """Stops the bot."""
    await ctx.send("Stopping the bot...")
    await bot.close()

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    """Kicks a member from the server."""
    await member.kick(reason=reason)
    await ctx.send(f'{member.mention} has been kicked.')

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):
    """Bans a member from the server."""
    await member.ban(reason=reason)
    await ctx.send(f'{member.mention} has been banned.')

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, limit: int):
    """Deletes a number of messages."""
    await ctx.channel.purge(limit=limit + 1)  
    await ctx.send(f'Deleted {limit} messages.', delete_after=5)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member, *, reason=None):
    """Mutes a member."""
    muted_role = discord.utils.get(ctx.guild.roles, name='Muted')
    await member.add_roles(muted_role, reason=reason)
    await ctx.send(f'{member.mention} has been muted.')

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member, *, reason=None):
    """Unmutes a member."""
    muted_role = discord.utils.get(ctx.guild.roles, name='Muted')
    await member.remove_roles(muted_role, reason=reason)
    await ctx.send(f'{member.mention} has been unmuted.')

@bot.command(name='8ball')
async def _8ball(ctx, *, question):
    responses = [
        "It is certain.", "It is decidedly so.", "Without a doubt.", "Yes - definitely.", "You may rely on it.",
        "As I see it, yes.", "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
        "Reply hazy, try again.", "Ask again later.", "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
        "Don't count on it.", "My reply is no.", "My sources say no.", "Outlook not so good.", "Very doubtful."
    ]
    await ctx.send(f'Question: {question}\nAnswer: {random.choice(responses)}')

@bot.command()
async def roll(ctx, dice: str):
    """Rolls a dice in NdN format."""
    try:
        rolls, limit = map(int, dice.split('d'))
    except Exception:
        await ctx.send('Format has to be in NdN!')
        return

    result = ', '.join(str(random.randint(1, limit)) for r in range(rolls))
    await ctx.send(result)

@bot.command()
async def coinflip(ctx):
    """Flips a coin."""
    result = random.choice(['Heads', 'Tails'])
    await ctx.send(f"The coin landed on: {result}")

@bot.command()
async def rng(ctx, low: int, high: int):
    """Generates a random number between two numbers."""
    if low >= high:
        await ctx.send("The lower number must be less than the higher number.")
        return
    result = random.randint(low, high)
    await ctx.send(f"The random number is: {result}")

@bot.command()
async def poll(ctx, question, *choices: str):
    """Create a poll for users to vote on."""
    if len(choices) < 2:
        await ctx.send("You must provide at least two choices.")
        return

    poll_message = f"**{question}**\n\n" + "\n".join([f"{index+1}. {choice}" for index, choice in enumerate(choices)])
    poll = await ctx.send(poll_message)

    for i in range(len(choices)):
        await poll.add_reaction(chr(127462 + i))  # 1️⃣, 2️⃣, 3️⃣, etc.

    await ctx.send("Poll created! Please vote by reacting to the poll.")

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    """Shows info about a user."""
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
    """Shows info about the server."""
    guild = ctx.guild
    embed = discord.Embed(title=f'{guild.name}', color=discord.Color.blue())
    embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name='Owner', value=guild.owner)
    embed.add_field(name='Members', value=guild.member_count)
    embed.add_field(name='Text Channels', value=len(guild.text_channels))
    embed.add_field(name='Voice Channels', value=len(guild.voice_channels))
    embed.add_field(name='Created', value=guild.created_at.strftime('%Y-%m-%d %H:%M:%S'))
    await ctx.send(embed=embed)

@bot.command()
async def leaderboard(ctx):
    """Displays the leaderboard of users with the most coins."""

    sorted_users = sorted(user_data.items(), key=lambda x: x[1].get('coins', 0), reverse=True)

    leaderboard_message = "**Leaderboard**\n"
    for idx, (user_id, data) in enumerate(sorted_users[:10], 1):  
        user = await bot.fetch_user(user_id)
        coins = data.get('coins', 0)
        leaderboard_message += f"{idx}. {user.name} - {coins} coins\n"

    if len(sorted_users) == 0:
        await ctx.send("No users found with coin data.")
    else:
        await ctx.send(leaderboard_message)

@bot.command()
async def balance(ctx):
    """Shows the user's balance."""
    user_id = str(ctx.author.id)
    coins = user_data.get(user_id, {}).get('coins', 0)
    money = user_data.get(user_id, {}).get('money', 1000)  
    await ctx.send(f"{ctx.author.mention}, you have {coins} coins and ${money}.")

@bot.command()
async def buycoin(ctx, amount: int):
    """Buy coins with money."""
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
    if message.mentions:
        for user in message.mentions:
            if user.id in afk_users:
                await message.channel.send(f"{user.mention} is AFK: {afk_users[user.id]}")
    await bot.process_commands(message)

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

@bot.command()
async def slots(ctx, bet: int):
    symbols = ['🍒', '🍋', '🔔', '🍉', '⭐', '7️⃣']
    result = [random.choice(symbols) for _ in range(3)]
    await ctx.send(f"{ctx.author.mention} spun: {' | '.join(result)}")
    
    if len(set(result)) == 1:
        await ctx.send(f"JACKPOT! You won {bet * 5} coins!")
    elif len(set(result)) == 2:
        await ctx.send(f"Nice! You won {bet * 2} coins!")
    else:
        await ctx.send(f"You lost {bet} coins. Try again!")

bot.run(TOKEN)
