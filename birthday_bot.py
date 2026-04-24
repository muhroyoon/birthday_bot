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
UPGRADE_LOG_CHANNEL_ID = 1490954873192185999
LEAVE_LOG_CHANNEL_ID = 1397126595092811848

RULE_ROLE_ID = 1486079820160041131
RULE_LOG_CHANNEL_ID = 1397124964246622238

BIRTHDAY_ROLE_ID = 1482668657178972300
NEW_MEMBER_ROLE_ID = 1481662617859657790

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ================== DB ==================
conn = sqlite3.connect("/data/birthday.db")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS birthdays(user_id TEXT PRIMARY KEY, date TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS congrats(message_id TEXT, user_id TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS congrats_count(user_id TEXT PRIMARY KEY, count INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS announced(user_id TEXT, date TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS scheduled_notices(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, send_time TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS rule_confirm(message_id TEXT, user_id TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS birthday_messages(message_id TEXT PRIMARY KEY, user_id TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS probation_roles(user_id TEXT PRIMARY KEY, assigned_at TEXT, notified INTEGER DEFAULT 0)")

conn.commit()

# ================== 신입 역할 추적 함수 ==================
def dt_to_db(value: datetime) -> str:
    return value.isoformat()

def dt_from_db(value: str) -> datetime:
    return datetime.fromisoformat(value)

async def backfill_probation_members():
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        return

    probation_role = guild.get_role(NEW_MEMBER_ROLE_ID)
    if probation_role is None:
        return

    now = get_kst_now()
    for member in probation_role.members:
        cursor.execute("SELECT assigned_at FROM probation_roles WHERE user_id=?", (str(member.id),))
        row = cursor.fetchone()
        if row:
            continue

        assigned_at = now
        if member.joined_at is not None:
            assigned_at = member.joined_at.astimezone(ZoneInfo("Asia/Seoul"))

        cursor.execute(
            "INSERT OR REPLACE INTO probation_roles(user_id, assigned_at, notified) VALUES (?, ?, 0)",
            (str(member.id), dt_to_db(assigned_at)),
        )

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
            m, d = map(int, date.split("-"))
            if m == now.month and d == now.day:
                desc += f"🎉 **{member.display_name}** - {date} (오늘!)\n"
            elif m == now.month:
                desc += f"⭐ **{member.display_name}** - {date}\n"
            else:
                desc += f"{member.display_name} - {date}\n"

        embed = discord.Embed(title="🎂 생일 목록", description=desc or "데이터 없음", color=0xff69b4)
        embed.set_footer(text=f"{self.page+1}/{self.max_page+1}")
        return embed

    @discord.ui.button(label="◀ 이전")
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="▶ 다음")
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_page:
            self.page += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

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

        await self.update_count(interaction.message)

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

# ================== 티켓 VIEW ==================
class UpgradeTicketView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user

    def is_admin(self, interaction: discord.Interaction):
        admin_roles = [1482028706850537676, 1409209830152863845]
        user_roles = [role.id for role in interaction.user.roles]
        return any(role_id in user_roles for role_id in admin_roles)

    async def disable_buttons_except_delete(self, message):
        for item in self.children:
            if item.custom_id != "ticket_delete":
                item.disabled = True
        await message.edit(view=self)

    async def send_log(self, interaction, action):
        log_channel = interaction.guild.get_channel(UPGRADE_LOG_CHANNEL_ID)
        if log_channel:
            embed = discord.Embed(title="📋 등업 로그", color=0x3498db)
            embed.add_field(name="대상", value=self.user.mention, inline=True)
            embed.add_field(name="처리자", value=interaction.user.mention, inline=True)
            embed.add_field(name="결과", value=action, inline=False)
            embed.timestamp = datetime.now()
            await log_channel.send(embed=embed)

    @discord.ui.button(label="클랜원등업", style=discord.ButtonStyle.primary, custom_id="upgrade_clan")
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

        await self.disable_buttons_except_delete(interaction.message)

        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            send_messages=False
        )

        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="게스트등업", style=discord.ButtonStyle.secondary, custom_id="upgrade_guest")
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

        await self.disable_buttons_except_delete(interaction.message)

        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            send_messages=False
        )

        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="티켓삭제", style=discord.ButtonStyle.danger, custom_id="ticket_delete")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        await interaction.response.send_message("삭제 중...")
        await interaction.channel.delete()

# ================== 시간대 설정 VIEW ==================
class TimeRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.roles = {
            "morning": 1494997225192030369,
            "afternoon": 1494997272641929298,
            "evening": 1494997462266544188,
            "night": 1494997501231759490,
            "dawn": 1494997538879832074
        }

    async def add_role(self, interaction, role_id):
        role = interaction.guild.get_role(role_id)

        if role in interaction.user.roles:
            await interaction.response.send_message("이미 선택된 시간대입니다.", ephemeral=True)
            return

        await interaction.user.add_roles(role)
        await interaction.response.send_message(f"{role.name} 역할이 추가되었습니다.", ephemeral=True)

    @discord.ui.button(label="오전반", style=discord.ButtonStyle.primary, custom_id="time_morning")
    async def morning(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, self.roles["morning"])

    @discord.ui.button(label="오후반", style=discord.ButtonStyle.primary, custom_id="time_afternoon")
    async def afternoon(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, self.roles["afternoon"])

    @discord.ui.button(label="저녁반", style=discord.ButtonStyle.primary, custom_id="time_evening")
    async def evening(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, self.roles["evening"])

    @discord.ui.button(label="심야반", style=discord.ButtonStyle.secondary, custom_id="time_night")
    async def night(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, self.roles["night"])

    @discord.ui.button(label="새벽반", style=discord.ButtonStyle.secondary, custom_id="time_dawn")
    async def dawn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, self.roles["dawn"])

    @discord.ui.button(label="리셋", style=discord.ButtonStyle.danger, custom_id="time_reset")
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        removed = []

        for role_id in self.roles.values():
            role = interaction.guild.get_role(role_id)
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                removed.append(role.name)

        if removed:
            await interaction.response.send_message(f"삭제된 역할: {', '.join(removed)}", ephemeral=True)
        else:
            await interaction.response.send_message("삭제할 시간대 역할이 없습니다.", ephemeral=True)

# ================== 명령어 ==================
@bot.tree.command(name="생일등록")
async def add_birthday(interaction: discord.Interaction, member: discord.Member, date: str):
    cursor.execute("INSERT OR REPLACE INTO birthdays VALUES (?,?)", (member.id, date))
    conn.commit()
    await interaction.response.send_message("등록 완료", ephemeral=True)

@bot.tree.command(name="생일삭제")
async def remove_birthday(interaction: discord.Interaction, member: discord.Member):
    cursor.execute("DELETE FROM birthdays WHERE user_id=?", (member.id,))
    conn.commit()
    await interaction.response.send_message("삭제 완료", ephemeral=True)

@bot.tree.command(name="생일목록")
async def birthday_list(interaction: discord.Interaction):
    cursor.execute("SELECT * FROM birthdays")
    data = cursor.fetchall()
    result = [(interaction.guild.get_member(int(uid)), date) for uid, date in data if interaction.guild.get_member(int(uid))]
    result.sort(key=lambda x: tuple(map(int, x[1].split("-"))))
    view = BirthdayListView(result)
    await interaction.response.send_message(embed=view.get_embed(), view=view)

@bot.tree.command(name="규칙버튼")
@app_commands.checks.has_permissions(administrator=True)
async def rule_button(interaction: discord.Interaction):
    embed = discord.Embed(
        description="""원활한 게임을 위해 클랜 규칙을 정독해 주세요!!
확인 후 아래 버튼을 눌러주세요!""",
        color=0x2ecc71
    )

    await interaction.channel.send(embed=embed, view=RuleConfirmView())
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

@bot.tree.command(name="시간설정패널")
async def time_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="플레이 시간대 설정",
        description="원하는 시간대를 선택해주세요!\n중복 선택 가능합니다.",
        color=0x5865F2
    )

    await interaction.channel.send(embed=embed, view=TimeRoleView())
    await interaction.response.send_message("시간 설정 패널 생성 완료", ephemeral=True)

