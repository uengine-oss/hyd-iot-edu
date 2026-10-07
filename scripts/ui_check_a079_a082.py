"""A079/A082 UI check in the real portal (headless Chromium), clicking the same controls a person uses.

    .venv314/Scripts/python scripts/ui_check_a079_a082.py .evidence/reaudit/a083-ui-<n>

1. Ontology tab: choose a small test manual (SOP-TEST-92, absent from the graph), press 미리보기, the per-SOP impact input
   renders; pick the failure mode, type the impact, tick reviewed, press 적재 → the graph holds a batch-owned AFFECTS edge
   with the typed sign; then press 이 판본 되돌리기 in the history → the skill and edge are gone.
2. Instances tab: open the given instance and record which rows show 작업 닫기; when --click is given, press it (the reason
   prompt is answered) and record the portal message — the server decides; this script never forces a close.
Screenshots and report.json go to the output folder.
"""
import argparse
import json
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

PORTAL = 'http://127.0.0.1:8088/'
SOP = 'SOP-TEST-92'
FM = 'fm:bearing-degradation'
MANUAL = f"""# 시험 매뉴얼 (A083, 영향 입력칸 화면 검사용)

## HT-2.1 팬 베어링 윤활 점검
진동이 기준을 넘으면 아래 절차를 따른다.

### {SOP} 팬 베어링 윤활 점검 절차
1. 설비를 정지하고 LOCAL로 전환한다.
2. 베어링 그리스 상태를 확인한다.
3. 결과를 CMMS에 기록한다.
"""


