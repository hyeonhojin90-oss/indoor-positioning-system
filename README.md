# 실내지도 제작 및 실내측위

조선대학교 IT융합대학의 실내 2D·3D 지도와 휴대폰 센서를 이용한 실내 위치 추정 연구·개발 자료다. 진현호가 담당한 지도 제작, 실내 측위 및 현장 수집·분석 내용을 증빙하기 위한 저장소다.

## 포함한 작업

- 피난안내도·현장 사진·GLB/LiDAR·실측을 활용한 1~10층 2D·3D 지도
- 실제 복도 거리표와 도면 표시 좌표의 변환, 층별 이동 가능 범위
- PDR·파티클·지도 제약, 자기장 격자/8걸음 패턴, BLE·AP 보정 코드
- Android 지도·강의실 안내·경로 라벨·센서 기준점 수집 앱과 이전 Expo 실험 앱
- 보행·기준점 측정 원본/정정본, 보폭·RoNIN·센서 조합 비교와 실패 사례

## 코드와 자료 찾기

| 경로 | 내용 |
|---|---|
| `indoor/web` | 2D·3D 지도, 공용 지도 자료와 측위 엔진 |
| `app/android-native` | Android Studio 앱 소스와 단위검사 |
| `app/expo-sensor-collector` | 이전 센서 수집·재생 실험 앱 |
| `app/android-updates` | Android 수정 및 검증 기록 |
| `indoor/data/raw`, `curated` | 측정 원본과 정정 자료 |
| `indoor/data/analysis` | 실험 조건·결과·오차·실패 사례 |
| `indoor/tools`, `tools` | 분석·재생·지도 검사·앱 동기화 도구 |
| `docs`, `indoor/docs` | 실내측위 진행상황·설계 결정·지도 근거 |

## 실행

Git LFS를 설치한 뒤 저장소를 복제한다.

```powershell
git clone https://github.com/hyeonhojin90-oss/indoor-positioning-system.git
cd indoor-positioning-system
git lfs pull
python -m http.server 4175 --bind 127.0.0.1 --directory indoor/web
```

2D 지도는 `http://127.0.0.1:4175/index.html`, 3D 지도는 `http://127.0.0.1:4175/clay.html`에서 확인한다. 3D 표시에는 인터넷으로 불러오는 Three.js가 필요하다.

Android Studio에서 `app/android-native`를 연다. SDK/JDK 및 빌드 방법은 [앱 안내](app/android-native/README.md)를 따른다. Node.js를 준비하면 `npm test`로 실내 검사 스크립트 14개를 실행한다. 브라우저 검사는 `npm ci`, 위 지도 서버와 Windows Edge를 준비한 뒤 `npm run test:browser`로 실행한다. Python 분석은 필요한 경우 `python -m pip install -r indoor/tools/requirements-analysis.txt`로 분석 패키지를 준비한다. RoNIN 학습 모델은 [출처·설치 안내](indoor/tools/ronin/README.md)에 따라 별도로 받는다.

## 현재 결과와 한계

지도·수집 앱·센서 융합 실험 코드를 구현했다. 자기장 보정으로 일부 기록의 평균 오차가 소폭 줄었지만 큰 누적 오차가 남아 있다. 같은 기록을 다시 계산한 개발 평가와 독립 현장 정확도를 구분한다. 전 층 자동 초기 위치·층 이동 종료 판정·설치 비콘 연동 등은 완료한 것으로 주장하지 않는다.

[현재 상태](docs/CURRENT_STATUS.md), [분석 자료](indoor/data/analysis), [미완료 항목](docs/INDOOR_AGREEMENT_AUDIT_20261002.md), [공개 범위](docs/GITHUB_SNAPSHOT_20261003.md)를 함께 확인한다. APK·개인 보고서·SDK 경로·개인키·빌드 캐시는 포함하지 않는다.
