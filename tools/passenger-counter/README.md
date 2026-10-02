# 버스 문 자동 검출·승차 집계 프로토타입

## 2026-10-02 정답 검토·카메라 준비

녹화 영상에서 모델을 돌리기 전에 사람별 승하차 구간을 기록한다. 다음 명령을 모듈 폴더에서 실행하고 표시되는 로컬 주소를 연다. 새로운 출력 폴더만 사용한다.

```powershell
.venv/Scripts/python.exe serve_passage_review.py --source data/commons-danfo-resume4/called-upright.mp4 --output reviews/NEW-REVIEW --port 8872
```

원본 프레임을 이동해 사람 이름·방향·시작/끝을 정하고 저장한다. 새 `windows-NNN.jsonl`과 `review-NNN.json`이 생성된다. 실제 검토자가 사람이면 사람 종류를 선택하고 도구 시험은 Codex 종류로 저장한다. 디코더의 프레임 위치를 확인하고 불일치할 때는 처음부터 순서대로 읽는다. 반환 JPEG SHA와 실제 요청 프레임도 기록한다. 이는 전체 영상을 사람이 봤다는 증거나 완전 정답이 아니다.

실제 전체 종료와 원본 SHA가 확인된 녹화 실행에만 다음 결합 평가를 사용한다. 영상/정답 SHA, 원본 프레임/FPS, 종료 코드, 저장된 전체 감사와 이벤트를 확인한다. 정답 시각 창을 자동으로 넓히지 않는다. 사람별 대응을 확인한 identity review가 없으면 시간 구간 일치만 평가한다.

```powershell
.venv/Scripts/python.exe evaluate_review_snapshot.py --run runs/COMPLETED-FILE-RUN --review-metadata reviews/NEW-REVIEW/review-001.json --identity-review runs/COMPLETED-FILE-RUN/identity-review.jsonl --output runs/NEW-BOUND-EVALUATION.json
```

Orin에서 카메라를 수령한 뒤 사용할 수집 명령 예시는 다음과 같다. 실제 카메라 번호와 설치 방향을 확인한다. 현재 검증은 기존 파일을 사용한 명시적인 file drill이며 실제 카메라는 연결하지 않았다.

```sh
python3 record_camera_sample.py --source 0 --duration 20 --recording-fps 30 --output captures/NEW-CLASSROOM-SAMPLE
```

검출 표시 없는 `sample.mp4`, 프레임별 호스트 read 시각 `read-times.jsonl`, `capture.json`과 전체 디코딩/해시 검사 `capture-audit.json`을 남긴다. 수집 시간/프레임 상한이 필요하다. duration은 반복문의 정지 조건이며 카메라 read 자체의 차단 시간은 보장하지 않는다. MP4 재생 시간은 고정 FPS, sidecar는 실제 호스트 읽기 시각이다. 파일 재생의 frame/fps 집계와 실제 라이브의 호스트 시간 집계는 구분하며 카메라 노출 시각이나 버퍼 지연을 측정했다고 해석하지 않는다.

강의실 시험 후보는 `configs/classroom-door-smoke-resume4.json`이다. 버스 등장 조건을 제외하고 generic 문·현재 관측 사람/자세를 사용한다. 문 검출 좌표는 자동이며 진입 방향·통과 구역은 설치 시 검토한다. 일반 문 모델은 닫힌 문도 검출하므로 실제 출입 가능 영역인지 확인한다. 공개 건물 사진을 반복한15프레임2개에서 문 잠금과0/0 회귀만 확인했다. 실제 강의실 승하차 영상이나 독립 정확도 검증은 아니다. 버스 기본 설정은 그대로 유지한다.

```powershell
.venv/Scripts/python.exe run_experiment.py --source CLASSROOM-RECORDING.mp4 --config configs/classroom-door-smoke-resume4.json --output runs/NEW-CLASSROOM-RUN --device cpu
```

부분/라이브 실행의 `observed_trace_verified`는 수집된 로그의 연속성·시간·코드 SHA·재생 집계 일치이며 전체 원본 완료나 실제 승차 정확도가 아니다. 전체 로컬 파일은 기존 `full_run_verified`를 확인한다. 최신 중단점은 CHECKPOINT.md, 실제 실행 상태는 `runs/resume4-current-experiment-index.json`이다. 고정 Orin r10은 생성 시점의80파일/7모델/27baseline이며 이후 도구와 스트림 해시 수정 후보를 자동 포함하지 않는다. 실제 배포 전에 최신 코드 묶음을 새로 생성한다.

## 2026-10-02 선택 외형 실험과 입력 시간

`bus-portal-measured-osnet-observed-resume4.json`은 공식 OSNet x0.25 ONNX 특징으로 현재 검출 박스의 짧은 가림 연결을 실험한다. `appearance_bridge`를 명시하지 않으면 기본은 사용하지 않는다. 실제 전체 실행에서 원본/왼쪽 각각6명을 인물별로 확인했지만 조기 집계1건씩 남아 공통 기본으로 승격하지 않았다. 모델 크기는901043bytes이며 CPU 수치 일치 검증만 완료했다.

```powershell
.venv/Scripts/python.exe run_experiment.py --source data/regression/green-shift-left80-20261001.mp4 --config configs/bus-portal-measured-osnet-observed-resume4.json --output runs/NEW-APPEARANCE-EXPERIMENT --device cpu
```

`run.py --source-kind auto`는 실제 로컬 파일을 frame/fps로 계산하고 숫자 카메라·RTSP URL·capture pipeline은 호스트 read 완료 경과 시간을 쓴다. `file`/`live`로 명시할 수도 있다. 결과 `source_timing`은 선택한 시간 기준을 기록한다. 저장되는 annotated.mp4는 고정 FPS이므로 라이브 시간 증거는 tracks/events의 time_s를 사용한다. 카메라 노출 시각·버퍼 지연·실제 RTSP/CSI 동작은 미검증이다.

