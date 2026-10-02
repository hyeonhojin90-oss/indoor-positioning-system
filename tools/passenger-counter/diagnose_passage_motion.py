"""Log state and measured displacement at saved passage events, without identity guesses."""
import argparse
import json
from pathlib import Path
from counter import PassageCounter

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--config',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    cfg=json.loads(a.config.read_text(encoding='utf-8-sig'));c=PassageCounter(**cfg['counting'])
    generation=None;proof=[]
    for line in (a.run/'tracks.jsonl').read_text().splitlines():
        row=json.loads(line);door=row['door']
        if generation!=row['door_generation'] or door is None:c.reset_tracks()
        generation=row['door_generation']
        if door is None:continue
        for tid,b in zip(row['ids'],row['boxes']):
            point=((b[0]+b[2])/2,b[1]+cfg.get('person_anchor_y',1)*(b[3]-b[1]))
            old=dict(vars(c.tracks[tid])) if tid in c.tracks else None
            event=c.update(tid,point,door,row['time_s'])
            if event:
                now=dict(vars(c.tracks[tid]));motion=now['side_origin_u']-old['side_origin_u']
                proof.append(dict(event,frame=row['frame'],prior=old,current=now,normalized_axis_motion=motion))
    value=dict(source_run=str(a.run),counts=c.totals,events=proof,development_diagnostic_only=True)
    with a.output.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)
    for e in proof:print(e['frame'],e['track_id'],e['direction'],round(e['normalized_axis_motion'],3),round(e['prior']['side_max_v'],3))
