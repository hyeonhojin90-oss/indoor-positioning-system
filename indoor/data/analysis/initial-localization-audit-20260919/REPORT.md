# AP·BLE 기준점 신호 분석

AP·BLE 신호 환경의 반복성·구역 분리력 사전검증. 위치 보정 또는 Fusion 적용 결과가 아님.

입력 55개 · 구역 비교 가능 schema 7+ 세션 42개 · 제외 13개

## 세션 상태

|파일|층·구역|완료|AP 신선 스캔/고유|BLE 관측/고유|상태|
|---|---|---|---:|---:|---|
|indoor_positioning_20260915_173155.jsonl|4 core_junction|완료|1/107|586/187|BLE 스캔 활성|
|indoor_positioning_20260915_173215.jsonl|4 core_junction|완료|1/96|1031/180|BLE 스캔 활성|
|indoor_positioning_20260915_173252.jsonl|4 core_junction|완료|0/0|742/157|BLE 스캔 활성|
|indoor_positioning_20260915_181508.jsonl|4 stairs_right|완료|3/100|1173/106|BLE 스캔 활성|
|indoor_positioning_20260915_181723.jsonl|2 stairs_right|완료|1/79|442/50|BLE 스캔 활성|
|indoor_positioning_20260915_181815.jsonl|2 f2_extension_2104_1|완료|2/126|1426/147|BLE 스캔 활성|
|indoor_positioning_20260915_181913.jsonl|2 f2_extension_2105_2|완료|0/0|1205/154|BLE 스캔 활성|
|indoor_positioning_20260915_181950.jsonl|2 f2_extension_2105_2|완료|1/102|1239/151|BLE 스캔 활성|
|indoor_positioning_20260915_182041.jsonl|2 f2_extension_tdm_side|완료|1/96|753/93|BLE 스캔 활성|
|indoor_positioning_20260915_182132.jsonl|2 f2_study_inside|완료|1/113|1118/89|BLE 스캔 활성|
|indoor_positioning_20260915_182257.jsonl|2 f2_extension_entry|완료|2/151|912/99|BLE 스캔 활성|
|indoor_positioning_20260915_182422.jsonl|2 f2_2107_entry_main|완료|2/127|724/105|BLE 스캔 활성|
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
|indoor_positioning_20260919_111300.jsonl|—|—|—|—|제외: zone_id가 없어 구역 지문으로 비교할 수 없음|
|indoor_positioning_20260919_111351.jsonl|—|—|—|—|제외: zone_id가 없어 구역 지문으로 비교할 수 없음|
|indoor_positioning_20260919_111437.jsonl|—|—|—|—|제외: zone_id가 없어 구역 지문으로 비교할 수 없음|
|indoor_positioning_20260919_111521.jsonl|—|—|—|—|제외: zone_id가 없어 구역 지문으로 비교할 수 없음|
|indoor_positioning_20260919_111532.jsonl|—|—|—|—|제외: zone_id가 없어 구역 지문으로 비교할 수 없음|
|indoor_positioning_20260919_111618.jsonl|4 stairs_right|완료|1/82|164/38|BLE 스캔 활성|
|indoor_positioning_20260919_111707.jsonl|4 main_right|완료|1/96|194/42|BLE 스캔 활성|
|indoor_positioning_20260919_111758.jsonl|4 core_junction|완료|0/0|241/33|BLE 스캔 활성|
|indoor_positioning_20260919_112827.jsonl|4 stairs_left|완료|1/82|400/29|BLE 스캔 활성|
|indoor_positioning_20260919_112915.jsonl|4 main_left|완료|1/100|356/32|BLE 스캔 활성|
|indoor_positioning_20260919_113013.jsonl|4 core_junction|완료|0/0|348/40|BLE 스캔 활성|
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
|android|2|f2_2107_entry_main|2|181|64|1.63|더 필요|
|android|2|f2_extension_2104_1|1|126|126|0.00|더 필요|
|android|2|f2_extension_2105_1|1|110|110|0.00|더 필요|
|android|2|f2_extension_2105_2|3|121|0|—|완료|
|android|2|f2_extension_entry|2|151|0|—|더 필요|
|android|2|f2_extension_tdm_side|2|96|0|—|더 필요|
|android|2|f2_study_entry_main|1|0|0|—|더 필요|
|android|2|f2_study_inside|2|148|70|1.50|더 필요|
|android|2|main_left|1|95|95|0.00|더 필요|
|android|2|stairs_left|1|69|69|0.00|더 필요|
|android|2|stairs_right|2|116|42|0.50|더 필요|
|android|4|core_junction|6|207|0|—|완료|
|android|4|main_left|2|149|90|2.00|더 필요|
|android|4|main_right|2|174|71|5.00|더 필요|
|android|4|stairs_left|3|169|57|3.89|완료|
|android|4|stairs_right|3|165|49|4.11|완료|
|android|9|core_junction|2|218|19|0.50|더 필요|
|android|9|main_left|2|250|12|3.25|더 필요|
|android|9|main_right|1|119|119|0.00|더 필요|
|android|9|stairs_left|1|66|66|0.00|더 필요|
|android|9|stairs_right_inside|1|28|28|0.00|더 필요|

회차 제외 구역 판별: 25개 평가 · Top-1 0.72 · 중앙 공통 신호 81개 · 중앙 RSSI MAE 4.85 dB.

## BLE 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|2|core_junction|1|31|31|0.00|더 필요|
|android|2|f2_2107_entry_main|2|128|14|1.25|더 필요|
|android|2|f2_extension_2104_1|1|147|147|0.00|더 필요|
|android|2|f2_extension_2105_1|1|69|69|0.00|더 필요|
|android|2|f2_extension_2105_2|3|224|16|1.31|완료|
|android|2|f2_extension_entry|2|151|17|1.50|더 필요|
|android|2|f2_extension_tdm_side|2|137|14|2.13|더 필요|
|android|2|f2_study_entry_main|1|62|62|0.00|더 필요|
|android|2|f2_study_inside|2|119|13|1.00|더 필요|
|android|2|main_left|1|22|22|0.00|더 필요|
|android|2|stairs_left|1|15|15|0.00|더 필요|
|android|2|stairs_right|2|73|5|0.75|더 필요|
|android|4|core_junction|6|850|4|2.95|완료|
|android|4|main_left|2|590|8|1.75|더 필요|
|android|4|main_right|2|464|4|5.50|더 필요|
|android|4|stairs_left|3|611|5|1.31|완료|
|android|4|stairs_right|3|344|5|1.93|완료|
|android|9|core_junction|2|239|4|1.50|더 필요|
|android|9|main_left|2|321|3|3.25|더 필요|
|android|9|main_right|1|119|119|0.00|더 필요|
|android|9|stairs_left|1|72|72|0.00|더 필요|
|android|9|stairs_right_inside|1|33|33|0.00|더 필요|

회차 제외 구역 판별: 33개 평가 · Top-1 0.636 · 중앙 공통 신호 8개 · 중앙 RSSI MAE 2.59 dB.

## 해석 규칙

- 이 결과는 신호 지문을 Fusion에 넣기 전의 품질 검사다. `Top-1` 수치가 있어도 실제 보행 위치 정확도가 증명되지는 않는다.
- BLE 또는 AP가 한 번만 잡히거나 RSSI 변동이 크면 위치 앵커로 사용하지 않는다.
- 보고서에는 원시 Wi-Fi BSSID와 BLE 식별자를 쓰지 않고 재현 가능한 익명 별칭만 내부 계산에 사용한다.
