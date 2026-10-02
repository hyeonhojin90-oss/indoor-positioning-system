import json
from pathlib import Path
from evaluate_events import evaluate_windows
run=Path('runs/green-aux-pose-deferred-20261001-full')
read=lambda p:[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
events=read(run/'events.jsonl');reference=json.loads(Path('runs/green-aux-pose-deferred-replay-20261001/replay.json').read_text())['events']
key=lambda e:(e['frame'],e['track_id'],e['direction'],e['time_s'])
if list(map(key,events))!=list(map(key,reference)):raise ValueError('Fresh events changed; original-frame review required')
reviews=read(Path('runs/green-aux-pose-deferred-replay-20261001/identity-review.jsonl'))
for r in reviews:r['note']='Fresh simultaneous body/pose inference original-frame montage reviewed. Brown observed89, committed118. Current-run complete-source/replay audit passed.'
with (run/'identity-review.jsonl').open('x') as f:
    for r in reviews:f.write(json.dumps(r)+'\n')
evaluation=evaluate_windows(events,read(Path('reviews/green-development-windows.jsonl')),0,reviews)
with (run/'identity-evaluation.json').open('x') as f:json.dump(evaluation,f,indent=2)
note='''## 2026-10-01 실제 전체 추론에서 갈색 승객 회복

`green-aux-pose-deferred-20261001-full`: 문·사람·보조 자세를 처음부터 실제 추론하여 전체513프레임 완료, 자동 문508·IN6/OUT0. 원본 인물/시각 고정 부분6/6과 전체 로그 재생 일치. 최초 완료 감사에서 구현 hash 변경 없음. 갈색 관측89/확정118, 나머지64/173/260/331/358은 기존 몸통 집계를 유지한다. 발목/몸통 집계를 서로 더하지 않고 같은 ID의 한 통과로 처리했다. 정지 영상 전체60은 IN0/OUT0·감사 통과. 개발 촬영6명을 맞춘 것이며 모든 승객의 완전한 정답이나 독립 정확도는 아직 아니다.

보조 발목 관측을2/3/5프레임 간격으로 건너뛰면 모든 위상에서 갈색을 다시 놓쳐5명이다. 따라서 임의 추론 간격 축소는 채택하지 않는다. 현재 문 접근 구간에 사람이 있을 때만 보조 자세를 켜는 재생 진단은 호출513→288에서 같은6명 이벤트를 유지했다. `green-aux-pose-gated-20261001-full`로 실제 자동 문+전체 재추론 확인 중이다. 모델 호출 수 감소를 Orin FPS/전력 개선으로 확정하지 않는다.

재현 설정: `configs/bus-portal-aux-pose-deferred-candidate.json`. 기존 가벼운5명 설정도 보존하며 새 보조 모델 비용과 가림/추적 오류를 비교한다. 도시 후보의 역방향 실패 및 실제 자세 단독 하차 누락은 미해결이다. 사용자95% 사용 중단 기준에 도달하지 않았으므로 작업 계속 중.

'''
for file in ['CHECKPOINT.md','STATUS.md','RESULTS.md','../../docs/CURRENT_STATUS.md','../../docs/WORKLOG.md']:
    p=Path(file);p.write_text(note+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
with Path('README.md').open('a',encoding='utf-8') as f:f.write('''
## 보조 자세를 통한 가림 승객 비교

초록 개발 영상에서 기존5명 후보에 동시 YOLO11s-pose 관측을 보조하여 실제 전체6명·고정 부분6/6을 확인했다. 다른 모델의 ID를 같다고 보지 않고 같은 프레임의 유일한 박스 대응만 사용한다. 두 발목 모두 신뢰도가 충분해야 하며 발이 없으면 추정 좌표를 만들지 않는다. 발목 진입은 보류하여 뒤따르는 몸통 통과를 우선하고, 몸통이 가려져 추적이 끊기면 앞서 실제 관측한 증거의 시각과 집계 확정 시각을 함께 남긴다. 문 변경이나 관측된 복귀는 보류 신호를 해제한다.

```powershell
.venv/Scripts/python.exe run.py --source data/regression/bus-green-32245403-720.mp4 --config configs/bus-portal-aux-pose-deferred-candidate.json --output runs/NEW-UNUSED-RUN --device cpu
```

카메라 각도에 맞춘 집계 방향은 사전 설정하며 문 위치는 자동 검출한다. 이번 개발 결과에는 약1초 뒤 확정된 갈색 승객이 포함된다. 자세 추론 비용·독립 영상 일반화·Orin 실행 성능은 별도 검증 대상이다. `pose_aux_gate` 후보는 현재 자동 문 앞에 사람이 접근하는 동안만 보조 추론을 실행한다. 건너뛴 프레임에 지난 발목 좌표를 재사용하지 않는다.
''')
print(evaluation['matched_reviewed_events'])
