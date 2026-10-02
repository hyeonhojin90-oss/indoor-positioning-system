# 전체 실내 센서 자료 상세분석 — 2026-09-08

중복 제외 JSONL 29개, 기압 CSV 4개. 동일해시 사본 3개는 중복 계산하지 않았다.

## 분석 범위와 방법

저장소 raw와 알려진 카카오톡 센서 폴더를 전수 점검했다. 휴대폰에만 남은 데이터, 현재 원본 경로가 없는 과거 기록까지 분석했다고 주장하지 않는다. 제외 manifest는 유지하며 외부 자료는 자동 학습 편입하지 않는다.

시간축: wall_time_ms; 동일시각 평균 후 가속도20Hz 재표본화, 0.5초 초과 공백은 보간하지 않음. 0.85초 이동평균 제거, 최소 피크 간격0.28초와 높이0.7/1.0/1.3 m/s² 민감도 비교. 회전은2초 기기방향차30° 이상 후보이며 실제 회전·위치 정답이 아님. 기압 구간차는 앞/뒤20% 중앙값. 원시 통계와 파생 궤적을 혼동하지 않는다.

## 로그별 결과

|파일|경로|초|카운터|피크1.0|회전후보|상태|
|---|---|---:|---:|---:|---:|---|
|[indoor_positioning_20260901_124041.jsonl](indoor_positioning_20260901_124041.md)|9F_LEGACY_MISLABELED|25.828|—|34|5|legacy_excluded|
|[indoor_positioning_20260901_124143.jsonl](indoor_positioning_20260901_124143.md)|4F_LEGACY_TO_4204|48.108|—|69|2|legacy_excluded|
|[indoor_positioning_20260901_124318.jsonl](indoor_positioning_20260901_124318.md)|4F_LEGACY_TO_4128|45.897|—|73|2|legacy_excluded|
|[indoor_positioning_20260901_151808.jsonl](indoor_positioning_20260901_151808.md)|4F_CORE_TO_RIGHT_STAIRS|50.645|67.000|89|4|accepted|
|[indoor_positioning_20260901_151915.jsonl](indoor_positioning_20260901_151915.md)|4F_LEFT_OLD_MIXED_ROWS|70.783|87.000|125|12|legacy_excluded|
|[indoor_positioning_20260901_153038.jsonl](indoor_positioning_20260901_153038.md)|4F_CORE_TO_RIGHT_STAIRS|60.501|54.000|84|5|accepted_with_review|
|[indoor_positioning_20260901_155425.jsonl](indoor_positioning_20260901_155425.md)|4F_CORE_TO_LEFT_STAIRS|53.292|53.000|79|4|accepted|
|[indoor_positioning_20260901_155615.jsonl](indoor_positioning_20260901_155615.md)|3F_CORE_TO_RIGHT_STAIRS|51.324|70.000|78|1|accepted|
|[indoor_positioning_20260901_160634.jsonl](indoor_positioning_20260901_160634.md)|3F_CORE_TO_LEFT_STAIRS|62.016|67.000|75|4|accepted|
|[indoor_positioning_20260901_160817.jsonl](indoor_positioning_20260901_160817.md)|3F_EXTENSION|65.363|81.000|95|6|accepted|
|[indoor_positioning_20260901_161014.jsonl](indoor_positioning_20260901_161014.md)|3F_IT_HALL|52.823|75.000|87|9|accepted_with_review|
|[indoor_positioning_20260901_161220.jsonl](indoor_positioning_20260901_161220.md)|2F_CORE_TO_LEFT_STAIRS|44.708|62.000|74|5|accepted|
|[indoor_positioning_20260901_161342.jsonl](indoor_positioning_20260901_161342.md)|2F_CORE_TO_RIGHT_STAIRS|44.653|65.000|75|2|accepted_with_review|
|[indoor_positioning_20260901_161506.jsonl](indoor_positioning_20260901_161506.md)|2F_2107_OPEN|29.339|44.000|47|3|accepted|
|[indoor_positioning_20260901_161605.jsonl](indoor_positioning_20260901_161605.md)|2F_STUDY|53.228|58.000|82|14|accepted|
|[indoor_positioning_20260901_161730.jsonl](indoor_positioning_20260901_161730.md)|2F_EXTENSION|71.536|103.000|118|11|accepted_with_review|
|[indoor_positioning_20260901_161957.jsonl](indoor_positioning_20260901_161957.md)|1F_CORE_TO_LEFT_STAIRS|59.646|62.000|76|7|accepted|
|[indoor_positioning_20260901_162413.jsonl](indoor_positioning_20260901_162413.md)|5F_CORE_TO_RIGHT_STAIRS|51.983|60.000|94|4|accepted_with_review|
|[indoor_positioning_20260901_163040.jsonl](indoor_positioning_20260901_163040.md)|5F_OUTDOOR|57.028|77.000|99|6|accepted_with_review|
|[indoor_positioning_ios_20260905_170448.jsonl](indoor_positioning_ios_20260905_170448.md)|4F_CORE_TO_RIGHT_STAIRS|66.262|66.000|78|2|accepted|
|[indoor_positioning_ios_20260905_170648.jsonl](indoor_positioning_ios_20260905_170648.md)|4F_CORE_TO_RIGHT_STAIRS|78.393|43.000|80|2|accepted_with_pedometer_review|
|[indoor_positioning_ios_20260905_170852.jsonl](indoor_positioning_ios_20260905_170852.md)|4F_CORE_TO_RIGHT_STAIRS|59.436|70.000|79|3|accepted|
|[indoor_positioning_ios_20260905_185437.jsonl](indoor_positioning_ios_20260905_185437.md)|AUTO_4F_CORE|63.938|68.000|83|0|unregistered_diagnostic|
|[indoor_positioning_ios_20260907_193212.jsonl](indoor_positioning_ios_20260907_193212.md)|FREE_4_CORE|80.593|80.000|92|3|unregistered_diagnostic|
|[indoor_positioning_ios_20260907_205807.jsonl](indoor_positioning_ios_20260907_205807.md)|4F_CORE_TO_RIGHT_STAIRS|74.949|64.000|85|0|unregistered_diagnostic|
|[indoor_positioning_ios_20260908_132920.jsonl](indoor_positioning_ios_20260908_132920.md)|4F_CORE_TO_RIGHT_STAIRS|54.905|81.000|82|3|unregistered_diagnostic|
|[indoor_positioning_ios_20260908_133049.jsonl](indoor_positioning_ios_20260908_133049.md)|4F_CORE_TO_RIGHT_STAIRS_REVERSE|48.670|73.000|78|2|unregistered_diagnostic|
|[indoor_positioning_ios_20260908_133154.jsonl](indoor_positioning_ios_20260908_133154.md)|4F_CORE_TO_RIGHT_STAIRS|47.302|70.000|78|1|unregistered_diagnostic|
|[indoor_positioning_ios_20260908_133254.jsonl](indoor_positioning_ios_20260908_133254.md)|4F_CORE_TO_RIGHT_STAIRS_REVERSE|47.134|70.000|77|3|unregistered_diagnostic|

