"""계정 채팅 독립검토 A1/A2 고침의 무모델 검증."""
from pathlib import Path
import argparse
import contextlib
import io
import json
import subprocess
import sys
import tempfile
from unittest.mock import patch

import account_chat as m

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True)
options = parser.parse_args()
real_run = subprocess.run

IDENTITY = '01234567-89ab-cdef-0123-456789abcdef'
def events(item=None):
    rows = [{'type':'thread.started','thread_id':IDENTITY}, {'type':'turn.started'},
            {'type':'item.completed','item':item or {'id':'msg','type':'agent_message','text':'tokens used\n0\nexec\nnot an event'}},
            {'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':2,'cached_input_tokens':0}}]
    return '\n'.join(json.dumps(row) for row in rows).encode()

results=[]
def check(name, value):
    results.append({'test':name,'passed':bool(value)})
    assert value, name

check('응답 문자열은 이벤트가 아님', not m.json_events(events())['actions'])
for kind in ('command_execution','mcp_tool_call','web_search','file_change','unknown'):
    check(kind+' 사용 검출', bool(m.json_events(events({'id':'x','type':kind}))['actions']))
check('깨진 이벤트 거절', bool(m.json_events(b'not json')['errors']))

with tempfile.TemporaryDirectory(prefix='hyd-account-trial-') as td:
    base=Path(td)
    home=base/'home'; (home/'sessions').mkdir(parents=True)
    (home/'auth.json').touch()  # 빈 시험용 파일이며 실제 계정 파일을 열지 않는다.
    rollout=home/'sessions'/f'rollout-2026-{IDENTITY}.jsonl'
    rollout.write_text(json.dumps({'type':'turn_context','payload':{'model':'gpt-6-luna','effort':'medium'}}),encoding='utf-8')
    check('이번 세션 설정 읽기', m.turn_settings(home,IDENTITY)=={'model':'gpt-6-luna','reasoning_effort':'medium'})
    for mode in ('success','project_success','paste_timeout','paste_oserror','tool_used','call_oserror'):
        lab=base/mode
        project = mode == 'project_success'
        requests = lab / ('output/model_requests' if project else '결과/요청')
        requests.mkdir(parents=True)
        for name in (('run.py','README.md','AGENTS.md','app/utils/llm_client.py') if project else ('START.md','llm_client.py')):
            path=lab/name; path.parent.mkdir(parents=True,exist_ok=True); path.touch()
        (requests/'abcdef012345.md').write_text('요청',encoding='utf-8')
        out=base/(mode+'-out')
        def fake_run(cmd,**kwargs):
            if 'exec' in cmd:
                if mode in ('success','project_success'):
                    check('계정 채팅에서 호스트 셸 제외', 'features.shell_tool=false' in cmd)
                if mode=='call_oserror': raise OSError('모형 실행 오류')
                Path(cmd[cmd.index('-o')+1]).write_text('{"finish":{"summary":"현재 관측 35℃"}}',encoding='utf-8')
                item={'id':'tool','type':'mcp_tool_call'} if mode=='tool_used' else None
                return subprocess.CompletedProcess(cmd,0,events(item),b'')
            if mode=='paste_timeout': raise subprocess.TimeoutExpired(cmd,30,output=b'partial')
            if mode=='paste_oserror': raise OSError('모형 붙여넣기 오류')
            if mode in ('success','project_success'):
                check(mode+' 학생 붙여넣기 진입점', cmd[1] == ('run.py' if project else 'llm_client.py'))
                # 부모 로케일에 기대지 않고 실제 파이프의 한글/단위가 보존되는지 본다.
                p = real_run([sys.executable, '-c', 'import sys; sys.stdout.buffer.write(sys.stdin.read().encode("utf-8"))'],
                             env=kwargs['env'], input=kwargs['input'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                check('자식 stdin UTF-8 바이트 보존', p.returncode == 0 and p.stdout == kwargs['input'])
            return subprocess.CompletedProcess(cmd,0,b'pasted',b'')
        args=['account_chat.py',str(lab),'abcdef012345','--out',str(out),'--codex-home',str(home),
              '--codex-bin','codex.exe','--model','gpt-6-luna','--reasoning','medium','--max-calls','1']
        with patch.object(sys,'argv',args), patch.object(m,'SPARE',base/'isolated'), \
             patch.object(m.shutil,'which',return_value='codex.exe'), patch.object(m.subprocess,'run',side_effect=fake_run), \
             contextlib.redirect_stdout(io.StringIO()):
            try: m.main()
            except SystemExit: pass
        report=json.loads((out/'abcdef012345/실행.json').read_text(encoding='utf-8'))
        check(mode+' 보고 보존·판정', report['pasted']==(mode in ('success','project_success')))
        if mode.startswith('paste_'):
            check(mode+' 정확한 실패',report['paste_exit']==('timeout' if mode=='paste_timeout' else 'launch_error'))
    invalid=base/'incomplete_project'; invalid.mkdir(); (invalid/'run.py').touch()
    try:
        m.student_interface(invalid)
    except ValueError:
        check('불완전 프로젝트 실행 거절', True)
    else:
        check('불완전 프로젝트 실행 거절', False)

out=options.out
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({'actual_model_calls':0,'tests':results,'passed':len(results),'failed':0},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'검사 {len(results)} · 실패 0 · 실제 모델 호출 0')
