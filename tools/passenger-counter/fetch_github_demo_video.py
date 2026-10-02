"""Fetch one public diagnostic example; verify its immutable Git blob identity."""
import hashlib,json,urllib.request
from pathlib import Path

def fetch(url,limit):
    req=urllib.request.Request(url,headers={'User-Agent':'PassengerCounterResearch','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=45) as r:
        if r.headers.get('Content-Length') and int(r.headers['Content-Length'])>limit:raise ValueError('File exceeds bounded download')
        data=r.read(limit+1)
        if len(data)>limit:raise ValueError('File exceeds bounded download')
        return data

def main():
    repo='sanjarbek1030/BusOccupancyCounter'
    api='https://api.github.com/repos/'+repo
    commit=json.loads(fetch(api+'/commits/main',2*1024*1024))['sha']
    metadata=json.loads(fetch(api+'/contents/bus_input.mp4?ref='+commit,1024*1024))
    assert metadata['type']=='file' and 0<metadata['size']<32*1024*1024
    url='https://raw.githubusercontent.com/'+repo+'/'+commit+'/bus_input.mp4'
    data=fetch(url,32*1024*1024)
    blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    assert blob==metadata['sha'] and len(data)==metadata['size']
    out=Path('data/public-github-bus-demo-20261001-r2.mp4')
    with out.open('xb') as f:f.write(data)
    report=dict(source_page='https://github.com/'+repo+'/blob/'+commit+'/bus_input.mp4',
        raw_url=url,commit=commit,git_blob_sha1=blob,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),
        repository_readme_license_statement='MIT — use freely, attribution appreciated.',
        video_original_author_and_separate_license_not_identified=True,
        diagnostic_only=True,training_used=False,redistribution_performed=False,
        event_labels_not_provided=True,independent_scene_not_yet_confirmed=True)
    with out.with_suffix('.source.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))

if __name__=='__main__':main()
