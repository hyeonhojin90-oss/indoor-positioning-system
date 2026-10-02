"""Acquire a small explicit Commons batch with machine-readable source/license metadata."""
import argparse,hashlib,json,urllib.parse,urllib.request
from pathlib import Path
from download_door_photos import acquire

SOURCES=[
 ('christchurch-boarding-1968.jpg','Passengers boarding bus at Cathedral Square, Christchurch.jpg'),
 ('boarding-island-2017.jpg','Bus boarding from boarding island (38270975711).jpg'),
 ('london-middle-door-2020.jpg','Middle-Door-Boarding-P1640542 (49997680861).jpg'),
 ('manhattan-boarding-1973.jpg','BOARDING A BUS IN THE FINANCE DISTRICT OF LOWER MANHATTAN - NARA - 549921.jpg')]

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args()
    if a.output.exists() and not a.resume:raise ValueError('New directory required')
    a.output.mkdir(parents=True,exist_ok=True);rows=[]
    prior=json.loads((a.output/'provenance.json').read_text()) if a.resume else []
    known={r['name']:r for r in prior}
    for name,title in SOURCES:
        if name in known and known[name].get('status')=='downloaded':
            row=known[name]
            if row['title']!=title or hashlib.sha256((a.output/name).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Resume source changed')
            rows.append(row);continue
        query=urllib.parse.urlencode(dict(action='query',format='json',prop='imageinfo',titles='File:'+title,iiprop='url|sha1|size|extmetadata',iiurlwidth=1280))
        req=urllib.request.Request('https://commons.wikimedia.org/w/api.php?'+query,headers={'User-Agent':'PassengerCounterResearch/0.1 (public image research)'})
        with urllib.request.urlopen(req,timeout=25) as response:payload=json.load(response)
        page=next(iter(payload['query']['pages'].values()));info=page['imageinfo'][0];meta=info['extmetadata']
        license_name=meta.get('LicenseShortName',{}).get('value','');license_url=meta.get('LicenseUrl',{}).get('value','')
        if not (license_name.startswith('CC BY') or license_name in ['Public domain','PD','CC0']):raise ValueError('Unverified reusable license: '+license_name)
        row=dict(name=name,title=title,page=info['descriptionurl'],url=info.get('thumburl',info['url']),original_url=info['url'],
            author_html=meta.get('Artist',{}).get('value'),credit_html=meta.get('Credit',{}).get('value'),
            license=license_name,license_url=license_url,original_sha1=info['sha1'],original_size=info['size'],
            original_dimensions=[info['width'],info['height']],training_used=False)
        result=acquire(row,a.output)
        if result['status']=='downloaded' and urllib.parse.urlparse(row['url']).path==urllib.parse.urlparse(row['original_url']).path:
            actual=hashlib.sha1((a.output/name).read_bytes()).hexdigest()
            if actual!=row['original_sha1']:raise ValueError('Original SHA1 differs from Commons')
            result['original_sha1_verified']=True;result['alterations']='Original source bytes retained'
        rows.append(result)
        (a.output/'provenance.json').write_text(json.dumps(rows,indent=2))
    print('Metadata and images saved; no model evaluation or training performed.')

if __name__=='__main__':main()
