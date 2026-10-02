import json
from pathlib import Path
from evaluate_events import evaluate_windows
run=Path('runs/green-aux-pose-deferred-replay-20261001')
result=json.loads((run/'replay.json').read_text())
people=['olive-shirt-white-bag','brown-shirt-white-bag','grey-hair-backpack','teal-shirt','yellow-bag-umbrella','white-shirt-grey-shorts']
reviews=[dict(frame=e['frame'],track_id=e['track_id'],direction=e['direction'],status='accepted',person=p,
    observed_frame=round(e['time_s']*30),note='Saved observations only. Brown ankle evidence at89, deferred commit118; source ID2-only montage reviewed. Other body events remain original verified baseline.') for e,p in zip(result['events'],people)]
if len(reviews)!=6:raise ValueError('Unexpected events; review required')
with (run/'identity-review.jsonl').open('x') as f:
    for r in reviews:f.write(json.dumps(r)+'\n')
truth=[json.loads(x) for x in Path('reviews/green-development-windows.jsonl').read_text().splitlines()]
evaluation=evaluate_windows(result['events'],truth,0,reviews)
with (run/'identity-evaluation.json').open('x') as f:json.dump(evaluation,f,indent=2)
print(evaluation['matched_reviewed_events'])
note='''## 2026-10-01 추가 검증 및 원본 인물 판정 정정

초록89프레임 ID2를 행인으로 판단한 앞선 기록은 잘못이었다. ID2만 표시한 원본80/85/89/90/95 모음에서89의 박스와 보조 발목은 갈색 상의 승객이고95부터 행인과 박스가 섞인다. `green-aux-pose-transition-replay-20261001/id2-only.jpg`를 기준으로 정정한다. 선행 발목 즉시 집계는 노란 가방298이 여전히 너무 이르므로 그대로 채택하지 않는다.

보조 발목 신호를 보류하고 이후 관측 몸통 통과를 우선하는 새 재생 `green-aux-pose-deferred-replay-20261001`: 전체513 관측·IN6/OUT0, 고정 부분 인물/시각6/6. 갈색은 관측89(2.967초)·확정118(3.933초), 노란 가방은 기존 몸통331을 유지한다. 같은 인물이 계속 보이면 임의 시간 경과만으로 발목 후보를 확정하지 않는다. 발목 복귀/몸통 이벤트/문 변경은 후보를 해제하며 검출된 발목을 추측 좌표로 대체하지 않는다. 이는 저장 로그 비교이며 실제 전체 재추론·부정/방향 회귀 결과는 아직 별도 확인 중이다.

도시 역방향 전체761 자동 추론 `city-crowdhuman-reverse-20261001-full`은 IN1/OUT3으로 실패했다. 원본 일부3/3을 일반 승하차 해결로 확정하지 않는다. 더 긴 확인4/6/10프레임 진단도 실제 아이 이벤트를 놓쳤다. 도시 실제 두 발목 후보 전체761 고정 문 재추적은 IN1/OUT0으로 하차 회복에 실패했다. 원본 hash·전체 프레임·재생 감사는 모두 통과했으며 정확도와 구분한다.

새 전체 초록 추론 `green-aux-pose-deferred-20261001-full` 진행 중. 단위92 통과. 앱 목표 상태 blocked 해제 도구가 없어 새 생성도 거절됐지만 파일 작업·실험은 계속한다. 새 목표 성공으로 잘못 종료하지 않는다.

'''
for file in ['CHECKPOINT.md','STATUS.md','RESULTS.md','../../docs/CURRENT_STATUS.md','../../docs/WORKLOG.md']:
    p=Path(file);p.write_text(note+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
