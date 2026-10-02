"""Read only this chat's recent local rate-limit telemetry; never infer token quota."""
import argparse
import json
from pathlib import Path
from datetime import datetime,timezone

def stop_policy(used, remaining_below=None):
    if remaining_below is None:
        return dict(stop_threshold_used_percent=95,stop_reached=used>=95)
    if not 0<remaining_below<=100:
        raise ValueError('Remaining threshold must be in (0,100]')
    return dict(stop_threshold_used_percent=100-remaining_below,
                stop_remaining_below_percent=remaining_below,
                stop_comparison='strictly_less_remaining',
                stop_reached=100-used<remaining_below)

def latest(path,remaining_below=None):
    with path.open('rb') as f:
        f.seek(0,2);size=f.tell();start=max(0,size-4*1024*1024);f.seek(start)
        data=f.read().splitlines()
    if start:data=data[1:]
    for line in reversed(data):
        if b'"token_count"' not in line:continue
        try:item=json.loads(line)
        except (ValueError,UnicodeError):continue
        payload=item.get('payload',{});limits=payload.get('rate_limits') or {}
        if payload.get('type')!='token_count' or not limits.get('primary'):continue
        observed=datetime.fromisoformat(item['timestamp'].replace('Z','+00:00'))
        age=(datetime.now(timezone.utc)-observed).total_seconds()
        primary=limits['primary'];secondary=limits.get('secondary') or {}
        return dict(timestamp=item['timestamp'],age_seconds=round(age,1),
                    primary_used_percent=primary['used_percent'],
                    primary_remaining_percent=100-primary['used_percent'],
                    primary_resets_at=primary['resets_at'],
                    secondary_used_percent=secondary.get('used_percent'),
                    **stop_policy(primary['used_percent'],remaining_below),
                    fresh=0<=age<=180,source='This chat local token_count rate_limits; not raw token balance.')
    raise ValueError('No recent primary rate-limit telemetry found; quota unknown')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True)
    p.add_argument('--output',type=Path);p.add_argument('--stop-remaining-below',type=float)
    a=p.parse_args();value=latest(a.session,a.stop_remaining_below)
    if a.output:a.output.write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(json.dumps(value,indent=2))
