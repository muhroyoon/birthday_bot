"""Private market rules. No database writes or public API serialization.

Magnitudes are basis points (100 = 1%). Thresholds are cumulative out of
1,000. Keep the three random draws in direction/band/magnitude order.
"""
from datetime import timedelta, timezone
from fractions import Fraction
import secrets

KST = timezone(timedelta(hours=9))
PRICE_INTERVAL_MINUTES = 10
REGIME_INTERVAL_HOURS = 6
SIDEWAYS_PERCENT = 35
MOVE_BANDS = ((800, 80, 400), (980, 401, 1500), (1000, 1501, 3500))
LEGACY_MOVE_BANDS = ((500, 300, 1000), (850, 1001, 2500),
                     (980, 2501, 4500), (1000, 4501, 7000))
# Row order is persisted as an integer in mari_web_five_state_regimes.
# Do not reorder: surge, bull, sideways, bear, crash.
REGIME_THRESHOLDS = (10, 35, 65, 90, 100)
REGIME_PARAMETERS = ((60, False), (55, False), (50, True),
                     (45, False), (40, False))


def draw_move(bands, up_chance, sideways=False):
    rising = secrets.randbelow(100) < up_chance
    bucket = secrets.randbelow(1000)
    low, high = next((low, high) for threshold, low, high in bands
                     if bucket < threshold)
    magnitude = low + secrets.randbelow(high - low + 1)
    if sideways:
        magnitude = round(Fraction(magnitude * SIDEWAYS_PERCENT, 100))
    return magnitude if rising else Fraction(-10000 * magnitude, 10000 + magnitude)


def stock_move_bps(up_chance=50, sideways=False):
    return draw_move(MOVE_BANDS, up_chance, sideways)


def legacy_stock_move_bps(up_chance=50):
    return draw_move(LEGACY_MOVE_BANDS, up_chance)


def draw_regime():
    draw = secrets.randbelow(100)
    return next(index for index, threshold in enumerate(REGIME_THRESHOLDS)
                if draw < threshold)


def regime_window(slot):
    local = slot.astimezone(KST)
    return local.replace(hour=local.hour // REGIME_INTERVAL_HOURS * REGIME_INTERVAL_HOURS,
                         minute=0, second=0, microsecond=0).isoformat()