개발용 `train_door.py --skip-test`는 validation으로 checkpoint를 선택하고 test를 평가하지 않는다. 학습 전후 manifest/이미지/라벨/초기 모델/학습 파일 무변경을 검사하며 `training-inputs.json`·`training-completion.json`을 남긴다. `--prepare-only`는 학습/검증 완료를 뜻하지 않는다.

## 2026-10-01 재중단 복구와 현재 후보

문 위치는 자동 취득하며 설치별 통과 방향은 보정한다. `bus-portal-measured-acquisition-fallback-resume3.json`은 기존 문416 모델의 유효 잠금/승객 지원 후보가 없고 strong 버스 검출일 때만 보강640 문 모델을 사용한다. 기존 원본·좌우·반전의 전체 검출/추적/이벤트를 보존했고 새 Commons 촬영에서 실제 탑승자1건을 검토했다. 다른 두 영상은 문 미검출로0명이다. 개발 후보이며 현장 일반화 검증은 아니다.

```powershell
.venv/Scripts/python.exe run_experiment.py --source data/commons-moving-bus-boarding-resume3.webm --config configs/bus-portal-measured-acquisition-fallback-resume3.json --output runs/NEW-FALLBACK-EXPERIMENT --device cpu
```

실행 폴더와 같은 위치의 `.process.json`에 실제 종료 코드·summary·전체 원본 감사 결과를 남기고 `.process.log`에 출력을 보존한다. `full_run_verified=true`를 확인한다. `phase=running`이나 `summary` 없는 마지막 프레임 기록은 완료 증거가 아니다. `--max-frames 5` 같은 일부 프레임 시험은 전체 영상 검증과 구분한다. 이 도구도 OS에 의해 종료될 수 있으므로 중단된 실행은 재개 시 파일로 확인한다.

Orin Nano 최신 전달 snapshot은 `runs/orin-handoff-resume3-r9.zip`이다. 65파일·7모델·26개 전체영상 baseline, SHA/ZIP CRC검증을 확인했다. 포함된 `ORIN_FIRST_RUN.md`와 `verify_handoff.py`로 시작한다. 원본 영상은 별도로 전송해 golden source SHA와 대조한다. `verify_engine_run.py`와 단계별 시간 측정 설정이 포함되어 있다. 실제대상 GPU context·양성박스/자세·전체이벤트 검증이 필요하며 전송 무결성이나 Windows 검사만으로 실기기 성공을 주장하지 않는다. 세부 현재 상태는 CHECKPOINT.md다.

## 2026-10-01 출력부 제거 실험 후보

`configs/bus-portal-segment-trained-box-guard-onnx-r2.json`은 YOLO11s-seg의 학습된 사람 박스 가중치를 그대로 유지하고 집계에 사용하지 않는 마스크 출력부만 제거한다. 기본 후보를 대체하지 않는다. 원본/좌우/반전/정지/음성 전체 실행의 박스·측정 발점·집계 일치를 확인했다. 원본 승차 고정6/6·좌우4/6으로 남은 누락은 그대로다. Windows CPU warmed 추론 median .320→.196초는 Orin 속도나 전체 처리 FPS가 아니다.

```powershell
.venv/Scripts/python.exe run.py --source data/regression/bus-green-32245403-720.mp4 --config configs/bus-portal-segment-trained-box-guard-onnx-r2.json --output runs/NEW-BOX-EXPERIMENT --device cpu
```

변환을 다시 만들 때는 기존 모델·결과를 덮어쓰지 않는다. `derive_segment_trained_box_detector.py`와 `export_verified_onnx.py`는 원본 tensor 보존·실제 양성 박스·계보를 확인한다. `compare_run_exports.py --box-derivation-provenance models/yolo11s-seg-trained-box-detector-r2.source.json`은 정확한 PT/ONNX hash와 전체 trace/이벤트를 검사해야만 segment/detect task 차이를 허용한다. 상세 완료 증거와 다음 작업의 기준은 CHECKPOINT.md/RESULTS.md다.

## 2026-10-01 재개 중인 비교 사용법

기본 후보는 기존 그대로다. 실험 실패도 RESULTS.md/CHECKPOINT.md에 기록하고 총계 증가만으로 성공 처리하지 않는다.

`probe_door_photos.py --review data/commons-door-photos-20261001-r2/portal-review.json --models nano=runs/door-dynamic-onnx-parity-20260930/model.onnx --output runs/NEW-PHOTO-PROBE`는 새 정지사진의 문 선택을 검사한다. `--grounding --auto-crops`는 GT 없이 검출된 승객/버스를 기준으로 자동 확대한다. known label을 쓰는 oracle IoU는 진단용이며 런타임 선택에 쓰지 않는다.

`prepare_text_door.py --model models/yoloe-11s-seg.pt --encoder models/mobileclip_blt.ts --prompt 'bus door' --output models/yoloe-NEW-text.pt`는 고정 문구 embedding을 저장하며 실행 중 encoder는 필요없다. 파일이 준비됐다고 문 검출이 성공한 것은 아니다.

`build_arrival_sequence.py`의 영상은 개발 영상 하드컷 스트레스이며 새 현장 검증이 아니다. 일반 영상 편집 전환은 별도 실행으로 나누는 기존 원칙을 유지한다. 현재 새 median/640 후보는 실패하여 기본 설정에 적용하지 않는다.

## 현재 개발 후보와 내보내기 검증

사람 YOLO11s/버스 YOLO11m 간헐 검출을 분리한 `bus-portal-small-separate-dynamic-onnx-candidate.json`도 전체513프레임 IN5/OUT0·부분5/6이다. 세 모델의 동적 ONNX/PT 전체 박스 및 이벤트가 일치했다. 선택 의존성 기록은 `requirements-onnx-export-tested.txt`; 이는 CPU 개발 검증이며 Orin 환경 설치 잠금이 아니다.

