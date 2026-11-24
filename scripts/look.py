import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import cdp
T = cdp.main_target(9223)
W = cdp.WS(T['webSocketDebuggerUrl'])
def jv(e):
    r = W.call('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    return r.get('result', {}).get('result', {}).get('value')
print('URL', jv('location.href'))
print('BODY:', (jv('document.body.innerText') or '')[:600])
print('--- buttons aria ---')
print(jv(r'''(function(){return [...document.querySelectorAll('button')].map(function(x){var a=x.getAttribute('aria-label')||'';var t=x.textContent.trim();return (a||t).slice(0,50);}).filter(Boolean).join(' | ');})()'''))
print('--- contenteditable count:', jv("document.querySelectorAll('[contenteditable=\"true\"]').length"))
