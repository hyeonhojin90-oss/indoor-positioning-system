"""Experimental appearance veto for lost-track reactivation only."""
import numpy as np


def veto_lost(costs, appearance, lost_rows, threshold):
    result = costs.copy()
    mask = np.asarray(lost_rows, dtype=bool)[:, None] & np.isfinite(appearance) & (appearance > threshold)
    result[mask] = 1.0
    return result


def install(cfg):
    enabled = cfg.get('lost_reid_guard', False)
    if type(enabled) is not bool:
        raise ValueError('lost_reid_guard must be boolean')
    if not enabled:
        return
    options = cfg.get('person_tracker_options', {})
    if (cfg.get('person_tracker') != 'botsort.yaml' or options.get('with_reid') is not True
            or not cfg.get('person_model', '').endswith('.pt') or options.get('model', 'auto') != 'auto'
            or cfg.get('person_task', 'detect') != 'detect'):
        raise ValueError('Lost ReID guard requires native PyTorch detector features with BoTSORT')
    import ultralytics
    if ultralytics.__version__ != '8.3.228':
        raise ValueError('Lost ReID guard has only been checked with Ultralytics 8.3.228')
    from ultralytics.trackers.bot_sort import BOTSORT
    from ultralytics.trackers.basetrack import TrackState
    from ultralytics.trackers.track import TRACKER_MAP
    from ultralytics.trackers.utils import matching

    class GuardedBOTSORT(BOTSORT):
        def get_dists(self, tracks, detections):
            costs = super().get_dists(tracks, detections)
            if not tracks or not detections:
                return costs
            appearance = matching.embedding_distance(tracks, detections) / 2.0
            return veto_lost(costs, appearance, [t.state == TrackState.Lost for t in tracks],
                             1 - self.appearance_thresh)

    # The CLI runs in its own process; no installed-package files are modified.
    TRACKER_MAP['botsort'] = GuardedBOTSORT
