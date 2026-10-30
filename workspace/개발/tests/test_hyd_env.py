""".env 해석기 한 벌(scripts/hyd_env.py) — 시작 · 점검 · 포트 준비가 Docker Compose 와 같은 값을 읽고, 쓴 값을 그대로 다시 읽는다.

정답은 Docker Compose v5.6.1 이 같은 줄을 읽은 결과다(2026-10-30, 스크래치 compose 에 `${X-unset}` 로 실측):
BOM · CRLF 무시, export 허용, = 앞뒤 공백 지움, 따옴표 없는 값은 「공백 + #」부터 주석, 같은 키는 마지막 값, 키에 공백이 있으면 오류.
"""
import pytest

import hyd_env


@pytest.mark.parametrize('text, key, value', [
    ('﻿A=bom\r\n', 'A', 'bom'),                         # 메모장이 붙이는 BOM · CRLF
    ('export B=exp\n', 'B', 'exp'),
    ('C=a#b\n', 'C', 'a#b'),                                 # 공백 없는 # 는 값
    ('D=x\t# tab\n', 'D', 'x\t# tab'),                       # 탭 + # 도 값(Compose 와 같게)
    ('E=1\nE=2\n', 'E', '2'),                                # 같은 키는 마지막 값
    ('F= # only\n', 'F', '# only'),                          # 값 맨 앞의 # 는 주석이 아니다
    ('G="q\\"x"\n', 'G', 'q"x'),
    ('  H  =  spaced  \n', 'H', 'spaced'),
    ('I="a\\nb"\n', 'I', 'a\nb'),
    ("J='a'b\n", 'J', 'a'),                                  # 닫는 따옴표 뒤는 버린다
    ('LLM_API_KEY = sk-abc # 메모\n', 'LLM_API_KEY', 'sk-abc'),
    ('Q="a b" # c\n', 'Q', 'a b'),
    ("R='x # y'\n", 'R', 'x # y'),
    ('M="첫 줄\n둘째 줄"\nN=1\n', 'M', '첫 줄\n둘째 줄'),     # 따옴표 안의 줄바꿈
    ('HYD_PORTS="8088=18088 54321=64321"\n', 'HYD_PORTS', '8088=18088 54321=64321'),
    ('URL=http://localhost:8088/a\n', 'URL', 'http://localhost:8088/a'),
])
def test_한_줄을_Compose와_같은_값으로_읽는다(text, key, value):
    assert hyd_env.parse(text)[key] == value


@pytest.mark.parametrize('text', [
    '#K=commented\n',
    '#HYD_KEY_OFF LLM_API_KEY=sk-abc\n',                     # 메인이 키를 끌 때 쓰는 표시
    '\n   \n# 설명만\n',
])
def test_주석과_빈_줄은_값이_아니다(text):
    assert hyd_env.parse(text) == {}


@pytest.mark.parametrize('text, line_no', [
    ('A=ok\nthis line is bad\n', 2),
    ('A=ok\nB="닫히지 않음\n', 2),
    ('한글키=1\n', 1),
])
def test_읽을_수_없는_줄은_그_줄_번호로_실패한다(text, line_no):
    with pytest.raises(hyd_env.EnvFileError, match=rf'{line_no}번째 줄'):
        hyd_env.parse(text)


@pytest.mark.parametrize('text, mode', [
    ('LLM_API_KEY=\n', 'replay'),
    ('', 'replay'),
    ('LLM_API_KEY=""\n', 'replay'),
    ("LLM_API_KEY=' '\n", 'replay'),
    ('#HYD_KEY_OFF LLM_API_KEY=sk-abc\n', 'replay'),
    ('LLM_API_KEY=sk-abc\n', 'live'),
    ('LLM_API_KEY = sk-abc # 수업 키\n', 'live'),              # 옛 시작은 공백 때문에 재생으로 잘못 정했다
    ('﻿LLM_API_KEY=sk-abc\r\n', 'live'),                  # 옛 시작은 첫 줄 BOM 때문에 재생으로 잘못 정했다
    ('LLM_API_KEY="sk-abc"\n', 'live'),
    ('LLM_API_KEY=sk-abc\nLLM_API_KEY=\n', 'replay'),         # 마지막 줄이 이긴다(Compose 와 같게)
])
def test_키가_있으면_실제_AI_없으면_재생으로_정한다(text, mode):
    assert hyd_env.ai_mode(hyd_env.parse(text)) == mode


