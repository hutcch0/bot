import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
from datetime import datetime, timezone
from mysql.connector import pooling
import logging

from config_loader import load_config
from dashboard import BotStats, DashboardServer

config = load_config()


def setup_logging():
    if not os.path.exists("logs"):
        os.makedirs("logs")

    log_filename = f"logs/bot_{datetime.now().strftime('%Y-%m-%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_filename, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)

    return logging.getLogger("bot")


logger = setup_logging()


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            application_id=config.get("APPLICATION_ID"),
        )

        self.config = config
        self.logger = logging.getLogger("bot.main")
        self.db_pool = None
        self.start_time = datetime.now(timezone.utc)
        self.stats = BotStats()
        self.dashboard = DashboardServer(self, self.stats)

    def create_db_pool(self):
        return pooling.MySQLConnectionPool(
            pool_name="bot_pool",
            pool_size=3,
            host=config["MYSQL_HOST"],
            port=config["MYSQL_PORT"],
            user=config["MYSQL_USER"],
            password=config["MYSQL_PASSWORD"],
            database=config["MYSQL_DB"],
        )

    async def connect_database(self):
        while not self.is_closed():
            try:
                self.db_pool = self.create_db_pool()
                self.create_tables()
                self.logger.info("Database pool created successfully")
                return
            except Exception as e:
                self.db_pool = None
                self.logger.error(
                    "Failed to connect to database: %s. Retrying in 30 seconds.",
                    e,
                )
                await asyncio.sleep(30)

    async def setup_hook(self):
        self.logger.info("Running setup hook...")
        asyncio.create_task(self.connect_database())
        await self.dashboard.start()

        async def on_tree_error(
            interaction: discord.Interaction,
            error: app_commands.AppCommandError,
        ):
            if interaction.response.is_done():
                send = interaction.followup.send
            else:
                send = interaction.response.send_message

            if isinstance(error, app_commands.MissingPermissions):
                await send(
                    "You don't have permission to use this command.",
                    ephemeral=True,
                )
            elif isinstance(error, app_commands.BotMissingPermissions):
                await send(
                    "I don't have the required permissions to do that.",
                    ephemeral=True,
                )
            elif isinstance(error, app_commands.CommandOnCooldown):
                await send(
                    f"Slow down! Try again in `{error.retry_after:.1f}s`.",
                    ephemeral=True,
                )
            elif isinstance(error, app_commands.CheckFailure):
                await send(
                    "You are not allowed to use this command.",
                    ephemeral=True,
                )
            else:
                await send(
                    "An unexpected error occurred.",
                    ephemeral=True,
                )
                self.logger.error(f"Slash command error: {error}")

        self.tree.on_error = on_tree_error

        cog_dir = "./cogs"
        if not os.path.exists(cog_dir):
            self.logger.warning("No cogs directory found, skipping cog loading")
            return

        loaded = 0
        failed = 0

        for filename in os.listdir(cog_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                cog_name = filename[:-3]
                if cog_name == "bot":
                    continue
                try:
                    await self.load_extension(f"cogs.{cog_name}")
                    self.logger.info(f"Loaded cog: {cog_name}")
                    loaded += 1
                except Exception as e:
                    self.logger.error(f"Failed to load cog {cog_name}: {e}")
                    failed += 1

        self.logger.info(f"Cogs: {loaded} loaded, {failed} failed")

        try:
            synced = await self.tree.sync()
            self.logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            self.logger.error(f"Failed to sync slash commands: {e}")

    def create_tables(self):
        if self.db_pool is None:
            return

        conn = None
        cursor = None
        try:
            conn = self.db_pool.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    money INT DEFAULT 1000,
                    coins INT DEFAULT 0,
                    xp INT DEFAULT 0
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS bans (
                    user_id BIGINT PRIMARY KEY,
                    reason TEXT,
                    banned_by BIGINT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS afk_users (
                    user_id BIGINT PRIMARY KEY,
                    reason TEXT,
                    timestamp DATETIME
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lottery_state (
                    id INT PRIMARY KEY,
                    pot INT DEFAULT 0
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lottery_tickets (
                    user_id BIGINT PRIMARY KEY,
                    tickets INT DEFAULT 0
                )
                """
            )

            cursor.execute(
                """
                INSERT IGNORE INTO lottery_state (id, pot) VALUES (1, 0)
                """
            )

            conn.commit()
            self.logger.info("Database tables verified/created")

        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.critical(f"Failed to create tables: {e}")
            raise RuntimeError(f"Failed to create tables: {e}") from e

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    async def on_ready(self):
        self.logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        self.logger.info(f"Connected to {len(self.guilds)} guild(s)")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | /help",
            ),
            status=discord.Status.online,
        )

        print("─" * 40)
        print(f"Logged in as: {self.user}")
        print(f"Bot ID: {self.user.id}")
        print(f"Servers: {len(self.guilds)}")
        print(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print("─" * 40)

    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: app_commands.Command,
    ):
        user = interaction.user.display_name if interaction.user else "Unknown"
        guild = interaction.guild.name if interaction.guild else None
        self.stats.record(command.qualified_name, user, guild)

    async def on_command(self, ctx: commands.Context):
        if ctx.command is None:
            return
        guild = ctx.guild.name if ctx.guild else None
        self.stats.record(ctx.command.qualified_name, str(ctx.author), guild)

    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, "on_error"):
            return

        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.NotOwner):
            await ctx.send("Only the bot owner can use this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing argument: `{error.param.name}`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Invalid argument provided.")
        else:
            await ctx.send("An unexpected error occurred.")
            self.logger.error(
                f"Unhandled error in command '{ctx.command}' "
                f"used by {ctx.author} ({ctx.author.id}): {error}"
            )


bot = MyBot()


@bot.command()
@commands.is_owner()
async def reload(ctx, cog: str):
    try:
        await bot.reload_extension(f"cogs.{cog}")
        logger.info(f"Cog reloaded: {cog} by {ctx.author}")
        await ctx.send(f"Successfully reloaded `{cog}`")
    except commands.ExtensionNotFound:
        await ctx.send(f"Cog `{cog}` does not exist.")
    except commands.ExtensionNotLoaded:
        await ctx.send(f"Cog `{cog}` is not loaded.")
    except commands.ExtensionFailed as e:
        logger.error(f"Failed to reload cog {cog}: {e.original}")
        await ctx.send(f"Cog `{cog}` failed to reload: `{e.original}`")


@bot.command()
@commands.is_owner()
async def load(ctx, cog: str):
    try:
        await bot.load_extension(f"cogs.{cog}")
        logger.info(f"Cog loaded: {cog} by {ctx.author}")
        await ctx.send(f"Successfully loaded `{cog}`")
    except commands.ExtensionNotFound:
        await ctx.send(f"Cog `{cog}` does not exist.")
    except commands.ExtensionAlreadyLoaded:
        await ctx.send(f"Cog `{cog}` is already loaded.")
    except commands.ExtensionFailed as e:
        logger.error(f"Failed to load cog {cog}: {e.original}")
        await ctx.send(f"Cog `{cog}` failed to load: `{e.original}`")


@bot.command()
@commands.is_owner()
async def unload(ctx, cog: str):
    try:
        await bot.unload_extension(f"cogs.{cog}")
        logger.info(f"Cog unloaded: {cog} by {ctx.author}")
        await ctx.send(f"Successfully unloaded `{cog}`")
    except commands.ExtensionNotFound:
        await ctx.send(f"Cog `{cog}` does not exist.")
    except commands.ExtensionNotLoaded:
        await ctx.send(f"Cog `{cog}` is not currently loaded.")


@bot.command()
@commands.is_owner()
async def cogs(ctx):
    loaded_cogs = list(bot.extensions.keys())
    if loaded_cogs:
        cog_list = "\n".join(f"- {cog}" for cog in loaded_cogs)
        await ctx.send(f"**Loaded Cogs:**\n{cog_list}")
    else:
        await ctx.send("No cogs are currently loaded.")


@bot.command()
@commands.is_owner()
async def sync(ctx):
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"Synced {len(synced)} slash commands!")
    except Exception as e:
        await ctx.send(f"Sync failed: {e}")


@bot.command()
@commands.is_owner()
async def stop(ctx):
    logger.info(f"Bot shutdown requested by {ctx.author} ({ctx.author.id})")
    await ctx.send("Shutting down safely...")
    await bot.close()


if __name__ == "__main__":
    try:
        bot.run(config["TOKEN"])
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
