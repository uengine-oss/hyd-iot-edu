"""저장소 루트에서 두 편의 녹음 직전 입력을 검사한다. 네트워크·유료 음성·인코딩을 쓰지 않는다."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

root = Path('workspace/강의제작')
config_dir = root / '제작도구/구성/통합반/05회차'
evidence_dir = root / '제작도구/근거/통합반_05회차_교재'
sys.path.insert(0, str((root / '제작도구/검사').resolve()))
sys.path.insert(0, str((root / '제작도구/기존제작/tools/video').resolve()))
from 장확정 import read_deck
import 강의영상 as video

def load(path):
    return json.loads(path.read_text(encoding='utf-8'))

def verify(path, expected):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise SystemExit(f'확정한 파일 지문과 다릅니다. {path}')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('episode', nargs='?', choices=['01','02'], help='지정하지 않으면 두 편을 확인한다.')
args = parser.parse_args()
config = load(config_dir / '구성.json')
deck = (config_dir / config['pptx']).resolve()
verify(deck, config['pptx_sha256'])
for unit in config['units']:
    script = (config_dir / unit['file']).resolve()
    if args.episode and script.name[:2] != args.episode:
        continue
    first, last = unit['slides']
    gate = unit['제작점검']
    if gate['상태'] != '제작 입력 확정' or gate['확인장'] != [first, last]:
        raise SystemExit(f'{script.name} 검토된 범위 {gate["확인장"]}. 정본 인계의 다음 장을 확인하세요.')
    verify(script, gate['대본_SHA256'])
    verify(config_dir / gate['강조설정'], gate['강조_SHA256'])
    ledger = read_deck(deck, script.parent)
    scope = (''.join(ledger[n] for n in range(first, last+1)) if first == 1 else '\n'.join(f'{n}:{ledger[n]}' for n in range(first, last+1)))
    if hashlib.sha256(scope.encode()).hexdigest() != gate['화면_노트_낭독_범위지문']:
        raise SystemExit(f'{script.name} 화면·노트·발화 범위 지문이 다릅니다.')
    report = load(evidence_dir / f'{script.name[:2]}_제작판정.json')
    for pause in report['쉼']['파일']:
        verify(Path(report['쉼']['폴더']) / pause['파일'], pause['SHA256'])
    trials = []
    for part in report['강조']['단원확인']:
        for name in ('시험낭독','강조계획','제작음원대조'):
            ref = part[name]
            verify(Path(ref['경로']), ref['SHA256'])
        trials.extend(load(Path(part['시험낭독']['경로']))['구획'])
    chunks = video.slides_text(script)
    if len(chunks) != len(trials):
        raise SystemExit(f'{script.name} 낭독 구획 수가 다릅니다.')
    for (n, end, speech), trial in zip(chunks, trials):
        if trial['장'] != [n, end] or hashlib.sha256(speech.encode()).hexdigest() != trial['낭독문SHA256']:
            raise SystemExit(f'{script.name} {n}장 낭독 구획이 다릅니다.')
    print(f'{script.name} {first}~{last}장, {len(trials)}구획, 쉼 {report["쉼"]["경계수"]}곳, 강조 {report["강조"]["표시수"]}개 확인')
