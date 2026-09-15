"""Bounded background PUBG reports. Secrets remain on the bot server."""
import asyncio
import hashlib
import json
import os
import re
import secrets
import time
from urllib.parse import urlparse
from aiohttp import ClientSession, ClientTimeout
from mari_web_pubg_analysis import match_row, summary, telemetry_metrics, season_metrics, timestamp

PLATFORMS={'steam','kakao','console'}
MODES={'squad','squad-fpp','duo','duo-fpp','solo','solo-fpp'}

class Pubg:
    def __init__(self,bridge,error):
        self.b=bridge;self.error=error;self.jobs={};self.tasks={};self.limits={};self.api_times=[]
        self.network=asyncio.Semaphore(4);self.heavy=asyncio.Semaphore(1)
        self.b.db.execute('CREATE TABLE IF NOT EXISTS mari_pubg_cache (cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL, expires REAL NOT NULL)')
        self.b.db.execute('CREATE INDEX IF NOT EXISTS mari_pubg_cache_expiry ON mari_pubg_cache(expires)')
        self.b.db.commit()

    def status(self):
        platform=os.environ.get('PUBG_DEFAULT_PLATFORM','steam')
        return {'configured':bool(os.environ.get('PUBG_API_KEY')),'aiConfigured':False,
                'defaultPlatform':platform if platform in PLATFORMS else 'steam'}

    def cached(self,key):
        r=self.b.db.execute('SELECT payload FROM mari_pubg_cache WHERE cache_key=? AND expires>?',(key,time.time())).fetchone()
        return json.loads(r[0]) if r else None

    def save(self,key,value,ttl):
        self.b.db.execute('DELETE FROM mari_pubg_cache WHERE expires<?',(time.time(),))
        self.b.db.execute('INSERT INTO mari_pubg_cache VALUES(?,?,?) ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload, expires=excluded.expires',
                          (key,json.dumps(value,ensure_ascii=False,separators=(',',':')),time.time()+ttl))
        self.b.db.commit()

    async def season_report(self,http,platform,account,requested):
        result={'status':'error','id':requested,'seasons':[],'normal':{},'ranked':{},'errors':[]}
        try:
            key='seasons:'+platform;data=self.cached(key)
            if not data:
                data=await self.json_request(http,f'https://api.pubg.com/shards/{platform}/seasons',auth=True)
                self.save(key,data,86400*30)
            seasons=[{'id':r['id'],'current':bool(r.get('attributes',{}).get('isCurrentSeason'))} for r in data.get('data',[]) if re.fullmatch(r'division\.bro\.official\.[a-z0-9-]+',r.get('id',''))]
            # Older region-sharded seasons cannot be queried with this platform-only service.
            if platform in ('steam','kakao'):
                seasons=[r for r in seasons if 'pc-2018-' in r['id'] and int(r['id'].rsplit('-',1)[-1])>=9]
            seasons.sort(key=lambda r:int(r['id'].rsplit('-',1)[-1]) if r['id'].rsplit('-',1)[-1].isdigit() else 0,reverse=True)
            result['seasons']=seasons
            sid=next((r['id'] for r in seasons if r['current']),seasons[0]['id'] if seasons else None) if requested=='current' else requested
            if sid!='lifetime' and sid not in {r['id'] for r in seasons}:raise ValueError('Unavailable season')
            result['id']=sid
            for kind in ('normal','ranked'):
                if sid=='lifetime' and kind=='ranked':continue
                key=f'stats:v1:{platform}:{account}:{sid}:{kind}'
                try:
                    raw=self.cached(key)
                    if raw is None:
                        raw=await self.json_request(http,f'https://api.pubg.com/shards/{platform}/players/{account}/seasons/{sid}'+('/ranked' if kind=='ranked' else ''),auth=True)
                        self.save(key,raw,600)
                    modes=raw.get('data',{}).get('attributes',{}).get('rankedGameModeStats' if kind=='ranked' else 'gameModeStats',{})
                    result[kind]={m:season_metrics(v,kind=='ranked') for m,v in modes.items() if m in MODES}
                except Exception:result['errors'].append(kind)
            result['status']='partial' if result['errors'] else 'ready'
        except Exception:result['errors'].append('seasons')
        return result

    async def coach(self,http,report,uid):
        # Paid AI commentary is disabled; reports use measured PUBG metrics only.
        return {'status':'disabled','text':None}

    async def json_request(self,http,url,params=None,auth=False,large=False):
        parsed=urlparse(url)
        permitted=(parsed.hostname=='api.pubg.com' if not large else parsed.hostname=='telemetry-cdn.pubg.com')
        if parsed.scheme!='https' or not permitted or parsed.port not in (None,443) or parsed.username or parsed.password:
            raise self.error('경기 데이터 주소를 확인하지 못했어요.',502)
        if auth:
            self.api_times=[x for x in self.api_times if x>time.time()-60]
            if len(self.api_times)>=8:raise self.error('배그 조회가 많아요. 1분 뒤 다시 검색해주세요.',429)
            self.api_times.append(time.time())
        headers={'Accept':'application/vnd.api+json','Accept-Encoding':'gzip'}
        if auth:headers['Authorization']='Bearer '+os.environ['PUBG_API_KEY']
        async with self.network:
            async with http.get(url,params=params,headers=headers,allow_redirects=False) as res:
                if res.status==404:raise self.error('해당 플랫폼에서 닉네임 또는 경기 기록을 찾지 못했어요.',404)
                if res.status==429:raise self.error('배그 API 조회 한도에 도달했어요. 잠시 후 다시 검색해주세요.',429)
                if res.status in (401,403):raise self.error('배그 API 연결 설정을 확인해야 해요.',503)
                if res.status!=200:raise self.error('배그 데이터 제공이 지연되고 있어요. 잠시 후 다시 시도해주세요.',502)
                limit=48_000_000 if large else 3_000_000
                raw=bytearray()
                async for chunk in res.content.iter_chunked(65536):
                    raw.extend(chunk)
                    if len(raw)>limit:raise self.error('경기 로그가 너무 커서 상세 분석에서 제외했어요.',502)
                return await asyncio.to_thread(json.loads,raw)

    def view(self,uid,id):
        if not isinstance(id,str):raise self.error('분석 요청 번호를 확인해주세요.')
        job=self.jobs.get(id)
        if not job or job['uid']!=uid:raise self.error('분석 요청이 만료됐어요. 닉네임을 다시 검색해주세요.',404)
        return {k:v for k,v in job.items() if k not in ('uid','key','created')}

    async def start(self,uid,data):
        if not self.status()['configured']:raise self.error('배그 API 연결을 준비 중이에요.',503)
        name=str(data.get('name','')).strip();platform=data.get('platform');mode=data.get('mode');kind=data.get('type');season=data.get('season','current')
        if not re.fullmatch(r'[A-Za-z0-9_ -]{3,32}',name) or platform not in PLATFORMS or mode not in MODES or kind not in ('official','competitive'):
            raise self.error('닉네임, 플랫폼, 경기 조건을 확인해주세요.')
        if not isinstance(season,str) or not (season in ('current','lifetime') or re.fullmatch(r'division\.bro\.official\.[a-z0-9-]{1,60}',season)):
            raise self.error('시즌을 확인해주세요.')
        now=time.time()
        for id in list(self.jobs):
            if self.jobs[id]['created']<now-1800 and id not in self.tasks:del self.jobs[id]
        completed=sorted((j for j in self.jobs.values() if j['id'] not in self.tasks),key=lambda j:j['created'])
        for j in completed[:-30]:del self.jobs[j['id']]
        key='report:v4:'+platform+':'+name.lower()+':'+mode+':'+kind+':'+season
        active=next((j for j in self.jobs.values() if j['uid']==uid and j['status']=='loading'),None)
        if active:
            if active['key']==key:return self.view(uid,active['id'])
            raise self.error('진행 중인 분석을 먼저 기다려주세요.',429)
        if len(self.tasks)>=2:raise self.error('다른 전적을 분석 중이에요. 잠시 후 다시 검색해주세요.',429)
        recent=[x for x in self.limits.get(uid,[]) if x>now-60]
        if len(recent)>=3:raise self.error('검색 간격을 조금만 두고 다시 시도해주세요.',429)
        self.limits={u:v for u,v in self.limits.items() if v and v[-1]>now-60};self.limits[uid]=recent+[now]
        id=secrets.token_urlsafe(18);report=self.cached(key)
        self.jobs[id]={'id':id,'uid':uid,'key':key,'created':now,'status':'ready' if report else 'loading',
                       'progress':'저장된 분석을 불러왔어요.' if report else '플레이어를 찾고 있어요.',
                       'report':report,'error':None}
        if not report:
            self.tasks[id]=asyncio.create_task(self.run(id,name,platform,mode,kind,season))
            self.tasks[id].add_done_callback(lambda _:self.tasks.pop(id,None))
        return self.view(uid,id)

    async def match(self,http,platform,id):
        if not re.fullmatch(r'[A-Za-z0-9-]{10,80}',id):return None
        key='match:'+platform+':'+id;raw=self.cached(key)
        if raw:return raw
        try:
            raw=await self.json_request(http,f'https://api.pubg.com/shards/{platform}/matches/{id}')
            self.save(key,raw,86400*14);return raw
        except Exception:return None

    async def run(self,id,name,platform,mode,kind,season="current"):
        job=self.jobs[id]
        try:
            async with asyncio.timeout(240):
                async with ClientSession(timeout=ClientTimeout(total=35)) as http:
                    pkey='player:'+platform+':'+name.lower();player=self.cached(pkey)
                    if not player:
                        raw=await self.json_request(http,f'https://api.pubg.com/shards/{platform}/players',{'filter[playerNames]':name},auth=True)
                        player=next((p for p in raw.get('data',[]) if p.get('attributes',{}).get('name','').lower()==name.lower()),None)
                        if not player:raise self.error('닉네임을 찾지 못했어요. 대소문자와 플랫폼을 확인해주세요.',404)
                        self.save(pkey,player,600)
                    account=player['id']
                    job['progress']='시즌 전체 전적을 조회하고 있어요.'
                    stats=await self.season_report(http,platform,account,season)
                    refs=list(dict.fromkeys(m['id'] for m in player.get('relationships',{}).get('matches',{}).get('data',[])))
                    # Match references have no guaranteed time ordering. Sort fetched details by createdAt.
                    raws=[];selected_refs=refs[:100]
                    for offset in range(0,len(selected_refs),4):
                        job['progress']=f'최근 경기 확인 중 · {min(offset+4,len(selected_refs))}/{len(selected_refs)}'
                        raws.extend(await asyncio.gather(*(self.match(http,platform,m) for m in selected_refs[offset:offset+4])))
                    pairs=[]
                    for raw in raws:
                        if not raw:continue
                        row=match_row(raw,account)
                        if row and not row['custom'] and row['mode']==mode and row['type']==kind:pairs.append((row,raw))
                    pairs=sorted(pairs,key=lambda x:x[0]['at'],reverse=True)
                    hkey=f'history:v1:{platform}:{account}:{mode}:{kind}'
                    history={m['id']:m for m in (self.cached(hkey) or []) if timestamp(m.get('at'))>time.time()-86400*90}
                    for row,_ in pairs:history[row['id']]=row
                    rows=sorted(history.values(),key=lambda m:m['at'],reverse=True)[:500]
                    self.save(hkey,rows,86400*90)
                    sample=[p[0] for p in pairs[:20]]
                    report={'name':player.get('attributes',{}).get('name',name),'platform':platform,'mode':mode,'type':kind,
                            'updatedAt':time.time(),'matches':rows,'summary':summary(sample),'seasonStats':stats,'analysisIds':[m['id'] for m in sample],
                            'referenceCount':len(refs),'checkedCount':len(selected_refs),'failedMatches':sum(r is None for r in raws),
                            'ai':{'status':'not_configured','text':None}}
                    job['report']=report
                    for index,(row,raw) in enumerate(pairs[:20]):
                        job['progress']=f'자기장·교전 분석 중 · {index+1}/{min(20,len(pairs))}'
                        cachekey='detail:v2:'+platform+':'+row['id']+':'+account
                        detail=self.cached(cachekey)
                        if not detail:
                            asset=next((a.get('attributes',{}).get('URL') for a in raw.get('included',[]) if a.get('type')=='asset'),None)
                            try:
                                if not asset:raise ValueError('No telemetry')
                                async with self.heavy:
                                    events=await self.json_request(http,asset,large=True)
                                    detail=await asyncio.to_thread(telemetry_metrics,events,account)
                                    del events
                                self.save(cachekey,detail,86400*14)
                            except Exception:detail={'available':False,'reason':'상세 로그를 가져오지 못했어요.'}
                        row['detail']=detail;row['telemetry']='ready' if detail.get('available') else 'unavailable'
                        report['summary']=summary(sample)
                    if self.status()['aiConfigured'] and report['summary']:
                        job['progress']='AI 코치가 기록을 정리하고 있어요.';report['ai']={'status':'loading','text':None}
                        report['ai']=await self.coach(http,report,job['uid'])
                    for row in rows:
                        if row.get('telemetry')=='pending':row['telemetry']='not_requested'
                    job['status']='ready';job['progress']='분석 완료';self.save(job['key'],report,600)
        except Exception as exc:
            if job['report'] is not None:
                for m in job['report']['matches']:
                    if m['telemetry']=='pending':m['telemetry']='unavailable'
                job['report']['summary']=summary([m for m in job['report']['matches'] if m['id'] in job['report'].get('analysisIds',[])]);job['status']='ready'
                job['report']['partial']=True;job['progress']='일부 로그를 제외하고 분석했어요.'
                if job['report']['ai']['status']=='loading':job['report']['ai']={'status':'error','text':None}
            else:
                job['status']='error';job['error']=str(exc) if isinstance(exc,self.error) else '배그 데이터를 가져오지 못했어요. 잠시 후 다시 검색해주세요.'
