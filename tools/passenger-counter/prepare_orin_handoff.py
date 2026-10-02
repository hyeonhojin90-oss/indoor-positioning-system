"""Build a local portable runtime/model snapshot, without Windows venv or videos."""
import argparse,ast,hashlib,json,shutil,zipfile
from pathlib import Path

def runtime_closure(start):
    found=set();pending=list(start)
    while pending:
        p=Path(pending.pop())
        if p in found:continue
        if not p.is_file():raise ValueError(f'Missing local runtime dependency {p}')
        found.add(p)
        for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
            names=[]
            if isinstance(n,ast.Import):names=[a.name.split('.')[0] for a in n.names]
            if isinstance(n,ast.ImportFrom) and n.module:names=[n.module.split('.')[0]]
            for name in names:
                local=Path(name+'.py')
                if local.is_file() and local not in found:pending.append(local)
    return sorted(found)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists() or a.output.with_suffix('.zip').exists():raise ValueError('Output snapshot already exists')
    configs=['bus-portal-aux-pose-gated-onnx-candidate.json','bus-portal-segment-trained-box-guard-onnx-r2.json','bus-portal-current-detection-boxes-resume3.json','bus-portal-measured-strict-exit-resume3.json','bus-portal-measured-acquisition-fallback-resume3.json','bus-portal-default-profiled-resume3.json']
    a.output.mkdir(parents=True);(a.output/'configs').mkdir();(a.output/'models').mkdir();(a.output/'evidence').mkdir()
    origins={}
    def copy(src,target):
        src=Path(src);shutil.copy2(src,target);origins[target.relative_to(a.output).as_posix()]=str(src)
    for src in runtime_closure(['run.py','run_experiment.py','audit_completed_run.py','collect_device_environment.py','verify_handoff.py','export_target_engine.py','prepare_engine_config.py','verify_target_run.py','verify_engine_run.py','compare_model_frames.py','serve_passage_review.py']):copy(src,a.output/src.name)
    copy('passage_review.html',a.output/'passage_review.html')
    (a.output/'licenses').mkdir()
    copy('.venv/Lib/site-packages/ultralytics-8.3.228.dist-info/licenses/LICENSE',a.output/'licenses/Ultralytics-AGPL-3.0.txt')
    weights={};checkpoints={}
    for name in configs:
        c=json.loads((Path('configs')/name).read_text())
        from prepare_engine_config import runtime_roles,expected_size
        from verify_target_run import model_path
        roles=runtime_roles(c)+(['door_primary_model'] if 'door_primary_model' in c else [])
        for key in roles:
            src=model_path(c,key);digest=hashlib.sha256(src.read_bytes()).hexdigest()
            target=a.output/'models'/(key+'-'+digest[:12]+src.suffix)
            if not target.exists():copy(src,target)
            value=c;parts=key.split('.')
            for part in parts[:-1]:value=value[part]
            portable=target.relative_to(a.output).as_posix()
            value[parts[-1]]=portable;weights[portable]=dict(sha256=digest,role=key)
            if src.suffix=='.onnx':
                pt=src.with_suffix('.pt');proof=json.loads((src.parent/'parity.json').read_text())
                pt_hash=hashlib.sha256(pt.read_bytes()).hexdigest()
                assert proof['parity_passed'] and proof['onnx_sha256']==digest and proof['checkpoint_sha256']==pt_hash
                pt_target=a.output/'models'/(key+'-'+pt_hash[:12]+'.pt')
                if not pt_target.exists():copy(pt,pt_target)
                runtime_imgsz=expected_size(c,key)
                checkpoints[portable]=dict(path=pt_target.relative_to(a.output).as_posix(),sha256=pt_hash,task_in_export_proof=proof.get('task'),runtime_imgsz=runtime_imgsz,fixed_parity_imgsz=proof['imgsz'])
        (a.output/'configs'/name).write_text(json.dumps(c,indent=2),encoding='utf-8')
    for src in ['models/yolo11s-seg-trained-box-detector-r2.source.json','runs/verified-resume2-experiment-index-r2.json','runs/segment-trained-box-cpu-inference-timing-r2.json','data/commons-moving-bus-boarding-resume3.source.json','runs/commons-enriched-door640-parity-resume3.json','runs/green-default-profile-preservation-resume3.json','runs/green-default-after-rtdetr-preservation-resume3.json']:
        copy(src,a.output/'evidence'/Path(src).name)
    golden=[]
    specifications=[(name+'-20261001-r2-full','bus-portal-segment-trained-box-guard-onnx-r2.json') for name in ['green-segment-trained-box','green-right80-segment-trained-box','green-left80-segment-trained-box','green-reverse-segment-trained-box','stationary-segment-trained-box','people-negative-segment-trained-box']]
    specifications+=[(name+'-measured-strict-exit-resume3-full','bus-portal-measured-strict-exit-resume3.json') for name in ['green','green-right80','green-left80','green-reverse']]
    specifications+=[('stationary-resume3-full','bus-portal-measured-strict-exit-resume3.json'),('people-negative-resume3-full','bus-portal-measured-strict-exit-resume3.json'),('green-default-regression-resume3-full','bus-portal-aux-pose-gated-onnx-candidate.json')]
    specifications+=[(name+'-acquisition-fallback-resume3-full','bus-portal-measured-acquisition-fallback-resume3.json') for name in ['commons-boarding','green','green-left80','green-right80','green-reverse','stationary','people-negative','pink','arrival']]
    specifications+=[('green-default-after-acquisition-resume3-full','bus-portal-aux-pose-gated-onnx-candidate.json')]
    specifications+=[('green-engine-backend-default-regression-resume3-full','bus-portal-aux-pose-gated-onnx-candidate.json')]
    specifications+=[('green-default-profiled-resume3-full','bus-portal-default-profiled-resume3.json')]
    specifications+=[('green-default-after-rtdetr-nms-resume3-full','bus-portal-default-profiled-resume3.json')]
    specifications+=[('green-default-appearance-isolation-resume4-full','bus-portal-default-profiled-resume3.json')]
    for src in ['runs/green-default-source-clock-preservation-resume4.json','runs/green-default-appearance-isolation-preservation-resume4.json','runs/file-as-live-clock-smoke-resume4/observed-trace-audit.json']:
        copy(src,a.output/'evidence'/Path(src).name)
    from verify_target_run import config_signature
    for name,config_name in specifications:
        root=Path('runs')/name;s=json.loads((root/'summary.json').read_text())
        completion=json.loads((root/'completion-audit.json').read_text())
        assert completion['complete_source'] and completion['replay_parity'] and not completion['implementation_drift_since_start']
        copied=json.loads((a.output/'configs'/config_name).read_text())
        assert config_signature(copied)==config_signature(s['config'])
        events=[json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()]
        golden.append(dict(name=name,config_snapshot='configs/'+config_name,config=s['config'],model_sha256=s['model_sha256'],source=s['source'],source_sha256=s['source_sha256'],frames=s['frames'],counts=s['counts'],events=events,source_included=False,development_baseline=True,independent_accuracy_validated=False))
    (a.output/'evidence/golden-events.json').write_text(json.dumps(golden,indent=2),encoding='utf-8')
    instructions='''# Orin Nano 수령 후 첫 검증

이 자료는 Windows에서 검증한 실행 코드·모델의 local snapshot이다. Orin 검증/실시간 성공을 뜻하지 않는다. Windows .venv와 동영상은 포함하지 않았다. AGPL Ultralytics 모델/코드와 원 출처 라이선스를 유지한다. 기기별 JetPack/CUDA/torch/TensorRT 버전은 확정하지 않았다.

1. 장치에서 python3 verify_handoff.py로 전송 무결성을 확인한다.
2. python3 collect_device_environment.py --output orin-environment.json 실행. 이 명령은 환경만 읽고 설치/전력모드 변경/플래시를 하지 않는다.
3. 수집한 JetPack·CUDA에 맞는 NVIDIA 제공 GPU torch/torchvision 및 TensorRT 설치 상태를 확인한다. Windows requirements를 설치하지 않는다. 현재 callback/index 복원 후보는 Ultralytics8.3.228에 한정된다. 최신 패키지로 무조건 업그레이드하지 않는다.
4. 원본 영상 파일을 별도로 가져와 evidence/golden-events.json의 SHA256과 비교한다. 다른 영상으로 같은 정답을 주장하지 않는다.
5. 우선 검증된 기본/출력부 제거 ONNX 후보를 기기 GPU에서 실행하고 CUDA provider·메모리·완료 summary/이벤트를 확인한다. 조건부 자세를 포함한 전체 파이프라인의 시간이 필요하다.
6. TensorRT engine은 실제 대상 장치에서 새 별도 폴더로 빌드한다. 고정640 square로 바꾸면 현재 rect 입력과 결과가 달라질 수 있어 전체 비교가 필요하다. FP16 수치 차이는 실제 박스/자세/이벤트로 확인한다. INT8은 대표 calibration 데이터/정확도 회귀 없이 적용하지 않는다.

예시: python3 run_experiment.py --source ORIGINAL-VIDEO.mp4 --config configs/bus-portal-segment-trained-box-guard-onnx-r2.json --output runs/ORIN-NEW-RUN --device 0

run_experiment.py는 자신이 시작한 run.py의 실제 종료코드와 summary/전체source 감사 결과를 runs/ORIN-NEW-RUN.process.json에 함께 남긴다. 로그는 .process.log다. process_finished만으로 전체완료를 주장하지 않으며 full_run_verified=true를 확인한다. --max-frames 시험은 실제전체프레임과 달라 full_run_verified=false다. 중단 후 phase=running이면 완료를 의미하지 않는다.

bus-portal-measured-acquisition-fallback-resume3.json은 문 잠금과 주모델의 지원후보가 없고 strong bus가 있을 때만 보강640 문 모델을 추가로 사용한다. 기존 초록 원본/좌우/반전은 주모델의 전체검출·이벤트를 그대로 유지했고 Commons 별도 촬영에서1건 승차를 검토했다. 다른 두 버스 영상에서는 문을 잡지 못해0명이다. 새 장면 전체정확도나 현장 일반화를 증명한 후보가 아니다. 보조문도 PT 계보와 ONNX SHA를 manifest에 기록했다.

실행 후: python3 verify_target_run.py --run runs/ORIN-NEW-RUN --golden evidence/golden-events.json --name green-segment-trained-box-20261001-r2-full --environment orin-environment.json --output runs/ORIN-NEW-RUN/target-regression.json . 실제 원본 SHA/전체프레임/모델 SHA/설정/인물ID·관측·확정 이벤트와 각 ONNX CUDA provider를 확인한다. 같은 총계라도 다른 ID/조기 집계면 실패한다. 코드의 프로세스 exit0도 별도로 확인한다. 독립 정확도·GPU 연산 profiling·장시간 온도/지연 검증은 별도다.

각 model을 바꿀 때 compare_model_frames.py --reference models/PT.pt --candidate exports/ENGINE.engine --source ORIGINAL-VIDEO.mp4 --frames 59 89 180 260 331 357 --imgsz 640 --task detect --device 0 --output engine-frames.json 으로 실제 rect 입력 박스/점수부터 대조한다. 자세는 --task pose, 문은 --imgsz 416이다. 기본 ONNX baseline verifier는 다른 engine SHA를 자동 승인하지 않는다.

엔진을 모두 빌드한 뒤 prepare_engine_config.py --config configs/선택후보.json --manifest handoff-manifest.json --exports person_model=exports/PERSON/export.json door_model=exports/DOOR/export.json bus_model=exports/BUS/export.json pose_aux_model=exports/POSE/export.json --output configs/NEW-ENGINE-CANDIDATE 로 별도 설정을 만든다. 보조문 후보는 door_acquisition_fallback.model=exports/FALLBACK/export.json도 필요하다. 실제 활성 역할 모두·원PT SHA·detect/pose task·원래 입력크기·동적 FP16 batch1·대상환경·engine SHA를 확인한다. 원본ONNX 설정을 덮어쓰지 않는다. 설정 생성만으로 엔진 로딩·박스·자세·전체집계 검증을 대신하지 않는다.

parity 명령의 --conf/--classes도 실제설정과 맞춘다: 현재 사람 .1/[0], 문 .35/[0], 버스 .05/[5], 자세 .1/[0]이다. 입력은 사람/버스/자세/보조문640, 주문416이며 rect=True를 유지한다. compare_model_frames.py는 실제양성 프레임·박스/점수/자세를 대조하고 대상환경·실제로딩한GPU context를 기록한다. 입력파일 변경도 앞뒤 SHA로 확인한다.

엔진 전체실행 뒤 verify_engine_run.py --run runs/ORIN-ENGINE-RUN --golden evidence/golden-events.json --name 해당baseline이름 --environment orin-environment.json --original-config configs/원ONNX후보.json --manifest handoff-manifest.json --engine-provenance configs/NEW-ENGINE-CANDIDATE/provenance.json --parities person_model=person-frames.json door_model=door-frames.json bus_model=bus-frames.json pose_aux_model=pose-frames.json --output runs/ORIN-ENGINE-RUN/engine-regression.json 으로 검사한다. 사용된보조문이 있으면 그 role의parity도 필수다. 동일원PT계보·실제GPU dynamicFP16 context·원클립양성표본·박스/자세일치재계산·전체source감사·이벤트를 요구한다. 같은총계만으로 통과하지 않는다. 미호출보조문은 validated 목록에서 제외되어 다른clip검증이 필요하다. 전체raw검출동일성/독립현장정확도/GPUoperation profiling/지속성능은 이검사에 포함되지 않는다.

person_measured_boxes+strict-exit 후보는 원본/좌우/반전 전체 완료, 고정6/6·4/6·5/6이며 기본 후보는 아니다. 일부 누락/ID 혼합이 남는다. handoff-manifest.json의 export_checkpoints에는 ONNX와 SHA로 연결된 PT 원본이 있어 실제 대상에서 export_target_engine.py --model models/해당-model.pt --imgsz 640 --output exports/NEW-TARGET-ENGINE 로 새 엔진을 만들 수 있다. 문 모델은416, 사람/버스/자세는640을 유지한다. 기존 문 위치 자동 취득과 설치별 집계 방향 설정은 그대로다. 입력영상/카메라·독립 사람정답/온도/전력모드/메모리/지연을 함께 기록해야 성능을 판단할 수 있다.

단계별 시간 측정은 configs/bus-portal-default-profiled-resume3.json으로 별도 실행한다. profile_pipeline=true는 읽기/사람/버스·문/자세/추적·집계/표시·저장/진단 시간을 pipeline-timing.jsonl과 summary.pipeline_profile에 기록한다. 최초5프레임은 시작 구간으로 분리한다. GPU 실행은 단계 사이 CUDA 동기화를 사용하므로 실제 비동기 운영과 스케줄이 달라질 수 있다. Windows 병렬 CPU 시험 시간은 Orin FPS가 아니다. 513프레임 기본시험과 사람검출/ID/관측점/전체이벤트가 일치한 자료를 evidence에 포함했다. Orin에서 같은 source/config/model과 실제 GPU 실행을 별도로 확인한 뒤 측정값을 사용한다.

공식 참고: https://docs.ultralytics.com/guides/nvidia-jetson/ ; https://docs.ultralytics.com/integrations/tensorrt/ ; https://developer.nvidia.com/embedded/jetpack-sdk . 사이트 최신 절차와 설치 장치 버전의 일치부터 확인한다.
'''
    instructions+='''

## 이번 스냅샷의 입력 시간과 정답 검토

기본 설정은 외형 특징 후보를 활성화하지 않는다. OSNet 추가 모델과 Danfo 개발 학습 모델은 이 묶음에 포함하지 않았다. 최근 기본 영상 513프레임의 실제 검출·ID·관측점·이벤트 일치 증거를 evidence에 포함했다.

녹화 파일은 원본 프레임/FPS 시간을 사용한다. --source-kind live는 읽기가 끝난 호스트 단조 시간이다. 카메라 노출 시각이나 버퍼 지연 측정이 아니다. 카메라 번호/RTSP/파이프라인은 live로 분류하며, 잘못 분류된 입력은 --source-kind로 명시한다. 카메라 연결 자체는 아직 검증하지 않았다.

부분 --max-frames 또는 live 입력은 observed-trace-audit.json과 observed_trace_verified를 확인한다. 이것은 수집된 프레임의 연속성·시간·현재 코드 SHA·추적 재생·이벤트 일치를 검증한다. full_run_verified는 false이며 원본 전체 길이·원본 SHA 검증이나 현장 정확도 검증을 뜻하지 않는다. process_returncode=0도 함께 확인한다. 녹화 파일 전체 실행은 기존 completion-audit.json/full_run_verified 검증을 유지한다.

검출 모델을 돌리기 전에 녹화 영상의 승하차 정답 구간을 검토하려면 python3 serve_passage_review.py --source ORIGINAL-VIDEO.mp4 --output reviews/NEW-REVIEW --port 8872 실행 후 장치의 http://127.0.0.1:8872/를 연다. 서버는 루프백만 사용하고 원본을 변경하지 않는다. 실제 프레임에서 사람별 시작·끝·방향을 기록하고 저장하면 새 windows-NNN.jsonl과 review-NNN.json이 생성된다. 기존 정답은 덮어쓰지 않는다. 일부 구간만 검토한 결과는 전체 정답이나 정밀도를 증명하지 않는다. 실제 검토자가 human인 경우에만 해당 종류를 선택한다. Windows에서 실제 UI 이동·저장을 검증했으며 Orin OpenCV 디코딩/브라우저 동작은 별도로 확인한다.
'''
    (a.output/'ORIN_FIRST_RUN.md').write_text(instructions,encoding='utf-8')
    files=[]
    for f in sorted(a.output.rglob('*')):
        if f.is_file():files.append(dict(path=f.relative_to(a.output).as_posix(),bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),original_path=origins.get(f.relative_to(a.output).as_posix())))
    manifest=dict(files=files,models=weights,export_checkpoints=checkpoints,videos_included=False,windows_venv_included=False,hardware_validated=False,tensorrt_validated=False)
    (a.output/'handoff-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    from verify_handoff import verify
    assert verify(a.output)['passed']
    with zipfile.ZipFile(a.output.with_suffix('.zip'),'x',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for f in sorted(a.output.rglob('*')):
            if f.is_file():z.write(f,f.relative_to(a.output).as_posix())
    print(json.dumps(dict(files=len(files),models=len(weights),output=str(a.output),zip_bytes=a.output.with_suffix('.zip').stat().st_size,integrity_verified=True,hardware_validated=False)))

if __name__=='__main__':main()
