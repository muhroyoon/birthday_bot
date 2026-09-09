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
            UNION ALL
            SELECT h.user_id,h.cost,mari_log_equity(h.cost,h.log_basis,h.leverage,h.side,p.price) AS equity FROM mari_web_log_positions h JOIN mari_web_stocks p ON p.symbol=h.symbol WHERE h.qty>0
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
        from mari_web_weekly import training_board
        game=data.get('game')
        if game in GAMES or game in self.b.ns['CASINO_GAMES'] or game=='work':
            if game=='all_in':return self.result([],uid,'money','몰빵은 주간 랭킹 상금 대상이 아닙니다.')
            return self.b.weekly.ranking(game,uid,data.get('period')=='previous')
        if game in ('pubg','fortune'):
            return self.result([],uid,'score','경쟁 기록이 없어 주간 랭킹 상금 대상이 아닙니다.')
        mode=data.get('mode') if game=='aim' else game
        if game not in ('aim','reaction','stopwatch','apple','snake','suika','2048'):raise self.Error('게임을 확인해주세요.')
        mode,difficulty,seconds=self.b.training.config({'mode':mode,'difficulty':data.get('difficulty'),'seconds':data.get('seconds')})
        device=data.get('input','mouse')
        if device not in ('mouse','touch'):raise self.Error('입력 장치를 확인해주세요.')
        return self.b.weekly.ranking(training_board(mode,difficulty,seconds,device),uid,data.get('period')=='previous')
