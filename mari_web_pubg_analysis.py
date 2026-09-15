"""Pure, reproducible PUBG metrics. No model-generated numbers or inferred sight lines."""
import math
from datetime import datetime

MAPS = {'Baltic_Main':'에란겔','Erangel_Main':'에란겔','Desert_Main':'미라마','Savage_Main':'사녹',
        'DihorOtok_Main':'비켄디','Tiger_Main':'태이고','Kiki_Main':'데스턴','Neon_Main':'론도',
        'Summerland_Main':'카라킨','Chimera_Main':'파라모','Heaven_Main':'헤이븐'}

def number(v, default=0):
    return float(v) if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) else default

def timestamp(v):
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).timestamp()
    except (ValueError,TypeError):return 0

def point(v):
    if not isinstance(v,dict) or not all(isinstance(v.get(k),(int,float)) and math.isfinite(v[k]) for k in ('x','y')):return None
    return [v['x']/100,v['y']/100]

def distance(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])

def match_row(raw, account):
    included=raw.get('included',[])
    p=next((p for p in included if p.get('type')=='participant' and p.get('attributes',{}).get('stats',{}).get('playerId')==account),None)
    if not p:return None
    a=raw.get('data',{}).get('attributes',{});s=p['attributes']['stats']
    return {'id':raw['data']['id'],'at':a.get('createdAt',''),'map':MAPS.get(a.get('mapName'),a.get('mapName','알 수 없는 맵')),
            'mapId':a.get('mapName',''),'mode':a.get('gameMode',''),'type':a.get('matchType',''),
            'custom':bool(a.get('isCustomMatch')),'rank':int(number(s.get('winPlace'))),
            'kills':number(s.get('kills')),'damage':round(number(s.get('damageDealt')),1),
            'assists':number(s.get('assists')),'revives':number(s.get('revives')),'knocks':number(s.get('DBNOs')),
            'headshots':number(s.get('headshotKills')),'survival':number(s.get('timeSurvived')),
            'walk':number(s.get('walkDistance')),'ride':number(s.get('rideDistance')),
            'telemetry':'pending'}

def telemetry_metrics(events, account):
    events=sorted((e for e in events if isinstance(e,dict)),key=lambda e:e.get('_D',''))
    start=next((timestamp(e.get('_D')) for e in events if e.get('_T')=='LogMatchStart'),0)
    if not start:return {'available':False,'reason':'경기 시작 시각이 없어 분석에서 제외했어요.'}
    positions={};dead=set();circles=[];current=None;pending=None;last_circle=None;seq=0
    path=[];timeline=[];weapons={};blue=0;damage_taken=0;throws=0;heals=0;isolated=0;knocks=0
    teammate_distances=[];team=None;last_path=-99;skipped=0
    for e in events:
        t=max(0,timestamp(e.get('_D'))-start);kind=e.get('_T');c=e.get('character') or {}
        uid=c.get('accountId');loc=point(c.get('location'))
        if kind=='LogPlayerKillV2' or kind=='LogPlayerKill':
            victim=e.get('victim') or {};dead.add(victim.get('accountId'))
            if victim.get('accountId')==account:
                timeline.append({'t':round(t),'kind':'death','label':'사망'})
                if pending:pending['outcome']='사망 전 미진입';pending=None
        if kind=='LogPlayerRedeploy':dead.discard(uid)
        if kind=='LogPlayerPosition' and uid and loc:
            positions[uid]=(t,loc,c.get('teamId'),number(c.get('health')))
            if uid==account:
                team=c.get('teamId')
                if number(c.get('health'))>0 and uid not in dead:
                    if t-last_path>=5:path.append({'t':round(t),'x':round(loc[0]),'y':round(loc[1])});last_path=t
                    if pending and distance(loc,pending['center'])<=pending['radius']:
                        pending['entrySeconds']=round(t-pending['t']);pending['outcome']='진입';pending=None
        if kind=='LogGameStatePeriodic':
            gs=e.get('gameState') or {};center=point(gs.get('poisonGasWarningPosition'));radius=number(gs.get('poisonGasWarningRadius'))/100
            if not center or radius<=0:continue
            sig=(round(center[0]),round(center[1]),round(radius))
            if sig==last_circle:continue
            # Warning circles are fixed targets; shrinking safety circles are never counted as rerolls.
            last_circle=sig;seq+=1
            if pending:pending['outcome']='다음 원까지 미진입';pending=None
            pos=positions.get(account)
            previous=current;current={'center':center,'radius':radius}
            if not previous:continue  # Initial circle depends strongly on landing choice.
            if not pos or account in dead or pos[3]<=0 or not 0<=t-pos[0]<=10:skipped+=1;continue
            outside=max(0,distance(pos[1],center)-radius)
            row={'phase':seq,'t':round(t),'center':[round(x) for x in center],'radius':round(radius),
                 'x':round(pos[1][0]),'y':round(pos[1][1]),'outside':round(outside),
                 'inside':outside==0,'sampleAge':round(t-pos[0],1),
                 'oldEdgeRatio':round(distance(pos[1],previous['center'])/previous['radius'],2),
                 'entrySeconds':None,'outcome':'이미 원 안' if outside==0 else '기록 종료 전 미진입'}
            circles.append(row)
            if outside>0:pending=row
        if kind=='LogPlayerTakeDamage':
            attacker=e.get('attacker') or {};victim=e.get('victim') or {};amount=max(0,number(e.get('damage')))
            if victim.get('accountId')==account:
                damage_taken+=amount
                if e.get('damageTypeCategory')=='Damage_BlueZone':blue+=amount
            if attacker.get('accountId')==account and victim.get('accountId')!=account and attacker.get('teamId')!=victim.get('teamId'):
                weapon=str(e.get('damageCauserName','Unknown'))[:80]
                w=weapons.setdefault(weapon,{'weapon':weapon,'damage':0,'hits':0,'distanceSum':0})
                w['damage']+=amount;w['hits']+=1
                ap=point(attacker.get('location'));vp=point(victim.get('location'))
                if ap and vp:w['distanceSum']+=distance(ap,vp)
        if kind=='LogPlayerMakeGroggy' and (e.get('victim') or {}).get('accountId')==account:
            knocks+=1;victim=e['victim'];vp=point(victim.get('location'));vt=victim.get('teamId',team)
            near=[distance(vp,p[1]) for k,p in positions.items() if vp and k!=account and p[2]==vt and p[3]>0 and k not in dead and 0<=t-p[0]<=10]
            if near:
                nearest=round(min(near));teammate_distances.append(nearest)
                if nearest>100:isolated+=1
                timeline.append({'t':round(t),'kind':'knock','label':f'기절 · 가장 가까운 팀원 약 {nearest}m'})
            else:timeline.append({'t':round(t),'kind':'knock','label':'기절 · 팀원 거리 확인 불가'})
        if kind=='LogPlayerUseThrowable' and (e.get('attacker') or {}).get('accountId')==account:throws+=1
        if kind=='LogHeal' and uid==account:heals+=number(e.get('healamount'))
        if kind=='LogPlayerRevive' and (e.get('reviver') or {}).get('accountId')==account:timeline.append({'t':round(t),'kind':'revive','label':'팀원 부활'})
        if kind in ('LogPlayerKillV2','LogPlayerKill') and (e.get('killer') or {}).get('accountId')==account:
            timeline.append({'t':round(t),'kind':'kill','label':'킬'})
    return {'available':True,'circles':circles,'skippedCircles':skipped,'path':path[:1500],
            'timeline':timeline[:100],'blueDamage':round(blue),'damageTaken':round(damage_taken),
            'throws':throws,'healing':round(heals),'knocked':knocks,'isolatedKnocks':isolated,
            'measuredKnocks':len(teammate_distances),
            'weapons':[{'weapon':w['weapon'],'damage':round(w['damage']),'hits':w['hits'],
                        'meanDistance':round(w['distanceSum']/w['hits'])} for w in sorted(weapons.values(),key=lambda w:-w['damage'])[:8]]}

