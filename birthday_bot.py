import os
import random
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks


def get_kst_now():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def normalize_birthday(date_str: str) -> str:
    value = date_str.strip().replace("/", "-").replace(".", "-")
    parts = value.split("-")

    if len(parts) != 2:
        raise ValueError("생일 형식은 MM-DD 로 입력해주세요.")

    month = int(parts[0])
    day = int(parts[1])

    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise ValueError("올바른 날짜를 입력해주세요.")

    return f"{month:02d}-{day:02d}"


def dt_to_db(value: datetime) -> str:
    return value.isoformat()


def dt_from_db(value: str) -> datetime:
    return datetime.fromisoformat(value)


TOKEN = os.getenv("TOKEN")

GUILD_ID = 1377672440276058214
CHANNEL_ID = 1377672440783704219
UPGRADE_LOG_CHANNEL_ID = 1490954873192185999
LEAVE_LOG_CHANNEL_ID = 1397126595092811848

RULE_ROLE_ID = 1486079820160041131
RULE_LOG_CHANNEL_ID = 1397124964246622238

BIRTHDAY_ROLE_ID = 1482668657178972300
NEW_MEMBER_ROLE_ID = 1481662617859657790

WELCOME_GUIDE_CHANNEL_ID = 1498220498155208784

DAILY_REWARD = 10000
MIN_BET = 100
COIN_FLIP_TIMEOUT = 60

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
cursor.execute(
    "CREATE TABLE IF NOT EXISTS scheduled_notices(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, send_time TEXT)"
)
cursor.execute("CREATE TABLE IF NOT EXISTS rule_confirm(message_id TEXT, user_id TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS birthday_messages(message_id TEXT PRIMARY KEY, user_id TEXT)")
cursor.execute(
    "CREATE TABLE IF NOT EXISTS probation_roles(user_id TEXT PRIMARY KEY, assigned_at TEXT, notified INTEGER DEFAULT 0)"
)
cursor.execute("CREATE TABLE IF NOT EXISTS balances(user_id TEXT PRIMARY KEY, balance INTEGER NOT NULL DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS daily_claims(user_id TEXT PRIMARY KEY, last_claim_date TEXT)")

conn.commit()

# ================== 돈 관리 ==================
def ensure_wallet(user_id: int):
    cursor.execute("INSERT OR IGNORE INTO balances(user_id, balance) VALUES (?, 0)", (str(user_id),))
    conn.commit()


def get_balance(user_id: int) -> int:
    ensure_wallet(user_id)
    cursor.execute("SELECT balance FROM balances WHERE user_id=?", (str(user_id),))
    row = cursor.fetchone()
    return row[0] if row else 0


def set_balance(user_id: int, amount: int):
    ensure_wallet(user_id)
    cursor.execute("UPDATE balances SET balance=? WHERE user_id=?", (amount, str(user_id)))
    conn.commit()


def add_balance(user_id: int, amount: int):
    ensure_wallet(user_id)
    cursor.execute("UPDATE balances SET balance=balance+? WHERE user_id=?", (amount, str(user_id)))
    conn.commit()


def can_afford(user_id: int, amount: int) -> bool:
    return get_balance(user_id) >= amount


def format_money(amount: int) -> str:
    return f"{amount:,}원"


# ================== 신입 역할 추적 함수 ==================
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
        if cursor.fetchone():
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
        cursor.execute(
            "SELECT * FROM congrats WHERE message_id=? AND user_id=?",
            (str(interaction.message.id), str(interaction.user.id)),
        )
        if cursor.fetchone():
            await interaction.response.send_message("이미 축하했습니다 🎂", ephemeral=True)
            return

        cursor.execute("INSERT INTO congrats VALUES (?,?)", (str(interaction.message.id), str(interaction.user.id)))
        cursor.execute("INSERT OR IGNORE INTO congrats_count VALUES (?,0)", (str(interaction.user.id),))
        cursor.execute("UPDATE congrats_count SET count=count+1 WHERE user_id=?", (str(interaction.user.id),))
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM congrats WHERE message_id=?", (str(interaction.message.id),))
        count = cursor.fetchone()[0]

        button.label = f"🎁 축하하기 ({count})"
        await interaction.message.edit(view=self)

        cursor.execute("SELECT user_id FROM birthday_messages WHERE message_id=?", (str(interaction.message.id),))
        result = cursor.fetchone()

        if result:
            member = interaction.guild.get_member(int(result[0]))
            if member:
                try:
                    embed = discord.Embed(
                        title="🎉 생일 축하 도착!",
                        description=f"**{interaction.user.display_name}님이 당신의 생일을 축하했습니다!** 🎂",
                        color=0xFF69B4,
                    )
                    embed.add_field(name="💌 메시지", value="서버에서 따뜻한 축하가 도착했어요!", inline=False)
                    embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    embed.set_footer(text="🎊 행복한 생일 보내세요!")
                    await member.send(embed=embed)
                except Exception:
                    pass

        await interaction.response.send_message("🎉 축하 완료!", ephemeral=True)


