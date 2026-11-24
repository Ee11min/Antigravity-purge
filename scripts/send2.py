import sys, os, json, time, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import cdp
T = cdp.main_target(9223); W = cdp.WS(T['webSocketDebuggerUrl'])
def jv(e):
    r = W.call('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
    return r.get('result', {}).get('result', {}).get('value')

txt = sys.argv[1]
# 清空输入框
jv(r'''(function(){var e=document.querySelector('[contenteditable="true"]');if(!e)return 'noinput';e.focus();var r=document.createRange();r.selectNodeContents(e);var s=getSelection();s.removeAllRanges();s.addRange(r);document.execCommand('delete');return e.textContent.length;})()''')
time.sleep(0.3)
jv("document.querySelector('[contenteditable=\"true\"]').focus()")
W.call('Input.insertText', {'text': txt})
time.sleep(0.6)
print('len in box:', jv("document.querySelector('[contenteditable=\"true\"]').textContent.length"))
for t in ('keyDown','keyUp'):
    W.call('Input.dispatchKeyEvent', {'type':t,'key':'Enter','code':'Enter','windowsVirtualKeyCode':13,'nativeVirtualKeyCode':13,'text':'\r' if t=='keyDown' else ''})
print('after enter, box len:', jv("document.querySelector('[contenteditable=\"true\"]').textContent.length"))