`bus-portal-visual-calibrated-candidate.json`은 작은 출입구 YOLO11n + 사람 YOLO11m + 제한2초 버스 영상 연속성 + 부분 박스 연결 후보다. 초록 버스 전체513프레임 IN5/OUT0, 부분 인물/시각5/6이며 갈색 셔츠 누락을 유지한다. `bus-corner-passage-candidate.json`은 도시 측면 카메라의 가로 진입과 발판 아래 하차를 처리해 전체761프레임 IN1/OUT1·부분2/3이다. 서로 다른 카메라의 판정 보정이며 자동으로 모든 카메라에 같은 출입 방향을 추론한 결과가 아니다.

문 위치는 영상마다 자동 취득하지만 카메라의 진입 방향/통과 기준은 설치 때 보정한다. `bus-front-diagonal-square-*-candidate.json`은 문 하단이 화면 밖으로 잘린 원본 카메라의 가로 진입 보정이다. 전체109프레임에서 PT/ONNX 모두 IN1, 동일 frame28 ID2 이벤트 및 사람/문 박스 일치를 확인했다. 모델/입력 변경 때 전체 로그를 다시 비교한다.

```sh
python export_verified_onnx.py --model models/yolo11m.pt --source data/regression/bus-green-32245403-720.mp4 --frames 45 181 267 --imgsz 640 --conf .1 --classes 0 5 --dynamic --output runs/person-export-v1
python compare_run_exports.py --reference runs/PT --exported runs/ONNX --output runs/export-comparison.json
```

`export_verified_onnx.py`는 원본 가중치를 새 출력 폴더에 복사해 FP32/opset17 ONNX로 변환하고 동일 전처리의 표본 검출을 비교한다. 선택 의존성은 `onnx==1.19.0`, `onnxruntime`이다. `--dynamic`은 기존 `rect=True` 직사각형 여백을 유지하며, 생략한 고정 정사각형은 PT/ONNX 모두 `rect=False`로 비교한다. run.py의 `person_rect`/`door_rect`로 이를 맞춘다. 초록 영상은 고정 square 입력에서 IN3으로 악화했고 가변 입력 전체513프레임은 PT와 박스/ID/이벤트가 일치해 IN5를 유지했다. 표본 일치나 원본 클립 일치를 전체 일반화/Orin/TensorRT 성능으로 보지 않는다.

CPU 제한은 PyTorch callback과 CPU 전용 ONNX SessionOptions를 따로 적용한다. 정적 ONNX의 출력 바인딩도 새 세션과 함께 이동한다. CUDA/TensorRT 세션은 이 CPU 설정으로 교체하지 않는다. summary의 `backend_execution`에 실제 provider와 ORT intra/inter thread 값을 기록한다. `cpu_threads_actual`의 범위는 PyTorch다.

혼합 학습의 공개 문/버스 개발 사진 평가는 `evaluate_door_subsets.py`로 분리한다. `train_door.py --bus-train-repeat 16`은 mixed manifest의 버스 train 사진을 더 자주 뽑으며 고유 사진 수를 늘리지 않는다. val/test 경로는 유지하고 `sampling.json`에 반복 비중을 남긴다. 현재 작은 버스 사진의 다른 장면 일반화는 부족하다.

## 버스 후보·승객 주변 문 탐색과 부분 박스 연결

`bus-passenger-door-candidate.json`은 버스 등장 게이트를 켜고, Grounding이 반환한 후보를 버스 영역으로 먼저 걸러낸 뒤 승객 발 주변의 문을 선택한다. 기존 잠금보다 새 후보의 승객 지지가 충분히 높아야 이동하며, 새 문에는 최소 지지가 필요하다. 후보가 없으면 수동 문 영역으로 대체하지 않는다.

`bus-passenger-search-candidate.json`은 검출된 버스 가까이의 전신 승객 박스에서 검색 영역을 자동 계산해 문 검출 참조에 추가한다. 취득 전에는 한 번에1개 영역·15프레임 간격으로 재시도하고, 유효 후보 또는 잠금이 있으면 매 문 검사마다 그 주변을 확대해 연속 확인한다. 고정 카메라 좌표나 수동 문 박스를 입력하지 않는다. 검색 영역 자체를 문으로 잡는 오검출을 줄이기 위해 두 가장자리에 닿는 확대 후보는 제외한다. 입력이 없을 때 기존 Grounding 동작은 유지한다. summary의 `reference_inference_stats`에 실제 전체/확대 추론 횟수를 따로 남긴다. 시작 시 `implementation_sha256`도 기록한다.

`bus-bottom-bridge-candidate.json`은 먼저 문 아래 접근이 관측된 ID에 한해 전신/상반신 중첩을3프레임 확인하고 연결한다. 머리 높이·중심·폭·포함 비율 조건을 모두 만족하는 부모가 하나여야 한다. 전신이 같이 보일 때는 전신을 쓰고 사라진 뒤 부분 박스를 이어 쓴다. 소실0.75초·문 잠금 세대 변경 때 연결을 지운다. 이것은 발 위치 복원이나 범용 ReID가 아니며 다른 사람을 합치는 위험을 별도 검증해야 한다. 로그 `ids/boxes`는 연결 후 집계 입력, `raw_ids/raw_boxes`는 모델 원본이고 summary에 연결 내역이 있다. 출력 사람 박스 ID는 모델 원본이므로 이벤트 ID와 달라질 수 있다. 완료한 전체 실행과 별도 비교 결과는 아래 결과 문서에 보존한다.

전체513프레임의 부분 연결 후보는 IN5/OUT0·검토6명 중5명 대응으로 완료됐다. 갈색 셔츠는 누락이며 정확한 발판 통과 시각·다른 카메라·Orin 성능은 미검증이다. ReID를 추가한 별도 고정 문 추론은4명으로 감소해 채택하지 않았다. [RESULTS.md](RESULTS.md)와 [CHECKPOINT.md](CHECKPOINT.md)에 실행별 상태를 기록한다.

