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
from mari_web_pubg_analysis import match_row, summary, telemetry_metrics

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
        return {'configured':bool(os.environ.get('PUBG_API_KEY')),'aiConfigured':bool(os.environ.get('OPENAI_API_KEY')),
                'defaultPlatform':platform if platform in PLATFORMS else 'steam'}

    def cached(self,key):
        r=self.b.db.execute('SELECT payload FROM mari_pubg_cache WHERE cache_key=? AND expires>?',(key,time.time())).fetchone()
        return json.loads(r[0]) if r else None

    def save(self,key,value,ttl):
        self.b.db.execute('DELETE FROM mari_pubg_cache WHERE expires<?',(time.time(),))
        self.b.db.execute('INSERT INTO mari_pubg_cache VALUES(?,?,?) ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload, expires=excluded.expires',
                          (key,json.dumps(value,ensure_ascii=False,separators=(',',':')),time.time()+ttl))
        self.b.db.commit()

    async def coach(self,http,report,uid):
        if not os.environ.get('OPENAI_API_KEY') or not report['summary']:return {'status':'not_configured','text':None}
        # Only aggregate game metrics leave the server; names, account IDs and raw telemetry do not.
        facts={'summary':report['summary'],'mode':report['mode'],'type':report['type']}
        payload=json.dumps(facts,ensure_ascii=False,sort_keys=True)
        key='ai:v1:'+hashlib.sha256(payload.encode()).hexdigest()
        cached=self.cached(key)
        if cached:return cached
        quota='ai-usage:'+str(uid)+':'+str(int(time.time()//86400));used=self.cached(quota) or 0
        if used>=20:return {'status':'limited','text':None}
        self.save(quota,used+1,86400)
        try:
            async with http.post('https://api.openai.com/v1/responses',allow_redirects=False,
                headers={'Authorization':'Bearer '+os.environ['OPENAI_API_KEY']},
                json={'model':os.environ.get('PUBG_AI_MODEL','gpt-4.1-mini'),'store':False,'max_output_tokens':1100,
                      'instructions':'한국어 PUBG 코치. 입력은 서버가 계산한 수치다. 잘한 점, 주의할 점, 다음 경기 목표를 각각 한두 문장으로 작성하라. 없는 사실, 확률, 백분위, 실력 등급을 만들지 마라. 자기장 포함률은 위치 선택이 섞인 체감 지표이며 순수 운이 아니다. 진입 평균은 진입 성공 표본만 계산된다. 표본 5경기 미만이면 판단을 유보하라. 적 시야, 엄폐, 팀원 잘못, 에임, 핵 사용은 단정하지 마라. 직선거리와 실제 이동경로를 구별하라. 조언은 제안으로 표현하고 모욕하지 마라. 500자 이내 평문으로 쓰라.',
                      'input':payload}) as res:
                if res.status!=200:return {'status':'error','text':None}
                data=await res.json()
                text='\n'.join(c.get('text','') for item in data.get('output',[]) if item.get('type')=='message' for c in item.get('content',[]) if c.get('type')=='output_text').strip()
                if not text or data.get('status')!='completed':return {'status':'error','text':None}
                result={'status':'ready','text':text[:2400]};self.save(key,result,86400);return result
        except Exception:return {'status':'error','text':None}

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
        name=str(data.get('name','')).strip();platform=data.get('platform');mode=data.get('mode');kind=data.get('type')
        if not re.fullmatch(r'[A-Za-z0-9_ -]{3,32}',name) or platform not in PLATFORMS or mode not in MODES or kind not in ('official','competitive'):
            raise self.error('닉네임, 플랫폼, 경기 조건을 확인해주세요.')
        now=time.time()
        for id in list(self.jobs):
            if self.jobs[id]['created']<now-1800 and id not in self.tasks:del self.jobs[id]
        completed=sorted((j for j in self.jobs.values() if j['id'] not in self.tasks),key=lambda j:j['created'])
        for j in completed[:-30]:del self.jobs[j['id']]
        key='report:v2:'+platform+':'+name.lower()+':'+mode+':'+kind
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
            self.tasks[id]=asyncio.create_task(self.run(id,name,platform,mode,kind))
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

    async def run(self,id,name,platform,mode,kind):
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
                    account=player['id'];refs=list(dict.fromkeys(m['id'] for m in player.get('relationships',{}).get('matches',{}).get('data',[])))
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
                    pairs=sorted(pairs,key=lambda x:x[0]['at'],reverse=True)[:20]
                    report={'name':player.get('attributes',{}).get('name',name),'platform':platform,'mode':mode,'type':kind,
                            'updatedAt':time.time(),'matches':[p[0] for p in pairs],'summary':summary([p[0] for p in pairs]),
                            'referenceCount':len(refs),'checkedCount':len(selected_refs),'failedMatches':sum(r is None for r in raws),
                            'ai':{'status':'not_configured','text':None}}
                    job['report']=report
                    for index,(row,raw) in enumerate(pairs):
                        job['progress']=f'자기장·교전 분석 중 · {index+1}/{len(pairs)}'
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
                        report['summary']=summary(report['matches'])
                    if self.status()['aiConfigured'] and report['summary']:
                        job['progress']='AI 코치가 기록을 정리하고 있어요.';report['ai']={'status':'loading','text':None}
                        report['ai']=await self.coach(http,report,job['uid'])
                    job['status']='ready';job['progress']='분석 완료';self.save(job['key'],report,600)
        except Exception as exc:
            if job['report'] is not None:
                for m in job['report']['matches']:
                    if m['telemetry']=='pending':m['telemetry']='unavailable'
                job['report']['summary']=summary(job['report']['matches']);job['status']='ready'
                job['report']['partial']=True;job['progress']='일부 로그를 제외하고 분석했어요.'
                if job['report']['ai']['status']=='loading':job['report']['ai']={'status':'error','text':None}
            else:
                job['status']='error';job['error']=str(exc) if isinstance(exc,self.error) else '배그 데이터를 가져오지 못했어요. 잠시 후 다시 검색해주세요.'
