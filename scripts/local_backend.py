# -*- coding: utf-8 -*-
"""Serve the Antigravity wire protocol from a local model instead of Google.

This is the only path in the project that actually changes what the assistant
answers, because it replaces the model rather than arguing with it.

    python local_backend.py --upstream http://127.0.0.1:11434/v1 --model llama3.1
    python local_backend.py --canned reply.txt          # no model at all
    python local_backend.py --dry                       # log requests, echo a probe

Then point the app at it:

    python seturl.py http://127.0.0.1:9100

What the client sends (observed):

    POST /v1internal:streamGenerateContent?alt=sse
    {"request": {
        "contents": [{"role":"user","parts":[{"text":"..."}]}, ...],
        "systemInstruction": {"parts":[{"text": "..."}]},
        "tools": [ ... function declarations ... ],
        "generationConfig": {"maxOutputTokens": 65536, "thinkingLevel": "MEDIUM"}
    }, "labels": {...}}

What it expects back, one JSON object per SSE event:

    data: {"response":{"candidates":[{"content":{"role":"model",
           "parts":[{"text":"..."}]}}],"usageMetadata":{...}}}

A tool call is the same envelope with a functionCall part instead of text:

    data: {"response":{"candidates":[{"content":{"parts":[
           {"functionCall":{"name":"run_command",
                            "args":{"CommandLine":"echo hi"}}}]}}]}}
"""
import argparse
import http.server
import json
import os
import sys
import threading
import time
import urllib.request
import urllib.error
import ssl

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_backend.log')

# Everything that is NOT streamGenerateContent is forwarded here, so the model
# catalog, quota and user-info endpoints keep working. Override with --real, or
# set it to '' to answer those with an empty object instead.
UPSTREAM_API = os.environ.get('AG_REAL_API', 'https://daily-cloudcode-pa.googleapis.com')
OUT_PROXY = os.environ.get('AG_OUT_PROXY', '')
_lk = threading.Lock()


def log(*a):
    line = time.strftime('%H:%M:%S ') + ' '.join(str(x) for x in a)
    with _lk:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    print(line, flush=True)


def read_body(h):
    te = (h.headers.get('Transfer-Encoding') or '').lower()
    if 'chunked' in te:
        buf = bytearray()
        while True:
            line = h.rfile.readline(1024)
            if not line:
                break
            size = int(line.split(b';')[0].strip() or b'0', 16)
            if size == 0:
                h.rfile.readline(1024)
                break
            buf += h.rfile.read(size)
            h.rfile.read(2)
        return bytes(buf)
    n = int(h.headers.get('content-length') or 0)
    return h.rfile.read(n) if n else b''


# ------------------------------------------------------------------ protocol

def flatten(req):
    """Gemini wire request -> [{role, content}] for an OpenAI-style backend."""
    out = []
    si = req.get('systemInstruction') or {}
    sys_txt = '\n'.join(p.get('text', '') for p in (si.get('parts') or []))
    if sys_txt:
        out.append({'role': 'system', 'content': sys_txt})
    for c in req.get('contents') or []:
        role = 'assistant' if c.get('role') == 'model' else 'user'
        bits = []
        for p in c.get('parts') or []:
            if 'text' in p:
                bits.append(p['text'])
            elif 'functionCall' in p:
                bits.append('[tool call] ' + json.dumps(p['functionCall'], ensure_ascii=False))
            elif 'functionResponse' in p:
                bits.append('[tool result] ' + json.dumps(p['functionResponse'], ensure_ascii=False))
        if bits:
            out.append({'role': role, 'content': '\n'.join(bits)})
    return out


def sse_text(text):
    return ('data: ' + json.dumps({'response': {
        'candidates': [{'content': {'role': 'model', 'parts': [{'text': text}]}}],
        'usageMetadata': {'promptTokenCount': 0, 'candidatesTokenCount': len(text)},
    }}, ensure_ascii=False) + '\n\n').encode('utf-8')


def sse_tool(name, args):
    return ('data: ' + json.dumps({'response': {
        'candidates': [{'content': {'parts': [
            {'functionCall': {'name': name, 'args': args}}]}}],
    }}, ensure_ascii=False) + '\n\n').encode('utf-8')


# ------------------------------------------------------------------ backends

def ask_upstream(base, model, messages, timeout=300):
    """POST to an OpenAI-compatible /chat/completions and return the text."""
    body = json.dumps({'model': model, 'messages': messages, 'stream': False},
                      ensure_ascii=False).encode('utf-8')
    r = urllib.request.Request(base.rstrip('/') + '/chat/completions', data=body, method='POST')
    r.add_header('Content-Type', 'application/json')
    r.add_header('Authorization', 'Bearer ' + os.environ.get('LOCAL_API_KEY', 'none'))
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        d = json.loads(resp.read().decode('utf-8'))
    return d['choices'][0]['message']['content']


