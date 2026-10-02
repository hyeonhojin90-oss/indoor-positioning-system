"""Live/remote log consistency, without claiming complete original camera footage."""
import hashlib
import json
import math
from pathlib import Path
from replay_counter import replay_rows


def audit(run,implementation_root=None):
    run=Path(run);base=Path(implementation_root) if implementation_root is not None else Path(__file__).resolve().parent
    summary=json.loads((run/'summary.json').read_text(encoding='utf-8'))
    rows=[json.loads(line) for line in (run/'tracks.jsonl').read_text(encoding='utf-8').splitlines()]
    events=[json.loads(line) for line in (run/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    if not rows or len(rows)!=summary['frames'] or any(row['frame']!=i for i,row in enumerate(rows)):
        raise ValueError('Observed trace incomplete for reported frames')
    times=[row['time_s'] for row in rows]
    if any(not isinstance(t,(float,int)) or isinstance(t,bool) or not math.isfinite(t) or t<0 for t in times) or any(b<a for a,b in zip(times,times[1:])):
        raise ValueError('Observation clock is invalid or regressed')
    for row in rows:
        if 'door_generation' not in row or len(row['ids'])!=len(row['boxes']) or len(row.get('points',row['ids']))!=len(row['ids']):
            raise ValueError('Incomplete identity/box/anchor observation')
        if len(set(row['ids']))!=len(row['ids']):raise ValueError('Duplicate canonical identity')
    for event in events:
        frame=event.get('frame');observed=event.get('observation_frame',frame)
        if type(frame) is not int or type(observed) is not int or not 0<=observed<=frame<len(rows):
            raise ValueError('Event frame is not an observed source frame')
        row=rows[frame]
        if event.get('door_generation')!=row['door_generation'] or row['door'] is None:
            raise ValueError('Event belongs to a different or missing door')
        if not math.isfinite(event['time_s']) or abs(event['time_s']-rows[observed]['time_s'])>.0015:
            raise ValueError('Event observation time differs from actual trace')
        if 'commit_time_s' in event and abs(event['commit_time_s']-row['time_s'])>.0015:
            raise ValueError('Event commitment time differs from actual trace')
    replay=replay_rows(rows,summary['config'])
    key=lambda event:(event['frame'],event['track_id'],event['direction'],event['time_s'],
        event.get('observation_frame'),event.get('commit_time_s'),event.get('anchor_evidence'))
    if replay['counts']!=summary['counts'] or [key(e) for e in replay['events']]!=[key(e) for e in events]:
        raise ValueError('Observed runtime and replay disagree')
    hashes=summary.get('implementation_sha256',{})
    required={'run.py','counter.py','person_anchor.py','multi_anchor_counter.py','source_timing.py'}
    if not required.issubset(hashes):raise ValueError('Required runtime provenance unavailable')
    if any(Path(name).name!=name for name in hashes):raise ValueError('Invalid local implementation name')
    drift=[name for name,digest in hashes.items() if hashlib.sha256((base/name).read_bytes()).hexdigest()!=digest]
    return dict(run=str(run),scope='observed_trace_only',frames=len(rows),counts=summary['counts'],
        observed_trace_verified=not drift,trace_complete_for_reported_frames=True,replay_parity=True,
        monotonic_observation_times=True,implementation_drift_since_start=drift,
        source_timing=summary.get('source_timing'),original_source_complete_verified=False,
        original_source_hash_verified=False,camera_exposure_timestamp_verified=False,
        independent_accuracy_validated=False,jetson_validated=False)
