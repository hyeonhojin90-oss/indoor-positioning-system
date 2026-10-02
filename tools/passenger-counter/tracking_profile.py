"""Validated ByteTrack overrides saved alongside each experiment."""
from pathlib import Path


def resolve_tracker(name, options, output):
    if name not in ('bytetrack.yaml','botsort.yaml'):
        raise ValueError('Unsupported person_tracker')
    if options is None:
        return name
    if not isinstance(options,dict):
        raise ValueError('Overrides require a mapping')
    defaults={'track_high_thresh':.25,'track_low_thresh':.1,'new_track_thresh':.25,
              'track_buffer':30,'match_thresh':.8,'fuse_score':True}
    if name=='botsort.yaml':
        if options.get('with_reid') is not True:
            raise ValueError('BoT-SORT overrides require explicit ReID experiment')
        defaults.update(gmc_method='none',proximity_thresh=.5,appearance_thresh=.8,with_reid=True)
    if not set(options)<=set(defaults):
        raise ValueError('Unknown ByteTrack option')
    values={**defaults,**options}
    for key in ('track_high_thresh','track_low_thresh','new_track_thresh','match_thresh'):
        v=values[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not 0 <= v <= 1:
            raise ValueError('Invalid tracker threshold')
    if values['track_low_thresh']>values['track_high_thresh']:
        raise ValueError('Low threshold exceeds high threshold')
    if type(values['track_buffer']) is not int or not 1<=values['track_buffer']<=300:
        raise ValueError('Invalid tracker buffer')
    if type(values['fuse_score']) is not bool:
        raise ValueError('Invalid fuse_score')
    if name=='botsort.yaml':
        if values['gmc_method'] not in ('none','sparseOptFlow'):
            raise ValueError('Invalid motion compensation')
        for key in ('proximity_thresh','appearance_thresh'):
            if isinstance(values[key],bool) or not isinstance(values[key],(int,float)) or not 0<=values[key]<=1:
                raise ValueError('Invalid appearance threshold')
        values['model']='auto'
    path=Path(output)/'person-tracker.yaml'
    text=f"tracker_type: {'bytetrack' if name=='bytetrack.yaml' else 'botsort'}\n"+''.join(f'{k}: {str(v).lower() if isinstance(v,bool) else v}\n' for k,v in values.items())
    path.write_text(text,encoding='utf-8')
    return str(path.resolve())
