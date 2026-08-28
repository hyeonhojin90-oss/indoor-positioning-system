# 실내 지도 웹

정적 HTML·CSS·JavaScript로 만든 IT융합대학 1~10층 지도 프로토타입이다.

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
