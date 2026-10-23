"""녹화 전 확인: segs/seg-25~39와 lib의 모든 음성 큐에 음성 파일(<id>.json)이 있는지. 사용: python check-cues.py"""
import json, re, sys
from pathlib import Path
from common import HERE, AUDIO
cues = json.loads((HERE / 'source-cues.json').read_text(encoding='utf-8'))
by_source = {x['source_action']: x['id'] for x in cues if x.get('source_action')}
by_text = {x['text']: x['id'] for x in cues}
CALL = re.compile(r"c\.(say|source|line)\('((?:[^'\\]|\\.)*)'")
files = [HERE / 'segs' / f'seg-{n}.mjs' for n in range(25, 40)] + [HERE / 'lib' / 'table-finish.mjs', HERE / 'lib' / 'file-popup.mjs']
n, bad = 0, []
for f in files:
    for kind, arg in CALL.findall(f.read_text(encoding='utf-8')):
        cid = arg if kind == 'say' else by_source.get(arg) if kind == 'source' else by_text.get(arg)
        n += 1
        if not cid or not (AUDIO / f'{cid}.json').exists():
            bad.append(f'{f.name}: {kind} {arg[:40]}')
print(n, 'cue calls')
if bad:
    sys.exit('음성 없는 큐:\n' + '\n'.join(bad))
print('all cues have audio')
