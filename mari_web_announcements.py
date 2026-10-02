"""Editorial releases. Set publication timestamp only after verified deployment."""
PUBLISHED_AT = '2026-10-02T10:43:54.159130+00:00'
RELEASE_ID = 'puzzle-refresh-20261002'

def entries():
 if not PUBLISHED_AT:return []
 return [{'id':RELEASE_ID,'at':PUBLISHED_AT,'category':'게임 업데이트',
 'title':'새로운 퍼즐 3종과 게임 라운지 개편',
 'summary':'섬 만들기·고리 잇기·다리 잇기 추가, 배그 운세 무료화, 공지 메뉴 신설',
 'sections':[
  {'title':'생각하는 즐거움, 새로운 퍼즐 3종','body':'섬 만들기, 고리 잇기, 다리 잇기가 두뇌 퍼즐에 추가됐어요. 자유 도전은 무료이며 완료하면 다음 단계로 진행해요. 단계가 높아질수록 큰 판과 복잡한 추론에 도전하게 됩니다. 오늘의 공통 문제는 최초 시작에만 티켓 1장을 사용해요.'},
  {'title':'내가 완료한 단계로 경쟁해요','body':'자유 도전 랭킹은 누적 합계가 아닌 최고 완료 단계로 비교해요. PC와 모바일 기록은 함께 집계하며 진행 중인 단계는 순위에 포함하지 않아요.'},
  {'title':'일부 게임의 서비스가 종료돼요','body':'마리 주차장 탈출, 기억력 게임, 빛의 미로, 보석 창고, 마리 낚시, 장애물 달리기, 배그 훈련장은 신규 플레이를 종료했어요. 기존 기록은 보관하고 이번 주에 획득한 기록은 기존 상금 규칙으로 정산해요. 배그 전적 검색은 계속 이용할 수 있어요.'},
  {'title':'오늘의 배그 운세, 이제 무료','body':'마리나 티켓 차감 없이 하루 한 번 오늘의 운세를 확인하세요. 같은 날 확인한 운세는 언제든 다시 볼 수 있어요.'},
  {'title':'업데이트와 마리일보를 공지에서','body':'공지 메뉴에서 업데이트 내용을 확인하고 마리일보도 읽을 수 있어요. 새 업데이트는 웹 알림함에서도 알려드려요.'}
 ]}]

def notices():
 return [{'key':'update:'+e['id'],'category':'updates','title':e['title'],'body':e['summary'],'at':e['at'],'tab':'notices','url':'/?tab=notices&update='+e['id']} for e in entries()]
