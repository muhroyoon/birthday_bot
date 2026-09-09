"""Friday 21:00 KST seasons; immutable results and transactional prize payments."""
import json
import time
from datetime import datetime, timedelta, timezone

KST=timezone(timedelta(hours=9))
WEEK=7*86400
PRIZES=(30000000,15000000,5000000)
NAMES={'flick':'에임 연습','reaction':'반응속도','stopwatch':'스톱워치','apple':'사과게임','snake':'지렁이 게임','suika':'수박게임','2048':'2048','fishing':'마리 낚시','runner':'장애물 달리기','memory':'기억력 게임','tower':'타워 쌓기','territory':'땅따먹기','dodge':'탄막 피하기','work':'마리 광산'}

def week_start(now):
    d=datetime.fromtimestamp(now,KST)
    friday=(d-timedelta(days=(d.weekday()-4)%7)).replace(hour=21,minute=0,second=0,microsecond=0)
    if d<friday:friday-=timedelta(days=7)
    return int(friday.timestamp())

def training_board(mode,difficulty,seconds,device):return f'{mode}:{difficulty}:{seconds}:{device}'

def official(board):
    if board=='all_in':return False
    if ':' not in board:return True
    mode,difficulty,seconds,device=board.split(':')
    durations={'flick':30,'reaction':60,'stopwatch':10,'apple':120,'snake':180,'suika':600,'2048':600}
    return difficulty=='normal' and device=='mouse' and mode in durations and int(seconds)==durations[mode]

