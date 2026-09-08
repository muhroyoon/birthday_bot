"""Account-wide click work; progress, random rewards and payout live on the bot."""
import re
import secrets
import time
from datetime import datetime, timezone, timedelta

CLICKS = 30
DAILY_JOBS = 30
MIN_CLICK_SECONDS = .10
REWARDS = [('일반', 70, 1000000), ('희귀', 25, 3000000), ('영웅', 4, 5000000), ('전설', 1, 10000000)]
KST = timezone(timedelta(hours=9))

class Work:
    def __init__(self, bridge, error):
        self.b=bridge; self.db=bridge.db; self.Error=error
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS mari_web_work_jobs(
          id TEXT PRIMARY KEY,user_id TEXT NOT NULL,guild_id TEXT NOT NULL,
          clicks INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL,last_click REAL NOT NULL,
          finished_day TEXT, reward INTEGER NOT NULL DEFAULT 0, tier TEXT);
        CREATE INDEX IF NOT EXISTS idx_work_user_day ON mari_web_work_jobs(user_id,finished_day);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_work_one_active ON mari_web_work_jobs(user_id) WHERE finished_day IS NULL;
        ''');self.db.commit()

    def today(self):return datetime.now(KST).date().isoformat()
    def completed(self, uid):
        return self.db.execute('SELECT COUNT(*),COALESCE(SUM(reward),0) FROM mari_web_work_jobs WHERE user_id=? AND finished_day=?',(str(uid),self.today())).fetchone()
    def status(self, member):
        done,earned=self.completed(member.id)
        row=self.db.execute('SELECT id,clicks,finished_day,reward,tier FROM mari_web_work_jobs WHERE user_id=? ORDER BY rowid DESC LIMIT 1',(str(member.id),)).fetchone()
        return {'required':CLICKS,'dailyLimit':DAILY_JOBS,'completed':done,'earned':earned,'day':self.today(),
                'balance':self.b.ns['get_balance'](member.id),'rewards':[{'tier':t,'chance':c,'amount':a} for t,c,a in REWARDS],
                'job':{'id':row[0],'clicks':row[1],'done':row[2] is not None,'reward':row[3],'tier':row[4]} if row else None}

    def mutate(self, member, action, data):
        uid=str(member.id);gid=str(member.guild.id)
        if data.get('expectedUser')!=uid or data.get('expectedGuild')!=gid:
            raise self.Error('계정이나 서버가 바뀌었어요. 새로고침해주세요.',409)
        job_id=data.get('id')
        if not isinstance(job_id,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,80}',job_id):raise self.Error('작업 번호를 확인해주세요.')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT user_id,clicks,last_click,finished_day FROM mari_web_work_jobs WHERE id=?',(job_id,)).fetchone()
            if row and row[0]!=uid:raise self.Error('다른 사람의 작업입니다.',403)
            if action=='work/start':
                if row:
                    self.db.commit();return self.status(member)
                active=self.db.execute('SELECT id FROM mari_web_work_jobs WHERE user_id=? AND finished_day IS NULL',(uid,)).fetchone()
                if active:
                    self.db.commit();return self.status(member)
                if self.completed(uid)[0]>=DAILY_JOBS:raise self.Error('오늘 작업을 모두 마쳤어요. 자정 이후 다시 와주세요.',409)
                now=time.time()
                self.db.execute('INSERT INTO mari_web_work_jobs(id,user_id,guild_id,created,last_click) VALUES(?,?,?,?,?)',(job_id,uid,gid,now,now))
            elif action=='work/hit':
                if not row:raise self.Error('진행 중인 작업을 찾을 수 없어요.',404)
                count=data.get('clicks')
                if type(count) is not int or not 1<=count<=CLICKS:raise self.Error('작업 횟수를 확인해주세요.')
                if row[3] is not None or count<=row[1]:
                    self.db.commit();return self.status(member)
                delta=count-row[1];now=time.time()
                if delta>5 or now-row[2]<delta*MIN_CLICK_SECONDS:raise self.Error('작업이 너무 빨라요. 잠시 후 다시 눌러주세요.',429)
                if self.completed(uid)[0]>=DAILY_JOBS:raise self.Error('오늘 작업을 모두 마쳤어요.',409)
                self.db.execute('UPDATE mari_web_work_jobs SET clicks=?,last_click=? WHERE id=?',(count,now,job_id))
                if count==CLICKS:
                    roll=secrets.randbelow(100)
                    for tier,chance,amount in REWARDS:
                        if roll<chance:break
                        roll-=chance
                    balance=self.b.ns['get_balance'](member.id)
                    if balance+amount>9_000_000_000_000_000:raise self.Error('지갑 보유 한도를 초과해 보상을 받을 수 없어요.',409)
                    self.db.execute('INSERT INTO balances(user_id,balance) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET balance=balance+excluded.balance',(uid,amount))
                    self.db.execute('UPDATE mari_web_work_jobs SET finished_day=?,reward=?,tier=? WHERE id=?',(self.today(),amount,tier,job_id))
                    self.b.log_history(member.id,member.guild.id,'마리 광산',tier+' 광석 작업 완료',amount)
            else:raise self.Error('지원하지 않는 작업입니다.',404)
            self.db.commit()
        except BaseException:
            self.db.rollback();raise
        return self.status(member)
