import json
from pathlib import Path
from fetch_github_demo_video import fetch

def main():
    api='https://api.github.com/repos/shijieS/people-counting-dataset'
    commit=json.loads(fetch(api+'/commits/master',2*1024*1024))['sha']
    tree=json.loads(fetch(api+'/git/trees/'+commit+'?recursive=1',4*1024*1024))
    assert not tree.get('truncated')
    files=[r for r in tree['tree'] if r['type']=='blob' and r['path'].lower().endswith(('.mp4','.avi','.webm','.gif'))]
    report=dict(source='https://github.com/shijieS/people-counting-dataset',commit=commit,files=files,
        license='CC BY-NC-SA 3.0',author='Sun, ShiJie et al.',
        citation='Benchmark data and method for real-time people counting in cluttered scenes using depth sensors, IEEE TITS, 2019',
        full_dataset_baidu_link_only=True,github_files_not_complete_dataset=True,
        footage_downloaded=False,rgb_depth_synchronization_not_guaranteed=True,
        camera='Kinect V1 above bus door; distinct from project exterior stop camera')
    with Path('reviews/pcds-public-file-inventory-r2.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
    q=Path('data/public-github-bus-demo-20261001-r2.source.json')
    r=json.loads(q.read_text());r.update(shutterstock_watermark_visually_confirmed=True,
        quarantined_from_training_and_accuracy_evaluation=True,model_inference_performed=False,
        note='Source-only inspection revealed stock-watermarked footage; repository MIT statement does not establish original video permission.')
    q.write_text(json.dumps(r,indent=2))

if __name__=='__main__':main()
