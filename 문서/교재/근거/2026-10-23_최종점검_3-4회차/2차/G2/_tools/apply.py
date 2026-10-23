import json, re, sys
src, edits_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(src, encoding='utf-8').read()
edits = json.load(open(edits_path, encoding='utf-8'))
# locate section spans
heads = [(m.start(), m.group(1)) for m in re.finditer(r'^## \[SLIDE ([0-9~]+)\]', text, flags=re.M)]
def span(slide):
    for i,(pos,s) in enumerate(heads):
        if s == slide:
            end = heads[i+1][0] if i+1 < len(heads) else len(text)
            return pos, end
    raise SystemExit('no slide '+slide)
start102 = span('102')[0]
for e in edits:
    a,b = span(e['slide'])
    sec = text[a:b]
    cnt_sec = sec.count(e['before'])
    cnt_all = text[start102:].count(e['before'])
    if cnt_sec != 1 or cnt_all != 1:
        raise SystemExit(f"edit {e['n']}: count in section={cnt_sec}, after102={cnt_all}")
    sec2 = sec.replace(e['before'], e['after'], 1)
    text = text[:a] + sec2 + text[b:]
    heads = [(m.start(), m.group(1)) for m in re.finditer(r'^## \[SLIDE ([0-9~]+)\]', text, flags=re.M)]
open(out, 'w', encoding='utf-8').write(text)
print('applied', len(edits))
