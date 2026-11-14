"""도구 서버 비밀 값(procsvc/mcp_secrets.py) — `${SECRET:이름}` 참조 · 채우기 · 가림과 비밀 값 표(실제 DB). 값의 원천은 표 하나다."""
import pytest

from procsvc import mcp_secrets, procdb
from procsvc.mcp_secrets import SecretError

TENANT = 'hyd'


@pytest.fixture
def repo(pg_dsn):
    import psycopg
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        db.execute('DELETE FROM mcp_secrets WHERE tenant_id=%s', (TENANT,))
    return procdb.PgRepo(pg_dsn)


@pytest.mark.parametrize('value, says', [
    ('sk-live-ABCDEF\r\nX-Evil: 1', '보이지 않는 글자'),
    ('tok\tab', '보이지 않는 글자'),
    ('   ', '비었습니다'),
    ('Bearer ${SECRET:OTHER}', '다른 자리표시자'),
    ('x' * (mcp_secrets.MAX_VALUE + 1), f'{mcp_secrets.MAX_VALUE}자 이하'),
], ids=['가운데 줄바꿈', '탭', '빈 값', '자리표시자', '너무 긺'])
def test_넣을_수_없는_비밀_값은_까닭과_함께_거절되고_저장되지_않는다(repo, value, says):
    with pytest.raises(SecretError) as refused:
        mcp_secrets.put(repo, TENANT, 'MY_TOKEN', value, '강사', 'now')
    assert refused.value.status == 422 and says in refused.value.reason
    assert mcp_secrets.load(repo, TENANT) == {}


@pytest.mark.parametrize('value, stored', [
    ('  sk-live-1234  \n', 'sk-live-1234'),                 # 앞뒤 공백 · 줄바꿈은 지운다
    ('x' * mcp_secrets.MAX_VALUE, 'x' * mcp_secrets.MAX_VALUE),
], ids=['앞뒤 공백', '상한 길이'])
def test_비밀_값은_앞뒤_공백을_지워_표에_저장하고_목록에는_값을_싣지_않는다(repo, value, stored):
    mcp_secrets.put(repo, TENANT, 'MY_TOKEN', value, '강사', 'now')
    assert mcp_secrets.load(repo, TENANT) == {'MY_TOKEN': stored}
    view = mcp_secrets.overview(repo, TENANT, {'my-drive': {'headers': {'Authorization': 'Bearer ${SECRET:MY_TOKEN}'}}})
    assert view['secrets'] == [{'key': 'MY_TOKEN', 'stored': True, 'updated_at': view['secrets'][0]['updated_at'], 'updated_by': '강사',
                                'used_by': ['my-drive'], 'missing': False}]
    assert stored not in str(view)


def test_값이_없는_참조로_부르면_도구_연결_화면에_넣으라고_말한다(repo):
    entry = {'type': 'url', 'url': 'https://x/mcp', 'headers': {'Authorization': 'Bearer ${SECRET:MISSING_TOKEN}'}}
    with pytest.raises(SecretError) as refused:
        mcp_secrets.runtime_spec(repo, TENANT, 'my-drive', entry)
    assert refused.value.status == 422
    assert refused.value.reason == "도구 서버 'my-drive'에 필요한 비밀 값 MISSING_TOKEN이 없습니다 — [도구 연결] 화면의 '비밀 값'에 넣은 뒤 다시 하세요"


def test_부르기_직전에만_참조를_채우고_채운_값을_돌려준다(repo):
    mcp_secrets.put(repo, TENANT, 'MY_TOKEN', 'sk-live-5678', '강사', 'now')
    entry = {'type': 'url', 'url': 'https://x/mcp', 'headers': {'Authorization': 'Bearer ${SECRET:MY_TOKEN}', 'Accept': 'x'}}
    spec, used = mcp_secrets.runtime_spec(repo, TENANT, 'my-drive', entry)
    assert (spec['headers'], used) == ({'Authorization': 'Bearer sk-live-5678', 'Accept': 'x'}, ['sk-live-5678'])
    assert entry['headers']['Authorization'] == 'Bearer ${SECRET:MY_TOKEN}'            # 설정은 그대로


@pytest.mark.parametrize('entry, problems', [
    ({'url': 'https://x/${SECRET:TOKEN}/mcp'}, ['url: 비밀 자리표시자는 접속 헤더 값에만 쓸 수 있습니다']),
    ({'url': 'https://x/mcp', 'headers': {'A': '${SECRET:lower}'}}, ['${SECRET:lower}: 비밀 이름은 대문자 · 숫자 · 밑줄(_) 64자 이내, 첫 글자는 대문자여야 합니다 (예: GOOGLE_TOKEN)']),
    ({'url': 'https://x/mcp', 'headers': {'A': 'Bearer ${SECRET:GOOD_ONE}'}}, []),
], ids=['주소 안 참조', '소문자 이름', '바른 참조'])
def test_자리표시자는_접속_헤더에만_바른_이름으로(entry, problems):
    assert mcp_secrets.misplaced(entry) == problems


def test_채운_비밀_값은_응답의_어느_칸에서도_가린다():
    out = mcp_secrets.redact({'error': 'denied for sk-live-9999', 'tools': [{'description': 'echo sk-live-9999'}], 'n': 1}, ['sk-live-9999', 'ab'])
    assert out == {'error': f'denied for {mcp_secrets.REDACTED}', 'tools': [{'description': f'echo {mcp_secrets.REDACTED}'}], 'n': 1}


@pytest.mark.parametrize('key', ['lower', 'HYD-X', '', '9START'], ids=['소문자', '하이픈', '빈 이름', '숫자로 시작'])
def test_이름_규칙에_맞지_않는_비밀은_지우기도_거절한다(repo, key):
    with pytest.raises(SecretError) as refused:
        mcp_secrets.remove(repo, TENANT, key)
    assert refused.value.status == 422


def test_없는_비밀을_지우면_404(repo):
    with pytest.raises(SecretError) as refused:
        mcp_secrets.remove(repo, TENANT, 'NOT_STORED')
    assert refused.value.status == 404
