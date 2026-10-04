"""Test-only transparent proxy: change real MES before one decision's command check.

Never replaces approval results. The real agent evaluates every request. An
explicit arm file restricts the decision/order/value and records original data.
Run only in the temporary acceptance-test Compose service, without host ports.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import psycopg

ROOT=Path('/evidence')
LOCK=threading.Lock()
DSN='postgresql://postgres:postgres@host.docker.internal:54322/postgres'


def save(name,value):
    path=ROOT/(name+'.json');temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');temporary.replace(path)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):self.forward()
    def do_POST(self):self.forward()
    def log_message(self,*args):pass
    def forward(self):
        body=self.rfile.read(int(self.headers.get('Content-Length',0)))
        with LOCK:
            arm_path=ROOT/'proxy-arm.json';count=None
            try:
                if self.path=='/api/agent/approval-check' and arm_path.exists():
                    arm=json.loads(arm_path.read_text(encoding='utf8'))
                    payload=json.loads(body)
                    if payload['decision']['id']==arm['decision']:
                        history=ROOT/'proxy-progress.json'
                        state=json.loads(history.read_text(encoding='utf8')) if history.exists() else {'checks':0,'mutated':False}
                        state['checks']+=1;count=state['checks']
                        save('proxy-progress',state)
                        if count>=3 and not state['mutated']:
                            source=json.loads((ROOT/'source-before.json').read_text(encoding='utf8'))
                            with psycopg.connect(DSN) as conn:
                                row=conn.execute('select due_in_h from ent.production_orders where order_id=%s for update',(source['order_id'],)).fetchone()
                                if not row or float(row[0]) not in (source['due'],source['changed_due']):
                                    raise RuntimeError('MES changed outside this fixture; refusing overwrite')
                                conn.execute('update ent.production_orders set due_in_h=%s where order_id=%s',(source['changed_due'],source['order_id']))
                            state['mutated']=True;save('proxy-progress',state)
                request=Request('http://agent:8091'+self.path,data=body if self.command=='POST' else None,
                                headers={'Content-Type':'application/json'},method=self.command)
                try:
                    with urlopen(request,timeout=40) as response:status=response.status;data=response.read()
                except HTTPError as error:status=error.code;data=error.read()
                if count is not None:save('proxy-check-'+str(count),{'status':status,'report':json.loads(data)})
                self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
            except Exception as error:
                save('proxy-error',{'type':type(error).__name__,'message':str(error)})
                self.send_response(503);self.end_headers();self.wfile.write(b'approval source probe unavailable')


if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',8091),Handler).serve_forever()
