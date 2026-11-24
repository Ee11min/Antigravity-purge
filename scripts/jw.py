import sys, os, json, glob, re, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import cdp

def hub():
    """match hub file to the port the front-end page is actually served on"""
    T = cdp.main_target(9223)
    m = re.search(r'https://127\.0\.0\.1:(\d+)', T['url'])
    port = int(m.group(1)) if m else None
    best = None
    for p in glob.glob(os.path.expanduser(r'~/.gemini/antigravity/daemon/hub_*.json')):
        d = json.load(open(p)); d['_file'] = p
        if port is not None and d.get('httpsPort') == port:
            return d, T
        if best is None or os.path.getmtime(p) > os.path.getmtime(best['_file']):
            best = d
    return best, T

H, T = hub()
TOK = H['csrfToken']
W = cdp.WS(T['webSocketDebuggerUrl'])

def js(expr):
    r = W.call('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
    return r.get('result', {}).get('result', {}).get('value')

def call(method, body='{}', wait=6, ctype='application/json'):
    if not isinstance(body, str):
        body = json.dumps(body)
    expr = """(function(){
      window.__J = null;
      fetch('/exa.language_server_pb.LanguageServerService/%s', {
        method:'POST',
        headers:{'Content-Type':'%s','x-codeium-csrf-token':'%s','x-user-agent':'CONNECT_ES_USER_AGENT'},
        body: %s
      }).then(function(r){return r.text().then(function(t){window.__J={s:r.status,b:t.slice(0,4000)};});})
        .catch(function(e){window.__J={s:-1,b:String(e)};});
      return 'fired';
    })()""" % (method, ctype, TOK, json.dumps(body))
    js(expr)
    for _ in range(int(wait*4)):
        time.sleep(0.25)
        v = js('window.__J')
        if v: return v
    return {'s':-2,'b':'timeout'}

if __name__ == '__main__':
    print('hub', H['_file'], 'tok', TOK)
    print('page', js('location.href'))
    for m in sys.argv[1:] or ['JetboxReadUserConfig']:
        print('=====', m); print(call(m))
