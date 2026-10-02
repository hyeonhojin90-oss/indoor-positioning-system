# AP·BLE 기준점 분석

Android `보정 수집 → 센서 기준점`의 schema 7 JSONL은 신호를 저장하는 원본이다. `indoor/tools/analyze_radio_anchors.cjs`는 원본을 변경하지 않고, 신호가 위치 보정 후보로 쓸 만한지 검사한다.

## 기준점 수집 규칙

- 라벨의 `중앙선`, `정면`, `가로폭 중앙`, `첫 계단참 중앙`에 발 위치를 맞춘다. `내부`, `근처`, `앞쪽`만 적은 새 라벨은 사용하지 않는다.
- 휴대폰은 세로로 들고 진행 방향을 보며, 30초 동안 발 위치·방향·자세를 유지한다.
- 같은 기준점을 다시 수집할 때도 같은 물리 기준선을 사용한다. 자세 변화 실험은 기준 세션과 별도 파일로 저장한다.
- 오른쪽 계단 내부는 `출입문 통과 후 첫 계단참 중앙`, 왼쪽 계단은 입구 정면까지만 수집한다.

2층 2107·책상공간·TDM은 메인복도 PDR과 지도 제약으로 근처 안내한다. 2104/2105 계열은 증축부 진입을 확정하고 PDR 진행이 발생한 뒤 5초가 지나면 첫 AP를 요청한다. 그 다음부터는 판정 성공 여부와 관계없이 안내 종료까지 30초 간격으로 새 AP를 계속 요청한다. BLE는 이동 중 연속 관측하되 최근 3~5초 창을 사용한다. 이는 실제 안내 정책이며, 정지 기준점 수집의 시작 직후·30초 반복 AP 수집과 분리한다. 현재 정책은 실행 연결 전이며, 재현 확인을 통과한 지문 없이 좌표를 보정하지 않는다.

경로 라벨 수집은 사용자가 계속 이동하므로 AP를 요청하지 않는다. Android schema 8 경로 수집은 BLE만 경로 전체의 연속 시계열로 저장한다. 각 BLE 레코드의 `route_context`에는 당시 걸음 수, PDR 정합 좌표와 마지막 통과 랩이 들어간다. 정확한 위치의 AP 지문은 사용자가 기준선에 멈추는 schema 7 기준점 수집에서만 얻는다.

```powershell
node indoor/tools/analyze_radio_anchors.cjs "$env:USERPROFILE\Downloads\IndoorPositioning" --out indoor/data/analysis/radio-anchor-YYYYMMDD
```

출력은 `REPORT.md`와 `radio-anchor-report.json`이다.

- 세션별 AP 신선 스캔 수, BLE 관측 수, Bluetooth/권한/스캔 실패 상태를 확인한다.
- 같은 플랫폼·층에서 같은 `zone_id`를 세 번 이상 수집했는지 확인한다.
- 같은 구역 신호의 반복 관측률과 RSSI 표준편차를 보고, 회차 하나를 제외한 구역 판별도 계산한다.
- 원시 Wi-Fi BSSID와 BLE 식별자는 보고서에 출력하지 않는다.

이 도구의 `Top-1` 값은 정지 기준점 구역 분리력일 뿐 실제 보행 위치 정확도나 Fusion 개선을 뜻하지 않는다. 반복성·분리력이 확인되기 전에는 AP·BLE 결과를 위치 엔진 입력으로 사용하지 않는다.

도구 자체 검증:

```powershell
node indoor/tools/test_radio_anchor_analysis.cjs
```
