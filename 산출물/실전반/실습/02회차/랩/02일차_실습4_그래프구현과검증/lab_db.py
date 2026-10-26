"""실습 폴더 전용 Neo4j 준비. 포털 DB에 접속하지 않는다."""
from pathlib import Path
import json,subprocess,sys,time,urllib.request,uuid,webbrowser
HERE=Path(__file__).resolve().parent
STATE=HERE/'랩_연결.json'
IMAGE='neo4j:5.26-community'

def docker(*args):
    result=subprocess.run(['docker',*args],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode:raise RuntimeError(result.stderr.strip() or 'Docker 실행을 확인하세요.')
    return result.stdout.strip()

def prepare():
    if STATE.exists():
        state=json.loads(STATE.read_text(encoding='utf-8'))
        info=json.loads(docker('inspect',state['container']))[0]
        if info['Config']['Labels'].get('hyd.practice.id')!=state['id']:
            raise RuntimeError('이 실습에서 만든 DB가 아닙니다. 랩_연결.json을 확인하세요.')
        if not info['State']['Running']:docker('start',state['container'])
    else:
        token=uuid.uuid4().hex[:12];name='hyd-student-'+token
        docker('run','-d','--name',name,'--label','hyd.practice.id='+token,
               '--memory=1g','-p','127.0.0.1::7474','-p','127.0.0.1::7687',
               '-e','NEO4J_AUTH=none','-e','NEO4J_server_memory_heap_initial__size=256m',
               '-e','NEO4J_server_memory_heap_max__size=512m','-e','NEO4J_server_memory_pagecache_size=128m',IMAGE)
        info=json.loads(docker('inspect',name))[0]
        ports=info['NetworkSettings']['Ports']
        http=ports['7474/tcp'][0]['HostPort'];bolt=ports['7687/tcp'][0]['HostPort']
        state={'id':token,'container':name,'browser':f'http://127.0.0.1:{http}/browser/',
               'http':f'http://127.0.0.1:{http}','bolt':f'bolt://127.0.0.1:{bolt}',
               'username':'neo4j','password':'','scope':'이 실습 폴더 전용 로컬 DB'}
        STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    deadline=time.monotonic()+90
    while True:
        try:
            with urllib.request.urlopen(state['http'],timeout=3) as response:
                if response.status==200:break
        except (OSError,TimeoutError):pass
        if time.monotonic()>deadline:raise RuntimeError('DB 시작 대기 시간을 넘었습니다. 같은 명령으로 다시 확인하세요.')
        time.sleep(1)
    print('랩 DB 준비 완료\nBrowser: '+state['browser']+'\nConnect URL: '+state['bolt']+'\nUsername: neo4j / Password: 비워 둠')
    return state

if __name__=='__main__':
    try:
        state=prepare()
        if '--no-open' not in sys.argv:webbrowser.open(state['browser'])
    except (OSError,ValueError,KeyError,RuntimeError) as e:
        print('랩 DB 준비 확인 필요: '+str(e));sys.exit(1)
