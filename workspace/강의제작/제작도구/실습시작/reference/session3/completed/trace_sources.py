"""sop.json · 조건표.csv의 출처마다 원문(자료/HM-8_매뉴얼.md)에서 그 절 · 단계 · 승인 줄을 찾아 나란히 적는다. 찾지 못한 출처는 따로 모은다.
사용: python 결과/trace_sources.py        → 결과/출처_대조.md, 화면에는 항목 수와 짝이 맞지 않는 항목
"""
from pathlib import Path
import csv
import json
import re

root = Path(__file__).resolve().parents[1]
manual = (root/'자료/HM-8_매뉴얼.md').read_text(encoding='utf-8').splitlines()
sections, lines_of, sop = {}, {}, None
for no, line in enumerate(manual, 1):
    m = re.match(r'## (HM-8\.\d+) ', line)
    if m:
        sections[m.group(1)], sop = (no, line[3:]), None
    m = re.match(r'### (SOP-[A-Z]+-\d+) ', line)
    if m:
        sop = m.group(1)
    m = re.match(r'(\d+)\. (.+)', line)
    if m and sop:
        lines_of[(sop, m.group(1))] = (no, m.group(2))
    if line.startswith('승인: ') and sop:
        lines_of[(sop, '승인')] = (no, line)


def find(source):
    """출처(「;」로 나눈 조각)마다 (조각, 원문 줄 번호 또는 None, 원문 또는 까닭)."""
    out = []
    for part in [p.strip() for p in source.split(';') if p.strip()]:
        m = re.fullmatch(r'(HM-8\.\d+)(?: (SOP-[A-Z]+-\d+) (?:단계 (\d+)|(승인)))?', part)
        if not m:
            out.append((part, None, '현행 원문의 절 · 단계 꼴이 아님'))
            continue
        sec, sop_id, step, approval = m.groups()
        hit = lines_of.get((sop_id, step or approval)) if sop_id else sections.get(sec)
        out.append((part, *hit) if hit else (part, None, '원문에서 찾지 못함'))
    return out


rows = []
doc = json.loads((root/'결과/sop.json').read_text(encoding='utf-8'))
for s in doc['sops']:
    for key in ('apply_conditions', 'prohibitions', 'steps', 'completion'):
        for i, item in enumerate(s[key], 1):
            rows.append((f'{s["id"]} {key}[{i}]', item['text'], item['source']))
    rows.append((f'{s["id"]} approval', s['approval']['role'], s['approval']['source']))
seen = set()
with (root/'결과/조건표.csv').open(encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f):
        if (r['rule_id'], r['action']) not in seen:
            seen.add((r['rule_id'], r['action']))
            rows.append((f'조건표 {r["rule_id"]} {r["action"]}', r['reason'], r['source_section']))

out = ['# 출처 대조', '', '| 항목 | 내용 | 출처 조각 | 원문 줄 | 원문 |', '|---|---|---|---|---|']
miss = []
for item, text, source in rows:
    for part, no, found in find(source):
        out.append(f'| {item} | {text} | {part} | {no or "—"} | {found} |')
        if no is None:
            miss.append(f'{item}: {part} — {found}')
out += ['', '## 짝이 맞지 않는 항목', ''] + ([f'- {m}' for m in miss] or ['- 없음'])
(root/'결과/출처_대조.md').write_text('\n'.join(out) + '\n', encoding='utf-8')
print(f'항목 {len(rows)}개, 짝이 맞지 않는 출처 조각 {len(miss)}개 → 결과/출처_대조.md')
for m in miss:
    print('  ' + m)
