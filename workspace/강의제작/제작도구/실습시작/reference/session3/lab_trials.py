"""통합반 3회차 두 랩(v7-lab)의 강사 참조 시험 — project_trials.py가 부른다. 학생 ZIP에 넣지 않는다.

1. 제공 설비 모델이 통합 2회차 그래프 랩 제공 모델과 같은 바이트인가(생성기 함수의 값, 그리고 지금 산출물), 자료가 data_session3_lab.build()와 같은가, 뺀 자료가 없는가.
2. 조치 기준 갈래(적용 범위 셋): 학생 경로(app/features 채움 → python run.py <기능>)로 돌린 판정이 손으로 정한 기대 판정과 같은가, HYD-04 사례의 답이 갈래마다 다른가.
3. 판단 기능 갈래(1순위로 내줄 기준 둘): 판정과 걸린 규칙이 기대와 같은가, 허용 후보가 경고가 붙어도 모두 견줘지는가, 비교값이 두 번째 구현과 같은가,
   1순위가 갈리는 경보가 lab_answers.TOPS와 같은가, 사례 다섯 종류마다 경보가 있는가, 기준값을 틀리게 바꾼 결정표가 사례 대조에서 「다름」으로 잡히는가.
4. 결정 줄이 빈 채로는 그 결정을 쓰는 기능이 그 줄을 짚고 멈추는가. 5. 랩 사슬(조치 기준 갈래의 output → 판단 기능의 내 조치 기준).
6. 검사기 고의 손상(ID 중복 · 끝점 없음 · 관계 방향 등). 7. 완성본을 새 폴더에 풀어 다시 실행. 8. 학생 폴더 경계 · 옛 낱말 · 가이드 · 사람 분.
"""
from pathlib import Path
import copy
import csv
import hashlib
import html
import io
import json
import re
import shutil
import subprocess
import sys
import zipfile

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path[:0] = [str(HERE), str(TOOLS)]
import build_session3_lab as L  # noqa: E402
import data_session3_lab as D  # noqa: E402
import lab_answers as A  # noqa: E402

F = L.F
GONE = ['hm8_manual_v1_0.md', 'hi01_supplement.md', 'work_standard.md', 'work_orders.csv', 'plc_status.csv', 'fan_counter.csv', 'forecasts.csv', 'orders.csv', 'collection_notes.md']
OLD_WORDS = ['작업지시', '정비 오더', 'CMMS 오더', '거절', '헌법', '조건표', '성과 지표 점수', '보류', '네 지표']
LEAK_WORDS = ['reference', '제작용', '강사', '정답', '해결 로직']


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode('utf-8')).hexdigest()


def table_rows(text):
    """머리의 # 줄을 건너뛰고 읽은 CSV 줄들."""
    return list(csv.DictReader(io.StringIO(''.join(x for x in text.splitlines(keepends=True) if not x.startswith('#')))))


def run(folder, *args):
    p = subprocess.run([sys.executable, '-B', *args], cwd=folder, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       env={'PYTHONUTF8': '1', 'PATH': '/usr/bin:/bin', 'SYSTEMROOT': 'C:\\Windows'})
    return p.returncode, (p.stdout + p.stderr).strip()


