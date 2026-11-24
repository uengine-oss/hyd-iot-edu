"""Versioned message admission and recovery criteria, without a fallback sensor.

alertPolicy.patterns = 이 흐름이 받는 경보 종류(패턴 코드) → 회복 계약. 회복은 언제나 원천의 해제(CLEAR — requireClear: true)이고, 시계열
회복 기준(tag · op · limit — 가상 설비 시계열 tag_1s 의 태그)은 선택이다. 기준이 있으면 효과 확인(재관측)이 그 값까지 보고, 없으면 해제만이
회복이다 — 그런 경보의 흐름에는 시계열을 읽는 효과 확인을 두지 못한다(bpmn_import.unobservable_patterns). 경보 종류는 학생 흐름이 스스로
선언할 수 있다(학생 시스템이 보내는 경보 — 감지기 경보와 같은 계약). 기준을 채우려고 시계열에 없는 태그를 지어 넣지 않는다."""
import math
import re

#: 경보 종류(패턴 코드)의 꼴 — 감지기 · 업무 감시 · 사람 입력 · 학생 시스템이 같은 꼴을 쓴다(대문자 · 숫자 · 밑줄)
PATTERN_RE = re.compile(r'^[A-Z][A-Z0-9_]{1,63}$')


def validate(raw):
    policy=raw.get('alertPolicy')
    if policy is None:
        return
    if not isinstance(policy,dict) or not isinstance(policy.get('patterns'),dict) or not policy['patterns']:
        raise ValueError('alertPolicy.patterns에 이 흐름이 받는 경보 종류가 필요합니다')
    for pattern,c in policy['patterns'].items():
        if not isinstance(pattern,str) or not PATTERN_RE.match(pattern) or not isinstance(c,dict):
            raise ValueError(f'경보 종류 {pattern!r}의 꼴이 올바르지 않습니다 — 대문자로 시작하는 영문 대문자 · 숫자 · 밑줄(2~64자), 회복 계약은 객체')
        if c.get('requireClear') is not True:
            raise ValueError(f'경보 {pattern}의 회복 계약에는 requireClear=true(원천의 해제)가 필요합니다')
        if any(k in c for k in ('tag','op','limit')):
            if not isinstance(c.get('tag'),str) or not c['tag'].strip() or c.get('op') not in ('<','>='):
                raise ValueError(f'경보 {pattern}의 시계열 회복 기준에는 tag와 지원 비교 연산(<, >=)이 필요합니다')
            limit=c.get('limit')
            if type(limit) not in (int,float) or not math.isfinite(limit):
                raise ValueError(f'경보 {pattern}의 시계열 회복 기준에는 유한 임계치가 필요합니다')
        extra=sorted(set(c)-{'tag','op','limit','requireClear','name'})
        if extra:
            raise ValueError(f'경보 {pattern}의 회복 계약에 모르는 칸이 있습니다: {", ".join(extra)}')
        if 'name' in c and (not isinstance(c['name'],str) or not c['name'].strip() or len(c['name'])>80):
            raise ValueError(f'경보 {pattern}의 이름(name)은 80자 이내 글입니다')
    fallback=policy.get('unsupported')
    if not isinstance(fallback,dict) or any(not isinstance(fallback.get(k),str) or not fallback[k].strip() for k in ('definition','version')):
        raise ValueError('미지원 경보의 사람 검토 정의/버전을 지정하세요')


def for_definition(raw,pattern):
    """경보 하나를 이 정의가 받는 길. 회복 기준은 정의의 alertPolicy 하나에서만 온다 — 정책이 없는 정의는 경보를 받지 않는다(코드 상수 기준으로
    대신하지 않는다)."""
    policy=raw.get('alertPolicy')
    if policy is None:
        raise ValueError(f"흐름 {raw.get('processDefinitionId')} {raw.get('version')}에는 경보 정책(alertPolicy)이 없어 경보를 받을 수 없습니다 — "
                         "경보 정책이 있는 판본을 배포하세요")
    c=policy['patterns'].get(pattern) if isinstance(pattern,str) else None
    criterion=(c['tag'],c['op'],c['limit']) if c and c.get('tag') else None      # 없으면 회복은 원천의 해제뿐(모듈 머리말)
    target=policy['unsupported']
    return {'pattern':pattern,'route':'response' if c is not None else 'triage','criterion':criterion,
            'definition':raw['processDefinitionId'],'version':raw['version'],
            'target':({'definition':raw['processDefinitionId'],'version':raw['version']} if c is not None else target)}


def require_triage(defn):
    """A fallback is a human review, not an alternate path to unreviewed effects."""
    from . import engine
    from .approval_part import CARD_TOOL
    if not defn.activities or any(not engine.is_human(a) or a.get('tool')==CARD_TOOL
                                  or a.get('orchestration') not in engine.NO_MODE
                                  for a in defn.activities.values()):
        raise ValueError('미지원 경보 경로는 조치 선택/에이전트/서비스 없는 사람 검토여야 합니다')
