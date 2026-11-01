"""Versioned message admission and recovery criteria, without a fallback sensor."""
import math


def validate(raw):
    policy=raw.get('alertPolicy')
    if policy is None:
        return
    if not isinstance(policy,dict) or not isinstance(policy.get('patterns'),dict) or not policy['patterns']:
        raise ValueError('alertPolicy.patterns에 명시 경보/회복 기준이 필요합니다')
    for pattern,c in policy['patterns'].items():
        if not isinstance(pattern,str) or not pattern.strip() or not isinstance(c,dict):
            raise ValueError('경보 패턴과 회복 기준 형식이 올바르지 않습니다')
        if not isinstance(c.get('tag'),str) or not c['tag'].strip() or c.get('op') not in ('<','>='):
            raise ValueError('회복 기준에는 tag와 지원 비교 연산(<, >=)이 필요합니다')
        limit=c.get('limit')
        if type(limit) not in (int,float) or not math.isfinite(limit) or c.get('requireClear') is not True:
            raise ValueError('회복 기준에는 유한 임계값과 requireClear=true가 필요합니다')
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
    criterion=(c['tag'],c['op'],c['limit']) if c else None
    target=policy['unsupported']
    return {'pattern':pattern,'route':'response' if criterion else 'triage','criterion':criterion,
            'definition':raw['processDefinitionId'],'version':raw['version'],
            'target':({'definition':raw['processDefinitionId'],'version':raw['version']} if criterion else target)}


def require_triage(defn):
    """A fallback is a human review, not an alternate path to unreviewed effects."""
    from . import engine
    from .approval_part import CARD_TOOL
    if not defn.activities or any(not engine.is_human(a) or a.get('tool')==CARD_TOOL
                                  or a.get('orchestration') not in engine.NO_MODE
                                  for a in defn.activities.values()):
        raise ValueError('미지원 경보 경로는 조치 선택/에이전트/서비스 없는 사람 검토여야 합니다')
