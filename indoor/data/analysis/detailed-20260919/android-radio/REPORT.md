# AP·BLE 기준점 신호 분석

AP·BLE 신호 환경의 반복성·구역 분리력 사전검증. 위치 보정 또는 Fusion 적용 결과가 아님.

입력 19개 · 구역 비교 가능 schema 7+ 세션 11개 · 제외 8개

## 세션 상태

|파일|층·구역|완료|AP 신선 스캔/고유|BLE 관측/고유|상태|
|---|---|---|---:|---:|---|
|indoor_positioning_20260919_114450.jsonl|—|—|—|—|제외: zone_id가 없어 구역 지문으로 비교할 수 없음|
|indoor_positioning_20260919_114551.jsonl|—|—|—|—|제외: zone_id가 없어 구역 지문으로 비교할 수 없음|
|indoor_positioning_20260919_114630.jsonl|—|—|—|—|제외: zone_id가 없어 구역 지문으로 비교할 수 없음|
|indoor_positioning_20260919_114722.jsonl|—|—|—|—|제외: zone_id가 없어 구역 지문으로 비교할 수 없음|
|indoor_positioning_20260919_114854.jsonl|—|—|—|—|제외: zone_id가 없어 구역 지문으로 비교할 수 없음|
|indoor_positioning_20260919_114920.jsonl|—|—|—|—|제외: zone_id가 없어 구역 지문으로 비교할 수 없음|
|indoor_positioning_20260919_114945.jsonl|—|—|—|—|제외: zone_id가 없어 구역 지문으로 비교할 수 없음|
|indoor_positioning_20260919_115013.jsonl|—|—|—|—|제외: zone_id가 없어 구역 지문으로 비교할 수 없음|
|indoor_positioning_20260919_115115.jsonl|2 f2_extension_2105_2|완료|1/100|530/59|BLE 스캔 활성|
|indoor_positioning_20260919_115158.jsonl|2 f2_extension_2105_1|완료|1/110|547/69|BLE 스캔 활성|
|indoor_positioning_20260919_115239.jsonl|2 f2_extension_tdm_side|완료|0/0|443/58|BLE 스캔 활성|
|indoor_positioning_20260919_115315.jsonl|2 f2_study_inside|완료|1/105|289/43|BLE 스캔 활성|
|indoor_positioning_20260919_115408.jsonl|2 stairs_right|완료|1/79|163/28|BLE 스캔 활성|
|indoor_positioning_20260919_115455.jsonl|2 f2_extension_entry|완료|0/0|551/69|BLE 스캔 활성|
|indoor_positioning_20260919_115531.jsonl|2 f2_study_entry_main|완료|0/0|334/62|BLE 스캔 활성|
|indoor_positioning_20260919_115610.jsonl|2 f2_2107_entry_main|완료|1/118|210/37|BLE 스캔 활성|
|indoor_positioning_20260919_115706.jsonl|2 core_junction|완료|0/0|192/31|BLE 스캔 활성|
|indoor_positioning_20260919_115808.jsonl|2 main_left|완료|1/95|155/22|BLE 스캔 활성|
|indoor_positioning_20260919_115910.jsonl|2 stairs_left|완료|1/69|92/15|BLE 스캔 활성|

## Wi-Fi AP 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|2|core_junction|1|0|0|—|더 필요|
|android|2|f2_2107_entry_main|1|118|118|0.00|더 필요|
|android|2|f2_extension_2105_1|1|110|110|0.00|더 필요|
|android|2|f2_extension_2105_2|1|100|100|0.00|더 필요|
|android|2|f2_extension_entry|1|0|0|—|더 필요|
|android|2|f2_extension_tdm_side|1|0|0|—|더 필요|
|android|2|f2_study_entry_main|1|0|0|—|더 필요|
|android|2|f2_study_inside|1|105|105|0.00|더 필요|
|android|2|main_left|1|95|95|0.00|더 필요|
|android|2|stairs_left|1|69|69|0.00|더 필요|
|android|2|stairs_right|1|79|79|0.00|더 필요|

회차 제외 구역 판별: 0개 평가 · Top-1 — · 중앙 공통 신호 —개 · 중앙 RSSI MAE — dB.
판정 보류: 같은 플랫폼·층에서 구역 2개 이상과 각 구역의 반복 수집이 필요합니다.

## BLE 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|2|core_junction|1|31|31|0.00|더 필요|
|android|2|f2_2107_entry_main|1|37|37|0.00|더 필요|
|android|2|f2_extension_2105_1|1|69|69|0.00|더 필요|
|android|2|f2_extension_2105_2|1|59|59|0.00|더 필요|
|android|2|f2_extension_entry|1|69|69|0.00|더 필요|
|android|2|f2_extension_tdm_side|1|58|58|0.00|더 필요|
|android|2|f2_study_entry_main|1|62|62|0.00|더 필요|
|android|2|f2_study_inside|1|43|43|0.00|더 필요|
|android|2|main_left|1|22|22|0.00|더 필요|
|android|2|stairs_left|1|15|15|0.00|더 필요|
|android|2|stairs_right|1|28|28|0.00|더 필요|

회차 제외 구역 판별: 0개 평가 · Top-1 — · 중앙 공통 신호 —개 · 중앙 RSSI MAE — dB.
판정 보류: 같은 플랫폼·층에서 구역 2개 이상과 각 구역의 반복 수집이 필요합니다.

## 해석 규칙

- 이 결과는 신호 지문을 Fusion에 넣기 전의 품질 검사다. `Top-1` 수치가 있어도 실제 보행 위치 정확도가 증명되지는 않는다.
- BLE 또는 AP가 한 번만 잡히거나 RSSI 변동이 크면 위치 앵커로 사용하지 않는다.
- 보고서에는 원시 Wi-Fi BSSID와 BLE 식별자를 쓰지 않고 재현 가능한 익명 별칭만 내부 계산에 사용한다.
