"""강사 참조 — 강사 추출 실행(수업 모델 호출). 저장소 밖 임시 사본 폴더에서 돌린다.

통합 04-2 랩 폴더의 사본에 학생이 만들 추출 코드(completed/extract_candidates.py — 학생용 완성본에 그대로 들어가는 그 코드)와
요청 글(강사_요청글.md — main manual_extraction INSTRUCTION 요지를 랩 계약 꼴로 옮긴 것, 완성본의 결과/prompt.md)을 결과/에 넣고,
사본 폴더에서 `python 결과/extract_candidates.py`를 실행한다. 모델은 그 폴더의 llm_client.py(학생과 같은 연결 도구 · 같은 상한 · 같은 응답 기록)로 부른다.
결과는 사본 폴더의 결과/후보/ · 결과/응답_기록/ · 결과/폴더_표지.txt. 고정하려면 --keep <이름>으로 강사_추출/<이름>/에 옮긴다(키 · 주소는 기록에 없다 — 옮기기 전에 센다).

사용(저장소 밖):
  cp -r <저장소>/workspace/강의제작/산출물/통합반/실습/04회차/랩/04일차_실습2_문서지식추출 <임시>/run1
  python instructor_extract.py <임시>/run1 --dry-run                (모델을 부르지 않고 조각 수만 — 회당 조각 수 = 보낼 요청 수)
  (<임시>/run1/.env 에 발급 도구가 준 세 줄을 붙여 넣는다 — 키 값은 어디에도 옮기지 않는다)
  python <임시>/run1/llm_client.py                                   (연결 확인 한 번)
  python instructor_extract.py <임시>/run1 [--keep run1]
  같은 일을 <임시>/run2 사본에서 한 번 더(같은 요청의 두 번째 응답 — 두 실행의 차이를 본다)
  python run_reference.py              (강사_추출/run1 · run2가 있으면 두 실행의 점수 · 차이 · 갈래 판정을 함께 본다)
  python completed.py                  (강사_추출/run1로 추출 완성본을 만든다)
"""
from __future__ import annotations

from pathlib import Path
import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CODE = HERE/'completed/extract_candidates.py'
PROMPT = HERE/'강사_요청글.md'
KEPT = HERE/'강사_추출'