# ================== 신입 역할 자동 기록 ==================
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    before_role_ids = {role.id for role in before.roles}
    after_role_ids = {role.id for role in after.roles}

    if NEW_MEMBER_ROLE_ID not in before_role_ids and NEW_MEMBER_ROLE_ID in after_role_ids:
        cursor.execute(
            "INSERT OR REPLACE INTO probation_roles(user_id, assigned_at, notified) VALUES (?, ?, 0)",
            (str(after.id), dt_to_db(get_kst_now())),
        )
        conn.commit()

    if NEW_MEMBER_ROLE_ID in before_role_ids and NEW_MEMBER_ROLE_ID not in after_role_ids:
        cursor.execute("DELETE FROM probation_roles WHERE user_id=?", (str(after.id),))
        conn.commit()

# ================== 서버 퇴장 로그 ==================
@bot.event
async def on_member_remove(member: discord.Member):
    if member.guild.id != GUILD_ID:
        return

    channel = bot.get_channel(LEAVE_LOG_CHANNEL_ID)
    if channel is None:
        return

    embed = discord.Embed(
        title="📤 서버 퇴장",
        color=0xE74C3C,
        timestamp=get_kst_now(),
    )
    embed.add_field(name="닉네임", value=member.display_name, inline=False)
    embed.add_field(name="계정명", value=str(member), inline=False)
    embed.add_field(name="유저 ID", value=str(member.id), inline=False)
    embed.add_field(name="시간", value=get_kst_now().strftime("%Y-%m-%d %H:%M:%S KST"), inline=False)

    if member.display_avatar:
        embed.set_thumbnail(url=member.display_avatar.url)

    await channel.send(embed=embed)

