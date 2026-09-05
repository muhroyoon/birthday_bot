"""Maribot web companion. Runs inside the existing Discord bot event loop.
No bot token, production database copy, or separate balance ledger is required.
"""
from __future__ import annotations
import asyncio
import base64
from contextvars import ContextVar
import hashlib
import inspect
import json
import logging
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any
from aiohttp import web, ClientSession, ClientTimeout
import discord

log = logging.getLogger("maribot.web")
KST = ZoneInfo("Asia/Seoul")
GAME_FUNCTIONS = {
    "slot": "slot", "coin": "coin", "baccarat": "baccarat",
    "blackjack": "blackjack", "horse_race": "horse_race",
    "rock_paper_scissors": "rock_paper_scissors", "number_baseball": "number_baseball",
    "minesweeper": "minesweeper", "supply_drop": "supply_drop",
    "duckmong": "duckmong", "seotda": "seotda", "all_in": "join_all_in_game",
}

class WebError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status

def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def integer(value: Any, minimum=1, maximum=9_000_000_000_000) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise WebError("올바른 정수 값을 입력해주세요.")
    return value

@dataclass
class Capture:
    id: str
    game: str
    uid: int
    gid: int
    balance_before: int
    owner: Any
    revision: int = 0
    busy: bool = True
    content: str = ""
    embeds: list = field(default_factory=list)
    view: Any = None
    image: str | None = None
    notice: str = ""
    timer: asyncio.Task | None = None
    timeout_at: float = 0
    logged: bool = False
    net_delta: int = 0
    slot_symbols: list = field(default_factory=list)

    @property
    def done(self):
        return not self.busy and (
            self.view is None or getattr(self.view, "resolved", False)
            or type(self.view).__name__ == "SeotdaResultView"
            or self.view.is_finished()
            or all(getattr(c, "disabled", False) for c in self.view.children)
        )

    async def edit(self, **kw):
        self.update(kw)
        return self

    def update(self, kw):
        if "content" in kw:
            self.content = kw["content"] or ""
        if "embed" in kw:
            self.embeds = [kw["embed"]] if kw["embed"] else []
        if "embeds" in kw:
            self.embeds = kw["embeds"] or []
        if "view" in kw:
            self.view = kw["view"]
            if self.view is not None:
                self.view.message = self
        files = kw.get("attachments", kw.get("files", [kw["file"]] if kw.get("file") else None))
        if files is not None:
            self.image = None
            for f in files:
                if isinstance(f, discord.File):
                    pos = f.fp.tell()
                    f.fp.seek(0)
                    data = f.fp.read(2_000_001)
                    f.fp.seek(pos)
                    if len(data) <= 2_000_000 and data.startswith(b"\x89PNG\r\n\x1a\n"):
                        self.image = "data:image/png;base64," + base64.b64encode(data).decode()
                        break
        self.revision += 1

    def snapshot(self):
        embed = self.embeds[0].to_dict() if self.embeds else {}
        controls = []
        if self.view and not self.done:
            for child in self.view.children:
                options = None
                if isinstance(child, discord.ui.Select):
                    options = [{"label": o.label, "value": o.value} for o in child.options]
                controls.append({
                    "id": child.custom_id, "label": getattr(child, "label", None) or getattr(child, "placeholder", None) or "선택",
                    "disabled": bool(getattr(child, "disabled", False)), "row": child.row,
                    "style": int(getattr(child, "style", 2)), "options": options,
                })
        motion = {}
        if self.done and self.game == "slot" and len(self.slot_symbols) == 3:
            motion["symbols"] = list(self.slot_symbols)
        if self.done and self.game == "coin":
            match = re.search(r"결과:\s*\*\*(앞|뒤)\*\*", embed.get("description", ""))
            if match:
                motion["coin"] = match.group(1)
        return {"id": self.id, "game": self.game, "revision": self.revision,
                "done": self.done, "busy": self.busy, "title": embed.get("title", "마리봇"),
                "description": embed.get("description", self.content),
                "fields": embed.get("fields", []), "image": self.image,
                "controls": controls, "notice": self.notice, "motion": motion}

class ResponseAdapter:
    def __init__(self, capture):
        self.capture = capture
        self.responded = False

    def is_done(self):
        return self.responded

    async def defer(self, **kw):
        self.responded = True

    async def send_message(self, content=None, **kw):
        self.responded = True
        if kw.get("ephemeral") and self.capture.embeds:
            self.capture.notice = content or (kw.get("embed").description if kw.get("embed") else "")
        else:
            self.capture.update({**kw, **({"content": content} if content is not None else {})})
        return self.capture

    async def edit_message(self, **kw):
        self.responded = True
        self.capture.update(kw)
        return self.capture

    async def send(self, content=None, **kw):
        return await self.send_message(content, **kw)

    async def send_modal(self, modal):
        raise WebError("이 입력은 현재 디스코드에서 진행해주세요.", 409)

class InteractionAdapter:
    def __init__(self, bot, member, capture):
        self.client = bot
        self.user = member
        self.guild = member.guild
        self.guild_id = member.guild.id
        self.message = capture
        self.response = ResponseAdapter(capture)
        self.followup = self.response
        self.data = {}
        self.channel = None
        self.channel_id = None

    async def original_response(self):
        return self.message

    async def edit_original_response(self, **kw):
        return await self.message.edit(**kw)

