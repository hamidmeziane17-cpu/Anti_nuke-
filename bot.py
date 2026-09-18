import discord
from discord.ext import commands, tasks
import os
import time
import asyncio
from threading import Thread
from flask import Flask
from collections import defaultdict, deque

# ============================================================
# 1. خادم الويب
# ============================================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is online and running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web, daemon=True).start()

# ============================================================
# 2. إعدادات البوت
# ============================================================
MY_ID = 1320438836878118973  # ضع ID المطور هنا

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.moderation = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ============================================================
# 3. تخزين الحالات (Snapshots + سجل الأحداث)
# ============================================================

# لقطة لكل سيرفر لمقارنة الأعداد
snapshots = {}  # {guild_id: {"channels": int, "members_set": set, ...}}

# سجل زمني لعمليات الحذف/الطرد/الحظر لكل سيرفر
# deque يحفظ آخر الأحداث مع توقيتها
event_log = {
    "channel_delete": defaultdict(lambda: deque(maxlen=50)),
    "member_kick":    defaultdict(lambda: deque(maxlen=50)),
    "member_ban":     defaultdict(lambda: deque(maxlen=50)),
}

# عتبة الحماية: عدد الأحداث خلال النافذة الزمنية
WINDOW = 5  # ثوانٍ
CHANNEL_DELETE_LIMIT = 3
KICK_LIMIT = 2
BAN_LIMIT = 2

# ============================================================
# 4. دوال مساعدة
# ============================================================

def count_recent(guild_id, event_type, seconds=WINDOW):
    """حساب عدد الأحداث خلال آخر X ثانية"""
    now = time.time()
    events = event_log[event_type][guild_id]
    return sum(1 for t in events if now - t <= seconds)


def log_event(guild_id, event_type):
    """تسجيل حدث جديد"""
    event_log[event_type][guild_id].append(time.time())


async def get_audit_actor(guild, action, max_age=10):
    """جلب من قام بالعملية من سجل التدقيق"""
    try:
        async for entry in guild.audit_logs(limit=5, action=action):
            if time.time() - entry.created_at.timestamp() <= max_age:
                return entry.user
    except Exception as e:
        print(f"⚠️ فشل قراءة Audit Log: {e}")
    return None


async def punish_attacker(guild, user, reason):
    """طرد الفاعل مع إزالة رتبه أولاً لتعطيل قدراته"""
    if user is None:
        return
    if user.id in (guild.owner_id, MY_ID, bot.user.id):
        return

    try:
        member = guild.get_member(user.id)
        if member:
            # إزالة كل الرتب فوراً لتعطيله حتى لا يواصل الهجوم
            try:
                await member.edit(roles=[], reason=f"Anti-Nuke: {reason}")
            except Exception as e:
                print(f"⚠️ فشل إزالة الرتب: {e}")

        # طرد العضو
        await guild.kick(user, reason=f"Anti-Nuke: {reason}")
        print(f"👢 تم طرد {user} ({user.id}) - السبب: {reason}")

        # إشعار المطور
        try:
            dev = await bot.fetch_user(MY_ID)
            await dev.send(
                f"🚨 **تنبيه أمني** 🚨\n"
                f"**السيرفر:** {guild.name}\n"
                f"**الفاعل:** {user.mention} (`{user.id}`)\n"
                f"**السبب:** {reason}\n"
                f"✅ تم طرده تلقائياً."
            )
        except:
            pass

    except discord.Forbidden:
        print(f"❌ لا توجد صلاحية لطرد {user} (رتبته أعلى من البوت)")
    except Exception as e:
        print(f"❌ فشل طرد {user}: {e}")


# ============================================================
# 5. مراقبة دورية كل ثانية (الحماية الأساسية)
# ============================================================

