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
args = parser.parse_args()

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
    for mode in ('success','paste_timeout','paste_oserror','tool_used','call_oserror'):
        lab=base/mode; (lab/'결과/요청').mkdir(parents=True)
        (lab/'START.md').touch(); (lab/'llm_client.py').touch()
        (lab/'결과/요청/abcdef012345.md').write_text('요청',encoding='utf-8')
        out=base/(mode+'-out')
        def fake_run(cmd,**kwargs):
            if 'exec' in cmd:
                if mode=='call_oserror': raise OSError('모형 실행 오류')
                Path(cmd[cmd.index('-o')+1]).write_text('{"finish":{}}',encoding='utf-8')
                item={'id':'tool','type':'mcp_tool_call'} if mode=='tool_used' else None
                return subprocess.CompletedProcess(cmd,0,events(item),b'')
            if mode=='paste_timeout': raise subprocess.TimeoutExpired(cmd,30,output=b'partial')
            if mode=='paste_oserror': raise OSError('모형 붙여넣기 오류')
            return subprocess.CompletedProcess(cmd,0,b'pasted',b'')
        args=['account_chat.py',str(lab),'abcdef012345','--out',str(out),'--codex-home',str(home),
              '--codex-bin','codex.exe','--model','gpt-6-luna','--reasoning','medium','--max-calls','1']
        with patch.object(sys,'argv',args), patch.object(m,'SPARE',base/'isolated'), \
             patch.object(m.shutil,'which',return_value='codex.exe'), patch.object(m.subprocess,'run',side_effect=fake_run), \
             contextlib.redirect_stdout(io.StringIO()):
            try: m.main()
            except SystemExit: pass
        report=json.loads((out/'abcdef012345/실행.json').read_text(encoding='utf-8'))
        check(mode+' 보고 보존·판정', report['pasted']==(mode=='success'))
        if mode.startswith('paste_'):
            check(mode+' 정확한 실패',report['paste_exit']==('timeout' if mode=='paste_timeout' else 'launch_error'))

out=args.out
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({'actual_model_calls':0,'tests':results,'passed':len(results),'failed':0},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'검사 {len(results)} · 실패 0 · 실제 모델 호출 0')
