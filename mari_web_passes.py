"""Paid-pass behavior shared by Economy without changing its public methods.

The host supplies db, Error, receipt, debit, remember, balance and today.
Transaction boundaries and replay receipts remain owned by each operation.
"""
import json
import secrets
import time
PAID = {'aim', 'pubg', 'reaction', 'stopwatch', 'apple', 'snake', 'suika', '2048', 'fortune'}
PASS_PRICE = 150000
FORTUNE_PRICE = 1000000
PASS_LIFETIME_SECONDS = 900

class PaidPasses:

    def ticket_count(self, uid):
        row = self.db.execute('SELECT quantity FROM mari_web_game_tickets WHERE user_id=?', (str(uid),)).fetchone()
        return row[0] if row else 0

    def consume_ticket(self, uid):
        # Caller owns the transaction, including creation of the playable run.
        if self.db.execute('UPDATE mari_web_game_tickets SET quantity=quantity-1 WHERE user_id=? AND quantity>0', (str(uid),)).rowcount != 1:
            raise self.Error('게임 티켓이 부족해요. 상점에서 티켓을 구매해주세요.', 409)

    def buy_tickets(self, member, data):
        request, fp, old = self.receipt(member, data, 'tickets/buy')
        if old:
            return old
        quantity = data.get('quantity')
        if type(quantity) is not int or not 1 <= quantity <= 100:
            raise self.Error('티켓은 한 번에 1~100장 구매할 수 있어요.')
        with self.db:
            self.debit(member.id, quantity * PASS_PRICE)
            self.db.execute('INSERT INTO mari_web_game_tickets VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET quantity=quantity+excluded.quantity', (str(member.id), quantity))
            self.b.log_history(member.id, member.guild.id, '게임 티켓', str(quantity) + '장 구매', -quantity * PASS_PRICE)
            result = {'tickets': self.ticket_count(member.id), 'balance': self.balance(member.id), 'purchased': quantity, 'total': quantity * PASS_PRICE, 'price': PASS_PRICE}
            self.remember(request, member.id, fp, result)
        return result

    def start(self, member, data, game=None, create=None):
        game = game or data.get('game')
        if game not in PAID:
            raise self.Error('지원하지 않는 티켓입니다.')
        request, fp, old = self.receipt(member, data, 'pass:' + game)
        if old:
            return old
        if game == 'fortune':
            oldday = self.db.execute('SELECT result FROM mari_web_fortune_days WHERE user_id=? AND day=?', (str(member.id), self.today().isoformat())).fetchone()
            if oldday:
                return json.loads(oldday[0])
            fortune = data.get('fortune')
            if not isinstance(fortune, dict) or fortune.get('date') != self.today().isoformat():
                raise self.Error('오늘 날짜로 운세를 다시 확인해주세요.')
        price = FORTUNE_PRICE if game == 'fortune' else PASS_PRICE
        with self.db:
            if game == 'fortune':
                self.debit(member.id, price)
            else:
                self.consume_ticket(member.id)
            rid = secrets.token_urlsafe(24)
            seed = secrets.randbits(32)
            now = time.time()
            self.db.execute('INSERT INTO mari_web_passes VALUES(?,?,?,?,?,?,0,NULL)', (rid, str(member.id), str(member.guild.id), game, seed, now))
            result = {'id': rid, 'seed': seed, 'game': game, 'price': price if game == 'fortune' else 0, 'tickets': self.ticket_count(member.id), 'balance': self.balance(member.id), 'created': now}
            if create:
                result.update(create(rid, seed, now))
            if game == 'fortune':
                result['fortune'] = data['fortune']
                self.db.execute('INSERT INTO mari_web_fortune_days VALUES(?,?,?,?)', (str(member.id), self.today().isoformat(), rid, json.dumps(result, ensure_ascii=False)))
            self.remember(request, member.id, fp, result)
        return result

    def status(self, member):
        row = self.db.execute('SELECT result FROM mari_web_fortune_days WHERE user_id=? AND day=?', (str(member.id), self.today().isoformat())).fetchone()
        return {'balance': self.balance(member.id), 'tickets': self.ticket_count(member.id), 'fortune': json.loads(row[0]) if row else None, 'day': self.today().isoformat(), 'price': PASS_PRICE, 'dailyPrice': FORTUNE_PRICE}

    def ticket(self, member, data):
        row = self.db.execute('SELECT game,seed,created,submitted FROM mari_web_passes WHERE id=? AND user_id=? AND guild_id=?', (data.get('id'), str(member.id), str(member.guild.id))).fetchone()
        if not row or row[0] not in ('apple', 'snake') or time.time() - row[2] > PASS_LIFETIME_SECONDS:
            raise self.Error('이 게임의 기록이 만료됐어요.', 409)
        return {'id': data['id'], 'game': row[0], 'seed': row[1], 'created': row[2]}
