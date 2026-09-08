"""Public, aggregate game popularity with daily visitor deduplication."""
import hashlib
import re
from datetime import datetime,timedelta,timezone
GAMES=('fishing','runner','memory','tower','territory','dodge','work','blackjack','slot','baccarat','horse_race','seotda','coin','minesweeper','supply_drop','duckmong','rock_paper_scissors','number_baseball','all_in','aim','pubg','reaction','stopwatch','fortune','stocks','apple','snake','suika','2048')
KST=timezone(timedelta(hours=9))
class GameCatalog:
    def __init__(self,bridge,error):
        self.b=bridge;self.db=bridge.db;self.Error=error
        self.db.execute('CREATE TABLE IF NOT EXISTS mari_web_catalog_visits(day TEXT NOT NULL,game TEXT NOT NULL,visitor TEXT NOT NULL,PRIMARY KEY(day,game,visitor))')
        self.db.execute('PRAGMA optimize');self.db.commit()
    def today(self):return datetime.now(KST).date()
    def view(self,data,token=None):
        game=data.get('game');visitor=data.get('visitor')
        if game not in GAMES or not isinstance(visitor,str) or not re.fullmatch(r'[a-f0-9-]{36}',visitor):raise self.Error('올바른 게임 방문이 아니에요.')
        day=self.today();key=hashlib.sha256((str(day)+':'+visitor).encode()).hexdigest()
        # The same browser counts once per game/day, including before/after login.
        self.db.execute('DELETE FROM mari_web_catalog_visits WHERE day<?',((day-timedelta(days=29)).isoformat(),))
        self.db.execute('INSERT OR IGNORE INTO mari_web_catalog_visits VALUES(?,?,?)',(day.isoformat(),game,key));self.db.commit()
        return {'recorded':True}
    def popularity(self):
        cutoff=(self.today()-timedelta(days=29)).isoformat()
        counts=dict(self.db.execute('SELECT game,COUNT(*) FROM mari_web_catalog_visits WHERE day>=? GROUP BY game',(cutoff,)))
        return {'counts':{game:counts.get(game,0) for game in GAMES},'windowDays':30,'basis':'daily_visitors'}
