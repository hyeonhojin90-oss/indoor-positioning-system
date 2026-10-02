# AP·BLE 기준점 신호 분석

AP·BLE 신호 환경의 반복성·구역 분리력 사전검증. 위치 보정 또는 Fusion 적용 결과가 아님.

입력 8개 · 구역 비교 가능 schema 7+ 세션 8개 · 제외 0개

## 세션 상태

|파일|층·구역|완료|AP 신선 스캔/고유|BLE 관측/고유|상태|
|---|---|---|---:|---:|---|
|indoor_positioning_20260917_103443__verified-f4-core.jsonl|4 core_junction|완료|3/174|2855/526|BLE 스캔 활성|
|indoor_positioning_20260917_103649__verified-f4-main-left-4225.jsonl|4 main_left|완료|3/139|4876/566|BLE 스캔 활성|
|indoor_positioning_20260917_103959__verified-f4-stairs-left.jsonl|4 stairs_left|완료|3/137|4500/493|BLE 스캔 활성|
|indoor_positioning_20260917_104254__verified-f4-main-right-4209.jsonl|4 main_right|완료|3/149|4033/426|BLE 스캔 활성|
|indoor_positioning_20260917_104448__corrected-f4-stairs-right.jsonl|4 stairs_right|완료|3/102|2009/213|BLE 스캔 활성|
|indoor_positioning_20260922_211714-left-stairs-corrected.jsonl|4 stairs_left|완료|2/125|900/74|BLE 스캔 활성|
|indoor_positioning_20260922_211406.jsonl|4 core_junction|완료|2/159|674/77|BLE 스캔 활성|
|indoor_positioning_20260922_211528.jsonl|4 stairs_right|완료|2/92|232/46|BLE 스캔 활성|

## Wi-Fi AP 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|4|core_junction|2|212|121|1.25|더 필요|
|android|4|main_left|1|139|139|0.00|더 필요|
|android|4|main_right|1|149|149|0.00|더 필요|
|android|4|stairs_left|2|164|98|2.63|더 필요|
|android|4|stairs_right|2|141|53|3.50|더 필요|

회차 제외 구역 판별: 6개 평가 · Top-1 1 · 중앙 공통 신호 98개 · 중앙 RSSI MAE 6.15 dB.

## BLE 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|4|core_junction|2|597|6|2.00|더 필요|
|android|4|main_left|1|566|566|0.00|더 필요|
|android|4|main_right|1|426|426|0.00|더 필요|
|android|4|stairs_left|2|560|7|1.00|더 필요|
|android|4|stairs_right|2|254|5|3.00|더 필요|

회차 제외 구역 판별: 6개 평가 · Top-1 1 · 중앙 공통 신호 6개 · 중앙 RSSI MAE 3.33 dB.

## 해석 규칙

- 이 결과는 신호 지문을 Fusion에 넣기 전의 품질 검사다. `Top-1` 수치가 있어도 실제 보행 위치 정확도가 증명되지는 않는다.
- BLE 또는 AP가 한 번만 잡히거나 RSSI 변동이 크면 위치 앵커로 사용하지 않는다.
- 보고서에는 원시 Wi-Fi BSSID와 BLE 식별자를 쓰지 않고 재현 가능한 익명 별칭만 내부 계산에 사용한다.
