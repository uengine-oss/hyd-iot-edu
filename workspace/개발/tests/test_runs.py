"""읽기 평가 실행 기록(it/agent/agentsvc/runs.py) — 평가할 때마다 새 실행, 응답으로만 돌려주고 쌓지 않는다(G1-07)."""
from agentsvc import runs


def test_같은_경보라도_평가할_때마다_새_id_의_실행이다():
    alert = {'alertId': 'EVAL-1', 'asset': 'HYD-01'}
    a, b = runs.Run.new(alert), runs.Run.new(alert)
    assert a.id != b.id and a.id.startswith('RUN-') and a.alert_id == 'EVAL-1'


def test_실행은_단계를_쌓고_끝_상태와_까닭을_남긴다():
    run = runs.Run.new({'alertId': 'EVAL-2', 'asset': 'HYD-02'})
    run.step('freshness', {'ok': True}, note='신선도')
    run.finish('WITHHELD', '근거 없음')
    out = run.to_dict()
    assert out['status'] == 'WITHHELD' and out['error'] == '근거 없음' and [s['name'] for s in out['steps']] == ['freshness'] and out['ended']
