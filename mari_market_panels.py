"""Persistent raffle panels and escrow auctions on the bot's shared SQLite database."""
import asyncio
import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord

KST = ZoneInfo('Asia/Seoul')
MAX_MONEY = 2**63 - 1
log = logging.getLogger(__name__)


class MarketError(ValueError):
    pass


def positive(value):
    try:
        result = int(str(value).replace(',', '').strip())
    except (ValueError, TypeError):
        raise MarketError('금액과 수량은 정수로 입력해주세요.')
    if not 1 <= result <= MAX_MONEY:
        raise MarketError('금액과 수량은 1 이상이며 지원 범위 안이어야 합니다.')
    return result


def parse_deadline(value, now=None):
    try:
        end = datetime.strptime(value.strip(), '%Y-%m-%d %H:%M').replace(tzinfo=KST).timestamp()
    except ValueError:
        raise MarketError('마감은 한국 시간 YYYY-MM-DD HH:MM 형식으로 입력해주세요.')
    if end <= (time.time() if now is None else now):
        raise MarketError('마감은 현재보다 미래 시각으로 입력해주세요.')
    return end


class MarketStore:
    def __init__(self, db):
        self.db = db
        db.executescript('''
        CREATE TABLE IF NOT EXISTS market_panels(kind TEXT,item_id INTEGER,guild_id TEXT,channel_id TEXT,message_id TEXT,signature TEXT,PRIMARY KEY(kind,item_id));
        CREATE TABLE IF NOT EXISTS market_auctions(id INTEGER PRIMARY KEY,guild_id TEXT,channel_id TEXT,seller TEXT,title TEXT,start INTEGER,step INTEGER,ends REAL,status TEXT NOT NULL DEFAULT 'open',bidder TEXT,amount INTEGER NOT NULL DEFAULT 0,created REAL,closed REAL,review TEXT);
        CREATE INDEX IF NOT EXISTS market_auction_due ON market_auctions(status,ends);
        CREATE TABLE IF NOT EXISTS market_receipts(request TEXT PRIMARY KEY,fingerprint TEXT,result TEXT);
        CREATE TABLE IF NOT EXISTS market_bids(id INTEGER PRIMARY KEY,auction_id INTEGER,user_id TEXT,amount INTEGER,at REAL);
        CREATE TABLE IF NOT EXISTS market_notices(id INTEGER PRIMARY KEY,kind TEXT,item_id INTEGER,channel_id TEXT,payload TEXT,created REAL,attempted REAL,message_id TEXT,next_retry REAL NOT NULL DEFAULT 0,UNIQUE(kind,item_id));
        CREATE TABLE IF NOT EXISTS market_panel_cleanup(channel_id TEXT,message_id TEXT PRIMARY KEY);
        ''')

    @contextmanager
    def transaction(self):
        if self.db.in_transaction:
            raise RuntimeError('Market operation cannot join an unrelated transaction')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            yield

    def one(self, query, args=()):
        cur = self.db.execute(query, args)
        row = cur.fetchone()
        return dict(zip([d[0] for d in cur.description], row)) if row else None

    def old(self, request, fingerprint):
        r = self.db.execute('SELECT fingerprint,result FROM market_receipts WHERE request=?', (str(request),)).fetchone()
        if r:
            if r[0] != fingerprint:
                raise MarketError('이미 다른 내용으로 처리된 요청입니다.')
            return json.loads(r[1])

    def remember(self, request, fingerprint, result):
        self.db.execute('INSERT INTO market_receipts VALUES(?,?,?)', (str(request), fingerprint, json.dumps(result)))
        return result

    def notice(self, kind, item, channel, payload, now):
        self.db.execute('INSERT OR IGNORE INTO market_notices(kind,item_id,channel_id,payload,created) VALUES(?,?,?,?,?)',
                        (kind, item, str(channel), json.dumps(payload, ensure_ascii=False), now))

    def credit(self, uid, amount):
        self.db.execute('INSERT OR IGNORE INTO balances(user_id,balance) VALUES(?,0)', (str(uid),))
        if self.db.execute('UPDATE balances SET balance=balance+? WHERE user_id=? AND balance<=?',
                           (amount, str(uid), MAX_MONEY-amount)).rowcount != 1:
            raise MarketError('받는 계정의 잔액 한도를 초과해 처리할 수 없습니다.')

    def debit(self, uid, amount):
        if self.db.execute('UPDATE balances SET balance=balance-? WHERE user_id=? AND balance>=?',
                           (amount, str(uid), amount)).rowcount != 1:
            raise MarketError('마리 잔액이 부족합니다.')

    def auction(self, aid, gid):
        r = self.one('SELECT * FROM market_auctions WHERE id=? AND guild_id=?', (aid, str(gid)))
        if not r:
            raise MarketError('이 서버의 경매를 찾을 수 없습니다.')
        return r

    def create_auction(self, gid, channel, seller, title, start, step, ends, *, now=None, request):
        now = time.time() if now is None else now
        start, step = positive(start), positive(step)
        title = title.strip()
        if not title or len(title)>100 or not now < ends < 253402214400:
            raise MarketError('상품명은 1~100자, 마감은 미래 시각이어야 합니다.')
        fp = json.dumps(['create', str(gid), str(channel), str(seller), title, start, step, ends])
        with self.transaction():
            old = self.old(request, fp)
            if old: return self.auction(old['id'], gid)
            cur = self.db.execute('INSERT INTO market_auctions(guild_id,channel_id,seller,title,start,step,ends,created) VALUES(?,?,?,?,?,?,?,?)',
                                  (str(gid), str(channel), str(seller), title, start, step, ends, now))
            aid = cur.lastrowid
            self.remember(request, fp, {'id': aid})
            self.notice('auction_panel', aid, channel, {'auction': aid, 'guild': str(gid)}, now)
        return self.auction(aid, gid)

    def bid(self, aid, gid, uid, amount, request, now=None):
        uid, amount = str(uid), positive(amount)
        fp = json.dumps(['bid', aid, str(gid), uid, amount])
        with self.transaction():
            now = time.time() if now is None else now
            old = self.old(request, fp)
            if old: return old
            a = self.auction(aid, gid)
            if a['status']!='open' or now>=a['ends']:
                raise MarketError('마감된 경매입니다.')
            if uid in (a['seller'], a['bidder']):
                raise MarketError('등록자 또는 현재 최고 입찰자는 입찰할 수 없습니다.')
            expected = a['start'] if a['bidder'] is None else a['amount']+a['step']
            if amount != expected:
                raise MarketError('최고가가 변경되었습니다. 입찰 버튼을 다시 눌러 금액을 확인해주세요.')
            self.debit(uid, amount)
            if a['bidder'] is not None:
                self.credit(a['bidder'], a['amount'])
            self.db.execute('UPDATE market_auctions SET bidder=?,amount=? WHERE id=?', (uid,amount,aid))
            bid = self.db.execute('INSERT INTO market_bids(auction_id,user_id,amount,at) VALUES(?,?,?,?)', (aid,uid,amount,now)).lastrowid
            self.notice('bid',bid,a['channel_id'],{'title':a['title'],'auction':aid,'user':uid,'amount':amount},now)
            return self.remember(request, fp, {'amount':amount,'auction':aid})

    def settle_due(self, now=None):
        now = time.time() if now is None else now
        ids = self.db.execute("SELECT id,guild_id FROM market_auctions WHERE status='open' AND ends<=?",(now,)).fetchall()
        for aid,gid in ids:
            try:
                with self.transaction():
                    a = self.auction(aid,gid)
                    if a['status']!='open': continue
                    if a['bidder'] is not None: self.credit(a['seller'],a['amount'])
                    status = 'sold' if a['bidder'] is not None else 'unsold'
                    self.db.execute('UPDATE market_auctions SET status=?,closed=? WHERE id=?',(status,now,aid))
                    self.notice('closed',aid,a['channel_id'],{'title':a['title'],'auction':aid,'guild':gid,'user':a['bidder'],'amount':a['amount']},now)
            except Exception:
                log.exception('Auction %s settlement retained for retry',aid)

    def review(self, aid, gid, uid, body, request, now=None):
        now = time.time() if now is None else now
        body=body.strip();uid=str(uid)
        if not 1<=len(body)<=1000: raise MarketError('후기는 1~1,000자로 입력해주세요.')
        fp=json.dumps(['review',aid,str(gid),uid,body])
        with self.transaction():
            old=self.old(request,fp)
            if old:return old
            a=self.auction(aid,gid)
            if a['status']!='sold' or a['bidder']!=uid: raise MarketError('낙찰자만 후기를 작성할 수 있습니다.')
            if a['review'] is not None: raise MarketError('이미 후기를 등록했습니다.')
            self.db.execute('UPDATE market_auctions SET review=? WHERE id=?',(body,aid))
            self.notice('review',aid,a['channel_id'],{'title':a['title'],'auction':aid,'user':uid,'amount':a['amount'],'body':body},now)
            return self.remember(request,fp,{'ok':True})

    def raffle(self, rid, gid):
        r=self.one('SELECT * FROM raffle_tickets WHERE id=? AND guild_id=?',(rid,str(gid)))
        if not r:raise MarketError('이 서버의 추첨권을 찾을 수 없습니다.')
        return r

    def buy_raffle(self, rid, gid, uid, quantity, request):
        uid,gid=str(uid),str(gid);quantity=positive(quantity)
        fp=json.dumps(['raffle',rid,gid,uid,quantity])
        now=datetime.now(KST);start=now.replace(hour=0,minute=0,second=0,microsecond=0)
        with self.transaction():
            old=self.old(request,fp)
            if old:return old
            r=self.raffle(rid,gid)
            if r['status']!='active':raise MarketError('삭제되었거나 추첨이 마감된 추첨권입니다.')
            if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='mari_web_draws'").fetchone():
                if self.db.execute('SELECT 1 FROM mari_web_draws WHERE raffle_id=?',(rid,)).fetchone():
                    raise MarketError('이미 추첨이 완료된 추첨권입니다.')
            count=self.db.execute('SELECT COALESCE(SUM(quantity),0) FROM raffle_purchases WHERE raffle_id=? AND guild_id=? AND user_id=? AND purchased_at>=? AND purchased_at<?',
                                  (rid,gid,uid,start.isoformat(),(start+timedelta(days=1)).isoformat())).fetchone()[0]
            if count+quantity>r['daily_limit']:raise MarketError(f"오늘은 {max(0,r['daily_limit']-count)}장까지 더 구매할 수 있습니다.")
            total=positive(r['price']*quantity)
            self.debit(uid,total)
            self.db.execute('INSERT INTO raffle_purchases(raffle_id,guild_id,user_id,quantity,total_amount,purchased_at) VALUES(?,?,?,?,?,?)',
                            (rid,gid,uid,quantity,total,now.isoformat()))
            return self.remember(request,fp,{'total':total,'quantity':quantity,'today':count+quantity,'title':r['title']})

    def delete_raffle(self,rid,gid,uid,admin):
        with self.transaction():
            r=self.raffle(rid,gid)
            if str(uid)!=r['created_by'] and not admin:raise MarketError('등록자 또는 서버 관리자만 삭제할 수 있습니다.')
            self.db.execute("UPDATE raffle_tickets SET status='deleted',deleted_at=? WHERE id=?",(datetime.now(KST).isoformat(),rid))

    def publish_raffle(self,rid,gid,channel):
        with self.transaction():
            self.raffle(rid,gid)
            self.notice('raffle_panel',rid,channel,{'raffle':rid,'guild':str(gid)},time.time())


