# AP·BLE 기준점 신호 분석

AP·BLE 신호 환경의 반복성·구역 분리력 사전검증. 위치 보정 또는 Fusion 적용 결과가 아님.

입력 8개 · 구역 비교 가능 schema 7 세션 8개 · 제외 0개

## 세션 상태

|파일|층·구역|완료|AP 신선 스캔/고유|BLE 관측/고유|상태|
|---|---|---|---:|---:|---|
|indoor_positioning_20260915_182257__corrected-f2-study-entry-main.jsonl|2 f2_study_entry_main|완료|2/151|912/99|BLE 스캔 활성|
|indoor_positioning_20260915_181723.jsonl|2 stairs_right|완료|1/79|442/50|BLE 스캔 활성|
|indoor_positioning_20260915_181815.jsonl|2 f2_extension_2104_1|완료|2/126|1426/147|BLE 스캔 활성|
|indoor_positioning_20260915_181913.jsonl|2 f2_extension_2105_2|완료|0/0|1205/154|BLE 스캔 활성|
|indoor_positioning_20260915_181950.jsonl|2 f2_extension_2105_2|완료|1/102|1239/151|BLE 스캔 활성|
|indoor_positioning_20260915_182041.jsonl|2 f2_extension_tdm_side|완료|1/96|753/93|BLE 스캔 활성|
|indoor_positioning_20260915_182132.jsonl|2 f2_study_inside|완료|1/113|1118/89|BLE 스캔 활성|
|indoor_positioning_20260915_182422.jsonl|2 f2_2107_entry_main|완료|2/127|724/105|BLE 스캔 활성|

## Wi-Fi AP 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|2|f2_2107_entry_main|1|127|127|0.00|더 필요|
|android|2|f2_extension_2104_1|1|126|126|0.00|더 필요|
|android|2|f2_extension_2105_2|2|102|0|—|더 필요|
|android|2|f2_extension_tdm_side|1|96|96|0.00|더 필요|
|android|2|f2_study_entry_main|1|151|151|0.00|더 필요|
|android|2|f2_study_inside|1|113|113|0.00|더 필요|
|android|2|stairs_right|1|79|79|0.00|더 필요|

회차 제외 구역 판별: 0개 평가 · Top-1 — · 중앙 공통 신호 —개 · 중앙 RSSI MAE — dB.
판정 보류: 같은 플랫폼·층에서 구역 2개 이상과 각 구역의 반복 수집이 필요합니다.

## BLE 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|2|f2_2107_entry_main|1|105|105|0.00|더 필요|
|android|2|f2_extension_2104_1|1|147|147|0.00|더 필요|
|android|2|f2_extension_2105_2|2|185|120|1.00|더 필요|
|android|2|f2_extension_tdm_side|1|93|93|0.00|더 필요|
|android|2|f2_study_entry_main|1|99|99|0.00|더 필요|
|android|2|f2_study_inside|1|89|89|0.00|더 필요|
|android|2|stairs_right|1|50|50|0.00|더 필요|

회차 제외 구역 판별: 2개 평가 · Top-1 1 · 중앙 공통 신호 120개 · 중앙 RSSI MAE 2.51 dB.

## 해석 규칙

- 이 결과는 신호 지문을 Fusion에 넣기 전의 품질 검사다. `Top-1` 수치가 있어도 실제 보행 위치 정확도가 증명되지는 않는다.
- BLE 또는 AP가 한 번만 잡히거나 RSSI 변동이 크면 위치 앵커로 사용하지 않는다.
- 보고서에는 원시 Wi-Fi BSSID와 BLE 식별자를 쓰지 않고 재현 가능한 익명 별칭만 내부 계산에 사용한다.
