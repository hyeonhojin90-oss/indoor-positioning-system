"""Explicit alternative detector policy; current deployment/export stays YOLO only."""
from pathlib import Path

def validate(config):
    family=config.get('person_family','yolo')
    if family not in ('yolo','rtdetr'):raise ValueError('Unknown person model family')
    if 'person_rtdetr_nms_iou' in config:
        if family!='rtdetr':raise ValueError('RT-DETR duplicate suppression cannot modify default YOLO')
        from rtdetr_duplicate_filter import kept_indices
        kept_indices([],[],[],config['person_rtdetr_nms_iou'])
    if family=='rtdetr':
        if config.get('person_task')!='detect' or config.get('person_tracker','bytetrack.yaml')!='bytetrack.yaml' or config.get('lost_reid_guard'):
            raise ValueError('RT-DETR comparison requires explicit detect and ByteTrack without native ReID hooks')
        if config.get('person_rect') is not False or config.get('person_imgsz',640)!=640:
            raise ValueError('RT-DETR comparison explicitly uses640 square scale-filled preprocessing')
        path=Path(config.get('person_model',''))
        if path.suffix!='.pt' or not path.is_file():raise ValueError('RT-DETR comparison requires existing native PT checkpoint; no engine/ONNX shortcut')
    return family

def load(config):
    family=validate(config)
    if family=='rtdetr':
        from ultralytics import RTDETR
        from ultralytics.nn.modules.head import RTDETRDecoder
        model=RTDETR(config['person_model'])
        if not isinstance(model.model.model[-1],RTDETRDecoder):raise ValueError('Checkpoint is not RT-DETR architecture')
        if 'person_rtdetr_nms_iou' in config:
            from rtdetr_duplicate_filter import RTDETRDuplicateFilter
            model.rtdetr_duplicate_filter=RTDETRDuplicateFilter(model,config['person_rtdetr_nms_iou'])
        return model
    from ultralytics import YOLO
    return YOLO(config.get('person_model','yolo11n.pt'),task=config.get('person_task'))
