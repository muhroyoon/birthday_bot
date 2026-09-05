"""Account-backed aim rankings; replay validation runs in the trusted site Worker."""
import json
import math
import secrets
import time

class TrainingRecords:
    def __init__(self,bridge,error):
        self.b=bridge;self.db=bridge.db;self.Error=error
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS mari_web_training_runs(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,guild_id TEXT NOT NULL,mode TEXT NOT NULL,difficulty TEXT NOT NULL,seconds INTEGER NOT NULL,seed INTEGER NOT NULL,started_at REAL NOT NULL,submitted INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS mari_web_training_best(user_id TEXT NOT NULL,guild_id TEXT NOT NULL,mode TEXT NOT NULL,difficulty TEXT NOT NULL,seconds INTEGER NOT NULL,input TEXT NOT NULL,score REAL NOT NULL,accuracy REAL NOT NULL,average_ms REAL NOT NULL,metrics TEXT NOT NULL,updated_at REAL NOT NULL,PRIMARY KEY(user_id,mode,difficulty,seconds,input));
        ''');self.db.commit()
    def config(self,data):
        mode=data.get('mode');difficulty=data.get('difficulty');seconds=data.get('seconds')
        if mode not in ('flick','grid','precision','path') or difficulty not in ('easy','normal','hard') or type(seconds) is not int or seconds not in (15,30,60):raise self.Error('연습 조건을 확인해주세요.')
        return mode,difficulty,seconds
    def start(self,member,data):
        mode,difficulty,seconds=self.config(data);now=time.time()
        self.db.execute('DELETE FROM mari_web_training_runs WHERE started_at<?',(now-900,))
        latest=self.db.execute('SELECT MAX(started_at) FROM mari_web_training_runs WHERE user_id=?',(str(member.id),)).fetchone()[0]
        if latest and now-latest<2:raise self.Error('잠시 후 다시 시작해주세요.',429)
        rid=secrets.token_urlsafe(24);seed=secrets.randbits(32)
        self.db.execute('INSERT INTO mari_web_training_runs VALUES(?,?,?,?,?,?,?,?,0)',(rid,str(member.id),str(member.guild.id),mode,difficulty,seconds,seed,now));self.db.commit()
        return {'id':rid,'seed':seed,'config':{'mode':mode,'difficulty':difficulty,'seconds':seconds}}
    def ticket(self,member,data):
        row=self.db.execute('SELECT user_id,guild_id,mode,difficulty,seconds,seed,started_at,submitted FROM mari_web_training_runs WHERE id=?',(data.get('id'),)).fetchone()
        if not row or row[0]!=str(member.id) or row[1]!=str(member.guild.id) or time.time()-row[6]>900:raise self.Error('연습 기록이 만료됐어요. 다시 연습해주세요.',409)
        return row
    def submit(self,member,data):
        row=self.ticket(member,data);m=data.get('metrics',{})
        if not isinstance(m,dict) or m.get('input') not in ('mouse','touch'):raise self.Error('입력 장치를 확인해주세요.')
        for key in ('score','accuracy','precision','averageMs','hits','elapsed'):
            n=m.get(key)
            if type(n) not in (int,float) or not math.isfinite(n) or n<0:raise self.Error('잘못된 측정 기록입니다.')
        if m['accuracy']>100 or m['precision']>100 or m['elapsed']>row[4] or time.time()-row[6]+1<m['elapsed']:raise self.Error('연습 시간을 확인해주세요.')
        config={'mode':row[2],'difficulty':row[3],'seconds':row[4],'input':m['input']}
        if row[7]:return self.ranking(config,member.id)
        old=self.db.execute('SELECT score,accuracy,average_ms FROM mari_web_training_best WHERE user_id=? AND mode=? AND difficulty=? AND seconds=? AND input=?',(str(member.id),row[2],row[3],row[4],m['input'])).fetchone()
        if not old or (m['score'],m['accuracy'],-m['averageMs'])>(old[0],old[1],-old[2]):
            self.db.execute('INSERT OR REPLACE INTO mari_web_training_best VALUES(?,?,?,?,?,?,?,?,?,?,?)',(str(member.id),str(member.guild.id),row[2],row[3],row[4],m['input'],m['score'],m['accuracy'],m['averageMs'],json.dumps(m),time.time()))
        self.db.execute('UPDATE mari_web_training_runs SET submitted=1 WHERE id=?',(data.get('id'),));self.db.commit()
        return self.ranking(config,member.id)
    def ranking(self,data,uid=None):
        mode,difficulty,seconds=self.config(data);device=data.get('input','mouse')
        if device not in ('mouse','touch'):raise self.Error('입력 장치를 확인해주세요.')
        members={}
        for gid in sorted(self.b.guild_ids):
            guild=self.b.bot.get_guild(gid)
            if guild:
                for member in guild.members:
                    if not member.bot:members[str(member.id)]=member
        entries=[];mine=None;total=0
        for user,gid,raw in self.db.execute('SELECT user_id,guild_id,metrics FROM mari_web_training_best WHERE mode=? AND difficulty=? AND seconds=? AND input=? ORDER BY score DESC,accuracy DESC,average_ms ASC,user_id ASC',(mode,difficulty,seconds,device)):
            member=members.get(user)
            if not member:continue
            total+=1
            item={'rank':total,'userId':user,'name':member.display_name,'guild':member.guild.name,**json.loads(raw)}
            if total<=20:entries.append(item)
            if user==str(uid):mine=item
        return {'entries':entries,'mine':mine,'total':total}
