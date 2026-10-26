"""화면 판정이 통과해도 별도 통신 실패를 완료 보고에서 숨기지 않는다."""
from scripts.class_round import LabLog, Round, Verdict


def test_report_exposes_network_failures_even_when_verdicts_pass(tmp_path):
    run = Round.__new__(Round)
    run.out = tmp_path
    run.verdicts = [Verdict('02', '판단 완료', True, 'normal', '')]
    run.logs = {'02': LabLog(failed_requests=['HTTP 503 /healthz'])}
    assert run.write() == 1
    report = (tmp_path / 'summary.md').read_text(encoding='utf-8')
    assert '실패 0개 · 별도 콘솔/통신 오류 실습 1개' in report
    assert 'HTTP 503 /healthz' in report
