"""Read-only comparison of process, Incident, and actual CMMS receipts.

Run on a completed work-order instance. This probes identity/order, not physical
recovery or whether a particular maintenance SOP is appropriate.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import urllib.request


def get(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.load(response)


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')) if value else None


def compare(view, incident, transactions):
    variables = {row['key']: row.get('value') for row in view['instance']['variables_data']}
    wi = next(w for w in view['workitems'] if w['tool'] == 'enterprise:WO_CREATE' and w['status'] == 'DONE')
    output = wi['output']['work_order']
    tx = next((row for row in transactions if row.get('ref') == output.get('ref')
               and row.get('decision') == variables.get('decision_id')
               and row.get('asset') == variables.get('asset')), None)
    wo = incident.get('workOrder') or {}
    checks = [
        {'name': 'service output identifies an actual matching CMMS receipt',
         'passed': output.get('ok') is True and tx is not None},
        {'name': 'Incident exposes the same actual CMMS reference',
         'passed': bool(output.get('ref')) and wo.get('id') == output.get('ref'),
         'actual': wo.get('id'), 'expected': output.get('ref')},
        {'name': 'Incident closes only after the actual CMMS receipt',
         'passed': bool(tx and incident.get('closed') and timestamp(incident['closed']) >= timestamp(tx['t'])),
         'incident_closed': incident.get('closed'), 'cmms_created': tx and tx['t']},
        {'name': 'work item completes only after the actual CMMS receipt',
         'passed': bool(tx and wi.get('end_date') and timestamp(wi['end_date']) >= timestamp(tx['t'])),
         'task_completed': wi.get('end_date'), 'cmms_created': tx and tx['t']},
    ]
    return {'checks': checks, 'passed': sum(c['passed'] for c in checks), 'total': len(checks),
            'instance': view['instance']['proc_inst_id'], 'incident': incident['id'],
            'service_output': output, 'incident_work_order': wo, 'enterprise_receipt': tx}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('instance')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    view = get('http://localhost:8080/api/instances/' + args.instance)
    variables = {row['key']: row.get('value') for row in view['instance']['variables_data']}
    incident = get('http://localhost:8080/api/incidents/' + variables['incident'])
    transactions = get('http://localhost:8095/api/transactions')
    report = compare(view, incident, transactions)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for check in report['checks']:
        print(('PASS' if check['passed'] else 'FAIL') + ': ' + check['name'])
    print(f"{report['passed']}/{report['total']}")
    raise SystemExit(0 if report['passed'] == report['total'] else 1)


if __name__ == '__main__':
    main()