async def reply(interaction, text):
    if interaction.response.is_done():
        await interaction.followup.send(text,ephemeral=True,allowed_mentions=discord.AllowedMentions.none())
    else:
        await interaction.response.send_message(text,ephemeral=True,allowed_mentions=discord.AllowedMentions.none())


class SafeView(discord.ui.View):
    async def interaction_check(self,i):
        if i.guild is None or i.user.bot:
            await reply(i,'서버 구성원만 이용할 수 있습니다.');return False
        return True

    async def on_error(self,i,error,item):
        if isinstance(error,MarketError):await reply(i,str(error))
        else:
            log.error('Market interaction failed',exc_info=error)
            await reply(i,'처리 상태를 확인하지 못했습니다. 잠시 후 현황을 확인해주세요.')


class SafeModal(discord.ui.Modal):
    async def on_error(self,i,error):
        if isinstance(error,MarketError):await reply(i,str(error))
        else:
            log.error('Market modal failed',exc_info=error)
            await reply(i,'처리 상태를 확인하지 못했습니다. 잠시 후 현황을 확인해주세요.')


class PurchaseModal(SafeModal):
    def __init__(self,market,rid):
        super().__init__(title='추첨권 구매')
        self.market,self.rid=market,rid
        self.quantity=discord.ui.TextInput(label='구매 수량',placeholder='예: 3',max_length=6)
        self.add_item(self.quantity)

    async def on_submit(self,i):
        if i.guild is None or i.user.bot:raise MarketError('서버 구성원만 구매할 수 있습니다.')
        r=self.market.store.buy_raffle(self.rid,i.guild.id,i.user.id,self.quantity.value,i.id)
        await reply(i,f"**{discord.utils.escape_markdown(r['title'])}** {r['quantity']:,}장 구매 완료\n차감: **{r['total']:,}마리** · 오늘 구매: {r['today']:,}장")


