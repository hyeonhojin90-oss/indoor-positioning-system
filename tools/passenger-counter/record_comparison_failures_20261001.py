import json
from pathlib import Path
from evaluate_events import evaluate_windows
read=lambda p:[json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]
truth=read('reviews/green-development-windows.jsonl')
for name,rows in [
    ('green-shift-right80-reid-20261001-full',[
        (52,18,'accepted','olive-shirt-white-bag','ID18-only source image reviewed; earlier than fixed window.'),
        (113,3,'duplicate','olive-shirt-white-bag','ID3 is brown frame64/89 and olive113; olive already counted as18 at52. No recovery of brown.'),
        (172,30,'accepted','grey-hair-backpack','Source event reviewed.'),
        (249,1,'accepted','teal-shirt','Source event reviewed; earlier than fixed window.'),
        (300,55,'accepted','yellow-bag-umbrella','Source event reviewed; earlier than fixed window.'),
        (355,61,'accepted','white-shirt-grey-shorts','Source event reviewed.')]),
    ('green-shift-right80-position-aug-door-20261001-full',[
        (176,67,'accepted','grey-hair-backpack','Source box/frame near reviewed172 confirms same backpack approach; event176 falls in fixed interval.')])]:
    run=Path('runs')/name
    reviews=[dict(frame=f,track_id=i,direction='in',status=s,person=person,note=note,derived_scene=True) for f,i,s,person,note in rows]
    with (run/'identity-review.jsonl').open('x') as f:
        for row in reviews:f.write(json.dumps(row)+'\n')
    evaluation=evaluate_windows(read(run/'events.jsonl'),truth,0,reviews)
    with (run/'identity-evaluation.json').open('x') as f:json.dump(evaluation,f,indent=2)
    print(name,evaluation['matched_reviewed_events'])
note='''## 2026-10-01 위치 변화 후보 탈락과 저학습률 비교

합성 오른쪽80픽셀 이동 전체513프레임에서 정사각형 사람 입력은 IN5/OUT0이지만 고정 부분2/6이다. 외형 특징 ReID 후보는 IN6/OUT0이지만 고정 부분2/6으로 실패했다. 직접 원본52/64/89/113을 확인했으며 ID18의 올리브 승객이52에서 집계된 뒤, 갈색을 담던 ID3가113에서 올리브로 바뀌어 다시 집계됐다. 6명 총계를 가림 승객 회복으로 보고하지 않는다. ByteTrack/BoT-SORT 이름이나 모델 크기만으로 박스 혼합이 해결되지 않는다.

새 COCO nano 초기값에 위치 증강 자료를 학습한 `door-position-augmentation-20261001`은27epoch에서 조기 종료했고 별도 검증/시험 mAP50=0이었다. 학습 촬영의 문 점수는0.99로 높지만 주변 오검출과 경계 오차가 남았으며 실제 자동 문+전체 오른쪽 영상은 IN1/OUT0·고정 부분1/6·완료 감사 통과로 탈락했다. 높은 검출 점수를 정확도라고 해석하지 않는다. 검증된 기존 모델/설정은 보존했다.

현재 `door-position-retention-20261001`: 기존 bootstrap 문 checkpoint를 시작점으로 AdamW lr0=0.0001, 초기10개 층의 가중치 학습 고정, 입력416·20epoch 후보를 비교 중이다. BatchNorm 통계까지 불변인 것으로 보장하지 않는다. 자료/분할은 같으며 새 독립 촬영이 아니다. 합성 시간 역방향 초록 영상 전체 추론도 방향 스트레스로 진행 중이고 실제 하차 현장 검증으로 취급하지 않는다.

완료 감사에 저장된 관측 프레임과 몸통/발목 증거 종류 대조를 추가했다. 필드가 없는 과거 로그는 해당 항목을 검증하지 않았다고 명시한다. 최신 원본6명 실행은 관측 프레임·증거 종류까지 재생 일치했다. 사용자95% 중단 기준에는 아직 도달하지 않았다.

'''
for name in ('STATUS.md','RESULTS.md','CHECKPOINT.md'):
    p=Path(name);p.write_text(note+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
root='''## 2026-10-01 승차 계수 후보 비교 추가 기록

원본 개발 촬영6명 결과를 보존하며 합성 위치 변화 후보를 비교했다. 정사각형 입력IN5, 외형 추적IN6은 실제 인물/시각 대조에서 모두2/6으로 탈락했고 새 문 학습 후보도IN1로 탈락했다. 같은 승객 중복을 발견하여 총계만으로 성공 처리하지 않았다. 기존 문 모델을 시작점으로 저학습률 위치 증강 비교와 시간 역방향 스트레스를 계속한다. 세부 증거는 `tools/passenger-counter/RESULTS.md`, 재개 지점은 `CHECKPOINT.md`에 기록했다.

'''
for name in ('../../docs/CURRENT_STATUS.md','../../docs/WORKLOG.md'):
    p=Path(name);p.write_text(root+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