# ================== 생일 목록 ==================
class BirthdayListView(discord.ui.View):
    def __init__(self, data, per_page=10):
        super().__init__(timeout=180)
        self.data = data
        self.page = 0
        self.per_page = per_page
        self.max_page = (len(data) - 1) // per_page if data else 0

    def get_embed(self):
        now = get_kst_now()
        start = self.page * self.per_page
        chunk = self.data[start:start + self.per_page]

        desc = ""
        for member, date in chunk:
            month, day = map(int, date.split("-"))
            if month == now.month and day == now.day:
                desc += f"🎉 **{member.display_name}** - {date} (오늘!)\n"
            elif month == now.month:
                desc += f"⭐ **{member.display_name}** - {date}\n"
            else:
                desc += f"{member.display_name} - {date}\n"

        embed = discord.Embed(title="🎂 생일 목록", description=desc or "데이터 없음", color=0xFF69B4)
        embed.set_footer(text=f"{self.page + 1}/{self.max_page + 1}")
        return embed

    @discord.ui.button(label="◀ 이전")
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="▶ 다음")
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_page:
            self.page += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()


# ================== 규칙 버튼 ==================
class RuleConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_count(self, message):
        cursor.execute("SELECT COUNT(*) FROM rule_confirm WHERE message_id=?", (str(message.id),))
        count = cursor.fetchone()[0]

        for item in self.children:
            if item.custom_id == "rule_confirm":
                item.label = f"✅ 규칙 확인 ({count})"

        await message.edit(view=self)

    @discord.ui.button(label="✅ 규칙 확인 (0)", style=discord.ButtonStyle.success, custom_id="rule_confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor.execute(
            "SELECT * FROM rule_confirm WHERE message_id=? AND user_id=?",
            (str(interaction.message.id), str(interaction.user.id)),
        )

        if cursor.fetchone():
            await interaction.response.send_message("이미 인증 완료된 상태입니다.", ephemeral=True)
            return

        cursor.execute(
            "INSERT INTO rule_confirm VALUES (?,?)",
            (str(interaction.message.id), str(interaction.user.id)),
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
            guild.me: discord.PermissionOverwrite(view_channel=True),
        }

        channel = await guild.create_text_channel(
            name=f"{user.name}-등업신청",
            overwrites=overwrites,
        )

        admin_roles = [
            guild.get_role(1482028706850537676),
            guild.get_role(1409209830152863845),
        ]
        mentions = " ".join(role.mention for role in admin_roles if role)

        await channel.send(
            content=(
                f"{mentions}\n{user.mention}님이 등업 신청을 하였습니다.\n"
                f"[자기소개 바로가기](https://discord.com/channels/{guild.id}/1477705269273165904)"
            ),
            view=UpgradeTicketView(user),
        )

        await interaction.response.send_message(f"{channel.mention} 생성 완료!", ephemeral=True)


