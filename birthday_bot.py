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
NOTICE_CHANNEL_ID = 1397125455454273578
UPGRADE_LOG_CHANNEL_ID = 1490954873192185999

RULE_ROLE_ID = 1486079820160041131
RULE_LOG_CHANNEL_ID = 1397124964246622238

BIRTHDAY_ROLE_ID = 1482668657178972300

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================== DB ==================
conn = sqlite3.connect("/data/birthday.db")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS birthdays(user_id TEXT PRIMARY KEY, date TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS congrats(message_id TEXT, user_id TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS congrats_count(user_id TEXT PRIMARY KEY, count INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS announced(user_id TEXT, date TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS scheduled_notices(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, send_time TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS notice_reactions(message_id TEXT, user_id TEXT, type TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS rule_confirm(message_id TEXT, user_id TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS birthday_messages(message_id TEXT PRIMARY KEY, user_id TEXT)")

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

        # ✅ DM 임베드
        cursor.execute("SELECT user_id FROM birthday_messages WHERE message_id=?", (interaction.message.id,))
        result = cursor.fetchone()

        if result:
            member = interaction.guild.get_member(int(result[0]))
            if member:
                try:
                    embed = discord.Embed(
                        title="🎉 생일 축하 도착!",
                        description=f"**{interaction.user.display_name}님이 당신의 생일을 축하했습니다!** 🎂",
                        color=0xff69b4
                    )
                    embed.add_field(name="💌 메시지", value="서버에서 따뜻한 축하가 도착했어요!", inline=False)
                    embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    embed.set_footer(text="🎊 행복한 생일 보내세요!")

                    await member.send(embed=embed)
                except:
                    pass

        await interaction.response.send_message("🎉 축하 완료!", ephemeral=True)

# ================== 생일 목록 ==================
class BirthdayListView(discord.ui.View):
    def __init__(self, data, per_page=10):
        super().__init__(timeout=180)
        self.data = data
        self.page = 0
        self.per_page = per_page
        self.max_page = (len(data)-1)//per_page if data else 0

    def get_embed(self):
        now = get_kst_now()
        start = self.page*self.per_page
        chunk = self.data[start:start+self.per_page]

        desc = ""
        for member, date in chunk:
            m,d = map(int,date.split("-"))
            if m==now.month and d==now.day:
                desc += f"🎉 **{member.display_name}** - {date} (오늘!)\n"
            elif m==now.month:
                desc += f"⭐ **{member.display_name}** - {date}\n"
            else:
                desc += f"{member.display_name} - {date}\n"

        embed = discord.Embed(title="🎂 생일 목록", description=desc or "데이터 없음", color=0xff69b4)
        embed.set_footer(text=f"{self.page+1}/{self.max_page+1}")
        return embed

    @discord.ui.button(label="◀ 이전")
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page>0:
            self.page-=1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="▶ 다음")
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page<self.max_page:
            self.page+=1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

# ================== 공지 버튼 ==================
class NoticeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update(self, message):
        counts = {"좋아요":0,"싫어요":0}
        cursor.execute("SELECT type, COUNT(*) FROM notice_reactions WHERE message_id=? GROUP BY type",(message.id,))
        for t,c in cursor.fetchall():
            counts[t]=c

        for item in self.children:
            if item.custom_id=="like":
                item.label=f"👍 좋아요 ({counts['좋아요']})"
            elif item.custom_id=="dislike":
                item.label=f"👎 싫어요 ({counts['싫어요']})"

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

    @discord.ui.button(label="👍 좋아요 (0)", style=discord.ButtonStyle.primary, custom_id="like")
    async def like(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle(interaction,"좋아요")

    @discord.ui.button(label="👎 싫어요 (0)", style=discord.ButtonStyle.danger, custom_id="dislike")
    async def dislike(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle(interaction,"싫어요")

# ================== 규칙 버튼 ==================
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

        cursor.execute(
            "SELECT * FROM rule_confirm WHERE message_id=? AND user_id=?",
            (interaction.message.id, interaction.user.id)
        )

        if cursor.fetchone():
            await interaction.response.send_message("이미 인증 완료된 상태입니다.", ephemeral=True)
            return

        cursor.execute(
            "INSERT INTO rule_confirm VALUES (?,?)",
            (interaction.message.id, interaction.user.id)
        )
        conn.commit()

        role = interaction.guild.get_role(RULE_ROLE_ID)
        if role and role not in interaction.user.roles:
            await interaction.user.add_roles(role)

        # 🔥 카운트 업데이트
        await self.update_count(interaction.message)

        # 🔥 로그 채널 알림
        log_channel = interaction.guild.get_channel(RULE_LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"✅ {interaction.user.mention} 님이 규칙 확인")

        await interaction.response.send_message("🎉 규칙 확인 완료!", ephemeral=True)

# ================== 등업 패널 ==================
class UpgradePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="등업신청", style=discord.ButtonStyle.success, custom_id="upgrade_apply")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild = interaction.guild
        user = interaction.user

        existing = discord.utils.get(guild.channels, name=f"{user.name}-등업신청")
        if existing:
            await interaction.response.send_message("이미 신청 티켓이 있습니다.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True)
        }

        channel = await guild.create_text_channel(
            name=f"{user.name}-등업신청",
            overwrites=overwrites
        )

        admin_roles = [
            guild.get_role(1482028706850537676),
            guild.get_role(1409209830152863845)
        ]
        mentions = " ".join([role.mention for role in admin_roles if role])

        await channel.send(
            content=f"{mentions}\n{user.mention}님이 등업 신청을 하였습니다.\n"
                    f"[자기소개 바로가기](https://discord.com/channels/{guild.id}/1477705269273165904)",
            view=UpgradeTicketView(user)
        )

        await interaction.response.send_message(f"{channel.mention} 생성 완료!", ephemeral=True)

class UpgradeTicketView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user

    def is_admin(self, interaction: discord.Interaction):
        admin_roles = [1482028706850537676, 1409209830152863845]
        user_roles = [role.id for role in interaction.user.roles]
        return any(role_id in user_roles for role_id in admin_roles)

    async def disable_all_buttons(self, message):
        for item in self.children:
            item.disabled = True
        await message.edit(view=self)

    async def send_log(self, interaction, action):
        log_channel = interaction.guild.get_channel(UPGRADE_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(
                title="📋 등업 로그",
                color=0x3498db
            )
            embed.add_field(name="대상", value=self.user.mention, inline=True)
            embed.add_field(name="처리자", value=interaction.user.mention, inline=True)
            embed.add_field(name="결과", value=action, inline=False)
            embed.set_footer(text=f"채널: {interaction.channel.name}")
            embed.timestamp = datetime.now()

            await log_channel.send(embed=embed)

    @discord.ui.button(label="클랜원등업", style=discord.ButtonStyle.primary)
    async def clan(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        role = interaction.guild.get_role(1409208539548876801)
        await self.user.add_roles(role)

        await self.send_log(interaction, "클랜원 등업")

        embed = discord.Embed(
            title="🎉 등업 완료",
            description=f"{self.user.mention}님의 등업이 완료되었습니다!",
            color=0x2ecc71
        )
        embed.add_field(name="처리자", value=interaction.user.mention, inline=True)
        embed.add_field(name="결과", value="클랜원", inline=True)
        embed.set_thumbnail(url=self.user.display_avatar.url)

        await self.disable_all_buttons(interaction.message)
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="게스트등업", style=discord.ButtonStyle.secondary)
    async def guest(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        role = interaction.guild.get_role(1478317433683968041)
        await self.user.add_roles(role)

        await self.send_log(interaction, "게스트 등업")

        embed = discord.Embed(
            title="🎉 등업 완료",
            description=f"{self.user.mention}님의 등업이 완료되었습니다!",
            color=0x95a5a6
        )
        embed.add_field(name="처리자", value=interaction.user.mention, inline=True)
        embed.add_field(name="결과", value="게스트", inline=True)
        embed.set_thumbnail(url=self.user.display_avatar.url)

        await self.disable_all_buttons(interaction.message)
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="티켓완료", style=discord.ButtonStyle.success)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        await self.send_log(interaction, "티켓 완료")
        await interaction.channel.edit(archived=True)
        await interaction.response.send_message("티켓 종료됨")

    @discord.ui.button(label="티켓삭제", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        await self.send_log(interaction, "티켓 삭제")
        await interaction.response.send_message("삭제 중...")
        await interaction.channel.delete()

# ================== 명령어 ==================
@bot.tree.command(name="공지")
async def notice(interaction: discord.Interaction, 제목: str, 내용: str):
    channel = bot.get_channel(NOTICE_CHANNEL_ID)
    embed=discord.Embed(description=내용.replace("|","\n"),color=0x5865F2)
    await channel.send(content="@everyone", embed=embed, view=NoticeView())
    await interaction.response.send_message("공지 완료",ephemeral=True)

@bot.tree.command(name="생일등록")
async def add_birthday(interaction: discord.Interaction, member: discord.Member, date: str):
    cursor.execute("INSERT OR REPLACE INTO birthdays VALUES (?,?)",(member.id,date))
    conn.commit()
    await interaction.response.send_message("등록 완료",ephemeral=True)

@bot.tree.command(name="생일삭제")
async def remove_birthday(interaction: discord.Interaction, member: discord.Member):
    cursor.execute("DELETE FROM birthdays WHERE user_id=?",(member.id,))
    conn.commit()
    await interaction.response.send_message("삭제 완료",ephemeral=True)

@bot.tree.command(name="생일목록")
async def birthday_list(interaction: discord.Interaction):
    cursor.execute("SELECT * FROM birthdays")
    data = cursor.fetchall()
    result=[(interaction.guild.get_member(int(uid)),date) for uid,date in data if interaction.guild.get_member(int(uid))]
    result.sort(key=lambda x: tuple(map(int, x[1].split("-"))))
    view=BirthdayListView(result)
    await interaction.response.send_message(embed=view.get_embed(),view=view)

@bot.tree.command(name="규칙버튼")
@app_commands.checks.has_permissions(administrator=True)
async def rule_button(interaction: discord.Interaction):

    embed = discord.Embed(
        description="""원활한 게임을 위해 클랜 규칙을 정독해 주세요!!
확인 후 아래 버튼을 눌러주세요!""",
        color=0x2ecc71  # 초록색 (사진이랑 동일 느낌)
    )

    await interaction.channel.send(
        embed=embed,
        view=RuleConfirmView()
    )

    await interaction.response.send_message("규칙 버튼 생성 완료", ephemeral=True)

@bot.tree.command(name="등업패널")
@app_commands.checks.has_permissions(administrator=True)
async def upgrade_panel(interaction: discord.Interaction):

    embed = discord.Embed(
        description="""HICKS 클랜 서버 등업 신청 채널입니다!

1. 닉네임 변경 [배그아이디/별명]
2. 자기소개 작성
3. 클랜규칙 확인
4. 출석체크

위 4가지를 완료하시면 아래 버튼을 눌러주세요!""",
        color=0x5865F2
    )

    await interaction.channel.send(embed=embed, view=UpgradePanelView())
    await interaction.response.send_message("등업 패널 생성 완료", ephemeral=True)

# ================== 생일 루프 ==================
@tasks.loop(minutes=1)
async def birthday_loop():
    now = get_kst_now()
    guild = bot.get_guild(GUILD_ID)
    if now.strftime("%H:%M")=="00:00":
        guild=bot.get_guild(GUILD_ID)
        channel=bot.get_channel(CHANNEL_ID)

        cursor.execute("SELECT user_id FROM birthdays WHERE date=?", (now.strftime("%m-%d"),))
        for (uid,) in cursor.fetchall():
            member=guild.get_member(int(uid))
            if not member: 
                continue

            embed = discord.Embed(
                title="🎂 오늘의 주인공 등장!",
                description=f"""
✨🎆✨🎆✨🎆✨🎆✨🎆

🎂🎉 오늘은 {member.mention}님의 생일입니다!!! 🎉🎂

💥🎊 축하 폭격 시작!!! 🎊💥
👇 아래 버튼으로 축하해주세요 👇

✨🎆✨🎆✨🎆✨🎆✨🎆
""",
                color=0xff69b4
            )

            # 🔥 이 두 줄도 반드시 안쪽
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="🎁 버튼 눌러서 축하해보세요!")

            msg = await channel.send(embed=embed, view=BirthdayView())

            cursor.execute("INSERT INTO birthday_messages VALUES (?,?)",(msg.id,uid))
            conn.commit()

    # ================== 생일 종료 처리 ==================

    yesterday = (now - timedelta(days=1)).strftime("%m-%d")

    cursor.execute("SELECT user_id FROM birthdays WHERE date=?", (yesterday,))
    users = cursor.fetchall()

    for (uid,) in users:
        member = guild.get_member(int(uid))
        if not member:
            continue

        role = guild.get_role(BIRTHDAY_ROLE_ID)

        # 역할 제거
        if role and role in member.roles:
            await member.remove_roles(role)

        # 닉네임에서 🎂 제거
        try:
            if "🎂" in member.display_name:
                await member.edit(nick=member.display_name.replace(" 🎂", ""))
        except:
            pass

# ================== READY ==================
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)

    bot.tree.clear_commands(guild=guild)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)

    bot.add_view(BirthdayView())
    bot.add_view(NoticeView())
    bot.add_view(RuleConfirmView())
    bot.add_view(UpgradePanelView())
bot.add_view(UpgradeTicketView(None))

    birthday_loop.start()

    print("봇 실행 완료")

bot.run(TOKEN)