# ================== 신입 역할 7일 경과 체크 ==================
@tasks.loop(hours=1)
async def probation_role_check_loop():
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        return

    channel = bot.get_channel(RULE_LOG_CHANNEL_ID)
    if channel is None:
        return

    probation_role = guild.get_role(NEW_MEMBER_ROLE_ID)
    if probation_role is None:
        return

    now = get_kst_now()
    due_time = now - timedelta(days=7)

    cursor.execute("SELECT user_id, assigned_at FROM probation_roles WHERE notified=0")
    rows = cursor.fetchall()

    for user_id, assigned_at_raw in rows:
        assigned_at = dt_from_db(assigned_at_raw)
        if assigned_at > due_time:
            continue

        member = guild.get_member(int(user_id))
        if member is None or probation_role not in member.roles:
            cursor.execute("DELETE FROM probation_roles WHERE user_id=?", (user_id,))
            conn.commit()
            continue

        joined_text = "알 수 없음"
        if member.joined_at is not None:
            joined_text = member.joined_at.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S KST")

        embed = discord.Embed(
            title="⏰ 신입 역할 7일 경과 알림",
            description="출석률과 평판을 확인한 뒤 신입 역할 제거 여부를 검토해주세요.",
            color=0xF1C40F,
            timestamp=now,
        )
        embed.add_field(name="닉네임", value=member.display_name, inline=False)
        embed.add_field(name="계정명", value=str(member), inline=False)
        embed.add_field(name="유저 ID", value=str(member.id), inline=False)
        embed.add_field(name="서버 입장일", value=joined_text, inline=False)
        embed.add_field(name="신입 역할 부여 시각", value=assigned_at.strftime("%Y-%m-%d %H:%M:%S KST"), inline=False)
        embed.add_field(
            name="확인 안내",
            value=f"{member.mention}\n출석과 평판 확인 후 역할을 조정해주세요.",
            inline=False,
        )

        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)

        await channel.send(content=member.mention, embed=embed)

        cursor.execute("UPDATE probation_roles SET notified=1 WHERE user_id=?", (user_id,))
        conn.commit()

# ================== 생일 루프 ==================
@tasks.loop(minutes=1)
async def birthday_loop():
    now = get_kst_now()
    guild = bot.get_guild(GUILD_ID)

    if now.strftime("%H:%M") == "00:00":
        channel = bot.get_channel(CHANNEL_ID)

        cursor.execute("SELECT user_id FROM birthdays WHERE date=?", (now.strftime("%m-%d"),))
        for (uid,) in cursor.fetchall():
            member = guild.get_member(int(uid))
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

            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="🎁 버튼 눌러서 축하해보세요!")

            msg = await channel.send(embed=embed, view=BirthdayView())

            cursor.execute("INSERT INTO birthday_messages VALUES (?,?)", (msg.id, uid))
            conn.commit()

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
    guild = discord.Object(id=GUILD_ID)

    bot.tree.clear_commands(guild=guild)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)

    bot.add_view(BirthdayView())
    bot.add_view(RuleConfirmView())
    bot.add_view(UpgradePanelView())
    bot.add_view(TimeRoleView())

    await backfill_probation_members()

    if not birthday_loop.is_running():
        birthday_loop.start()

    if not probation_role_check_loop.is_running():
        probation_role_check_loop.start()

    print("봇 실행 완료")

bot.run(TOKEN)
