"""One-to-one event matching; never infer accuracy from equal total counts alone."""
import argparse
import json
import math
from pathlib import Path


def evaluate(predicted, truth, tolerance=.5):
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('Invalid tolerance')
    for event in list(predicted)+list(truth):
        if event['direction'] not in ('in','out') or not math.isfinite(event['time_s']) or event['time_s']<0:
            raise ValueError('Invalid timed event')
    result={}
    for direction in ('in','out'):
        pred=sorted(e['time_s'] for e in predicted if e['direction']==direction)
        gt=sorted(e['time_s'] for e in truth if e['direction']==direction)
        # Earliest compatible pairs maximize cardinality for ordered time intervals.
        i=j=tp=0
        while i<len(pred) and j<len(gt):
            if pred[i]<gt[j]-tolerance: i+=1
            elif pred[i]>gt[j]+tolerance: j+=1
            else: tp+=1; i+=1; j+=1
        result[direction]={'tp':tp,'fp':len(pred)-tp,'fn':len(gt)-tp,
                           'precision':tp/len(pred) if pred else None,
                           'recall':tp/len(gt) if gt else None}
    return result


def evaluate_windows(predicted, truth, tolerance=0, identity_review=None):
    """Match reviewed time intervals one-to-one, including overlapping intervals.

    Unmatched predictions remain unclassified: a reviewed subset cannot establish FP.
    """
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('Invalid tolerance')
    for event in predicted:
        if event['direction'] not in ('in','out') or not math.isfinite(event['time_s']):
            raise ValueError('Invalid predicted event')
    for event in truth:
        if (event['direction'] not in ('in','out')
                or not math.isfinite(event['start_s']) or not math.isfinite(event['end_s'])
                or not 0 <= event['start_s'] <= event['end_s']):
            raise ValueError('Invalid reviewed window')
    reviews = {}
    if identity_review is not None:
        for review in identity_review:
            key = (review['frame'],review['track_id'],review['direction'])
            if key in reviews or review['status'] not in ('accepted','duplicate','uncertain'):
                raise ValueError('Invalid or duplicate identity review')
            if review['status']=='accepted' and review.get('person') not in {t.get('person') for t in truth}:
                raise ValueError('Unknown reviewed person')
            reviews[key] = review
        predicted_keys = {(p['frame'],p['track_id'],p['direction']) for p in predicted}
        if not set(reviews).issubset(predicted_keys):
            raise ValueError('Identity review does not match predicted events')
    def compatible(p,t):
        if identity_review is None:
            return True
        review = reviews.get((p['frame'],p['track_id'],p['direction']),{})
        return review.get('status')=='accepted' and review['person']==t.get('person')
    edges = [[i for i,p in enumerate(predicted)
              if p['direction']==t['direction']
              and compatible(p,t)
              and t['start_s']-tolerance <= p['time_s'] <= t['end_s']+tolerance]
             for t in truth]
    matched = {}
    def assign(tid, seen):
        for pid in edges[tid]:
            if pid in seen:
                continue
            seen.add(pid)
            if pid not in matched or assign(matched[pid],seen):
                matched[pid] = tid
                return True
        return False
    for tid in range(len(truth)):
        assign(tid,set())
    found = set(matched.values())
    return {'reviewed_events':len(truth),'matched_reviewed_events':len(found),
            'missed_reviewed_events':[t for i,t in enumerate(truth) if i not in found],
            'matches':[{'reviewed':truth[tid],'predicted':predicted[pid]}
                       for pid,tid in sorted(matched.items())],
            'unclassified_predictions':[p for i,p in enumerate(predicted) if i not in matched],
            'temporal_matching_only':identity_review is None,
            'identity_review':identity_review,
            'subset_review':True,'precision':None,'independent_accuracy_validated':False}


def evaluate_person_directions(predicted, truth, identity_review):
    """Separate visually matched people from strict event-time accuracy.

    Partial truth cannot establish total precision. Repeated visits by the same
    person need passage labels and are deliberately unsupported by this metric.
    """
    temporal=evaluate_windows(predicted,truth,0,identity_review)
    expected=[(event['person'],event['direction']) for event in truth]
    if len(set(expected))!=len(expected):
        raise ValueError('Repeated person visits require passage-level review')
    reviews={(r['frame'],r['track_id'],r['direction']):r for r in identity_review}
    observed={};unclassified=[]
    for event in predicted:
        review=reviews.get((event['frame'],event['track_id'],event['direction']))
        if review is None or review['status']!='accepted':
            unclassified.append(event);continue
        identity=(review['person'],event['direction'])
        if identity not in set(expected):
            unclassified.append(event);continue
        observed.setdefault(identity,[]).append(event)
    return dict(reviewed_person_directions=len(expected),
        matched_person_directions=len(observed),
        missed_person_directions=[dict(person=p,direction=d) for p,d in expected if (p,d) not in observed],
        repeated_accepted_person_predictions=[dict(person=p,direction=d,events=events)
            for (p,d),events in observed.items() if len(events)>1],
        unclassified_predictions=unclassified,strict_time_matching=temporal,
        temporal_accuracy_validated=False,subset_review=True,precision=None,
        whole_ground_truth_complete=False,independent_accuracy_validated=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--predicted',required=True);p.add_argument('--truth',required=True)
    p.add_argument('--reviewed-windows',action='store_true',help='Partial review; truth has start_s/end_s')
    p.add_argument('--identity-review',help='JSONL visual event review; use with --reviewed-windows')
    p.add_argument('--tolerance',type=float,default=.5);args=p.parse_args()
    read=lambda x:[json.loads(line) for line in Path(x).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    if args.identity_review and not args.reviewed_windows:
        p.error('--identity-review requires --reviewed-windows')
    if args.reviewed_windows:
        result = evaluate_windows(read(args.predicted),read(args.truth),args.tolerance,
                                  read(args.identity_review) if args.identity_review else None)
    else:
        result = evaluate(read(args.predicted),read(args.truth),args.tolerance)
    print(json.dumps(result,indent=2))
