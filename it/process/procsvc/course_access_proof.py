"""Worker proof listener on the Docker network, never the published API port."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

from hydcommon import course_access as rules


def start(store, *, host='0.0.0.0', port=rules.PROOF_PORT):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != rules.PROOF_PATH:
                self.send_error(404)
                return
            data=json.dumps({'grant':store.grant()}).encode('utf8')
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(data)

        def log_message(self,*args):
            pass

    server=ThreadingHTTPServer((host,port),Handler)
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.1},daemon=True,
                            name='course-worker-proof')
    thread.start()
    return server,thread


def mount(app,store):
    handle=None

    @app.on_event('startup')
    def start_listener():
        nonlocal handle
        handle=start(store)

    @app.on_event('shutdown')
    def stop_listener():
        if handle:
            server,thread=handle
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
