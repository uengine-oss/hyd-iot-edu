"""로컬 검증용 시작 도구 묶음. 공개 배포 주소는 검증 뒤 별도로 고정한다.

launcher.py · 실습시작.cmd · settings.json은 손으로 관리하는 원본이다. 이 도구는 package-index.json에 주소를 붙여
catalog.json을 쓰고, 넷을 실습시작.zip으로 묶는다(lab_package.write_zip — 내용이 같으면 바이트도 같다).
"""
from pathlib import Path
import argparse,json
from urllib.parse import quote
from lab_package import write_zip
here=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--base-url',default='http://127.0.0.1:8765')
args=parser.parse_args()
data=json.loads((here/'package-index.json').read_text(encoding='utf-8'))
for lab in data['labs']:
    relative = Path(lab.pop('path')).relative_to('workspace/강의제작').as_posix()
    lab['url']=args.base_url.rstrip('/')+'/'+quote(relative)
    if 'guide_file' in lab:   # 코딩 랩 가이드(랩 폴더 밖) — 시작 도구가 받아 실습 폴더 옆에 둔다
        guide=lab['guide_file']
        guide['url']=args.base_url.rstrip('/')+'/'+quote(Path(guide.pop('path')).relative_to('workspace/강의제작').as_posix())
(here/'catalog.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
write_zip(here/'실습시작.zip',[('실습시작/'+name,(here/name).read_bytes()) for name in ['launcher.py','실습시작.cmd','catalog.json','settings.json']])
print(f"실습 시작 묶음: D:/HYD-Practice, 두 과정 {len(data['labs'])}개 항목, {args.base_url}")
