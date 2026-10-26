"""로컬 검증용 시작 도구 묶음. 공개 배포 주소는 검증 뒤 별도로 고정한다."""
from pathlib import Path
import argparse,json,zipfile
from urllib.parse import quote
here=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--base-url',default='http://127.0.0.1:8765')
args=parser.parse_args()
p=here/'launcher.py'
s=p.read_text(encoding='utf-8')
s=s.replace("root=Path.home()/'HYD-Practice'", "root=Path(json.loads((HERE/'settings.json').read_text(encoding='utf-8'))['practice_root'])")
s=s.replace("message=tk.StringVar(value='새로 시작하면 별도 폴더에 자료를 받습니다.')", "message=tk.StringVar(value='새로 시작하면 별도 폴더에 자료를 받습니다.\\n저장 위치: '+str(root))")
p.write_text(s,encoding='utf-8')
(here/'settings.json').write_text(json.dumps({'practice_root':'D:/HYD-Practice'},indent=2),encoding='utf-8')
data=json.loads((here/'package-index.json').read_text(encoding='utf-8'))
for lab in data['labs']:
    lab['url']=args.base_url.rstrip('/')+'/'+quote(lab.pop('path'))
(here/'catalog.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(here/'실습시작.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in ['launcher.py','실습시작.cmd','catalog.json','settings.json']:z.write(here/name,'실습시작/'+name)
print(f"실습 시작 묶음: D:/HYD-Practice, 두 과정 {len(data['labs'])}개 항목, {args.base_url}")
