"""Write current evidence without upgrading experiments to field validation."""
import json
from pathlib import Path
from record_resume2_status import prepend

title='2026-10-01 최신 검증: 전체 ONNX 일치·큰 모델 한계·마스크 제거 실험'
body='''현재 기본 설정은 기존 후보를 유지한다. 버스 문 자동 검출과 승차 집계가 1순위이며 정류장 대기열/탑승 가능성은 후속 목표다. 아래 수치는 한 기존 영상과 그 좌우 이동 변형을 사용한 개발 검증이며 독립 실제 승차 정확도나 Orin Nano 성능을 뜻하지 않는다.

- 사람 YOLO11s-seg + 측정 발 하차 보정: 원본/오른쪽/왼쪽 전체513프레임 IN/OUT=6/0,5/0,5/0; 고정 시간·인물 검토 일치6/6,4/6,4/6. ONNX box-render 전체3회 완료 감사, 모든 검출 박스/측정점/관측·집계 이벤트가 PT와 일치했다. 사람만 있는 음성341프레임0/0, 문 활성0. 반전 전체1/3은 이전 입력·이벤트와 그대로였다. 사용하지 않는 마스크 그림 표시를 제거해 확인된 표시 병목을 줄였다.
- 사진 보강 문 모델: 고정 test4장/3문에서 mAP50 약.051→.52이나 recall .333, blind holdout/사람 검토 없음. 원본5/0·고정4/6, 왼쪽4/0·4/6, 오른쪽7/1·보수적5/6. 오른쪽 추가 이벤트의 사람 혼합/ID 교체는 uncertain으로 남겼다. 기본 미채택.
- optional door_selection_confidence를 custom 모드에 연결, 기본false. 최소 승객 지지와 유효 문 잠금 유지 규칙은 유지한다. 기존 모델 원본 전체513프레임6/0·6/6 및 입력/이벤트 완전 동일. 보강 모델 원본 weighted/unweighted 모두5/0·4/6, 완전 동일. Vancouver 사진만 창문→문 IoU .865 개선, 다른 실패 유지.
- 더 큰 YOLO11m 사람 모델 + 같은 문/집계 설정: 원본6/0·고정6/6, 오른쪽5/0·2/6, 왼쪽5/0·4/6. 오른쪽 청록/노란 가방 승차 시점이 고정 구간보다 이르며 첫 ID 교체는 uncertain. 숫자가 같아도 정확도 개선으로 처리하지 않는다.
- DoorLock은 각 generation에서 문 박스를 고정했다. 해당 누락을 generation 내부 문 흔들림으로 설명할 근거가 없다. 실험용 몸통-발 접근 범위 확장의 저장 trace6회 재생은 모두 기존 이벤트와 같아 개선되지 않았다. 런타임에 채택하지 않았다.
- 분할 모델에서 unused proto/cv4 마스크 출력부만 제거한 별도 box 모델: 파라미터10,113,248→9,443,760, 남긴 모든 tensor 정확히 동일, 원본 모델 미변경. 640입력 고정8프레임 원본/파생 박스 일치, dynamic ONNX 변환 양성53박스 일치. 원본/좌우 전체3회 각각513프레임 완료 감사와 검출·발점·이벤트 일치, 고정6/6·4/6·4/6 유지. 사람만 있는341프레임과 정지60프레임도 원본/PT와 전체 박스·이벤트 일치,0/0. 반전은 같은seg 가중치 두 모델 전체513프레임1/4와 완전 동일; 이전 기본 검출기의1/3과 별개다. 반전 원본 고정 구간을512-frame으로 그대로 뒤집어 사람별 검토3/6, IN485는 ID혼합/교체로 uncertain. 재학습이 아니며 Orin 검증이 아니다.
- 발목 하나만 보이는 조건의 저장 자세 재생: 원본/오른쪽/왼쪽에서 추가 측정 발점77/18/155개이나 네 실행 모두 기존 집계·이벤트와 정확히 같아 누락 개선 없음. conf.5와 고정 구간은 유지, 기본min_visible2 그대로.
- 부분 박스 연결 제거의 실제raw ID/자세 저장 재생: 원본6→5, 오른쪽5→5, 왼쪽5→3, 반전1/4→0/4, 정지·음성0/0 유지. 역재생 오탐은 줄지만 정상 승차 누락이 커져 기본 미채택. 추가 모델 재추론/독립 검증 아님.

자료 조사: PCDS 공식 저장소는 버스 천장 RGB/depth 데이터 설명과 Baidu 링크를 제공하지만 pinned 공개 파일 tree에 영상 없음; 전체 데이터 미획득. BerlinAPC는20x25 depth/HDF5 자료로 RGB 문 검출 데이터와 다르다. GitHub BusOccupancyCounter 공개 데모 파일은 Shutterstock 워터마크를 확인해 원 영상 권리가 검증되지 않았으므로 훈련·정확도 평가에서 격리했고 모델 추론도 하지 않았다. 저장소 MIT 표기를 원 영상 사용권으로 해석하지 않는다. PAMELA는 연구자 접근 신청 조건이며 연락하지 않았다.

재개 순서: 독립 버스 승차 영상/사람별 정답 확보와 실제 문 좌표 라벨 보강 → 겹침에 따른 ID 교체/조기 승차를 줄이는 후보의 원본·좌우·반전 회귀 → Orin 실기기 TensorRT·메모리·지연 검증. 파생 box 모델의 출력부 제거는 여섯 전체 장면에서 검출/집계 보존을 확인한 최적화 후보다. 문 사진 성능이나 동일 영상의 6명 집계를 현장 성공으로 확대하지 않는다. 기존 중단/오타 실패 폴더는 실패 기록으로 보존한다.
'''
for n in ['green','green-right80','green-left80']:
    root=Path('runs')/(n+'-segment-trained-box-20261001-r2-full')
    if (root/'summary.json').exists():
        s=json.loads((root/'summary.json').read_text())
        comparison=root/'box-derivation-parity.json'
        passed=json.loads(comparison.read_text())['passed'] if comparison.exists() else False
        state=f"{s['frames']}프레임 {s['counts']}, audit={(root/'completion-audit.json').exists()}, full parity passed={passed}"
    else:state='진행 중; 전체 성공 아님'
    body+=f'\n- `{root}`: {state}\n'
