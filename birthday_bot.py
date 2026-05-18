import os
import random
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

# ============================================================
# 목차
# 1. 기본 유틸리티
# 2. 전역 설정
# 3. 데이터베이스 초기화
# 4. 서버 설정 / 템플릿 헬퍼
# 5. 재화 / 지급 헬퍼
# 6. 대기방 / 닉네임 패널 헬퍼
# 7. 신용 / 대출 / 적금 / 노동 헬퍼
# 8. 무기 강화 헬퍼
# 9. UI 뷰 / 모달
# 10. 슬래시 명령어
#    - 관리자 설정 명령어
#    - 재화 / 적금 명령어
#    - 게임 명령어
#    - 신용 / 대출 명령어
#    - 무기 강화 명령어
#    - 관리자 신용 관리 명령어
# 11. 디스코드 이벤트
# 12. 백그라운드 작업
# 13. 봇 시작 설정
# ============================================================


# ============================================================
# 기본 유틸리티
# ============================================================

def get_kst_now():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def normalize_birthday(date_str: str) -> str:
    value = date_str.strip().replace("/", "-").replace(".", "-")
    parts = value.split("-")

    if len(parts) != 2:
        raise ValueError("?앹씪 ?뺤떇? MM-DD 濡??낅젰?댁＜?몄슂.")

    month = int(parts[0])
    day = int(parts[1])

    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise ValueError("?щ컮瑜??좎쭨瑜??낅젰?댁＜?몄슂.")

    return f"{month:02d}-{day:02d}"


def dt_to_db(value: datetime) -> str:
    return value.isoformat()


def dt_from_db(value: str) -> datetime:
    return datetime.fromisoformat(value)


TOKEN = os.getenv("TOKEN")

# ============================================================
# 전역 설정
# ============================================================

DAILY_REWARD = 10000
MIN_BET = 100
COIN_FLIP_TIMEOUT = 60
ROULETTE_TIMEOUT = 60
MAX_PLAYERS = 4
ALL_IN_COST = 10000
ALL_IN_GAME_NAME = "紐곕뭇寃뚯엫"
GAME_HISTORY_LIMIT = 10
INITIAL_CREDIT_GRADE = 5
LOAN_REPAYMENT_DAYS = 2
DEFAULT_SAVINGS_DAYS = "3"
DEFAULT_SAVINGS_INTEREST_RATE = "10"
DEFAULT_LABOR_DEBT_AMOUNT = 100_000

LOAN_GRADE_LIMITS = {
    1: 10_000_000,
    2: 8_000_000,
    3: 6_000_000,
    4: 4_000_000,
    5: 2_000_000,
    6: 1_000_000,
}

LOAN_GRADE_INTEREST = {
    1: 10,
    2: 15,
    3: 20,
    4: 25,
    5: 30,
    6: 35,
}

DUCKMONG_FAKE_NAMES = [
    "보안관",
    "자경단",
    "캐나다거위",
    "차원여행자",
    "연예인",
    "한탕주의자",
]

WEAPON_LEVEL_NAMES = {
    1: "프라이팬",
    2: "곡괭이",
    3: "소드오프",
    4: "S686",
    5: "S12K",
    6: "UZI",
    7: "Vector",
    8: "MP5K",
    9: "K2",
    10: "SCAR-L",
    11: "SLR",
    12: "ACE32",
    13: "MK12",
    14: "Beryl M762",
    15: "M416",
    16: "AUG",
    17: "M24",
    18: "MK14",
    19: "P90",
    20: "AWM",
    21: "링스",
}

WEAPON_UPGRADE_COSTS = {
    1: 10000,
    2: 18000,
    3: 28000,
    4: 40000,
    5: 55000,
    6: 75000,
    7: 100000,
    8: 130000,
    9: 170000,
    10: 220000,
    11: 290000,
    12: 380000,
    13: 500000,
    14: 650000,
    15: 850000,
    16: 1100000,
    17: 1420000,
    18: 1820000,
    19: 2320000,
    20: 2950000,
}

WEAPON_SELL_PRICES = {
    1: 0,
    2: 7000,
    3: 16000,
    4: 28000,
    5: 42000,
    6: 60000,
    7: 85000,
    8: 125000,
    9: 180000,
    10: 255000,
    11: 360000,
    12: 1500000,
    13: 2200000,
    14: 3100000,
    15: 4300000,
    16: 5800000,
    17: 7700000,
    18: 10200000,
    19: 13400000,
    20: 17500000,
    21: 22800000,
}

WEAPON_UPGRADE_RATES = {
    1: {"success": 100, "down": 0, "destroy": 0, "keep": 0},
    2: {"success": 95, "down": 0, "destroy": 0, "keep": 5},
    3: {"success": 90, "down": 0, "destroy": 0, "keep": 10},
    4: {"success": 85, "down": 5, "destroy": 0, "keep": 10},
    5: {"success": 80, "down": 8, "destroy": 0, "keep": 12},
    6: {"success": 75, "down": 10, "destroy": 3, "keep": 12},
    7: {"success": 70, "down": 13, "destroy": 5, "keep": 12},
    8: {"success": 65, "down": 15, "destroy": 8, "keep": 12},
    9: {"success": 60, "down": 18, "destroy": 10, "keep": 12},
    10: {"success": 55, "down": 20, "destroy": 13, "keep": 12},
    11: {"success": 50, "down": 23, "destroy": 15, "keep": 12},
    12: {"success": 45, "down": 25, "destroy": 18, "keep": 12},
    13: {"success": 40, "down": 28, "destroy": 20, "keep": 12},
    14: {"success": 35, "down": 30, "destroy": 23, "keep": 12},
    15: {"success": 30, "down": 33, "destroy": 25, "keep": 12},
    16: {"success": 26, "down": 35, "destroy": 27, "keep": 12},
    17: {"success": 22, "down": 38, "destroy": 28, "keep": 12},
    18: {"success": 18, "down": 40, "destroy": 30, "keep": 12},
    19: {"success": 14, "down": 42, "destroy": 32, "keep": 12},
    20: {"success": 10, "down": 45, "destroy": 33, "keep": 12},
}

PROTECTION_TIER_PRICES = {
    "low": 100000,    # 1媛?7媛?
    "mid": 400000,    # 8媛?14媛?
    "high": 1200000,  # 15媛?21媛?
}

PROTECTION_TIER_LABELS = {
    "low": "저강 보호권",
    "mid": "중강 보호권",
    "high": "고강 보호권",
}

TIME_SLOT_CHOICES = ["morning", "afternoon", "evening", "night", "dawn"]
TIME_SLOT_LABELS = {
    "morning": "오전반",
    "afternoon": "오후반",
    "evening": "저녁반",
    "night": "심야반",
    "dawn": "새벽반",
}

DEFAULT_RULE_BUTTON_TEXT = "원활한 게임을 위해 서버 규칙을 확인해주세요.\n확인 후 아래 버튼을 눌러주세요!"
DEFAULT_UPGRADE_PANEL_TEXT = (
    "?깆뾽 ?좎껌 ?⑤꼸?낅땲??\n\n"
    "1. ?됰꽕??蹂寃?n"
    "2. ?먭린?뚭컻 ?묒꽦\n"
    "3. 洹쒖튃 ?뺤씤\n"
    "4. 異쒖꽍 泥댄겕\n\n"
    "?꾨즺?섏뀲?ㅻ㈃ ?꾨옒 踰꾪듉???뚮윭二쇱꽭??"
)
DEFAULT_WELCOME_DM_TEXT = (
    "?덈뀞?섏꽭??{user}?? ?쒕쾭???ㅼ떊 嫄??섏쁺?⑸땲??\n"
    "?쒕쾭 ?덈궡??{guide_channel} ???뺣━?섏뼱 ?덉뒿?덈떎.\n"
    "沅곴툑???먯씠 ?덉쑝硫?愿由ъ옄?먭쾶 臾몄쓽?댁＜?몄슂!"
)
DEFAULT_PROBATION_NOTICE_TEXT = (
    "?좎엯 ??븷 遺????7?쇱씠 吏?ъ뒿?덈떎.\n"
    "異쒖꽍怨??됲뙋???뺤씤??????븷 ?좎? ?щ?瑜?寃?좏빐二쇱꽭??"
)
DEFAULT_PROBATION_DAYS = "7"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
active_recruits = {}

# ============================================================
# 데이터베이스 초기화
# ============================================================

