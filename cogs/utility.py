import discord
from discord.ext import commands
import json
import random
from datetime import datetime

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.afk_users = {}

    @commands.command()
    async def uptime(self, ctx):
        delta = datetime.utcnow() - self.bot.start_time
        await ctx.send(f"⏱️ Online for: {str(delta).split('.')[0]}")

    @commands.command()
    async def afk(self, ctx, *, reason="AFK"):
        self.afk_users[ctx.author.id] = reason
        await ctx.send(f"💤 {ctx.author.mention} is now AFK: {reason}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        if message.author.id in self.afk_users:
            del self.afk_users[message.author.id]
            await message.channel.send(f"Welcome back {message.author.mention}!", delete_after=5)
        for u in message.mentions:
            if u.id in self.afk_users:
                await message.channel.send(f"⚠️ {u.name} is AFK: {self.afk_users[u.id]}")

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed(title=member.name, color=member.color)
        embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(name="ID", value=member.id)
        embed.add_field(name="Joined Discord", value=member.created_at.strftime("%Y-%m-%d"))
        await ctx.send(embed=embed)

    @commands.command()
    async def serverinfo(self, ctx):
        guild = ctx.guild
        embed = discord.Embed(title=guild.name, color=0x3498db)
        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Owner", value=guild.owner)
        await ctx.send(embed=embed)

    @commands.command()
    async def photo(self, ctx):
        try:
            with open('photo.json', 'r') as f:
                photos = json.load(f)
            await ctx.send(random.choice(list(photos.values())))
        except:
            await ctx.send("No photos found.")

    @commands.command()
    async def social(self, ctx):
        embed = discord.Embed(title="🌐 Socials", description="[Website](https://hutcch.neocities.org/html/Links-Page)\n[YouTube](https://www.youtube.com/channel/UCbhfUDBi3YEXRTJGI5EXtQQ)", color=0x3498db)
        await ctx.send(embed=embed)

    @commands.command()
    async def report(self, ctx, member: discord.Member, *, reason):
        chan = self.bot.get_channel(1309979922319540305)
        if chan:
            await chan.send(f"🚨 **Report**\nTarget: {member.mention}\nBy: {ctx.author.mention}\nReason: {reason}")
            await ctx.send("Report submitted.")

async def setup(bot):
    await bot.add_cog(Utility(bot))
