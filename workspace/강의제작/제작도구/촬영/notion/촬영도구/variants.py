"""대사 손질을 구간 모듈에 반영한다(한 번 실행).
1) 반복 안내: voice-variants.json의 큐가 segs/seg-25~39에 두 번째로 나올 때부터 <id>-r<n> 큐로 바꾼다(다른 표현, 비슷한 길이).
2) 화면과 안 맞던 대사: 오전 검수에서 고친 음성(fix-*)으로 바꾼다.
새 큐의 문장은 voice-jobs.json에 모아 voice.py가 음성을 만든다. 같은 큐를 두 번 바꾸지 않도록 이미 바뀐 모듈이면 멈춘다."""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
cues = json.loads((HERE / 'source-cues.json').read_text(encoding='utf-8'))
by_source = {x['source_action']: x['id'] for x in cues if x.get('source_action')}
by_text = {x['text']: x['id'] for x in cues}
variants = {k: v for k, v in json.loads((HERE / 'voice-variants.json').read_text(encoding='utf-8')).items() if k != 'note'}
CALL = re.compile(r"c\.(say|source|line)\('((?:[^'\\]|\\.)*)'")
order = [HERE / 'segs' / f'seg-{n}.mjs' for n in range(25, 40)]
if any('-r2' in p.read_text(encoding='utf-8') for p in order):
    sys.exit('이미 반영된 모듈이 있다(-r2 큐 발견) — 다시 실행하지 않는다')

seen, jobs = {}, []
for p in order:
    src = p.read_text(encoding='utf-8')
    def swap(m):
        kind, arg = m.groups()
        cid = arg if kind == 'say' else by_source.get(arg) if kind == 'source' else by_text.get(arg)
        if cid not in variants:
            return m.group(0)
        seen[cid] = seen.get(cid, 0) + 1
        n = seen[cid]
        if n == 1:
            return m.group(0)
        texts = variants[cid]
        if n - 2 >= len(texts):
            sys.exit(f'{cid}: {n}번째 표현이 voice-variants.json에 없다({p.name})')
        new = f'{cid}-r{n}'
        jobs.append({'id': new, 'text': texts[n - 2], 'from': cid, 'segment': p.name})
        return f"c.say('{new}'"
    p.write_text(CALL.sub(swap, src), encoding='utf-8')
for cid, texts in variants.items():
    if seen.get(cid, 0) - 1 != len(texts):
        sys.exit(f'{cid}: 반복 {seen.get(cid, 0) - 1}번인데 표현은 {len(texts)}개')

# 화면과 안 맞던 대사 → 검수에서 고친 음성
FIX = [('segs/seg-29.mjs', "c.source('N17-03'", "c.say('fix-heading-two'"),
       ('segs/seg-32.mjs', "c.source('N20-20'", "c.say('fix-heading-two'"),
       ('segs/seg-36.mjs', "c.source('N24-22'", "c.say('fix-heading-two'"),
       ('segs/seg-29.mjs', "c.say('live-link-finish'", "c.say('fix-link-before-action'"),
       ('segs/seg-35.mjs', "c.say('live-image-second'", "c.say('fix-second-topic-open'"),
       ('segs/seg-35.mjs', "c.say('live-close-settings'", "c.say('fix-close-settings'"),
       ('lib/table-finish.mjs', "c.say('live-close-settings'", "c.say('fix-close-settings'"),
       ('lib/table-finish.mjs', "c.say('live-property-settings'", "c.say('fix-visible-properties'"),
       ('lib/table-finish.mjs', "c.say('live-search-close'", "c.say('fix-search-close'")]
for f, old, new in FIX:
    p = HERE / f; s = p.read_text(encoding='utf-8')
    if s.count(old) != 1:
        sys.exit(f'{f}: {old} 가 정확히 1번이 아니다({s.count(old)})')
    p.write_text(s.replace(old, new), encoding='utf-8')
(HERE / 'voice-jobs.json').write_text(json.dumps(jobs, ensure_ascii=False, indent=1), encoding='utf-8')
print(len(jobs), '개 새 큐,', len(FIX), '곳 고친 음성')
