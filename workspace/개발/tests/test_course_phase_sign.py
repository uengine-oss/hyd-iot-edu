"""강사 단계 선언 서명 도구(workspace/개발/scripts/course_phase_sign.py) — 학생 PC와 같은 판정(course_policy.load_phase)을 통과한 선언만 쓰는가.

키 · 선언 파일은 테스트 임시 폴더에만 만든다(저장소의 course_phase.json 은 건드리지 않는다).
"""
import base64
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import course_phase_sign as sign  # noqa: E402
from procsvc import course_policy  # noqa: E402

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


def public(private, padded):
    text = base64.urlsafe_b64encode(private.public_key().public_bytes_raw()).decode()
    return text if padded else text.rstrip('=')


@pytest.fixture
def key():
    return Ed25519PrivateKey.generate()


@pytest.mark.parametrize('padded', [True, False], ids=['PHASE_KEYS에_끝_등호가_있는_꼴', '끝_등호가_없는_꼴'])
def test_공개_키를_어느_꼴로_적어도_PBL_선언을_쓰고_학생_PC가_PBL로_읽는다(tmp_path, key, padded):
    out = tmp_path / 'course_phase.json'
    got = sign.write_phase(key, 'pbl', out, expires='2026-12-31T23:59:59+09:00', keys=(public(key, padded),), now=NOW)
    assert got.name == 'pbl'
    assert course_policy.load_phase(out, keys=(public(key, padded),), now=NOW).name == 'pbl'


def test_PHASE_KEYS에_없는_키로_서명하면_멈추고_선언_파일을_그대로_둔다(tmp_path, key):
    out = tmp_path / 'course_phase.json'
    out.write_text('원래 선언', encoding='utf8')
    other = Ed25519PrivateKey.generate()
    with pytest.raises(sign.SignError, match='PHASE_KEYS'):
        sign.write_phase(key, 'pbl', out, expires='2026-12-31T23:59:59+09:00', keys=(public(other, True),), now=NOW)
    assert out.read_text(encoding='utf8') == '원래 선언'
    assert sorted(p.name for p in tmp_path.iterdir()) == ['course_phase.json']


@pytest.mark.parametrize('expires', [(NOW - timedelta(days=1)).isoformat(), NOW.isoformat()], ids=['어제', '지금'])
def test_이미_지난_PBL_기한이면_멈추고_선언_파일을_그대로_둔다(tmp_path, key, expires):
    out = tmp_path / 'course_phase.json'
    out.write_text('원래 선언', encoding='utf8')
    with pytest.raises(sign.SignError, match='지나'):
        sign.write_phase(key, 'pbl', out, expires=expires, keys=(public(key, True),), now=NOW)
    assert out.read_text(encoding='utf8') == '원래 선언'


def test_시간대_없는_PBL_기한은_쓰기_전에_거절한다(tmp_path, key):
    with pytest.raises(sign.SignError, match='시간대'):
        sign.write_phase(key, 'pbl', tmp_path / 'course_phase.json', expires='2026-12-31T23:59:59', keys=(public(key, True),), now=NOW)
    assert not list(tmp_path.iterdir())


def test_수업_단계로_닫는_선언은_기한_없이_쓰고_학생_PC가_수업으로_읽는다(tmp_path, key):
    out = tmp_path / 'course_phase.json'
    assert sign.write_phase(key, 'course', out, keys=(public(key, False),), now=NOW).name == 'course'
    assert course_policy.load_phase(out, keys=(public(key, False),), now=NOW).name == 'course'


def test_keygen은_저장소_안에_비밀_키를_만들지_않는다():
    with pytest.raises(sign.SignError, match='저장소 안'):
        sign.keygen(sign.ROOT / 'it' / '시험키-만들지-않음.key')
    assert not (sign.ROOT / 'it' / '시험키-만들지-않음.key').exists()
