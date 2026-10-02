# AP·BLE 기준점 신호 분석

AP·BLE 신호 환경의 반복성·구역 분리력 사전검증. 위치 보정 또는 Fusion 적용 결과가 아님.

입력 7개 · 구역 비교 가능 schema 7 세션 7개 · 제외 0개

## 세션 상태

|파일|층·구역|완료|AP 신선 스캔/고유|BLE 관측/고유|상태|
|---|---|---|---:|---:|---|
|indoor_positioning_20260918_155958__verified-f9-core.jsonl|9 core_junction|완료|3/141|1578/163|BLE 스캔 활성|
|indoor_positioning_20260918_160148__verified-f9-main-left-9120.jsonl|9 main_left|완료|3/167|3625/241|BLE 스캔 활성|
|indoor_positioning_20260918_160943__corrected-f5-stairs-right-inside.jsonl|5 stairs_right_inside|완료|1/28|106/33|BLE 스캔 활성|
|indoor_positioning_20260918_161212__corrected-f5-main-right-5209.jsonl|5 main_right|완료|3/119|1527/119|BLE 스캔 활성|
|indoor_positioning_20260918_161443__corrected-f5-core.jsonl|5 core_junction|완료|2/96|498/80|BLE 스캔 활성|
|indoor_positioning_20260918_161545__corrected-f5-main-left-5119.jsonl|5 main_left|완료|1/95|588/83|BLE 스캔 활성|
|indoor_positioning_20260918_161643__corrected-f5-stairs-left.jsonl|5 stairs_left|완료|1/66|428/72|BLE 스캔 활성|

## Wi-Fi AP 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|5|core_junction|1|96|96|0.00|더 필요|
|android|5|main_left|1|95|95|0.00|더 필요|
|android|5|main_right|1|119|119|0.00|더 필요|
|android|5|stairs_left|1|66|66|0.00|더 필요|
|android|5|stairs_right_inside|1|28|28|0.00|더 필요|
|android|9|core_junction|1|141|141|0.00|더 필요|
|android|9|main_left|1|167|167|0.00|더 필요|

회차 제외 구역 판별: 0개 평가 · Top-1 — · 중앙 공통 신호 —개 · 중앙 RSSI MAE — dB.
판정 보류: 같은 플랫폼·층에서 구역 2개 이상과 각 구역의 반복 수집이 필요합니다.

## BLE 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|5|core_junction|1|80|80|0.00|더 필요|
|android|5|main_left|1|83|83|0.00|더 필요|
|android|5|main_right|1|119|119|0.00|더 필요|
|android|5|stairs_left|1|72|72|0.00|더 필요|
|android|5|stairs_right_inside|1|33|33|0.00|더 필요|
|android|9|core_junction|1|163|163|0.00|더 필요|
|android|9|main_left|1|241|241|0.00|더 필요|

회차 제외 구역 판별: 0개 평가 · Top-1 — · 중앙 공통 신호 —개 · 중앙 RSSI MAE — dB.
판정 보류: 같은 플랫폼·층에서 구역 2개 이상과 각 구역의 반복 수집이 필요합니다.

## 해석 규칙

- 이 결과는 신호 지문을 Fusion에 넣기 전의 품질 검사다. `Top-1` 수치가 있어도 실제 보행 위치 정확도가 증명되지는 않는다.
- BLE 또는 AP가 한 번만 잡히거나 RSSI 변동이 크면 위치 앵커로 사용하지 않는다.
- 보고서에는 원시 Wi-Fi BSSID와 BLE 식별자를 쓰지 않고 재현 가능한 익명 별칭만 내부 계산에 사용한다.
