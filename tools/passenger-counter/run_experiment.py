"""Record owned child-process exit and full-source verification across chat interruptions."""
import argparse,datetime,hashlib,json,os,re,subprocess,sys
from pathlib import Path

def timestamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(path,state):
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('x',encoding='utf-8') as f:json.dump(state,f,indent=2)
    temporary.replace(path)

def completion_state(returncode,summary_saved,audit_report):
    return dict(process_returncode=returncode,summary_saved=summary_saved,
                full_run_verified=returncode==0 and summary_saved and audit_report is not None
                    and audit_report.get('complete_source') is True and audit_report.get('replay_parity') is True
                    and not audit_report.get('implementation_drift_since_start'),
                project_goal_completed=False,hardware_validated=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--config',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--device',default='cpu')
    p.add_argument('--source-kind',choices=['auto','file','live'],default='auto')
    p.add_argument('--max-frames',type=int,default=0);a=p.parse_args()
    if a.max_frames<0:raise ValueError('Negative frame limit')
    base=Path(__file__).resolve().parent
    if Path.cwd().resolve()!=base:raise ValueError('Run from module directory so saved source/model paths stay reproducible')
    proof=a.output.with_name(a.output.name+'.process.json');log=a.output.with_name(a.output.name+'.process.log')
    if a.output.exists() or proof.exists() or log.exists() or proof.with_name(proof.name+'.tmp').exists():
        raise ValueError('Exclusive new experiment output and process files required')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,str(base/'run.py'),'--source',a.source,'--config',str(a.config),'--output',str(a.output),'--device',a.device,'--source-kind',a.source_kind]
    if a.max_frames:command+=['--max-frames',str(a.max_frames)]
    state=dict(command=command,started_at=timestamp(),phase='starting',process_returncode=None,
               summary_saved=False,full_run_verified=False,project_goal_completed=False,hardware_validated=False,
               supervisor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    child=None
    with log.open('x',encoding='utf-8') as stream:
        save(proof,state)
        try:
            environment=dict(os.environ,PYTHONUNBUFFERED='1',PYTHONIOENCODING='utf-8')
            child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=environment)
            state.update(phase='running',child_pid=child.pid);save(proof,state)
            for line in child.stdout:
                stream.write(line);stream.flush()
                if line.startswith('frame='):
                    print(line,end='',flush=True)
                    match=re.match(r'frame=(\d+)',line)
                    if match:state['last_reported_frame']=int(match.group(1));state['progress_at']=timestamp();save(proof,state)
            code=child.wait();audit_report=None;summary_saved=(a.output/'summary.json').is_file()
            if code==0 and summary_saved:
                try:
                    summary=json.loads((a.output/'summary.json').read_text(encoding='utf-8'))
                    if summary.get('source_sha256') is None or a.max_frames or summary.get('source_timing',{}).get('source_kind')=='live':
                        from audit_observed_trace import audit
                        observed=audit(a.output)
                        with (a.output/'observed-trace-audit.json').open('x') as f:json.dump(observed,f,indent=2)
                        state.update(audit_scope='observed_trace_only',observed_trace_verified=observed['observed_trace_verified'])
                    else:
                        from audit_completed_run import audit
                        audit_report=audit(a.output)
                        with (a.output/'completion-audit.json').open('x') as f:json.dump(audit_report,f,indent=2)
                        state['audit_scope']='complete_local_source'
                except Exception as error:state['full_audit_error']=f'{type(error).__name__}: {error}'
            state['supervisor_code_unchanged']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==state['supervisor_sha256']
            state.update(completion_state(code,summary_saved,audit_report),phase='process_finished' if code==0 else 'process_failed',finished_at=timestamp())
            if not state['supervisor_code_unchanged']:
                state['full_run_verified']=False;state['observed_trace_verified']=False
            save(proof,state)
            print(json.dumps(state,indent=2),flush=True)
            if code:raise SystemExit(code)
        except BaseException as error:
            if child is not None and child.poll() is None:
                child.terminate()
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:child.kill();child.wait()
            state.update(phase='process_failed',error=f'{type(error).__name__}: {error}',finished_at=timestamp(),full_run_verified=False)
            if child is not None:state['process_returncode']=child.returncode
            save(proof,state)
            raise

if __name__=='__main__':main()
