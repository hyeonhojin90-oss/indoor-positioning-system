"""Replay saved tracks to separate geometry from detector availability.

Oracle box is a human diagnostic input, never an automatic detection result.
"""
import argparse
import json
from pathlib import Path
from counter import PassageCounter


def replay(rows, box_override=None, low=.4, high=.6):
    counter=PassageCounter(low=low,high=high)
    events=[]
    previous=None
    for row in rows:
        box=box_override or row['door']
        if box is None or (previous is not None and box!=previous):
            counter.reset_tracks()
        previous=box
        if box is None: continue
        for tid,b in zip(row['ids'],row['boxes']):
            event=counter.update(tid,((b[0]+b[2])/2,b[3]),box,row['time_s'])
            if event: events.append(dict(event,frame=row['frame']))
    return {'counts':counter.totals,'events':events}


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True)
    p.add_argument('--oracle-box',required=True,nargs=4,type=float)
    p.add_argument('--low',type=float,default=.82);p.add_argument('--high',type=float,default=.94)
    args=p.parse_args(); run=Path(args.run)
    rows=[json.loads(l) for l in (run/'tracks.jsonl').read_text().splitlines()]
    result={'purpose':'same-video diagnostic only; manual box and adjusted gates are not independent validation',
            'oracle_box':args.oracle_box,'adjusted_gates':[args.low,args.high],
            'automatic_default':replay(rows),
            'oracle_default':replay(rows,args.oracle_box),
            'oracle_adjusted':replay(rows,args.oracle_box,args.low,args.high),
            'automatic_adjusted':replay(rows,None,args.low,args.high)}
    (run/'diagnosis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