class RafflePanel(SafeView):
    def __init__(self,market,rid,active=True):
        super().__init__(timeout=None);self.market,self.rid=market,rid
        for label,action,style in [('구매',self.buy,discord.ButtonStyle.success),('현황',self.status,discord.ButtonStyle.secondary),('삭제',self.delete,discord.ButtonStyle.danger)]:
            b=discord.ui.Button(label=label,style=style,custom_id=f'mari:raffle:{rid}:{label}',disabled=label=='구매' and not active)
            b.callback=action;self.add_item(b)

    async def buy(self,i):
        r=self.market.store.raffle(self.rid,i.guild.id)
        if r['status']!='active':raise MarketError('판매가 마감된 추첨권입니다.')
        await i.response.send_modal(PurchaseModal(self.market,self.rid))

    async def status(self,i):
        self.market.store.raffle(self.rid,i.guild.id)
        view=RaffleStatus(self.market,self.rid,i.guild.id,i.user.id)
        await i.response.send_message(embed=view.embed(),view=view,ephemeral=True,allowed_mentions=discord.AllowedMentions.none())

    async def delete(self,i):
        r=self.market.store.raffle(self.rid,i.guild.id)
        if str(i.user.id)!=r['created_by'] and not i.user.guild_permissions.administrator:
            raise MarketError('등록자 또는 서버 관리자만 삭제할 수 있습니다.')
        view=DeleteConfirm(self.market,self.rid,i.user.id)
        await i.response.send_message('패널을 삭제하고 판매를 종료할까요? 구매·추첨 기록은 보존되며 자동 환급하지 않습니다.',view=view,ephemeral=True)


