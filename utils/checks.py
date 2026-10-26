import discord
from discord import app_commands


def is_bot_owner():
    """Slash command check — only the bot owner can use this."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not await interaction.client.is_owner(interaction.user):
            raise app_commands.CheckFailure(
                "❌ Only the bot owner can use this command."
            )
        return True
    return app_commands.check(predicate)


def has_guild_permissions(**perms):
    """
    Slash command check — checks the user's actual guild permissions.
    Usage: @has_guild_permissions(kick_members=True)
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        # Always allow bot owner
        if await interaction.client.is_owner(interaction.user):
            return True

        if not interaction.guild:
            raise app_commands.CheckFailure(
                "❌ This command can only be used in a server."
            )

        user_perms = interaction.user.guild_permissions

        missing = [
            perm for perm, value in perms.items()
            if getattr(user_perms, perm, None) != value
        ]

        if missing:
            raise app_commands.MissingPermissions(missing)

        return True
    return app_commands.check(predicate)


def is_in_guild():
    """Slash command check — command must be used inside a server."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            raise app_commands.CheckFailure(
                "❌ This command can only be used inside a server."
            )
        return True
    return app_commands.check(predicate)
