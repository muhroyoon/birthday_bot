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

DAILY_REWARD = 10000
MIN_BET = 100
COIN_FLIP_TIMEOUT = 60
ROULETTE_TIMEOUT = 60
MAX_PLAYERS = 4
ALL_IN_COST = 10000
ALL_IN_GAME_NAME = "몰빵게임"
GAME_HISTORY_LIMIT = 10
INITIAL_CREDIT_GRADE = 5
LOAN_REPAYMENT_DAYS = 2

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
    11: 380000,
    12: 560000,
    13: 820000,
    14: 1180000,
    15: 1700000,
    16: 2450000,
    17: 3500000,
    18: 5000000,
    19: 7100000,
    20: 10000000,
    21: 14000000,
}


WEAPON_PROTECTION_COSTS = {
    1: 5000,
    2: 9000,
    3: 15000,
    4: 24000,
    5: 36000,
    6: 52000,
    7: 72000,
    8: 98000,
    9: 132000,
    10: 176000,
    11: 235000,
    12: 310000,
    13: 410000,
    14: 540000,
    15: 710000,
    16: 930000,
    17: 1210000,
    18: 1570000,
    19: 2030000,
    20: 2610000,
    21: 3350000,
}

WEAPON_SELL_PRICES = {
    1: 9000,
    2: 18000,
    3: 32000,
    4: 52000,
    5: 78000,
    6: 112000,
    7: 158000,
    8: 220000,
    9: 305000,
    10: 415000,
    11: 560000,
    12: 750000,
    13: 1000000,
    14: 1330000,
    15: 1760000,
    16: 2320000,
    17: 3020000,
    18: 3920000,
    19: 5050000,
    20: 6480000,
    21: 8300000,
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
    "등업 신청 패널입니다.\n\n"
    "1. 닉네임 변경\n"
    "2. 자기소개 작성\n"
    "3. 규칙 확인\n"
    "4. 출석 체크\n\n"
    "완료하셨다면 아래 버튼을 눌러주세요!"
)
DEFAULT_WELCOME_DM_TEXT = (
    "안녕하세요 {user}님! 서버에 오신 걸 환영합니다!\n"
    "서버 안내는 {guide_channel} 에 정리되어 있습니다.\n"
    "궁금한 점이 있으면 관리자에게 문의해주세요!"
)
DEFAULT_PROBATION_NOTICE_TEXT = (
    "신입 역할 부여 후 7일이 지났습니다.\n"
    "출석과 평판을 확인한 뒤 역할 유지 여부를 검토해주세요."
)
DEFAULT_PROBATION_DAYS = "7"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
active_recruits = {}

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
    CREATE TABLE IF NOT EXISTS weapon_inventory(
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        weapon_level INTEGER NOT NULL DEFAULT 0,
        protection_count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )
    """
)

conn.commit()


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
        return ["📺관전중"]

    return [item.strip() for item in raw.split(",") if item.strip()]


def is_spectator_member(member: discord.Member, guild_id: int) -> bool:
    display_name = member.display_name.strip()

    for prefix in get_spectator_prefixes(guild_id):
        token = f"[{prefix}]"
        if display_name.startswith(token):
            return True

    return False



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
        "SELECT grade, is_blacklisted FROM credit_profiles WHERE user_id=?",
        (str(user_id),),
    )
    row = cursor.fetchone()
    if not row:
        return {"grade": INITIAL_CREDIT_GRADE, "is_blacklisted": False}

    return {
        "grade": int(row[0]),
        "is_blacklisted": bool(row[1]),
    }


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
    cursor.execute(
        "UPDATE credit_profiles SET is_blacklisted=? WHERE user_id=?",
        (1 if is_blacklisted else 0, str(user_id)),
    )
    conn.commit()


def upgrade_credit_grade(user_id: int):
    profile = get_credit_profile(user_id)

    if profile["is_blacklisted"]:
        # 신용불량자 해제 시 6등급으로 복귀
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
        SELECT id, user_id, due_at
        FROM loans
        WHERE status='active' AND delinquency_processed=0 AND due_at<=?
        ORDER BY id ASC
        """,
        (dt_to_db(now),),
    )
    return cursor.fetchall()

def ensure_weapon_inventory(guild_id: int, user_id: int):
    cursor.execute(
        """
        INSERT OR IGNORE INTO weapon_inventory(guild_id, user_id, weapon_level, protection_count)
        VALUES (?, ?, 0, 0)
        """,
        (str(guild_id), str(user_id)),
    )
    conn.commit()


def get_weapon_inventory(guild_id: int, user_id: int):
    ensure_weapon_inventory(guild_id, user_id)
    cursor.execute(
        """
        SELECT weapon_level, protection_count
        FROM weapon_inventory
        WHERE guild_id=? AND user_id=?
        """,
        (str(guild_id), str(user_id)),
    )
    row = cursor.fetchone()
    if not row:
        return {"weapon_level": 0, "protection_count": 0}

    return {
        "weapon_level": int(row[0]),
        "protection_count": int(row[1]),
    }


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


def add_protection_count(guild_id: int, user_id: int, amount: int):
    ensure_weapon_inventory(guild_id, user_id)
    cursor.execute(
        """
        UPDATE weapon_inventory
        SET protection_count=protection_count+?
        WHERE guild_id=? AND user_id=?
        """,
        (amount, str(guild_id), str(user_id)),
    )
    conn.commit()


def consume_protection_count(guild_id: int, user_id: int, amount: int = 1):
    ensure_weapon_inventory(guild_id, user_id)
    cursor.execute(
        """
        UPDATE weapon_inventory
        SET protection_count=MAX(protection_count-?, 0)
        WHERE guild_id=? AND user_id=?
        """,
        (amount, str(guild_id), str(user_id)),
    )
    conn.commit()


def ensure_base_weapon(guild_id: int, user_id: int):
    inventory = get_weapon_inventory(guild_id, user_id)
    if inventory["weapon_level"] <= 0:
        set_weapon_level(guild_id, user_id, 1)


def get_weapon_name(level: int) -> str:
    return WEAPON_LEVEL_NAMES.get(level, "알 수 없는 무기")


def get_upgrade_cost(level: int) -> int | None:
    return WEAPON_UPGRADE_COSTS.get(level)


def get_protection_cost(level: int) -> int:
    return WEAPON_PROTECTION_COSTS.get(level, WEAPON_PROTECTION_COSTS[21])


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
    protection_count = inventory["protection_count"]

    embed = discord.Embed(title="🔧 무기 강화", color=0x5865F2)

    embed.add_field(
        name="현재 무기",
        value=f"{current_level}강 {current_name}",
        inline=False
    )

    embed.add_field(
        name="보유 보호권",
        value=f"{protection_count}장",
        inline=False
    )

    embed.add_field(
        name="현재 잔액",
        value=format_money(get_balance(user_id)),
        inline=False
    )

    if current_level >= 21:
        embed.add_field(
            name="강화 상태",
            value="최대 강화 단계입니다.",
            inline=False
        )
        return embed

    next_level = current_level + 1
    next_name = get_weapon_name(next_level)

    upgrade_cost = get_upgrade_cost(current_level)
    protection_cost = get_protection_cost(current_level)

    rates = WEAPON_UPGRADE_RATES[current_level]

    embed.add_field(
        name="다음 무기",
        value=f"{next_level}강 {next_name}",
        inline=False
    )

    embed.add_field(
        name="강화 비용",
        value=format_money(upgrade_cost),
        inline=False
    )

    embed.add_field(
        name="보호권 가격",
        value=format_money(protection_cost),
        inline=False
    )

    embed.add_field(
        name="강화 확률",
        value=(
            f"성공: {rates['success']}%\n"
            f"하락: {rates['down']}%\n"
            f"파괴: {rates['destroy']}%\n"
            f"유지: {rates['keep']}%"
        ),
        inline=False,
    )

    embed.add_field(
        name="안내",
        value="보호권은 강화 성공을 보장하지 않으며, 실패 시 하락과 파괴를 자동으로 방지합니다.",
        inline=False,
    )

    return embed


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
    "슬롯": "슬롯",
    "동전": "동전",
    "룰렛": "룰렛",
    "보급": "보급",
    "몰빵게임": "몰빵게임",
}



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
                    await member.send(embed=embed)
                except Exception:
                    pass

        await interaction.response.send_message("🎉 축하 완료!", ephemeral=True)


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
                await log_channel.send(f"✅ {interaction.user.mention} 님이 규칙 확인")

        await interaction.response.send_message("🎉 규칙 확인 완료!", ephemeral=True)


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

        await channel.send(
            content=f"{user.mention}님의 등업 신청 채널입니다.",
            view=UpgradeTicketView(user),
        )

        await interaction.response.send_message(f"{channel.mention} 생성 완료!", ephemeral=True)


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
            embed = discord.Embed(title="📋 등업 로그", color=0x3498DB)
            embed.add_field(name="대상", value=self.user.mention, inline=True)
            embed.add_field(name="처리자", value=interaction.user.mention, inline=True)
            embed.add_field(name="결과", value=action, inline=False)
            await log_channel.send(embed=embed)

    async def send_welcome_dm(self):
        guild_id = self.user.guild.id
        template = get_template_with_default(guild_id, "welcome_dm", DEFAULT_WELCOME_DM_TEXT)
        guide_channel_id = get_guild_setting(guild_id, "welcome_guide_channel_id")
        guide_channel_text = f"<#{guide_channel_id}>" if guide_channel_id else "안내 채널"
        content = template.replace("{user}", self.user.mention).replace("{guide_channel}", guide_channel_text)

        try:
            await self.user.send(content)
        except Exception:
            pass

    @discord.ui.button(label="클랜원등업", style=discord.ButtonStyle.primary, custom_id="upgrade_clan")
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

    @discord.ui.button(label="게스트등업", style=discord.ButtonStyle.secondary, custom_id="upgrade_guest")
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

    @discord.ui.button(label="티켓삭제", style=discord.ButtonStyle.danger, custom_id="ticket_delete")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        await interaction.response.send_message("삭제 중...")
        await interaction.channel.delete()


class TimeRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def add_role(self, interaction: discord.Interaction, slot_name: str):
        role_id = get_time_role_id(interaction.guild.id, slot_name)
        if role_id is None:
            await interaction.response.send_message("이 시간대 역할이 아직 설정되지 않았습니다.", ephemeral=True)
            return

        role = interaction.guild.get_role(role_id)
        if role is None:
            await interaction.response.send_message("설정된 역할을 찾을 수 없습니다.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("이미 선택된 시간대입니다.", ephemeral=True)
            return

        await interaction.user.add_roles(role)
        await interaction.response.send_message(f"{role.name} 역할이 추가되었습니다.", ephemeral=True)

    @discord.ui.button(label="오전반", style=discord.ButtonStyle.primary, custom_id="time_morning")
    async def morning(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, "morning")

    @discord.ui.button(label="오후반", style=discord.ButtonStyle.primary, custom_id="time_afternoon")
    async def afternoon(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, "afternoon")

    @discord.ui.button(label="저녁반", style=discord.ButtonStyle.primary, custom_id="time_evening")
    async def evening(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, "evening")

    @discord.ui.button(label="심야반", style=discord.ButtonStyle.secondary, custom_id="time_night")
    async def night(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, "night")

    @discord.ui.button(label="새벽반", style=discord.ButtonStyle.secondary, custom_id="time_dawn")
    async def dawn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.add_role(interaction, "dawn")

    @discord.ui.button(label="리셋", style=discord.ButtonStyle.danger, custom_id="time_reset")
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_map = get_all_time_roles(interaction.guild.id)
        removed = []
        for role_id in role_map.values():
            role = interaction.guild.get_role(role_id)
            if role and role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                removed.append(role.name)

        if removed:
            await interaction.response.send_message(f"삭제된 역할: {', '.join(removed)}", ephemeral=True)
        else:
            await interaction.response.send_message("삭제할 시간대 역할이 없습니다.", ephemeral=True)


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
            payout = int(self.bet_amount * 1.8)
            add_balance(self.user_id, payout)
            description = f"선택: **{choice}**\n결과: **{result}**\n축하합니다! `{format_money(payout)}`을 받았습니다."
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
            f"{interaction.user.display_name} - 선택:{choice} / 결과:{result} / {'당첨' if win else '꽝'}"
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
            await interaction.response.send_message("이 버튼은 명령어를 사용한 사람만 누를 수 있습니다.", ephemeral=True)
            return False
        return True

    def spin_result(self) -> str:
        return random.choices(
            ["빨강", "노랑", "파랑", "검정", "초록"],
            weights=[34, 25, 19, 13, 9],
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
            f"{interaction.user.display_name} - 선택:{choice} / 결과:{result} / {'당첨' if win else '꽝'}"
        )

        await interaction.response.edit_message(embed=embed, view=self)


    async def on_timeout(self):
        if self.resolved:
            return
        self.resolved = True
        add_balance(self.user_id, self.bet_amount)
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="🔴 빨강", style=discord.ButtonStyle.danger)
    async def red(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "빨강")

    @discord.ui.button(label="🟡 노랑", style=discord.ButtonStyle.primary)
    async def yellow(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "노랑")

    @discord.ui.button(label="🔵 파랑", style=discord.ButtonStyle.primary)
    async def blue(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "파랑")

    @discord.ui.button(label="⚫ 검정", style=discord.ButtonStyle.secondary)
    async def black(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.finish(interaction, "검정")

    @discord.ui.button(label="🟢 초록", style=discord.ButtonStyle.success)
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
                "이 버튼은 명령어를 사용한 사람만 누를 수 있습니다.",
                ephemeral=True,
            )
            return False
        return True

    def roll_result(self):
        result = random.choices(
            [
                ("빈 상자", 0.0, "📦 보급상자를 열었지만... 이미 누군가 싹 털어간 빈 상자였습니다."),
                ("1뚝", 0.8, "🪖 낡은 1레벨 헬멧 하나만 겨우 건졌습니다."),
                ("2뚝", 1.0, "🪖 2레벨 헬멧을 챙겼습니다. 최소한 머리는 지킬 수 있겠네요."),
                ("3뚝", 1.6, "✨ 3레벨 헬멧을 획득했습니다! 이번 교전은 자신 있어집니다."),
                ("보급 총기 획득", 2.8, "🔫 보급 총기를 획득했습니다! 적들이 긴장하기 시작합니다."),
                ("풀세트 보급 대박", 4.5, "🔥 3뚝, 3갑, 보급총기까지 전부 챙겼습니다! 완벽한 풀세트 보급 대박입니다!"),
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
            title="📦 보급상자 개봉 결과",
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

    @discord.ui.button(label="📦 보급 열기", style=discord.ButtonStyle.primary)
    async def open_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_supply(interaction)


class TeamSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    async def create_team(self, interaction: discord.Interaction, team_size: int):
        if interaction.user.voice is None:
            await interaction.response.send_message("❌ 음성채널에 있어야 합니다.", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        players = [
            member.display_name
            for member in channel.members
            if not member.bot and not is_spectator_member(member, interaction.guild.id)
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


class NicknamePrefixApplyButton(discord.ui.Button):
    def __init__(self, prefix: str, managed_prefixes: list[str], panel_key: str):
        super().__init__(
            label=f"{prefix}적용",
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
            f"닉네임 앞에 `[{self.prefix}]` 접두사를 적용했습니다.",
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

    @discord.ui.button(label="티켓보관", style=discord.ButtonStyle.secondary, custom_id="inquiry_archive")
    async def archive_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        await interaction.channel.set_permissions(self.user, send_messages=False)
        await interaction.response.send_message("티켓을 보관했습니다. 작성자는 더 이상 메시지를 보낼 수 없습니다.")

    @discord.ui.button(label="티켓삭제", style=discord.ButtonStyle.danger, custom_id="inquiry_delete")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        await interaction.response.send_message("티켓을 삭제합니다.")
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
            await interaction.response.send_message(f"이미 {ticket_type} 티켓이 있습니다: {existing.mention}", ephemeral=True)
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
            title=f"{ticket_type} 티켓",
            description=f"{user.mention}님의 [{ticket_type}] 입니다.",
            color=0x5865F2,
        )

        await channel.send(
            content=user.mention,
            embed=embed,
            view=InquiryManageView(user, ticket_type),
        )

        await interaction.response.send_message(f"{channel.mention} 티켓이 생성되었습니다.", ephemeral=True)

    @discord.ui.button(label="문의하기", style=discord.ButtonStyle.primary, custom_id="inquiry_open")
    async def inquiry_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "문의")

    @discord.ui.button(label="신고하기", style=discord.ButtonStyle.danger, custom_id="report_open")
    async def report_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "신고")

    @discord.ui.button(label="건의하기", style=discord.ButtonStyle.success, custom_id="suggest_open")
    async def suggest_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "건의")

class HistoryGameSelectView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id

    async def show_history(self, interaction: discord.Interaction, game_name: str):
        rows = get_recent_game_history(self.guild_id, game_name, GAME_HISTORY_LIMIT)

        if not rows:
            await interaction.response.send_message(
                f"{game_name}의 최근 기록이 없습니다.",
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
            title=f"📜 {game_name} 최근 {min(len(rows), GAME_HISTORY_LIMIT)}게임",
            description="\n".join(lines),
            color=0x5865F2,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="슬롯", style=discord.ButtonStyle.primary)
    async def slot_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "슬롯")

    @discord.ui.button(label="동전", style=discord.ButtonStyle.primary)
    async def coin_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "동전")

    @discord.ui.button(label="룰렛", style=discord.ButtonStyle.primary)
    async def roulette_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "룰렛")

    @discord.ui.button(label="보급", style=discord.ButtonStyle.success)
    async def supply_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "보급")

    @discord.ui.button(label="몰빵게임", style=discord.ButtonStyle.secondary)
    async def all_in_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "몰빵게임")

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
            await interaction.response.send_message("이 버튼은 명령어를 사용한 사람만 누를 수 있습니다.", ephemeral=True)
            return False
        return True

    async def resolve_choice(self, interaction: discord.Interaction, fake_name: str):
        if self.resolved:
            await interaction.response.send_message("이미 결과가 확정되었습니다.", ephemeral=True)
            return

        self.resolved = True
        result_type = self.hidden_results[fake_name]

        payout = 0
        if result_type == "오리":
            payout = self.bet_amount * 2
            add_balance(self.user_id, payout)
            result_text = f"정답은 **오리**였습니다! `{format_money(self.bet_amount)}`을 추가로 벌었습니다."
            color = 0x2ECC71
        elif result_type == "팰리컨":
            payout = self.bet_amount
            add_balance(self.user_id, payout)
            result_text = "정답은 **팰리컨**이었습니다. 배팅금액을 그대로 돌려받았습니다."
            color = 0x3498DB
        else:
            result_text = "정답은 **거위**였습니다. 배팅금액을 잃었습니다."
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
        embed.add_field(name="현재 잔액", value=format_money(get_balance(self.user_id)), inline=False)

        add_game_history(
            interaction.guild.id,
            "덕몽",
            f"{interaction.user.display_name} - 선택:{fake_name} / 결과:{result_type}"
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
            self.host, self.channel, players, spectators, self.message_content, self.max_players
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
                await interaction.response.send_message(f"{self.channel.mention} 음성채널로 이동했습니다.", ephemeral=True)
                return
            except (discord.Forbidden, discord.HTTPException):
                pass

        invite = await self.channel.create_invite(max_age=300, max_uses=1)
        await interaction.response.send_message(f"바로 이동 권한이 없어 초대 링크를 드릴게요: {invite.url}", ephemeral=True)

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


class WelcomeDmModal(discord.ui.Modal, title="환영 DM 설정"):
    content = discord.ui.TextInput(
        label="환영 DM 문구",
        placeholder="여러 줄로 입력하세요. {user}, {guide_channel} 사용 가능",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        set_template(interaction.guild.id, "welcome_dm", str(self.content).strip())
        await interaction.response.send_message("환영 DM 문구를 저장했습니다.", ephemeral=True)


class ProtectionPurchaseModal(discord.ui.Modal, title="강화보호권 구매"):
    quantity = discord.ui.TextInput(
        label="구매 수량",
        placeholder="예: 1",
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
            await interaction.response.send_message("구매 수량은 숫자로 입력해주세요.", ephemeral=True)
            return

        if quantity <= 0:
            await interaction.response.send_message("구매 수량은 1 이상이어야 합니다.", ephemeral=True)
            return

        inventory = get_weapon_inventory(self.guild_id, self.user_id)
        current_level = inventory["weapon_level"]

        if current_level <= 0:
            await interaction.response.send_message("보유 중인 무기가 없습니다.", ephemeral=True)
            return

        protection_cost = get_protection_cost(current_level)
        total_cost = protection_cost * quantity

        if not can_afford(self.user_id, total_cost):
            await interaction.response.send_message(
                f"보호권 구매 비용 `{format_money(total_cost)}`이 부족합니다.",
                ephemeral=True,
            )
            return

        add_balance(self.user_id, -total_cost)
        add_protection_count(self.guild_id, self.user_id, quantity)

        embed = build_upgrade_embed(self.guild_id, self.user_id)
        view = WeaponUpgradeView(self.guild_id, self.user_id)

        await interaction.response.edit_message(embed=embed, view=view)

class WeaponUpgradeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="강화", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if interaction.user.id != view.user_id:
            await interaction.response.send_message("이 버튼은 명령어를 사용한 사람만 누를 수 있습니다.", ephemeral=True)
            return

        inventory = get_weapon_inventory(view.guild_id, view.user_id)
        current_level = inventory["weapon_level"]
        protection_count = inventory["protection_count"]

        if current_level <= 0:
            ensure_base_weapon(view.guild_id, view.user_id)
            inventory = get_weapon_inventory(view.guild_id, view.user_id)
            current_level = inventory["weapon_level"]
            protection_count = inventory["protection_count"]

        if current_level >= 21:
            await interaction.response.send_message("이미 최대 강화 단계입니다.", ephemeral=True)
            return

        upgrade_cost = get_upgrade_cost(current_level)
        if upgrade_cost is None:
            await interaction.response.send_message("강화 비용 정보를 찾을 수 없습니다.", ephemeral=True)
            return

        if not can_afford(view.user_id, upgrade_cost):
            await interaction.response.send_message(
                f"강화 비용 `{format_money(upgrade_cost)}`이 부족합니다.",
                ephemeral=True,
            )
            return

        add_balance(view.user_id, -upgrade_cost)

        before_name = get_weapon_name(current_level)
        target_level = current_level + 1
        target_name = get_weapon_name(target_level)

        result = roll_upgrade_result(current_level)
        used_protection = False
        message_text = ""
        color = 0x5865F2

        if result == "success":
            set_weapon_level(view.guild_id, view.user_id, target_level)
            message_text = f"강화 성공! `{current_level}강 {before_name}` -> `{target_level}강 {target_name}`"
            color = 0x2ECC71
        elif result == "down":
            if protection_count > 0:
                consume_protection_count(view.guild_id, view.user_id, 1)
                used_protection = True
                message_text = f"강화 실패! 보호권이 자동 사용되어 하락이 방지되었습니다. 현재 무기: `{current_level}강 {before_name}`"
                color = 0x3498DB
            else:
                new_level = max(1, current_level - 1)
                set_weapon_level(view.guild_id, view.user_id, new_level)
                message_text = f"강화 실패! 단계가 하락했습니다. `{current_level}강 {before_name}` -> `{new_level}강 {get_weapon_name(new_level)}`"
                color = 0xE67E22
        elif result == "destroy":
            if protection_count > 0:
                consume_protection_count(view.guild_id, view.user_id, 1)
                used_protection = True
                message_text = f"강화 실패! 보호권이 자동 사용되어 파괴가 방지되었습니다. 현재 무기: `{current_level}강 {before_name}`"
                color = 0x3498DB
            else:
                set_weapon_level(view.guild_id, view.user_id, 0)
                message_text = f"강화 실패! `{current_level}강 {before_name}` 무기가 파괴되었습니다."
                color = 0xE74C3C
        else:
            message_text = f"강화 실패! 단계는 유지되었습니다. 현재 무기: `{current_level}강 {before_name}`"
            color = 0x95A5A6

        add_game_history(
            interaction.guild.id,
            "강화",
            f"{interaction.user.display_name} - {current_level}강 {before_name} / 결과:{result}{' / 보호권사용' if used_protection else ''}"
        )

        embed = build_upgrade_embed(view.guild_id, view.user_id)
        embed.title = "🔧 무기 강화 결과"
        embed.color = color
        embed.description = message_text

        await interaction.response.edit_message(embed=embed, view=WeaponUpgradeView(view.guild_id, view.user_id))


class ProtectionPurchaseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="보호권구매", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if interaction.user.id != view.user_id:
            await interaction.response.send_message("이 버튼은 명령어를 사용한 사람만 누를 수 있습니다.", ephemeral=True)
            return

        await interaction.response.send_modal(ProtectionPurchaseModal(view.guild_id, view.user_id))


class WeaponUpgradeView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=180)
        self.guild_id = guild_id
        self.user_id = user_id

        self.add_item(WeaponUpgradeButton())
        self.add_item(ProtectionPurchaseButton())


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
            f"{interaction.channel.mention} 채널의 고정메시지를 설정했습니다.",
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
        title=f"🎮 {game_name} 모집중!!",
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


@bot.tree.command(name="세팅생일알림", description="현재 채널을 생일 알림 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_birthday_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "birthday_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"생일 알림 채널을 {interaction.channel.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅등업로그", description="현재 채널을 등업 로그 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_upgrade_log_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "upgrade_log_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"등업 로그 채널을 {interaction.channel.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅퇴장로그", description="현재 채널을 퇴장 로그 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_leave_log_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "leave_log_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"퇴장 로그 채널을 {interaction.channel.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅규칙로그", description="현재 채널을 규칙/신입 알림 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_rule_log_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "rule_log_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"규칙 로그 채널을 {interaction.channel.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅구인채널", description="현재 채널을 구인 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_recruit_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "recruit_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"구인 채널을 {interaction.channel.mention} 으로 설정했습니다.", ephemeral=True)

@bot.tree.command(name="세팅몰빵결과채널", description="현재 채널을 몰빵게임 결과 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_all_in_result_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "all_in_result_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(
        f"몰빵게임 결과 채널을 {interaction.channel.mention} 으로 설정했습니다.",
        ephemeral=True,
    )

@bot.tree.command(name="세팅가입안내", description="현재 채널을 가입 안내 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_guide_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "welcome_guide_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"가입 안내 채널을 {interaction.channel.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅환영메시지채널", description="현재 채널을 환영메시지 송출 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_message_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "welcome_message_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"환영메시지 채널을 {interaction.channel.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅규칙역할", description="규칙 확인 시 지급할 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_rule_role(interaction: discord.Interaction, role: discord.Role):
    set_guild_setting(interaction.guild.id, "rule_role_id", str(role.id))
    await interaction.response.send_message(f"규칙 역할을 {role.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅신입역할", description="신입 추적용 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_new_member_role(interaction: discord.Interaction, role: discord.Role):
    set_guild_setting(interaction.guild.id, "new_member_role_id", str(role.id))
    await interaction.response.send_message(f"신입 역할을 {role.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅생일역할", description="생일 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_birthday_role(interaction: discord.Interaction, role: discord.Role):
    set_guild_setting(interaction.guild.id, "birthday_role_id", str(role.id))
    await interaction.response.send_message(f"생일 역할을 {role.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅클랜원역할", description="클랜원 등업 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_upgrade_clan_role(interaction: discord.Interaction, role: discord.Role):
    set_guild_setting(interaction.guild.id, "upgrade_clan_role_id", str(role.id))
    await interaction.response.send_message(f"클랜원 등업 역할을 {role.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅게스트역할", description="게스트 등업 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_upgrade_guest_role(interaction: discord.Interaction, role: discord.Role):
    set_guild_setting(interaction.guild.id, "upgrade_guest_role_id", str(role.id))
    await interaction.response.send_message(f"게스트 등업 역할을 {role.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅시간대역할", description="시간대 버튼에 연결할 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(slot_name="morning / afternoon / evening / night / dawn")
async def set_time_role_command(interaction: discord.Interaction, slot_name: str, role: discord.Role):
    slot_name = slot_name.lower().strip()
    if slot_name not in TIME_SLOT_CHOICES:
        await interaction.response.send_message("slot_name은 morning, afternoon, evening, night, dawn 중 하나여야 합니다.", ephemeral=True)
        return

    set_time_role(interaction.guild.id, slot_name, role.id)
    await interaction.response.send_message(f"{TIME_SLOT_LABELS[slot_name]} 역할을 {role.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅환영dm", description="등업 시 보낼 DM 문구를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_dm_template(interaction: discord.Interaction):
    await interaction.response.send_modal(WelcomeDmModal())


@bot.tree.command(name="세팅규칙안내문", description="규칙 버튼 안내문을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_rule_button_template(interaction: discord.Interaction, content: str):
    set_template(interaction.guild.id, "rule_button_text", content)
    await interaction.response.send_message("규칙 안내문을 저장했습니다.", ephemeral=True)


@bot.tree.command(name="세팅등업패널문구", description="등업 패널 문구를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_upgrade_panel_template(interaction: discord.Interaction, content: str):
    set_template(interaction.guild.id, "upgrade_panel_text", content)
    await interaction.response.send_message("등업 패널 문구를 저장했습니다.", ephemeral=True)


@bot.tree.command(name="세팅신입알림문구", description="신입 역할 경과 알림 문구를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_probation_notice_template(interaction: discord.Interaction, content: str):
    set_template(interaction.guild.id, "probation_notice_text", content)
    await interaction.response.send_message("신입 알림 문구를 저장했습니다.", ephemeral=True)


@bot.tree.command(name="세팅신입경과일", description="신입 역할 경과 알림 일수를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_probation_days(interaction: discord.Interaction, days: int):
    if days < 1:
        await interaction.response.send_message("일수는 1 이상이어야 합니다.", ephemeral=True)
        return

    set_guild_setting(interaction.guild.id, "probation_days", str(days))
    await interaction.response.send_message(
        f"신입 역할 경과일을 {days}일로 설정했습니다.",
        ephemeral=True,
    )


@bot.tree.command(name="설정확인", description="현재 채널 설정을 확인합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def show_settings(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    keys = [
        ("생일 알림", "birthday_channel_id"),
        ("등업 로그", "upgrade_log_channel_id"),
        ("퇴장 로그", "leave_log_channel_id"),
        ("규칙 로그", "rule_log_channel_id"),
        ("구인 채널", "recruit_channel_id"),
        ("가입 안내", "welcome_guide_channel_id"),
        ("환영메시지 채널", "welcome_message_channel_id"),
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
        ("규칙 역할", "rule_role_id"),
        ("신입 역할", "new_member_role_id"),
        ("생일 역할", "birthday_role_id"),
        ("클랜원 등업 역할", "upgrade_clan_role_id"),
        ("게스트 등업 역할", "upgrade_guest_role_id"),
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


@bot.tree.command(name="문구설정확인", description="현재 저장된 커스텀 문구를 확인합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def show_template_settings(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    embed = discord.Embed(title="문구 설정", color=0x9B59B6)
    embed.add_field(
        name="환영 DM",
        value=get_template_with_default(guild_id, "welcome_dm", DEFAULT_WELCOME_DM_TEXT),
        inline=False,
    )
    embed.add_field(
        name="규칙 안내문",
        value=get_template_with_default(guild_id, "rule_button_text", DEFAULT_RULE_BUTTON_TEXT),
        inline=False,
    )
    embed.add_field(
        name="등업 패널 문구",
        value=get_template_with_default(guild_id, "upgrade_panel_text", DEFAULT_UPGRADE_PANEL_TEXT),
        inline=False,
    )
    embed.add_field(
        name="신입 알림 문구",
        value=get_template_with_default(guild_id, "probation_notice_text", DEFAULT_PROBATION_NOTICE_TEXT),
        inline=False,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="환영메시지", description="특정 역할에 대한 환영메시지를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def welcome_message(interaction: discord.Interaction, role: discord.Role, content: str):
    set_welcome_message(interaction.guild.id, role.id, content)
    await interaction.response.send_message(f"{role.mention} 역할의 환영메시지를 저장했습니다.", ephemeral=True)


@bot.tree.command(name="환영메시지삭제", description="특정 역할의 환영메시지를 삭제합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def delete_welcome_message_command(interaction: discord.Interaction, role: discord.Role):
    delete_welcome_message(interaction.guild.id, role.id)
    await interaction.response.send_message(f"{role.mention} 역할의 환영메시지를 삭제했습니다.", ephemeral=True)


@bot.tree.command(name="환영메시지목록", description="등록된 환영메시지 목록을 확인합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def list_welcome_messages(interaction: discord.Interaction):
    rows = get_all_welcome_messages(interaction.guild.id)
    if not rows:
        await interaction.response.send_message("등록된 환영메시지가 없습니다.", ephemeral=True)
        return

    lines = []
    for role_id, content in rows:
        lines.append(f"<@&{role_id}> -> {content}")

    embed = discord.Embed(title="환영메시지 목록", description="\n\n".join(lines), color=0x2ECC71)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="고정메시지", description="현재 채널에 항상 하단에 유지될 메시지를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def sticky_message(interaction: discord.Interaction):
    await interaction.response.send_modal(StickyMessageModal())


@bot.tree.command(name="고정해제", description="현재 채널의 고정메시지를 해제합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def sticky_clear(interaction: discord.Interaction):
    existing = get_sticky_message(interaction.guild.id, interaction.channel.id)
    if not existing:
        await interaction.response.send_message("이 채널에는 설정된 고정메시지가 없습니다.", ephemeral=True)
        return

    if existing.get("message_id"):
        try:
            old_message = await interaction.channel.fetch_message(existing["message_id"])
            await old_message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    clear_sticky_message(interaction.guild.id, interaction.channel.id)
    await interaction.response.send_message("현재 채널의 고정메시지를 해제했습니다.", ephemeral=True)


@bot.tree.command(name="고정확인", description="현재 채널의 고정메시지 내용을 확인합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def sticky_check(interaction: discord.Interaction):
    existing = get_sticky_message(interaction.guild.id, interaction.channel.id)
    if not existing:
        await interaction.response.send_message("이 채널에는 설정된 고정메시지가 없습니다.", ephemeral=True)
        return

    embed = discord.Embed(title="고정메시지 확인", color=0x5865F2)
    embed.add_field(name="채널", value=interaction.channel.mention, inline=False)
    embed.add_field(name="내용", value=existing["content"], inline=False)
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
    text = get_template_with_default(interaction.guild.id, "rule_button_text", DEFAULT_RULE_BUTTON_TEXT)
    embed = discord.Embed(description=text, color=0x2ECC71)
    await interaction.channel.send(embed=embed, view=RuleConfirmView())
    await interaction.response.send_message("규칙 버튼 생성 완료", ephemeral=True)


@bot.tree.command(name="등업패널", description="등업 신청 패널을 생성합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def upgrade_panel(interaction: discord.Interaction):
    text = get_template_with_default(interaction.guild.id, "upgrade_panel_text", DEFAULT_UPGRADE_PANEL_TEXT)
    embed = discord.Embed(description=text, color=0x5865F2)
    await interaction.channel.send(embed=embed, view=UpgradePanelView())
    await interaction.response.send_message("등업 패널 생성 완료", ephemeral=True)


@bot.tree.command(name="시간설정패널", description="시간대 역할 선택 패널을 생성합니다.")
async def time_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="플레이 시간대 설정",
        description="원하는 시간대를 선택해주세요.\n중복 선택 가능합니다.",
        color=0x5865F2,
    )
    await interaction.channel.send(embed=embed, view=TimeRoleView())
    await interaction.response.send_message("시간 설정 패널 생성 완료", ephemeral=True)


@bot.tree.command(name="상생지원금", description="하루에 한 번 상생지원금 10,000원을 받습니다.")
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

    await interaction.response.send_message(
        f"오늘의 상생지원금 `{format_money(DAILY_REWARD)}`을 받았습니다!\n현재 잔액: `{format_money(get_balance(interaction.user.id))}`"
    )


@bot.tree.command(name="잔액", description="현재 내 보유 금액을 확인합니다.")
async def balance(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"{interaction.user.mention}님의 현재 잔액은 `{format_money(get_balance(interaction.user.id))}`입니다."
    )


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
    await interaction.response.send_message(
        f"{member.mention}님에게 `{format_money(amount)}`을 송금했습니다.\n현재 잔액: `{format_money(get_balance(interaction.user.id))}`"
    )


@bot.tree.command(name="돈지급", description="서버 관리자 이상이 여러 유저에게 같은 금액을 지급합니다.")
@app_commands.rename(targets="대상들", amount="금액")
@app_commands.describe(
    targets="멘션 또는 ID를 공백/쉼표로 구분해서 입력",
    amount="각 유저에게 지급할 금액",
)
async def grant_money(interaction: discord.Interaction, targets: str, amount: int):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    if not (
        interaction.user.id == interaction.guild.owner_id
        or interaction.user.guild_permissions.administrator
        or interaction.user.guild_permissions.manage_guild
    ):
        await interaction.response.send_message("이 명령어는 서버 관리자 이상만 사용할 수 있습니다.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("지급 금액은 1원 이상이어야 합니다.", ephemeral=True)
        return

    raw_ids = []
    for token in targets.replace(",", " ").split():
        cleaned = token.strip().replace("<@", "").replace("!", "").replace(">", "")
        if cleaned.isdigit():
            raw_ids.append(int(cleaned))

    if not raw_ids:
        await interaction.response.send_message(
            "대상을 한 명 이상 입력해주세요. 예: `@유저1 @유저2 @유저3`",
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
        await interaction.response.send_message("지급 가능한 유저가 없습니다.", ephemeral=True)
        return

    lines = [
        f"총 {len(success_members)}명에게 각각 `{format_money(amount)}`을 지급했습니다.",
        f"대상: {', '.join(success_members)}",
    ]

    if skipped_members:
        lines.append(f"제외됨: {', '.join(skipped_members)}")

    await interaction.response.send_message("\n".join(lines))




@bot.tree.command(name="돈삭제", description="서버 주인이 특정 유저의 돈을 차감합니다.")
async def remove_money(interaction: discord.Interaction, member: discord.Member, amount: int):
    if interaction.guild is None or interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("이 명령어는 서버 주인만 사용할 수 있습니다.", ephemeral=True)
        return

    if member.bot:
        await interaction.response.send_message("봇의 돈은 삭제할 수 없습니다.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("차감 금액은 1원 이상이어야 합니다.", ephemeral=True)
        return

    current_balance = get_balance(member.id)
    deducted_amount = min(current_balance, amount)
    add_balance(member.id, -deducted_amount)

    await interaction.response.send_message(
        f"{member.mention}님에게서 `{format_money(deducted_amount)}`을 차감했습니다.\n"
        f"{member.mention}님의 현재 잔액: `{format_money(get_balance(member.id))}`"
    )


@bot.tree.command(name="슬롯", description="입력한 금액으로 슬롯머신을 돌립니다.")
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
    second = first if random.random() < 0.05 else random.choice(symbols)
    third = first if random.random() < 0.05 else random.choice(symbols)
    result = [first, second, third]

    multiplier = 0

    if len(set(result)) == 1:
        if result[0] == "7️⃣":
            multiplier = 12
        elif result[0] == "💎":
            multiplier = 8
        else:
            multiplier = 6
    elif len(set(result)) == 2:
        counts = {symbol: result.count(symbol) for symbol in set(result)}
        pair_symbol = max(counts, key=counts.get)

        if counts[pair_symbol] == 2:
            if pair_symbol == "7️⃣":
                multiplier = 1.6
            elif pair_symbol == "💎":
                multiplier = 1.3
            else:
                multiplier = 1.1

    winnings = int(amount * multiplier)
    if winnings > 0:
        add_balance(interaction.user.id, winnings)

    balance_now = get_balance(interaction.user.id)

    if multiplier == 0:
        desc = f"`{' | '.join(result)}`\n\n아쉽네요... `{format_money(amount)}`을 잃었습니다.\n현재 잔액: `{format_money(balance_now)}`"
        color = 0xE74C3C
    elif len(set(result)) == 1:
        desc = f"`{' | '.join(result)}`\n\n대박! `{multiplier}배` 당첨으로 `{format_money(winnings)}`을 받았습니다.\n현재 잔액: `{format_money(balance_now)}`"
        color = 0x2ECC71
    else:
        desc = f"`{' | '.join(result)}`\n\n2개 일치! `{multiplier}배` 보상으로 `{format_money(winnings)}`을 받았습니다.\n현재 잔액: `{format_money(balance_now)}`"
        color = 0x3498DB

    add_game_history(
        interaction.guild.id,
        "슬롯",
        f"{interaction.user.display_name} - {' | '.join(result)} - {('꽝' if multiplier == 0 else f'{multiplier}배')}"
    )

    embed = discord.Embed(title="🎰 슬롯 결과", description=desc, color=color)
    await interaction.response.send_message(embed=embed)



@bot.tree.command(name="동전", description="입력한 금액으로 동전 앞뒤 맞추기를 합니다.")
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
            "당첨 시 1.8배를 지급합니다.\n"
            f"{COIN_FLIP_TIMEOUT}초 안에 선택하지 않으면 자동 취소되고 돈이 반환됩니다."
        ),
        color=0xF1C40F,
    )
    await interaction.response.send_message(embed=embed, view=CoinFlipView(interaction.user.id, amount))


@bot.tree.command(name="룰렛", description="룰렛에 배팅하고 색상을 선택합니다.")
async def roulette(interaction: discord.Interaction, amount: int):
    if amount < MIN_BET:
        await interaction.response.send_message(
            f"최소 배팅 금액은 `{format_money(MIN_BET)}`입니다.",
            ephemeral=True,
        )
        return

    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)

    embed = discord.Embed(
        title="🎡 룰렛",
        description=(
            f"배팅 금액: `{format_money(amount)}`\n\n"
            "색상을 선택하세요.\n\n"
            "🔴 빨강: 당첨 시 2.5배\n"
            "🟡 노랑: 당첨 시 3.4배\n"
            "🔵 파랑: 당첨 시 4.4배\n"
            "⚫ 검정: 당첨 시 6.5배\n"
            "🟢 초록: 당첨 시 9.5배\n\n"
            "빨강은 가장 안전하고,\n"
            "점점 확률은 낮아지지만 배당은 높아집니다.\n"
        ),
        color=0xF1C40F,
    )

    await interaction.response.send_message(
        embed=embed,
        view=RouletteView(interaction.user.id, amount),
    )


@bot.tree.command(name="세팅대기방추가", description="대기방 음성채널을 등록합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def add_waiting_room_command(interaction: discord.Interaction, channel: discord.VoiceChannel):
    add_waiting_room(interaction.guild.id, channel.id)
    await interaction.response.send_message(
        f"{channel.mention} 채널을 대기방으로 등록했습니다.",
        ephemeral=True,
    )


@bot.tree.command(name="세팅대기방삭제", description="등록된 대기방을 제거합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def remove_waiting_room_command(interaction: discord.Interaction, channel: discord.VoiceChannel):
    remove_waiting_room(interaction.guild.id, channel.id)
    await interaction.response.send_message(
        f"{channel.mention} 채널을 대기방에서 제거했습니다.",
        ephemeral=True,
    )


@bot.tree.command(name="대기방목록", description="현재 등록된 대기방 목록을 확인합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def list_waiting_rooms(interaction: discord.Interaction):
    room_ids = get_waiting_rooms(interaction.guild.id)
    if not room_ids:
        await interaction.response.send_message("등록된 대기방이 없습니다.", ephemeral=True)
        return

    lines = [f"<#{room_id}>" for room_id in room_ids]
    embed = discord.Embed(title="등록된 대기방 목록", description="\n".join(lines), color=0x3498DB)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="팀", description="랜덤 팀 생성")
async def team(interaction: discord.Interaction):
    embed = discord.Embed(title="👥 팀 생성", description="팀 인원을 선택하세요", color=0x3498DB)
    await interaction.response.send_message(embed=embed, view=TeamSelectView())

@bot.tree.command(name="팀섞기규칙설정", description="관전자 제외용 접두사를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.rename(prefixes="접두사들")
@app_commands.describe(prefixes="쉼표로 구분해서 입력하세요. 예: 📺관전중,🚫휴식중")
async def set_team_mix_rule(interaction: discord.Interaction, prefixes: str):
    prefix_list = [item.strip() for item in prefixes.split(",") if item.strip()]

    if not prefix_list:
        await interaction.response.send_message(
            "접두사를 하나 이상 입력해주세요. 예: `📺관전중,🚫휴식중`",
            ephemeral=True,
        )
        return

    set_guild_setting(interaction.guild.id, "spectator_prefixes", ",".join(prefix_list))
    await interaction.response.send_message(
        f"팀섞기 관전자 접두사를 설정했습니다: {', '.join(f'[{p}]' for p in prefix_list)}",
        ephemeral=True,
    )

@bot.tree.command(name="팀섞기규칙확인", description="현재 관전자 제외 접두사를 확인합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def show_team_mix_rule(interaction: discord.Interaction):
    prefixes = get_spectator_prefixes(interaction.guild.id)
    await interaction.response.send_message(
        f"현재 관전자 접두사: {', '.join(f'[{p}]' for p in prefixes)}",
        ephemeral=True,
    )

@bot.tree.command(name="구인", description="배그 구인")
async def recruit(interaction: discord.Interaction, message: str):
    recruit_channel_id = get_guild_setting_channel_id(interaction.guild.id, "recruit_channel_id")
    if recruit_channel_id is None:
        await interaction.response.send_message("구인 채널이 아직 설정되지 않았습니다.", ephemeral=True)
        return
    if interaction.channel.id != recruit_channel_id:
        await interaction.response.send_message("구인 채널에서만 사용 가능합니다.", ephemeral=True)
        return
    if not interaction.user.voice:
        await interaction.response.send_message("음성채널 먼저 들어가세요.", ephemeral=True)
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


@bot.tree.command(name="종겜구인", description="원하는 게임으로 구인 글 작성")
async def general_recruit(interaction: discord.Interaction):
    await interaction.response.send_modal(GeneralRecruitModal())


@bot.tree.command(name="보급", description="배그 보급상자를 열어 결과에 따라 보상을 받습니다.")
async def supply_drop(interaction: discord.Interaction, amount: int):
    if amount < MIN_BET:
        await interaction.response.send_message(
            f"최소 배팅 금액은 `{format_money(MIN_BET)}`입니다.",
            ephemeral=True,
        )
        return

    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)

    embed = discord.Embed(
        title="📦 보급",
        description=(
            f"배팅 금액: `{format_money(amount)}`\n\n"
            "✈️ 하늘에서 보급이 떨어지고 있습니다...\n"
            "📦 상자를 열어 어떤 아이템을 챙길 수 있을지 확인하세요.\n\n"
            "가능한 결과:\n"
            "▫️ 빈 상자\n"
            "▫️ 1뚝\n"
            "▫️ 2뚝\n"
            "▫️ 3뚝\n"
            "▫️ 보급 총기 획득\n"
            "▫️ 풀세트 보급 대박\n\n"
            "버튼을 눌러 보급상자를 개봉하세요."
        ),
        color=0xF39C12,
    )

    await interaction.response.send_message(
        embed=embed,
        view=SupplyDropView(interaction.user.id, amount),
    )

@bot.tree.command(name="문의패널", description="문의/신고/건의 티켓 패널을 생성합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def inquiry_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="문의 안내",
        description="문의하기 입니다. 아래 항목을 선택해 주세요.",
        color=0x3498DB,
    )
    await interaction.channel.send(embed=embed, view=InquiryPanelView())
    await interaction.response.send_message("문의 패널 생성 완료", ephemeral=True)

@bot.tree.command(name="닉네임패널생성", description="닉네임 접두사 적용 패널을 생성합니다.")
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
            "접두사를 하나 이상 입력해주세요. 예: `📺관전중,🔴빨코,🟢초코`",
            ephemeral=True,
        )
        return

    if len(prefix_list) > 24:
        await interaction.response.send_message(
            "접두사는 최대 24개까지만 설정할 수 있습니다.",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title=menu_name,
        description="원하는 접두사를 선택해주세요.",
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

@bot.tree.command(name="확률표", description="현재 게임들의 확률과 배당을 확인합니다.")
async def probability_table(interaction: discord.Interaction):
    embed = discord.Embed(title="🎲 게임 확률표", color=0x3498DB)

    embed.add_field(
        name="슬롯",
        value=(
            "3개 동일: 약 4.34%\n"
            "7️⃣ 7️⃣ 7️⃣ : 약 0.72% / 12배\n"
            "💎 💎 💎 : 약 0.72% / 8배\n"
            "기타 3개 동일 : 각각 약 0.72% / 6배\n\n"
            "정확히 2개 일치: 약 45.52%\n"
            "7️⃣ 7️⃣ : 약 7.59% / 1.6배\n"
            "💎 💎 : 약 7.59% / 1.3배\n"
            "기타 2개 일치 : 각각 약 7.59% / 1.1배\n\n"
            "완전 꽝 : 약 50.14%"
        ),
        inline=False,
    )


    embed.add_field(
        name="동전",
        value="앞/뒤 50% 확률\n당첨 시 1.8배",
        inline=False,
    )

    embed.add_field(
        name="룰렛",
        value=(
            "🔴 빨강 34% / 2.5배\n"
            "🟡 노랑 25% / 3.4배\n"
            "🔵 파랑 19% / 4.4배\n"
            "⚫ 검정 13% / 6.5배\n"
            "🟢 초록 9% / 9.5배"
        ),
        inline=False,
    )

    embed.add_field(
        name="보급",
        value=(
            "빈 상자 38% / 0배\n"
            "1뚝 24% / 0.8배\n"
            "2뚝 17% / 1.0배\n"
            "3뚝 10% / 1.6배\n"
            "보급 총기 획득 8% / 2.8배\n"
            "풀세트 보급 대박 3% / 4.5배"
        ),
        inline=False,
    )

    embed.add_field(
        name="몰빵게임",
        value=(
            f"참가비 `{format_money(ALL_IN_COST)}`\n"
            "하루 동안 참가한 사람 중 1명 무작위 추첨\n"
            "그날 참가자들이 낸 금액 전부를 당첨자 1명이 가져갑니다."
        ),
        inline=False,
    )
  
    embed.add_field(
        name="덕몽",
        value=(
            "오리 33.33% / 2배 회수\n"
            "팰리컨 33.33% / 원금 반환\n"
            "거위 33.33% / 전부 잃음"
        ),
        inline=False,
    )


    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="족보", description="최근 게임 결과를 확인합니다.")
async def game_history_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📜 족보",
        description="확인할 게임을 선택해주세요.",
        color=0x5865F2,
    )
    await interaction.response.send_message(
        embed=embed,
        view=HistoryGameSelectView(interaction.guild.id),
        ephemeral=True,
    )


@bot.tree.command(name="몰빵참여", description="오늘의 몰빵게임에 참여합니다.")
async def join_all_in_game(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    today = get_today_kst_date_str()

    if has_all_in_entry(today, interaction.guild.id, interaction.user.id):
        await interaction.response.send_message("오늘은 이미 몰빵게임에 참여했습니다.", ephemeral=True)
        return

    if not can_afford(interaction.user.id, ALL_IN_COST):
        await interaction.response.send_message(
            f"몰빵게임 참가비 `{format_money(ALL_IN_COST)}`이 부족합니다.",
            ephemeral=True,
        )
        return

    add_balance(interaction.user.id, -ALL_IN_COST)
    add_all_in_entry(today, interaction.guild.id, interaction.user.id, ALL_IN_COST)

    entries = get_all_in_entries(today, interaction.guild.id)
    pool_amount = sum(amount for _, amount in entries)

    await interaction.response.send_message(
        f"{interaction.user.mention}님이 오늘의 몰빵게임에 참여했습니다.\n"
        f"참가비: `{format_money(ALL_IN_COST)}`\n"
        f"현재 참가자 수: `{len(entries)}명`\n"
        f"현재 누적 상금: `{format_money(pool_amount)}`"
    )


@bot.tree.command(name="돈지급내역", description="특정 인원의 돈지급 내역을 확인합니다.")
@app_commands.rename(member="인원")
@app_commands.describe(member="조회할 인원")
async def money_grant_history(interaction: discord.Interaction, member: discord.Member):
    rows = get_money_grant_logs(interaction.guild.id, member.id, 20)

    if not rows:
        await interaction.response.send_message("지급 내역이 없습니다.", ephemeral=True)
        return

    lines = []
    for giver_user_id, amount, created_at in rows:
        giver = interaction.guild.get_member(int(giver_user_id))
        giver_name = giver.display_name if giver else f"알 수 없는 유저 ({giver_user_id})"
        try:
            created_text = dt_from_db(created_at).strftime("%Y-%m-%d %H:%M")
        except Exception:
            created_text = created_at
        lines.append(f"[{created_text}] {giver_name} -> {format_money(amount)}")

    embed = discord.Embed(
        title=f"💸 {member.display_name}님의 돈지급 내역",
        description="\n".join(lines),
        color=0xF1C40F,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="일수", description="현재 신용등급 기준으로 대출을 받습니다.")
@app_commands.rename(amount="금액")
async def loan_money(interaction: discord.Interaction, amount: int):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("대출 금액은 1원 이상이어야 합니다.", ephemeral=True)
        return

    profile = get_credit_profile(interaction.user.id)
    active_loan = get_active_loan(interaction.user.id)

    if active_loan is not None:
        await interaction.response.send_message(
            "이미 상환되지 않은 대출이 있습니다. `/중도상환`으로 먼저 갚아주세요.",
            ephemeral=True,
        )
        return

    if profile["is_blacklisted"]:
        await interaction.response.send_message(
            "현재 신용불량자 상태입니다. 기존 대출을 모두 상환하기 전까지 새 대출이 불가능합니다.",
            ephemeral=True,
        )
        return

    grade = profile["grade"]
    max_amount = get_loan_limit_by_grade(grade)
    interest_rate = get_loan_interest_by_grade(grade)

    if amount > max_amount:
        await interaction.response.send_message(
            f"현재 {grade}등급의 최대 대출 가능 금액은 `{format_money(max_amount)}`입니다.",
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
        await interaction.response.send_message("현재 상환할 대출이 없습니다.", ephemeral=True)
        return

    repayment_amount = active_loan["total_repayment"]
    if not can_afford(interaction.user.id, repayment_amount):
        await interaction.response.send_message(
            f"상환 금액 `{format_money(repayment_amount)}`이 부족합니다.",
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
            name="등급 변동",
            value="기존 대출을 모두 상환하여 신용불량자 상태가 해제되고 6등급으로 복귀했습니다.",
            inline=False,
        )
    elif grade_up:
        embed.add_field(
            name="등급 변동",
            value="현재 등급의 최대 한도 이상 대출을 정상 상환하여 신용등급이 1단계 상승했습니다.",
            inline=False,
        )
    else:
        required_amount = get_loan_limit_by_grade(profile["grade"])
        embed.add_field(
            name="등급 변동",
            value=(
                "대출은 정상 상환되었지만 신용등급은 유지되었습니다.\n"
                f"등급 상승을 위해서는 현재 등급 기준 최대 한도인 `{format_money(required_amount)}` 이상 대출 후 상환해야 합니다."
            ),
            inline=False,
        )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="내신용", description="현재 신용등급과 대출 상태를 확인합니다.")
async def my_credit(interaction: discord.Interaction):
    profile = get_credit_profile(interaction.user.id)
    active_loan = get_active_loan(interaction.user.id)

    if profile["is_blacklisted"]:
        grade_text = "신용불량자"
        max_amount_text = "대출 불가"
        interest_text = "대출 불가"
    else:
        grade_text = f"{profile['grade']}등급"
        max_amount_text = format_money(get_loan_limit_by_grade(profile["grade"]))
        interest_text = f"{get_loan_interest_by_grade(profile['grade'])}%"

    embed = discord.Embed(title="📄 내 신용 정보", color=0x5865F2)
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

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="덕몽", description="덕몽어스 테마의 오리를 찾아라 게임입니다.")
async def duckmong(interaction: discord.Interaction, amount: int):
    if amount < MIN_BET:
        await interaction.response.send_message(
            f"최소 배팅 금액은 `{format_money(MIN_BET)}`입니다.",
            ephemeral=True,
        )
        return

    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)

    fake_names = random.sample(DUCKMONG_FAKE_NAMES, 3)
    hidden_roles = ["오리", "거위", "팰리컨"]
    random.shuffle(hidden_roles)
    hidden_results = {fake_name: hidden_roles[idx] for idx, fake_name in enumerate(fake_names)}

    embed = discord.Embed(
        title="🦆 오리를 찾아라",
        description=(
            f"배팅 금액: `{format_money(amount)}`\n\n"
            "세 직업 중 하나를 골라주세요.\n"
            "그 안에는 오리, 거위, 팰리컨이 하나씩 숨어 있습니다.\n\n"
            "오리: 배팅금액만큼 추가 획득\n"
            "거위: 전부 잃음\n"
            "팰리컨: 원금 반환"
        ),
        color=0xF1C40F,
    )

    await interaction.response.send_message(
        embed=embed,
        view=DuckmongView(interaction.user.id, amount, fake_names, hidden_results),
    )

@bot.tree.command(name="강화", description="현재 무기의 강화 정보와 강화 버튼을 확인합니다.")
async def upgrade_weapon(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    ensure_base_weapon(interaction.guild.id, interaction.user.id)

    embed = build_upgrade_embed(interaction.guild.id, interaction.user.id)
    view = WeaponUpgradeView(interaction.guild.id, interaction.user.id)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="무기판매", description="현재 보유 중인 무기를 판매합니다.")
async def sell_weapon(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    inventory = get_weapon_inventory(interaction.guild.id, interaction.user.id)
    current_level = inventory["weapon_level"]

    if current_level <= 0:
        await interaction.response.send_message("판매할 무기가 없습니다.", ephemeral=True)
        return

    weapon_name = get_weapon_name(current_level)
    sell_price = get_weapon_sell_price(current_level)

    add_balance(interaction.user.id, sell_price)
    set_weapon_level(interaction.guild.id, interaction.user.id, 0)

    embed = discord.Embed(title="💰 무기 판매 완료", color=0x2ECC71)
    embed.add_field(name="판매 무기", value=f"{current_level}강 {weapon_name}", inline=False)
    embed.add_field(name="판매 금액", value=format_money(sell_price), inline=False)
    embed.add_field(name="현재 잔액", value=format_money(get_balance(interaction.user.id)), inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="강화현황", description="현재 보유 중인 무기와 보호권 수량을 확인합니다.")
async def weapon_status(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    inventory = get_weapon_inventory(interaction.guild.id, interaction.user.id)
    current_level = inventory["weapon_level"]
    protection_count = inventory["protection_count"]

    embed = discord.Embed(title="📋 강화 현황", color=0x5865F2)

    if current_level <= 0:
        embed.add_field(name="현재 무기", value="없음", inline=False)
        embed.add_field(name="안내", value="`/강화`를 사용하면 1강 프라이팬이 자동 지급됩니다.", inline=False)
    else:
        embed.add_field(name="현재 무기", value=f"{current_level}강 {get_weapon_name(current_level)}", inline=False)
        embed.add_field(name="판매 가격", value=format_money(get_weapon_sell_price(current_level)), inline=False)

        if current_level < 21:
            embed.add_field(name="다음 강화 비용", value=format_money(get_upgrade_cost(current_level)), inline=False)
            embed.add_field(name="보호권 가격", value=format_money(get_protection_cost(current_level)), inline=False)
        else:
            embed.add_field(name="강화 상태", value="최대 강화 단계", inline=False)

    embed.add_field(name="보유 보호권", value=f"{protection_count}장", inline=False)
    embed.add_field(name="현재 잔액", value=format_money(get_balance(interaction.user.id)), inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="강화확률표", description="1강부터 21강까지 강화 확률, 비용, 보호권 가격을 확인합니다.")
async def weapon_upgrade_table(interaction: discord.Interaction):
    ranges = [
        (1, 7, "🔧 강화 확률표 (1강~7강)", 0x3498DB),
        (8, 14, "🔧 강화 확률표 (8강~14강)", 0x5865F2),
        (15, 21, "🔧 강화 확률표 (15강~21강)", 0x9B59B6),
    ]

    embeds = []

    for start, end, title, color in ranges:
        embed = discord.Embed(title=title, color=color)
        lines = []

        for level in range(start, end + 1):
            weapon_name = get_weapon_name(level)
            protection_cost = WEAPON_PROTECTION_COSTS.get(level)

            if level <= 20:
                cost = WEAPON_UPGRADE_COSTS.get(level)
                rates = WEAPON_UPGRADE_RATES.get(level)

                if cost is None or rates is None:
                    continue

                lines.append(
                    f"**{level}강 {weapon_name}**\n"
                    f"강화비용: `{format_money(cost)}`\n"
                    f"성공 {rates['success']}% / 하락 {rates['down']}% / 파괴 {rates['destroy']}% / 유지 {rates['keep']}%\n"
                    f"보호권: `{format_money(protection_cost)}`"
                )
            else:
                lines.append(
                    f"**{level}강 {weapon_name}**\n"
                    f"최대 강화 단계\n"
                    f"보호권: `{format_money(protection_cost)}`"
                )

        embed.description = "\n\n".join(lines)
        embeds.append(embed)

    await interaction.response.send_message(embeds=embeds, ephemeral=True)


@bot.tree.command(name="무기판매가격표", description="1강부터 21강까지 무기 판매 가격을 확인합니다.")
async def weapon_sell_price_table(interaction: discord.Interaction):
    embed1 = discord.Embed(title="💰 무기 판매 가격표 (1강~10강)", color=0x2ECC71)
    lines1 = []

    for level in range(1, 11):
        weapon_name = get_weapon_name(level)
        sell_price = get_weapon_sell_price(level)
        lines1.append(f"**{level}강 {weapon_name}** - `{format_money(sell_price)}`")

    embed1.description = "\n".join(lines1)

    embed2 = discord.Embed(title="💰 무기 판매 가격표 (11강~21강)", color=0x27AE60)
    lines2 = []

    for level in range(11, 22):
        weapon_name = get_weapon_name(level)
        sell_price = get_weapon_sell_price(level)
        lines2.append(f"**{level}강 {weapon_name}** - `{format_money(sell_price)}`")

    embed2.description = "\n".join(lines2)

    await interaction.response.send_message(embeds=[embed1, embed2], ephemeral=True)

@bot.tree.command(name="도박명령어", description="도박 및 재화 시스템 관련 명령어를 확인합니다.")
async def gambling_commands(interaction: discord.Interaction):
    embed = discord.Embed(title="🎰 도박 / 재화 시스템 명령어", color=0xF1C40F)

    embed.add_field(
        name="기본 재화",
        value=(
            "`/상생지원금` - 하루 지원금 받기\n"
            "`/잔액` - 현재 잔액 확인\n"
            "`/랭킹` - 자산 랭킹 확인\n"
            "`/송금` - 다른 유저에게 송금"
        ),
        inline=False,
    )

    embed.add_field(
        name="대출 / 신용",
        value=(
            "`/일수 [금액]` - 대출 받기\n"
            "`/중도상환` - 현재 대출 상환\n"
            "`/내신용` - 신용등급 및 대출 상태 확인"
        ),
        inline=False,
    )

    embed.add_field(
        name="도박 게임",
        value=(
            "`/슬롯 [금액]` - 슬롯머신\n"
            "`/동전 [금액]` - 동전 앞뒤 맞추기\n"
            "`/룰렛 [금액]` - 색상 배팅 룰렛\n"
            "`/보급 [금액]` - 보급상자 게임\n"
            "`/덕몽 [금액]` - 오리를 찾아라 야바위\n"
            "`/몰빵참여` - 몰빵게임 참여"
        ),
        inline=False,
    )

    embed.add_field(
        name="확률 / 기록",
        value=(
            "`/확률표` - 게임 확률과 배당 확인\n"
            "`/족보` - 최근 게임 결과 확인"
        ),
        inline=False,
    )

    embed.add_field(
        name="강화 시스템",
        value=(
            "`/강화` - 무기 강화 패널 열기\n"
            "`/강화현황` - 현재 무기 / 보호권 확인\n"
            "`/강화확률표` - 전체 강화 확률표 확인\n"
            "`/무기판매` - 현재 무기 판매\n"
            "`/무기판매가격표` - 전체 무기 판매 가격표 확인"
        ),
        inline=False,
    )

    embed.add_field(
        name="관리자 전용",
        value=(
            "`/돈지급` - 여러 유저에게 재화 지급\n"
            "`/돈지급내역` - 특정 유저 지급 내역 확인\n"
            "`/돈삭제` - 특정 유저 재화 차감"
        ),
        inline=False,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


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
                    rendered = rendered.replace("{role}", role.mention if role else "역할")
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
                        content=f"@here 📢 {member.mention}님이 대기방 {after.channel.mention}에 들어왔습니다."
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

            joined_text = "알 수 없음"
            if member.joined_at is not None:
                joined_text = member.joined_at.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S KST")

            embed = discord.Embed(
                title=f"⏰ 신입 역할 {probation_days}일 경과 알림",
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
                            title="🎂 오늘의 주인공 등장!",
                            description=f"오늘은 {member.mention}님의 생일입니다! 축하해주세요!",
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
                if "🎂" in member.display_name:
                    await member.edit(nick=member.display_name.replace(" 🎂", ""))
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
                f"{target_date} - 참가자 {len(rows)}명 / "
                f"유효 참가자 {len(valid_members)}명 / "
                f"당첨자 {winner.display_name} / "
                f"총 상금 {format_money(total_amount)}"
            )
            add_game_history(guild.id, ALL_IN_GAME_NAME, result_text)

            if target_channel is not None:
                embed = discord.Embed(
                    title="💥 몰빵게임 결과",
                    description=(
                        f"날짜: `{target_date}`\n"
                        f"전체 참가자 수: `{len(rows)}명`\n"
                        f"추첨 가능 인원: `{len(valid_members)}명`\n"
                        f"총 상금: `{format_money(total_amount)}`\n\n"
                        f"🏆 당첨자: {winner.mention}"
                    ),
                    color=0xF1C40F,
                )
                await target_channel.send(embed=embed)

            clear_all_in_entries(target_date, guild.id)

@tasks.loop(minutes=1)
async def loan_due_check_loop():
    now = get_kst_now()
    rows = get_due_loans(now)

    for loan_id, user_id, due_at in rows:
        mark_loan_overdue(loan_id)
        downgrade_credit_grade(int(user_id))



@bot.event
async def on_ready():
    for guild in bot.guilds:
        try:
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
        except Exception as e:
            print(f"길드 명령어 초기화 실패 ({guild.id}): {e}")

    await bot.tree.sync()

    bot.add_view(BirthdayView())
    bot.add_view(RuleConfirmView())
    bot.add_view(UpgradePanelView())
    bot.add_view(TimeRoleView())
    bot.add_view(InquiryPanelView())

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


    print("멀티서버 대응 마리봇 실행 완료")


bot.run(TOKEN)
