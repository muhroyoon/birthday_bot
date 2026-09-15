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
    roster=next((r for r in included if r.get('type')=='roster' and any(v.get('id')==p.get('id') for v in r.get('relationships',{}).get('participants',{}).get('data',[]))),{})
    ids={v.get('id') for v in roster.get('relationships',{}).get('participants',{}).get('data',[])}
    teammates=[]
    for v in included:
        if v.get('type')=='participant' and v.get('id') in ids:
            st=v.get('attributes',{}).get('stats',{})
            teammates.append({'name':st.get('name',''),'kills':number(st.get('kills')),'damage':round(number(st.get('damageDealt'))),'knocks':number(st.get('DBNOs')),'survival':number(st.get('timeSurvived'))})
    return {'id':raw['data']['id'],'at':a.get('createdAt',''),'map':MAPS.get(a.get('mapName'),a.get('mapName','알 수 없는 맵')),
            'mapId':a.get('mapName',''),'mode':a.get('gameMode',''),'type':a.get('matchType',''),
            'custom':bool(a.get('isCustomMatch')),'rank':int(number(s.get('winPlace'))),
            'kills':number(s.get('kills')),'damage':round(number(s.get('damageDealt')),1),
            'assists':number(s.get('assists')),'revives':number(s.get('revives')),'knocks':number(s.get('DBNOs')),
            'headshots':number(s.get('headshotKills')),'survival':number(s.get('timeSurvived')),
            'walk':number(s.get('walkDistance')),'ride':number(s.get('rideDistance')),
            'longestKill':number(s.get('longestKill')),'swim':number(s.get('swimDistance')),'heals':number(s.get('heals')),'boosts':number(s.get('boosts')),'team':teammates,'totalTeams':sum(r.get('type')=='roster' for r in included),
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
            # Positive-health position records also establish a return after recall/respawn,
            # including matches where a separate redeploy event is absent.
            if number(c.get('health'))>0:dead.discard(uid)
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
            if amount>0 and attacker.get('accountId')==account and victim.get('accountId')!=account and attacker.get('teamId')!=victim.get('teamId'):
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
    k['finishRate']=round(k['wins']/k['top10']*100,1) if k['top10'] else None
    k['maps']=[]
    for name in dict.fromkeys(m.get('map','알 수 없는 맵') for m in matches):
        rows=[m for m in matches if m.get('map','알 수 없는 맵')==name]
        k['maps'].append({'map':name,'matches':len(rows),'damage':round(sum(m['damage'] for m in rows)/len(rows),1),'rank':round(sum(m['rank'] for m in rows)/len(rows),1),'wins':sum(m['rank']==1 for m in rows),'early':sum(m['survival']<180 and m['rank']!=1 for m in rows)})
    return k


def season_metrics(raw, ranked=False):
    """Keep unsupported fields null; normal K/D uses official losses, ranked uses deaths."""
    deprecated={'avgSurvivalTime','roundMostKills','longestKill','headshotKills','headshotKillRatio','revives','heals','boosts','weaponsAcquired','teamKills','playTime','killStreak'}
    def val(k):return number(raw[k]) if k in raw and not (ranked and k in deprecated) else None
    n=val('roundsPlayed');kills=val('kills');wins=val('wins');deaths=val('deaths' if ranked else 'losses')
    def ratio(a,b,m=1):return round(a/b*m,2) if a is not None and b and b>0 else None
    def tier(k):
        v=raw.get(k) or {}
        return ' '.join(str(v.get(x,'')) for x in ('tier','subTier')).strip() or None
    top=val('top10s')
    if ranked and n and val('top10Ratio') is not None and 0<=val('top10Ratio')<=1:top=round(val('top10Ratio')*n)
    return {'matches':n,'wins':wins,'kills':kills,'deaths':deaths,'kd':ratio(kills,deaths),'winRate':ratio(wins,n,100),
      'top10Rate':round(val('top10Ratio')*100,2) if ranked and val('top10Ratio') is not None else ratio(top,n,100),
      'top10':top,'averageDamage':ratio(val('damageDealt'),n),'totalDamage':val('damageDealt'),'averageRank':val('avgRank'),
      'assists':val('assists'),'knocks':val('dBNOs'),'headshotRate':ratio(val('headshotKills'),kills,100),'headshots':val('headshotKills'),
      'maxKills':val('roundMostKills'),'longestKill':val('longestKill'),'averageSurvival':val('avgSurvivalTime') if ranked else ratio(val('timeSurvived'),n),
      'playTime':val('playTime') if ranked else val('timeSurvived'),'revives':val('revives'),'heals':val('heals'),'boosts':val('boosts'),
      'walk':val('walkDistance'),'ride':val('rideDistance'),'swim':val('swimDistance'),'teamKills':val('teamKills'),'roadKills':val('roadKills'),
      'tier':tier('currentTier'),'bestTier':tier('bestTier'),'rp':val('currentRankPoint'),'bestRp':val('bestRankPoint')}
