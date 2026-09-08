"""Cosmetic inventory, earned achievements, stock discussion and daily digest."""
import json
import time
from datetime import datetime,timedelta,timezone
from mari_web_adventure import GAMES
KST=timezone(timedelta(hours=9))
COLORS=['mint','blue','rose','gold','purple','cyan','orange','silver']
ITEMS=[]
for i,(name,color) in enumerate(zip(['새싹 정원','푸른 항해','장밋빛 순간','골든 아워','보랏빛 꿈','오로라','노을 산책','달빛 산책'],COLORS)):
 for kind,label in [('frame','테두리'),('background','배경'),('badge','배지')]:
  ITEMS.append(dict(id=f'{kind}-{color}',kind=kind,name=f'{name} {label}',style=color,price=(i+1)*1000000*(2 if kind=='background' else 1)))
for i,name in enumerate(['마리 산책자','치킨을 기다리며','오늘도 접속','존버의 미학','롱과 숏 사이','배당 없는 낭만','광산 야근조','손끝의 예술가','클랜 분위기 메이커','김천물류 단골','머로증권 응원단','삼성식품 시식단']):
 ITEMS.append(dict(id=f'title-shop-{i}',kind='title',name=name,style=COLORS[i%8],price=(i+1)*1500000))
ACH=[]
for g,label in GAMES.items():
 for count,title in [(1,{'fishing':'첫 입질','runner':'달리기 첫걸음','memory':'기억의 조각','tower':'신입 건축가','territory':'영역 탐험가','dodge':'탄막 입문자'}[g]),(10,{'fishing':'물가의 단골','runner':'멈추지 않는 발','memory':'인간 블랙박스','tower':'하늘의 건축가','territory':'영토 개척자','dodge':'회피 본능'}[g])]:
  ACH.append(dict(id=f'{g}-{count}',name=title,description=f'{label} {count}회 완료',stat=g,target=count))
for aid,name,desc,stat,target in [
 ('variety','다재다능','새 게임 6종 모두 완료','variety',6),('arcade50','라운지 단골','새 게임 합계 50회 완료','plays',50),
 ('arcade100','마리의 전설','새 게임 합계 100회 완료','plays',100),('work1','광산 출근','광산 작업 1회 완료','work',1),
 ('work30','성실한 광부','광산 작업 30회 완료','work',30),('work100','광산의 주인','광산 작업 100회 완료','work',100),
 ('trade1','첫 거래','주식 거래 1회','trades',1),('trade30','시장의 단골','주식 거래 30회','trades',30),
 ('trade100','거래소 터줏대감','주식 거래 100회','trades',100),('fishrare','황금빛 손맛','황금용왕어 1마리 포획','rare',1),
 ('fish20','풍어 기원','물고기 20마리 포획','fish',20),('tower10','10층의 꿈','타워 한 판 10층 완성','towerFloors',10),
 ('memory5','기억의 달인','기억력 한 판 5단계 통과','memoryLevel',5),('runner500','질주의 끝','장애물 달리기 500점 달성','runnerBest',500),
 ('dodge500','빗속의 춤','탄막 피하기 500점 달성','dodgeBest',500),('territory75','정복자','땅따먹기 75% 점령','territoryCells',210)]:
 ACH.append(dict(id=aid,name=name,description=desc,stat=stat,target=target))
for game,name,title in [('blackjack','블랙잭','21의 문턱'),('slot','슬롯','릴의 속삭임'),('baccarat','바카라','테이블의 손님'),('horse_race','경마','트랙의 응원단'),('seotda','섯다','패를 읽는 눈'),('coin','동전','운명의 양면'),('minesweeper','지뢰찾기','조심스러운 한 칸'),('supply_drop','보급','보급 상자 개봉자'),('duckmong','덕몽','오리 탐정'),('rock_paper_scissors','가위바위보','첫 번째 승부수'),('number_baseball','숫자야구','숫자의 단서'),('all_in','몰빵게임','함께 건 한 판'),('aim','에임 연습','표적을 향해'),('apple','사과게임','열의 발견'),('snake','지렁이 게임','첫 먹이'),('suika','수박게임','과일의 연금술'),('2048','2048','숫자를 합치다'),('reaction','반응속도','찰나의 순간'),('stopwatch','스톱워치','시간을 잡다'),('fortune','배그 운세','오늘의 치킨운')]:
 ACH.append(dict(id='legacy-'+game,name=title,description=name+' 웹 기록 1회'+(' 참여' if game in ('all_in','fortune') else ' 완료'),stat='legacy-'+game,target=1))
