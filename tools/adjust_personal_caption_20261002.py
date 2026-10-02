"""Make a narrow HWPX layout edit while preserving all embedded images."""
from pathlib import Path
from zipfile import ZipFile
from copy import deepcopy
from lxml import etree as ET
import hashlib
import json

OUT = Path(__file__).resolve().parents[1] / 'exports/reports/personal-caption-20261002'
SOURCE = OUT / 'before-caption.hwpx'
TARGET = OUT / 'personal-caption-edited.hwpx'
NS = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
      'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
      'hh': 'http://www.hancom.co.kr/hwpml/2011/head'}
ratio = 0.72

with ZipFile(SOURCE) as src:
    section = ET.fromstring(src.read('Contents/section0.xml'))
    header = ET.fromstring(src.read('Contents/header.xml'))
    pictures = section.findall('.//hp:pic', NS)
    assert len(pictures) == 16
    targets = pictures[-2:]
    target_table = next(a for a in targets[0].iterancestors() if ET.QName(a).localname == 'tbl')
    assert target_table is next(a for a in targets[1].iterancestors() if ET.QName(a).localname == 'tbl')
    caption_nodes = target_table.findall('.//hp:t', NS)
    nonempty = [t for t in caption_nodes if t.text]
    assert [t.text for t in nonempty] == [
        '보정데이터 수집 – 경로라벨 비교', '보정데이터 수집 – 센서 기준점']
    replacements = {
        '보정데이터 수집 – 경로라벨 비교': '[그림11] 보정데이터 수집 – 경로라벨 비교',
        '보정데이터 수집 – 센서 기준점': '[그림12] 보정데이터 수집 – 센서 기준점',
    }
    before_text = section.xpath('.//hp:t/text()', namespaces=NS)
    for t in nonempty:
        t.text = replacements[t.text]

    # Apply a new paragraph style only to this two-column image/caption table.
    para_collection = header.find('.//hh:paraProperties', NS)
    base = next(p for p in para_collection if p.get('id') == '0')
    centered = deepcopy(base)
    new_id = str(max(int(p.get('id')) for p in para_collection) + 1)
    centered.set('id', new_id)
    centered.find('hh:align', NS).set('horizontal', 'CENTER')
    para_collection.append(centered)
    para_collection.set('itemCnt', str(len(para_collection)))
    for p in target_table.findall('.//hp:p', NS):
        p.set('paraPrIDRef', new_id)
        for seg in p.findall('hp:linesegarray', NS):
            p.remove(seg)

    image_changes = []
    for pic in targets:
        size = pic.find('hp:sz', NS)
        old = {k: int(size.get(k)) for k in ('width', 'height')}
        new = {k: round(v * ratio) for k, v in old.items()}
        for child_name in ('sz', 'curSz'):
            child = pic.find('hp:' + child_name, NS)
            for k, v in new.items():
                child.set(k, str(v))
        rotation = pic.find('hp:rotationInfo', NS)
        rotation.set('centerX', str(new['width'] // 2))
        rotation.set('centerY', str(new['height'] // 2))
        offset = pic.find('hp:offset', NS)
        offset.set('x', '0')
        offset.set('y', '0')
        rendering = pic.find('hp:renderingInfo', NS)
        for child_name in ('transMatrix', 'scaMatrix'):
            matrix = rendering.find('hc:' + child_name, NS)
            matrix.set('e3', '0')
            matrix.set('e6', '0')
        matrix = rendering.find('hc:scaMatrix', NS)
        for k in ('e1', 'e5'):
            matrix.set(k, format(float(matrix.get(k)) * ratio, '.8f'))
        pos = pic.find('hp:pos', NS)
        pos.set('treatAsChar', '1')
        pos.set('horzOffset', '0')
        pos.set('vertOffset', '0')
        cell = next(a for a in pic.iterancestors() if ET.QName(a).localname == 'tc')
        cell.find('hp:cellSz', NS).set('height', str(new['height'] + 282))
        image_changes.append({'id': pic.get('id'), 'before': old, 'after': new})

    caption_height = max(int(tc.find('hp:cellSz', NS).get('height'))
                         for tc in target_table.findall('hp:tr', NS)[1].findall('hp:tc', NS))
    target_table.find('hp:sz', NS).set('height', str(max(c['after']['height'] for c in image_changes) + caption_height + 282))

    new_text = section.xpath('.//hp:t/text()', namespaces=NS)
    assert new_text == [replacements.get(t, t) for t in before_text]
    replacements_xml = {
        'Contents/section0.xml': ET.tostring(section, xml_declaration=True, encoding='UTF-8', standalone=True),
        'Contents/header.xml': ET.tostring(header, xml_declaration=True, encoding='UTF-8', standalone=True),
    }
    with ZipFile(TARGET, 'w') as dest:
        for entry in src.infolist():
            dest.writestr(entry, replacements_xml.get(entry.filename, src.read(entry.filename)))

with ZipFile(SOURCE) as src, ZipFile(TARGET) as dest:
    assert dest.testzip() is None
    assert src.namelist() == dest.namelist()
    unchanged = [name for name in src.namelist() if name not in replacements_xml]
    assert all(src.read(name) == dest.read(name) for name in unchanged)
    assert len(dest.read('Contents/section0.xml')) > 0
    proof = {'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
             'edited_sha256': hashlib.sha256(TARGET.read_bytes()).hexdigest(),
             'scale_ratio': ratio, 'images': image_changes,
             'changed_zip_entries': list(replacements_xml),
             'unchanged_zip_entries': len(unchanged),
             'original_text_preserved_except_caption_prefixes': True,
             'all_embedded_images_preserved': True}
    (OUT / 'edit-verification.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(proof, ensure_ascii=False))
