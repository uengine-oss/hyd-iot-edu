"""관계 조회의 실제 프레임에서 결과 표만 추출한다. 원본과 자르기 좌표를 기록한다."""
from pathlib import Path
import hashlib,json
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'.evidence/practice-20261026/relations-guide-steps'
boxes={'01-cooler':(618,284,1905,572),'02-quantity-compact':(618,315,1887,787),'03-parts':(618,284,1905,634),'04-counts':(618,284,1905,634)}
records=[]
for name,box in boxes.items():
    src=SOURCE/(name+'.jpg')
    with Image.open(src) as im:
        assert im.size==(1920,1080)
        cropped=im.crop(box)
        for course in ['통합반','실전반']:
            dest=ROOT/'산출물'/course/'실습/02회차/랩/02일차_실습1_관계조회/images'/(name+'.png')
            dest.parent.mkdir(parents=True,exist_ok=True);cropped.save(dest)
    records.append({'source':src.relative_to(ROOT).as_posix(),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'crop':box,'output':name+'.png','kind':'actual Neo4j result; crop only'})
(Path(__file__).parent/'relation-screen-provenance.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print('실제 조회 표 4개·두 과정 가이드 이미지 저장')
