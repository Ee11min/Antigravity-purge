import http.server, json, sys, threading, os, time
LOG = r'D:\dpskk\ag\tap.log'
class H(http.server.BaseHTTPRequestHandler):
    def _h(self):
        n = int(self.headers.get('content-length') or 0)
        body = self.rfile.read(n) if n else b''
        with open(LOG,'ab') as f:
            f.write(b'\n===== %s %s\n' % (self.command.encode(), self.path.encode()))
            for k,v in self.headers.items():
                f.write(('%s: %s\n' % (k,v)).encode())
            f.write(body[:4000] + b'\n')
        self.send_response(503); self.send_header('content-type','application/json'); self.end_headers()
        self.wfile.write(b'{"error":"tap"}')
    do_GET=_h; do_POST=_h; do_PUT=_h; do_PATCH=_h
    def log_message(self,*a): pass
http.server.ThreadingHTTPServer(('127.0.0.1',9100),H).serve_forever()