conn = sqlite3.connect("/data/birthday.db")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS birthdays(user_id TEXT PRIMARY KEY, date TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS congrats(message_id TEXT, user_id TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS congrats_count(user_id TEXT PRIMARY KEY, count INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS birthday_messages(message_id TEXT PRIMARY KEY, user_id TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS balances(user_id TEXT PRIMARY KEY, balance INTEGER NOT NULL DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS daily_claims(user_id TEXT PRIMARY KEY, last_claim_date TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS rule_confirm(message_id TEXT, user_id TEXT)")
cursor.execute(
    "CREATE TABLE IF NOT EXISTS guild_settings(guild_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT, PRIMARY KEY (guild_id, key))"
)
cursor.execute(
    "CREATE TABLE IF NOT EXISTS guild_templates(guild_id TEXT NOT NULL, template_name TEXT NOT NULL, content TEXT NOT NULL, PRIMARY KEY (guild_id, template_name))"
)
cursor.execute(
    "CREATE TABLE IF NOT EXISTS guild_time_roles(guild_id TEXT NOT NULL, slot_name TEXT NOT NULL, role_id TEXT NOT NULL, PRIMARY KEY (guild_id, slot_name))"
)

cursor.execute("PRAGMA table_info(probation_roles)")
probation_columns = [row[1] for row in cursor.fetchall()]
if probation_columns and "guild_id" not in probation_columns:
    cursor.execute("DROP TABLE probation_roles")
    conn.commit()

cursor.execute("PRAGMA table_info(welcome_messages)")
welcome_columns = [row[1] for row in cursor.fetchall()]
if welcome_columns and "guild_id" not in welcome_columns:
    cursor.execute("DROP TABLE welcome_messages")
    conn.commit()

cursor.execute("PRAGMA table_info(sticky_messages)")
sticky_columns = [row[1] for row in cursor.fetchall()]
if sticky_columns and "guild_id" not in sticky_columns:
    cursor.execute("DROP TABLE sticky_messages")
    conn.commit()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS probation_roles(
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        assigned_at TEXT,
        notified INTEGER DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS welcome_messages(
        guild_id TEXT NOT NULL,
        role_id TEXT NOT NULL,
        content TEXT NOT NULL,
        PRIMARY KEY (guild_id, role_id)
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS sticky_messages(
        guild_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        content TEXT NOT NULL,
        message_id TEXT,
        PRIMARY KEY (guild_id, channel_id)
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS waiting_rooms(
        guild_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        PRIMARY KEY (guild_id, channel_id)
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS nickname_panels(
        guild_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        message_id TEXT NOT NULL PRIMARY KEY,
        menu_name TEXT NOT NULL,
        prefixes TEXT NOT NULL
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS all_in_entries(
        entry_date TEXT NOT NULL,
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        amount INTEGER NOT NULL,
        PRIMARY KEY (entry_date, guild_id, user_id)
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS game_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        game_name TEXT NOT NULL,
        result_text TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS money_grant_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        target_user_id TEXT NOT NULL,
        giver_user_id TEXT NOT NULL,
        amount INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS credit_profiles(
        user_id TEXT PRIMARY KEY,
        grade INTEGER NOT NULL DEFAULT 5,
        is_blacklisted INTEGER NOT NULL DEFAULT 0
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS loans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        principal INTEGER NOT NULL,
        interest_rate INTEGER NOT NULL,
        total_repayment INTEGER NOT NULL,
        borrowed_at TEXT NOT NULL,
        due_at TEXT NOT NULL,
        repaid_at TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        delinquency_processed INTEGER NOT NULL DEFAULT 0
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS savings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        principal INTEGER NOT NULL,
        interest_rate INTEGER NOT NULL,
        total_amount INTEGER NOT NULL,
        deposited_at TEXT NOT NULL,
        due_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        claimed_at TEXT
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS labor_penalties(
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        debt_amount INTEGER NOT NULL,
        required_count INTEGER NOT NULL,
        completed_count INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        PRIMARY KEY (guild_id, user_id)
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS scrim_signups(
        message_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        PRIMARY KEY (message_id, user_id)
    )
    """
)

cursor.execute("PRAGMA table_info(credit_profiles)")
credit_profile_columns = [row[1] for row in cursor.fetchall()]

if "blacklisted_at" not in credit_profile_columns:
    cursor.execute("ALTER TABLE credit_profiles ADD COLUMN blacklisted_at TEXT")
    conn.commit()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS weapon_inventory(
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        weapon_level INTEGER NOT NULL DEFAULT 0,
        low_protection_count INTEGER NOT NULL DEFAULT 0,
        mid_protection_count INTEGER NOT NULL DEFAULT 0,
        high_protection_count INTEGER NOT NULL DEFAULT 0,
        total_upgrade_spent INTEGER NOT NULL DEFAULT 0,
        total_protection_spent INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )
    """
)

cursor.execute("PRAGMA table_info(weapon_inventory)")
weapon_columns = [row[1] for row in cursor.fetchall()]

if "low_protection_count" not in weapon_columns:
    cursor.execute("ALTER TABLE weapon_inventory ADD COLUMN low_protection_count INTEGER NOT NULL DEFAULT 0")
if "mid_protection_count" not in weapon_columns:
    cursor.execute("ALTER TABLE weapon_inventory ADD COLUMN mid_protection_count INTEGER NOT NULL DEFAULT 0")
if "high_protection_count" not in weapon_columns:
    cursor.execute("ALTER TABLE weapon_inventory ADD COLUMN high_protection_count INTEGER NOT NULL DEFAULT 0")
if "total_upgrade_spent" not in weapon_columns:
    cursor.execute("ALTER TABLE weapon_inventory ADD COLUMN total_upgrade_spent INTEGER NOT NULL DEFAULT 0")
if "total_protection_spent" not in weapon_columns:
    cursor.execute("ALTER TABLE weapon_inventory ADD COLUMN total_protection_spent INTEGER NOT NULL DEFAULT 0")

conn.commit()


# ============================================================
# 서버 설정 / 템플릿 헬퍼
# ============================================================

def set_guild_setting(guild_id: int, key: str, value: str):
    cursor.execute(
        "INSERT OR REPLACE INTO guild_settings(guild_id, key, value) VALUES (?, ?, ?)",
        (str(guild_id), key, value),
    )
    conn.commit()


def get_guild_setting(guild_id: int, key: str):
    cursor.execute(
        "SELECT value FROM guild_settings WHERE guild_id=? AND key=?",
        (str(guild_id), key),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def get_guild_setting_channel_id(guild_id: int, key: str):
    value = get_guild_setting(guild_id, key)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def get_guild_setting_role_id(guild_id: int, key: str):
    value = get_guild_setting(guild_id, key)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def set_template(guild_id: int, template_name: str, content: str):
    cursor.execute(
        "INSERT OR REPLACE INTO guild_templates(guild_id, template_name, content) VALUES (?, ?, ?)",
        (str(guild_id), template_name, content),
    )
    conn.commit()


def get_template(guild_id: int, template_name: str):
    cursor.execute(
        "SELECT content FROM guild_templates WHERE guild_id=? AND template_name=?",
        (str(guild_id), template_name),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def get_template_with_default(guild_id: int, template_name: str, default_value: str):
    return get_template(guild_id, template_name) or default_value


def get_setting_with_default(guild_id: int, key: str, default_value: str):
    value = get_guild_setting(guild_id, key)
    return value if value is not None else default_value


def get_savings_days(guild_id: int) -> int:
    return int(get_setting_with_default(guild_id, "savings_days", DEFAULT_SAVINGS_DAYS))


def get_savings_interest_rate(guild_id: int) -> int:
    return int(get_setting_with_default(guild_id, "savings_interest_rate", DEFAULT_SAVINGS_INTEREST_RATE))


def set_time_role(guild_id: int, slot_name: str, role_id: int):
    cursor.execute(
        "INSERT OR REPLACE INTO guild_time_roles(guild_id, slot_name, role_id) VALUES (?, ?, ?)",
        (str(guild_id), slot_name, str(role_id)),
    )
    conn.commit()


def get_time_role_id(guild_id: int, slot_name: str):
    cursor.execute(
        "SELECT role_id FROM guild_time_roles WHERE guild_id=? AND slot_name=?",
        (str(guild_id), slot_name),
    )
    row = cursor.fetchone()
    if not row:
        return None
    try:
        return int(row[0])
    except ValueError:
        return None


def get_all_time_roles(guild_id: int):
    cursor.execute(
        "SELECT slot_name, role_id FROM guild_time_roles WHERE guild_id=? ORDER BY slot_name ASC",
        (str(guild_id),),
    )
    rows = cursor.fetchall()
    result = {}
    for slot_name, role_id in rows:
        try:
            result[slot_name] = int(role_id)
        except ValueError:
            continue
    return result


def set_welcome_message(guild_id: int, role_id: int, content: str):
    cursor.execute(
        "INSERT OR REPLACE INTO welcome_messages(guild_id, role_id, content) VALUES (?, ?, ?)",
        (str(guild_id), str(role_id), content),
    )
    conn.commit()


def get_welcome_message(guild_id: int, role_id: int):
    cursor.execute(
        "SELECT content FROM welcome_messages WHERE guild_id=? AND role_id=?",
        (str(guild_id), str(role_id)),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def get_all_welcome_messages(guild_id: int):
    cursor.execute(
        "SELECT role_id, content FROM welcome_messages WHERE guild_id=? ORDER BY role_id ASC",
        (str(guild_id),),
    )
    return cursor.fetchall()


def delete_welcome_message(guild_id: int, role_id: int):
    cursor.execute(
        "DELETE FROM welcome_messages WHERE guild_id=? AND role_id=?",
        (str(guild_id), str(role_id)),
    )
    conn.commit()


def set_sticky_message(guild_id: int, channel_id: int, content: str, message_id: int | None = None):
    cursor.execute(
        """
        INSERT OR REPLACE INTO sticky_messages(guild_id, channel_id, content, message_id)
        VALUES (?, ?, ?, ?)
        """,
        (str(guild_id), str(channel_id), content, str(message_id) if message_id else None),
    )
    conn.commit()


def get_sticky_message(guild_id: int, channel_id: int):
    cursor.execute(
        "SELECT content, message_id FROM sticky_messages WHERE guild_id=? AND channel_id=?",
        (str(guild_id), str(channel_id)),
    )
    row = cursor.fetchone()
    if not row:
        return None

    content, message_id = row
    return {
        "content": content,
        "message_id": int(message_id) if message_id else None,
    }


def clear_sticky_message(guild_id: int, channel_id: int):
    cursor.execute(
        "DELETE FROM sticky_messages WHERE guild_id=? AND channel_id=?",
        (str(guild_id), str(channel_id)),
    )
    conn.commit()


async def refresh_sticky_message(channel: discord.TextChannel):
    sticky = get_sticky_message(channel.guild.id, channel.id)
    if not sticky:
        return

    old_message_id = sticky.get("message_id")
    if old_message_id:
        try:
            old_message = await channel.fetch_message(old_message_id)
            await old_message.delete()
        except discord.NotFound:
            pass
        except (discord.Forbidden, discord.HTTPException):
            return

    new_message = await channel.send(sticky["content"])
    set_sticky_message(channel.guild.id, channel.id, sticky["content"], new_message.id)


# ============================================================
# 재화 / 지급 헬퍼
# ============================================================

def ensure_wallet(user_id: int):
    cursor.execute("INSERT OR IGNORE INTO balances(user_id, balance) VALUES (?, 0)", (str(user_id),))
    conn.commit()


def get_balance(user_id: int) -> int:
    ensure_wallet(user_id)
    cursor.execute("SELECT balance FROM balances WHERE user_id=?", (str(user_id),))
    row = cursor.fetchone()
    return row[0] if row else 0


def add_balance(user_id: int, amount: int):
    ensure_wallet(user_id)
    cursor.execute("UPDATE balances SET balance=balance+? WHERE user_id=?", (amount, str(user_id)))
    conn.commit()


def can_afford(user_id: int, amount: int) -> bool:
    return get_balance(user_id) >= amount


def format_money(amount: int) -> str:
    return f"{amount:,}원"

def get_spectator_prefixes(guild_id: int) -> list[str]:
    raw = get_guild_setting(guild_id, "spectator_prefixes")
    if not raw:
        return ["관전자"]

    return [item.strip() for item in raw.split(",") if item.strip()]


def is_spectator_member(member: discord.Member, guild_id: int) -> bool:
    display_name = member.display_name.strip()

    for prefix in get_spectator_prefixes(guild_id):
        token = f"[{prefix}]"
        if display_name.startswith(token):
            return True

    return False



# ============================================================
# 대기방 / 닉네임 패널 헬퍼
# ============================================================

def add_waiting_room(guild_id: int, channel_id: int):
    cursor.execute(
        "INSERT OR IGNORE INTO waiting_rooms(guild_id, channel_id) VALUES (?, ?)",
        (str(guild_id), str(channel_id)),
    )
    conn.commit()


def remove_waiting_room(guild_id: int, channel_id: int):
    cursor.execute(
        "DELETE FROM waiting_rooms WHERE guild_id=? AND channel_id=?",
        (str(guild_id), str(channel_id)),
    )
    conn.commit()


def get_waiting_rooms(guild_id: int):
    cursor.execute(
        "SELECT channel_id FROM waiting_rooms WHERE guild_id=? ORDER BY channel_id ASC",
        (str(guild_id),),
    )
    rows = cursor.fetchall()
    result = []
    for (channel_id,) in rows:
        try:
            result.append(int(channel_id))
        except ValueError:
            continue
    return result


def is_waiting_room(guild_id: int, channel_id: int) -> bool:
    cursor.execute(
        "SELECT 1 FROM waiting_rooms WHERE guild_id=? AND channel_id=?",
        (str(guild_id), str(channel_id)),
    )
    return cursor.fetchone() is not None

def save_nickname_panel(guild_id: int, channel_id: int, message_id: int, menu_name: str, prefixes: list[str]):
    cursor.execute(
        """
        INSERT OR REPLACE INTO nickname_panels(guild_id, channel_id, message_id, menu_name, prefixes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (str(guild_id), str(channel_id), str(message_id), menu_name, "|".join(prefixes)),
    )
    conn.commit()


def get_all_nickname_panels():
    cursor.execute(
        "SELECT guild_id, channel_id, message_id, menu_name, prefixes FROM nickname_panels"
    )
    return cursor.fetchall()


def delete_nickname_panel(message_id: int):
    cursor.execute(
        "DELETE FROM nickname_panels WHERE message_id=?",
        (str(message_id),),
    )
    conn.commit()

async def restore_nickname_panels():
    rows = get_all_nickname_panels()

    for guild_id, channel_id, message_id, menu_name, prefixes_raw in rows:
        try:
            guild_id_int = int(guild_id)
            channel_id_int = int(channel_id)
            message_id_int = int(message_id)
            prefixes = [item for item in prefixes_raw.split("|") if item]
        except ValueError:
            delete_nickname_panel(int(message_id))
            continue

        guild = bot.get_guild(guild_id_int)
        if guild is None:
            continue

        channel = guild.get_channel(channel_id_int)
        if channel is None:
            continue

        try:
            await channel.fetch_message(message_id_int)
        except discord.NotFound:
            delete_nickname_panel(message_id_int)
            continue
        except (discord.Forbidden, discord.HTTPException):
            continue

        bot.add_view(
            NicknamePrefixView(
                guild_id_int,
                channel_id_int,
                message_id_int,
                prefixes,
            ),
            message_id=message_id_int,
        )


def apply_prefix_to_nickname(current_name: str, selected_prefix: str, managed_prefixes: list[str]) -> str:
    base_name = current_name.strip()

    for prefix in managed_prefixes:
        token = f"[{prefix}]"
        if base_name.startswith(token):
            base_name = base_name[len(token):].strip()
            break

    return f"[{selected_prefix}] {base_name}"


def reset_prefix_from_nickname(current_name: str, managed_prefixes: list[str]) -> str:
    base_name = current_name.strip()

    for prefix in managed_prefixes:
        token = f"[{prefix}]"
        if base_name.startswith(token):
            return base_name[len(token):].strip()

    return base_name

def get_today_kst_date_str() -> str:
    return get_kst_now().strftime("%Y-%m-%d")


def add_game_history(guild_id: int, game_name: str, result_text: str):
    cursor.execute(
        """
        INSERT INTO game_history(guild_id, game_name, result_text, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (str(guild_id), game_name, result_text, dt_to_db(get_kst_now())),
    )
    conn.commit()


def get_recent_game_history(guild_id: int, game_name: str, limit: int = 10):
    cursor.execute(
        """
        SELECT result_text, created_at
        FROM game_history
        WHERE guild_id=? AND game_name=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (str(guild_id), game_name, limit),
    )
    return cursor.fetchall()


def add_money_grant_log(guild_id: int, target_user_id: int, giver_user_id: int, amount: int):
    cursor.execute(
        """
        INSERT INTO money_grant_logs(guild_id, target_user_id, giver_user_id, amount, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (str(guild_id), str(target_user_id), str(giver_user_id), amount, dt_to_db(get_kst_now())),
    )
    conn.commit()


def get_money_grant_logs(guild_id: int, target_user_id: int, limit: int = 20):
    cursor.execute(
        """
        SELECT giver_user_id, amount, created_at
        FROM money_grant_logs
        WHERE guild_id=? AND target_user_id=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (str(guild_id), str(target_user_id), limit),
    )
    return cursor.fetchall()


def add_all_in_entry(entry_date: str, guild_id: int, user_id: int, amount: int):
    cursor.execute(
        """
        INSERT OR REPLACE INTO all_in_entries(entry_date, guild_id, user_id, amount)
        VALUES (?, ?, ?, ?)
        """,
        (entry_date, str(guild_id), str(user_id), amount),
    )
    conn.commit()


def has_all_in_entry(entry_date: str, guild_id: int, user_id: int) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM all_in_entries
        WHERE entry_date=? AND guild_id=? AND user_id=?
        """,
        (entry_date, str(guild_id), str(user_id)),
    )
    return cursor.fetchone() is not None


def get_all_in_entries(entry_date: str, guild_id: int):
    cursor.execute(
        """
        SELECT user_id, amount
        FROM all_in_entries
        WHERE entry_date=? AND guild_id=?
        ORDER BY user_id ASC
        """,
        (entry_date, str(guild_id)),
    )
    return cursor.fetchall()


def clear_all_in_entries(entry_date: str, guild_id: int):
    cursor.execute(
        """
        DELETE FROM all_in_entries
        WHERE entry_date=? AND guild_id=?
        """,
        (entry_date, str(guild_id)),
    )
    conn.commit()

# ============================================================
# 신용 / 대출 / 적금 / 노동 헬퍼
# ============================================================

def ensure_credit_profile(user_id: int):
    cursor.execute(
        """
        INSERT OR IGNORE INTO credit_profiles(user_id, grade, is_blacklisted)
        VALUES (?, ?, 0)
        """,
        (str(user_id), INITIAL_CREDIT_GRADE),
    )
    conn.commit()


def get_credit_profile(user_id: int):
    ensure_credit_profile(user_id)
    cursor.execute(
        "SELECT grade, is_blacklisted, blacklisted_at FROM credit_profiles WHERE user_id=?",
        (str(user_id),),
    )
    row = cursor.fetchone()
    if not row:
        return {
            "grade": INITIAL_CREDIT_GRADE,
            "is_blacklisted": False,
            "blacklisted_at": None,
        }

    return {
        "grade": int(row[0]),
        "is_blacklisted": bool(row[1]),
        "blacklisted_at": row[2],
    }

def get_blacklisted_profiles():
    cursor.execute(
        """
        SELECT user_id, grade, blacklisted_at
        FROM credit_profiles
        WHERE is_blacklisted=1
        ORDER BY blacklisted_at ASC, user_id ASC
        """
    )
    return cursor.fetchall()


def set_credit_grade(user_id: int, grade: int):
    ensure_credit_profile(user_id)
    grade = max(1, min(6, grade))
    cursor.execute(
        "UPDATE credit_profiles SET grade=? WHERE user_id=?",
        (grade, str(user_id)),
    )
    conn.commit()


def set_credit_blacklisted(user_id: int, is_blacklisted: bool):
    ensure_credit_profile(user_id)
    blacklisted_at = dt_to_db(get_kst_now()) if is_blacklisted else None
    cursor.execute(
        """
        UPDATE credit_profiles
        SET is_blacklisted=?, blacklisted_at=?
        WHERE user_id=?
        """,
        (1 if is_blacklisted else 0, blacklisted_at, str(user_id)),
    )
    conn.commit()


def upgrade_credit_grade(user_id: int):
    profile = get_credit_profile(user_id)

    if profile["is_blacklisted"]:
        # ?좎슜遺덈웾???댁젣 ??6?깃툒?쇰줈 蹂듦?
        set_credit_blacklisted(user_id, False)
        set_credit_grade(user_id, 6)
        return

    set_credit_grade(user_id, profile["grade"] - 1)


def downgrade_credit_grade(user_id: int):
    profile = get_credit_profile(user_id)

    if profile["grade"] >= 6:
        set_credit_grade(user_id, 6)
        set_credit_blacklisted(user_id, True)
        return

    set_credit_grade(user_id, profile["grade"] + 1)


def get_credit_grade_text(user_id: int) -> str:
    profile = get_credit_profile(user_id)
    if profile["is_blacklisted"]:
        return "신용불량자"
    return f"{profile['grade']}등급"


def get_loan_limit_by_grade(grade: int) -> int:
    return LOAN_GRADE_LIMITS.get(grade, LOAN_GRADE_LIMITS[6])


def get_loan_interest_by_grade(grade: int) -> int:
    return LOAN_GRADE_INTEREST.get(grade, LOAN_GRADE_INTEREST[6])


def calculate_total_repayment(principal: int, interest_rate: int) -> int:
    return int(principal * (100 + interest_rate) / 100)


def get_active_loan(user_id: int):
    cursor.execute(
        """
        SELECT id, guild_id, principal, interest_rate, total_repayment, borrowed_at, due_at, status
        FROM loans
        WHERE user_id=? AND status IN ('active', 'overdue')
        ORDER BY id DESC
        LIMIT 1
        """,
        (str(user_id),),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "id": row[0],
        "guild_id": row[1],
        "principal": row[2],
        "interest_rate": row[3],
        "total_repayment": row[4],
        "borrowed_at": row[5],
        "due_at": row[6],
        "status": row[7],
    }


def create_loan(guild_id: int, user_id: int, principal: int, interest_rate: int, total_repayment: int, borrowed_at: datetime, due_at: datetime):
    cursor.execute(
        """
        INSERT INTO loans(
            guild_id, user_id, principal, interest_rate, total_repayment,
            borrowed_at, due_at, status, delinquency_processed
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'active', 0)
        """,
        (
            str(guild_id),
            str(user_id),
            principal,
            interest_rate,
            total_repayment,
            dt_to_db(borrowed_at),
            dt_to_db(due_at),
        ),
    )
    conn.commit()


def repay_loan(loan_id: int):
    cursor.execute(
        """
        UPDATE loans
        SET status='repaid', repaid_at=?, delinquency_processed=1
        WHERE id=?
        """,
        (dt_to_db(get_kst_now()), loan_id),
    )
    conn.commit()


def mark_loan_overdue(loan_id: int):
    cursor.execute(
        """
        UPDATE loans
        SET status='overdue', delinquency_processed=1
        WHERE id=?
        """,
        (loan_id,),
    )
    conn.commit()


def get_due_loans(now: datetime):
    cursor.execute(
        """
        SELECT id, guild_id, user_id, total_repayment, due_at
        FROM loans
        WHERE status='active' AND delinquency_processed=0 AND due_at<=?
        ORDER BY id ASC
        """,
        (dt_to_db(now),),
    )
    return cursor.fetchall()


def get_active_saving(guild_id: int, user_id: int):
    cursor.execute(
        """
        SELECT id, principal, interest_rate, total_amount, deposited_at, due_at, status
        FROM savings
        WHERE guild_id=? AND user_id=? AND status='active'
        ORDER BY id DESC
        LIMIT 1
        """,
        (str(guild_id), str(user_id)),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "id": row[0],
        "principal": row[1],
        "interest_rate": row[2],
        "total_amount": row[3],
        "deposited_at": row[4],
        "due_at": row[5],
        "status": row[6],
    }


def create_saving(
    guild_id: int,
    user_id: int,
    principal: int,
    interest_rate: int,
    total_amount: int,
    due_at: datetime,
):
    cursor.execute(
        """
        INSERT INTO savings(guild_id, user_id, principal, interest_rate, total_amount, deposited_at, due_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
        """,
        (
            str(guild_id),
            str(user_id),
            principal,
            interest_rate,
            total_amount,
            dt_to_db(get_kst_now()),
            dt_to_db(due_at),
        ),
    )
    conn.commit()


def claim_saving(saving_id: int):
    cursor.execute(
        """
        UPDATE savings
        SET status='claimed', claimed_at=?
        WHERE id=?
        """,
        (dt_to_db(get_kst_now()), saving_id),
    )
    conn.commit()


def calculate_labor_required_count(debt_amount: int) -> int:
    return max(10, min(1000, debt_amount // 10_000))


def create_or_replace_labor_penalty(guild_id: int, user_id: int, debt_amount: int):
    required_count = calculate_labor_required_count(debt_amount)
    cursor.execute(
        """
        INSERT OR REPLACE INTO labor_penalties(
            guild_id, user_id, debt_amount, required_count, completed_count, status, created_at, resolved_at
        )
        VALUES (?, ?, ?, ?, 0, 'active', ?, NULL)
        """,
        (str(guild_id), str(user_id), debt_amount, required_count, dt_to_db(get_kst_now())),
    )
    conn.commit()


def get_active_labor_penalty(guild_id: int, user_id: int):
    cursor.execute(
        """
        SELECT debt_amount, required_count, completed_count, created_at
        FROM labor_penalties
        WHERE guild_id=? AND user_id=? AND status='active'
        """,
        (str(guild_id), str(user_id)),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "debt_amount": int(row[0]),
        "required_count": int(row[1]),
        "completed_count": int(row[2]),
        "created_at": row[3],
    }


def ensure_active_labor_penalty(guild_id: int, user_id: int):
    penalty = get_active_labor_penalty(guild_id, user_id)
    if penalty is not None:
        return penalty

    profile = get_credit_profile(user_id)
    if not profile["is_blacklisted"]:
        return None

    active_loan = get_active_loan(user_id)
    debt_amount = active_loan["total_repayment"] if active_loan else DEFAULT_LABOR_DEBT_AMOUNT
    create_or_replace_labor_penalty(guild_id, user_id, debt_amount)
    return get_active_labor_penalty(guild_id, user_id)


def increment_labor_count(guild_id: int, user_id: int):
    penalty = ensure_active_labor_penalty(guild_id, user_id)
    if penalty is None:
        return None, False

    cursor.execute(
        """
        UPDATE labor_penalties
        SET completed_count=completed_count+1
        WHERE guild_id=? AND user_id=? AND status='active'
        """,
        (str(guild_id), str(user_id)),
    )
    conn.commit()

    updated = get_active_labor_penalty(guild_id, user_id)
    if updated is None:
        return None, False

    if updated["completed_count"] >= updated["required_count"]:
        cursor.execute(
            """
            UPDATE labor_penalties
            SET status='resolved', resolved_at=?
            WHERE guild_id=? AND user_id=?
            """,
            (dt_to_db(get_kst_now()), str(guild_id), str(user_id)),
        )
        conn.commit()

        active_loan = get_active_loan(user_id)
        if active_loan is not None:
            repay_loan(active_loan["id"])

        set_credit_blacklisted(user_id, False)
        set_credit_grade(user_id, INITIAL_CREDIT_GRADE)
        return updated, True

    return updated, False


def delete_labor_penalty(guild_id: int, user_id: int):
    cursor.execute(
        "DELETE FROM labor_penalties WHERE guild_id=? AND user_id=?",
        (str(guild_id), str(user_id)),
    )
    conn.commit()


async def ensure_not_blacklisted_for_gambling(interaction: discord.Interaction) -> bool:
    profile = get_credit_profile(interaction.user.id)
    if profile["is_blacklisted"]:
        await interaction.response.send_message(
            "?꾩옱 ?좎슜遺덈웾???곹깭???꾨컯 紐낅졊?대? ?ъ슜?????놁뒿?덈떎. `/?몃룞`?쇰줈 ?좎슜 ?뚮났??吏꾪뻾?댁＜?몄슂.",
            ephemeral=True,
        )
        return False
    return True


def build_labor_embed(member: discord.Member, penalty: dict) -> discord.Embed:
    remaining = max(0, penalty["required_count"] - penalty["completed_count"])
    embed = discord.Embed(title="🛠 노동", color=0xE67E22)
    embed.add_field(name="대상", value=member.mention, inline=False)
    embed.add_field(name="미상환 기준 금액", value=format_money(penalty["debt_amount"]), inline=False)
    embed.add_field(
        name="진행 현황",
        value=(
            f"완료: `{penalty['completed_count']}회`\n"
            f"필요: `{penalty['required_count']}회`\n"
            f"남은 횟수: `{remaining}회`"
        ),
        inline=False,
    )
    return embed

# ============================================================
# 무기 강화 헬퍼
# ============================================================

def ensure_weapon_inventory(guild_id: int, user_id: int):
    cursor.execute(
        """
        INSERT OR IGNORE INTO weapon_inventory(
            guild_id, user_id, weapon_level,
            low_protection_count, mid_protection_count, high_protection_count,
            total_upgrade_spent, total_protection_spent
        )
        VALUES (?, ?, 0, 0, 0, 0, 0, 0)
        """,
        (str(guild_id), str(user_id)),
    )
    conn.commit()



def get_weapon_inventory(guild_id: int, user_id: int):
    ensure_weapon_inventory(guild_id, user_id)
    cursor.execute(
        """
        SELECT
            weapon_level,
            low_protection_count,
            mid_protection_count,
            high_protection_count,
            total_upgrade_spent,
            total_protection_spent
        FROM weapon_inventory
        WHERE guild_id=? AND user_id=?
        """,
        (str(guild_id), str(user_id)),
    )
    row = cursor.fetchone()
    if not row:
        return {
            "weapon_level": 0,
            "low_protection_count": 0,
            "mid_protection_count": 0,
            "high_protection_count": 0,
            "total_upgrade_spent": 0,
            "total_protection_spent": 0,
        }

    return {
        "weapon_level": int(row[0]),
        "low_protection_count": int(row[1]),
        "mid_protection_count": int(row[2]),
        "high_protection_count": int(row[3]),
        "total_upgrade_spent": int(row[4]),
        "total_protection_spent": int(row[5]),
    }


def add_upgrade_spent(guild_id: int, user_id: int, amount: int):
    ensure_weapon_inventory(guild_id, user_id)
    cursor.execute(
        """
        UPDATE weapon_inventory
        SET total_upgrade_spent=total_upgrade_spent+?
        WHERE guild_id=? AND user_id=?
        """,
        (amount, str(guild_id), str(user_id)),
    )
    conn.commit()


def add_protection_spent(guild_id: int, user_id: int, amount: int):
    ensure_weapon_inventory(guild_id, user_id)
    cursor.execute(
        """
        UPDATE weapon_inventory
        SET total_protection_spent=total_protection_spent+?
        WHERE guild_id=? AND user_id=?
        """,
        (amount, str(guild_id), str(user_id)),
    )
    conn.commit()


def set_weapon_level(guild_id: int, user_id: int, level: int):
    ensure_weapon_inventory(guild_id, user_id)
    cursor.execute(
        """
        UPDATE weapon_inventory
        SET weapon_level=?
        WHERE guild_id=? AND user_id=?
        """,
        (level, str(guild_id), str(user_id)),
    )
    conn.commit()

def reset_weapon_progress(guild_id: int, user_id: int):
    ensure_weapon_inventory(guild_id, user_id)
    cursor.execute(
        """
        UPDATE weapon_inventory
        SET weapon_level=0,
            total_upgrade_spent=0,
            total_protection_spent=0
        WHERE guild_id=? AND user_id=?
        """,
        (str(guild_id), str(user_id)),
    )
    conn.commit()


def get_protection_tier(level: int) -> str:
    if 1 <= level <= 7:
        return "low"
    if 8 <= level <= 14:
        return "mid"
    return "high"


def get_protection_purchase_level(tier: str) -> int:
    if tier == "low":
        return 1
    if tier == "mid":
        return 8
    return 15


def get_protection_cost_by_tier(tier: str) -> int:
    return PROTECTION_TIER_PRICES[tier]

def add_protection_count(guild_id: int, user_id: int, tier: str, amount: int):
    ensure_weapon_inventory(guild_id, user_id)
    column = {
        "low": "low_protection_count",
        "mid": "mid_protection_count",
        "high": "high_protection_count",
    }[tier]
    cursor.execute(
        f"""
        UPDATE weapon_inventory
        SET {column}={column}+?
        WHERE guild_id=? AND user_id=?
        """,
        (amount, str(guild_id), str(user_id)),
    )
    conn.commit()


def consume_protection_count(guild_id: int, user_id: int, tier: str, amount: int = 1):
    ensure_weapon_inventory(guild_id, user_id)
    column = {
        "low": "low_protection_count",
        "mid": "mid_protection_count",
        "high": "high_protection_count",
    }[tier]
    cursor.execute(
        f"""
        UPDATE weapon_inventory
        SET {column}=MAX({column}-?, 0)
        WHERE guild_id=? AND user_id=?
        """,
        (amount, str(guild_id), str(user_id)),
    )
    conn.commit()


def get_protection_count_for_level(inventory: dict, level: int) -> int:
    tier = get_protection_tier(level)
    if tier == "low":
        return inventory["low_protection_count"]
    if tier == "mid":
        return inventory["mid_protection_count"]
    return inventory["high_protection_count"]



def ensure_base_weapon(guild_id: int, user_id: int):
    inventory = get_weapon_inventory(guild_id, user_id)
    if inventory["weapon_level"] <= 0:
        set_weapon_level(guild_id, user_id, 1)


def get_weapon_name(level: int) -> str:
    return WEAPON_LEVEL_NAMES.get(level, "?????녿뒗 臾닿린")


def get_upgrade_cost(level: int) -> int | None:
    return WEAPON_UPGRADE_COSTS.get(level)


def get_weapon_sell_price(level: int) -> int:
    return WEAPON_SELL_PRICES.get(level, 0)


def roll_upgrade_result(level: int) -> str:
    rates = WEAPON_UPGRADE_RATES[level]
    return random.choices(
        ["success", "down", "destroy", "keep"],
        weights=[rates["success"], rates["down"], rates["destroy"], rates["keep"]],
        k=1,
    )[0]

def build_upgrade_embed(guild_id: int, user_id: int) -> discord.Embed:
    ensure_base_weapon(guild_id, user_id)
    inventory = get_weapon_inventory(guild_id, user_id)

    current_level = inventory["weapon_level"]
    current_name = get_weapon_name(current_level)
    current_sell_price = get_weapon_sell_price(current_level)
    balance = get_balance(user_id)

    low_count = inventory["low_protection_count"]
    mid_count = inventory["mid_protection_count"]
    high_count = inventory["high_protection_count"]

    total_upgrade_spent = inventory["total_upgrade_spent"]
    total_protection_spent = inventory["total_protection_spent"]
    total_invested = total_upgrade_spent + total_protection_spent

    embed = discord.Embed(
        title="?뵩 臾닿린 媛뺥솕",
        description="媛뺥솕??臾닿린 ?뺣낫瑜??뺤씤?섍퀬 ?꾨옒 踰꾪듉?쇰줈 吏꾪뻾?댁＜?몄슂.",
        color=0x5865F2,
    )

    embed.add_field(
        name="?꾩옱 臾닿린",
        value=(
            f"`{current_level}媛?{current_name}`\n"
            f"?먮ℓ 媛寃? `{format_money(current_sell_price)}`"
        ),
        inline=False,
    )

    embed.add_field(
        name="?꾩쟻 ?ъ옄",
        value=(
            f"媛뺥솕 ?꾩쟻: `{format_money(total_upgrade_spent)}`\n"
            f"蹂댄샇沅??꾩쟻: `{format_money(total_protection_spent)}`\n"
            f"珥??ъ옄: `{format_money(total_invested)}`"
        ),
        inline=False,
    )

    embed.add_field(
        name="보유 보호권",
        value=(
            f"저강: `{low_count}개`\n"
            f"중강: `{mid_count}개`\n"
            f"고강: `{high_count}개`"
        ),
        inline=True,
    )

    embed.add_field(
        name="?꾩옱 ?붿븸",
        value=f"`{format_money(balance)}`",
        inline=True,
    )

    if current_level >= 21:
        embed.add_field(
            name="媛뺥솕 ?곹깭",
            value="理쒕? 媛뺥솕 ?④퀎?낅땲??",
            inline=False,
        )
        return embed

    next_level = current_level + 1
    next_name = get_weapon_name(next_level)
    upgrade_cost = get_upgrade_cost(current_level)
    rates = WEAPON_UPGRADE_RATES[current_level]

    tier = get_protection_tier(current_level)
    protection_label = PROTECTION_TIER_LABELS[tier]
    protection_cost = get_protection_cost_by_tier(tier)
    purchase_level = get_protection_purchase_level(tier)

    embed.add_field(
        name="?ㅼ쓬 臾닿린",
        value=f"`{next_level}媛?{next_name}`",
        inline=False,
    )

    embed.add_field(
        name="鍮꾩슜 ?뺣낫",
        value=(
            f"媛뺥솕 鍮꾩슜: `{format_money(upgrade_cost)}`\n"
            f"{protection_label}: `{format_money(protection_cost)}`"
        ),
        inline=True,
    )

    embed.add_field(
        name="媛뺥솕 ?뺣쪧",
        value=(
            f"?깃났: `{rates['success']}%`\n"
            f"?섎씫: `{rates['down']}%`\n"
            f"?뚭눼: `{rates['destroy']}%`\n"
            f"?좎?: `{rates['keep']}%`"
        ),
        inline=True,
    )

    embed.add_field(
        name="蹂댄샇沅??덈궡",
        value=(
            f"?꾩옱 援ш컙: `{protection_label}`\n"
            f"援щℓ 媛???④퀎: `{purchase_level}媛?\n"
            "蹂댄샇沅뚯? 媛뺥솕 ?깃났??蹂댁옣?섏? ?딆쑝硫?\n"
            "?ㅽ뙣 ???섎씫 / ?뚭눼留??먮룞 諛⑹??⑸땲??"
        ),
        inline=False,
    )

    return embed



def add_scrim_signup(message_id: int, user_id: int):
    cursor.execute(
        "INSERT OR IGNORE INTO scrim_signups(message_id, user_id) VALUES (?, ?)",
        (str(message_id), str(user_id)),
    )
    conn.commit()

def remove_scrim_signup(message_id: int, user_id: int):
    cursor.execute(
        "DELETE FROM scrim_signups WHERE message_id=? AND user_id=?",
        (str(message_id), str(user_id)),
    )
    conn.commit()


def has_scrim_signup(message_id: int, user_id: int) -> bool:
    cursor.execute(
        "SELECT 1 FROM scrim_signups WHERE message_id=? AND user_id=?",
        (str(message_id), str(user_id)),
    )
    return cursor.fetchone() is not None


def get_scrim_signups(message_id: int):
    cursor.execute(
        "SELECT user_id FROM scrim_signups WHERE message_id=? ORDER BY rowid ASC",
        (str(message_id),),
    )
    return [row[0] for row in cursor.fetchall()]

def get_pending_all_in_dates(guild_id: int, today_date: str):
    cursor.execute(
        """
        SELECT DISTINCT entry_date
        FROM all_in_entries
        WHERE guild_id=? AND entry_date < ?
        ORDER BY entry_date ASC
        """,
        (str(guild_id), today_date),
    )
    return [row[0] for row in cursor.fetchall()]


GAME_LABELS = {
    "?щ’": "?щ’",
    "?숈쟾": "?숈쟾",
    "猷곕젢": "猷곕젢",
    "蹂닿툒": "蹂닿툒",
    "紐곕뭇寃뚯엫": "紐곕뭇寃뚯엫",
}



# ============================================================
# UI 뷰 / 모달
# ============================================================

async def backfill_probation_members():
    for guild in bot.guilds:
        new_member_role_id = get_guild_setting_role_id(guild.id, "new_member_role_id")
        if new_member_role_id is None:
            continue

        probation_role = guild.get_role(new_member_role_id)
        if probation_role is None:
            continue

        now = get_kst_now()
        for member in probation_role.members:
            cursor.execute(
                "SELECT assigned_at FROM probation_roles WHERE guild_id=? AND user_id=?",
                (str(guild.id), str(member.id)),
            )
            if cursor.fetchone():
                continue

            assigned_at = now
            if member.joined_at is not None:
                assigned_at = member.joined_at.astimezone(ZoneInfo("Asia/Seoul"))

            cursor.execute(
                """
                INSERT OR REPLACE INTO probation_roles(guild_id, user_id, assigned_at, notified)
                VALUES (?, ?, ?, 0)
                """,
                (str(guild.id), str(member.id), dt_to_db(assigned_at)),
            )

    conn.commit()


class UpgradePanelTemplateModal(discord.ui.Modal):
    def __init__(self, guild_id: int):
        super().__init__(title="?깆뾽 ?⑤꼸 臾멸뎄 ?ㅼ젙")
        self.guild_id = guild_id
        self.content = discord.ui.TextInput(
            label="?깆뾽 ?⑤꼸 臾멸뎄",
            placeholder="以꾨컮轅덊빐???낅젰?댁＜?몄슂.",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True,
            default=get_template_with_default(
                guild_id,
                "upgrade_panel_text",
                DEFAULT_UPGRADE_PANEL_TEXT,
            ),
        )
        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction):
        set_template(interaction.guild.id, "upgrade_panel_text", str(self.content).strip())
        await interaction.response.send_message("?깆뾽 ?⑤꼸 臾멸뎄瑜???ν뻽?듬땲??", ephemeral=True)


class BirthdayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="?럞 異뺥븯?섍린 (0)", style=discord.ButtonStyle.green, custom_id="birthday_congrats")
    async def congrats(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor.execute(
            "SELECT * FROM congrats WHERE message_id=? AND user_id=?",
            (str(interaction.message.id), str(interaction.user.id)),
        )
        if cursor.fetchone():
            await interaction.response.send_message("?대? 異뺥븯?덉뒿?덈떎 ?럟", ephemeral=True)
            return

        cursor.execute("INSERT INTO congrats VALUES (?,?)", (str(interaction.message.id), str(interaction.user.id)))
        cursor.execute("INSERT OR IGNORE INTO congrats_count VALUES (?,0)", (str(interaction.user.id),))
        cursor.execute("UPDATE congrats_count SET count=count+1 WHERE user_id=?", (str(interaction.user.id),))
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM congrats WHERE message_id=?", (str(interaction.message.id),))
        count = cursor.fetchone()[0]

        button.label = f"?럞 異뺥븯?섍린 ({count})"
        await interaction.message.edit(view=self)

        cursor.execute("SELECT user_id FROM birthday_messages WHERE message_id=?", (str(interaction.message.id),))
        result = cursor.fetchone()
        if result:
            member = interaction.guild.get_member(int(result[0]))
            if member:
                try:
                    embed = discord.Embed(
                        title="?럦 ?앹씪 異뺥븯 ?꾩갑!",
                        description=f"**{interaction.user.display_name}?섏씠 ?뱀떊???앹씪??異뺥븯?덉뒿?덈떎!** ?럟",
                        color=0xFF69B4,
                    )
                    await member.send(embed=embed)
                except Exception:
                    pass

        await interaction.response.send_message("?럦 異뺥븯 ?꾨즺!", ephemeral=True)


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
                desc += f"?럦 **{member.display_name}** - {date} (?ㅻ뒛!)\n"
            elif month == now.month:
                desc += f"狩?**{member.display_name}** - {date}\n"
            else:
                desc += f"{member.display_name} - {date}\n"

        embed = discord.Embed(title="?럟 ?앹씪 紐⑸줉", description=desc or "?곗씠???놁쓬", color=0xFF69B4)
        embed.set_footer(text=f"{self.page + 1}/{self.max_page + 1}")
        return embed

    @discord.ui.button(label="? ?댁쟾")
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="???ㅼ쓬")
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_page:
            self.page += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()


class RuleConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_count(self, message):
        cursor.execute("SELECT COUNT(*) FROM rule_confirm WHERE message_id=?", (str(message.id),))
        count = cursor.fetchone()[0]
        for item in self.children:
            if item.custom_id == "rule_confirm":
                item.label = f"??洹쒖튃 ?뺤씤 ({count})"
        await message.edit(view=self)

    @discord.ui.button(label="??洹쒖튃 ?뺤씤 (0)", style=discord.ButtonStyle.success, custom_id="rule_confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor.execute(
            "SELECT * FROM rule_confirm WHERE message_id=? AND user_id=?",
            (str(interaction.message.id), str(interaction.user.id)),
        )
        if cursor.fetchone():
            await interaction.response.send_message("?대? ?몄쬆 ?꾨즺???곹깭?낅땲??", ephemeral=True)
            return

        cursor.execute("INSERT INTO rule_confirm VALUES (?,?)", (str(interaction.message.id), str(interaction.user.id)))
        conn.commit()

        rule_role_id = get_guild_setting_role_id(interaction.guild.id, "rule_role_id")
        if rule_role_id is not None:
            role = interaction.guild.get_role(rule_role_id)
            if role and role not in interaction.user.roles:
                await interaction.user.add_roles(role)

        await self.update_count(interaction.message)

        rule_log_channel_id = get_guild_setting_channel_id(interaction.guild.id, "rule_log_channel_id")
        if rule_log_channel_id is not None:
            log_channel = interaction.guild.get_channel(rule_log_channel_id)
            if log_channel:
                await log_channel.send(f"??{interaction.user.mention} ?섏씠 洹쒖튃 ?뺤씤")

        await interaction.response.send_message("?럦 洹쒖튃 ?뺤씤 ?꾨즺!", ephemeral=True)


class UpgradePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="?깆뾽?좎껌", style=discord.ButtonStyle.success, custom_id="upgrade_apply")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        existing = discord.utils.get(guild.channels, name=f"{user.name}-?깆뾽?좎껌")
        if existing:
            await interaction.response.send_message("?대? ?좎껌 ?곗폆???덉뒿?덈떎.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True),
        }

        channel = await guild.create_text_channel(
            name=f"{user.name}-?깆뾽?좎껌",
            overwrites=overwrites,
        )

        await channel.send(
            content=f"{user.mention}?섏쓽 ?깆뾽 ?좎껌 梨꾨꼸?낅땲??",
            view=UpgradeTicketView(user),
        )

        await interaction.response.send_message(f"{channel.mention} ?앹꽦 ?꾨즺!", ephemeral=True)


class UpgradeTicketView(discord.ui.View):
    def __init__(self, user: discord.Member):
        super().__init__(timeout=None)
        self.user = user

    def is_admin(self, interaction: discord.Interaction):
        return interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator

    async def disable_buttons_except_delete(self, message):
        for item in self.children:
            if item.custom_id != "ticket_delete":
                item.disabled = True
        await message.edit(view=self)

    async def send_log(self, interaction, action):
        upgrade_log_channel_id = get_guild_setting_channel_id(interaction.guild.id, "upgrade_log_channel_id")
        if upgrade_log_channel_id is None:
            return
        log_channel = interaction.guild.get_channel(upgrade_log_channel_id)
        if log_channel:
            embed = discord.Embed(title="📒 등업 로그", color=0x3498DB)
            embed.add_field(name="대상", value=self.user.mention, inline=True)
            embed.add_field(name="처리자", value=interaction.user.mention, inline=True)
            embed.add_field(name="寃곌낵", value=action, inline=False)
            await log_channel.send(embed=embed)

    async def send_welcome_dm(self):
        guild_id = self.user.guild.id
        template = get_template_with_default(guild_id, "welcome_dm", DEFAULT_WELCOME_DM_TEXT)
        guide_channel_id = get_guild_setting(guild_id, "welcome_guide_channel_id")
        guide_channel_text = f"<#{guide_channel_id}>" if guide_channel_id else "?덈궡 梨꾨꼸"
        content = template.replace("{user}", self.user.mention).replace("{guide_channel}", guide_channel_text)

        try:
            await self.user.send(content)
        except Exception:
            pass

    @discord.ui.button(label="클랜원 등업", style=discord.ButtonStyle.primary, custom_id="upgrade_clan")
    async def clan(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        role_id = get_guild_setting_role_id(interaction.guild.id, "upgrade_clan_role_id")
        role = interaction.guild.get_role(role_id) if role_id else None
        if role:
            await self.user.add_roles(role)

        await self.send_welcome_dm()
        await self.send_log(interaction, "클랜원 등업")
        await self.disable_buttons_except_delete(interaction.message)
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message(f"{self.user.mention}님의 클랜원 등업이 완료되었습니다.")

    @discord.ui.button(label="게스트 등업", style=discord.ButtonStyle.secondary, custom_id="upgrade_guest")
    async def guest(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        role_id = get_guild_setting_role_id(interaction.guild.id, "upgrade_guest_role_id")
        role = interaction.guild.get_role(role_id) if role_id else None
        if role:
            await self.user.add_roles(role)

        await self.send_welcome_dm()
        await self.send_log(interaction, "게스트 등업")
        await self.disable_buttons_except_delete(interaction.message)
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message(f"{self.user.mention}님의 게스트 등업이 완료되었습니다.")

    @discord.ui.button(label="티켓 삭제", style=discord.ButtonStyle.danger, custom_id="ticket_delete")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        await interaction.response.send_message("티켓을 삭제합니다.")
        await interaction.channel.delete()


class TimeRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def add_role(self, interaction: discord.Interaction, slot_name: str):
        role_id = get_time_role_id(interaction.guild.id, slot_name)
        if role_id is None:
            await interaction.response.send_message("해당 시간대 역할이 아직 설정되지 않았습니다.", ephemeral=True)
            return

        role = interaction.guild.get_role(role_id)
        if role is None:
            await interaction.response.send_message("설정된 역할을 찾을 수 없습니다.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("이미 선택한 시간대입니다.", ephemeral=True)
            return

        await interaction.user.add_roles(role)
        await interaction.response.send_message(f"{role.name} 역할을 추가했습니다.", ephemeral=True)

    @discord.ui.button(label="오전반", style=discord.ButtonStyle.primary, custom_id="time_morning")
    async def morning(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, "morning")

    @discord.ui.button(label="오후반", style=discord.ButtonStyle.primary, custom_id="time_afternoon")
    async def afternoon(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, "afternoon")

    @discord.ui.button(label="??곷컲", style=discord.ButtonStyle.primary, custom_id="time_evening")
    async def evening(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, "evening")

    @discord.ui.button(label="심야반", style=discord.ButtonStyle.secondary, custom_id="time_night")
    async def night(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, "night")

    @discord.ui.button(label="새벽반", style=discord.ButtonStyle.secondary, custom_id="time_dawn")
    async def dawn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, "dawn")

    @discord.ui.button(label="由ъ뀑", style=discord.ButtonStyle.danger, custom_id="time_reset")
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_map = get_all_time_roles(interaction.guild.id)
        removed = []
        for role_id in role_map.values():
            role = interaction.guild.get_role(role_id)
            if role and role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                removed.append(role.name)

        if removed:
            await interaction.response.send_message(f"제거된 역할: {', '.join(removed)}", ephemeral=True)
        else:
            await interaction.response.send_message("제거할 시간대 역할이 없습니다.", ephemeral=True)


class CoinFlipView(discord.ui.View):
    def __init__(self, user_id: int, bet_amount: int):
        super().__init__(timeout=COIN_FLIP_TIMEOUT)
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 명령어를 사용한 본인만 누를 수 있습니다.", ephemeral=True)
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
            payout = int(self.bet_amount * 1.8)
            add_balance(self.user_id, payout)
            description = f"선택: **{choice}**\n결과: **{result}**\n축하합니다! `{format_money(payout)}`을 획득했습니다."
            color = 0x2ECC71
        else:
            description = f"선택: **{choice}**\n결과: **{result}**\n아쉽네요... `{format_money(self.bet_amount)}`을 잃었습니다."
            color = 0xE74C3C

        for item in self.children:
            item.disabled = True

        balance = get_balance(self.user_id)
        embed = discord.Embed(title="🪙 동전 던지기 결과", description=description, color=color)
        embed.add_field(name="현재 잔액", value=format_money(balance), inline=False)

        add_game_history(
            interaction.guild.id,
            "동전",
            f"{interaction.user.display_name} - 선택:{choice} / 결과:{result} / {'승리' if win else '패배'}"
        )

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


class RouletteView(discord.ui.View):
    def __init__(self, user_id: int, bet_amount: int):
        super().__init__(timeout=ROULETTE_TIMEOUT)
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 명령어를 사용한 본인만 누를 수 있습니다.", ephemeral=True)
            return False
        return True

    def spin_result(self) -> str:
        return random.choices(
            ["빨강", "노랑", "파랑", "검정", "초록"],
            weights=[35, 25, 19, 12, 9],
            k=1,
        )[0]

    def get_payout(self, choice: str) -> int:
        if choice == "빨강":
            return int(self.bet_amount * 2.5)
        if choice == "노랑":
            return int(self.bet_amount * 3.4)
        if choice == "파랑":
            return int(self.bet_amount * 4.4)
        if choice == "검정":
            return int(self.bet_amount * 6.5)
        if choice == "초록":
            return int(self.bet_amount * 9.5)
        return 0

    async def finish(self, interaction: discord.Interaction, choice: str):
        if self.resolved:
            await interaction.response.send_message("이미 결과가 확정되었습니다.", ephemeral=True)
            return

        self.resolved = True
        result = self.spin_result()
        win = choice == result

        if win:
            payout = self.get_payout(choice)
            add_balance(self.user_id, payout)
            description = f"선택: **{choice}**\n결과: **{result}**\n축하합니다! `{format_money(payout)}`을 획득했습니다."
            color = 0x2ECC71
        else:
            description = f"선택: **{choice}**\n결과: **{result}**\n아쉽네요... `{format_money(self.bet_amount)}`을 잃었습니다."
            color = 0xE74C3C

        for item in self.children:
            item.disabled = True

        balance = get_balance(self.user_id)
        embed = discord.Embed(title="🎡 룰렛 결과", description=description, color=color)
        embed.add_field(name="현재 잔액", value=format_money(balance), inline=False)

        add_game_history(
            interaction.guild.id,
            "룰렛",
            f"{interaction.user.display_name} - 선택:{choice} / 결과:{result} / {'승리' if win else '패배'}"
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.resolved:
            return
        self.resolved = True
        add_balance(self.user_id, self.bet_amount)
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="🟥 빨강", style=discord.ButtonStyle.danger)
    async def red(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "빨강")

    @discord.ui.button(label="🟨 노랑", style=discord.ButtonStyle.primary)
    async def yellow(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "노랑")

    @discord.ui.button(label="🟦 파랑", style=discord.ButtonStyle.primary)
    async def blue(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "파랑")

    @discord.ui.button(label="⬛ 검정", style=discord.ButtonStyle.secondary)
    async def black(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "검정")

    @discord.ui.button(label="🟩 초록", style=discord.ButtonStyle.success)
    async def green(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "초록")



class SupplyDropView(discord.ui.View):
    def __init__(self, user_id: int, bet_amount: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "??踰꾪듉? 紐낅졊?대? ?ъ슜???щ엺留??꾨? ???덉뒿?덈떎.",
                ephemeral=True,
            )
            return False
        return True

    def roll_result(self):
        result = random.choices(
            [
                ("빈 상자", 0.0, "보급 상자를 열었지만 아쉽게도 아무것도 나오지 않았습니다."),
                ("1뚝", 0.9, "낡은 1뚝을 챙겼습니다. 큰 수확은 아니지만 빈손은 아닙니다."),
                ("2뚝", 1.0, "2뚝을 획득했습니다. 본전은 지켰습니다."),
                ("3뚝", 1.6, "3뚝을 획득했습니다! 이번 교전은 조금 더 든든합니다."),
                ("보급 총기 획득", 2.8, "보급 총기를 획득했습니다! 분위기가 달아오르기 시작합니다."),
                ("풀세트 보급 대박", 4.5, "3뚝과 보급 총기까지 모두 챙겼습니다! 말 그대로 풀세트 보급 대박입니다!"),
            ],
            weights=[38, 24, 17, 10, 8, 3],
            k=1,
        )[0]
        return result


    async def open_supply(self, interaction: discord.Interaction):
        if self.resolved:
            await interaction.response.send_message("이미 보급 결과가 확정되었습니다.", ephemeral=True)
            return

        self.resolved = True
        result_name, multiplier, flavor_text = self.roll_result()
        payout = int(self.bet_amount * multiplier)

        if payout > 0:
            add_balance(self.user_id, payout)

        for item in self.children:
            item.disabled = True

        balance = get_balance(self.user_id)

        if multiplier == 0:
            color = 0xE74C3C
            desc = (
                f"결과: **{result_name}**\n"
                f"{flavor_text}\n\n"
                f"`{format_money(self.bet_amount)}`을 잃었습니다."
            )
        else:
            color = 0x2ECC71 if multiplier >= 1.6 else 0x3498DB
            desc = (
                f"결과: **{result_name}**\n"
                f"{flavor_text}\n\n"
                f"`{format_money(payout)}`을 획득했습니다."
            )

        embed = discord.Embed(
            title="📦 보급 상자 결과",
            description=desc,
            color=color,
        )
        embed.add_field(name="현재 잔액", value=format_money(balance), inline=False)

        add_game_history(
            interaction.guild.id,
            "보급",
            f"{interaction.user.display_name} - 결과:{result_name} / 배당:{multiplier}배"
        )

        await interaction.response.edit_message(embed=embed, view=self)


    async def on_timeout(self):
        if self.resolved:
            return

        self.resolved = True
        add_balance(self.user_id, self.bet_amount)

        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="?벀 蹂닿툒 ?닿린", style=discord.ButtonStyle.primary)
    async def open_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_supply(interaction)


class TeamSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    async def create_team(self, interaction: discord.Interaction, team_size: int):
        if interaction.user.voice is None:
            await interaction.response.send_message("???뚯꽦梨꾨꼸???덉뼱???⑸땲??", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        players = [
            member.display_name
            for member in channel.members
            if not member.bot and not is_spectator_member(member, interaction.guild.id)
        ]


        if len(players) < 2:
            await interaction.response.send_message("?뚮젅?댁뼱媛 遺議깊빀?덈떎.", ephemeral=True)
            return

        random.shuffle(players)
        teams = [players[i:i + team_size] for i in range(0, len(players), team_size)]

        embed = discord.Embed(
            title="?렜 ?쒕뜡 ? 寃곌낵",
            description=f"梨꾨꼸: {channel.name}",
            color=0x2ECC71,
        )
        for index, team in enumerate(teams, start=1):
            embed.add_field(name=f"? {index}", value="\n".join(team), inline=False)

        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="2紐??", style=discord.ButtonStyle.primary)
    async def team2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_team(interaction, 2)

    @discord.ui.button(label="3紐??", style=discord.ButtonStyle.primary)
    async def team3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_team(interaction, 3)

    @discord.ui.button(label="4紐??", style=discord.ButtonStyle.success)
    async def team4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_team(interaction, 4)

    @discord.ui.button(label="5紐??", style=discord.ButtonStyle.secondary)
    async def team5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_team(interaction, 5)


class NicknamePrefixApplyButton(discord.ui.Button):
    def __init__(self, prefix: str, managed_prefixes: list[str], panel_key: str):
        super().__init__(
            label=f"{prefix}?곸슜",
            style=discord.ButtonStyle.primary,
            custom_id=f"nickname_prefix_apply:{panel_key}:{prefix}",
        )
        self.prefix = prefix
        self.managed_prefixes = managed_prefixes

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        new_nick = apply_prefix_to_nickname(
            member.display_name,
            self.prefix,
            self.managed_prefixes,
        )

        try:
            await member.edit(nick=new_nick)
        except discord.Forbidden:
            await interaction.response.send_message("닉네임을 변경할 권한이 없습니다.", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.response.send_message("닉네임 변경 중 오류가 발생했습니다.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"닉네임 앞에 `[{self.prefix}]` 접두어를 적용했습니다.",
            ephemeral=True,
        )


class NicknamePrefixResetButton(discord.ui.Button):
    def __init__(self, managed_prefixes: list[str], panel_key: str):
        super().__init__(
            label="원래대로",
            style=discord.ButtonStyle.secondary,
            custom_id=f"nickname_prefix_reset:{panel_key}",
        )
        self.managed_prefixes = managed_prefixes

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        new_nick = reset_prefix_from_nickname(
            member.display_name,
            self.managed_prefixes,
        )

        try:
            await member.edit(nick=new_nick)
        except discord.Forbidden:
            await interaction.response.send_message("닉네임을 변경할 권한이 없습니다.", ephemeral=True)
            return
        except discord.HTTPException:
            await interaction.response.send_message("닉네임 변경 중 오류가 발생했습니다.", ephemeral=True)
            return

        await interaction.response.send_message(
            "닉네임을 원래대로 되돌렸습니다.",
            ephemeral=True,
        )


class NicknamePrefixView(discord.ui.View):
    def __init__(self, guild_id: int, channel_id: int, message_id: int, prefixes: list[str]):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.message_id = message_id
        self.prefixes = prefixes

        panel_key = f"{guild_id}:{channel_id}:{message_id}"

        for prefix in prefixes:
            self.add_item(NicknamePrefixApplyButton(prefix, prefixes, panel_key))

        self.add_item(NicknamePrefixResetButton(prefixes, panel_key))

class InquiryManageView(discord.ui.View):
    def __init__(self, user: discord.Member, ticket_type: str):
        super().__init__(timeout=None)
        self.user = user
        self.ticket_type = ticket_type

    def is_admin(self, interaction: discord.Interaction):
        return interaction.user.guild_permissions.manage_channels or interaction.user.guild_permissions.administrator

    @discord.ui.button(label="?곗폆蹂닿?", style=discord.ButtonStyle.secondary, custom_id="inquiry_archive")
    async def archive_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("愿由ъ옄留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
            return

        await interaction.channel.set_permissions(self.user, send_messages=False)
        await interaction.response.send_message("?곗폆??蹂닿??덉뒿?덈떎. ?묒꽦?먮뒗 ???댁긽 硫붿떆吏瑜?蹂대궪 ???놁뒿?덈떎.")

    @discord.ui.button(label="?곗폆??젣", style=discord.ButtonStyle.danger, custom_id="inquiry_delete")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("愿由ъ옄留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
            return

        await interaction.response.send_message("?곗폆????젣?⑸땲??")
        await interaction.channel.delete()


class InquiryPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str):
        guild = interaction.guild
        user = interaction.user

        existing = discord.utils.get(
            guild.channels,
            name=f"{user.name}-{ticket_type}"
        )
        if existing:
            await interaction.response.send_message(f"?대? {ticket_type} ?곗폆???덉뒿?덈떎: {existing.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }

        channel = await guild.create_text_channel(
            name=f"{user.name}-{ticket_type}",
            overwrites=overwrites,
        )

        embed = discord.Embed(
            title=f"{ticket_type} ?곗폆",
            description=f"{user.mention}?섏쓽 [{ticket_type}] ?낅땲??",
            color=0x5865F2,
        )

        await channel.send(
            content=user.mention,
            embed=embed,
            view=InquiryManageView(user, ticket_type),
        )

        await interaction.response.send_message(f"{channel.mention} ?곗폆???앹꽦?섏뿀?듬땲??", ephemeral=True)

    @discord.ui.button(label="臾몄쓽?섍린", style=discord.ButtonStyle.primary, custom_id="inquiry_open")
    async def inquiry_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "臾몄쓽")

    @discord.ui.button(label="?좉퀬?섍린", style=discord.ButtonStyle.danger, custom_id="report_open")
    async def report_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "?좉퀬")

    @discord.ui.button(label="嫄댁쓽?섍린", style=discord.ButtonStyle.success, custom_id="suggest_open")
    async def suggest_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "嫄댁쓽")

class HistoryGameSelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id

    async def show_history(self, interaction: discord.Interaction, game_name: str):
        rows = get_recent_game_history(self.guild_id, game_name, GAME_HISTORY_LIMIT)

        if not rows:
            await interaction.response.send_message(
                f"{game_name}??理쒓렐 湲곕줉???놁뒿?덈떎.",
                ephemeral=True,
            )
            return

        lines = []
        for idx, (result_text, created_at) in enumerate(rows, start=1):
            try:
                dt = dt_from_db(created_at).strftime("%m-%d %H:%M")
            except Exception:
                dt = created_at
            lines.append(f"{idx}. [{dt}] {result_text}")

        embed = discord.Embed(
            title=f"?뱶 {game_name} 理쒓렐 {min(len(rows), GAME_HISTORY_LIMIT)}寃뚯엫",
            description="\n".join(lines),
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="?щ’", style=discord.ButtonStyle.primary)
    async def slot_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "?щ’")

    @discord.ui.button(label="?숈쟾", style=discord.ButtonStyle.primary)
    async def coin_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "?숈쟾")

    @discord.ui.button(label="猷곕젢", style=discord.ButtonStyle.primary)
    async def roulette_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "猷곕젢")

    @discord.ui.button(label="蹂닿툒", style=discord.ButtonStyle.success)
    async def supply_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "蹂닿툒")

    @discord.ui.button(label="紐곕뭇寃뚯엫", style=discord.ButtonStyle.secondary)
    async def all_in_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "紐곕뭇寃뚯엫")

class DuckmongView(discord.ui.View):
    def __init__(self, user_id: int, bet_amount: int, fake_names: list[str], hidden_results: dict[str, str]):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.fake_names = fake_names
        self.hidden_results = hidden_results
        self.resolved = False

        for fake_name in fake_names:
            self.add_item(DuckmongChoiceButton(fake_name))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("??踰꾪듉? 紐낅졊?대? ?ъ슜???щ엺留??꾨? ???덉뒿?덈떎.", ephemeral=True)
            return False
        return True

    async def resolve_choice(self, interaction: discord.Interaction, fake_name: str):
        if self.resolved:
            await interaction.response.send_message("?대? 寃곌낵媛 ?뺤젙?섏뿀?듬땲??", ephemeral=True)
            return

        self.resolved = True
        result_type = self.hidden_results[fake_name]

        payout = 0
        if result_type == "오리":
            payout = self.bet_amount * 2
            add_balance(self.user_id, payout)
            result_text = f"정답은 **오리**였습니다! `{format_money(self.bet_amount)}`을 추가로 벌었습니다."
            color = 0x2ECC71
        elif result_type == "너리콘":
            payout = self.bet_amount
            add_balance(self.user_id, payout)
            result_text = "정답은 **너리콘**이었습니다! 베팅 금액을 그대로 돌려받았습니다."
            color = 0x3498DB
        else:
            result_text = "정답은 **거위**였습니다! 베팅 금액을 잃었습니다."
            color = 0xE74C3C

        for item in self.children:
            item.disabled = True

        reveal_lines = []
        for name in self.fake_names:
            reveal_lines.append(f"{name} -> {self.hidden_results[name]}")

        embed = discord.Embed(
            title="🦆 오리를 찾아라 결과",
            description=(
                f"선택한 직업: **{fake_name}**\n"
                f"{result_text}\n\n"
                f"배치 결과:\n" + "\n".join(reveal_lines)
            ),
            color=color,
        )
        embed.add_field(name="?꾩옱 ?붿븸", value=format_money(get_balance(self.user_id)), inline=False)

        add_game_history(
            interaction.guild.id,
            "?뺣そ",
            f"{interaction.user.display_name} - ?좏깮:{fake_name} / 寃곌낵:{result_type}"
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.resolved:
            return
        self.resolved = True
        add_balance(self.user_id, self.bet_amount)
        for item in self.children:
            item.disabled = True


class DuckmongChoiceButton(discord.ui.Button):
    def __init__(self, fake_name: str):
        super().__init__(label=fake_name, style=discord.ButtonStyle.primary)
        self.fake_name = fake_name

    async def callback(self, interaction: discord.Interaction):
        await self.view.resolve_choice(interaction, self.fake_name)


def count_members(channel):
    players = 0
    spectators = 0

    for member in channel.members:
        if member.bot:
            continue

        if is_spectator_member(member, channel.guild.id):
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
    return get_color(max_players - players)


def build_description(host, voice_channel, players, spectators, message_content, max_players=None):
    lines = [
        f"모집자 : {host.mention}",
        f"채널 : {voice_channel.name}",
        "",
    ]
    if max_players is None:
        lines.append(f"참여 인원 : {players}명")
        lines.append(f"관전자 : {spectators}")
    else:
        remain = max_players - players
        lines.append(f"참여 인원 : {players} / {max_players}")
        lines.append(f"관전자 : {spectators}")
        lines.append("")
        lines.append(f"남은 자리 : {remain}")
    lines.extend(["", f"메모 : {message_content}"])
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
        embed.title = f"?렜 {self.game_name} 紐⑥쭛以?!"
        embed.color = get_recruit_color(players, self.max_players)
        embed.description = build_description(
            self.host, self.channel, players, spectators, self.message_content, self.max_players
        )
        await self.message.edit(embed=embed, view=self)

        if self.max_players is not None and players >= self.max_players:
            await self.auto_close()

    async def auto_close(self):
        embed = self.message.embeds[0]
        embed.title = f"?렜 {self.game_name} 紐⑥쭛 醫낅즺"
        embed.color = 0xFF0000
        for item in self.children:
            item.disabled = True
        await self.message.edit(embed=embed, view=self)

        if self.channel.id in active_recruits:
            del active_recruits[self.channel.id]

    @discord.ui.button(label="李멸??섍린", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.voice and interaction.user.voice.channel == self.channel:
            await interaction.response.send_message("?대? ?대떦 ?뚯꽦梨꾨꼸??李몄뿬 以묒엯?덈떎.", ephemeral=True)
            return

        permissions = self.channel.permissions_for(interaction.guild.me)
        can_move = permissions.move_members and permissions.connect
        if interaction.user.voice and can_move:
            try:
                await interaction.user.move_to(self.channel)
                await interaction.response.send_message(f"{self.channel.mention} ?뚯꽦梨꾨꼸濡??대룞?덉뒿?덈떎.", ephemeral=True)
                return
            except (discord.Forbidden, discord.HTTPException):
                pass

        invite = await self.channel.create_invite(max_age=300, max_uses=1)
        await interaction.response.send_message(f"諛붾줈 ?대룞 沅뚰븳???놁뼱 珥덈? 留곹겕瑜??쒕┫寃뚯슂: {invite.url}", ephemeral=True)

    @discord.ui.button(label="紐⑥쭛醫낅즺", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            await interaction.response.send_message("紐⑥쭛?먮쭔 醫낅즺?????덉뒿?덈떎.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.auto_close()


class GeneralRecruitModal(discord.ui.Modal, title="醫낃쿇 援ъ씤"):
    game_name = discord.ui.TextInput(
        label="寃뚯엫 ?대쫫",
        placeholder="?? 濡? 諛쒕줈??? 留덊겕",
        max_length=100,
    )
    message_content = discord.ui.TextInput(
        label="구인 메모",
        placeholder="예: 2명만 가볍게 하실 분",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("?뚯꽦梨꾨꼸 癒쇱? ?ㅼ뼱媛?몄슂.", ephemeral=True)
            return

        await create_recruit_post(
            interaction=interaction,
            text_channel=interaction.channel,
            voice_channel=interaction.user.voice.channel,
            host=interaction.user,
            game_name=str(self.game_name).strip(),
            message_content=str(self.message_content).strip() or " ",
            mention_here=False,
            max_players=None,
        )


class WelcomeDmModal(discord.ui.Modal, title="?섏쁺 DM ?ㅼ젙"):
    content = discord.ui.TextInput(
        label="?섏쁺 DM 臾멸뎄",
        placeholder="여러 줄로 입력하세요. {user}, {guide_channel} 사용 가능",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        set_template(interaction.guild.id, "welcome_dm", str(self.content).strip())
        await interaction.response.send_message("?섏쁺 DM 臾멸뎄瑜???ν뻽?듬땲??", ephemeral=True)


class ProtectionPurchaseModal(discord.ui.Modal, title="媛뺥솕蹂댄샇沅?援щℓ"):
    quantity = discord.ui.TextInput(
        label="援щℓ ?섎웾",
        placeholder="?? 1",
        required=True,
        max_length=5,
    )

    def __init__(self, guild_id: int, user_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity = int(str(self.quantity).strip())
        except ValueError:
            await interaction.response.send_message("援щℓ ?섎웾? ?レ옄濡??낅젰?댁＜?몄슂.", ephemeral=True)
            return

        if quantity <= 0:
            await interaction.response.send_message("援щℓ ?섎웾? 1 ?댁긽?댁뼱???⑸땲??", ephemeral=True)
            return

        inventory = get_weapon_inventory(self.guild_id, self.user_id)
        current_level = inventory["weapon_level"]

        if current_level <= 0:
            await interaction.response.send_message("蹂댁쑀 以묒씤 臾닿린媛 ?놁뒿?덈떎.", ephemeral=True)
            return

        tier = get_protection_tier(current_level)
        purchase_level = get_protection_purchase_level(tier)

        if current_level != purchase_level:
            await interaction.response.send_message(
                f"蹂댄샇沅뚯? `{purchase_level}媛????뚮쭔 援щℓ?????덉뒿?덈떎.",
                ephemeral=True,
            )
            return

        protection_cost = get_protection_cost_by_tier(tier)
        total_cost = protection_cost * quantity

        if not can_afford(self.user_id, total_cost):
            await interaction.response.send_message(
                f"蹂댄샇沅?援щℓ 鍮꾩슜 `{format_money(total_cost)}`??遺議깊빀?덈떎.",
                ephemeral=True,
            )
            return

        add_balance(self.user_id, -total_cost)
        add_protection_spent(self.guild_id, self.user_id, total_cost)
        add_protection_count(self.guild_id, self.user_id, tier, quantity)


        embed = build_upgrade_embed(self.guild_id, self.user_id)
        view = WeaponUpgradeView(self.guild_id, self.user_id)

        await interaction.response.edit_message(embed=embed, view=view)


class WeaponUpgradeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="媛뺥솕", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if interaction.user.id != view.user_id:
            await interaction.response.send_message("??踰꾪듉? 紐낅졊?대? ?ъ슜???щ엺留??꾨? ???덉뒿?덈떎.", ephemeral=True)
            return

        inventory = get_weapon_inventory(view.guild_id, view.user_id)
        current_level = inventory["weapon_level"]

        if current_level <= 0:
            ensure_base_weapon(view.guild_id, view.user_id)
            inventory = get_weapon_inventory(view.guild_id, view.user_id)
            current_level = inventory["weapon_level"]

        current_tier = get_protection_tier(current_level)
        protection_count = get_protection_count_for_level(inventory, current_level)


        if current_level >= 21:
            await interaction.response.send_message("?대? 理쒕? 媛뺥솕 ?④퀎?낅땲??", ephemeral=True)
            return

        upgrade_cost = get_upgrade_cost(current_level)
        if upgrade_cost is None:
            await interaction.response.send_message("媛뺥솕 鍮꾩슜 ?뺣낫瑜?李얠쓣 ???놁뒿?덈떎.", ephemeral=True)
            return

        if not can_afford(view.user_id, upgrade_cost):
            await interaction.response.send_message(
                f"媛뺥솕 鍮꾩슜 `{format_money(upgrade_cost)}`??遺議깊빀?덈떎.",
                ephemeral=True,
            )
            return

        add_balance(view.user_id, -upgrade_cost)
        add_upgrade_spent(view.guild_id, view.user_id, upgrade_cost)


        before_name = get_weapon_name(current_level)
        target_level = current_level + 1
        target_name = get_weapon_name(target_level)

        result = roll_upgrade_result(current_level)
        used_protection = False
        message_text = ""
        color = 0x5865F2

        if result == "success":
            set_weapon_level(view.guild_id, view.user_id, target_level)
            message_text = f"媛뺥솕 ?깃났! `{current_level}媛?{before_name}` -> `{target_level}媛?{target_name}`"
            color = 0x2ECC71
        elif result == "down":
            if protection_count > 0:
                consume_protection_count(view.guild_id, view.user_id, current_tier, 1)
                used_protection = True
                message_text = f"媛뺥솕 ?ㅽ뙣! 蹂댄샇沅뚯씠 ?먮룞 ?ъ슜?섏뼱 ?섎씫??諛⑹??섏뿀?듬땲?? ?꾩옱 臾닿린: `{current_level}媛?{before_name}`"
                color = 0x3498DB
            else:
                new_level = max(1, current_level - 1)
                set_weapon_level(view.guild_id, view.user_id, new_level)
                message_text = f"媛뺥솕 ?ㅽ뙣! ?④퀎媛 ?섎씫?덉뒿?덈떎. `{current_level}媛?{before_name}` -> `{new_level}媛?{get_weapon_name(new_level)}`"
                color = 0xE67E22
        elif result == "destroy":
            if protection_count > 0:
                consume_protection_count(view.guild_id, view.user_id, current_tier, 1)
                used_protection = True
                message_text = f"媛뺥솕 ?ㅽ뙣! 蹂댄샇沅뚯씠 ?먮룞 ?ъ슜?섏뼱 ?뚭눼媛 諛⑹??섏뿀?듬땲?? ?꾩옱 臾닿린: `{current_level}媛?{before_name}`"
                color = 0x3498DB
            else:
                reset_weapon_progress(view.guild_id, view.user_id)
                message_text = f"媛뺥솕 ?ㅽ뙣! `{current_level}媛?{before_name}` 臾닿린媛 ?뚭눼?섏뿀?듬땲??"
                color = 0xE74C3C
        else:
            message_text = f"媛뺥솕 ?ㅽ뙣! ?④퀎???좎??섏뿀?듬땲?? ?꾩옱 臾닿린: `{current_level}媛?{before_name}`"
            color = 0x95A5A6

        add_game_history(
            interaction.guild.id,
            "媛뺥솕",
            f"{interaction.user.display_name} - {current_level}강 {before_name} / 결과:{result}{' / 보호권 사용' if used_protection else ''}"
        )

        embed = build_upgrade_embed(view.guild_id, view.user_id)
        embed.title = "?뵩 臾닿린 媛뺥솕 寃곌낵"
        embed.color = color
        embed.description = message_text

        await interaction.response.edit_message(embed=embed, view=WeaponUpgradeView(view.guild_id, view.user_id))


class ProtectionPurchaseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="보호권 구매", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if interaction.user.id != view.user_id:
            await interaction.response.send_message("이 버튼은 명령어를 사용한 본인만 누를 수 있습니다.", ephemeral=True)
            return

        await interaction.response.send_modal(ProtectionPurchaseModal(view.guild_id, view.user_id))


class ScrimSignupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_embed(self, message: discord.Message):
        embed = message.embeds[0]
        user_ids = get_scrim_signups(message.id)

        if user_ids:
            participants = []
            for user_id in user_ids:
                member = message.guild.get_member(int(user_id))
                if member is not None:
                    participants.append(member.mention)
                else:
                    participants.append(f"?????녿뒗 ?좎? ({user_id})")

            participant_text = "\n".join(
                f"{idx}. {name}" for idx, name in enumerate(participants, start=1)
            )
        else:
            participant_text = "?꾩쭅 李몄뿬?먭? ?놁뒿?덈떎."

        if len(embed.fields) >= 1:
            embed.set_field_at(0, name="李몄뿬??紐⑸줉", value=participant_text, inline=False)
        else:
            embed.add_field(name="李몄뿬??紐⑸줉", value=participant_text, inline=False)

        for item in self.children:
            if item.custom_id == "scrim_signup_button":
                item.label = f"李몄뿬?섍린 ({len(user_ids)})"

        await message.edit(embed=embed, view=self)

    @discord.ui.button(label="李몄뿬?섍린 (0)", style=discord.ButtonStyle.success, custom_id="scrim_signup_button")
    async def signup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if has_scrim_signup(interaction.message.id, interaction.user.id):
            await interaction.response.send_message("?대? 李몄뿬???곹깭?낅땲??", ephemeral=True)
            return

        add_scrim_signup(interaction.message.id, interaction.user.id)
        await self.update_embed(interaction.message)
        await interaction.response.send_message("?댁쟾 李몄뿬媛 ?깅줉?섏뿀?듬땲??", ephemeral=True)

    @discord.ui.button(label="李몄뿬痍⑥냼", style=discord.ButtonStyle.danger, custom_id="scrim_cancel_button")
    async def cancel_signup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_scrim_signup(interaction.message.id, interaction.user.id):
            await interaction.response.send_message("?꾩옱 李몄뿬???곹깭媛 ?꾨떃?덈떎.", ephemeral=True)
            return

        remove_scrim_signup(interaction.message.id, interaction.user.id)
        await self.update_embed(interaction.message)
        await interaction.response.send_message("?댁쟾 李몄뿬媛 痍⑥냼?섏뿀?듬땲??", ephemeral=True)

class ScrimNoticeModal(discord.ui.Modal, title="?댁쟾 怨듭? ?묒꽦"):
    title_input = discord.ui.TextInput(
        label="?쒕ぉ",
        placeholder="?? ?ㅻ뒛 ???9???댁쟾 紐⑥쭛",
        max_length=100,
        required=True,
    )
    body_input = discord.ui.TextInput(
        label="蹂몃Ц",
        placeholder="?? 李몄뿬?섏떎 遺꾩? ?꾨옒 踰꾪듉???뚮윭二쇱꽭??",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=str(self.title_input).strip(),
            description=str(self.body_input).strip(),
            color=0x5865F2,
        )
        embed.add_field(name="李몄뿬??紐⑸줉", value="?꾩쭅 李몄뿬?먭? ?놁뒿?덈떎.", inline=False)

        await interaction.channel.send(embed=embed, view=ScrimSignupView())
        await interaction.response.send_message("?댁쟾 怨듭?瑜??깅줉?덉뒿?덈떎.", ephemeral=True)



class WeaponUpgradeView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.user_id = user_id

        self.add_item(WeaponUpgradeButton())
        self.add_item(ProtectionPurchaseButton())


class LaborWorkView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.user_id = user_id

    @discord.ui.button(label="?몃룞?섍린", style=discord.ButtonStyle.primary)
    async def work(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("??踰꾪듉? 紐낅졊?대? ?ъ슜???щ엺留??꾨? ???덉뒿?덈떎.", ephemeral=True)
            return

        penalty, resolved = increment_labor_count(self.guild_id, self.user_id)
        if penalty is None:
            await interaction.response.send_message("吏꾪뻾 以묒씤 ?몃룞 ?⑤꼸?곌? ?놁뒿?덈떎.", ephemeral=True)
            return

        embed = build_labor_embed(interaction.user, penalty)

        if resolved:
            embed.title = "???몃룞 ?꾨즺"
            embed.color = 0x2ECC71
            embed.add_field(
                name="寃곌낵",
                value=f"?꾩슂 ?몃룞 ?잛닔瑜?紐⑤몢 梨꾩썙 ?좎슜遺덈웾???곹깭媛 ?댁젣?섍퀬 `{INITIAL_CREDIT_GRADE}?깃툒`?쇰줈 珥덇린?붾릺?덉뒿?덈떎.",
                inline=False,
            )
            for item in self.children:
                item.disabled = True
        else:
            embed.add_field(name="寃곌낵", value="?몃룞 1?뚮? ?꾨즺?덉뒿?덈떎.", inline=False)

        await interaction.response.edit_message(embed=embed, view=self)


class StickyMessageModal(discord.ui.Modal, title="怨좎젙硫붿떆吏 ?ㅼ젙"):
    content = discord.ui.TextInput(
        label="怨좎젙??硫붿떆吏 ?댁슜",
        placeholder="?ш린???щ윭 以꾨줈 ?낅젰?섏꽭??",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        content = str(self.content).strip()
        existing = get_sticky_message(interaction.guild.id, interaction.channel.id)

        if existing and existing.get("message_id"):
            try:
                old_message = await interaction.channel.fetch_message(existing["message_id"])
                await old_message.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        sticky_msg = await interaction.channel.send(content)
        set_sticky_message(interaction.guild.id, interaction.channel.id, content, sticky_msg.id)

        await interaction.response.send_message(
            f"{interaction.channel.mention} 梨꾨꼸??怨좎젙硫붿떆吏瑜??ㅼ젙?덉뒿?덈떎.",
            ephemeral=True,
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
        title=f"?렜 {game_name} 紐⑥쭛以?!",
        description=build_description(host, voice_channel, players, spectators, message_content, max_players),
        color=get_recruit_color(players, max_players),
    )

    view = RecruitView(voice_channel, host, game_name, message_content, max_players=max_players)
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


# ============================================================
# 슬래시 명령어
# ============================================================

# ----------------------------
# 관리자 설정 명령어
# ----------------------------

@bot.tree.command(name="세팅생일알림", description="현재 채널을 생일 알림 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_birthday_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "birthday_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"?앹씪 ?뚮┝ 梨꾨꼸??{interaction.channel.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="세팅등업로그", description="현재 채널을 등업 로그 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_upgrade_log_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "upgrade_log_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"?깆뾽 濡쒓렇 梨꾨꼸??{interaction.channel.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="세팅퇴장로그", description="현재 채널을 퇴장 로그 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_leave_log_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "leave_log_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"?댁옣 濡쒓렇 梨꾨꼸??{interaction.channel.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="세팅규칙로그", description="현재 채널을 규칙/신입 알림 로그 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_rule_log_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "rule_log_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"洹쒖튃 濡쒓렇 梨꾨꼸??{interaction.channel.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="세팅구인채널", description="현재 채널을 구인 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_recruit_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "recruit_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"援ъ씤 梨꾨꼸??{interaction.channel.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.", ephemeral=True)

@bot.tree.command(name="세팅몰빵결과채널", description="현재 채널을 몰빵게임 결과 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_all_in_result_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "all_in_result_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(
        f"紐곕뭇寃뚯엫 寃곌낵 梨꾨꼸??{interaction.channel.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.",
        ephemeral=True,
    )

@bot.tree.command(name="세팅가이드안내", description="현재 채널을 가이드 안내 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_guide_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "welcome_guide_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"媛???덈궡 梨꾨꼸??{interaction.channel.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="세팅환영메시지채널", description="현재 채널을 환영 메시지 출력 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_message_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "welcome_message_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"?섏쁺硫붿떆吏 梨꾨꼸??{interaction.channel.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="세팅규칙역할", description="규칙 확인 시 지급할 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_rule_role(interaction: discord.Interaction, role: discord.Role):
    set_guild_setting(interaction.guild.id, "rule_role_id", str(role.id))
    await interaction.response.send_message(f"洹쒖튃 ??븷??{role.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="세팅신입역할", description="신입 추적용 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_new_member_role(interaction: discord.Interaction, role: discord.Role):
    set_guild_setting(interaction.guild.id, "new_member_role_id", str(role.id))
    await interaction.response.send_message(f"?좎엯 ??븷??{role.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="세팅생일역할", description="생일 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_birthday_role(interaction: discord.Interaction, role: discord.Role):
    set_guild_setting(interaction.guild.id, "birthday_role_id", str(role.id))
    await interaction.response.send_message(f"?앹씪 ??븷??{role.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="세팅클랜등업역할", description="클랜 등업 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_upgrade_clan_role(interaction: discord.Interaction, role: discord.Role):
    set_guild_setting(interaction.guild.id, "upgrade_clan_role_id", str(role.id))
    await interaction.response.send_message(f"?대옖???깆뾽 ??븷??{role.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="세팅게스트등업역할", description="게스트 등업 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_upgrade_guest_role(interaction: discord.Interaction, role: discord.Role):
    set_guild_setting(interaction.guild.id, "upgrade_guest_role_id", str(role.id))
    await interaction.response.send_message(f"寃뚯뒪???깆뾽 ??븷??{role.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="세팅시간대역할", description="시간대 버튼에 연결할 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(slot_name="morning / afternoon / evening / night / dawn")
async def set_time_role_command(interaction: discord.Interaction, slot_name: str, role: discord.Role):
    slot_name = slot_name.lower().strip()
    if slot_name not in TIME_SLOT_CHOICES:
        await interaction.response.send_message("slot_name? morning, afternoon, evening, night, dawn 以??섎굹?ъ빞 ?⑸땲??", ephemeral=True)
        return

    set_time_role(interaction.guild.id, slot_name, role.id)
    await interaction.response.send_message(f"{TIME_SLOT_LABELS[slot_name]} ??븷??{role.mention} ?쇰줈 ?ㅼ젙?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="세팅환영dm", description="유저에게 보낼 환영 DM 문구를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_dm_template(interaction: discord.Interaction):
    await interaction.response.send_modal(WelcomeDmModal())


@bot.tree.command(name="세팅규칙안내문", description="규칙 버튼 안내문을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_rule_button_template(interaction: discord.Interaction, content: str):
    set_template(interaction.guild.id, "rule_button_text", content)
    await interaction.response.send_message("洹쒖튃 ?덈궡臾몄쓣 ??ν뻽?듬땲??", ephemeral=True)


@bot.tree.command(name="세팅등업패널문구", description="등업 패널 문구를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_upgrade_panel_template(interaction: discord.Interaction):
    await interaction.response.send_modal(UpgradePanelTemplateModal(interaction.guild.id))


@bot.tree.command(name="세팅신입알림문구", description="신입 역할 경과 알림 문구를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_probation_notice_template(interaction: discord.Interaction, content: str):
    set_template(interaction.guild.id, "probation_notice_text", content)
    await interaction.response.send_message("?좎엯 ?뚮┝ 臾멸뎄瑜???ν뻽?듬땲??", ephemeral=True)


@bot.tree.command(name="세팅신입경과일", description="신입 역할 경과 알림 일수를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_probation_days(interaction: discord.Interaction, days: int):
    if days < 1:
        await interaction.response.send_message("?쇱닔??1 ?댁긽?댁뼱???⑸땲??", ephemeral=True)
        return

    set_guild_setting(interaction.guild.id, "probation_days", str(days))
    await interaction.response.send_message(
        f"?좎엯 ??븷 寃쎄낵?쇱쓣 {days}?쇰줈 ?ㅼ젙?덉뒿?덈떎.",
        ephemeral=True,
    )


@bot.tree.command(name="?곴툑?명똿", description="?곴툑 湲곌컙怨??댁옄?⑥쓣 ?ㅼ젙?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def savings_setting(interaction: discord.Interaction, days: int, interest_rate: int):
    if days < 1:
        await interaction.response.send_message("?곴툑 湲곌컙? 1???댁긽?댁뼱???⑸땲??", ephemeral=True)
        return
    if interest_rate < 0:
        await interaction.response.send_message("?댁옄?⑥? 0 ?댁긽?댁뼱???⑸땲??", ephemeral=True)
        return

    set_guild_setting(interaction.guild.id, "savings_days", str(days))
    set_guild_setting(interaction.guild.id, "savings_interest_rate", str(interest_rate))
    await interaction.response.send_message(
        f"?곴툑 ?ㅼ젙????ν뻽?듬땲??\n湲곌컙: `{days}??\n?댁옄?? `{interest_rate}%`",
        ephemeral=True,
    )


@bot.tree.command(name="?ㅼ젙?뺤씤", description="?꾩옱 梨꾨꼸 ?ㅼ젙???뺤씤?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def show_settings(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    keys = [
        ("?앹씪 ?뚮┝", "birthday_channel_id"),
        ("?깆뾽 濡쒓렇", "upgrade_log_channel_id"),
        ("?댁옣 濡쒓렇", "leave_log_channel_id"),
        ("洹쒖튃 濡쒓렇", "rule_log_channel_id"),
        ("援ъ씤 梨꾨꼸", "recruit_channel_id"),
        ("媛???덈궡", "welcome_guide_channel_id"),
        ("?섏쁺硫붿떆吏 梨꾨꼸", "welcome_message_channel_id"),
    ]

    def fmt(channel_id):
        return f"<#{channel_id}>" if channel_id else "미설정"

    embed = discord.Embed(title="채널 설정", color=0x5865F2)
    for label, key in keys:
        embed.add_field(name=label, value=fmt(get_guild_setting(guild_id, key)), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="역할설정확인", description="현재 역할 설정을 확인합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def show_role_settings(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    keys = [
        ("洹쒖튃 ??븷", "rule_role_id"),
        ("?좎엯 ??븷", "new_member_role_id"),
        ("?앹씪 ??븷", "birthday_role_id"),
        ("?대옖???깆뾽 ??븷", "upgrade_clan_role_id"),
        ("寃뚯뒪???깆뾽 ??븷", "upgrade_guest_role_id"),
    ]

    def fmt(role_id):
        return f"<@&{role_id}>" if role_id else "미설정"

    embed = discord.Embed(title="역할 설정", color=0x3498DB)
    for label, key in keys:
        embed.add_field(name=label, value=fmt(get_guild_setting(guild_id, key)), inline=False)

    time_roles = get_all_time_roles(guild_id)
    time_lines = []
    for slot_name in TIME_SLOT_CHOICES:
        role_id = time_roles.get(slot_name)
        label = TIME_SLOT_LABELS[slot_name]
        time_lines.append(f"{label}: {'<@&' + str(role_id) + '>' if role_id else '미설정'}")
    embed.add_field(name="시간대 역할", value="\n".join(time_lines), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="문구설정확인", description="현재 등록된 커스텀 문구를 확인합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def show_template_settings(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    embed = discord.Embed(title="문구 설정", color=0x9B59B6)
    embed.add_field(
        name="?섏쁺 DM",
        value=get_template_with_default(guild_id, "welcome_dm", DEFAULT_WELCOME_DM_TEXT),
        inline=False,
    )
    embed.add_field(
        name="규칙 안내문",
        value=get_template_with_default(guild_id, "rule_button_text", DEFAULT_RULE_BUTTON_TEXT),
        inline=False,
    )
    embed.add_field(
        name="?깆뾽 ?⑤꼸 臾멸뎄",
        value=get_template_with_default(guild_id, "upgrade_panel_text", DEFAULT_UPGRADE_PANEL_TEXT),
        inline=False,
    )
    embed.add_field(
        name="?좎엯 ?뚮┝ 臾멸뎄",
        value=get_template_with_default(guild_id, "probation_notice_text", DEFAULT_PROBATION_NOTICE_TEXT),
        inline=False,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="?섏쁺硫붿떆吏", description="?뱀젙 ??븷??????섏쁺硫붿떆吏瑜??ㅼ젙?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def welcome_message(interaction: discord.Interaction, role: discord.Role, content: str):
    set_welcome_message(interaction.guild.id, role.id, content)
    await interaction.response.send_message(f"{role.mention} ??븷???섏쁺硫붿떆吏瑜???ν뻽?듬땲??", ephemeral=True)


@bot.tree.command(name="?섏쁺硫붿떆吏??젣", description="?뱀젙 ??븷???섏쁺硫붿떆吏瑜???젣?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def delete_welcome_message_command(interaction: discord.Interaction, role: discord.Role):
    delete_welcome_message(interaction.guild.id, role.id)
    await interaction.response.send_message(f"{role.mention} ??븷???섏쁺硫붿떆吏瑜???젣?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="?섏쁺硫붿떆吏紐⑸줉", description="?깅줉???섏쁺硫붿떆吏 紐⑸줉???뺤씤?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def list_welcome_messages(interaction: discord.Interaction):
    rows = get_all_welcome_messages(interaction.guild.id)
    if not rows:
        await interaction.response.send_message("?깅줉???섏쁺硫붿떆吏媛 ?놁뒿?덈떎.", ephemeral=True)
        return

    lines = []
    for role_id, content in rows:
        lines.append(f"<@&{role_id}> -> {content}")

    embed = discord.Embed(title="?섏쁺硫붿떆吏 紐⑸줉", description="\n\n".join(lines), color=0x2ECC71)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="怨좎젙硫붿떆吏", description="?꾩옱 梨꾨꼸????긽 ?섎떒???좎???硫붿떆吏瑜??ㅼ젙?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def sticky_message(interaction: discord.Interaction):
    await interaction.response.send_modal(StickyMessageModal())


@bot.tree.command(name="怨좎젙?댁젣", description="?꾩옱 梨꾨꼸??怨좎젙硫붿떆吏瑜??댁젣?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def sticky_clear(interaction: discord.Interaction):
    existing = get_sticky_message(interaction.guild.id, interaction.channel.id)
    if not existing:
        await interaction.response.send_message("??梨꾨꼸?먮뒗 ?ㅼ젙??怨좎젙硫붿떆吏媛 ?놁뒿?덈떎.", ephemeral=True)
        return

    if existing.get("message_id"):
        try:
            old_message = await interaction.channel.fetch_message(existing["message_id"])
            await old_message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    clear_sticky_message(interaction.guild.id, interaction.channel.id)
    await interaction.response.send_message("?꾩옱 梨꾨꼸??怨좎젙硫붿떆吏瑜??댁젣?덉뒿?덈떎.", ephemeral=True)


@bot.tree.command(name="怨좎젙?뺤씤", description="?꾩옱 梨꾨꼸??怨좎젙硫붿떆吏 ?댁슜???뺤씤?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def sticky_check(interaction: discord.Interaction):
    existing = get_sticky_message(interaction.guild.id, interaction.channel.id)
    if not existing:
        await interaction.response.send_message("??梨꾨꼸?먮뒗 ?ㅼ젙??怨좎젙硫붿떆吏媛 ?놁뒿?덈떎.", ephemeral=True)
        return

    embed = discord.Embed(title="怨좎젙硫붿떆吏 ?뺤씤", color=0x5865F2)
    embed.add_field(name="梨꾨꼸", value=interaction.channel.mention, inline=False)
    embed.add_field(name="?댁슜", value=existing["content"], inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="?앹씪?깅줉", description="?좎????앹씪???깅줉?⑸땲??")
@app_commands.describe(member="?앹씪???깅줉???좎?", date="MM-DD ?뺤떇?쇰줈 ?낅젰")
async def add_birthday(interaction: discord.Interaction, member: discord.Member, date: str):
    try:
        normalized_date = normalize_birthday(date)
    except ValueError as error:
        await interaction.response.send_message(str(error), ephemeral=True)
        return

    cursor.execute("INSERT OR REPLACE INTO birthdays VALUES (?,?)", (str(member.id), normalized_date))
    conn.commit()
    await interaction.response.send_message("?깅줉 ?꾨즺", ephemeral=True)


@bot.tree.command(name="?앹씪??젣", description="?좎????앹씪 ?뺣낫瑜???젣?⑸땲??")
async def remove_birthday(interaction: discord.Interaction, member: discord.Member):
    cursor.execute("DELETE FROM birthdays WHERE user_id=?", (str(member.id),))
    conn.commit()
    await interaction.response.send_message("??젣 ?꾨즺", ephemeral=True)


@bot.tree.command(name="?앹씪紐⑸줉", description="?깅줉???앹씪 紐⑸줉???뺤씤?⑸땲??")
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


@bot.tree.command(name="洹쒖튃踰꾪듉", description="洹쒖튃 ?뺤씤 踰꾪듉 硫붿떆吏瑜??앹꽦?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def rule_button(interaction: discord.Interaction):
    text = get_template_with_default(interaction.guild.id, "rule_button_text", DEFAULT_RULE_BUTTON_TEXT)
    embed = discord.Embed(description=text, color=0x2ECC71)
    await interaction.channel.send(embed=embed, view=RuleConfirmView())
    await interaction.response.send_message("洹쒖튃 踰꾪듉 ?앹꽦 ?꾨즺", ephemeral=True)


@bot.tree.command(name="?깆뾽?⑤꼸", description="?깆뾽 ?좎껌 ?⑤꼸???앹꽦?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def upgrade_panel(interaction: discord.Interaction):
    text = get_template_with_default(interaction.guild.id, "upgrade_panel_text", DEFAULT_UPGRADE_PANEL_TEXT)
    embed = discord.Embed(description=text, color=0x5865F2)
    await interaction.channel.send(embed=embed, view=UpgradePanelView())
    await interaction.response.send_message("?깆뾽 ?⑤꼸 ?앹꽦 ?꾨즺", ephemeral=True)


@bot.tree.command(name="?쒓컙?ㅼ젙?⑤꼸", description="?쒓컙? ??븷 ?좏깮 ?⑤꼸???앹꽦?⑸땲??")
async def time_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="?뚮젅???쒓컙? ?ㅼ젙",
        description="?먰븯???쒓컙?瑜??좏깮?댁＜?몄슂.\n以묐났 ?좏깮 媛?ν빀?덈떎.",
        color=0x5865F2,
    )
    await interaction.channel.send(embed=embed, view=TimeRoleView())
    await interaction.response.send_message("?쒓컙 ?ㅼ젙 ?⑤꼸 ?앹꽦 ?꾨즺", ephemeral=True)


# ----------------------------
# 재화 / 적금 명령어
# ----------------------------

@bot.tree.command(name="?곸깮吏?먭툑", description="?섎（????踰??곸깮吏?먭툑 10,000?먯쓣 諛쏆뒿?덈떎.")
async def daily_money(interaction: discord.Interaction):
    today = get_kst_now().strftime("%Y-%m-%d")
    cursor.execute("SELECT last_claim_date FROM daily_claims WHERE user_id=?", (str(interaction.user.id),))
    row = cursor.fetchone()
    if row and row[0] == today:
        await interaction.response.send_message("?ㅻ뒛? ?대? ?덉쓣 諛쏆븯?듬땲?? ?댁씪 ?ㅼ떆 ?쒕룄?댁＜?몄슂.", ephemeral=True)
        return

    ensure_wallet(interaction.user.id)
    add_balance(interaction.user.id, DAILY_REWARD)
    cursor.execute(
        "INSERT OR REPLACE INTO daily_claims(user_id, last_claim_date) VALUES (?, ?)",
        (str(interaction.user.id), today),
    )
    conn.commit()

    await interaction.response.send_message(
        f"?ㅻ뒛???곸깮吏?먭툑 `{format_money(DAILY_REWARD)}`??諛쏆븯?듬땲??\n?꾩옱 ?붿븸: `{format_money(get_balance(interaction.user.id))}`"
    )


@bot.tree.command(name="?붿븸", description="?꾩옱 ??蹂댁쑀 湲덉븸???뺤씤?⑸땲??")
async def balance(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"{interaction.user.mention}?섏쓽 ?꾩옱 ?붿븸? `{format_money(get_balance(interaction.user.id))}`?낅땲??"
    )


@bot.tree.command(name="?곴툑", description="?꾩옱 ?쒕쾭 ?ㅼ젙 湲곗??쇰줈 ?곴툑??媛?낇빀?덈떎.")
async def savings_join(interaction: discord.Interaction, amount: int):
    if interaction.guild is None:
        await interaction.response.send_message("?쒕쾭?먯꽌留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("?곴툑 湲덉븸? 1???댁긽?댁뼱???⑸땲??", ephemeral=True)
        return
    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("?붿븸??遺議깊빀?덈떎.", ephemeral=True)
        return
    if get_active_saving(interaction.guild.id, interaction.user.id) is not None:
        await interaction.response.send_message("?대? 吏꾪뻾 以묒씤 ?곴툑???덉뒿?덈떎. `/?댁쟻湲??쇰줈 ?뺤씤?댁＜?몄슂.", ephemeral=True)
        return

    days = get_savings_days(interaction.guild.id)
    interest_rate = get_savings_interest_rate(interaction.guild.id)
    due_at = get_kst_now() + timedelta(days=days)
    total_amount = int(amount * (100 + interest_rate) / 100)

    add_balance(interaction.user.id, -amount)
    create_saving(interaction.guild.id, interaction.user.id, amount, interest_rate, total_amount, due_at)

    embed = discord.Embed(title="🏦 적금 가입 완료", color=0x3498DB)
    embed.add_field(name="원금", value=format_money(amount), inline=False)
    embed.add_field(name="이자율", value=f"{interest_rate}%", inline=False)
    embed.add_field(name="만기 수령액", value=format_money(total_amount), inline=False)
    embed.add_field(name="만기일", value=due_at.strftime("%Y-%m-%d %H:%M:%S KST"), inline=False)
    embed.add_field(name="현재 잔액", value=format_money(get_balance(interaction.user.id)), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="내적금", description="현재 가입 중인 적금 정보를 확인합니다.")
async def my_savings(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("?쒕쾭?먯꽌留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
        return

    saving = get_active_saving(interaction.guild.id, interaction.user.id)
    if saving is None:
        await interaction.response.send_message("?꾩옱 媛??以묒씤 ?곴툑???놁뒿?덈떎.", ephemeral=True)
        return

    due_at = dt_from_db(saving["due_at"])
    matured = get_kst_now() >= due_at

    embed = discord.Embed(title="🏦 내 적금", color=0x1ABC9C)
    embed.add_field(name="원금", value=format_money(saving["principal"]), inline=False)
    embed.add_field(name="이자율", value=f"{saving['interest_rate']}%", inline=False)
    embed.add_field(name="만기 수령액", value=format_money(saving["total_amount"]), inline=False)
    embed.add_field(name="만기일", value=due_at.strftime("%Y-%m-%d %H:%M:%S KST"), inline=False)
    embed.add_field(name="상태", value="수령 가능" if matured else "적금 진행 중", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="적금수령", description="만기된 적금을 수령합니다.")
async def savings_claim(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("?쒕쾭?먯꽌留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
        return

    saving = get_active_saving(interaction.guild.id, interaction.user.id)
    if saving is None:
        await interaction.response.send_message("?꾩옱 ?섎졊???곴툑???놁뒿?덈떎.", ephemeral=True)
        return

    due_at = dt_from_db(saving["due_at"])
    if get_kst_now() < due_at:
        await interaction.response.send_message("?꾩쭅 ?곴툑 留뚭린 ?꾩엯?덈떎.", ephemeral=True)
        return

    add_balance(interaction.user.id, saving["total_amount"])
    claim_saving(saving["id"])

    embed = discord.Embed(title="🏦 적금 수령 완료", color=0x2ECC71)
    embed.add_field(name="수령액", value=format_money(saving["total_amount"]), inline=False)
    embed.add_field(name="현재 잔액", value=format_money(get_balance(interaction.user.id)), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="재산", description="서버 재산 상위 10명을 확인합니다.")
async def ranking(interaction: discord.Interaction):
    cursor.execute("SELECT user_id, balance FROM balances ORDER BY balance DESC, user_id ASC LIMIT 10")
    rows = cursor.fetchall()
    if not rows:
        await interaction.response.send_message("?꾩쭅 ??궧 ?곗씠?곌? ?놁뒿?덈떎.")
        return

    lines = []
    for index, (user_id, amount) in enumerate(rows, start=1):
        member = interaction.guild.get_member(int(user_id))
        name = member.display_name if member else f"?????녿뒗 ?좎? ({user_id})"
        medal = "?몣 " if index == 1 else ""
        lines.append(f"{index}. {medal}{name} - {format_money(amount)}")

    embed = discord.Embed(title="?뮥 ?먯궛 ??궧", description="\n".join(lines), color=0xF1C40F)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="?↔툑", description="?ㅻⅨ ?좎??먭쾶 ?덉쓣 ?↔툑?⑸땲??")
async def transfer(interaction: discord.Interaction, member: discord.Member, amount: int):
    if member.bot:
        await interaction.response.send_message("遊뉗뿉寃뚮뒗 ?↔툑?????놁뒿?덈떎.", ephemeral=True)
        return
    if member.id == interaction.user.id:
        await interaction.response.send_message("?먭린 ?먯떊?먭쾶???↔툑?????놁뒿?덈떎.", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("?↔툑 湲덉븸? 1???댁긽?댁뼱???⑸땲??", ephemeral=True)
        return
    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("?붿븸??遺議깊빀?덈떎.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)
    add_balance(member.id, amount)
    await interaction.response.send_message(
        f"{member.mention}?섏뿉寃?`{format_money(amount)}`???↔툑?덉뒿?덈떎.\n?꾩옱 ?붿븸: `{format_money(get_balance(interaction.user.id))}`"
    )


@bot.tree.command(name="돈주기", description="서버 관리자 이상이 여러 유저에게 같은 금액을 지급합니다.")
@app_commands.rename(targets="대상들", amount="금액")
@app_commands.describe(
    targets="硫섏뀡 ?먮뒗 ID瑜?怨듬갚/?쇳몴濡?援щ텇?댁꽌 ?낅젰",
    amount="媛??좎??먭쾶 吏湲됲븷 湲덉븸",
)
async def grant_money(interaction: discord.Interaction, targets: str, amount: int):
    if interaction.guild is None:
        await interaction.response.send_message("?쒕쾭?먯꽌留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
        return

    if not (
        interaction.user.id == interaction.guild.owner_id
        or interaction.user.guild_permissions.administrator
        or interaction.user.guild_permissions.manage_guild
    ):
        await interaction.response.send_message("??紐낅졊?대뒗 ?쒕쾭 愿由ъ옄 ?댁긽留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("吏湲?湲덉븸? 1???댁긽?댁뼱???⑸땲??", ephemeral=True)
        return

    raw_ids = []
    for token in targets.replace(",", " ").split():
        cleaned = token.strip().replace("<@", "").replace("!", "").replace(">", "")
        if cleaned.isdigit():
            raw_ids.append(int(cleaned))

    if not raw_ids:
        await interaction.response.send_message(
            "??곸쓣 ??紐??댁긽 ?낅젰?댁＜?몄슂. ?? `@?좎?1 @?좎?2 @?좎?3`",
            ephemeral=True,
        )
        return

    success_members = []
    skipped_members = []

    for user_id in dict.fromkeys(raw_ids):
        member = interaction.guild.get_member(user_id)
        if member is None or member.bot:
            skipped_members.append(str(user_id))
            continue

        add_balance(member.id, amount)
        add_money_grant_log(interaction.guild.id, member.id, interaction.user.id, amount)
        success_members.append(member.mention)

    if not success_members:
        await interaction.response.send_message("吏湲?媛?ν븳 ?좎?媛 ?놁뒿?덈떎.", ephemeral=True)
        return

    lines = [
        f"珥?{len(success_members)}紐낆뿉寃?媛곴컖 `{format_money(amount)}`??吏湲됲뻽?듬땲??",
        f"??? {', '.join(success_members)}",
    ]

    if skipped_members:
        lines.append(f"?쒖쇅?? {', '.join(skipped_members)}")

    await interaction.response.send_message("\n".join(lines))




@bot.tree.command(name="돈삭제", description="서버 주인이 특정 유저의 재화를 차감합니다.")
async def remove_money(interaction: discord.Interaction, member: discord.Member, amount: int):
    if interaction.guild is None or interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("??紐낅졊?대뒗 ?쒕쾭 二쇱씤留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
        return

    if member.bot:
        await interaction.response.send_message("遊뉗쓽 ?덉? ??젣?????놁뒿?덈떎.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("李④컧 湲덉븸? 1???댁긽?댁뼱???⑸땲??", ephemeral=True)
        return

    current_balance = get_balance(member.id)
    deducted_amount = min(current_balance, amount)
    add_balance(member.id, -deducted_amount)

    await interaction.response.send_message(
        f"{member.mention}?섏뿉寃뚯꽌 `{format_money(deducted_amount)}`??李④컧?덉뒿?덈떎.\n"
        f"{member.mention}?섏쓽 ?꾩옱 ?붿븸: `{format_money(get_balance(member.id))}`"
    )


# ----------------------------
# 게임 명령어
# ----------------------------

@bot.tree.command(name="?щ’", description="?낅젰??湲덉븸?쇰줈 ?щ’癒몄떊???뚮┰?덈떎.")
async def slot(interaction: discord.Interaction, amount: int):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if amount < MIN_BET:
        await interaction.response.send_message(f"理쒖냼 諛고똿 湲덉븸? `{format_money(MIN_BET)}`?낅땲??", ephemeral=True)
        return
    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("?붿븸??遺議깊빀?덈떎.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)
    symbols = ["체리", "레몬", "포도", "사과", "클로버", "7"]

    first = random.choice(symbols)
    second = first if random.random() < 0.05 else random.choice(symbols)
    third = first if random.random() < 0.05 else random.choice(symbols)
    result = [first, second, third]

    multiplier = 0

    if len(set(result)) == 1:
        if result[0] == "7":
            multiplier = 12
        elif result[0] == "클로버":
            multiplier = 8
        else:
            multiplier = 6
    elif len(set(result)) == 2:
        counts = {symbol: result.count(symbol) for symbol in set(result)}
        pair_symbol = max(counts, key=counts.get)

        if counts[pair_symbol] == 2:
            if pair_symbol == "7":
                multiplier = 1.7
            elif pair_symbol == "클로버":
                multiplier = 1.4
            else:
                multiplier = 1.15


    

    winnings = int(amount * multiplier)
    if winnings > 0:
        add_balance(interaction.user.id, winnings)

    balance_now = get_balance(interaction.user.id)

    if multiplier == 0:
        desc = f"`{' | '.join(result)}`\n\n아쉽네요... `{format_money(amount)}`을 잃었습니다.\n현재 잔액: `{format_money(balance_now)}`"
        color = 0xE74C3C
    elif len(set(result)) == 1:
        desc = f"`{' | '.join(result)}`\n\n대박! `{multiplier}배` 당첨으로 `{format_money(winnings)}`을 획득했습니다.\n현재 잔액: `{format_money(balance_now)}`"
        color = 0x2ECC71
    else:
        desc = f"`{' | '.join(result)}`\n\n2개 일치! `{multiplier}배` 보상으로 `{format_money(winnings)}`을 획득했습니다.\n현재 잔액: `{format_money(balance_now)}`"
        color = 0x3498DB

    add_game_history(
        interaction.guild.id,
        "슬롯",
        f"{interaction.user.display_name} - {' | '.join(result)} - {('꽝' if multiplier == 0 else f'{multiplier}배')}"
    )

    embed = discord.Embed(title="🎰 슬롯 결과", description=desc, color=color)
    await interaction.response.send_message(embed=embed)



@bot.tree.command(name="?숈쟾", description="?낅젰??湲덉븸?쇰줈 ?숈쟾 ?욌뮘 留욎텛湲곕? ?⑸땲??")
async def coin(interaction: discord.Interaction, amount: int):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if amount < MIN_BET:
        await interaction.response.send_message(f"理쒖냼 諛고똿 湲덉븸? `{format_money(MIN_BET)}`?낅땲??", ephemeral=True)
        return
    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("?붿븸??遺議깊빀?덈떎.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)
    embed = discord.Embed(
        title="🪙 동전 던지기",
        description=(
            f"베팅 금액: `{format_money(amount)}`\n"
            "아래 버튼에서 `앞` 또는 `뒤`를 선택해주세요.\n"
            "승리 시 1.8배를 지급합니다.\n"
            f"{COIN_FLIP_TIMEOUT}초 안에 선택하지 않으면 자동 취소되고 돈이 반환됩니다."
        ),
        color=0xF1C40F,
    )
    await interaction.response.send_message(embed=embed, view=CoinFlipView(interaction.user.id, amount))


@bot.tree.command(name="룰렛", description="룰렛에 베팅하고 색상을 선택합니다.")
async def roulette(interaction: discord.Interaction, amount: int):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if amount < MIN_BET:
        await interaction.response.send_message(
            f"理쒖냼 諛고똿 湲덉븸? `{format_money(MIN_BET)}`?낅땲??",
            ephemeral=True,
        )
        return

    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("?붿븸??遺議깊빀?덈떎.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)

    embed = discord.Embed(
        title="🎡 룰렛",
        description=(
            f"베팅 금액: `{format_money(amount)}`\n\n"
            "색상을 선택해주세요.\n\n"
            "🟥 빨강: 승리 시 2.5배\n"
            "🟨 노랑: 승리 시 3.4배\n"
            "🟦 파랑: 승리 시 4.4배\n"
            "⬛ 검정: 승리 시 6.5배\n"
            "🟩 초록: 승리 시 9.5배\n\n"
            "빨강은 가장 안전하고,\n"
            "뒤로 갈수록 확률은 낮아지지만 배당은 높아집니다.\n"
        ),
        color=0xF1C40F,
    )

    await interaction.response.send_message(
        embed=embed,
        view=RouletteView(interaction.user.id, amount),
    )


@bot.tree.command(name="?명똿?湲곕갑異붽?", description="?湲곕갑 ?뚯꽦梨꾨꼸???깅줉?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def add_waiting_room_command(interaction: discord.Interaction, channel: discord.VoiceChannel):
    add_waiting_room(interaction.guild.id, channel.id)
    await interaction.response.send_message(
        f"{channel.mention} 梨꾨꼸???湲곕갑?쇰줈 ?깅줉?덉뒿?덈떎.",
        ephemeral=True,
    )


@bot.tree.command(name="?명똿?湲곕갑??젣", description="?깅줉???湲곕갑???쒓굅?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def remove_waiting_room_command(interaction: discord.Interaction, channel: discord.VoiceChannel):
    remove_waiting_room(interaction.guild.id, channel.id)
    await interaction.response.send_message(
        f"{channel.mention} 梨꾨꼸???湲곕갑?먯꽌 ?쒓굅?덉뒿?덈떎.",
        ephemeral=True,
    )


@bot.tree.command(name="?湲곕갑紐⑸줉", description="?꾩옱 ?깅줉???湲곕갑 紐⑸줉???뺤씤?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def list_waiting_rooms(interaction: discord.Interaction):
    room_ids = get_waiting_rooms(interaction.guild.id)
    if not room_ids:
        await interaction.response.send_message("?깅줉???湲곕갑???놁뒿?덈떎.", ephemeral=True)
        return

    lines = [f"<#{room_id}>" for room_id in room_ids]
    embed = discord.Embed(title="?깅줉???湲곕갑 紐⑸줉", description="\n".join(lines), color=0x3498DB)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="팀", description="랜덤 팀을 생성합니다.")
async def team(interaction: discord.Interaction):
    embed = discord.Embed(title="👥 팀 생성", description="팀 인원을 선택해주세요.", color=0x3498DB)
    await interaction.response.send_message(embed=embed, view=TeamSelectView())

@bot.tree.command(name="팀섞기규칙설정", description="관전자 제외용 접두어를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.rename(prefixes="접두어들")
@app_commands.describe(prefixes="쉼표로 구분해서 입력하세요. 예: 관전자,휴식중")
async def set_team_mix_rule(interaction: discord.Interaction, prefixes: str):
    prefix_list = [item.strip() for item in prefixes.split(",") if item.strip()]

    if not prefix_list:
        await interaction.response.send_message(
            "접두어를 하나 이상 입력해주세요. 예: `관전자,휴식중`",
            ephemeral=True,
        )
        return

    set_guild_setting(interaction.guild.id, "spectator_prefixes", ",".join(prefix_list))
    await interaction.response.send_message(
        f"팀섞기 관전자 접두어를 설정했습니다: {', '.join(f'[{p}]' for p in prefix_list)}",
        ephemeral=True,
    )

@bot.tree.command(name="팀섞기규칙확인", description="현재 관전자 제외 접두어를 확인합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def show_team_mix_rule(interaction: discord.Interaction):
    prefixes = get_spectator_prefixes(interaction.guild.id)
    await interaction.response.send_message(
        f"현재 관전자 접두어: {', '.join(f'[{p}]' for p in prefixes)}",
        ephemeral=True,
    )

@bot.tree.command(name="援ъ씤", description="諛곌렇 援ъ씤")
async def recruit(interaction: discord.Interaction, message: str):
    recruit_channel_id = get_guild_setting_channel_id(interaction.guild.id, "recruit_channel_id")
    if recruit_channel_id is None:
        await interaction.response.send_message("援ъ씤 梨꾨꼸???꾩쭅 ?ㅼ젙?섏? ?딆븯?듬땲??", ephemeral=True)
        return
    if interaction.channel.id != recruit_channel_id:
        await interaction.response.send_message("援ъ씤 梨꾨꼸?먯꽌留??ъ슜 媛?ν빀?덈떎.", ephemeral=True)
        return
    if not interaction.user.voice:
        await interaction.response.send_message("?뚯꽦梨꾨꼸 癒쇱? ?ㅼ뼱媛?몄슂.", ephemeral=True)
        return

    await create_recruit_post(
        interaction=interaction,
        text_channel=interaction.channel,
        voice_channel=interaction.user.voice.channel,
        host=interaction.user,
        game_name="PUBG",
        message_content=message,
        mention_here=True,
        max_players=MAX_PLAYERS,
    )


@bot.tree.command(name="醫낃쿇援ъ씤", description="?먰븯??寃뚯엫?쇰줈 援ъ씤 湲 ?묒꽦")
async def general_recruit(interaction: discord.Interaction):
    await interaction.response.send_modal(GeneralRecruitModal())


@bot.tree.command(name="蹂닿툒", description="諛곌렇 蹂닿툒?곸옄瑜??댁뼱 寃곌낵???곕씪 蹂댁긽??諛쏆뒿?덈떎.")
async def supply_drop(interaction: discord.Interaction, amount: int):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if amount < MIN_BET:
        await interaction.response.send_message(
            f"理쒖냼 諛고똿 湲덉븸? `{format_money(MIN_BET)}`?낅땲??",
            ephemeral=True,
        )
        return

    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("?붿븸??遺議깊빀?덈떎.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)

    embed = discord.Embed(
        title="?벀 蹂닿툒",
        description=(
            f"諛고똿 湲덉븸: `{format_money(amount)}`\n\n"
            "?덌툘 ?섎뒛?먯꽌 蹂닿툒???⑥뼱吏怨??덉뒿?덈떎...\n"
            "?벀 ?곸옄瑜??댁뼱 ?대뼡 ?꾩씠?쒖쓣 梨숆만 ???덉쓣吏 ?뺤씤?섏꽭??\n\n"
            "媛?ν븳 寃곌낵:\n"
            "?ワ툘 鍮??곸옄\n"
            "?ワ툘 1??n"
            "?ワ툘 2??n"
            "?ワ툘 3??n"
            "?ワ툘 蹂닿툒 珥앷린 ?띾뱷\n"
            "?ワ툘 ??명듃 蹂닿툒 ?諛?n\n"
            "踰꾪듉???뚮윭 蹂닿툒?곸옄瑜?媛쒕큺?섏꽭??"
        ),
        color=0xF39C12,
    )

    await interaction.response.send_message(
        embed=embed,
        view=SupplyDropView(interaction.user.id, amount),
    )

@bot.tree.command(name="臾몄쓽?⑤꼸", description="臾몄쓽/?좉퀬/嫄댁쓽 ?곗폆 ?⑤꼸???앹꽦?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def inquiry_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="臾몄쓽 ?덈궡",
        description="臾몄쓽?섍린 ?낅땲?? ?꾨옒 ??ぉ???좏깮??二쇱꽭??",
        color=0x3498DB,
    )
    await interaction.channel.send(embed=embed, view=InquiryPanelView())
    await interaction.response.send_message("臾몄쓽 ?⑤꼸 ?앹꽦 ?꾨즺", ephemeral=True)

@bot.tree.command(name="닉네임패널생성", description="닉네임 접두어 적용 패널을 생성합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def create_nickname_panel(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    menu_name: str,
    prefixes: str,
):
    prefix_list = [item.strip() for item in prefixes.split(",") if item.strip()]

    if not prefix_list:
        await interaction.response.send_message(
            "접두어를 하나 이상 입력해주세요. 예: `관전자,빨팀,파팀`",
            ephemeral=True,
        )
        return

    if len(prefix_list) > 24:
        await interaction.response.send_message(
            "접두어는 최대 24개까지만 설정할 수 있습니다.",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title=menu_name,
        description="원하는 접두어를 선택해주세요.",
        color=0x5865F2,
    )

    await interaction.response.send_message("닉네임 패널을 생성하는 중입니다.", ephemeral=True)

    panel_message = await channel.send(embed=embed)
    view = NicknamePrefixView(interaction.guild.id, channel.id, panel_message.id, prefix_list)
    await panel_message.edit(view=view)

    save_nickname_panel(
        interaction.guild.id,
        channel.id,
        panel_message.id,
        menu_name,
        prefix_list,
    )

@bot.tree.command(name="배당표", description="현재 게임들의 확률과 배당을 확인합니다.")
async def probability_table(interaction: discord.Interaction):
    embed = discord.Embed(title="🎰 게임 배당표", color=0x3498DB)

    embed.add_field(
        name="?щ’",
        value=(
            "3媛??숈씪: ??4.34%\n"
            "7截뤴깵 7截뤴깵 7截뤴깵 : ??0.72% / 12諛?n"
            "?뭿 ?뭿 ?뭿 : ??0.72% / 8諛?n"
            "湲고? 3媛??숈씪 : 媛곴컖 ??0.72% / 6諛?n\n"
            "?뺥솗??2媛??쇱튂: ??45.52%\n"
            "7截뤴깵 7截뤴깵 : ??7.59% / 1.7諛?n"
            "?뭿 ?뭿 : ??7.59% / 1.4諛?n"
            "湲고? 2媛??쇱튂 : 媛곴컖 ??7.59% / 1.15諛?n\n"
            "?꾩쟾 苑?: ??50.14%"
        ),
        inline=False,
    )


    embed.add_field(
        name="동전",
        value="앞/뒤 50% 확률\n승리 시 1.8배",
        inline=False,
    )

    embed.add_field(
        name="猷곕젢",
        value=(
            "빨강 35% / 2.5배\n"
            "노랑 25% / 3.4배\n"
            "파랑 19% / 4.4배\n"
            "검정 12% / 6.5배\n"
            "초록 9% / 9.5배"
        ),
        inline=False,
    )

    embed.add_field(
        name="蹂닿툒",
        value=(
            "빈 상자 38% / 0배\n"
            "1뚝 24% / 0.9배\n"
            "2뚝 17% / 1.0배\n"
            "3뚝 10% / 1.6배\n"
            "보급 총기 획득 8% / 2.8배\n"
            "풀세트 보급 대박 3% / 4.5배"
        ),
        inline=False,
    )

    embed.add_field(
        name="紐곕뭇寃뚯엫",
        value=(
            f"李멸?鍮?`{format_money(ALL_IN_COST)}`\n"
            "?섎（ ?숈븞 李멸????щ엺 以?1紐?臾댁옉??異붿꺼\n"
            "洹몃궇 李멸??먮뱾????湲덉븸 ?꾨?瑜??뱀꺼??1紐낆씠 媛?멸컩?덈떎."
        ),
        inline=False,
    )
  
    embed.add_field(
        name="?뺣そ",
        value=(
            "오리 33.33% / 2배 회수\n"
            "너리콘 33.33% / 원금 반환\n"
            "거위 33.33% / 전부 잃음"
        ),
        inline=False,
    )


    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="전적", description="최근 게임 결과를 확인합니다.")
async def game_history_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📜 전적",
        description="확인할 게임을 선택해주세요.",
        color=0x5865F2,
    )
    await interaction.response.send_message(
        embed=embed,
        view=HistoryGameSelectView(interaction.guild.id),
        ephemeral=True,
    )


@bot.tree.command(name="紐곕뭇李몄뿬", description="?ㅻ뒛??紐곕뭇寃뚯엫??李몄뿬?⑸땲??")
async def join_all_in_game(interaction: discord.Interaction):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if interaction.guild is None:
        await interaction.response.send_message("?쒕쾭?먯꽌留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
        return

    today = get_today_kst_date_str()

    if has_all_in_entry(today, interaction.guild.id, interaction.user.id):
        await interaction.response.send_message("?ㅻ뒛? ?대? 紐곕뭇寃뚯엫??李몄뿬?덉뒿?덈떎.", ephemeral=True)
        return

    if not can_afford(interaction.user.id, ALL_IN_COST):
        await interaction.response.send_message(
            f"紐곕뭇寃뚯엫 李멸?鍮?`{format_money(ALL_IN_COST)}`??遺議깊빀?덈떎.",
            ephemeral=True,
        )
        return

    add_balance(interaction.user.id, -ALL_IN_COST)
    add_all_in_entry(today, interaction.guild.id, interaction.user.id, ALL_IN_COST)

    entries = get_all_in_entries(today, interaction.guild.id)
    pool_amount = sum(amount for _, amount in entries)

    await interaction.response.send_message(
        f"{interaction.user.mention}?섏씠 ?ㅻ뒛??紐곕뭇寃뚯엫??李몄뿬?덉뒿?덈떎.\n"
        f"李멸?鍮? `{format_money(ALL_IN_COST)}`\n"
        f"?꾩옱 李멸????? `{len(entries)}紐?\n"
        f"?꾩옱 ?꾩쟻 ?곴툑: `{format_money(pool_amount)}`"
    )


@bot.tree.command(name="돈주기내역", description="특정 인원의 돈 지급 내역을 확인합니다.")
@app_commands.rename(member="인원")
@app_commands.describe(member="조회할 인원")
async def money_grant_history(interaction: discord.Interaction, member: discord.Member):
    rows = get_money_grant_logs(interaction.guild.id, member.id, 20)

    if not rows:
        await interaction.response.send_message("吏湲??댁뿭???놁뒿?덈떎.", ephemeral=True)
        return

    lines = []
    for giver_user_id, amount, created_at in rows:
        giver = interaction.guild.get_member(int(giver_user_id))
        giver_name = giver.display_name if giver else f"?????녿뒗 ?좎? ({giver_user_id})"
        try:
            created_text = dt_from_db(created_at).strftime("%Y-%m-%d %H:%M")
        except Exception:
            created_text = created_at
        lines.append(f"[{created_text}] {giver_name} -> {format_money(amount)}")

    embed = discord.Embed(
        title=f"?뮯 {member.display_name}?섏쓽 ?덉?湲??댁뿭",
        description="\n".join(lines),
        color=0xF1C40F,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ----------------------------
# 신용 / 대출 명령어
# ----------------------------

@bot.tree.command(name="대출", description="현재 신용등급 기준으로 대출을 받습니다.")
@app_commands.rename(amount="금액")
async def loan_money(interaction: discord.Interaction, amount: int):
    if interaction.guild is None:
        await interaction.response.send_message("?쒕쾭?먯꽌留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("?異?湲덉븸? 1???댁긽?댁뼱???⑸땲??", ephemeral=True)
        return

    profile = get_credit_profile(interaction.user.id)
    active_loan = get_active_loan(interaction.user.id)

    if active_loan is not None:
        await interaction.response.send_message(
            "?대? ?곹솚?섏? ?딆? ?異쒖씠 ?덉뒿?덈떎. `/以묐룄?곹솚`?쇰줈 癒쇱? 媛싳븘二쇱꽭??",
            ephemeral=True,
        )
        return

    if profile["is_blacklisted"]:
        await interaction.response.send_message(
            "?꾩옱 ?좎슜遺덈웾???곹깭?낅땲?? 湲곗〈 ?異쒖쓣 紐⑤몢 ?곹솚?섍린 ?꾧퉴吏 ???異쒖씠 遺덇??ν빀?덈떎.",
            ephemeral=True,
        )
        return

    grade = profile["grade"]
    max_amount = get_loan_limit_by_grade(grade)
    interest_rate = get_loan_interest_by_grade(grade)

    if amount > max_amount:
        await interaction.response.send_message(
            f"?꾩옱 {grade}?깃툒??理쒕? ?異?媛??湲덉븸? `{format_money(max_amount)}`?낅땲??",
            ephemeral=True,
        )
        return

    borrowed_at = get_kst_now()
    due_at = borrowed_at + timedelta(days=LOAN_REPAYMENT_DAYS)
    total_repayment = calculate_total_repayment(amount, interest_rate)

    add_balance(interaction.user.id, amount)
    create_loan(
        interaction.guild.id,
        interaction.user.id,
        amount,
        interest_rate,
        total_repayment,
        borrowed_at,
        due_at,
    )

    embed = discord.Embed(title="💳 대출 실행 완료", color=0x3498DB)
    embed.add_field(name="현재 신용등급", value=f"{grade}등급", inline=False)
    embed.add_field(name="대출 금액", value=format_money(amount), inline=False)
    embed.add_field(name="이자율", value=f"{interest_rate}%", inline=False)
    embed.add_field(name="총 상환 금액", value=format_money(total_repayment), inline=False)
    embed.add_field(name="상환 기한", value=due_at.strftime("%Y-%m-%d %H:%M:%S KST"), inline=False)
    embed.add_field(name="현재 잔액", value=format_money(get_balance(interaction.user.id)), inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="중도상환", description="현재 대출을 즉시 전액 상환합니다.")
async def repay_loan_command(interaction: discord.Interaction):
    active_loan = get_active_loan(interaction.user.id)
    if active_loan is None:
        await interaction.response.send_message("?꾩옱 ?곹솚???異쒖씠 ?놁뒿?덈떎.", ephemeral=True)
        return

    repayment_amount = active_loan["total_repayment"]
    if not can_afford(interaction.user.id, repayment_amount):
        await interaction.response.send_message(
            f"?곹솚 湲덉븸 `{format_money(repayment_amount)}`??遺議깊빀?덈떎.",
            ephemeral=True,
        )
        return

    profile = get_credit_profile(interaction.user.id)
    previous_grade_text = get_credit_grade_text(interaction.user.id)

    add_balance(interaction.user.id, -repayment_amount)
    repay_loan(active_loan["id"])

    grade_up = False

    if profile["is_blacklisted"]:
        set_credit_blacklisted(interaction.user.id, False)
        set_credit_grade(interaction.user.id, 6)
        if interaction.guild is not None:
            delete_labor_penalty(interaction.guild.id, interaction.user.id)
        grade_up = True
    else:
        required_amount = get_loan_limit_by_grade(profile["grade"])
        if active_loan["principal"] >= required_amount:
            upgrade_credit_grade(interaction.user.id)
            grade_up = True

    current_grade_text = get_credit_grade_text(interaction.user.id)

    embed = discord.Embed(title="✅ 대출 상환 완료", color=0x2ECC71)
    embed.add_field(name="상환 금액", value=format_money(repayment_amount), inline=False)
    embed.add_field(name="상환 전 신용등급", value=previous_grade_text, inline=False)
    embed.add_field(name="현재 신용등급", value=current_grade_text, inline=False)
    embed.add_field(name="현재 잔액", value=format_money(get_balance(interaction.user.id)), inline=False)

    if profile["is_blacklisted"]:
        embed.add_field(
            name="등급 변화",
            value="기존 대출을 모두 상환하여 신용불량자 상태가 해제되고 6등급으로 복귀했습니다.",
            inline=False,
        )
    elif grade_up:
        embed.add_field(
            name="등급 변화",
            value="현재 등급의 최대 한도 이상 대출을 정상 상환하여 신용등급이 1단계 상승했습니다.",
            inline=False,
        )
    else:
        required_amount = get_loan_limit_by_grade(profile["grade"])
        embed.add_field(
            name="등급 변화",
            value=(
                "대출은 정상 상환했지만 신용등급은 유지되었습니다.\n"
                f"등급 상승을 위해서는 현재 등급 기준 최대 한도인 `{format_money(required_amount)}` 이상 대출을 상환해야 합니다."
            ),
            inline=False,
        )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="내신용", description="현재 신용등급과 대출 상태를 확인합니다.")
async def my_credit(interaction: discord.Interaction):
    profile = get_credit_profile(interaction.user.id)
    active_loan = get_active_loan(interaction.user.id)
    labor_penalty = ensure_active_labor_penalty(interaction.guild.id, interaction.user.id) if interaction.guild else None

    if profile["is_blacklisted"]:
        grade_text = "신용불량자"
        max_amount_text = "대출 불가"
        interest_text = "대출 불가"
    else:
        grade_text = f"{profile['grade']}등급"
        max_amount_text = format_money(get_loan_limit_by_grade(profile["grade"]))
        interest_text = f"{get_loan_interest_by_grade(profile['grade'])}%"

    embed = discord.Embed(title="📋 내 신용 정보", color=0x5865F2)
    embed.add_field(name="현재 신용등급", value=grade_text, inline=False)
    embed.add_field(name="최대 대출 가능 금액", value=max_amount_text, inline=False)
    embed.add_field(name="현재 대출 이자율", value=interest_text, inline=False)

    if active_loan is None:
        embed.add_field(name="현재 대출 상태", value="진행 중인 대출 없음", inline=False)
    else:
        embed.add_field(name="현재 대출 상태", value=active_loan["status"], inline=False)
        embed.add_field(name="대출 원금", value=format_money(active_loan["principal"]), inline=False)
        embed.add_field(name="총 상환 금액", value=format_money(active_loan["total_repayment"]), inline=False)
        try:
            due_text = dt_from_db(active_loan["due_at"]).strftime("%Y-%m-%d %H:%M:%S KST")
        except Exception:
            due_text = active_loan["due_at"]
        embed.add_field(name="상환 기한", value=due_text, inline=False)

    if labor_penalty is not None:
        remaining = max(0, labor_penalty["required_count"] - labor_penalty["completed_count"])
        embed.add_field(
            name="노동 진행 현황",
            value=(
                f"완료: `{labor_penalty['completed_count']}회`\n"
                f"필요: `{labor_penalty['required_count']}회`\n"
                f"남은 횟수: `{remaining}회`"
            ),
            inline=False,
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="노동", description="신용불량자 상태일 때 노동을 진행합니다.")
async def labor(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("?쒕쾭?먯꽌留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
        return

    profile = get_credit_profile(interaction.user.id)
    if not profile["is_blacklisted"]:
        await interaction.response.send_message("?꾩옱 ?좎슜遺덈웾???곹깭媛 ?꾨떃?덈떎.", ephemeral=True)
        return

    penalty = ensure_active_labor_penalty(interaction.guild.id, interaction.user.id)
    if penalty is None:
        await interaction.response.send_message("吏꾪뻾 以묒씤 ?몃룞 ?⑤꼸???뺣낫媛 ?놁뒿?덈떎. 愿由ъ옄?먭쾶 臾몄쓽?댁＜?몄슂.", ephemeral=True)
        return

    embed = build_labor_embed(interaction.user, penalty)
    await interaction.response.send_message(
        embed=embed,
        view=LaborWorkView(interaction.guild.id, interaction.user.id),
    )


@bot.tree.command(name="노동현황", description="현재 노동 진행 현황을 확인합니다.")
async def labor_status(interaction: discord.Interaction, member: discord.Member | None = None):
    if interaction.guild is None:
        await interaction.response.send_message("?쒕쾭?먯꽌留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
        return

    target = member or interaction.user
    penalty = ensure_active_labor_penalty(interaction.guild.id, target.id)
    if penalty is None:
        await interaction.response.send_message("吏꾪뻾 以묒씤 ?몃룞 ?⑤꼸?곌? ?놁뒿?덈떎.", ephemeral=True)
        return

    embed = build_labor_embed(target, penalty)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="?뺣そ", description="?뺣そ?댁뒪 ?뚮쭏???ㅻ━瑜?李얠븘??寃뚯엫?낅땲??")
async def duckmong(interaction: discord.Interaction, amount: int):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if amount < MIN_BET:
        await interaction.response.send_message(
            f"理쒖냼 諛고똿 湲덉븸? `{format_money(MIN_BET)}`?낅땲??",
            ephemeral=True,
        )
        return

    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("?붿븸??遺議깊빀?덈떎.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)

    fake_names = random.sample(DUCKMONG_FAKE_NAMES, 3)
    hidden_roles = ["오리", "거위", "너리콘"]
    random.shuffle(hidden_roles)
    hidden_results = {fake_name: hidden_roles[idx] for idx, fake_name in enumerate(fake_names)}

    embed = discord.Embed(
        title="🦆 오리를 찾아라",
        description=(
            f"베팅 금액: `{format_money(amount)}`\n\n"
            "세 직업 중 하나를 골라주세요.\n"
            "그 안에는 오리, 거위, 너리콘이 하나씩 숨어 있습니다.\n\n"
            "오리: 베팅금액만큼 추가 획득\n"
            "거위: 전부 잃음\n"
            "너리콘: 원금 반환"
        ),
        color=0xF1C40F,
    )

    await interaction.response.send_message(
        embed=embed,
        view=DuckmongView(interaction.user.id, amount, fake_names, hidden_results),
    )

# ----------------------------
# 무기 강화 명령어
# ----------------------------

@bot.tree.command(name="媛뺥솕", description="?꾩옱 臾닿린??媛뺥솕 ?뺣낫? 媛뺥솕 踰꾪듉???뺤씤?⑸땲??")
async def upgrade_weapon(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("?쒕쾭?먯꽌留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
        return

    ensure_base_weapon(interaction.guild.id, interaction.user.id)

    embed = build_upgrade_embed(interaction.guild.id, interaction.user.id)
    view = WeaponUpgradeView(interaction.guild.id, interaction.user.id)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="臾닿린?먮ℓ", description="?꾩옱 蹂댁쑀 以묒씤 臾닿린瑜??먮ℓ?⑸땲??")
async def sell_weapon(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("?쒕쾭?먯꽌留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
        return

    inventory = get_weapon_inventory(interaction.guild.id, interaction.user.id)
    current_level = inventory["weapon_level"]

    if current_level <= 0:
        await interaction.response.send_message("?먮ℓ??臾닿린媛 ?놁뒿?덈떎.", ephemeral=True)
        return

    weapon_name = get_weapon_name(current_level)
    sell_price = get_weapon_sell_price(current_level)

    add_balance(interaction.user.id, sell_price)
    reset_weapon_progress(interaction.guild.id, interaction.user.id)

    embed = discord.Embed(title="?뮥 臾닿린 ?먮ℓ ?꾨즺", color=0x2ECC71)
    embed.add_field(name="?먮ℓ 臾닿린", value=f"{current_level}媛?{weapon_name}", inline=False)
    embed.add_field(name="?먮ℓ 湲덉븸", value=format_money(sell_price), inline=False)
    embed.add_field(name="?꾩옱 ?붿븸", value=format_money(get_balance(interaction.user.id)), inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="媛뺥솕?꾪솴", description="?꾩옱 蹂댁쑀 以묒씤 臾닿린? 蹂댄샇沅??섎웾???뺤씤?⑸땲??")
async def weapon_status(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("?쒕쾭?먯꽌留??ъ슜?????덉뒿?덈떎.", ephemeral=True)
        return

    inventory = get_weapon_inventory(interaction.guild.id, interaction.user.id)
    current_level = inventory["weapon_level"]

    total_upgrade_spent = inventory["total_upgrade_spent"]
    total_protection_spent = inventory["total_protection_spent"]
    total_invested = total_upgrade_spent + total_protection_spent

    embed = discord.Embed(title="🔧 강화 현황", color=0x5865F2)

    if current_level <= 0:
        embed.add_field(name="현재 무기", value="없음", inline=False)
        embed.add_field(name="안내", value="`/강화`를 사용하면 1강 프라이팬부터 자동 지급됩니다.", inline=False)
    else:
        embed.add_field(name="현재 무기", value=f"{current_level}강 {get_weapon_name(current_level)}", inline=False)
        embed.add_field(name="판매 가격", value=format_money(get_weapon_sell_price(current_level)), inline=False)

        if current_level < 21:
            embed.add_field(name="?ㅼ쓬 媛뺥솕 鍮꾩슜", value=format_money(get_upgrade_cost(current_level)), inline=False)
        else:
            embed.add_field(name="媛뺥솕 ?곹깭", value="理쒕? 媛뺥솕 ?④퀎", inline=False)

    embed.add_field(
        name="보유 보호권",
        value=(
            f"저강 보호권 `{inventory['low_protection_count']}개`\n"
            f"중강 보호권 `{inventory['mid_protection_count']}개`\n"
            f"고강 보호권 `{inventory['high_protection_count']}개`"
        ),
        inline=False,
    )

    embed.add_field(
        name="누적 투자",
        value=(
            f"강화 투자: `{format_money(total_upgrade_spent)}`\n"
            f"보호권 투자: `{format_money(total_protection_spent)}`\n"
            f"총 투자: `{format_money(total_invested)}`"
        ),
        inline=False,
    )

    embed.add_field(name="?꾩옱 ?붿븸", value=format_money(get_balance(interaction.user.id)), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="媛뺥솕?뺣낫", description="1媛뺣???21媛뺢퉴吏 媛뺥솕 鍮꾩슜, ?뺣쪧, 蹂댄샇沅?媛寃? ?먮ℓ 媛寃⑹쓣 ?뺤씤?⑸땲??")
async def weapon_info_table(interaction: discord.Interaction):
    ranges = [
        (1, 7, "?뵩 媛뺥솕 ?뺣낫??(1媛?7媛?", 0x3498DB),
        (8, 14, "?뵩 媛뺥솕 ?뺣낫??(8媛?14媛?", 0x5865F2),
        (15, 21, "?뵩 媛뺥솕 ?뺣낫??(15媛?21媛?", 0x9B59B6),
    ]

    embeds = []

    for start, end, title, color in ranges:
        embed = discord.Embed(title=title, color=color)
        lines = []

        for level in range(start, end + 1):
            weapon_name = get_weapon_name(level)
            tier = get_protection_tier(level)
            protection_cost = get_protection_cost_by_tier(tier)
            sell_price = WEAPON_SELL_PRICES.get(level, 0)

            if level <= 20:
                cost = WEAPON_UPGRADE_COSTS.get(level)
                rates = WEAPON_UPGRADE_RATES.get(level)

                if cost is None or rates is None:
                    continue

                lines.append(
                    f"**{level}媛?{weapon_name}**\n"
                    f"媛뺥솕鍮꾩슜: `{format_money(cost)}`\n"
                    f"?깃났 {rates['success']}% / ?섎씫 {rates['down']}% / ?뚭눼 {rates['destroy']}% / ?좎? {rates['keep']}%\n"
                    f"蹂댄샇沅? `{format_money(protection_cost)}`\n"
                    f"?먮ℓ媛寃? `{format_money(sell_price)}`"
                )
            else:
                lines.append(
                    f"**{level}媛?{weapon_name}**\n"
                    f"理쒕? 媛뺥솕 ?④퀎\n"
                    f"蹂댄샇沅? `{format_money(protection_cost)}`\n"
                    f"?먮ℓ媛寃? `{format_money(sell_price)}`"
                )

        embed.description = "\n\n".join(lines)
        embeds.append(embed)

    await interaction.response.send_message(embeds=embeds, ephemeral=True)


@bot.tree.command(name="도박명령어", description="도박 및 재화 시스템 관련 명령어를 확인합니다.")
async def gambling_commands(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎲 도박 / 재화 시스템 명령어",
        description=(
            "재화, 대출, 적금, 강화, 도박 명령어를 한 번에 확인할 수 있습니다.\n"
            "신용불량자 상태에서는 일부 도박 명령어 사용이 제한됩니다."
        ),
        color=0xF1C40F,
    )

    embed.add_field(
        name="재화 관리",
        value=(
            "`/생활지원금` - 하루 1회 지원금 받기\n"
            "`/잔액` - 현재 잔액 확인\n"
            "`/재산` - 서버 재산 순위 확인\n"
            "`/송금` - 다른 유저에게 돈 보내기"
        ),
        inline=False,
    )

    embed.add_field(
        name="적금",
        value=(
            "`/적금 [금액]` - 적금 가입\n"
            "`/내적금` - 현재 적금 확인\n"
            "`/적금수령` - 만기 적금 수령"
        ),
        inline=False,
    )

    embed.add_field(
        name="대출 / 신용",
        value=(
            "`/대출 [금액]` - 현재 신용등급 기준 대출\n"
            "`/중도상환` - 현재 대출 전액 상환\n"
            "`/내신용` - 신용등급, 대출, 노동 현황 확인\n"
            "`/노동` - 신용불량자 노동 진행\n"
            "`/노동현황` - 노동 진행 상황 확인"
        ),
        inline=False,
    )

    embed.add_field(
        name="도박 / 게임",
        value=(
            "`/슬롯 [금액]` - 슬롯머신\n"
            "`/동전 [금액]` - 동전 앞뒤 맞추기\n"
            "`/룰렛 [금액]` - 색상 선택 룰렛\n"
            "`/보급 [금액]` - 보급 상자 게임\n"
            "`/덕몽 [금액]` - 오리를 찾아라\n"
            "`/몰빵참여` - 주간 몰빵게임 참여"
        ),
        inline=False,
    )

    embed.add_field(
        name="강화 시스템",
        value=(
            "`/강화` - 무기 강화 창 열기\n"
            "`/강화현황` - 현재 무기, 보호권, 투자 확인\n"
            "`/강화정보` - 단계별 비용과 확률 확인\n"
            "`/무기판매` - 현재 무기 판매"
        ),
        inline=False,
    )

    embed.add_field(
        name="참고 정보",
        value=(
            "`/배당표` - 게임 확률과 배당 확인\n"
            "`/전적` - 최근 게임 결과 확인\n"
            "`/관리자명령어` - 관리자/일반 명령어 전체 목록"
        ),
        inline=False,
    )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="관리자명령어", description="관리자 명령어와 일반 명령어를 카테고리별로 확인합니다.")
async def admin_commands_guide(interaction: discord.Interaction):
    admin_embed = discord.Embed(
        title="🛠 [관리자명령어]",
        description=(
            "서버 운영에 필요한 관리자 전용 명령어를 한눈에 볼 수 있도록 정리했습니다.\n"
            "카테고리별로 필요한 명령어를 빠르게 찾아보세요."
        ),
        color=0xE74C3C,
    )
    admin_embed.add_field(
        name="📌 채널 / 역할 설정",
        value=(
            "`/세팅생일알림`, `/세팅등업로그`, `/세팅퇴장로그`, `/세팅규칙로그`\n"
            "`/세팅구인채널`, `/세팅몰빵결과채널`, `/세팅가이드안내`, `/세팅환영메시지채널`\n"
            "`/세팅규칙역할`, `/세팅신입역할`, `/세팅생일역할`\n"
            "`/세팅클랜등업역할`, `/세팅게스트등업역할`, `/세팅시간대역할`"
        ),
        inline=False,
    )
    admin_embed.add_field(
        name="📝 문구 / 패널 설정",
        value=(
            "`/세팅환영dm`, `/세팅규칙안내문`, `/세팅등업패널문구`\n"
            "`/세팅신입알림문구`, `/세팅신입경과일`, `/적금세팅`\n"
            "`/문구설정확인`, `/설정확인`, `/역할설정확인`"
        ),
        inline=False,
    )
    admin_embed.add_field(
        name="🎛 메시지 / 패널 생성",
        value=(
            "`/규칙버튼`, `/등업패널`, `/시간설정패널`, `/문의패널`\n"
            "`/고정메시지`, `/고정해제`, `/고정확인`, `/내전공지`"
        ),
        inline=False,
    )
    admin_embed.add_field(
        name="🎉 환영 / 문의 / 대기방 관리",
        value=(
            "`/환영메시지`, `/환영메시지삭제`, `/환영메시지목록`\n"
            "`/세팅대기방추가`, `/세팅대기방삭제`, `/대기방목록`\n"
            "`/팀섞기규칙설정`, `/팀섞기규칙확인`, `/닉네임패널생성`"
        ),
        inline=False,
    )
    admin_embed.add_field(
        name="💰 경제 / 신용 관리",
        value=(
            "`/돈주기`, `/돈주기내역`, `/돈삭제`\n"
            "`/신용불량자등록`, `/신용불량자목록`, `/신용불량자삭제`, `/신용초기화`"
        ),
        inline=False,
    )
    admin_embed.add_field(
        name="✨ 자주 쓰는 예시",
        value=(
            "`/세팅등업패널문구`  여러 줄 패널 문구 설정\n"
            "`/신용불량자등록 @유저`  해당 유저 등록\n"
            "`/돈주기 @유저 10000`  특정 유저에게 재화 지급"
        ),
        inline=False,
    )
    admin_embed.set_footer(text="관리자 권한이 필요한 명령어만 모아두었습니다.")

    general_embed = discord.Embed(
        title="📚 [일반명령어]",
        description=(
            "일반 유저가 자주 사용하는 명령어를 분야별로 정리했습니다.\n"
            "경제, 게임, 생활 기능을 빠르게 찾아 사용할 수 있습니다."
        ),
        color=0x3498DB,
    )
    general_embed.add_field(
        name="🏠 기본 / 정보",
        value=(
            "`/생활지원금`, `/잔액`, `/재산`, `/송금`\n"
            "`/도박명령어`, `/배당표`, `/전적`, `/관리자명령어`"
        ),
        inline=False,
    )
    general_embed.add_field(
        name="🏦 적금 / 대출 / 신용",
        value=(
            "`/적금`, `/내적금`, `/적금수령`\n"
            "`/대출`, `/중도상환`, `/내신용`, `/노동`, `/노동현황`"
        ),
        inline=False,
    )
    general_embed.add_field(
        name="🎮 도박 / 게임",
        value=(
            "`/슬롯`, `/동전`, `/룰렛`, `/보급`, `/덕몽`\n"
            "`/몰빵참여`, `/강화`, `/무기판매`, `/강화현황`, `/강화정보`"
        ),
        inline=False,
    )
    general_embed.add_field(
        name="🎂 생일 / 인증 / 문의",
        value=(
            "`/생일등록`, `/생일삭제`, `/생일목록`\n"
            "`/문의패널`, `/문의하기`, `/신고하기`, `/건의하기`"
        ),
        inline=False,
    )
    general_embed.add_field(
        name="👥 구인 / 팀 / 기타",
        value=(
            "`/구인`, `/종겜구인`, `/팀`, `/시간설정패널`\n"
            "`/등업패널`, `/규칙버튼`, `/닉네임패널생성`"
        ),
        inline=False,
    )
    general_embed.add_field(
        name="✨ 자주 쓰는 예시",
        value=(
            "`/적금 50000`  5만원 적금\n"
            "`/보급 10000`  1만원 보급 참여\n"
            "`/내신용`  대출, 신용등급, 노동 현황 확인"
        ),
        inline=False,
    )
    general_embed.set_footer(text="일반 유저가 자주 쓰는 명령어만 모아두었습니다.")

    await interaction.response.send_message(embeds=[admin_embed, general_embed], ephemeral=True)

@bot.tree.command(name="?댁쟾怨듭?", description="李몄뿬 踰꾪듉???덈뒗 ?댁쟾 怨듭?瑜??묒꽦?⑸땲??")
@app_commands.checks.has_permissions(administrator=True)
async def scrim_notice(interaction: discord.Interaction):
    await interaction.response.send_modal(ScrimNoticeModal())

# ----------------------------
# ----------------------------
# 관리자 신용 관리 명령어
# ----------------------------

@bot.tree.command(name="신용불량자등록", description="특정 인원을 신용불량자로 등록합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def blacklist_user(interaction: discord.Interaction, member: discord.Member):
    set_credit_grade(member.id, 6)
    set_credit_blacklisted(member.id, True)
    active_loan = get_active_loan(member.id)
    debt_amount = active_loan["total_repayment"] if active_loan else DEFAULT_LABOR_DEBT_AMOUNT
    create_or_replace_labor_penalty(interaction.guild.id, member.id, debt_amount)

    await interaction.response.send_message(
        f"{member.mention}님을 신용불량자로 등록했습니다.\n필요 노동 횟수: `{calculate_labor_required_count(debt_amount)}회`",
        ephemeral=True,
    )

@bot.tree.command(name="신용불량자목록", description="현재 등록된 신용불량자 목록을 확인합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def blacklist_list(interaction: discord.Interaction):
    rows = get_blacklisted_profiles()

    if not rows:
        await interaction.response.send_message("현재 등록된 신용불량자가 없습니다.", ephemeral=True)
        return

    lines = []
    for user_id, grade, blacklisted_at in rows:
        member = interaction.guild.get_member(int(user_id)) if interaction.guild else None
        name = member.display_name if member else f"알 수 없는 유저 ({user_id})"

        if blacklisted_at:
            try:
                blacklisted_text = dt_from_db(blacklisted_at).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                blacklisted_text = blacklisted_at
        else:
            blacklisted_text = "기록 없음"

        lines.append(
            f"**{name}**\n"
            f"등록일: `{blacklisted_text}`\n"
            f"신용등급: `{grade}등급 (신용불량자)`"
        )

    embed = discord.Embed(
        title="📋 신용불량자 목록",
        description="\n\n".join(lines),
        color=0xE74C3C,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="신용불량자삭제", description="오등록된 인원을 신용불량자 목록에서 제거합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def remove_blacklist(interaction: discord.Interaction, member: discord.Member):
    set_credit_blacklisted(member.id, False)
    delete_labor_penalty(interaction.guild.id, member.id)

    await interaction.response.send_message(
        f"{member.mention}님의 신용불량자 등록을 해제했습니다.\n신용등급은 변경하지 않습니다.",
        ephemeral=True,
    )


@bot.tree.command(name="신용초기화", description="특정 인원의 신용불량자 상태를 해제하고 원하는 등급으로 조정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def reset_credit(interaction: discord.Interaction, member: discord.Member, grade: int):
    if grade < 1 or grade > 6:
        await interaction.response.send_message("등급은 1등급부터 6등급까지만 가능합니다.", ephemeral=True)
        return

    set_credit_blacklisted(member.id, False)
    set_credit_grade(member.id, grade)
    delete_labor_penalty(interaction.guild.id, member.id)

    await interaction.response.send_message(
        f"{member.mention}님의 신용을 `{grade}등급`으로 초기화했습니다.",
        ephemeral=True,
    )



# ============================================================
# 디스코드 이벤트
# ============================================================

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    guild_id = after.guild.id
    before_role_ids = {role.id for role in before.roles}
    after_role_ids = {role.id for role in after.roles}

    new_member_role_id = get_guild_setting_role_id(guild_id, "new_member_role_id")
    if new_member_role_id is not None:
        if new_member_role_id not in before_role_ids and new_member_role_id in after_role_ids:
            cursor.execute(
                """
                INSERT OR REPLACE INTO probation_roles(guild_id, user_id, assigned_at, notified)
                VALUES (?, ?, ?, 0)
                """,
                (str(guild_id), str(after.id), dt_to_db(get_kst_now())),
            )
            conn.commit()

        if new_member_role_id in before_role_ids and new_member_role_id not in after_role_ids:
            cursor.execute(
                "DELETE FROM probation_roles WHERE guild_id=? AND user_id=?",
                (str(guild_id), str(after.id)),
            )
            conn.commit()

    added_role_ids = after_role_ids - before_role_ids
    if added_role_ids:
        welcome_message_channel_id = get_guild_setting_channel_id(guild_id, "welcome_message_channel_id")
        if welcome_message_channel_id is not None:
            welcome_channel = after.guild.get_channel(welcome_message_channel_id)
            if welcome_channel is not None:
                for role_id in added_role_ids:
                    content = get_welcome_message(guild_id, role_id)
                    if not content:
                        continue

                    role = after.guild.get_role(role_id)
                    rendered = content.replace("{user}", after.mention)
                    rendered = rendered.replace("{role}", role.mention if role else "??븷")
                    await welcome_channel.send(rendered)


@bot.event
async def on_member_remove(member: discord.Member):
    leave_log_channel_id = get_guild_setting_channel_id(member.guild.id, "leave_log_channel_id")
    if leave_log_channel_id is None:
        return

    channel = bot.get_channel(leave_log_channel_id)
    if channel is None:
        return

    embed = discord.Embed(title="📤 서버 퇴장", color=0xE74C3C, timestamp=get_kst_now())
    embed.add_field(name="닉네임", value=member.display_name, inline=False)
    embed.add_field(name="계정명", value=str(member), inline=False)
    embed.add_field(name="유저 ID", value=str(member.id), inline=False)
    await channel.send(embed=embed)


@bot.event
async def on_voice_state_update(member, before, after):
    channels = []

    if after.channel and (before.channel is None or before.channel.id != after.channel.id):
        if is_waiting_room(member.guild.id, after.channel.id):
            recruit_channel_id = get_guild_setting_channel_id(member.guild.id, "recruit_channel_id")
            if recruit_channel_id is not None:
                recruit_channel = member.guild.get_channel(recruit_channel_id)
                if recruit_channel is not None:
                    await recruit_channel.send(
                        content=f"@here {member.mention}님이 대기방 {after.channel.mention}에 들어왔습니다."
                    )


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
            view = RecruitView(channel, member, data["game_name"], data["message_content"], max_players=data.get("max_players"))
            view.message = msg
            await view.auto_close()
            continue

        view = RecruitView(channel, host_member, data["game_name"], data["message_content"], max_players=data.get("max_players"))
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

    sticky = get_sticky_message(message.guild.id, message.channel.id)
    if sticky:
        if sticky.get("message_id") and message.id == sticky["message_id"]:
            await bot.process_commands(message)
            return
        try:
            await refresh_sticky_message(message.channel)
        except Exception:
            pass

    await bot.process_commands(message)


# ============================================================
# 백그라운드 작업
# ============================================================

@tasks.loop(hours=1)
async def probation_role_check_loop():
    now = get_kst_now()

    for guild in bot.guilds:
        rule_log_channel_id = get_guild_setting_channel_id(guild.id, "rule_log_channel_id")
        new_member_role_id = get_guild_setting_role_id(guild.id, "new_member_role_id")
        if rule_log_channel_id is None or new_member_role_id is None:
            continue

        channel = bot.get_channel(rule_log_channel_id)
        probation_role = guild.get_role(new_member_role_id)
        if channel is None or probation_role is None:
            continue

        notice_text = get_template_with_default(guild.id, "probation_notice_text", DEFAULT_PROBATION_NOTICE_TEXT)
        probation_days = int(get_setting_with_default(guild.id, "probation_days", DEFAULT_PROBATION_DAYS))
        due_time = now - timedelta(days=probation_days)

        cursor.execute(
            "SELECT user_id, assigned_at FROM probation_roles WHERE guild_id=? AND notified=0",
            (str(guild.id),),
        )
        rows = cursor.fetchall()

        for user_id, assigned_at_raw in rows:
            assigned_at = dt_from_db(assigned_at_raw)
            if assigned_at > due_time:
                continue

            member = guild.get_member(int(user_id))
            if member is None or probation_role not in member.roles:
                cursor.execute(
                    "DELETE FROM probation_roles WHERE guild_id=? AND user_id=?",
                    (str(guild.id), user_id),
                )
                conn.commit()
                continue

            joined_text = "기록 없음"
            if member.joined_at is not None:
                joined_text = member.joined_at.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S KST")

            embed = discord.Embed(
                title=f"🔔 신입 역할 {probation_days}일 경과 알림",
                description=notice_text,
                color=0xF1C40F,
                timestamp=now,
            )
            embed.add_field(name="닉네임", value=member.display_name, inline=False)
            embed.add_field(name="계정명", value=str(member), inline=False)
            embed.add_field(name="유저 ID", value=str(member.id), inline=False)
            embed.add_field(name="서버 입장일", value=joined_text, inline=False)
            embed.add_field(name="신입 역할 부여 시각", value=assigned_at.strftime("%Y-%m-%d %H:%M:%S KST"), inline=False)

            await channel.send(content=member.mention, embed=embed)
            cursor.execute(
                "UPDATE probation_roles SET notified=1 WHERE guild_id=? AND user_id=?",
                (str(guild.id), user_id),
            )
            conn.commit()


@tasks.loop(minutes=1)
async def birthday_loop():
    now = get_kst_now()
    today_str = now.strftime("%m-%d")
    yesterday_str = (now - timedelta(days=1)).strftime("%m-%d")

    for guild in bot.guilds:
        if now.strftime("%H:%M") == "00:00":
            birthday_channel_id = get_guild_setting_channel_id(guild.id, "birthday_channel_id")
            if birthday_channel_id is not None:
                channel = bot.get_channel(birthday_channel_id)
                if channel is not None:
                    cursor.execute("SELECT user_id FROM birthdays WHERE date=?", (today_str,))
                    for (uid,) in cursor.fetchall():
                        member = guild.get_member(int(uid))
                        if not member:
                            continue

                        embed = discord.Embed(
                            title="?럟 ?ㅻ뒛??二쇱씤怨??깆옣!",
                            description=f"?ㅻ뒛? {member.mention}?섏쓽 ?앹씪?낅땲?? 異뺥븯?댁＜?몄슂!",
                            color=0xFF69B4,
                        )
                        msg = await channel.send(embed=embed, view=BirthdayView())
                        cursor.execute("INSERT OR REPLACE INTO birthday_messages VALUES (?,?)", (str(msg.id), str(uid)))
                        conn.commit()

                        birthday_role_id = get_guild_setting_role_id(guild.id, "birthday_role_id")
                        if birthday_role_id is not None:
                            role = guild.get_role(birthday_role_id)
                            if role and role not in member.roles:
                                try:
                                    await member.add_roles(role)
                                except Exception:
                                    pass

        cursor.execute("SELECT user_id FROM birthdays WHERE date=?", (yesterday_str,))
        users = cursor.fetchall()

        birthday_role_id = get_guild_setting_role_id(guild.id, "birthday_role_id")
        role = guild.get_role(birthday_role_id) if birthday_role_id else None

        for (uid,) in users:
            member = guild.get_member(int(uid))
            if not member:
                continue

            if role and role in member.roles:
                try:
                    await member.remove_roles(role)
                except Exception:
                    pass

            try:
                if "?럟" in member.display_name:
                    await member.edit(nick=member.display_name.replace(" ?럟", ""))
            except Exception:
                pass

@tasks.loop(minutes=1)
async def all_in_game_loop():
    today_date = get_today_kst_date_str()

    for guild in bot.guilds:
        pending_dates = get_pending_all_in_dates(guild.id, today_date)
        if not pending_dates:
            continue

        for target_date in pending_dates:
            rows = get_all_in_entries(target_date, guild.id)
            if not rows:
                continue

            valid_members = []
            total_amount = 0

            for user_id, amount in rows:
                total_amount += amount

                member = guild.get_member(int(user_id))
                if member is not None:
                    valid_members.append(member)

            if total_amount <= 0:
                clear_all_in_entries(target_date, guild.id)
                continue

            if not valid_members:
                clear_all_in_entries(target_date, guild.id)
                continue

            winner = random.choice(valid_members)
            add_balance(winner.id, total_amount)

            result_channel_id = get_guild_setting_channel_id(guild.id, "all_in_result_channel_id")
            target_channel = guild.get_channel(result_channel_id) if result_channel_id else None

            result_text = (
                f"{target_date} - 李멸???{len(rows)}紐?/ "
                f"?좏슚 李멸???{len(valid_members)}紐?/ "
                f"?뱀꺼??{winner.display_name} / "
                f"珥??곴툑 {format_money(total_amount)}"
            )
            add_game_history(guild.id, ALL_IN_GAME_NAME, result_text)

            if target_channel is not None:
                embed = discord.Embed(
                    title="?뮙 紐곕뭇寃뚯엫 寃곌낵",
                    description=(
                        f"?좎쭨: `{target_date}`\n"
                        f"?꾩껜 李멸????? `{len(rows)}紐?\n"
                        f"異붿꺼 媛???몄썝: `{len(valid_members)}紐?\n"
                        f"珥??곴툑: `{format_money(total_amount)}`\n\n"
                        f"?룇 ?뱀꺼?? {winner.mention}"
                    ),
                    color=0xF1C40F,
                )
                await target_channel.send(embed=embed)

            clear_all_in_entries(target_date, guild.id)

@tasks.loop(minutes=1)
async def loan_due_check_loop():
    now = get_kst_now()
    rows = get_due_loans(now)

    for loan_id, guild_id, user_id, total_repayment, due_at in rows:
        mark_loan_overdue(loan_id)
        downgrade_credit_grade(int(user_id))
        profile = get_credit_profile(int(user_id))
        if profile["is_blacklisted"]:
            create_or_replace_labor_penalty(int(guild_id), int(user_id), int(total_repayment))



# ============================================================
# 봇 시작 설정
# ============================================================

@bot.event
async def on_ready():
    for guild in bot.guilds:
        try:
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
        except Exception as e:
            print(f"湲몃뱶 紐낅졊??珥덇린???ㅽ뙣 ({guild.id}): {e}")

    await bot.tree.sync()

    bot.add_view(BirthdayView())
    bot.add_view(RuleConfirmView())
    bot.add_view(UpgradePanelView())
    bot.add_view(TimeRoleView())
    bot.add_view(InquiryPanelView())
    bot.add_view(ScrimSignupView())


    await restore_nickname_panels()
    await backfill_probation_members()

    if not birthday_loop.is_running():
        birthday_loop.start()

    if not probation_role_check_loop.is_running():
        probation_role_check_loop.start()

    if not all_in_game_loop.is_running():
        all_in_game_loop.start()
        
    if not loan_due_check_loop.is_running():
        loan_due_check_loop.start()


    print("硫?곗꽌踰????留덈━遊??ㅽ뻾 ?꾨즺")


bot.run(TOKEN)

