# 9F_LEGACY_MISLABELED / indoor_positioning_20260901_124041.jsonl

원본: `C:\Users\20222967\Documents\ChatGPT\자율설계 2\indoor\data\raw\2026-09-01\indoor_positioning_20260901_124041.jsonl`

SHA-256: `953a6d4926faf201fd3fbc866674c75999d9527d6d9627a8a958a8c4eb813406`

기존 분석: baseline summary/segments; excluded logs quality only / 기존 상태: legacy_excluded

시간 25.828초 · 카운터 — · 가속도 피크 후보(.7/1/1.3): {'0.7': 34, '1.0': 34, '1.3': 34}

방향 출처: `quaternion_device_yaw_not_walking_heading`. 휴대폰 회전 후보를 보행 회전으로 확정하지 않는다.

![Sensor timelines](indoor_positioning_20260901_124041.svg)

L0,L1…은 원본 라벨 시점이다. 표시 위치 정답이나 지도 경로가 아니다.

## 품질·한계

- Excluded by existing manifest; quality audit only, not training or truth.
- No intermediate truth labels; final displayed position is an engine estimate, not arrival evidence.
- Device orientation is not calibrated walking direction; no absolute map-path accuracy claim.

## 센서 기록

|센서|샘플|동일 wall time|중앙 간격 ms|최대 공백 s|
|---|---:|---:|---:|---:|
|accelerometer_mps2|11826|1449|2.000|0.016|
|gyroscope_rads|1182|2|22.000|0.042|
|magnetic_field_ut|1295|1|20.000|0.027|
|pressure_hpa|161|0|160.000|0.169|
|rotation_vector|1183|2|21.000|0.042|

## 랩 구간 분석

|구간|초|카운터|피크 후보|동적 RMS|B 평균±SD µT|기압차 hPa|기기방향 변화°|
|---|---:|---:|---:|---:|---|---:|---:|
|코어복도·메인복도 교차점 → session_end (not position truth)|25.828|—|34|1.993|120.076 ± 103.259|0.004|54.873|

## 2초 창의 휴대폰 방향 변화 후보

|시점 s|방향 변화°|자이로 RMS|동시 피크 후보|
|---:|---:|---:|---:|
|4.052|-30.290|0.444|1|
|6.052|-67.228|0.989|3|
|9.252|-30.539|0.581|3|
|22.252|31.629|0.811|3|
|24.252|165.460|1.905|3|

각도 변화30°/2초는 진단용 기준이다. 자세 변화·자기장 교란·축 정의 영향을 포함한다. 가속도 피크도 실제 걸음 정답이 아니다. 샘플 수는 물리 센서의 독립 관측 수와 같지 않다.
