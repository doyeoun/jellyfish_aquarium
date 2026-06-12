import urllib.request, json, os, subprocess, sys, time

REPO     = 'doyeoun/jellyfish_aquarium'
BRANCH   = 'master'
RAW_URL  = f'https://raw.githubusercontent.com/{REPO}/{BRANCH}/jellyfish_aquarium.py'
API_URL  = f'https://api.github.com/repos/{REPO}/commits/{BRANCH}'
VER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.version')
PY_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jellyfish_aquarium.py')

def _get_remote_sha():
    req = urllib.request.Request(API_URL, headers={'User-Agent': 'jf-updater'})
    with urllib.request.urlopen(req, timeout=6) as r:
        return json.loads(r.read())['sha']

def _get_local_sha():
    try:
        with open(VER_FILE, 'r') as f:
            return f.read().strip()
    except:
        return ''

def _download():
    req = urllib.request.Request(RAW_URL, headers={'User-Agent': 'jf-updater'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    tmp = PY_FILE + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    # 교체
    if os.path.exists(PY_FILE):
        os.replace(tmp, PY_FILE)
    else:
        os.rename(tmp, PY_FILE)

def check_and_update():
    try:
        sha = _get_remote_sha()
        if sha != _get_local_sha():
            _download()
            with open(VER_FILE, 'w') as f:
                f.write(sha)
    except Exception:
        pass  # 업데이트 실패해도 게임은 실행

if __name__ == '__main__':
    check_and_update()
    py_dir  = os.path.dirname(os.path.abspath(__file__))
    # 배포 패키지: python\ 서브폴더 / 개발환경: 시스템 pythonw
    candidates = [
        os.path.join(py_dir, 'python', 'pythonw.exe'),
        os.path.join(py_dir, 'python', 'python.exe'),
        r'C:\Users\dorong\Downloads\Reperence-Viewer-main\python\pythonw.exe',
        sys.executable.replace('python.exe', 'pythonw.exe'),
        sys.executable,
    ]
    pythonw = next((p for p in candidates if os.path.exists(p)), sys.executable)
    subprocess.Popen([pythonw, PY_FILE], cwd=py_dir)
