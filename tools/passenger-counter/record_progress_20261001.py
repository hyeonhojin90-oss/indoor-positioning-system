import json
from pathlib import Path
from evaluate_events import evaluate_windows

read=lambda p:[json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
name='city-crowdhuman-motion-quarter-resume-full'
review=[dict(frame=f,track_id=t,direction=d,status='accepted',person=p,note='Exact original source event montage reviewed; fixed original window.') for f,t,d,p in [(373,2,'out','pink-hat-child'),(421,23,'in','red-coat'),(450,60,'out','grey-coat-white-bags')]]
with (Path('reviews')/(name+'-identity.jsonl')).open('x',encoding='utf-8') as f:
    for item in review:f.write(json.dumps(item)+'\n')
result=evaluate_windows(read(Path('runs')/name/'events.jsonl'),read(Path('reviews/city-independent-windows.jsonl')),0,review)
with (Path('runs')/name/'identity-evaluation.json').open('x') as f:json.dump(result,f,indent=2)
print(result)
note='''## 2026-10-01 재개 중 — 최신 상태

사용자 재개 지시로 작업 진행 중. 현재 중단 기준은 5시간 사용량95%(잔여5%)이며 이전10% 기준과 이전 paused 기록은 과거 상태다. 최근 자체 세션 한도 기록은 사용22%/잔여78%; 원시 토큰 잔량은 아니다. 목표 UI에는 blocked 표시가 남아 있지만 실제 원인 분석·실험은 진행 중이다.

- 도시 전체761프레임 `city-crowdhuman-motion-quarter-resume-full`: 자동 문361프레임, 승차1/하차2. 원본 정확한 이벤트373(아이),421(빨간 외투),450(회색 외투 흰 가방)을 대조하여 고정 부분 검토3/3. CrowdHuman 몸통 검출과 문 폭의.25 이상 승차 이동 조건이 기존 잘못된 아이 승차2건을 제거했다. 특정 카메라 개발 결과이며 전체 정답/독립 정확도 검증은 아니다.
- 같은 후보 버스 없는 보행자341프레임 전체: 문0·승하차0. 두 실행 완전성·원본 hash·로그 재생 감사 통과. 이후 pose 보조 코드 추가로 실행 당시 구현과 현재 파일 hash의 차이는 기록된다.
- 초록 기존 후보 전체513 승차5/하차0·부분5/6 유지. S960, pose 단독, CrowdHuman 몸통/머리 확대는 안정적인 개선을 만들지 못했다.
- 새 `replay_aux_pose.py`는 같은 원본·동시 프레임의 두 검출 결과를 유일한 박스 IoU로 대응한다. 보조 발목+몸통 전환 조건 재생은 숫자6이지만 원본89프레임 ID2가 앞을 지나가는 행인이고 노란 가방298은 기존 검토305~345보다 이르다. 따라서 갈색 승객 회복/6명 성공으로 채택하지 않는다. 결과 창은 이동하지 않는다. 재생은 전체 새 추론을 대신하지 않는다.
- 다음: 보조 발목 행인 오집계의 ID/몸통 이동 원인 확인, 갈색 승객의 실제 검출·관측 범위 개선. 버스 승차가1순위; 정류장 대기 규모·잔여 좌석 기반 탑승 가능성은 후속 목표다. Orin 성능·TensorRT·현장 검증은 아직 없다.

'''
for path in ['CHECKPOINT.md','STATUS.md','RESULTS.md','../../docs/CURRENT_STATUS.md','../../docs/WORKLOG.md']:
    p=Path(path);old=p.read_text(encoding='utf-8-sig');p.write_text(note+old,encoding='utf-8')
with Path('README.md').open('a',encoding='utf-8') as f:f.write('\n최근 재개 비교와 실패 판정은 [CHECKPOINT.md](CHECKPOINT.md)의 2026-10-01 항목을 따른다. 도시 부분3/3은 개발 영상 인물·시각 검토이며 독립 정확도가 아니다.\n')
