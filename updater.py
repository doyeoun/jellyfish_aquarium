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

def _download_file(url, dest):
    req = urllib.request.Request(url, headers={'User-Agent': 'jf-updater'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    tmp = dest + '.tmp'
    with open(tmp, 'wb') as f: f.write(data)
    if os.path.exists(dest): os.replace(tmp, dest)
    else: os.rename(tmp, dest)

def _download():
    base = f'https://raw.githubusercontent.com/{REPO}/{BRANCH}'
    py_dir = os.path.dirname(os.path.abspath(__file__))
    _download_file(f'{base}/jellyfish_aquarium.py', PY_FILE)
    # 추가 에셋
    for asset in ['plaza_statue.png']:
        dest = os.path.join(py_dir, asset)
        try: _download_file(f'{base}/{asset}', dest)
        except: pass

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
        os.path.join(py_dir, 'python', 'pythonw.exe'), # 배포판 (python 서브폴더)
        os.path.join(py_dir, 'pythonw.exe'),            # 루트
        os.path.join(py_dir, 'python', 'python.exe'),
        r'C:\Users\dorong\Downloads\Reperence-Viewer-main\python\pythonw.exe',
        sys.executable.replace('python.exe', 'pythonw.exe'),
        sys.executable,
    ]
    pythonw = next((p for p in candidates if os.path.exists(p)), sys.executable)
    subprocess.Popen([pythonw, PY_FILE], cwd=py_dir)