for a in ACH:
 ITEMS.append(dict(id='earned-'+a['id'],kind='title',name=a['name'],style='gold',price=None,achievement=a['id']))
LEGACY_ACH=ACH
TIERS=[('bronze','브론즈'),('silver','실버'),('gold','골드'),('master','마스터')]
TRACKS=[]
special={
 'legacy-fortune':([7,30,100,365],'오늘의 치킨운','운세 확인 일수'),
 'legacy-all_in':([5,20,60,180],'함께 건 한 판','몰빵 참여 횟수'),
 'variety':([1,3,5,6],'여섯 가지 모험','서로 다른 새 게임 완료'),
 'plays':([50,250,1000,5000],'라운지의 전설','새 게임 완료 횟수'),
 'work':([10,100,500,2000],'광산 개척자','작업 완료 횟수'),
 'trades':([20,200,1000,5000],'시장의 기록','주식 거래 횟수'),
 'rare':([3,10,30,100],'황금빛 손맛','황금용왕어 포획'),
 'fish':([10,100,500,2000],'풍어의 기록','물고기 포획'),
 'towerFloors':([5,10,18,25],'하늘의 건축가','한 판 최고 층수'),
 'memoryLevel':([2,5,8,12],'기억의 달인','한 판 통과 단계'),
 'runnerBest':([100,300,500,800],'멈추지 않는 질주','한 판 최고 점수'),
 'dodgeBest':([100,300,500,800],'탄막 속의 춤','한 판 최고 점수'),
 'territoryCells':([90,130,170,210],'영토 개척자','한 판 최대 점령 칸'),
}
for a in LEGACY_ACH:
 stat=a['stat']
 if any(t['id']==stat for t in TRACKS):continue
 targets,name,description=special.get(stat,([10,50,200,1000],GAMES.get(stat,a['name']),a['description'].replace(' 1회 완료','').replace(' 1회 참여','').replace(' 웹 기록','')+' 완료 횟수'))
 TRACKS.append(dict(id=stat,name=name,description=description,targets=targets))
ACH=[]
for track in TRACKS:
 for index,(tier,label) in enumerate(TIERS):
  a=dict(id=track['id']+'-'+tier,name=track['name']+' · '+label,description=track['description'],stat=track['id'],target=track['targets'][index],tier=tier)
  ACH.append(a);ITEMS.append(dict(id='tier-'+a['id'],kind='title',name=a['name'],style=tier,price=None,achievement=a['id'],tier=tier))
ITEM_MAP={i['id']:i for i in ITEMS}

