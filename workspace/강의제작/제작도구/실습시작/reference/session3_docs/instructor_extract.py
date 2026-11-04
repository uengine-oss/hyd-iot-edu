"""강사 참조 — 강사 추출 실행(수업 모델 호출). 저장소 밖 임시 사본 폴더에서 메인이 돌린다(이 파일을 쓴 작업자는 모델을 부르지 않았다).

통합 04-2 랩 폴더의 사본에서, 그 폴더의 llm_client.py(학생과 같은 연결 도구 · 같은 상한 · 같은 응답 기록)로 강사 요청 글(강사_요청글.md — main
manual_extraction INSTRUCTION 요지를 랩 계약 꼴로 옮김)을 문서 조각마다 보낸다. 받은 답을 계약 꼴 후보로 바꾸고, 인용 위치는 원문에서 코드로 찾는다
(파일 글자 그대로 한 곳 → exact, 글자 · 숫자만 남겨 한 곳 → normalized, 그 밖 → unlocated). 결과는 사본 폴더의 결과/후보/ · 결과/응답_기록/.

사용(메인, 저장소 밖):
  cp -r <저장소>/workspace/강의제작/산출물/통합반/실습/04회차/랩/04일차_실습2_문서지식추출 <임시>/run1
  (<임시>/run1/.env 에 발급 도구가 준 세 줄을 붙여 넣는다 — 키 값은 어디에도 옮기지 않는다)
  python <저장소>/…/reference/session3_docs/instructor_extract.py <임시>/run1 [--dry-run]
  같은 일을 <임시>/run2 사본에서 한 번 더(같은 요청의 두 번째 응답 — 두 실행의 차이를 본다)
  python <저장소>/…/reference/session3_docs/run_reference.py --model-candidates <임시>/run1/결과/후보 --model-candidates <임시>/run2/결과/후보
--dry-run: 모델을 부르지 않고 조각 수 · 글자 수만 찍는다. 조각은 문서마다 절 머리(##, 제N조, 스캔본 HM-9.x)에서 끊고 1,000자 안에서 묶는다(폴더 상한 60번 안).
"""
from __future__ import annotations

from pathlib import Path
import argparse
import importlib.util
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract_reference as X  # noqa: E402
import branches as BR  # noqa: E402

LIMIT = 1000
HEAD = re.compile(r'^(##\s+\S|제\d+조\(|HM-9\.\d+\s+\S|=== 스캔)')


def chunks(text):
    """[(첫 줄 번호, 조각 글)] — 절 머리에서 끊고 LIMIT 안에서 묶는다."""
    lines = text.splitlines()
    blocks, cur, start = [], [], 1
    for n, line in enumerate(lines, 1):
        if HEAD.match(line.strip()) and cur and '....' not in line:
            blocks.append((start, cur))
            cur, start = [], n
        cur.append(line)
    if cur:
        blocks.append((start, cur))
    out, buf, first = [], [], None
    for s, block in blocks:
        body = '\n'.join(block)
        if buf and len('\n'.join(buf)) + len(body) > LIMIT:
            out.append((first, '\n'.join(buf)))
            buf, first = [], None
        if first is None:
            first = s
        buf.append(body)
    if buf:
        out.append((first, '\n'.join(buf)))
    return out