class UpgradeTicketView(discord.ui.View):
    def __init__(self, user: discord.Member):
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
            embed = discord.Embed(title="📋 등업 로그", color=0x3498DB)
            embed.add_field(name="대상", value=self.user.mention, inline=True)
            embed.add_field(name="처리자", value=interaction.user.mention, inline=True)
            embed.add_field(name="결과", value=action, inline=False)
            embed.timestamp = datetime.now()
            await log_channel.send(embed=embed)

    async def send_welcome_dm(self):
        try:
            await self.user.send(
                f"""안녕하세요 {self.user.mention}님! 저희 HICKS에 오신 걸 환영합니다!
저희 서버를 알기 쉽게 <#{WELCOME_GUIDE_CHANNEL_ID}> 여기에 정리해 두었어요!!
궁금하신 점이 있거나 불편하신 점이 있으시면 언제든 관리자에게 문의 부탁드립니다!
즐겜하세요!!"""
            )
        except Exception:
            pass

    @discord.ui.button(label="클랜원등업", style=discord.ButtonStyle.primary, custom_id="upgrade_clan")
    async def clan(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        role = interaction.guild.get_role(1409208539548876801)
        if role:
            await self.user.add_roles(role)
        await self.send_welcome_dm()
        await self.send_log(interaction, "클랜원 등업")

        embed = discord.Embed(
            title="🎉 등업 완료",
            description=f"{self.user.mention}님의 등업이 완료되었습니다!",
            color=0x2ECC71,
        )
        embed.add_field(name="처리자", value=interaction.user.mention, inline=True)
        embed.add_field(name="결과", value="클랜원", inline=True)
        embed.set_thumbnail(url=self.user.display_avatar.url)

        await self.disable_buttons_except_delete(interaction.message)
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="게스트등업", style=discord.ButtonStyle.secondary, custom_id="upgrade_guest")
    async def guest(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        role = interaction.guild.get_role(1478317433683968041)
        if role:
            await self.user.add_roles(role)
        await self.send_welcome_dm()
        await self.send_log(interaction, "게스트 등업")

        embed = discord.Embed(
            title="🎉 등업 완료",
            description=f"{self.user.mention}님의 등업이 완료되었습니다!",
            color=0x95A5A6,
        )
        embed.add_field(name="처리자", value=interaction.user.mention, inline=True)
        embed.add_field(name="결과", value="게스트", inline=True)
        embed.set_thumbnail(url=self.user.display_avatar.url)

        await self.disable_buttons_except_delete(interaction.message)
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
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
            "dawn": 1494997538879832074,
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


# ================== 동전 던지기 VIEW ==================
class CoinFlipView(discord.ui.View):
    def __init__(self, user_id: int, bet_amount: int):
        super().__init__(timeout=COIN_FLIP_TIMEOUT)
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 명령어를 사용한 사람만 누를 수 있습니다.", ephemeral=True)
            return False
        return True

    async def finish(self, interaction: discord.Interaction, choice: str):
        if self.resolved:
            await interaction.response.send_message("이미 결과가 확정되었습니다.", ephemeral=True)
            return

        self.resolved = True
        result = random.choice(["앞", "뒤"])
        win = choice == result

        if win:
            payout = self.bet_amount * 2
            add_balance(self.user_id, payout)
            description = (
                f"선택: **{choice}**\n"
                f"결과: **{result}**\n"
                f"축하합니다! `{format_money(self.bet_amount)}`을 따서 "
                f"`{format_money(payout)}`을 받았습니다."
            )
            color = 0x2ECC71
        else:
            description = (
                f"선택: **{choice}**\n"
                f"결과: **{result}**\n"
                f"아쉽네요... `{format_money(self.bet_amount)}`을 잃었습니다."
            )
            color = 0xE74C3C

        for item in self.children:
            item.disabled = True

        balance = get_balance(self.user_id)
        embed = discord.Embed(title="🪙 동전 던지기 결과", description=description, color=color)
        embed.add_field(name="현재 잔액", value=format_money(balance), inline=False)

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.resolved:
            return
        self.resolved = True
        add_balance(self.user_id, self.bet_amount)
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="앞", style=discord.ButtonStyle.primary)
    async def heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "앞")

    @discord.ui.button(label="뒤", style=discord.ButtonStyle.secondary)
    async def tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "뒤")


# ================== 명령어 ==================
@bot.tree.command(name="생일등록")
@app_commands.describe(member="생일을 등록할 유저", date="MM-DD 형식으로 입력")
async def add_birthday(interaction: discord.Interaction, member: discord.Member, date: str):
    try:
        normalized_date = normalize_birthday(date)
    except ValueError as error:
        await interaction.response.send_message(str(error), ephemeral=True)
        return

    cursor.execute("INSERT OR REPLACE INTO birthdays VALUES (?,?)", (str(member.id), normalized_date))
    conn.commit()
    await interaction.response.send_message("등록 완료", ephemeral=True)


@bot.tree.command(name="생일삭제")
async def remove_birthday(interaction: discord.Interaction, member: discord.Member):
    cursor.execute("DELETE FROM birthdays WHERE user_id=?", (str(member.id),))
    conn.commit()
    await interaction.response.send_message("삭제 완료", ephemeral=True)


