"""Require engine lineage, positive device parity and exact full-source event regression."""
import argparse,hashlib,json
from pathlib import Path
from audit_completed_run import audit
from prepare_engine_config import runtime_roles,expected_size
from verify_target_run import model_path,config_signature,EVENT_KEYS
from export_target_engine import validate_target
from export_verified_onnx import compare_detections,compare_pose_detections

def role_backend(role):
    return {'person_model':'people','door_model':'door','bus_model':'bus','pose_aux_model':'pose_aux','door_acquisition_fallback.model':'door_acquisition_fallback'}[role]

def engine_loaded(backend):
    return backend.get('tensorrt_engine') is True and backend.get('execution_context_loaded') is True and backend.get('device')=='cuda:0' and backend.get('dynamic') is True and backend.get('fp16') is True

def assess(summary,golden,environment,original,manifest,provenance,parities):
    errors=[]
    try:validate_target(environment)
    except (ValueError,KeyError) as e:errors.append(str(e))
    if summary.get('device') not in ('0','cuda:0'):errors.append('Run did not request GPU0')
    if summary.get('ultralytics')!=environment.get('packages',{}).get('ultralytics'):errors.append('Runtime version differs from device inventory')
    for key in ['source_sha256','frames','counts']:
        if summary.get(key)!=golden.get(key):errors.append(key+' differs')
    if config_signature(summary['config'])!=config_signature(golden['config']) or config_signature(original)!=config_signature(golden['config']):errors.append('Runtime/original configuration differs from golden')
    events=lambda r:[tuple(e.get(k) for k in EVENT_KEYS) for e in r]
    if events(summary.get('events',[]))!=events(golden.get('events',[])):errors.append('Events differ despite possibly equal totals')
    roles=runtime_roles(original);proof_roles=provenance.get('roles',{})
    if set(roles)!=set(proof_roles):errors.append('Engine preparation omitted or added runtime roles')
    used_roles=[r for r in roles if r!='door_acquisition_fallback.model' or summary.get('door_acquisition_fallback_calls',0)>0]
    validated=[]
    for role in roles:
        try:
            onnx=model_path(original,role).as_posix();checkpoint=manifest['export_checkpoints'][onnx];proof=proof_roles[role]
            if manifest['models'][onnx]['sha256']!=golden['model_sha256'][role]:raise ValueError('Original ONNX does not match golden')
            if proof['original_onnx']!=onnx or proof['checkpoint_sha256']!=checkpoint['sha256']:raise ValueError('Engine source PT lineage differs')
            if proof['engine_sha256']!=summary['model_sha256'][role]:raise ValueError('Runtime engine hash differs from prepared config')
            if role not in used_roles:continue
            backend=summary.get('backend_execution',{}).get(role_backend(role),{})
            if not engine_loaded(backend):raise ValueError('Actual dynamic FP16 GPU engine context not recorded')
            parity=parities[role]
            validate_target(parity['target_environment'])
            if parity['hashes']!=dict(reference=checkpoint['sha256'],candidate=proof['engine_sha256'],source=golden['source_sha256']):raise ValueError('Parity model/source hashes differ')
            if parity.get('imgsz')!=expected_size(original,role) or parity.get('rect') is not True or parity.get('device') not in ('0','cuda:0'):raise ValueError('Parity input geometry/device differs')
            task='pose' if role=='pose_aux_model' else 'detect'
            if parity.get('task')!=task or not engine_loaded(parity.get('backend',{}).get('candidate',{})):raise ValueError('Parity task or actual engine backend differs')
            expected_conf=original.get('pose_aux_conf',.1) if role=='pose_aux_model' else (original.get('person_conf',.1) if role=='person_model' else (original.get('bus_detector',{}).get('conf',.05) if role=='bus_model' else original.get('door_conf',.25)))
            if parity.get('conf')!=expected_conf or parity.get('classes')!=([5] if role=='bus_model' else [0]):raise ValueError('Parity class/conf differs from runtime')
            rows=parity.get('rows',[])
            if not rows or len({r['frame'] for r in rows})!=len(rows) or any(not 0<=r['frame']<golden['frames'] for r in rows):raise ValueError('Missing/duplicate/out-of-source parity frames')
            compare=compare_pose_detections if task=='pose' else compare_detections
            if parity.get('passed') is not True or not all(compare(r['reference'],r['candidate'])['passed'] for r in rows):raise ValueError('Recomputed frame parity failed')
            if not any(r['reference'] and r['candidate'] for r in rows):raise ValueError('Empty-only model parity is insufficient')
            validated.append(role)
        except (KeyError,ValueError,TypeError) as e:errors.append(role+': '+str(e))
    return dict(passed=not errors,errors=errors,validated_used_roles=validated,unused_roles=[r for r in roles if r not in used_roles],
        events_exact=events(summary.get('events',[]))==events(golden.get('events',[])),
        full_detection_trace_compared=False,operation_execution_profile_verified=False,
        independent_accuracy_validated=False,field_validated=False,sustained_performance_validated=False,
        note='Exact development events and sampled positive PT/engine parity only. Inactive fallback is not inferred validated; full detections, independent field accuracy and sustained performance remain separate.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--golden',type=Path,required=True);p.add_argument('--name',required=True)
    p.add_argument('--environment',type=Path,required=True);p.add_argument('--original-config',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--engine-provenance',type=Path,required=True);p.add_argument('--parities',nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    matches=[r for r in json.loads(a.golden.read_text()) if r['name']==a.name]
    if len(matches)!=1:raise ValueError('Unique golden name required')
    summary=json.loads((a.run/'summary.json').read_text());summary['events']=[json.loads(x) for x in (a.run/'events.jsonl').read_text().splitlines()]
    provenance=json.loads(a.engine_provenance.read_text());paths={}
    for spec in a.parities:
        role,path=spec.split('=',1)
        if role in paths:raise ValueError('Duplicate parity role')
        paths[role]=Path(path)
    result=assess(summary,matches[0],json.loads(a.environment.read_text()),json.loads(a.original_config.read_text()),json.loads(a.manifest.read_text()),provenance,{k:json.loads(v.read_text()) for k,v in paths.items()})
    completion=audit(a.run);result['completion_audit']=completion
    if completion['implementation_drift_since_start']:result['errors'].append('Implementation changed after start')
    for role,digest in summary['model_sha256'].items():
        path=model_path(summary['config'],role)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:result['errors'].append(role+': current model hash differs')
    for path,key in [(a.original_config,'source_config_sha256'),(a.manifest,'manifest_sha256')]:
        if hashlib.sha256(path.read_bytes()).hexdigest()!=provenance.get(key):result['errors'].append(key+': preparation input differs')
    result['parity_report_sha256']={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in paths.items()};result['passed']=not result['errors']
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
