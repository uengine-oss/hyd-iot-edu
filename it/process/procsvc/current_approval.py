"""Fail-closed adapter to current graph and authoritative source assessment."""
import json
import os
import urllib.error
import urllib.request
from copy import deepcopy


class ApprovalReviewRequired(ValueError):
    """A completed source assessment explicitly refuses the saved consent."""
    def __init__(self, report):
        self.report = deepcopy(report)
        super().__init__('현재 조건에서 승인을 보류합니다: ' + '; '.join(report.get('reasons') or ['새 판단과 승인이 필요합니다']))


def check(decision, option, role):
    request = urllib.request.Request(
        os.getenv('AGENT_URL', 'http://agent:8091') + '/api/agent/approval-check',
        data=json.dumps(dict(decision=decision, option=option, role=role), ensure_ascii=False).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            report = json.loads(response.read())
    except (OSError, ValueError) as e:
        raise ValueError('현재 승인 조건을 확인할 수 없습니다. 원천 연결을 확인하고 다시 판단하세요') from e
    if not isinstance(report, dict) or report.get('decision') != decision['id'] or report.get('option') != option:
        raise ValueError('현재 조건 검사 응답이 승인 대상과 일치하지 않습니다')
    return report


def require(checker, decision, option, role):
    report = checker(decision, option, role)
    if isinstance(report, dict) and report.get('allowed') is False:
        raise ApprovalReviewRequired(report)
    if not isinstance(report, dict) or report.get('allowed') is not True:
        reasons = report.get('reasons') if isinstance(report, dict) else None
        raise ValueError('현재 조건에서 승인을 보류합니다: ' + '; '.join(reasons or ['검사 결과를 확인할 수 없습니다']))
    return report


def preview(decision, option, parameters):
    request = urllib.request.Request(os.getenv('AGENT_URL','http://agent:8091')+'/api/agent/choice-preview',
        data=json.dumps(dict(decision=decision,option=option,parameters=parameters),ensure_ascii=False).encode(),
        headers={'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(request,timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get('detail')
        except (ValueError,AttributeError):
            detail = None
        raise ValueError(str(detail or '현재 조건으로 새 예측을 만들 수 없습니다')) from exc
    except (OSError,ValueError) as exc:
        raise ValueError('예측 원천 연결을 확인할 수 없습니다') from exc
