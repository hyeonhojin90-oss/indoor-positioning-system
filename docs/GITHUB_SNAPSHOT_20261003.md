# 실내지도·측위 공개 범위

공개 저장소: https://github.com/hyeonhojin90-oss/indoor-positioning-system

현재 파일 구성은 1~10층 2D·3D 지도, 실내 측위 엔진, Android/Expo 수집 앱, 실측·보행·기준점 원본과 분석 결과다. GPS·승차 집계·학교 AI 도구·개인/팀 보고서 제작 도구·전체 프로젝트 문서는 현재 파일 구성에서 제외했다. 전체 개발 원본은 로컬 작업 폴더에 보존했다. 과거 커밋 기록은 그대로 남는다.

공용 웹/Android 알고리즘은 범위 정리를 위해 변경하지 않았다. 일부 분석 실행 안내가 제외한 도구의 Python 환경을 참조하고 있어 독립 Python 실행 안내로 바꿨다. 복제 시 Git LFS가 필요하다. 정확한 선별 범위와 검사 결과는 PUBLICATION_SCOPE.json을 따른다.

후속 전체 작업 폴더에서 공개본을 갱신할 때는 tools/export_indoor_publication.py --output exports/새폴더로 준비한 뒤 검토·검사·커밋·푸시한다. 전체 개발 저장소의 파일을 그대로 공개 저장소에 푸시하지 않는다.

검증: 실내 검사 스크립트14개, Android 단위37개·Lint 오류0/경고14·APK 빌드가 통과했다. 공용자산34개 SHA 일치 및 APK CRC를 확인했으며 생성 APK의 SHA는 이전 검증본과 동일했다. 지도·측위·수집 앱·측정 원본의 Git 변경이 없음을 확인했다. 기기 설치와 새 현장 정확도 평가는 수행하지 않았다.
