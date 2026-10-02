"""Real detector run on a file-backed mocked stream; never connects to a camera."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--source-file',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();runtime=args.runtime.resolve();source=args.source_file.resolve();output=args.output.resolve()
    if not source.is_file() or output.exists():raise ValueError('Existing drill source and exclusive output required')
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    # Own child installs a narrow file-backed read adapter, then runs actual inference.
    program='''import sys,json
from pathlib import Path
import cv2
from unittest.mock import patch
runtime,source,output=sys.argv[1:]
sys.path.insert(0,runtime)
import run
actual=cv2.VideoCapture
sys.argv=['run.py','--source','file-backed-drill-stream://fixture','--config',str(Path(runtime)/'config.json'),'--output',output,'--max-frames','8','--device','cpu']
with patch('cv2.VideoCapture',side_effect=lambda address:actual(source)):
    run.main()
from audit_observed_trace import audit
report=audit(Path(output),Path(runtime))
report.update(file_backed_stream_drill=True,actual_camera_accessed=False,actual_network_stream_connected=False)
with (Path(output)/'observed-trace-audit.json').open('x') as stream:json.dump(report,stream,indent=2)
'''
    log=output.with_name(output.name+'.drill.log')
    with log.open('x',encoding='utf-8') as stream:
        completed=subprocess.run([sys.executable,'-c',program,str(runtime),str(source),str(output)],
                                 cwd=runtime,stdout=stream,stderr=subprocess.STDOUT)
    unchanged=hashlib.sha256(source.read_bytes()).hexdigest()==before
    proof=dict(process_returncode=completed.returncode,file_backed_stream_drill=True,
               original_source_sha256=before,original_source_unchanged=unchanged,
               actual_camera_accessed=False,actual_network_stream_connected=False,full_run_verified=False)
    output.with_name(output.name+'.drill-process.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps(proof))
    if completed.returncode or not unchanged:raise SystemExit(completed.returncode or 1)


if __name__=='__main__':main()
