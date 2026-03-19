import discord
from discord.ext import commands
import json
import os
from datetime import datetime
from mysql.connector import pooling

with open('config.json', 'r') as f:
    config = json.load(f)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix='!', 
            intents=intents,
            application_id=config.get("APPLICATION_ID")
        )
        
        self.db_pool = pooling.MySQLConnectionPool(
            pool_name="bot_pool",
            pool_size=10,
            host=config["MYSQL_HOST"],
            port=config["MYSQL_PORT"],
            user=config["MYSQL_USER"],
            password=config["MYSQL_PASSWORD"],
            database=config["MYSQL_DB"]
        )
        
        self.start_time = datetime.utcnow()

    async def setup_hook(self):
        self.create_tables()
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f'✅ Loaded Cog: {filename}')

    def create_tables(self):
        conn = self.db_pool.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                money INT DEFAULT 1000,
                coins INT DEFAULT 0,
                xp INT DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bans (
                user_id BIGINT PRIMARY KEY,
                reason TEXT,
                banned_by BIGINT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()

bot = MyBot()

@bot.command()
@commands.is_owner()
async def reload(ctx, cog: str):
    """Reloads a specific cog instantly."""
    try:
        await bot.reload_extension(f'cogs.{cog}')
        await ctx.send(f"🔄 Successfully reloaded `cogs.{cog}`")
    except Exception as e:
        await ctx.send(f"❌ Error reloading `{cog}`: {e}")

bot.run(config["TOKEN"])
