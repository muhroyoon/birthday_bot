import os
import math
import random
import sqlite3
import asyncio
import shutil
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
# 8. UI 뷰 / 모달
# 9. 슬래시 명령어
#    - 관리자 설정 명령어
#    - 재화 / 적금 명령어
#    - 게임 명령어
#    - 신용 / 대출 명령어
#    - 관리자 신용 관리 명령어
# 10. 디스코드 이벤트
# 11. 백그라운드 작업
# 12. 봇 시작 설정
# ============================================================


# ============================================================
# 기본 유틸리티
# ============================================================

def get_kst_now():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def dt_to_db(value: datetime) -> str:
    return value.isoformat()


def dt_from_db(value: str) -> datetime:
    return datetime.fromisoformat(value)


def parse_date_range(start_date: str | None, end_date: str | None, *, default_days: int = 30):
    now = get_kst_now()
    if not start_date and not end_date:
        return now - timedelta(days=default_days), now

    try:
        if start_date:
            start_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d").replace(tzinfo=ZoneInfo("Asia/Seoul"))
        else:
            start_dt = now - timedelta(days=default_days)

        if end_date:
            end_dt = datetime.strptime(end_date.strip(), "%Y-%m-%d").replace(tzinfo=ZoneInfo("Asia/Seoul"))
            end_dt = end_dt + timedelta(days=1) - timedelta(seconds=1)
        else:
            end_dt = now
    except ValueError:
        raise ValueError("날짜 형식은 YYYY-MM-DD 로 입력해주세요.")

    if end_dt < start_dt:
        raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")

    return start_dt, end_dt


TOKEN = os.getenv("TOKEN")

# ============================================================
# 전역 설정
# ============================================================

DAILY_REWARD = 10000
MIN_BET = 100
COIN_FLIP_TIMEOUT = 60
SEOTDA_TIMEOUT = 60
MAX_PLAYERS = 4
ALL_IN_GAME_NAME = "몰빵게임"
GAME_HISTORY_LIMIT = 10
MIN_CREDIT_GRADE = 1
MAX_CREDIT_GRADE = 10
INITIAL_CREDIT_GRADE = 10
LOAN_REPAYMENT_DAYS = 2
LOAN_LIMIT_RECOVERY_DELAY_MINUTES = 15
DEFAULT_SAVINGS_DAYS = "3"
DEFAULT_SAVINGS_INTEREST_RATE = "10"
DEFAULT_LABOR_DEBT_AMOUNT = 100_000
LOAN_GRADE_DECAY_DAYS = 2

LABOR_GACHA_RESULTS = [
    ("꽝", 0, 1800),
    ("-10%", 10, 1199),
    ("-20%", 20, 600),
    ("-30%", 30, 250),
    ("-40%", 40, 100),
    ("-50%", 50, 30),
    ("-60%", 60, 12),
    ("-70%", 70, 5),
    ("-80%", 80, 2),
    ("-90%", 90, 1),
    ("-100%", 100, 1),
]

LOAN_GRADE_LIMITS = {
    1: 20_000_000,
    2: 15_000_000,
    3: 10_000_000,
    4: 6_000_000,
    5: 4_000_000,
    6: 2_500_000,
    7: 1_500_000,
    8: 1_000_000,
    9: 500_000,
    10: 300_000,
}

LOAN_GRADE_INTEREST = {
    1: 3,
    2: 5,
    3: 7,
    4: 9,
    5: 11,
    6: 13,
    7: 15,
    8: 17,
    9: 19,
    10: 20,
}

labor_click_locks: set[tuple[int, int]] = set()

SLOT_SYMBOL_EMOJIS = {
    "체리": "🍒",
    "레몬": "🍋",
    "포도": "🍇",
    "사과": "🍎",
    "클로버": "🍀",
    "7": "7️⃣",
}

DUCKMONG_FAKE_NAMES = [
    "보안관",
    "자경단",
    "캐나다거위",
    "차원여행자",
    "연예인",
    "한탕주의자",
]

SEOTDA_SPECIAL_RANKS = {
    (1, 2): ("알리", 8000),
    (1, 4): ("독사", 7990),
    (1, 9): ("구삥", 7980),
    (1, 10): ("장삥", 7970),
    (4, 10): ("장사", 7960),
    (4, 6): ("세륙", 7950),
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
    "등업 요청 패널입니다.\n\n"
    "1. 닉네임 변경\n"
    "2. 자기소개 작성\n"
    "3. 규칙 확인\n"
    "4. 출석 체크\n\n"
    "완료하셨다면 아래 버튼을 눌러주세요."
)
DEFAULT_WELCOME_DM_TEXT = (
    "안녕하세요 {user}님, 서버에 오신 것을 환영합니다.\n"
    "서버 안내는 {guide_channel} 채널에 정리되어 있습니다.\n"
    "궁금한 점이 있으면 관리자에게 문의해주세요!"
)
DEFAULT_PROBATION_NOTICE_TEXT = (
    "신입 역할 부여 후 7일이 지났습니다.\n"
    "출석과 활동량을 확인하시고 역할 유지 여부를 검토해주세요."
)
DEFAULT_PROBATION_DAYS = "7"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
active_recruits = {}
playlist_queues: dict[int, list[dict]] = {}
playlist_now_playing: dict[int, dict] = {}
playlist_text_channels: dict[int, int] = {}
playlist_previous_tracks: dict[int, dict] = {}
playlist_library_cache: dict[int, list[dict]] = {}
playlist_modes: dict[int, str] = {}
playlist_panel_messages: dict[int, tuple[int, int]] = {}

# ============================================================
# 데이터베이스 초기화
# ============================================================

