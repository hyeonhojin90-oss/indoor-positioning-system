"""Bind observed embeddings to the exact frozen detections used for cropping."""
import hashlib
from pathlib import Path


def snapshot_files(paths):
    return {str(Path(path)): hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in paths}


def require_unchanged(snapshot):
    for path, expected in snapshot.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError('Feature input changed during work: ' + path)


def validate_feature_cache(reference, summary, cache_rows, feature_bytes,
                           reference_summary_bytes, reference_tracks_bytes):
    for key, data in [('features_sha256', feature_bytes),
                      ('reference_summary_sha256', reference_summary_bytes),
                      ('reference_tracks_sha256', reference_tracks_bytes)]:
        if summary.get(key) != hashlib.sha256(data).hexdigest():
            raise ValueError('Changed or unbound feature input: ' + key)
    if len(reference) != len(cache_rows):
        raise ValueError('Incomplete observed feature cache')
    for actual, cached in zip(reference, cache_rows):
        for key in ('frame', 'raw_ids', 'raw_boxes'):
            if cached.get(key) != actual[key]:
                raise ValueError('Different observed crop input: ' + key)
        if len(cached['features']) != len(actual['raw_boxes']):
            raise ValueError('Different observed feature count')
