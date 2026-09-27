"""Daily KST chicken proof bonuses; the shared SQLite connection is event-loop owned."""
import asyncio
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')
GUILD_ID = 1377672440276058214
CHANNEL_ID = 1396872061124608120
AMOUNT = 1_000_000
MANUAL_MARKER = '🍗 치킨 성과급 지급 완료'
log = logging.getLogger(__name__)


class ChickenBonus:
    def __init__(self, bot, connection):
        self.bot = bot
        self.db = connection
        self.lock = asyncio.Lock()
        self.guild_id = GUILD_ID
        self.channel_id = CHANNEL_ID
        self.active_from = None

    def initialize(self, now=None):
        """Persist first installation day; never infer a historical backfill window."""
        today = (now or datetime.now(KST)).astimezone(KST).date().isoformat()
        if self.db.in_transaction:
            raise RuntimeError('Chicken bonus cannot join an unrelated transaction')
        with self.db:
            self.db.execute('''CREATE TABLE IF NOT EXISTS chicken_bonus_state (
                channel_id TEXT PRIMARY KEY, initialized_day TEXT NOT NULL,
                next_day TEXT NOT NULL)''')
            self.db.execute('''CREATE TABLE IF NOT EXISTS chicken_bonus_payouts (
                channel_id TEXT NOT NULL, message_id TEXT NOT NULL, user_id TEXT NOT NULL,
                proof_day TEXT NOT NULL, amount INTEGER NOT NULL, paid_at TEXT NOT NULL,
                PRIMARY KEY(channel_id, message_id, user_id))''')
            self.db.execute('INSERT OR IGNORE INTO chicken_bonus_state VALUES (?, ?, ?)',
                            (str(CHANNEL_ID), today, today))
            self.db.execute('''CREATE TABLE IF NOT EXISTS chicken_bonus_config (
                guild_id TEXT PRIMARY KEY, channel_id TEXT NOT NULL, active_from TEXT NOT NULL,
                pending_channel TEXT, effective_at TEXT)''')
            self.db.execute('INSERT OR IGNORE INTO chicken_bonus_config(guild_id,channel_id,active_from) VALUES (?, ?, ?)',
                (str(GUILD_ID), str(CHANNEL_ID), today+'T00:00:00+09:00'))

    async def configure(self, guild_id, channel_id, now=None):
        now = (now or datetime.now(KST)).astimezone(KST)
        async with self.lock:
            self.initialize(now)
            row = self.db.execute('SELECT guild_id,channel_id,active_from,pending_channel,effective_at FROM chicken_bonus_config WHERE guild_id=?', (str(guild_id),)).fetchone()
            if row and row[4] and datetime.fromisoformat(row[4]) <= now:
                # Honor an already-effective reservation before accepting another change.
                await self._process_config(row, now)
            current = self.db.execute('SELECT channel_id FROM chicken_bonus_config WHERE guild_id=?',
                                      (str(guild_id),)).fetchone()
            if current and current[0] == str(channel_id):
                with self.db:
                    self.db.execute('UPDATE chicken_bonus_config SET pending_channel=NULL,effective_at=NULL WHERE guild_id=?', (str(guild_id),))
                return
            with self.db:
                if current:
                    effective = datetime.combine(now.date()+timedelta(days=1), time.min, KST)
                    self.db.execute('UPDATE chicken_bonus_config SET pending_channel=?,effective_at=? WHERE guild_id=?',
                                    (str(channel_id), effective.isoformat(), str(guild_id)))
                    return effective
                self.db.execute('''INSERT INTO chicken_bonus_config(guild_id,channel_id,active_from)
                    VALUES (?, ?, ?)''', (str(guild_id), str(channel_id), now.isoformat()))
                self.db.execute('''INSERT INTO chicken_bonus_state VALUES (?, ?, ?)
                    ON CONFLICT(channel_id) DO UPDATE SET next_day=excluded.next_day''',
                    (str(channel_id), now.date().isoformat(), now.date().isoformat()))
            return now

    async def run_due(self, now=None):
        async with self.lock:
            now = (now or datetime.now(KST)).astimezone(KST)
            self.initialize(now)
            configs = self.db.execute('SELECT guild_id, channel_id, active_from,pending_channel,effective_at FROM chicken_bonus_config').fetchall()
            failures = []
            for row in configs:
                try:
                    await self._process_config(row, now)
                except Exception as exc:
                    log.warning('Chicken bonus guild %s failed: %s', row[0], exc)
                    failures.append(exc)
            if failures:
                raise failures[0]

    async def _process_config(self, row, now):
        guild_id, channel_id, active_from, pending, effective_at = row
        self.guild_id, self.channel_id = int(guild_id), int(channel_id)
        self.active_from = datetime.fromisoformat(active_from)
        effective = datetime.fromisoformat(effective_at) if effective_at else None
        await self._run_channel(min(now, effective) if effective else now)
        if pending and now >= effective:
            with self.db:
                self.db.execute('UPDATE chicken_bonus_config SET channel_id=?,active_from=?,pending_channel=NULL,effective_at=NULL WHERE guild_id=?',
                    (pending, effective_at, guild_id))
                self.db.execute('''INSERT INTO chicken_bonus_state VALUES (?, ?, ?)
                    ON CONFLICT(channel_id) DO UPDATE SET next_day=excluded.next_day''',
                    (pending,effective.date().isoformat(),effective.date().isoformat()))
            self.channel_id, self.active_from = int(pending), effective
            await self._run_channel(now)

    async def _run_channel(self, now):
        while True:
            day = self.db.execute('SELECT next_day FROM chicken_bonus_state WHERE channel_id=?',
                                  (str(self.channel_id),)).fetchone()[0]
            start = datetime.combine(datetime.fromisoformat(day).date(), time.min, KST)
            end = start + timedelta(days=1)
            if end > now:
                return
            await self.pay_day(start, end, now)
            if self.db.in_transaction:
                raise RuntimeError('Chicken bonus cannot join an unrelated transaction')
            with self.db:
                self.db.execute('UPDATE chicken_bonus_state SET next_day=? WHERE channel_id=?',
                                (end.date().isoformat(), str(self.channel_id)))

    async def pay_day(self, start, end, now):
        guild = self.bot.get_guild(self.guild_id)
        if guild is None or self.bot.user is None:
            raise RuntimeError('Chicken bonus guild/bot unavailable')
        channel = self.bot.get_channel(self.channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(self.channel_id)
        if channel.guild.id != self.guild_id or channel.id != self.channel_id:
            raise RuntimeError('Chicken bonus channel belongs to another guild')
        # Discord history's after boundary is exclusive; filter explicitly for [start, end).
        messages = [m async for m in channel.history(limit=None, oldest_first=True,
                    after=start-timedelta(seconds=1), before=end)
                    if start <= m.created_at < end]
        marker = max((m.id for m in messages if m.author.id == self.bot.user.id
                      and any(e.title == MANUAL_MARKER for e in m.embeds)), default=0)
        proofs = [m for m in messages if m.created_at >= self.active_from and m.id > marker and not m.author.bot
                  and m.mentions and (m.attachments or m.embeds)]
        # Finish all member requests before writing any payouts for this day.
        members = {}
        for user_id in sorted({u.id for m in proofs for u in m.mentions}):
            member = guild.get_member(user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(user_id)
                except Exception as exc:
                    # A definitive unknown member is ineligible. Other failures retry the day.
                    if getattr(exc, 'status', None) != 404:
                        raise
            members[user_id] = member
        for message in proofs:
            for user_id in sorted({u.id for u in message.mentions}):
                member = members[user_id]
                if member is not None and not member.bot:
                    self.pay_once(message.id, user_id, start.date().isoformat(), now)

    def pay_once(self, message_id, user_id, day, now):
        # No await in this transaction: ledger, balance, and grant log commit together.
        if self.db.in_transaction:
            raise RuntimeError('Chicken bonus cannot join an unrelated transaction')
        with self.db:
            inserted = self.db.execute('INSERT OR IGNORE INTO chicken_bonus_payouts VALUES (?, ?, ?, ?, ?, ?)',
                (str(self.channel_id), str(message_id), str(user_id), day, AMOUNT, now.isoformat()))
            if inserted.rowcount == 0:
                return
            self.db.execute('''INSERT INTO balances(user_id, balance) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET balance=balance+excluded.balance''',
                (str(user_id), AMOUNT))
            self.db.execute('''INSERT INTO money_grant_logs
                (guild_id, target_user_id, giver_user_id, amount, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)''',
                (str(self.guild_id), str(user_id), str(self.bot.user.id), AMOUNT,
                 f'치킨 자동 성과급 / {day} / 인증 {message_id}', now.isoformat()))

    async def run(self):
        while not self.bot.is_closed():
            try:
                await self.bot.wait_until_ready()
                await self.run_due()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception('Chicken bonus failed; retrying without advancing failed day')
            now = datetime.now(KST)
            midnight = datetime.combine(now.date()+timedelta(days=1), time.min, KST)
            await asyncio.sleep(min(60, max(0.1, (midnight-now).total_seconds())))


def install(bot, connection):
    """Called from on_ready; reconnects reuse the existing task."""
    existing = getattr(bot, '_mari_chicken_bonus_task', None)
    if existing is not None and not existing.done():
        return existing
    service = ChickenBonus(bot, connection)
    service.initialize()
    bot._mari_chicken_bonus_service = service
    task = asyncio.create_task(service.run(), name='mari-chicken-bonus')
    bot._mari_chicken_bonus_task = task
    return task
