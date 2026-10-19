"""구성.json이 가리키는 분할 대본을 덱 원고·PPTX 노트에 동기화한다.

화면 XML과 랩은 변경하지 않는다. PDF 생성이나 실습 실행은 하지 않는다.
사용: python 회차노트동기화.py 제작용/구성/실전반/04회차/구성.json
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import re
import zipfile
from lxml import etree as E

NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
OFF = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'

def sync(config):
    config = Path(config).resolve()
    cfg = json.loads(config.read_text('utf-8-sig'))
    notes = {}
    for unit in cfg['units']:
        if unit['kind'] != 'pptx':
            continue
        text = (config.parent / unit['file']).read_text('utf-8-sig')
        for block in re.split(r'(?=^## \[SLIDE )', text, flags=re.M)[1:]:
            match = re.match(r'## \[SLIDE (\d+)(?:~(\d+))?\]', block)
            first, last = int(match[1]), int(match[2] or match[1])
            speech = ' '.join(line.strip().replace('**', '') for line in block.splitlines()[1:]
                              if line.strip() and not line.startswith(('>', '#', '---')))
            for number in range(first, last + 1):
                if number in notes:
                    raise ValueError(f'중복 발화: {number}')
                notes[number] = speech if number == first else f'{first}~{last}장 통합 발화는 {first}장 발표자 노트를 따른다.'
    assert set(notes) == set(range(1, cfg['slide_count'] + 1)), '대본 슬라이드 범위 불일치'
    deck = (config.parent / cfg['deck']).resolve()
    before = deck.read_text('utf-8-sig')
    blocks = re.split(r'(?=^## SLIDE )', before, flags=re.M)
    assert len(blocks) == cfg['slide_count'] + 1
    for n in notes:
        assert int(re.match(r'## SLIDE (\d+)', blocks[n])[1]) == n
        blocks[n] = re.sub(r'^- 노트:.*\n?', '', blocks[n], flags=re.M).replace(
            '### 화면 구성', '- 노트: ' + notes[n] + '\n### 화면 구성', 1)
    after = ''.join(blocks)
    if after != before:
        deck.write_text(after, encoding='utf-8')
    ppt = (config.parent / cfg['pptx']).resolve()
    changes = {}
    with zipfile.ZipFile(ppt) as source:
        for n, speech in notes.items():
            rels = E.fromstring(source.read(f'ppt/slides/_rels/slide{n}.xml.rels'))
            relation = next(r for r in rels if r.get('Type') == OFF + 'notesSlide')
            name = 'ppt/' + relation.get('Target').removeprefix('../')
            root = E.fromstring(source.read(name))
            body = root.xpath('//p:sp[p:nvSpPr/p:nvPr/p:ph[@type="body"]]/p:txBody', namespaces=NS)[0]
            if ''.join(body.xpath('.//a:t/text()', namespaces=NS)) == speech:
                continue
            for paragraph in list(body):
                if paragraph.tag == '{' + NS['a'] + '}p':
                    body.remove(paragraph)
            p = E.SubElement(body, '{' + NS['a'] + '}p')
            r = E.SubElement(p, '{' + NS['a'] + '}r')
            E.SubElement(r, '{' + NS['a'] + '}t').text = speech
            changes[name] = E.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
        if changes:
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w') as target:
                for entry in source.infolist():
                    target.writestr(entry, changes.get(entry.filename, source.read(entry)))
    if changes:
        ppt.write_bytes(out.getvalue())
    cfg['pptx_sha256'] = hashlib.sha256(ppt.read_bytes()).hexdigest()
    config.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'config': str(config), 'slides': len(notes), 'changed_notes': len(changes)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('configs', nargs='+')
    args = parser.parse_args()
    print(json.dumps([sync(p) for p in args.configs], ensure_ascii=False, indent=2))
