"""ego 실제 조회 화면에서 결과 표만 추출. 원본·좌표·해시를 함께 기록."""
from pathlib import Path
from PIL import Image
import hashlib,json
root=Path(__file__).resolve().parents[2]
evidence=root/'.evidence/practice-20261026'
records=[]
for filename,source,box,courses in [
 ('part-usage.png','neo4j-zoom-reset.png',(19,750,1902,1040),['통합반','실전반']),
 ('supplier-conditions.png','neo4j-supply-compact.png',(19,343,1902,994),['실전반'])]:
    src=evidence/source
    im=Image.open(src)
    for course in courses:
        target=root/'산출물'/course/'실습/02회차/랩/02일차_실습4_그래프구현과검증/images'/filename
        target.parent.mkdir(parents=True,exist_ok=True)
        im.crop(box).save(target)
        records.append({'target':target.relative_to(root).as_posix(),'source':src.relative_to(root).as_posix(),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'crop_box':box,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'kind':'별도 교육 DB의 강사 참조 모델 실제 조회; 학생 수행 화면 아님'})
(Path(__file__).parent/'capture-provenance.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
print('실제 조회 표 3개 저장')