@bot.tree.command(name="생일목록")
async def birthday_list(interaction: discord.Interaction):
    cursor.execute("SELECT * FROM birthdays")
    data = cursor.fetchall()

    result = []
    for uid, date in data:
        member = interaction.guild.get_member(int(uid))
        if not member:
            continue

        try:
            normalized_date = normalize_birthday(date)
        except ValueError:
            continue

        result.append((member, normalized_date))

    result.sort(key=lambda item: tuple(map(int, item[1].split("-"))))
    view = BirthdayListView(result)
    await interaction.response.send_message(embed=view.get_embed(), view=view)


@bot.tree.command(name="규칙버튼")
@app_commands.checks.has_permissions(administrator=True)
async def rule_button(interaction: discord.Interaction):
    embed = discord.Embed(
        description="원활한 게임을 위해 클랜 규칙을 정독해 주세요!!\n확인 후 아래 버튼을 눌러주세요!",
        color=0x2ECC71,
    )
    await interaction.channel.send(embed=embed, view=RuleConfirmView())
    await interaction.response.send_message("규칙 버튼 생성 완료", ephemeral=True)


@bot.tree.command(name="등업패널")
@app_commands.checks.has_permissions(administrator=True)
async def upgrade_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        description=(
            "HICKS 클랜 서버 등업 신청 채널입니다!\n\n"
            "1. 닉네임 변경 [배그아이디/별명]\n"
            "2. 자기소개 작성\n"
            "3. 클랜규칙 확인\n"
            "4. 출석체크\n\n"
            "위 4가지를 완료하시면 아래 버튼을 눌러주세요!"
        ),
        color=0x5865F2,
    )
    await interaction.channel.send(embed=embed, view=UpgradePanelView())
    await interaction.response.send_message("등업 패널 생성 완료", ephemeral=True)


@bot.tree.command(name="시간설정패널")
async def time_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="플레이 시간대 설정",
        description="원하는 시간대를 선택해주세요!\n중복 선택 가능합니다.",
        color=0x5865F2,
    )
    await interaction.channel.send(embed=embed, view=TimeRoleView())
    await interaction.response.send_message("시간 설정 패널 생성 완료", ephemeral=True)


@bot.tree.command(name="돈줘")
async def daily_money(interaction: discord.Interaction):
    today = get_kst_now().strftime("%Y-%m-%d")
    cursor.execute("SELECT last_claim_date FROM daily_claims WHERE user_id=?", (str(interaction.user.id),))
    row = cursor.fetchone()

    if row and row[0] == today:
        await interaction.response.send_message("오늘은 이미 돈을 받았습니다. 내일 다시 시도해주세요.", ephemeral=True)
        return

    ensure_wallet(interaction.user.id)
    add_balance(interaction.user.id, DAILY_REWARD)
    cursor.execute(
        "INSERT OR REPLACE INTO daily_claims(user_id, last_claim_date) VALUES (?, ?)",
        (str(interaction.user.id), today),
    )
    conn.commit()

    balance = get_balance(interaction.user.id)
    await interaction.response.send_message(
        f"오늘의 지원금 `{format_money(DAILY_REWARD)}`을 받았습니다!\n현재 잔액: `{format_money(balance)}`"
    )


@bot.tree.command(name="잔액")
async def balance(interaction: discord.Interaction):
    amount = get_balance(interaction.user.id)
    await interaction.response.send_message(f"{interaction.user.mention}님의 현재 잔액은 `{format_money(amount)}`입니다.")


@bot.tree.command(name="랭킹")
async def ranking(interaction: discord.Interaction):
    cursor.execute("SELECT user_id, balance FROM balances ORDER BY balance DESC, user_id ASC LIMIT 10")
    rows = cursor.fetchall()

    if not rows:
        await interaction.response.send_message("아직 랭킹 데이터가 없습니다.")
        return

    lines = []
    for index, (user_id, amount) in enumerate(rows, start=1):
        member = interaction.guild.get_member(int(user_id))
        name = member.display_name if member else f"알 수 없는 유저 ({user_id})"
        medal = "👑 " if index == 1 else ""
        lines.append(f"{index}. {medal}{name} - {format_money(amount)}")

    embed = discord.Embed(title="💰 자산 랭킹", description="\n".join(lines), color=0xF1C40F)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="송금")