class Weekly:
    def __init__(self,b):
        self.b=b;self.db=b.db
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS mari_web_weekly_meta(id INTEGER PRIMARY KEY, activated REAL NOT NULL, next_end INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS mari_web_weekly_records(id TEXT PRIMARY KEY,week INTEGER,board TEXT,user_id TEXT,guild_id TEXT,at REAL,score REAL,accuracy REAL,average_ms REAL,metrics TEXT);
        CREATE INDEX IF NOT EXISTS weekly_board ON mari_web_weekly_records(week,board,user_id);
        CREATE TABLE IF NOT EXISTS mari_web_weekly_results(week INTEGER,board TEXT,rows_json TEXT NOT NULL,PRIMARY KEY(week,board));
        CREATE TABLE IF NOT EXISTS mari_web_weekly_awards(week INTEGER,board TEXT,user_id TEXT,rank INTEGER,amount INTEGER,paid_at REAL,PRIMARY KEY(week,board,user_id),UNIQUE(week,board,rank));
        ''')
        now=time.time()
        self.db.execute('INSERT OR IGNORE INTO mari_web_weekly_meta VALUES(1,?,?)',(now,week_start(now)+WEEK));self.db.commit()

    def record(self,event,board,uid,gid,score,metrics=None,at=None):
        now=time.time() if at is None else at;m=metrics or {}
        self.db.execute('INSERT OR IGNORE INTO mari_web_weekly_records VALUES(?,?,?,?,?,?,?,?,?,?)',(event,week_start(now),board,str(uid),str(gid),now,score,m.get('accuracy',0),m.get('averageMs',0),json.dumps(m)))

    def rows(self,week,board):
        records=self.db.execute('SELECT user_id,guild_id,at,score,accuracy,average_ms,metrics FROM mari_web_weekly_records WHERE week=? AND board=? ORDER BY at,id',(week,board)).fetchall()
        summed=board=='work' or board in self.b.ns.get('CASINO_GAMES',{})
        best={}
        for uid,gid,at,score,accuracy,average,raw in records:
            item={'userId':uid,'guildId':gid,'score':score,'accuracy':accuracy,'averageMs':average,'at':at,'plays':1,'metrics':json.loads(raw)}
            old=best.get(uid)
            if old:item['plays']=old['plays']+1
            if summed and old:item['score']+=old['score']
            if summed or old is None or (score,accuracy,-average)>(old['score'],old['accuracy'],-old['averageMs']):best[uid]=item
            elif old:old['plays']+=1
        return sorted(best.values(),key=lambda r:(-r['score'],-r['accuracy'],r['averageMs'],r['at'],r['userId']))

    def decorate(self,rows):
        from mari_web_rankings import Rankings
        members=Rankings(self.b,ValueError).members();result=[]
        for row in rows:
            m=members.get(row['userId'])
            if not m:continue
            result.append({**row,'rank':len(result)+1,'name':m.display_name,'username':m.name,'avatar':str(m.display_avatar.url),'guild':self.b.guild_info(m.guild)})
        return result

    def settle(self,now=None):
        now=time.time() if now is None else now
        deadline=self.db.execute('SELECT next_end FROM mari_web_weekly_meta WHERE id=1').fetchone()[0]
        if now<deadline:return
        # One transaction covers every ledger entry, balance increment and checkpoint.
        with self.db:
            while deadline<=now:
                week=deadline-WEEK
                boards=[r[0] for r in self.db.execute('SELECT DISTINCT board FROM mari_web_weekly_records WHERE week=?',(week,))]
                for board in boards:
                    if self.db.execute('SELECT 1 FROM mari_web_weekly_results WHERE week=? AND board=?',(week,board)).fetchone():continue
                    rows=self.decorate(self.rows(week,board))
                    self.db.execute('INSERT INTO mari_web_weekly_results VALUES(?,?,?)',(week,board,json.dumps(rows)))
                    if not official(board):continue
                    for row,amount in zip(rows,PRIZES):
                        cur=self.db.execute('INSERT OR IGNORE INTO mari_web_weekly_awards VALUES(?,?,?,?,?,?)',(week,board,row['userId'],row['rank'],amount,now))
                        if cur.rowcount:
                            self.db.execute('INSERT INTO balances(user_id,balance) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET balance=balance+excluded.balance',(row['userId'],amount))
                deadline+=WEEK
                self.db.execute('UPDATE mari_web_weekly_meta SET next_end=? WHERE id=1',(deadline,))

    def ranking(self,board,uid,previous=False):
        now=time.time();week=week_start(now)-(WEEK if previous else 0)
        archived=self.db.execute('SELECT rows_json FROM mari_web_weekly_results WHERE week=? AND board=?',(week,board)).fetchone()
        rows=json.loads(archived[0]) if archived else self.decorate(self.rows(week,board))
        mode=board.split(':')[0]
        metric='ms' if mode in ('reaction','stopwatch') else 'percent' if mode in ('precision','path') else 'speed' if mode in ('flick','grid') else 'money' if mode=='work' or mode in self.b.ns.get('CASINO_GAMES',{}) else 'score'
        for row in rows:row['value']=row['averageMs'] if metric=='ms' else row['score']
        return {'entries':rows[:100],'mine':next((r for r in rows if r['userId']==str(uid)),None),'total':len(rows),'metric':metric,
                'note':'선택한 주의 기록 기준입니다. 동점은 점수·정확도·평균 시간 비교 후 먼저 달성한 기록을 우선합니다.','weekly':{'start':datetime.fromtimestamp(week,KST).isoformat(),'end':datetime.fromtimestamp(week+WEEK,KST).isoformat(),'prizeEligible':official(board),'prizes':PRIZES,'previous':previous,'settled':bool(archived)}}

    def notices(self,uid):
        rows=self.db.execute('SELECT week,board,rank,amount,paid_at FROM mari_web_weekly_awards WHERE user_id=? ORDER BY paid_at DESC LIMIT 30',(str(uid),)).fetchall()
        games=self.b.ns.get('CASINO_GAMES',{})
        return [{'key':f'weekly:{w}:{board}:{uid}','category':'weekly','title':'주간 랭킹 상금 지급','body':f'{NAMES.get(board.split(":")[0],games.get(board,{}).get("name",board))} {rank}위 · {amount:,} 마리','at':datetime.fromtimestamp(at,KST).isoformat(),'tab':'ranking'} for w,board,rank,amount,at in rows]
