import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import cdp
T = cdp.main_target(9223); W = cdp.WS(T['webSocketDebuggerUrl'])
def jv(e):
    r = W.call('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    return r.get('result', {}).get('result', {}).get('value')
name = sys.argv[1]
print(jv(r'''(function(){
  var b=[...document.querySelectorAll('button')].filter(function(x){return /^\u9009\u62e9\u6a21\u578b/.test(x.getAttribute('aria-label')||'');})[0];
  if(!b) return 'no-btn'; b.click(); return 'opened';})()'''))
time.sleep(1.5)
print(jv('(function(){var n=%s; var it=[...document.querySelectorAll("[data-testid], [role=menuitem], [role=menuitemradio], div")].filter(function(e){var t=e.textContent.trim().replace(/\\s+/g," "); return t.indexOf(n)===0 && t.length<60;}); if(!it.length) return "notfound"; it[it.length-1].click(); return "clicked:"+it.length;})()' % ('"'+name+'"')))
time.sleep(1)
print('now:', jv(r'''(function(){var b=[...document.querySelectorAll('button')].filter(function(x){return /^\u9009\u62e9\u6a21\u578b/.test(x.getAttribute('aria-label')||'');})[0]; return b?b.getAttribute('aria-label'):'?';})()'''))
