"""Cross-server rankings from recorded games and the stock position ledger."""
from fractions import Fraction
import json

class Rankings:
    def __init__(self,b,error):self.b=b;self.db=b.db;self.Error=error
    def members(self):
        preferred=dict(self.db.execute('SELECT user_id,guild_id FROM mari_web_profiles'));result={}
        for gid in sorted(self.b.guild_ids):
            guild=self.b.bot.get_guild(gid)
            if not guild:continue
            for member in guild.members:
                uid=str(member.id)
                if not member.bot and (uid not in result or preferred.get(uid)==str(gid)):result[uid]=member
        return result
    def result(self,rows,uid,metric,note):
        members=self.members();entries=[];mine=None;total=0
        for raw in rows:
            member=members.get(raw['userId'])
            if not member:continue
            total+=1
            row={**raw,'rank':total,'name':member.display_name,'username':member.name,'avatar':str(member.display_avatar.url),'guild':self.b.guild_info(member.guild),'style':self.b.social.decoration(member.id) if hasattr(self.b,'social') else {}}
            if total<=100:entries.append(row)
            if raw['userId']==str(uid):mine=row
        return {'entries':entries,'mine':mine,'total':total,'metric':metric,'note':note}
    def stocks(self,uid):
        self.b.economy.settle()
        rows=self.db.execute('''
        WITH trades AS (
          SELECT user_id,
            SUM(CASE WHEN side IN ('buy','long_open','short_open') THEN total ELSE 0 END) AS opened,
            SUM(CASE WHEN side IN ('sell','long_close','short_close','short_liquidate','long_liquidate') THEN total-profit ELSE 0 END) AS closed_basis,
            SUM(CASE WHEN side IN ('sell','long_close','short_close','short_liquidate','long_liquidate') THEN profit ELSE 0 END) AS realized
          FROM mari_web_stock_trades GROUP BY user_id
        ), positions AS (
          SELECT user_id,SUM(cost) cost,SUM(equity) equity FROM (
            SELECT h.user_id,h.cost,h.qty*p.price equity FROM mari_web_holdings h JOIN mari_web_stocks p ON p.symbol=h.symbol WHERE h.qty>0
            UNION ALL
            SELECT h.user_id,h.cost,MAX(0,2*h.cost-h.qty*p.price) equity FROM mari_web_shorts h JOIN mari_web_stocks p ON p.symbol=h.symbol WHERE h.qty>0
            UNION ALL
            SELECT h.user_id,h.cost,MAX(0,h.cost+(h.qty*p.price-h.notional)*CASE WHEN h.side='long' THEN 1 ELSE -1 END) equity FROM mari_web_leveraged h JOIN mari_web_stocks p ON p.symbol=h.symbol WHERE h.qty>0
          ) GROUP BY user_id
        ), users AS (SELECT user_id FROM trades UNION SELECT user_id FROM positions)
        SELECT u.user_id,COALESCE(t.realized,0),COALESCE(p.equity,0)-COALESCE(p.cost,0),
          MAX(COALESCE(t.opened,0),COALESCE(t.closed_basis,0)+COALESCE(p.cost,0))
        FROM users u LEFT JOIN trades t ON u.user_id=t.user_id LEFT JOIN positions p ON u.user_id=p.user_id
        ''').fetchall()
        rows=[{'userId':user,'realized':realized,'unrealized':unrealized,'profit':realized+unrealized,'invested':invested,'value':round((realized+unrealized)/invested*100,4)} for user,realized,unrealized,invested in rows if invested>0]
        rows.sort(key=lambda r:(-Fraction(r['profit'],r['invested']),r['userId']))
        return self.result(rows,uid,'return','수익률 = (누적 실현 손익 + 현재 평가 손익) ÷ 누적 진입 금액. 재투자도 진입 금액에 포함하며, 기존 주식에서 전환한 원금도 합산합니다.')
    def game(self,uid,data):
        from mari_web_adventure import GAMES,Adventure
        if data.get('game') in GAMES:
            Adventure(self.b,self.Error)
            rows=self.db.execute('SELECT user_id,MAX(score),COUNT(*) FROM mari_web_adventures WHERE game=? AND done=1 GROUP BY user_id ORDER BY MAX(score) DESC,user_id',(data['game'],)).fetchall()
            return self.result([{'userId':u,'value':score,'plays':plays} for u,score,plays in rows],uid,'score','서버에서 판정한 최고 점수입니다. 동점은 디스코드 ID 순서입니다.')
        game=data.get('game')
        if game=='all_in':
            return self.result([],uid,'money','몰빵은 과거 당첨자의 계정 ID와 지급액이 함께 보존되지 않아 누적 순이익 순위를 집계할 수 없습니다. 현재 참여 현황은 몰빵 화면에서 확인해주세요.')
        if game in self.b.ns['CASINO_GAMES']:
            name=self.b.ns['CASINO_GAMES'][game]['name']
            # Match the original completed-game receipt, excluding raffle/reward
            # history that happens to share a game name. EXISTS avoids duplicates.
            rows=self.db.execute('''SELECT h.user_id,SUM(h.delta),COUNT(*) FROM mari_web_history h
              WHERE h.name=? AND EXISTS(SELECT 1 FROM mari_web_rounds r
                WHERE r.user_id=h.user_id AND r.guild_id=h.guild_id AND r.game=? AND r.status='done'
                AND h.detail=json_extract(r.snapshot,'$.title')||' · '||substr(json_extract(r.snapshot,'$.description'),1,400))
              GROUP BY h.user_id ORDER BY SUM(h.delta) DESC,h.user_id ASC''',(name,game)).fetchall()
            return self.result([{'userId':u,'value':profit,'plays':plays} for u,profit,plays in rows],uid,'money','웹에서 완료된 게임의 누적 순이익 기준입니다. 디스코드 전용 플레이는 계정별 손익 기록이 없어 포함되지 않습니다.')
        if game=='work':
            # This table is created lazily by the work feature.
            if not self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='mari_web_work_jobs'").fetchone():rows=[]
            else:rows=self.db.execute('SELECT user_id,SUM(reward),COUNT(*) FROM mari_web_work_jobs WHERE finished_day IS NOT NULL GROUP BY user_id ORDER BY SUM(reward) DESC,user_id ASC').fetchall()
            return self.result([{'userId':u,'value':earned,'plays':plays} for u,earned,plays in rows],uid,'money','마리 광산에서 받은 누적 보상 기준입니다.')
        if game in ('pubg','fortune'):
            return self.result([],uid,'score','배그 훈련장은 현재 서버에 검증된 점수를 저장하지 않으며, 오늘의 운세는 경쟁 점수가 없어 순위를 집계하지 않습니다.')
        mode=data.get('mode') if game=='aim' else game
        if game=='aim' and mode not in ('flick','grid','precision','path'):raise self.Error('에임 모드를 확인해주세요.')
        if game not in ('aim','reaction','stopwatch','apple','snake','suika','2048'):raise self.Error('게임을 확인해주세요.')
        config={'mode':mode,'difficulty':data.get('difficulty'),'seconds':data.get('seconds')}
        mode,difficulty,seconds=self.b.training.config(config);device=data.get('input','mouse')
        if device not in ('mouse','touch'):raise self.Error('입력 장치를 확인해주세요.')
        rows=self.db.execute('SELECT user_id,score,accuracy,average_ms FROM mari_web_training_best WHERE mode=? AND difficulty=? AND seconds=? AND input=? ORDER BY score DESC,accuracy DESC,average_ms ASC,user_id ASC',(mode,difficulty,seconds,device)).fetchall()
        metric='ms' if mode in ('reaction','stopwatch') else 'percent' if mode in ('precision','path') else 'speed' if game=='aim' else 'score'
        return self.result([{'userId':u,'value':avg if metric=='ms' else score,'accuracy':accuracy,'averageMs':avg} for u,score,accuracy,avg in rows],uid,metric,'같은 모드·난이도·시간·입력 장치에서 기록한 계정별 최고 기록입니다. 동점은 정확도, 평균 시간, 디스코드 ID 순으로 비교합니다.')
