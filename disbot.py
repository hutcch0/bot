import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timezone
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

        try:
            self.db_pool = pooling.MySQLConnectionPool(
                pool_name="bot_pool",
                pool_size=3,
                host=config["MYSQL_HOST"],
                port=config["MYSQL_PORT"],
                user=config["MYSQL_USER"],
                password=config["MYSQL_PASSWORD"],
                database=config["MYSQL_DB"]
            )
            print("Database pool created successfully")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to database: {e}")

        self.start_time = datetime.now(timezone.utc)

    async def setup_hook(self):
        print("⚙️  Running setup hook...")
        self.create_tables()

        cog_dir = './cogs'
        if not os.path.exists(cog_dir):
            print("No cogs directory found, skipping cog loading")
            return

        loaded = 0
        failed = 0

        for filename in os.listdir(cog_dir):
            if filename.endswith('.py'):
                cog_name = filename[:-3]
                try:
                    await self.load_extension(f'cogs.{cog_name}')
                    print(f'Loaded cog: {cog_name}')
                    loaded += 1
                except Exception as e:
                    print(f'Failed to load cog {cog_name}: {e}')
                    failed += 1

        print(f"Cogs: {loaded} loaded, {failed} failed")

    def create_tables(self):
        conn = None
        cursor = None
        try:
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
            print("Database tables verified/created")

        except Exception as e:
            if conn:
                conn.rollback()
            raise RuntimeError(f"Failed to create tables: {e}")

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    async def on_ready(self):
        print("─" * 40)
        print(f' Logged in as: {self.user}')
        print(f' Bot ID: {self.user.id}')
        print(f' Servers: {len(self.guilds)}')
        print(f' Started at: {self.start_time.strftime("%Y-%m-%d %H:%M:%S")} UTC')
        print("─" * 40)

    async def on_command_error(self, ctx, error):

        if hasattr(ctx.command, 'on_error'):
            return

        if isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, commands.NotOwner):
            await ctx.send("Only the bot owner can use this command.")

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing argument: `{error.param.name}`")

        elif isinstance(error, commands.BadArgument):
            await ctx.send("Invalid argument provided.")

        else:
            await ctx.send(f"An error occurred: {error}")
            print(f"Unhandled error in {ctx.command}: {error}")

bot = MyBot()

@bot.command()
@commands.is_owner()
async def reload(ctx, cog: str):
    """Reloads a specific cog."""
    try:
        await bot.reload_extension(f'cogs.{cog}')
        await ctx.send(f"Successfully reloaded `{cog}`")
    except commands.ExtensionNotFound:
        await ctx.send(f"Cog `{cog}` does not exist.")
    except commands.ExtensionNotLoaded:
        await ctx.send(f"Cog `{cog}` is not loaded.")
    except commands.ExtensionFailed as e:
        await ctx.send(f"Cog `{cog}` failed to reload: `{e.original}`")

@bot.command()
@commands.is_owner()
async def load(ctx, cog: str):
    """Loads a cog that isn't currently loaded."""
    try:
        await bot.load_extension(f'cogs.{cog}')
        await ctx.send(f"Successfully loaded `{cog}`")
    except commands.ExtensionNotFound:
        await ctx.send(f"Cog `{cog}` does not exist.")
    except commands.ExtensionAlreadyLoaded:
        await ctx.send(f"Cog `{cog}` is already loaded.")
    except commands.ExtensionFailed as e:
        await ctx.send(f"Cog `{cog}` failed to load: `{e.original}`")

@bot.command()
@commands.is_owner()
async def unload(ctx, cog: str):
    """Unloads a currently loaded cog."""
    try:
        await bot.unload_extension(f'cogs.{cog}')
        await ctx.send(f"Successfully unloaded `{cog}`")
    except commands.ExtensionNotFound:
        await ctx.send(f"Cog `{cog}` does not exist.")
    except commands.ExtensionNotLoaded:
        await ctx.send(f"Cog `{cog}` is not currently loaded.")

@bot.command()
@commands.is_owner()
async def cogs(ctx):
    """Lists all loaded cogs."""
    loaded_cogs = [ext for ext in bot.extensions.keys()]
    if loaded_cogs:
        cog_list = "\n".join(f"{cog}" for cog in loaded_cogs)
        await ctx.send(f"**Loaded Cogs:**\n{cog_list}")
    else:
        await ctx.send("No cogs are currently loaded.")

if __name__ == "__main__":
    bot.run(config["TOKEN"])
