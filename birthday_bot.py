# ================== 기본 설정 ==================
import os
import sqlite3
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def get_kst_now():
    return datetime.now(ZoneInfo("Asia/Seoul"))

TOKEN = os.getenv("TOKEN")

GUILD_ID = 1377672440276058214
CHANNEL_ID = 1377672440783704219
ROLE_ID = 1482668657178972300
NOTICE_CHANNEL_ID = 1397125455454273578

# ✅ 규칙 관련
RULE_ROLE_ID = 1486079820160041131
RULE_LOG_CHANNEL_ID = 1397124964246622238

# ✅ 생일 역할
BIRTHDAY_ROLE_ID = 1482668657178972300

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================== DB ==================
conn = sqlite3.connect("/data/birthday.db")
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS birthdays(user_id TEXT PRIMARY KEY, date TEXT)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS congrats(message_id TEXT, user_id TEXT)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS congrats_count(user_id TEXT PRIMARY KEY, count INTEGER)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS announced(user_id TEXT, date TEXT)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS scheduled_notices(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, send_time TEXT)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS notice_reactions(message_id TEXT, user_id TEXT, type TEXT)""")

# ✅ 추가 테이블
cursor.execute("""CREATE TABLE IF NOT EXISTS rule_confirm(message_id TEXT, user_id TEXT)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS birthday_messages(message_id TEXT PRIMARY KEY, user_id TEXT)""")

conn.commit()

# ================== 생일 축하 버튼 ==================
class BirthdayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎁 축하하기 (0)", style=discord.ButtonStyle.green, custom_id="birthday_congrats")
    async def congrats(self, interaction: discord.Interaction, button: discord.ui.Button):

        cursor.execute("SELECT * FROM congrats WHERE message_id=? AND user_id=?", (interaction.message.id, interaction.user.id))
        if cursor.fetchone():
            await interaction.response.send_message("이미 축하했습니다 🎂", ephemeral=True)
            return

        cursor.execute("INSERT INTO congrats VALUES (?,?)", (interaction.message.id, interaction.user.id))
        cursor.execute("INSERT OR IGNORE INTO congrats_count VALUES (?,0)", (interaction.user.id,))
        cursor.execute("UPDATE congrats_count SET count=count+1 WHERE user_id=?", (interaction.user.id,))
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM congrats WHERE message_id=?", (interaction.message.id,))
        count = cursor.fetchone()[0]

        button.label = f"🎁 축하하기 ({count})"
        await interaction.message.edit(view=self)

        # 🎉 생일 주인에게 DM
        cursor.execute("SELECT user_id FROM birthday_messages WHERE message_id=?", (interaction.message.id,))
        result = cursor.fetchone()

        if result:
            member = interaction.guild.get_member(int(result[0]))
            if member:
                try:
                    await member.send(f"🎉 {interaction.user.display_name}님이 생일을 축하했습니다!")
                except:
                    pass

        await interaction.response.send_message("🎉 축하 완료!", ephemeral=True)

# ================== 생일 목록 ==================
class BirthdayListView(discord.ui.View):
    def __init__(self, data, per_page=10):
        super().__init__(timeout=180)
        self.data = data
        self.per_page = per_page
        self.page = 0
        self.max_page = (len(data) - 1) // per_page

    def update_buttons(self):
        self.prev.disabled = self.page == 0
        self.next.disabled = self.page == self.max_page

    def get_embed(self):
        self.update_buttons()
        now = get_kst_now()

        start = self.page * self.per_page
        chunk = self.data[start:start+self.per_page]

        desc = ""
        for member, date in chunk:
            m, d = map(int, date.split("-"))
            if m == now.month and d == now.day:
                desc += f"🎉 **{member.display_name}** - {date} (오늘!)\n"
            elif m == now.month:
                desc += f"⭐ **{member.display_name}** - {date}\n"
            else:
                desc += f"{member.display_name} - {date}\n"

        embed = discord.Embed(title="🎂 생일 목록", description=desc or "데이터 없음", color=0xff69b4)
        embed.set_footer(text=f"{self.page+1}/{self.max_page+1} 페이지")
        return embed

    @discord.ui.button(label="◀ 이전", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="▶ 다음", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_page:
            self.page += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

# ================== 공지 버튼 ==================
class NoticeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update(self, message):
        counts = {"참여":0,"불참":0,"좋아요":0}
        cursor.execute("SELECT type, COUNT(*) FROM notice_reactions WHERE message_id=? GROUP BY type",(message.id,))
        for t,c in cursor.fetchall():
            counts[t]=c

        for item in self.children:
            if item.custom_id=="join":
                item.label=f"🙋 참여 ({counts['참여']})"
            elif item.custom_id=="no":
                item.label=f"❌ 불참 ({counts['불참']})"
            elif item.custom_id=="like":
                item.label=f"👍 좋아요 ({counts['좋아요']})"

        await message.edit(view=self)

    async def handle(self, interaction, t):
        cursor.execute("SELECT * FROM notice_reactions WHERE message_id=? AND user_id=?",(interaction.message.id,interaction.user.id))
        if cursor.fetchone():
            cursor.execute("UPDATE notice_reactions SET type=? WHERE message_id=? AND user_id=?",(t,interaction.message.id,interaction.user.id))
        else:
            cursor.execute("INSERT INTO notice_reactions VALUES (?,?,?)",(interaction.message.id,interaction.user.id,t))
        conn.commit()
        await self.update(interaction.message)
        await interaction.response.send_message("반영 완료", ephemeral=True)

    @discord.ui.button(label="🙋 참여 (0)", style=discord.ButtonStyle.success, custom_id="join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle(interaction,"참여")

    @discord.ui.button(label="❌ 불참 (0)", style=discord.ButtonStyle.danger, custom_id="no")
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle(interaction,"불참")

    @discord.ui.button(label="👍 좋아요 (0)", style=discord.ButtonStyle.primary, custom_id="like")
    async def like(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle(interaction,"좋아요")

# ================== 규칙 확인 버튼 ==================
class RuleConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_count(self, message):
        cursor.execute("SELECT COUNT(*) FROM rule_confirm WHERE message_id=?", (message.id,))
        count = cursor.fetchone()[0]

        for item in self.children:
            if item.custom_id == "rule_confirm":
                item.label = f"✅ 규칙 확인 ({count})"

        await message.edit(view=self)

    @discord.ui.button(label="✅ 규칙 확인 (0)", style=discord.ButtonStyle.success, custom_id="rule_confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):

        cursor.execute("SELECT * FROM rule_confirm WHERE message_id=? AND user_id=?",
                       (interaction.message.id, interaction.user.id))
        if cursor.fetchone():
            await interaction.response.send_message("이미 인증 완료된 상태입니다.", ephemeral=True)
            return

        cursor.execute("INSERT INTO rule_confirm VALUES (?,?)",
                       (interaction.message.id, interaction.user.id))
        conn.commit()

        role = interaction.guild.get_role(RULE_ROLE_ID)
        if role and role not in interaction.user.roles:
            await interaction.user.add_roles(role)

        await self.update_count(interaction.message)

        log_channel = interaction.guild.get_channel(RULE_LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"✅ {interaction.user.mention} 님이 규칙 확인")

        await interaction.response.send_message("🎉 규칙 확인 완료!", ephemeral=True)

# ================== 명령어 ==================

@bot.tree.command(name="공지")
@app_commands.checks.has_permissions(administrator=True)
async def notice(interaction: discord.Interaction, 제목: str, 내용: str):
    channel = bot.get_channel(NOTICE_CHANNEL_ID)

    content_with_breaks = 내용.replace("|", "\n")

    banner=f"""
