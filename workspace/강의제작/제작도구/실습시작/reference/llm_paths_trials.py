"""언제: lab_llm 경로 API 변경 뒤 실제 자식 프로세스로 기존/새 랩의 무료 응답 흐름을 확인할 때.

시험 입력임을 밝힌 문자열만 붙여 넣으며 모델·네트워크·실제 인증 파일은 사용하지 않는다.
python reference/llm_paths_trials.py --out 작업/<작업>/판정/모델경로검사.json
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent/'lab_llm.py'
REQUEST = '무모델 경로 검사용 요청입니다. 실제 관측이나 모델 실행이 아닙니다.'
RESPONSE = '{"finish":{"summary":"무모델 시험 문자열: 현재값·35℃·0과 값 없음 구분"}}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    results = []

    def check(name, value):
        results.append({'test': name, 'passed': bool(value)})
        assert value, name

    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    with tempfile.TemporaryDirectory(prefix='_llm_paths_', dir=args.out.parent) as temp:
        base = Path(temp).resolve()
        assert base.is_relative_to(args.out.parent.resolve())
        for project in (False, True):
            label = '새 프로젝트' if project else '기존 랩'
            lab = base/('project' if project else 'legacy')
            client = lab/('app/utils/llm_client.py' if project else 'llm_client.py')
            client.parent.mkdir(parents=True)
            shutil.copyfile(SOURCE, client)
            if project:
                entry = lab/'run.py'
                entry.write_text('from pathlib import Path\nfrom app.utils import llm_client\n'
                                 'llm_client.configure(Path(__file__).resolve().parent, project=True)\n'
                                 'raise SystemExit(llm_client.main())\n', encoding='utf-8')
                setup = 'from pathlib import Path; from app.utils import llm_client as m; m.configure(Path.cwd(), project=True); '
            else:
                entry = client
                setup = 'import llm_client as m; '
            command = setup+f'r=m.ask({REQUEST!r}); print("RESULT_JSON="+__import__("json").dumps(r,ensure_ascii=False))'
            call = lambda tail, data=None: subprocess.run([sys.executable, *tail], cwd=lab, env=env,
                                                          input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
            first = call(['-c', command])
            request_dir = lab/('output/model_requests' if project else '결과/요청')
            response_dir = lab/('output/model_responses' if project else '결과/응답_기록')
            paths = list(request_dir.glob('*.md'))
            check(label+' 키 없이 요청만 기록', first.returncode == 2 and len(paths) == 1 and not response_dir.exists())
            digest = paths[0].stem
            stdout = first.stdout.decode('utf-8')
            expected_command = 'python run.py' if project else 'python llm_client.py'
            check(label+' 실제 실행 진입점 안내', f'{expected_command} --paste {digest}' in stdout)
            check(label+' UTF8 요청 보존', REQUEST in paths[0].read_text(encoding='utf-8'))
            pasted = call([str(entry), '--paste', digest, '--model', 'no-model-test'], RESPONSE.encode('utf-8'))
            records = list(response_dir.glob('*.json'))
            check(label+' 실제 stdin 붙여넣기 저장', pasted.returncode == 0 and len(records) == 1)
            stored = json.loads(records[0].read_text(encoding='utf-8'))
            check(label+' 응답·방법 구분', stored['response_text'] == RESPONSE and stored['method'] == '채팅으로 받음' and stored['response_raw'] is None)
            record_hash = hashlib.sha256(records[0].read_bytes()).hexdigest()
            resumed = call(['-c', command])
            reply_line = next((line[len('RESULT_JSON='):] for line in resumed.stdout.decode('utf-8').splitlines() if line.startswith('RESULT_JSON=')), None)
            reply = json.loads(reply_line) if reply_line else {}
            check(label+' 같은 요청에서 보낸 척하지 않고 재사용', resumed.returncode == 0 and reply.get('sent') is False and reply.get('response_text') == RESPONSE)
            check(label+' 응답 파일 중복 생성 없음', len(list(response_dir.glob('*.json'))) == 1 and hashlib.sha256(records[0].read_bytes()).hexdigest() == record_hash)
            counted = call([str(entry), '--count'])
            check(label+' 호출/붙여넣기 계수 구분', counted.returncode == 0 and '모델 서버로 보낸 기록 0개' in counted.stdout.decode('utf-8') and '채팅으로 받은 기록 1개' in counted.stdout.decode('utf-8'))
            check(label+' 환경 파일 생성 없음', not (lab/'.env').exists())
            if project:
                check('새 프로젝트의 중첩 출력 오생성 없음', not (lab/'app/utils/output').exists() and not (lab/'결과').exists())
        # 같은 모듈의 루트를 바꿨을 때 이전 요청 기록을 다른 프로젝트에 섞지 않는다.
        switched = base/'project_two'; switched.mkdir()
        command = setup + f'm.configure({str(switched)!r}, project=True); m.ask({REQUEST!r})'
        different = call(['-c', command])
        check('루트 변경 시 다른 프로젝트 응답을 재사용하지 않음', different.returncode == 2 and len(list((switched/'output/model_requests').glob('*.md'))) == 1 and not (switched/'output/model_responses').exists())
    report = {'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'actual_model_calls': 0,
              'method': '키 없는 실제 자식 프로세스·파일·stdin 경로 검사', 'tests': results,
              'passed': sum(x['passed'] for x in results), 'failed': sum(not x['passed'] for x in results)}
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'검사 {report["passed"]} · 실패 {report["failed"]} · 실제 모델 호출 0')


if __name__ == '__main__':
    main()