@app_commands.describe(member="송금 받을 유저", amount="보낼 금액")
async def transfer(interaction: discord.Interaction, member: discord.Member, amount: int):
    if member.bot:
        await interaction.response.send_message("봇에게는 송금할 수 없습니다.", ephemeral=True)
        return

    if member.id == interaction.user.id:
        await interaction.response.send_message("자기 자신에게는 송금할 수 없습니다.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("송금 금액은 1원 이상이어야 합니다.", ephemeral=True)
        return

    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)
    add_balance(member.id, amount)

    sender_balance = get_balance(interaction.user.id)
    await interaction.response.send_message(
        f"{member.mention}님에게 `{format_money(amount)}`을 송금했습니다.\n현재 잔액: `{format_money(sender_balance)}`"
    )


@bot.tree.command(name="슬롯")
@app_commands.describe(amount="배팅 금액")
async def slot(interaction: discord.Interaction, amount: int):
    if amount < MIN_BET:
        await interaction.response.send_message(f"최소 배팅 금액은 `{format_money(MIN_BET)}`입니다.", ephemeral=True)
        return

    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)

    symbols = ["🍒", "🍋", "🍉", "⭐", "💎", "7️⃣"]
    result = [random.choice(symbols) for _ in range(3)]

    multiplier = 0
    if len(set(result)) == 1:
        if result[0] == "7️⃣":
            multiplier = 10
        elif result[0] == "💎":
            multiplier = 6
        else:
            multiplier = 4
    elif len(set(result)) == 2:
        multiplier = 1

    winnings = amount * multiplier
    if winnings > 0:
        add_balance(interaction.user.id, winnings)

    balance_now = get_balance(interaction.user.id)
    if multiplier == 0:
        desc = (
            f"`{' | '.join(result)}`\n\n"
            f"아쉽네요... `{format_money(amount)}`을 잃었습니다.\n"
            f"현재 잔액: `{format_money(balance_now)}`"
        )
        color = 0xE74C3C
    elif multiplier == 1:
        desc = (
            f"`{' | '.join(result)}`\n\n"
            f"두 개가 맞아서 본전입니다.\n"
            f"`{format_money(winnings)}`을 돌려받았습니다.\n"
            f"현재 잔액: `{format_money(balance_now)}`"
        )
        color = 0x3498DB
    else:
        desc = (
            f"`{' | '.join(result)}`\n\n"
            f"대박! `{multiplier}배` 당첨으로 `{format_money(winnings)}`을 받았습니다.\n"
            f"현재 잔액: `{format_money(balance_now)}`"
        )
        color = 0x2ECC71

    embed = discord.Embed(title="🎰 슬롯 결과", description=desc, color=color)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="동전")
@app_commands.describe(amount="배팅 금액")
async def coin(interaction: discord.Interaction, amount: int):
    if amount < MIN_BET:
        await interaction.response.send_message(f"최소 배팅 금액은 `{format_money(MIN_BET)}`입니다.", ephemeral=True)
        return

    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)

    embed = discord.Embed(
        title="🪙 동전 던지기",
        description=(
            f"배팅 금액: `{format_money(amount)}`\n"
            "아래 버튼에서 `앞` 또는 `뒤`를 선택해주세요.\n"
            f"{COIN_FLIP_TIMEOUT}초 안에 선택하지 않으면 자동 취소되고 돈이 반환됩니다."
        ),
        color=0xF1C40F,
    )
    await interaction.response.send_message(embed=embed, view=CoinFlipView(interaction.user.id, amount))


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

    embed = discord.Embed(title="📤 서버 퇴장", color=0xE74C3C, timestamp=get_kst_now())
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
    if guild is None:
        return

    if now.strftime("%H:%M") == "00:00":
        channel = bot.get_channel(CHANNEL_ID)
        cursor.execute("SELECT user_id FROM birthdays WHERE date=?", (now.strftime("%m-%d"),))
        for (uid,) in cursor.fetchall():
            member = guild.get_member(int(uid))
            if not member:
                continue

            embed = discord.Embed(
                title="🎂 오늘의 주인공 등장!",
                description=(
                    "✨🎆✨🎆✨🎆✨🎆✨🎆\n\n"
                    f"🎂🎉 오늘은 {member.mention}님의 생일입니다!!! 🎉🎂\n\n"
                    "💥🎊 축하 폭격 시작!!! 🎊💥\n"
                    "👇 아래 버튼으로 축하해주세요 👇\n\n"
                    "✨🎆✨🎆✨🎆✨🎆✨🎆"
                ),
                color=0xFF69B4,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="🎁 버튼 눌러서 축하해보세요!")

            msg = await channel.send(embed=embed, view=BirthdayView())
            cursor.execute("INSERT INTO birthday_messages VALUES (?,?)", (str(msg.id), str(uid)))
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
        except Exception:
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
