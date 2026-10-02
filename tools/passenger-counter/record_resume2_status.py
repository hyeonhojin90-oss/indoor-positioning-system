"""Preserve previous records and update the ongoing resume2 evidence pointers."""
import json
from pathlib import Path

def prepend(path,title,body):
    text=path.read_text(encoding='utf-8')
    marker='## '+title+'\n\n'
    if text.startswith(marker):
        end=text.find('\n## ',len(marker))
        text=text[end+1:] if end>=0 else ''
    path.write_text(marker+body.strip()+'\n\n'+text,encoding='utf-8')

def main():
    title='2026-10-01 두 번째 재개: 추가 전체 비교와 새로운 사진 진단'
    body='''작업 진행 중. 중단은 own-chat의 최신5시간 잔여 사용량이 엄격히5% 미만일 때이며, 잔여5%에서는 계속한다. 기존 기본 `bus-portal-aux-pose-gated-onnx-candidate.json`을 보존한다. Orin/독립 승차 정확도는 미검증이다.

| 비교 | 전체 IN/OUT | 고정 부분 인물·시각 일치 | 판정 |
| --- | --- | --- | --- |
| 초기문 median5 원본/오른쪽/왼쪽 | 5/0,4/1,5/0 | 5/6,2/6,4/6 | 원본 누락·오른쪽 잘못된 OUT, 미채택 |
| 기존 문 모델 입력640 오른쪽 | 4/0 | 2/6 | 416보다 개선 없음 |
| 두 차례 합성 도착 기존 | 9/0 (첫6+둘째3) | 8/12 | development stress only |
| 두 차례 합성 도착 partial-retry | 11/0 (첫6+둘째5) | 10/12 | 청록 누락·둘째 노랑 조기 집계 남음 |

두 차례 영상은 원본513+버스없는90+왼쪽513의 하드컷 합성1116프레임이다. 실제 새 버스 도착 촬영이 아니다. 중간513..602 이벤트0이며 잔존 문513..532(20프레임)은 기존 버스 grace 뒤 사라진다. 문 세대·집계 상태를 다시 얻는 동작을 확인했지만 두 번째 정류장 정확도가 충분하지 않다. 새 raw_confidences는 원시ID/박스 길이와 범위 전1116프레임 검사 통과. 각 runs/*-20261001-r2-full에 완료 감사·인물 리뷰·고정창 평가·arrival-segments.json을 보존했다.

새 Commons 사진3장을 출처·저자·CC 라이선스·hash와 함께 확보했다. 모델 예측 전에 문 좌표를 assistant가 고정했으며 human review는 없다. Vancouver 열린 문은 기존nano ONNX IoU.854 / Grounding.907, Boston 좁은 비스듬한 문은 두 모델 모두 선택 실패. Beijing은 승차 장면이나 문이 버스 몸체 뒤 가려져 좌표 없음이며 음성으로 쓰지 않는다. Grounding open prompt+승객 자동crop도 Boston 실패·Vancouver.912로 좁은 문 문제를 해결하지 못했다. 사진에는 승차 이벤트 정확도 수치가 없다. `data/commons-door-photos-20261001-r2/portal-review.json`, `runs/new-door-photos*probe/diagnostic.json` 참조.

공식 YOLOE11s visual 두 준비는 bootstrap12표본 문0, text `bus door`와 `door`도 새사진 문0(conf.35)·bootstrap12표본 각각문0으로 실패했다. 공식 MobileCLIP encoder599764649bytes/SHA a67804d1b0f07b8b9a20c1761ec0847f34660f5fa338ec70e8f3fce68ed95e54 다운로드 완료 후 text embedding을 모델에 저장/복원 확인했다. encoder는 준비에만 필요하며 현장 실행에600MB encoder를 추가할 설계가 아니다. prepared person은 같은사진416/640에서 사람8/10 검출로 준비/저장/추론 경로의 알려진 대상 동작을 확인했다(conf.1 진단용). 문은 같은conf.1에서도0이며 모델의 범용 문 한계를 확인한다. prepared person을 사람 검출기로 사용하는 원본/좌우 전체 비교는 진행 중.

실제 installed Ultralytics8.3.228 trainer는 고정층 BatchNorm을 eval로 유지한다. small/retention 두 학습의 초기10층198텐서 각각을 시작점과 대조해 차이0으로 확인했다(`runs/frozen-backbone-bn-integrity-r2.json`). BN통계 변화를 실패 원인으로 지목하지 않는다.

Roboflow bus-door-detection-2 실제 브라우저 확인: 공개1884이미지·Public Domain·Front_door/Rear_door/Bus/Number·train1696/valid94/test94, 배포Dataset0/Model0. 이미지/공개raw라벨 열람은 가능하지만 Download image 클릭 시 Login or create a free account 대화상자다. 로그인/계정생성/포크/전체 데이터 다운로드는 하지 않았다. 페이지의 general detection API 예시는 이 데이터로 훈련된 내려받을 수 있는 문 모델이 아니다.

기존 partial-retry 회귀4건 전체0/0,0/0,1/0,0/1·테스트108 통과. 사람seg 박스 원본6/1·오른쪽5/0·왼쪽5/0(부분6/6,4/6,4/6)은 잘못된 OUT 때문에 미채택. masks 및 head flow를 런타임 집계에 도입하지 않았다. median 옵션도 기본latest를 바꾸지 않았다.'''
    body=body.replace('prepared person을 사람 검출기로 사용하는 원본/좌우 전체 비교는 진행 중.',
        'prepared person 원본/왼쪽/오른쪽 전체513프레임 비교는 각각6/1,6/1,6/1이며 고정 인물·시각 일치5/6,4/6,2/6이다. 모두 잘못된 하차와 조기 집계가 있어 미채택. 각 yoloe-person 전체 실행의 완료 감사와 인물 평가를 보존했다.')
    body+='''

추가 개선: `exit_evidence_guard.py`와 `dual_anchor.exit_ankle_guard` 선택 기능은 현재 측정한 발이 문 밖에 있거나 이전에 발의 문 안 관측이 확인된 경우에 몸 박스 OUT을 허용한다. 발이 없으면 unknown으로 기존 판단을 유지한다. 발이 중립/안쪽이고 이전 안쪽 증거도 없으면 OUT을 보류한다. 기본 false이며 body 이동/승차 기준·GT 창은 변경하지 않았다. 반전 영상의 한 발이 다시 안쪽인 정상 OUT을 막지 않도록 이전 안쪽 증거를 보존한다.

사람seg+보정 후보 전체513프레임 원본/오른쪽/왼쪽은6/0,5/0,5/0, 고정 부분 일치는6/6,4/6,4/6이다. 원본 false OUT32 한 건을 제거했고 승차6건을 유지했다. 오른쪽 첫 집계는 갈색→올리브 ID 연결이 불확실하여 인정하지 않았고, 왼쪽 올리브49는 기존55..85보다 이르다. 모두 소스 hash·전체 프레임·이벤트 재생 일치·구현 drift 없음 감사 완료. 이것은 같은 영상 파생 비교이며 독립 현장 성능이 아니다. 기존 기본은 유지하며 하차 반전·음성·정지·기본 회귀 검사는 진행 중이다.

추가 Commons4사진은 출처·CC 라이선스·SHA 보존 후 좌표를 고정했다. Waltham과 APSRTC의 가려진 문은 unlocalizable positive이며 음성 라벨이 아니다. Nigeria와 Kenya 열린 문은 기존 nano 검출0으로 선택 실패했다. `portal-review-validated-r2.json`은 이전 좌표를 바꾸지 않고 필수 status만 보완했다. 입력 검증을 추론 전 수행하도록 수정했다. 앞선 missing-key/잘못된 모델 경로 실행은 실패이며 완료 비교에 넣지 않는다. 아직 학습 미사용. Grounding 비교 진행 중. 전체 단위 테스트117 통과.
'''
    for filename in ['CHECKPOINT.md','STATUS.md','RESULTS.md']:
        prepend(Path(filename),title,body)
    brief='''두 번째 재개 작업 진행 중. median 문 취득·문 입력640 비교는 개선되지 않아 미채택. 두 도착 합성1116프레임에서 빠른 문 재확인은 전체9→11건·고정 부분8/12→10/12이지만 누락/조기집계가 남았다. 중간 버스 없는 구간 집계0. 새 Commons3사진은 넓은 문에 성공·좁은 비스듬한 문 실패를 확인했다. YOLOE text/공식 모델 비교를 계속한다. 상세 실행·증거·남은 작업은 tools/passenger-counter/CHECKPOINT.md·RESULTS.md를 따른다. Orin 실기기·독립 승차 정확도는 미검증.'''
    brief+=' 사람seg+발 증거 OUT 보정은 원본6/0·좌우5/0, 고정 부분6/6·4/6·4/6으로 원본 false OUT을 제거했다. 하차/음성/기본 회귀 검사 진행 중이며 기본 미변경. YOLOE 사람 비교는 조기 집계·false OUT으로 미채택. 새 Commons 사진은 총7장으로 버스 종류/각도 변화에서 문 미검출이 남음. 단위 테스트117 통과.'
    for filename in ['CURRENT_STATUS.md','WORKLOG.md']:
        prepend(Path('../../docs')/filename,title,brief)
    sources=json.loads(Path('reviews/commons-door-photo-sources-r2.json').read_text())
    source_body='모델 예측 전에 assistant가 문 좌표를 고정한 정지 사진 진단이다. 승차 이벤트/인원 정확도를 검증하지 않는다. 원본1280px 공개 파생사진과 hash는 `data/commons-door-photos-20261001-r2/provenance.json`에 있으며 박스 표시·진단 이미지는 변형본이다. 학습 미사용.\n\n'
    for s in sources:
        source_body+=f"- [{s['name']}]({s['page']}): {s['author']}, [{s['license']}]({s['license_url']}).\n"
    for s in json.loads(Path('reviews/commons-door-photo-sources-r2-extra.json').read_text()):
        source_body+=f"- [{s['name']}]({s['page']}): {s['author']}, [{s['license']}]({s['license_url']}).\n"
    source_body+='\n[공식 YOLOE](https://docs.ultralytics.com/models/yoloe/)의 v8.3.0 사전학습 yoloe-11s-seg.pt와 mobileclip_blt.ts, [공식 YOLO11](https://docs.ultralytics.com/models/yolo11/)의 yolo11s-seg.pt를 비교한다. 정확한 release URL·SHA는 models/*.source.json 및 mobileclip_blt.download.json에 있다. Orin 성능 미검증.\n\n[Roboflow 버스 문1884사진](https://universe.roboflow.com/bus-door/bus-door-detection-2)은 공개raw라벨을 확인했으나 Dataset0/Model0 및 이미지 다운로드 로그인 요구로 로컬 확보하지 않았다. 공개 열람과 학습 데이터 확보를 구별한다.'
    prepend(Path('SOURCES.md'),'2026-10-01 새로운 공개 문 사진과 사전학습 비교',source_body)
    prepend(Path('README.md'),'2026-10-01 재개 중인 비교 사용법','''기본 후보는 기존 그대로다. 실험 실패도 RESULTS.md/CHECKPOINT.md에 기록하고 총계 증가만으로 성공 처리하지 않는다.

`probe_door_photos.py --review data/commons-door-photos-20261001-r2/portal-review.json --models nano=runs/door-dynamic-onnx-parity-20260930/model.onnx --output runs/NEW-PHOTO-PROBE`는 새 정지사진의 문 선택을 검사한다. `--grounding --auto-crops`는 GT 없이 검출된 승객/버스를 기준으로 자동 확대한다. known label을 쓰는 oracle IoU는 진단용이며 런타임 선택에 쓰지 않는다.

`prepare_text_door.py --model models/yoloe-11s-seg.pt --encoder models/mobileclip_blt.ts --prompt 'bus door' --output models/yoloe-NEW-text.pt`는 고정 문구 embedding을 저장하며 실행 중 encoder는 필요없다. 파일이 준비됐다고 문 검출이 성공한 것은 아니다.

`build_arrival_sequence.py`의 영상은 개발 영상 하드컷 스트레스이며 새 현장 검증이 아니다. 일반 영상 편집 전환은 별도 실행으로 나누는 기존 원칙을 유지한다. 현재 새 median/640 후보는 실패하여 기본 설정에 적용하지 않는다.''')

if __name__=='__main__':main()
