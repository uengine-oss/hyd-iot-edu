"""저장 기록의 직접 참조를 확인한다. 외부 서비스나 AI를 호출하지 않는다."""
import argparse
import json
from pathlib import Path


def check_link(label, source, field, target, target_field):
    """입력의 존재와 일치 여부를 구분해 연결 판정을 만든다.

    반환할 dict: link(관계 이름), state(확인/미확인/실패),
    reference(출발 참조 값), identity(도착 식별자), reason(판정 이유).
    호출부·입력 자료는 바꾸지 않는다. 조건과 이유는 직접 설계한다.
    """
    raise NotImplementedError("참조 비교 규칙을 먼저 설명한 뒤 이 함수를 구현하세요.")


def inspect_records(data):
    work = data.get('work_order', {})
    decision = data.get('decision', {})
    incident = data.get('incident', {})
    links = [
        check_link('작업지시 → 판단', work, 'decision_id', decision, 'id'),
        check_link('판단 → 사건', decision, 'incident_id', incident, 'id'),
        check_link('사건 → 경보', incident, 'alert_id', data.get('alert', {}), 'alertId'),
    ]
    states = [item['state'] for item in links]
    overall = '실패' if '실패' in states else ('미확인' if '미확인' in states else '확인')
    return {
        'state': overall,
        'links': links,
        'work_status': work.get('status'),
        'completed_at': work.get('completed_at'),
        'scope': '참조 연결의 검사 결과입니다. 명령 ACK나 실제 정비 완료를 판정하지 않습니다.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', default='recorded/case_a.json')
    parser.add_argument('--output', default='result/trace_result.json')
    args = parser.parse_args()
    result = inspect_records(json.loads(Path(args.input).read_text('utf-8')))
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for item in result['links']:
        print(f"{item['link']}: {item['state']} — {item['reason']}")
    print(f"전체 연결: {result['state']} / 작업지시 상태: {result['work_status']}")
    print(result['scope'])
    print(f'결과 저장: {destination}')


if __name__ == '__main__':
    main()