class Social:
 def __init__(self,b,error):
  self.b=b;self.db=b.db;self.Error=error
  self.db.executescript('''
  CREATE TABLE IF NOT EXISTS mari_web_cosmetics(user_id TEXT,item TEXT,at REAL,PRIMARY KEY(user_id,item));
  CREATE TABLE IF NOT EXISTS mari_web_style(user_id TEXT PRIMARY KEY,title TEXT DEFAULT '',frame TEXT DEFAULT '',background TEXT DEFAULT '',badge TEXT DEFAULT '',bio TEXT DEFAULT '');
  CREATE TABLE IF NOT EXISTS mari_web_stock_talk(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT,guild_id TEXT,symbol TEXT,body TEXT,name TEXT,avatar TEXT,at REAL,deleted INTEGER DEFAULT 0);
  CREATE INDEX IF NOT EXISTS stock_talk_lookup ON mari_web_stock_talk(symbol,deleted,id);
  CREATE TABLE IF NOT EXISTS mari_web_daily_paper(day TEXT PRIMARY KEY,body TEXT,published REAL);
  ''');self.db.commit()
  if 'title' not in {r[1] for r in self.db.execute('PRAGMA table_info(mari_web_stock_talk)')}:
   self.db.execute("ALTER TABLE mari_web_stock_talk ADD COLUMN title TEXT NOT NULL DEFAULT ''");self.db.commit()
 def exists(self,table):return bool(self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())
 def stats(self,uid):
  stats=dict(plays=0,variety=0,work=0,trades=0,fish=0,rare=0,towerFloors=0,memoryLevel=0,runnerBest=0,dodgeBest=0,territoryCells=0)
  if self.exists('mari_web_adventures'):
   for game,count,best in self.db.execute('SELECT game,COUNT(*),MAX(score) FROM mari_web_adventures WHERE user_id=? AND done=1 GROUP BY game',(uid,)):
    stats[game]=count;stats['plays']+=count;stats['variety']+=1
    if game in ('runner','dodge'):stats[game+'Best']=best
   for (raw,) in self.db.execute("SELECT state FROM mari_web_adventures WHERE user_id=? AND game IN ('fishing','tower','memory','territory')",(uid,)):
    s=json.loads(raw);fish=s.get('fish',[]);stats['fish']+=len(fish);stats['rare']+=sum(f['rarity']==3 for f in fish)
    stats['towerFloors']=max(stats['towerFloors'],len(s.get('blocks',[]))-1)
    stats['memoryLevel']=max(stats['memoryLevel'],s.get('level',1)-1)
    stats['territoryCells']=max(stats['territoryCells'],len(s.get('claimed',[])))
  if self.exists('mari_web_work_jobs'):stats['work']=self.db.execute('SELECT COUNT(*) FROM mari_web_work_jobs WHERE user_id=? AND finished_day IS NOT NULL',(uid,)).fetchone()[0]
  stats['trades']=self.db.execute('SELECT COUNT(*) FROM mari_web_stock_trades WHERE user_id=?',(uid,)).fetchone()[0]
  for game,count in self.db.execute("SELECT game,COUNT(*) FROM mari_web_rounds WHERE user_id=? AND status='done' GROUP BY game",(uid,)):stats['legacy-'+game]=count
  if self.exists('mari_web_training_runs'):
   for mode,count in self.db.execute('SELECT mode,COUNT(*) FROM mari_web_training_runs WHERE user_id=? AND submitted=1 GROUP BY mode',(uid,)):
    key='legacy-'+('aim' if mode in ('flick','grid','precision','path') else mode);stats[key]=stats.get(key,0)+count
  stats['legacy-fortune']=self.db.execute('SELECT COUNT(*) FROM mari_web_fortune_days WHERE user_id=?',(uid,)).fetchone()[0]
  if self.exists('all_in_entries'):stats['legacy-all_in']=self.db.execute('SELECT COUNT(*) FROM all_in_entries WHERE user_id=?',(uid,)).fetchone()[0]
  return stats
 def decoration(self,uid):
  row=self.db.execute('SELECT title,frame,background,badge,bio FROM mari_web_style WHERE user_id=?',(str(uid),)).fetchone() or ('','','','','')
  return {**{kind:ITEM_MAP.get(item) for kind,item in zip(('title','frame','background','badge'),row[:4])},'bio':row[4]}
 def public_profile(self,data):
  uid=data.get('user')
  if not isinstance(uid,str) or not uid.isdigit():raise self.Error('프로필을 확인해주세요.')
  member=None
  for gid in self.b.guild_ids:
   guild=self.b.bot.get_guild(gid)
   if guild:
    member=guild.get_member(int(uid))
    if member and not member.bot:break
  if not member or member.bot:raise self.Error('연동 서버의 프로필을 찾을 수 없어요.',404)
  titles=[ITEM_MAP[r[0]] for r in self.db.execute('SELECT item FROM mari_web_cosmetics WHERE user_id=?',(uid,)) if r[0] in ITEM_MAP and ITEM_MAP[r[0]].get('achievement')]
  return {'name':member.display_name,'avatar':str(member.display_avatar.url),'guild':member.guild.name,'style':self.decoration(uid),'titles':titles}
 def profile(self,member):
  uid=str(member.id);stats=self.stats(uid);owned={r[0] for r in self.db.execute('SELECT item FROM mari_web_cosmetics WHERE user_id=?',(uid,))}
  earned={'earned-'+a['id'] for a in LEGACY_ACH if stats.get(a['stat'],0)>=a['target']}
  earned|={'tier-'+a['id'] for a in ACH if stats.get(a['stat'],0)>=a['target']}
  with self.db:
   for item in earned:self.db.execute('INSERT OR IGNORE INTO mari_web_cosmetics VALUES(?,?,?)',(uid,item,time.time()))
  owned|=earned
  tracks=[]
  for track in TRACKS:
   levels=[{'tier':tier,'label':label,'target':track['targets'][i],'item':'tier-'+track['id']+'-'+tier,'earned':'tier-'+track['id']+'-'+tier in owned} for i,(tier,label) in enumerate(TIERS)]
   progress=stats.get(track['id'],0)
   tracks.append({**track,'progress':progress,'levels':levels})
  return {'items':ITEMS,'owned':sorted(owned),'style':self.decoration(uid),'balance':self.b.economy.balance(uid),'tracks':tracks,
          'achievements':[{**a,'progress':stats.get(a['stat'],0),'earned':'tier-'+a['id'] in owned} for a in ACH]}
 def buy(self,member,data):
  request,fp,old=self.b.economy.receipt(member,data,'cosmetics/buy')
  if old:return self.profile(member)
  item=ITEM_MAP.get(data.get('item'));uid=str(member.id)
  if not item or item['price'] is None:raise self.Error('상점에서 구매할 수 없는 아이템이에요.')
  with self.db:
   if not self.db.execute('SELECT 1 FROM mari_web_cosmetics WHERE user_id=? AND item=?',(uid,item['id'])).fetchone():
    self.b.economy.debit(uid,item['price']);self.db.execute('INSERT INTO mari_web_cosmetics VALUES(?,?,?)',(uid,item['id'],time.time()))
    self.b.log_history(member.id,member.guild.id,'꾸미기 상점',item['name'], -item['price'])
   self.b.economy.remember(request,uid,fp,{'ok':True})
  return self.profile(member)
 def equip(self,member,data):
  current=self.profile(member);uid=str(member.id);kind=data.get('kind');item=data.get('item','')
  if kind not in ('title','frame','background','badge','bio'):raise self.Error('꾸미기 종류를 확인해주세요.')
  if kind=='bio':
   if not isinstance(item,str) or len(item)>80 or any(ord(c)<32 for c in item):raise self.Error('소개는 80자 이내로 입력해주세요.')
  elif item and (item not in current['owned'] or ITEM_MAP[item]['kind']!=kind):raise self.Error('보유한 아이템만 장착할 수 있어요.',403)
  with self.db:
   self.db.execute('INSERT OR IGNORE INTO mari_web_style(user_id) VALUES(?)',(uid,))
   self.db.execute(f'UPDATE mari_web_style SET {kind}=? WHERE user_id=?',(item,uid))
  return self.profile(member)
 def talk(self,member,data,action):
  from mari_web_economy import STOCKS
  symbol=data.get('symbol');uid=str(member.id)
  if symbol not in [s[0] for s in STOCKS]:raise self.Error('종목을 확인해주세요.')
  if action=='social/talk/send':
   request,fp,old=self.b.economy.receipt(member,data,action)
   if not old:
    body=data.get('body')
    if not isinstance(body,str) or not 1<=len(body.strip())<=2000 or any(ord(c)<32 and c not in '\n\t' for c in body):raise self.Error('본문은 1~2,000자로 입력해주세요.')
    title=data.get('title',body.strip().splitlines()[0][:80])
    if not isinstance(title,str) or not 1<=len(title.strip())<=80 or any(ord(c)<32 for c in title):raise self.Error('제목은 1~80자로 입력해주세요.')
    last=self.db.execute('SELECT MAX(at) FROM mari_web_stock_talk WHERE user_id=?',(uid,)).fetchone()[0]
    if last and time.time()-last<3:raise self.Error('3초 뒤에 다시 작성해주세요.',429)
    with self.db:
     self.db.execute('INSERT INTO mari_web_stock_talk(user_id,guild_id,symbol,body,name,avatar,at,title) VALUES(?,?,?,?,?,?,?,?)',(uid,str(member.guild.id),symbol,body.strip(),member.display_name,str(member.display_avatar.url),time.time(),title.strip()))
     self.b.economy.remember(request,uid,fp,{'ok':True})
  elif action=='social/talk/delete':
   row=self.db.execute('SELECT user_id,guild_id FROM mari_web_stock_talk WHERE id=? AND symbol=?',(data.get('id'),symbol)).fetchone()
   if not row or not(row[0]==uid or (row[1]==str(member.guild.id) and member.guild_permissions.administrator)):raise self.Error('이 글을 삭제할 권한이 없어요.',403)
   with self.db:self.db.execute('UPDATE mari_web_stock_talk SET deleted=1 WHERE id=?',(data.get('id'),))
  linked=[str(g) for g in self.b.guild_ids];rows=[];page=data.get('page',1);search=data.get('search','')
  if type(page) is not int or page<1 or not isinstance(search,str) or len(search)>60:raise self.Error('페이지와 검색어를 확인해주세요.')
  if not linked:return {'posts':[],'total':0,'page':1,'pages':1}
  where="symbol=? AND deleted=0 AND guild_id IN ("+','.join('?' for _ in linked)+')';args=[symbol,*linked]
  if search.strip():
   where+=" AND (instr(lower(title),lower(?))>0 OR instr(lower(body),lower(?))>0)";args.extend([search.strip(),search.strip()])
  page_size=5
  total=self.db.execute('SELECT COUNT(*) FROM mari_web_stock_talk WHERE '+where,args).fetchone()[0];pages=max(1,(total+page_size-1)//page_size);page=min(page,pages)
  for rid,user,guild,body,name,avatar,at,title in self.db.execute('SELECT id,user_id,guild_id,body,name,avatar,at,title FROM mari_web_stock_talk WHERE '+where+' ORDER BY id DESC LIMIT ? OFFSET ?',[*args,page_size,(page-1)*page_size]):
   g=self.b.bot.get_guild(int(guild));rows.append(dict(id=rid,userId=user,title=title or body.splitlines()[0][:80],body=body,name=name,avatar=avatar,at=at,guild=g.name if g else '',style=self.decoration(user),canDelete=user==uid or (guild==str(member.guild.id) and member.guild_permissions.administrator)))
  return {'posts':rows,'total':total,'page':page,'pages':pages}
 def paper(self):
  now=datetime.now(KST);edition=now.date() if now.hour>=9 else now.date()-timedelta(days=1);day=edition.isoformat()
  if not self.db.execute('SELECT 1 FROM mari_web_daily_paper WHERE day=?',(day,)).fetchone():
   date=edition-timedelta(days=1);start=datetime.combine(date,datetime.min.time(),KST);end=start+timedelta(days=1);articles=[]
   if self.exists('mari_web_adventures'):
    rows=self.db.execute('SELECT game,COUNT(*),MAX(score) FROM mari_web_adventures WHERE done=1 AND last>=? AND last<? GROUP BY game ORDER BY COUNT(*) DESC,game',(start.timestamp(),end.timestamp())).fetchall()
    for game,count,best in rows[:3]:articles.append({'title':GAMES[game]+f', 어제 {count}번의 도전','body':f'하루 최고 기록은 {best:,}점. 새로운 기록에 도전하는 플레이가 이어졌어요.'})
   if self.exists('mari_web_work_jobs'):
    n,reward=self.db.execute('SELECT COUNT(*),COALESCE(SUM(reward),0) FROM mari_web_work_jobs WHERE finished_day=?',(date.isoformat(),)).fetchone()
    if n:articles.append({'title':f'광산에서 완료한 작업 {n:,}회','body':f'어제 지급된 작업 보상은 총 {reward:,}마리예요.'})
   from mari_web_economy import STOCKS
   changes=[]
   for symbol,name,_ in STOCKS:
    rows=self.db.execute('SELECT open,close FROM mari_web_stock_days WHERE symbol=? AND day>=? AND day<? ORDER BY day',(symbol,start.isoformat(),end.isoformat())).fetchall()
    if rows:changes.append((abs((rows[-1][1]/rows[0][0]-1)*100),name,(rows[-1][1]/rows[0][0]-1)*100))
   if changes:
    _,name,change=max(changes);articles.append({'title':name+'에 쏠린 시선','body':f'어제 첫 갱신 전 가격 대비 마지막 가격은 {change:+.2f}%. 상장 종목 가운데 하루 변동 폭이 가장 컸어요.'})
   if not articles:articles=[{'title':'새로운 하루를 기다리며','body':'어제 집계된 활동이 아직 없어요. 오늘의 기록은 내일 신문에서 만나요.'}]
   issue={'day':day,'covered':date.isoformat(),'articles':articles}
   with self.db:self.db.execute('INSERT OR IGNORE INTO mari_web_daily_paper VALUES(?,?,?)',(day,json.dumps(issue,ensure_ascii=False),time.time()))
  return {'issues':[json.loads(r[0]) for r in self.db.execute('SELECT body FROM mari_web_daily_paper ORDER BY day DESC LIMIT 7')]}
