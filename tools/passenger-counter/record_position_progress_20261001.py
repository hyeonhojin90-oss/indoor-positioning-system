"""Record completed runs and explicit open issues without overwriting run evidence."""
import json
from pathlib import Path
from evaluate_events import evaluate_windows

read=lambda p:[json.loads(line) for line in Path(p).read_text().splitlines() if line.strip()]
truth=read('reviews/green-development-windows.jsonl')
for name,review in [
    ('green-shift-right80-aux-20261001-full',[
        (113,3,'uncertain',None,'ID3 changes from brown frame64/89 to olive frame113; merged identity, not accepted.'),
        (172,67,'accepted','grey-hair-backpack','Source event montage reviewed.'),
        (300,74,'accepted','yellow-bag-umbrella','Source identity reviewed; event precedes unchanged reviewed passage window.'),
        (355,82,'accepted','white-shirt-grey-shorts','Source event montage reviewed.')]),
    ('green-shift-left80-aux-20261001-full',[
        (64,21,'accepted','olive-shirt-white-bag','Source event montage reviewed.'),
        (179,55,'accepted','grey-hair-backpack','Source event montage reviewed.'),
        (302,71,'accepted','yellow-bag-umbrella','Source identity reviewed; event precedes unchanged reviewed passage window.'),
        (350,76,'accepted','white-shirt-grey-shorts','Source event montage reviewed.')])]:
    run=Path('runs')/name
    reviews=[dict(frame=f,track_id=i,direction='in',status=s,person=person,note=note,derived_scene=True) for f,i,s,person,note in review]
    with (run/'identity-review.jsonl').open('x') as out:
        for row in reviews:out.write(json.dumps(row)+'\n')
    evaluation=evaluate_windows(read(run/'events.jsonl'),truth,0,reviews)
    with (run/'identity-evaluation.json').open('x') as out:json.dump(evaluation,out,indent=2)
    print(name,evaluation['matched_reviewed_events'])

note='''## 2026-10-01 보조 자세 ONNX 전체 검증과 위치 변화 실패 기록

현재 완료 기준: `green-aux-pose-latest-20261001-full` 전체513프레임, 자동 문508·IN6/OUT0, 원본 고정 부분 인물/시각6/6. 완료 감사에서 원본 hash·전체 프레임·이벤트 시각/확정 시각 재생 일치, 실행 중 구현 변경 없음. 실제 조건부 보조 자세 호출288회로6명을 유지했고, 보조 자세도 동적 ONNX로 실행했다. `green-aux-pose-whole-onnx-parity-20261001.json`은 전체513프레임의 검출/문/실측 발목/이벤트 대응을 확인했다. 버스 없는 실제341프레임은 자동 문0·IN0/OUT0·보조 자세 호출0. 기존 대각 카메라 프로필 원본109은 IN1, 역방향109은 OUT1을 유지했다. Orin/TensorRT/FPS 개선은 아직 검증하지 않았다.

모델 강도 비교: 실제 전체 nano 자세 후보는 IN5로 갈색을 놓쳤고 medium은 IN6으로 small과 집계가 같았다. medium의 발목 좌표가 달라 기존 인물 리뷰 자동 승계는 거부했다. 더 큰 모델을 바로 배포 후보로 채택하지 않는다.

초록 원본 전체를 좌우80픽셀 옮긴 합성 위치 시험은 양쪽 모두 IN4/OUT0으로 실패했다. 오른쪽은 ID3 갈색→올리브 혼합과 노란 가방300의 이른 집계가 있어 기존 시각/인물 고정 부분2/6, 왼쪽은 노란 가방302가 이르게 집계되어3/6이다. 정답 구간은 바꾸지 않았다. 합성 이동은 새 촬영이나 버스만 이동한 현장이 아니며 화면 가장자리 잘림도 있다. 로그의 문과 사람을 교차 대입한 진단에서도 원본6명을 안정적으로 복구하지 못해 문 경계 오차와 검출/추적 변화가 함께 남아 있다.

다음 비교: 원본12개 학습 이미지에 좌우 이동·반전만 추가한48개 파생 학습 자료, 기존 검증2/시험3개의 이미지와 라벨은 바이트 그대로 보존했다. 한글 경로 OpenCV 읽기/쓰기 오류를 수정하고 라벨 모음을 직접 확인했다. `door-position-augmentation-20261001` nano 후보를 명목 배치4·입력416으로 학습 중이다. 이 실험도 기존 개발 촬영 재사용이며 독립 평가로 승격하지 않는다. 관련 단위98개 통과.

도시 역방향 IN1/OUT3의 방향 오류는 미해결이다. 목표 도구는 여전히 blocked이고 active로 재개할 도구가 없지만 영상·코드 작업은 계속한다. 목표를 허위 완료하여 새로 만들지 않는다. 사용자 중단 기준은5시간 계정95% 사용이며 최신54% 사용 관측에서는 도달하지 않았다.

'''
for name in ('CHECKPOINT.md','STATUS.md','RESULTS.md'):
    p=Path(name);p.write_text(note+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
root='''## 2026-10-01 승하차 계수 작업 재개 및 위치 변화 비교

승차 우선순위를 유지하며 초록 개발 촬영 전체513프레임에서 자동 문+사람+보조 자세 ONNX로 IN6/OUT0·고정 부분6/6·완료 감사를 확인했다. 보조 호출288회, 실제 버스 없는341프레임은 호출0·집계0. 합성 좌우 위치 이동은 양쪽IN4로 실패하여 문 위치 증강 후보를 학습·비교 중이다. 도시 방향 오류, 독립 현장 정확도, Orin 성능은 미해결. 앱 목표 상태는 재개 도구 부재로blocked지만 실제 작업은 계속한다. 상세 증거와 재현 지점은 `tools/passenger-counter/STATUS.md`·`CHECKPOINT.md`를 따른다.

'''
p=Path('../../docs/CURRENT_STATUS.md');p.write_text(root+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
p=Path('../../docs/WORKLOG.md');p.write_text(root+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
with Path('README.md').open('a',encoding='utf-8') as f:f.write('''
### 조건부 자세 ONNX 후보와 위치 변화 한계

`configs/bus-portal-aux-pose-gated-onnx-candidate.json`은 현재 문 앞 접근 구간에서만 YOLO11s-pose ONNX를 호출한다. 전체 개발 촬영6명·보조288회, 버스 없는 실제 촬영은0회였다. 원본과 좌우 이동 영상 모두 비교해야 한다. 현재 좌우80픽셀 이동은4명으로 줄어든다. `diagnose_shift_geometry.py`는 저장 문/사람 관측을 교차 대입하는 원인 진단이며 새 추론이나 독립 정확도 시험이 아니다. `augment_portal_positions.py`는 원래 촬영 단위 분할을 유지하며 학습 이미지에만 이동·반전을 추가한다. 개발 영상 개선과 Jetson 실제 실행 검증은 별도다.
''')
