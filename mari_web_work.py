"""Account-wide 20-second rhythm work with server judged replay and atomic payout."""
import hashlib
import re
import secrets
import time
from datetime import datetime, timezone, timedelta

DURATION = 20_000
WINDOW = 180
DAILY_JOBS = 30
REWARDS = [('일반', 70, 1000000), ('희귀', 25, 3000000), ('영웅', 4, 5000000), ('전설', 1, 10000000)]
KST = timezone(timedelta(hours=9))

def chart(seed, version=2):
    """Slow introductory notes become denser; directions remain reproducible."""
    notes = []
    at = 1800
    while at <= DURATION - 500:
        direction = hashlib.sha256(f'{seed}:{len(notes)}'.encode()).digest()[0] % 4
        notes.append({'t': at, 'key': 'wasd'[direction]})
        at += max(450, 1200 - len(notes) * 38) if version == 1 else max(350, 1050 - len(notes) * 42)
    return notes

def minimum(total, version=2):
    return (total+1)//2 if version == 1 else (total*65+99)//100

class Work:
    def __init__(self, bridge, error):
        self.b=bridge; self.db=bridge.db; self.Error=error
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS mari_web_work_jobs(
          id TEXT PRIMARY KEY,user_id TEXT NOT NULL,guild_id TEXT NOT NULL,
          clicks INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL,last_click REAL NOT NULL,
          finished_day TEXT, reward INTEGER NOT NULL DEFAULT 0, tier TEXT);
        CREATE INDEX IF NOT EXISTS idx_work_user_day ON mari_web_work_jobs(user_id,finished_day);
        ''')
        columns = {r[1] for r in self.db.execute('PRAGMA table_info(mari_web_work_jobs)')}
        for name, definition in [('version','INTEGER NOT NULL DEFAULT 0'), ('seed','TEXT'), ('ended','REAL')]:
            if name not in columns:
                self.db.execute(f'ALTER TABLE mari_web_work_jobs ADD COLUMN {name} {definition}')
        # Historical paid jobs remain counted. Unfinished click jobs upgrade on explicit start.
        if 'ended' not in columns:
            self.db.execute('UPDATE mari_web_work_jobs SET ended=last_click WHERE finished_day IS NOT NULL')
        index=self.db.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_work_one_active'").fetchone()
        if index and 'finished_day' in index[0].lower():
            self.db.execute('DROP INDEX idx_work_one_active')
        self.db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_work_one_active ON mari_web_work_jobs(user_id) WHERE ended IS NULL')
        self.db.commit()

    def today(self):return datetime.now(KST).date().isoformat()
    def completed(self, uid):
        return self.db.execute('SELECT COUNT(*),COALESCE(SUM(reward),0) FROM mari_web_work_jobs WHERE user_id=? AND finished_day=?',(str(uid),self.today())).fetchone()

    def status(self, member):
        done,earned=self.completed(member.id)
        row=self.db.execute('SELECT id,clicks,finished_day,reward,tier,version,seed,created,ended FROM mari_web_work_jobs WHERE user_id=? ORDER BY rowid DESC LIMIT 1',(str(member.id),)).fetchone()
        version=row[5] if row else 2
        notes=chart(row[6],version) if row and version in (1,2) else []
        job=None if not row else {'id':row[0], 'clicks':row[1], 'hits':row[1], 'done':row[8] is not None,
            'success':row[2] is not None, 'reward':row[3], 'tier':row[4], 'legacy':row[5] not in (1,2),
            'notes':notes, 'elapsed':max(0,round((time.time()-row[7])*1000))}
        return {'required':len(notes), 'duration':DURATION, 'window':230 if version==1 else WINDOW, 'minimum':minimum(len(notes),version),
                'dailyLimit':DAILY_JOBS,'completed':done,'earned':earned,'day':self.today(),
                'balance':self.b.ns['get_balance'](member.id),'rewards':[{'tier':t,'chance':c,'amount':a} for t,c,a in REWARDS], 'job':job}

    def judge(self, events, seed, elapsed, version=2):
        if not isinstance(events,list) or len(events)>100:
            raise self.Error('입력 기록을 확인해주세요.')
        notes=chart(seed,version); matched=set();previous=-80
        window=230 if version==1 else WINDOW
        for event in events:
            if not isinstance(event,dict):raise self.Error('입력 기록을 확인해주세요.')
            at=event.get('t');key=event.get('key')
            if type(at) is not int or not isinstance(key,str) or key not in ('w','a','s','d') or not 0<=at<=DURATION or at>elapsed+100 or at-previous<80:
                raise self.Error('입력 시간이나 방향을 확인해주세요.')
            previous=at
            candidates=[(abs(note['t']-at),i) for i,note in enumerate(notes) if i not in matched and note['key']==key and abs(note['t']-at)<=window]
            if candidates:matched.add(min(candidates)[1] if version==1 else min(i for _,i in candidates))
        return len(matched),len(notes)

    def mutate(self, member, action, data):
        uid=str(member.id);gid=str(member.guild.id)
        if data.get('expectedUser')!=uid or data.get('expectedGuild')!=gid:
            raise self.Error('계정이나 서버가 바뀌었어요. 새로고침해주세요.',409)
        job_id=data.get('id')
        if not isinstance(job_id,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,80}',job_id):raise self.Error('작업 번호를 확인해주세요.')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT user_id,clicks,created,ended,version,seed,guild_id FROM mari_web_work_jobs WHERE id=?',(job_id,)).fetchone()
            if row and (row[0]!=uid or row[6]!=gid):raise self.Error('이 계정과 서버의 작업이 아닙니다.',403)
            if action=='work/start':
                if row and row[4] in (1,2):
                    self.db.commit();return self.status(member)
                active=self.db.execute('SELECT id,version,guild_id FROM mari_web_work_jobs WHERE user_id=? AND ended IS NULL',(uid,)).fetchone()
                if active and active[2]!=gid:raise self.Error('작업을 시작한 서버로 돌아가주세요.',409)
                if active and active[1] in (1,2):
                    self.db.commit();return self.status(member)
                if row and row[3] is not None:
                    self.db.commit();return self.status(member)
                if self.completed(uid)[0]>=DAILY_JOBS:raise self.Error('오늘 작업을 모두 마쳤어요. 자정 이후 다시 와주세요.',409)
                now=time.time();seed=secrets.token_hex(16)
                if active:
                    self.db.execute('UPDATE mari_web_work_jobs SET version=2,seed=?,clicks=0,created=?,last_click=? WHERE id=?',(seed,now,now,active[0]))
                else:
                    self.db.execute('INSERT INTO mari_web_work_jobs(id,user_id,guild_id,created,last_click,version,seed) VALUES(?,?,?,?,?,2,?)',(job_id,uid,gid,now,now,seed))
            elif action=='work/hit':
                if not row:raise self.Error('진행 중인 작업을 찾을 수 없어요.',404)
                if row[3] is not None:
                    self.db.commit();return self.status(member)
                if row[4] not in (1,2):raise self.Error('새로운 광산 작업을 시작해주세요.',409)
                now=time.time();elapsed=round((now-row[2])*1000)
                if elapsed<DURATION:raise self.Error('20초 작업을 끝낸 뒤 결과를 확인해주세요.',429)
                hits,total=self.judge(data.get('events'),row[5],elapsed,row[4])
                if data.get('finish') is not True:raise self.Error('작업 완료 기록을 확인해주세요.')
                self.db.execute('UPDATE mari_web_work_jobs SET clicks=?,last_click=?,ended=? WHERE id=?',(hits,now,now,job_id))
                if hits>=minimum(total,row[4]):
                    if self.completed(uid)[0]>=DAILY_JOBS:raise self.Error('오늘 작업을 모두 마쳤어요.',409)
                    roll=secrets.randbelow(100)
                    for tier,chance,amount in REWARDS:
                        if roll<chance:break
                        roll-=chance
                    balance=self.b.ns['get_balance'](member.id)
                    if balance+amount>9_000_000_000_000_000:raise self.Error('지갑 보유 한도를 초과해 보상을 받을 수 없어요.',409)
                    self.db.execute('INSERT INTO balances(user_id,balance) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET balance=balance+excluded.balance',(uid,amount))
                    self.db.execute('UPDATE mari_web_work_jobs SET finished_day=?,reward=?,tier=? WHERE id=?',(self.today(),amount,tier,job_id))
                    self.b.weekly.record('work:'+job_id,'work',member.id,member.guild.id,amount)
                    self.b.log_history(member.id,member.guild.id,'마리 광산',tier+' 리듬 채굴 완료',amount)
            else:raise self.Error('지원하지 않는 작업입니다.',404)
            self.db.commit()
        except BaseException:
            self.db.rollback();raise
        return self.status(member)
