"""조사 붙이기(common/hydcommon/words.py) — 학생에게 가는 문장에 「단계이(가)」 · 「TAN이(가)」 · 「…을(를)」 같은 두 꼴이 나가지 않게."""
import pytest

from hydcommon.words import josa


@pytest.mark.parametrize('word, particle, expect', [
    ('단계', '이', '단계가'), ('시작', '이', '시작이'), ('산가 TAN', '이', '산가 TAN이'), ('수분 함량', '가', '수분 함량이'),
    ('「원인 진단 · 냉각 조치 제안」', '을', '「원인 진단 · 냉각 조치 제안」을'), ('「인계안 작성 · 보완 2」', '을', '「인계안 작성 · 보완 2」를'),
    ("'SOP-COOL-11 팬 최대 운전'", '을', "'SOP-COOL-11 팬 최대 운전'을"), ('부하 70 %', '를', '부하 70 %를'),
    ('HYD-01', '으로', 'HYD-01로'), ('설비 HYD-03', '로', '설비 HYD-03으로'), ('팔', '으로', '팔로'), ('검수', '은', '검수는'),
    ('hyd-dmn', '이', 'hyd-dmn이'), ('query', '는', 'query는'),
], ids=lambda v: str(v))
def test_마지막_글자의_소리에_맞는_조사를_붙인다(word, particle, expect):
    assert josa(word, particle) == expect


def test_소리를_알_수_없는_끝_글자에는_틀린_조사를_내지_않고_두_꼴을_함께_적는다():
    assert josa('★', '이') == '★이(가)' and josa('', '을') == '을(를)'