class Bridge:
    def __init__(self, namespace, secret: str, guild_ids: set[int]):
        if len(secret) < 32 or not guild_ids:
            raise ValueError("MARIBOT_BRIDGE_SECRET (32+ characters) and MARIBOT_WEB_GUILD_IDS are required")
        self.ns = namespace
        self.bot = namespace["bot"]
        self.db = namespace["conn"]
        self.secret = secret
        self.guild_ids = guild_ids
        self.codes: dict[str, tuple[int, int, float]] = {}
        self.rounds: dict[int, Capture] = {}
        self.lock = asyncio.Lock()
        self.member_sync_lock = asyncio.Lock()
        self.runner = None
        self.recruit_cache = {}
        self.create_schema()
        from mari_web_activities import Activities
        self.activities = Activities(self, WebError)
        self.guild_ids.update(int(row[0]) for row in self.db.execute("SELECT guild_id FROM mari_web_servers"))
        self.delta_context = ContextVar("mari_web_balance_capture", default=None)
        original_add_balance = namespace["add_balance"]
        def tracked_add_balance(uid, amount):
            result = original_add_balance(uid, amount)
            capture = self.delta_context.get()
            if capture is not None and capture.uid == uid:
                capture.net_delta += amount
            return result
        namespace["add_balance"] = tracked_add_balance
        original_slot_image = namespace.get("build_slot_image_file")
        if original_slot_image:
            def tracked_slot_image(symbols, *args, **kwargs):
                result = original_slot_image(symbols, *args, **kwargs)
                capture = self.delta_context.get()
                if capture is not None and capture.game == "slot":
                    capture.slot_symbols = list(symbols)
                return result
            namespace["build_slot_image_file"] = tracked_slot_image

    def create_schema(self):
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS mari_web_chat (
            id INTEGER PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, user_id TEXT NOT NULL,
            guild_id TEXT NOT NULL, name TEXT NOT NULL, avatar TEXT, body TEXT NOT NULL,
            created_at REAL NOT NULL, deleted INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_mari_chat_user_time ON mari_web_chat(user_id,created_at);
        CREATE TABLE IF NOT EXISTS mari_web_servers (
            guild_id TEXT PRIMARY KEY, connected_by TEXT NOT NULL, connected_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mari_web_identities (
            token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, guild_ids TEXT NOT NULL, expires_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mari_web_profiles (
            user_id TEXT PRIMARY KEY, guild_id TEXT NOT NULL, name TEXT NOT NULL,
            username TEXT NOT NULL, avatar TEXT, linked_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_mari_web_profile_guild ON mari_web_profiles(guild_id);
        CREATE TABLE IF NOT EXISTS mari_web_sessions (
            token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, guild_id TEXT NOT NULL, expires_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mari_web_requests (
            request_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
            status TEXT NOT NULL, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS mari_web_rounds (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, guild_id TEXT NOT NULL, game TEXT NOT NULL,
            balance_before INTEGER NOT NULL, status TEXT NOT NULL, snapshot TEXT, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_mari_web_round_user ON mari_web_rounds(user_id,status);
        CREATE TABLE IF NOT EXISTS mari_web_history (
            id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, guild_id TEXT NOT NULL,
            name TEXT NOT NULL, detail TEXT NOT NULL, delta INTEGER NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_mari_web_history_user ON mari_web_history(user_id,guild_id,id);
        CREATE TABLE IF NOT EXISTS mari_web_draws (
            raffle_id INTEGER PRIMARY KEY, guild_id TEXT NOT NULL, winner_id TEXT NOT NULL,
            ticket_count INTEGER NOT NULL, selected_ticket INTEGER NOT NULL,
            participant_snapshot TEXT NOT NULL, drawn_by TEXT NOT NULL, drawn_at TEXT NOT NULL
        );
        """)
        self.db.execute("PRAGMA optimize")
        self.db.commit()

    def issue_code(self, uid, gid):
        now = time.time()
        self.codes = {k: v for k, v in self.codes.items() if v[2] > now and v[:2] != (uid, gid)}
        code = secrets.token_urlsafe(18)
        self.codes[digest(code)] = (uid, gid, now + 300)
        return code

    async def member(self, uid, gid, fresh=False):
        if gid not in self.guild_ids:
            raise WebError("허용되지 않은 디스코드 서버입니다.", 403)
        guild = self.bot.get_guild(gid)
        if not guild:
            raise WebError("마리봇의 서버 연결을 확인해주세요.", 503)
        member = None if fresh else guild.get_member(uid)
        if member is None:
            try:
                member = await guild.fetch_member(uid)
            except discord.HTTPException:
                raise WebError("서버 멤버만 이용할 수 있어요.", 403)
        return member

    def session(self, token):
        if not isinstance(token, str) or len(token) > 128:
            raise WebError("계정을 다시 연결해주세요.", 401)
        row = self.db.execute(
            "SELECT user_id,guild_id FROM mari_web_sessions WHERE token_hash=? AND expires_at>?",
            (digest(token), time.time())).fetchone()
        if not row:
            raise WebError("연결 시간이 만료됐어요. 계정을 다시 연결해주세요.", 401)
        return int(row[0]), int(row[1])

    def log_history(self, uid, gid, name, detail, delta):
        self.db.execute("INSERT INTO mari_web_history(user_id,guild_id,name,detail,delta,created_at) VALUES(?,?,?,?,?,?)",
                        (str(uid), str(gid), name, detail, delta, datetime.now(KST).isoformat()))

    def linked_profile(self, member):
        self.db.execute("""INSERT INTO mari_web_profiles(user_id,guild_id,name,username,avatar,linked_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
            guild_id=excluded.guild_id,name=excluded.name,username=excluded.username,
            avatar=excluded.avatar,linked_at=excluded.linked_at""",
            (str(member.id),str(member.guild.id),member.display_name,member.name,
             str(member.display_avatar.url),datetime.now(KST).isoformat()))

    def guild_info(self, guild):
        icon = getattr(guild, "icon", None)
        return {"id": str(guild.id), "name": getattr(guild, "name", str(guild.id)),
                "icon": str(icon.url) if icon else None}

    async def ensure_server_members(self, guild_ids=None):
        # Discord's member cache is maintained by join/remove/update events.
        # Initial chunking also covers members who have never visited the website.
        async with self.member_sync_lock:
            for gid in sorted(self.guild_ids if guild_ids is None else guild_ids):
                guild = self.bot.get_guild(gid)
                if guild is None or guild.chunked:
                    continue
                try:
                    await asyncio.wait_for(guild.chunk(cache=True), timeout=20)
                except (discord.HTTPException, discord.ClientException, asyncio.TimeoutError):
                    raise WebError("서버 멤버 데이터를 불러오는 중이에요. 잠시 후 다시 시도해주세요.", 503)
                if not guild.chunked:
                    raise WebError("서버 멤버 동기화가 완료되지 않았어요. 잠시 후 다시 시도해주세요.", 503)

    def leaderboard(self, uid):
        # Balances belong to Discord users globally. Count a user once across
        # connected servers; web profiles only select a preferred display server.
        preferred = dict(self.db.execute("SELECT user_id,guild_id FROM mari_web_profiles"))
        members = {}
        for gid in sorted(self.guild_ids):
            guild = self.bot.get_guild(gid)
            if guild is None:
                continue
            for member in guild.members:
                if member.bot:
                    continue
                key = str(member.id)
                if key not in members or preferred.get(key) == str(gid):
                    members[key] = member
        rows = self.db.execute("SELECT user_id,balance FROM balances ORDER BY balance DESC,user_id ASC")
        entries, mine, total = [], None, 0
        for user_id, balance in rows:
            member = members.get(str(user_id))
            if member is None:
                continue
            total += 1
            if total > 100 and str(user_id) != str(uid):
                continue
            item = {"userId": str(user_id), "name": member.display_name,
                    "username": member.name, "avatar": str(member.display_avatar.url),
                    "balance": balance, "rank": total, "guild": self.guild_info(member.guild)}
            if total <= 100:
                entries.append(item)
            if str(user_id) == str(uid):
                mine = item
        return {"entries": entries, "mine": mine, "total": total}

    def account(self, member):
        uid, gid = member.id, member.guild.id
        rows = self.db.execute("""
            SELECT r.id,r.title,r.price,r.daily_limit,r.status,d.winner_id
            FROM raffle_tickets r LEFT JOIN mari_web_draws d ON r.id=d.raffle_id
            WHERE r.guild_id=? AND (r.status='active' OR d.raffle_id IS NOT NULL)
            ORDER BY r.id DESC
        """, (str(gid),)).fetchall()
        raffles = []
        for rid, title, price, limit, status, winner in rows:
            owned = self.db.execute(
                "SELECT COALESCE(SUM(quantity),0) FROM raffle_purchases WHERE raffle_id=? AND guild_id=? AND user_id=?",
                (rid, str(gid), str(uid))).fetchone()[0]
            winner_member = member.guild.get_member(int(winner)) if winner else None
            raffles.append({"id": rid, "title": title, "price": price, "limit": limit, "owned": owned,
                           "purchasedToday": self.ns["get_raffle_purchase_count_today"](rid, gid, uid),
                           "drawn": winner is not None, "winner": winner_member.display_name if winner_member else winner,
                           "guild": self.guild_info(member.guild)})
        records = self.db.execute(
            "SELECT id,name,detail,delta,created_at FROM mari_web_history WHERE user_id=? AND guild_id=? ORDER BY id DESC LIMIT 100",
            (str(uid), str(gid))).fetchall()
        capture = self.rounds.get(uid)
        public_round = capture.snapshot() if capture and capture.gid == gid else None
        if public_round is None:
            last = self.db.execute(
                "SELECT snapshot,status FROM mari_web_rounds WHERE user_id=? AND guild_id=? ORDER BY created_at DESC LIMIT 1",
                (str(uid), str(gid))).fetchone()
            if last and last[0]:
                public_round = json.loads(last[0])
                if last[1] != "done":
                    public_round.update(done=True, controls=[], notice="봇 재시작으로 중단된 게임입니다. 관리자에게 정산 확인을 요청해주세요.")
        return {"user": {"id":str(uid),"name": member.display_name,"username":member.name, "avatar": str(member.display_avatar.url)},
                "guild":self.guild_info(member.guild),"leaderboard":self.leaderboard(uid),
                "balance": self.ns["get_balance"](uid), "admin": member.guild_permissions.administrator,
                "raffles": raffles, "round": public_round,
                "history": [{"id": str(r[0]), "name": r[1], "detail": r[2], "delta": r[3], "at": r[4]} for r in records]}

    def save_capture(self, capture):
        snapshot = capture.snapshot()
        # Keep private game state and image bytes out of the persistent public receipt.
        stored = {**snapshot, "image": None}
        status = "done" if capture.done else "active"
        self.db.execute("UPDATE mari_web_rounds SET status=?,snapshot=? WHERE id=?",
                        (status, json.dumps(stored, ensure_ascii=False), capture.id))
        if capture.done and not capture.logged:
            capture.logged = True
            self.log_history(capture.uid, capture.gid, self.ns["CASINO_GAMES"][capture.game]["name"],
                             snapshot["title"] + " · " + snapshot["description"][:400], capture.net_delta)
        self.db.commit()

    def schedule_timeout(self, capture):
        if capture.timer:
            capture.timer.cancel()
        if capture.done or capture.view is None:
            return
        capture.timeout_at = time.monotonic() + float(capture.view.timeout or 120)
        capture.timer = asyncio.create_task(self.expire(capture))

    async def expire(self, capture):
        try:
            await asyncio.sleep(max(0, capture.timeout_at - time.monotonic()))
            async with self.lock:
                if capture.done:
                    return
                capture.busy = True
                context_token = self.delta_context.set(capture)
                try:
                    await capture.view.on_timeout()
                finally:
                    self.delta_context.reset(context_token)
                capture.view.stop()
                capture.busy = False
                capture.revision += 1
                capture.notice = "제한 시간이 지나 기존 마리봇 규칙으로 자동 처리됐어요."
                self.save_capture(capture)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Web game timeout needs reconciliation: %s", capture.id)
            capture.busy = False
            capture.notice = "자동 처리 중 문제가 발생했어요. 관리자에게 정산 확인을 요청해주세요."

    def buy_raffle(self, member, data, request_id):
        rid, qty = integer(data.get("id")), integer(data.get("quantity"), 1, 10000)
        uid, gid = member.id, member.guild.id
        now = datetime.now(KST)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        to_db = self.ns["dt_to_db"]
        try:
            self.db.execute("BEGIN IMMEDIATE")
            raffle = self.db.execute("SELECT title,price,daily_limit FROM raffle_tickets WHERE id=? AND guild_id=? AND status='active'",
                                     (rid, str(gid))).fetchone()
            if not raffle:
                raise WebError("추첨이 마감됐거나 존재하지 않아요.")
            if self.db.execute("SELECT 1 FROM mari_web_draws WHERE raffle_id=?", (rid,)).fetchone():
                raise WebError("이미 추첨이 완료됐어요.")
            count = self.db.execute("""
                SELECT COALESCE(SUM(quantity),0) FROM raffle_purchases
                WHERE raffle_id=? AND guild_id=? AND user_id=? AND purchased_at>=? AND purchased_at<?
            """, (rid, str(gid), str(uid), to_db(start), to_db(start + timedelta(days=1)))).fetchone()[0]
            if count + qty > raffle[2]:
                raise WebError("오늘 구매 가능한 수량을 초과했어요.")
            total = integer(raffle[1] * qty)
            changed = self.db.execute("UPDATE balances SET balance=balance-? WHERE user_id=? AND balance>=?",
                                      (total, str(uid), total)).rowcount
            if changed != 1:
                raise WebError("잔액이 부족해요.")
            self.db.execute("""
                INSERT INTO raffle_purchases(raffle_id,guild_id,user_id,quantity,total_amount,purchased_at)
                VALUES(?,?,?,?,?,?)
            """, (rid, str(gid), str(uid), qty, total, to_db(now)))
            self.log_history(uid, gid, raffle[0], str(qty) + "장 구매", -total)
            self.db.execute("UPDATE mari_web_requests SET status='done' WHERE request_id=?", (request_id,))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def draw_raffle(self, member, data, request_id):
        if not member.guild_permissions.administrator:
            raise WebError("서버 관리자만 추첨할 수 있어요.", 403)
        rid, gid = integer(data.get("id")), member.guild.id
        try:
            self.db.execute("BEGIN IMMEDIATE")
            raffle = self.db.execute("SELECT title FROM raffle_tickets WHERE id=? AND guild_id=? AND status='active'",
                                     (rid, str(gid))).fetchone()
            if not raffle:
                raise WebError("추첨이 마감됐거나 존재하지 않아요.")
            rows = self.db.execute("""
                SELECT user_id,SUM(quantity) FROM raffle_purchases WHERE raffle_id=? AND guild_id=?
                GROUP BY user_id ORDER BY user_id
            """, (rid, str(gid))).fetchall()
            total = sum(r[1] for r in rows)
            if total <= 0:
                raise WebError("구매된 추첨권이 없어요.")
            selected = secrets.randbelow(total)
            cursor = selected
            winner = None
            for uid, count in rows:
                if cursor < count:
                    winner = uid
                    break
                cursor -= count
            self.db.execute("""
                INSERT INTO mari_web_draws(raffle_id,guild_id,winner_id,ticket_count,selected_ticket,participant_snapshot,drawn_by,drawn_at)
                VALUES(?,?,?,?,?,?,?,?)
            """, (rid, str(gid), winner, total, selected, json.dumps(rows), str(member.id), datetime.now(KST).isoformat()))
            self.db.execute("UPDATE raffle_tickets SET status='drawn' WHERE id=? AND guild_id=?", (rid, str(gid)))
            self.log_history(member.id, gid, raffle[0], "추첨 완료 · 당첨자 " + str(winner), 0)
            if str(member.id) != str(winner):
                self.log_history(winner, gid, raffle[0], "추첨 당첨 · 상품 수령은 운영진 안내를 확인해주세요.", 0)
            self.db.execute("UPDATE mari_web_requests SET status='done' WHERE request_id=?", (request_id,))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    async def game_action(self, member, action, data):
        uid, gid = member.id, member.guild.id
        if action == "game/start":
            game = data.get("game")
            if game not in GAME_FUNCTIONS:
                raise WebError("지원하지 않는 게임이에요.")
            existing = self.rounds.get(uid)
            if existing and not existing.done:
                raise WebError("진행 중인 게임을 먼저 마무리해주세요.", 409)
            unresolved = self.db.execute("SELECT id FROM mari_web_rounds WHERE user_id=? AND status<>'done' LIMIT 1",
                                         (str(uid),)).fetchone()
            if unresolved:
                raise WebError("중단된 게임의 정산 확인이 필요해요. 관리자에게 문의해주세요.", 409)
            amount = self.ns["NUMBER_BASEBALL_COST"] if game == "number_baseball" else integer(data.get("amount"))
            minimum = self.ns["CASINO_GAMES"][game]["minimum"]
            if amount < minimum:
                raise WebError("최소 " + str(minimum) + "마리 이상 입력해주세요.")
            capture = Capture(secrets.token_urlsafe(18), game, uid, gid, self.ns["get_balance"](uid), self)
            self.rounds[uid] = capture
            self.db.execute("INSERT INTO mari_web_rounds(id,user_id,guild_id,game,balance_before,status,created_at) VALUES(?,?,?,?,?,'active',?)",
                            (capture.id, str(uid), str(gid), game, capture.balance_before, datetime.now(KST).isoformat()))
            self.db.commit()
            interaction = InteractionAdapter(self.bot, member, capture)
            fn = self.ns[GAME_FUNCTIONS[game]]
            fn = getattr(fn, "callback", fn)
            context_token = self.delta_context.set(capture)
            try:
                await fn(interaction, **({} if game == "number_baseball" else {"amount": amount}))
            finally:
                self.delta_context.reset(context_token)
        else:
            capture = self.rounds.get(uid)
            if not capture or capture.gid != gid or capture.id != data.get("roundId") or capture.done:
                raise WebError("진행 중인 게임을 찾을 수 없어요.", 409)
            if capture.revision != data.get("revision"):
                raise WebError("게임 화면이 갱신됐어요. 다시 확인해주세요.", 409)
            interaction = InteractionAdapter(self.bot, member, capture)
            if not await capture.view.interaction_check(interaction):
                raise WebError(capture.notice or "이 게임을 진행할 권한이 없어요.", 403)
            if action == "game/guess":
                if capture.game != "number_baseball":
                    raise WebError("숫자야구에서만 사용할 수 있어요.")
                guess = data.get("guess")
                if not isinstance(guess, str) or len(guess) > 10:
                    raise WebError("서로 다른 숫자 4개를 입력해주세요.")
                capture.busy = True
                context_token = self.delta_context.set(capture)
                try:
                    await capture.view.submit_guess(interaction, guess)
                finally:
                    self.delta_context.reset(context_token)
            elif action == "game/control":
                control = next((c for c in capture.view.children if c.custom_id == data.get("controlId")), None)
                if control is None or getattr(control, "disabled", False):
                    raise WebError("사용할 수 없는 버튼입니다.", 409)
                if isinstance(control, discord.ui.Select):
                    value = data.get("value")
                    if value not in [o.value for o in control.options]:
                        raise WebError("올바른 항목을 선택해주세요.")
                    control._values = [value]
                    interaction.data = {"values": [value]}
                capture.busy = True
                context_token = self.delta_context.set(capture)
                try:
                    await control.callback(interaction)
                finally:
                    self.delta_context.reset(context_token)
            else:
                raise WebError("지원하지 않는 요청이에요.", 404)
        capture.busy = False
        capture.revision += 1
        self.save_capture(capture)
        self.schedule_timeout(capture)

    async def discord_identity(self, access_token):
        if not isinstance(access_token, str) or not 10 <= len(access_token) <= 2048:
            raise WebError("디스코드 로그인을 다시 진행해주세요.", 401)
        async with ClientSession(timeout=ClientTimeout(total=15), headers={"Authorization": "Bearer " + access_token}) as http:
            async with http.get("https://discord.com/api/v10/users/@me") as res:
                if res.status != 200:
                    raise WebError("디스코드 로그인을 다시 진행해주세요.", 401)
                user = await res.json()
            async with http.get("https://discord.com/api/v10/users/@me/guilds?limit=200") as res:
                if res.status != 200:
                    raise WebError("서버 목록을 확인하지 못했어요. 다시 로그인해주세요.", 401)
                guilds = await res.json()
        return int(user["id"]), [int(g["id"]) for g in guilds]

    def identity(self, token):
        if not isinstance(token, str):
            raise WebError("디스코드로 로그인해주세요.", 401)
        row = self.db.execute("SELECT user_id,guild_ids FROM mari_web_identities WHERE token_hash=? AND expires_at>?", (digest(token), time.time())).fetchone()
        if not row:
            raise WebError("로그인이 만료됐어요. 디스코드로 다시 로그인해주세요.", 401)
        return int(row[0]), json.loads(row[1])

    async def server_list(self, uid, candidates):
        servers = []
        for gid in candidates:
            guild = self.bot.get_guild(gid)
            if guild is not None:
                servers.append({**self.guild_info(guild), "connected": gid in self.guild_ids,
                                "owner": guild.owner_id == uid})
        return {"servers": servers}

    async def oauth_action(self, action, token, data):
        if action == "oauth/login":
            uid, candidates = await self.discord_identity(data.get("accessToken"))
            identity = secrets.token_urlsafe(32)
            self.db.execute("DELETE FROM mari_web_identities WHERE expires_at<=?", (time.time(),))
            self.db.execute("INSERT INTO mari_web_identities VALUES(?,?,?,?)", (digest(identity), str(uid), json.dumps(candidates), time.time()+43200))
            self.db.commit()
            return {"identity": identity, **await self.server_list(uid, candidates)}
        uid, candidates = self.identity(token)
        if action == "servers":
            return await self.server_list(uid, candidates)
        if action == "oauth/logout":
            self.db.execute("DELETE FROM mari_web_identities WHERE token_hash=?", (digest(token),))
            self.db.execute("DELETE FROM mari_web_sessions WHERE user_id=?", (str(uid),))
            self.db.commit()
            return {"ok": True}
        try:
            gid = int(data.get("guildId", ""))
        except (ValueError, TypeError):
            raise WebError("이용할 서버를 선택해주세요.")
        guild = self.bot.get_guild(gid)
        if gid not in candidates or guild is None:
            raise WebError("마리봇이 있는 가입 서버만 선택할 수 있어요.", 403)
        try:
            member = await guild.fetch_member(uid)
        except discord.HTTPException:
            raise WebError("현재 서버 멤버만 이용할 수 있어요.", 403)
        if action == "servers/connect":
            if guild.owner_id != uid:
                raise WebError("서버 주인만 서버를 연결할 수 있어요.", 403)
            await self.ensure_server_members({gid})
            self.db.execute("INSERT OR IGNORE INTO mari_web_servers VALUES(?,?,?)", (str(gid), str(uid), time.time()))
            self.db.commit()
            self.guild_ids.add(gid)
            return await self.server_list(uid, candidates)
        if action != "servers/select" or gid not in self.guild_ids:
            raise WebError("서버 주인이 먼저 서버를 연결해야 해요.", 403)
        # A server change must not orphan an unfinished game or an uncertain settlement.
        pending = self.db.execute("SELECT guild_id FROM mari_web_rounds WHERE user_id=? AND status!='done' LIMIT 1", (str(uid),)).fetchone()
        if pending and int(pending[0]) != gid:
            raise WebError("진행 중인 게임을 마무리한 후 서버를 바꿔주세요.", 409)
        session = secrets.token_urlsafe(32)
        self.db.execute("INSERT INTO mari_web_sessions VALUES(?,?,?,?)", (digest(session), str(uid), str(gid), time.time()+43200))
        self.linked_profile(member)
        self.db.commit()
        return {"session": session}

    def server_emojis(self, member):
        roles={r.id for r in getattr(member,'roles',[])}
        return [{"id":str(e.id),"name":e.name,"animated":e.animated,
                 "token":f"<{'a' if e.animated else ''}:{e.name}:{e.id}>","url":str(e.url)}
                for e in getattr(member.guild,'emojis',[]) if e.available and
                (not e.roles or any(r.id in roles for r in e.roles))]

    def chat_messages(self, member):
        ids=[str(gid) for gid in self.guild_ids if self.bot.get_guild(gid)]
        if not ids: return {"messages": []}
        marks=','.join('?' for _ in ids)
        rows=self.db.execute(f"SELECT id,user_id,guild_id,name,avatar,body,created_at FROM mari_web_chat WHERE deleted=0 AND guild_id IN ({marks}) ORDER BY id DESC LIMIT 100",ids).fetchall()
        return {"emojis":self.server_emojis(member),"messages": [{"id":str(r[0]),"userId":r[1],"guild":self.guild_info(self.bot.get_guild(int(r[2]))),
                "name":r[3],"avatar":r[4],"body":r[5],"at":datetime.fromtimestamp(r[6],KST).isoformat(),
                "canDelete":r[1]==str(member.id) or (r[2]==str(member.guild.id) and member.guild_permissions.administrator)} for r in reversed(rows)]}

    def chat_action(self, member, action, data):
        if action=='chat/send':
            body=data.get('body'); rid=data.get('requestId')
            if not isinstance(body,str) or not 1<=len(body.strip())<=500 or any(ord(c)<32 and c not in '\n\t' for c in body):
                raise WebError("메시지는 1~500자로 입력해주세요.")
            if not isinstance(rid,str) or not 16<=len(rid)<=80: raise WebError("요청 번호가 필요해요.")
            previous=self.db.execute('SELECT user_id,body FROM mari_web_chat WHERE request_id=?',(rid,)).fetchone()
            if previous:
                if previous!=(str(member.id),body.strip()): raise WebError("다른 메시지의 요청 번호입니다.",409)
                return self.chat_messages(member)
            allowed={e['token'] for e in self.server_emojis(member)}
            for match in re.finditer(r'<a?:[A-Za-z0-9_]+:[0-9]{1,20}>',body):
                if match.group(0) not in allowed:
                    raise WebError("현재 서버에서 사용할 수 있는 이모지를 선택해주세요.",403)
            now=time.time()
            recent=self.db.execute('SELECT MAX(created_at),COUNT(*) FROM mari_web_chat WHERE user_id=? AND created_at>?',(str(member.id),now-60)).fetchone()
            if recent[0] is not None and (now-recent[0]<3 or recent[1]>=20): raise WebError("메시지를 너무 빠르게 보내고 있어요. 잠시 기다려주세요.",429)
            self.db.execute('INSERT INTO mari_web_chat(request_id,user_id,guild_id,name,avatar,body,created_at) VALUES(?,?,?,?,?,?,?)',
                (rid,str(member.id),str(member.guild.id),member.display_name,str(member.display_avatar.url),body.strip(),now))
        elif action=='chat/delete':
            mid=integer(data.get('id'))
            row=self.db.execute('SELECT user_id,guild_id FROM mari_web_chat WHERE id=?',(mid,)).fetchone()
            if not row or not (row[0]==str(member.id) or (row[1]==str(member.guild.id) and member.guild_permissions.administrator)):
                raise WebError("이 메시지를 삭제할 권한이 없어요.",403)
            self.db.execute('UPDATE mari_web_chat SET deleted=1 WHERE id=?',(mid,))
        else: raise WebError("지원하지 않는 요청입니다.",404)
        self.db.commit()
        return self.chat_messages(member)

    def recruit_is_closed(self, guild, message, embed):
        if '모집 종료' in (embed.title or ''):
            return True
        buttons=[button for row in getattr(message,'components',[]) for button in getattr(row,'children',[])]
        joins=[button for button in buttons if getattr(button,'label',None)=='참여하기']
        if joins and all(getattr(button,'disabled',False) for button in joins):
            return True
        # A historical title is not proof of a live recruitment. The bot owns
        # exactly one active post per voice channel; restart/replacement retires it.
        active=next(((vid,data) for vid,data in self.ns.get('active_recruits',{}).items()
                     if str(data.get('message_id'))==str(message.id) and data.get('text_channel_id')==message.channel.id),None)
        if active is None:
            return True
        vid,data=active
        voice=guild.get_channel(vid)
        if voice is None or not any(m.id==data.get('host_id') for m in voice.members):
            return True
        maximum=data.get('max_players')
        if maximum is not None:
            players,_=self.ns['count_members'](voice)
            if players>=maximum:
                return True
        return False

    async def recruit_posts(self, member):
        # Only scan channels the requesting member can read. Never expose private
        # channel messages through a server-level membership check alone.
        posts=[]
        for cid in self.ns.get('get_recruit_channel_ids',lambda gid:[])(member.guild.id):
            channel=member.guild.get_channel(cid)
            if channel is None: continue
            perms=channel.permissions_for(member)
            if not perms.view_channel or not perms.read_message_history: continue
            cached=self.recruit_cache.get(cid)
            if cached and time.time()-cached[0]<30:
                messages=cached[1]
            else:
                try:
                    messages=[m async for m in channel.history(limit=100)]
                except discord.Forbidden: continue
                except discord.HTTPException: raise WebError("구인 글을 불러오지 못했어요. 잠시 후 다시 시도해주세요.",503)
                self.recruit_cache[cid]=(time.time(),messages)
            for message in messages:
                if message.author.id!=self.bot.user.id: continue
                for embed in message.embeds:
                    title=embed.title or ''
                    if not (title.startswith('🎮 ') and ('모집중!' in title or '모집 종료' in title)): continue
                    closed=self.recruit_is_closed(member.guild,message,embed)
                    display_title=title.replace("모집중!","모집 종료") if closed else title
                    posts.append({"id":str(message.id),"title":display_title,"body":re.sub(r'<@!?(\d+)>', lambda m: "@"+getattr(member.guild.get_member(int(m[1])),"display_name","알 수 없는 멤버"), embed.description or ''),
                        "guild":self.guild_info(member.guild),"channel":channel.name,"url":message.jump_url,
                        "at":message.created_at.isoformat(),"closed":closed})
        posts.sort(key=lambda p:p['id'].zfill(25),reverse=True)
        return {"posts":posts[:100]}

    async def dispatch(self, action, token, data):
        if action in {"oauth/login", "oauth/logout", "servers", "servers/connect", "servers/select"}:
            return await self.oauth_action(action, token, data)
        if action == "claim":
            code = data.get("code")
            if not isinstance(code, str) or not 20 <= len(code) <= 64:
                raise WebError("올바른 연결 코드를 입력해주세요.")
            identity = self.codes.get(digest(code))
            if not identity or identity[2] <= time.time():
                raise WebError("코드가 만료됐거나 이미 사용됐어요. /웹연결로 다시 발급해주세요.", 401)
            uid, gid, _ = identity
            linked_member = await self.member(uid, gid, fresh=True)
            async with self.lock:
                if self.codes.pop(digest(code), None) is None:
                    raise WebError("이미 사용된 코드입니다.", 401)
                session = secrets.token_urlsafe(32)
                self.db.execute("DELETE FROM mari_web_sessions WHERE expires_at<=?", (time.time(),))
                self.db.execute("INSERT INTO mari_web_sessions VALUES(?,?,?,?)",
                                (digest(session), str(uid), str(gid), time.time() + 43200))
                self.linked_profile(linked_member)
                self.db.commit()
            return {"session": session}
        uid, gid = self.session(token)
        member = await self.member(uid, gid, fresh=action not in {"account", "logout"})
        if action == 'kill': return self.activities.listing(member)
        if isinstance(action,str) and action.startswith('kill/'):
            async with self.lock:
                try: return self.activities.mutate(member,action,data)
                except ValueError as exc: raise WebError(str(exc))
        if action == 'notifications': return self.activities.notifications(member)
        if action == 'notifications/read':
            async with self.lock: return self.activities.mark_read(member,data)
        if action == "recruits": return await self.recruit_posts(member)
        if action == "chat": return self.chat_messages(member)
        if action in {"chat/send","chat/delete"}:
            async with self.lock: return self.chat_action(member,action,data)
        if action != "logout":
            await self.ensure_server_members()
        async with self.lock:
            if action == "logout":
                self.db.execute("DELETE FROM mari_web_sessions WHERE token_hash=?", (digest(token),))
                self.db.commit()
                return {"ok": True}
            if action == "account":
                return self.account(member)
            request_id = data.get("requestId")
            if not isinstance(request_id, str) or not 16 <= len(request_id) <= 80:
                raise WebError("요청 번호가 필요해요.")
            fingerprint = digest(json.dumps([action, {k: v for k, v in data.items() if k != "requestId"}], sort_keys=True))
            receipt = self.db.execute("SELECT user_id,fingerprint,status FROM mari_web_requests WHERE request_id=?", (request_id,)).fetchone()
            if receipt:
                if receipt[0] != str(uid) or receipt[1] != fingerprint:
                    raise WebError("요청 번호가 다른 작업에 사용됐어요.", 409)
                if receipt[2] != "done":
                    raise WebError("이전 요청의 처리 확인이 필요해요. 새로고침 후 결과를 확인해주세요.", 409)
                return self.account(member)
            self.db.execute("INSERT INTO mari_web_requests VALUES(?,?,?,'pending',?)",
                            (request_id, str(uid), fingerprint, time.time()))
            self.db.commit()
            try:
                if action == "raffles/buy":
                    self.buy_raffle(member, data, request_id)
                elif action == "raffles/draw":
                    self.draw_raffle(member, data, request_id)
                elif action in {"game/start", "game/control", "game/guess"}:
                    await self.game_action(member, action, data)
                    self.db.execute("UPDATE mari_web_requests SET status='done' WHERE request_id=?", (request_id,))
                    self.db.commit()
                else:
                    raise WebError("지원하지 않는 요청입니다.", 404)
            except WebError:
                # Business-rule rejection may be corrected with a new action.
                self.db.execute("DELETE FROM mari_web_requests WHERE request_id=?", (request_id,))
                self.db.commit()
                raise
            except Exception:
                # Never replay an uncertain operation; the durable pending receipt is retained.
                log.exception("Web operation needs reconciliation: %s", request_id)
                raise WebError("처리 중 문제가 발생했어요. 재시도 전에 관리자에게 정산 확인을 요청해주세요.", 503)
            return self.account(member)

    async def handler(self, request):
        expected = "Bearer " + self.secret
        if not secrets.compare_digest(request.headers.get("Authorization", ""), expected):
            return web.json_response({"error": "Unauthorized"}, status=401)
        try:
            body = await request.json()
            if not isinstance(body, dict) or not isinstance(body.get("data", {}), dict):
                raise WebError("잘못된 요청입니다.")
            result = await self.dispatch(body.get("action"), body.get("session"), body.get("data", {}))
            return web.json_response(result, headers={"Cache-Control": "no-store"})
        except WebError as exc:
            return web.json_response({"error": str(exc)}, status=exc.status)
        except (ValueError, TypeError):
            return web.json_response({"error": "잘못된 요청입니다."}, status=400)
        except Exception:
            log.exception("Bridge request failed")
            return web.json_response({"error": "마리봇 연결을 확인해주세요."}, status=503)

    async def health(self, request):
        ready = self.bot.is_ready()
        return web.json_response({"ready": ready}, status=200 if ready else 503,
                                 headers={"Cache-Control": "no-store"})

    async def start(self):
        if self.runner:
            return
        app = web.Application(client_max_size=16384)
        app.router.add_get("/health", self.health)
        app.router.add_post("/v1", self.handler)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        port = int(os.environ.get("PORT", os.environ.get("MARIBOT_WEB_PORT", "8080")))
        await web.TCPSite(self.runner, "0.0.0.0", port).start()
        log.info("Maribot web bridge started on port %s", port)

def install(namespace):
    """Call before bot.run, only when MARIBOT_WEB_ENABLED=1."""
    secret = os.environ.get("MARIBOT_BRIDGE_SECRET", "")
    guild_ids = {int(v.strip()) for v in os.environ.get("MARIBOT_WEB_GUILD_IDS", "").split(",") if v.strip()}
    bridge = Bridge(namespace, secret, guild_ids)
    bot = namespace["bot"]

    @bot.tree.command(name="웹연결", description="마리봇 웹사이트에서 디스코드로 로그인합니다.")
    async def web_link(interaction: discord.Interaction):
        await interaction.response.send_message(
            "https://maribot.co.kr\n"
            "디스코드로 로그인하면 기존 잔액과 추첨권을 이용할 수 있어요.\n"
            "서버 주인이 한 번 서버를 연결하면 멤버는 별도 코드 없이 이용해요.",
            ephemeral=True,
        )

    bot.add_listener(bridge.start, "on_ready")
    namespace["mari_web_bridge"] = bridge
    return bridge

