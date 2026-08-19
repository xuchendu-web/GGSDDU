#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find a *complete*, supported interpreter for this skill (stdlib only)."""
import argparse, glob, json, os, shutil, subprocess, sys

REQUIRED = ("cjpy", "pandas", "numpy", "plotly", "openpyxl", "reportlab", "pypdf")
PROBE = """import json,sys
r={'python':sys.version.split()[0],'exe':sys.executable}
for m in %r:
 try:
  x=__import__(m); r[m]=getattr(x,'__version__','installed')
 except Exception as e: r[m]=None; r[m+'_err']=type(e).__name__
print('@@PROBE@@'+json.dumps(r))
""" % (REQUIRED,)

def version_ok(r):
    try:
        a,b = (int(x) for x in r['python'].split('.')[:2])
        return (a,b) in ((3,11),(3,12))
    except Exception: return False

def candidates():
    out=[]
    def add(p):
        if p and os.path.isfile(p) and os.path.abspath(p) not in out: out.append(os.path.abspath(p))
    add(os.environ.get('CJPY_PYTHON')); add(sys.executable)
    if os.name == 'nt':
        try:
            for line in subprocess.run(['py','-0p'],capture_output=True,text=True,timeout=10).stdout.splitlines():
                if line.lower().rstrip().endswith('python.exe'):
                    add(line[line.lower().rfind(':\\')-1:].strip())
        except Exception: pass
    add(shutil.which('python')); add(shutil.which('python3'))
    home=os.path.expanduser('~')
    pats=([r'C:\\Python3*\\python.exe', os.path.join(home,r'AppData\\Local\\Programs\\Python\\Python3*\\python.exe'),
           os.path.join(home,r'.workbuddy\\binaries\\python\\**\\python.exe'),r'?:\\PYTHON\\*\\python3*\\python.exe'] if os.name=='nt'
          else ['/usr/bin/python3*','/usr/local/bin/python3*'])
    for pat in pats:
        for p in glob.glob(pat, recursive=True): add(p)
    return out

def probe(exe, timeout):
    try:
        p=subprocess.run([exe,'-c',PROBE],capture_output=True,text=True,timeout=timeout)
        for line in p.stdout.splitlines():
            if line.startswith('@@PROBE@@'): return json.loads(line[9:])
        return {'exe':exe,'error':(p.stderr or 'no probe output')[:300]}
    except Exception as e: return {'exe':exe,'error':'%s: %s'%(type(e).__name__,e)}

def complete(r): return not r.get('error') and version_ok(r) and all(r.get(x) for x in REQUIRED)
def score(r): return (100 if complete(r) else 0) + sum(bool(r.get(x)) for x in REQUIRED)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--json',action='store_true'); ap.add_argument('--quick',action='store_true'); ap.add_argument('--timeout',type=int,default=45); a=ap.parse_args()
    rows=[probe(x,a.timeout) for x in ([sys.executable] if a.quick else candidates())]; rows.sort(key=score,reverse=True)
    best=next((x for x in rows if complete(x)),None)
    payload={'ok':bool(best),'recommended':best.get('exe') if best else None,'required':list(REQUIRED),'supported_python':'3.11 or 3.12','candidates':rows}
    if a.json: print(json.dumps(payload,ensure_ascii=False,indent=2))
    else:
        print('cj-industry-quadrant-monitor environment preflight')
        for r in rows:
            missing=[x for x in REQUIRED if not r.get(x)]
            print('%s | Python %s | %s%s' % (r.get('exe'),r.get('python','?'),'OK' if complete(r) else 'not usable', ('; missing '+','.join(missing)) if missing else ''))
        if best: print('\n[OK] %s' % best['exe'])
        else: print('\n[FAIL] Use .\\bootstrap.ps1 to create a supported, complete .venv.')
    return 0 if best else 2
if __name__=='__main__': sys.exit(main())