def to_candidates(row, text, replies):
    """받은 답들 → 후보 파일(dict). 인용 위치는 원문에서 찾는다."""
    doc = X.Doc(text, '스캔본' in row['상태'])
    bilingual = bool(re.search(r'^\s*(?:\d+\.\s+)?EN:', text, re.M))
    cands, unlocated, warnings, runs = [], [], [], []
    for reply in replies:
        runs.append({'record': reply['file'], 'request_hash': reply['request_hash'], 'model': reply['model'], 'method': reply['method'], 'reused_from': reply.get('reused_from')})
        raw = reply.get('response_text') or ''
        m = re.search(r'\{.*\}', raw, re.S)
        try:
            data = json.loads(m.group()) if m else {}
        except ValueError:
            warnings.append(f'{reply["file"]}: 답을 JSON으로 읽지 못함')
            continue
        warnings += [str(w) for w in data.get('warnings', [])]
        for c in data.get('candidates', []):
            if not isinstance(c, dict) or c.get('kind') not in ('step', 'precondition', 'prohibition', 'completion', 'unit_value'):
                warnings.append(f'{reply["file"]}: 종류를 알 수 없는 후보 {str(c)[:60]}')
                continue
            quote = str(c.get('quote') or '')
            item = {'id': f'{row["문서 식별자"]}-M{len(cands) + len(unlocated) + 1:03d}', 'section': c.get('section') or '머리말', 'procedure': c.get('procedure'),
                    'kind': c['kind'], 'text': c.get('text') or quote}
            exact = [n for n, l in enumerate(doc.lines, 1) if quote and quote.split('\n')[0] in l]
            found = None
            if quote and text.count(quote) == 1 and exact:
                found = (exact[0], exact[0] + quote.count('\n'), 'exact')
            elif quote and X.squash(text).count(X.squash(quote)) == 1:
                target = X.squash(quote)
                for a in range(1, len(doc.lines) + 1):
                    for b in range(a, min(a + 6, len(doc.lines)) + 1):
                        if target in X.squash('\n'.join(doc.lines[a - 1:b])):
                            found = (a, b, 'normalized')
                            break
                    if found:
                        break
            if not found:
                unlocated.append(item | {'quote': quote, 'note': '원문 한 곳에서 찾지 못함(없거나 여러 곳)', 'status': 'pending'})
                continue
            item |= {'quote': quote, 'quote_match': found[2], 'line_start': found[0], 'line_end': found[1]}
            if '스캔본' in row['상태']:
                item['page'] = doc.page.get(found[1])
            if bilingual:
                item['lang'] = 'en' if re.match(r'^\s*(?:\d+\.\s*)?EN:', doc.lines[found[0] - 1]) else 'ko'
            item['refs'] = [str(r) for r in c.get('refs') or []]
            item['status'] = 'pending'
            for k in ('order', 'value', 'value_max', 'unit', 'comparator', 'value_text'):
                if c.get(k) is not None:
                    item[k] = c[k]
            cands.append(item)
    return cands, unlocated, warnings, runs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('lab')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)
    lab = Path(a.lab).resolve()
    if str(lab).startswith(str(HERE.parents[4])):
        raise SystemExit('저장소 안 랩 폴더에서는 돌리지 않습니다 — 저장소 밖 사본에서 돌립니다(응답 기록 · .env가 저장소에 들어가지 않게).')
    prompt = (HERE/'강사_요청글.md').read_text(encoding='utf-8')
    total = 0
    client = None
    if not a.dry_run:
        spec = importlib.util.spec_from_file_location('llm_client', lab/'llm_client.py')
        client = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(client)
    (lab/'결과/후보').mkdir(parents=True, exist_ok=True)
    for row in X.read_register(lab):
        if row['파일'] not in BR.TARGETS:
            continue
        raw = (lab/'자료'/row['파일']).read_bytes()
        text, enc = X.decode(raw)
        parts = chunks(text)
        total += len(parts)
        print(f'{row["파일"]}: 조각 {len(parts)}개, 글자 {sum(len(t) for _, t in parts)}')
        if a.dry_run:
            continue
        replies = []
        for first, body in parts:
            msgs = [{'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': f'문서 {row["문서 식별자"]} 판 {row["판"]} 상태 {row["상태"]} — 원문 {first}줄부터:\n\n{body}'}]
            replies.append(client.ask(msgs))
        cands, unlocated, warnings, runs = to_candidates(row, text, replies)
        out = {'doc_id': row['문서 식별자'], 'rev': row['판'], 'doc_status': row['상태'], 'source_file': row['파일'], 'source_sha256': X.hashlib.sha256(raw).hexdigest(),
               'encoding': enc, 'extractor': 'instructor_extract.py(강사 요청 글, 절 머리 조각)', 'generated_at': client.datetime.now().astimezone().isoformat(timespec='seconds'),
               'model_run': runs, 'candidates': cands, 'unlocated': unlocated, 'warnings': warnings}
        (lab/'결과/후보'/f'{X.file_stem(row)}.json').write_text(X.dump(out), encoding='utf-8')
        print(f'  후보 {len(cands)}개 · 찾지 못한 인용 {len(unlocated)}개')
    print(f'조각 합계 {total}개(폴더 상한 60번)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
