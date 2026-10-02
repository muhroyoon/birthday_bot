"""Atomic attendance payouts; pending attendance is persisted before calling this."""

REWARDS = {1: 5_000_000, 2: 3_000_000, 3: 1_000_000}


def reward_amount(rank):
    return REWARDS.get(rank, 0)


def pay_reward(db, guild_id, day, user_id, rank):
    amount = reward_amount(rank)
    if not amount:
        return 0
    if db.in_transaction:
        raise RuntimeError('Attendance payout requires its own transaction')
    with db:
        db.execute('''CREATE TABLE IF NOT EXISTS attendance_reward_payments (
            guild_id TEXT NOT NULL, day TEXT NOT NULL, user_id TEXT NOT NULL,
            rank INTEGER NOT NULL, amount INTEGER NOT NULL,
            paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(guild_id, day, user_id), UNIQUE(guild_id, day, rank))''')
        inserted = db.execute('''INSERT OR IGNORE INTO attendance_reward_payments
            (guild_id, day, user_id, rank, amount) VALUES (?, ?, ?, ?, ?)''',
            (str(guild_id), day, str(user_id), rank, amount)).rowcount
        if not inserted:
            return 0
        db.execute('INSERT OR IGNORE INTO balances(user_id, balance) VALUES (?, 0)', (str(user_id),))
        db.execute('UPDATE balances SET balance=balance+? WHERE user_id=?', (amount, str(user_id)))
    return amount
