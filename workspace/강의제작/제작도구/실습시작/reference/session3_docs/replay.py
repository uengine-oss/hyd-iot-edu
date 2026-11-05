"""강사 참조 — 문서 지식 네 랩의 「정답 보기」 재생(DoD 11)과 갈래 실행의 공용 부품. 학생 폴더 · ZIP에 넣지 않는다.

새 사본(저장소 밖 임시 폴더)에 랩 폴더를 풀고, 가이드의 정답 토글 apply(= fills.py의 판)를 단계마다 차례로 써 넣으며 `python show_result.py --no-open`을 돌려
그 단계가 「채움」 · 「볼 것 없음」으로 끝나는지(오류 · 비어 있음 · 아직이 아닌지) 본다. 모델은 부르지 않는다 — 추출 랩은 강사 추출 실행 run1의 응답 기록과 폴더 표지를 사본에 넣고
(.env의 모델 이름 coding, 키 없음), 같은 요청을 다시 보낸 답은 run2의 같은 요청 해시 기록을 둘째 기록으로 넣어 결과/시험_조각.json을 제공 코드의 꼴로 미리 쓴다(다시 보내는 길은 리허설에서 본다).
그래프 랩은 사본에서 lab_db.py --no-open으로(브라우저를 띄우지 않음) 그 사본 전용 랩 DB를 켜고 끝나면 지운다.
"""
from __future__ import annotations

from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
RUN1, RUN2 = HERE/'강사_추출/run1/결과', HERE/'강사_추출/run2/결과'
PY = sys.executable


