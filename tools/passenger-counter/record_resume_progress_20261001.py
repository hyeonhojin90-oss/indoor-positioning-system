from pathlib import Path

note='''## 2026-10-01 완료 후보 정리와 인물 재연결 원인 수정 실험

기준 후보는 `configs/bus-portal-aux-pose-gated-onnx-candidate.json`이다. 원본 전체513프레임 IN6/OUT0·고정 부분 인물/시각6/6을 보존한다. 아래 수치는 모두 개발 장면 또는 그 합성 파생이며 새 현장 정확도가 아니다. 기존 시각 정답은 변경하지 않았다.

| 완료 후보 | 원본 IN/OUT | 오른쪽80 IN/OUT | 왼쪽80 IN/OUT | 고정 부분 일치 |
| --- | --- | --- | --- | --- |
| 기존 문에서 저학습률 위치 증강 | 4/0 | 4/1 | 5/1 | 각각4/6,2/6,4/6 |
| 단일 small 자세 검출·추적 | 5/0 | 4/1 | 미실행 | 각각5/6,2/6 |
| 단일 medium 자세 검출·추적 | 미실행 | 5/1 | 미실행 | 오른쪽2/6 |

저학습률 문 학습은14epoch에서 조기 종료했다. 기존 3장·문2개 시험 세트 mAP50은0.129667이었지만 실제 전체 계수는 나빠졌고 잘못된 하차가 추가됐다. 재사용한 작은 시험 세트의 지표 상승으로 배포 모델을 바꾸지 않는다. 단일 small 자세 모델은 갈색 승객을 회복하지만 청록 승객을 놓쳤다. medium은 오른쪽 장면에서 잘못된 하차와 인물 혼합이 남았다. 모든 인물 리뷰와 평가를 각 실행 폴더 `identity-review.jsonl`, `identity-evaluation.json`에 기록했다. accepted는 인물 확인을 뜻하며 방향/시각까지 정답임을 뜻하지 않는다.

합성 시간 역방향 전체513프레임은 IN1/OUT3, 역변환한 원본 고정 구간2/6이었다. `green-reverse-aux-20261001-full/derived-review-windows.jsonl`은 원본 구간의 N-1-frame 변환이며 후보에 맞춘 시간 조정이 아니다. 실제 하차 독립 영상으로 취급하지 않는다.

외형 ReID 진단 `right80-reid-cost-diagnosis-20261001-v2`는 앞130프레임의 원래 raw ID/박스와 일치한다. ID3은 갈색 승객을 추적하다96~112에서 사라지고113에서 올리브 승객에게 재연결된다. 실제 선택된 검출 index4의 외형 비용0.401521은 허용0.2보다 크지만 박스/점수 비용0.680484가 허용되어 연결됐다. `lost_reid_guard.py`는 설치 패키지를 수정하지 않고 사라진 track에만 기존 외형 임계값의 거부를 적용한다. 기본 비활성이며 native PyTorch detect·BoTSORT·Ultralytics8.3.228만 허용한다. 오른쪽 전체513프레임은 ID3 재연결을 차단했지만 IN5/OUT0으로 끝났고 갈색 실측 발목 관측75는 고정 구간보다 이르다. 성공/기준 모델 승격으로 처리하지 않는다. 원본 회귀 실행을 계속한다.

`diagnose_partial_door.py`는 원래 문 후보를 재생하여 기본 문 잠금의 전체 좌표/세대를 먼저 정확히 재현했다. 현재 유효 문 안으로 작아지는 후보를 누락으로 취급하는 shadow는 원본6→6, 오른쪽4→4, 왼쪽4→5이었다. 마지막 정상 관측 시각과 TTL을 연장하지 않는다. 추론 일정·보조 발목·ID bridge가 원래 문에 의존하므로 이 결과는 실제 새 전체 추론의 개선 증거가 아니다. 실제 비교 전에는 채택하지 않는다.

run.py의 선택적 person_task=pose는 ONNX 자세 결과의 keypoint 처리를 명시한다. 기존 detect 기본 경로를 유지했고 대각 카메라 원본109프레임 IN1 회귀를 확인했다. 새 외형 guard의 lost/visible/알 수 없는 외형 구분과 설정 거부를 포함해 단위 테스트101개 통과. `render_event_review.py`는 원본 SHA를 확인하고 실제 이벤트·관측 프레임을 렌더링한다. 과거 완료 감사의 실행 당시 drift 없음 기록은 보존하며 이후 run.py 수정과 혼동하지 않는다.

목표 UI는 get_goal에서 여전히 blocked이며 현재 도구에는 active 재개 기능이 없다. 목표를 거짓 complete 처리하지 않았다. 실제 수정·학습·전체 영상 검증은 계속 진행 중이다. 계정 5시간 사용량은 마지막 확인79%, 사용자 중단 기준95% 미도달이다. Orin/TensorRT 실기기 성능은 미검증.

'''
for name in ('STATUS.md','RESULTS.md','CHECKPOINT.md'):
    p=Path(name);p.write_text(note+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
brief='''## 2026-10-01 승차 계수 정체 원인 분리와 실험 재개

원본6명 후보를 보존했다. 추가 문 학습·단일 자세 모델의 전체 영상 실행과 인물 평가를 완료했지만 이동 장면의 잘못된 하차/혼합 때문에 채택하지 않았다. 사라진 승객 ID가 다른 사람에게 재연결되는 실제 비용을 확인해 선택적 외형 거부를 구현하고 전체 비교 중이다. 문 가림에 따른 잠금 초기화도 별도 진단한다. 상세 결과는 `tools/passenger-counter/RESULTS.md`, 재개 상태는 `tools/passenger-counter/CHECKPOINT.md`에 있다. 단위 테스트101개 통과. 목표 UI의 blocked 표시는 도구로 해제하지 못했지만 실제 작업은 계속한다. 계정 사용량95% 기준 미도달.

'''
for name in ('../../docs/CURRENT_STATUS.md','../../docs/WORKLOG.md'):
    p=Path(name);p.write_text(brief+p.read_text(encoding='utf-8-sig'),encoding='utf-8')
p=Path('README.md');s=p.read_text(encoding='utf-8-sig')
p.write_text(s.replace('# 승차 인원 계수 실험 — Jetson Orin Nano 대상\n', '# 승차 인원 계수 실험 — Jetson Orin Nano 대상\n\n현재 기준은 `configs/bus-portal-aux-pose-gated-onnx-candidate.json`: 원본 개발 촬영 전체513프레임 IN6/OUT0·부분 인물/시각6/6이다. 좌우80픽셀 합성 이동은 각각4명으로 실패한다. 큰 자세 모델/추가 문 학습의 총계 상승만으로 후보를 바꾸지 않는다. 최신 전체 비교·한계는 [RESULTS.md](RESULTS.md), 실행 중 작업은 [CHECKPOINT.md](CHECKPOINT.md)를 먼저 읽는다. Orin 실기기 검증 전이다.\n',1),encoding='utf-8')
p=Path('SOURCES.md');s=p.read_text(encoding='utf-8-sig')
s+='''\n## 2026-10-01 추가 영상 후보 접근 조건 확인\n\n[Mixkit Lined up to board a bus](https://mixkit.co/free-stock-video/lined-up-to-board-a-bus-24971/)는 Restricted License 개인 용도 표시이며 [Mixkit 약관](https://mixkit.co/terms/)이 Envato AUP를 적용한다. [Envato AUP](https://help.elements.envato.com/hc/en-us/articles/31035788503321-Acceptable-Use-Policy) 4(m)은 허가 없는 AI/ML 개발 사용을 제한하므로 이번 알고리즘 자료에서 제외했다. 다운로드하지 않았다.\n\nPexels36445878은 기존 `data/bus-arrival-36445878.mp4`로 이미 확보한 촬영이다. 2026-10-01 다른 경로로 페이지 접근을 다시 시도했으나 HTTP403으로 새 파일은 받지 못했다. 새 독립 영상 확보로 보고하지 않는다. PAMELA는 연구 접근 허가가 필요하여 접근 우회/계정 요청을 하지 않았다. 기존 수집 자료와 합성 스트레스 검증을 계속한다.\n'''
p.write_text(s,encoding='utf-8')
