"""Update verified resume3 evidence while keeping running experiments explicit."""
import json
from pathlib import Path
from record_resume2_status import prepend
from latest_usage import latest

title='2026-10-01 세 번째 재개 검증: 검출좌표 복원·하차 근거·Orin 전달 준비'
u=latest(Path('C:/Users/20222967/.codex/sessions/2026/09/18/rollout-2026-09-18T20-25-08-01a0b417-a35f-7f33-a8e7-d28bc7398f3d_01a0b443-5bc9-7c11-80e2-c2c99e610aac.jsonl'))
Path('runs/usage-resume3-latest.json').write_text(json.dumps(u,indent=2))
body='''실제 작업 진행 중. 최신 사용자 중단 기준은 잔여5% 도달(used>=95)이다. Orin Nano는 곧 수령 예정이며 아직 미연결. 이전 기본/실험 파일 보존, 기존 가상환경 패키지 미수정.

원인 확인: 설치된 Ultralytics8.3.228 BYTETracker의 result 좌표는 Kalman 보정값이다. 기존 로그 raw_boxes는 nested bridge 전이라는 의미였고 검출 직후 박스는 아니었다. init_track은 high/low 분할 뒤 각각 index를 할당하여 동일 subset index가 두 검출을 가리킬 수 있다. `measured_detection_boxes.py`는 모델 callback에서 추적 전에 검출 목록을 보존하고 현재 활성 ID의 high/low subset·class·score를 검증하여 실제 관측 좌표를 복원한다. 추정/사라진 track 좌표를 사용하지 않는다. 버전/명시task/별도bus·자세 모델을 검증하며 기본 false. 같은 실제8프레임 fresh detector 양성59박스와 .001pixel/score1e-5로 일치했다. 검증된 버전의 특정 callback/index 의미에 의존하므로 새 버전은 별도 재검증해야 한다.

복원 좌표 후보 전체513프레임 원본6/1·고정6/6, 오른쪽5/0·4/6, 왼쪽5/0·5/6. 왼쪽 첫 승차가 이전49에서73으로 이동하여 고정55..85 안에 들어왔고 실제 ID55 관측68/71/73/76/80을 검토했다. 원본 OUT27은 발 미관측·이전 안쪽 발 증거 없음으로 오탐/uncertain이다. 짧은 최초 smoke의 잘못된 subset 해석 실패는 보존, v2 15프레임 완료는 smoke일 뿐이다.

`dual_anchor.exit_unknown_requires_inside` 선택 정책: 발이 없는 OUT에서 이전 confirm2 실제 문 안 발을 확인한 경우만 허용한다. 현재 발이 보이는 경우 기존 증거 정책 그대로, 기본false와 승차 조건/GT 창 유지. 저장재생에서 원본 false OUT 제거/반전4OUT 유지 후 실제전체4회 완료: 원본6/0·6/6, 오른쪽5/0·4/6, 왼쪽5/0·5/6, 반전1/4·뒤집은 고정3/6. 원본/좌우 이전 좌표 후보와 전체 input trace 정확히 동일하며 남은 이벤트도 정확히 같고 OUT27만 제거했다. 추가 partial 사람 ID 혼합/반전 false IN은 남아 있다. 개발 후보이며 기본 자동 승격 아님.

회귀: strict 후보 정지60프레임0/0, 버스 없는341프레임0/0·문활성0. 기존 기본 전체513프레임6/0·6/6, 이전 전체 검출·발점·ID·관측/집계 이벤트 완전 일치. 각 프로세스 exit0, summary, 전체source SHA/프레임/로그재생/시작hash감사 완료. 초기 감사는 후속 코드 변경 전에 보존한다. 전체 단위144통과.

별도 실험: head flow 재생 오른쪽5/0·왼쪽4/0, 원본 첫버전 canonical duplicate 오류. 실험모듈은 동시에 다시 나타난 ID를 합치지 않고 alias를 revoke하도록 수정하고3테스트 통과. 원본v2 전체513에서5/0으로 끝나 기존6명보다 개선 아님; 런타임 미도입. 오래된 first_seen 정리. partial person을 같은 프레임 pose의 전체몸으로 회복하는 진단은 왼쪽250/260/270/280/290/300/310에서 회복0, 자세모델은 실제 호출됐고 해결 근거 없어 런타임 미도입.

Orin 준비: `collect_device_environment.py`는 장치/JetPack/torch/CUDA/GPU/TensorRT 정보만 읽고 설치·전력모드·플래시 없음. 현재 Windows검사는 Jetson/CUDA/TensorRT 모두false로 올바르게 기록. `export_target_engine.py`는 실제Jetson Linux ARM64+CUDA torch+TensorRT+검증된Ultralytics8.3.228에서만 별도 새 폴더로 dynamic FP16 엔진을 생성하도록 준비, Windows에서 생성/실기기검증 안 함. 파일이 만들어져도 박스/자세·전체집계·지연 검증은 false다. Windows .venv/영상은 전달zip에 넣지 않는다. 모델과 코드의 라이선스를 유지한다. source video는 별도로 가져와 golden-events.json SHA와 대조해야 한다. 원본 권리 미확인 GitHub 워터마크 데모는 포함하지 않는다.

다음: 낮은 점수 검출0.05를 ByteTrack의 low단계에 활용하는 실제 전체 비교 → 사람별 소스/고정시각·오탐 검토 → 독립 촬영/Orin 환경과 온도·전력·메모리·전체pipeline 지연 검증. 새6/6 또는 전송 파일 성공을 현장 성공으로 처리하지 않는다.
'''
for n in ['green','green-right80','green-left80']:
    root=Path('runs')/(n+'-measured-low-score-resume3-full')
    if (root/'summary.json').exists():
        s=json.loads((root/'summary.json').read_text());state=f"summary {s['frames']}프레임 {s['counts']}, audit={(root/'completion-audit.json').exists()}"
    else:state='진행 중; 전체 성공 판정 없음'
    body+=f'\n- 낮은 점수 후보 `{root}`: {state}\n'