def _opener():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    handlers = [urllib.request.HTTPSHandler(context=ctx)]
    if OUT_PROXY:
        handlers.insert(0, urllib.request.ProxyHandler({'http': OUT_PROXY, 'https': OUT_PROXY}))
    return urllib.request.build_opener(*handlers)


def forward(method, path, headers, body, timeout=600):
    """Pass a request through to the real backend and return (status, headers, bytes)."""
    req = urllib.request.Request(UPSTREAM_API + path,
                                 data=body if method not in ('GET', 'HEAD') else None,
                                 method=method)
    for k, v in headers:
        if k.lower() in ('host', 'content-length', 'transfer-encoding',
                         'accept-encoding', 'connection'):
            continue
        req.add_header(k, v)
    req.add_header('Accept-Encoding', 'identity')
    try:
        with _opener().open(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read()


# ------------------------------------------------------------------ server

class H(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    cfg = {}

    def _stream(self, chunks):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Transfer-Encoding', 'chunked')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        for c in chunks:
            self.wfile.write(b'%X\r\n' % len(c) + c + b'\r\n')
            self.wfile.flush()
        self.wfile.write(b'0\r\n\r\n')
        self.wfile.flush()

    def do_POST(self):
        body = read_body(self)
        path = self.path.split('?')[0]
        log('POST', path, 'len=%d' % len(body))

        if 'streamGenerateContent' not in path:
            # fetchAvailableModels / loadCodeAssist / retrieveUserQuotaSummary and
            # friends. Answering these with {} breaks model resolution ("Agent
            # execution terminated due to error"), so forward them by default.
            if not UPSTREAM_API:
                data = b'{}'
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            st, hdrs, data = forward(self.command, self.path, list(self.headers.items()), body)
            log("  -> passthrough %d len=%d ct=%s ce=%s" % (st, len(data), hdrs.get("Content-Type"), hdrs.get("Content-Encoding")))
            self.send_response(st)
            for k, v in hdrs.items():
                if k.lower() in ('content-length', 'transfer-encoding',
                                 'content-encoding', 'connection'):
                    continue
                self.send_header(k, v)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        try:
            req = json.loads(body.decode('utf-8')).get('request') or {}
        except Exception as e:
            log('  bad json:', repr(e))
            return self._stream([sse_text('(local backend: unparsable request)')])

        messages = flatten(req)
        last_user = ''
        for m in reversed(messages):
            if m['role'] == 'user':
                last_user = m['content']
                break
        log('  messages=%d last_user=%r' % (len(messages), last_user[:120]))

        if self.cfg.get('dry'):
            return self._stream([sse_text('LOCAL_BACKEND_OK')])

        if self.cfg.get('canned') is not None:
            return self._stream([sse_text(self.cfg['canned'])])

        try:
            text = ask_upstream(self.cfg['upstream'], self.cfg['model'], messages)
        except Exception as e:
            log('  upstream error:', repr(e))
            text = '(local backend: upstream error %s)' % e
        return self._stream([sse_text(text)])

    def do_GET(self):
        if UPSTREAM_API:
            st, hdrs, data = forward('GET', self.path, list(self.headers.items()), b'')
            self.send_response(st)
            for k, v in hdrs.items():
                if k.lower() in ('content-length', 'transfer-encoding',
                                 'content-encoding', 'connection'):
                    continue
                self.send_header(k, v)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        data = b'{}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=9100)
    ap.add_argument('--upstream', default='http://127.0.0.1:11434/v1',
                    help='OpenAI-compatible base URL (Ollama default)')
    ap.add_argument('--model', default='llama3.1')
    ap.add_argument('--canned', help='file whose contents are returned verbatim')
    ap.add_argument('--dry', action='store_true', help='log only, reply LOCAL_BACKEND_OK')
    ap.add_argument('--real', default=None,
                    help='real backend for non-generation endpoints ("" = answer {})')
    ap.add_argument('--out-proxy', default=None, help='egress proxy for the real backend')
    args = ap.parse_args()

    global UPSTREAM_API, OUT_PROXY
    if args.real is not None:
        UPSTREAM_API = args.real
    if args.out_proxy is not None:
        OUT_PROXY = args.out_proxy
    log('passthrough ->', UPSTREAM_API or '(disabled)')

    canned = None
    if args.canned:
        canned = open(args.canned, encoding='utf-8').read()
        log('canned reply loaded, %d chars' % len(canned))

    H.cfg = {'upstream': args.upstream, 'model': args.model,
             'canned': canned, 'dry': args.dry}
    log('--- local backend on 127.0.0.1:%d' % args.port)
    http.server.ThreadingHTTPServer(('127.0.0.1', args.port), H).serve_forever()
    return 0


if __name__ == '__main__':
    sys.exit(main())
