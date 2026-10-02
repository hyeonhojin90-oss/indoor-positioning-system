"""Re-evaluate saved tracks/door locks without rerunning detection models."""
import argparse
import json
from pathlib import Path
from counter import PassageCounter
from person_anchor import row_points
from multi_anchor_counter import DualAnchorCounter


def replay_rows(rows, cfg):
    dual=cfg.get('person_anchor_kind')=='pose_dual'
    counter = DualAnchorCounter(cfg['counting'],cfg.get('person_anchor_y',1),**cfg.get('dual_anchor',{})) if dual else PassageCounter(**cfg['counting'])
    events = []
    prior_door = None
    prior_generation = None
    frames = 0
    approximate = False
    for row in rows:
        door = row['door']
        current_generation = row.get('door_generation')
        if current_generation is None:
            # Older logs omitted the lock generation. Door-coordinate changes
            # are only an approximation of runtime resets for those logs.
            approximate = True
            changed = door != prior_door
        else:
            changed = current_generation != prior_generation
        if changed or door is None:
            counter.reset_tracks()
        prior_door = door
        prior_generation = current_generation
        if door is not None:
            if dual:
                for event in counter.advance(row['time_s'],row['ids']):events.append(dict(event,frame=row['frame']))
            for tid,b,point in zip(row['ids'],row['boxes'],row_points(row,cfg)):
                if point is None and not dual:continue
                event = counter.update(tid,b,point,door,row['time_s'],frame=row['frame']) if dual else counter.update(tid,point,door,row['time_s'])
                if event:
                    events.append(dict(event, frame=row['frame']))
        frames += 1
    return {'frames':frames,'counts':counter.totals,'events':events,
            'legacy_reset_approximation':approximate,
            **({'anchor_evidence':counter.evidence} if dual else {})}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True, help='Existing run containing tracks.jsonl')
    parser.add_argument('--config', required=True, help='Counting profile to evaluate')
    parser.add_argument('--output', required=True, help='New JSON result path')
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    with (Path(args.run)/'tracks.jsonl').open(encoding='utf-8') as stream:
        replay = replay_rows((json.loads(line) for line in stream), cfg)
    result = {'source_run':args.run,**replay,
              'config':cfg,'replay_not_independent_validation':True}
    path = Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps(replay,indent=2))


if __name__ == '__main__':
    main()
