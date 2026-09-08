"""Versioned game-only log-return contracts. Legacy tables remain untouched."""
from decimal import Decimal, localcontext, ROUND_FLOOR, ROUND_HALF_EVEN
from functools import lru_cache
import secrets
import time

@lru_cache(maxsize=4096)
def log_price(price):
    with localcontext() as ctx:
        ctx.prec=60
        return Decimal(price).ln()

def raw_equity(cost,basis,leverage,side,price):
    with localcontext() as ctx:
        ctx.prec=60
        value=Decimal(cost)+(Decimal(cost)*log_price(price)-Decimal(basis))*leverage*(1 if side=='long' else -1)
        # Snap only numerical dust, never a material fraction of one Mari.
        nearest=value.to_integral_value(rounding=ROUND_HALF_EVEN)
        if abs(value-nearest)<Decimal('1e-30'):value=nearest
        return value

def equity(cost,basis,leverage,side,price):
    return max(0,int(raw_equity(cost,basis,leverage,side,price).to_integral_value(rounding=ROUND_FLOOR)))

def split_basis(cost,basis,closed_cost):
    with localcontext() as ctx:
        ctx.prec=60
        part=Decimal(basis)*closed_cost/cost
        return str(part),str(Decimal(basis)-part)

def position(symbol,side,leverage,qty,cost,notional,basis,price):
    with localcontext() as ctx:
        ctx.prec=60
        average=Decimal(basis)/cost
        entry=float(average.exp())
        liquidation=float((average-Decimal(1 if side=='long' else -1)/leverage).exp())
    value=equity(cost,basis,leverage,side,price)
    return dict(symbol=symbol,side=side,leverage=leverage,quantity=qty,cost=cost,notional=notional,entry=entry,liquidation=liquidation,equity=value,profit=value-cost,settlement='log')

def trade(e,member,data,request,fp):
    uid=str(member.id);symbol=data['symbol'];side=data['side'];lev=data.get('leverage',1);qty=data['quantity'];action=data['action']
    key=(uid,symbol,side,lev)
    with e.db:
        price=e.db.execute('SELECT price FROM mari_web_stocks WHERE symbol=?',(symbol,)).fetchone()[0]
        if type(data.get('price')) is not int or data['price']!=price:raise e.Error('가격이 바뀌었어요. 새 가격을 확인해주세요.',409)
        owned,cost,notional,basis=e.db.execute('SELECT qty,cost,notional,log_basis FROM mari_web_log_positions WHERE user_id=? AND symbol=? AND side=? AND leverage=?',key).fetchone() or (0,0,0,'0')
        profit=0
        if action=='open':
            if owned+qty>100000000:raise e.Error('종목·방향별 최대 보유 수량을 초과해요.')
            total=(price*qty+lev-1)//lev
            e.debit(uid,total)
            with localcontext() as ctx:
                ctx.prec=60
                basis=str(Decimal(basis)+total*log_price(price))
            owned+=qty;cost+=total;notional+=price*qty
        else:
            if qty>owned:raise e.Error('보유 포지션 수량보다 많이 종료할 수 없어요.',409)
            part_cost=cost*qty//owned;part_notional=notional*qty//owned
            part_basis,basis=split_basis(cost,basis,part_cost)
            total=equity(part_cost,part_basis,lev,side,price);profit=total-part_cost
            if e.balance(uid)+total>9000000000000000:raise e.Error('보유 가능한 마리 한도를 초과해요.')
            owned-=qty;cost-=part_cost;notional-=part_notional
            e.db.execute('INSERT INTO balances VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET balance=balance+excluded.balance',(uid,total))
        if owned:
            e.db.execute('INSERT INTO mari_web_log_positions VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(user_id,symbol,side,leverage) DO UPDATE SET qty=excluded.qty,cost=excluded.cost,notional=excluded.notional,log_basis=excluded.log_basis',(*key,owned,cost,notional,basis))
        else:e.db.execute('DELETE FROM mari_web_log_positions WHERE user_id=? AND symbol=? AND side=? AND leverage=?',key)
        e.db.execute('INSERT INTO mari_web_stock_trades VALUES(?,?,?,?,?,?,?,?,?)',(request,uid,symbol,side+'_'+action,qty,price,total,profit,time.time()))
        e.db.execute('INSERT INTO mari_web_trade_contract VALUES(?,?)',(request,'log'))
        e.db.execute('INSERT INTO mari_web_trade_leverage VALUES(?,?)',(request,lev))
        result=dict(ok=True,price=price,quantity=qty,total=total,profit=profit,balance=e.balance(uid),settlement='log')
        e.remember(request,uid,fp,result)
        return result

def liquidate(e,symbol,price,at):
    for uid,side,lev,qty,cost,basis in list(e.db.execute('SELECT user_id,side,leverage,qty,cost,log_basis FROM mari_web_log_positions WHERE symbol=?',(symbol,))):
        if raw_equity(cost,basis,lev,side,price)>0:continue
        rid='liquidate:'+secrets.token_hex(16)
        e.db.execute('INSERT INTO mari_web_stock_trades VALUES(?,?,?,?,?,?,?,?,?)',(rid,uid,symbol,side+'_liquidate',qty,price,0,-cost,at))
        e.db.execute('INSERT INTO mari_web_trade_contract VALUES(?,?)',(rid,'log'))
        e.db.execute('INSERT INTO mari_web_trade_leverage VALUES(?,?)',(rid,lev))
        e.db.execute('DELETE FROM mari_web_log_positions WHERE user_id=? AND symbol=? AND side=? AND leverage=?',(uid,symbol,side,lev))