`audit_completed_run.py --run runs/EXPERIMENT --output runs/EXPERIMENT/completion-audit.json`은 원본 해시·전체 프레임·연속 로그·프레임/ID/방향 재생 동일성을 검사한다. 옛 사람 비교 로그는 `--config`를 추가한다. 이 검사는 정확도 검증과 구별된다. `review_track_frames.py`는 원시/집계 ID를 원본 위에 그려 인물 중복을 확인한다.

`retrack_people.py --door-crop`은 고정된 자동 문 주변에서 사람을 확대 추론하는 개발 비교 옵션이다. 확대 변환이 바뀌면 트래커를 초기화한다. 수동 `--crop`과 함께 사용할 수 없으며 문 검출부터 새로 실행한 결과로 취급하지 않는다. 이전 ROI 실패도 보존하고 이번 후보의 누락·거짓 하차를 따로 검토한다.

## 옆 접근의 조기 집계·추적 비교

`bus-side-view-penetration-candidate.json`은 `lateral_inset=0.25`를 추가한다. 옆 바깥에서 접근한 ID는 발 박스 하단뿐 아니라 가로 중심도 문 너비25~75%까지 들어와야 승차를 확정한다. 아래쪽에서 접근하는 경로는 기존 내부 구역을 유지한다. 시간 지연을 모든 승객에 일괄 적용하지 않으며 정답 시각 범위를 변경하지 않는다. 생략 시 기존 2차원 후보와 같다.

`person_imgsz`로 사람 모델의 입력 크기만 변경할 수 있다(생략 시 `imgsz`). `person_tracker_options`는 ByteTrack의 점수 문턱·버퍼 등 검증된 항목만 재정의하며 실행 폴더의 `person-tracker.yaml`에 실제 설정을 저장한다. `bus-side-view-continuity-candidate.json`은 약한 검출 연결 비교용이며 결과 검토 없이 배포 설정으로 채택하지 않는다. 문 로그를 고정한 `retrack_people.py` 비교는 사람 추적 실험으로, 문 검출부터 수행한 전체 실행과 구별한다.

## 2026-09-30 옆에서 문으로 접근하는 경로

`configs/bus-side-view-doorway-candidate.json`은 문 잠금 재검증 후보에 `counting.geometry="doorway"`를 추가한다. 기존 세로 통과선은 문 아래에서 올라오는 경로만 처리해 옆에서 접근하는 승객을 놓쳤다. 새 후보는 문 아래 또는 좌우 바깥에서 관측된 같은 ID가 문 내부로 들어오면 승차, 반대 이동이면 하차로 판정한다. 내부는 문 상대 가로 좌표0.1~0.9·세로 좌표0.95 미만, 바깥은 세로1.1 초과 또는 가로-0.1 미만/1.1 초과다. 사이 영역은 판정을 보류한다. 관측 허용 여백0.6·각 구역2프레임 확인·소실0.75초 조건을 사용한다.

```sh
python run.py --source data/regression/bus-green-32245403-720.mp4 --config configs/bus-side-view-doorway-candidate.json --output runs/green-doorway-new --device cpu
```

이는 `axis=y`, `entry=negative` 전용 개발 옵션이다. 생략하면 기존 선 통과 방식이 유지되며 ID를 합치지 않는다. 검출 박스 하단을 발 위치로 사용하므로 가림으로 박스가 잘리면 실제 승차보다 이른 이벤트가 생길 수 있다. 출력 영상의 노란 선은 세로 기준이며 좌우 판정 경계는 그려지지 않는다. 독립 카메라 보정과 Orin 실측은 미완료다.

## 2026-09-30 잠근 문 위치를 이용한 재검증 후보

`configs/bus-side-view-associated-candidate.json`은 기존 YOLO11m/ByteTrack 설정에 `cascade.associated_conf=0.25`만 추가한다. 새 문은 기존 Grounding 신뢰도0.35로 취득한다. 아직 시간 제한을 넘지 않은 문 잠금이 있을 때만 Grounding 후보 문턱을0.25까지 내려서 찾고, 신뢰도0.35 미만 후보는 기존 문과 IoU0.75 이상일 때만 갱신에 사용한다. 높은 신뢰도로 다른 위치에 나온 문은 기존처럼 잠금을 해제한다. TTL을 늘리거나 수동 문 박스를 추가하는 설정이 아니다. 옵션을 생략하면 기존 경로를 유지한다.

```sh
python run.py --source data/regression/bus-green-32245403-720.mp4 --config configs/bus-side-view-associated-candidate.json --output runs/green-associated-new --device cpu
```

이 설정은 개발 영상의 검출 누락을 줄이는 비교 후보이며 실제 장치용 설정으로 확정하지 않았다. 같은 위치의 잘못된 후보까지 완전히 구별할 수는 없어 독립 카메라와 문 소실·이동을 검증해야 한다. 전체 실행 결과는 `RESULTS.md`에서 확인한다.

## 2026-09-30 승객별 부분 검토

`review_frames.py`는 모델 박스가 없는 원본 프레임과 번호·시각이 있는 모음을 추출한다. 원본 비율을 보존하며 출력 폴더가 있으면 덮어쓰기를 거부한다. 초록색 버스의 접근·발판 진입이 보이는 여섯 승객 시각 범위를 `reviews/green-development-windows.jsonl`에 기록했다. 시작부터 승차 중이거나 끝까지 대기한 사람을 제외한 부분 목록이며, 전체 인원 정답·독립 정확도 자료로 사용하지 않는다. 세부 기준은 `reviews/README.md`를 본다.

```sh
python review_frames.py --source data/regression/bus-green-32245403-720.mp4 --output runs/source-review-new --step 15
python evaluate_events.py --predicted runs/green-cascade-m-full-001/events.jsonl --truth reviews/green-development-windows.jsonl --reviewed-windows --tolerance 0
```

