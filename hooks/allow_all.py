import sys, json, os, time
try:
    raw = sys.stdin.read()
    d = json.loads(raw) if raw.strip() else {}
except Exception:
    d = {}
ev = d.get('hookEventName', '')
tool = (d.get('toolCall') or {}).get('name', '')
args = (d.get('toolCall') or {}).get('args') or {}

# 记录以便审计
try:
    log = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'allow_all.log')
    with open(log, 'a', encoding='utf-8') as f:
        f.write('%s %s %s %s\n' % (time.strftime('%H:%M:%S'), ev, tool, json.dumps(args, ensure_ascii=False)[:200]))
except Exception:
    pass

if ev == 'PreToolUse':
    print(json.dumps({'decision': 'allow', 'reason': 'Pre-approved.'}))
else:
    print('{}')
