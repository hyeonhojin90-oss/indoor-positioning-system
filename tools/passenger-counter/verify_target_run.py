"""Compare a completed ONNX target run with its exact saved development baseline."""
import argparse,copy,hashlib,json
from pathlib import Path
from audit_completed_run import audit

MODEL_KEYS=('person_model','door_model','door_primary_model','bus_model','pose_aux_model')
EVENT_KEYS=('frame','track_id','direction','time_s','observation_frame','commit_time_s','anchor_evidence','door_generation')

def config_signature(config):
    value=copy.deepcopy(config)
    value.pop('experiment_note',None)
    value.pop('profile_pipeline',None)
    for key in MODEL_KEYS:value.pop(key,None)
    if isinstance(value.get('door_acquisition_fallback'),dict):
        value['door_acquisition_fallback'].pop('model',None)
    return value

def model_path(config,key):
    value=config
    for part in key.split('.'):value=value[part]
    return Path(value)

def assess(summary,golden,environment):
    errors=[]
    for key in ('source_sha256','frames','counts','model_sha256'):
        if summary.get(key)!=golden.get(key):errors.append(key+' differs')
    if not golden.get('config') or config_signature(summary['config'])!=config_signature(golden['config']):
        errors.append('counting/detector configuration differs or golden config missing')
    events=lambda rows:[tuple(row.get(k) for k in EVENT_KEYS) for row in rows]
    if events(summary.get('events',[]))!=events(golden.get('events',[])):errors.append('events differ')
    target=environment.get('platform')=='Linux' and environment.get('machine') in ('aarch64','arm64') and environment.get('jetson_detected') is True
    if not target:errors.append('not an identified Jetson ARM64 environment')
    if environment.get('cuda_available') is not True:errors.append('CUDA torch unavailable')
    if summary.get('device') not in ('0','cuda:0'):errors.append('run did not request GPU0')
    if summary.get('ultralytics')!=environment.get('packages',{}).get('ultralytics'):errors.append('runtime/environment version differs')
    roles=['people','door']
    for key,role in [('bus_model','bus'),('pose_aux_model','pose_aux')]:
        if key in summary['config']:roles.append(role)
    if summary.get('door_acquisition_fallback_calls',0)>0:roles.append('door_acquisition_fallback')
    providers={role:summary.get('backend_execution',{}).get(role,{}).get('providers',[]) for role in roles}
    if not all('CUDAExecutionProvider' in values for values in providers.values()):
        errors.append('CUDA provider missing from one or more ONNX backends')
    return dict(passed=not errors,errors=errors,providers=providers,
                events_exact=events(summary.get('events',[]))==events(golden.get('events',[])),
                gpu_provider_configured=all('CUDAExecutionProvider' in v for v in providers.values()),
                operation_execution_profile_verified=False,full_detection_trace_compared=False,
                independent_accuracy_validated=False,field_validated=False,
                note='Exact ONNX baseline/event regression and configured provider only. This is not independent passenger accuracy, CUDA operation profiling, or sustained thermal/latency validation. TensorRT requires its own re-export parity evidence.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    p.add_argument('--golden',type=Path,required=True);p.add_argument('--name',required=True)
    p.add_argument('--environment',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();matches=[r for r in json.loads(a.golden.read_text()) if r['name']==a.name]
    if len(matches)!=1:raise ValueError('Golden name must identify exactly one baseline')
    summary=json.loads((a.run/'summary.json').read_text());summary['events']=[json.loads(x) for x in (a.run/'events.jsonl').read_text().splitlines()]
    completion=audit(a.run)
    report=assess(summary,matches[0],json.loads(a.environment.read_text()))
    report['completion_audit']=completion
    if completion['implementation_drift_since_start']:report['errors'].append('implementation changed since run start')
    for key,digest in summary['model_sha256'].items():
        model=model_path(summary['config'],key)
        if not model.is_file() or hashlib.sha256(model.read_bytes()).hexdigest()!=digest:
            report['errors'].append(key+' current model hash differs')
    report['passed']=not report['errors']
    with a.output.open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