부분 검토 모드는 중첩 시각 범위에도 예측과 검토 이벤트를 일대일 대조한다. 목록 밖 예측을 오탐으로 단정하지 않고 미분류로 남긴다. 모델의 인물 ID를 검토 인물과 연결하는 기능은 없으므로 실제 장면 대조를 함께 수행한다.

`--identity-review reviews/green-m-botsort-identity.jsonl`을 추가하면 육안으로 승인한 이벤트만 해당 검토 인물에 대응한다. 시각만 대조한 결과는 `temporal_matching_only=true`다. BoT-SORT의 IN3 중 한 건은 동일 승객 중복이므로 이 후보는 채택하지 않았다. `run.py`의 선택 항목 `person_tracker`는 `bytetrack.yaml`/`botsort.yaml`을 지원하며 기존 기본값은 ByteTrack이다. `bus-side-view-m-botsort-candidate.json`은 거부된 실험을 재현하는 설정이다.

후속 작업으로 공개 문 가중치·라벨을 실제 확보하고 경량 모델의 전이학습 시험을 추가했다. 아래 초기 설명 중 미확보/미학습 상태는 `STATUS.md`의 최신 후속 결과가 우선한다.

## 2026-09-29 버스 등장 조건과 카메라별 통과 구역

`configs/bus-cascade-arrival.json`은 YOLO11n의 COCO `bus` 검출로 버스가 보일 때만 자동 문 검출을 호출한다. 잠깐의 검출 누락은 0.75초 유예하고, 버스가 사라지면 문 잠금과 혼합 검출 참조 박스를 비운다. 사람 추적은 계속 수행하며 집계 대상은 `person` 클래스만이다. `doors.jsonl`의 `backend=bus_gate`는 문 검출을 건너뛴 프레임이고, `summary.json`에 문 검출 호출 수와 건너뛴 프레임 수가 남는다. 이 조건은 버스가 영상에서 충분히 크게 검출되는 카메라를 가정한다.

새로운 버스 정면 영상에서는 Grounding이 출입문 대신 버스 전면 전체를 문으로 잡는 사례가 나왔다. 이 설정의 `max_door_bus_width_ratio=0.65`는 문 후보 중심이 버스 박스 안에 있으면서 후보 너비가 버스 너비의 65% 이하일 때만 잠금에 사용한다. 이 비율은 오검출 방지 실험값이며 넓은 쌍문이나 버스 박스가 부분만 잡히는 시점에서는 다시 확인해야 한다.

`configs/bus-side-view-development.json`은 별도 측면 영상의 사람 발 경로에 맞춰 문 박스 하단을 넘어 통과 구역을 확장한 **개발용 보정**이다. `counting.low/high`는 문 높이에 대한 통과선 위치이고 `outside_margin`은 문 길이 방향만 추가 허용하는 폭이다. 문 너비 방향은 그대로 제한한다. 실제 정류장/강의실에서는 카메라를 고정하고 통과선과 허용 범위를 직접 검수해야 한다. 이 설정의 성공은 보정에 사용한 영상의 정확도 검증이 아니다.

```sh
python run.py --source data/bus-3132290.mp4 --config configs/bus-cascade-arrival.json --output runs/arrival-original-new
python run.py --source data/people-walking.mp4 --config configs/bus-cascade-arrival.json --output runs/arrival-no-bus-new --max-frames 60
python run.py --source data/wiki-man-boarding.webm --config configs/bus-side-view-development.json --output runs/wiki-side-view-new
python run.py --source data/regression/bus-absence-reentry.mp4 --config configs/bus-cascade-arrival.json --output runs/arrival-reentry-new
```

버스가 없는 동안에도 사람 YOLO 추적과 결과 영상 렌더링은 수행한다. Windows CPU와 Jetson Orin Nano의 속도·정확도를 동일하게 보지 않는다. 이번 검증값과 실패 범위는 `RESULTS.md`에 기록했다.
재등장 회귀 영상은 `make_regression_clips.py`가 원본 첫35프레임+검은 화면35프레임+동일 첫35프레임으로 생성한다. 이미 회귀 영상이 있으면 덮어쓰기를 거부하므로 새 디렉터리에서 생성하거나 보존된 파일을 사용한다.

`probe_independent.py --source VIDEO --frames 88 176 264 352 --resize-width 1280 --output NEW_DIR`로 다른 카메라의 문 후보를 표본 점검할 수 있다. 새 Pexels 정면 영상에서는 버스 전면 전체 오검출이 반복됐고, 버스 상대 너비 조건으로 이를 막았지만 실제 문은 찾지 못했다. 이 경우 `IN0`은 정답이 아니라 집계 불가다. 상세 실패 근거는 `RESULTS.md`를 본다.

`tracks.jsonl`은 이제 `door_generation`을 포함한다. `replay_counter.py`는 이를 사용해 실제 실행과 동일한 시점에 추적 이력을 비운다. 이전 로그를 재생하면 결과의 `legacy_reset_approximation=true`가 표시되며 문 좌표 변화로 세대를 근사하므로 정확히 일치할 수 없다.

초록색 버스의 여러 승객 영상은 초기 YOLO11n 전체 실행에서 IN0으로 실패했다. 같은 영상을 개발 자료로 사용해 사람 모델·추적기·입력 크기를 비교한 뒤 YOLO11m 후보로 문 검출부터 다시 실행해 IN2/OUT0을 얻었다. 두 이벤트 장면은 문 진입과 맞지만 전체 승차 정답과 Orin Nano 실측은 없다. [조건·실패·후속 결과](RESULTS.md)를 확인한다.

`retrack_people.py`는 완료된 실행의 문 박스·잠금 세대를 고정하고 같은 영상의 사람 모델·추적기·입력 크기를 비교한다. 영상 해시와 참조 로그의 프레임 수·순서를 검증하며, `door_generation`이 없는 이전 로그는 재실행을 요구한다. 결과의 `frozen_door_experiment=true`는 전체 문 검출 재실행이나 독립 정확도 시험이 아니라는 뜻이다. 출력 경로는 매번 새로 지정한다.

