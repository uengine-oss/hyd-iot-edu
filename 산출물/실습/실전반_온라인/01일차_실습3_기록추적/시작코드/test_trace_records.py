"""누락과 잘못된 연결을 정상으로 판정하지 않는지 검증한다."""
import copy
import json
from pathlib import Path
import unittest
from trace_records import inspect_records


class TraceRecordsTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((Path(__file__).parent/'recorded/case_a.json').read_text('utf-8'))

    def test_actual_excerpt_has_only_one_proven_link(self):
        result = inspect_records(self.data)
        self.assertEqual([x['state'] for x in result['links']], ['확인', '미확인', '미확인'])
        self.assertEqual(result['state'], '미확인')
        self.assertEqual(result['work_status'], '배정됨')
        self.assertIsNone(result['completed_at'])

    def test_unrelated_decision_is_rejected(self):
        changed = copy.deepcopy(self.data)
        changed['decision']['id'] = 'synthetic_other_decision'
        self.assertEqual(inspect_records(changed)['state'], '실패')

    def test_missing_reference_is_not_guessed_from_context(self):
        self.data['work_order'].pop('decision_id')
        self.assertEqual(inspect_records(self.data)['links'][0]['state'], '미확인')

    def test_empty_identifiers_do_not_match(self):
        self.data['work_order']['decision_id'] = ''
        self.data['decision']['id'] = ''
        self.assertEqual(inspect_records(self.data)['links'][0]['state'], '미확인')


if __name__ == '__main__':
    unittest.main()
