"""추출 결과 다시 쓰기의 열쇠(procsvc/manual_cache.py) — 같은 원문 · 파서 · 카탈로그 · 구간 · 설정 판본이면 같은 열쇠, 하나라도 다르면 다른 열쇠.
열쇠는 강사 쪽이 준 범위(scope) · 설정(profile)이 있어야 만든다(요청 본문에서 베끼지 않는다). 처리 건 쪽(start · result)은 test_manual_api 가 본다."""
import pytest

import class_knowledge
from procsvc import manual_cache
from procsvc.manual_sources import ManualSources

HM8 = next(i for i in class_knowledge.reviewed() if i['doc'] == 'HM-8')
PROFILE = {'model': 'reviewed-source-cache', 'revision': 'r1'}


@pytest.fixture
def source(tmp_path):
    return ManualSources(tmp_path / 'm.sqlite3').save('hyd', HM8['filename'], HM8['raw'])


def key(source, **over):
    args = dict(tenant='hyd', source=source, catalog={'parts': []}, scope='provided-manuals/x', profile=PROFILE)
    args.update(over)
    return manual_cache.identity(args.pop('tenant'), args.pop('source'), args.pop('catalog'), **args)


def test_같은_입력이면_같은_열쇠다(source):
    assert key(source) == key(source) and len(key(source)) == 64


@pytest.mark.parametrize('over', [dict(tenant='other'), dict(catalog={'parts': ['p']}), dict(scope='provided-manuals/y'),
                                  dict(profile={'model': 'reviewed-source-cache', 'revision': 'r2'}),
                                  dict(feedback={'by': '강사', 'items': [{'target': 't', 'verdict': 'OK'}]})],
                         ids=['교육 공간', '카탈로그', '승인 범위', '설정 판본', '검토 의견'])
def test_하나라도_다르면_다른_열쇠다(source, over):
    assert key(source, **over) != key(source)


def test_같은_글이라도_파일_형식이_다르면_원문_지문이_다르다(tmp_path):
    archive = ManualSources(tmp_path / 'm.sqlite3')
    md = archive.save('hyd', HM8['filename'], HM8['raw'])
    txt = archive.save('hyd', HM8['filename'].replace('.md', '.txt'), HM8['raw'])
    assert md['sha256'] == txt['sha256'] and manual_cache.source_fingerprint(md) != manual_cache.source_fingerprint(txt)


@pytest.mark.parametrize('over, says', [(dict(scope=''), '승인 범위'), (dict(profile={'model': 'm'}), '설정 판본'), (dict(profile=None), '설정 판본')])
def test_강사_쪽_범위와_설정_판본_없이는_열쇠를_만들지_않는다(source, over, says):
    with pytest.raises(ValueError, match=says):
        key(source, **over)
