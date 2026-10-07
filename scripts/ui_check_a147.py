"""A147 — 포털 묶음 3 나머지(항목 6 · 7 · 8 · 9)의 브라우저 확인 + 바뀐 탭 1440 캡처 1회.

    PYTHONUTF8=1 python scripts/ui_check_a147.py .evidence/a147

상태를 바꾸는 요청은 하나도 서버에 가지 않는다: 폐기 · 보상 POST 는 page.route 로 끊고(abort = 응답 유실), 시험용 승인 · 효과 · 거래 ·
스트림 응답은 route 로 주입한다(주입한 화면 캡처는 파일 이름에 -mock). 읽기 GET 만 실제 서버로 간다.
  6  시스템 구성: 선택 도구는 5초 확인에서 빠짐 → 페이지를 20초 열어 둬도 콘솔 0, 켜진 FUXA 클릭 → 새 창, 꺼진 Redpanda Console 클릭 → "(꺼짐 …)"
  7  승인과 실행 → 시스템 실행 이력: 거래(a109 원장의 실제 기록 1건 주입)의 `변경 전·후` 접기가 기본 닫힘, 열면 바뀐 항목만
  8  처리 건: 폐기 · 보상 응답 유실 → sessionStorage 에 같은 request_id 보존 · 재확인 버튼 · 재시도 본문 request_id 동일 · 새로고침 뒤 복원 · 서버 기록이 보이면 해제
  9  실시간 스트림: 409 + 기본 처리 모드 → "실시간 꺼짐", 재연결 없음 / 503 → 2 · 4 · 8 s 백오프 재연결 → 통과시키면 연결됨
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PORTAL = 'http://127.0.0.1:8088/'
PROC = 'http://127.0.0.1:8080'
ROOT = Path(__file__).resolve().parents[1]
TX_SAMPLE = ROOT / '.evidence/reaudit/a109-report-ui/ledger.json'
WID = 'WI-A147-TEST'


def find_tx(o):
    if isinstance(o, dict):
        if 'compensates' in o and 'after' in o and o.get('before'):
            return o
        for v in o.values():
            r = find_tx(v)
            if r: return r
    if isinstance(o, list):
        for v in o:
            r = find_tx(v)
            if r: return r


def new_page(browser, w=1440, h=900):
    ctx = browser.new_context(viewport={'width': w, 'height': h}, locale='ko-KR')
    pg = ctx.new_page(); msgs = []
    pg.on('console', lambda m: msgs.append({'type': m.type, 'text': m.text[:240], 'url': (m.location or {}).get('url', '')}))
    pg.on('pageerror', lambda e: msgs.append({'type': 'pageerror', 'text': str(e)[:240]}))
    return ctx, pg, msgs


def errors(msgs):
    return [m for m in msgs if m['type'] in ('error', 'pageerror', 'warning')]


def item6(browser, out, R):
    ctx, pg, msgs = new_page(browser)
    pg.goto(PORTAL, wait_until='networkidle'); pg.click('[data-tab="home"]'); pg.wait_for_timeout(20000)   # 5초 확인 4회
    R['6'] = {'console_after_20s': errors(msgs), 'header': pg.locator('#healthDots').inner_text(),
              'entries': pg.eval_on_selector_all('[data-entry-status]', 'es => es.map(e => [e.dataset.entryStatus, e.textContent])')}
    pg.screenshot(path=str(out / 'home-1440.png'), full_page=True)
    msgs.clear()
    with ctx.expect_page(timeout=8000) as popup:                                       # FUXA(켜짐) → 새 창
        pg.click('a[data-entry$=":1881"]')
    R['6']['fuxa_click'] = {'opened': popup.value.url, 'status': pg.locator('[data-entry-status$=":1881"]').inner_text()}
    popup.value.close()
    pg.click('a[data-entry$=":8085/topics"]'); pg.wait_for_timeout(4000)              # Redpanda Console(꺼짐) → 표시만
    R['6']['console_click'] = {'status': pg.locator('[data-entry-status$=":8085/topics"]').inner_text(), 'pages': len(ctx.pages), 'console_on_click': errors(msgs)}
    ctx.close()


def item7(browser, out, R):
    tx = find_tx(json.loads(TX_SAMPLE.read_text(encoding='utf8')))
    ctx, pg, msgs = new_page(browser)
    pg.route('**/api/transactions*', lambda route: route.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps([tx], ensure_ascii=False)))
    pg.goto(PORTAL, wait_until='networkidle'); pg.click('[data-tab="process"]'); pg.wait_for_timeout(5000)
    pg.evaluate("document.querySelector('#txFold').open = true"); pg.wait_for_timeout(300)
    fold = pg.locator('#txList details.fold', has=pg.locator('summary', has_text='변경 전·후')).first
    closed = fold.evaluate('d => !d.open')
    fold.evaluate('d => d.open = true'); pg.wait_for_timeout(300)
    rows = fold.locator('tbody tr').all_inner_texts()
    R['7'] = {'tx': tx['id'], 'summary': fold.locator('summary').inner_text(), 'default_closed': closed, 'rows': rows, 'console': errors(msgs)}
    pg.locator('#txFold').scroll_into_view_if_needed()
    pg.screenshot(path=str(out / 'process-1440-mock-tx.png'), full_page=True)
    pg.locator('#txFold').screenshot(path=str(out / 'crop-process-tx-1440-mock.png'))
    ctx.close()


def item8(browser, out, R):
    inst = json.load(__import__('urllib.request').request.urlopen(PROC + '/api/instances?status=COMPLETED&limit=20', timeout=10))
    iid = next(x['proc_inst_id'] for x in inst if x['proc_inst_id'].startswith('anomaly_response.'))
    S = {'approval': 'FAILED', 'discard_rid': None, 'receipt': None, 'posts': []}
    eff_id = 'eff:a147-test'

    def view(route):
        r = route.fetch(); v = r.json()
        v['instance']['status'] = 'RUNNING'
        snap = {'roles': {'role:prod-mgr': {'name': '생산관리자'}}}
        a = {'todo_id': WID, 'status': S['approval'], 'attempts': 1, 'error': None, 'payload': {'by': '시험', 'option': 'opt:a147', 'plan': {'option': {'name': '시험 승인(주입)'}, '_snapshot': snap}},
             'history': [{'request_id': S['discard_rid'], 'by': 'A147', 'role': 'role:prod-mgr', 'reason': '시험'}] if S['approval'] == 'DISCARDED' else []}
        v['approvals'] = [a]
        route.fulfill(response=r, json=v)

    def effects(route):
        body = {'incident': {'state': 'CLOSED', 'cmdId': None}, 'review_roles': ['role:prod-mgr'],
                'effects': [{'id': eff_id, 'kind': 'enterprise', 'system': 'sys:cmms', 'skill': 'skill:create-work-order', 'ref': 'WO-A147', 'detail': '시험 작업지시(주입)', 'reversible': True, 'inverse': 'skill:cancel-work-order'}],
                'resolution': {'pending': [] if S['receipt'] else [eff_id], 'compensated': [eff_id] if S['receipt'] else [], 'acknowledged': []},
                'receipts': [S['receipt']] if S['receipt'] else []}
        route.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(body, ensure_ascii=False))

    def lost(route):                                       # 응답 유실: 요청을 기록하고 끊는다(서버에 가지 않음)
        S['posts'].append({'url': route.request.url.split('/api/')[1], 'body': json.loads(route.request.post_data or '{}')}); route.abort('connectionreset')

    def preview(route):
        route.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'},
                      body=json.dumps({'incident': {'state': 'CLOSED'}, 'enterprise_receipts': [], 'outcome': '실제 조치 없음(주입)', 'cancel_workitems': []}, ensure_ascii=False))

    ctx, pg, msgs = new_page(browser)
    pg.route(f'**/api/instances/{iid}', view)
    pg.route(f'**/api/instances/{iid}/effects', effects)
    pg.route('**/api/instances/*/effects/*', lost)
    pg.route('**/approval-discard-preview', preview)
    pg.route('**/approval-discard', lost)

    def open_case():
        pg.goto(PORTAL, wait_until='networkidle'); pg.click('[data-tab="instances"]'); pg.wait_for_timeout(2500)
        pg.evaluate('id => window.hydInstancesSelect(id)', iid); pg.wait_for_timeout(3500)
        pg.click('[data-inst-tab="flow"]'); pg.wait_for_timeout(800)          # 승인 · 효과 패널은 흐름 탭에 있다

    open_case()
    # 8a 보상: 응답 유실 → 보존 · 재확인 → 같은 request_id
    pg.evaluate("""() => { const set = (s, v) => { const e = document.querySelector(s); e.value = v; e.dispatchEvent(new Event(e.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })); };
      set('#efBy', 'A147 시험'); set('#efRole', 'role:prod-mgr'); set('#efReason', '응답 유실 시험'); document.querySelector('#efCompensate').click(); }""")
    pg.wait_for_timeout(1500)
    key = f'hyd:effects:{iid}'
    e1 = {'stored': pg.evaluate('k => sessionStorage.getItem(k)', key), 'retry_button': pg.locator('#efRetry').count(), 'error_text': pg.locator('#effectsPanel .form-actions').inner_text() if pg.locator('#effectsPanel .form-actions').count() else ''}
    pg.click('#efRetry'); pg.wait_for_timeout(1500)
    pg.locator('#effectsPanel').scroll_into_view_if_needed()
    pg.locator('#effectsPanel').screenshot(path=str(out / 'crop-instances-effects-pending-1440-mock.png'))
    pg.wait_for_timeout(4000)                                  # 보상 재시도 뒤 처리 건 다시 그리기가 끝난 다음 폐기 미리보기(다시 그리면 미리보기 카드가 지워진다)
    # 8b 폐기: 미리보기(주입) → 확정 → 응답 유실
    pg.evaluate(f"""() => {{ const p = document.querySelector('[data-approval-discard-preview="{WID}"]').closest('[data-approval-panel]');
      p.querySelector('[data-retry-by]').value = 'A147 시험'; p.querySelector('[data-retry-role]').value = 'role:prod-mgr'; p.querySelector('[data-discard-reason]').value = '응답 유실 시험';
      p.querySelector('[data-approval-discard-preview]').click(); }}""")
    pg.wait_for_timeout(1500)
    pg.click('[data-confirm-discard]'); pg.wait_for_timeout(2000)
    dkey = f'hyd:discard:{WID}'
    d1 = {'stored': pg.evaluate('k => sessionStorage.getItem(k)', dkey), 'retry_button': pg.locator(f'[data-discard-retry="{WID}"]').count()}
    pg.click(f'[data-discard-retry="{WID}"]'); pg.wait_for_timeout(2000)
    pg.screenshot(path=str(out / 'instances-1440-mock-pending.png'), full_page=True)
    # 새로고침 뒤에도 남는가
    open_case()
    restored = {'effects_retry': pg.locator('#efRetry').count(), 'effects_by': pg.locator('#efBy').input_value() if pg.locator('#efBy').count() else None,
                'discard_retry': pg.locator(f'[data-discard-retry="{WID}"]').count()}
    # 서버 기록이 보이면 해제 (주입한 GET 이 처리 완료를 돌려준다)
    rid_e = json.loads(e1['stored'] or '{}').get('body', {}).get('request_id')
    S['discard_rid'] = json.loads(d1['stored'] or '{}').get('request_id')
    S['receipt'] = {'request_id': rid_e, 'kind': 'compensation', 'status': 'DELIVERED', 'request': {'by': 'A147 시험', 'role': 'role:prod-mgr', 'reason': '응답 유실 시험'}}
    S['approval'] = 'DISCARDED'
    pg.wait_for_timeout(5000)
    pg.evaluate('id => window.hydInstancesSelect(id)', iid); pg.wait_for_timeout(3500)
    pg.click('[data-inst-tab="flow"]'); pg.wait_for_timeout(800)
    cleared = {'effects_key': pg.evaluate('k => sessionStorage.getItem(k)', key), 'discard_key': pg.evaluate('k => sessionStorage.getItem(k)', dkey),
               'effects_retry': pg.locator('#efRetry').count(), 'discard_retry': pg.locator(f'[data-discard-retry="{WID}"]').count(),
               'notice': pg.locator('#effectsPanel [role=status]').all_inner_texts()}
    posts = S['posts']
    R['8'] = {'instance': iid, 'effects_first': e1, 'discard_first': d1, 'posts': posts,
              'same_request_id_effects': len({p['body'].get('request_id') for p in posts if 'effects/' in p['url']}) == 1 and sum('effects/' in p['url'] for p in posts) == 2,
              'same_request_id_discard': len({p['body'].get('request_id') for p in posts if 'approval-discard' in p['url']}) == 1 and sum('approval-discard' in p['url'] for p in posts) == 2,
              'restored_after_reload': restored, 'cleared_after_server_record': cleared,
              'console': [m for m in errors(msgs) if 'ERR_CONNECTION_RESET' not in m['text'] and 'ERR_FAILED' not in m['text']],
              'console_expected_aborts': len([m for m in errors(msgs) if 'ERR_CONNECTION_RESET' in m['text'] or 'ERR_FAILED' in m['text']])}
    ctx.close()


def item9(browser, out, R):
    res = {}
    # 9a: 409 + 기본 처리 모드 → 꺼짐, 재연결 없음
    ctx, pg, msgs = new_page(browser); hits = []
    def s409(route):
        hits.append(time.time()); route.fulfill(status=409, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body='{"detail":"process is in legacy mode (set PROCESS_MODE=instance)"}')
    pg.route('**/api/events/stream*', s409)
    pg.route('**/api/process/mode', lambda route: route.fulfill(status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body='{"mode":"legacy","agent_bridge":null,"definition":null}'))
    pg.goto(PORTAL, wait_until='networkidle'); pg.wait_for_timeout(12000)
    res['legacy'] = {'stream_requests_12s': len(hits), 'conn': pg.evaluate("(document.getElementById('streamConn') || {}).textContent")}
    ctx.close()
    # 9b: 503 세 번 → 백오프 재연결 → 통과
    ctx, pg, msgs = new_page(browser); hits = []
    def s503(route):
        hits.append(time.time())
        if len(hits) <= 3:
            route.fulfill(status=503, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'}, body='{"detail":"restarting"}')
        else:
            route.continue_()
    pg.route('**/api/events/stream*', s503)
    pg.goto(PORTAL, wait_until='domcontentloaded'); pg.wait_for_timeout(1500)
    mid = pg.evaluate("(document.getElementById('streamConn') || {}).textContent")
    pg.wait_for_timeout(16000)
    res['backoff'] = {'requests': len(hits), 'gaps_s': [round(b - a, 1) for a, b in zip(hits, hits[1:])], 'conn_during': mid, 'conn_after': pg.evaluate("(document.getElementById('streamConn') || {}).textContent")}
    ctx.close()
    R['9'] = res


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else '.evidence/a147'); out.mkdir(parents=True, exist_ok=True)
    R = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for fn in (item6, item7, item8, item9):
            try:
                fn(b, out, R)
            except Exception as e:  # noqa: BLE001
                R[fn.__name__] = {'FAIL': repr(e)[:500]}
            print(fn.__name__, json.dumps(R.get(fn.__name__[-1], R.get(fn.__name__)), ensure_ascii=False)[:900], flush=True)
        b.close()
    (out / 'behavior.json').write_text(json.dumps(R, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
