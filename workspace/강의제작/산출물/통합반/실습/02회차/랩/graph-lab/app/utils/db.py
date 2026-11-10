"""실습 폴더 전용 Neo4j 준비. 포털 DB에 접속하지 않는다."""
from pathlib import Path
import json,subprocess,sys,time,urllib.request,urllib.parse,uuid,webbrowser
HERE=Path(__file__).resolve().parents[2]
STATE=HERE/'.lab_connection.json'
IMAGE='neo4j:5.26-community'

def docker(*args):
    result=subprocess.run(['docker',*args],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode:raise RuntimeError(result.stderr.strip() or 'Docker 실행을 확인하세요.')
    return result.stdout.strip()

def create():
    """이 폴더 전용 새 컨테이너. 라벨 hyd.practice.id가 .lab_connection.json의 id와 같아야 다음에 다시 쓴다."""
    token=uuid.uuid4().hex[:12];name='hyd-student-'+token
    docker('run','-d','--name',name,'--label','hyd.practice.id='+token,
           '--memory=1g','-p','127.0.0.1::7474','-p','127.0.0.1::7687',
           '-e','NEO4J_AUTH=none','-e','NEO4J_server_memory_heap_initial__size=256m',
           '-e','NEO4J_server_memory_heap_max__size=512m','-e','NEO4J_server_memory_pagecache_size=128m',IMAGE)
    return {'id':token,'container':name,'username':'neo4j','password':'','scope':'이 실습 폴더 전용 로컬 DB'}

def prepare():
    state=None;renewed=False
    if STATE.exists():
        state=json.loads(STATE.read_text(encoding='utf-8'))
        # 폴더를 USB 등으로 다른 PC에 옮기면 .lab_connection.json만 오고 컨테이너는 오지 않는다. 그때는 새 DB를 만들되, 그 사실을 알린다.
        if not docker('ps','-a','-q','--filter','name=^/'+state['container']+'$'):
            print(f'이 폴더의 랩 DB({state["container"]})가 이 PC의 Docker에 없습니다. 폴더를 다른 PC에서 옮겨 왔거나 그 DB가 지워진 경우입니다.\n'
                  '이 폴더 전용 랩 DB를 새로 만듭니다. 새 DB는 비어 있으니, 저장해 둔 적재 · 수정 파일을 같은 순서로 다시 실행하세요.')
            state=None;renewed=True
        else:
            info=json.loads(docker('inspect',state['container']))[0]
            if info['Config']['Labels'].get('hyd.practice.id')!=state['id']:
                raise RuntimeError('이 실습에서 만든 DB가 아닙니다. .lab_connection.json을 확인하세요.')
            if not info['State']['Running']:docker('start',state['container'])
    if state is None:state=create()
    # Docker의 임의 호스트 포트는 재시작 후 달라질 수 있다.
    # 저장된 주소 대신 현재 실행 중인 컨테이너의 매핑을 사용한다.
    info=json.loads(docker('inspect',state['container']))[0]
    ports=info['NetworkSettings']['Ports']
    http=ports['7474/tcp'][0]['HostPort'];bolt=ports['7687/tcp'][0]['HostPort']
    connect=urllib.parse.quote(f'bolt://127.0.0.1:{bolt}',safe='')
    state.update(browser=f'http://127.0.0.1:{http}/browser/?connectURL={connect}',
                 http=f'http://127.0.0.1:{http}',bolt=f'bolt://127.0.0.1:{bolt}')
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
    if renewed:print('새로 만든 랩 DB라 비어 있습니다. 적재부터 다시 실행하세요.')
    return state

if __name__=='__main__':
    try:
        state=prepare()
        if '--no-open' not in sys.argv:webbrowser.open(state['browser'])
    except (OSError,ValueError,KeyError,RuntimeError) as e:
        print('랩 DB 준비 확인 필요: '+str(e));sys.exit(1)
