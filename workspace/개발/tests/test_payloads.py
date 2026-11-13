"""큰 도구 결과 원문(worker/payloads.py) — 처리 기록 한 칸에 못 담는 원문을 (처리 건, 내용 해시) 한 행으로, CLI 가 옮긴 파일은 그 세션 폴더 안만."""
import json

from worker import payloads


def test_잘린_미리보기의_원문을_내용_해시와_요약으로_잡는다():
    captured = payloads.capture('x' * 9000, preview_cut=True)
    assert captured == {'content': 'x' * 9000, 'source': 'event_text', 'meta': {}}
    row, summary = payloads.payload_row(captured, tool='mcp__hyd-dmn__evaluate_cards', tool_use_id='t1', job_id='j', todo_id='w', proc_inst_id='p')
    digest = row['meta']['content_sha256']
    assert row['id'] == payloads.payload_id('p', digest) and row['chars'] == 9000 and row['meta']['cut'] is False and summary
    ref = payloads.reference(row, summary, stored=True)
    assert ref['stored'] is True and ref['ref'] == row['id'] and ref['sha256'] == digest


def test_같은_처리_건의_같은_내용은_한_행이고_처리_건이_다르면_다른_행이다():
    assert payloads.payload_id('p1', 'h') == payloads.payload_id('p1', 'h') != payloads.payload_id('p2', 'h')


def test_작은_결과는_따로_잡지_않는다():
    assert payloads.capture('작은 결과', preview_cut=False) is None


def test_CLI_가_옮긴_파일은_그_세션_폴더_안이면_원문을_읽고_MCP_묶음을_푼다(tmp_path):
    saved = tmp_path / 'tool-results' / 'r.json'
    saved.parent.mkdir()
    saved.write_text(json.dumps([{'type': 'text', 'text': '원문'}]), encoding='utf8')
    text = f'MCP tool result (91234 characters) exceeds maximum allowed tokens. Output has been saved to {saved}'
    captured = payloads.capture(text, preview_cut=False, allowed_directory=saved.parent)
    assert payloads.oversized(text) and captured['content'] == '원문' and captured['meta']['unwrapped'] is True


def test_CLI_가_옮긴_파일이_그_세션_폴더_밖이면_읽지_않고_못_읽었다고_적는다(tmp_path):
    outside = tmp_path / 'secret.txt'
    outside.write_text('비밀', encoding='utf8')
    allowed = tmp_path / 'session'
    allowed.mkdir()
    text = f'MCP tool result (91234 characters) exceeds maximum allowed tokens. Output has been saved to {outside}'
    assert payloads.saved_path(text, allowed_directory=allowed) is None
    captured = payloads.capture(text, preview_cut=False, allowed_directory=allowed)
    assert captured['content'] is None and '찾지 못했거나' in payloads.unread_reference(captured)['error']
