"""Prepare exclusive device-engine config from exact bundle checkpoint lineage."""
import argparse,copy,hashlib,json
from pathlib import Path
from export_target_engine import validate_target
from verify_target_run import model_path

def runtime_roles(config):
    if config.get('person_family','yolo')!='yolo':raise ValueError('Current device export/parity protocol supports YOLO family only; alternative predictors need separate validation')
    roles=['person_model','door_model']
    for key in ['bus_model','pose_aux_model']:
        if key in config:roles.append(key)
    if config.get('door_acquisition_fallback'):roles.append('door_acquisition_fallback.model')
    return roles

def expected_size(config,role):
    if role=='door_model':return config.get('imgsz',640)
    if role=='door_acquisition_fallback.model':return config['door_acquisition_fallback'].get('imgsz',640)
    if role=='bus_model':return config.get('bus_detector',{}).get('imgsz',config.get('person_imgsz',config.get('imgsz',640)))
    return config.get('person_imgsz',config.get('imgsz',640))

def validate_export(config,role,checkpoint,report,engine):
    validate_target(report['target_environment'])
    if report.get('engine_build_completed') is not True or report.get('dynamic') is not True or report.get('half') is not True or report.get('batch')!=1:
        raise ValueError('Expected completed dynamic FP16 batch1 device export')
    if report.get('source_model_sha256')!=checkpoint['sha256']:raise ValueError('Checkpoint lineage differs')
    if report.get('imgsz')!=expected_size(config,role):raise ValueError('Export size differs from original runtime')
    if report.get('task')!=('pose' if role=='pose_aux_model' else 'detect'):raise ValueError('Export task differs')
    if not engine.is_file() or hashlib.sha256(engine.read_bytes()).hexdigest()!=report.get('engine_sha256'):
        raise ValueError('Engine missing or changed since device export')

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--exports',nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('New output directory required')
    config=json.loads(a.config.read_text());manifest=json.loads(a.manifest.read_text());provided={}
    for spec in a.exports:
        key,path=spec.split('=',1)
        if key in provided:raise ValueError('Repeated engine role')
        provided[key]=Path(path)
    if set(provided)!=set(runtime_roles(config)):raise ValueError('Exactly all active runtime model roles must have exports')
    target=copy.deepcopy(config);proof={}
    for role,path in provided.items():
        original=model_path(config,role).as_posix()
        checkpoint=manifest['export_checkpoints'][original]
        report=json.loads(path.read_text());engine=Path(report['engine'])
        if not engine.is_absolute():engine=Path.cwd()/engine
        validate_export(config,role,checkpoint,report,engine)
        value=target;parts=role.split('.')
        for part in parts[:-1]:value=value[part]
        value[parts[-1]]=str(engine.resolve())
        proof[role]=dict(original_onnx=original,checkpoint_sha256=checkpoint['sha256'],engine_sha256=report['engine_sha256'],
                        export_report=str(path),export_report_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'config.json').write_text(json.dumps(target,indent=2))
    (a.output/'provenance.json').write_text(json.dumps(dict(source_config_sha256=hashlib.sha256(a.config.read_bytes()).hexdigest(),
        manifest_sha256=hashlib.sha256(a.manifest.read_bytes()).hexdigest(),roles=proof,
        all_runtime_roles_replaced=True,engine_context_loaded=False,counter_validated=False,
        keypoint_parity_validated=False,independent_accuracy_validated=False,
        note='Configuration preparation only; load/parity/full-event and sustained device performance remain unverified.'),indent=2))
    print('Device-engine candidate config saved; inference/parity validation is still required.')

if __name__=='__main__':main()