@pytest.mark.parametrize('text, mode', [('LLM_API_KEY=sk-abc\n', 'record'), ('LLM_API_KEY=\n', None)])
def test_응답_저장은_키가_있을_때만_된다(text, mode):
    if mode is None:
        with pytest.raises(hyd_env.EnvFileError, match='LLM_API_KEY'):
            hyd_env.ai_mode(hyd_env.parse(text), record=True)
    else:
        assert hyd_env.ai_mode(hyd_env.parse(text), record=True) == mode


@pytest.mark.parametrize('text', [
    '',
    '# 설명\nA=1\n',
    '﻿A=1\r\nB=2\r\n',
    'A=1\nA=2\n# 끝\n',
    'M="여러\n줄"\nA=1\n',
])
@pytest.mark.parametrize('updates', [
    {'A': '9'},
    {'HYD_PORTS': '8088=18088 54321=64321'},
    {'X': 'a # b', 'Y': 'q"x', 'Z': '$HOME'},
    {'A': '', 'M': 'one'},
])
def test_고쳐_쓴_파일을_다시_읽으면_고친_값과_나머지_값이_그대로다(text, updates):
    new = hyd_env.with_updates(text, updates)
    assert hyd_env.parse(new) == {**hyd_env.parse(text), **updates}
    assert '\r' not in new and not new.startswith('﻿')


def test_고쳐_쓸_때_다른_줄의_주석은_그대로_남는다():
    text = '# 수업 키를 넣는다\nLLM_API_KEY=sk-abc # 메모\nAI_MODE=live\n'
    assert hyd_env.with_updates(text, {'AI_MODE': 'replay'}) == '# 수업 키를 넣는다\nLLM_API_KEY=sk-abc # 메모\nAI_MODE=replay\n'


@pytest.mark.parametrize('name, value', [('A', '첫\n둘'), ('나쁜 이름', '1'), ('A', "$'")])
def test_다시_읽을_수_없는_값은_쓰지_않는다(name, value):
    with pytest.raises(hyd_env.EnvFileError):
        hyd_env.with_updates('', {name: value})


@pytest.mark.parametrize('content, args, code, mode', [
    ('LLM_API_KEY=sk-abc\n', ['ai-mode'], 0, 'live'),
    ('LLM_API_KEY=\n', ['ai-mode'], 0, 'replay'),
    ('LLM_API_KEY=sk-abc\n', ['ai-mode', '--record'], 0, 'record'),
    ('LLM_API_KEY=\n', ['ai-mode', '--record'], 1, None),
    ('LLM_API_KEY=\n', ['모르는-명령'], 2, None),
])
def test_시작이_부르는_명령은_정한_방식을_AI_MODE에_적고_낱말을_낸다(tmp_path, capsys, content, args, code, mode):
    (tmp_path / '.env').write_text(content, encoding='utf-8')
    assert hyd_env.main(['hyd_env.py', *args], root=tmp_path) == code
    out = capsys.readouterr()
    values = hyd_env.read(tmp_path / '.env')
    if mode:
        assert out.out.strip() == mode and values['AI_MODE'] == mode
    else:
        assert 'AI_MODE' not in values and out.err.strip()


def test_다른_인코딩으로_저장한_env는_줄을_어림하지_않고_실패한다(tmp_path):
    (tmp_path / '.env').write_bytes('# 수업 키\nLLM_API_KEY=sk\n'.encode('cp949'))
    with pytest.raises(UnicodeDecodeError):
        hyd_env.read(tmp_path / '.env')
