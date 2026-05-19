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
ROULETTE_TIMEOUT = 60
SEOTDA_TIMEOUT = 60
