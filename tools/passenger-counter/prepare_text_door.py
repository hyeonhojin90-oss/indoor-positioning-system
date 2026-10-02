"""Cache a pretrained text class offline so runtime does not need a text encoder."""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault('YOLO_CONFIG_DIR',str(Path(__file__).resolve().parent/'runs/settings'))


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--encoder',type=Path,required=True)
    p.add_argument('--prompt',default='bus door')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    model_path,encoder,output=a.model.resolve(),a.encoder.resolve(),a.output.resolve()
    if encoder.name!='mobileclip_blt.ts' or not encoder.is_file():
        raise ValueError('Supply the existing official mobileclip_blt.ts; no implicit download')
    if output.exists() or output.with_suffix('.source.json').exists() or 'yoloe' not in output.stem:
        raise ValueError('New yoloe output required')
    import torch
    import ultralytics
    from ultralytics import YOLO,YOLOE
    torch.set_num_threads(2)
    model=YOLOE(str(model_path))
    before=digest(model_path)
    cwd=Path.cwd()
    try:
        os.chdir(encoder.parent)
        embedding=model.get_text_pe([a.prompt])
    finally:
        os.chdir(cwd)
    model.set_classes([a.prompt],embedding)
    output.parent.mkdir(parents=True,exist_ok=True)
    model.save(output)
    restored=YOLO(str(output))
    if (restored.names!={0:a.prompt} or restored.task!='segment'
            or not torch.allclose(model.model.pe.cpu(),restored.model.pe.cpu(),atol=.001,rtol=0)
            or digest(model_path)!=before):
        raise RuntimeError('Prepared text checkpoint failed to restore class embeddings')
    metadata=dict(base_model_sha256=before,base_model=str(model_path),
                  encoder=str(encoder),encoder_sha256=digest(encoder),
                  output_sha256=digest(output),prompt=a.prompt,prompt_kind='fixed_text',
                  embedding_restore_parity=True,ultralytics=ultralytics.__version__,
                  uses_training_reference=False,requires_runtime_encoder=False,
                  independent_accuracy_validated=False,jetson_validated=False)
    output.with_suffix('.source.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps(metadata,indent=2))


if __name__=='__main__':main()
