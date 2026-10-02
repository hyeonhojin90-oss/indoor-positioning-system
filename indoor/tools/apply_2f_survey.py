"""Generate display/navigation derivatives from the preserved GLB measurement.
Uses the saved pre-change SVG as a template; never transforms an already transformed SVG.
"""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'indoor/data/analysis/2f-survey-apply-20260922'
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def write(p,v):(ROOT/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
m=read('indoor/data/analysis/scan-geometry-20260921/2f-extension-measurements.json')['measurements']
xs=135.407/1240;ys=7.9/110
near=700-m['main_entry_to_extension_start_m']/ys
far=near-m['extension_start_wall_to_end_wall_m']/ys
width=m['extension_local_widths_m']['10'];right=1146+width/xs
entry_axis_svg_x=(1146+right)/2
entry_axis_map_x=69.424+(entry_axis_svg_x-732)/(1310-732)*(0-69.424)
survey=dict(version='2f-glb-20260922',source='2f-rescan.glb',
 entry_to_straight_m=m['main_entry_to_extension_start_m'],straight_length_m=m['extension_start_wall_to_end_wall_m'],
 entry_to_end_m=m['main_entry_to_end_m'],corridor_width_m=width,
 svg_near_y=near,svg_far_y=far,svg_corridor_right=right,
 entry_axis_svg_x=entry_axis_svg_x,entry_axis_map_x=entry_axis_map_x,
 source_status='scan-derived-approximate',room_interiors_surveyed=False)
write('indoor/web/data/maps/floor-02-survey.json',survey)
def Y(y):
 if y>=700:return y
 if y>=590:return 700+(y-700)*(700-near)/110
 return near+(y-585)*(near-far)/500
mp=read('indoor/web/data/maps/floor-02.json');mp['floor2_extension']['survey']=survey
for room in mp['rooms']:
 if room['id']=='STUDY':room['label']='ㄴ자 학습공간'
write('indoor/web/data/maps/floor-02.json',mp)
current_nav=read('indoor/web/data/navigation/areas-v1.json')
nav=read('indoor/data/analysis/2f-survey-apply-20260922/before/indoor/web/data/navigation/areas-v1.json')
# Preserve later floor surveys and the shared main-corridor metric when this
# generator is rerun.  Only floor 2 branch geometry belongs to this script.
for key,value in current_nav.get('floors',{}).items():
 if key!='2':nav['floors'][key]=value
f=nav['floors']['2']
if current_nav.get('floors',{}).get('2',{}).get('distanceMetric'):
 f['distanceMetric']=current_nav['floors']['2']['distanceMetric']
for a in f['areas']:
 if a['id']=='study':a['label']='ㄴ자 책상공간 주변'
 if 'svg_rect' not in a:continue
 x1,y1,x2,y2=a['svg_rect']
 if a['id']=='open_2107':x1=996
 if a['id']=='extension':x2=right;a['status']='glb-wall-reference-approximate'
 if a['id']=='entry':x2=1252
 a['svg_rect']=[x1,Y(y1),x2,Y(y2)]
for p in f['portals']:
 if 'svg_line' not in p:continue
 if p['id'] in ['main_entry','entry_extension']:p['svg_line'][1][0]=right
 if p['id']=='main_2107':p['svg_line'][0][0]=996
 if p['id']=='2107_mspace':p['svg_line']=[[1037,590],[1049,590]]
 p['svg_line']=[[x,Y(y)] for x,y in p['svg_line']]
for w in f['walls']:w['svg_line']=[[x,Y(y)] for x,y in w['svg_line']]
f['extensionMotionMetric']={'legacyStepMeters':nav['floors']['4']['distanceMetric']['metersPerLegacyUnit'],
 'xMetersPerUnit':xs/(69.424/578),'yMetersPerUnit':1,
 'note':'Only upper branch motion. Common corridor calibration unchanged; y above main edge is physical meters.'}
f['survey']=survey
f['note']='2F extension depth/width GLB 20260921; room split and entry width provisional; stairs beyond end excluded.'
write('indoor/web/data/navigation/areas-v1.json',nav)
html=(OUT/'before/indoor/web/pages/floors/floor-02.html').read_text(encoding='utf-8')
def transform_group(text,cls,transform):
 start=text.index('<g class="'+cls+'"');pos=text.index('>',start)+1;depth=1
 for match in re.finditer(r'<g\b[^>]*>|</g>',text[pos:]):
  depth+=-1 if match.group().startswith('</') else 1
  if depth==0:
   end=pos+match.start();return text[:pos]+f'<g transform="{transform}">'+text[pos:end]+'</g>'+text[end:]
 raise ValueError(cls)
sy=(near-far)/500;ty=near-585*sy
for cls in ['s-space-open','extension-room it-hall']:
 html=transform_group(html,cls,f'translate(0 {ty}) scale(1 {sy})')
sx=(right-1146)/86
html=transform_group(html,'extension-corridor',f'translate({1146*(1-sx)} {ty}) scale({sx} {sy})')
html=transform_group(html,'extension-room room-3104',f'translate({right-1232} {ty}) scale(1 {sy})')
sy2=(700-near)/110
for cls in ['floor2-open-zone','study-zone']:
 html=transform_group(html,cls,f'translate(0 {230*(1-sy2)}) scale(1 {sy2})')
html=html.replace('M1080 120V230',f'M1080 {near-470}V230')
html=html.replace('M1146 700H1232',f'M1146 700H{right}')
html=html.replace('M1037 590H1049',f'M1037 {near}H1049')
html=html.replace('M1189 732V105',f'M{(1146+right)/2} 732V{far+20}')
html=html.replace('M1049 636V365',f'M1043 {Y(636)}V{Y(365)}')
html=html.replace('x="1066" y="58"',f'x="1066" y="{far-25}"')
html=html.replace('ㄷ자','ㄴ자')
html=html.replace('다음 단계에서 GLB를 대조해 M-space, 책상, 2107과 증축 강의실의 실제 비율을 세부 조정합니다.',
 '증축 진입선~끝은 GLB 기준 약 32.1m(연결부 6.9m+직선 25.2m), 직선 폭 약 3.7m를 반영했습니다. 방 내부와 문별 좌표는 미측정입니다.')
(ROOT/'indoor/web/pages/floors/floor-02.html').write_text(html,encoding='utf-8')
print(json.dumps(survey,indent=2))
