"""Evaluate old detector once on the exact new test cohort; never tune thresholds."""
import hashlib,json,os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path('runs/settings').resolve()))
os.environ.setdefault('MPLCONFIGDIR',str(Path('runs/matplotlib').resolve()))

def main():
    import torch
    from ultralytics import YOLO
    from runtime_threads import configure_model_threads
    data=Path('runs/door-photo-enriched-retention-20261001-r2/dataset.yaml')
    model_path=Path('runs/bus-portal-bootstrap-train-20260930/training/door/weights/best.pt')
    out=Path('runs/door-photo-enriched-old-baseline-20261001-r2');out.mkdir(exist_ok=False)
    torch.set_num_threads(2);model=YOLO(str(model_path));configure_model_threads(model,2)
    metrics=model.val(data=str(data.resolve()),split='test',device='cpu',imgsz=416,workers=0,
                      project=str(out.resolve()),name='test')
    result=dict(metrics=metrics.results_dict,model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
        test_list_sha256=hashlib.sha256((data.parent/'test.txt').read_bytes()).hexdigest(),
        same_test_cohort=True,already_inspected_photos=True,independent_video_accuracy_validated=False,
        note='Same four held-out test images; this metric must not be compared with a different old test cohort.')
    (out/'metrics.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
