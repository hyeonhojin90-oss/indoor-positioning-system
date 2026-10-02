"""Record current resume without overwriting prior completed experimental evidence."""
import json
from pathlib import Path
from record_resume2_status import prepend
from latest_usage import latest

session=Path('C:/Users/20222967/.codex/sessions/2026/09/18/rollout-2026-09-18T20-25-08-01a0b417-a35f-7f33-a8e7-d28bc7398f3d_01a0b443-5bc9-7c11-80e2-c2c99e610aac.jsonl')
u=latest(session)
Path('runs/usage-resume3-latest.json').write_text(json.dumps(u,indent=2))
title='2026-10-01 세 번째 재개: 실측 박스·ID 연결·Orin 준비'
body='''재개 요청에 따라 실제 작업 진행 중. 최신 사용자 기준은 잔여5%까지(used>=95에서 중단)이며 이전 엄격히5% 미만 기준과 다르다. 사용량은 own-chat 최신 primary telemetry만 사용한다. Orin Nano는 사용자가 곧 가져올 예정이고 아직 연결되지 않았다.

기존 결과/기본 후보 보존. Head flow frozen 재생은 오른쪽5/0·왼쪽4/0으로 끝났고 원본은 simultaneous canonical alias 오류로 중단. 실패한 부분 로그를 성공으로 처리하지 않는다. 런타임에 도입하지 않았다.

설치된 Ultralytics8.3.228 ByteTrack은 반환 좌표가 Kalman 보정 결과다. 기존 raw_boxes는 nested bridge 전 좌표라는 의미이고 검출 직후 raw detection이라는 의미가 아니다. init_track은 high/low 분할 뒤 subset별 index를 할당한다. experimental person_measured_boxes는 tracker ID/score와 high/low subset을 확인하고 현재 검출 좌표를 복원해 집계/자세 연결에 사용한다. 분할 index를 전체 index로 처리한 첫 smoke는 실패 보존; 보정v2 15프레임 완료. 짧은 smoke는 전체 성공 아님. 원본/좌우 전체 영상 비교 중; 기존 기본false와 환경 원본 패키지 그대로다. 설치된 버전에만 허용한다.

문 위치/승차 방향/고정 인물·시간 구간은 바꾸지 않는다. head-flow/실측box는 대체 후보 비교이며 전체 검출·문·자세 실행 및 보수적 인물 검토 없이는 채택하지 않는다. 자료/Orin 준비는 hardware 확인 후 JetPack·CUDA·torch·TensorRT 환경을 수집하고 대상에서 엔진을 빌드/검증하도록 진행한다. Windows CPU 결과를 Orin 결과로 취급하지 않는다.
'''
body+=f"\n최근 사용량 {u['timestamp']}, remaining={u['primary_remaining_percent']}%, fresh={u['fresh']}.\n"
for f in ['CHECKPOINT.md','STATUS.md']:prepend(Path(f),title,body)
for f in ['CURRENT_STATUS.md','WORKLOG.md']:prepend(Path('../../docs')/f,title,'사용량 초기화100% 확인 후 재개. 잔여5% 도달 기준. Orin Nano 도착 전 겹침 ID 연결·현재 검출 박스 집계 후보 비교와 장치 환경 검사 준비 진행. 기존 기본 보존, 현장/Orin 미검증. 상세 tools/passenger-counter/CHECKPOINT.md.')
for name,reason in [('green-head-motion-resume3','Simultaneous canonical aliases; source-preserving partial replay, not completed.'),('green-current-detection-boxes-resume3-smoke','High/low subset indices incorrectly treated as full detection indices; failed before full completion.')]:
    p=Path('runs')/name/'failure.json'
    if not p.exists():p.write_text(json.dumps(dict(completed=False,reason=reason),indent=2))
print('Resume3 current state saved; inclusive five-percent stop.')