## 분기 자기장 분포 비교

동일 플랫폼·동일 층의 세션 전체 분포 비교다. 이동구간 구성이 달라 구역 분류 정확도가 아니며 반복 세션 검증을 대체하지 않는다.

|경로쌍|평균차/합동SD|중앙90% 범위 겹침|
|---|---:|---|
|3F_EXTENSION / 3F_IT_HALL|0.188|True|
|2F_2107_OPEN / 2F_STUDY|1.129|True|
|2F_2107_OPEN / 2F_EXTENSION|0.143|True|
|2F_STUDY / 2F_EXTENSION|0.950|True|

## 기압 CSV

|파일|샘플|초|끝-시작 hPa|0.44hPa 간격 수|
|---|---:|---:|---:|---:|
|[barometer_2026-08-29_20-03-33.csv](barometer_2026-08-29_20-03-33.svg)|1|0.000|0.0000|0.00|
|[barometer_2026-08-29_20-12-43.csv](barometer_2026-08-29_20-12-43.svg)|43|45.290|-3.9400|8.95|
|[barometer_2026-08-29_20-13-38.csv](barometer_2026-08-29_20-13-38.svg)|37|38.819|2.6100|5.93|
|[barometer_2026-08-29_20-35-51.csv](barometer_2026-08-29_20-35-51.svg)|32|33.424|1.3400|3.05|

0.44hPa 간격 수는 압력 변화를 환산한 참고값이며 실제 층이나 층 이동 정답이 아니다. 20-35-51 CSV의 실제 이동 경로는 별도 확인 필요.

## 원본·검증

`analysis.json`에 모든 원본 경로/해시, 기존 분석 범위, 센서 공백, 랩별 수치, 휴대폰 회전 후보와 기록된 엔진 종료값을 보존했다. 각 세션 MD/SVG/CSV로 시간축을 검토할 수 있다. 엔진 코드·지도·원시 데이터·manifest는 변경하지 않았다.