━━━━━━━━━━━━━━━━━━
📢 **{제목}**
━━━━━━━━━━━━━━━━━━

{content_with_breaks}

👇 아래 버튼 클릭
"""

    embed=discord.Embed(description=banner,color=0x5865F2)
    embed.set_footer(text=f"쫀놈이 | {interaction.user.display_name}")
    embed.timestamp=get_kst_now()

    await channel.send(content="@everyone", embed=embed, view=NoticeView())
    await interaction.response.send_message("공지 완료",ephemeral=True)

@bot.tree.command(name="공지통계")
async def stats(interaction: discord.Interaction, message_id: str):

    cursor.execute(
        "SELECT user_id, type FROM notice_reactions WHERE message_id=?",
        (message_id,)
    )

    data = cursor.fetchall()

    grouped = {
        "참여": [],
        "불참": [],
        "좋아요": []
    }

    for user_id, t in data:
        member = interaction.guild.get_member(int(user_id))
        if member:
            grouped[t].append(member.display_name)

    result = "📊 공지 통계\n\n"

    total = len(data)

    for t in ["참여", "불참", "좋아요"]:
        users = grouped[t]
        count = len(users)
        percent = (count / total * 100) if total > 0 else 0

        result += f"**{t} ({count}명 / {percent:.1f}%)**\n"

        if users:
            for name in users:
                result += f"- {name}\n"
        else:
            result += "- 없음\n"

        result += "\n"

    await interaction.response.send_message(result)

@bot.tree.command(name="규칙")
@app_commands.checks.has_permissions(administrator=True)
async def rule(interaction: discord.Interaction, 내용: str):

    desc = f"""
