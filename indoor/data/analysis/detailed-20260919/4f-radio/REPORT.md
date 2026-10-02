# AP·BLE 기준점 신호 분석

AP·BLE 신호 환경의 반복성·구역 분리력 사전검증. 위치 보정 또는 Fusion 적용 결과가 아님.

입력 11개 · 구역 비교 가능 schema 7+ 세션 6개 · 제외 5개

## 세션 상태

|파일|층·구역|완료|AP 신선 스캔/고유|BLE 관측/고유|상태|
|---|---|---|---:|---:|---|
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

## Wi-Fi AP 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|4|core_junction|2|0|0|—|더 필요|
|android|4|main_left|1|100|100|0.00|더 필요|
|android|4|main_right|1|96|96|0.00|더 필요|
|android|4|stairs_left|1|82|82|0.00|더 필요|
|android|4|stairs_right|1|82|82|0.00|더 필요|

회차 제외 구역 판별: 0개 평가 · Top-1 — · 중앙 공통 신호 —개 · 중앙 RSSI MAE — dB.
판정 보류: 같은 플랫폼·층에서 구역 2개 이상과 각 구역의 반복 수집이 필요합니다.

## BLE 반복성·구역 구분

|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|
|---|---:|---|---:|---:|---:|---:|---|
|android|4|core_junction|2|58|15|0.50|더 필요|
|android|4|main_left|1|32|32|0.00|더 필요|
|android|4|main_right|1|42|42|0.00|더 필요|
|android|4|stairs_left|1|29|29|0.00|더 필요|
|android|4|stairs_right|1|38|38|0.00|더 필요|

회차 제외 구역 판별: 2개 평가 · Top-1 1 · 중앙 공통 신호 15개 · 중앙 RSSI MAE 1.90 dB.

## 해석 규칙

- 이 결과는 신호 지문을 Fusion에 넣기 전의 품질 검사다. `Top-1` 수치가 있어도 실제 보행 위치 정확도가 증명되지는 않는다.
- BLE 또는 AP가 한 번만 잡히거나 RSSI 변동이 크면 위치 앵커로 사용하지 않는다.
- 보고서에는 원시 Wi-Fi BSSID와 BLE 식별자를 쓰지 않고 재현 가능한 익명 별칭만 내부 계산에 사용한다.
