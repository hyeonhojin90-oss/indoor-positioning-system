# AP·BLE 기준점 신호 분석

AP·BLE 신호 환경의 반복성·구역 분리력 사전검증. 위치 보정 또는 Fusion 적용 결과가 아님.

입력 16개 · 구역 비교 가능 schema 7+ 세션 16개 · 제외 0개

## 세션 상태

|파일|층·구역|완료|AP 신선 스캔/고유|BLE 관측/고유|상태|
|---|---|---|---:|---:|---|
|indoor_positioning_20260915_173155.jsonl|4 core_junction|완료|1/107|586/187|BLE 스캔 활성|
|indoor_positioning_20260915_173215.jsonl|4 core_junction|완료|1/96|1031/180|BLE 스캔 활성|
|indoor_positioning_20260915_173252.jsonl|4 core_junction|완료|0/0|742/157|BLE 스캔 활성|
|indoor_positioning_20260915_181508.jsonl|4 stairs_right|완료|3/100|1173/106|BLE 스캔 활성|
|indoor_positioning_20260917_103443.jsonl|4 core_junction|완료|3/174|2855/526|BLE 스캔 활성|
|indoor_positioning_20260917_103649.jsonl|4 main_left|완료|3/139|4876/566|BLE 스캔 활성|
|indoor_positioning_20260917_103837.jsonl|4 stairs_left|미완료|2/110|2174/367|BLE 스캔 활성|
|indoor_positioning_20260917_103959.jsonl|4 stairs_left|완료|3/137|4500/493|BLE 스캔 활성|
|indoor_positioning_20260917_104254.jsonl|4 main_right|완료|3/149|4033/426|BLE 스캔 활성|
|indoor_positioning_20260917_104448.jsonl|4 stairs_right|완료|3/102|2009/213|BLE 스캔 활성|
|indoor_positioning_20260919_111618.jsonl|4 stairs_right|완료|1/82|164/38|BLE 스캔 활성|
|indoor_positioning_20260919_111707.jsonl|4 main_right|완료|1/96|194/42|BLE 스캔 활성|
|indoor_positioning_20260919_111758.jsonl|4 core_junction|완료|0/0|241/33|BLE 스캔 활성|
|indoor_positioning_20260919_112827.jsonl|4 stairs_left|완료|1/82|400/29|BLE 스캔 활성|
|indoor_positioning_20260919_112915.jsonl|4 main_left|완료|1/100|356/32|BLE 스캔 활성|
|indoor_positioning_20260919_113013.jsonl|4 core_junction|완료|0/0|348/40|BLE 스캔 활성|

## Wi-Fi AP 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|4|core_junction|6|207|0|—|완료|
|android|4|main_left|2|149|90|2.00|더 필요|
|android|4|main_right|2|174|71|5.00|더 필요|
|android|4|stairs_left|3|169|57|3.89|완료|
|android|4|stairs_right|3|165|49|4.11|완료|

회차 제외 구역 판별: 13개 평가 · Top-1 0.846 · 중앙 공통 신호 90개 · 중앙 RSSI MAE 5.89 dB.

## BLE 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|4|core_junction|6|850|4|2.95|완료|
|android|4|main_left|2|590|8|1.75|더 필요|
|android|4|main_right|2|464|4|5.50|더 필요|
|android|4|stairs_left|3|611|5|1.31|완료|
|android|4|stairs_right|3|344|5|1.93|완료|

회차 제외 구역 판별: 16개 평가 · Top-1 0.75 · 중앙 공통 신호 8개 · 중앙 RSSI MAE 3.12 dB.

## 해석 규칙

- 이 결과는 신호 지문을 Fusion에 넣기 전의 품질 검사다. `Top-1` 수치가 있어도 실제 보행 위치 정확도가 증명되지는 않는다.
- BLE 또는 AP가 한 번만 잡히거나 RSSI 변동이 크면 위치 앵커로 사용하지 않는다.
- 보고서에는 원시 Wi-Fi BSSID와 BLE 식별자를 쓰지 않고 재현 가능한 익명 별칭만 내부 계산에 사용한다.
