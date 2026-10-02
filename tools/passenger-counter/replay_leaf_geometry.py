"""Development-only geometry hypothesis; never changes detector output or GT."""
import argparse
import json
from pathlib import Path
from replay_counter import replay_rows


def expand_rows(rows, minimum_aspect=4, leaf_widths=1, bottom_fraction=0):
    last_generation=None;count_box=None;audit=[];output=[]
    for row in rows:
        box=row['door'];generation=row['door_generation']
        if box is None:
            count_box=None;last_generation=generation
        elif count_box is None or last_generation!=generation:
            last_generation=generation;count_box=list(box)
            w,h=box[2]-box[0],box[3]-box[1]
            left=right=0
            if w>0 and h/w>=minimum_aspect:
                for p in row['boxes']:
                    x,y=(p[0]+p[2])/2,p[3]
                    if .7<=(y-box[1])/h<=1.6:
                        if box[0]-2*w<=x<box[0]:left+=1
                        if box[2]<x<=box[2]+2*w:right+=1
                if left>right:count_box[0]-=w*leaf_widths
                elif right>left:count_box[2]+=w*leaf_widths
                count_box[3]+=h*bottom_fraction
            audit.append({'frame':row['frame'],'generation':generation,'detected_box':box,
                          'counting_box':count_box,'left_votes':left,'right_votes':right})
        output.append(dict(row,detected_door=box,door=count_box))
    return output,audit


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--leaf-widths',type=float,default=1);a=p.parse_args()
    if not 0<a.leaf_widths<=2:raise ValueError('leaf-widths must be in (0,2]')
    summary=json.loads((a.run/'summary.json').read_text())
    rows=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()]
    if len(rows)!=summary['frames']:raise ValueError('Incomplete run')
    cfg=json.loads(a.config.read_text(encoding='utf-8-sig'))
    transformed,geometry=expand_rows(rows,leaf_widths=a.leaf_widths)
    result={'source_run':str(a.run),**replay_rows(transformed,cfg),'geometry':geometry,
            'leaf_widths':a.leaf_widths,'virtual_geometry':True,'replay_not_independent_validation':True}
    with a.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))
