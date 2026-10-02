"""Download only pinned author-published OSNet checkpoint/source/license."""
import urllib.request,json,hashlib
from pathlib import Path
ROOT=Path('models/osnet-x025-author-resume4')
GH='f8cd150fdf77e8d9e1ed143b7f308c2c609ded50';HF='a5c5cc037c24235cda3b21085b93ad77c9616224'
WEIGHT='osnet_x0_25_msmt17_combineall_256x128_amsgrad_ep150_stp60_lr0.0015_b64_fb10_softmax_labelsmooth_flip_jitter.pth'
def main():
 ROOT.mkdir(exist_ok=False)
 sources=[('osnet.py','https://raw.githubusercontent.com/KaiyangZhou/deep-person-reid/'+GH+'/torchreid/models/osnet.py'),('LICENSE','https://raw.githubusercontent.com/KaiyangZhou/deep-person-reid/'+GH+'/LICENSE'),('README.md','https://huggingface.co/kaiyangzhou/osnet/resolve/'+HF+'/README.md'),('model.pth','https://huggingface.co/kaiyangzhou/osnet/resolve/'+HF+'/'+WEIGHT)]
 rows=[]
 for name,url in sources:
  with urllib.request.urlopen(url,timeout=60) as response:data=response.read(20_000_001)
  if len(data)>20_000_000:raise ValueError('Unexpected oversized asset')
  (ROOT/name).write_bytes(data);rows.append(dict(path=name,url=url,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()));print(name,len(data),flush=True)
 (ROOT/'source.json').write_text(json.dumps(dict(files=rows,github_revision=GH,huggingface_revision=HF,author='Kaiyang Zhou',pretraining_dataset='MSMT17',task='person_reidentification',download_complete=True,source_executed=False,hardware_validated=False,independent_accuracy_validated=False),indent=2))
if __name__=='__main__':main()