for name in ['orin-handoff-resume3-r1','orin-handoff-resume3-r3']:
    root=Path('exports')/name
    if root.with_suffix('.zip').exists():body+=f'\n- 전달 snapshot `{root.with_suffix(".zip")}` 준비됨; 대상하드웨어 검증 없음. 현재 코드의 자동 최신본이라는 뜻이 아니라 해당 시점의 고정 snapshot이다.\n'
    else:body+=f'\n- 전달 `{root}`는 작성 중; 완료 판정 없음.\n'
body+=f"\n사용량 {u['timestamp']}: 잔여{u['primary_remaining_percent']}%, fresh={u['fresh']}, stop={u['stop_reached']}.\n"
for f in ['CHECKPOINT.md','STATUS.md','RESULTS.md']:prepend(Path(f),title,body)
brief='검출 직후 좌표를 현재 ByteTrack ID/high-low subset과 대조해 복원, unknown-발 하차는 실제이전안쪽증거 요구 선택 기능. 전체 원본6/0·6/6 유지, 왼쪽5/0·고정4/6→5/6, 오른쪽5/0·4/6 유지; 반전1/4·3/6로 누락/ID혼합 남음. 정지/음성0/0, 기존 기본 전체 검출·집계 보존.144테스트. 낮은 점수 후보 전체 비교 중. Orin Nano 수령 전 환경검사·대상 엔진/무결성 전달 자료 준비. Orin/독립정확도 미검증. 잔여5%도달 기준으로 작업 계속. 상세 tools/passenger-counter/CHECKPOINT.md.'
for f in ['CURRENT_STATUS.md','WORKLOG.md']:prepend(Path('../../docs')/f,title,brief)
print('Verified resume3 state and pending comparisons saved.')
