"""저장 기록의 직접 참조를 확인한다. 외부 서비스나 AI를 호출하지 않는다."""
import argparse
import json
from pathlib import Path


def check_link(label, source, field, target, target_field):
    reference = source.get(field)
    identity = target.get(target_field)
    if not reference or not identity:
        state, reason = '미확인', '참조 또는 도착 기록의 식별자가 없습니다.'
    elif reference != identity:
        state, reason = '실패', '참조와 도착 기록의 식별자가 다릅니다.'
    else:
        state, reason = '확인', '제공된 직접 참조와 식별자가 일치합니다.'
    return dict(link=label, state=state, reference=reference, identity=identity, reason=reason)


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
