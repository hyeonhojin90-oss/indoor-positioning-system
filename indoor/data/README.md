# 실내 측위 데이터

휴대폰에서 수집한 원시 JSONL과 재현 가능한 오프라인 분석 결과를 보존한다.

- `raw/YYYY-MM-DD/`: Android `Downloads/IndoorPositioning`에서 가져온 변경하지 않은 원시 로그
- `manifest.json`: 경로, 사용자 판정과 사용 상태
- `analysis/`: 분석 스크립트가 생성한 요약, 구간 통계와 PDR 궤적

원시 로그는 크기가 크므로 Git LFS로 관리한다. 분석은 저장소 루트에서 다음처럼 실행한다.

```powershell
python .\indoor\tools\analyze_positioning_logs.py
```

현재 PDR 결과는 1차 오프라인 기준선이다. 복도 경로는 고정 0.75 m 보폭 궤적과 지도 끝점으로 보폭을 맞춘 보정 궤적을 함께 계산한다. 지도 끝점 보정 결과는 알고리즘 정확도의 독립 검증값이 아니다.
