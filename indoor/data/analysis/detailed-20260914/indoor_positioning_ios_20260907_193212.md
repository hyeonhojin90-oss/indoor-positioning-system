# FREE_4_CORE / indoor_positioning_ios_20260907_193212.jsonl

원본: `C:\Users\20222967\Documents\카카오톡 받은 파일\indoor_positioning_ios_20260907_193212.jsonl`

SHA-256: `63843386456cd0dda7ffe97a419cfd0cffcd8b9079e7e3606ab8f827376c928c`

기존 분석: none found / 기존 상태: unregistered_diagnostic

시간 80.593초 · 카운터 80.000 · 가속도 피크 후보(.7/1/1.3): {'0.7': 96, '1.0': 92, '1.3': 81}

방향 출처: `absolute_heading_degrees`. 휴대폰 회전 후보를 보행 회전으로 확정하지 않는다.

![Sensor timelines](indoor_positioning_ios_20260907_193212.svg)

L0,L1…은 원본 라벨 시점이다. 표시 위치 정답이나 지도 경로가 아니다.

## 품질·한계

- No intermediate truth labels; final displayed position is an engine estimate, not arrival evidence.
- External/unregistered source; analyzed as diagnostic, not automatically accepted for training.

## 센서 기록

|센서|샘플|동일 wall time|중앙 간격 ms|최대 공백 s|
|---|---:|---:|---:|---:|
|accelerometer_mps2|1619|0|50.000|0.093|
|device_motion_rotation_rads|1618|0|50.000|0.094|
|gyroscope_rads|1619|0|50.000|0.093|
|heading_degrees|685|67|76.000|1.433|
|magnetic_field_ut|809|0|100.000|0.142|
|pressure_hpa|74|0|1075.000|1.526|
|step_counter|31|1|2548.000|5.095|

## 랩 구간 분석

|구간|초|카운터|피크 후보|동적 RMS|B 평균±SD µT|기압차 hPa|기기방향 변화°|
|---|---:|---:|---:|---:|---|---:|---:|
|코어복도 출구 중앙점 → session_end (not position truth)|80.593|80.000|92|1.423|46.078 ± 6.972|0.022|197.094|

## 2초 창의 휴대폰 방향 변화 후보

|시점 s|방향 변화°|자이로 RMS|동시 피크 후보|
|---:|---:|---:|---:|
|2.579|42.459|0.595|2|
|75.979|38.154|0.633|2|
|77.979|30.735|0.653|0|

각도 변화30°/2초는 진단용 기준이다. 자세 변화·자기장 교란·축 정의 영향을 포함한다. 가속도 피크도 실제 걸음 정답이 아니다. 샘플 수는 물리 센서의 독립 관측 수와 같지 않다.