📌 **클랜 규칙 안내**
━━━━━━━━━━━━━━━━━━

{내용.replace("|", "\n")}

━━━━━━━━━━━━━━━━━━
🎮 위 규칙을 정독해 주세요!

👇 아래 버튼 클릭
"""

    embed = discord.Embed(description=desc, color=0x2ecc71)
    embed.timestamp = get_kst_now()

    await interaction.channel.send(embed=embed, view=RuleConfirmView())
    await interaction.response.send_message("규칙 전송 완료", ephemeral=True)

@bot.tree.command(name="규칙통계")
async def rule_stats(interaction: discord.Interaction, message_id: str):

    cursor.execute("SELECT user_id FROM rule_confirm WHERE message_id=?", (message_id,))
    data = cursor.fetchall()

    names = []
    for (uid,) in data:
        m = interaction.guild.get_member(int(uid))
        if m:
            names.append(m.display_name)

    result = f"📊 규칙 확인 인원 ({len(names)}명)\n\n"
    result += "\n".join([f"- {n}" for n in names]) if names else "없음"

    await interaction.response.send_message(result)

@bot.tree.command(name="생일등록")
@app_commands.checks.has_permissions(administrator=True)
async def add_birthday(interaction: discord.Interaction, member: discord.Member, date: str):
    cursor.execute("INSERT OR REPLACE INTO birthdays VALUES (?,?)",(member.id,date))
    conn.commit()
    await interaction.response.send_message("등록 완료",ephemeral=True)

@bot.tree.command(name="생일목록")
async def birthday_list(interaction: discord.Interaction):
    cursor.execute("SELECT * FROM birthdays")
    data=cursor.fetchall()

    lst=[]
    for uid,date in data:
        m=interaction.guild.get_member(int(uid))
        if m:
            lst.append((m,date))

    lst.sort(key=lambda x:tuple(map(int,x[1].split("-"))))

    view=BirthdayListView(lst)
    await interaction.response.send_message(embed=view.get_embed(),view=view)

# ================== 루프 ==================
@tasks.loop(minutes=1)
async def birthday_loop():
    now = get_kst_now()

    if now.strftime("%H:%M") == "00:00":

        guild = bot.get_guild(GUILD_ID)
        channel = bot.get_channel(CHANNEL_ID)

        today = now.strftime("%m-%d")

        # 생일 시작
        cursor.execute("SELECT user_id FROM birthdays WHERE date=?", (today,))
        users = cursor.fetchall()

        for (uid,) in users:
            member = guild.get_member(int(uid))
            if not member:
                continue

            role = guild.get_role(BIRTHDAY_ROLE_ID)
            if role and role not in member.roles:
                await member.add_roles(role)

            try:
                if "🎂" not in member.display_name:
                    await member.edit(nick=f"{member.display_name} 🎂")
            except:
                pass

            msg = await channel.send(
                f"🎂 **오늘은 {member.mention}님의 생일입니다!** 🎉\n\n다 같이 축하해주세요 👇",
                view=BirthdayView()
            )

            cursor.execute("INSERT INTO birthday_messages VALUES (?, ?)", (msg.id, uid))
            conn.commit()

        # 생일 종료
        yesterday = (now - timedelta(days=1)).strftime("%m-%d")

        cursor.execute("SELECT user_id FROM birthdays WHERE date=?", (yesterday,))
        users = cursor.fetchall()

        for (uid,) in users:
            member = guild.get_member(int(uid))
            if not member:
                continue

            role = guild.get_role(BIRTHDAY_ROLE_ID)
            if role and role in member.roles:
                await member.remove_roles(role)

            try:
                if "🎂" in member.display_name:
                    await member.edit(nick=member.display_name.replace(" 🎂", ""))
            except:
                pass

# ================== READY ==================
@bot.event
async def on_ready():
    guild=discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)

    bot.add_view(BirthdayView())
    bot.add_view(NoticeView())
    bot.add_view(RuleConfirmView())

    birthday_loop.start()

    print("쫀놈이 ON")

bot.run(TOKEN)