timing=Path('runs/segment-trained-box-cpu-inference-timing-r2.json')
if timing.exists():
    t=json.loads(timing.read_text())
    body+=f"\nWindows CPU warmed 추론 median 원본seg={t['median_segment_seconds']:.4f}s, box={t['median_box_seconds']:.4f}s. host 부하 통제/전체pipeline/Orin FPS 아님.\n"
usage=json.loads(Path('runs/usage-resume2-latest.json').read_text())
body+=f"\n사용량 기록: {usage['timestamp']}, 5시간 잔여{usage['primary_remaining_percent']}%, stop_reached={usage['stop_reached']}. 엄격히5% 미만일 때 중단.\n"
if usage['stop_reached']:
    body+='\n사용자 지정 사용량 중단점 도달: 실험 프로세스 모두 종료·완료 검증됨. 프로젝트 목표 전체 완료를 뜻하지 않는다. 다음 재개는 독립 영상/정답과 겹침 ID 교체 문제부터 진행한다.\n'
body+='\n주요 완료14건의 원본·모델 SHA, 전체 재생, 고정 인물/시각 구간과 최적화 계보를 다시 확인한 실행별 색인: `runs/verified-resume2-experiment-index-r2.json`. 조회 가능한 일부 시간 구간 평가이며 전체 precision을 추정하지 않는다. 비교 예외는 정확한 원본/파생 checkpoint 및 ONNX SHA 계보를 확인한 task 차이에만 적용하며 집계 임계값 변경, 모델 변조, 문자열 false는 허용하지 않는다. 최종 단위129통과.\n'
for f in ['CHECKPOINT.md','STATUS.md','RESULTS.md']:prepend(Path(f),title,body)
brief='사람seg+하차 발 증거 원본6/6·좌우4/6, unused 마스크 출력부 제거는 원본/좌우/반전/정지/음성 여섯 전체장면의 검출·발점·집계 일치. Windows CPU warmed 추론 median .320→.196초(전체 FPS/Orin 아님). 큰 YOLO11m 오른쪽2/6·왼쪽4/6, 사진 보강과 confidence는 미해결·기본 미채택. 한 발 조건은 개선 없고 부분박스 연결 제거는 승차 누락 증가. 주요14건 SHA/전체재생 색인 완료. 테스트129통과. 상세 tools/passenger-counter/CHECKPOINT.md. 독립 실제 승차/Orin 미검증.'
for f in ['CURRENT_STATUS.md','WORKLOG.md']:prepend(Path('../../docs')/f,title,brief)
sources='''공식 출처: https://github.com/shijieS/people-counting-dataset (PCDS CC BY-NC-SA3.0, RGB/depth 비동기 가능, 공개 tree 조사 `reviews/pcds-public-file-inventory-r2.json`). BerlinAPC https://depositonce.tu-berlin.de/items/485b22be-83ef-4361-94d8-f91d319c5643 는 저해상도 depth 자료이며 미획득. PAMELA https://videodatasets.org/PAMELA-UANDES/whole_data.html 접근 신청 필요/연락 안 함. https://github.com/sanjarbek1030/BusOccupancyCounter 데모의 원본 영상 권리는 확인되지 않았고 Shutterstock 워터마크로 격리(`data/public-github-bus-demo-20261001-r2.mp4.source.json`), 훈련/평가/추론 미사용.

파생 box 모델은 기존 Ultralytics YOLO11s-seg의 backbone/box/class 가중치를 그대로 유지한 local architecture derivative이며 새로운 데이터로 재학습하지 않았다. 원본 모델 라이선스가 그대로 관련된다. 출처/삭제 tensor/양성 박스 계보 `models/yolo11s-seg-trained-box-detector-r2.source.json`; 원본 불변 SHA와 ONNX 계보 검증 없이는 task 차이를 비교에서 무시하지 않는다.'''
prepend(Path('SOURCES.md'),title,sources)
for filename in ['SOURCES.md','CHECKPOINT.md','STATUS.md','RESULTS.md']:
    p=Path(filename);text=p.read_text(encoding='utf-8')
    p.write_text(text.replace('public-github-bus-demo-20261001-r2.mp4.source.json','public-github-bus-demo-20261001-r2.source.json'),encoding='utf-8')
if usage['stop_reached']:
    for filename in ['CURRENT_STATUS.md','WORKLOG.md']:
        p=Path('../../docs')/filename;text=p.read_text(encoding='utf-8')
        marker='## '+title+'\n\n'
        text=text.replace(marker,marker+f"사용자 지정 중단점 도달: 최신 5시간 잔여{usage['primary_remaining_percent']}% ({usage['timestamp']}). 실험 프로세스 전부 종료. 프로젝트 전체 완료 아님.\n\n",1)
        p.write_text(text,encoding='utf-8')
print('Current verified checkpoint and shared status written.')