conn = sqlite3.connect("/data/birthday.db")
cursor = conn.cursor()

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
        note TEXT,
        created_at TEXT NOT NULL
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS transfer_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        sender_user_id TEXT NOT NULL,
        receiver_user_id TEXT NOT NULL,
        amount INTEGER NOT NULL,
        note TEXT,
        created_at TEXT NOT NULL
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS hidden_gambling_forces(
        user_id TEXT PRIMARY KEY,
        game_name TEXT NOT NULL,
        force_value TEXT,
        remaining_count INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS credit_profiles(
        user_id TEXT PRIMARY KEY,
        grade INTEGER NOT NULL DEFAULT 10,
        is_blacklisted INTEGER NOT NULL DEFAULT 0,
        blacklisted_at TEXT,
        last_loan_used_at TEXT,
        loan_progress_amount INTEGER NOT NULL DEFAULT 0
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
    CREATE TABLE IF NOT EXISTS loan_limit_holds(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        amount INTEGER NOT NULL,
        available_at TEXT NOT NULL,
        created_at TEXT NOT NULL
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
    CREATE TABLE IF NOT EXISTS labor_gacha_tickets(
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        ticket_count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (guild_id, user_id)
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS manual_credit_debts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        amount INTEGER NOT NULL,
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        resolved_at TEXT
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS promissory_notes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        lender_user_id TEXT NOT NULL,
        borrower_user_id TEXT NOT NULL,
        amount INTEGER NOT NULL,
        principal_amount INTEGER NOT NULL DEFAULT 0,
        interest_amount INTEGER NOT NULL DEFAULT 0,
        due_text TEXT NOT NULL,
        note TEXT,
        channel_id TEXT,
        message_id TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        resolved_at TEXT
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
if "last_loan_used_at" not in credit_profile_columns:
    cursor.execute("ALTER TABLE credit_profiles ADD COLUMN last_loan_used_at TEXT")
    cursor.execute(
        "UPDATE credit_profiles SET last_loan_used_at=? WHERE last_loan_used_at IS NULL",
        (dt_to_db(get_kst_now()),),
    )
    conn.commit()
if "loan_progress_amount" not in credit_profile_columns:
    cursor.execute("ALTER TABLE credit_profiles ADD COLUMN loan_progress_amount INTEGER NOT NULL DEFAULT 0")
    conn.commit()

cursor.execute("PRAGMA table_info(loans)")
loan_columns = [row[1] for row in cursor.fetchall()]
if "remaining_principal" not in loan_columns:
    cursor.execute("ALTER TABLE loans ADD COLUMN remaining_principal INTEGER NOT NULL DEFAULT 0")
    cursor.execute(
        """
        UPDATE loans
        SET remaining_principal=
            CASE
                WHEN status IN ('active', 'overdue') THEN principal
                ELSE 0
            END
        WHERE remaining_principal=0
        """
    )
    conn.commit()

if "remaining_total_repayment" not in loan_columns:
    cursor.execute("ALTER TABLE loans ADD COLUMN remaining_total_repayment INTEGER NOT NULL DEFAULT 0")
    cursor.execute(
        """
        UPDATE loans
        SET remaining_total_repayment=
            CASE
                WHEN status IN ('active', 'overdue') THEN total_repayment
                ELSE 0
            END
        WHERE remaining_total_repayment=0
        """
    )
    conn.commit()

cursor.execute("PRAGMA table_info(money_grant_logs)")
money_grant_log_columns = [row[1] for row in cursor.fetchall()]

if "note" not in money_grant_log_columns:
    cursor.execute("ALTER TABLE money_grant_logs ADD COLUMN note TEXT")
    conn.commit()

cursor.execute("PRAGMA table_info(promissory_notes)")
promissory_note_columns = [row[1] for row in cursor.fetchall()]

if "principal_amount" not in promissory_note_columns:
    cursor.execute("ALTER TABLE promissory_notes ADD COLUMN principal_amount INTEGER NOT NULL DEFAULT 0")
if "interest_amount" not in promissory_note_columns:
    cursor.execute("ALTER TABLE promissory_notes ADD COLUMN interest_amount INTEGER NOT NULL DEFAULT 0")

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS team_mix_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        message_id TEXT,
        channel_id TEXT NOT NULL,
        team_size INTEGER NOT NULL,
        team_label TEXT NOT NULL,
        members_text TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """
)

cursor.execute("PRAGMA table_info(team_mix_logs)")
team_mix_log_columns = [row[1] for row in cursor.fetchall()]

if "message_id" not in team_mix_log_columns:
    cursor.execute("ALTER TABLE team_mix_logs ADD COLUMN message_id TEXT")
    conn.commit()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS voice_channel_sessions(
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        started_at TEXT NOT NULL,
        PRIMARY KEY (guild_id, user_id)
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS voice_channel_logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        started_at TEXT NOT NULL,
        ended_at TEXT NOT NULL,
        duration_seconds INTEGER NOT NULL
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS playlist_tracks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id TEXT NOT NULL,
        owner_user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """
)

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


def format_duration_korean(total_seconds: int) -> str:
    hours, remainder = divmod(max(0, total_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(f"{hours}시간")
    if minutes:
        parts.append(f"{minutes}분")
    if seconds or not parts:
        parts.append(f"{seconds}초")
    return " ".join(parts)

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


def format_history_result_text(result_text: str) -> str:
    if " - " in result_text:
        actor, detail_text = result_text.split(" - ", 1)
        detail_parts = [part.strip() for part in detail_text.split(" / ") if part.strip()]
        lines = [f"플레이어: **{actor}**"]
        lines.extend(f"• {part}" for part in detail_parts)
        return "\n".join(lines)

    detail_parts = [part.strip() for part in result_text.split(" / ") if part.strip()]
    if len(detail_parts) >= 2:
        return "\n".join(f"• {part}" for part in detail_parts)
    return result_text


def join_discord_field_lines(lines: list[str], *, limit: int = 1024) -> str:
    selected_lines = []
    current_length = 0

    for line in lines:
        separator_length = 2 if selected_lines else 0
        next_length = current_length + separator_length + len(line)
        if next_length > limit:
            remaining_count = len(lines) - len(selected_lines)
            suffix = f"\n\n외 {remaining_count}개 기록이 더 있습니다."
            while selected_lines and current_length + len(suffix) > limit:
                removed = selected_lines.pop()
                current_length -= len(removed)
                if selected_lines:
                    current_length -= 2
            return ("\n\n".join(selected_lines) + suffix)[:limit]

        selected_lines.append(line)
        current_length = next_length

    return "\n\n".join(selected_lines) if selected_lines else "표시할 기록이 없습니다."


def join_compact_discord_field_lines(lines: list[str], *, limit: int = 1024) -> str:
    selected_lines = []
    current_length = 0

    for line in lines:
        separator_length = 1 if selected_lines else 0
        next_length = current_length + separator_length + len(line)
        if next_length > limit:
            remaining_count = len(lines) - len(selected_lines)
            suffix = f"\n외 {remaining_count}개 기록이 더 있습니다."
            while selected_lines and current_length + len(suffix) > limit:
                removed = selected_lines.pop()
                current_length -= len(removed)
                if selected_lines:
                    current_length -= 1
            return ("\n".join(selected_lines) + suffix)[:limit]

        selected_lines.append(line)
        current_length = next_length

    return "\n".join(selected_lines) if selected_lines else "표시할 기록이 없습니다."


def add_money_grant_log(guild_id: int, target_user_id: int, giver_user_id: int, amount: int, note: str | None = None):
    cursor.execute(
        """
        INSERT INTO money_grant_logs(guild_id, target_user_id, giver_user_id, amount, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(guild_id), str(target_user_id), str(giver_user_id), amount, note, dt_to_db(get_kst_now())),
    )
    conn.commit()


def get_money_grant_logs(guild_id: int, target_user_id: int, limit: int = 20):
    cursor.execute(
        """
        SELECT giver_user_id, amount, note, created_at
        FROM money_grant_logs
        WHERE guild_id=? AND target_user_id=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (str(guild_id), str(target_user_id), limit),
    )
    return cursor.fetchall()


def add_transfer_log(
    guild_id: int,
    sender_user_id: int,
    receiver_user_id: int,
    amount: int,
    note: str | None = None,
):
    cursor.execute(
        """
        INSERT INTO transfer_logs(guild_id, sender_user_id, receiver_user_id, amount, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(guild_id), str(sender_user_id), str(receiver_user_id), amount, note, dt_to_db(get_kst_now())),
    )
    conn.commit()


def get_transfer_logs(guild_id: int, receiver_user_id: int, limit: int = 20):
    cursor.execute(
        """
        SELECT sender_user_id, amount, note, created_at
        FROM transfer_logs
        WHERE guild_id=? AND receiver_user_id=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (str(guild_id), str(receiver_user_id), limit),
    )
    return cursor.fetchall()


def is_bot_guild_owner(user_id: int) -> bool:
    return any(guild.owner_id == user_id for guild in bot.guilds)


def set_hidden_gambling_force(user_id: int, game_name: str, force_value: str | None = None, remaining_count: int = 1):
    cursor.execute(
        """
        INSERT OR REPLACE INTO hidden_gambling_forces(user_id, game_name, force_value, remaining_count, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (str(user_id), game_name, force_value, remaining_count, dt_to_db(get_kst_now())),
    )
    conn.commit()


def get_hidden_gambling_force(user_id: int):
    cursor.execute(
        """
        SELECT user_id, game_name, force_value, remaining_count, created_at
        FROM hidden_gambling_forces
        WHERE user_id=? AND remaining_count > 0
        """,
        (str(user_id),),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "user_id": int(row[0]),
        "game_name": row[1],
        "force_value": row[2] or "",
        "remaining_count": int(row[3]),
        "created_at": row[4],
    }


def clear_hidden_gambling_force(user_id: int):
    cursor.execute("DELETE FROM hidden_gambling_forces WHERE user_id=?", (str(user_id),))
    conn.commit()


def consume_hidden_gambling_force(user_id: int):
    force_info = get_hidden_gambling_force(user_id)
    if force_info is None:
        return None

    if force_info["remaining_count"] <= 1:
        clear_hidden_gambling_force(user_id)
    else:
        cursor.execute(
            "UPDATE hidden_gambling_forces SET remaining_count=remaining_count-1 WHERE user_id=?",
            (str(user_id),),
        )
        conn.commit()

    return force_info


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
        INSERT OR IGNORE INTO credit_profiles(user_id, grade, is_blacklisted, last_loan_used_at, loan_progress_amount)
        VALUES (?, ?, 0, ?, 0)
        """,
        (str(user_id), INITIAL_CREDIT_GRADE, dt_to_db(get_kst_now())),
    )
    cursor.execute(
        """
        UPDATE credit_profiles
        SET last_loan_used_at=COALESCE(last_loan_used_at, ?)
        WHERE user_id=?
        """,
        (dt_to_db(get_kst_now()), str(user_id)),
    )
    conn.commit()


def get_credit_profile(user_id: int):
    ensure_credit_profile(user_id)
    cursor.execute(
        "SELECT grade, is_blacklisted, blacklisted_at, last_loan_used_at, loan_progress_amount FROM credit_profiles WHERE user_id=?",
        (str(user_id),),
    )
    row = cursor.fetchone()
    if not row:
        return {
            "grade": INITIAL_CREDIT_GRADE,
            "is_blacklisted": False,
            "blacklisted_at": None,
            "last_loan_used_at": None,
            "loan_progress_amount": 0,
        }

    return {
        "grade": int(row[0]),
        "is_blacklisted": bool(row[1]),
        "blacklisted_at": row[2],
        "last_loan_used_at": row[3],
        "loan_progress_amount": int(row[4] or 0),
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
    grade = max(MIN_CREDIT_GRADE, min(MAX_CREDIT_GRADE, grade))
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


def update_last_loan_used_at(user_id: int, used_at: datetime | None = None):
    ensure_credit_profile(user_id)
    target_time = used_at or get_kst_now()
    cursor.execute(
        "UPDATE credit_profiles SET last_loan_used_at=? WHERE user_id=?",
        (dt_to_db(target_time), str(user_id)),
    )
    conn.commit()


def add_loan_progress_amount(user_id: int, amount: int):
    ensure_credit_profile(user_id)
    cursor.execute(
        "UPDATE credit_profiles SET loan_progress_amount=MAX(0, loan_progress_amount + ?) WHERE user_id=?",
        (amount, str(user_id)),
    )
    conn.commit()


def reset_loan_progress_amount(user_id: int):
    ensure_credit_profile(user_id)
    cursor.execute(
        "UPDATE credit_profiles SET loan_progress_amount=0 WHERE user_id=?",
        (str(user_id),),
    )
    conn.commit()


def upgrade_credit_grade(user_id: int):
    profile = get_credit_profile(user_id)

    if profile["is_blacklisted"]:
        set_credit_blacklisted(user_id, False)
        set_credit_grade(user_id, INITIAL_CREDIT_GRADE)
        reset_loan_progress_amount(user_id)
        return

    set_credit_grade(user_id, profile["grade"] - 1)
    reset_loan_progress_amount(user_id)


def downgrade_credit_grade(user_id: int):
    profile = get_credit_profile(user_id)

    if profile["grade"] >= MAX_CREDIT_GRADE:
        set_credit_grade(user_id, MAX_CREDIT_GRADE)
        set_credit_blacklisted(user_id, True)
        reset_loan_progress_amount(user_id)
        return

    set_credit_grade(user_id, profile["grade"] + 1)
    reset_loan_progress_amount(user_id)


def downgrade_credit_grade_for_inactivity(user_id: int) -> bool:
    profile = get_credit_profile(user_id)
    if profile["is_blacklisted"]:
        return False

    if profile["grade"] >= MAX_CREDIT_GRADE:
        return False

    set_credit_grade(user_id, profile["grade"] + 1)
    reset_loan_progress_amount(user_id)
    return True


def get_credit_grade_text(user_id: int) -> str:
    profile = get_credit_profile(user_id)
    if profile["is_blacklisted"]:
        return "신용불량자"
    return f"{profile['grade']}등급"


def get_loan_limit_by_grade(grade: int) -> int:
    return LOAN_GRADE_LIMITS.get(grade, LOAN_GRADE_LIMITS[MAX_CREDIT_GRADE])


def get_loan_interest_by_grade(grade: int) -> int:
    return LOAN_GRADE_INTEREST.get(grade, LOAN_GRADE_INTEREST[MAX_CREDIT_GRADE])


def calculate_total_repayment(principal: int, interest_rate: int) -> int:
    return int(principal * (100 + interest_rate) / 100)


def get_active_loans(user_id: int):
    cursor.execute(
        """
        SELECT id, guild_id, principal, interest_rate, total_repayment, remaining_principal,
               remaining_total_repayment, borrowed_at, due_at, status
        FROM loans
        WHERE user_id=? AND status IN ('active', 'overdue')
        ORDER BY id DESC
        """,
        (str(user_id),),
    )
    rows = cursor.fetchall()
    loans = []
    for row in rows:
        loans.append(
            {
                "id": row[0],
                "guild_id": row[1],
                "principal": row[2],
                "interest_rate": row[3],
                "total_repayment": row[4],
                "remaining_principal": row[5],
                "remaining_total_repayment": row[6],
                "borrowed_at": row[7],
                "due_at": row[8],
                "status": row[9],
            }
        )
    return loans


def get_active_loan(user_id: int):
    loans = get_active_loans(user_id)
    return loans[0] if loans else None


def get_total_active_loan_principal(user_id: int) -> int:
    return sum(loan["remaining_principal"] for loan in get_active_loans(user_id))


def get_total_active_loan_repayment(user_id: int) -> int:
    return sum(loan["remaining_total_repayment"] for loan in get_active_loans(user_id))


def get_loan_by_id(loan_id: int):
    cursor.execute(
        """
        SELECT id, guild_id, user_id, principal, interest_rate, total_repayment, remaining_principal,
               remaining_total_repayment, borrowed_at, due_at, repaid_at, status
        FROM loans
        WHERE id=?
        """,
        (loan_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "id": int(row[0]),
        "guild_id": row[1],
        "user_id": int(row[2]),
        "principal": int(row[3]),
        "interest_rate": int(row[4]),
        "total_repayment": int(row[5]),
        "remaining_principal": int(row[6]),
        "remaining_total_repayment": int(row[7]),
        "borrowed_at": row[8],
        "due_at": row[9],
        "repaid_at": row[10],
        "status": row[11],
    }


def add_loan_limit_hold(user_id: int, amount: int, available_at: datetime | None = None):
    if amount <= 0:
        return

    target_time = available_at or (get_kst_now() + timedelta(minutes=LOAN_LIMIT_RECOVERY_DELAY_MINUTES))
    cursor.execute(
        """
        INSERT INTO loan_limit_holds(user_id, amount, available_at, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (str(user_id), amount, dt_to_db(target_time), dt_to_db(get_kst_now())),
    )
    conn.commit()


def clear_expired_loan_limit_holds(user_id: int):
    cursor.execute(
        "DELETE FROM loan_limit_holds WHERE user_id=? AND available_at<=?",
        (str(user_id), dt_to_db(get_kst_now())),
    )
    conn.commit()


def get_pending_loan_limit_hold_amount(user_id: int) -> int:
    clear_expired_loan_limit_holds(user_id)
    cursor.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM loan_limit_holds
        WHERE user_id=? AND available_at>?
        """,
        (str(user_id), dt_to_db(get_kst_now())),
    )
    row = cursor.fetchone()
    return int(row[0] or 0)


def get_next_loan_limit_release_at(user_id: int):
    clear_expired_loan_limit_holds(user_id)
    cursor.execute(
        """
        SELECT MIN(available_at)
        FROM loan_limit_holds
        WHERE user_id=? AND available_at>?
        """,
        (str(user_id), dt_to_db(get_kst_now())),
    )
    row = cursor.fetchone()
    return row[0] if row and row[0] else None


def create_manual_credit_debt(guild_id: int, user_id: int, amount: int, reason: str):
    cursor.execute(
        """
        INSERT INTO manual_credit_debts(guild_id, user_id, amount, reason, status, created_at)
        VALUES (?, ?, ?, ?, 'active', ?)
        """,
        (str(guild_id), str(user_id), amount, reason, dt_to_db(get_kst_now())),
    )
    conn.commit()
    return cursor.lastrowid


def get_active_manual_credit_debts(guild_id: int, user_id: int):
    cursor.execute(
        """
        SELECT id, amount, reason, created_at
        FROM manual_credit_debts
        WHERE guild_id=? AND user_id=? AND status='active'
        ORDER BY id DESC
        """,
        (str(guild_id), str(user_id)),
    )
    rows = cursor.fetchall()
    return [
        {
            "id": int(row[0]),
            "amount": int(row[1]),
            "reason": row[2] or "",
            "created_at": row[3],
        }
        for row in rows
    ]


def get_manual_credit_debt(debt_id: int):
    cursor.execute(
        """
        SELECT id, guild_id, user_id, amount, reason, status, created_at, resolved_at
        FROM manual_credit_debts
        WHERE id=?
        """,
        (debt_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "id": int(row[0]),
        "guild_id": row[1],
        "user_id": int(row[2]),
        "amount": int(row[3]),
        "reason": row[4] or "",
        "status": row[5],
        "created_at": row[6],
        "resolved_at": row[7],
    }


def get_total_active_manual_credit_debt(guild_id: int, user_id: int) -> int:
    cursor.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM manual_credit_debts
        WHERE guild_id=? AND user_id=? AND status='active'
        """,
        (str(guild_id), str(user_id)),
    )
    row = cursor.fetchone()
    return int(row[0] or 0)


def resolve_manual_credit_debts(guild_id: int, user_id: int):
    cursor.execute(
        """
        UPDATE manual_credit_debts
        SET status='resolved', resolved_at=?
        WHERE guild_id=? AND user_id=? AND status='active'
        """,
        (dt_to_db(get_kst_now()), str(guild_id), str(user_id)),
    )
    conn.commit()


def resolve_manual_credit_debt(debt_id: int):
    cursor.execute(
        """
        UPDATE manual_credit_debts
        SET status='resolved', resolved_at=?
        WHERE id=? AND status='active'
        """,
        (dt_to_db(get_kst_now()), debt_id),
    )
    conn.commit()


def get_total_credit_obligation(guild_id: int | None, user_id: int) -> int:
    total = get_total_active_loan_repayment(user_id)
    if guild_id is not None:
        total += get_total_active_manual_credit_debt(guild_id, user_id)
    return total


def get_remaining_loan_limit(user_id: int) -> int:
    profile = get_credit_profile(user_id)
    if profile["is_blacklisted"]:
        return 0

    grade_limit = get_loan_limit_by_grade(profile["grade"])
    used_limit = get_total_active_loan_principal(user_id)
    pending_hold = get_pending_loan_limit_hold_amount(user_id)
    return max(0, grade_limit - used_limit - pending_hold)


def create_loan(guild_id: int, user_id: int, principal: int, interest_rate: int, total_repayment: int, borrowed_at: datetime, due_at: datetime):
    cursor.execute(
        """
        INSERT INTO loans(
            guild_id, user_id, principal, interest_rate, total_repayment, remaining_principal, remaining_total_repayment,
            borrowed_at, due_at, status, delinquency_processed
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 0)
        """,
        (
            str(guild_id),
            str(user_id),
            principal,
            interest_rate,
            total_repayment,
            principal,
            total_repayment,
            dt_to_db(borrowed_at),
            dt_to_db(due_at),
        ),
    )
    conn.commit()
    update_last_loan_used_at(user_id, borrowed_at)
    add_loan_progress_amount(user_id, principal)


def repay_loans(loan_ids: list[int]):
    if not loan_ids:
        return

    loan_rows = [get_loan_by_id(loan_id) for loan_id in loan_ids]
    for loan in loan_rows:
        if loan is None:
            continue
        add_loan_limit_hold(loan["user_id"], loan["remaining_principal"])

    cursor.executemany(
        """
        UPDATE loans
        SET status='repaid', repaid_at=?, delinquency_processed=1, remaining_principal=0, remaining_total_repayment=0
        WHERE id=?
        """,
        [(dt_to_db(get_kst_now()), loan_id) for loan_id in loan_ids],
    )
    conn.commit()


def repay_loan(loan_id: int):
    repay_loans([loan_id])


def repay_loan_amount(loan_id: int, amount: int):
    loan = get_loan_by_id(loan_id)
    if loan is None or loan["status"] not in {"active", "overdue"}:
        return None

    remaining_total = loan["remaining_total_repayment"]
    remaining_principal = loan["remaining_principal"]
    payment_amount = max(0, min(amount, remaining_total))
    if payment_amount <= 0:
        return None

    new_remaining_total = remaining_total - payment_amount
    if new_remaining_total <= 0:
        principal_recovered = remaining_principal
        add_loan_limit_hold(loan["user_id"], principal_recovered)
        cursor.execute(
            """
            UPDATE loans
            SET remaining_principal=0,
                remaining_total_repayment=0,
                status='repaid',
                repaid_at=?,
                delinquency_processed=1
            WHERE id=?
            """,
            (dt_to_db(get_kst_now()), loan_id),
        )
    else:
        new_remaining_principal = math.ceil(new_remaining_total * loan["principal"] / loan["total_repayment"])
        principal_recovered = max(0, remaining_principal - new_remaining_principal)
        add_loan_limit_hold(loan["user_id"], principal_recovered)
        cursor.execute(
            """
            UPDATE loans
            SET remaining_principal=?,
                remaining_total_repayment=?
            WHERE id=?
            """,
            (new_remaining_principal, new_remaining_total, loan_id),
        )

    conn.commit()
    return {
        "loan": loan,
        "payment_amount": payment_amount,
        "principal_recovered": principal_recovered,
        "fully_repaid": new_remaining_total <= 0,
        "remaining_total_repayment": max(0, new_remaining_total),
    }


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
        SELECT id, guild_id, user_id, remaining_total_repayment, due_at
        FROM loans
        WHERE status='active' AND delinquency_processed=0 AND due_at<=?
        ORDER BY id ASC
        """,
        (dt_to_db(now),),
    )
    return cursor.fetchall()


def refresh_active_labor_penalty_debt(guild_id: int, user_id: int):
    penalty = get_active_labor_penalty(guild_id, user_id)
    total_debt_amount = get_total_credit_obligation(guild_id, user_id) or DEFAULT_LABOR_DEBT_AMOUNT

    if penalty is None:
        profile = get_credit_profile(user_id)
        if profile["is_blacklisted"]:
            create_or_replace_labor_penalty(guild_id, user_id, total_debt_amount)
            return get_active_labor_penalty(guild_id, user_id)
        return None

    new_required_count = calculate_labor_required_count(total_debt_amount)
    cursor.execute(
        """
        UPDATE labor_penalties
        SET debt_amount=?, required_count=?
        WHERE guild_id=? AND user_id=? AND status='active'
        """,
        (total_debt_amount, new_required_count, str(guild_id), str(user_id)),
    )
    conn.commit()

    updated = get_active_labor_penalty(guild_id, user_id)
    if updated is None:
        return None

    updated, _resolved = resolve_labor_penalty_if_complete(guild_id, user_id, updated)
    return updated


def get_credit_profiles_due_for_decay(now: datetime):
    cursor.execute(
        """
        SELECT user_id, grade, last_loan_used_at
        FROM credit_profiles
        WHERE is_blacklisted=0 AND last_loan_used_at IS NOT NULL
        ORDER BY user_id ASC
        """
    )
    return cursor.fetchall()


def build_credit_embed(member: discord.abc.User, guild_id: int | None = None) -> discord.Embed:
    profile = get_credit_profile(member.id)
    active_loans = get_active_loans(member.id)
    manual_debts = get_active_manual_credit_debts(guild_id, member.id) if guild_id is not None else []
    manual_debt_total = get_total_active_manual_credit_debt(guild_id, member.id) if guild_id is not None else 0
    labor_penalty = ensure_active_labor_penalty(guild_id, member.id) if guild_id is not None else None

    if profile["is_blacklisted"]:
        grade_text = "신용불량자"
        max_amount_text = "대출 불가"
        interest_text = "대출 불가"
        remaining_limit_text = "대출 불가"
    else:
        grade_text = f"{profile['grade']}등급"
        max_amount_text = format_money(get_loan_limit_by_grade(profile["grade"]))
        interest_text = f"{get_loan_interest_by_grade(profile['grade'])}%"
        remaining_limit_text = format_money(get_remaining_loan_limit(member.id))
        progress_target_text = format_money(get_loan_limit_by_grade(profile["grade"]))
    pending_hold_amount = get_pending_loan_limit_hold_amount(member.id)
    next_limit_release_at = get_next_loan_limit_release_at(member.id)

    embed = discord.Embed(title=f"📋 {member.display_name}님의 신용 정보", color=0x5865F2)
    embed.add_field(name="현재 신용등급", value=grade_text, inline=False)
    embed.add_field(name="최대 대출 가능 금액", value=max_amount_text, inline=True)
    embed.add_field(name="현재 대출 이자율", value=interest_text, inline=True)
    embed.add_field(name="남은 대출 한도", value=remaining_limit_text, inline=True)
    embed.add_field(name="현재 잔액", value=format_money(get_balance(member.id)), inline=False)
    if pending_hold_amount > 0:
        release_text = "확인 불가"
        if next_limit_release_at:
            try:
                release_text = dt_from_db(next_limit_release_at).strftime("%Y-%m-%d %H:%M:%S KST")
            except Exception:
                release_text = next_limit_release_at
        embed.add_field(
            name="한도 회복 대기 금액",
            value=f"{format_money(pending_hold_amount)}\n회복 예정: `{release_text}`",
            inline=False,
        )
    if profile["is_blacklisted"]:
        embed.add_field(name="등급 상승 누적 실적", value="신용불량자 상태에서는 집계되지 않습니다.", inline=False)
    else:
        embed.add_field(
            name="등급 상승 누적 실적",
            value=f"{format_money(profile['loan_progress_amount'])} / {progress_target_text}",
            inline=False,
        )
    if profile["last_loan_used_at"]:
        try:
            last_loan_used_text = dt_from_db(profile["last_loan_used_at"]).strftime("%Y-%m-%d %H:%M:%S KST")
        except Exception:
            last_loan_used_text = profile["last_loan_used_at"]
        embed.add_field(name="마지막 대출 사용 시각", value=last_loan_used_text, inline=False)

    if not active_loans and manual_debt_total <= 0:
        embed.add_field(name="현재 대출 상태", value="진행 중인 대출/벌금 없음", inline=False)
    else:
        latest_loan = active_loans[0] if active_loans else None
        latest_due_text = ""
        if latest_loan is not None:
            latest_due_text = latest_loan["due_at"]
            try:
                latest_due_text = dt_from_db(latest_loan["due_at"]).strftime("%Y-%m-%d %H:%M:%S KST")
            except Exception:
                pass

        embed.add_field(name="진행 중인 대출 수", value=f"{len(active_loans)}건", inline=True)
        embed.add_field(
            name="남은 원금 합계",
            value=format_money(sum(loan["principal"] for loan in active_loans)),
            inline=True,
        )
        embed.add_field(
            name="총 상환 금액 합계",
            value=format_money(sum(loan["total_repayment"] for loan in active_loans)),
            inline=True,
        )
        embed.add_field(name="관리자 부채 합계", value=format_money(manual_debt_total), inline=False)

        if latest_loan is not None:
            embed.add_field(
                name="가장 최근 대출 상태",
                value=f"{latest_loan['status']} / {latest_due_text}",
                inline=False,
            )
            loan_lines = []
            for idx, loan in enumerate(active_loans[:10], start=1):
                loan_lines.append(
                    f"#{loan['id']} 원금 `{format_money(loan['remaining_principal'])}` / 상환 `{format_money(loan['remaining_total_repayment'])}` / {loan['status']}"
                )
            embed.add_field(name="진행 중인 대출 내역", value="\n".join(loan_lines), inline=False)

        if manual_debts:
            debt_lines = []
            for debt in manual_debts[:10]:
                reason_text = debt["reason"] if debt["reason"] else "사유 없음"
                debt_lines.append(
                    f"{debt['id']}. `{format_money(debt['amount'])}` / 사유: {reason_text}"
                )
            embed.add_field(name="관리자 부채 내역", value="\n".join(debt_lines), inline=False)

    if labor_penalty is not None:
        remaining = max(0, labor_penalty["required_count"] - labor_penalty["completed_count"])
        ticket_count = get_labor_gacha_ticket_count(guild_id, member.id) if guild_id is not None else 0
        embed.add_field(
            name="노동 진행 현황",
            value=(
                f"완료: `{labor_penalty['completed_count']}회`\n"
                f"필요: `{labor_penalty['required_count']}회`\n"
                f"남은 횟수: `{remaining}회`\n"
                f"노동가챠권: `{ticket_count}장`"
            ),
            inline=False,
        )

    return embed


async def sync_blacklist_role(member: discord.Member, should_have_role: bool):
    role_id = get_guild_setting_role_id(member.guild.id, "blacklist_role_id")
    if role_id is None:
        return

    role = member.guild.get_role(role_id)
    if role is None:
        return

    try:
        if should_have_role and role not in member.roles:
            await member.add_roles(role)
        elif not should_have_role and role in member.roles:
            await member.remove_roles(role)
    except Exception:
        pass


def add_team_mix_logs(guild_id: int, message_id: int, channel_id: int, team_size: int, teams: list[list[discord.Member]]):
    created_at = dt_to_db(get_kst_now())
    cursor.execute(
        "DELETE FROM team_mix_logs WHERE guild_id=? AND message_id=?",
        (str(guild_id), str(message_id)),
    )
    for index, team_members in enumerate(teams, start=1):
        team_label = f"팀 {index}"
        members_text = ", ".join(member.display_name for member in team_members)
        for member in team_members:
            cursor.execute(
                """
                INSERT INTO team_mix_logs(guild_id, user_id, message_id, channel_id, team_size, team_label, members_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(guild_id),
                    str(member.id),
                    str(message_id),
                    str(channel_id),
                    team_size,
                    team_label,
                    members_text,
                    created_at,
                ),
            )
    conn.commit()


def get_team_mix_logs(guild_id: int, user_id: int, limit: int = 20):
    cursor.execute(
        """
        SELECT channel_id, team_size, team_label, members_text, created_at
        FROM team_mix_logs
        WHERE guild_id=? AND user_id=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (str(guild_id), str(user_id), limit),
    )
    return cursor.fetchall()


def get_team_mix_count_between(guild_id: int, user_id: int, start_dt: datetime, end_dt: datetime) -> int:
    cursor.execute(
        """
        SELECT COUNT(DISTINCT COALESCE(message_id, id))
        FROM team_mix_logs
        WHERE guild_id=? AND user_id=? AND created_at>=? AND created_at<=?
        """,
        (str(guild_id), str(user_id), dt_to_db(start_dt), dt_to_db(end_dt)),
    )
    row = cursor.fetchone()
    return int(row[0] or 0) if row else 0


def start_voice_session(guild_id: int, user_id: int, channel_id: int):
    cursor.execute(
        """
        INSERT OR REPLACE INTO voice_channel_sessions(guild_id, user_id, channel_id, started_at)
        VALUES (?, ?, ?, ?)
        """,
        (str(guild_id), str(user_id), str(channel_id), dt_to_db(get_kst_now())),
    )
    conn.commit()


def get_active_voice_session(guild_id: int, user_id: int):
    cursor.execute(
        """
        SELECT channel_id, started_at
        FROM voice_channel_sessions
        WHERE guild_id=? AND user_id=?
        """,
        (str(guild_id), str(user_id)),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "channel_id": int(row[0]),
        "started_at": row[1],
    }


def end_voice_session(guild_id: int, user_id: int):
    session = get_active_voice_session(guild_id, user_id)
    if session is None:
        return

    started_at = dt_from_db(session["started_at"])
    ended_at = get_kst_now()
    duration_seconds = max(0, int((ended_at - started_at).total_seconds()))

    cursor.execute(
        """
        INSERT INTO voice_channel_logs(guild_id, user_id, channel_id, started_at, ended_at, duration_seconds)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(guild_id),
            str(user_id),
            str(session["channel_id"]),
            dt_to_db(started_at),
            dt_to_db(ended_at),
            duration_seconds,
        ),
    )
    cursor.execute(
        "DELETE FROM voice_channel_sessions WHERE guild_id=? AND user_id=?",
        (str(guild_id), str(user_id)),
    )
    conn.commit()


def get_voice_channel_log_summary(guild_id: int, user_id: int, since: datetime):
    cursor.execute(
        """
        SELECT channel_id, SUM(duration_seconds) AS total_seconds, COUNT(*) AS session_count, MAX(ended_at) AS last_ended_at
        FROM voice_channel_logs
        WHERE guild_id=? AND user_id=? AND ended_at>=?
        GROUP BY channel_id
        ORDER BY total_seconds DESC, channel_id ASC
        """,
        (str(guild_id), str(user_id), dt_to_db(since)),
    )
    return cursor.fetchall()


def get_voice_channel_intervals(guild_id: int, user_id: int, since: datetime):
    cursor.execute(
        """
        SELECT channel_id, started_at, ended_at
        FROM voice_channel_logs
        WHERE guild_id=? AND user_id=? AND ended_at>=?
        ORDER BY started_at ASC
        """,
        (str(guild_id), str(user_id), dt_to_db(since)),
    )
    rows = cursor.fetchall()
    intervals = []
    for channel_id, started_at, ended_at in rows:
        try:
            start_dt = max(dt_from_db(started_at), since)
            end_dt = dt_from_db(ended_at)
        except Exception:
            continue
        if end_dt <= start_dt:
            continue
        intervals.append(
            {
                "channel_id": int(channel_id),
                "start": start_dt,
                "end": end_dt,
                "active": False,
            }
        )

    active_session = get_active_voice_session(guild_id, user_id)
    if active_session is not None:
        try:
            start_dt = max(dt_from_db(active_session["started_at"]), since)
        except Exception:
            start_dt = since
        end_dt = get_kst_now()
        if end_dt > start_dt:
            intervals.append(
                {
                    "channel_id": active_session["channel_id"],
                    "start": start_dt,
                    "end": end_dt,
                    "active": True,
                }
            )

    return intervals


def get_voice_channel_intervals_between(guild_id: int, user_id: int, start_dt: datetime, end_dt: datetime):
    intervals = []
    for item in get_voice_channel_intervals(guild_id, user_id, start_dt):
        clamped_start = max(item["start"], start_dt)
        clamped_end = min(item["end"], end_dt)
        if clamped_end <= clamped_start:
            continue
        intervals.append(
            {
                "channel_id": item["channel_id"],
                "start": clamped_start,
                "end": clamped_end,
                "active": item.get("active", False),
            }
        )
    return intervals


def get_voice_log_user_ids_between(guild_id: int, start_dt: datetime, end_dt: datetime) -> list[int]:
    cursor.execute(
        """
        SELECT DISTINCT user_id
        FROM voice_channel_logs
        WHERE guild_id=? AND ended_at>=? AND started_at<=?
        UNION
        SELECT DISTINCT user_id
        FROM voice_channel_sessions
        WHERE guild_id=? AND started_at<=?
        """,
        (str(guild_id), dt_to_db(start_dt), dt_to_db(end_dt), str(guild_id), dt_to_db(end_dt)),
    )
    user_ids = []
    for (user_id,) in cursor.fetchall():
        try:
            user_ids.append(int(user_id))
        except (TypeError, ValueError):
            continue
    return user_ids


def clear_active_voice_session(guild_id: int, user_id: int):
    cursor.execute(
        "DELETE FROM voice_channel_sessions WHERE guild_id=? AND user_id=?",
        (str(guild_id), str(user_id)),
    )
    conn.commit()


async def sync_active_voice_sessions():
    for guild in bot.guilds:
        seen_user_ids = set()

        for voice_channel in guild.voice_channels:
            for member in voice_channel.members:
                if member.bot or is_spectator_member(member, guild.id):
                    continue

                seen_user_ids.add(member.id)
                session = get_active_voice_session(guild.id, member.id)
                if session is None:
                    start_voice_session(guild.id, member.id, voice_channel.id)
                    continue

                if session["channel_id"] != voice_channel.id:
                    clear_active_voice_session(guild.id, member.id)
                    start_voice_session(guild.id, member.id, voice_channel.id)

        cursor.execute(
            "SELECT user_id FROM voice_channel_sessions WHERE guild_id=?",
            (str(guild.id),),
        )
        stored_user_ids = []
        for (user_id,) in cursor.fetchall():
            try:
                stored_user_ids.append(int(user_id))
            except ValueError:
                continue

        for user_id in stored_user_ids:
            if user_id not in seen_user_ids:
                clear_active_voice_session(guild.id, user_id)


def sum_voice_intervals_seconds(intervals: list[dict]) -> int:
    return sum(max(0, int((item["end"] - item["start"]).total_seconds())) for item in intervals)


def calculate_voice_overlap_seconds(intervals_a: list[dict], intervals_b: list[dict]):
    overlap_by_channel: dict[int, int] = {}

    grouped_a: dict[int, list[dict]] = {}
    grouped_b: dict[int, list[dict]] = {}

    for item in intervals_a:
        grouped_a.setdefault(item["channel_id"], []).append(item)
    for item in intervals_b:
        grouped_b.setdefault(item["channel_id"], []).append(item)

    for channel_id in set(grouped_a.keys()) & set(grouped_b.keys()):
        a_list = sorted(grouped_a[channel_id], key=lambda item: item["start"])
        b_list = sorted(grouped_b[channel_id], key=lambda item: item["start"])
        i = 0
        j = 0
        overlap_seconds = 0

        while i < len(a_list) and j < len(b_list):
            start = max(a_list[i]["start"], b_list[j]["start"])
            end = min(a_list[i]["end"], b_list[j]["end"])
            if end > start:
                overlap_seconds += int((end - start).total_seconds())

            if a_list[i]["end"] <= b_list[j]["end"]:
                i += 1
            else:
                j += 1

        if overlap_seconds > 0:
            overlap_by_channel[channel_id] = overlap_seconds

    return overlap_by_channel


def add_playlist_track(guild_id: int, owner_user_id: int, title: str, url: str):
    cursor.execute(
        """
        INSERT INTO playlist_tracks(guild_id, owner_user_id, title, url, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (str(guild_id), str(owner_user_id), title.strip(), url.strip(), dt_to_db(get_kst_now())),
    )
    conn.commit()
    return cursor.lastrowid


def get_playlist_tracks(guild_id: int, limit: int = 30):
    cursor.execute(
        """
        SELECT id, owner_user_id, title, url, created_at
        FROM playlist_tracks
        WHERE guild_id=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (str(guild_id), limit),
    )
    return cursor.fetchall()


def get_playlist_track(guild_id: int, track_id: int):
    cursor.execute(
        """
        SELECT id, owner_user_id, title, url, created_at
        FROM playlist_tracks
        WHERE guild_id=? AND id=?
        """,
        (str(guild_id), track_id),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "owner_user_id": int(row[1]),
        "title": row[2],
        "url": row[3],
        "created_at": row[4],
    }


def delete_playlist_track(guild_id: int, track_id: int):
    cursor.execute(
        "DELETE FROM playlist_tracks WHERE guild_id=? AND id=?",
        (str(guild_id), track_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def build_playlist_track_from_row(row) -> dict:
    track_id, owner_user_id, title, url, created_at = row
    return {
        "id": track_id,
        "owner_user_id": int(owner_user_id),
        "title": title,
        "url": url,
        "created_at": created_at,
    }


def get_ffmpeg_executable_path() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    raise RuntimeError(
        "시스템 ffmpeg를 찾지 못했습니다. Railway 배포 루트에 `nixpacks.toml`이 적용됐는지 확인해주세요."
    )


async def resolve_playlist_audio_url(url: str):
    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError("음악 재생을 위해 서버에 `yt-dlp` 설치가 필요합니다.")

    options = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "default_search": "auto",
    }

    def extract():
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
            if "entries" in info:
                info = next((entry for entry in info["entries"] if entry), None)
            if not info:
                raise RuntimeError("재생 정보를 가져오지 못했습니다.")
            stream_url = info.get("url")
            if not stream_url:
                raise RuntimeError("재생 가능한 오디오 스트림을 찾지 못했습니다.")
            return {
                "title": info.get("title") or "제목 없음",
                "stream_url": stream_url,
                "webpage_url": info.get("webpage_url") or url,
                "http_headers": info.get("http_headers") or {},
            }

    return await asyncio.to_thread(extract)


async def start_next_playlist_track(guild: discord.Guild):
    voice_client = guild.voice_client

    if voice_client is None:
        playlist_now_playing.pop(guild.id, None)
        await refresh_playlist_panel(guild)
        return

    mode = playlist_modes.get(guild.id, "order")
    queue = playlist_queues.setdefault(guild.id, [])
    library = playlist_library_cache.get(guild.id, [])

    if not queue and mode == "order" and library:
        queue.extend(library)

    if not queue:
        playlist_now_playing.pop(guild.id, None)
        await refresh_playlist_panel(guild)
        return

    current_track = playlist_now_playing.get(guild.id)
    if current_track:
        playlist_previous_tracks[guild.id] = current_track

    if mode == "random":
        source_tracks = queue or library
        if not source_tracks:
            playlist_now_playing.pop(guild.id, None)
            await refresh_playlist_panel(guild)
            return
        track = random.choice(source_tracks)
        if queue and track in queue:
            queue.remove(track)
    else:
        track = queue.pop(0)

    playlist_now_playing[guild.id] = track
    await refresh_playlist_panel(guild)

    try:
        audio_info = await resolve_playlist_audio_url(track["url"])
    except Exception as e:
        text_channel = guild.get_channel(playlist_text_channels.get(guild.id, 0))
        if text_channel:
            await text_channel.send(f"`{track['title']}` 재생 준비 중 오류가 발생했습니다: {e}")
        await start_next_playlist_track(guild)
        return

    try:
        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -loglevel error",
        }
        ffmpeg_path = get_ffmpeg_executable_path()
        source = discord.FFmpegOpusAudio(
            audio_info["stream_url"],
            executable=ffmpeg_path,
            **ffmpeg_options,
        )
        print(f"플레이리스트 ffmpeg 경로: {ffmpeg_path}")

        def after_play(error):
            if error:
                print(f"플레이리스트 재생 오류: {error}")
            bot.loop.create_task(start_next_playlist_track(guild))

        voice_client.play(source, after=after_play)
    except Exception as e:
        text_channel = guild.get_channel(playlist_text_channels.get(guild.id, 0))
        error_text = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        if text_channel:
            await text_channel.send(f"`{track['title']}` 재생 시작 중 오류가 발생했습니다: {error_text}")
        await start_next_playlist_track(guild)
        return


async def refresh_playlist_panel(guild: discord.Guild):
    panel_info = playlist_panel_messages.get(guild.id)
    if not panel_info:
        return

    channel_id, message_id = panel_info
    channel = guild.get_channel(channel_id)
    if channel is None:
        return

    try:
        message = await channel.fetch_message(message_id)
        await message.edit(embed=build_playlist_panel_embed(guild))
    except Exception:
        pass


async def disconnect_playlist_if_alone(guild: discord.Guild):
    voice_client = guild.voice_client
    if voice_client is None or not voice_client.is_connected() or voice_client.channel is None:
        return

    human_members = [member for member in voice_client.channel.members if not member.bot]
    if human_members:
        return

    playlist_queues.pop(guild.id, None)
    playlist_now_playing.pop(guild.id, None)
    playlist_text_channels.pop(guild.id, None)
    playlist_previous_tracks.pop(guild.id, None)
    playlist_library_cache.pop(guild.id, None)
    playlist_modes.pop(guild.id, None)
    await disable_playlist_panel(guild)
    await voice_client.disconnect(force=True)


async def disable_playlist_panel(guild: discord.Guild):
    panel_info = playlist_panel_messages.pop(guild.id, None)
    if not panel_info:
        return

    channel_id, message_id = panel_info
    channel = guild.get_channel(channel_id)
    if channel is None:
        return

    try:
        message = await channel.fetch_message(message_id)
    except Exception:
        return

    view = discord.ui.View()
    for label, style in [
        ("이전 곡", discord.ButtonStyle.secondary),
        ("정지", discord.ButtonStyle.danger),
        ("다음 곡", discord.ButtonStyle.primary),
        ("랜덤재생", discord.ButtonStyle.success),
        ("순서재생", discord.ButtonStyle.success),
    ]:
        view.add_item(discord.ui.Button(label=label, style=style, disabled=True))

    try:
        await message.edit(embed=build_playlist_panel_embed(guild), view=view)
    except Exception:
        pass


async def start_playlist_player(
    interaction: discord.Interaction,
    tracks: list[dict],
    *,
    mode: str = "order",
    start_immediately: bool = True,
):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    if not tracks:
        await interaction.response.send_message("재생할 플레이리스트 곡이 없습니다.", ephemeral=True)
        return

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("먼저 재생할 음성채널에 들어가 주세요.", ephemeral=True)
        return

    await interaction.response.defer()

    voice_channel = interaction.user.voice.channel
    try:
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            voice_client = await voice_channel.connect(timeout=10, reconnect=False)
        elif voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
    except Exception as e:
        if getattr(e, "code", None) == 4017:
            await interaction.followup.send(
                "이 음성채널은 E2EE/DAVE 보안 음성 연결이 필요해서 봇이 접속하지 못했습니다.\n"
                "일반 음성채널에서 다시 시도하거나, 해당 채널의 E2EE/DAVE 관련 설정을 꺼주세요.",
                ephemeral=True,
            )
            return
        await interaction.followup.send(f"음성채널에 연결하지 못했습니다: {e}", ephemeral=True)
        return

    playlist_text_channels[interaction.guild.id] = interaction.channel.id
    playlist_library_cache[interaction.guild.id] = list(tracks)
    playlist_modes[interaction.guild.id] = mode
    playlist_queues[interaction.guild.id] = list(tracks)

    if not start_immediately:
        await interaction.followup.send("🎧 플레이리스트 패널을 열었습니다.")
        return

    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    await start_next_playlist_track(interaction.guild)


class PlaylistPanelView(discord.ui.View):
    def __init__(self, requester_id: int, tracks: list[dict]):
        super().__init__(timeout=180)
        self.requester_id = requester_id
        self.tracks = tracks

    async def refresh_panel(self, interaction: discord.Interaction):
        if interaction.message and interaction.guild:
            try:
                await interaction.message.edit(embed=build_playlist_panel_embed(interaction.guild), view=self)
            except Exception:
                pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("이 플레이리스트 패널은 명령어를 사용한 사람만 조작할 수 있습니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="이전 곡", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
            return

        previous_track = playlist_previous_tracks.get(interaction.guild.id)
        voice_client = interaction.guild.voice_client
        if previous_track is None or voice_client is None or not voice_client.is_connected():
            await interaction.response.send_message("이전 곡이 없습니다.", ephemeral=True)
            return

        playlist_queues.setdefault(interaction.guild.id, []).insert(0, previous_track)
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
        else:
            await start_next_playlist_track(interaction.guild)
        await interaction.response.defer()
        await self.refresh_panel(interaction)

    @discord.ui.button(label="정지", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
            return

        playlist_queues.pop(interaction.guild.id, None)
        playlist_now_playing.pop(interaction.guild.id, None)
        playlist_previous_tracks.pop(interaction.guild.id, None)
        playlist_library_cache.pop(interaction.guild.id, None)
        playlist_modes.pop(interaction.guild.id, None)
        playlist_text_channels.pop(interaction.guild.id, None)

        voice_client = interaction.guild.voice_client
        if voice_client is not None and voice_client.is_connected():
            await interaction.response.defer()
            await disable_playlist_panel(interaction.guild)
            await voice_client.disconnect(force=True)
            return
        await interaction.response.send_message("현재 연결된 음성채널이 없습니다.", ephemeral=True)

    @discord.ui.button(label="다음 곡", style=discord.ButtonStyle.primary)
    async def next_track(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = interaction.guild.voice_client if interaction.guild else None
        if voice_client is None or not voice_client.is_connected():
            await interaction.response.send_message("현재 재생 중인 플레이리스트가 없습니다.", ephemeral=True)
            return
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
            await interaction.response.defer()
            await self.refresh_panel(interaction)
            return
        await start_next_playlist_track(interaction.guild)
        await interaction.response.defer()
        await self.refresh_panel(interaction)

    @discord.ui.button(label="랜덤재생", style=discord.ButtonStyle.success)
    async def random_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
            return

        library = playlist_library_cache.get(interaction.guild.id) or self.tracks
        await start_playlist_player(interaction, list(library), mode="random")
        await self.refresh_panel(interaction)

    @discord.ui.button(label="순서재생", style=discord.ButtonStyle.success)
    async def order_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
            return

        library = playlist_library_cache.get(interaction.guild.id) or self.tracks
        await start_playlist_player(interaction, list(library), mode="order")
        await self.refresh_panel(interaction)


def build_playlist_panel_embed(guild: discord.Guild):
    embed = discord.Embed(
        title="🎧 마리봇 플레이리스트",
        description="현재 재생 중인 곡을 확인하고 재생 방식을 선택할 수 있습니다.",
        color=0x1DB954,
    )

    now_playing = playlist_now_playing.get(guild.id)
    if now_playing:
        owner = guild.get_member(now_playing["owner_user_id"])
        owner_name = owner.display_name if owner else f"알 수 없는 유저 ({now_playing['owner_user_id']})"
        embed.add_field(
            name="현재 재생 중",
            value=(
                f"**{now_playing['title']}**\n"
                f"등록자: {owner_name}\n"
                f"곡번호: `{now_playing['id']}`"
            ),
            inline=False,
        )
    else:
        embed.add_field(name="현재 재생 중", value="재생 중인 곡이 없습니다.", inline=False)

    mode = playlist_modes.get(guild.id, "order")
    mode_text = "랜덤재생" if mode == "random" else "순서재생"
    embed.add_field(name="재생 모드", value=f"`{mode_text}`", inline=True)
    embed.add_field(name="대기열", value=f"`{len(playlist_queues.get(guild.id, []))}곡`", inline=True)
    embed.set_footer(text="이전 곡 / 정지 / 다음 곡 / 랜덤재생 / 순서재생 버튼으로 조작합니다.")
    return embed


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


def cancel_saving(saving_id: int):
    cursor.execute(
        """
        UPDATE savings
        SET status='cancelled', claimed_at=?
        WHERE id=?
        """,
        (dt_to_db(get_kst_now()), saving_id),
    )
    conn.commit()


def get_due_savings(now: datetime):
    cursor.execute(
        """
        SELECT id, user_id, total_amount
        FROM savings
        WHERE status='active' AND due_at<=?
        ORDER BY id ASC
        """,
        (dt_to_db(now),),
    )
    return cursor.fetchall()


def calculate_labor_required_count(debt_amount: int) -> int:
    return max(10, (debt_amount // 10_000) * 2)


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

    debt_amount = get_total_credit_obligation(guild_id, user_id) or DEFAULT_LABOR_DEBT_AMOUNT
    create_or_replace_labor_penalty(guild_id, user_id, debt_amount)
    return get_active_labor_penalty(guild_id, user_id)


def increment_labor_count(guild_id: int, user_id: int):
    penalty = ensure_active_labor_penalty(guild_id, user_id)
    if penalty is None:
        return None, False

    return apply_labor_progress(guild_id, user_id, 1)


def resolve_labor_penalty_if_complete(guild_id: int, user_id: int, penalty: dict):
    if penalty["completed_count"] < penalty["required_count"]:
        return penalty, False

    cursor.execute(
        """
        UPDATE labor_penalties
        SET status='resolved', resolved_at=?
        WHERE guild_id=? AND user_id=?
        """,
        (dt_to_db(get_kst_now()), str(guild_id), str(user_id)),
    )
    conn.commit()

    active_loans = get_active_loans(user_id)
    if active_loans:
        repay_loans([loan["id"] for loan in active_loans])
    resolve_manual_credit_debts(guild_id, user_id)

    set_credit_blacklisted(user_id, False)
    set_credit_grade(user_id, INITIAL_CREDIT_GRADE)
    reset_loan_progress_amount(user_id)
    return penalty, True


def apply_labor_progress(guild_id: int, user_id: int, progress_count: int):
    penalty = ensure_active_labor_penalty(guild_id, user_id)
    if penalty is None:
        return None, False

    cursor.execute(
        """
        UPDATE labor_penalties
        SET completed_count=MIN(required_count, completed_count + ?)
        WHERE guild_id=? AND user_id=? AND status='active'
        """,
        (progress_count, str(guild_id), str(user_id)),
    )
    conn.commit()

    updated = get_active_labor_penalty(guild_id, user_id)
    if updated is None:
        return None, False

    return resolve_labor_penalty_if_complete(guild_id, user_id, updated)


def get_labor_gacha_ticket_count(guild_id: int, user_id: int) -> int:
    cursor.execute(
        "SELECT ticket_count FROM labor_gacha_tickets WHERE guild_id=? AND user_id=?",
        (str(guild_id), str(user_id)),
    )
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def add_labor_gacha_tickets(guild_id: int, user_id: int, amount: int):
    cursor.execute(
        """
        INSERT INTO labor_gacha_tickets(guild_id, user_id, ticket_count)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id, user_id)
        DO UPDATE SET ticket_count=ticket_count + excluded.ticket_count
        """,
        (str(guild_id), str(user_id), amount),
    )
    conn.commit()


def consume_labor_gacha_ticket(guild_id: int, user_id: int) -> bool:
    current_count = get_labor_gacha_ticket_count(guild_id, user_id)
    if current_count <= 0:
        return False

    cursor.execute(
        """
        UPDATE labor_gacha_tickets
        SET ticket_count=ticket_count-1
        WHERE guild_id=? AND user_id=? AND ticket_count>0
        """,
        (str(guild_id), str(user_id)),
    )
    conn.commit()
    return cursor.rowcount > 0


def roll_labor_gacha():
    labels = [item[0] for item in LABOR_GACHA_RESULTS]
    weights = [item[2] for item in LABOR_GACHA_RESULTS]
    label = random.choices(labels, weights=weights, k=1)[0]

    for result_label, percent, _weight in LABOR_GACHA_RESULTS:
        if result_label == label:
            return result_label, percent

    return "꽝", 0


def delete_labor_penalty(guild_id: int, user_id: int):
    cursor.execute(
        "DELETE FROM labor_penalties WHERE guild_id=? AND user_id=?",
        (str(guild_id), str(user_id)),
    )
    conn.commit()


def create_promissory_note(
    guild_id: int,
    lender_user_id: int,
    borrower_user_id: int,
    principal_amount: int,
    interest_amount: int,
    due_text: str,
    note: str,
    channel_id: int,
    message_id: int,
):
    created_at = dt_to_db(get_kst_now())
    amount = principal_amount + interest_amount
    cursor.execute(
        """
        INSERT INTO promissory_notes(
            guild_id, lender_user_id, borrower_user_id, amount, principal_amount, interest_amount,
            due_text, note, channel_id, message_id, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
        """,
        (
            str(guild_id),
            str(lender_user_id),
            str(borrower_user_id),
            amount,
            principal_amount,
            interest_amount,
            due_text,
            note,
            str(channel_id),
            str(message_id),
            created_at,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def get_promissory_note(note_id: int):
    cursor.execute(
        """
        SELECT
            id, guild_id, lender_user_id, borrower_user_id, amount, principal_amount, interest_amount,
            due_text, note, channel_id, message_id, status, created_at, resolved_at
        FROM promissory_notes
        WHERE id=?
        """,
        (note_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "id": int(row[0]),
        "guild_id": row[1],
        "lender_user_id": int(row[2]),
        "borrower_user_id": int(row[3]),
        "amount": int(row[4]),
        "principal_amount": int(row[5]),
        "interest_amount": int(row[6]),
        "due_text": row[7],
        "note": row[8] or "",
        "channel_id": int(row[9]) if row[9] else None,
        "message_id": int(row[10]) if row[10] else None,
        "status": row[11],
        "created_at": row[12],
        "resolved_at": row[13],
    }


def get_active_promissory_notes_for_user(guild_id: int, user_id: int):
    cursor.execute(
        """
        SELECT
            id, lender_user_id, borrower_user_id, amount, principal_amount, interest_amount, due_text, note, created_at
        FROM promissory_notes
        WHERE guild_id=? AND status='active' AND (lender_user_id=? OR borrower_user_id=?)
        ORDER BY id DESC
        """,
        (str(guild_id), str(user_id), str(user_id)),
    )
    rows = cursor.fetchall()
    notes = []
    for row in rows:
        notes.append(
            {
                "id": int(row[0]),
                "lender_user_id": int(row[1]),
                "borrower_user_id": int(row[2]),
                "amount": int(row[3]),
                "principal_amount": int(row[4]),
                "interest_amount": int(row[5]),
                "due_text": row[6],
                "note": row[7] or "",
                "created_at": row[8],
            }
        )
    return notes


def resolve_promissory_note(note_id: int):
    cursor.execute(
        """
        UPDATE promissory_notes
        SET status='resolved', resolved_at=?
        WHERE id=? AND status='active'
        """,
        (dt_to_db(get_kst_now()), note_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def build_promissory_note_embed(
    lender: discord.Member | discord.User | None,
    borrower: discord.Member | discord.User | None,
    principal_amount: int,
    interest_amount: int,
    due_text: str,
    note: str,
    *,
    title: str,
    color: int,
    status_text: str,
    note_id: int | None = None,
):
    def mention_or_fallback(user_obj, fallback_text: str) -> str:
        if user_obj is None:
            return fallback_text
        return user_obj.mention

    embed = discord.Embed(title=title, color=color)
    if note_id is not None:
        embed.add_field(name="차용증 번호", value=f"`#{note_id}`", inline=False)
    embed.add_field(name="채권자", value=mention_or_fallback(lender, "알 수 없는 유저"), inline=True)
    embed.add_field(name="채무자", value=mention_or_fallback(borrower, "알 수 없는 유저"), inline=True)
    embed.add_field(name="원금", value=f"`{format_money(principal_amount)}`", inline=True)
    embed.add_field(name="이자", value=f"`{format_money(interest_amount)}`", inline=True)
    embed.add_field(name="총 상환 금액", value=f"`{format_money(principal_amount + interest_amount)}`", inline=False)
    embed.add_field(name="상환 약속일", value=due_text, inline=False)
    embed.add_field(name="상태", value=status_text, inline=False)
    embed.add_field(name="비고", value=note or "없음", inline=False)
    embed.add_field(
        name="안내",
        value="실제 재화 이동은 자동 처리되지 않습니다. 필요하면 `/송금`을 별도로 사용해주세요.",
        inline=False,
    )
    return embed


async def ensure_not_blacklisted_for_gambling(interaction: discord.Interaction) -> bool:
    profile = get_credit_profile(interaction.user.id)
    if profile["is_blacklisted"]:
        await interaction.response.send_message(
            "현재 신용불량자 상태에서는 도박 명령어를 사용할 수 없습니다. `/노동`으로 신용 회복을 진행해주세요.",
            ephemeral=True,
        )
        return False
    return True


def roll_labor_mine_result(mine_key: str):
    mine_info = LABOR_MINE_TABLE[mine_key]
    picked = random.choices(
        mine_info["results"],
        weights=[item["weight"] for item in mine_info["results"]],
        k=1,
    )[0]
    return {
        "mine_key": mine_key,
        "mine_label": mine_info["label"],
        "mine_color": mine_info["color"],
        "name": picked["name"],
        "progress": picked["progress"],
        "description": picked["description"],
        "ticket_bonus": picked["ticket_bonus"],
    }


def build_labor_embed(
    member: discord.Member,
    penalty: dict,
    guild_id: int | None = None,
    mine_result: dict | None = None,
) -> discord.Embed:
    remaining = max(0, penalty["required_count"] - penalty["completed_count"])
    embed = discord.Embed(title="⛏ 아오지탄광", color=0xE67E22)
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
    if guild_id is not None:
        embed.add_field(
            name="보유 노동가챠권",
            value=f"`{get_labor_gacha_ticket_count(guild_id, member.id)}장`",
            inline=False,
        )
    if mine_result is None:
        embed.add_field(
            name="채굴 안내",
            value=(
                "`얕은 광맥`은 가장 안정적이고,\n"
                "`일반 광맥`은 무난하며,\n"
                "`심층 광맥`은 평균 효율은 낮지만 대박과 가챠권을 노릴 수 있습니다."
            ),
            inline=False,
        )
    else:
        result_lines = [
            f"선택한 광맥: **{mine_result['mine_label']}**",
            f"채굴 결과: **{mine_result['name']}**",
            mine_result["description"],
            f"노동 감소량: `{mine_result['progress']}회`",
        ]
        if mine_result["ticket_bonus"] > 0:
            result_lines.append(f"추가 획득: `노동가챠권 {mine_result['ticket_bonus']}장`")
        result_lines.append(f"남은 노동 횟수: `{remaining}회`")
        embed.color = mine_result["mine_color"]
        embed.add_field(name="채굴 결과", value="\n".join(result_lines), inline=False)
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
    "슬롯": "슬롯",
    "동전": "동전",
    "보급": "보급",
    "블랙잭": "블랙잭",
    "경마": "경마",
    "숫자야구": "숫자야구",
    "야추": "야추",
    "지뢰찾기": "지뢰찾기",
    "섯다": "섯다",
    "몰빵게임": "몰빵게임",
}

BLACKJACK_TIMEOUT = 90
BLACKJACK_CARD_VALUES = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
NUMBER_BASEBALL_DIGITS = 4
NUMBER_BASEBALL_ATTEMPTS = 8
NUMBER_BASEBALL_COST = 100_000
HORSE_RACE_TABLE = [
    {"name": "즈미", "weight": 20, "payout": 5.0},
    {"name": "훈이", "weight": 18, "payout": 5.5},
    {"name": "해랑솔", "weight": 16, "payout": 6.25},
    {"name": "김천", "weight": 14, "payout": 7.1},
    {"name": "삼성", "weight": 12, "payout": 8.3},
    {"name": "하랑", "weight": 11, "payout": 9.1},
    {"name": "개쩌는머로", "weight": 9, "payout": 11.1},
]
DICE_POKER_PAYOUTS = {
    "야추": 20.0,
    "포카드": 8.0,
    "풀하우스": 4.0,
    "라지 스트레이트": 3.0,
    "스몰 스트레이트": 2.0,
    "트리플": 2.2,
    "투페어": 1.5,
    "원페어": 1.1,
    "노페어": 0.0,
}
DICE_POKER_RANKS = {
    "노페어": 0,
    "원페어": 1,
    "투페어": 2,
    "트리플": 3,
    "스몰 스트레이트": 4,
    "라지 스트레이트": 5,
    "풀하우스": 6,
    "포카드": 7,
    "야추": 8,
}
MINESWEEPER_SIZE = 4
MINESWEEPER_MINE_COUNT = 3
MINESWEEPER_MULTIPLIERS = {
    1: 1.15,
    2: 1.30,
    3: 1.50,
    4: 1.75,
    5: 2.05,
    6: 2.45,
    7: 3.00,
    8: 3.80,
    9: 5.00,
    10: 6.50,
    11: 8.50,
    12: 11.00,
    13: 15.00,
}

LABOR_MINE_TABLE = {
    "shallow": {
        "label": "얕은 광맥",
        "color": 0xF1C40F,
        "results": [
            {"name": "석탄", "weight": 35, "progress": 1, "description": "석탄을 캐냈습니다. 무난한 하루치 작업입니다.", "ticket_bonus": 0},
            {"name": "철광석", "weight": 40, "progress": 2, "description": "철광석을 발견했습니다. 삽질한 보람이 느껴집니다.", "ticket_bonus": 0},
            {"name": "은광석", "weight": 20, "progress": 3, "description": "은광석을 캤습니다. 오늘은 제법 손맛이 좋습니다.", "ticket_bonus": 0},
            {"name": "꽝", "weight": 5, "progress": 0, "description": "쓸 만한 광물을 찾지 못했습니다. 먼지만 잔뜩 뒤집어썼습니다.", "ticket_bonus": 0},
        ],
    },
    "normal": {
        "label": "일반 광맥",
        "color": 0xE67E22,
        "results": [
            {"name": "석탄", "weight": 45, "progress": 1, "description": "석탄 더미를 건졌습니다. 평범하지만 확실한 수확입니다.", "ticket_bonus": 0},
            {"name": "철광석", "weight": 27, "progress": 2, "description": "철광석 덩어리를 캐냈습니다. 제법 묵직한 한 방입니다.", "ticket_bonus": 0},
            {"name": "은광석", "weight": 13, "progress": 3, "description": "은광석이 섞인 광맥을 찾았습니다. 생각보다 괜찮은 성과입니다.", "ticket_bonus": 0},
            {"name": "금광석", "weight": 8, "progress": 4, "description": "금광석을 발견했습니다. 오늘 인부들 사이에서 자랑할 만합니다.", "ticket_bonus": 0},
            {"name": "꽝", "weight": 7, "progress": 0, "description": "광맥을 잘못 짚었습니다. 이번 작업은 허탕입니다.", "ticket_bonus": 0},
        ],
    },
    "deep": {
        "label": "심층 광맥",
        "color": 0x8E44AD,
        "results": [
            {"name": "철광석", "weight": 625, "progress": 2, "description": "위험을 감수한 보람은 있었습니다. 철광석을 확보했습니다.", "ticket_bonus": 0},
            {"name": "은광석", "weight": 450, "progress": 3, "description": "심층부에서 은광석을 찾아냈습니다. 꽤 괜찮은 성과입니다.", "ticket_bonus": 0},
            {"name": "금광석", "weight": 200, "progress": 4, "description": "희미하게 빛나는 금광석을 발견했습니다. 탄광장도 탐낼 만한 물건입니다.", "ticket_bonus": 0},
            {"name": "다이아 원석", "weight": 75, "progress": 7, "description": "다이아 원석을 캐냈습니다! 오늘 작업은 전설로 남을 겁니다.", "ticket_bonus": 0},
            {"name": "꽝", "weight": 600, "progress": 0, "description": "깊숙이 들어갔지만 광맥을 놓쳤습니다. 체력만 빠졌습니다.", "ticket_bonus": 0},
            {"name": "붕락", "weight": 548, "progress": 0, "description": "탄광이 무너져 작업을 중단했습니다. 겨우 몸만 빠져나왔습니다.", "ticket_bonus": 0},
            {"name": "노동가챠권 발견", "weight": 2, "progress": 1, "description": "심층부 틈새에서 노동가챠권을 찾아냈습니다. 위험을 감수한 보상이 따릅니다.", "ticket_bonus": 1},
        ],
    },
}


def create_seotda_deck():
    deck = []
    for month in range(1, 11):
        if month in {1, 3, 8}:
            deck.append((month, True))
            deck.append((month, False))
        else:
            deck.append((month, False))
            deck.append((month, False))
    return deck


def format_seotda_card(card: tuple[int, bool]) -> str:
    month, is_kwang = card
    return f"{month}{'광' if is_kwang else '월'}"


def format_seotda_hand(cards: list[tuple[int, bool]]) -> str:
    return " / ".join(format_seotda_card(card) for card in cards)


def draw_seotda_hands():
    drawn_cards = random.sample(create_seotda_deck(), 4)
    return drawn_cards[:2], drawn_cards[2:]


def evaluate_seotda_hand(cards: list[tuple[int, bool]]):
    sorted_cards = sorted(cards, key=lambda card: (card[0], 0 if card[1] else 1))
    months = sorted(card[0] for card in sorted_cards)
    month_tuple = tuple(months)
    all_kwang = all(card[1] for card in sorted_cards)

    if all_kwang and month_tuple == (3, 8):
        return {"name": "38광땡", "score": 10000}
    if all_kwang and month_tuple in {(1, 3), (1, 8)}:
        return {"name": f"{months[0]}{months[1]}광땡", "score": 9900}
    if months[0] == months[1]:
        return {"name": f"{months[0]}땡", "score": 9000 + months[0]}
    if month_tuple in SEOTDA_SPECIAL_RANKS:
        name, score = SEOTDA_SPECIAL_RANKS[month_tuple]
        return {"name": name, "score": score}

    kkeut = sum(months) % 10
    if kkeut == 0:
        return {"name": "망통", "score": 7000}
    if kkeut == 9:
        return {"name": "갑오", "score": 7009}
    return {"name": f"{kkeut}끗", "score": 7000 + kkeut}


def build_seotda_result_embed(
    challenger: discord.Member | discord.User,
    opponent: discord.Member | discord.User,
    challenger_cards: list[tuple[int, bool]],
    opponent_cards: list[tuple[int, bool]],
    challenger_result: dict,
    opponent_result: dict,
    amount: int,
    result_text: str,
    color: int,
):
    embed = discord.Embed(title="🃏 섯다 결과", description=result_text, color=color)
    embed.add_field(
        name=f"{challenger.display_name if hasattr(challenger, 'display_name') else challenger.name} 패",
        value=f"`{format_seotda_hand(challenger_cards)}`\n족보: **{challenger_result['name']}**",
        inline=False,
    )
    embed.add_field(
        name=f"{opponent.display_name if hasattr(opponent, 'display_name') else opponent.name} 패",
        value=f"`{format_seotda_hand(opponent_cards)}`\n족보: **{opponent_result['name']}**",
        inline=False,
    )
    embed.add_field(name="판돈", value=f"`{format_money(amount)}`", inline=False)
    return embed


def build_seotda_progress_embed(
    challenger: discord.Member | discord.User,
    opponent: discord.Member | discord.User,
    challenger_cards: list[tuple[int, bool]],
    opponent_cards: list[tuple[int, bool]],
    base_amount: int,
    pot_amount: int,
    challenger_action: str | None,
    opponent_action: str | None,
):
    def action_text(action: str | None) -> str:
        if action in {"bet", "allin", "die"}:
            return "선택 완료"
        return "대기 중"

    challenger_name = challenger.display_name if hasattr(challenger, "display_name") else challenger.name
    opponent_name = opponent.display_name if hasattr(opponent, "display_name") else opponent.name

    embed = discord.Embed(
        title="🃏 섯다",
        description=(
            "첫 번째 패가 공개되었습니다.\n"
            "아래 버튼에서 `배팅` 또는 `다이`를 선택해주세요.\n"
            "두 사람 모두 `배팅`을 선택해야 다음 패가 공개됩니다."
        ),
        color=0xF1C40F,
    )
    embed.add_field(
        name=f"{challenger_name} 패",
        value=f"`{format_seotda_card(challenger_cards[0])}` / `??`\n상태: **{action_text(challenger_action)}**",
        inline=False,
    )
    embed.add_field(
        name=f"{opponent_name} 패",
        value=f"`{format_seotda_card(opponent_cards[0])}` / `??`\n상태: **{action_text(opponent_action)}**",
        inline=False,
    )
    embed.add_field(name="기본 배팅금", value=f"`{format_money(base_amount)}`", inline=True)
    embed.add_field(name="현재 판돈", value=f"`{format_money(pot_amount)}`", inline=True)
    embed.add_field(
        name="진행 방식",
        value=(
            "`배팅`을 누르면 처음 건 금액만큼 추가로 겁니다.\n"
            "잔액이 부족하면 가능한 금액만큼 자동 올인합니다.\n"
            "`다이`를 누르면 그 판에서 패배합니다."
        ),
        inline=False,
    )
    return embed



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
        super().__init__(title="등업 패널 문구 설정")
        self.guild_id = guild_id
        self.content = discord.ui.TextInput(
            label="등업 패널 문구",
            placeholder="줄바꿈해서 입력해주세요.",
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
        await interaction.response.send_message("등업 패널 문구를 저장했습니다.", ephemeral=True)


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
                await log_channel.send(f"✅ {interaction.user.mention} 님이 규칙을 확인했습니다.")

        await interaction.response.send_message("🎉 규칙 확인 완료!", ephemeral=True)


class UpgradePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="등업요청", style=discord.ButtonStyle.success, custom_id="upgrade_apply")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        existing = discord.utils.get(guild.channels, name=f"{user.name}-등업요청")
        if existing:
            await interaction.response.send_message("이미 요청 채널이 있습니다.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True),
        }

        channel = await guild.create_text_channel(
            name=f"{user.name}-등업요청",
            overwrites=overwrites,
        )

        await channel.send(
            content=f"{user.mention}님의 등업 요청 채널입니다.",
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
            embed = discord.Embed(title="📒 등업 로그", color=0x3498DB)
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

    @discord.ui.button(label="클랜원 등업", style=discord.ButtonStyle.primary, custom_id="upgrade_clan")
    async def clan(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        role_id = get_guild_setting_role_id(interaction.guild.id, "upgrade_clan_role_id")
        role = interaction.guild.get_role(role_id) if role_id else None
        if role:
            await self.user.add_roles(role)

        await self.send_welcome_dm()
        await self.send_log(interaction, "클랜원 등업")
        await self.disable_buttons_except_delete(interaction.message)
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.followup.send(f"{self.user.mention}님의 클랜원 등업이 완료되었습니다.", ephemeral=True)

    @discord.ui.button(label="게스트 등업", style=discord.ButtonStyle.secondary, custom_id="upgrade_guest")
    async def guest(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        role_id = get_guild_setting_role_id(interaction.guild.id, "upgrade_guest_role_id")
        role = interaction.guild.get_role(role_id) if role_id else None
        if role:
            await self.user.add_roles(role)

        await self.send_welcome_dm()
        await self.send_log(interaction, "게스트 등업")
        await self.disable_buttons_except_delete(interaction.message)
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.followup.send(f"{self.user.mention}님의 게스트 등업이 완료되었습니다.", ephemeral=True)

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
        force_info = get_hidden_gambling_force(self.user_id)
        if force_info and force_info["game_name"] == "coin":
            consume_hidden_gambling_force(self.user_id)
            result = choice
        else:
            result = random.choice(["앞", "뒤"])
        win = choice == result

        if win:
            payout = int(self.bet_amount * 2)
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


def draw_blackjack_card() -> str:
    return random.choice(BLACKJACK_CARD_VALUES)


def blackjack_hand_value(cards: list[str]) -> int:
    total = 0
    aces = 0
    for card in cards:
        if card == "A":
            total += 11
            aces += 1
        elif card in {"J", "Q", "K"}:
            total += 10
        else:
            total += int(card)

    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def format_blackjack_cards(cards: list[str], hide_second: bool = False) -> str:
    if hide_second and len(cards) >= 2:
        visible_cards = [cards[0], "?"]
    else:
        visible_cards = cards
    return " ".join(f"`{card}`" for card in visible_cards)


class BlackjackView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, bet_amount: int):
        super().__init__(timeout=BLACKJACK_TIMEOUT)
        self.guild_id = guild_id
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.player_cards = [draw_blackjack_card(), draw_blackjack_card()]
        self.dealer_cards = [draw_blackjack_card(), draw_blackjack_card()]
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 명령어를 사용한 본인만 누를 수 있습니다.", ephemeral=True)
            return False
        return True

    def build_embed(self, reveal_dealer: bool = False, result_text: str | None = None, color: int = 0x2C3E50):
        player_value = blackjack_hand_value(self.player_cards)
        dealer_value = blackjack_hand_value(self.dealer_cards)
        dealer_display_value = dealer_value if reveal_dealer else "?"

        embed = discord.Embed(title="🃏 블랙잭", color=color)
        embed.add_field(
            name="내 패",
            value=f"{format_blackjack_cards(self.player_cards)}\n합계: `{player_value}`",
            inline=False,
        )
        embed.add_field(
            name="딜러 패",
            value=(
                f"{format_blackjack_cards(self.dealer_cards, hide_second=not reveal_dealer)}\n"
                f"합계: `{dealer_display_value}`"
            ),
            inline=False,
        )
        embed.add_field(name="베팅 금액", value=format_money(self.bet_amount), inline=False)
        if result_text:
            embed.description = result_text
            embed.add_field(name="현재 잔액", value=format_money(get_balance(self.user_id)), inline=False)
        else:
            embed.set_footer(text="21에 가까울수록 유리합니다. 21을 넘으면 버스트로 패배합니다.")
        return embed

    async def settle(self, interaction: discord.Interaction, reason: str):
        if self.resolved:
            await interaction.response.send_message("이미 결과가 확정되었습니다.", ephemeral=True)
            return

        self.resolved = True
        player_value = blackjack_hand_value(self.player_cards)

        if reason == "stand":
            while blackjack_hand_value(self.dealer_cards) < 17:
                self.dealer_cards.append(draw_blackjack_card())

        dealer_value = blackjack_hand_value(self.dealer_cards)
        payout = 0

        if player_value > 21:
            result_text = f"버스트입니다. `{format_money(self.bet_amount)}`을 잃었습니다."
            result_label = "패배"
            color = 0xE74C3C
        elif dealer_value > 21 or player_value > dealer_value:
            is_natural = len(self.player_cards) == 2 and player_value == 21
            multiplier = 2.5 if is_natural else 2.0
            payout = int(self.bet_amount * multiplier)
            add_balance(self.user_id, payout)
            result_text = f"승리했습니다! `{format_money(payout)}`을 획득했습니다."
            result_label = "블랙잭 승리" if is_natural else "승리"
            color = 0x2ECC71
        elif player_value == dealer_value:
            payout = self.bet_amount
            add_balance(self.user_id, payout)
            result_text = f"무승부입니다. `{format_money(payout)}`을 돌려받았습니다."
            result_label = "무승부"
            color = 0x3498DB
        else:
            result_text = f"딜러 승리입니다. `{format_money(self.bet_amount)}`을 잃었습니다."
            result_label = "패배"
            color = 0xE74C3C

        for item in self.children:
            item.disabled = True

        add_game_history(
            self.guild_id,
            "블랙잭",
            (
                f"{interaction.user.display_name} - 내 패:{' '.join(self.player_cards)}({player_value}) / "
                f"딜러:{' '.join(self.dealer_cards)}({dealer_value}) / {result_label}"
            ),
        )

        await interaction.response.edit_message(
            embed=self.build_embed(reveal_dealer=True, result_text=result_text, color=color),
            view=self,
        )

    async def on_timeout(self):
        if self.resolved:
            return
        self.resolved = True
        add_balance(self.user_id, self.bet_amount)
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="카드 받기", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player_cards.append(draw_blackjack_card())
        if blackjack_hand_value(self.player_cards) > 21:
            await self.settle(interaction, "bust")
            return
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="멈추기", style=discord.ButtonStyle.success)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.settle(interaction, "stand")


class HorseRaceView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, bet_amount: int):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.resolved = False

        for horse in HORSE_RACE_TABLE:
            self.add_item(HorseRaceButton(horse["name"]))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 명령어를 사용한 본인만 누를 수 있습니다.", ephemeral=True)
            return False
        return True

    def pick_winner(self) -> dict:
        return random.choices(
            HORSE_RACE_TABLE,
            weights=[horse["weight"] for horse in HORSE_RACE_TABLE],
            k=1,
        )[0]

    async def finish(self, interaction: discord.Interaction, selected_name: str):
        if self.resolved:
            await interaction.response.send_message("이미 경주가 종료되었습니다.", ephemeral=True)
            return

        self.resolved = True
        winner = self.pick_winner()
        remaining = [horse["name"] for horse in HORSE_RACE_TABLE if horse["name"] != winner["name"]]
        random.shuffle(remaining)
        ranking = [winner["name"]] + remaining
        is_win = selected_name == winner["name"]
        payout = int(self.bet_amount * winner["payout"]) if is_win else 0

        if payout > 0:
            add_balance(self.user_id, payout)

        for item in self.children:
            item.disabled = True

        ranking_text = "\n".join(f"{idx}위: **{name}**" for idx, name in enumerate(ranking, start=1))
        if is_win:
            description = (
                f"선택한 말: **{selected_name}**\n\n"
                f"{ranking_text}\n\n"
                f"적중! `{format_money(payout)}`을 획득했습니다."
            )
            color = 0x2ECC71
            result_label = "적중"
        else:
            description = (
                f"선택한 말: **{selected_name}**\n\n"
                f"{ranking_text}\n\n"
                f"아쉽게도 `{format_money(self.bet_amount)}`을 잃었습니다."
            )
            color = 0xE74C3C
            result_label = "실패"

        embed = discord.Embed(title="🏇 경마 결과", description=description, color=color)
        embed.add_field(name="현재 잔액", value=format_money(get_balance(self.user_id)), inline=False)

        add_game_history(
            self.guild_id,
            "경마",
            f"{interaction.user.display_name} - 선택:{selected_name} / 1위:{winner['name']} / {result_label}",
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.resolved:
            return
        self.resolved = True
        add_balance(self.user_id, self.bet_amount)
        for item in self.children:
            item.disabled = True


class HorseRaceButton(discord.ui.Button):
    def __init__(self, horse_name: str):
        super().__init__(label=horse_name, style=discord.ButtonStyle.primary)
        self.horse_name = horse_name

    async def callback(self, interaction: discord.Interaction):
        await self.view.finish(interaction, self.horse_name)


def generate_number_baseball_answer() -> str:
    return "".join(random.sample("0123456789", NUMBER_BASEBALL_DIGITS))


def validate_number_baseball_guess(guess: str) -> str | None:
    if len(guess) != NUMBER_BASEBALL_DIGITS or not guess.isdigit():
        return f"서로 다른 숫자 {NUMBER_BASEBALL_DIGITS}개를 입력해주세요. 예: `1379`"
    if len(set(guess)) != NUMBER_BASEBALL_DIGITS:
        return f"중복되지 않는 숫자 {NUMBER_BASEBALL_DIGITS}개를 입력해주세요. 예: `1379`"
    return None


def score_number_baseball(answer: str, guess: str) -> tuple[int, int]:
    strikes = sum(1 for idx, digit in enumerate(guess) if answer[idx] == digit)
    balls = sum(1 for digit in guess if digit in answer) - strikes
    return strikes, balls


def get_number_baseball_multiplier(attempt_count: int) -> float:
    if attempt_count <= 3:
        return 4.0
    if attempt_count <= 5:
        return 2.5
    return 1.5


def roll_dice_poker_hand() -> list[int]:
    return [random.randint(1, 6) for _ in range(5)]


def evaluate_dice_poker_hand(dice: list[int]) -> tuple[str, float]:
    counts = sorted([dice.count(value) for value in set(dice)], reverse=True)
    unique_values = set(dice)

    if counts == [5]:
        hand_name = "야추"
    elif counts == [4, 1]:
        hand_name = "포카드"
    elif counts == [3, 2]:
        hand_name = "풀하우스"
    elif unique_values == {1, 2, 3, 4, 5} or unique_values == {2, 3, 4, 5, 6}:
        hand_name = "라지 스트레이트"
    elif any(sequence.issubset(unique_values) for sequence in ({1, 2, 3, 4}, {2, 3, 4, 5}, {3, 4, 5, 6})):
        hand_name = "스몰 스트레이트"
    elif counts == [3, 1, 1]:
        hand_name = "트리플"
    elif counts == [2, 2, 1]:
        hand_name = "투페어"
    elif counts == [2, 1, 1, 1]:
        hand_name = "원페어"
    else:
        hand_name = "노페어"

    return hand_name, DICE_POKER_PAYOUTS[hand_name]


def get_dice_poker_tiebreaker(dice: list[int]) -> tuple[int, ...]:
    counts = {}
    for value in dice:
        counts[value] = counts.get(value, 0) + 1
    grouped_values = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    return tuple(value for value, count in grouped_values for _ in range(count))


def compare_dice_poker_hands(left_dice: list[int], right_dice: list[int]) -> int:
    left_name, _ = evaluate_dice_poker_hand(left_dice)
    right_name, _ = evaluate_dice_poker_hand(right_dice)
    left_rank = DICE_POKER_RANKS[left_name]
    right_rank = DICE_POKER_RANKS[right_name]

    if left_rank > right_rank:
        return 1
    if left_rank < right_rank:
        return -1

    left_tiebreaker = get_dice_poker_tiebreaker(left_dice)
    right_tiebreaker = get_dice_poker_tiebreaker(right_dice)
    if left_tiebreaker > right_tiebreaker:
        return 1
    if left_tiebreaker < right_tiebreaker:
        return -1
    return 0


def format_dice_poker_hand(dice: list[int]) -> str:
    return " | ".join(f"🎲 {value}" for value in dice)


def build_yahtzee_result_embed(
    challenger: discord.Member | discord.User | None,
    opponent: discord.Member | discord.User | None,
    challenger_dice: list[int],
    opponent_dice: list[int],
    amount: int,
    result_text: str,
    color: int,
):
    challenger_name = challenger.display_name if challenger else "도전자"
    opponent_name = opponent.display_name if opponent else "마리봇"
    challenger_hand, _ = evaluate_dice_poker_hand(challenger_dice)
    opponent_hand, _ = evaluate_dice_poker_hand(opponent_dice)
    pot_amount = amount * 2

    embed = discord.Embed(title="🎲 야추 대결 결과", description=result_text, color=color)
    embed.add_field(
        name=challenger_name,
        value=(
            f"{format_dice_poker_hand(challenger_dice)}\n"
            f"숫자: `{' '.join(str(value) for value in challenger_dice)}`\n"
            f"족보: **{challenger_hand}**"
        ),
        inline=False,
    )
    embed.add_field(
        name=opponent_name,
        value=(
            f"{format_dice_poker_hand(opponent_dice)}\n"
            f"숫자: `{' '.join(str(value) for value in opponent_dice)}`\n"
            f"족보: **{opponent_hand}**"
        ),
        inline=False,
    )
    embed.add_field(name="판돈", value=f"`{format_money(pot_amount)}`", inline=False)
    return embed


def format_yahtzee_visible_dice(dice: list[int], reveal_all: bool = False) -> str:
    if reveal_all:
        return format_dice_poker_hand(dice)
    return f"{format_dice_poker_hand(dice[:3])} | ? | ?"


def format_yahtzee_action(action: str | None) -> str:
    if action == "bet":
        return "배팅"
    if action == "allin":
        return "올인"
    if action == "die":
        return "다이"
    return "선택 대기"


def build_yahtzee_progress_embed(
    challenger: discord.Member | discord.User | None,
    opponent: discord.Member | discord.User | None,
    challenger_dice: list[int],
    opponent_dice: list[int],
    amount: int,
    pot_amount: int,
    challenger_action: str | None,
    opponent_action: str | None,
):
    challenger_name = challenger.display_name if challenger else "도전자"
    opponent_name = opponent.display_name if opponent else "마리봇"
    embed = discord.Embed(
        title="🎲 야추 대결",
        description="각자 주사위 5개 중 3개가 먼저 공개되었습니다.\n배팅 또는 다이를 선택해주세요.",
        color=0xF1C40F,
    )
    embed.add_field(name="기본 베팅금", value=f"`{format_money(amount)}`", inline=True)
    embed.add_field(name="현재 판돈", value=f"`{format_money(pot_amount)}`", inline=True)
    embed.add_field(
        name=challenger_name,
        value=(
            f"{format_yahtzee_visible_dice(challenger_dice)}\n"
            f"상태: `{format_yahtzee_action(challenger_action)}`"
        ),
        inline=False,
    )
    embed.add_field(
        name=opponent_name,
        value=(
            f"{format_yahtzee_visible_dice(opponent_dice)}\n"
            f"상태: `{format_yahtzee_action(opponent_action)}`"
        ),
        inline=False,
    )
    embed.set_footer(text="둘 다 배팅해야 남은 주사위 2개를 공개하고 승부합니다.")
    return embed


class YahtzeeMatchView(discord.ui.View):
    def __init__(self, guild_id: int, challenger_id: int, opponent_id: int | None, amount: int):
        super().__init__(timeout=SEOTDA_TIMEOUT)
        self.guild_id = guild_id
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id
        self.amount = amount
        self.pot_amount = amount * 2
        self.challenger_dice = roll_dice_poker_hand()
        self.opponent_dice = roll_dice_poker_hand()
        self.challenger_action: str | None = None
        self.opponent_action: str | None = None
        self.challenger_bet_amount = 0
        self.opponent_bet_amount = 0
        self.resolved = False

    def _is_bot_match(self) -> bool:
        return self.opponent_id is None

    def _get_role_key(self, user_id: int) -> str | None:
        if user_id == self.challenger_id:
            return "challenger"
        if user_id == self.opponent_id:
            return "opponent"
        return None

    def _set_action(self, role_key: str, action: str):
        if role_key == "challenger":
            self.challenger_action = action
        elif role_key == "opponent":
            self.opponent_action = action

    def _get_action(self, role_key: str) -> str | None:
        return self.challenger_action if role_key == "challenger" else self.opponent_action

    def _get_participants(self, guild: discord.Guild, bot_user: discord.ClientUser | None):
        challenger = guild.get_member(self.challenger_id)
        if self._is_bot_match():
            opponent = bot_user
        else:
            opponent = guild.get_member(self.opponent_id)
        return challenger, opponent

    def build_embed(self, guild: discord.Guild, bot_user: discord.ClientUser | None):
        challenger, opponent = self._get_participants(guild, bot_user)
        return build_yahtzee_progress_embed(
            challenger,
            opponent,
            self.challenger_dice,
            self.opponent_dice,
            self.amount,
            self.pot_amount,
            self.challenger_action,
            self.opponent_action,
        )

    def _apply_additional_bet(self, role_key: str, user_id: int | None) -> str:
        if user_id is None:
            additional_amount = self.amount
        else:
            current_balance = get_balance(user_id)
            additional_amount = min(current_balance, self.amount)
            if additional_amount > 0:
                add_balance(user_id, -additional_amount)

        if role_key == "challenger":
            self.challenger_bet_amount = additional_amount
        else:
            self.opponent_bet_amount = additional_amount

        self.pot_amount += additional_amount
        return "bet" if additional_amount >= self.amount else "allin"

    def _settle_all_in_difference(self):
        matched_amount = min(self.challenger_bet_amount, self.opponent_bet_amount)

        if self.challenger_bet_amount > matched_amount:
            refund = self.challenger_bet_amount - matched_amount
            add_balance(self.challenger_id, refund)
            self.pot_amount -= refund
            self.challenger_bet_amount = matched_amount

        if self.opponent_id is not None and self.opponent_bet_amount > matched_amount:
            refund = self.opponent_bet_amount - matched_amount
            add_balance(self.opponent_id, refund)
            self.pot_amount -= refund
            self.opponent_bet_amount = matched_amount

        if self.opponent_id is None and self.opponent_bet_amount > matched_amount:
            refund = self.opponent_bet_amount - matched_amount
            self.pot_amount -= refund
            self.opponent_bet_amount = matched_amount

    async def _resolve_round(self, interaction: discord.Interaction):
        self.resolved = True
        challenger, opponent = self._get_participants(interaction.guild, interaction.client.user)

        if self.challenger_action == "die" and self.opponent_action == "die":
            add_balance(self.challenger_id, self.amount)
            if not self._is_bot_match():
                add_balance(self.opponent_id, self.amount)
            embed = discord.Embed(
                title="🎲 야추 대결 결과",
                description="두 사람이 모두 다이를 선택해 무승부가 되었습니다.\n처음 건 금액은 각각 반환되었습니다.",
                color=0x95A5A6,
            )
            embed.add_field(name="판돈", value=f"`{format_money(self.pot_amount)}`", inline=False)
            add_game_history(interaction.guild.id, "야추", f"{challenger.display_name} vs {opponent.display_name if opponent else '마리봇'} / 양쪽 다이 무승부")
            await interaction.response.edit_message(embed=embed, view=None)
            return

        if self.challenger_action == "die" and self.opponent_action in {"bet", "allin"}:
            if not self._is_bot_match():
                add_balance(self.opponent_id, self.pot_amount)
            embed = discord.Embed(
                title="🎲 야추 대결 결과",
                description=f"{challenger.mention}님이 다이를 선택했습니다.\n{opponent.mention if opponent else '마리봇'} 승리!",
                color=0x3498DB,
            )
            embed.add_field(name="판돈", value=f"`{format_money(self.pot_amount)}`", inline=False)
            add_game_history(interaction.guild.id, "야추", f"{challenger.display_name} vs {opponent.display_name if opponent else '마리봇'} / 다이 패배")
            await interaction.response.edit_message(embed=embed, view=None)
            return

        if self.challenger_action in {"bet", "allin"} and self.opponent_action == "die":
            add_balance(self.challenger_id, self.pot_amount)
            embed = discord.Embed(
                title="🎲 야추 대결 결과",
                description=f"{opponent.mention if opponent else '마리봇'}이 다이를 선택했습니다.\n{challenger.mention}님 승리!",
                color=0x2ECC71,
            )
            embed.add_field(name="판돈", value=f"`{format_money(self.pot_amount)}`", inline=False)
            add_game_history(interaction.guild.id, "야추", f"{challenger.display_name} vs {opponent.display_name if opponent else '마리봇'} / 다이 승리")
            await interaction.response.edit_message(embed=embed, view=None)
            return

        self._settle_all_in_difference()
        comparison = compare_dice_poker_hands(self.challenger_dice, self.opponent_dice)
        challenger_hand, _ = evaluate_dice_poker_hand(self.challenger_dice)
        opponent_hand, _ = evaluate_dice_poker_hand(self.opponent_dice)

        if comparison > 0:
            add_balance(self.challenger_id, self.pot_amount)
            result_text = f"{challenger.mention}님 승리!\n`{format_money(self.pot_amount)}`을 획득했습니다."
            color = 0x2ECC71
            history_text = f"{challenger.display_name} vs {opponent.display_name if opponent else '마리봇'} / {challenger_hand} 승리"
        elif comparison < 0:
            if not self._is_bot_match():
                add_balance(self.opponent_id, self.pot_amount)
            result_text = f"{opponent.mention if opponent else '마리봇'} 승리!"
            if not self._is_bot_match():
                result_text += f"\n`{format_money(self.pot_amount)}`을 획득했습니다."
            color = 0x3498DB
            history_text = f"{challenger.display_name} vs {opponent.display_name if opponent else '마리봇'} / {opponent_hand} 승리"
        else:
            add_balance(self.challenger_id, self.pot_amount // 2)
            if not self._is_bot_match():
                add_balance(self.opponent_id, self.pot_amount // 2)
            result_text = "같은 수준의 족보가 나와 무승부입니다. 판돈은 반씩 반환되었습니다."
            color = 0x95A5A6
            history_text = f"{challenger.display_name} vs {opponent.display_name if opponent else '마리봇'} / 무승부 ({challenger_hand})"

        embed = build_yahtzee_result_embed(
            challenger,
            opponent,
            self.challenger_dice,
            self.opponent_dice,
            self.pot_amount // 2,
            result_text,
            color,
        )
        add_game_history(interaction.guild.id, "야추", history_text)
        await interaction.response.edit_message(embed=embed, view=None)

    async def _handle_choice(self, interaction: discord.Interaction, action: str):
        if self.resolved:
            await interaction.response.send_message("이미 결과가 확정된 판입니다.", ephemeral=True)
            return

        role_key = self._get_role_key(interaction.user.id)
        if role_key is None:
            await interaction.response.send_message("대결 당사자만 버튼을 누를 수 있습니다.", ephemeral=True)
            return

        if self._get_action(role_key) is not None:
            await interaction.response.send_message("이미 선택을 완료했습니다.", ephemeral=True)
            return

        if action == "bet":
            action = self._apply_additional_bet(role_key, interaction.user.id)

        self._set_action(role_key, action)

        if self._is_bot_match() and role_key == "challenger":
            if action == "die":
                self.opponent_action = "bet"
                self.opponent_bet_amount = 0
            else:
                bot_action = self._apply_additional_bet("opponent", None)
                self._set_action("opponent", bot_action)

        if self.challenger_action is not None and self.opponent_action is not None:
            await self._resolve_round(interaction)
            return

        await interaction.response.edit_message(embed=self.build_embed(interaction.guild, interaction.client.user), view=self)

    @discord.ui.button(label="배팅", style=discord.ButtonStyle.success)
    async def bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "bet")

    @discord.ui.button(label="다이", style=discord.ButtonStyle.danger)
    async def die(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "die")


def resolve_yahtzee_match(guild_id: int, challenger, opponent, amount: int):
    challenger_dice = roll_dice_poker_hand()
    opponent_dice = roll_dice_poker_hand()
    challenger_name = challenger.display_name if challenger else "도전자"
    opponent_name = opponent.display_name if opponent else "마리봇"
    comparison = compare_dice_poker_hands(challenger_dice, opponent_dice)
    challenger_hand, _ = evaluate_dice_poker_hand(challenger_dice)
    opponent_hand, _ = evaluate_dice_poker_hand(opponent_dice)
    pot_amount = amount * 2

    if comparison > 0:
        add_balance(challenger.id, pot_amount)
        result_text = f"{challenger.mention}님 승리!\n`{format_money(pot_amount)}`을 획득했습니다."
        color = 0x2ECC71
        history_text = f"{challenger_name} vs {opponent_name} / {challenger_hand} 승리"
    elif comparison < 0:
        if opponent is not None and not getattr(opponent, "bot", False):
            add_balance(opponent.id, pot_amount)
        result_text = f"{opponent.mention if opponent else '마리봇'} 승리!"
        if opponent is not None and not getattr(opponent, "bot", False):
            result_text += f"\n`{format_money(pot_amount)}`을 획득했습니다."
        color = 0x3498DB
        history_text = f"{challenger_name} vs {opponent_name} / {opponent_hand} 승리"
    else:
        add_balance(challenger.id, amount)
        if opponent is not None and not getattr(opponent, "bot", False):
            add_balance(opponent.id, amount)
        result_text = "같은 수준의 족보가 나와 무승부입니다. 각자 베팅금이 반환되었습니다."
        color = 0x95A5A6
        history_text = f"{challenger_name} vs {opponent_name} / 무승부 ({challenger_hand})"

    add_game_history(guild_id, "야추", history_text)
    return build_yahtzee_result_embed(
        challenger,
        opponent,
        challenger_dice,
        opponent_dice,
        amount,
        result_text,
        color,
    )


class YahtzeeChallengeView(discord.ui.View):
    def __init__(self, challenger_id: int, opponent_id: int, amount: int):
        super().__init__(timeout=60)
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id
        self.amount = amount
        self.resolved = False

    async def _ensure_opponent(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.opponent_id:
            await interaction.response.send_message("이 버튼은 대결 요청을 받은 본인만 누를 수 있습니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="수락", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.resolved or not await self._ensure_opponent(interaction):
            return

        challenger = interaction.guild.get_member(self.challenger_id)
        opponent = interaction.guild.get_member(self.opponent_id)
        if challenger is None or opponent is None:
            await interaction.response.send_message("대결 대상 중 한 명을 찾을 수 없습니다.", ephemeral=True)
            return

        if not can_afford(challenger.id, self.amount):
            await interaction.response.send_message("도전자의 잔액이 부족해 대결을 시작할 수 없습니다.", ephemeral=True)
            return

        if not can_afford(opponent.id, self.amount):
            await interaction.response.send_message("본인의 잔액이 부족해 대결을 시작할 수 없습니다.", ephemeral=True)
            return

        self.resolved = True
        add_balance(challenger.id, -self.amount)
        add_balance(opponent.id, -self.amount)

        for item in self.children:
            item.disabled = True

        match_view = YahtzeeMatchView(interaction.guild.id, self.challenger_id, self.opponent_id, self.amount)
        embed = match_view.build_embed(interaction.guild, interaction.client.user)
        await interaction.response.edit_message(content=None, embed=embed, view=match_view)

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.resolved or not await self._ensure_opponent(interaction):
            return

        self.resolved = True
        challenger = interaction.guild.get_member(self.challenger_id)
        opponent = interaction.guild.get_member(self.opponent_id)
        embed = discord.Embed(
            title="🎲 야추 대결 요청",
            description=f"{opponent.mention if opponent else '상대방'}님이 대결을 거절했습니다.",
            color=0xE74C3C,
        )
        if challenger is not None and opponent is not None:
            embed.add_field(name="도전자", value=challenger.mention, inline=True)
            embed.add_field(name="상대", value=opponent.mention, inline=True)
        embed.add_field(name="베팅금", value=f"`{format_money(self.amount)}`", inline=False)

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)


class NumberBaseballGuessModal(discord.ui.Modal):
    def __init__(self, game_view):
        super().__init__(title="숫자야구 입력")
        self.game_view = game_view
        self.guess = discord.ui.TextInput(
            label="예상 숫자",
            placeholder="예: 1379",
            min_length=NUMBER_BASEBALL_DIGITS,
            max_length=NUMBER_BASEBALL_DIGITS,
            required=True,
        )
        self.add_item(self.guess)

    async def on_submit(self, interaction: discord.Interaction):
        await self.game_view.submit_guess(interaction, str(self.guess).strip())


class NumberBaseballView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, bet_amount: int):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.answer = generate_number_baseball_answer()
        self.records: list[tuple[str, str]] = []
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 명령어를 사용한 본인만 누를 수 있습니다.", ephemeral=True)
            return False
        return True

    def build_embed(self, result_text: str | None = None, color: int = 0x3498DB):
        remaining = max(0, NUMBER_BASEBALL_ATTEMPTS - len(self.records))
        record_text = "\n".join(
            f"{idx}. `{guess}` → {result}"
            for idx, (guess, result) in enumerate(self.records, start=1)
        ) or "아직 입력 기록이 없습니다."

        embed = discord.Embed(
            title="⚾ 숫자야구",
            description=result_text or f"마리봇이 서로 다른 숫자 {NUMBER_BASEBALL_DIGITS}개를 정했습니다.",
            color=color,
        )
        embed.add_field(name="베팅 금액", value=format_money(self.bet_amount), inline=False)
        embed.add_field(name="남은 기회", value=f"{remaining}회", inline=True)
        embed.add_field(name="입력 기록", value=record_text, inline=False)
        embed.add_field(
            name="규칙",
            value="숫자와 위치가 모두 맞으면 S\n숫자만 맞으면 B\n아무것도 맞지 않으면 OUT",
            inline=False,
        )
        if self.resolved:
            embed.add_field(name="정답", value=f"`{self.answer}`", inline=True)
            embed.add_field(name="현재 잔액", value=format_money(get_balance(self.user_id)), inline=False)
        else:
            embed.set_footer(text="숫자 입력 버튼을 눌러 정답을 추리하세요.")
        return embed

    async def finish(self, interaction: discord.Interaction, result_text: str, result_label: str, color: int):
        self.resolved = True
        for item in self.children:
            item.disabled = True

        add_game_history(
            self.guild_id,
            "숫자야구",
            f"{interaction.user.display_name} - 정답:{self.answer} / 시도:{len(self.records)}회 / {result_label}",
        )

        await interaction.response.edit_message(
            embed=self.build_embed(result_text=result_text, color=color),
            view=self,
        )

    async def submit_guess(self, interaction: discord.Interaction, guess: str):
        if self.resolved:
            await interaction.response.send_message("이미 숫자야구가 종료되었습니다.", ephemeral=True)
            return

        error_text = validate_number_baseball_guess(guess)
        if error_text:
            await interaction.response.send_message(error_text, ephemeral=True)
            return

        if any(previous_guess == guess for previous_guess, _ in self.records):
            await interaction.response.send_message("이미 입력했던 숫자입니다. 다른 숫자를 입력해주세요.", ephemeral=True)
            return

        strikes, balls = score_number_baseball(self.answer, guess)
        if strikes == NUMBER_BASEBALL_DIGITS:
            self.records.append((guess, f"{NUMBER_BASEBALL_DIGITS}S"))
            attempt_count = len(self.records)
            multiplier = get_number_baseball_multiplier(attempt_count)
            payout = int(self.bet_amount * multiplier)
            add_balance(self.user_id, payout)
            await self.finish(
                interaction,
                f"정답입니다! `{attempt_count}회` 만에 맞혀 `{format_money(payout)}`을 획득했습니다.",
                f"성공 {attempt_count}회 / {multiplier}배",
                0x2ECC71,
            )
            return

        result = "OUT" if strikes == 0 and balls == 0 else f"{strikes}S {balls}B"
        self.records.append((guess, result))

        if len(self.records) >= NUMBER_BASEBALL_ATTEMPTS:
            await self.finish(
                interaction,
                f"기회를 모두 사용했습니다. `{format_money(self.bet_amount)}`을 잃었습니다.",
                "실패",
                0xE74C3C,
            )
            return

        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_timeout(self):
        if self.resolved:
            return
        self.resolved = True
        add_balance(self.user_id, self.bet_amount)
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="숫자 입력", style=discord.ButtonStyle.primary)
    async def guess_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NumberBaseballGuessModal(self))


def get_minesweeper_multiplier(safe_count: int) -> float:
    return MINESWEEPER_MULTIPLIERS.get(safe_count, 1.0)


class MinesweeperCellButton(discord.ui.Button):
    def __init__(self, index: int):
        super().__init__(
            label="⬜",
            style=discord.ButtonStyle.secondary,
            row=index // MINESWEEPER_SIZE,
        )
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        await self.view.reveal_cell(interaction, self)


class MinesweeperCashoutButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="수익 확정", style=discord.ButtonStyle.success, row=4)

    async def callback(self, interaction: discord.Interaction):
        await self.view.cash_out(interaction)


class MinesweeperView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, bet_amount: int):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.safe_count = 0
        self.resolved = False
        total_cells = MINESWEEPER_SIZE * MINESWEEPER_SIZE
        self.mine_positions = set(random.sample(range(total_cells), MINESWEEPER_MINE_COUNT))

        for index in range(total_cells):
            self.add_item(MinesweeperCellButton(index))
        self.add_item(MinesweeperCashoutButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 명령어를 사용한 본인만 누를 수 있습니다.", ephemeral=True)
            return False
        return True

    def current_multiplier(self) -> float:
        return get_minesweeper_multiplier(self.safe_count)

    def current_payout(self) -> int:
        return int(self.bet_amount * self.current_multiplier())

    def build_embed(self, title: str = "💣 지뢰찾기", description: str | None = None, color: int = 0xF1C40F):
        multiplier = self.current_multiplier()
        embed = discord.Embed(
            title=title,
            description=description or "안전 칸을 열수록 배당이 올라갑니다. 지뢰를 밟기 전에 수익을 확정하세요.",
            color=color,
        )
        embed.add_field(name="베팅 금액", value=format_money(self.bet_amount), inline=True)
        embed.add_field(name="안전 칸", value=f"`{self.safe_count}개`", inline=True)
        embed.add_field(name="현재 배당", value=f"`{multiplier:.2f}배`", inline=True)
        embed.add_field(name="예상 수령액", value=format_money(self.current_payout()), inline=False)
        embed.set_footer(text=f"{MINESWEEPER_SIZE}x{MINESWEEPER_SIZE} 보드 / 지뢰 {MINESWEEPER_MINE_COUNT}개")
        return embed

    def disable_all_buttons(self):
        for item in self.children:
            item.disabled = True

    def reveal_all_mines(self):
        for item in self.children:
            if isinstance(item, MinesweeperCellButton) and item.index in self.mine_positions:
                item.label = "💣"
                item.style = discord.ButtonStyle.danger

    async def reveal_cell(self, interaction: discord.Interaction, button: MinesweeperCellButton):
        if self.resolved:
            await interaction.response.send_message("이미 종료된 지뢰찾기입니다.", ephemeral=True)
            return

        if button.index in self.mine_positions:
            self.resolved = True
            button.label = "💥"
            button.style = discord.ButtonStyle.danger
            self.reveal_all_mines()
            self.disable_all_buttons()
            embed = self.build_embed(
                title="💥 지뢰 폭발!",
                description=f"지뢰를 밟았습니다. `{format_money(self.bet_amount)}`을 잃었습니다.",
                color=0xE74C3C,
            )
            add_game_history(
                self.guild_id,
                "지뢰찾기",
                f"{interaction.user.display_name} - 안전:{self.safe_count}개 / 폭발",
            )
            await interaction.response.edit_message(embed=embed, view=self)
            return

        button.label = "💎"
        button.style = discord.ButtonStyle.success
        button.disabled = True
        self.safe_count += 1

        max_safe_count = MINESWEEPER_SIZE * MINESWEEPER_SIZE - MINESWEEPER_MINE_COUNT
        if self.safe_count >= max_safe_count:
            await self.cash_out(interaction, auto_complete=True)
            return

        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def cash_out(self, interaction: discord.Interaction, auto_complete: bool = False):
        if self.resolved:
            await interaction.response.send_message("이미 종료된 지뢰찾기입니다.", ephemeral=True)
            return

        self.resolved = True
        payout = self.current_payout()
        add_balance(self.user_id, payout)
        self.disable_all_buttons()

        title = "✅ 지뢰찾기 완전 성공" if auto_complete else "✅ 지뢰찾기 수익 확정"
        embed = self.build_embed(
            title=title,
            description=f"`{format_money(payout)}`을 획득했습니다.",
            color=0x2ECC71,
        )
        embed.add_field(name="현재 잔액", value=format_money(get_balance(self.user_id)), inline=False)
        add_game_history(
            self.guild_id,
            "지뢰찾기",
            f"{interaction.user.display_name} - 안전:{self.safe_count}개 / {self.current_multiplier():.2f}배 수익 확정",
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.resolved:
            return
        self.resolved = True
        add_balance(self.user_id, self.bet_amount)
        self.disable_all_buttons()


class SupplyDropView(discord.ui.View):
    def __init__(self, user_id: int, bet_amount: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "이 버튼은 명령어를 사용한 본인만 누를 수 있습니다.",
                ephemeral=True,
            )
            return False
        return True

    def roll_result(self):
        result = random.choices(
            [
                ("빈 상자", 0.0, "보급 상자를 열었지만 아쉽게도 아무것도 나오지 않았습니다."),
                ("1뚝", 1.0, "낡은 1뚝을 챙겼습니다. 큰 수확은 아니지만 빈손은 아닙니다."),
                ("2뚝", 1.1, "2뚝을 획득했습니다. 본전 이상은 챙겼습니다."),
                ("3뚝", 1.6, "3뚝을 획득했습니다! 이번 교전은 조금 더 든든합니다."),
                ("보급 총기 획득", 2.6, "보급 총기를 획득했습니다! 분위기가 달아오르기 시작합니다."),
                ("풀세트 보급 대박", 4.7, "3뚝과 보급 총기까지 모두 챙겼습니다! 말 그대로 풀세트 보급 대박입니다!"),
            ],
            weights=[34, 24, 19, 11, 9, 3],
            k=1,
        )[0]
        return result


    async def open_supply(self, interaction: discord.Interaction):
        if self.resolved:
            await interaction.response.send_message("이미 보급 결과가 확정되었습니다.", ephemeral=True)
            return

        self.resolved = True
        force_info = get_hidden_gambling_force(self.user_id)
        if force_info and force_info["game_name"] == "supply":
            consume_hidden_gambling_force(self.user_id)
            result_name, multiplier, flavor_text = (
                "풀세트 보급 대박",
                4.7,
                "3뚝과 보급 총기까지 모두 챙겼습니다! 말 그대로 풀세트 보급 대박입니다!",
            )
        else:
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

    @discord.ui.button(label="보급 열기", style=discord.ButtonStyle.primary)
    async def open_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_supply(interaction)


class SeotdaResultView(discord.ui.View):
    def __init__(self, guild_id: int, challenger_id: int, opponent_id: int | None, next_amount: int | None, winner_id: int | None):
        super().__init__(timeout=SEOTDA_TIMEOUT)
        self.guild_id = guild_id
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id
        self.next_amount = next_amount
        self.winner_id = winner_id

    @discord.ui.button(label="묻고 따블로?", style=discord.ButtonStyle.success)
    async def double(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.winner_id is None or self.next_amount is None:
            await interaction.response.send_message("이번 판은 묻고 따블로를 진행할 수 없습니다.", ephemeral=True)
            return

        if interaction.user.id != self.winner_id:
            await interaction.response.send_message("이번 판의 승자만 묻고 따블로를 누를 수 있습니다.", ephemeral=True)
            return

        challenger = interaction.guild.get_member(self.challenger_id)
        if challenger is None:
            await interaction.response.send_message("도전자를 찾을 수 없습니다.", ephemeral=True)
            return

        if not can_afford(challenger.id, self.next_amount):
            await interaction.response.send_message("도전자의 잔액이 부족해 묻고 따블로를 진행할 수 없습니다.", ephemeral=True)
            return

        opponent_is_bot = self.opponent_id is None
        opponent = None if opponent_is_bot else interaction.guild.get_member(self.opponent_id)
        if not opponent_is_bot and opponent is None:
            await interaction.response.send_message("상대를 찾을 수 없습니다.", ephemeral=True)
            return

        if opponent_is_bot:
            add_balance(challenger.id, -self.next_amount)
            match_view = SeotdaMatchView(self.guild_id, self.winner_id, None, self.next_amount)
            embed = match_view.build_embed(interaction.guild, interaction.client.user)
            embed.add_field(name="상대", value="봇", inline=False)
            await interaction.response.edit_message(embed=embed, view=match_view)
            return

        requester_id = self.winner_id
        target_id = self.opponent_id if self.winner_id == self.challenger_id else self.challenger_id
        requester = interaction.guild.get_member(requester_id)
        target = interaction.guild.get_member(target_id)

        if requester is None or target is None:
            await interaction.response.send_message("재대결 대상을 찾을 수 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🃏 섯다 재대결 요청",
            description=f"{target.mention}님, {requester.mention}님이 묻고 따블로를 신청했습니다.",
            color=0xF1C40F,
        )
        embed.add_field(name="도전자", value=requester.mention, inline=True)
        embed.add_field(name="상대", value=target.mention, inline=True)
        embed.add_field(name="기본 배팅금", value=f"`{format_money(self.next_amount)}`", inline=False)
        embed.add_field(
            name="룰",
            value=(
                "수락 시 두 사람 모두 같은 금액을 먼저 겁니다.\n"
                "첫 패 공개 후 `배팅` 또는 `다이`를 선택합니다.\n"
                "둘 다 배팅해야 다음 패를 공개하고 승부합니다."
            ),
            inline=False,
        )
        embed.set_footer(text="상대방만 수락 또는 거절할 수 있습니다.")
        await interaction.response.edit_message(
            embed=embed,
            view=SeotdaChallengeView(requester_id, target_id, self.next_amount),
        )

    @discord.ui.button(label="다이", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in {self.challenger_id, self.opponent_id}:
            await interaction.response.send_message("대결 당사자만 종료할 수 있습니다.", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True

        embed = interaction.message.embeds[0]
        embed.set_footer(text="섯다 게임이 종료되었습니다.")
        await interaction.response.edit_message(embed=embed, view=self)


class SeotdaMatchView(discord.ui.View):
    def __init__(self, guild_id: int, challenger_id: int, opponent_id: int | None, amount: int):
        super().__init__(timeout=SEOTDA_TIMEOUT)
        self.guild_id = guild_id
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id
        self.amount = amount
        self.pot_amount = amount * 2
        self.challenger_cards, self.opponent_cards = draw_seotda_hands()
        self.challenger_action: str | None = None
        self.opponent_action: str | None = None
        self.challenger_bet_amount = 0
        self.opponent_bet_amount = 0
        self.resolved = False

    def _is_bot_match(self) -> bool:
        return self.opponent_id is None

    def _get_role_key(self, user_id: int) -> str | None:
        if user_id == self.challenger_id:
            return "challenger"
        if user_id == self.opponent_id:
            return "opponent"
        return None

    def _set_action(self, role_key: str, action: str):
        if role_key == "challenger":
            self.challenger_action = action
        elif role_key == "opponent":
            self.opponent_action = action

    def _get_action(self, role_key: str) -> str | None:
        return self.challenger_action if role_key == "challenger" else self.opponent_action

    def _get_participants(self, guild: discord.Guild, bot_user: discord.ClientUser | None):
        challenger = guild.get_member(self.challenger_id)
        if self._is_bot_match():
            opponent = bot_user
        else:
            opponent = guild.get_member(self.opponent_id)
        return challenger, opponent

    def build_embed(self, guild: discord.Guild, bot_user: discord.ClientUser | None):
        challenger, opponent = self._get_participants(guild, bot_user)
        return build_seotda_progress_embed(
            challenger,
            opponent,
            self.challenger_cards,
            self.opponent_cards,
            self.amount,
            self.pot_amount,
            self.challenger_action,
            self.opponent_action,
        )

    def _bot_should_bet(self) -> bool:
        return True

    def _apply_additional_bet(self, role_key: str, user_id: int | None) -> str:
        if user_id is None:
            additional_amount = self.amount
        else:
            current_balance = get_balance(user_id)
            additional_amount = min(current_balance, self.amount)
            if additional_amount > 0:
                add_balance(user_id, -additional_amount)

        if role_key == "challenger":
            self.challenger_bet_amount = additional_amount
        else:
            self.opponent_bet_amount = additional_amount

        self.pot_amount += additional_amount
        return "bet" if additional_amount >= self.amount else "allin"

    def _settle_all_in_difference(self):
        matched_amount = min(self.challenger_bet_amount, self.opponent_bet_amount)

        if self.challenger_bet_amount > matched_amount:
            refund = self.challenger_bet_amount - matched_amount
            add_balance(self.challenger_id, refund)
            self.pot_amount -= refund
            self.challenger_bet_amount = matched_amount

        if self.opponent_id is not None and self.opponent_bet_amount > matched_amount:
            refund = self.opponent_bet_amount - matched_amount
            add_balance(self.opponent_id, refund)
            self.pot_amount -= refund
            self.opponent_bet_amount = matched_amount

        if self.opponent_id is None and self.opponent_bet_amount > matched_amount:
            refund = self.opponent_bet_amount - matched_amount
            self.pot_amount -= refund
            self.opponent_bet_amount = matched_amount

        return matched_amount

    async def _resolve_round(self, interaction: discord.Interaction):
        self.resolved = True
        challenger, opponent = self._get_participants(interaction.guild, interaction.client.user)
        result_view: SeotdaResultView

        if self.challenger_action == "die" and self.opponent_action == "die":
            add_balance(self.challenger_id, self.amount)
            if not self._is_bot_match():
                add_balance(self.opponent_id, self.amount)

            embed = discord.Embed(
                title="🃏 섯다 결과",
                description="두 사람이 모두 다이를 선택해 무승부가 되었습니다.\n처음 건 금액은 각각 반환되었습니다.",
                color=0x95A5A6,
            )
            embed.add_field(name="판돈", value=f"`{format_money(self.pot_amount)}`", inline=False)
            add_game_history(interaction.guild.id, "섯다", f"{challenger.display_name} vs {opponent.display_name if opponent else '봇'} / 양쪽 다이 무승부")
            result_view = SeotdaResultView(self.guild_id, self.challenger_id, self.opponent_id, None, None)
            await interaction.response.edit_message(embed=embed, view=result_view)
            return

        if self.challenger_action == "die" and self.opponent_action == "bet":
            if self._is_bot_match():
                winner_id = None
            else:
                add_balance(self.opponent_id, self.pot_amount)
                winner_id = self.opponent_id

            embed = discord.Embed(
                title="🃏 섯다 결과",
                description=f"{challenger.mention}님이 다이를 선택했습니다.\n{opponent.mention if opponent else '봇'} 승리!",
                color=0x3498DB,
            )
            embed.add_field(name="판돈", value=f"`{format_money(self.pot_amount)}`", inline=False)
            add_game_history(interaction.guild.id, "섯다", f"{challenger.display_name} vs {opponent.display_name if opponent else '봇'} / 다이 패배")
            next_amount = self.pot_amount if winner_id is not None else None
            result_view = SeotdaResultView(self.guild_id, self.challenger_id, self.opponent_id, next_amount, winner_id)
            await interaction.response.edit_message(embed=embed, view=result_view)
            return

        if self.challenger_action == "bet" and self.opponent_action == "die":
            add_balance(self.challenger_id, self.pot_amount)
            embed = discord.Embed(
                title="🃏 섯다 결과",
                description=f"{opponent.mention if opponent else '봇'}이 다이를 선택했습니다.\n{challenger.mention}님 승리!",
                color=0x2ECC71,
            )
            embed.add_field(name="판돈", value=f"`{format_money(self.pot_amount)}`", inline=False)
            add_game_history(interaction.guild.id, "섯다", f"{challenger.display_name} vs {opponent.display_name if opponent else '봇'} / 다이 승리")
            result_view = SeotdaResultView(self.guild_id, self.challenger_id, self.opponent_id, self.pot_amount, self.challenger_id)
            await interaction.response.edit_message(embed=embed, view=result_view)
            return

        self._settle_all_in_difference()
        challenger_result = evaluate_seotda_hand(self.challenger_cards)
        opponent_result = evaluate_seotda_hand(self.opponent_cards)

        if challenger_result["score"] > opponent_result["score"]:
            add_balance(self.challenger_id, self.pot_amount)
            result_text = f"{challenger.mention}님 승리!\n`{format_money(self.pot_amount)}`을 획득했습니다."
            color = 0x2ECC71
            history_text = f"{challenger.display_name} vs {opponent.display_name if opponent else '봇'} / {challenger_result['name']} 승리"
            winner_id = self.challenger_id
        elif challenger_result["score"] < opponent_result["score"]:
            if self._is_bot_match():
                winner_id = None
            else:
                add_balance(self.opponent_id, self.pot_amount)
                winner_id = self.opponent_id
            result_text = f"{opponent.mention if opponent else '봇'} 승리!\n`{format_money(self.pot_amount)}`을 획득했습니다."
            color = 0x3498DB
            history_text = f"{challenger.display_name} vs {opponent.display_name if opponent else '봇'} / {opponent_result['name']} 승리"
        else:
            add_balance(self.challenger_id, self.pot_amount // 2)
            if not self._is_bot_match():
                add_balance(self.opponent_id, self.pot_amount // 2)
            result_text = "같은 족보가 나와 무승부입니다. 판돈은 반씩 반환되었습니다."
            color = 0x95A5A6
            history_text = f"{challenger.display_name} vs {opponent.display_name if opponent else '봇'} / 무승부 ({challenger_result['name']})"
            winner_id = None

        embed = build_seotda_result_embed(
            challenger,
            opponent,
            self.challenger_cards,
            self.opponent_cards,
            challenger_result,
            opponent_result,
            self.pot_amount,
            result_text,
            color,
        )
        add_game_history(interaction.guild.id, "섯다", history_text)
        next_amount = self.pot_amount if winner_id is not None else None
        result_view = SeotdaResultView(self.guild_id, self.challenger_id, self.opponent_id, next_amount, winner_id)
        await interaction.response.edit_message(embed=embed, view=result_view)

    async def _handle_choice(self, interaction: discord.Interaction, action: str):
        if self.resolved:
            await interaction.response.send_message("이미 결과가 확정된 판입니다.", ephemeral=True)
            return

        role_key = self._get_role_key(interaction.user.id)
        if role_key is None:
            await interaction.response.send_message("대결 당사자만 버튼을 누를 수 있습니다.", ephemeral=True)
            return

        if self._get_action(role_key) is not None:
            await interaction.response.send_message("이미 선택을 완료했습니다.", ephemeral=True)
            return

        if action == "bet":
            action = self._apply_additional_bet(role_key, interaction.user.id)

        self._set_action(role_key, action)

        if self._is_bot_match() and role_key == "challenger":
            if action == "die":
                self._set_action("opponent", "bet")
            else:
                bot_action = "bet" if self._bot_should_bet() else "die"
                if bot_action == "bet":
                    bot_action = self._apply_additional_bet("opponent", None)
                self._set_action("opponent", bot_action)

        if self.challenger_action is not None and self.opponent_action is not None:
            await self._resolve_round(interaction)
            return

        embed = self.build_embed(interaction.guild, interaction.client.user)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="배팅", style=discord.ButtonStyle.success)
    async def bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "bet")

    @discord.ui.button(label="다이", style=discord.ButtonStyle.danger)
    async def die(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_choice(interaction, "die")


class SeotdaChallengeView(discord.ui.View):
    def __init__(self, challenger_id: int, opponent_id: int, amount: int):
        super().__init__(timeout=SEOTDA_TIMEOUT)
        self.challenger_id = challenger_id
        self.opponent_id = opponent_id
        self.amount = amount
        self.resolved = False

    async def _ensure_opponent(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.opponent_id:
            await interaction.response.send_message("이 버튼은 대결 요청을 받은 본인만 누를 수 있습니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="수락", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.resolved or not await self._ensure_opponent(interaction):
            return

        challenger = interaction.guild.get_member(self.challenger_id)
        opponent = interaction.guild.get_member(self.opponent_id)
        if challenger is None or opponent is None:
            await interaction.response.send_message("대결 대상 중 한 명을 찾을 수 없습니다.", ephemeral=True)
            return

        if not can_afford(challenger.id, self.amount):
            await interaction.response.send_message("도전자의 잔액이 부족해 대결을 시작할 수 없습니다.", ephemeral=True)
            return

        if not can_afford(opponent.id, self.amount):
            await interaction.response.send_message("본인의 잔액이 부족해 대결을 시작할 수 없습니다.", ephemeral=True)
            return

        self.resolved = True
        add_balance(challenger.id, -self.amount)
        add_balance(opponent.id, -self.amount)

        match_view = SeotdaMatchView(interaction.guild.id, self.challenger_id, self.opponent_id, self.amount)
        embed = match_view.build_embed(interaction.guild, interaction.client.user)
        await interaction.response.edit_message(embed=embed, view=match_view)

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.resolved or not await self._ensure_opponent(interaction):
            return

        self.resolved = True
        challenger = interaction.guild.get_member(self.challenger_id)
        opponent = interaction.guild.get_member(self.opponent_id)

        embed = discord.Embed(
            title="🃏 섯다 대결 요청",
            description=f"{opponent.mention if opponent else '상대방'}님이 대결을 거절했습니다.",
            color=0xE74C3C,
        )
        if challenger is not None and opponent is not None:
            embed.add_field(name="도전자", value=challenger.mention, inline=True)
            embed.add_field(name="상대", value=opponent.mention, inline=True)
        embed.add_field(name="기본 배팅금", value=f"`{format_money(self.amount)}`", inline=False)

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)


class TeamSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    async def create_team(self, interaction: discord.Interaction, team_size: int):
        if interaction.user.voice is None:
            await interaction.response.send_message("음성채널에 들어가 있어야 합니다.", ephemeral=True)
            return

        channel = interaction.user.voice.channel
        players = [
            member
            for member in channel.members
            if not member.bot and not is_spectator_member(member, interaction.guild.id)
        ]


        if len(players) < 2:
            await interaction.response.send_message("플레이어가 부족합니다.", ephemeral=True)
            return

        random.shuffle(players)
        teams = [players[i:i + team_size] for i in range(0, len(players), team_size)]
        add_team_mix_logs(interaction.guild.id, interaction.message.id, channel.id, team_size, teams)

        embed = discord.Embed(
            title="🎲 랜덤 팀 결과",
            description=f"채널: {channel.name}",
            color=0x2ECC71,
        )
        for index, team in enumerate(teams, start=1):
            embed.add_field(
                name=f"팀 {index}",
                value="\n".join(member.display_name for member in team),
                inline=False,
            )

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
            label=f"{prefix} 적용",
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

    @discord.ui.button(label="티켓보관", style=discord.ButtonStyle.secondary, custom_id="inquiry_archive")
    async def archive_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction):
            await interaction.response.send_message("관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        await interaction.channel.set_permissions(self.user, send_messages=False)
        await interaction.response.send_message("티켓이 보관되었습니다. 작성자는 더 이상 메시지를 보낼 수 없습니다.")

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
            description=f"{user.mention}님의 [{ticket_type}] 티켓입니다.",
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
            lines.append(f"**{idx}. {dt}**\n{format_history_result_text(result_text)}")

        embed = discord.Embed(
            title=f"📜 {game_name} 최근 {min(len(rows), GAME_HISTORY_LIMIT)}게임",
            description="\n\n".join(lines),
            color=0x5865F2,
        )
        embed.set_footer(text="최신 기록이 위에 표시됩니다.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="슬롯", style=discord.ButtonStyle.primary)
    async def slot_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "슬롯")

    @discord.ui.button(label="동전", style=discord.ButtonStyle.primary)
    async def coin_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "동전")

    @discord.ui.button(label="보급", style=discord.ButtonStyle.success)
    async def supply_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "보급")

    @discord.ui.button(label="블랙잭", style=discord.ButtonStyle.success)
    async def blackjack_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "블랙잭")

    @discord.ui.button(label="경마", style=discord.ButtonStyle.success)
    async def horse_race_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "경마")

    @discord.ui.button(label="숫자야구", style=discord.ButtonStyle.success)
    async def number_baseball_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "숫자야구")

    @discord.ui.button(label="야추", style=discord.ButtonStyle.success)
    async def yahtzee_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "야추")

    @discord.ui.button(label="지뢰찾기", style=discord.ButtonStyle.success)
    async def minesweeper_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "지뢰찾기")

    @discord.ui.button(label="섯다", style=discord.ButtonStyle.success)
    async def seotda_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_history(interaction, "섯다")

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
            await interaction.response.send_message("이 버튼은 명령어를 사용한 본인만 누를 수 있습니다.", ephemeral=True)
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
            result_text = "정답은 **팰리컨**이었습니다! 베팅 금액을 그대로 돌려받았습니다."
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
        embed.title = f"🎮 {self.game_name} 모집중!"
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

    @discord.ui.button(label="참여하기", style=discord.ButtonStyle.green)
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
        await interaction.response.send_message(f"바로 이동 권한이 없어 초대 링크를 보내드릴게요: {invite.url}", ephemeral=True)

    @discord.ui.button(label="모집종료", style=discord.ButtonStyle.red)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.host:
            await interaction.response.send_message("모집자만 종료할 수 있습니다.", ephemeral=True)
            return
        await interaction.response.defer()
        await self.auto_close()


class GeneralRecruitModal(discord.ui.Modal, title="종합 구인"):
    game_name = discord.ui.TextInput(
        label="게임 이름",
        placeholder="예: 발로란트, 배그, 마크",
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
            await interaction.response.send_message("음성채널에 먼저 들어가주세요.", ephemeral=True)
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
                    participants.append(f"알 수 없는 유저 ({user_id})")

            participant_text = "\n".join(
                f"{idx}. {name}" for idx, name in enumerate(participants, start=1)
            )
        else:
            participant_text = "아직 참여자가 없습니다."

        if len(embed.fields) >= 1:
            embed.set_field_at(0, name="참여자 목록", value=participant_text, inline=False)
        else:
            embed.add_field(name="참여자 목록", value=participant_text, inline=False)

        for item in self.children:
            if item.custom_id == "scrim_signup_button":
                item.label = f"참여하기 ({len(user_ids)})"

        await message.edit(embed=embed, view=self)

    @discord.ui.button(label="참여하기 (0)", style=discord.ButtonStyle.success, custom_id="scrim_signup_button")
    async def signup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if has_scrim_signup(interaction.message.id, interaction.user.id):
            await interaction.response.send_message("이미 참여 중인 상태입니다.", ephemeral=True)
            return

        add_scrim_signup(interaction.message.id, interaction.user.id)
        await self.update_embed(interaction.message)
        await interaction.response.send_message("내전 참여가 등록되었습니다.", ephemeral=True)

    @discord.ui.button(label="참여취소", style=discord.ButtonStyle.danger, custom_id="scrim_cancel_button")
    async def cancel_signup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_scrim_signup(interaction.message.id, interaction.user.id):
            await interaction.response.send_message("현재 참여 중인 상태가 아닙니다.", ephemeral=True)
            return

        remove_scrim_signup(interaction.message.id, interaction.user.id)
        await self.update_embed(interaction.message)
        await interaction.response.send_message("내전 참여가 취소되었습니다.", ephemeral=True)

class ScrimNoticeModal(discord.ui.Modal, title="내전 공지 작성"):
    title_input = discord.ui.TextInput(
        label="제목",
        placeholder="예: 오늘 오후 9시 내전 모집",
        max_length=100,
        required=True,
    )
    body_input = discord.ui.TextInput(
        label="본문",
        placeholder="예: 참여하실 분은 아래 버튼을 눌러주세요.",
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
        embed.add_field(name="참여자 목록", value="아직 참여자가 없습니다.", inline=False)

        await interaction.channel.send(embed=embed, view=ScrimSignupView())
        await interaction.response.send_message("내전 공지를 등록했습니다.", ephemeral=True)



class LaborWorkView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.user_id = user_id

    async def run_mining(self, interaction: discord.Interaction, mine_key: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 명령어를 사용한 본인만 누를 수 있습니다.", ephemeral=True)
            return

        session_key = (self.guild_id, self.user_id)

        if session_key in labor_click_locks:
            await interaction.response.send_message("이미 다른 노동 클릭을 처리 중입니다. 잠시 후 다시 눌러주세요.", ephemeral=True)
            return

        labor_click_locks.add(session_key)
        try:
            penalty = ensure_active_labor_penalty(self.guild_id, self.user_id)
            if penalty is None:
                updated_penalty = None
                resolved = False
                mine_result = None
            else:
                mine_result = roll_labor_mine_result(mine_key)
                if mine_result["ticket_bonus"] > 0:
                    add_labor_gacha_tickets(self.guild_id, self.user_id, mine_result["ticket_bonus"])
                updated_penalty, resolved = apply_labor_progress(self.guild_id, self.user_id, mine_result["progress"])
        finally:
            labor_click_locks.discard(session_key)

        if updated_penalty is None:
            await interaction.response.send_message("진행 중인 노동 패널티가 없습니다.", ephemeral=True)
            return

        embed = build_labor_embed(interaction.user, updated_penalty, self.guild_id, mine_result)

        if resolved:
            embed.title = "✅ 노동 완료"
            embed.color = 0x2ECC71
            embed.add_field(
                name="결과",
                value=f"필요 노동 횟수를 모두 채워 신용불량자 상태가 해제되고 `{INITIAL_CREDIT_GRADE}등급`으로 초기화되었습니다.",
                inline=False,
            )
            await sync_blacklist_role(interaction.user, False)
            for item in self.children:
                item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="얕은 광맥", style=discord.ButtonStyle.success)
    async def shallow(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.run_mining(interaction, "shallow")

    @discord.ui.button(label="일반 광맥", style=discord.ButtonStyle.primary)
    async def normal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.run_mining(interaction, "normal")

    @discord.ui.button(label="심층 광맥", style=discord.ButtonStyle.danger)
    async def deep(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.run_mining(interaction, "deep")


class PromissoryNoteModal(discord.ui.Modal):
    principal_amount = discord.ui.TextInput(
        label="원금",
        placeholder="예: 50000",
        required=True,
        max_length=20,
    )
    interest_amount = discord.ui.TextInput(
        label="이자",
        placeholder="예: 5000",
        required=True,
        max_length=20,
    )
    due_text = discord.ui.TextInput(
        label="상환 약속일",
        placeholder="예: 2026-05-31 또는 다음 주 금요일",
        required=True,
        max_length=100,
    )
    note = discord.ui.TextInput(
        label="비고",
        placeholder="추가로 남길 메모가 있으면 적어주세요.",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
    )

    def __init__(self, borrower: discord.Member):
        super().__init__(title="차용증 작성")
        self.borrower = borrower

    async def on_submit(self, interaction: discord.Interaction):
        try:
            principal_amount = int(str(self.principal_amount).strip().replace(",", ""))
            interest_amount = int(str(self.interest_amount).strip().replace(",", ""))
        except ValueError:
            await interaction.response.send_message("원금과 이자는 숫자로 입력해주세요.", ephemeral=True)
            return

        if principal_amount <= 0:
            await interaction.response.send_message("원금은 1원 이상이어야 합니다.", ephemeral=True)
            return

        if interest_amount < 0:
            await interaction.response.send_message("이자는 0원 이상이어야 합니다.", ephemeral=True)
            return

        clean_due_text = str(self.due_text).strip()
        clean_note = str(self.note).strip()

        embed = build_promissory_note_embed(
            interaction.user,
            self.borrower,
            principal_amount,
            interest_amount,
            clean_due_text,
            clean_note,
            title="🧾 차용증 요청",
            color=0xF1C40F,
            status_text="상대방 확인 대기 중",
        )
        embed.set_footer(text="채무자는 아래 버튼으로 수락 또는 거절을 선택할 수 있습니다.")

        await interaction.response.send_message(
            content=self.borrower.mention,
            embed=embed,
            view=PromissoryNoteRequestView(
                interaction.guild.id,
                interaction.user.id,
                self.borrower.id,
                principal_amount,
                interest_amount,
                clean_due_text,
                clean_note,
            ),
        )


class PromissoryNoteRequestView(discord.ui.View):
    def __init__(
        self,
        guild_id: int,
        lender_user_id: int,
        borrower_user_id: int,
        principal_amount: int,
        interest_amount: int,
        due_text: str,
        note: str,
    ):
        super().__init__(timeout=86400)
        self.guild_id = guild_id
        self.lender_user_id = lender_user_id
        self.borrower_user_id = borrower_user_id
        self.principal_amount = principal_amount
        self.interest_amount = interest_amount
        self.due_text = due_text
        self.note = note

    async def _reject_if_not_borrower(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.borrower_user_id:
            await interaction.response.send_message("이 버튼은 차용증을 받은 본인만 누를 수 있습니다.", ephemeral=True)
            return True
        return False

    @discord.ui.button(label="수락", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._reject_if_not_borrower(interaction):
            return

        lender = interaction.guild.get_member(self.lender_user_id) or interaction.client.get_user(self.lender_user_id)
        borrower = interaction.guild.get_member(self.borrower_user_id) or interaction.client.get_user(self.borrower_user_id)
        note_id = create_promissory_note(
            self.guild_id,
            self.lender_user_id,
            self.borrower_user_id,
            self.principal_amount,
            self.interest_amount,
            self.due_text,
            self.note,
            interaction.channel.id,
            interaction.message.id,
        )

        embed = build_promissory_note_embed(
            lender,
            borrower,
            self.principal_amount,
            self.interest_amount,
            self.due_text,
            self.note,
            title="🧾 차용증 등록 완료",
            color=0x2ECC71,
            status_text="수락됨",
            note_id=note_id,
        )
        embed.set_footer(text="상환이 끝나면 /차용증삭제 로 정리할 수 있습니다.")

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if await self._reject_if_not_borrower(interaction):
            return

        lender = interaction.guild.get_member(self.lender_user_id) or interaction.client.get_user(self.lender_user_id)
        borrower = interaction.guild.get_member(self.borrower_user_id) or interaction.client.get_user(self.borrower_user_id)

        embed = build_promissory_note_embed(
            lender,
            borrower,
            self.principal_amount,
            self.interest_amount,
            self.due_text,
            self.note,
            title="❌ 차용증 요청 거절됨",
            color=0xE74C3C,
            status_text="거절됨",
        )

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)


class StickyMessageModal(discord.ui.Modal, title="고정메시지 설정"):
    content = discord.ui.TextInput(
        label="고정 메시지 내용",
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
            f"{interaction.channel.mention} 채널에 고정메시지를 설정했습니다.",
            ephemeral=True,
        )


class LoanConfirmView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, amount: int):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.user_id = user_id
        self.amount = amount
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("이 버튼은 대출을 신청한 본인만 누를 수 있습니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="확인", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.resolved:
            await interaction.response.send_message("이미 처리된 대출 요청입니다.", ephemeral=True)
            return

        profile = get_credit_profile(self.user_id)
        if profile["is_blacklisted"]:
            await interaction.response.send_message("현재 신용불량자 상태라 대출이 불가능합니다.", ephemeral=True)
            return

        if len(get_active_loans(self.user_id)) >= 2:
            await interaction.response.send_message("동시에 진행할 수 있는 대출은 최대 2건입니다.", ephemeral=True)
            return

        remaining_limit = get_remaining_loan_limit(self.user_id)
        if self.amount > remaining_limit:
            await interaction.response.send_message(
                f"남은 대출 한도 `{format_money(remaining_limit)}`를 초과했습니다.",
                ephemeral=True,
            )
            return

        required_balance = (self.amount + 3) // 4
        current_balance = get_balance(self.user_id)
        if current_balance < required_balance:
            await interaction.response.send_message(
                (
                    "대출 조건을 다시 확인해주세요.\n"
                    f"필요 잔액: `{format_money(required_balance)}` / 현재 잔액: `{format_money(current_balance)}`"
                ),
                ephemeral=True,
            )
            return

        self.resolved = True
        grade = profile["grade"]
        interest_rate = get_loan_interest_by_grade(grade)
        borrowed_at = get_kst_now()
        due_at = borrowed_at + timedelta(days=LOAN_REPAYMENT_DAYS)
        total_repayment = calculate_total_repayment(self.amount, interest_rate)

        add_balance(self.user_id, self.amount)
        create_loan(
            self.guild_id,
            self.user_id,
            self.amount,
            interest_rate,
            total_repayment,
            borrowed_at,
            due_at,
        )

        for item in self.children:
            item.disabled = True

        embed = discord.Embed(title="💳 대출 실행 완료", color=0x3498DB)
        embed.add_field(name="현재 신용등급", value=f"{grade}등급", inline=False)
        embed.add_field(name="대출 금액", value=format_money(self.amount), inline=False)
        embed.add_field(name="이자율", value=f"{interest_rate}%", inline=False)
        embed.add_field(name="총 상환 금액", value=format_money(total_repayment), inline=False)
        embed.add_field(name="상환 기한", value=due_at.strftime("%Y-%m-%d %H:%M:%S KST"), inline=False)
        embed.add_field(name="현재 진행 중인 대출 수", value=f"{len(get_active_loans(self.user_id))}건", inline=False)
        embed.add_field(name="남은 대출 한도", value=format_money(get_remaining_loan_limit(self.user_id)), inline=False)
        current_profile = get_credit_profile(self.user_id)
        embed.add_field(
            name="등급 상승 누적 실적",
            value=(
                f"{format_money(current_profile['loan_progress_amount'])} / "
                f"{format_money(get_loan_limit_by_grade(current_profile['grade']))}"
            ),
            inline=False,
        )
        embed.add_field(name="현재 잔액", value=format_money(get_balance(self.user_id)), inline=False)
        embed.set_footer(text=f"대출 상환 후 한도는 {LOAN_LIMIT_RECOVERY_DELAY_MINUTES}분 뒤 회복됩니다.")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="취소", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.resolved:
            await interaction.response.send_message("이미 처리된 대출 요청입니다.", ephemeral=True)
            return

        self.resolved = True
        for item in self.children:
            item.disabled = True

        embed = discord.Embed(
            title="💳 대출 취소",
            description="대출 신청이 취소되었습니다.",
            color=0x95A5A6,
        )
        await interaction.response.edit_message(embed=embed, view=self)


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
        title=f"🎮 {game_name} 모집중!",
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


@bot.tree.command(name="세팅규칙로그", description="현재 채널을 규칙/신입 알림 로그 채널로 설정합니다.")
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

@bot.tree.command(name="세팅가이드안내", description="현재 채널을 가이드 안내 채널로 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_welcome_guide_channel(interaction: discord.Interaction):
    set_guild_setting(interaction.guild.id, "welcome_guide_channel_id", str(interaction.channel.id))
    await interaction.response.send_message(f"가이드 안내 채널을 {interaction.channel.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅환영메시지채널", description="현재 채널을 환영 메시지 출력 채널로 설정합니다.")
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


@bot.tree.command(name="신용불량자역할", description="신용불량자에게 자동으로 부여할 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_blacklist_role(interaction: discord.Interaction, role: discord.Role):
    set_guild_setting(interaction.guild.id, "blacklist_role_id", str(role.id))
    await interaction.response.send_message(f"신용불량자 역할을 {role.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅클랜등업역할", description="클랜 등업 역할을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def set_upgrade_clan_role(interaction: discord.Interaction, role: discord.Role):
    set_guild_setting(interaction.guild.id, "upgrade_clan_role_id", str(role.id))
    await interaction.response.send_message(f"클랜 등업 역할을 {role.mention} 으로 설정했습니다.", ephemeral=True)


@bot.tree.command(name="세팅게스트등업역할", description="게스트 등업 역할을 설정합니다.")
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


@bot.tree.command(name="세팅환영dm", description="유저에게 보낼 환영 DM 문구를 설정합니다.")
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
async def set_upgrade_panel_template(interaction: discord.Interaction):
    await interaction.response.send_modal(UpgradePanelTemplateModal(interaction.guild.id))


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


@bot.tree.command(name="적금세팅", description="적금 기간과 이자율을 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def savings_setting(interaction: discord.Interaction, days: int, interest_rate: int):
    if days < 1:
        await interaction.response.send_message("적금 기간은 1일 이상이어야 합니다.", ephemeral=True)
        return
    if interest_rate < 0:
        await interaction.response.send_message("이자율은 0 이상이어야 합니다.", ephemeral=True)
        return

    set_guild_setting(interaction.guild.id, "savings_days", str(days))
    set_guild_setting(interaction.guild.id, "savings_interest_rate", str(interest_rate))
    await interaction.response.send_message(
        f"적금 설정을 저장했습니다.\n기간: `{days}일`\n이자율: `{interest_rate}%`",
        ephemeral=True,
    )


@bot.tree.command(name="설정확인", description="현재 채널 설정을 확인합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def show_settings(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    keys = [
        ("등업 로그", "upgrade_log_channel_id"),
        ("퇴장 로그", "leave_log_channel_id"),
        ("규칙 로그", "rule_log_channel_id"),
        ("구인 채널", "recruit_channel_id"),
        ("가이드 안내", "welcome_guide_channel_id"),
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
        ("신용불량자 역할", "blacklist_role_id"),
        ("클랜 등업 역할", "upgrade_clan_role_id"),
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


@bot.tree.command(name="문구설정확인", description="현재 등록된 커스텀 문구를 확인합니다.")
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


@bot.tree.command(name="고정메시지", description="현재 채널의 최하단 고정 메시지를 설정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def sticky_message(interaction: discord.Interaction):
    await interaction.response.send_modal(StickyMessageModal())


@bot.tree.command(name="고정메시지해제", description="현재 채널의 고정 메시지를 해제합니다.")
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


@bot.tree.command(name="고정메시지확인", description="현재 채널의 고정 메시지 내용을 확인합니다.")
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


@bot.tree.command(name="규칙버튼", description="규칙 확인 버튼 메시지를 생성합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def rule_button(interaction: discord.Interaction):
    text = get_template_with_default(interaction.guild.id, "rule_button_text", DEFAULT_RULE_BUTTON_TEXT)
    embed = discord.Embed(description=text, color=0x2ECC71)
    await interaction.channel.send(embed=embed, view=RuleConfirmView())
    await interaction.response.send_message("규칙 버튼 생성 완료", ephemeral=True)


@bot.tree.command(name="등업패널", description="등업 요청 패널을 생성합니다.")
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


# ----------------------------
# 재화 / 적금 명령어
# ----------------------------

@bot.tree.command(name="기초생활수급비", description="하루에 한 번 기초생활수급비 10,000원을 받습니다.")
async def daily_money(interaction: discord.Interaction):
    today = get_kst_now().strftime("%Y-%m-%d")
    cursor.execute("SELECT last_claim_date FROM daily_claims WHERE user_id=?", (str(interaction.user.id),))
    row = cursor.fetchone()
    if row and row[0] == today:
        await interaction.response.send_message("오늘은 이미 지원금을 받았습니다. 내일 다시 시도해주세요.", ephemeral=True)
        return

    ensure_wallet(interaction.user.id)
    add_balance(interaction.user.id, DAILY_REWARD)
    cursor.execute(
        "INSERT OR REPLACE INTO daily_claims(user_id, last_claim_date) VALUES (?, ?)",
        (str(interaction.user.id), today),
    )
    conn.commit()

    await interaction.response.send_message(
        f"오늘의 기초생활수급비 `{format_money(DAILY_REWARD)}`을 받았습니다.\n현재 잔액: `{format_money(get_balance(interaction.user.id))}`"
    )


@bot.tree.command(name="잔액", description="현재 보유 금액을 확인합니다.")
async def balance(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"{interaction.user.mention}님의 현재 잔액은 `{format_money(get_balance(interaction.user.id))}`입니다."
    )


@bot.tree.command(name="적금", description="현재 서버 설정 기준으로 적금에 가입합니다.")
async def savings_join(interaction: discord.Interaction, amount: int):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("적금 금액은 1원 이상이어야 합니다.", ephemeral=True)
        return
    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
        return
    if get_active_saving(interaction.guild.id, interaction.user.id) is not None:
        await interaction.response.send_message("이미 진행 중인 적금이 있습니다. `/내적금`으로 확인해주세요.", ephemeral=True)
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
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    saving = get_active_saving(interaction.guild.id, interaction.user.id)
    if saving is None:
        await interaction.response.send_message("현재 가입 중인 적금이 없습니다.", ephemeral=True)
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
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    saving = get_active_saving(interaction.guild.id, interaction.user.id)
    if saving is None:
        await interaction.response.send_message("현재 수령할 적금이 없습니다.", ephemeral=True)
        return

    due_at = dt_from_db(saving["due_at"])
    if get_kst_now() < due_at:
        await interaction.response.send_message("아직 적금 만기 전입니다.", ephemeral=True)
        return

    add_balance(interaction.user.id, saving["total_amount"])
    claim_saving(saving["id"])

    embed = discord.Embed(title="🏦 적금 수령 완료", color=0x2ECC71)
    embed.add_field(name="수령액", value=format_money(saving["total_amount"]), inline=False)
    embed.add_field(name="현재 잔액", value=format_money(get_balance(interaction.user.id)), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="적금중도해지", description="진행 중인 적금을 중도해지하고 원금만 돌려받습니다.")
async def savings_cancel(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    saving = get_active_saving(interaction.guild.id, interaction.user.id)
    if saving is None:
        await interaction.response.send_message("현재 해지할 적금이 없습니다.", ephemeral=True)
        return

    due_at = dt_from_db(saving["due_at"])
    if get_kst_now() >= due_at:
        await interaction.response.send_message("이미 만기된 적금입니다. `/적금수령`을 사용해주세요.", ephemeral=True)
        return

    add_balance(interaction.user.id, saving["principal"])
    cancel_saving(saving["id"])

    embed = discord.Embed(title="🏦 적금 중도해지 완료", color=0xE67E22)
    embed.add_field(name="반환액", value=format_money(saving["principal"]), inline=False)
    embed.add_field(name="안내", value="중도해지 시 이자는 지급되지 않고 원금만 반환됩니다.", inline=False)
    embed.add_field(name="현재 잔액", value=format_money(get_balance(interaction.user.id)), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="랭킹", description="서버 재산 상위 10명을 확인합니다.")
async def ranking(interaction: discord.Interaction):
    cursor.execute("SELECT user_id, balance FROM balances ORDER BY balance DESC, user_id ASC LIMIT 10")
    rows = cursor.fetchall()
    if not rows:
        await interaction.response.send_message("아직 재산 데이터가 없습니다.")
        return

    lines = []
    for index, (user_id, amount) in enumerate(rows, start=1):
        member = interaction.guild.get_member(int(user_id))
        name = member.display_name if member else f"알 수 없는 유저 ({user_id})"
        medal = "👑 " if index == 1 else ""
        lines.append(f"{index}. {medal}{name} - {format_money(amount)}")

    embed = discord.Embed(title="🏆 재산 순위", description="\n".join(lines), color=0xF1C40F)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="송금", description="다른 유저에게 재화를 송금합니다.")
@app_commands.rename(member="대상", amount="금액", note="비고")
@app_commands.describe(note="송금 사유나 메모, 비워두면 생략")
async def transfer(interaction: discord.Interaction, member: discord.Member, amount: int, note: str | None = None):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return
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

    note_text = (note or "").strip() or None
    add_balance(interaction.user.id, -amount)
    add_balance(member.id, amount)
    add_transfer_log(interaction.guild.id, interaction.user.id, member.id, amount, note_text)

    lines = [
        f"{member.mention}에게 `{format_money(amount)}`을 송금했습니다.",
        f"현재 잔액: `{format_money(get_balance(interaction.user.id))}`",
    ]
    if note_text:
        lines.append(f"비고: {note_text}")

    await interaction.response.send_message("\n".join(lines))


@bot.tree.command(name="송금내역", description="특정 인원의 송금 받은 내역을 확인합니다.")
@app_commands.rename(member="인원")
@app_commands.describe(member="조회할 인원, 본인 외 조회는 관리자만 가능")
async def transfer_history(interaction: discord.Interaction, member: discord.Member):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    if member.id != interaction.user.id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("다른 사람의 송금내역은 관리자만 확인할 수 있습니다.", ephemeral=True)
        return

    rows = get_transfer_logs(interaction.guild.id, member.id, 20)
    if not rows:
        await interaction.response.send_message("송금 받은 내역이 없습니다.", ephemeral=True)
        return

    lines = []
    for sender_user_id, amount, note_text, created_at in rows:
        sender = interaction.guild.get_member(int(sender_user_id))
        sender_name = sender.display_name if sender else f"알 수 없는 유저 ({sender_user_id})"
        try:
            created_text = dt_from_db(created_at).strftime("%Y-%m-%d %H:%M")
        except Exception:
            created_text = created_at

        line = f"**[{created_text}]**\n보낸 사람: {sender_name}\n금액: {format_money(amount)}"
        if note_text:
            line += f"\n비고: {note_text}"
        lines.append(line)

    embed = discord.Embed(
        title=f"💸 {member.display_name}님의 송금 받은 내역",
        description="\n\n".join(lines),
        color=0x2ECC71,
    )
    embed.set_footer(text="최근 20개의 받은 송금 내역을 표시합니다.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="돈주기", description="서버 관리자 이상이 여러 유저에게 같은 금액을 지급합니다.")
@app_commands.rename(targets="대상들", amount="금액", note="비고")
@app_commands.describe(
    targets="멘션 또는 ID를 공백이나 쉼표로 구분해 입력",
    amount="각 유저에게 지급할 금액",
    note="지급 사유나 메모, 비워두면 생략",
)
async def grant_money(interaction: discord.Interaction, targets: str, amount: int, note: str | None = None):
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
    note_text = (note or "").strip() or None

    for user_id in dict.fromkeys(raw_ids):
        member = interaction.guild.get_member(user_id)
        if member is None or member.bot:
            skipped_members.append(str(user_id))
            continue

        add_balance(member.id, amount)
        add_money_grant_log(interaction.guild.id, member.id, interaction.user.id, amount, note_text)
        success_members.append(member.mention)

    if not success_members:
        await interaction.response.send_message("지급 가능한 유저가 없습니다.", ephemeral=True)
        return

    lines = [
        f"총 {len(success_members)}명에게 각각 `{format_money(amount)}`을 지급했습니다.",
        f"대상: {', '.join(success_members)}",
    ]

    if note_text:
        lines.append(f"비고: {note_text}")

    if skipped_members:
        lines.append(f"제외됨: {', '.join(skipped_members)}")

    await interaction.response.send_message("\n".join(lines))




@bot.tree.command(name="돈삭제", description="서버 주인이 특정 유저의 재화를 차감합니다.")
async def remove_money(interaction: discord.Interaction, member: discord.Member, amount: int):
    if interaction.guild is None or interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message("이 명령어는 서버 주인만 사용할 수 있습니다.", ephemeral=True)
        return

    if member.bot:
        await interaction.response.send_message("봇의 재화는 차감할 수 없습니다.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("차감 금액은 1원 이상이어야 합니다.", ephemeral=True)
        return

    current_balance = get_balance(member.id)
    deducted_amount = min(current_balance, amount)
    add_balance(member.id, -deducted_amount)

    await interaction.response.send_message(
        f"{member.mention}에게서 `{format_money(deducted_amount)}`을 차감했습니다.\n"
        f"{member.mention}의 현재 잔액: `{format_money(get_balance(member.id))}`"
    )


@bot.tree.command(name="벌금부여", description="신용등급에는 영향 없이 노동/신용 화면에 반영되는 관리자 부채를 부여합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.rename(member="인원", amount="금액", reason="사유")
async def assign_manual_credit_debt(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: int,
    reason: str | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    if member.bot:
        await interaction.response.send_message("봇에게는 벌금을 부여할 수 없습니다.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("벌금 금액은 1원 이상이어야 합니다.", ephemeral=True)
        return

    note = (reason or "").strip()
    debt_id = create_manual_credit_debt(interaction.guild.id, member.id, amount, note)
    total_manual_debt = get_total_active_manual_credit_debt(interaction.guild.id, member.id)

    profile = get_credit_profile(member.id)
    if profile["is_blacklisted"]:
        refresh_active_labor_penalty_debt(interaction.guild.id, member.id)

    lines = [
        f"{member.mention}님에게 관리자 부채 `{format_money(amount)}`을 부여했습니다.",
        f"부채 번호: `#{debt_id}`",
        f"현재 관리자 부채 합계: `{format_money(total_manual_debt)}`",
        "이 금액은 대출 한도와 신용등급에는 영향을 주지 않지만, /내신용, /신용조회, 노동 횟수에는 반영됩니다.",
    ]
    if note:
        lines.append(f"사유: {note}")

    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@bot.tree.command(name="벌금삭제", description="상환이 끝난 관리자 부채를 정리합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.rename(debt_id="부채번호")
async def resolve_manual_credit_debt_command(interaction: discord.Interaction, debt_id: int):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    debt = get_manual_credit_debt(debt_id)
    if debt is None or debt["guild_id"] != str(interaction.guild.id):
        await interaction.response.send_message("해당 관리자 부채를 찾을 수 없습니다.", ephemeral=True)
        return

    if debt["status"] != "active":
        await interaction.response.send_message("이미 정리된 관리자 부채입니다.", ephemeral=True)
        return

    resolve_manual_credit_debt(debt_id)

    profile = get_credit_profile(debt["user_id"])
    member = interaction.guild.get_member(debt["user_id"])
    remaining_manual_debt = get_total_active_manual_credit_debt(interaction.guild.id, debt["user_id"])

    if profile["is_blacklisted"]:
        if get_total_credit_obligation(interaction.guild.id, debt["user_id"]) <= 0:
            set_credit_blacklisted(debt["user_id"], False)
            set_credit_grade(debt["user_id"], INITIAL_CREDIT_GRADE)
            delete_labor_penalty(interaction.guild.id, debt["user_id"])
            if member is not None:
                await sync_blacklist_role(member, False)
        else:
            refresh_active_labor_penalty_debt(interaction.guild.id, debt["user_id"])

    member_text = member.mention if member is not None else f"`{debt['user_id']}`"
    lines = [
        f"{member_text}님의 관리자 부채 `#{debt_id}`를 정리했습니다.",
        f"정리된 금액: `{format_money(debt['amount'])}`",
        f"남은 관리자 부채 합계: `{format_money(remaining_manual_debt)}`",
    ]
    if debt["reason"]:
        lines.append(f"사유: {debt['reason']}")

    await interaction.response.send_message("\n".join(lines), ephemeral=True)


# ----------------------------
# 게임 명령어
# ----------------------------

@bot.tree.command(name="슬롯", description="입력한 금액으로 슬롯머신을 돌립니다.")
async def slot(interaction: discord.Interaction, amount: int):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if amount < MIN_BET:
        await interaction.response.send_message(f"최소 베팅 금액은 `{format_money(MIN_BET)}`입니다.", ephemeral=True)
        return
    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)
    symbols = ["체리", "레몬", "포도", "사과", "클로버", "7"]

    force_info = get_hidden_gambling_force(interaction.user.id)
    if force_info and force_info["game_name"] == "slot":
        consume_hidden_gambling_force(interaction.user.id)
        result = ["7", "7", "7"]
    else:
        first = random.choice(symbols)
        second = first if random.random() < 0.05 else random.choice(symbols)
        third = first if random.random() < 0.05 else random.choice(symbols)
        result = [first, second, third]
    result_display = " | ".join(SLOT_SYMBOL_EMOJIS.get(symbol, symbol) for symbol in result)

    multiplier = 0

    if len(set(result)) == 1:
        if result[0] == "7":
            multiplier = 14
        elif result[0] == "클로버":
            multiplier = 9
        else:
            multiplier = 7
    elif len(set(result)) == 2:
        counts = {symbol: result.count(symbol) for symbol in set(result)}
        pair_symbol = max(counts, key=counts.get)

        if counts[pair_symbol] == 2:
            if pair_symbol == "7":
                multiplier = 1.8
            elif pair_symbol == "클로버":
                multiplier = 1.5
            else:
                multiplier = 1.25


    

    winnings = int(amount * multiplier)
    if winnings > 0:
        add_balance(interaction.user.id, winnings)

    balance_now = get_balance(interaction.user.id)

    if multiplier == 0:
        desc = f"{result_display}\n\n아쉽네요... `{format_money(amount)}`을 잃었습니다.\n현재 잔액: `{format_money(balance_now)}`"
        color = 0xE74C3C
    elif len(set(result)) == 1:
        desc = f"{result_display}\n\n대박! `{multiplier}배` 당첨으로 `{format_money(winnings)}`을 획득했습니다.\n현재 잔액: `{format_money(balance_now)}`"
        color = 0x2ECC71
    else:
        desc = f"{result_display}\n\n2개 일치! `{multiplier}배` 보상으로 `{format_money(winnings)}`을 획득했습니다.\n현재 잔액: `{format_money(balance_now)}`"
        color = 0x3498DB

    add_game_history(
        interaction.guild.id,
        "슬롯",
        f"{interaction.user.display_name} - {' | '.join(result)} - {('꽝' if multiplier == 0 else f'{multiplier}배')}"
    )

    embed = discord.Embed(title="🎰 슬롯 결과", description=desc, color=color)
    await interaction.response.send_message(embed=embed)



@bot.tree.command(name="동전", description="입력한 금액으로 동전 앞뒤 맞히기를 합니다.")
async def coin(interaction: discord.Interaction, amount: int):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if amount < MIN_BET:
        await interaction.response.send_message(f"최소 베팅 금액은 `{format_money(MIN_BET)}`입니다.", ephemeral=True)
        return
    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)
    embed = discord.Embed(
        title="🪙 동전 던지기",
        description=(
            f"베팅 금액: `{format_money(amount)}`\n"
            "아래 버튼에서 `앞` 또는 `뒤`를 선택해주세요.\n"
            "승리 시 2배를 지급합니다.\n"
            f"{COIN_FLIP_TIMEOUT}초 안에 선택하지 않으면 자동 취소되고 돈이 반환됩니다."
        ),
        color=0xF1C40F,
    )
    await interaction.response.send_message(embed=embed, view=CoinFlipView(interaction.user.id, amount))


@bot.tree.command(name="블랙잭", description="입력한 금액으로 딜러와 블랙잭을 합니다.")
async def blackjack(interaction: discord.Interaction, amount: int):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return
    if amount < MIN_BET:
        await interaction.response.send_message(f"최소 베팅 금액은 `{format_money(MIN_BET)}`입니다.", ephemeral=True)
        return
    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)
    view = BlackjackView(interaction.guild.id, interaction.user.id, amount)
    await interaction.response.send_message(embed=view.build_embed(), view=view)


@bot.tree.command(name="경마", description="입력한 금액으로 원하는 말에 베팅합니다.")
async def horse_race(interaction: discord.Interaction, amount: int):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return
    if amount < MIN_BET:
        await interaction.response.send_message(f"최소 베팅 금액은 `{format_money(MIN_BET)}`입니다.", ephemeral=True)
        return
    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)
    lines = [
        f"**{horse['name']}** - 승률 {horse['weight']}% / 배당 {horse['payout']}배"
        for horse in HORSE_RACE_TABLE
    ]
    embed = discord.Embed(
        title="🏇 오늘의 경마",
        description=(
            f"베팅 금액: `{format_money(amount)}`\n\n"
            + "\n".join(lines)
            + "\n\n응원할 말을 선택해주세요."
        ),
        color=0xE67E22,
    )
    await interaction.response.send_message(
        embed=embed,
        view=HorseRaceView(interaction.guild.id, interaction.user.id, amount),
    )


@bot.tree.command(name="숫자야구", description="고정 참가비로 숫자야구에 도전합니다.")
async def number_baseball(interaction: discord.Interaction):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return
    amount = NUMBER_BASEBALL_COST
    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message(
            f"숫자야구 참가비 `{format_money(amount)}`이 부족합니다.",
            ephemeral=True,
        )
        return

    add_balance(interaction.user.id, -amount)
    view = NumberBaseballView(interaction.guild.id, interaction.user.id, amount)
    await interaction.response.send_message(embed=view.build_embed(), view=view)


@bot.tree.command(name="야추", description="입력한 금액으로 봇 또는 유저와 야추 대결을 합니다.")
@app_commands.rename(amount="금액", member="상대")
@app_commands.describe(amount="베팅 금액", member="비워두면 봇과 대결합니다.")
async def yahtzee(interaction: discord.Interaction, amount: int, member: discord.Member | None = None):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return
    if amount < MIN_BET:
        await interaction.response.send_message(f"최소 베팅 금액은 `{format_money(MIN_BET)}`입니다.", ephemeral=True)
        return
    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
        return

    if member is None:
        add_balance(interaction.user.id, -amount)
        match_view = YahtzeeMatchView(interaction.guild.id, interaction.user.id, None, amount)
        embed = match_view.build_embed(interaction.guild, interaction.client.user)
        embed.add_field(name="상대", value="봇", inline=False)
        await interaction.response.send_message(embed=embed, view=match_view)
        return

    if member.bot:
        await interaction.response.send_message("봇과 대결하려면 상대를 비워두고 `/야추`를 사용해주세요.", ephemeral=True)
        return

    if member.id == interaction.user.id:
        await interaction.response.send_message("본인과는 대결할 수 없습니다.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎲 야추 대결 요청",
        description=f"{member.mention}님, {interaction.user.mention}님이 야추 대결을 신청했습니다.",
        color=0xF1C40F,
    )
    embed.add_field(name="도전자", value=interaction.user.mention, inline=True)
    embed.add_field(name="상대", value=member.mention, inline=True)
    embed.add_field(name="베팅금", value=f"`{format_money(amount)}`", inline=False)
    embed.add_field(
        name="룰",
        value=(
            "수락 시 두 사람 모두 같은 금액을 먼저 겁니다.\n"
            "각자 주사위 5개 중 3개를 먼저 공개합니다.\n"
            "배팅 또는 다이를 선택하고, 둘 다 배팅해야 최종 주사위를 공개합니다."
        ),
        inline=False,
    )
    embed.set_footer(text="상대방만 수락 또는 거절할 수 있습니다.")
    await interaction.response.send_message(
        content=member.mention,
        embed=embed,
        view=YahtzeeChallengeView(interaction.user.id, member.id, amount),
    )


@bot.tree.command(name="지뢰찾기", description="입력한 금액으로 지뢰를 피해 보상을 쌓습니다.")
async def minesweeper(interaction: discord.Interaction, amount: int):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return
    if amount < MIN_BET:
        await interaction.response.send_message(f"최소 베팅 금액은 `{format_money(MIN_BET)}`입니다.", ephemeral=True)
        return
    if not can_afford(interaction.user.id, amount):
        await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
        return

    add_balance(interaction.user.id, -amount)
    view = MinesweeperView(interaction.guild.id, interaction.user.id, amount)
    await interaction.response.send_message(embed=view.build_embed(), view=view)


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


@bot.tree.command(name="팀", description="랜덤 팀을 생성합니다.")
async def team(interaction: discord.Interaction):
    embed = discord.Embed(title="👥 팀 생성", description="팀 인원을 선택해주세요.", color=0x3498DB)
    await interaction.response.send_message(embed=embed, view=TeamSelectView())


@bot.tree.command(name="팀섞기로그", description="특정 인원의 팀섞기 참여 기록을 확인합니다.")
@app_commands.rename(member="인원")
@app_commands.describe(member="조회할 인원")
async def team_mix_log(interaction: discord.Interaction, member: discord.Member):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    rows = get_team_mix_logs(interaction.guild.id, member.id, 20)
    if not rows:
        await interaction.response.send_message("해당 인원의 팀섞기 기록이 없습니다.", ephemeral=True)
        return

    lines = []
    latest_text = None
    for idx, (channel_id, team_size, team_label, members_text, created_at) in enumerate(rows, start=1):
        try:
            created_text = dt_from_db(created_at).strftime("%Y-%m-%d %H:%M")
        except Exception:
            created_text = created_at

        channel_text = f"<#{channel_id}>"
        member_lines = "\n".join(f"- {name.strip()}" for name in members_text.split(",") if name.strip())
        if latest_text is None:
            latest_text = (
                f"시간: `{created_text}`\n"
                f"채널: {channel_text}\n"
                f"팀 구성: `{team_size}인 팀` / `{team_label}`"
            )

        lines.append(
            f"**{idx}. {created_text}**\n"
            f"채널: {channel_text}\n"
            f"팀 구성: `{team_size}인 팀` / `{team_label}`\n"
            f"참여 멤버\n{member_lines}"
        )

    embed = discord.Embed(
        title=f"📝 {member.display_name}님의 팀섞기 기록",
        description="최근 팀섞기 패널 기준 마지막 결과만 정리해서 표시합니다.",
        color=0x5865F2,
    )
    embed.add_field(name="가장 최근 기록", value=latest_text or "최근 기록 없음", inline=False)
    embed.add_field(name="기록 목록", value=join_discord_field_lines(lines), inline=False)
    embed.set_footer(text="최근 20개의 팀섞기 패널 기준 마지막 결과를 표시합니다.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


def build_voice_log_embed(guild: discord.Guild, member: discord.Member, since: datetime, until: datetime):
    intervals = get_voice_channel_intervals_between(guild.id, member.id, since, until)
    summary_map = {}
    for item in intervals:
        seconds = max(0, int((item["end"] - item["start"]).total_seconds()))
        if seconds <= 0:
            continue
        channel_entry = summary_map.setdefault(
            item["channel_id"],
            {"total_seconds": 0, "session_count": 0, "last_ended_at": None},
        )
        channel_entry["total_seconds"] += seconds
        channel_entry["session_count"] += 1
        if item.get("active"):
            channel_entry["last_ended_at"] = "현재 접속 중"
        else:
            end_text = dt_to_db(item["end"])
            if channel_entry["last_ended_at"] is None or end_text > str(channel_entry["last_ended_at"]):
                channel_entry["last_ended_at"] = end_text

    if not summary_map:
        return None, "해당 기간 기준 음성채널 체류 기록이 없습니다."

    sorted_rows = sorted(
        summary_map.items(),
        key=lambda item: (-item[1]["total_seconds"], item[0]),
    )
    total_seconds = sum(item["total_seconds"] for _, item in sorted_rows)
    if total_seconds <= 0:
        return None, "해당 기간 기준 집계 가능한 음성채널 기록이 없습니다."

    lines = []
    top_channel_id, top_channel_item = sorted_rows[0]
    top_channel = guild.get_channel(int(top_channel_id))
    top_channel_name = top_channel.name if top_channel else f"알 수 없는 채널 ({top_channel_id})"
    team_mix_count = get_team_mix_count_between(guild.id, member.id, since, until)
    companion_rows = []

    for candidate_id in get_voice_log_user_ids_between(guild.id, since, until):
        if candidate_id == member.id:
            continue

        candidate = guild.get_member(candidate_id)
        if candidate is None or candidate.bot or is_spectator_member(candidate, guild.id):
            continue

        candidate_intervals = get_voice_channel_intervals_between(guild.id, candidate_id, since, until)
        overlap_seconds = sum(calculate_voice_overlap_seconds(intervals, candidate_intervals).values())
        if overlap_seconds <= 0:
            continue

        companion_rows.append((candidate, overlap_seconds))

    companion_rows.sort(key=lambda item: (-item[1], item[0].display_name))
    companion_lines = []
    for idx, (candidate, overlap_seconds) in enumerate(companion_rows[:3], start=1):
        percentage = (overlap_seconds / total_seconds) * 100 if total_seconds > 0 else 0
        companion_lines.append(
            f"{idx}. {candidate.display_name}\n"
            f"같이 있던 시간: `{format_duration_korean(overlap_seconds)}`\n"
            f"전체 체류 대비: `{percentage:.1f}%`"
        )

    for idx, (channel_id, item) in enumerate(sorted_rows[:10], start=1):
        percentage = (item["total_seconds"] / total_seconds) * 100
        channel = guild.get_channel(int(channel_id))
        channel_name = channel.name if channel else f"알 수 없는 채널 ({channel_id})"
        lines.append(
            f"{idx}. {channel_name}\n"
            f"체류 시간: `{format_duration_korean(item['total_seconds'])}`\n"
            f"전체 비중: `{percentage:.1f}%`"
        )

    embed = discord.Embed(
        title=f"🎧 {member.display_name}님의 음성채널 로그",
        description=f"지정한 기간 동안 가장 오래 머문 채널은 **{top_channel_name}**입니다.",
        color=0x3498DB,
    )
    embed.add_field(
        name="집계 기준",
        value=f"`{since.strftime('%Y-%m-%d')}` ~ `{until.strftime('%Y-%m-%d')}` / 관전자 시간 제외",
        inline=False,
    )
    embed.add_field(
        name="한눈에 보기",
        value=(
            f"총 체류 시간: `{format_duration_korean(total_seconds)}`\n"
            f"팀섞기 참여: `{team_mix_count}회`"
        ),
        inline=False,
    )
    embed.add_field(
        name="같이 있던 인원 TOP3",
        value=join_discord_field_lines(companion_lines) if companion_lines else "같은 음성채널에 함께 있었던 기록이 없습니다.",
        inline=False,
    )
    embed.add_field(
        name="채널별 체류 TOP",
        value=join_discord_field_lines(lines),
        inline=False,
    )
    return embed, None


class VoiceLogCustomRangeModal(discord.ui.Modal):
    def __init__(self, member: discord.Member):
        super().__init__(title="음성로그 조회기간 입력")
        self.member = member
        self.start_date = discord.ui.TextInput(
            label="시작일",
            placeholder="예: 2026-06-01",
            min_length=10,
            max_length=10,
            required=True,
        )
        self.end_date = discord.ui.TextInput(
            label="종료일",
            placeholder="예: 2026-06-05",
            min_length=10,
            max_length=10,
            required=True,
        )
        self.add_item(self.start_date)
        self.add_item(self.end_date)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
            return

        try:
            since, until = parse_date_range(str(self.start_date), str(self.end_date), default_days=30)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        embed, error_text = build_voice_log_embed(interaction.guild, self.member, since, until)
        if error_text:
            await interaction.response.send_message(error_text, ephemeral=True)
            return
        await interaction.response.send_message(embed=embed, ephemeral=True)


class VoiceLogPeriodView(discord.ui.View):
    def __init__(self, requester_id: int, member: discord.Member):
        super().__init__(timeout=120)
        self.requester_id = requester_id
        self.member = member

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("이 조회 패널은 명령어를 사용한 사람만 선택할 수 있습니다.", ephemeral=True)
            return False
        return True

    async def show_period(self, interaction: discord.Interaction, since: datetime, until: datetime):
        embed, error_text = build_voice_log_embed(interaction.guild, self.member, since, until)
        for item in self.children:
            item.disabled = True

        if error_text:
            await interaction.response.edit_message(content=error_text, embed=None, view=self)
            return
        await interaction.response.edit_message(content=None, embed=embed, view=self)

    @discord.ui.button(label="오늘", style=discord.ButtonStyle.primary)
    async def today(self, interaction: discord.Interaction, button: discord.ui.Button):
        now = get_kst_now()
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        await self.show_period(interaction, since, now)

    @discord.ui.button(label="어제", style=discord.ButtonStyle.secondary)
    async def yesterday(self, interaction: discord.Interaction, button: discord.ui.Button):
        now = get_kst_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        since = today_start - timedelta(days=1)
        until = today_start - timedelta(seconds=1)
        await self.show_period(interaction, since, until)

    @discord.ui.button(label="일주일", style=discord.ButtonStyle.success)
    async def week(self, interaction: discord.Interaction, button: discord.ui.Button):
        now = get_kst_now()
        await self.show_period(interaction, now - timedelta(days=7), now)

    @discord.ui.button(label="조회기간입력", style=discord.ButtonStyle.primary)
    async def custom_range(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VoiceLogCustomRangeModal(self.member))


@bot.tree.command(name="음성로그", description="특정 인원의 음성채널 체류 기록을 기간별로 확인합니다.")
@app_commands.rename(member="인원")
@app_commands.describe(member="조회할 인원")
async def voice_channel_log(interaction: discord.Interaction, member: discord.Member):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"🎧 {member.display_name}님의 음성로그",
        description="조회할 기간을 선택해주세요.",
        color=0x3498DB,
    )
    embed.add_field(name="빠른 조회", value="오늘 / 어제 / 일주일", inline=False)
    embed.add_field(name="직접 입력", value="조회기간입력 버튼을 눌러 시작일과 종료일을 입력합니다.", inline=False)
    await interaction.response.send_message(
        embed=embed,
        view=VoiceLogPeriodView(interaction.user.id, member),
        ephemeral=True,
    )


@bot.tree.command(name="끼리끼리조회", description="두 인원의 음성채널 체류 시간과 겹친 시간을 비교합니다.")
@app_commands.rename(member1="인원1", member2="인원2", start_date="시작일", end_date="종료일")
@app_commands.describe(
    member1="첫 번째 인원",
    member2="두 번째 인원",
    start_date="예: 2026-05-01, 비워두면 최근 30일",
    end_date="예: 2026-05-31, 비워두면 현재까지",
)
async def pair_voice_compare(
    interaction: discord.Interaction,
    member1: discord.Member,
    member2: discord.Member,
    start_date: str | None = None,
    end_date: str | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    if member1.id == member2.id:
        await interaction.response.send_message("서로 다른 두 인원을 선택해주세요.", ephemeral=True)
        return

    try:
        since, until = parse_date_range(start_date, end_date, default_days=30)
    except ValueError as e:
        await interaction.response.send_message(str(e), ephemeral=True)
        return

    intervals_1 = get_voice_channel_intervals_between(interaction.guild.id, member1.id, since, until)
    intervals_2 = get_voice_channel_intervals_between(interaction.guild.id, member2.id, since, until)

    total_1 = sum_voice_intervals_seconds(intervals_1)
    total_2 = sum_voice_intervals_seconds(intervals_2)
    overlap_by_channel = calculate_voice_overlap_seconds(intervals_1, intervals_2)
    overlap_total = sum(overlap_by_channel.values())

    if total_1 <= 0 and total_2 <= 0:
        await interaction.response.send_message("해당 기간 기준 두 인원의 음성채널 기록이 없습니다.", ephemeral=True)
        return

    solo_1 = max(0, total_1 - overlap_total)
    solo_2 = max(0, total_2 - overlap_total)
    overlap_rate_1 = (overlap_total / total_1) * 100 if total_1 > 0 else 0
    overlap_rate_2 = (overlap_total / total_2) * 100 if total_2 > 0 else 0
    combined_total = total_1 + total_2
    together_share = (overlap_total * 2 / combined_total) * 100 if combined_total > 0 else 0

    channel_lines = []
    for idx, (channel_id, seconds) in enumerate(
        sorted(overlap_by_channel.items(), key=lambda item: (-item[1], item[0]))[:10],
        start=1,
    ):
        channel = interaction.guild.get_channel(channel_id)
        channel_name = channel.mention if channel else f"알 수 없는 채널 ({channel_id})"
        channel_percentage = (seconds / overlap_total) * 100 if overlap_total > 0 else 0
        channel_lines.append(
            f"**{idx}. {channel_name}**\n"
            f"함께 체류: `{format_duration_korean(seconds)}` / `{channel_percentage:.1f}%`"
        )

    embed = discord.Embed(
        title=f"🎙 {member1.display_name} / {member2.display_name} 끼리끼리조회",
        description=(
            f"두 사람이 같은 음성채널에 함께 있었던 시간은 "
            f"**{format_duration_korean(overlap_total)}**입니다."
        ),
        color=0x5865F2,
    )
    embed.add_field(
        name="집계 기준",
        value=f"`{since.strftime('%Y-%m-%d')}` ~ `{until.strftime('%Y-%m-%d')}` / 관전자 시간 제외",
        inline=False,
    )
    embed.add_field(
        name="한눈에 보기",
        value=(
            f"함께 체류: `{format_duration_korean(overlap_total)}`\n"
            f"전체 체류 대비 함께한 비중: `{together_share:.1f}%`\n"
            f"{member1.display_name} 기준 겹침: `{overlap_rate_1:.1f}%`\n"
            f"{member2.display_name} 기준 겹침: `{overlap_rate_2:.1f}%`"
        ),
        inline=False,
    )
    embed.add_field(
        name=f"{member1.display_name}",
        value=(
            f"총 체류: `{format_duration_korean(total_1)}`\n"
            f"단독 체류: `{format_duration_korean(solo_1)}`"
        ),
        inline=True,
    )
    embed.add_field(
        name=f"{member2.display_name}",
        value=(
            f"총 체류: `{format_duration_korean(total_2)}`\n"
            f"단독 체류: `{format_duration_korean(solo_2)}`"
        ),
        inline=True,
    )

    embed.add_field(
        name="같이 있었던 채널 TOP",
        value="\n".join(channel_lines) if channel_lines else "같은 채널에 함께 있었던 기록이 없습니다.",
        inline=False,
    )
    embed.set_footer(text="함께 체류 시간은 두 사람이 같은 음성채널에 동시에 있었던 시간만 집계합니다.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


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
        await interaction.response.send_message("음성채널에 먼저 들어가주세요.", ephemeral=True)
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
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if amount < MIN_BET:
        await interaction.response.send_message(
            f"최소 베팅 금액은 `{format_money(MIN_BET)}`입니다.",
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
            f"베팅 금액: `{format_money(amount)}`\n\n"
            "두근두근 보급 상자가 떨어지고 있습니다...\n"
            "상자를 열어 어떤 아이템을 챙길지 확인해보세요.\n\n"
            "가능한 결과:\n"
            "• 빈 상자\n"
            "• 1뚝\n"
            "• 2뚝\n"
            "• 3뚝\n"
            "• 보급 총기 획득\n"
            "• 풀세트 보급 대박\n\n"
            "버튼을 눌러 보급 상자를 개봉하세요."
        ),
        color=0xF39C12,
    )

    await interaction.response.send_message(
        embed=embed,
        view=SupplyDropView(interaction.user.id, amount),
    )

@bot.tree.command(name="문의패널", description="문의, 신고, 건의용 선택 패널을 생성합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def inquiry_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="문의 안내",
        description="문의하기 전 아래 항목에서 원하는 종류를 선택해주세요.",
        color=0x3498DB,
    )
    await interaction.channel.send(embed=embed, view=InquiryPanelView())
    await interaction.response.send_message("문의 패널 생성이 완료되었습니다.", ephemeral=True)

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

@bot.tree.command(name="확률표", description="현재 게임들의 확률과 배당을 확인합니다.")
async def probability_table(interaction: discord.Interaction):
    embed = discord.Embed(title="🎰 게임 배당표", color=0x3498DB)

    embed.add_field(
        name="슬롯",
        value=(
            "3개 일치: 약 4.34%\n"
            "7 7 7 : 약 0.72% / 14배\n"
            "클로버 클로버 클로버 : 약 0.72% / 9배\n"
            "기타 3개 일치 : 각각 약 0.72% / 7배\n\n"
            "정확히 2개 일치: 약 45.52%\n"
            "7 7 : 약 7.59% / 1.8배\n"
            "클로버 클로버 : 약 7.59% / 1.5배\n"
            "기타 2개 일치 : 각각 약 7.59% / 1.25배\n\n"
            "완전 꽝: 약 50.14%"
        ),
        inline=False,
    )


    embed.add_field(
        name="동전",
        value="앞/뒤 50% 확률\n승리 시 2배",
        inline=False,
    )

    embed.add_field(
        name="보급",
        value=(
            "빈 상자 34% / 0배\n"
            "1뚝 24% / 1.0배\n"
            "2뚝 19% / 1.1배\n"
            "3뚝 11% / 1.6배\n"
            "보급 총기 획득 9% / 2.6배\n"
            "풀세트 보급 대박 3% / 4.7배"
        ),
        inline=False,
    )

    embed.add_field(
        name="블랙잭",
        value=(
            "딜러와 21에 가까운 패를 겨룹니다.\n"
            "일반 승리 / 2배\n"
            "첫 두 장으로 21 달성 / 2.5배\n"
            "무승부 / 원금 반환"
        ),
        inline=False,
    )

    embed.add_field(
        name="경마",
        value=(
            "즈미 20% / 5.0배\n"
            "훈이 18% / 5.5배\n"
            "해랑솔 16% / 6.25배\n"
            "김천 14% / 7.1배\n"
            "삼성 12% / 8.3배\n"
            "하랑 11% / 9.1배\n"
            "개쩌는머로 9% / 11.1배"
        ),
        inline=False,
    )

    embed.add_field(
        name="숫자야구",
        value=(
            f"참가비 `{format_money(NUMBER_BASEBALL_COST)}` 고정\n"
            f"서로 다른 숫자 {NUMBER_BASEBALL_DIGITS}개를 `{NUMBER_BASEBALL_ATTEMPTS}회` 안에 추리\n"
            "1~3회 성공 / 4배\n"
            "4~5회 성공 / 2.5배\n"
            "6~8회 성공 / 1.5배\n"
            "실패 / 베팅금 손실"
        ),
        inline=False,
    )

    embed.add_field(
        name="야추",
        value=(
            "첫 주사위 3개 공개 후 배팅/다이 진행\n"
            "두 사람 모두 배팅해야 최종 주사위 공개\n"
            "족보 순위:\n"
            "야추 > 포카드 > 풀하우스 > 라지 스트레이트 > 스몰 스트레이트 > 트리플 > 투페어 > 원페어 > 노페어\n"
            "승리 시 판돈 획득 / 무승부 시 베팅금 반환"
        ),
        inline=False,
    )

    embed.add_field(
        name="지뢰찾기",
        value=(
            f"{MINESWEEPER_SIZE}x{MINESWEEPER_SIZE} 보드 / 지뢰 {MINESWEEPER_MINE_COUNT}개\n"
            "안전 칸을 열수록 배당 상승\n"
            "1개 1.15배 / 3개 1.50배 / 5개 2.05배\n"
            "8개 3.80배 / 10개 6.50배 / 13개 15배\n"
            "지뢰 클릭 시 베팅금 손실"
        ),
        inline=False,
    )

    embed.add_field(
        name="몰빵게임",
        value=(
            f"참가비 `{format_money(MIN_BET)}` 이상 자유 입력\n"
            "하루 동안 참가한 사람 중 1명을 무작위로 추첨\n"
            "그날 참가자들의 총 금액을 모두 1명이 가져갑니다."
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

    embed.add_field(
        name="섯다",
        value=(
            "첫 패 공개 후 배팅/다이 진행\n"
            "두 사람 모두 배팅해야 두 번째 패 공개\n"
            "광땡 > 땡 > 알리 > 독사 > 구삥 > 장삥 > 장사 > 세륙 > 갑오 > 끗 > 망통"
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


@bot.tree.command(name="플리등록", description="서버 플레이리스트에 음악 링크를 등록합니다.")
@app_commands.rename(title="제목", url="링크")
@app_commands.describe(title="목록에 표시할 음악 제목", url="유튜브 등 재생할 음악 링크")
async def playlist_add(interaction: discord.Interaction, title: str, url: str):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    title = title.strip()
    url = url.strip()
    if not title or not url:
        await interaction.response.send_message("제목과 링크를 모두 입력해주세요.", ephemeral=True)
        return

    track_id = add_playlist_track(interaction.guild.id, interaction.user.id, title, url)
    await interaction.response.send_message(
        f"🎵 플레이리스트에 등록했습니다.\n"
        f"곡번호: `{track_id}`\n"
        f"제목: **{title}**"
    )


@bot.tree.command(name="플리목록", description="서버 플레이리스트 목록을 확인합니다.")
async def playlist_list(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    rows = get_playlist_tracks(interaction.guild.id, 30)
    if not rows:
        await interaction.response.send_message("등록된 플레이리스트가 없습니다.", ephemeral=True)
        return

    lines = []
    for track_id, owner_user_id, title, url, created_at in rows:
        owner = interaction.guild.get_member(int(owner_user_id))
        owner_name = owner.display_name if owner else f"알 수 없는 유저 ({owner_user_id})"
        lines.append(
            f"`{track_id}` **{title}**\n"
            f"등록자: {owner_name}\n"
            f"링크: {url}"
        )

    embed = discord.Embed(
        title="🎵 서버 플레이리스트",
        description="`/플리재생`을 입력하면 플레이리스트 패널에서 음악을 선택해 재생할 수 있습니다.",
        color=0x1DB954,
    )
    embed.add_field(name="최근 등록곡", value=join_discord_field_lines(lines), inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="플리삭제", description="서버 플레이리스트에서 곡을 삭제합니다.")
@app_commands.rename(track_id="곡번호")
@app_commands.describe(track_id="삭제할 곡번호")
async def playlist_delete(interaction: discord.Interaction, track_id: int):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    track = get_playlist_track(interaction.guild.id, track_id)
    if track is None:
        await interaction.response.send_message("해당 곡번호의 음악을 찾을 수 없습니다.", ephemeral=True)
        return

    can_delete = track["owner_user_id"] == interaction.user.id
    if isinstance(interaction.user, discord.Member):
        can_delete = can_delete or interaction.user.guild_permissions.administrator

    if not can_delete:
        await interaction.response.send_message("등록자 또는 관리자만 삭제할 수 있습니다.", ephemeral=True)
        return

    delete_playlist_track(interaction.guild.id, track_id)
    await interaction.response.send_message(f"🗑 플레이리스트에서 **{track['title']}** 곡을 삭제했습니다.")


@bot.tree.command(name="플리재생", description="서버 플레이리스트 패널을 열어 음악을 재생합니다.")
async def playlist_play(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    rows = get_playlist_tracks(interaction.guild.id, 25)
    tracks = [build_playlist_track_from_row(row) for row in rows]

    if not tracks:
        await interaction.response.send_message("재생할 플레이리스트 곡이 없습니다.", ephemeral=True)
        return

    playlist_library_cache[interaction.guild.id] = list(tracks)
    playlist_modes.setdefault(interaction.guild.id, "order")

    await disable_playlist_panel(interaction.guild)
    await interaction.response.send_message(
        embed=build_playlist_panel_embed(interaction.guild),
        view=PlaylistPanelView(interaction.user.id, tracks),
    )
    panel_message = await interaction.original_response()
    playlist_panel_messages[interaction.guild.id] = (interaction.channel.id, panel_message.id)


@bot.tree.command(name="플리스킵", description="현재 재생 중인 플레이리스트 곡을 넘깁니다.")
async def playlist_skip(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    voice_client = interaction.guild.voice_client
    if voice_client is None or not voice_client.is_connected():
        await interaction.response.send_message("현재 재생 중인 플레이리스트가 없습니다.", ephemeral=True)
        return

    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
        await interaction.response.send_message("⏭ 현재 곡을 넘겼습니다.")
        return

    await interaction.response.send_message("넘길 곡이 없습니다.", ephemeral=True)


@bot.tree.command(name="플리정지", description="플레이리스트 재생을 정지하고 음성채널에서 나갑니다.")
async def playlist_stop(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    playlist_queues.pop(interaction.guild.id, None)
    playlist_now_playing.pop(interaction.guild.id, None)
    playlist_previous_tracks.pop(interaction.guild.id, None)
    playlist_library_cache.pop(interaction.guild.id, None)
    playlist_modes.pop(interaction.guild.id, None)
    playlist_text_channels.pop(interaction.guild.id, None)
    await disable_playlist_panel(interaction.guild)

    voice_client = interaction.guild.voice_client
    if voice_client is not None and voice_client.is_connected():
        await voice_client.disconnect(force=True)
        await interaction.response.send_message("⏹ 플레이리스트 재생을 정지했습니다.")
        return

    await interaction.response.send_message("현재 연결된 음성채널이 없습니다.", ephemeral=True)


@bot.tree.command(name="몰빵참여", description="입력한 금액으로 오늘의 몰빵게임에 참여합니다.")
async def join_all_in_game(interaction: discord.Interaction, amount: int):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return
    if amount < MIN_BET:
        await interaction.response.send_message(f"최소 참가 금액은 `{format_money(MIN_BET)}`입니다.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    today = get_today_kst_date_str()

    if has_all_in_entry(today, interaction.guild.id, interaction.user.id):
        await interaction.followup.send("오늘은 이미 몰빵게임에 참여했습니다.", ephemeral=True)
        return

    if not can_afford(interaction.user.id, amount):
        await interaction.followup.send(
            f"몰빵게임 참가비 `{format_money(amount)}`이 부족합니다.",
            ephemeral=True,
        )
        return

    add_balance(interaction.user.id, -amount)
    add_all_in_entry(today, interaction.guild.id, interaction.user.id, amount)

    entries = get_all_in_entries(today, interaction.guild.id)
    pool_amount = sum(amount for _, amount in entries)

    await interaction.followup.send(
        f"{interaction.user.mention}님이 오늘의 몰빵게임에 참여했습니다.\n"
        f"참가비 `{format_money(amount)}`\n"
        f"현재 참가 인원: `{len(entries)}명`\n"
        f"현재 누적 금액: `{format_money(pool_amount)}`"
    )


@bot.tree.command(name="돈주기내역", description="특정 인원의 돈 지급 내역을 확인합니다.")
@app_commands.rename(member="인원")
@app_commands.describe(member="조회할 인원")
async def money_grant_history(interaction: discord.Interaction, member: discord.Member):
    rows = get_money_grant_logs(interaction.guild.id, member.id, 20)

    if not rows:
        await interaction.response.send_message("지급 내역이 없습니다.", ephemeral=True)
        return

    lines = []
    for giver_user_id, amount, note_text, created_at in rows:
        giver = interaction.guild.get_member(int(giver_user_id))
        giver_name = giver.display_name if giver else f"알 수 없는 유저 ({giver_user_id})"
        try:
            created_text = dt_from_db(created_at).strftime("%Y-%m-%d %H:%M")
        except Exception:
            created_text = created_at
        line = f"**[{created_text}]**\n지급자: {giver_name}\n금액: {format_money(amount)}"
        if note_text:
            line += f"\n비고: {note_text}"
        lines.append(line)

    embed = discord.Embed(
        title=f"🧾 {member.display_name}님의 돈 지급 내역",
        description="\n\n".join(lines),
        color=0xF1C40F,
    )
    embed.set_footer(text="최근 20개의 지급 내역을 표시합니다.")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ----------------------------
# 신용 / 대출 명령어
# ----------------------------

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

    if profile["is_blacklisted"]:
        await interaction.response.send_message(
            "현재 신용불량자 상태입니다. 기존 대출을 모두 상환하기 전까지는 대출이 불가능합니다.",
            ephemeral=True,
        )
        return

    grade = profile["grade"]
    max_amount = get_loan_limit_by_grade(grade)
    remaining_limit = get_remaining_loan_limit(interaction.user.id)
    interest_rate = get_loan_interest_by_grade(grade)
    active_loan_count = len(get_active_loans(interaction.user.id))

    if active_loan_count >= 2:
        await interaction.response.send_message(
            (
                "동시에 진행할 수 있는 대출은 최대 2건입니다.\n"
                "기존 대출을 `/대출상환` 또는 `/중도상환`으로 정리한 뒤 다시 시도해주세요."
            ),
            ephemeral=True,
        )
        return

    if remaining_limit <= 0:
        await interaction.response.send_message(
            f"현재 {grade}등급의 대출 한도를 모두 사용 중입니다. `/대출상환` 또는 `/중도상환` 후 다시 시도해주세요.",
            ephemeral=True,
        )
        return

    if amount > remaining_limit:
        await interaction.response.send_message(
            (
                f"현재 {grade}등급의 최대 대출 가능 금액은 `{format_money(max_amount)}`이며,\n"
                f"이미 사용 중인 한도를 제외한 남은 대출 가능 금액은 `{format_money(remaining_limit)}`입니다."
            ),
            ephemeral=True,
        )
        return

    required_balance = (amount + 3) // 4
    current_balance = get_balance(interaction.user.id)
    if current_balance < required_balance:
        await interaction.response.send_message(
            (
                f"대출을 받으려면 현재 잔액이 대출 금액의 25% 이상이어야 합니다.\n"
                f"필요 잔액: `{format_money(required_balance)}`\n"
                f"현재 잔액: `{format_money(current_balance)}`"
            ),
            ephemeral=True,
        )
        return

    borrowed_at = get_kst_now()
    due_at = borrowed_at + timedelta(days=LOAN_REPAYMENT_DAYS)
    total_repayment = calculate_total_repayment(amount, interest_rate)

    embed = discord.Embed(title="💳 대출 실행 확인", color=0xF1C40F)
    embed.add_field(name="현재 신용등급", value=f"{grade}등급", inline=False)
    embed.add_field(name="대출 금액", value=format_money(amount), inline=False)
    embed.add_field(name="이자율", value=f"{interest_rate}%", inline=False)
    embed.add_field(name="총 상환 금액", value=format_money(total_repayment), inline=False)
    embed.add_field(name="상환 기한", value=due_at.strftime("%Y-%m-%d %H:%M:%S KST"), inline=False)
    embed.add_field(name="현재 진행 중인 대출 수", value=f"{active_loan_count}건", inline=False)
    embed.add_field(name="남은 대출 한도", value=format_money(remaining_limit), inline=False)
    embed.add_field(name="현재 잔액", value=format_money(current_balance), inline=False)
    embed.add_field(
        name="대출 조건 확인",
        value=(
            "확인을 누르면 대출이 즉시 실행됩니다.\n"
            f"상환 후 대출 한도는 {LOAN_LIMIT_RECOVERY_DELAY_MINUTES}분 뒤 회복됩니다."
        ),
        inline=False,
    )

    await interaction.response.send_message(
        embed=embed,
        view=LoanConfirmView(interaction.guild.id, interaction.user.id, amount),
        ephemeral=True,
    )


@bot.tree.command(name="중도상환", description="현재 대출을 즉시 전액 상환합니다.")
async def repay_loan_command(interaction: discord.Interaction):
    active_loans = get_active_loans(interaction.user.id)
    if not active_loans:
        await interaction.response.send_message("현재 상환할 대출이 없습니다.", ephemeral=True)
        return

    repayment_amount = sum(loan["total_repayment"] for loan in active_loans)
    if not can_afford(interaction.user.id, repayment_amount):
        await interaction.response.send_message(
            f"상환 금액 `{format_money(repayment_amount)}`이 부족합니다.",
            ephemeral=True,
        )
        return

    profile = get_credit_profile(interaction.user.id)
    previous_grade_text = get_credit_grade_text(interaction.user.id)
    loan_progress_amount = profile["loan_progress_amount"]

    add_balance(interaction.user.id, -repayment_amount)
    repay_loans([loan["id"] for loan in active_loans])

    grade_up = False

    if profile["is_blacklisted"]:
        manual_debt_total = get_total_active_manual_credit_debt(interaction.guild.id, interaction.user.id) if interaction.guild else 0
        if manual_debt_total <= 0:
            set_credit_blacklisted(interaction.user.id, False)
            set_credit_grade(interaction.user.id, INITIAL_CREDIT_GRADE)
            if interaction.guild is not None:
                delete_labor_penalty(interaction.guild.id, interaction.user.id)
                await sync_blacklist_role(interaction.user, False)
            grade_up = True
        elif interaction.guild is not None:
            refresh_active_labor_penalty_debt(interaction.guild.id, interaction.user.id)
    else:
        required_amount = get_loan_limit_by_grade(profile["grade"])
        if loan_progress_amount >= required_amount:
            upgrade_credit_grade(interaction.user.id)
            grade_up = True

    current_grade_text = get_credit_grade_text(interaction.user.id)

    embed = discord.Embed(title="✅ 대출 상환 완료", color=0x2ECC71)
    embed.add_field(name="상환한 대출 수", value=f"{len(active_loans)}건", inline=False)
    embed.add_field(name="상환 금액", value=format_money(repayment_amount), inline=False)
    embed.add_field(name="상환 전 신용등급", value=previous_grade_text, inline=False)
    embed.add_field(name="현재 신용등급", value=current_grade_text, inline=False)
    embed.add_field(name="현재 잔액", value=format_money(get_balance(interaction.user.id)), inline=False)
    embed.add_field(
        name="한도 회복 안내",
        value=f"상환한 원금만큼의 대출 한도는 `{LOAN_LIMIT_RECOVERY_DELAY_MINUTES}분` 뒤 회복됩니다.",
        inline=False,
    )

    if profile["is_blacklisted"]:
        manual_debt_total = get_total_active_manual_credit_debt(interaction.guild.id, interaction.user.id) if interaction.guild else 0
        if manual_debt_total <= 0:
            embed.add_field(
                name="등급 변화",
                value=f"기존 대출을 모두 상환하여 신용불량자 상태가 해제되고 {INITIAL_CREDIT_GRADE}등급으로 복귀했습니다.",
                inline=False,
            )
        else:
            embed.add_field(
                name="등급 변화",
                value=(
                    "일반 대출은 모두 상환했지만 관리자 부채가 남아 있어 신용불량자 상태는 유지됩니다.\n"
                    f"남은 관리자 부채: `{format_money(manual_debt_total)}`"
                ),
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
                f"등급 상승을 위해서는 현재 등급 기준 최대 한도인 `{format_money(required_amount)}` 이상 대출 실적을 쌓아야 합니다.\n"
                f"현재 누적 실적: `{format_money(loan_progress_amount)}`"
            ),
            inline=False,
        )

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="내신용", description="현재 신용등급과 대출 상태를 확인합니다.")
async def my_credit(interaction: discord.Interaction):
    embed = build_credit_embed(interaction.user, interaction.guild.id if interaction.guild else None)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="신용조회", description="특정 인원의 신용등급과 대출 상태를 조회합니다.")
@app_commands.rename(member="인원")
async def credit_lookup(interaction: discord.Interaction, member: discord.Member):
    embed = build_credit_embed(member, interaction.guild.id if interaction.guild else None)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="신용등급표", description="등급별 대출 한도와 이자율을 확인합니다.")
async def credit_grade_table(interaction: discord.Interaction):
    lines = []
    for grade in range(MAX_CREDIT_GRADE, MIN_CREDIT_GRADE - 1, -1):
        limit_text = format_money(get_loan_limit_by_grade(grade))
        interest_text = f"{get_loan_interest_by_grade(grade)}%"
        lines.append(f"`{grade}등급`  대출 한도 {limit_text} / 이자율 {interest_text}")

    embed = discord.Embed(
        title="📊 신용등급표",
        description="\n".join(lines),
        color=0x3498DB,
    )
    embed.add_field(
        name="대출 조건",
        value=(
            "대출은 현재 신용등급의 남은 한도 내에서만 가능합니다.\n"
            "또한 현재 잔액이 대출 금액의 25% 이상이어야 합니다.\n"
            f"상환 후 대출 한도는 {LOAN_LIMIT_RECOVERY_DELAY_MINUTES}분 뒤 회복됩니다."
        ),
        inline=False,
    )
    embed.add_field(
        name="등급 변동 기준",
        value=(
            "현재 등급 최대 한도 이상 대출 실적을 쌓고 정상 상환하면 1단계 상승합니다.\n"
            f"마지막 대출 사용 후 {LOAN_GRADE_DECAY_DAYS}일 동안 새 대출이 없으면 1단계 하락합니다."
        ),
        inline=False,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="노동", description="신용불량자 상태일 때 노동을 진행합니다.")
async def labor(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    profile = get_credit_profile(interaction.user.id)
    if not profile["is_blacklisted"]:
        await interaction.response.send_message("현재 신용불량자 상태가 아닙니다.", ephemeral=True)
        return

    penalty = ensure_active_labor_penalty(interaction.guild.id, interaction.user.id)
    if penalty is None:
        await interaction.response.send_message("진행 중인 노동 패널티 정보가 없습니다. 관리자에게 문의해주세요.", ephemeral=True)
        return

    embed = build_labor_embed(interaction.user, penalty, interaction.guild.id)
    await interaction.response.send_message(
        embed=embed,
        view=LaborWorkView(interaction.guild.id, interaction.user.id),
    )


@bot.tree.command(name="노동현황", description="현재 노동 진행 현황을 확인합니다.")
async def labor_status(interaction: discord.Interaction, member: discord.Member | None = None):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    target = member or interaction.user
    penalty = ensure_active_labor_penalty(interaction.guild.id, target.id)
    if penalty is None:
        await interaction.response.send_message("진행 중인 노동 패널티가 없습니다.", ephemeral=True)
        return

    embed = build_labor_embed(target, penalty, interaction.guild.id)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="노동가챠", description="가챠권을 사용해 남은 노동 횟수를 줄여봅니다.")
async def labor_gacha(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    profile = get_credit_profile(interaction.user.id)
    if not profile["is_blacklisted"]:
        await interaction.response.send_message("현재 신용불량자 상태가 아니라 노동가챠를 사용할 수 없습니다.", ephemeral=True)
        return

    penalty = ensure_active_labor_penalty(interaction.guild.id, interaction.user.id)
    if penalty is None:
        await interaction.response.send_message("진행 중인 노동 패널티가 없습니다.", ephemeral=True)
        return

    ticket_count = get_labor_gacha_ticket_count(interaction.guild.id, interaction.user.id)
    if ticket_count <= 0:
        await interaction.response.send_message("보유한 노동가챠권이 없습니다. 관리자에게 지급을 요청해주세요.", ephemeral=True)
        return

    if not consume_labor_gacha_ticket(interaction.guild.id, interaction.user.id):
        await interaction.response.send_message("노동가챠권 사용에 실패했습니다. 다시 시도해주세요.", ephemeral=True)
        return

    result_label, percent = roll_labor_gacha()
    remaining_before = max(0, penalty["required_count"] - penalty["completed_count"])
    reduction_count = 0
    resolved = False
    updated_penalty = penalty

    if percent > 0 and remaining_before > 0:
        reduction_count = min(remaining_before, max(1, math.ceil(remaining_before * percent / 100)))
        updated_penalty, resolved = apply_labor_progress(interaction.guild.id, interaction.user.id, reduction_count)
        if updated_penalty is None:
            await interaction.response.send_message("노동가챠 처리 중 오류가 발생했습니다.", ephemeral=True)
            return
    else:
        updated_penalty = get_active_labor_penalty(interaction.guild.id, interaction.user.id) or penalty

    remaining_after = max(0, updated_penalty["required_count"] - updated_penalty["completed_count"])
    embed = discord.Embed(title="🎟 노동가챠 결과", color=0xF1C40F)
    embed.add_field(name="결과", value=result_label, inline=False)
    embed.add_field(name="가챠 적용 전 남은 노동", value=f"`{remaining_before}회`", inline=True)
    embed.add_field(name="감소한 노동 횟수", value=f"`{reduction_count}회`", inline=True)
    embed.add_field(name="가챠 적용 후 남은 노동", value=f"`{remaining_after}회`", inline=True)
    embed.add_field(
        name="남은 가챠권",
        value=f"`{get_labor_gacha_ticket_count(interaction.guild.id, interaction.user.id)}장`",
        inline=False,
    )

    if resolved:
        embed.color = 0x2ECC71
        embed.add_field(
            name="결과 안내",
            value=f"노동이 모두 해제되어 신용불량자 상태가 종료되고 `{INITIAL_CREDIT_GRADE}등급`으로 복귀했습니다.",
            inline=False,
        )
        await sync_blacklist_role(interaction.user, False)
    elif percent == 0:
        embed.add_field(name="결과 안내", value="이번에는 꽝입니다. 다음 가챠권을 노려보세요.", inline=False)
    else:
        embed.add_field(name="결과 안내", value=f"남은 노동 횟수의 {percent}%가 감소했습니다.", inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="대출상환", description="특정 대출 번호에 원하는 금액만큼 상환합니다.")
@app_commands.rename(loan_id="대출번호", amount="금액")
async def repay_single_loan_command(interaction: discord.Interaction, loan_id: int, amount: int):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("상환 금액은 1원 이상이어야 합니다.", ephemeral=True)
        return

    loan = get_loan_by_id(loan_id)
    if loan is None or loan["user_id"] != interaction.user.id or loan["status"] not in {"active", "overdue"}:
        await interaction.response.send_message("상환 가능한 대출번호를 찾을 수 없습니다.", ephemeral=True)
        return

    payment_amount = min(amount, loan["remaining_total_repayment"])
    if not can_afford(interaction.user.id, payment_amount):
        await interaction.response.send_message(
            f"상환 금액 `{format_money(payment_amount)}`이 부족합니다.",
            ephemeral=True,
        )
        return

    profile = get_credit_profile(interaction.user.id)
    previous_grade_text = get_credit_grade_text(interaction.user.id)
    loan_progress_amount = profile["loan_progress_amount"]

    add_balance(interaction.user.id, -payment_amount)
    result = repay_loan_amount(loan_id, payment_amount)
    if result is None:
        await interaction.response.send_message("대출 상환 처리에 실패했습니다.", ephemeral=True)
        return

    grade_up = False
    if profile["is_blacklisted"]:
        if get_total_credit_obligation(interaction.guild.id, interaction.user.id) <= 0:
            set_credit_blacklisted(interaction.user.id, False)
            set_credit_grade(interaction.user.id, INITIAL_CREDIT_GRADE)
            delete_labor_penalty(interaction.guild.id, interaction.user.id)
            await sync_blacklist_role(interaction.user, False)
            grade_up = True
        else:
            refresh_active_labor_penalty_debt(interaction.guild.id, interaction.user.id)
    else:
        required_amount = get_loan_limit_by_grade(profile["grade"])
        if loan_progress_amount >= required_amount and not get_active_loans(interaction.user.id):
            upgrade_credit_grade(interaction.user.id)
            grade_up = True

    current_grade_text = get_credit_grade_text(interaction.user.id)
    embed = discord.Embed(title="✅ 대출 부분 상환 완료", color=0x2ECC71)
    embed.add_field(name="대출번호", value=f"`{loan_id}`", inline=False)
    embed.add_field(name="상환 금액", value=format_money(result["payment_amount"]), inline=False)
    embed.add_field(name="남은 상환 금액", value=format_money(result["remaining_total_repayment"]), inline=False)
    embed.add_field(name="회복 대기 한도", value=format_money(result["principal_recovered"]), inline=False)
    embed.add_field(name="상환 전 신용등급", value=previous_grade_text, inline=False)
    embed.add_field(name="현재 신용등급", value=current_grade_text, inline=False)
    embed.add_field(name="현재 잔액", value=format_money(get_balance(interaction.user.id)), inline=False)
    embed.add_field(
        name="한도 회복 안내",
        value=f"이번 상환으로 회복된 한도는 `{LOAN_LIMIT_RECOVERY_DELAY_MINUTES}분` 뒤 반영됩니다.",
        inline=False,
    )
    if result["fully_repaid"]:
        embed.add_field(name="대출 상태", value="해당 대출은 전액 상환되어 종료되었습니다.", inline=False)
    if profile["is_blacklisted"] and not grade_up and get_total_credit_obligation(interaction.guild.id, interaction.user.id) > 0:
        embed.add_field(name="신용 상태", value="남은 채무가 있어 신용불량자 상태는 유지됩니다.", inline=False)
    elif grade_up:
        embed.add_field(name="등급 변화", value="상환 조건이 충족되어 신용 상태가 갱신되었습니다.", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="차용증", description="개인 간 차용증 요청 창을 엽니다.")
@app_commands.rename(member="상대")
@app_commands.describe(member="차용증을 받을 상대")
async def create_promissory_note_command(interaction: discord.Interaction, member: discord.Member):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    if member.bot:
        await interaction.response.send_message("봇에게는 차용증을 보낼 수 없습니다.", ephemeral=True)
        return

    if member.id == interaction.user.id:
        await interaction.response.send_message("본인에게 차용증을 보낼 수는 없습니다.", ephemeral=True)
        return

    await interaction.response.send_modal(PromissoryNoteModal(member))


@bot.tree.command(name="차용증목록", description="현재 활성화된 차용증 목록을 확인합니다.")
@app_commands.rename(member="인원")
@app_commands.describe(member="확인할 인원, 비워두면 본인 기준")
async def promissory_note_list(interaction: discord.Interaction, member: discord.Member | None = None):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    target = member or interaction.user
    if target.id != interaction.user.id and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("다른 사람의 차용증 목록은 관리자만 확인할 수 있습니다.", ephemeral=True)
        return

    notes = get_active_promissory_notes_for_user(interaction.guild.id, target.id)
    if not notes:
        await interaction.response.send_message("현재 활성화된 차용증이 없습니다.", ephemeral=True)
        return

    lines = []
    for note_info in notes:
        lender = interaction.guild.get_member(note_info["lender_user_id"])
        borrower = interaction.guild.get_member(note_info["borrower_user_id"])
        lender_name = lender.display_name if lender else f"알 수 없는 유저 ({note_info['lender_user_id']})"
        borrower_name = borrower.display_name if borrower else f"알 수 없는 유저 ({note_info['borrower_user_id']})"
        role_text = "채권자" if target.id == note_info["lender_user_id"] else "채무자"
        lines.append(
            f"**차용증 #{note_info['id']}**\n"
            f"내 역할: `{role_text}`\n"
            f"채권자: {lender_name}\n"
            f"채무자: {borrower_name}\n"
            f"원금: `{format_money(note_info['principal_amount'])}`\n"
            f"이자: `{format_money(note_info['interest_amount'])}`\n"
            f"총 상환 금액: `{format_money(note_info['amount'])}`\n"
            f"상환 약속일: `{note_info['due_text']}`"
            + (f"\n비고: {note_info['note']}" if note_info["note"] else "")
        )

    embed = discord.Embed(
        title=f"🗂 {target.display_name}님의 차용증 목록",
        description="\n\n".join(lines[:20]),
        color=0x3498DB,
    )
    embed.set_footer(text="최근 활성 차용증 최대 20개를 표시합니다. 상환 완료 후에는 /차용증삭제 로 정리할 수 있습니다.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="차용증삭제", description="상환이 끝난 차용증을 정리합니다.")
@app_commands.rename(note_id="차용증번호")
@app_commands.describe(note_id="삭제할 차용증 번호")
async def delete_promissory_note_command(interaction: discord.Interaction, note_id: int):
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    note_info = get_promissory_note(note_id)
    if note_info is None or note_info["guild_id"] != str(interaction.guild.id):
        await interaction.response.send_message("해당 차용증을 찾을 수 없습니다.", ephemeral=True)
        return

    if note_info["status"] != "active":
        await interaction.response.send_message("이미 정리된 차용증입니다.", ephemeral=True)
        return

    if interaction.user.id != note_info["lender_user_id"]:
        await interaction.response.send_message("차용증은 채권자만 정리할 수 있습니다.", ephemeral=True)
        return

    resolve_promissory_note(note_id)

    lender = interaction.guild.get_member(note_info["lender_user_id"]) or interaction.client.get_user(note_info["lender_user_id"])
    borrower = interaction.guild.get_member(note_info["borrower_user_id"]) or interaction.client.get_user(note_info["borrower_user_id"])
    embed = build_promissory_note_embed(
        lender,
        borrower,
        note_info["principal_amount"],
        note_info["interest_amount"],
        note_info["due_text"],
        note_info["note"],
        title="✅ 차용증 정리 완료",
        color=0x2ECC71,
        status_text="상환 완료 처리됨",
        note_id=note_info["id"],
    )
    embed.set_footer(text="DB에는 이력이 남고, 활성 목록에서는 제외됩니다.")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="덕몽", description="덕몽의 진짜 오리를 찾아내는 게임입니다.")
async def duckmong(interaction: discord.Interaction, amount: int):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if amount < MIN_BET:
        await interaction.response.send_message(
            f"최소 베팅 금액은 `{format_money(MIN_BET)}`입니다.",
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
            f"베팅 금액: `{format_money(amount)}`\n\n"
            "세 직업 중 하나를 골라주세요.\n"
            "그 안에는 오리, 거위, 팰리컨이 하나씩 숨어 있습니다.\n\n"
            "오리: 베팅금액만큼 추가 획득\n"
            "거위: 전부 잃음\n"
            "팰리컨: 원금 반환"
        ),
        color=0xF1C40F,
    )

    await interaction.response.send_message(
        embed=embed,
        view=DuckmongView(interaction.user.id, amount, fake_names, hidden_results),
    )


@bot.tree.command(name="섯다", description="봇 또는 다른 유저와 일반 섯다 족보로 대결합니다.")
@app_commands.rename(amount="금액", member="상대")
@app_commands.describe(amount="배팅 금액", member="비워두면 봇과 대결합니다.")
async def seotda(interaction: discord.Interaction, amount: int, member: discord.Member | None = None):
    if not await ensure_not_blacklisted_for_gambling(interaction):
        return
    if interaction.guild is None:
        await interaction.response.send_message("서버에서만 사용할 수 있습니다.", ephemeral=True)
        return
    if amount < MIN_BET:
        await interaction.response.send_message(
            f"최소 베팅 금액은 `{format_money(MIN_BET)}`입니다.",
            ephemeral=True,
        )
        return

    if member is None:
        if not can_afford(interaction.user.id, amount):
            await interaction.response.send_message("잔액이 부족합니다.", ephemeral=True)
            return

        add_balance(interaction.user.id, -amount)
        match_view = SeotdaMatchView(interaction.guild.id, interaction.user.id, None, amount)
        embed = match_view.build_embed(interaction.guild, interaction.client.user)
        embed.add_field(name="상대", value="봇", inline=False)
        await interaction.response.send_message(embed=embed, view=match_view)
        return

    if member.bot:
        await interaction.response.send_message("봇과 대결하려면 상대를 비워두고 `/섯다`를 사용해주세요.", ephemeral=True)
        return

    if member.id == interaction.user.id:
        await interaction.response.send_message("본인과는 대결할 수 없습니다.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🃏 섯다 대결 요청",
        description=f"{member.mention}님, {interaction.user.mention}님이 섯다 대결을 신청했습니다.",
        color=0xF1C40F,
    )
    embed.add_field(name="도전자", value=interaction.user.mention, inline=True)
    embed.add_field(name="상대", value=member.mention, inline=True)
    embed.add_field(name="기본 배팅금", value=f"`{format_money(amount)}`", inline=False)
    embed.add_field(
        name="룰",
        value=(
            "수락 시 두 사람 모두 같은 금액을 먼저 겁니다.\n"
            "첫 패 공개 후 `배팅` 또는 `다이`를 선택합니다.\n"
            "둘 다 배팅해야 다음 패를 공개하고 승부합니다."
        ),
        inline=False,
    )
    embed.set_footer(text="상대방만 수락 또는 거절할 수 있습니다.")

    await interaction.response.send_message(
        content=member.mention,
        embed=embed,
        view=SeotdaChallengeView(interaction.user.id, member.id, amount),
    )


@bot.tree.command(name="도박명령어", description="도박 및 재화 시스템 관련 명령어를 확인합니다.")
async def gambling_commands(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎲 도박 / 재화 시스템 명령어",
        description=(
            "재화, 대출, 적금, 도박 명령어를 한 번에 확인할 수 있습니다.\n"
            "신용불량자 상태에서는 일부 도박 명령어 사용이 제한됩니다."
        ),
        color=0xF1C40F,
    )

    embed.add_field(
        name="재화 관리",
        value=(
            "`/기초생활수급비` - 하루 1회 지원금 받기\n"
            "`/잔액` - 현재 잔액 확인\n"
            "`/랭킹` - 서버 재산 순위 확인\n"
            "`/송금` - 비고와 함께 다른 유저에게 돈 보내기\n"
            "`/송금내역 [인원]` - 특정 인원이 받은 송금 내역 확인\n"
            "`/차용증` - 개인 간 차용증 요청"
        ),
        inline=False,
    )

    embed.add_field(
        name="적금",
        value=(
            "`/적금 [금액]` - 적금 가입\n"
            "`/내적금` - 현재 적금 확인\n"
            "`/적금수령` - 만기 적금 수령\n"
            "`/적금중도해지` - 원금만 돌려받고 적금 해지"
        ),
        inline=False,
    )

    embed.add_field(
        name="대출 / 신용",
        value=(
            "`/일수 [금액]` - 남은 대출 한도 내에서 추가 대출\n"
            "`/대출상환 [대출번호] [금액]` - 특정 대출 부분 상환\n"
            "`/중도상환` - 현재 진행 중인 대출 전체 상환\n"
            "`/내신용` - 내 신용등급, 대출, 노동 현황 확인\n"
            "`/신용조회 [인원]` - 특정 인원의 신용 정보 조회\n"
            "`/신용등급표` - 등급별 대출 한도와 이자율 확인\n"
            "`/노동` - 아오지탄광에서 광맥을 골라 채굴 진행\n"
            "`/노동가챠` - 노동가챠권으로 남은 노동 횟수 감소 시도\n"
            "`/노동현황` - 노동 진행 상황 확인\n"
            "`/벌금부여`로 등록된 관리자 부채는 노동 횟수에 반영됩니다.\n"
            "`/벌금삭제 [부채번호]` - 상환 완료된 관리자 부채 정리\n"
            "`/차용증목록` - 현재 차용증 목록 확인\n"
            "`/차용증삭제` - 채권자가 상환 완료된 차용증 정리"
        ),
        inline=False,
    )

    embed.add_field(
        name="도박 / 게임",
        value=(
            "`/슬롯 [금액]` - 슬롯머신\n"
            "`/동전 [금액]` - 동전 앞뒤 맞추기\n"
            "`/보급 [금액]` - 보급 상자 게임\n"
            "`/덕몽 [금액]` - 오리를 찾아라\n"
            "`/블랙잭 [금액]` - 딜러와 21 대결\n"
            "`/경마 [금액]` - 원하는 말에 베팅\n"
            "`/숫자야구` - 10만원 고정 숫자 추리 게임\n"
            "`/야추 [금액] [상대]` - 봇 또는 유저와 주사위 족보 대결\n"
            "`/지뢰찾기 [금액]` - 지뢰를 피해 수익 확정\n"
            "`/섯다 [금액] [상대]` - 봇 또는 유저와 섯다 대결\n"
            "`/몰빵참여 [금액]` - 원하는 금액으로 몰빵게임 참여"
        ),
        inline=False,
    )

    embed.add_field(
        name="참고 정보",
        value=(
            "`/확률표` - 게임 확률과 배당 확인\n"
            "`/족보` - 최근 게임 결과 확인\n"
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
            "`/세팅등업로그`, `/세팅퇴장로그`, `/세팅규칙로그`\n"
            "`/세팅구인채널`, `/세팅몰빵결과채널`, `/세팅가이드안내`, `/세팅환영메시지채널`\n"
            "`/세팅규칙역할`, `/세팅신입역할`, `/신용불량자역할`\n"
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
            "`/고정메시지`, `/고정메시지해제`, `/고정메시지확인`, `/내전공지`"
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
            "`/돈주기`, `/돈주기내역`, `/돈삭제`, `/송금내역`, `/벌금부여`, `/벌금삭제`\n"
            "`/신용불량자등록`, `/신용불량자목록`, `/신용불량자삭제`, `/신용초기화`\n"
            "`/노동가챠권지급`\n"
            "`/신용조회`, `/신용등급표`, `/일수`, `/대출상환`, `/중도상환`"
        ),
        inline=False,
    )
    admin_embed.add_field(
        name="✨ 자주 쓰는 예시",
        value=(
            "`/세팅등업패널문구`  여러 줄 패널 문구 설정\n"
            "`/신용불량자등록 @유저`  해당 유저 등록\n"
            "`/돈주기 @유저 10000 이벤트 보상`  특정 유저에게 비고와 함께 재화 지급"
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
            "`/기초생활수급비`, `/잔액`, `/랭킹`, `/송금`, `/송금내역`\n"
            "`/도박명령어`, `/확률표`, `/족보`"
        ),
        inline=False,
    )
    general_embed.add_field(
        name="🏦 적금 / 대출 / 신용",
        value=(
            "`/적금`, `/내적금`, `/적금수령`, `/적금중도해지`\n"
            "`/일수`, `/대출상환`, `/중도상환`, `/내신용`, `/신용조회`, `/신용등급표`, `/노동`, `/노동가챠`, `/노동현황`\n"
            "`/차용증`, `/차용증목록`, `/차용증삭제`"
        ),
        inline=False,
    )
    general_embed.add_field(
        name="🎮 도박 / 게임",
        value=(
            "`/슬롯`, `/동전`, `/보급`, `/덕몽`\n"
            "`/블랙잭`, `/경마`, `/숫자야구`, `/야추`, `/지뢰찾기`\n"
            "`/섯다`, `/몰빵참여`"
        ),
        inline=False,
    )
    general_embed.add_field(
        name="📨 인증 / 문의",
        value="`/문의패널`  패널 안에서 문의하기 / 신고하기 / 건의하기 버튼 사용",
        inline=False,
    )
    general_embed.add_field(
        name="👥 구인 / 팀 / 기타",
        value=(
            "`/구인`, `/종겜구인`, `/팀`, `/팀섞기로그`, `/음성로그`, `/끼리끼리조회`, `/시간설정패널`\n"
            "`/등업패널`, `/규칙버튼`, `/닉네임패널생성`\n"
            "`/플리등록`, `/플리목록`, `/플리삭제`, `/플리재생`, `/플리스킵`, `/플리정지`"
        ),
        inline=False,
    )
    general_embed.add_field(
        name="✨ 자주 쓰는 예시",
        value=(
            "`/적금 50000`  5만원 적금\n"
            "`/보급 10000`  1만원 보급 참여\n"
            "`/내신용`  대출, 신용등급, 노동 현황 확인\n"
            "`/차용증 @유저`  모달에서 원금, 이자, 상환일 입력\n"
            "`/섯다 10000 @유저`  유저와 섯다 대결 요청"
        ),
        inline=False,
    )
    general_embed.set_footer(text="일반 유저가 자주 쓰는 명령어만 모아두었습니다.")

    await interaction.response.send_message(embeds=[admin_embed, general_embed], ephemeral=True)

@bot.tree.command(name="내전공지", description="참여 버튼이 있는 내전 공지를 작성합니다.")
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
    set_credit_grade(member.id, MAX_CREDIT_GRADE)
    set_credit_blacklisted(member.id, True)
    reset_loan_progress_amount(member.id)
    debt_amount = get_total_credit_obligation(interaction.guild.id, member.id) or DEFAULT_LABOR_DEBT_AMOUNT
    create_or_replace_labor_penalty(interaction.guild.id, member.id, debt_amount)
    await sync_blacklist_role(member, True)

    await interaction.response.send_message(
        f"{member.mention}님을 신용불량자로 등록했습니다.\n필요 노동 횟수: `{calculate_labor_required_count(debt_amount)}회`",
        ephemeral=True,
    )


@bot.tree.command(name="노동가챠권지급", description="특정 인원에게 노동가챠권을 지급합니다.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.rename(member="인원", amount="개수")
async def grant_labor_gacha_ticket(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message("지급 개수는 1개 이상이어야 합니다.", ephemeral=True)
        return

    add_labor_gacha_tickets(interaction.guild.id, member.id, amount)
    current_count = get_labor_gacha_ticket_count(interaction.guild.id, member.id)
    await interaction.response.send_message(
        f"{member.mention}님에게 노동가챠권 `{amount}장`을 지급했습니다.\n현재 보유 수량: `{current_count}장`",
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
    reset_loan_progress_amount(member.id)
    delete_labor_penalty(interaction.guild.id, member.id)
    await sync_blacklist_role(member, False)

    await interaction.response.send_message(
        f"{member.mention}님의 신용불량자 등록을 해제했습니다.\n신용등급은 변경하지 않습니다.",
        ephemeral=True,
    )


@bot.tree.command(name="신용초기화", description="특정 인원의 신용불량자 상태를 해제하고 원하는 등급으로 조정합니다.")
@app_commands.checks.has_permissions(administrator=True)
async def reset_credit(interaction: discord.Interaction, member: discord.Member, grade: int):
    if grade < MIN_CREDIT_GRADE or grade > MAX_CREDIT_GRADE:
        await interaction.response.send_message(
            f"등급은 {MIN_CREDIT_GRADE}등급부터 {MAX_CREDIT_GRADE}등급까지만 가능합니다.",
            ephemeral=True,
        )
        return

    set_credit_blacklisted(member.id, False)
    set_credit_grade(member.id, grade)
    reset_loan_progress_amount(member.id)
    delete_labor_penalty(interaction.guild.id, member.id)
    await sync_blacklist_role(member, False)

    await interaction.response.send_message(
        f"{member.mention}님의 신용을 `{grade}등급`으로 초기화했습니다.",
        ephemeral=True,
    )



# ============================================================
# 디스코드 이벤트
# ============================================================

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        if interaction.response.is_done():
            await interaction.followup.send("이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True)
        else:
            await interaction.response.send_message("이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True)
        return

    raise error


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    guild_id = after.guild.id
    before_role_ids = {role.id for role in before.roles}
    after_role_ids = {role.id for role in after.roles}
    before_is_spectator = is_spectator_member(before, guild_id)
    after_is_spectator = is_spectator_member(after, guild_id)

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

    if after.voice and after.voice.channel is not None:
        if not before_is_spectator and after_is_spectator:
            end_voice_session(guild_id, after.id)
        elif before_is_spectator and not after_is_spectator:
            if get_active_voice_session(guild_id, after.id) is None:
                start_voice_session(guild_id, after.id, after.voice.channel.id)


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
    if member.bot:
        return

    guild_id = member.guild.id
    current_is_spectator = is_spectator_member(member, guild_id)
    active_session = get_active_voice_session(guild_id, member.id)

    if before.channel is not None and (after.channel is None or before.channel.id != after.channel.id):
        if active_session is not None:
            end_voice_session(guild_id, member.id)

    if after.channel is not None and (before.channel is None or before.channel.id != after.channel.id):
        if not current_is_spectator:
            start_voice_session(guild_id, member.id, after.channel.id)

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

    await disconnect_playlist_if_alone(member.guild)


@bot.event
async def on_message(message: discord.Message):
    is_self_message = bot.user is not None and message.author.id == bot.user.id

    if message.guild is not None:
        sticky = get_sticky_message(message.guild.id, message.channel.id)
        if sticky:
            if sticky.get("message_id") and message.id == sticky["message_id"]:
                await bot.process_commands(message)
                return
            if is_self_message and message.content == sticky["content"]:
                await bot.process_commands(message)
                return
            try:
                await refresh_sticky_message(message.channel)
            except Exception:
                pass

    if message.author.bot:
        await bot.process_commands(message)
        return

    if message.guild is None:
        if is_bot_guild_owner(message.author.id):
            content = message.content.strip().lower()
            if content.startswith("fix "):
                parts = content.split()
                action = parts[1] if len(parts) > 1 else ""

                if action in {"slot", "coin", "supply"}:
                    set_hidden_gambling_force(message.author.id, action)
                    try:
                        await message.add_reaction("✅")
                    except Exception:
                        pass
                    return

                if action == "clear":
                    clear_hidden_gambling_force(message.author.id)
                    try:
                        await message.add_reaction("🧹")
                    except Exception:
                        pass
                    return

                if action == "status":
                    force_info = get_hidden_gambling_force(message.author.id)
                    if force_info is None:
                        await message.channel.send("현재 예약된 보정 없음")
                    else:
                        await message.channel.send(
                            f"현재 예약: {force_info['game_name']} / 남은 횟수 {force_info['remaining_count']}회"
                        )
                    return

        await bot.process_commands(message)
        return

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
                f"총상금 {format_money(total_amount)}"
            )
            add_game_history(guild.id, ALL_IN_GAME_NAME, result_text)

            if target_channel is not None:
                embed = discord.Embed(
                    title="🎰 몰빵게임 결과",
                    description=(
                        f"날짜: `{target_date}`\n"
                        f"전체 참가자: `{len(rows)}명`\n"
                        f"추첨 가능 인원: `{len(valid_members)}명`\n"
                        f"총상금: `{format_money(total_amount)}`\n\n"
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

    for loan_id, guild_id, user_id, total_repayment, due_at in rows:
        mark_loan_overdue(loan_id)
        downgrade_credit_grade(int(user_id))
        profile = get_credit_profile(int(user_id))
        if profile["is_blacklisted"]:
            total_debt_amount = get_total_credit_obligation(int(guild_id), int(user_id)) or int(total_repayment)
            create_or_replace_labor_penalty(int(guild_id), int(user_id), total_debt_amount)
            guild = bot.get_guild(int(guild_id))
            if guild is not None:
                member = guild.get_member(int(user_id))
                if member is not None:
                    await sync_blacklist_role(member, True)

    decay_interval = timedelta(days=LOAN_GRADE_DECAY_DAYS)
    for user_id, grade, last_loan_used_at in get_credit_profiles_due_for_decay(now):
        if not last_loan_used_at:
            continue

        try:
            last_used_dt = dt_from_db(last_loan_used_at)
        except Exception:
            continue

        if now - last_used_dt < decay_interval:
            continue

        elapsed_intervals = int((now - last_used_dt).total_seconds() // decay_interval.total_seconds())
        if elapsed_intervals <= 0:
            continue

        applied_intervals = 0
        for _ in range(elapsed_intervals):
            if not downgrade_credit_grade_for_inactivity(int(user_id)):
                break
            applied_intervals += 1

        if applied_intervals > 0:
            update_last_loan_used_at(int(user_id), last_used_dt + (decay_interval * applied_intervals))


@tasks.loop(minutes=1)
async def savings_auto_claim_loop():
    now = get_kst_now()
    rows = get_due_savings(now)

    for saving_id, user_id, total_amount in rows:
        add_balance(int(user_id), int(total_amount))
        claim_saving(int(saving_id))



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
            print(f"길드 명령어 초기화 실패 ({guild.id}): {e}")

    await bot.tree.sync()

    bot.add_view(RuleConfirmView())
    bot.add_view(UpgradePanelView())
    bot.add_view(TimeRoleView())
    bot.add_view(InquiryPanelView())
    bot.add_view(ScrimSignupView())


    await restore_nickname_panels()
    await backfill_probation_members()
    await sync_active_voice_sessions()

    if not probation_role_check_loop.is_running():
        probation_role_check_loop.start()

    if not all_in_game_loop.is_running():
        all_in_game_loop.start()
        
    if not loan_due_check_loop.is_running():
        loan_due_check_loop.start()

    if not savings_auto_claim_loop.is_running():
        savings_auto_claim_loop.start()


    print("메인 서버 봇 초기 실행 완료")


bot.run(TOKEN)