def cypher(q):
    r = subprocess.run(['docker', 'exec', 'hyd-iot-edu-neo4j-1', 'cypher-shell', '-u', 'neo4j', '-p', 'hydpass123', '--format', 'plain', q],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    return r.stdout.strip().splitlines()[1:] if r.returncode == 0 else ['ERR ' + r.stderr[-200:]]


def knowledge(pg, out, report):
    assert not cypher(f"MATCH (k:Skill {{sopId:'{SOP}'}}) RETURN k.id;"), 'test SOP already in the graph'
    src = out / 'a083-ui-test-manual.md'; src.write_text(MANUAL, encoding='utf-8')
    pg.click('button[data-tab="ontology"]'); pg.wait_for_timeout(1500)
    pg.set_input_files('#manualFile', str(src))
    pg.click('#manualPreview')
    pg.wait_for_selector(f'[data-affects="{SOP}"]', timeout=30000)
    report['affects_inputs'] = len(pg.query_selector_all('[data-affects]'))
    report['affects_placeholder'] = pg.get_attribute(f'[data-affects="{SOP}"]', 'placeholder')
    pg.select_option(f'[data-fm="{SOP}"]', FM)
    pg.fill(f'[data-affects="{SOP}"]', 'sv:bearing-wear:-')
    pg.fill('#manualBy', 'A083 화면 검사')
    pg.check('#manualReviewed')
    pg.query_selector(f'[data-affects="{SOP}"]').scroll_into_view_if_needed()
    pg.screenshot(path=str(out / '1-knowledge-affects-filled.png'))
    pg.click('#manualCommit')
    pg.wait_for_function("document.querySelector('#manualMsg') && /적재 완료|실패/.test(document.querySelector('#manualMsg').textContent)", timeout=60000)
    report['commit_message'] = pg.text_content('#manualMsg')
    pg.screenshot(path=str(out / '2-knowledge-committed.png'))
    sid = 'skill:' + SOP.lower()
    report['graph_affects_after_commit'] = cypher(f"MATCH (k:Skill {{id:'{sid}'}})-[a:AFFECTS]->(t) RETURN t.id, a.sign, a._manual_document IS NOT NULL;")
    report['graph_fm_after_commit'] = cypher(f"MATCH (f:FailureMode)-[r]->(k:Skill {{id:'{sid}'}}) RETURN f.id, type(r);")
    rollback(pg, out, report)


def rollback(pg, out, report):
    """Press 이 판본 되돌리기 on the test manual's row in the history table (collapsed by default)."""
    sid = 'skill:' + SOP.lower()
    pg.click('button[data-tab="ontology"]'); pg.wait_for_timeout(1500)
    pg.wait_for_selector('#manualHistory [data-manual-undo]', state='attached', timeout=30000)
    hist = pg.query_selector('#manualHistory details')
    if hist and hist.get_attribute('open') is None: pg.click('#manualHistory summary')
    row = pg.query_selector('#manualHistory tr:has-text("a083-ui-test-manual.md") [data-manual-undo]')
    report['undo_button_found'] = row is not None
    if row:
        row.scroll_into_view_if_needed(); row.click()
        pg.wait_for_function("![...document.querySelectorAll('#manualHistory tr')].some(t => t.textContent.includes('a083-ui-test-manual.md') && t.querySelector('[data-manual-undo]'))", timeout=60000)
        report['history_row_after_rollback'] = [t.inner_text() for t in pg.query_selector_all('#manualHistory tr:has-text("a083-ui-test-manual.md")')][:2]
        pg.screenshot(path=str(out / '3-knowledge-rolled-back.png'))
    report['graph_skill_after_rollback'] = cypher(f"MATCH (k:Skill {{id:'{sid}'}}) RETURN k.id;")
    report['graph_edges_after_rollback'] = cypher(f"MATCH (k:Skill {{id:'{sid}'}})-[a]-() RETURN type(a);")
    report['graph_rule_edge_after_rollback'] = cypher(f"MATCH (:Rule)-[o:OUTPUTS]->(:Skill {{id:'{sid}'}}) RETURN o;")

def task_rows(pg):
    return [{'activity': r.query_selector('td').inner_text().split('\n')[0], 'status': r.query_selector_all('td')[1].inner_text().replace('\n', ' '),
             'close': (r.query_selector('[data-close-task]') or None) and r.query_selector('[data-close-task]').get_attribute('data-close-task')}
            for r in pg.query_selector_all('table.inst-table tbody tr')]


def instances(pg, out, report, inst, click, status):
    pg.click('button[data-tab="instances"]'); pg.wait_for_timeout(2500)
    report['list_default_has_instance'] = pg.query_selector(f'#instList .item:has-text("{inst}")') is not None
    if status:
        pg.select_option('#instStatus', status); pg.wait_for_timeout(3000)
        report['list_filter'] = status
        report['list_filtered_count'] = len(pg.query_selector_all('#instList .item'))
    item = pg.query_selector(f'#instList .item:has-text("{inst}")')
    report['instance_in_list'] = item is not None
    pg.screenshot(path=str(out / '4-instance-list.png'))
    if not item: return
    item.click(); pg.wait_for_selector(f'h2:has-text("{inst}")', timeout=30000); pg.wait_for_timeout(1500)
    report['tasks'] = task_rows(pg)
    report['close_buttons'] = [t for t in report['tasks'] if t['close']]
    pg.screenshot(path=str(out / '5-instance-detail.png'), full_page=True)
    if click and report['close_buttons']:
        pg.once('dialog', lambda d: d.accept('A083 화면 검사: 멈춘 에이전트 작업 닫기'))
        pg.click('[data-close-task]'); pg.wait_for_timeout(4000)
        report['tasks_after_click'] = task_rows(pg)
        report['header_after_click'] = pg.inner_text('#instDetail h2') if pg.query_selector('#instDetail h2') else None
        pg.screenshot(path=str(out / '6-after-close-click.png'), full_page=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--instance'); ap.add_argument('--click', action='store_true')
    ap.add_argument('--skip-knowledge', action='store_true'); ap.add_argument('--rollback-only', action='store_true')
    ap.add_argument('--status', help='pick this value in the instance list filter first (e.g. RUNNING)'); a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=False)
    report = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={'width': 1360, 'height': 900})
        pg.goto(PORTAL, wait_until='networkidle'); pg.wait_for_timeout(1500)
        try:
            if a.rollback_only: rollback(pg, out, report)
            elif not a.skip_knowledge: knowledge(pg, out, report)
            if a.instance: instances(pg, out, report, a.instance, a.click, a.status)
        finally:
            (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
            b.close()
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
