"""Download a public video URL explicitly published in its source page, never guessed."""
import argparse,hashlib,html,json,re
from pathlib import Path
import urllib.request
from urllib.parse import urlparse

def main():
    p=argparse.ArgumentParser();p.add_argument('--page',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    if not a.page.startswith('https://www.pexels.com/video/'):raise ValueError('Expected public Pexels source')
    req=urllib.request.Request(a.page,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=30) as r:page=r.read(8*1024*1024).decode('utf-8')
    urls=re.findall(r'https://videos\.pexels\.com/[^\s"<>\\]+\.mp4[^\s"<>\\]*',html.unescape(page))
    clip_id=re.search(r'-(\d+)/?$',urlparse(a.page).path)
    if clip_id is None:raise ValueError('Source has no explicit clip identity')
    urls=[u for u in urls if re.search(r'/'+clip_id[1]+r'(?:/|-)',urlparse(u).path)]
    urls=sorted(set(urls),key=lambda u:(('720' not in u),len(u)))
    if not urls:raise ValueError('No explicitly published public MP4 URL found')
    url=urls[0];a.output.parent.mkdir(parents=True,exist_ok=True);total=0
    with urllib.request.urlopen(url,timeout=45) as source,a.output.open('xb') as f:
        while chunk:=source.read(1024*1024):
            total+=len(chunk)
            if total>128*1024*1024:raise ValueError('Public clip exceeds bounded download budget')
            f.write(chunk)
    report=dict(page=a.page,url=url,bytes=total,sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),
        purpose='Independent scene validation; source page license applies; no redistribution.',all_published_candidates=urls)
    with a.output.with_suffix('.source.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps({k:report[k] for k in ('page','bytes','sha256')}))
if __name__=='__main__':main()
