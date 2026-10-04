"""Immutable, durable action previews. Creating or loading one grants no consent.

SQLite stores review artifacts before returning them. Approval copies their exact
snapshot into the existing transactional Pg outbox. The work item transaction
owns consumption; retries use that committed outbox, never a mutable preview.
"""
from copy import deepcopy
import hashlib
import json
from uuid import uuid4
from hydcommon.timeutil import now_iso


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(',', ':'),allow_nan=False).encode()).hexdigest()


class DecisionReviews:
    def __init__(self, store, book, incidents, evaluate):
        self.store, self.book, self.incidents, self.evaluate = store, book, incidents, evaluate

    def _pending(self, decision_id, option_id):
        d = self.book.get(decision_id)
        if not d or d.get('state') != 'PENDING_APPROVAL':
            raise ValueError('검토할 대기 중 결정이 없습니다')
        inc = self.incidents.get((d.get('origin') or {}).get('incident'))
        if not inc or inc.asset != d.get('asset') or inc.state != 'AWAITING_APPROVAL':
            raise ValueError('이 사건은 현재 조치 검토 상태가 아닙니다')
        if not any(o.get('id')==option_id for o in d.get('options', [])):
            raise ValueError('결정에 없는 SOP입니다')
        return deepcopy(d)

    @staticmethod
    def _scope(d, option_id, scope):
        expected = dict(decision=d['id'],option=option_id,asset=d['asset'],incident=d['origin']['incident'])
        if any(k in scope and scope[k] != v for k,v in expected.items()):
            raise ValueError('검토 대상이 이 작업의 사건·설비와 다릅니다')
        return dict(scope, **expected)

    def create(self, decision_id, option_id, parameters, scope):
        source = self._pending(decision_id, option_id)
        fingerprint = digest(source)
        fresh = self.evaluate(source, option_id, parameters)
        if digest(self._pending(decision_id,option_id)) != fingerprint:
            raise ValueError('예측 중 원래 결정이 변경됐습니다. 다시 검토하세요')
        if (fresh.get('id'),fresh.get('asset'),fresh.get('origin')) != (source['id'],source['asset'],source.get('origin')):
            raise ValueError('예측 응답이 검토 대상과 일치하지 않습니다')
        if len(fresh.get('options', [])) != 1 or fresh['options'][0].get('id') != option_id:
            raise ValueError('예측 응답에 선택한 카드가 없습니다')
        if (fresh['options'][0].get('reviewed_choice') or {}).get('parameters') != parameters:
            raise ValueError('예측 응답의 조치값이 요청과 다릅니다')
        review_id = 'REV-' + str(uuid4())
        fresh = deepcopy(fresh)
        fresh['original_decision'] = source
        fresh['review_id'] = review_id
        review = {'id':review_id,'created':now_iso(),'scope':self._scope(source,option_id,scope),
                  'source_sha256':fingerprint,'snapshot':fresh,'execution_authorized':False}
        self.store.put_review(review)
        return deepcopy(review)

    def snapshot(self, review_id, decision_id, option_id, scope):
        source = self._pending(decision_id,option_id)
        review = self.store.get_review(review_id)
        if review['scope'] != self._scope(source,option_id,scope):
            raise ValueError('이 작업·사건·카드의 검토본이 아닙니다')
        if review['source_sha256'] != digest(source):
            raise ValueError('원래 결정이 변경됐습니다. 새 검토본이 필요합니다')
        return deepcopy(review['snapshot'])