def run(folder, *args, check=False, timeout=900):
    env = dict(os.environ, PYTHONUTF8='1')
    r = subprocess.run([PY, *args], cwd=folder, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=timeout)
    if check and r.returncode:
        raise RuntimeError(f'{folder.name}: {" ".join(args)} 실패(rc {r.returncode})\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    return r


def states(out):
    """show_result 출력의 단계 줄 — {번호: 상태}."""
    return {int(m.group(1)): m.group(3) for m in re.finditer(r'^(\d\d) (.+?): (\S.*)$', out, re.M)}


def copy_lab(src, dst):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__'))
    return dst


def seed_extract(folder):
    """run1의 응답 기록 · 폴더 표지와 모델 이름(.env) — 같은 판의 정할 자리면 제공 코드가 다시 보내지 않고 이 기록을 쓴다."""
    shutil.copytree(RUN1/'응답_기록', folder/'결과/응답_기록', dirs_exist_ok=True)
    shutil.copy2(RUN1/'폴더_표지.txt', folder/'결과/폴더_표지.txt')
    (folder/'.env').write_text('OPENAI_BASE_URL=\nLLM_API_KEY=\nLLM_MODEL=coding\n', encoding='utf-8', newline='\n')


def seed_trial(folder):
    """같은 요청을 한 번 더 보낸 답 — run2의 같은 요청 해시 기록을 둘째 기록으로 두고, 제공 코드의 꼴로 결과/시험_조각.json을 쓴다(다른 폴더에서 받은 답이라 표지가 다르다고 적는다)."""
    sys.path.insert(0, str(folder))
    import importlib
    X = importlib.import_module('doc_extract')
    importlib.reload(X)
    cfg, prompt = X.settings(), X.prompt_text()
    name, line = cfg['시험_조각'].rsplit(':', 1)
    row, text, enc, raw = X.by_file()[name]
    first, body = next((f, b) for f, b in X.split_chunks(text, cfg['단위'], cfg['글자_상한']) if X.chunk_range(f, b)[0] <= int(line) <= X.chunk_range(f, b)[1])
    import llm_client as L
    importlib.reload(L)
    digest = L.request_hash(L.body_of(L.as_messages(X.build_request(prompt, row, first, body)), 'coding'))
    second = folder/'결과/응답_기록'/f'{digest}-2.json'
    shutil.copy2(RUN2/'응답_기록'/f'{digest}.json', second)
    answers = []
    for p in (folder/'결과/응답_기록'/f'{digest}.json', second):
        rec = dict(json.loads(p.read_text(encoding='utf-8')), file=p.relative_to(folder).as_posix())
        cands, unl, warns, _ = X.to_candidates(row, text, [rec])
        answers.append({'record': rec['file'], 'finish_reason': rec.get('finish_reason'), 'candidates': cands, 'unlocated': unl, 'warnings': warns})
    mark = X.stamp(cfg, prompt) + f' · 시험 조각 {name} {X.chunk_range(first, body)[0]}~{X.chunk_range(first, body)[1]}줄'
    out = {'stamp': mark, 'source_file': name, 'chunk': list(X.chunk_range(first, body)), 'request_hash': digest, 'answers': answers,
           'note': '다시 보낸 답은 같은 요청을 다른 폴더(강사 실행 둘째 판)에서 보낸 기록이다'}
    (folder/'결과/시험_조각.json').write_text(X.dump(out), encoding='utf-8', newline='\n')
    sys.path.remove(str(folder))
    for m in ('doc_extract', 'llm_client'):
        sys.modules.pop(m, None)
    return digest


def steps_of(key):
    import build_document_labs as BD
    if key in BD.LABS:
        return BD.lab(key, None)['steps']
    return BD.glab(key)['steps']


def apply(folder, answer):
    for rel, text in (answer or {}).get('apply', {}).items():
        p = folder/rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8', newline='\n')


def replay(key, work, keep_db=False, snaps=None):
    """정답 토글을 단계마다 차례로 적용해 show_result를 돌린다. 돌려주는 값: [(단계 번호, 이름, 상태)], 사본 폴더.
    snaps에 목록을 주면 단계마다 그 실행이 쓴 개수 스냅숏(결과/.보기_이전.json)을 차례로 담는다(학생용 완성본의 기록 칸)."""
    import build_document_labs as BD
    graph = key in BD.GLABS
    src = (BD.GLABS if graph else BD.LABS)[key]
    folder = copy_lab(src, work/src.name)
    steps = steps_of(key)
    out = []
    if graph:
        run(folder, 'lab_db.py', '--no-open', check=True)
    else:
        seed_extract(folder)
    try:
        for i, s in enumerate(steps, 1):
            apply(folder, s.get('answer'))
            if not graph and s.get('answer') and '결과/prompt.md' in s['answer'].get('apply', {}):
                seed_trial(folder)
            r = run(folder, 'show_result.py', '--no-open')
            st = states(r.stdout)
            if snaps is not None:
                snaps.append(json.loads((folder/'결과/.보기_이전.json').read_text(encoding='utf-8')))
            out.append((i, s['name'], st.get(i, '(줄 없음)'), r.stdout if st.get(i) not in ('채움', '볼 것 없음', '결과 보기') else ''))
    finally:
        if graph and not keep_db:
            drop_db(folder)
    return out, folder


def drop_db(folder):
    state = folder/'랩_연결.json'
    if state.is_file():
        name = json.loads(state.read_text(encoding='utf-8'))['container']
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True)


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('keys', nargs='*')
    a = p.parse_args(argv)
    sys.path[:0] = [str(HERE), str(TOOLS)]
    import build_document_labs as BD
    keys = a.keys or sorted(BD.LABS) + sorted(BD.GLABS)
    bad = 0
    with tempfile.TemporaryDirectory(prefix='doc_replay_') as tmp:
        for key in keys:
            res, _ = replay(key, Path(tmp))
            for i, name, state, log in res:
                ok = state in ('채움', '볼 것 없음', '결과 보기')
                bad += not ok
                print(f'{key} {i:02d} {name}: {state}' + ('' if ok else '  ← 불일치\n' + log[-2500:]))
    print('정답 재생 불일치 0' if not bad else f'정답 재생 불일치 {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