class DeleteConfirm(SafeView):
    def __init__(self,market,rid,uid):
        super().__init__(timeout=120);self.market,self.rid,self.uid=market,rid,uid

    @discord.ui.button(label='삭제 확인',style=discord.ButtonStyle.danger)
    async def confirm(self,i,button):
        if i.user.id!=self.uid:raise MarketError('본인의 확인 화면을 이용해주세요.')
        self.market.store.delete_raffle(self.rid,i.guild.id,i.user.id,i.user.guild_permissions.administrator)
        await i.response.edit_message(content='판매 종료 처리했습니다. 공개 패널을 삭제합니다.',view=None)
        await self.market.refresh_panels()


class RaffleStatus(SafeView):
    def __init__(self,market,rid,gid,uid):
        super().__init__(timeout=180);self.market,self.rid,self.gid,self.uid=market,rid,gid,uid;self.page=0

    def embed(self):
        s=self.market.store;r=s.raffle(self.rid,self.gid)
        rows=s.db.execute('SELECT user_id,SUM(quantity),SUM(total_amount) FROM raffle_purchases WHERE raffle_id=? AND guild_id=? GROUP BY user_id ORDER BY SUM(quantity) DESC,user_id',(self.rid,str(self.gid))).fetchall()
        pages=max(1,(len(rows)+14)//15);self.page=min(self.page,pages-1)
        e=discord.Embed(title=f"🎟 {r['title']} · 구매 현황",color=0xf1c40f)
        e.description='\n'.join(f"{self.page*15+n+1}. <@{u}> — **{q:,}장** · {v:,}마리" for n,(u,q,v) in enumerate(rows[self.page*15:self.page*15+15])) or '아직 구매자가 없습니다.'
        e.add_field(name='총 판매량',value=f"{sum(r[1] for r in rows):,}장")
        e.add_field(name='총 구매 금액',value=f"{sum(r[2] for r in rows):,}마리")
        e.set_footer(text=f'{self.page+1}/{pages} 페이지 · 웹·디스코드 구매 통합')
        self.children[0].disabled=self.page==0;self.children[1].disabled=self.page>=pages-1
        return e

    async def turn(self,i,delta):
        if i.user.id!=self.uid:raise MarketError('본인의 현황 화면을 열어주세요.')
        self.page=max(0,self.page+delta)
        await i.response.edit_message(embed=self.embed(),view=self)

    @discord.ui.button(label='이전')
    async def previous(self,i,b):await self.turn(i,-1)

    @discord.ui.button(label='다음')
    async def next(self,i,b):await self.turn(i,1)


class AuctionCreate(SafeModal):
    def __init__(self,market):
        super().__init__(title='경매 등록');self.market=market
        self.product=discord.ui.TextInput(label='상품명',max_length=100)
        self.price=discord.ui.TextInput(label='시작가 (마리)',placeholder='예: 1000000',max_length=19)
        self.step=discord.ui.TextInput(label='호찰가 (입찰 증가액, 마리)',placeholder='예: 100000',max_length=19)
        self.end=discord.ui.TextInput(label='마감일시 (한국 시간)',placeholder='예: 2026-10-01 21:00',max_length=16)
        for item in (self.product,self.price,self.step,self.end):self.add_item(item)

    async def on_submit(self,i):
        if i.guild is None or i.user.bot:raise MarketError('서버 구성원만 등록할 수 있습니다.')
        perms=i.channel.permissions_for(i.guild.me)
        if not (perms.send_messages and perms.embed_links and perms.read_message_history):
            raise MarketError('이 채널에서 봇의 메시지 전송·임베드·메시지 기록 보기 권한이 필요합니다.')
        a=self.market.store.create_auction(i.guild.id,i.channel_id,i.user.id,self.product.value,self.price.value,self.step.value,parse_deadline(self.end.value),request=i.id)
        await reply(i,f"경매 #{a['id']} 등록 완료. 이 채널에 공개 패널을 게시합니다.")
        await self.market.flush()


class AuctionPanel(SafeView):
    def __init__(self,market,aid,status='open',reviewed=False):
        super().__init__(timeout=None);self.market,self.aid=market,aid
        if status=='open':
            b=discord.ui.Button(label='입찰하기',emoji='🔨',style=discord.ButtonStyle.success,custom_id=f'mari:auction:{aid}:bid');b.callback=self.bid;self.add_item(b)
        elif status=='sold':
            b=discord.ui.Button(label='후기 등록 완료' if reviewed else '낙찰 후기 쓰기',emoji='✍️',style=discord.ButtonStyle.secondary if reviewed else discord.ButtonStyle.primary,custom_id=f'mari:auction:{aid}:review',disabled=reviewed);b.callback=self.review;self.add_item(b)

    async def bid(self,i):
        a=self.market.store.auction(self.aid,i.guild.id)
        if a['status']!='open' or time.time()>=a['ends']:raise MarketError('마감된 경매입니다.')
        if str(i.user.id) in (a['seller'],a['bidder']):raise MarketError('등록자 또는 현재 최고 입찰자는 입찰할 수 없습니다.')
        amount=positive(a['start'] if a['bidder'] is None else a['amount']+a['step'])
        await i.response.send_message(f"**{amount:,}마리**에 입찰할까요?\n입찰금은 즉시 보관되며, 다른 사람이 상위 입찰하면 전액 환급됩니다.",view=BidConfirm(self.market,self.aid,i.user.id,amount),ephemeral=True)

    async def review(self,i):
        a=self.market.store.auction(self.aid,i.guild.id)
        if a['status']!='sold' or a['bidder']!=str(i.user.id):raise MarketError('낙찰자만 후기를 작성할 수 있습니다.')
        if a['review'] is not None:raise MarketError('이미 후기를 등록했습니다.')
        await i.response.send_modal(ReviewModal(self.market,self.aid))


class BidConfirm(SafeView):
    def __init__(self,market,aid,uid,amount):
        super().__init__(timeout=120);self.market,self.aid,self.uid,self.amount=market,aid,uid,amount

    @discord.ui.button(label='이 금액으로 입찰',style=discord.ButtonStyle.success)
    async def confirm(self,i,b):
        if i.user.id!=self.uid:raise MarketError('본인의 확인 화면을 이용해주세요.')
        result=self.market.store.bid(self.aid,i.guild.id,i.user.id,self.amount,i.id)
        await i.response.edit_message(content=f"{result['amount']:,}마리 입찰 완료. 마감까지 최고가이면 낙찰됩니다.",view=None)
        await self.market.flush()


class ReviewModal(SafeModal):
    def __init__(self,market,aid):
        super().__init__(title='낙찰 후기 등록');self.market,self.aid=market,aid
        self.body=discord.ui.TextInput(label='후기 (공개 게시, 1회 작성)',style=discord.TextStyle.paragraph,max_length=1000)
        self.add_item(self.body)

    async def on_submit(self,i):
        if i.guild is None or i.user.bot:raise MarketError('서버 구성원만 작성할 수 있습니다.')
        self.market.store.review(self.aid,i.guild.id,i.user.id,self.body.value,i.id)
        await reply(i,'후기를 등록했습니다. 경매 채널에 공개됩니다.')
        await self.market.flush()


class Market:
    def __init__(self,bot,db):
        self.bot,self.store=bot,MarketStore(db);self.lock=asyncio.Lock();self.task=None

    def raffle_embed(self,r):
        q,v=self.store.db.execute('SELECT COALESCE(SUM(quantity),0),COALESCE(SUM(total_amount),0) FROM raffle_purchases WHERE raffle_id=?',(r['id'],)).fetchone()
        e=discord.Embed(title=f"🎟 {r['title']}",description='아래 구매 버튼에서 수량을 입력하세요. 웹 구매와 한도가 합산됩니다.' if r['status']=='active' else '추첨이 마감되었습니다. 구매 현황은 계속 확인할 수 있습니다.',color=0xf1c40f)
        for name,value in [('1장 가격',f"{r['price']:,}마리"),('하루 구매 한도',f"{r['daily_limit']:,}장"),('총 판매량',f'{q:,}장'),('총 구매 금액',f'{v:,}마리'),('등록자',f"<@{r['created_by']}>")]:e.add_field(name=name,value=value)
        e.set_footer(text=f"추첨권 #{r['id']} · 삭제 전까지 유지")
        return e

    def auction_embed(self, a):
        status = a['status']
        labels = {'open': '입찰 진행 중', 'sold': '낙찰 완료', 'unsold': '입찰 없이 마감'}
        colors = {'open': 0x8DDBC0, 'sold': 0xEDC877, 'unsold': 0x89919E}
        count = self.store.db.execute('SELECT COUNT(*) FROM market_bids WHERE auction_id=?', (a['id'],)).fetchone()[0]
        e = discord.Embed(title=a['title'], color=colors[status])
        e.set_author(name=f"MARI AUCTION  ·  {labels[status]}")
        if status == 'open':
            amount = a['amount'] if a['bidder'] else a['start']
            caption = '현재 최고가' if a['bidder'] else '첫 입찰을 기다리고 있어요'
            e.description = f"{caption}\n**{amount:,} 마리**"
            next_amount = a['amount'] + a['step'] if a['bidder'] else a['start']
            e.add_field(name='다음 입찰가', value=f"**{next_amount:,} 마리**", inline=True)
            e.add_field(name='남은 시간', value=f"<t:{int(a['ends'])}:R>", inline=True)
            e.add_field(name='최고 입찰자', value=f"<@{a['bidder']}>" if a['bidder'] else '아직 없어요 · 첫 주인공이 되어보세요', inline=False)
        elif status == 'sold':
            e.description = f"🏆 **낙찰을 축하합니다!**\n**{a['amount']:,} 마리**에 경매가 마감됐어요."
            e.add_field(name='낙찰자', value=f"<@{a['bidder']}>", inline=True)
            e.add_field(name='정산', value='등록자에게 낙찰금 지급 완료', inline=True)
        else:
            e.description = '이번 경매는 입찰 없이 마감됐어요.'
        e.add_field(name='경매 조건', value=f"시작가 **{a['start']:,} 마리**  ·  호찰가 **+{a['step']:,} 마리**", inline=False)
        e.add_field(name='마감 일시', value=f"<t:{int(a['ends'])}:F>", inline=True)
        e.add_field(name='등록자', value=f"<@{a['seller']}>", inline=True)
        if status == 'open':
            e.add_field(name='입찰 안내', value='아래 버튼에서 금액을 확인한 뒤 입찰하세요.\n더 높은 입찰이 들어오면 보관된 마리는 전액 돌려드려요.', inline=False)
        elif status == 'sold':
            e.add_field(name='낙찰 후기', value='후기 등록이 완료됐어요. 감사합니다!' if a['review'] is not None else '낙찰자만 아래 버튼으로 후기를 한 번 남길 수 있어요.', inline=False)
        e.set_footer(text=f"경매 #{a['id']}  ·  총 {count:,}회 입찰  ·  마리 경매장")
        return e

    def auction_notice_embed(self, kind, p):
        colors = {'bid': 0x8DDBC0, 'closed': 0xEDC877 if p['user'] else 0x89919E, 'review': 0xB5A5E8}
        labels = {'bid': '새로운 최고 입찰', 'closed': '낙찰 완료' if p['user'] else '입찰 없이 마감', 'review': '낙찰자의 후기'}
        e = discord.Embed(title=p['title'], color=colors[kind])
        e.set_author(name=f"MARI AUCTION  ·  {labels[kind]}")
        if kind == 'review':
            e.description = p['body']
            e.add_field(name='작성자', value=f"<@{p['user']}>", inline=True)
            e.add_field(name='낙찰 금액', value=f"{p['amount']:,} 마리", inline=True)
        elif p['user']:
            e.description = f"{'🔨' if kind == 'bid' else '🏆'} **{p['amount']:,} 마리**"
            e.add_field(name='최고 입찰자' if kind == 'bid' else '낙찰자', value=f"<@{p['user']}>", inline=True)
            e.add_field(name='안내', value='이전 입찰금은 전액 환급됩니다.' if kind == 'bid' else '등록자에게 낙찰금이 지급됐어요.\n낙찰자는 아래에서 후기를 남겨주세요.', inline=False)
        else:
            e.description = '입찰자가 없어 이번 경매는 유찰됐어요.'
        e.set_footer(text=f"경매 #{p['auction']}  ·  마리 경매장")
        return e

    async def channel(self,cid):
        return self.bot.get_channel(int(cid)) or await self.bot.fetch_channel(int(cid))

    def register(self):
        for rid, in self.store.db.execute('SELECT id FROM raffle_tickets'):
            self.bot.add_view(RafflePanel(self,rid))
        for aid,status,review in self.store.db.execute('SELECT id,status,review FROM market_auctions'):
            # Register both callbacks; database authorization remains authoritative.
            self.bot.add_view(AuctionPanel(self,aid,'open'))
            self.bot.add_view(AuctionPanel(self,aid,'sold',review is not None))

    async def flush(self):
        async with self.lock:
            notices=self.store.db.execute('SELECT id,kind,item_id,channel_id,payload,created,attempted FROM market_notices WHERE message_id IS NULL AND next_retry<=? ORDER BY id LIMIT 50',(time.time(),)).fetchall()
            for nid,kind,item,cid,raw,created,attempted in notices:
                try:
                    channel=await self.channel(cid);p=json.loads(raw);view=None
                    marker=f'mari-market:{nid}'
                    found=None
                    if attempted is not None:
                        async for msg in channel.history(limit=None,after=datetime.fromtimestamp(attempted-5,KST)):
                            if msg.author.id==self.bot.user.id and any(e.footer.text==marker for e in msg.embeds):
                                found=msg;break
                    if kind=='raffle_panel':
                        r=self.store.raffle(item,p['guild'])
                        if r['status']=='deleted':
                            with self.store.db:self.store.db.execute("UPDATE market_notices SET message_id='cancelled' WHERE id=?",(nid,))
                            continue
                        e=self.raffle_embed(r);view=RafflePanel(self,item,r['status']=='active');self.bot.add_view(view)
                    elif kind in ('auction_panel','auction_bump'):
                        if kind=='auction_bump':item=p['auction']
                        a=self.store.auction(item,p['guild']);e=self.auction_embed(a);view=AuctionPanel(self,item,a['status'],a['review'] is not None);self.bot.add_view(AuctionPanel(self,item,'open'));self.bot.add_view(AuctionPanel(self,item,'sold'))
                    else:
                        e=self.auction_notice_embed(kind,p)
                        if kind=='closed' and p['user']:view=AuctionPanel(self,item,'sold')
                    e.set_footer(text=marker)
                    if not found:
                        with self.store.db:self.store.db.execute('UPDATE market_notices SET attempted=? WHERE id=?',(time.time(),nid))
                        options={'silent':True} if kind=='auction_bump' else {}
                        found=await channel.send(embed=e,view=view,allowed_mentions=discord.AllowedMentions.none(),**options)
                    with self.store.db:
                        self.store.db.execute('UPDATE market_notices SET message_id=? WHERE id=?',(str(found.id),nid))
                        if kind in ('auction_panel','raffle_panel'):
                            self.store.db.execute('INSERT OR REPLACE INTO market_panels VALUES(?,?,?,?,?,NULL)',(kind,item,p['guild'],cid,str(found.id)))
                        elif kind=='auction_bump':
                            self.store.db.execute("UPDATE market_panels SET message_id=?,signature=NULL WHERE kind='auction_panel' AND item_id=? AND message_id=?",(str(found.id),item,p['previous']))
                            self.store.db.execute('INSERT OR IGNORE INTO market_panel_cleanup VALUES(?,?)',(cid,p['previous']))
                except Exception:
                    with self.store.db:self.store.db.execute('UPDATE market_notices SET next_retry=? WHERE id=?',(time.time()+60,nid))
                    log.exception('Market notice %s pending retry',nid)

    async def queue_auction_bumps(self):
        # One trailing group per channel, so multiple auctions never chase each other.
        async with self.lock:
            groups={}
            rows=self.store.db.execute("SELECT p.item_id,p.guild_id,p.channel_id,p.message_id FROM market_panels p JOIN market_auctions a ON a.id=p.item_id WHERE p.kind='auction_panel' AND a.status='open' AND a.ends>?",(time.time(),)).fetchall()
            for item,gid,cid,mid in rows:groups.setdefault(cid,[]).append((item,gid,mid))
            for cid,panels in groups.items():
                try:
                    channel=await self.channel(cid)
                    latest=next(iter([m async for m in channel.history(limit=1)]),None)
                    if latest is None or str(latest.id) in {mid for _,_,mid in panels}:continue
                    if latest.id<=max(int(mid) for _,_,mid in panels):continue
                    with self.store.db:
                        for item,gid,mid in panels:
                            self.store.notice('auction_bump',int(mid),cid,{'auction':item,'guild':gid,'previous':mid},time.time())
                except Exception:log.exception('Auction bottom placement failed: %s',cid)

    async def cleanup_panels(self):
        # Persist cleanup before removing old bot messages; retries survive restarts.
        async with self.lock:
            for cid,mid in self.store.db.execute('SELECT channel_id,message_id FROM market_panel_cleanup').fetchall():
                try:
                    channel=await self.channel(cid)
                    try:await channel.get_partial_message(int(mid)).delete()
                    except discord.NotFound:pass
                    with self.store.db:self.store.db.execute('DELETE FROM market_panel_cleanup WHERE message_id=?',(mid,))
                except Exception:log.exception('Old auction panel cleanup pending: %s',mid)

    async def refresh_panels(self):
        async with self.lock:
            rows=self.store.db.execute('SELECT kind,item_id,guild_id,channel_id,message_id,signature FROM market_panels').fetchall()
            for kind,item,gid,cid,mid,signature in rows:
                try:
                    r=self.store.raffle(item,gid) if kind=='raffle_panel' else self.store.auction(item,gid)
                    if kind=='raffle_panel' and r['status']=='deleted':
                        channel=await self.channel(cid)
                        try:await channel.get_partial_message(int(mid)).delete()
                        except discord.NotFound:pass
                        with self.store.db:self.store.db.execute('DELETE FROM market_panels WHERE kind=? AND item_id=?',(kind,item))
                        continue
                    e=self.raffle_embed(r) if kind=='raffle_panel' else self.auction_embed(r)
                    view=RafflePanel(self,item,r['status']=='active') if kind=='raffle_panel' else AuctionPanel(self,item,r['status'],r['review'] is not None)
                    sig=json.dumps([e.to_dict(),[(b.label,b.disabled) for b in view.children]],sort_keys=True)
                    if sig==signature:continue
                    channel=await self.channel(cid)
                    await channel.get_partial_message(int(mid)).edit(embed=e,view=view,allowed_mentions=discord.AllowedMentions.none())
                    with self.store.db:self.store.db.execute('UPDATE market_panels SET signature=? WHERE kind=? AND item_id=?',(sig,kind,item))
                except discord.NotFound:
                    with self.store.db:self.store.db.execute('DELETE FROM market_panels WHERE kind=? AND item_id=?',(kind,item))
                except Exception:log.exception('Market panel refresh failed: %s %s',kind,item)

    async def run(self):
        while not self.bot.is_closed():
            try:
                self.store.settle_due()
            except Exception:log.exception('Market settlement pass failed')
            for action in (self.queue_auction_bumps,self.flush,self.refresh_panels,self.cleanup_panels):
                try:await action()
                except Exception:log.exception('Market maintenance failed')
            await asyncio.sleep(10)

    def start(self):
        if self.task is None or self.task.done():
            self.register();self.task=asyncio.create_task(self.run())


def install(bot,db):
    market=getattr(bot,'mari_market',None)
    if market is None:
        market=Market(bot,db);bot.mari_market=market
    market.start()
    return market