```sh
python retrack_people.py --source data/regression/bus-green-32245403-720.mp4 --reference-run runs/green-heldout-001 --config configs/bus-side-view-development.json --person-model models/yolo11m.pt --output runs/green-retrack-new
python run.py --source data/regression/bus-green-32245403-720.mp4 --config configs/bus-side-view-m-candidate.json --output runs/green-cascade-m-new
```

## 2026-09-29 혼합 문 검출 실험

`configs/bus-cascade.json`은 처음 문을 찾을 때 Grounding DINO를 사용하고, 문을 잠근 뒤에는 공개 문 YOLOv8으로 같은 위치를 확인한다. 경량 모델의 검출이 없거나 마지막 Grounding 문과 IoU가 낮으면 Grounding으로 재검사한다. 문 잠금 중 검출 간격은 15프레임, 잠금 전은 5프레임이다. 버스가 움직여 IoU가 떨어지거나 문이 사라지면 `DoorLock`이 집계를 중단하고 재잠금을 요구한다. 모델이 반환한 박스만 사용하며 수동 박스로 대체하지 않는다.

별도 영상에서 버스 차체 전체도 문 후보로 나온 사례가 있어 이 설정에는 높이/너비가 1 이상인 세로형 문 후보만 남긴다. 다른 형태의 문을 쓰는 카메라에서는 `min_door_aspect`를 실측 자료로 재조정한다.

실행 전 아래 2026-09-18 절의 참조 모델 의존성·snapshot을 설치한다.

```sh
python run.py --source data/bus-3132290.mp4 --config configs/bus-cascade.json --output runs/cascade-original-new
python run.py --source data/regression/shift-left.mp4 --config configs/bus-cascade.json --output runs/cascade-shift-new
python summarize_comparison.py
```

공개 문 가중치의 별도 이용허락은 확인되지 않아 위 혼합 설정도 비교 실험용이다. 실제 카메라는 처리 시간 때문에 TTL이 경과할 수 있으므로 실시간 입력은 대상 장치 FPS·지연 검증 전 계수 정확도를 주장하지 않는다. 이 설정의 통과선도 원본 영상에 맞춘 값이다. 상세 결과는 `RESULTS.md`.

별도 촬영 영상의 문 후보만 점검하려면 `python probe_independent.py --output runs/wiki-door-probe-new`를 사용한다. `data/wiki-man-boarding.webm`은 정차한 버스 영상이 아니며 전체 계수 실패가 `RESULTS.md`에 기록돼 있다.

## 2026-09-18 모델 비교 후 실행 경로

공개 버스 클립에서 자동 문 검출 → 사람 추적 → IN 1 / OUT 0까지 실행했다. 경량 문 모델의 다중 해상도 재시도와 Grounding DINO 참조 모델을 비교한다. 두 설정의 통과선 0.90/0.95는 이 영상의 발 경로를 보고 보정한 값으로, 다른 카메라에 그대로 적용하는 기본값이 아니다. 결과와 파생 영상 시험의 한계는 `RESULTS.md`를 확인한다.

```sh
python run.py --source data/bus-3132290.mp4 --config configs/bus-calibrated-multiscale.json --output runs/multiscale-new
python -m pip install -r requirements-reference.txt
python -c "from huggingface_hub import snapshot_download; snapshot_download('IDEA-Research/grounding-dino-tiny', revision='a2bb814dd30d776dcf7e30523b00659f4f141c71', cache_dir='models/hf')"
python run.py --source data/bus-3132290.mp4 --config configs/bus-grounding-reference.json --output runs/grounding-new
```

Grounding 참조 설정은 위 revision의 로컬 snapshot 경로를 사용한다. 다운로드는 최초 한 번 필요하며 추론 시에는 네트워크 요청 없이 불러온다. Windows CPU에서 느린 비교용이며 Orin 실시간 배포 모델로 확정하지 않았다. Grounding 입력 크기는 자체 processor 설정을 따르고 `imgsz`는 사람 YOLO에 적용된다. 공개 문 모델의 fallback 1280은 640 입력에서 허용된 문 후보가 없을 때만 수행한다.

`make_regression_clips.py`는 원본의 수평 이동/역재생/정지 파생 영상을 만든다. 이 자료는 좌표 이동·방향·정지 회귀 시험이며 독립 실영상 정확도 평가가 아니다. `compare_models.py`는 동일 9프레임으로 YOLO 모델 크기와 640/960 입력을 비교한다. 출력 폴더가 이미 있으면 새 경로를 사용하거나 기존 자료를 별도로 보존한다.

## 공개 문 데이터 학습 재현

`data/doors-detection.zip` 원본 출처·SHA256은 SOURCES.md에 기록했다. 공개 원본 라벨은 형식 검사와 표본 검토만 완료했으며 모두 사람이 재검수한 정답은 아니다.

```sh
python prepare_public_doors.py
python train_door.py --manifest data/public-doors-date-split/manifest.csv --output runs/public-nano-5epochs --device cpu --epochs 5 --batch 8 --workers 0 --imgsz 416
python run.py --source data/bus-3132290.mp4 --config configs/door-public-nano.json --output runs/nano-bus-new
```

CPU의 5 epoch·416 입력은 학습 실행 및 초기 전이 확인용이며 완성 모델이 아니다. 날짜 분할은 물리적 장소 분리까지 보장하지 않는다. 버스 클립은 학습에 넣지 않는다. `door-v8-public.json`은 별도로 받은 문 전용 가중치 비교 설정이고, 0.1의 낮은 신뢰도 문턱은 탐색용이다. 최종 카메라 기준으로 검증되지 않았다.

실행 결과에 `tracks.jsonl`과 문 후보 신뢰도, 모델 SHA256을 추가했다. 수동으로 확인한 통과 시각/방향의 JSONL 정답을 만들면 `python evaluate_events.py --predicted runs/NAME/events.jsonl --truth data/truth.jsonl`로 일대일 이벤트 대조가 가능하다. 정답 형식은 `{"time_s": 2.5, "direction": "in"}`이며 같은 수가 나와도 시각·방향이 틀리면 성공 처리하지 않는다.

