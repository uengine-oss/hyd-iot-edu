#!/usr/bin/env python3
"""A4 (U6) AI 판단 채점 CLI — 포털 '판단 채점' 화면과 같은 API(process /api/eval/*)를 터미널에서 쓴다.
정답표는 이 스크립트에도 없다. 사람이 적은 JSON 파일을 올리거나 포털에서 적는다.

  python scripts/evaluate_judgment.py golden                              # 정답표 보기 (처음엔 비어 있다)
  python scripts/evaluate_judgment.py golden-put item.json --by 강사      # 항목 새로 적기 (--update 면 고치기)
  python scripts/evaluate_judgment.py golden-del ITEM_ID --by 강사
  python scripts/evaluate_judgment.py knowledge                           # 지금 지식 상태(그래프 지문)
  python scripts/evaluate_judgment.py run --by 강사 [--path decide|evaluate] [--items a,b] [--repeats N] [--note 고치기 전]
  python scripts/evaluate_judgment.py run --by 강사 --path worker --instances 처리건1,처리건2
  python scripts/evaluate_judgment.py runs | show RUN_ID | compare BEFORE_ID AFTER_ID
  python scripts/evaluate_judgment.py score item.json judged.json          # 오프라인: 내 채점기와 포털 점수가 같은지 (랩업 L18)

score 는 네트워크 없이 process 의 순수 함수(procsvc.judgment_eval.score_judgement)를 그대로 쓴다. judged.json 은
agent /api/agent/decide 응답 또는 /api/agent/evaluate 실행 기록이다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK_NAMES = {'cause': '원인 적중', 'top': '1위 허용', 'forbidden': '빠질 조치', 'evidence': '근거 포함'}


def call(base: str, method: str, path: str, body=None, timeout: float = 600):
    req = urllib.request.Request(base.rstrip('/') + path, method=method, headers={'Content-Type': 'application/json'},
                                 data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors='replace')
        try:
            detail = json.loads(raw).get('detail')
        except ValueError:
            detail = raw
        sys.exit(f'실패 ({e.code}): {detail}')
    except urllib.error.URLError as e:
        sys.exit(f'process 서비스에 연결할 수 없습니다 ({base}): {e.reason}')


def show_item_result(r: dict) -> None:
    head = f"  {r['item']:<24} {r['score']:>5.1f}점"
    if r['repeats'] > 1:
        head += f"  {r['repeats']}회 " + ('모두 같음' if r.get('identical') else f"흔들림 {r['stability'] * 100:.0f}% · {r['min']}~{r['max']}")
    print(head + f"   {r['modal_outcome']}")
    if r.get('reason'):
        print(f"      사유: {r['reason']}")
    for key, label in CHECK_NAMES.items():
        c = r['checks'][key]
        extra = ''
        if key == 'evidence' and c['missing']:
            extra = ' 빠짐: ' + ', '.join(c['missing'])
        if key == 'forbidden':
            extra = ' ' + ' · '.join(f"{d['skill']} {d['got']}" for d in c['detail'] if not d['ok'])
        print(f"      {'O' if c['ok'] else 'X'} {label}{extra}")
    for m in r.get('facts_mismatch') or []:
        print(f"      ! 사실 다름: {m['key']} 정답표 {m['want']} / 판단 때 {m['got']}")


def show_run(run: dict) -> None:
    s, k = run['summary'], run.get('knowledge') or {}
    print(f"{run['id']}  {run['path']}  {run['by']}  {run['created']}  평균 {s['score']}점  항목 {s['items']}  만점 {s['perfect']}  보류 {s['withheld']}  흔들림 {s['unstable']}")
    print(f"  지식: 노드 {k.get('nodes')} · 관계 {k.get('relationships')} · 지문 {k.get('fingerprint')} · 마지막 변경 {k.get('last_change') or k.get('last_change_note')}")
    for r in run.get('items') or []:
        show_item_result(r)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='AI 판단 채점 (process /api/eval)')
    ap.add_argument('--process', default=os.getenv('PROCESS_URL', 'http://localhost:8080'))
    ap.add_argument('--json', action='store_true', help='응답 원문(JSON)으로 출력')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('golden')
    p = sub.add_parser('golden-put'); p.add_argument('file'); p.add_argument('--by', required=True); p.add_argument('--update', action='store_true')
    p = sub.add_parser('golden-del'); p.add_argument('item'); p.add_argument('--by', required=True)
    sub.add_parser('knowledge')
    p = sub.add_parser('run'); p.add_argument('--by', required=True); p.add_argument('--path', default='decide', choices=('decide', 'evaluate', 'worker'))
    p.add_argument('--items', default=''); p.add_argument('--repeats', type=int, default=1); p.add_argument('--instances', default=''); p.add_argument('--note', default='')
    p = sub.add_parser('runs'); p.add_argument('--limit', type=int, default=20)
    p = sub.add_parser('show'); p.add_argument('run')
    p = sub.add_parser('compare'); p.add_argument('before'); p.add_argument('after')
    p = sub.add_parser('score'); p.add_argument('item'); p.add_argument('judged')
    a = ap.parse_args(argv)
    base = a.process

    if a.cmd == 'score':
        sys.path.insert(0, str(ROOT / 'it/process'))
        from procsvc import judgment_eval as je
        item = je.validate_item(json.loads(Path(a.item).read_text(encoding='utf-8')))
        raw = json.loads(Path(a.judged).read_text(encoding='utf-8'))
        judged = je.normalize_evaluation(raw) if 'evaluation' in raw or 'steps' in raw else je.normalize_decision(raw)
        r = je.aggregate(item, [judged])
        print(json.dumps(r, ensure_ascii=False, indent=2)) if a.json else show_item_result(r)
        return 0
    if a.cmd == 'golden':
        out = call(base, 'GET', '/api/eval/golden')
        if a.json:
            print(json.dumps(out, ensure_ascii=False, indent=2)); return 0
        if not out['items']:
            print(out.get('empty_note') or '정답표가 비어 있습니다'); return 0
        for it in out['items']:
            print(f"{it['id']:<24} {it['asset']} {it['pattern']}  {it['title']}  (지문 {it['item_hash']}, {it['updated_by']})")
        return 0
    if a.cmd == 'golden-put':
        item = json.loads(Path(a.file).read_text(encoding='utf-8'))
        out = call(base, 'PUT', '/api/eval/golden/items/' + urllib.parse.quote(item.get('id', ''), safe=''), {'item': item, 'by': a.by}) if a.update \
            else call(base, 'POST', '/api/eval/golden/items', {'item': item, 'by': a.by})
        print(json.dumps(out, ensure_ascii=False, indent=2) if a.json else f"저장: {out['id']} (지문 {out['item_hash']})"); return 0
    if a.cmd == 'golden-del':
        call(base, 'DELETE', f"/api/eval/golden/items/{urllib.parse.quote(a.item, safe='')}?by={urllib.parse.quote(a.by)}")
        print(f'지움: {a.item}'); return 0
    if a.cmd == 'knowledge':
        print(json.dumps(call(base, 'GET', '/api/eval/knowledge'), ensure_ascii=False, indent=2)); return 0
    if a.cmd == 'run':
        body = {'path': a.path, 'by': a.by, 'note': a.note or None, 'repeats': a.repeats}
        if a.path == 'worker':
            body['instances'] = [{'instance': x.strip()} for x in a.instances.split(',') if x.strip()]
        elif a.items:
            body['items'] = [x.strip() for x in a.items.split(',') if x.strip()]
        out = call(base, 'POST', '/api/eval/runs', body)
        print(json.dumps(out, ensure_ascii=False, indent=2)) if a.json else show_run(out); return 0
    if a.cmd == 'runs':
        out = call(base, 'GET', f'/api/eval/runs?limit={a.limit}')
        if a.json:
            print(json.dumps(out, ensure_ascii=False, indent=2)); return 0
        for r in out:
            print(f"{r['id']}  {r['path']:<8} {r['by']:<8} {r['created']}  평균 {r['summary']['score']}점 · 항목 {r['summary']['items']}  {r.get('note') or ''}")
        return 0
    if a.cmd == 'show':
        out = call(base, 'GET', '/api/eval/runs/' + urllib.parse.quote(a.run, safe=''))
        print(json.dumps(out, ensure_ascii=False, indent=2)) if a.json else show_run(out); return 0
    if a.cmd == 'compare':
        out = call(base, 'GET', '/api/eval/compare?' + urllib.parse.urlencode({'before': a.before, 'after': a.after}))
        if a.json:
            print(json.dumps(out, ensure_ascii=False, indent=2)); return 0
        kd = out['knowledge']
        print(f"전 {out['before']['id']} → 후 {out['after']['id']}  평균 변화 {out['delta']}  좋아짐 {out['improved']} · 나빠짐 {out['regressed']} · 같음 {out['same']}")
        print(f"지식 바뀜: {'예' if kd['changed'] else '아니요'}  노드 {kd['nodes'][0]}→{kd['nodes'][1]} · 관계 {kd['relationships'][0]}→{kd['relationships'][1]}" + (f"  ({kd['note']})" if kd.get('note') else ''))
        for x in kd.get('removed_rels') or []:
            print(f"  - 끊긴 관계 {x['from']} -[{x['type']}]-> {x['to']}")
        for x in kd.get('added_rels') or []:
            print(f"  + 생긴 관계 {x['from']} -[{x['type']}]-> {x['to']}")
        for r in out['rows']:
            flags = ' (정답표 바뀜)' if r['golden_changed'] else ''
            print(f"  {r['item']:<24} {r['before']:>5} → {r['after']:<5} ({r['delta']:+}){flags}  " + ', '.join(f"{CHECK_NAMES[c['check']]} {'O' if c['before'] else 'X'}→{'O' if c['after'] else 'X'}" for c in r['changed']))
        return 0
    return 2


if __name__ == '__main__':
    sys.exit(main())
