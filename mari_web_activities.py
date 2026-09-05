"""Website activities reuse the bot SQLite tables and scoring functions."""
import hashlib
import json
import math
import time
from datetime import datetime
from zoneinfo import ZoneInfo

class DeferredConnection:
    def __init__(self, db): self.db=db
    def commit(self): pass
    def __getattr__(self, name): return getattr(self.db,name)

class Activities:
    def __init__(self, bridge, error):
        self.b=bridge; self.db=bridge.db; self.ns=bridge.ns; self.Error=error
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS mari_web_kill_entries(
            session_id INTEGER NOT NULL,user_id TEXT NOT NULL,player_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',created_at REAL NOT NULL,
            PRIMARY KEY(session_id,user_id));
        CREATE UNIQUE INDEX IF NOT EXISTS mari_kill_one_player ON mari_web_kill_entries(session_id,player_id) WHERE status='approved';
        CREATE TABLE IF NOT EXISTS mari_web_activity_requests(
            request_id TEXT PRIMARY KEY,user_id TEXT NOT NULL,fingerprint TEXT NOT NULL,created_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS mari_web_notice_reads(user_id TEXT NOT NULL,event_key TEXT NOT NULL,PRIMARY KEY(user_id,event_key));
        """); self.db.commit()

    def number(self,value,minimum=0,maximum=1000000):
        try: n=float(value)
        except (ValueError,TypeError): raise self.Error('올바른 숫자를 입력해주세요.')
        if not math.isfinite(n) or not minimum<=n<=maximum: raise self.Error('입력한 숫자가 허용 범위를 벗어났어요.')
        return n

    def text(self,value,maximum=1000):
        if not isinstance(value,str) or len(value)>maximum: raise self.Error('입력 내용을 확인해주세요.')
        return value.strip()

    def visible(self,member,channel_id):
        channel=member.guild.get_channel(int(channel_id))
        if channel is None: return False
        perms=channel.permissions_for(member)
        return perms.view_channel and perms.read_message_history

    def manage(self,member,session):
        return str(member.id)==str(session['creator_user_id']) or member.guild_permissions.administrator

    def session(self,member,value):
        sid=int(self.number(value,1))
        session=self.ns['get_kill_bet_session_by_id'](member.guild.id,sid)
        if not session or not self.visible(member,session['channel_id']): raise self.Error('이 킬내기에 접근할 수 없어요.',403)
        return session

    def listing(self,member):
        channels=[{'id':str(c.id),'name':c.name} for c in getattr(member.guild,'text_channels',[]) if self.visible(member,c.id)]
        rows=self.db.execute('SELECT id FROM kill_bet_sessions WHERE guild_id=? ORDER BY id DESC LIMIT 50',(str(member.guild.id),)).fetchall()
        sessions=[]
        for (sid,) in rows:
            s=self.ns['get_kill_bet_session_by_id'](member.guild.id,sid)
            if not s or not self.visible(member,s['channel_id']): continue
            players=self.ns['get_kill_bet_players'](sid)
            rounds=self.db.execute('SELECT id FROM kill_bet_rounds WHERE session_id=? ORDER BY round_no DESC LIMIT 30',(sid,)).fetchall()
            details=[]
            for (rid,) in rounds:
                r=self.ns['get_kill_bet_round_by_id'](sid,rid)
                details.append({**r,'scores':self.ns['get_kill_bet_round_scores'](rid)})
            entries=self.db.execute('SELECT user_id,player_id,status FROM mari_web_kill_entries WHERE session_id=?',(sid,)).fetchall()
            teams={}
            for player in players:
                key=player['team_name'] or player['pubg_name']
                teams[key]=teams.get(key,0)+player['total_score']
            s.update(players=players,rounds=details,canManage=self.manage(member,s),
                standings=[{'name':name,'score':score} for name,score in sorted(teams.items(),key=lambda x:(-x[1],x[0]))],
                entries=[{'userId':uid,'name':getattr(member.guild.get_member(int(uid)),'display_name','서버 멤버'),'playerId':pid,'status':status} for uid,pid,status in entries])
            sessions.append(s)
        return {'sessions':sessions,'rules':[dict(key=k,**v) for k,v in self.ns['KILL_BET_RULES'].items()],'channels':channels}

    def mutate(self,member,action,data):
        request=self.text(data.get('requestId'),80)
        if len(request)<16: raise self.Error('요청 번호가 필요해요.')
        fingerprint=hashlib.sha256(json.dumps([action,data],sort_keys=True).encode()).hexdigest()
        existing=self.db.execute('SELECT user_id,fingerprint FROM mari_web_activity_requests WHERE request_id=?',(request,)).fetchone()
        if existing:
            if existing!=(str(member.id),fingerprint): raise self.Error('다른 작업의 요청 번호입니다.',409)
            return self.listing(member)
        original=self.ns['conn']
        self.db.execute('BEGIN IMMEDIATE')
        self.ns['conn']=DeferredConnection(self.db)
        try:
            self._apply(member,action,data)
            self.db.execute('INSERT INTO mari_web_activity_requests VALUES(?,?,?,?)',(request,str(member.id),fingerprint,time.time()))
            self.db.commit()
        except BaseException:
            self.db.rollback();raise
        finally: self.ns['conn']=original
        return self.listing(member)

    def _apply(self,member,action,data):
        if action=='kill/create':
            key=self.text(data.get('rule'),50); rule=self.ns['get_kill_bet_rule'](key)
            if not rule: raise self.Error('킬내기 룰을 선택해주세요.')
            channel_value=self.text(data.get('channelId'),24)
            if not channel_value.isdigit(): raise self.Error('서버 채널을 선택해주세요.')
            cid=int(channel_value)
            if not self.visible(member,cid): raise self.Error('접근 가능한 서버 채널을 선택해주세요.',403)
            if self.db.execute("SELECT COUNT(*) FROM kill_bet_sessions WHERE creator_user_id=? AND guild_id=? AND status='active'",(str(member.id),str(member.guild.id))).fetchone()[0]>=5:
                raise self.Error('진행 중인 내기를 먼저 마무리해주세요.')
            participants=self.ns['parse_kill_bet_participants'](rule,self.text(data.get('participants'),900),self.text(data.get('handicaps',''),600))
            names=[p['pubg_name'].lower() for p in participants]
            if len(names)!=len(set(names)) or len(names)>64: raise self.Error('참가자 닉네임은 중복 없이 최대 64명까지 입력해주세요.')
            for p in participants:
                self.number(p['handicap_kill'],-100,100);self.number(p['handicap_damage'],-100,100)
            target=self.number(data.get('target'),1) if rule['target_score_required'] else None
            self.ns['create_kill_bet_session'](member.guild.id,cid,None,member.id,key,'manual',target,participants)
            return
        s=self.session(member,data.get('id'));sid=s['id']
        if s['status']!='active': raise self.Error('이미 종료된 킬내기입니다.',409)
        if action=='kill/join':
            pid=int(self.number(data.get('playerId'),1))
            if not self.ns['get_kill_bet_player_by_id'](sid,pid): raise self.Error('등록된 참가자를 선택해주세요.')
            old=self.db.execute('SELECT status FROM mari_web_kill_entries WHERE session_id=? AND user_id=?',(sid,str(member.id))).fetchone()
            if old and old[0]=='approved': raise self.Error('이미 참가가 승인되었어요.')
            self.db.execute("INSERT INTO mari_web_kill_entries VALUES(?,?,?,'pending',?) ON CONFLICT(session_id,user_id) DO UPDATE SET player_id=excluded.player_id,status='pending',created_at=excluded.created_at",(sid,str(member.id),pid,time.time()))
            return
        if not self.manage(member,s): raise self.Error('킬내기 생성자 또는 서버 관리자만 처리할 수 있어요.',403)
        if action=='kill/approve':
            uid=self.text(data.get('userId'),24)
            if not uid.isdigit() or member.guild.get_member(int(uid)) is None: raise self.Error('현재 서버 멤버만 참가 승인할 수 있어요.',403)
            row=self.db.execute('SELECT player_id FROM mari_web_kill_entries WHERE session_id=? AND user_id=?',(sid,uid)).fetchone()
            if not row: raise self.Error('참가 신청이 없어요.')
            if self.db.execute("SELECT 1 FROM mari_web_kill_entries WHERE session_id=? AND player_id=? AND status='approved' AND user_id!=?",(sid,row[0],uid)).fetchone(): raise self.Error('이미 다른 멤버가 참가한 닉네임입니다.')
            self.db.execute("UPDATE mari_web_kill_entries SET status='approved' WHERE session_id=? AND user_id=?",(sid,uid));return
        if action=='kill/end':
            if self.db.execute("SELECT 1 FROM kill_bet_rounds WHERE session_id=? AND status='inputting'",(sid,)).fetchone(): raise self.Error('입력 중인 판의 참가자 점수를 모두 입력한 후 종료해주세요.')
            self.ns['finish_kill_bet_session'](sid);return
        if action!='kill/score': raise self.Error('지원하지 않는 작업입니다.',404)
        parsed=self.ns['parse_kill_bet_manual_score_lines'](self.text(data.get('scores'),4000))
        players={p['pubg_name'].lower():p for p in self.ns['get_kill_bet_players'](sid)}
        seen=set();selected=[]
        for row in parsed:
            player=players.get(row['pubg_name'].lower())
            if not player or player['id'] in seen: raise self.Error('등록된 닉네임의 점수를 중복 없이 입력해주세요.')
            seen.add(player['id']);self.number(row['kills'],0,1000);self.number(row['damage'],0,1000000)
            if row['rank'] is not None: self.number(row['rank'],1,1000)
            selected.append((player,row))
        team=None
        if self.ns['get_kill_bet_rule'](s['rule_key'])['mode']=='team':
            teams={p['team_name'] or '미지정' for p,r in selected}
            if len(teams)!=1: raise self.Error('팀전 점수는 한 번에 한 팀씩 입력해주세요.')
            team=next(iter(teams))
        round_data=self.ns['get_or_create_open_kill_bet_round'](sid,team)
        for player,row in selected:
            self.ns['save_kill_bet_round_score'](round_data['id'],player,row['kills'],row['damage'],row['rank'],member.id)
        expected=[p for p in players.values() if team is None or (p['team_name'] or '미지정')==team]
        if len(self.ns['get_kill_bet_round_scores'](round_data['id']))>=len(expected):
            self.ns['finalize_kill_bet_round'](s,round_data)
            if self.ns['kill_bet_target_reached'](s): self.ns['finish_kill_bet_session'](sid)

    def all_in_status(self,member):
        gid=str(member.guild.id)
        today=datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
        participants=[]
        for uid,amount in self.db.execute('SELECT user_id,amount FROM all_in_entries WHERE guild_id=? AND entry_date=? ORDER BY amount DESC,user_id',(gid,today)):
            person=member.guild.get_member(int(uid))
            participants.append({'id':str(uid),'name':getattr(person,'display_name','알 수 없는 멤버'),'amount':amount})
        results=[{'id':str(i),'text':text,'at':at} for i,text,at in self.db.execute('SELECT id,result_text,created_at FROM game_history WHERE guild_id=? AND game_name=? ORDER BY id DESC LIMIT 5',(gid,self.ns.get('ALL_IN_GAME_NAME','몰빵게임')))]
        return {'date':today,'participants':participants,'total':sum(p['amount'] for p in participants),'results':results}

    async def notifications(self,member):
        notices=[];uid=str(member.id);gid=str(member.guild.id)
        for day,amount in self.db.execute('SELECT entry_date,amount FROM all_in_entries WHERE user_id=? AND guild_id=? ORDER BY entry_date DESC LIMIT 10',(uid,gid)):
            notices.append({'key':f'all-in:{gid}:{day}:{uid}','category':'all_in','title':'몰빵 참여 완료','body':f'{day} · {amount:,} 마리 참여','at':day+'T00:00:00+09:00','tab':'games'})
        recruits=await self.b.recruit_posts(member)
        for post in [p for p in recruits['posts'] if not p['closed']][:10]:
            notices.append({'key':f'recruit:{gid}:{post["id"]}','category':'recruit','title':'새 구인 글 · #'+post['channel'],'body':post['title'],'at':post['at'],'tab':'recruits','url':post['url']})
        read={r[0] for r in self.db.execute('SELECT event_key FROM mari_web_notice_reads WHERE user_id=?',(uid,))}
        notices.sort(key=lambda n:datetime.fromisoformat(n['at']).timestamp(),reverse=True)
        result=[dict(n,read=n['key'] in read) for n in notices[:100]]
        return {'notices':result,'unread':sum(not n['read'] for n in result),'allIn':self.all_in_status(member)}

    async def mark_read(self,member,data):
        result=await self.notifications(member)
        keys={n['key'] for n in result['notices']}
        selected=data.get('keys',[])
        if not isinstance(selected,list) or len(selected)>100 or any(not isinstance(k,str) or k not in keys for k in selected): raise self.Error('알림을 다시 확인해주세요.')
        self.db.executemany('INSERT OR IGNORE INTO mari_web_notice_reads VALUES(?,?)',[(str(member.id),k) for k in selected]);self.db.commit()
        for notice in result['notices']:
            if notice['key'] in selected: notice['read']=True
        result['unread']=sum(not n['read'] for n in result['notices'])
        return result