정류장 설치 전 공개 영상 → 강의실 카메라 → 실제 버스 순으로 검증하는 독립 프로토타입이다. 기존 GPS·실내 측위·앱은 변경하지 않는다. 현재 실측 성능과 문 자동 검출 성공을 보장하지 않는다. 상세 실행 결과는 `STATUS.md`, 공개 자료는 `SOURCES.md`를 본다.

## 구조

- 사람: COCO 사전학습 YOLO11n + Ultralytics ByteTrack. 처음부터 재학습하지 않는다.
- 문: YOLO-World의 텍스트 지정 검출을 탐색용으로 연결했다. 실제 버스 시험에서 실패했으므로 확정 배포 모델이 아니다. 검수한 문 라벨로 YOLO11n을 미세조정하는 경로를 별도로 제공한다.
- 영역: 연속 문 검출의 IoU가 안정되면 좌표를 고정한다. 위치 변화·시간 초과 시 추적 이력을 비운다. 문이 없으면 집계를 중지한다. 자동 모드에서 수동 영역으로 몰래 대체하지 않는다.
- 집계: 사람 박스 하단 중앙(설정 가능)이 문 기준 두 구역을 순서대로 통과하면 IN/OUT 이벤트를 기록한다. 같은 쪽 체류·중간에서 회귀·영역 이탈·긴 추적 공백은 추가 집계하지 않는다.
- 결과: `annotated.mp4`, `events.jsonl`, `doors.jsonl`, `summary.json`, 검토용 프레임. FPS는 추론·추적·렌더링 포함, 모델 로딩 제외다.

## PC에서 재현

