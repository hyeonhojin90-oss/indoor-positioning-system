# 전체 시스템 구조

```text
GPS·IMU·자기장 센서 → 위치 추정·보정 → 실내 지도 좌표 → 경로 탐색 → 웹·모바일 안내
```

## 저장소 영역

- `indoor/web`: 정적 웹 기반 2D·3D 지도와 PDR 실험
- `indoor/tools/glb-viewer`: LiDAR/GLB 검사와 변환
- `gps`: GPS 펌웨어, 데이터, 실험 코드
- `app`: 향후 공통 지도 데이터를 사용하는 Android/iOS 앱

## 실내 지도 구조

- `indoor/web/data/maps/floor-04.json`은 공통 본동·코어 기준 데이터다.
- 나머지 층 데이터는 `inherits: floor-04.json` 관계와 층별 오버라이드로 구성한다.
- `src/map-2d.js`는 메인 2D 화면, `src/map-3d.js`는 1~10층 단독·통합 3D 화면을 담당한다.
- `src/pdr.js`는 현재 3·4층 PDR 실험 화면을 담당한다.
- 층별 검토도는 `pages/floors/`, 관련 스타일·스크립트는 `src/floors/`에 둔다.

`indoor/web`을 정적 서버 루트로 실행하며 모든 웹 리소스 경로는 이 루트를 기준으로 유지한다.