def summary(matches):
    n=len(matches)
    if not n:return None
    def avg(key):return round(sum(m[key] for m in matches)/n,1)
    valid=[m['detail'] for m in matches if m.get('detail',{}).get('available')]
    circles=[c for d in valid for c in d['circles']];outside=[c for c in circles if not c['inside']]
    entries=[c['entrySeconds'] for c in outside if c['entrySeconds'] is not None]
    def run(inside):
        best=0
        for d in valid:
            streak=0
            for c in d['circles']:
                streak=streak+1 if c['inside']==inside else 0;best=max(best,streak)
        return best
    k={'matches':n,'averageDamage':avg('damage'),'averageKills':avg('kills'),'averageSurvival':avg('survival'),
       'wins':sum(m['rank']==1 for m in matches),'top10':sum(0<m['rank']<=10 for m in matches),
       'earlyDeaths':sum(m['survival']<180 and m['rank']!=1 for m in matches),'revives':sum(m['revives'] for m in matches),
       'assists':sum(m['assists'] for m in matches),'telemetryMatches':len(valid),
       'zone':{'samples':len(circles),'inside':len(circles)-len(outside),
               'inclusionRate':round(100*(len(circles)-len(outside))/len(circles)) if circles else None,
               'requiredDistance':sum(c['outside'] for c in circles),'outsideSamples':len(outside),
               'averageOutside':round(sum(c['outside'] for c in outside)/len(outside)) if outside else None,
               'entrySamples':len(entries),'averageEntry':round(sum(entries)/len(entries)) if entries else None,
               'insideStreak':run(True),'outsideStreak':run(False),'blueDamage':sum(d['blueDamage'] for d in valid)},
       'team':{'isolatedKnocks':sum(d['isolatedKnocks'] for d in valid),'measuredKnocks':sum(d['measuredKnocks'] for d in valid)},
       'trend':None}
    if n>=10:
        half=n//2;recent=matches[:half];prior=matches[half:half*2]
        k['trend']={'each':half,'recentDamage':round(sum(m['damage'] for m in recent)/half,1),
                    'priorDamage':round(sum(m['damage'] for m in prior)/half,1)}
    return k
