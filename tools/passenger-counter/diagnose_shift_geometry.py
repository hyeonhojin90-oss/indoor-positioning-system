"""Separate recorded door and person changes; diagnostic replays, never new accuracy."""
import argparse,json,copy
from pathlib import Path
from replay_counter import replay_rows

def read_rows(run):
    return [json.loads(line) for line in (run/'tracks.jsonl').read_text().splitlines()]

def substitute_doors(people,doors,dx):
    if len(people)!=len(doors):raise ValueError('Frame counts differ')
    result=[]
    for person,door in zip(people,doors):
        if person['frame']!=door['frame'] or person['time_s']!=door['time_s']:
            raise ValueError('Observations are not aligned')
        row=copy.deepcopy(person);box=door['door']
        row['door']=None if box is None else [box[0]+dx,box[1],box[2]+dx,box[3]]
        row['door_generation']=door['door_generation'];result.append(row)
    return result

def translate_observations(rows,dx):
    result=copy.deepcopy(rows)
    for row in result:
        if row['door'] is not None:
            row['door'][0]+=dx;row['door'][2]+=dx
        for box in row['boxes']:box[0]+=dx;box[2]+=dx
        for point in row.get('points',[]):
            if point is not None:point[0]+=dx
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--shifted',type=Path,required=True);p.add_argument('--dx',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    base=read_rows(a.base);shifted=read_rows(a.shifted)
    cfg=json.loads((a.base/'summary.json').read_text())['config']
    shifted_cfg=json.loads((a.shifted/'summary.json').read_text())['config']
    if cfg!=shifted_cfg:raise ValueError('Configurations differ')
    result=dict(base_run=str(a.base),shifted_run=str(a.shifted),dx=a.dx,
        diagnostic_only=True,new_inference=False,independent_validation=False,
        limitation='Auxiliary activation and track aliases already depend on their original door. Swaps isolate saved observations only.',
        base=replay_rows(base,cfg),shifted=replay_rows(shifted,cfg),
        translated_base_observations=replay_rows(translate_observations(base,a.dx),cfg),
        base_people_shifted_door=replay_rows(substitute_doors(base,shifted,-a.dx),cfg),
        shifted_people_base_door=replay_rows(substitute_doors(shifted,base,a.dx),cfg))
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v['counts'] for k,v in result.items() if isinstance(v,dict)},indent=2))
