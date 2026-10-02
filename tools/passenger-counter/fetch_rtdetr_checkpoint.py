"""Fetch the published older official asset compatible with the pinned comparison runtime."""
import json,subprocess,sys,urllib.request
from pathlib import Path

def main():
    url='https://api.github.com/repos/ultralytics/assets/releases/tags/v8.3.0'
    req=urllib.request.Request(url,headers={'User-Agent':'PassengerCounterResearch/0.1'})
    with urllib.request.urlopen(req,timeout=25) as response:release=json.load(response)
    assets=[a for a in release['assets'] if a['name']=='rtdetr-l.pt']
    if len(assets)!=1:raise ValueError('Expected one published official checkpoint')
    asset=assets[0];out=Path('models/rtdetr-l.pt')
    metadata=out.with_suffix('.asset.json')
    with metadata.open('x') as f:json.dump(dict(release_api=url,release_page=release['html_url'],asset=asset,
        model_documentation='https://docs.ultralytics.com/models/rtdetr/',purpose='Alternative pretrained detector diagnostic; not adopted or Orin tested.'),f,indent=2)
    subprocess.run([sys.executable,'download_checkpoint.py','--url',asset['browser_download_url'],'--output',str(out),
        '--expected-bytes',str(asset['size']),'--deadline-seconds','600'],check=True)

if __name__=='__main__':main()