@tasks.loop(seconds=1)
async def monitor_guilds():
    """فحص كل سيرفر كل ثانية لاكتشاف الهجمات"""
    for guild in bot.guilds:
        try:
            gid = guild.id
            
            # ----- لقطة أولية -----
            current_channels = set(c.id for c in guild.channels)
            current_members = set(m.id for m in guild.members)
            
            if gid not in snapshots:
                snapshots[gid] = {
                    "channels": current_channels,
                    "members": current_members,
                    "initialized": True
                }
                continue
            
            snap = snapshots[gid]
            prev_channels = snap["channels"]
            prev_members = snap["members"]
            
            # ----- حساب الفروقات -----
            deleted_channels = prev_channels - current_channels
            added_members = current_members - prev_members   # (للعلم فقط)
            removed_members = prev_members - current_members  # قد يكون طرد/حظر/مغادرة
            
            # ============================================================
            # (أ) اكتشاف حذف القنوات
            # ============================================================
            if deleted_channels:
                for _ in deleted_channels:
                    log_event(gid, "channel_delete")
                
                recent = count_recent(gid, "channel_delete")
                print(f"🗑️ [{guild.name}] حُذفت {len(deleted_channels)} قناة | إجمالي آخر {WINDOW}ث: {recent}")
                
                if recent >= CHANNEL_DELETE_LIMIT:
                    actor = await get_audit_actor(
                        guild,
                        discord.AuditLogAction.channel_delete,
                        max_age=WINDOW
                    )
                    await punish_attacker(
                        guild, actor,
                        f"حذف {recent} قنوات خلال {WINDOW} ثوانٍ"
                    )
                    # تصفير السجل لتجنب تكرار العقوبة
                    event_log["channel_delete"][gid].clear()
            
            # ============================================================
            # (ب) اكتشاف الطرد والحظر
            # ============================================================
            if removed_members:
                # نحتاج معرفة هل السبب طرد أم حظر أم مغادرة عادية
                # نتحقق من Audit Log لكل نوع
                try:
                    # حظر؟
                    async for entry in guild.audit_logs(
                        limit=10,
                        action=discord.AuditLogAction.ban
                    ):
                        if time.time() - entry.created_at.timestamp() <= 3:
                            if entry.target.id in removed_members:
                                log_event(gid, "member_ban")
                                print(f"🔨 [{guild.name}] حظر: {entry.target} بواسطة {entry.user}")
                except:
                    pass
                
                try:
                    # طرد؟
                    async for entry in guild.audit_logs(
                        limit=10,
                        action=discord.AuditLogAction.kick
                    ):
                        if time.time() - entry.created_at.timestamp() <= 3:
                            if entry.target.id in removed_members:
                                log_event(gid, "member_kick")
                                print(f"👢 [{guild.name}] طرد: {entry.target} بواسطة {entry.user}")
                except:
                    pass
                
                # فحص عتبة الحظر
                recent_ban = count_recent(gid, "member_ban")
                if recent_ban >= BAN_LIMIT:
                    actor = await get_audit_actor(
                        guild,
                        discord.AuditLogAction.ban,
                        max_age=WINDOW
                    )
                    await punish_attacker(
                        guild, actor,
                        f"حظر {recent_ban} أعضاء خلال {WINDOW} ثوانٍ"
                    )
                    event_log["member_ban"][gid].clear()
                
                # فحص عتبة الطرد
                recent_kick = count_recent(gid, "member_kick")
                if recent_kick >= KICK_LIMIT:
                    actor = await get_audit_actor(
                        guild,
                        discord.AuditLogAction.kick,
                        max_age=WINDOW
                    )
                    await punish_attacker(
                        guild, actor,
                        f"طرد {recent_kick} أعضاء خلال {WINDOW} ثوانٍ"
                    )
                    event_log["member_kick"][gid].clear()
            
            # ----- تحديث اللقطة -----
            snapshots[gid]["channels"] = current_channels
            snapshots[gid]["members"] = current_members
        
        except Exception as e:
            print(f"⚠️ خطأ في مراقبة {guild.name}: {e}")


@bot.event
async def on_ready():
    print(f"✅ البوت متصل كـ {bot.user}")
    print(f"📡 يراقب {len(bot.guilds)} سيرفر")
    if not monitor_guilds.is_running():
        monitor_guilds.start()


# ============================================================
# 6. حماية إضافية: أوامر النيوك المكتوبة
# ============================================================
DANGEROUS_COMMANDS = {
    "nuke", "confirm_nuke", "massban", "masskick",
    "banall", "kickall", "destroy", "raid", "spam"
}

@bot.event
async def on_message(message):
    if not message.guild:
        return await bot.process_commands(message)
    
    content = message.content.strip().lower()
    
    if not content.startswith(bot.command_prefix):
        return await bot.process_commands(message)
    
    command_part = content[len(bot.command_prefix):].split()[0]
    
    # المطور والمالك يمران
    if message.author.id in (MY_ID, message.guild.owner_id):
        return await bot.process_commands(message)
    
    if command_part in DANGEROUS_COMMANDS:
        try:
            await message.delete()
        except:
            pass
        
        if message.author.bot:
            await punish_attacker(
                message.guild, message.author,
                f"بوت حاول تنفيذ أمر خطير: {command_part}"
            )
        else:
            try:
                await message.channel.send(
                    f"⚠️ {message.author.mention}، هذا الأمر محظور!",
                    delete_after=5
                )
            except:
                pass
        return
    
    return await bot.process_commands(message)


# ============================================================
# 7. الأوامر الأساسية
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
async def stats(ctx):
    """عرض إحصائيات الحماية الحالية"""
    gid = ctx.guild.id
    ch = count_recent(gid, "channel_delete")
    kb = count_recent(gid, "member_kick")
    bn = count_recent(gid, "member_ban")
    await ctx.send(
        f"📊 **إحصائيات آخر {WINDOW} ثوانٍ**\n"
        f"🗑️ قنوات محذوفة: `{ch}` / {CHANNEL_DELETE_LIMIT}\n"
        f"👢 أعضاء مطردون: `{kb}` / {KICK_LIMIT}\n"
        f"🔨 أعضاء محظورون: `{bn}` / {BAN_LIMIT}"
    )


# ============================================================
# 8. تشغيل البوت
# ============================================================
TOKEN = os.getenv("TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ خطأ: لم يتم العثور على التوكن!")
