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

RULE_ROLE_ID = 1486079820160041131
BIRTHDAY_ROLE_ID = 1482668657178972300
NEW_MEMBER_ROLE_ID = 1481662617859657790

DAILY_REWARD = 10000
MIN_BET = 100
COIN_FLIP_TIMEOUT = 60

MAX_PLAYERS = 4

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
active_recruits = {}

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
cursor.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS sticky_messages(
        channel_id TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        message_id TEXT
    )
    """
)

conn.commit()


# ================== 설정 ==================
def set_setting(key: str, value: str):
    cursor.execute(
        "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()


def get_setting(key: str):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cursor.fetchone()
    return row[0] if row else None


def get_setting_channel_id(key: str):
    value = get_setting(key)
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None

def set_sticky_message(channel_id: int, content: str, message_id: int | None = None):
    cursor.execute(
        """
        INSERT OR REPLACE INTO sticky_messages(channel_id, content, message_id)
        VALUES (?, ?, ?)
        """,
        (str(channel_id), content, str(message_id) if message_id else None),
    )
    conn.commit()


def get_sticky_message(channel_id: int):
    cursor.execute(
        "SELECT content, message_id FROM sticky_messages WHERE channel_id=?",
        (str(channel_id),),
    )
    row = cursor.fetchone()
    if not row:
        return None

    content, message_id = row
    return {
        "content": content,
        "message_id": int(message_id) if message_id else None,
    }


def clear_sticky_message(channel_id: int):
    cursor.execute(
        "DELETE FROM sticky_messages WHERE channel_id=?",
        (str(channel_id),),
    )
    conn.commit()


async def refresh_sticky_message(channel: discord.TextChannel):
    sticky = get_sticky_message(channel.id)
    if not sticky:
        return

    old_message_id = sticky.get("message_id")
    if old_message_id:
        try:
            old_message = await channel.fetch_message(old_message_id)
            await old_message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            return
        except discord.HTTPException:
            return

    new_message = await channel.send(sticky["content"])
    set_sticky_message(channel.id, sticky["content"], new_message.id)


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

        rule_log_channel_id = get_setting_channel_id("rule_log_channel_id")
        if rule_log_channel_id is not None:
            log_channel = interaction.guild.get_channel(rule_log_channel_id)
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
        upgrade_log_channel_id = get_setting_channel_id("upgrade_log_channel_id")
        if upgrade_log_channel_id is None:
            return

        log_channel = interaction.guild.get_channel(upgrade_log_channel_id)
        if log_channel:
            embed = discord.Embed(title="📋 등업 로그", color=0x3498DB)
            embed.add_field(name="대상", value=self.user.mention, inline=True)
            embed.add_field(name="처리자", value=interaction.user.mention, inline=True)
            embed.add_field(name="결과", value=action, inline=False)
            embed.timestamp = datetime.now()
            await log_channel.send(embed=embed)

    async def send_welcome_dm(self):
        try:
            welcome_guide_channel_id = get_setting("welcome_guide_channel_id")
            welcome_guide_text = f"<#{welcome_guide_channel_id}>" if welcome_guide_channel_id else "가입 안내 채널"

            await self.user.send(
                f"""안녕하세요 {self.user.mention}님! 저희 HICKS에 오신 걸 환영합니다!
저희 서버를 알기 쉽게 {welcome_guide_text} 여기에 정리해 두었어요!!
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


# ================== 팀 나누기 VIEW ==================
class TeamSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_team(self, interaction: discord.Interaction, team_size: int):
        if interaction.user.voice is None:
            await interaction.response.send_message("❌ 음성채널에 있어야 합니다.", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        members = channel.members

        players = [
            member.display_name
            for member in members
            if "[📺관전중]" not in member.display_name and not member.bot
        ]

        if len(players) < 2:
            await interaction.response.send_message("플레이어가 부족합니다.", ephemeral=True)
            return

        random.shuffle(players)
        teams = [players[i:i + team_size] for i in range(0, len(players), team_size)]

        embed = discord.Embed(
            title="🎮 랜덤 팀 결과",
            description=f"채널: {channel.name}",
            color=0x2ECC71,
        )

        for index, team in enumerate(teams, start=1):
            embed.add_field(name=f"팀 {index}", value="\n".join(team), inline=False)

        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="2명 팀", style=discord.ButtonStyle.primary)
    async def team2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_team(interaction, 2)

    @discord.ui.button(label="3명 팀", style=discord.ButtonStyle.primary)
    async def team3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_team(interaction, 3)

    @discord.ui.button(label="4명 팀", style=discord.ButtonStyle.success)
    async def team4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_team(interaction, 4)

    @discord.ui.button(label="5명 팀", style=discord.ButtonStyle.secondary)
    async def team5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_team(interaction, 5)