이 디렉터리에서 실행한다. 설치된 Windows 환경은 `.venv/Scripts/python.exe`이며 `requirements-windows-tested.txt`는 해당 환경 기록이다. Jetson에 Windows 의존성 잠금을 그대로 설치하지 않는다.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-world.txt
.venv/Scripts/python.exe -m unittest discover -p 'test_*.py' -v
.venv/Scripts/python.exe run.py --source data/people-walking.mp4 --config configs/walkway-smoke.json --output runs/walkway-new --max-frames 240
.venv/Scripts/python.exe run.py --source data/bus-3132290.mp4 --config configs/door-auto.json --output runs/bus-new
```

처음에는 공식 모델/CLIP 다운로드를 위한 인터넷이 필요하다. 출력 폴더는 기존 결과 보호를 위해 새 이름이어야 한다. `--source 0`은 USB 카메라다. 녹화 영상은 프레임을 건너뛰지 않고 전부 처리한다.

`walkway-smoke.json`은 문 없는 보행 영상의 **수동 가상 영역** 시험이며 자동 문 검출 증거가 아니다. 사람 전신 기준 모델이므로 뒤통수만 보이는 영상은 별도 머리 검출 모델과 좌표 기준이 필요하다.

## 우리 카메라에 맞출 항목

`counting.axis`는 화면의 통과 방향 x/y, `entry`는 좌표가 증가하면 positive/감소하면 negative다. `low/high`는 문 박스 안의 비율이다. 기본 0.4/0.6은 예시로, 실제 두 통과 위치에 맞게 보정해야 한다. 카메라 원근·기울기가 바뀌면 문 박스 하나만으로 통과 방향까지 알아낼 수 없다. 대각선 통과·문 앞 접근 영역의 투시 변환은 후속 과제다.

`person_anchor_y=1.0`은 발 위치, `0.5`는 몸 중앙이다. 가림이나 검출 박스 크기 변화에 영향을 받는다. `max_door_area=0.6`은 버스 측면 전체 오검출을 거부하는 탐색 설정이며 가까운 문은 거부할 수 있다. `door_interval_frames=10`은 비용을 줄이는 초기 설정이다. `ttl`보다 실제 검사 간격이 길면 잠금이 풀리므로 영상 FPS와 함께 조절한다.

한 번에 문 하나를 처리한다. 기본값은 최고 신뢰도 후보이며 선택 옵션을 켜면 버스 영역과 승객 발 주변의 지지로 후보를 선택하고 IoU로 연결한다. 여러 문을 동시에 집계하거나 문 역할을 확정적으로 구분하는 기능, 버스 ID·정차 세션 자동 분리, 문 열림 판정, ID 변경에 따른 중복 복구, 차량 전체 재실 인원은 아직 구현하지 않았다. 합계는 현재 실행 전체 IN/OUT이며 버스별 탑승자 수가 아니다. 영상 컷/탐색은 새 실행으로 나눈다.

## 문 추가 학습

공개 문 데이터의 클래스·라벨·이용 조건을 확인하고 `door` 단일 클래스로 수동 검수해 합친다. 창문·버스 전체를 문으로 라벨링하지 않는다. 문짝이 아닌 통과 가능한 입구 범위를 일관되게 지정한다. 버스 문과 강의실 문 모두 필요하면 두 환경을 포함하되 환경별 평가도 남긴다. 자동 라벨은 사람이 확인하기 전 정답으로 쓰지 않는다.

같은 영상의 인접 프레임을 train/val/test에 섞지 않는다. 촬영 회차·버스·카메라 위치 단위로 분리하고, 중복/유사 공개 데이터도 제거한다. 아래 CSV를 데이터 폴더에 작성한다. 각 이미지에는 대응하는 `labels/...txt`가 있어야 한다. 빈 라벨은 검수한 음성 이미지에만 쓴다.

```csv
image,session_id,split
images/train/a.jpg,bus_recording_01,train
images/val/b.jpg,bus_recording_02,val
images/test/c.jpg,classroom_recording_03,test
```

```sh
python train_door.py --manifest data/reviewed/manifest.csv --output runs/dataset-v1 --prepare-only
python train_door.py --manifest data/reviewed/manifest.csv --output runs/train-v1 --device 0 --epochs 50 --batch 4
```

첫 명령은 검수한 데이터의 회차 중복·동일 이미지 중복·라벨 형식 검사를 수행한다. 두 번째는 사전학습 YOLO11n에서 전이학습하고 best 체크포인트를 test 분할에서 평가한다. 50 epoch/batch 4는 초기값이다. 공개 문 사진과 AI 시각 검토 버스17장으로 개발 전이학습을 실행했다. 사람의 독립 라벨 교정과 새 촬영 정확도 검증은 아직 없다. 개발 PC/GPU에서 학습한 가중치를 Jetson에 배포하는 것을 기본으로 한다.

## Jetson Orin Nano 배포

실물의 RAM 용량·JetPack 버전은 미확인이다. 먼저 NVIDIA/Ultralytics 공식 Jetson 안내에 맞는 CUDA PyTorch 환경을 준비한다. 일반 PC용 torch wheel로 덮어쓰지 않는다. `torch.cuda.is_available()`를 확인하고 버전·전력모드·온도를 결과에 기록한다.

경량 배포 후보는 사람 YOLO11n + 미세조정 문 YOLO11n, 640 입력, batch 1, TensorRT FP16이다. **engine은 대상 Orin Nano에서 생성한다.** 학습용 GPU에서 만든 engine을 복사하지 않는다. 아래는 고정한 Ultralytics 8.3.228의 명령이며 실제 JetPack 조합 확인 전 실행 보장 없음.

```sh
yolo export model=models/person.pt format=engine half=True device=0 imgsz=640 batch=1
yolo export model=models/door.pt format=engine half=True device=0 imgsz=640 batch=1
python run.py --source data/test.mp4 --config configs/door-custom-orin.json --output runs/orin-test --device 0
```

`person.pt`는 사전학습 yolo11n.pt의 복사본, `door.pt`는 검증된 best.pt의 복사본이다. `.pt` 결과와 `.engine` 결과의 검출·집계 차이도 비교한다. INT8은 별도 대표 보정 데이터와 정확도 재검증 전 적용하지 않는다. YOLO-World는 탐색용으로 남기며 Nano에서 충분히 빠르다고 가정하지 않는다.

검증 기록: 영상별 사람 수 정답, 예측 IN/OUT, 누락·중복 시각, 문 박스 정확성/검출률, 영역 안정화 시간, 처리 FPS와 지연, 입력 해상도/FPS, 장치 환경. 정답 이벤트와 예측 이벤트를 일대일 대응해 방향별 precision/recall도 측정한다. 같은 클립을 튜닝한 뒤 얻은 수치를 독립 정확도로 보고하지 않는다.

최근 재개 비교와 실패 판정은 [CHECKPOINT.md](CHECKPOINT.md)의 2026-10-01 항목을 따른다. 도시 부분3/3은 개발 영상 인물·시각 검토이며 독립 정확도가 아니다.

## 보조 자세를 통한 가림 승객 비교

초록 개발 영상에서 기존5명 후보에 동시 YOLO11s-pose 관측을 보조하여 실제 전체6명·고정 부분6/6을 확인했다. 다른 모델의 ID를 같다고 보지 않고 같은 프레임의 유일한 박스 대응만 사용한다. 두 발목 모두 신뢰도가 충분해야 하며 발이 없으면 추정 좌표를 만들지 않는다. 발목 진입은 보류하여 뒤따르는 몸통 통과를 우선하고, 몸통이 가려져 추적이 끊기면 앞서 실제 관측한 증거의 시각과 집계 확정 시각을 함께 남긴다. 문 변경이나 관측된 복귀는 보류 신호를 해제한다.

```powershell
.venv/Scripts/python.exe run.py --source data/regression/bus-green-32245403-720.mp4 --config configs/bus-portal-aux-pose-deferred-candidate.json --output runs/NEW-UNUSED-RUN --device cpu
```

카메라 각도에 맞춘 집계 방향은 사전 설정하며 문 위치는 자동 검출한다. 이번 개발 결과에는 약1초 뒤 확정된 갈색 승객이 포함된다. 자세 추론 비용·독립 영상 일반화·Orin 실행 성능은 별도 검증 대상이다. `pose_aux_gate` 후보는 현재 자동 문 앞에 사람이 접근하는 동안만 보조 추론을 실행한다. 건너뛴 프레임에 지난 발목 좌표를 재사용하지 않는다.

### 조건부 자세 ONNX 후보와 위치 변화 한계

`configs/bus-portal-aux-pose-gated-onnx-candidate.json`은 현재 문 앞 접근 구간에서만 YOLO11s-pose ONNX를 호출한다. 전체 개발 촬영6명·보조288회, 버스 없는 실제 촬영은0회였다. 원본과 좌우 이동 영상 모두 비교해야 한다. 현재 좌우80픽셀 이동은4명으로 줄어든다. `diagnose_shift_geometry.py`는 저장 문/사람 관측을 교차 대입하는 원인 진단이며 새 추론이나 독립 정확도 시험이 아니다. `augment_portal_positions.py`는 원래 촬영 단위 분할을 유지하며 학습 이미지에만 이동·반전을 추가한다. 개발 영상 개선과 Jetson 실제 실행 검증은 별도다.

### 문 가림 재확인 개발 후보

`configs/bus-portal-aux-pose-partial-retry-candidate.json`은 부분 문 검출을 정상 관측으로 갱신하지 않고 빠르게 재확인한다. 전체 원본6/6·오른쪽2/6 유지, 왼쪽3/6→4/6(4→5명)이다. 기존 기본 후보를 자동 대체하지 않았다. 오른쪽 누락·왼쪽 청록 누락·독립 촬영·Orin 실행은 다음 검증 대상이다. 외형 거부 결합과 새 small 문 학습도 전체 비교했지만 추가 개선은 없었다.
