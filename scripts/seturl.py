# -*- coding: utf-8 -*-
"""Point Antigravity's cloud backend at a local proxy, or reset it.

    python seturl.py                  # -> http://127.0.0.1:9100
    python seturl.py http://127.0.0.1:9200
    python seturl.py --reset          # -> "" (back to the real backend)
    python seturl.py --show

Requires the app to be running with --remote-debugging-port=9223, and the
proxy from scripts/proxy.py listening on the target port.
"""
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import jw  # noqa: E402  (module-level hub discovery runs on import)


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == '--show':
        print(jw.call('GetCloudCodeURL') if hasattr(jw, 'call') else '?')
        return 0

    if argv and argv[0] == '--reset':
        url = ''
    elif argv:
        url = argv[0]
    else:
        url = 'http://127.0.0.1:9100'

    print('hub ', jw.H['_file'])
    print('page', jw.js('location.href'))
    print('set ', repr(url))
    print('resp', jw.call('SetCloudCodeURL', {'url': url}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
