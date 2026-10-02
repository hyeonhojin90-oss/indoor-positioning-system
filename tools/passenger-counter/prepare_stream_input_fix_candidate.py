"""Freeze and exercise a stream hashing fix while an existing run is still active."""
import argparse
import json
import shutil
from pathlib import Path
from prepare_orin_handoff import runtime_closure


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--variant',choices=['fix','original'],default='fix');args=parser.parse_args()
    root=args.output;root.mkdir(parents=True,exist_ok=False)
    for file in runtime_closure(['run.py','run_experiment.py','runtime_input_evidence.py']):shutil.copy2(file,root/file.name)
    path=root/'run.py';code=path.read_text(encoding='utf-8')
    replacements=[
        ("    cfg = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))",
         "    cfg = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))\n    from runtime_input_evidence import RuntimeInputEvidence\n    source = int(args.source) if args.source.isdecimal() else args.source\n    input_evidence = RuntimeInputEvidence(source, args.config, cfg)"),
        ("'source_timing.py','appearance_runtime.py')}","'source_timing.py','appearance_runtime.py','runtime_input_evidence.py')}"),
        ("    source_hash = hashlib.sha256(Path(source).read_bytes()).hexdigest() if isinstance(source,str) else None",
         "    input_report = input_evidence.verify()\n    source_hash = input_report['source_sha256']"),
        ("    summary['source_timing']=source_clock.describe()",
         "    summary['source_timing']=source_clock.describe()\n    summary['runtime_input_evidence']=input_report")]
    for before,after in replacements if args.variant=='fix' else []:
        if code.count(before)!=1:raise ValueError('Unexpected runtime patch point')
        code=code.replace(before,after)
    path.write_text(code,encoding='utf-8')
    config=json.loads(Path('configs/bus-portal-default-profiled-resume3.json').read_text(encoding='utf-8'))
    for key in ('person_model','door_model','door_primary_model','bus_model','pose_aux_model'):
        if key in config and Path(config[key]).is_file():config[key]=str(Path(config[key]).resolve())
    (root/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    print(str(root))


if __name__=='__main__':main()