# ================== 고정메시지 VIEW ==================
class StickyMessageModal(discord.ui.Modal, title="고정메시지 설정"):
    content = discord.ui.TextInput(
        label="고정할 메시지 내용",
        placeholder="여기에 여러 줄로 입력하세요.",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        content = str(self.content).strip()
        existing = get_sticky_message(interaction.channel.id)

        if existing and existing.get("message_id"):
            try:
                old_message = await interaction.channel.fetch_message(existing["message_id"])
                await old_message.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        sticky_msg = await interaction.channel.send(content)
        set_sticky_message(interaction.channel.id, content, sticky_msg.id)

        await interaction.response.send_message(
            f"{interaction.channel.mention} 채널의 고정메시지를 설정했습니다.",
            ephemeral=True,
        )


# ================== 구인 유틸 ==================
def count_members(channel):
    players = 0
    spectators = 0

    for member in channel.members:
        if member.bot:
            continue

        if "[📺관전중]" in member.display_name:
            spectators += 1
        else:
            players += 1

    return players, spectators


def get_color(remain):
    if remain <= 0:
        return 0xFF0000
    if remain == 1:
        return 0xFFCC00
    return 0x00FF00


def get_recruit_color(players, max_players):
    if max_players is None:
        return 0x00FF00

    remain = max_players - players
    return get_color(remain)


def build_description(host, voice_channel, players, spectators, message_content, max_players=None):
    lines = [
        f"👤 모집자 : {host.mention}",
        f"🔊 채널 : {voice_channel.name}",
        "",
    ]

    if max_players is None:
        lines.append(f"👥 참여 인원 : {players}명")
        lines.append(f"📺 관전자 : {spectators}")
    else:
        remain = max_players - players
        lines.append(f"👥 참여 인원 : {players} / {max_players}")
        lines.append(f"📺 관전자 : {spectators}")
        lines.append("")
        lines.append(f"🪑 남은 자리 : {remain}")

    lines.extend(["", f"💬 {message_content}"])
    return "\n".join(lines)


class RecruitView(discord.ui.View):
    def __init__(self, channel, host, game_name, message_content, max_players=None):
        super().__init__(timeout=None)
        self.channel = channel
        self.host = host
        self.game_name = game_name
        self.message_content = message_content
        self.max_players = max_players
        self.message = None

    async def update_embed(self):
        players, spectators = count_members(self.channel)

        embed = self.message.embeds[0]
        embed.title = f"🎮 {self.game_name} 모집중!!"
        embed.color = get_recruit_color(players, self.max_players)
        embed.description = build_description(
            self.host,
            self.channel,
            players,
            spectators,
            self.message_content,
            self.max_players,
        )

        await self.message.edit(embed=embed, view=self)

        if self.max_players is not None and players >= self.max_players:
            await self.auto_close()

    async def auto_close(self):
        embed = self.message.embeds[0]
        embed.title = f"🎮 {self.game_name} 모집 종료"
        embed.color = 0xFF0000

        for item in self.children:
            item.disabled = True

        await self.message.edit(embed=embed, view=self)

        if self.channel.id in active_recruits:
            del active_recruits[self.channel.id]

    @discord.ui.button(label="참가하기", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.voice and interaction.user.voice.channel == self.channel:
            await interaction.response.send_message("이미 해당 음성채널에 참여 중입니다.", ephemeral=True)
            return

        permissions = self.channel.permissions_for(interaction.guild.me)
        can_move = permissions.move_members and permissions.connect

        if interaction.user.voice and can_move:
            try:
                await interaction.user.move_to(self.channel)
                await interaction.response.send_message(
                    f"{self.channel.mention} 음성채널로 이동했습니다.",
                    ephemeral=True,
                )
                return
            except (discord.Forbidden, discord.HTTPException):
                pass

        invite = await self.channel.create_invite(max_age=300, max_uses=1)
        await interaction.response.send_message(
            f"바로 이동 권한이 없어 초대 링크를 드릴게요: {invite.url}",
            ephemeral=True,
        )

    @discord.ui.button(label="모집종료", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            await interaction.response.send_message("모집자만 종료할 수 있습니다.", ephemeral=True)
            return

        await interaction.response.defer()
        await self.auto_close()


class GeneralRecruitModal(discord.ui.Modal, title="종겜 구인"):
    game_name = discord.ui.TextInput(
        label="게임 이름",
        placeholder="예: 롤, 발로란트, 마크",
        max_length=100,
    )
    message_content = discord.ui.TextInput(
        label="하고 싶은 말",
        placeholder="예: 2판만 가볍게 하실 분",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("음성채널 먼저 들어가세요.", ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel
        message_text = str(self.message_content).strip() or " "

        await create_recruit_post(
            interaction=interaction,
            text_channel=interaction.channel,
            voice_channel=voice_channel,
            host=interaction.user,
            game_name=str(self.game_name).strip(),
            message_content=message_text,
            mention_here=False,
            max_players=None,
        )


async def create_recruit_post(
    interaction: discord.Interaction,
    text_channel: discord.TextChannel,
    voice_channel: discord.VoiceChannel,
    host: discord.Member,
    game_name: str,
    message_content: str,
    mention_here: bool,
    max_players=None,
):
    players, spectators = count_members(voice_channel)

    embed = discord.Embed(
        title=f"🎮 {game_name} 모집중!!",
        description=build_description(
            host,
            voice_channel,
            players,
            spectators,
            message_content,
            max_players,
        ),
        color=get_recruit_color(players, max_players),
    )

    view = RecruitView(
        voice_channel,
        host,
        game_name,
        message_content,
        max_players=max_players,
    )
    content = "@here" if mention_here else None

    await interaction.response.send_message(content=content, embed=embed, view=view)
    msg = await interaction.original_response()
    view.message = msg

    active_recruits[voice_channel.id] = {
        "message_id": msg.id,
        "host_id": host.id,
        "text_channel_id": text_channel.id,
        "game_name": game_name,
        "message_content": message_content,
        "max_players": max_players,
    }


# ================== 명령어 ==================
@bot.tree.command(name="세팅생일알림", description="현재 채널을 생일 알림 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_birthday_channel(interaction: discord.Interaction):
    set_setting("birthday_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(
        f"생일 알림 채널을 {interaction.channel.mention} 으로 설정했습니다.",
        ephemeral=True,
    )


@bot.tree.command(name="세팅등업로그", description="현재 채널을 등업 로그 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_upgrade_log_channel(interaction: discord.Interaction):
    set_setting("upgrade_log_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(
        f"등업 로그 채널을 {interaction.channel.mention} 으로 설정했습니다.",
        ephemeral=True,
    )


@bot.tree.command(name="세팅퇴장로그", description="현재 채널을 퇴장 로그 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_leave_log_channel(interaction: discord.Interaction):
    set_setting("leave_log_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(
        f"퇴장 로그 채널을 {interaction.channel.mention} 으로 설정했습니다.",
        ephemeral=True,
    )


@bot.tree.command(name="세팅규칙로그", description="현재 채널을 규칙/신입 알림 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_rule_log_channel(interaction: discord.Interaction):
    set_setting("rule_log_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(
        f"규칙 로그 채널을 {interaction.channel.mention} 으로 설정했습니다.",
        ephemeral=True,
    )


@bot.tree.command(name="세팅구인채널", description="현재 채널을 구인 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_recruit_channel(interaction: discord.Interaction):
    set_setting("recruit_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(
        f"구인 채널을 {interaction.channel.mention} 으로 설정했습니다.",
        ephemeral=True,
    )


@bot.tree.command(name="세팅가입안내", description="현재 채널을 가입 안내 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_guide_channel(interaction: discord.Interaction):
    set_setting("welcome_guide_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(
        f"가입 안내 채널을 {interaction.channel.mention} 으로 설정했습니다.",
        ephemeral=True,
    )


@bot.tree.command(name="설정확인", description="현재 설정된 채널들을 확인합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def show_settings(interaction: discord.Interaction):
    birthday_channel_id = get_setting("birthday_channel_id")
    upgrade_log_channel_id = get_setting("upgrade_log_channel_id")
    leave_log_channel_id = get_setting("leave_log_channel_id")
    rule_log_channel_id = get_setting("rule_log_channel_id")
    recruit_channel_id = get_setting("recruit_channel_id")
    welcome_guide_channel_id = get_setting("welcome_guide_channel_id")

    def fmt(channel_id):
        return f"<#{channel_id}>" if channel_id else "미설정"

    embed = discord.Embed(title="서버 채널 설정", color=0x5865F2)
    embed.add_field(name="생일 알림", value=fmt(birthday_channel_id), inline=False)
    embed.add_field(name="등업 로그", value=fmt(upgrade_log_channel_id), inline=False)
    embed.add_field(name="퇴장 로그", value=fmt(leave_log_channel_id), inline=False)
    embed.add_field(name="규칙 로그", value=fmt(rule_log_channel_id), inline=False)
    embed.add_field(name="구인 채널", value=fmt(recruit_channel_id), inline=False)
    embed.add_field(name="가입 안내", value=fmt(welcome_guide_channel_id), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="생일등록", description="유저의 생일을 등록합니다.")
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


@bot.tree.command(name="생일삭제", description="유저의 생일 정보를 삭제합니다.")
@app_commands.describe(member="생일 정보를 삭제할 유저")
async def remove_birthday(interaction: discord.Interaction, member: discord.Member):
    cursor.execute("DELETE FROM birthdays WHERE user_id=?", (str(member.id),))
    conn.commit()
    await interaction.response.send_message("삭제 완료", ephemeral=True)


@bot.tree.command(name="생일목록", description="등록된 생일 목록을 확인합니다.")
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


@bot.tree.command(name="규칙버튼", description="규칙 확인 버튼 메시지를 생성합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def rule_button(interaction: discord.Interaction):
    embed = discord.Embed(
        description="원활한 게임을 위해 클랜 규칙을 정독해 주세요!!\n확인 후 아래 버튼을 눌러주세요!",
        color=0x2ECC71,
    )
    await interaction.channel.send(embed=embed, view=RuleConfirmView())
    await interaction.response.send_message("규칙 버튼 생성 완료", ephemeral=True)


@bot.tree.command(name="등업패널", description="등업 신청 패널을 생성합니다.")
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


@bot.tree.command(name="시간설정패널", description="시간대 역할 선택 패널을 생성합니다.")
async def time_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="플레이 시간대 설정",
        description="원하는 시간대를 선택해주세요!\n중복 선택 가능합니다.",
        color=0x5865F2,
    )
    await interaction.channel.send(embed=embed, view=TimeRoleView())
    await interaction.response.send_message("시간 설정 패널 생성 완료", ephemeral=True)


@bot.tree.command(name="돈줘", description="하루에 한 번 지원금 10,000원을 받습니다.")
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


@bot.tree.command(name="잔액", description="현재 내 보유 금액을 확인합니다.")
async def balance(interaction: discord.Interaction):
    amount = get_balance(interaction.user.id)
    await interaction.response.send_message(f"{interaction.user.mention}님의 현재 잔액은 `{format_money(amount)}`입니다.")


@bot.tree.command(name="랭킹", description="서버 자산 랭킹 상위 10명을 확인합니다.")
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


@bot.tree.command(name="송금", description="다른 유저에게 돈을 송금합니다.")
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


@bot.tree.command(name="돈지급", description="서버 주인이 특정 유저에게 돈을 지급합니다.")
@app_commands.describe(member="돈을 받을 유저", amount="지급할 금액")
async def grant_money(interaction: discord.Interaction, member: discord.Member, amount: int):
    if interaction.guild is None or interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("이 명령어는 서버 주인만 사용할 수 있습니다.", ephemeral=True)
        return

    if member.bot:
        await interaction.response.send_message("봇에게는 지급할 수 없습니다.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("지급 금액은 1원 이상이어야 합니다.", ephemeral=True)
        return

    add_balance(member.id, amount)
    await interaction.response.send_message(
        f"{member.mention}님에게 `{format_money(amount)}`을 지급했습니다.\n"
        f"{member.mention}님의 현재 잔액: `{format_money(get_balance(member.id))}`"
    )


@bot.tree.command(name="슬롯", description="입력한 금액으로 슬롯머신을 돌립니다.")
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

    first = random.choice(symbols)
    second = first if random.random() < 0.45 else random.choice(symbols)
    third = first if random.random() < 0.35 else random.choice(symbols)

    result = [first, second, third]

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


@bot.tree.command(name="동전", description="입력한 금액으로 동전 앞뒤 맞추기를 합니다.")
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


@bot.tree.command(name="팀", description="랜덤 팀 생성")
async def team(interaction: discord.Interaction):
    embed = discord.Embed(
        title="👥 팀 생성",
        description="팀 인원을 선택하세요",
        color=0x3498DB,
    )
    await interaction.response.send_message(embed=embed, view=TeamSelectView())


@bot.tree.command(name="구인", description="배그 구인")
@app_commands.describe(message="하고 싶은 말")
async def recruit(interaction: discord.Interaction, message: str):
    recruit_channel_id = get_setting_channel_id("recruit_channel_id")
    if recruit_channel_id is None:
        await interaction.response.send_message("구인 채널이 아직 설정되지 않았습니다.", ephemeral=True)
        return

    if interaction.channel.id != recruit_channel_id:
        await interaction.response.send_message("구인 채널에서만 사용 가능합니다.", ephemeral=True)
        return

    if not interaction.user.voice:
        await interaction.response.send_message("음성채널 먼저 들어가세요.", ephemeral=True)
        return

    voice_channel = interaction.user.voice.channel

    await create_recruit_post(
        interaction=interaction,
        text_channel=interaction.channel,
        voice_channel=voice_channel,
        host=interaction.user,
        game_name="PUBG",
        message_content=message,
        mention_here=True,
        max_players=MAX_PLAYERS,
    )


@bot.tree.command(name="종겜구인", description="원하는 게임으로 구인 글 작성")
async def general_recruit(interaction: discord.Interaction):
    await interaction.response.send_modal(GeneralRecruitModal())

@bot.tree.command(name="고정메시지", description="현재 채널에 항상 하단에 유지될 메시지를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def sticky_message(interaction: discord.Interaction):
    await interaction.response.send_modal(StickyMessageModal())


@bot.tree.command(name="고정해제", description="현재 채널의 고정메시지를 해제합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def sticky_clear(interaction: discord.Interaction):
    existing = get_sticky_message(interaction.channel.id)
    if not existing:
        await interaction.response.send_message("이 채널에는 설정된 고정메시지가 없습니다.", ephemeral=True)
        return

    if existing.get("message_id"):
        try:
            old_message = await interaction.channel.fetch_message(existing["message_id"])
            await old_message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    clear_sticky_message(interaction.channel.id)
    await interaction.response.send_message("현재 채널의 고정메시지를 해제했습니다.", ephemeral=True)


@bot.tree.command(name="고정확인", description="현재 채널의 고정메시지 내용을 확인합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def sticky_check(interaction: discord.Interaction):
    existing = get_sticky_message(interaction.channel.id)
    if not existing:
        await interaction.response.send_message("이 채널에는 설정된 고정메시지가 없습니다.", ephemeral=True)
        return

    embed = discord.Embed(title="고정메시지 확인", color=0x5865F2)
    embed.add_field(name="채널", value=interaction.channel.mention, inline=False)
    embed.add_field(name="내용", value=existing["content"], inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ================== 이벤트 ==================
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


@bot.event
async def on_member_remove(member: discord.Member):
    if member.guild.id != GUILD_ID:
        return

    leave_log_channel_id = get_setting_channel_id("leave_log_channel_id")
    if leave_log_channel_id is None:
        return

    channel = bot.get_channel(leave_log_channel_id)
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


@bot.event
async def on_voice_state_update(member, before, after):
    channels = []
    if before.channel:
        channels.append(before.channel)
    if after.channel and after.channel not in channels:
        channels.append(after.channel)

    for channel in channels:
        if channel.id not in active_recruits:
            continue

        data = active_recruits[channel.id]
        text_channel = channel.guild.get_channel(data["text_channel_id"])

        if text_channel is None:
            continue

        try:
            msg = await text_channel.fetch_message(data["message_id"])
        except Exception:
            continue

        host_member = member.guild.get_member(data["host_id"])
        if host_member is None:
            view = RecruitView(
                channel,
                member,
                data["game_name"],
                data["message_content"],
                max_players=data.get("max_players"),
            )
            view.message = msg
            await view.auto_close()
            continue

        view = RecruitView(
            channel,
            host_member,
            data["game_name"],
            data["message_content"],
            max_players=data.get("max_players"),
        )
        view.message = msg

        if view.host not in channel.members:
            await view.auto_close()
            continue

        await view.update_embed()

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        await bot.process_commands(message)
        return

    if message.guild is None:
        await bot.process_commands(message)
        return

    sticky = get_sticky_message(message.channel.id)
    if sticky:
        if sticky.get("message_id") and message.id == sticky["message_id"]:
            await bot.process_commands(message)
            return

        try:
            await refresh_sticky_message(message.channel)
        except Exception:
            pass

    await bot.process_commands(message)


# ================== 반복 작업 ==================
@tasks.loop(hours=1)
async def probation_role_check_loop():
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        return

    rule_log_channel_id = get_setting_channel_id("rule_log_channel_id")
    if rule_log_channel_id is None:
        return

    channel = bot.get_channel(rule_log_channel_id)
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


@tasks.loop(minutes=1)
async def birthday_loop():
    now = get_kst_now()
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        return

    if now.strftime("%H:%M") == "00:00":
        birthday_channel_id = get_setting_channel_id("birthday_channel_id")
        if birthday_channel_id is None:
            return

        channel = bot.get_channel(birthday_channel_id)
        if channel is None:
            return

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

    print("HICKS_마리봇 실행 완료")



bot.run(TOKEN)
