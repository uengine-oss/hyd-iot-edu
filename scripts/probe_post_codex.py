"""Check deployed replay prevention and stopped-pump detection; preserve observations."""
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

OUT = Path('.evidence/reaudit/post-codex-live.json')
INSTANCE = 'anomaly_response.1dfcaa53-0ba0-4d6d-844d-3a9ad4bb6035'


def request(port, path, data=None):
    req = urllib.request.Request(f'http://localhost:{port}{path}',
        data=None if data is None else json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def main():
    report = {'checks': {}, 'samples': []}
    def check(name, passed, detail):
        report['checks'][name] = {'passed': bool(passed), 'detail': detail}
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(name, 'PASS' if passed else 'FAIL', flush=True)
        assert passed, name
    try:
        mode = request(8080, '/api/process/mode')[1]
        check('baseline_mode_restored', mode.get('agent_bridge') == 'legacy' and mode.get('time_scale') == 20, mode)
        view = request(8080, '/api/instances/' + INSTANCE)[1]
        variables = {v['key']: v.get('value') for v in view['instance']['variables_data']}
        alert = {'alertId': variables['alert_id'], 'asset': variables['asset'], 'pattern': variables['pattern']}
        status, replay = request(8080, '/api/instances/start', {'alert': alert})
        check('completed_replay_rejected', view['instance']['status'] == 'COMPLETED' and status == 409, replay)
        request(8000, '/api/reset', {})
        status, command = request(8000, '/api/manual', {'asset': 'HYD-02', 'writes': {'Stop': 1}})
        check('actual_plc_stop', status == 200 and command.get('result') == 'DONE', command)
        # 20 wall seconds = 400 sim seconds, longer than 60 sim-second hold.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            time.sleep(2)
            plant = request(8000, '/api/state')[1]
            detector = request(8092, '/api/detector/state')[1]
            report['samples'].append({'plant': plant['units']['HYD-02'], 'detector': detector['assets']['HYD-02']})
        final = report['samples'][-1]
        check('stopped_pump_no_false_raise',
              final['plant']['status']['state'] == 'STOP'
              and final['plant']['tags']['FS1'] == 0
              and final['detector']['plc_state'] == 'STOP'
              and all(s['detector']['patterns']['PUMP_LEAKAGE']['phase'] == 'IDLE' for s in report['samples']), final)
    finally:
        report['reset'] = request(8000, '/api/reset', {})[0]
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
