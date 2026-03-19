import discord
from discord.ext import commands

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        conn = self.bot.db_pool.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT reason FROM bans WHERE user_id = %s", (member.id,))
            row = cursor.fetchone()
            if row:
                await member.ban(reason=f"Global Ban: {row[0]}")
        finally:
            cursor.close()
            conn.close()

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def globalban(self, ctx, user: discord.User, *, reason="No reason"):
        conn = self.bot.db_pool.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("REPLACE INTO bans (user_id, reason, banned_by) VALUES (%s, %s, %s)", 
                           (user.id, reason, ctx.author.id))
            conn.commit()
            
            for guild in self.bot.guilds:
                try: await guild.ban(user, reason=f"Global Ban: {reason}")
                except: continue
                
            await ctx.send(f"🚫 {user.name} has been globally banned.")
        finally:
            cursor.close()
            conn.close()

async def setup(bot):
    await bot.add_cog(Moderation(bot))
