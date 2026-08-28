# 교내 이동·실내 안내 프로젝트

조선대학교 자율설계학기제 프로젝트의 코드, 지도, 센서 실험과 문서를 한 저장소에서 관리한다.

## 영역

- `indoor/`: IT융합대학 1~10층 2D·3D 지도, PDR·자기장 실험, GLB 도구
- `gps/`: GPS 수집 펌웨어, 원시·가공 데이터, 실험 문서
- `app/`: 향후 Android/iOS 안내 앱
- `docs/`: 전체 구조, 결정, 진행상황과 작업 기록

## 현재 상태 확인

작업 시작 전 `AGENTS.md`, `docs/CURRENT_STATUS.md`, 작업 영역의 지침과 상태 문서를 순서대로 읽는다.

## 실내 지도 실행

```powershell
cd .\indoor\web
python -m http.server 4173 --bind 127.0.0.1
```

- 2D 지도: `http://127.0.0.1:4173/index.html`
- 3D 지도: `http://127.0.0.1:4173/clay.html`
- PDR 실험: `http://127.0.0.1:4173/pdr.html`

대용량 GLB·PDF·이미지는 Git LFS로 관리한다. 작업 완료는 코드 저장뿐 아니라 실행·검증과 상태 문서 갱신까지 포함한다.
