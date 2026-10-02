# 실내 지도 웹

정적 HTML·CSS·JavaScript로 만든 IT융합대학 1~10층 지도 프로토타입이다.

## 2026-10-02 추적 좌표 비교

공용 navigation/Fusion은 층별 등록 통행 범위와 계단 평면 추적 중지 상태를 사용한다. 기본 `fusion-route-runtime.html`은 기존 좌표를 유지하며 `fusion-route-runtime.html?coordinates=meters`는 파티클 저장 좌표까지 m를 사용하는 선택 실험이다. 기존 엔진도 복도 진행량은 실측 거리표로 변환했다. m 버전은 별도 정확도 개선으로 확인되지 않았다.

JS `IndoorRuntime.snapshot`의 m 모드 x/y는 m다. Android host에는 기존 표시 x/y와 `metricPosition`의 m를 구분해 보낸다. 입력이 기존 좌표일 때만 `inputCoordinates:'legacy'`로 변환한다. 자세한 시험·제약·미검증/복구: `../data/analysis/meters-20261002/REPORT.md`. 최신 설치 APK가 이번 공용 코드를 이미 포함한다고 가정하지 않는다.

## 주요 파일

- `index.html`, `src/map-2d.js`: 2D 지도
- `clay.html`, `src/map-3d.js`: 단독·통합 3D 지도
- `pdr.html`, `src/pdr.js`: PDR·자기장 실험
- `data/maps/floor-01.json`~`floor-10.json`: 층별 지도 데이터
- `data/sensors/magnetic/floor-04.json`: 4층 자기장 측정값
- `pages/floors/`: 층별 2D 구조 검토도

## 실행

```powershell
python -m http.server 4173 --bind 127.0.0.1
```