class Trials:
    def __init__(self, dest, tmp, fail, report):
        self.dest, self.tmp, self.fail, self.report = Path(dest), Path(tmp), fail, report
        self.data = D.build()
        self.folder = {k: self.dest / L.PROJECT[k] for k in L.PROJECT}

    def fresh(self, kind, name):
        dst = self.tmp / 'lab' / name / L.PROJECT[kind]
        shutil.copytree(self.folder[kind], dst, ignore=shutil.ignore_patterns('output', '__pycache__'))
        return dst

    def feature(self, folder, cmd, ok=True):
        code, out = run(folder, 'run.py', cmd, '--no-open')
        if ok and code:
            self.fail(f'{folder.name}: python run.py {cmd} exit {code}\n{out[:1500]}')
        return code, out, json.loads((folder / 'output/result.json').read_text(encoding='utf-8'))['blocks']

    def rows(self, blocks, title):
        b = next((b for b in blocks if (b.get('title') or '').startswith(title)), None)
        if b is None:
            self.fail(f'결과 화면에 「{title}」 표가 없음')
            return []
        return b['rows']

    # ───────────── 1. 모델 · 자료 ─────────────
    def inputs(self):
        rec = {'설비 모델': {}, '자료': {}, '뺀 자료가 남았는가': {}}
        made = L.model_files()
        graph_lab = F.OUT / '통합반/실습/02회차/랩/graph-lab/data/model'
        for name, text in ((n, made[n]) for n in ('schema.json', 'graph.json')):
            mine = (self.folder['criteria'] / 'data/model' / name).read_bytes()
            same_fn, same_out = mine == text.encode('utf-8'), (graph_lab / name).is_file() and (graph_lab / name).read_bytes() == mine
            rec['설비 모델'][name] = {'sha256': sha(mine)[:16], '생성기 함수(reference_model · GRAPH_LAB_INPUT 통합반)와 같은 바이트': same_fn, '산출물 graph-lab 제공 모델과 같은 바이트': same_out}
            if not same_fn or not same_out:
                self.fail(f'action-criteria-lab: data/model/{name}이 통합 2회차 그래프 랩 제공 모델과 다름(함수 {same_fn} · 산출물 {same_out})')
        graph = json.loads(made['graph.json'])
        rec['설비 모델']['설비'] = sorted(n['props']['id'] for n in graph['nodes'] if 'Asset' in n['labels'])
        if rec['설비 모델']['설비'] != ['HYD-01', 'HYD-02', 'HYD-03', 'HYD-04', 'HYD-07']:
            self.fail(f'제공 설비 모델이 v31의 다섯 대가 아님: {rec["설비 모델"]["설비"]}')
        fan04 = [n['props']['name'] for n in graph['nodes'] if n['props']['id'].startswith('HYD-04:') and 'Component' in n['labels']]
        rec['설비 모델']['HYD-04 구성 요소'] = fan04
        if '쿨러 팬' in fan04:
            self.fail('HYD-04에 쿨러 팬이 있음 — 적용 범위 갈래가 갈리지 않는다')
        places = {'criteria': ['hm8_manual.md', 'decision_table_export.txt', 'targets.csv', 'failure_modes.csv', 'check_cases.csv'],
                  'judge': list(L.JUDGE_DATA)}
        for kind, names in places.items():
            for name in names:
                p = self.folder[kind] / 'data' / name
                same = p.is_file() and p.read_text(encoding='utf-8') == self.data[name]
                rec['자료'][f'{L.PROJECT[kind]}/data/{name}'] = {'줄': len(self.data[name].splitlines()), '바이트': len(self.data[name].encode('utf-8')), '자료 모듈과 같음': same}
                if not same:
                    self.fail(f'{L.PROJECT[kind]}: data/{name}이 data_session3_lab.build()와 다름')
            every = sorted(p.relative_to(self.folder[kind]).as_posix() for p in (self.folder[kind] / 'data').rglob('*') if p.is_file())
            rec['자료'][f'{L.PROJECT[kind]} data/ 전체'] = {'파일': len(every), '줄': sum(len(p.read_text(encoding='utf-8-sig').splitlines()) for p in (self.folder[kind] / 'data').rglob('*') if p.is_file()), '목록': every}
            left = [g for g in GONE if any(Path(e).name == g for e in every)]
            rec['뺀 자료가 남았는가'][L.PROJECT[kind]] = left
            if left:
                self.fail(f'{L.PROJECT[kind]}: 구성안이 뺀 자료가 남음 {left}')
        alarms = table_rows(self.data['alarms.csv'])
        rec['경보'] = {'수': len(alarms), '설비마다': {a: sum(r['설비'] == a for r in alarms) for a in sorted({r['설비'] for r in alarms})},
                     '값이 빈 칸이 있는 경보': [r['경보_ID'] for r in alarms if '' in r.values()]}
        self.report['통합_입력'] = rec

    # ───────────── 2. 조치 기준 갈래 ─────────────
    def criteria(self):
        rec, answers, done = {}, {}, {}
        for scope, s in A.SCOPES.items():
            f = self.fresh('criteria', f'criteria_{scope}')
            L.fill('criteria', f, self.data, scope)
            for cmd in ('sop', 'relations', 'scope'):
                self.feature(f, cmd)
            _, _, blocks = self.feature(f, 'rules')
            got = {r[0]: r[2] for r in self.rows(blocks, '확인 사례 · 후보마다 판정')}
            want = {f'{alarm} / {sop}': v[0] for alarm, verdicts in {**A.EXPECTED_CRITERIA, A.HYD04_CASE: s['hyd04']}.items() for sop, v in verdicts.items()}
            wrong = {k: (v, got.get(k)) for k, v in want.items() if (got.get(k) or '').split(' — ')[0] != v}
            if wrong:
                self.fail(f'조치 기준 갈래 {scope}: 판정이 손으로 정한 기대와 다름 {list(wrong.items())[:4]}')
            cmp_ = next(b for b in blocks if b['kind'] == 'compare')
            states = sorted({r['state'] for r in cmp_['rows']})
            if states != ['같음']:
                self.fail(f'조치 기준 갈래 {scope}: 결과 화면의 기대 ↔ 판정 대조에 같음이 아닌 줄 {states}')
            code, out = run(f, '-m', 'app.utils.check')
            if code or '구조 검사 통과' not in out:
                self.fail(f'조치 기준 갈래 {scope}: 검사기 exit {code}\n{out[:1200]}')
            doc = json.loads((f / 'output/sop.json').read_text(encoding='utf-8'))
            answers[scope] = {k.split(' / ')[1]: v for k, v in got.items() if k.startswith(A.HYD04_CASE)}
            others = {k: v for k, v in got.items() if not k.startswith(A.HYD04_CASE)}
            rec[scope] = {'고른 것': s['chosen'], 'SOP마다 건 설비': {x['id']: x['assets'] for x in doc['sops']}, 'HYD-04 사례의 후보마다 판정': answers[scope],
                          '그 답을 받은 야간 운전원의 다음 행동': s['next'], '기대 판정과 다른 줄': len(wrong), '대조한 줄': len(cmp_['rows']), '검사기': f'exit {code}',
                          'HYD-04 밖 사례의 판정 sha256': sha(json.dumps(others, ensure_ascii=False, sort_keys=True))[:16]}
            done[scope] = f
        names = list(answers)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if answers[a] == answers[b]:
                    self.fail(f'조치 기준: 적용 범위 갈래 {a} · {b}에서 HYD-04 사례의 답이 같음 — 정할 지점이 답을 가르지 않는다')
        if len({r['HYD-04 밖 사례의 판정 sha256'] for r in rec.values()}) != 1:
            self.fail('조치 기준: 적용 범위와 상관없는 설비(HYD-01~03) 사례의 판정이 갈래마다 다름')
        f = self.fresh('criteria', 'criteria_blank_decision')
        L.fill('criteria', f, self.data)
        (f / 'app/features/decisions.csv').write_text(L.TEMPLATES['criteria']['decisions.csv'], encoding='utf-8', newline='\n')
        code, out, _ = self.feature(f, 'scope', ok=False)
        stopped = code != 0 and 'app/features/decisions.csv:4' in out
        rec['결정 줄이 빈 채로 python run.py scope'] = {'exit': code, '그 줄을 짚고 멈춤': stopped, '출력': out[:300]}
        f = self.fresh('criteria', 'criteria_wrong_threshold')
        L.fill('criteria', f, self.data)
        path = f / 'app/features/decision_table.csv'
        path.write_text(A.wrong_table(path.read_text(encoding='utf-8')), encoding='utf-8', newline='\n')
        _, _, blocks = self.feature(f, 'rules')
        off = [r['key'] for b in blocks if b['kind'] == 'compare' for r in b['rows'] if r['state'] != '같음']
        rec['기준값을 틀리게 바꾼 결정표(R3 > 55 · R2 >= 25 · R4 냉각 효율 < 35)'] = {'대조에서 다름으로 나온 줄': off}
        if not any('0205' in k for k in off) or not any('0171' in k for k in off):
            self.fail(f'조치 기준: 기준값을 틀리게 바꿨는데 경계 · 복수 조건 사례가 다름으로 잡히지 않음 {off}')
        if not stopped:
            self.fail(f'조치 기준: 적용 범위 줄이 비었는데 scope가 그 줄을 짚고 멈추지 않음\n{out[:600]}')
        for kind, bad in (('criteria', 'data/hm8_manual.md:31.2'), ('judge', 'data/alarms.csv:999')):      # 근거 칸의 꼴 — 문장 번호를 섞거나 없는 줄을 대면 그 줄을 짚고 멈춘다
            f = self.fresh(kind, f'{kind}_bad_evidence')
            L.fill(kind, f, self.data)
            path = f / 'app/features/expected.csv'
            lines = path.read_text(encoding='utf-8').splitlines()
            no = next(n for n, x in enumerate(lines) if x.startswith(('ALT-', '정상,')))
            lines[no] = lines[no].rsplit(',', 1)[0] + ',' + bad
            path.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
            code, out, _ = self.feature(f, 'expected', ok=False)
            stopped = code != 0 and f'app/features/expected.csv:{no + 1}' in out
            rec[f'{L.PROJECT[kind]}: 근거 칸에 「{bad}」'] = {'exit': code, '그 줄을 짚고 멈춤': stopped}
            if not stopped:
                self.fail(f'{L.PROJECT[kind]}: 근거 칸의 꼴이 어긋났는데 expected가 그 줄을 짚고 멈추지 않음\n{out[:500]}')
        f = self.fresh('criteria', 'criteria_fan_rule_one_sop')      # 감점 규칙을 글자대로 「팬 최대 운전」 하나에만 댄 읽기 — 참조(팬을 올리는 두 SOP)와 어디서 갈리는지 남긴다
        L.fill('criteria', f, self.data)
        path = f / 'app/features/decision_table.csv'
        text = path.read_text(encoding='utf-8')
        if text.count(',' + A.FAN_UP + ',') != 1:
            self.fail('조치 기준: 감점 규칙의 적용 대상 줄을 찾지 못함')
        path.write_text(text.replace(',' + A.FAN_UP + ',', ',SOP-COOL-11,'), encoding='utf-8', newline='\n')
        _, _, blocks = self.feature(f, 'rules')
        off = [r['key'] for b in blocks if b['kind'] == 'compare' for r in b['rows'] if r['state'] != '같음']
        rec['감점 규칙을 SOP-COOL-11에만 댄 읽기'] = {'참조의 기대와 다름으로 나온 줄': off}
        if not off:
            self.fail('조치 기준: 감점 규칙의 적용 대상을 좁혀도 확인 사례가 가리지 못함')
        self.report['조치_기준_갈래'] = rec
        return done

    # ───────────── 3. 판단 기능 갈래 ─────────────
    def second_total(self, row, sop, penalty):
        """비교 산식의 두 번째 구현(제공 코드 app/utils/compare.py와 따로 쓴 것) — 값이 없으면 None."""
        v = {x['이름']: x['값'] for x in json.loads(self.data['metrics/business_values.json'])['값']}
        fan, load, stop, job, root = {'SOP-COOL-11': (100, 90, 0, 0, False), 'SOP-COOL-12': (100, 80, 0, 0, False), 'SOP-COOL-13': (60, 70, 3, 40, True), 'SOP-COOL-14': (60, 90, 3, 40, True)}[sop]
        if '' in (row[f'예측_유온_{sop}_C'], row['납기까지_남은_시간_h'], row['오더_잔량_ea'], row['고온_로트_수량_ea']):
            return None
        p, remain, hot, f = float(row['납기까지_남은_시간_h']), float(row['오더_잔량_ea']), float(row['고온_로트_수량_ea']), float(row[f'예측_유온_{sop}_C'])
        ratio = load / 90
        parts = [job + (0 if root else v['계획_외_고장_비용'] * min(p / v['평균_고장_간격'], 1)),
                 v['시간당_생산_가치'] * (p * (1 - ratio) + stop) + v['납기_지연_위약금'] * max(stop + remain / (v['시간당_생산_수량'] * ratio) - p, 0),
                 v['고온_로트_불량_확률'] * v['고온_로트_클레임_금액'] if f >= 55 and hot > 0 else 0,
                 (fan - 60) * v['팬_최대_추가_전력'] / 40 * p * v['전력_단가']]
        return round(sum(round(x, 2) for x in parts) + penalty, 2)

    def judge(self):
        rec, tops, done = {}, {}, {}
        alarms = {r['경보_ID']: r for r in table_rows(self.data['alarms.csv'])}
        for branch, c in A.ORDERS.items():
            f = self.fresh('judge', f'judge_{branch}')
            L.fill('judge', f, self.data, branch)
            for cmd in ('judge', 'compare', 'write'):
                self.feature(f, cmd)
            _, _, blocks = self.feature(f, 'cases')
            cmp_ = next(b for b in blocks if b['kind'] == 'compare')
            states = sorted({r['state'] for r in cmp_['rows']})
            if states != ['같음']:
                self.fail(f'판단 기능 갈래 {branch}: 사례 대조에 같음이 아닌 줄 {states}')
            code, out = run(f, '-m', 'app.utils.check')
            if code or '구조 검사 통과' not in out:
                self.fail(f'판단 기능 갈래 {branch}: 검사기 exit {code}\n{out[:1200]}')
            doc = json.loads((f / 'output/judgement.json').read_text(encoding='utf-8'))
            bad = []
            for e in doc['events']:
                for cand in e['candidates']:
                    if cand['comparison']:
                        penalty = sum(h['penalty'] for h in cand['hits'] if h['result'] == '감점')
                        want = self.second_total(alarms[e['id']], cand['sop'], penalty)
                        if want is None or abs(want - cand['comparison']['비교값']) > 0.005:
                            bad.append((e['id'], cand['sop'], cand['comparison']['비교값'], want))
            if bad:
                self.fail(f'판단 기능 갈래 {branch}: 비교값이 두 번째 구현과 다름 {bad[:3]}')
            lost = [(e['id'], x['sop']) for e in doc['events'] for x in e['candidates'] if x['status'] == '허용' and x['comparison'] is None and x['not_compared'] is None]
            if lost:
                self.fail(f'판단 기능 갈래 {branch}: 허용인데 비교값도 견주지 못한 까닭도 없는 후보 {lost[:3]} — 경고가 붙어도 허용이면 비교에 남아야 한다(덱 32장)')
            tops[branch] = {e['id']: e['top'] for e in doc['events']}
            warned_top = [e['id'] for e in doc['events'] for cand in e['candidates'] if cand['sop'] in e['top'] and any(h['result'] == '경고' for h in cand['hits'])]
            rec[branch] = {'고른 것': c['chosen'], '경보 수': len(doc['events']), '1순위가 있는 경보': sum(1 for e in doc['events'] if e['top']), '경고가 붙은 후보가 1순위인 경보': warned_top,
                           '뒤로 미룬 후보 수': sum(1 for e in doc['events'] for x in e['candidates'] if x['held_back']),
                           '견준 후보 수': sum(1 for e in doc['events'] for x in e['candidates'] if x['comparison']), '비교값이 두 번째 구현과 다른 줄': len(bad),
                           '사례 대조 줄': len(cmp_['rows']), '검사기': f'exit {code}'}
            done[branch] = f
        a, b = list(A.ORDERS)
        split = {i: {a: tops[a][i], b: tops[b][i]} for i in tops[a] if tops[a][i] != tops[b][i]}
        want = {i: {k: [v] for k, v in t.items()} for i, t in A.TOPS.items()}
        if split != want:
            self.fail(f'판단 기능: 1순위가 갈리는 경보가 손으로 구한 것과 다름 — 실제 {split} / 기대 {want}')
        if not split:
            self.fail('판단 기능: 갈래에 따라 1순위가 달라지는 경보가 없음 — 정할 지점이 답을 가르지 않는다')
        still = [i for i in split if not float(alarms[i]['팬100_연속_h'] or 0) > 0]
        if still:
            self.fail(f'판단 기능: 1순위가 갈리는 경보 {still}는 팬이 100 %가 아닌데 강사 참조의 다음 행동은 「팬이 이미 100 %」를 전제한다')
        rec['갈래마다 1순위가 달라지는 경보'] = {i: {'팬100_연속_h': alarms[i]['팬100_연속_h'], **{k: {'1순위': v[0], '답을 받은 사람의 다음 행동': A.NEXT[v[0]]} for k, v in t.items()}} for i, t in split.items()}
        kinds = {}
        for kind, alarm, _ in A.EXPECTED_JUDGE:
            kinds.setdefault(kind, []).append(alarm)
            if alarm not in alarms:
                self.fail(f'판단 기능: 사례 종류 {kind}의 경보 {alarm}이 alarms.csv에 없음')
        rec['사례 다섯 종류마다 경보'] = kinds
        if sorted(kinds) != sorted(['정상', '경계', '복수 조건', '모두 제외', '필수값 누락']):
            self.fail(f'판단 기능: 사례 다섯 종류가 다 있지 않음 {sorted(kinds)}')
        for point, cmd in (('쓰는 사람에 따라 갈리는 답', 'compare'), ('비교 기준 문장', 'write')):
            f = self.fresh('judge', f'judge_blank_{cmd}')
            L.fill('judge', f, self.data)
            text = (f / 'app/features/decisions.csv').read_text(encoding='utf-8').splitlines()
            line = next(n for n, x in enumerate(text, 1) if x.startswith(point + ','))
            text[line - 1] = point + ',,,'
            (f / 'app/features/decisions.csv').write_text('\n'.join(text) + '\n', encoding='utf-8', newline='\n')
            code, out, blocks = self.feature(f, cmd, ok=False)
            stopped = code != 0 and f'app/features/decisions.csv:{line}' in out
            rec[f'「{point}」 줄이 빈 채로 python run.py {cmd}'] = {'exit': code, '그 줄을 짚고 멈춤': stopped}
            if cmd == 'compare':
                before = [b for b in blocks if b['kind'] == 'table' and b['title'].startswith('후보마다 비교값(만 원)과 비교값 순위')]
                rec[f'「{point}」 줄이 빈 채로 python run.py {cmd}']['결정 전에도 비교값 표가 보임'] = bool(before) and len(before[0]['rows'])
                if not before or any('내줄 차례' == c for c in before[0]['columns']):
                    self.fail('판단 기능: 결정 줄이 빈 채의 compare가 비교값 표를 보이지 않거나 내줄 차례를 미리 보임')
            if not stopped:
                self.fail(f'판단 기능: 「{point}」 줄이 비었는데 {cmd}가 그 줄을 짚고 멈추지 않음\n{out[:600]}')
        base = (done[A.BASE_ORDER] / 'app/features/decisions.csv').read_text(encoding='utf-8')
        statement = next(x for x in csv.reader(io.StringIO(base)) if x and x[0] == '비교 기준 문장')
        rec['「비교 기준 문장」 줄은 고른_것 · 근거만 채우고 write가 돈다'] = {'바뀌는_답 칸': statement[3], '통과': statement[3] == ''}
        if statement[3] != '':
            self.fail('판단 기능: 강사 참조의 비교 기준 문장 줄에 바뀌는_답이 채워져 있어 「두 칸만 채워도 돈다」를 확인하지 못함')
        f = self.fresh('judge', 'judge_wrong_threshold')
        L.fill('judge', f, self.data)
        (f / 'app/features/criteria').mkdir(parents=True)
        shutil.copyfile(f / 'data/criteria/sop.json', f / 'app/features/criteria/sop.json')
        (f / 'app/features/criteria/decision_table.csv').write_text(A.wrong_table((f / 'data/criteria/decision_table.csv').read_text(encoding='utf-8')), encoding='utf-8', newline='\n')
        _, _, blocks = self.feature(f, 'cases')
        off = [r['key'] for b in blocks if b['kind'] == 'compare' for r in b['rows'] if r['state'] != '같음']
        kinds_off = sorted({k for k, alarm, _ in A.EXPECTED_JUDGE if any(alarm in x for x in off)})
        rec['기준값을 틀리게 바꾼 결정표(R3 > 55 · R2 >= 25 · R4 냉각 효율 < 35)'] = {'사례 대조에서 다름으로 나온 줄': off, '다름이 나온 사례 종류': kinds_off}
        if '경계' not in kinds_off or '복수 조건' not in kinds_off:
            self.fail(f'판단 기능: 기준값을 틀리게 바꿨는데 경계 · 복수 조건 사례가 다름으로 잡히지 않음 {kinds_off}')
        f = self.fresh('judge', 'judge_unfilled')
        code, out, blocks = self.feature(f, 'judge')
        rec['빈 틀 그대로 python run.py judge(결정 없이 도는 일반 판정)'] = {'exit': code, '판정 줄': len(self.rows(blocks, '경보 · 후보마다 판정'))}
        self.report['판단_기능_갈래'] = rec
        return done

    # ───────────── 5. 랩 사슬 ─────────────
    def chain(self, criteria_done, judge_done):
        rec = {}
        base = json.loads((judge_done[A.BASE_ORDER] / 'output/judgement.json').read_text(encoding='utf-8'))
        for scope, src in criteria_done.items():
            f = self.fresh('judge', f'chain_{scope}')
            L.fill('judge', f, self.data)
            for name in ('sop.json', 'decision_table.csv'):
                (f / 'app/features/criteria').mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src / 'output' / name, f / 'app/features/criteria' / name)
            self.feature(f, 'write')
            code, out = run(f, '-m', 'app.utils.check')
            doc = json.loads((f / 'output/judgement.json').read_text(encoding='utf-8'))
            same_events = doc['events'] == base['events']
            hyd04 = {e['id']: [c['sop'] + ' ' + c['status'] for c in e['candidates']] for e in doc['events'] if e['asset'] == 'HYD-04'}
            given = self.folder['judge'] / 'data/criteria'
            same_bytes = (scope == A.BASE_SCOPE and (src / 'output/sop.json').read_bytes() == (given / 'sop.json').read_bytes()
                          and (src / 'output/decision_table.csv').read_text(encoding='utf-8').replace(f'# {L.MARK} — ', '# 제공 조치 기준의 결정표 — ', 1) == (given / 'decision_table.csv').read_text(encoding='utf-8'))
            rec[scope] = {'쓴 조치 기준': doc['criteria'], '검사기': f'exit {code}', '제공 기준으로 낸 판정과 같음': same_events, 'HYD-04 경보의 후보': hyd04,
                          '이 갈래의 output이 판단 기능 랩 제공 기준과 같은 바이트': same_bytes if scope == A.BASE_SCOPE else '해당 없음'}
            if code or doc['criteria'] != 'app/features/criteria':
                self.fail(f'랩 사슬 {scope}: 검사기 exit {code} 또는 내 조치 기준을 쓰지 않음\n{out[:800]}')
            if scope == A.BASE_SCOPE and not (same_events and same_bytes):
                self.fail('랩 사슬: 기본 갈래의 조치 기준 output이 판단 기능 랩의 제공 기준과 다름')
            if scope != A.BASE_SCOPE and same_events:
                self.fail(f'랩 사슬 {scope}: 적용 범위가 다른 조치 기준인데 판정이 제공 기준과 같음')
        self.report['통합_랩_사슬'] = rec

    # ───────────── 6. 검사기 고의 손상 ─────────────
    def damages(self, done):
        def edit(path, fn):
            d = json.loads(path.read_text(encoding='utf-8'))
            fn(d)
            path.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')

        def swap(d):
            r = next(r for r in d['relations'] if r['type'] == 'MITIGATED_BY')
            r['from'], r['to'] = r['to'], r['from']

        def ranked(d):
            e = next(e for e in d['events'] if sum(1 for c in e['candidates'] if c['rank']) >= 2)
            a, b = [c for c in e['candidates'] if c['rank'] in (1, 2)][:2]
            a['rank'], b['rank'] = b['rank'], a['rank']

        def total(d):
            c = next(c for e in d['events'] for c in e['candidates'] if c['comparison'])
            c['comparison']['비교값'] += 5

        trials = {
            'criteria': [('SOP ID 중복', lambda f: edit(f / 'output/sop.json', lambda d: d['sops'].append(copy.deepcopy(d['sops'][0]))), '번 있습니다'),
                         ('고장 유형 ID 중복', lambda f: edit(f / 'output/sop.json', lambda d: d['failure_modes'].append(copy.deepcopy(d['failure_modes'][0]))), '번 있습니다'),
                         ('관계 끝점 없음', lambda f: edit(f / 'output/sop.json', lambda d: d['relations'][0].update(to='SOP-NONE-00')), '목록에 없습니다'),
                         ('관계 방향 거꾸로', lambda f: edit(f / 'output/sop.json', swap), '방향이 거꾸로'),
                         ('모델에 없는 설비', lambda f: edit(f / 'output/sop.json', lambda d: d['sops'][0]['assets'].append('HYD-99')), '설비 모델에 없는 식별자'),
                         ('규칙과 조건 문장이 끊김', lambda f: edit(f / 'output/sop.json', lambda d: [i.update(rules=[]) for s in d['sops'] for i in s['items']]), '가리키는 조건 문장이 없습니다'),
                         ('제공 코드가 바뀜', lambda f: (f / 'app/utils/rules.py').write_text((f / 'app/utils/rules.py').read_text(encoding='utf-8') + '\n# x\n', encoding='utf-8'), '제공 파일이 바뀌었습니다')],
            'judge': [('경보 중복', lambda f: edit(f / 'output/judgement.json', lambda d: d['events'].append(copy.deepcopy(d['events'][0]))), '번 있습니다'),
                      ('없는 후보(끝점 없음)', lambda f: edit(f / 'output/judgement.json', lambda d: d['events'][0]['candidates'][0].update(sop='SOP-NONE-00')), '조치 기준의 SOP에 없습니다'),
                      ('없는 경보(끝점 없음)', lambda f: edit(f / 'output/judgement.json', lambda d: d['events'][0].update(id='ALT-none-0000')), 'data/alarms.csv에 없습니다'),
                      ('순위가 비교값 차례와 거꾸로', lambda f: edit(f / 'output/judgement.json', ranked), '비교값의 크기 차례'),
                      ('내줄 차례가 거꾸로', lambda f: edit(f / 'output/judgement.json', lambda d: next(e for e in d['events'] if len(e['order']) >= 2)['order'].reverse()), '내줄 차례가'),
                      ('비교값이 네 손실과 감점의 합과 다름', lambda f: edit(f / 'output/judgement.json', total), '합과 다릅니다')],
        }
        rec = {}
        for kind, items in trials.items():
            base, name = done[kind], L.PROJECT[kind]
            code, out = run(base, '-m', 'app.utils.check')
            rec[name] = {'손상 없음': f'exit {code}'}
            if code or '구조 검사 통과' not in out:
                self.fail(f'{name} 완성본: 손상 전 검사기 통과 아님\n{out[:1000]}')
            for label, damage, needle in items:
                f = self.tmp / 'lab_damage' / kind / re.sub(r'\W+', '_', label) / name
                shutil.copytree(base, f)
                damage(f)
                code, out = run(f, '-m', 'app.utils.check')
                caught = code != 0 and needle in out
                rec[name][label] = {'exit': code, '잡음': caught, '찾은 줄': next((x.strip() for x in out.splitlines() if needle in x), '')[:200]}
                if not caught:
                    self.fail(f'{name} 손상 「{label}」: 검사기가 잡지 않음(exit {code})\n{out[:800]}')
        self.report['통합_검사기_고의_손상'] = rec

    # ───────────── 7. 완성본 새 폴더 ─────────────
    def completed(self):
        rec, done = {}, {}
        for kind, name in L.PROJECT.items():
            archive = self.dest / (name + '-completed.zip')
            target = self.tmp / 'lab_completed'
            with zipfile.ZipFile(archive) as z:
                z.extractall(target)
                packed = {n: z.read(n) for n in z.namelist() if n.startswith(name + '/output/')}
            folder = target / name
            shutil.rmtree(folder / 'output')
            codes = {}
            for cmd in L.RUNS[kind]:
                codes[cmd] = run(folder, 'run.py', cmd, '--no-open')[0]
                if codes[cmd]:
                    self.fail(f'{name} 완성본 새 폴더: python run.py {cmd} exit {codes[cmd]}')
            same = {n.split('/', 1)[1]: (folder / n.split('/', 1)[1]).read_bytes() == data for n, data in packed.items() if not n.endswith(('result.html', 'result.json'))}
            if not same or not all(same.values()):
                self.fail(f'{name} 완성본 새 폴더: 다시 실행한 결과 파일이 동봉한 것과 다름 {same}')
            code, out = run(folder, '-m', 'app.utils.check')
            if code or '구조 검사 통과' not in out:
                self.fail(f'{name} 완성본 새 폴더: 검사기 통과 아님\n{out[:800]}')
            rec[name] = {'zip sha256': sha(archive.read_bytes()), '명령 exit': codes, '동봉 결과와 같은 바이트': same, '검사기': f'exit {code}'}
            done[kind] = folder
        self.report['통합_완성본_새_폴더'] = rec
        return done

    # ───────────── 8. 경계 · 낱말 · 가이드 ─────────────
    def boundary(self):
        rec = {}
        for kind, name in L.PROJECT.items():
            folder, r = self.folder[kind], {}
            leaks, old = [], {}
            secret = [s[k] for s in A.SCOPES.values() for k in ('chosen', 'why', 'next')] + [c[k] for c in A.ORDERS.values() for k in ('chosen', 'why')] + [A.STATEMENT]
            for p in sorted(folder.rglob('*')):
                if not p.is_file() or p.suffix == '.pyc':
                    continue
                rel = p.relative_to(folder).as_posix()
                text = p.read_text(encoding='utf-8-sig')
                leaks += [f'{rel}: 「{w}」' for w in LEAK_WORDS if w in text]
                leaks += [f'{rel}: 강사 참조의 갈래 문장' for s in secret if s in text]
                for w in OLD_WORDS:
                    if w in text:
                        old.setdefault(w, []).append(rel)
            r['답 · 강사 자료를 가리키는 낱말'] = leaks
            r['옛 낱말(쓰지 않을 말)'] = old
            for x in leaks:
                self.fail(f'{name}: 학생 폴더 경계 {x}')
            for w, where in old.items():
                self.fail(f'{name}: 옛 낱말 「{w}」가 남음 {where}')
            guide = (self.dest / (name + '_guide.html')).read_text(encoding='utf-8')
            sections = re.findall(r'<section id="s\d+"><h2>\d+ (.*?)</h2>(.*?)</section>', guide, re.S)
            commands = set(re.findall(r"^    '([a-z]+)': \(", (folder / 'app/utils/actions.py').read_text(encoding='utf-8'), re.M))
            steps = []
            for title, body in sections:
                used = re.findall(r'python run\.py(?: ([a-z]+))?', html.unescape(re.sub(r'<[^>]+>', '', body)))
                bad = [c for c in used if c and c not in commands]
                if bad:
                    self.fail(f'{name} 가이드 「{html.unescape(title)}」: 없는 기능 {bad}')
                steps.append({'단계': html.unescape(title), '명령': sorted({('python run.py ' + c).strip() for c in used}), '정답 토글': body.count('class="answer"')})
            r['가이드 단계'] = steps
            plain = re.sub(r'<[^>]+>', '', guide)
            words = {w: plain.count(w) for w in OLD_WORDS + ['헌법 파일', 'KPI 점수'] if w in plain}
            r['가이드의 옛 낱말'] = words
            for w in words:
                self.fail(f'{name} 가이드: 옛 낱말 「{w}」')
            r['첫 블록 앞에 손으로 치지 않는 까닭'] = '오타를 줄이도록' in guide[:guide.find('class="block ')]
            r['앞 회차 한 마디'] = guide.count(F.TIP_RECALL.strip())
            r['2회차 요령의 까닭 문장'] = [t for t in (F.TIP_DATA, F.TIP_REQUEST, F.TIP_CHOOSE, F.TIP_ONE, F.TIP_DIFF) if t.strip() in guide]
            if r['2회차 요령의 까닭 문장'] or r['앞 회차 한 마디'] < 1 or '틀린 결과도 맞아 보' in guide:
                self.fail(f'{name} 가이드: AI 요령의 까닭을 다시 풀었거나 「앞 회차 실습에서 해 본 대로」가 없음')
            ai = sum(int(s['ai']) for s in __import__('session3_lab_guides').steps(kind))
            cost = F.guide_cost(guide, ai_turns=ai)
            r['사람 분(K-1)'] = {'줄': F.cost_line(folder, cost), '정할 지점 판단 3분을 더한 값': round(cost['사람_분'] + 3, 1)}
            agents = (folder / 'AGENTS.md').read_text(encoding='utf-8')
            r['AGENTS.md'] = {'공통 문구(project_layout.AI_RULES)로 시작': agents.startswith(__import__('project_layout').AI_RULES), '랩별 경계 줄': agents.count('\n- ') - __import__('project_layout').AI_RULES.count('\n- ')}
            rec[name] = r
        self.report['통합_경계_가이드'] = rec


def run_all(dest, tmp, fail, report):
    t = Trials(dest, tmp, fail, report)
    t.inputs()
    c, j = t.criteria(), t.judge()
    t.chain(c, j)
    t.damages(t.completed())
    t.boundary()
