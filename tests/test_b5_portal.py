"""B5 화면: node 로 실제 화면 코드(ui.js + ask.js · kpi.js · whatif.js)를 돌려 그린다 — 서버 계산 결과(진짜 view · report · whatif)를 넣고
질문 · 도구 호출 · 답 + 근거 · 답할 수 없음 + 이유 · 처리 과정 링크, 시험 목표 · 원래 판정, 관점 중요도 칸이 보이는지와 영문 id 노출 0을 본다."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from test_instance_mode import world  # noqa: F401 — fixture
from test_whatif import ent, mf  # noqa: F401 — fixture (업무 DB 계약)

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / 'it' / 'portal' / 'www'
NODE = shutil.which('node')
RUNNER = r"""
const vm = require('vm'); const fs = require('fs');
const [www, file, data] = process.argv.slice(1);
const ctx = { window: {}, console, location: { protocol: 'http:', hostname: 'x' }, fetch: async () => ({ ok: false, json: async () => ({}) }),
  document: { getElementById: () => null, querySelectorAll: () => [], readyState: 'complete', addEventListener() {}, createElement: () => ({}) },
  setTimeout: () => 0, clearTimeout() {}, crypto: {} };
ctx.globalThis = ctx; vm.createContext(ctx);
vm.runInContext("const esc = (s) => String(s ?? '').replace(/[&<>\"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;' }[c])); const API = { process: 'http://x:8080', agent: 'http://x:8091' };", ctx);
vm.runInContext(fs.readFileSync(www + '/ui.js', 'utf8'), ctx);
vm.runInContext(fs.readFileSync(www + '/' + file, 'utf8'), ctx);
ctx.D = JSON.parse(fs.readFileSync(data, 'utf8'));
const el = { innerHTML: '', querySelector: () => null, querySelectorAll: () => [] };
ctx.EL = el;
vm.runInContext(ctx.D.script, ctx);
console.log(JSON.stringify(el.innerHTML));
"""
LEAK = re.compile(r'\b(?:msr|skill|sv|obj|persp|cause|pattern|dept|ask_agent|anomaly_response|agent|sys|role)[:.][\w-]+')


def render(tmp_path, file, data, script):
    if NODE is None:
        pytest.skip('node 없음')
    p = tmp_path / 'd.json'
    p.write_text(json.dumps(dict(data, script=script), ensure_ascii=False, default=str), encoding='utf-8')
    out = subprocess.run([NODE, '-e', RUNNER, str(WWW), file, str(p)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    html = json.loads(out.stdout)
    shown = re.sub(r'<code>[^<]*</code>', ' ', html)                 # 실행한 질의(code)는 근거로 그대로 보인다
    shown = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', shown))
    return html, shown


# ---------------------------------------------------------------- 질문하기
def _ask_views(world, tmp_path):
    from procsvc import ask
    from test_b5_ask import ANSWER, _ask, _cli, _people, _work
    rt = world['rt']; _people(rt)
    a = _ask(rt, agent='agent:student-db')
    _work(rt, tmp_path, _cli(ANSWER))
    b = _ask(rt, q='다음 달 환율은?')
    _work(rt, tmp_path, _cli(ANSWER, calls=()))
    status = ask.readiness(lambda: {'url': 'http://agent-worker:8097', 'reachable': False, 'error': 'connection refused'}, 'legacy') \
        | {'agents': ask.agents(rt.repo, rt.tenant_id), 'default': ask.DEFAULT_AGENT}
    return ask.view(rt, a['id']), ask.view(rt, b['id']), ask.history(rt), status


def test_ask_screen_shows_tool_calls_answer_evidence_and_link(world, tmp_path):
    good, bad, hist, status = _ask_views(world, tmp_path)
    script = "const A = window.hydAsk._state; Object.assign(A, { el: EL, status: D.status, agents: D.status.agents, agent: 'agent:student-db', cur: D.cur, history: D.hist }); window.hydAsk._render();"
    html, text = render(tmp_path, 'ask.js', {'cur': good, 'hist': hist, 'status': status}, script)
    for word in ('에이전트에게 질문하기', '업무 DB 조회 도우미', '(내가 만든 것)', '도구 호출', '업무 데이터 조회', '성공', 'HYD-02, 100개',
                 '실행 기록에서 확인됨', '근거 1개 확인', '처리 과정 보기', '지난 질문', '답할 수 없음', 'AGENT_BRIDGE=legacy'):
        assert word in text, word
    assert f'href="{good["link"]}"' in html and '/task/' in good['link']
    assert '<code>select asset, fg_stock from ent.fg_inventory' in html
    assert LEAK.findall(text) == [], LEAK.findall(text)
    html, text = render(tmp_path, 'ask.js', {'cur': bad, 'hist': hist, 'status': status},
                        "const A = window.hydAsk._state; Object.assign(A, { el: EL, status: D.status, agents: D.status.agents, cur: D.cur, history: D.hist }); window.hydAsk._render();")
    assert '답할 수 없음' in text and '성공한 도구 조회가 하나도 없습니다' in text and '근거 확인 안 됨' in text
    assert LEAK.findall(text) == [], LEAK.findall(text)


# ---------------------------------------------------------------- KPI 목표 바꿔 보기
def test_kpi_screen_shows_trial_targets_and_original_judgement(tmp_path):
    from procsvc import kpi
    from test_kpi import BIZ, NOW, TS, Fake
    rep = kpi.report(Fake(TS, BIZ), '24h', now=NOW, time_scale=20, targets={'msr:availability': 90})
    script = ("const st = { el: EL, period: '24h', data: D.rep, trace: null, targets: { 'msr:availability': '90' }, applied: { 'msr:availability': 90 }, trialOpen: true };"
              "window.hydKpi._render(st);")
    html, text = render(tmp_path, 'kpi.js', {'rep': rep}, script)
    for word in ('시험 목표 1개 적용 중', '설비 가동률', '미달 → 달성', '원래 목표 95', '원래 판정 미달', '원래대로', '목표값 바꿔 보기', '시험 판정', '그대로'):
        assert word in text, word
    assert html.count('data-kpi-target=') == 21 and LEAK.findall(text) == [], LEAK.findall(text)


# ---------------------------------------------------------------- What-if 관점 중요도
def test_whatif_rules_tab_shows_perspective_weights_from_the_ontology(tmp_path, mf):
    from agentsvc import whatif
    from test_b5_whatif_perspectives import pb
    b = pb()
    pol = {'weights': {}, 'penalties': {}, 'perspectives': {'persp:internal': 5}}

    def view(policy=None):
        ev = whatif.evaluate(b, mf, None, policy)
        return dict(ev, variables=whatif.variable_list(mf), policy=whatif.policy_view(b['dmn']), perspectives=whatif.perspective_view(b),
                    summary=whatif.summary(ev, whatif.evaluate(b, mf)['top'] if policy else None), original={'unchanged': True, 'note': ''},
                    cause={'name': '쿨러 핀 오염'}, asset='HYD-01', created='2026-10-08T00:00:00Z')
    script = ("const W = window.hydWhatif._W; Object.assign(W, { el: EL, base: D.base, view: D.view, tab: 'rules', bounds: [],"
              " policy: { weights: {}, penalties: {}, perspectives: { 'persp:internal': 5 } }, perspForm: { 'persp:internal': 5 } }); window.hydWhatif._render();")
    html, text = render(tmp_path, 'whatif.js', {'base': view(), 'view': view(pol)}, script)
    for word in ('관점 중요도 바꿔 보기', '재무 (배)', '고객 (배)', '내부 프로세스 (배)', '학습과 성장 (배)', '관점 비중으로 다시 계산',
                 '이 판단의 카드 득실에 나오지 않는 관점', '카드별 관점 득실', '내부 프로세스 5배', '바뀌었습니다'):
        assert word in text, word
    assert html.count('data-wi-persp=') == 4 and LEAK.findall(text) == [], LEAK.findall(text)