def student_code():
    """학생 추출 코드 모듈 — 조각 나누기 · 답 → 후보 변환을 강사 참조에서도 같은 함수로 쓴다(한 곳)."""
    spec = importlib.util.spec_from_file_location('extract_candidates', CODE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def compare_runs(lab, run1, run2):
    """같은 요청을 두 폴더에서 보낸 두 실행의 차이 — 요청 해시가 같은 응답 기록끼리 답 글 · 후보 인용을 견준다(연결 확인 요청은 뺀다).
    task = 핀 세척 절(HM-8 1.1 HM-8.7)이 든 조각, all = 조각 전부의 합, chunks_first = 첫 실행의 조각 기록 수."""
    S = student_code()
    rows = {(r['문서 식별자'], r['판']): r for r in S.register(lab) if r['파일']}
    def recs(run):
        out = {}
        for p in sorted((Path(run)/'결과/응답_기록').glob('*.json')):
            d = json.loads(p.read_text(encoding='utf-8'))
            user = d['request']['messages'][-1]['content'] if isinstance(d.get('request'), dict) and d['request'].get('messages') else ''
            m = re.match(r'문서 (\S+) 판 (\S*) 상태 .*? — 원문 (\d+)줄부터:\n\n', user)
            if m and d.get('usable') is not False:
                out[d['request_hash']] = (d | {'file': f'결과/응답_기록/{p.name}'}, m.group(1), m.group(2), int(m.group(3)), user[m.end():])
        return out
    one, two = recs(run1), recs(run2)
    total = {'chunks': 0, 'same_text': 0, 'n1': 0, 'n2': 0, 'both': 0, 'only1': 0, 'only2': 0}
    task = None
    for h in sorted(set(one) & set(two)):
        (r1, doc, rev, first, body), (r2, *_ ) = one[h], two[h]
        row = rows[(doc, rev)]
        text, _, _ = S.read_document(lab, row)
        c1, c2 = (S.to_candidates(row, text, [r])[0] for r in (r1, r2))
        q1, q2 = {S.squash(c['quote']) for c in c1}, {S.squash(c['quote']) for c in c2}
        got = {'chunks': 1, 'same_text': int(r1['response_text'] == r2['response_text']), 'n1': len(c1), 'n2': len(c2),
               'both': len(q1 & q2), 'only1': len(q1 - q2), 'only2': len(q2 - q1)}
        total = {k: total[k] + got[k] for k in total}
        if row['파일'] == 'HM-8_매뉴얼.md' and '## HM-8.7' in body:
            task = got | {'hash': h, 'lines': f'{first}~{first + body.count(chr(10))}줄'}
    return {'task': task, 'all': total, 'chunks_first': len(one)}


def secrets_in(folder, paths):
    """사본 .env의 접속 주소 · 키가 파일들에 몇 번 나오는지(값은 찍지 않는다)."""
    env = {}
    for line in (folder/'.env').read_text(encoding='utf-8-sig').splitlines() if (folder/'.env').is_file() else []:
        if '=' in line and not line.lstrip().startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"\'')
    needles = [v for k, v in env.items() if k in ('OPENAI_BASE_URL', 'LLM_API_KEY') and len(v) >= 8]
    needles += [v.split('://', 1)[-1].split('/', 1)[0] for k, v in env.items() if k == 'OPENAI_BASE_URL' and '://' in v]
    return sum(p.read_text(encoding='utf-8', errors='replace').count(n) for p in paths for n in needles if n)


def keep(folder, name):
    """사본의 결과(후보 · 응답 기록 · 폴더 표지 · 요청 글 · 코드)를 강사_추출/<name>/결과/로 옮긴다 — 키 · 주소가 섞였으면 멈춘다."""
    files = sorted(p for p in (folder/'결과').rglob('*') if p.is_file() and '__pycache__' not in p.parts
                   and (p.parts[-2] in ('후보', '응답_기록') or p.name in ('폴더_표지.txt', 'prompt.md', 'extract_candidates.py')))
    hits = secrets_in(folder, files)
    if hits:
        raise SystemExit(f'옮길 파일에 접속 주소 · 키가 {hits}번 나옵니다 — 옮기지 않습니다.')
    dest = KEPT/name
    if dest.exists():
        shutil.rmtree(dest)
    for p in files:
        target = dest/p.relative_to(folder)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(p.read_bytes())
    print(f'강사_추출/{name}/에 파일 {len(files)}개를 옮겼습니다(접속 주소 · 키 0번).')


def usage_of(folder):
    recs = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((folder/'결과/응답_기록').glob('*.json'))]
    sent = [r for r in recs if r.get('method') == '모델 서버']
    tok = {k: sum((r.get('usage') or {}).get(k) or 0 for r in sent) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
    return len(sent), tok


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('lab')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--keep', metavar='이름', help='끝난 뒤 결과를 강사_추출/<이름>/으로 옮긴다')
    a = ap.parse_args(argv)
    lab = Path(a.lab).resolve()
    if str(lab).startswith(str(HERE.parents[4])):
        raise SystemExit('저장소 안 랩 폴더에서는 돌리지 않습니다 — 저장소 밖 사본에서 돌립니다(응답 기록 · .env가 저장소에 들어가지 않게).')
    (lab/'결과').mkdir(exist_ok=True)
    shutil.copyfile(CODE, lab/'결과/extract_candidates.py')
    shutil.copyfile(PROMPT, lab/'결과/prompt.md')
    r = subprocess.run([sys.executable, '결과/extract_candidates.py'] + (['--list'] if a.dry_run else []), cwd=lab)
    if (lab/'결과/응답_기록').is_dir():
        n, tok = usage_of(lab)
        print(f'이 폴더에서 모델 서버로 보낸 요청 {n}번 · 토큰 {tok}')
    if r.returncode == 0 and a.keep and not a.dry_run:
        keep(lab, a.keep)
    return r.returncode


if __name__ == '__main__':
    sys.exit(main())
