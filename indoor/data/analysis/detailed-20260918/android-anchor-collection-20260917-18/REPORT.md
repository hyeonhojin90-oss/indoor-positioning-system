# AP·BLE 기준점 신호 분석

AP·BLE 신호 환경의 반복성·구역 분리력 사전검증. 위치 보정 또는 Fusion 적용 결과가 아님.

입력 13개 · 구역 비교 가능 schema 7 세션 13개 · 제외 0개

## 세션 상태

|파일|층·구역|완료|AP 신선 스캔/고유|BLE 관측/고유|상태|
|---|---|---|---:|---:|---|
|indoor_positioning_20260917_103443.jsonl|4 core_junction|완료|3/174|2855/526|BLE 스캔 활성|
|indoor_positioning_20260917_103649.jsonl|4 main_left|완료|3/139|4876/566|BLE 스캔 활성|
|indoor_positioning_20260917_103837.jsonl|4 stairs_left|미완료|2/110|2174/367|BLE 스캔 활성|
|indoor_positioning_20260917_103959.jsonl|4 stairs_left|완료|3/137|4500/493|BLE 스캔 활성|
|indoor_positioning_20260917_104254.jsonl|4 main_right|완료|3/149|4033/426|BLE 스캔 활성|
|indoor_positioning_20260917_104448.jsonl|4 stairs_right|완료|3/102|2009/213|BLE 스캔 활성|
|indoor_positioning_20260918_155958.jsonl|9 core_junction|완료|3/141|1578/163|BLE 스캔 활성|
|indoor_positioning_20260918_160148.jsonl|9 main_left|완료|3/167|3625/241|BLE 스캔 활성|
|indoor_positioning_20260918_160943.jsonl|9 stairs_right_inside|완료|1/28|106/33|BLE 스캔 활성|
|indoor_positioning_20260918_161212.jsonl|9 main_right|완료|3/119|1527/119|BLE 스캔 활성|
|indoor_positioning_20260918_161443.jsonl|9 core_junction|완료|2/96|498/80|BLE 스캔 활성|
|indoor_positioning_20260918_161545.jsonl|9 main_left|완료|1/95|588/83|BLE 스캔 활성|
|indoor_positioning_20260918_161643.jsonl|9 stairs_left|완료|1/66|428/72|BLE 스캔 활성|

## Wi-Fi AP 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|4|core_junction|1|174|174|0.00|더 필요|
|android|4|main_left|1|139|139|0.00|더 필요|
|android|4|main_right|1|149|149|0.00|더 필요|
|android|4|stairs_left|2|157|90|0.75|더 필요|
|android|4|stairs_right|1|102|102|0.00|더 필요|
|android|9|core_junction|2|218|19|0.50|더 필요|
|android|9|main_left|2|250|12|3.25|더 필요|
|android|9|main_right|1|119|119|0.00|더 필요|
|android|9|stairs_left|1|66|66|0.00|더 필요|
|android|9|stairs_right_inside|1|28|28|0.00|더 필요|

회차 제외 구역 판별: 6개 평가 · Top-1 0.5 · 중앙 공통 신호 11.5개 · 중앙 RSSI MAE 3.65 dB.

## BLE 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|4|core_junction|1|526|526|0.00|더 필요|
|android|4|main_left|1|566|566|0.00|더 필요|
|android|4|main_right|1|426|426|0.00|더 필요|
|android|4|stairs_left|2|587|273|0.75|더 필요|
|android|4|stairs_right|1|213|213|0.00|더 필요|
|android|9|core_junction|2|239|4|1.50|더 필요|
|android|9|main_left|2|321|3|3.25|더 필요|
|android|9|main_right|1|119|119|0.00|더 필요|
|android|9|stairs_left|1|72|72|0.00|더 필요|
|android|9|stairs_right_inside|1|33|33|0.00|더 필요|

회차 제외 구역 판별: 6개 평가 · Top-1 0.833 · 중앙 공통 신호 8개 · 중앙 RSSI MAE 2.88 dB.

## 해석 규칙

- 이 결과는 신호 지문을 Fusion에 넣기 전의 품질 검사다. `Top-1` 수치가 있어도 실제 보행 위치 정확도가 증명되지는 않는다.
- BLE 또는 AP가 한 번만 잡히거나 RSSI 변동이 크면 위치 앵커로 사용하지 않는다.
- 보고서에는 원시 Wi-Fi BSSID와 BLE 식별자를 쓰지 않고 재현 가능한 익명 별칭만 내부 계산에 사용한다.
