"""Daily rewards reuse the original Discord callbacks and their claim ledgers."""
import hashlib
import json
import time
from mari_web_activities import DeferredConnection

class Rewards:
    def __init__(self,bridge,error):
        self.b=bridge;self.db=bridge.db;self.ns=bridge.ns;self.Error=error

    def status(self,member):
        ns=self.ns;uid=member.id;gid=member.guild.id
        today=ns['get_kst_now']().strftime('%Y-%m-%d')
        daily=self.db.execute('SELECT last_claim_date FROM daily_claims WHERE user_id=?',(str(uid),)).fetchone()
        day,start,end=ns['get_yesterday_range_kst']()
        claim=ns['get_voice_bonus_claim'](gid,uid,day)
        seconds=ns['get_voice_bonus_duration_seconds'](gid,uid,start,end)
        minutes=seconds//60
        profile=self.db.execute('SELECT is_blacklisted FROM credit_profiles WHERE user_id=?',(str(uid),)).fetchone()
        tickets=bool(profile and profile[0])
        rate=ns['VOICE_BONUS_BLACKLIST_TICKETS_PER_HOUR'] if tickets else ns['get_voice_bonus_hourly_amount'](gid)
        amount=minutes*rate//60
        if claim:
            tickets=claim['reward_type']=='labor_gacha'
            amount=claim['ticket_count'] if tickets else claim['amount']
        return {'support':{'date':today,'amount':ns['DAILY_REWARD'],'claimed':bool(daily and daily[0]==today)},
                'bonus':{'date':day,'minutes':minutes,'amount':amount,'unit':'장' if tickets else '마리','type':'labor_gacha' if tickets else 'money','claimed':claim is not None,'available':claim is None and minutes>0 and amount>0}}

    async def claim(self,member,kind,data):
        from mari_web_bridge import Capture,InteractionAdapter
        if kind not in ('support','bonus'): raise self.Error('지원하지 않는 보상입니다.',404)
        request=data.get('requestId')
        if not isinstance(request,str) or not 16<=len(request)<=80: raise self.Error('요청 번호가 필요해요.')
        fingerprint=hashlib.sha256(json.dumps(['reward',kind,str(member.guild.id)]).encode()).hexdigest()
        old=self.db.execute('SELECT user_id,fingerprint FROM mari_web_activity_requests WHERE request_id=?',(request,)).fetchone()
        if old:
            if old!=(str(member.id),fingerprint): raise self.Error('다른 작업의 요청 번호입니다.',409)
            return {'rewards':self.status(member),'message':'이미 처리한 수령 요청입니다. 현재 수령 상태를 확인해주세요.'}
        capture=Capture(request,'reward',member.id,member.guild.id,self.ns['get_balance'](member.id),self.b)
        interaction=InteractionAdapter(self.b.bot,member,capture)
        original=self.ns['conn']
        self.db.execute('BEGIN IMMEDIATE')
        self.ns['conn']=DeferredConnection(self.db)
        try:
            # Original callbacks do all ledger work before their final response.
            # The response adapter has no network wait, keeping the transaction
            # on the bot event loop atomic with respect to Discord claims.
            if kind=='support': await self.ns['claim_daily_support_money'](interaction,ephemeral_success=True)
            else:
                view=self.ns['VoiceBonusPanelView']()
                button=next(c for c in view.children if c.custom_id=='voice_bonus_claim')
                await button.callback(interaction)
            self.db.execute('INSERT INTO mari_web_activity_requests VALUES(?,?,?,?)',(request,str(member.id),fingerprint,time.time()))
            self.db.commit()
        except BaseException:
            self.db.rollback();raise
        finally: self.ns['conn']=original
        message=capture.embeds[0].title if capture.embeds else capture.content
        return {'rewards':self.status(member),'message':message or '수령 상태를 확인해주세요.'}
