import pygame
import math
import random
import sys
import json
import os
import threading
import urllib.request as _url_req
import webbrowser

VERSION = '3.2.0'
_latest_ver  = None   # None=확인중, ''=최신, 버전문자열=업데이트있음
_release_url = ''

def _fetch_update():
    global _latest_ver, _release_url
    try:
        req = _url_req.Request(
            'https://api.github.com/repos/doyeoun/jellyfish_aquarium/releases/latest',
            headers={'User-Agent': 'jellyfish-game'})
        with _url_req.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        tag = data.get('tag_name', '').lstrip('v')
        _release_url = data.get('html_url', '')
        _latest_ver  = tag if tag and tag != VERSION else ''
    except Exception:
        _latest_ver = ''

threading.Thread(target=_fetch_update, daemon=True).start()

# exe로 패키징돼도 저장 위치가 실행 파일 옆으로 유지됨
_BASE = os.path.dirname(sys.executable if getattr(sys,'frozen',False)
                        else os.path.abspath(__file__))
SAVE_PATH = os.path.join(_BASE, 'jellyfish_save.json')
# exe 번들 시 _MEIPASS에서 사운드 로드, 아니면 exe 옆 sounds/ 폴더
if getattr(sys,'frozen',False) and getattr(sys,'_MEIPASS',None):
    SOUNDS_DIR = os.path.join(sys._MEIPASS, 'sounds')
else:
    SOUNDS_DIR = os.path.join(_BASE, 'sounds')

# 사운드는 pygame.init() 이후에 초기화됨 (아래 init_sounds() 호출)
SND_KILL = SND_FEED = SND_BUBBLE = SND_BELL = SND_FANFARE = SND_AQUARIUM = SND_UI1 = SND_UI2 = SND_RELEASE = SND_CHAT1 = SND_CHAT2 = SND_SQUEAK1 = SND_SQUEAK2 = None

def play_ui_click():
    opts = [s for s in [SND_UI1, SND_UI2] if s]
    if opts: random.choice(opts).play()

def _snd(filename):
    path = os.path.join(SOUNDS_DIR, filename)
    try:
        return pygame.mixer.Sound(path)
    except:
        return None

def init_sounds():
    global SND_KILL, SND_FEED, SND_BUBBLE, SND_BELL, SND_FANFARE, SND_AQUARIUM, SND_UI1, SND_UI2, SND_RELEASE, SND_CHAT1, SND_CHAT2, SND_SQUEAK1, SND_SQUEAK2
    try:
        pygame.mixer.music.load(os.path.join(SOUNDS_DIR, 'bgm.mp3'))
        pygame.mixer.music.set_volume(0.35)
        pygame.mixer.music.play(-1)
    except: pass
    SND_KILL     = _snd('scream.mp3')
    SND_FEED     = _snd('eating.mp3')
    SND_BUBBLE   = _snd('bubbles-single2.wav')
    SND_BELL     = _snd('bell.wav')
    SND_FANFARE  = _snd('castlefanfare.mp3')
    SND_AQUARIUM = _snd('bubbles.mp3')
    SND_UI1      = _snd('ui_pop1.mp3')
    SND_UI2      = _snd('ui_pop2.wav')
    SND_RELEASE  = _snd('release.mp3')
    SND_CHAT1    = _snd('chat1.mp3')
    SND_CHAT2    = _snd('chat2.mp3')
    SND_SQUEAK1  = _snd('squeak1.mp3')
    SND_SQUEAK2  = _snd('squeak2.mp3')
    for _s, _v in [(SND_KILL,0.7),(SND_FEED,0.8),(SND_BUBBLE,0.5),
                   (SND_BELL,0.7),(SND_FANFARE,0.8),(SND_AQUARIUM,0.6),
                   (SND_UI1,0.6),(SND_UI2,0.6),(SND_RELEASE,0.75),
                   (SND_CHAT1,0.7),(SND_CHAT2,0.7),
                   (SND_SQUEAK1,0.7),(SND_SQUEAK2,0.7)]:
        if _s: _s.set_volume(_v)
FIREBASE_URL = "https://jellyfish-aquarium-default-rtdb.firebaseio.com/"
GRADE_SCORES = {'common':10,'uncommon':25,'rare':60,'epic':150,'legendary':800,'secret':500,'lock':0}

def calc_score(inventory):
    return sum(GRADE_SCORES.get(JELLY_GRADES.get(s,'common'),0)*c for s,c in inventory.items())

_rankings_cache   = []
_rankings_loading = False

def upload_score_bg(nickname, score):
    def _up():
        try:
            import urllib.request as _ur, urllib.parse as _up2, json as _j
            safe_nick = _up2.quote(nickname, safe='')
            url  = FIREBASE_URL + f"rankings/{safe_nick}.json"
            data = _j.dumps({"nickname":nickname,"score":score}).encode('utf-8')
            req  = _ur.Request(url, data=data, method='PUT',
                               headers={'Content-Type':'application/json','User-Agent':'jellyfish-game'})
            _ur.urlopen(req, timeout=5)
        except: pass
    import threading as _t; _t.Thread(target=_up, daemon=True).start()

# ── 온라인 멀티플레이 ─────────────────────────────────────────
_online_players = {}   # nick → {x,y,nickname,last_seen}
_online_chat    = []   # [{nick,text,time}]
_push_events    = {}   # nick → {vx,vy,t} 최신 push 이벤트

def sync_online_pos(nick, x, y, action=None, action_phase=0.0, equipped_item=None):
    def _s():
        try:
            import urllib.request as _ur, urllib.parse as _up2, json as _j, time as _tm
            safe = _up2.quote(nick, safe='')
            url  = FIREBASE_URL + f"online/{safe}.json"
            payload = {"x":int(x),"y":int(y),"nickname":nick,"last_seen":int(_tm.time())}
            if action: payload['action'] = action; payload['action_phase'] = round(action_phase, 2)
            else:      payload['action'] = ''; payload['action_phase'] = 0.0
            payload['equipped'] = equipped_item or ''
            data = _j.dumps(payload).encode()
            req  = _ur.Request(url,data=data,method='PUT',
                               headers={'Content-Type':'application/json','User-Agent':'jellyfish-game'})
            _ur.urlopen(req,timeout=3)
        except: pass
    import threading as _t; _t.Thread(target=_s,daemon=True).start()

def send_push_event(target_nick, vx, vy):
    def _p():
        try:
            import urllib.request as _ur, urllib.parse as _up3, json as _j, time as _tm
            safe = _up3.quote(target_nick, safe='')
            data = _j.dumps({'vx':round(vx,2),'vy':round(vy,2),'t':int(_tm.time())}).encode()
            req  = _ur.Request(FIREBASE_URL+f'push_events/{safe}.json',data=data,method='PUT',
                               headers={'Content-Type':'application/json','User-Agent':'jellyfish-game'})
            _ur.urlopen(req,timeout=3)
        except: pass
    import threading as _t; _t.Thread(target=_p,daemon=True).start()

def fetch_push_events():
    def _fp():
        global _push_events
        try:
            import urllib.request as _ur, json as _j, time as _tm
            req = _ur.Request(FIREBASE_URL+'push_events.json',headers={'User-Agent':'jellyfish-game'})
            with _ur.urlopen(req,timeout=3) as r: data=_j.loads(r.read()) or {}
            now = int(_tm.time())
            _push_events = {k:v for k,v in data.items() if now-v.get('t',0)<4}
        except: pass
    import threading as _t; _t.Thread(target=_fp,daemon=True).start()

def remove_online_player(nick):
    def _r():
        try:
            import urllib.request as _ur, urllib.parse as _up2
            safe = _up2.quote(nick, safe='')
            req  = _ur.Request(FIREBASE_URL+f"online/{safe}.json",method='DELETE',
                               headers={'User-Agent':'jellyfish-game'})
            _ur.urlopen(req,timeout=3)
        except: pass
    import threading as _t; _t.Thread(target=_r,daemon=True).start()

_sse_running = False

def start_sse_stream(nick_self):
    """Firebase SSE 스트리밍 — 변경 즉시 수신."""
    global _sse_running
    _sse_running = True
    def _stream():
        global _online_players, _sse_running
        import urllib.request as _ur, json as _j, time as _tm
        while _sse_running:
            try:
                req = _ur.Request(FIREBASE_URL+"online.json",
                                  headers={'Accept':'text/event-stream','User-Agent':'jellyfish-game'})
                with _ur.urlopen(req, timeout=None) as r:
                    buf = ''
                    while _sse_running:
                        ch = r.read(1).decode('utf-8','ignore')
                        if not ch: break
                        buf += ch
                        if buf.endswith('\n\n'):
                            lines = buf.strip().split('\n')
                            data_line = next((l[6:] for l in lines if l.startswith('data:')), None)
                            if data_line:
                                try:
                                    pkt = _j.loads(data_line)
                                    raw = pkt.get('data') or {}
                                    now = int(_tm.time())
                                    new_op={k:v for k,v in raw.items()
                                            if k!=nick_self and now-v.get('last_seen',0)<20}
                                    for k,v in new_op.items():
                                        old=_online_players.get(k,{})
                                        v['cur_x']=old.get('cur_x',v['x'])
                                        v['cur_y']=old.get('cur_y',v['y'])
                                    _online_players=new_op
                                except: pass
                            buf=''
            except:
                _tm.sleep(1)  # 끊기면 1초 후 재연결
    import threading as _t; _t.Thread(target=_stream,daemon=True).start()

def stop_sse_stream():
    global _sse_running
    _sse_running = False

def fetch_online_bg(nick_self):
    def _f():
        global _online_players, _online_chat
        try:
            import urllib.request as _ur, json as _j, time as _tm
            req=_ur.Request(FIREBASE_URL+"online.json",headers={'User-Agent':'jellyfish-game'})
            with _ur.urlopen(req,timeout=3) as r: data=_j.loads(r.read())
            now=int(_tm.time())
            new_op={k:v for k,v in (data or {}).items()
                    if k!=nick_self and now-v.get('last_seen',0)<20}
            # 보간 위치 보존
            for k,v in new_op.items():
                old=_online_players.get(k,{})
                v['cur_x']=old.get('cur_x', v['x'])
                v['cur_y']=old.get('cur_y', v['y'])
            _online_players=new_op
        except: pass
        try:
            import urllib.request as _ur2, json as _j2
            req2=_ur2.Request(FIREBASE_URL+"ochat.json",headers={'User-Agent':'jellyfish-game'})
            with _ur2.urlopen(req2,timeout=3) as r2: d2=_j2.loads(r2.read())
            if d2: _online_chat=sorted(d2.values(),key=lambda x:x.get('t',0))[-8:]
        except: pass
    import threading as _t; _t.Thread(target=_f,daemon=True).start()

def send_online_chat(nick, text):
    def _sc():
        try:
            import urllib.request as _ur, json as _j, time as _tm
            url=FIREBASE_URL+"ochat.json"
            data=_j.dumps({"nick":nick,"text":text,"t":int(_tm.time())}).encode()
            req=_ur.Request(url,data=data,method='POST',
                            headers={'Content-Type':'application/json','User-Agent':'jellyfish-game'})
            _ur.urlopen(req,timeout=3)
        except: pass
    import threading as _t; _t.Thread(target=_sc,daemon=True).start()


def fetch_rankings_bg():
    global _rankings_cache, _rankings_loading
    _rankings_loading = True
    def _fetch():
        global _rankings_cache, _rankings_loading
        try:
            import urllib.request as _ur, json as _j
            req = _ur.Request(FIREBASE_URL+"rankings.json", headers={'User-Agent':'jellyfish-game'})
            with _ur.urlopen(req, timeout=5) as r:
                data = _j.loads(r.read())
            if data:
                _rankings_cache = sorted(data.values(), key=lambda x:x.get('score',0), reverse=True)[:10]
        except: pass
        _rankings_loading = False
    import threading as _t; _t.Thread(target=_fetch, daemon=True).start()

_wardrobe_cache = {'items': set(), 'equipped': None}

def save_game(inventory, stage, cult_docs=None, aquarium=None, nickname='', bgm_vol=0.35, sfx_vol=0.7, chat_vol=0.7, wardrobe_items=None, equipped_item=None):
    wd = wardrobe_items if wardrobe_items is not None else _wardrobe_cache['items']
    eq = equipped_item if equipped_item is not None else _wardrobe_cache['equipped']
    data = {
        'inventory': {str(k): v for k, v in inventory.items()},
        'stage': stage,
        'cult_docs': {str(k): v for k, v in (cult_docs or {}).items()},
        'aquarium':  list(aquarium or []),
        'bred_slots': list(_bred_slots),
        'nickname':   nickname,
        'bgm_vol':    bgm_vol,
        'sfx_vol':    sfx_vol,
        'chat_vol':   chat_vol,
        'wardrobe':   list(wd),
        'equipped_item': eq or '',
    }
    try:
        with open(SAVE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_game():
    if not os.path.exists(SAVE_PATH):
        return {}, 1, {}, [], set(), '', 0.35, 0.7, 0.7, set(), None
    try:
        with open(SAVE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        inv        = {int(k): v for k, v in data.get('inventory', {}).items()}
        stage      = data.get('stage', 1)
        cult_docs  = {int(k): v for k, v in data.get('cult_docs', {}).items()}
        aquarium   = [int(x) for x in data.get('aquarium', [])]
        bred_slots = set(int(x) for x in data.get('bred_slots', []))
        nickname   = data.get('nickname', '')
        bgm_vol    = float(data.get('bgm_vol', 0.35))
        sfx_vol    = float(data.get('sfx_vol', 0.7))
        chat_vol   = float(data.get('chat_vol', 0.7))
        raw_w = data.get('wardrobe', [])
        wardrobe = set(raw_w) if isinstance(raw_w, list) else set(raw_w.keys())
        equipped_item_sv = data.get('equipped_item', '') or None
        return inv, stage, cult_docs, aquarium, bred_slots, nickname, bgm_vol, sfx_vol, chat_vol, wardrobe, equipped_item_sv
    except Exception:
        return {}, 1, {}, [], set(), '', 0.35, 0.7, 0.7, set(), None

try:
    import ctypes
    CTYPES_OK = True
except ImportError:
    CTYPES_OK = False

pygame.init()
init_sounds()

WIDTH, HEIGHT = 380, 560
FPS = 60

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("해파리 수족관 🪼")

if CTYPES_OK:
    try:
        hwnd = pygame.display.get_wm_info()['window']
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 3)
    except Exception:
        pass

clock = pygame.time.Clock()
W_PIX = 16

DEV_MODE = False  # False = 정상 플레이 모드

# ── 폰트 ──────────────────────────────────────────────────────
_font_cache = {}
def get_font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        for name in ['malgun gothic', 'gulim', 'dotum']:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f:
                _font_cache[key] = f
                return f
        _font_cache[key] = pygame.font.Font(None, size + 4)
    return _font_cache[key]

# ── 해파리 기본 디자인 2종 (파랑 / 분홍) ───────────────────────
JELLY_DEFS = [
    {   # 0 – 파란 해파리
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(15,82,118),'D':(35,152,185),'M':(65,205,228),'H':(145,235,248)},
        'tc': (25,118,155), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 1 – 분홍 해파리
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMMMMMDDX..",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(118,23,73),'D':(192,68,118),'M':(228,118,160),'H':(250,190,210)},
        'tc': (235,130,172), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 2 – 노란 베이스 (전기 해파리)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(122,92,8),'D':(202,165,12),'M':(245,212,32),'H':(255,244,150)},
        'tc': (248,218,22), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 3 – 슬라임 (초록, 반투명)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMMMMMDDX..",
            "..XDDMMHMMMDDX..",
            "..XDDMMMMMMDDX..",
            "...XDDDDDDDDX...",
            "....XXXXXXXX....",
        ],
        'cmap': {'.':None,'X':(42,125,30),'D':(70,175,48),'M':(112,210,75),'H':(172,238,140)},
        'tc': (70,175,48), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 4 – 얼어붙은 (하늘색)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(78,162,218),'D':(128,198,238),'M':(172,222,248),'H':(218,242,255)},
        'tc': (128,198,238), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 5 – 천사 (#fdf2cd 기반 연크림색)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(202,180,108),'D':(235,218,162),'M':(253,242,205),'H':(255,251,232)},
        'tc': (235,218,162), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 6 – 유령 (흰색, 눈 없음, 반투명)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMMMMMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(172,178,198),'D':(202,208,222),'M':(225,230,242),'H':(245,247,252)},
        'tc': (192,198,215), 'tb': [3,6,9,12], 'ps': 4,
        'eyes': False,
    },
    {   # 7 – 털복숭이 (따뜻한 베이지/갈색)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(140,100,60),'D':(188,145,96),'M':(222,182,136),'H':(245,222,196)},
        'tc': (172,128,78), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 8 – 해파리 왕 (#fdd7c8 연살구색)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(205,148,118),'D':(238,188,164),'M':(253,215,200),'H':(255,238,228)},
        'tc': (238,188,164), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 9 – 썩은 좀비 (어두운 초록 + 어두운 분홍 혼합)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMPPMMDDX..",
            "..XDDMPPPPMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(30,42,28),'D':(60,88,45),'M':(80,118,62),'P':(145,55,82),'H':(145,55,82)},
        'tc': (68,85,55), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 10 – 심해 해파리 (짙은 남색/거의 검정)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(5,8,22),'D':(10,15,40),'M':(18,28,62),'H':(30,48,95)},
        'tc': (12,22,50), 'tb': [3,6,9,12], 'ps': 4,
        'eye_color': (48, 218, 178),  # 낚싯대 orb 색과 동일
    },
    {   # 11 – 구름 해파리 (볼록볼록한 구름 모양 도트)
        'art': [
            ".MMM..MMM..MMM..",   # 세 볼록 꼭대기
            "MMHM.MMHM.MMHM..",  # 볼록 하이라이트
            "MMHMMMMHMMMMHMMM",  # 볼록 퍼지며 합쳐짐
            "MMMMMMMMMMMMMMMM",  # 가장 넓은 몸통
            "MMMMHHHHHHHMMMM.",  # 내부 하이라이트
            ".MMMMMMMMMMMMM..",  # 몸통
            "...MMMMMMMMMM...",  # 아래 좁아짐
            "....XXXXXXXXXX..",  # 밑선
        ],
        'cmap': {'.':None,'X':(182,196,222),'D':(225,232,248),'M':(232,238,250),'H':(250,253,255)},
        'tc': (200,215,240), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 12 – 화난 해파리 (빨간/오렌지)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(118,16,16),'D':(192,44,30),'M':(238,78,60),'H':(255,152,140)},
        'tc': (192,44,30), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 13 – 멋쟁이 해파리 (보라/바이올렛)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(62,20,95),'D':(115,50,168),'M':(165,92,215),'H':(218,168,245)},
        'tc': (115,50,168), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 14 – 토끼 해파리 (#fdc8d4 연분홍)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(205,142,160),'D':(238,175,190),'M':(253,200,212),'H':(255,228,235)},
        'tc': (238,175,190), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 15 – 저주받은 해파리 (어두운 혈흑)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(28,0,5),'D':(66,0,13),'M':(95,5,18),'H':(140,15,30)},
        'tc': (100,8,16), 'tb': [3,6,9,12], 'ps': 4,
        'eyes': False,
    },
    {   # 16 – 선인장 해파리 (초록)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(22,140,18),'D':(38,200,32),'M':(60,239,51),'H':(148,255,138)},
        'tc': (38,200,32), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 17 – 눈사람 해파리 (흰색, 벨은 직접 그림)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMMMMMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(158,172,198),'D':(208,218,235),'M':(235,240,250),'H':(252,254,255)},
        'tc': (185,198,220), 'tb': [3,6,9,12], 'ps': 4,
        'eyes': False,
    },
    {   # 18 – 황금 해파리
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(178,126,15),'D':(212,168,35),'M':(242,202,58),'H':(255,238,128)},
        'tc': (218,172,38), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 21 – 푸딩 해파리 (커스터드 노랑)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(182,100,5),'D':(228,152,18),'M':(252,190,48),'H':(255,228,125)},
        'tc': (228,152,18), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 22 – 소다맛 푸딩 해파리 (#95ed9d 민트 그린)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(48,152,60),'D':(95,205,108),'M':(149,237,157),'H':(200,250,205)},
        'tc': (95,205,108), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 23 – 벚꽃 해파리 (연분홍)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(192,118,138),'D':(238,175,192),'M':(255,210,222),'H':(255,238,244)},
        'tc': (238,175,192), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 24 – 쌍둥이 해파리 (더미 - 실제 스프라이트는 TWIN_BELL_SPRITE)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(145,92,178),'D':(185,135,215),'M':(218,172,238),'H':(242,215,252)},
        'tc': (185,135,215), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 19 – 무지개 해파리 (더미 - 실제 스프라이트는 RAINBOW_BELL_SPRITE)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(120,45,170),'D':(160,70,215),'M':(190,105,240),'H':(220,165,255)},
        'tc': (190,105,240), 'tb': [3,6,9,12], 'ps': 4,
    },
    {   # 20 – 파분 해파리 (파랑+분홍 혼합, 파스텔 라벤더)
        'art': [
            "......XXXX......",
            "....XXDDDDXX....",
            "...XDDMMMMDDX...",
            "..XDDMMHHMMDDX..",
            "..XDDMHHHHMDDX..",
            "..XDDMMMMMMDDX..",
            "..XDDDDDDDDDDX..",
            "..XXXXXXXXXXXX..",
        ],
        'cmap': {'.':None,'X':(118,75,158),'D':(172,120,205),'M':(215,158,230),'H':(240,205,248)},
        'tc': (188,132,218), 'tb': [3,6,9,12], 'ps': 4,
    },
]

JELLY_NAMES = ['파란 해파리', '분홍 해파리', '개구리 모자 해파리',
               '안경 해파리', '전기 해파리', '고양이 해파리',
               '슬라임 해파리', '얼어붙은 해파리', '천사 해파리', '유령 해파리',
               '털복숭이 해파리', '해파리 왕', '썩은 해파리', '심해 해파리', '구름 해파리', '화난 해파리',
               '멋쟁이 해파리', '토끼 해파리', '저주받은 해파리',
               '선인장 해파리', '눈사람 해파리', '황금 해파리', '무지개 해파리', '파분 해파리', '푸딩 해파리', '소다맛 푸딩 해파리', '벚꽃 해파리', '쌍둥이 해파리']

# ── 등급 시스템 ───────────────────────────────────────────────
GRADE_ORDER  = ['common', 'uncommon', 'rare', 'epic', 'legendary', 'secret', 'lock']
GRADE_COLORS = {
    'common':    (55,  125, 250),
    'uncommon':  (72,  190,  72),
    'rare':      (220,  45,  45),
    'epic':      (165,  55, 248),
    'legendary': (255, 158,  12),
    'secret':    (212, 253, 246),
    'lock':      (60,  60,  70),
}
GRADE_LABEL = {
    'common':    'COMMON',
    'uncommon':  'UNCOMMON',
    'rare':      'RARE',
    'epic':      'EPIC',
    'legendary': 'LEGENDARY',
    'secret':    'SECRET',
    'lock':      'LOCK',
}
SECRET_COLS   = [(253,200,253), (212,253,200), (200,253,246)]
GRADE_WEIGHTS = {'common':20,'uncommon':10,'rare':4,'epic':1.5,'legendary':0.5,'secret':4,'lock':0}

# ── 배양서 데이터 ──────────────────────────────────────────────
CULT_DOC_NAMES = {
    1: '무지개 해파리 배양서',
    2: '파분 해파리 배양서',
    3: '쌍둥이 해파리 배양서',
}
CULT_DOC_DESCS = {
    1: '영롱한 일곱 빛깔이 담긴 배양서. 무지개 해파리를 교배로 만들 수 있다.',
    2: '파랑과 분홍이 뒤섞인 배양서. 파분 해파리를 교배로 만들 수 있다.',
    3: '두 개의 영혼이 담긴 배양서. 쌍둥이 해파리를 교배로 만들 수 있다.',
}
CULT_DOC_RESULT = {
    1: 22,    # → 무지개 해파리
    2: 23,    # → 파분 해파리
    3: 27,    # → 쌍둥이 해파리
}
# (재료 A 슬롯, 재료 B 슬롯)
CULT_DOC_RECIPE = {
    1: (18, 21),  # 저주받은 해파리 + 황금 해파리 → 무지개 해파리
    2: (0,  1),   # 파란 해파리 + 분홍 해파리 → 파분 해파리
    3: (18, 14),  # 저주받은 해파리 + 구름 해파리 → 쌍둥이 해파리
}
# 각 design_idx 등급 설정 (여기서만 수정하면 됨)
JELLY_GRADES = {
    0:  'common',    # 파란 해파리
    1:  'common',    # 분홍 해파리
    2:  'uncommon',  # 개구리 모자 해파리
    3:  'common',    # 안경 해파리
    4:  'rare',      # 전기 해파리
    5:  'common',    # 고양이 해파리
    6:  'uncommon',  # 슬라임 해파리
    7:  'rare',      # 얼어붙은 해파리
    8:  'rare',      # 천사 해파리
    9:  'rare',      # 유령 해파리
    10: 'uncommon',  # 털복숭이 해파리
    11: 'epic',      # 해파리 왕
    12: 'common',    # 썩은 해파리
    13: 'legendary', # 심해 해파리
    14: 'rare',      # 구름 해파리
    15: 'uncommon',  # 화난 해파리
    16: 'uncommon',  # 멋쟁이 해파리
    17: 'uncommon',  # 토끼 해파리
    18: 'legendary', # 저주받은 해파리
    19: 'common',    # 선인장 해파리
    20: 'epic',      # 눈사람 해파리
    21: 'legendary', # 황금 해파리
    22: 'secret',    # 무지개 해파리
    23: 'secret',    # 파분 해파리
    24: 'lock',      # 푸딩 해파리 (원래: epic)
    25: 'lock',      # 소다맛 푸딩 해파리 (원래: epic)
    26: 'lock',      # 벚꽃 해파리 (원래: epic)
    27: 'secret',    # 쌍둥이 해파리
}

# ── 해파리 도감 정보 ───────────────────────────────────────────
JELLY_INFO = {
    0:  {'habitat': '얕고 따뜻한 연안 바다',
         'personality': '온순하고 겁이 없다. 처음 만나는 해파리에게도 먼저 다가간다.',
         'quote': '"수족관의 분위기를 잡아주는 건 역시 나야."'},
    1:  {'habitat': '산호초 근처 따뜻한 물',
         'personality': '사교적이고 에너지가 넘친다. 주변을 들뜨게 만드는 분위기 메이커.',
         'quote': '"오늘도 예쁘지? 어제도 예뻤지만."'},
    2:  {'habitat': '수풀이 많은 강 하구',
         'personality': '개구리를 동경해서 모자를 쓰기 시작했다. 정작 개구리는 무서워한다.',
         'quote': '"언젠간 진짜 개구리가 될 거야."'},
    3:  {'habitat': '책이 많은 바다 (자칭)',
         'personality': '지적인 척하지만 안경을 쓴 이후로 오히려 더 잘 안 보인다.',
         'quote': '"흠, 알고는 있었어. 그냥 확인해본 거야."'},
    4:  {'habitat': '깊은 전도성 해구',
         'personality': '몸에서 정전기가 끊임없이 흐른다. 악의는 없는데 가까이 가면 따끔하다.',
         'quote': '"조심해. 나도 가끔 깜짝 놀라거든."'},
    5:  {'habitat': '고양이가 좋아하는 어느 바다',
         'personality': '고양이 귀가 진짜인지 아무도 확인하지 못했다. 도도하게 눈을 마주치지 않는다.',
         'quote': '"…별로 궁금하지 않아."'},
    6:  {'habitat': '진흙이 많은 강바닥',
         'personality': '끈적한 점액질로 덮여 있다. 다른 해파리들이 은근히 멀리한다.',
         'quote': '"왜들 그래. 나 나쁜 해파리 아니거든."'},
    7:  {'habitat': '극지방 빙하 아래',
         'personality': '차갑고 조용하다. 가까이 있으면 주변 온도가 살짝 내려가는 것 같다.',
         'quote': '"…(말이 없다)"'},
    8:  {'habitat': '구름 위 어딘가',
         'personality': '항상 온화하게 미소 짓는다. 링이 진짜인지 가짜인지는 본인도 모른다.',
         'quote': '"모두 잘 되길 바라고 있어."'},
    9:  {'habitat': '어둡고 아무것도 없는 곳',
         'personality': '반투명해서 어디 있는지 자주 잊힌다. 본인도 자신이 있는지 가끔 헷갈린다.',
         'quote': '"…나 여기 있어. 못 봤어?"'},
    10: {'habitat': '깊고 따뜻한 해저 동굴',
         'personality': '왜 털이 있는지 과학적으로 설명이 불가능하다. 본인은 자랑스러워한다.',
         'quote': '"뽀송뽀송하지? 나 관리 열심히 해."'},
    11: {'habitat': '수족관 한가운데 (자칭 왕좌)',
         'personality': '수염과 왕관을 달고 위엄 있게 떠다닌다. 아무도 왕으로 인정하지 않지만 본인은 확신한다.',
         'quote': '"짐이 여기 있으니 이 수족관이 왕국이니라."'},
    12: {'habitat': '오래된 침몰선 내부',
         'personality': '뇌가 머리 위에 올라가 있다. 왜인지 모르지만 본인은 불편하지 않다고 한다. 놀라면 뇌를 떨어트린다.',
         'quote': '"뇌가 바깥에 있으면 생각이 더 잘 돼."'},
    13: {'habitat': '수심 3000m 이하 심해',
         'personality': '빛으로 먹이를 유인하는 냉정한 사냥꾼. 깊은 바다에서 올라온 탓에 밝은 곳이 불편하다.',
         'quote': '"…내려와. 더 좋은 게 있어."'},
    14: {'habitat': '고기압이 발달한 구름층',
         'personality': '하늘에서 떨어진 구름 조각 같다. 솜털 같은 촉감이지만 실제로는 만지면 안 된다.',
         'quote': '"나 물이야, 공기야? 나도 몰라."'},
    15: {'habitat': '조류가 거친 해협',
         'personality': '항상 화가 나 있다. 이유를 물어보면 그것 때문에 더 화가 난다.',
         'quote': '"뭘 봐!"'},
    16: {'habitat': '유럽풍 심해 살롱 (자칭)',
         'personality': '탑햇을 쓰고 우아하게 떠다닌다. 아무것도 하지 않아도 품위 있어 보인다.',
         'quote': '"좋은 저녁이야. 물론 나한테는 항상 좋지."'},
    17: {'habitat': '봄날 풀밭 근처 연못',
         'personality': '귀가 쫑긋하고 항상 무언가를 경계한다. 겁이 많지만 호기심도 많다.',
         'quote': '"저게 뭐지? 아, 무서워! 그래도 보고 싶어."'},
    18: {'habitat': '저주받은 어두운 심연',
         'personality': '여우불을 두르고 조용히 떠다닌다. 눈이 빨갛게 빛나지만 적의는 없다(고 한다).',
         'quote': '"저주? 그냥 개성이야."'},
    19: {'habitat': '수심이 얕은 사막 오아시스',
         'personality': '전신에 가시가 돋아 있다. 악수를 하고 싶어도 할 수가 없어 늘 외롭다.',
         'quote': '"가까이 오면 다쳐. …그래도 와줘."'},
    20: {'habitat': '겨울 바다 표층',
         'personality': '눈으로 만들어졌지만 절대 녹지 않는다. 봄이 와도 여름이 와도 여전히 있다.',
         'quote': '"나 안 녹아. 걱정 마."'},
    21: {'habitat': '전설 속 황금 해구 심층부',
         'personality': '온몸이 황금빛으로 빛난다. 목격담이 거의 없으며, 보는 것만으로도 행운이 찾아온다고 전해진다.',
         'quote': '"…반짝이는 건 다 금은 아니지만, 나는 진짜야."'},
    27: {'habitat': '쌍둥이가 태어나는 신비로운 산호초',
         'personality': '두 머리가 항상 같은 방향을 보며 헤엄친다. 한 쪽이 배고프면 다른 쪽도 배가 고프다.',
         'quote': '"우린 항상 함께야. 그게 좋아." / "나도."'},
    26: {'habitat': '벚꽃나무 아래 잔잔한 봄 연못',
         'personality': '조용하고 우아하다. 꽃잎처럼 살랑살랑 헤엄치며 주변을 환하게 만든다.',
         'quote': '"꽃잎이 떨어지는 건 슬프지 않아. 내가 여기 있잖아."'},
    25: {'habitat': '탄산이 올라오는 청량한 얕은 바다',
         'personality': '통통 튀고 청량하다. 언제나 기분이 좋고 주변에 작은 거품을 뿜는다.',
         'quote': '"쏴아~ 기분 좋지? 나도 기분 좋아."'},
    24: {'habitat': '달콤한 조류가 흐르는 따뜻한 얕은 바다',
         'personality': '언제나 달콤하고 부드럽다. 주변 해파리들이 왠지 이 녀석 곁에 있으면 기분이 좋아진다고 한다.',
         'quote': '"체리는 직접 올렸어. 생크림도 내가 만든 거야."'},
    23: {'habitat': '파란 바다와 분홍 산호초가 만나는 경계',
         'personality': '파란 해파리의 차분함과 분홍 해파리의 에너지가 균형 있게 섞여 있다. 어느 쪽에도 치우치지 않아 늘 조화롭다.',
         'quote': '"뭐가 더 어울려? 파랑이야, 분홍이야? ...둘 다야."'},
    22: {'habitat': '빛이 굴절되는 얕은 바다 수면 아래',
         'personality': '몸 전체에서 일곱 빛깔 무지개가 흐른다. 보는 이에게 근거 없는 설렘을 준다.',
         'quote': '"세상에 나쁜 색은 없어. 다 아름답거든."'},
}

# ── 개구리 모자 픽셀 아트 ─────────────────────────────────────
FROG_HAT_ART = [
    "...g..g...",   # 눈 돌출부 꼭대기 (10자)
    "..gWXgWXg.",   # 눈 (W=흰자, X=동공)
    "..GGGGGGG.",   # 모자 윗부분
    ".GGGGGGGGG",   # 모자 몸통
    "GGGGGGGGGG",   # 챙
]
FROG_HAT_CMAP = {
    '.': None,
    'G': (45,155,68),
    'g': (85,208,100),
    'W': (218,238,222),
    'X': (15,15,25),
}

def make_frog_hat():
    H, W = len(FROG_HAT_ART), 10
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(FROG_HAT_ART):
        for col, ch in enumerate(line[:W]):
            c = FROG_HAT_CMAP.get(ch)
            if c:
                s.set_at((col, row), (*c, 255))
    return s

FROG_HAT_BASE = make_frog_hat()

# ── 동그란 안경 픽셀 아트 ─────────────────────────────────────
GLASSES_ART = [
    ".ooo..ooo.",   # 10자: 두 원 윗호
    "o...oo...o",   # 양 옆 + 브릿지 (가운데 투명 = 눈이 보임)
    ".ooo..ooo.",   # 두 원 아랫호
]
GLASSES_CMAP = {'.': None, 'o': (12, 12, 18)}

def make_glasses():
    H, W = len(GLASSES_ART), 10
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(GLASSES_ART):
        for col, ch in enumerate(line[:W]):
            c = GLASSES_CMAP.get(ch)
            if c:
                s.set_at((col, row), (*c, 255))
    return s

GLASSES_BASE = make_glasses()

# ── 고양이 귀 픽셀 아트 ───────────────────────────────────────
CAT_EARS_ART = [
    "oo......oo",   # 10자: 귀 끝
    "oXo....oXo",   # 분홍 속귀
    "ooo....ooo",   # 귀 밑
    "oooooooooo",   # 연결 베이스
]
CAT_EARS_CMAP = {'.': None, 'o': (28, 20, 30), 'X': (255, 145, 175)}

def make_cat_ears():
    H, W = len(CAT_EARS_ART), 10
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(CAT_EARS_ART):
        for col, ch in enumerate(line[:W]):
            c = CAT_EARS_CMAP.get(ch)
            if c:
                s.set_at((col, row), (*c, 255))
    return s

CAT_EARS_BASE = make_cat_ears()

# ── 인간 코 픽셀 아트 (9×7) ──────────────────────────────────
NOSE_ART = [
    "....n....",   # 9자
    "...nnn...",
    "..nnnnn..",
    ".nnnnnnn.",
    ".nnnnnnn.",
    "nnn...nnn",
    "nN.....Nn",   # 콧구멍
]
NOSE_CMAP = {'.': None, 'n': (218, 165, 112), 'N': (145, 95, 52)}

def make_nose():
    H, W = len(NOSE_ART), 9
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(NOSE_ART):
        for col, ch in enumerate(line[:W]):
            c = NOSE_CMAP.get(ch)
            if c:
                s.set_at((col, row), (*c, 255))
    return s

NOSE_BASE = make_nose()

# ── 돼지코 픽셀 아트 (5×3) ───────────────────────────────────
PIG_NOSE_ART = [
    ".PPP.",   # 5자
    "PNpNP",
    ".PPP.",
]
PIG_NOSE_CMAP = {'.': None, 'P': (228, 145, 135), 'p': (248, 180, 170), 'N': (75, 32, 28)}

def make_pig_nose():
    H, W = len(PIG_NOSE_ART), 5
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(PIG_NOSE_ART):
        for col, ch in enumerate(line[:W]):
            c = PIG_NOSE_CMAP.get(ch)
            if c:
                s.set_at((col, row), (*c, 255))
    return s

PIG_NOSE_BASE = make_pig_nose()

# ── 돼지 귀 픽셀 아트 (6×3) ──────────────────────────────────
PIG_EARS_ART = [
    ".P....P.",   # 8자: 뾰족한 귀 끝, 넓은 간격
    "PP....PP",   # 귀 밑 (연결 없음)
]
PIG_EARS_CMAP = {'.': None, 'P': (228, 145, 135)}

def make_pig_ears():
    H, W = len(PIG_EARS_ART), len(PIG_EARS_ART[0])
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(PIG_EARS_ART):
        for col, ch in enumerate(line[:W]):
            c = PIG_EARS_CMAP.get(ch)
            if c:
                s.set_at((col, row), (*c, 255))
    return s

PIG_EARS_BASE = make_pig_ears()

# ── 픽셀 아트 안경 (12×4) ────────────────────────────────────
GLASSES_DISGUISE_ART = [
    ".XXXX.XXXX..",   # 12자: 두 렌즈 테두리 윗선
    "XhhhXoXhhhX.",   # 렌즈(h) + 브릿지(o)
    "XhhhXoXhhhX.",
    ".XXXX.XXXX..",   # 두 렌즈 테두리 아랫선
]
GLASSES_DISGUISE_CMAP = {'.':None,'X':(14,11,11),'h':(55,50,58),'o':(14,11,11)}

def make_glasses_disguise():
    H, W = len(GLASSES_DISGUISE_ART), 12
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(GLASSES_DISGUISE_ART):
        for col, ch in enumerate(line[:W]):
            c = GLASSES_DISGUISE_CMAP.get(ch)
            if c: s.set_at((col, row), (*c, 255))
    return s

GLASSES_DISGUISE = make_glasses_disguise()

# ── 픽셀 아트 콧수염 (10×3) ──────────────────────────────────
MUSTACHE_ART = [
    "MMMMMMMMMM",   # 10자: 수염 윗줄
    "MM.MMMM.MM",   # 가운데 가름
    ".MM.MM.MM.",   # 끝이 말리는 느낌
]
MUSTACHE_CMAP = {'.':None,'M':(20,16,15)}

def make_mustache():
    H, W = len(MUSTACHE_ART), 10
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(MUSTACHE_ART):
        for col, ch in enumerate(line[:W]):
            c = MUSTACHE_CMAP.get(ch)
            if c: s.set_at((col, row), (*c, 255))
    return s

MUSTACHE_DISGUISE = make_mustache()

# ── 천사 링 픽셀 아트 (11×3) ─────────────────────────────────
HALO_ART = [
    "..ooooooo..",
    ".o.......o.",
    "..ooooooo..",
]
HALO_CMAP = {'.': None, 'o': (255, 225, 28)}

def make_halo():
    H, W = len(HALO_ART), 11
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(HALO_ART):
        for col, ch in enumerate(line[:W]):
            c = HALO_CMAP.get(ch)
            if c:
                s.set_at((col, row), (*c, 255))
    return s

HALO_BASE = make_halo()

# ── 왕관 픽셀 아트 (11×3) ────────────────────────────────────
CROWN_ART = [
    "o....o....o",   # 11자: 세 뾰족 꼭대기
    "oo...o...oo",
    "ooooooooooo",
]
CROWN_CMAP = {'.': None, 'o': (255, 200, 28)}

def make_crown():
    H, W = len(CROWN_ART), 11
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(CROWN_ART):
        for col, ch in enumerate(line[:W]):
            c = CROWN_CMAP.get(ch)
            if c:
                s.set_at((col, row), (*c, 255))
    return s

CROWN_BASE = make_crown()

# ── 수염 픽셀 아트 (9×5) ─────────────────────────────────────
BEARD_ART = [
    "wwwwwwwww",   # 9자: 수염 윗줄
    "w.w.w.w.w",
    "..w.w.w..",
    "...w.w...",
    "....w....",   # 끝 모아짐
]
BEARD_CMAP = {'.': None, 'w': (245, 245, 248)}

def make_beard():
    H, W = len(BEARD_ART), 9
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(BEARD_ART):
        for col, ch in enumerate(line[:W]):
            c = BEARD_CMAP.get(ch)
            if c:
                s.set_at((col, row), (*c, 255))
    return s

BEARD_BASE = make_beard()

# ── 토끼 귀 픽셀 아트 (8×6) ──────────────────────────────────
RABBIT_EARS_ART = [
    "oo....oo",   # 8자: 귀 끝
    "oXo..oXo",   # 분홍 속귀
    "oXo..oXo",
    "oXo..oXo",   # 길쭉한 귀 몸통
    "ooo..ooo",   # 귀 밑 벌어짐
    "oooooooo",   # 머리와 연결
]
RABBIT_EARS_CMAP = {'.': None, 'o': (28, 20, 28), 'X': (255, 172, 192)}

def make_rabbit_ears():
    H, W = len(RABBIT_EARS_ART), 8
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(RABBIT_EARS_ART):
        for col, ch in enumerate(line[:W]):
            c = RABBIT_EARS_CMAP.get(ch)
            if c: s.set_at((col, row), (*c, 255))
    return s

RABBIT_EARS_BASE = make_rabbit_ears()

# ── 마왕 왕관 픽셀 아트 (12×4, 흰색 → 런타임에 빨간색으로 틴팅) ─
DEMON_CROWN_ART = [
    "..X..XX..X..",   # 12자: 3 스파이크 (중앙이 2칸 = 가장 높음)
    ".XX.XXXX.XX.",   # 스파이크 넓어짐
    "XXXXXXXXXXXX",   # 왕관 상단
    "XGGGRGGGGgX.",   # 금 + 빨간 보석
    "BBBBBBBBBBBB",   # 밑면
]
DEMON_CROWN_CMAP = {
    '.': None,
    'X': (12, 10, 10),    # 거의 검정
    'G': (85,  58,  2),   # 매우 어두운 금
    'g': (112, 80,  8),   # 어두운 금 하이라이트
    'R': (155, 10, 10),   # 어두운 빨간 보석
    'B': (55,  35,  0),   # 거의 검정 밑면
}

def make_demon_crown():
    H, W = len(DEMON_CROWN_ART), 12
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(DEMON_CROWN_ART):
        for col, ch in enumerate(line[:W]):
            c = DEMON_CROWN_CMAP.get(ch)
            if c: s.set_at((col, row), (*c, 255))
    return s

DEMON_CROWN_BASE = make_demon_crown()

# ── 탑햇 픽셀 아트 (12×6) ────────────────────────────────────
TOP_HAT_ART = [
    ".....XX.....",   # 12자: 좁은 꼭대기
    "....XXXX....",   # 모자 몸통
    "....XXXX....",
    "....BBBB....",   # B = 모자 밴드 (포인트 색)
    "XXXXXXXXXXXX",   # 챙 (가장 넓음)
    ".XXXXXXXXXX.",   # 챙 아랫면
]
TOP_HAT_CMAP = {'.':None,'X':(20,16,20),'B':(200,55,100)}

def make_top_hat():
    H, W = len(TOP_HAT_ART), 12
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(TOP_HAT_ART):
        for col, ch in enumerate(line[:W]):
            c = TOP_HAT_CMAP.get(ch)
            if c: s.set_at((col, row), (*c, 255))
    return s

TOP_HAT_BASE = make_top_hat()

# ── 리본/나비 넥타이 픽셀 아트 (8×5) ─────────────────────────
RIBBON_ART = [
    "Rr....rR",   # 8자: 나비 날개 끝
    ".RrrrrR.",   # 안쪽 날개
    "..RllR..",   # 가운데 매듭 (l=밝은 하이라이트)
    ".RrrrrR.",   # 안쪽 날개
    "Rr....rR",   # 날개 끝
]
RIBBON_CMAP = {'.':None,'R':(215,52,90),'r':(248,108,142),'l':(255,172,192)}

def make_ribbon():
    H, W = len(RIBBON_ART), 8
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(RIBBON_ART):
        for col, ch in enumerate(line[:W]):
            c = RIBBON_CMAP.get(ch)
            if c: s.set_at((col, row), (*c, 255))
    return s

RIBBON_BASE = make_ribbon()

# ── 뇌 픽셀 아트 (10×5, 구름 모양 도트) ─────────────────────
BRAIN_ART = [
    "..bb.bb...",   # 10자: 두 볼록 꼭대기
    ".bBBbBBb..",   # 볼록에 하이라이트
    "bBBBbBBBb.",   # 옆으로 퍼짐
    "bBBBBBBBBb",   # 가장 넓은 원형
    "bBBBBBBBBb",
    ".bBBBBBBb.",   # 아래쪽 좁아짐
    "..bbbbbb..",   # 바닥 곡선
]
BRAIN_CMAP = {'.': None, 'b': (198, 55, 85), 'B': (232, 102, 135)}

def make_brain():
    H, W = len(BRAIN_ART), 10
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    for row, line in enumerate(BRAIN_ART):
        for col, ch in enumerate(line[:W]):
            c = BRAIN_CMAP.get(ch)
            if c:
                s.set_at((col, row), (*c, 255))
    return s

BRAIN_BASE = make_brain()

# ── 인벤토리 페이지 버튼 영역 ──────────────────────────────────
INV_PREV_RECT = pygame.Rect(15, HEIGHT-48, 78, 28)
INV_NEXT_RECT = pygame.Rect(WIDTH-93, HEIGHT-48, 78, 28)

# ── 가짜 해파리 얼굴 이미지 로딩 ──────────────────────────────
def load_face_img(path, max_dim=160, threshold=235):
    img = pygame.image.load(path).convert_alpha()
    W, H = img.get_size()
    sc = min(1.0, max_dim / max(W, H))
    img = pygame.transform.scale(img, (max(1,int(W*sc)), max(1,int(H*sc))))
    W, H = img.get_size()
    # 흰 배경 flood-fill 제거
    visited = [[False]*H for _ in range(W)]
    stack = []
    for x in range(0, W, 2): stack += [(x,0),(x,H-1)]
    for y in range(0, H, 2): stack += [(0,y),(W-1,y)]
    while stack:
        px, py = stack.pop()
        if not (0<=px<W and 0<=py<H) or visited[px][py]: continue
        r,g,b,a = img.get_at((px,py))
        if min(r,g,b) < threshold: continue
        visited[px][py] = True
        img.set_at((px,py),(r,g,b,0))
        stack += [(px+1,py),(px-1,py),(px,py+1),(px,py-1)]
    return img

FAKE_FACE_IMG = None  # 가짜 해파리 제거됨


def make_bell_sprite(defn):
    art, cmap, ps = defn['art'], defn['cmap'], defn['ps']
    BH = len(art)
    s = pygame.Surface((W_PIX, BH), pygame.SRCALPHA)
    for row, line in enumerate(art):
        for col, ch in enumerate(line[:W_PIX]):
            c = cmap.get(ch)
            if c:
                s.set_at((col, row), (*c, 255))
    if defn.get('eyes', True):
        ey  = BH - 3
        ec  = defn.get('eye_color', (12, 12, 32))
        s.set_at((W_PIX//2-2, ey), (*ec, 255))
        s.set_at((W_PIX//2+1, ey), (*ec, 255))
    return pygame.transform.scale(s, (W_PIX*ps, BH*ps))

BELL_SPRITES = [make_bell_sprite(d) for d in JELLY_DEFS]

# ── 무지개 해파리 ─────────────────────────────────────────────
JELLY_CHAT_MSGS = [
    "우릴 먹을거야?", "저 잡지마세요..", "안녕하세요!", "여기 좋다~",
    "배고파...", "저 잡으려고요?", "도망칠게요!", "오늘 날씨 좋다",
    "졸려...", "친구가 없어요", "같이 놀아요!", "낯선 분이에요",
    "여기가 어디죠?", "살려줘요!", "얍!", "조용히 해줘요",
    "나 예쁘죠?", "나 좀 봐줘요", "으아아~", "뭘 보는 거예요?",
    "우리 사이좋게 지내요", "쉬고싶다...", "이 바다 맘에 들어요",
]

RAINBOW_HUES = [
    (255,  65,  65),  # 빨강
    (255, 148,  20),  # 주황
    (255, 222,  20),  # 노랑
    ( 50, 210,  70),  # 초록
    ( 38, 140, 255),  # 파랑
    (100,  65, 218),  # 남색
    (188,  58, 215),  # 보라
    (228,  62, 185),  # 핑크보라
]

def make_rainbow_bell_sprite():
    art = JELLY_DEFS[0]['art']
    BH  = len(art)
    ps  = 4
    raw = pygame.Surface((W_PIX, BH), pygame.SRCALPHA)
    for row, line in enumerate(art):
        r, g, b = RAINBOW_HUES[row % len(RAINBOW_HUES)]
        cmap = {
            '.': None,
            'X': (max(0,r-85), max(0,g-80), max(0,b-80)),
            'D': (r, g, b),
            'M': (min(255,r+38), min(255,g+38), min(255,b+38)),
            'H': (min(255,r+90), min(255,g+90), min(255,b+90)),
        }
        for col, ch in enumerate(line[:W_PIX]):
            c = cmap.get(ch)
            if c:
                raw.set_at((col, row), (*c, 255))
    ey = BH - 3
    raw.set_at((W_PIX//2-2, ey), (20, 20, 40, 255))
    raw.set_at((W_PIX//2+1, ey), (20, 20, 40, 255))
    return pygame.transform.scale(raw, (W_PIX*ps, BH*ps))

RAINBOW_BELL_SPRITE = make_rainbow_bell_sprite()

def make_player_bell_sprite():
    """온라인 플레이어 아바타: 살색 해파리."""
    cmap_p = {'.':None,'X':(192,128,92),'D':(228,175,132),'M':(252,210,168),'H':(255,238,215)}
    art = JELLY_DEFS[0]['art']
    BH = len(art); ps = 4
    raw = pygame.Surface((W_PIX, BH), pygame.SRCALPHA)
    for row, line in enumerate(art):
        for col, ch in enumerate(line[:W_PIX]):
            c = cmap_p.get(ch)
            if c: raw.set_at((col, row), (*c, 255))
    ey = BH - 3
    raw.set_at((W_PIX//2-2, ey), (80, 40, 20, 255))
    raw.set_at((W_PIX//2+1, ey), (80, 40, 20, 255))
    return pygame.transform.scale(raw, (W_PIX*ps, BH*ps))

PLAYER_BELL_SPRITE = make_player_bell_sprite()

def _make_headset_sprite():
    _path = r'C:\Users\dorong\Downloads\49b430fecb4afb177a81492554d7a983.jpg'
    if not os.path.exists(_path): return None
    try:
        raw = pygame.image.load(_path)
        # 작업 크기로 축소 후 배경 제거
        sz = 96
        small = pygame.transform.scale(raw, (sz, sz))
        result = pygame.Surface((sz, sz), pygame.SRCALPHA)
        result.fill((0,0,0,0))
        for _y in range(sz):
            for _x in range(sz):
                _r,_g,_b = small.get_at((_x,_y))[:3]
                # 흰색/밝은 회색 배경 제거
                if _r > 225 and _g > 225 and _b > 225: continue
                result.set_at((_x,_y), (_r,_g,_b,255))
        return result
    except: return None

HEADSET_SPRITE = _make_headset_sprite()

def make_twin_bell_sprite():
    """쌍둥이 해파리: 두 머리가 공유 몸통으로 붙은 커스텀 20×8 아트."""
    TWIN_W = 20
    cmap_t = {'.':None,'X':(145,92,178),'D':(185,135,215),'M':(218,172,238),'H':(242,215,252)}
    twin_art = [
        ".....XXXX..XXXX.....",   # 20
        "...XXDDDDXXDDDDXX...",   # 20
        "..XDDMMMMDDMMMMDDX..",   # 20
        ".XDDMMHHMMMMHHMMDDX.",   # 20 (우측 col18)
        ".XDDMHHHHHHHHHHMDDX.",   # 20
        ".XDDMMMMMMMMMMMMDDX.",   # 20
        ".XDDDDDDDDDDDDDDDDX.",   # 20
        ".XXXXXXXXXXXXXXXXXX.",   # 20
    ]
    BH = len(twin_art); ps = 4
    raw = pygame.Surface((TWIN_W, BH), pygame.SRCALPHA)
    for row, line in enumerate(twin_art):
        for col, ch in enumerate(line[:TWIN_W]):
            c = cmap_t.get(ch)
            if c:
                raw.set_at((col, row), (*c, 255))
    ey = BH - 3; ec = (20,20,40,255)
    raw.set_at((5, ey), ec); raw.set_at((8, ey), ec)
    raw.set_at((11,ey), ec); raw.set_at((14,ey), ec)
    return pygame.transform.scale(raw, (TWIN_W*ps, BH*ps))

TWIN_BELL_SPRITE = make_twin_bell_sprite()

def make_pabun_bell_sprite():
    """파분 해파리: 좌절반 파랑, 우절반 분홍 (세로 중앙 기준 반반)."""
    blue_def = JELLY_DEFS[0]   # 파란 해파리 cmap
    pink_def = JELLY_DEFS[1]   # 분홍 해파리 cmap
    art = blue_def['art']
    BH  = len(art)
    ps  = 4
    raw = pygame.Surface((W_PIX, BH), pygame.SRCALPHA)
    mid = W_PIX // 2
    for row, line in enumerate(art):
        for col, ch in enumerate(line[:W_PIX]):
            cmap = blue_def['cmap'] if col < mid else pink_def['cmap']
            c = cmap.get(ch)
            if c:
                raw.set_at((col, row), (*c, 255))
    ey = BH - 3
    raw.set_at((W_PIX//2-2, ey), (12,12,32,255))
    raw.set_at((W_PIX//2+1, ey), (12,12,32,255))
    return pygame.transform.scale(raw, (W_PIX*ps, BH*ps))

PABUN_BELL_SPRITE = make_pabun_bell_sprite()

# ── 언락 스테이지 ─────────────────────────────────────────────
_current_stage = 1   # 1~6단계

def get_stage(inventory):
    return 1  # 호환성 유지용

def get_unlocked_slots(inventory):
    """획득 조건에 따라 해금된 design_idx 집합 반환."""
    i = inventory
    u = {0}  # 파랑 기본 해금 (푸딩/소다/벚꽃/쌍둥이=lock or 교배전용)
    if i.get(0,0)>=5:                            u.add(1)   # 분홍
    if i.get(1,0)>=10:                           u.add(2)   # 개구리모자
    if i.get(2,0)>=6:                            u.add(3)   # 안경
    if i.get(3,0)>=9:                            u.add(4)   # 전기
    if i.get(4,0)>=10:                           u.add(5)   # 고양이
    if i.get(5,0)>=4:                            u.add(6)   # 슬라임
    if i.get(6,0)>=5:                            u.add(7)   # 얼어붙은
    if i.get(7,0)>=5:                            u.add(8)   # 천사
    if i.get(8,0)>=4:                            u.add(9)   # 유령
    if i.get(9,0)>=5:                            u.add(10)  # 털복숭이
    if i.get(10,0)>=4:                           u.add(11)  # 해파리왕
    if i.get(11,0)>=3:                           u.add(12)  # 썩은
    if i.get(12,0)>=3:                           u.add(13)  # 심해
    if i.get(13,0)>=5:                           u.add(14)  # 구름
    if i.get(14,0)>=2:                           u.add(15)  # 화난
    if i.get(15,0)>=2:                           u.add(16)  # 멋쟁이
    if i.get(16,0)>=3:                           u.add(17)  # 토끼
    if i.get(17,0)>=4:                           u.add(18)  # 저주받은
    if i.get(18,0)>=1:                           u.add(19)  # 선인장
    if i.get(19,0)>=6:                           u.add(20)  # 눈사람
    if i.get(20,0)>=10:                          u.add(21)  # 황금
    return u

_unlocked_slots = {0}
_bred_slots     = set()   # 교배로 해금된 시크릿 해파리

def update_unlocked_slots(inventory):
    global _unlocked_slots
    _unlocked_slots = get_unlocked_slots(inventory)


def lerp_color(c1, c2, t):
    return tuple(int(c1[i]+(c2[i]-c1[i])*t) for i in range(3))


MAKE_BTN_RECT      = pygame.Rect(WIDTH//2 - 58, HEIGHT - 52, 116, 34)
INTRO_NEW_BTN      = pygame.Rect(WIDTH//2 - 88, 320, 176, 52)
INTRO_CONT_BTN     = pygame.Rect(WIDTH//2 - 88, 388, 176, 52)
WARN_OK_BTN        = pygame.Rect(WIDTH//2 - 90, HEIGHT//2 + 42, 84, 36)
WARN_CANCEL_BTN    = pygame.Rect(WIDTH//2 + 6,  HEIGHT//2 + 42, 84, 36)
GACHA_CONFIRM_RECT = pygame.Rect(WIDTH//2 - 52, HEIGHT - 58, 104, 34)
GACHA_TOTAL        = 300

# ── 가방 아이콘 ───────────────────────────────────────────────
BAG_RECT      = pygame.Rect(WIDTH-48,  6, 38, 38)
SCROLL_RECT   = pygame.Rect(WIDTH-48, 50, 38, 38)
AQUARIUM_RECT = pygame.Rect(WIDTH-48,  94, 38, 38)
RANKING_RECT   = pygame.Rect(WIDTH-48, 138, 38, 38)
SETTINGS_RECT  = pygame.Rect(6,  6, 38, 38)
ONLINE_RECT    = pygame.Rect(6, 50, 38, 38)
OW = 380; OH_PLAY = 430; OH_CHAT = 130  # 온라인 월드 치수
# 설정 화면 슬라이더 (x, y, width)
SL_BGM  = (50, 175, WIDTH-100)
SL_SFX  = (50, 248, WIDTH-100)
SL_CHAT = (50, 321, WIDTH-100)
AQ_L, AQ_R, AQ_T, AQ_B = 18, WIDTH-18, 82, HEIGHT-72
AQUARIUM_ADD_BTN = pygame.Rect(WIDTH//2-52, HEIGHT-46, 104, 30)
AQ_BACK_RECT     = pygame.Rect(15, 12, 75, 28)
AQ_WARDROBE_RECT = pygame.Rect(WIDTH-46, 46, 30, 28)
WARDROBE_ITEM_DEFS = [
    ('angel_halo',    '천사 링'),
    ('crown',         '황금 왕관'),
    ('glasses',       '동그란 안경'),
    ('ribbon',        '분홍 리본'),
    ('hat',           '마법사 모자'),
    ('redcap',        '빨간 캡모자'),
    ('headset',       '헤드셋'),
    ('deep_orb',      '심해 구슬'),
    ('angry_brow',    '화난 눈썹'),
    ('rabbit_ears',   '토끼 귀'),
    ('cherry_top',    '체리 토핑'),
    ('frog_hat_item', '개구리 모자'),
    ('foxfire',       '여우불'),
    ('blossom_pin',   '벚꽃 핀'),
]
# 특정 해파리만 드랍 가능 (design_idx → item_id 목록). 없으면 공용 드랍
WARDROBE_DROP_MAP = {
    11: ['crown'],             # 해파리 왕
    16: ['hat'],               # 멋쟁이 해파리
    3:  ['glasses'],           # 안경 해파리
    23: ['ribbon'],            # 파분 해파리
    13: ['deep_orb'],          # 심해 해파리
    15: ['angry_brow'],        # 화난 해파리
    17: ['rabbit_ears'],       # 토끼 해파리
    24: ['cherry_top'],        # 푸딩 해파리
    25: ['cherry_top'],        # 소다맛 푸딩 해파리
    2:  ['frog_hat_item'],     # 개구리 모자 해파리
    18: ['foxfire'],           # 저주받은 해파리
    26: ['blossom_pin'],       # 벚꽃 해파리
    8:  ['angel_halo'],        # 천사 해파리
}
WARDROBE_COMMON_DROPS = ['redcap', 'headset']
DEV_RESET_BACK   = pygame.Rect(15, 12, 75, 28)

def draw_bag_icon(surf, rect, has_new):
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    pygame.draw.rect(surf, (148,112,68), (x+w//4, y+2, w//2, h//3), 3, border_radius=4)
    by = y+h//4; bh = h-h//4-2
    pygame.draw.rect(surf, (198,162,105), (x+2, by, w-4, bh), border_radius=5)
    pygame.draw.rect(surf, (148,112,68),  (x+2, by, w-4, bh), 2, border_radius=5)
    cy2 = by+bh//2
    pygame.draw.rect(surf, (222,188,130), (x+w//2-6, cy2-3, 12,6), border_radius=2)
    pygame.draw.rect(surf, (148,112,68),  (x+w//2-6, cy2-3, 12,6), 1, border_radius=2)
    if has_new:
        bx2, by2 = x+w-7, y+7
        pygame.draw.circle(surf, (230,60,60), (bx2, by2), 8)
        f = get_font(13, bold=True)
        t = f.render('!', True, (255,255,255))
        surf.blit(t, (bx2-t.get_width()//2, by2-t.get_height()//2))


def draw_scroll_icon(surf, rect, has_new):
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    # 종이 배경
    pygame.draw.rect(surf, (242, 235, 210), (x+4, y+3, w-8, h-6), border_radius=3)
    pygame.draw.rect(surf, (188, 165, 118), (x+4, y+3, w-8, h-6), 1, border_radius=3)
    # 접힌 귀퉁이 (오른쪽 위)
    pygame.draw.polygon(surf, (210, 198, 168),
                        [(x+w-10, y+3), (x+w-4, y+9), (x+w-4, y+3)])
    pygame.draw.line(surf, (188,165,118), (x+w-10,y+3), (x+w-4,y+9), 1)
    # 줄 3개
    lc = (168, 145, 100)
    for i in range(3):
        ly = y + 11 + i * 7
        pygame.draw.line(surf, lc, (x+8, ly), (x+w-10, ly), 1)
    if has_new:
        bx2, by2 = x+w-7, y+7
        pygame.draw.circle(surf, (230, 60, 60), (bx2, by2), 8)
        f = get_font(13, bold=True)
        t = f.render('!', True, (255,255,255))
        surf.blit(t, (bx2-t.get_width()//2, by2-t.get_height()//2))


def draw_aquarium_icon(surf, rect):
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    # 탱크 프레임
    pygame.draw.rect(surf, (162, 132, 80), (x+2, y+4, w-4, h-8), border_radius=3)
    # 물
    pygame.draw.rect(surf, (32, 82, 168), (x+4, y+6, w-8, h-13), border_radius=2)
    pygame.draw.rect(surf, (78, 148, 225), (x+4, y+6, w-8, 4),   border_radius=2)
    # 모래
    pygame.draw.rect(surf, (185,162,108), (x+4, y+h-11, w-8, 6), border_radius=2)
    # 작은 물고기 (bouncing dot)
    t22 = pygame.time.get_ticks() * 0.001
    bx2 = x+6 + int((w-14)*(0.5+math.sin(t22*1.5)*0.38))
    by2 = y+9 + int((h-22)*(0.4+math.sin(t22*0.9)*0.3))
    pygame.draw.circle(surf, (145, 215, 255), (bx2, by2), 3)
    pygame.draw.circle(surf, (200, 240, 255), (bx2-1, by2-1), 1)
    # 거품
    bub_x = x+8+int((w-18)*(0.5+math.sin(t22*2.2)*0.35))
    bub_y = y+6+int((h-16)*(0.5+math.cos(t22*1.8)*0.3))
    pygame.draw.circle(surf, (150, 210, 255, 120), (bub_x, bub_y), 2)
    # 테두리
    pygame.draw.rect(surf, (128, 100, 52), (x+2, y+4, w-4, h-8), 1, border_radius=3)


# ── 어항 해파리 ───────────────────────────────────────────────
class GlassBottle:
    _LAND_Y = AQ_B - 26

    def __init__(self, x, spawn_y=None, item=None):
        self.x = float(x)
        self.y = float(spawn_y if spawn_y is not None else AQ_T + 10)
        self.vy = 0.25
        self.landed = False
        self.bounce_v = 0.0
        if item is None: item = random.choice(WARDROBE_ITEM_DEFS)
        self.item_id, self.item_name = item
        self.collected = False

    def update(self):
        if self.collected: return False
        if not self.landed:
            self.vy = min(self.vy + 0.04, 3.2)
            self.y += self.vy
            if self.y >= self._LAND_Y:
                self.y = self._LAND_Y
                self.vy = -self.vy * 0.32
                if abs(self.vy) < 0.6: self.landed = True; self.vy = 0
        else:
            if self.bounce_v != 0:
                self.y += self.bounce_v
                self.bounce_v *= 0.7
                if abs(self.bounce_v) < 0.2: self.bounce_v = 0
        return True

    def hit_test(self, mx, my):
        return abs(mx - self.x) < 14 and abs(my - self.y) < 24

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        # bottle neck
        pygame.draw.rect(surf, (155, 208, 238), (x-3, y-20, 6, 10), border_radius=2)
        # cork
        pygame.draw.rect(surf, (195, 155, 88), (x-4, y-24, 8, 5), border_radius=2)
        # body
        pygame.draw.ellipse(surf, (148, 208, 240), (x-9, y-12, 18, 20))
        pygame.draw.ellipse(surf, (90, 165, 210), (x-9, y-12, 18, 20), 1)
        # shine
        pygame.draw.line(surf, (215, 242, 255), (x-4, y-8), (x-4, y+2), 2)
        # scroll inside
        pygame.draw.rect(surf, (245, 235, 200), (x-3, y-5, 7, 8), border_radius=1)


class AquariumFish:
    def __init__(self, design_idx):
        self.design_idx = design_idx
        sf = random.uniform(0.82, 1.18)
        self.bw0 = int(52 * sf)
        self.bh0 = int(38 * sf)
        self.x  = random.uniform(AQ_L+40, AQ_R-40)
        self.y  = random.uniform(AQ_T+40, AQ_B-60)
        self.vx = random.uniform(-0.55, 0.55) or 0.3
        self.vy = random.uniform(-0.28, 0.28)
        self.pulse      = random.uniform(0, math.pi*2)
        self.pulse_spd  = random.uniform(0.022, 0.045)
        self.drift_ph   = random.uniform(0, math.pi*2)
        self.drift_spd  = random.uniform(0.005, 0.012)
        self.tent_ph    = random.uniform(0, math.pi*2)
        self.tent_spd   = random.uniform(0.034, 0.06)
        self.happy_timer  = 0
        self.dance_phase  = 0.0
        self.click_squish = 0.0

    def update(self):
        self.pulse    += self.pulse_spd
        self.drift_ph += self.drift_spd
        self.tent_ph  += self.tent_spd
        self.x += self.vx + math.sin(self.drift_ph) * 0.32
        self.y += self.vy + math.sin(self.pulse)     * 0.16
        hw, hh = self.bw0//2+5, self.bh0//2+8
        if self.x < AQ_L + hw: self.vx =  abs(self.vx)*0.85 + 0.12
        if self.x > AQ_R - hw: self.vx = -abs(self.vx)*0.85 - 0.12
        if self.y < AQ_T + hh: self.vy =  abs(self.vy)*0.85 + 0.08
        if self.y > AQ_B - hh - 18: self.vy = -abs(self.vy)*0.85 - 0.08
        self.vx = max(-1.1, min(1.1, self.vx))
        self.vy = max(-0.7, min(0.7, self.vy))
        if self.happy_timer > 0:
            self.happy_timer -= 1
            self.dance_phase  += 0.15
        if self.click_squish > 0:
            self.click_squish = max(0.0, self.click_squish - 0.055)

    def feed(self):
        self.happy_timer = 120
        self.dance_phase  = 0.0

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        sq = math.cos(self.pulse*0.7)*0.08 + math.sin(self.click_squish*math.pi)*0.32
        # 웨이브 댄스
        hp_ratio = self.happy_timer / 210.0
        if self.happy_timer > 0:
            sq += math.cos(self.dance_phase*3)*0.28*hp_ratio   # 꿀렁 스쿼시
            x  += int(math.sin(self.dance_phase*2)*3*hp_ratio)  # 살짝 좌우
            y  += int(math.sin(self.dance_phase*3)*4*hp_ratio)  # 위아래 통통
        bw  = max(8, int(self.bw0*(1+sq)))
        bh  = max(4, int(self.bh0*(1-sq*0.5)))
        bi  = _slot_base_idx(self.design_idx)
        spr = (RAINBOW_BELL_SPRITE if self.design_idx==22
               else PABUN_BELL_SPRITE if self.design_idx==23
               else TWIN_BELL_SPRITE  if self.design_idx==27
               else BELL_SPRITES[bi])
        spr = pygame.transform.scale(spr, (bw, bh))
        if self.design_idx == 9:   spr.set_alpha(72)
        elif self.design_idx == 6: spr.set_alpha(175)
        defn_aq = JELLY_DEFS[bi]
        # 전기 해파리 스파크
        if self.design_idx == 4:
            t_e = pygame.time.get_ticks() * 0.001
            ps_e = max(2, bw//12)
            for i_e in range(10):
                r_e  = 0.18 + abs(math.sin(t_e*2.3+i_e*1.8))*0.52
                sx_e = x + int(math.sin(t_e*7.1+i_e*2.5)*bw*r_e)
                sy_e = y + int(math.sin(t_e*6.3+i_e*1.9)*bh*r_e*0.75)
                vis  = abs(math.sin(t_e*11.3+i_e*3.1))
                if vis < 0.50: continue
                br = 205+int(vis*50)
                col_e = (br, int(br*0.90), 8)
                seg_e = 1+int(abs(math.sin(t_e*5.7+i_e*1.3))*2)
                ori   = int(abs(t_e*3.1+i_e*2.7))%4
                if ori==0: pygame.draw.rect(surf,col_e,(sx_e,sy_e,seg_e*ps_e,ps_e))
                elif ori==1: pygame.draw.rect(surf,col_e,(sx_e,sy_e,ps_e,seg_e*ps_e))
                elif ori==2:
                    for k_e in range(seg_e): pygame.draw.rect(surf,col_e,(sx_e+k_e*ps_e,sy_e-k_e*ps_e,ps_e,ps_e))
                else:
                    for k_e in range(seg_e): pygame.draw.rect(surf,col_e,(sx_e+k_e*ps_e,sy_e+k_e*ps_e,ps_e,ps_e))
                pygame.draw.rect(surf,(255,255,215),(sx_e,sy_e,ps_e,ps_e))
        surf.blit(spr, (x-bw//2, y-bh//2))
        _draw_slot_overlay(surf, self.design_idx, x, y-bh//2+4, bw, bh, happy=self.happy_timer>0)

        # 눈웃음 (∩ 모양)
        defn_aq = JELLY_DEFS[bi]

        # 하트 파티클 — 세 개가 일정 간격으로 위로 떠오름
        if self.happy_timer > 0:
            for hk in range(3):
                t_h  = ((self.dance_phase/(math.pi*2)) + hk/3.0) % 1.0
                hpx  = x + (hk-1)*16
                hpy  = int(y - bh//2 - 10 - t_h*38)
                hpa  = int((1-t_h)*hp_ratio*210)
                if hpa > 8 and AQ_T < hpy < AQ_B:
                    hpa2 = min(255, int(hpa * 2.0))
                    hs = pygame.Surface((18,18),pygame.SRCALPHA)
                    pygame.draw.circle(hs,(255,85,128,hpa2),(5,5),4)
                    pygame.draw.circle(hs,(255,85,128,hpa2),(12,5),4)
                    pygame.draw.polygon(hs,(255,85,128,hpa2),[(1,8),(16,8),(8,16)])
                    surf.blit(hs,(hpx-9,hpy-9))

        # 촉수
        tc  = JELLY_DEFS[bi]['tc']
        if self.design_idx == 7:  # 얼어붙은: 정적 픽셀 촉수
            th_f  = max(6, int(bh*0.55)); dot_f = max(2, bw//W_PIX)
            t_s   = pygame.Surface((bw, th_f), pygame.SRCALPHA)
            for bx_pix in [3,6,9,12]:
                bx_f = int(bx_pix*bw/W_PIX)
                for row in range(8):
                    py_f = int(row*th_f/8); ph_f = max(dot_f, int(th_f/8))
                    px_f = max(0, min(bw-dot_f, bx_f))
                    t_s.fill((*tc, max(80,220-row*15)), (px_f,py_f,dot_f,ph_f))
            surf.blit(t_s, (x-bw//2, y+bh//2))
        else:
            amp = 4.0+math.sin(self.dance_phase*3)*2.0 if self.happy_timer>0 else 2.0
            for i, dx_f in enumerate([-0.28,-0.10,0.10,0.28]):
                bx2   = x + int(dx_f*bw)
                base  = int(bw*0.20)
                wave  = int(math.sin(self.tent_ph*1.8+i*1.3)*bw*0.06)
                length= max(5, base+wave+int(amp*2))
                sway  = int(math.sin(self.tent_ph+i)*(1+amp*0.7))
                alp   = 72 if self.design_idx==9 else 195
                s2    = pygame.Surface((14,length+10),pygame.SRCALPHA)

                if self.happy_timer > 0 and i in (0, 3):
                    # 벨 측면에서 위로 뻗는 팔
                    side = -1 if i == 0 else 1
                    wave_arm = int(math.sin(self.tent_ph*2+self.dance_phase)*5)
                    sx_arm = x + side*int(bw*0.44)
                    sy_arm = y + bh//6
                    ex_arm = x + side*int(bw*0.78)
                    ey_arm = y - int(bh*0.55) + wave_arm
                    thick_arm = max(2, bw//18)
                    pygame.draw.line(surf, (*tc,alp), (sx_arm,sy_arm), (ex_arm,ey_arm), thick_arm)
                    pygame.draw.circle(surf, (*tc,int(alp*0.9)), (ex_arm,ey_arm), max(2,thick_arm+1))
                else:
                    pygame.draw.line(s2,(*tc,alp),(7,0),(7+sway,length),3)
                    pygame.draw.circle(s2,(*tc,int(alp*0.9)),(7+sway,length),max(2,length//6))
                    surf.blit(s2,(bx2-7,y+bh//2))

    def hit_test(self, mx, my):
        return abs(mx-self.x) < self.bw0*0.6 and abs(my-self.y) < self.bh0*0.65


class FoodPellet:
    def __init__(self, x, y):
        self.x  = float(x) + random.uniform(-25, 25)
        self.y  = float(y) + random.uniform(-8, 5)
        self.vy = random.uniform(0.35, 0.75)
        self.vx = random.uniform(-0.18, 0.18)
        self.r  = random.randint(4, 6)
        self.alive = True
    def update(self):
        self.y += self.vy; self.x += self.vx
        if self.y > AQ_B - 26: self.alive = False
        return self.alive
    def draw(self, surf):
        r = self.r
        s = pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
        pygame.draw.circle(s,(188,112,42,225),(r+1,r+1),r)
        pygame.draw.circle(s,(218,152,78,185),(r,r),max(1,r-1))
        surf.blit(s,(int(self.x)-r-1,int(self.y)-r-1))


class AquariumContextMenu:
    def __init__(self, fish):
        self.fish = fish
        self.w = 92; self.bh_btn = 34
    def _pos(self):
        total_h = self.bh_btn*2+4
        x = max(4, min(WIDTH-self.w-4, int(self.fish.x)-self.w//2))
        y = max(4, min(HEIGHT-total_h-4,
                       int(self.fish.y)-self.fish.bh0//2-total_h-8))
        return x, y
    def get_feed_rect(self):
        x,y=self._pos(); return pygame.Rect(x,y,self.w,self.bh_btn)
    def get_release_rect(self):
        x,y=self._pos(); return pygame.Rect(x,y+self.bh_btn+4,self.w,self.bh_btn)
    def draw(self, surf):
        for rect,bg,border,tc,label in [
            (self.get_feed_rect(),   (10,48,18,228),(55,188,78), (138,255,152),'먹이주기'),
            (self.get_release_rect(),(8,28,58,228), (55,132,215),(138,202,255),'방생하기'),
        ]:
            btn=pygame.Surface((rect.w,rect.h),pygame.SRCALPHA)
            btn.fill(bg)
            pygame.draw.rect(btn,border,(0,0,rect.w,rect.h),1,border_radius=7)
            surf.blit(btn,rect.topleft)
            ft=get_font(14).render(label,True,tc)
            surf.blit(ft,(rect.x+rect.w//2-ft.get_width()//2,
                          rect.y+rect.h//2-ft.get_height()//2))


def draw_wardrobe_item_icon(surf, cx, cy, item_id, unlocked=True):
    c = lambda lit, dim: lit if unlocked else dim
    if item_id == 'angel_halo':
        hc = c((255,225,28),(60,80,110))
        pygame.draw.ellipse(surf, hc, (cx-10,cy-5,20,8), 2)
        pygame.draw.ellipse(surf, c((255,245,140),(70,90,120)), (cx-7,cy-4,14,5), 1)
    elif item_id == 'ribbon':
        rc = c((254,107,149),(60,80,110))
        pygame.draw.circle(surf, rc, (cx-5,cy), 6)
        pygame.draw.circle(surf, rc, (cx+5,cy), 6)
        pygame.draw.circle(surf, c((255,160,185),(70,90,120)), (cx,cy), 4)
    elif item_id == 'crown':
        cc = c((255,210,55),(60,80,110))
        pts = [(cx-11,cy+5),(cx-7,cy-6),(cx,cy+1),(cx+7,cy-6),(cx+11,cy+5)]
        pygame.draw.polygon(surf, cc, pts)
        for px2 in [cx-7,cx,cx+7]: pygame.draw.circle(surf,c((255,230,100),(70,90,120)),(px2,cy-4),2)
    elif item_id == 'glasses':
        gc = c((30,30,30),(60,80,110))
        pygame.draw.circle(surf, gc, (cx-6,cy), 5, 2)
        pygame.draw.circle(surf, gc, (cx+6,cy), 5, 2)
        pygame.draw.line(surf, gc, (cx-1,cy),(cx+1,cy), 1)
        pygame.draw.line(surf, gc, (cx-11,cy-1),(cx-11,cy+3), 1)
        pygame.draw.line(surf, gc, (cx+11,cy-1),(cx+11,cy+3), 1)
    elif item_id == 'pearl':
        pc = c((245,245,255),(60,80,110))
        for ppx in range(-2,3): pygame.draw.circle(surf, pc, (cx+ppx*6,cy), 4)
        for ppx in range(-2,3): pygame.draw.circle(surf, c((255,255,255),(70,90,120)), (cx+ppx*6-1,cy-1), 1)
    elif item_id in ('bow', 'ribbon'):
        rc2 = c((254,107,149),(60,80,110))
        pygame.draw.circle(surf, rc2, (cx-6,cy), 6)
        pygame.draw.circle(surf, rc2, (cx+6,cy), 6)
        pygame.draw.circle(surf, c((255,160,185),(70,90,120)), (cx,cy), 4)
        pygame.draw.line(surf, c((255,190,210),(50,65,95)), (cx,cy-4),(cx,cy+4),2)
    elif item_id == 'hat':
        hc = c((85,45,150),(60,80,110))
        pygame.draw.ellipse(surf, hc, (cx-11,cy+3,22,7))
        pygame.draw.rect(surf, hc, (cx-5,cy-10,10,15))
        pygame.draw.line(surf, c((205,165,255),(70,90,120)), (cx-4,cy-2),(cx+4,cy-2), 1)
    elif item_id == 'redcap':
        rd = c((185,25,25),(45,55,85)); rm = c((220,40,40),(60,80,110)); rl = c((255,115,115),(70,90,120))
        # 돔 (큰 반원, cx 중심)
        dome = [(int(cx-1+11*math.cos(math.radians(a))), int(cy+4-11*math.sin(math.radians(a)))) for a in range(0,181,10)]
        pygame.draw.polygon(surf, rm, [(cx-12,cy+4)]+dome+[(cx+10,cy+4)])
        # 밴드 라인
        pygame.draw.line(surf, rd, (cx-12,cy+4),(cx+10,cy+4), 2)
        # 챙 (오른쪽, 살짝 아래)
        pygame.draw.polygon(surf, rd, [(cx+8,cy+3),(cx+16,cy+6),(cx+14,cy+8),(cx+7,cy+5)])
        # 하이라이트
        pygame.draw.arc(surf, rl, (cx-7,cy-7,12,9), math.radians(35), math.radians(145), 1)
        # 버튼 (상단)
        pygame.draw.rect(surf, rd, (cx-1,cy-7,3,2), border_radius=1)
    elif item_id == 'deep_orb':
        dc = c((48,218,178),(50,65,95))
        dg = c((180,255,235),(60,80,110))
        # 줄기
        pygame.draw.line(surf, c((35,165,130),(45,60,90)), (cx,cy+2),(cx,cy-7), 2)
        # 외부 글로우
        gs = pygame.Surface((18,18),pygame.SRCALPHA)
        pygame.draw.circle(gs, (*c((48,218,178),(55,70,105)), 60), (9,9), 8)
        surf.blit(gs,(cx-9,cy-17))
        # 구슬 본체
        pygame.draw.circle(surf, dc, (cx,cy-9), 6)
        pygame.draw.circle(surf, dg, (cx-1,cy-11), 3)
        pygame.draw.circle(surf, c((220,255,242),(60,80,110)), (cx-2,cy-11), 1)
    elif item_id == 'rabbit_ears':
        ec = c((28,20,28),(50,60,90)); ic = c((255,172,192),(65,75,110))
        for ex in (cx-6, cx+6):
            pygame.draw.rect(surf, ec, (ex-3,cy-12,6,12), border_radius=3)
            pygame.draw.rect(surf, ic, (ex-2,cy-11,4,9), border_radius=2)
    elif item_id == 'cherry_top':
        # 생크림
        for cxo2,cyo2 in [(0,-4),(-4,0),(4,0),(0,0)]:
            pygame.draw.circle(surf, c((245,245,245),(65,80,115)), (cx+cxo2,cy+cyo2), 5)
        # 체리
        pygame.draw.circle(surf, c((148,8,8),(50,60,90)), (cx,cy-8), 5)
        pygame.draw.circle(surf, c((195,18,18),(60,70,100)), (cx,cy-8), 4)
        pygame.draw.line(surf, c((120,15,15),(45,55,85)), (cx,cy-13),(cx+3,cy-18), 1)
    elif item_id == 'frog_hat_item':
        fc2 = c((45,155,68),(50,65,90)); fl2 = c((85,208,100),(65,80,110))
        # 챙
        pygame.draw.ellipse(surf, fc2, (cx-11,cy+2,22,6))
        # 모자 몸통
        pygame.draw.rect(surf, fc2, (cx-7,cy-8,14,12), border_radius=2)
        # 개구리 눈 돌출
        for ex2 in (cx-4, cx+4):
            pygame.draw.circle(surf, fl2, (ex2,cy-9), 3)
            pygame.draw.circle(surf, (15,15,25) if unlocked else (40,50,70), (ex2,cy-9), 1)
    elif item_id == 'foxfire':
        ft2 = pygame.time.get_ticks()*0.001
        for fi in range(3):
            fa = ft2*0.9 + fi*(math.pi*2/3)
            fx2 = cx + int(math.cos(fa)*9); fy2 = cy + int(math.sin(fa)*6)
            fr2 = int(2+abs(math.sin(ft2*3+fi))*2)
            frc = int(175+abs(math.sin(ft2*2+fi))*80)
            fgc = int(8+abs(math.sin(ft2*2+fi))*28)
            gs3 = pygame.Surface((fr2*4+2,fr2*4+2),pygame.SRCALPHA)
            pygame.draw.circle(gs3,(frc,fgc,5,50),(fr2*2+1,fr2*2+1),fr2*2)
            surf.blit(gs3,(fx2-fr2*2-1,fy2-fr2*2-1))
            pygame.draw.circle(surf,c((frc,fgc,5),(50,60,90)),(fx2,fy2),max(1,fr2))
    elif item_id == 'blossom_pin':
        def _blossom(sx,sy,sr,col_p,col_c):
            for _bi in range(5):
                _ba=math.radians(_bi*72-90)
                pygame.draw.circle(surf,col_p,(int(sx+math.cos(_ba)*sr),int(sy+math.sin(_ba)*sr)),sr)
            pygame.draw.circle(surf,col_c,(sx,sy),max(1,sr//2+1))
        bp_col = c((254,117,156),(55,65,100)); bc_col = c((255,230,100),(65,75,110))
        _blossom(cx-7,cy-3,4,bp_col,bc_col)
        _blossom(cx+7,cy-3,4,bp_col,bc_col)
        pygame.draw.line(surf,c((180,140,160),(45,55,85)),(cx-7,cy+1),(cx-7,cy+7),1)
        pygame.draw.line(surf,c((180,140,160),(45,55,85)),(cx+7,cy+1),(cx+7,cy+7),1)
    elif item_id == 'angry_brow':
        ac2 = c((40,18,10),(50,60,90))
        thick2 = 3 if unlocked else 2
        # 왼쪽 눈썹 \ (바깥높음, 안낮음)
        pygame.draw.line(surf, ac2, (cx-10,cy-6),(cx-3,cy-2), thick2)
        # 오른쪽 눈썹 / (안낮음, 바깥높음)
        pygame.draw.line(surf, ac2, (cx+3,cy-2),(cx+10,cy-6), thick2)
    elif item_id == 'headset':
        bk = c((12,12,12),(42,52,82)); dg = c((50,50,50),(50,60,90)); pd = c((8,8,10),(40,50,80))
        # 왼쪽 이어컵 (동그란)
        pygame.draw.ellipse(surf, dg, (cx-14,cy-5,8,11))
        pygame.draw.ellipse(surf, bk, (cx-14,cy-5,8,11), 1)
        pygame.draw.ellipse(surf, pd, (cx-13,cy-4,6,9))
        # 오른쪽 이어컵 (동그란)
        pygame.draw.ellipse(surf, dg, (cx+6,cy-5,8,11))
        pygame.draw.ellipse(surf, bk, (cx+6,cy-5,8,11), 1)
        pygame.draw.ellipse(surf, pd, (cx+7,cy-4,6,9))
        # 헤드밴드 아치
        pygame.draw.arc(surf, bk, (cx-10,cy-13,20,16), 0, math.pi, 2)


def draw_wardrobe_icon(surf, rect, has_new=False):
    x, y, w, h = rect
    col = (175, 210, 248)
    pygame.draw.rect(surf, (42, 72, 125), (x+2,y+2,w-4,h-4), border_radius=4)
    pygame.draw.rect(surf, col, (x+2,y+2,w-4,h-4), 2, border_radius=4)
    cx2 = x + w//2
    pygame.draw.line(surf, col, (cx2, y+6), (cx2, y+h-4), 1)
    pygame.draw.circle(surf, col, (cx2-5, y+h//2), 2)
    pygame.draw.circle(surf, col, (cx2+5, y+h//2), 2)
    pygame.draw.line(surf, (140, 180, 225), (x+5,y+8), (x+w-5,y+8), 1)
    if has_new:
        pygame.draw.circle(surf, (255,70,70), (x+w-3,y+3), 5)
        pygame.draw.circle(surf, (255,150,150), (x+w-3,y+3), 3)


def draw_wardrobe_screen(surf, wardrobe_items, equipped_item=None, context_item=None):
    overlay = pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
    overlay.fill((4,12,35,248))
    surf.blit(overlay,(0,0))
    bb = pygame.Surface((75,28),pygame.SRCALPHA); bb.fill((18,38,88,210))
    pygame.draw.rect(bb,(65,128,218),(0,0,75,28),1,border_radius=6); surf.blit(bb,(15,12))
    fb=get_font(13,bold=True); tb=fb.render('◀ 뒤로',True,(160,210,255))
    surf.blit(tb,(15+37-tb.get_width()//2, 12+14-tb.get_height()//2))
    ft=get_font(18,bold=True); nt=ft.render('유저 해파리 옷장',True,(178,222,255))
    surf.blit(nt,(WIDTH//2-nt.get_width()//2, 14))
    pygame.draw.line(surf,(50,90,160),(18,48),(WIDTH-18,48),1)
    cw,ch = 82,80; cols = 4; gap = 6
    total_w = cols*(cw+gap)-gap
    sx = (WIDTH-total_w)//2; sy = 58
    for i,(item_id,item_name) in enumerate(WARDROBE_ITEM_DEFS):
        ci = i%cols; ri = i//cols
        ix = sx + ci*(cw+gap); iy = sy + ri*(ch+gap)
        acquired = item_id in wardrobe_items
        is_eq = (item_id == equipped_item)
        slot=pygame.Surface((cw,ch),pygame.SRCALPHA)
        slot.fill((22,60,115,220) if acquired else (10,25,55,145))
        border_col = (255,210,60) if is_eq else ((72,135,215) if acquired else (35,65,115))
        pygame.draw.rect(slot,border_col,(0,0,cw,ch),2 if is_eq else 1,border_radius=8)
        surf.blit(slot,(ix,iy))
        if acquired:
            # 착용중 배지
            if is_eq:
                bw2,bh2=44,16
                eq_s=pygame.Surface((bw2,bh2),pygame.SRCALPHA)
                eq_s.fill((200,155,0,230))
                pygame.draw.rect(eq_s,(255,215,60),(0,0,bw2,bh2),1,border_radius=4)
                surf.blit(eq_s,(ix+cw//2-bw2//2, iy-8))
                fe=get_font(10,bold=True); te=fe.render('착용중',True,(255,240,180))
                surf.blit(te,(ix+cw//2-te.get_width()//2, iy-7))
            draw_wardrobe_item_icon(surf, ix+cw//2, iy+ch//2-6, item_id, True)
            fn2=get_font(10); tn2=fn2.render(item_name,True,(200,235,255))
            surf.blit(tn2,(ix+cw//2-tn2.get_width()//2, iy+ch-17))
        else:
            fq=get_font(16,bold=True); tq=fq.render('???',True,(75,105,160))
            surf.blit(tq,(ix+cw//2-tq.get_width()//2, iy+ch//2-tq.get_height()//2-4))
            fn2=get_font(10); tn2=fn2.render('???',True,(55,80,125))
            surf.blit(tn2,(ix+cw//2-tn2.get_width()//2, iy+ch-17))
    # 우클릭 팝업
    if context_item and context_item in wardrobe_items:
        ci2 = next((j for j,(iid,_) in enumerate(WARDROBE_ITEM_DEFS) if iid==context_item), 0)
        px3 = sx + (ci2%cols)*(cw+gap); py3 = sy + (ci2//cols)*(ch+gap)
        pw,ph = 80,32; pop_x=min(px3+cw+4, WIDTH-pw-4); pop_y=max(py3,4)
        pop_s=pygame.Surface((pw,ph),pygame.SRCALPHA); pop_s.fill((18,42,95,240))
        is_eq2 = (context_item==equipped_item)
        lbl = '착용 해제' if is_eq2 else '착용'
        bcol = (200,80,80) if is_eq2 else (60,140,240)
        pygame.draw.rect(pop_s,bcol,(0,0,pw,ph),1,border_radius=6)
        surf.blit(pop_s,(pop_x,pop_y))
        fp=get_font(13,bold=True); tp=fp.render(lbl,True,(230,240,255))
        surf.blit(tp,(pop_x+pw//2-tp.get_width()//2, pop_y+ph//2-tp.get_height()//2))


def draw_aquarium_screen(surf, fish_list):
    # 배경
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((4, 12, 35, 245))
    surf.blit(overlay, (0,0))
    # 뒤로 버튼
    bb = pygame.Surface((AQ_BACK_RECT.w, AQ_BACK_RECT.h), pygame.SRCALPHA)
    bb.fill((18,38,88,210))
    pygame.draw.rect(bb,(65,128,218),(0,0,AQ_BACK_RECT.w,AQ_BACK_RECT.h),1,border_radius=6)
    surf.blit(bb, AQ_BACK_RECT.topleft)
    fb = get_font(13,bold=True)
    tb = fb.render('◀ 뒤로', True,(160,210,255))
    surf.blit(tb,(AQ_BACK_RECT.x+AQ_BACK_RECT.w//2-tb.get_width()//2,
                  AQ_BACK_RECT.y+AQ_BACK_RECT.h//2-tb.get_height()//2))
    # 제목
    ft = get_font(19,bold=True)
    nt = ft.render('내 어항', True,(178,222,255))
    surf.blit(nt,(WIDTH//2-nt.get_width()//2, 14))
    # 탱크 물 (그라디언트)
    for yy in range(AQ_T, AQ_B):
        tt = (yy-AQ_T)/(AQ_B-AQ_T)
        cc = (int(10+tt*18), int(30+tt*45), int(88+tt*62))
        pygame.draw.line(surf, cc, (AQ_L+2,yy),(AQ_R-2,yy))
    # 모래
    sand_y = AQ_B - 24
    pygame.draw.rect(surf,(185,162,108),(AQ_L+2,sand_y,AQ_R-AQ_L-4,22),border_radius=2)
    pygame.draw.rect(surf,(208,188,135),(AQ_L+2,sand_y,AQ_R-AQ_L-4,9), border_radius=2)
    # 산호/해초
    t_aq = pygame.time.get_ticks()*0.001
    for cx_d, cc_d in [(40,(240,80,95)),(AQ_R-38,(80,190,175))]:
        for dy in range(0,28,5):
            pygame.draw.circle(surf,cc_d,(cx_d,sand_y-dy),max(2,4-dy//8))
    for wx in [AQ_L+52, AQ_R-58]:
        for seg in range(6):
            wy  = sand_y - seg*9
            woff= int(math.sin(t_aq*1.2+seg*0.9+wx*0.02)*5)
            pygame.draw.circle(surf,(48,155,72),(wx+woff,wy),4)
    # 거품
    for bi2 in range(5):
        bx3 = AQ_L+18 + bi2*58
        by3 = AQ_T+20 + int(math.sin(t_aq*0.8+bi2*1.3)*12)
        ba3 = int(50+abs(math.sin(t_aq*1.5+bi2))*80)
        bbs = pygame.Surface((8,8),pygame.SRCALPHA)
        pygame.draw.circle(bbs,(180,225,255,ba3),(4,4),3,1)
        surf.blit(bbs,(bx3-4,by3-4))
    # 탱크 테두리
    tw = AQ_R-AQ_L; th = AQ_B-AQ_T
    pygame.draw.rect(surf,(72,132,210),(AQ_L,AQ_T,tw,th),2,border_radius=10)
    pygame.draw.rect(surf,(110,170,240),(AQ_L,AQ_T,tw,9),border_radius=8)
    pygame.draw.rect(surf,(180,212,255,40),(AQ_L,AQ_T,tw,9),border_radius=8)
    # 물고기
    for f in fish_list:
        f.draw(surf)
    # 옷장 아이콘
    draw_wardrobe_icon(surf, AQ_WARDROBE_RECT)
    # 마리 수
    fc2 = get_font(13)
    ct2 = fc2.render(f'{len(fish_list)} / 5 마리', True,(172,215,252))
    surf.blit(ct2,(WIDTH//2-ct2.get_width()//2, HEIGHT-65))
    # + 버튼
    if len(fish_list) < 5:
        bs3 = pygame.Surface((AQUARIUM_ADD_BTN.w,AQUARIUM_ADD_BTN.h),pygame.SRCALPHA)
        bs3.fill((18,48,105,215))
        pygame.draw.rect(bs3,(65,132,218),(0,0,AQUARIUM_ADD_BTN.w,AQUARIUM_ADD_BTN.h),1,border_radius=9)
        surf.blit(bs3,AQUARIUM_ADD_BTN.topleft)
        fb3 = get_font(13,bold=True)
        ft3 = fb3.render('+ 해파리 추가', True,(162,212,255))
        surf.blit(ft3,(AQUARIUM_ADD_BTN.x+AQUARIUM_ADD_BTN.w//2-ft3.get_width()//2,
                       AQUARIUM_ADD_BTN.y+AQUARIUM_ADD_BTN.h//2-ft3.get_height()//2))


def draw_aquarium_add_screen(surf, inventory, scroll_y=0):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((4, 12, 35, 245))
    surf.blit(overlay, (0,0))
    bb = pygame.Surface((AQ_BACK_RECT.w,AQ_BACK_RECT.h),pygame.SRCALPHA)
    bb.fill((18,38,88,210))
    pygame.draw.rect(bb,(65,128,218),(0,0,AQ_BACK_RECT.w,AQ_BACK_RECT.h),1,border_radius=6)
    surf.blit(bb,AQ_BACK_RECT.topleft)
    fb4 = get_font(13,bold=True)
    tb4 = fb4.render('◀ 뒤로', True,(160,210,255))
    surf.blit(tb4,(AQ_BACK_RECT.x+AQ_BACK_RECT.w//2-tb4.get_width()//2,
                   AQ_BACK_RECT.y+AQ_BACK_RECT.h//2-tb4.get_height()//2))
    ft4 = get_font(17,bold=True)
    nt4 = ft4.render('어항에 넣을 해파리 선택', True,(175,220,255))
    surf.blit(nt4,(WIDTH//2-nt4.get_width()//2,14))
    pygame.draw.line(surf,(45,90,165),(18,46),(WIDTH-18,46),1)

    # 보유 해파리 그리드 (3열)
    CW, CH = 110, 95
    cols, margin_x, start_y = 3, 15, 55
    pos_i = 0
    for slot in range(len(JELLY_NAMES)):
        cnt = inventory.get(slot, 0)
        if cnt <= 0:
            continue
        col = pos_i % cols
        row = pos_i // cols
        cx5 = margin_x + CW//2 + col*(CW+5)
        cy5 = start_y + CH//2 + row*(CH+5) - scroll_y
        if cy5 < 46 - CH or cy5 > HEIGHT + CH:
            pos_i += 1; continue
        # 카드
        card = pygame.Surface((CW,CH),pygame.SRCALPHA)
        card.fill((18,42,92,195))
        pygame.draw.rect(card,(55,115,200,180),(0,0,CW,CH),1,border_radius=7)
        surf.blit(card,(cx5-CW//2,cy5-CH//2))
        # 스프라이트
        sw5,sh5 = 50,38
        bi5  = _slot_base_idx(slot)
        spr5 = (RAINBOW_BELL_SPRITE if slot==22
                else PABUN_BELL_SPRITE if slot==23
                else TWIN_BELL_SPRITE  if slot==27
                else BELL_SPRITES[bi5])
        spr5 = pygame.transform.scale(spr5,(sw5,sh5))
        if slot==9:   spr5.set_alpha(72)
        elif slot==6: spr5.set_alpha(175)
        surf.blit(spr5,(cx5-sw5//2,cy5-CH//2+8))
        _draw_slot_overlay(surf,slot,cx5,cy5-CH//2+8+4,sw5,sh5)
        # 이름
        fn5 = get_font(10)
        nt5 = fn5.render(JELLY_NAMES[slot], True,(175,215,245))
        surf.blit(nt5,(cx5-nt5.get_width()//2,cy5+CH//2-28))
        # 보유수
        fc5 = get_font(11,bold=True)
        ct5 = fc5.render(f'×{cnt}', True,(255,235,140))
        surf.blit(ct5,(cx5-ct5.get_width()//2,cy5+CH//2-14))
        pos_i += 1
        if cy5+CH//2 > HEIGHT-10:
            break


def draw_dev_reset_screen(surf, inventory):
    """[DEV] 특정 해파리를 미획득 상태로 리셋하는 개발자 화면."""
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((15, 5, 5, 245))
    surf.blit(overlay, (0, 0))
    # 뒤로 버튼
    bb = pygame.Surface((DEV_RESET_BACK.w, DEV_RESET_BACK.h), pygame.SRCALPHA)
    bb.fill((55, 18, 18, 210))
    pygame.draw.rect(bb, (200, 55, 55), (0, 0, DEV_RESET_BACK.w, DEV_RESET_BACK.h), 1, border_radius=6)
    surf.blit(bb, DEV_RESET_BACK.topleft)
    fb = get_font(13, bold=True)
    tb = fb.render('◀ 닫기', True, (255, 155, 155))
    surf.blit(tb, (DEV_RESET_BACK.x+DEV_RESET_BACK.w//2-tb.get_width()//2,
                   DEV_RESET_BACK.y+DEV_RESET_BACK.h//2-tb.get_height()//2))
    # 제목
    ft = get_font(17, bold=True)
    nt = ft.render('[DEV] 해파리 리셋 — 클릭 시 미획득 상태로', True, (255, 120, 120))
    surf.blit(nt, (WIDTH//2-nt.get_width()//2, 14))
    pygame.draw.line(surf, (150, 40, 40), (18, 46), (WIDTH-18, 46), 1)
    # 획득한 해파리 그리드
    CW, CH = 110, 95
    cols, margin_x, start_y = 3, 15, 55
    pos_i = 0
    for slot in range(len(JELLY_NAMES)):
        if slot not in inventory or inventory[slot] <= 0:
            continue
        col = pos_i % cols; row = pos_i // cols
        cx5 = margin_x + CW//2 + col*(CW+5)
        cy5 = start_y + CH//2 + row*(CH+5)
        card = pygame.Surface((CW, CH), pygame.SRCALPHA)
        card.fill((45, 12, 12, 205))
        pygame.draw.rect(card, (180, 50, 50, 180), (0,0,CW,CH), 1, border_radius=7)
        surf.blit(card, (cx5-CW//2, cy5-CH//2))
        sw5, sh5 = 50, 38
        bi5 = _slot_base_idx(slot)
        spr5 = (RAINBOW_BELL_SPRITE if slot==22
                else PABUN_BELL_SPRITE if slot==23
                else TWIN_BELL_SPRITE  if slot==27
                else BELL_SPRITES[bi5])
        spr5 = pygame.transform.scale(spr5, (sw5, sh5))
        if slot==9: spr5.set_alpha(72)
        elif slot==6: spr5.set_alpha(175)
        surf.blit(spr5, (cx5-sw5//2, cy5-CH//2+8))
        fn5 = get_font(10)
        nt5 = fn5.render(JELLY_NAMES[slot], True, (240, 185, 185))
        surf.blit(nt5, (cx5-nt5.get_width()//2, cy5+CH//2-28))
        fc5 = get_font(11, bold=True)
        ct5 = fc5.render(f'×{inventory[slot]}', True, (255, 130, 130))
        surf.blit(ct5, (cx5-ct5.get_width()//2, cy5+CH//2-14))
        pos_i += 1
        if cy5+CH//2 > HEIGHT-10: break
    if pos_i == 0:
        fe = get_font(14)
        et = fe.render('획득한 해파리가 없어.', True, (120, 60, 60))
        surf.blit(et, (WIDTH//2-et.get_width()//2, HEIGHT//2))


def draw_dev_add_screen(surf, inventory):
    """[DEV] 미획득 해파리를 획득 상태로 만드는 화면."""
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((5, 15, 5, 245))
    surf.blit(overlay, (0, 0))
    bb = pygame.Surface((DEV_RESET_BACK.w, DEV_RESET_BACK.h), pygame.SRCALPHA)
    bb.fill((18, 55, 18, 210))
    pygame.draw.rect(bb, (55, 200, 55), (0, 0, DEV_RESET_BACK.w, DEV_RESET_BACK.h), 1, border_radius=6)
    surf.blit(bb, DEV_RESET_BACK.topleft)
    fb = get_font(13, bold=True)
    tb = fb.render('◀ 닫기', True, (155, 255, 155))
    surf.blit(tb, (DEV_RESET_BACK.x+DEV_RESET_BACK.w//2-tb.get_width()//2,
                   DEV_RESET_BACK.y+DEV_RESET_BACK.h//2-tb.get_height()//2))
    ft = get_font(17, bold=True)
    nt = ft.render('[DEV] 획득 추가 — 클릭 시 획득 상태로', True, (120, 255, 120))
    surf.blit(nt, (WIDTH//2-nt.get_width()//2, 14))
    pygame.draw.line(surf, (40, 150, 40), (18, 46), (WIDTH-18, 46), 1)
    CW, CH = 110, 95
    cols, margin_x, start_y = 3, 15, 55
    pos_i = 0
    for slot in range(len(JELLY_NAMES)):
        if inventory.get(slot, 0) > 0:
            continue
        col = pos_i % cols; row = pos_i // cols
        cx5 = margin_x + CW//2 + col*(CW+5)
        cy5 = start_y + CH//2 + row*(CH+5)
        card = pygame.Surface((CW, CH), pygame.SRCALPHA)
        card.fill((12, 45, 12, 205))
        pygame.draw.rect(card, (50, 180, 50, 180), (0,0,CW,CH), 1, border_radius=7)
        surf.blit(card, (cx5-CW//2, cy5-CH//2))
        sw5, sh5 = 50, 38
        bi5 = _slot_base_idx(slot)
        spr5 = (RAINBOW_BELL_SPRITE if slot==22
                else PABUN_BELL_SPRITE if slot==23
                else TWIN_BELL_SPRITE  if slot==27
                else BELL_SPRITES[bi5])
        spr5 = pygame.transform.scale(spr5, (sw5, sh5))
        if slot==9: spr5.set_alpha(72)
        elif slot==6: spr5.set_alpha(175)
        surf.blit(spr5, (cx5-sw5//2, cy5-CH//2+8))
        fn5 = get_font(10)
        nt5 = fn5.render(JELLY_NAMES[slot], True, (175, 240, 175))
        surf.blit(nt5, (cx5-nt5.get_width()//2, cy5+CH//2-28))
        pos_i += 1
        if cy5+CH//2 > HEIGHT-10: break
    if pos_i == 0:
        fe = get_font(14)
        et = fe.render('미획득 해파리가 없어.', True, (60, 120, 60))
        surf.blit(et, (WIDTH//2-et.get_width()//2, HEIGHT//2))


def draw_online_icon(surf, rect):
    x,y,w,h = rect.x,rect.y,rect.w,rect.h
    cx,cy = x+w//2, y+h//2
    pygame.draw.circle(surf,(80,200,130),(cx,cy),12,2)
    pygame.draw.circle(surf,(80,200,130),(cx,cy),7,1)
    pygame.draw.line(surf,(80,200,130),(cx-12,cy),(cx+12,cy),1)
    pygame.draw.line(surf,(80,200,130),(cx,cy-12),(cx,cy+12),1)
    t_ic=pygame.time.get_ticks()*0.001
    px_=cx+int(math.cos(t_ic*1.8)*8); py_=cy+int(math.sin(t_ic*1.8)*5)
    pygame.draw.circle(surf,(255,255,180),(px_,py_),3)


_online_bg = None
def make_online_bg():
    s = pygame.Surface((OW, OH_PLAY))
    for y in range(OH_PLAY):
        t=y/OH_PLAY
        pygame.draw.line(s,(int(18+t*12),int(95+t*40),int(82+t*35)),(0,y),(OW,y))
    rng2=random.Random(55)
    # 바닥 장식
    for _ in range(18):
        bx2=rng2.randint(10,OW-10); by2=rng2.randint(OH_PLAY-60,OH_PLAY-5)
        pygame.draw.circle(s,(int(28+rng2.randint(0,20)),int(68+rng2.randint(0,20)),int(65+rng2.randint(0,15))),(bx2,by2),rng2.randint(4,14))
    for _ in range(8):
        sx2=rng2.randint(15,OW-15)
        for seg in range(rng2.randint(3,8)):
            sy2=OH_PLAY-seg*14-5
            pygame.draw.rect(s,(50+rng2.randint(0,30),155+rng2.randint(0,30),60+rng2.randint(0,20)),(sx2,sy2,7,12))
    return s


def _draw_online_tentacles(surf, cx, cy, bw, bh, phase, moving):
    tc = (228, 175, 132)
    amp = 4.5 if moving else 1.8
    for i, dx_f in enumerate([-0.28,-0.10,0.10,0.28]):
        bx = cx + int(dx_f * bw)
        base = int(bw * 0.18)
        wave = int(math.sin(phase * 2.2 + i * 1.3) * bw * 0.06)
        length = max(4, base + wave + int(amp * 2))
        sway = int(math.sin(phase + i) * (1 + amp * 0.6))
        s = pygame.Surface((12, length+8), pygame.SRCALPHA)
        pygame.draw.line(s,(*tc,200),(6,0),(6+sway,length),2)
        pygame.draw.circle(s,(*tc,180),(6+sway,length),max(2,length//6))
        surf.blit(s,(bx-6, cy+bh//2))

def _draw_online_chat_bubble(surf, cx, top_y, text):
    fc = get_font(10, bold=True)
    tw = fc.render(text, True, (30,30,50))
    pad = 6
    bw2 = min(tw.get_width()+pad*2, 160)
    bh2 = tw.get_height()+pad
    bx2 = max(2, min(OW-bw2-2, cx-bw2//2))
    by2 = top_y - bh2 - 8
    bs = pygame.Surface((bw2, bh2+6), pygame.SRCALPHA)
    pygame.draw.rect(bs,(255,255,255,230),(0,0,bw2,bh2),border_radius=7)
    pygame.draw.rect(bs,(180,220,180,180),(0,0,bw2,bh2),1,border_radius=7)
    tip = min(max(bw2//2,8),bw2-8)
    pygame.draw.polygon(bs,(255,255,255,230),[(tip-4,bh2),(tip+4,bh2),(tip,bh2+6)])
    surf.blit(bs,(bx2,by2))
    surf.blit(tw,(bx2+pad, by2+pad//2))


def draw_online_world(surf, lx, ly, lnick, players, chat_msgs, chat_input, chat_active, chat_ime, move_phase=0.0, local_chat='', local_chat_t=0, interact_open=False, action=None, action_phase=0.0, selected=None, pushed=None, push_anim_t=0, push_dir=(1,0), equipped_item=None, self_pushed=None):
    global _online_bg
    if _online_bg is None: _online_bg = make_online_bg()
    surf.blit(_online_bg,(0,0))
    sp_sz = 40; sp_h = int(sp_sz*0.75)
    import time as _tm2; now2 = int(_tm2.time())

    def _nick_chat(nick):
        msgs = [m for m in chat_msgs if m.get('nick')==nick and now2-m.get('t',0)<10]
        return msgs[-1].get('text','') if msgs else ''

    moving = move_phase  # non-zero when moving
    if pushed is None: pushed = {}
    # 다른 플레이어
    for nick,data in players.items():
        px2=int(data.get('cur_x', data.get('x',190))); py2=int(data.get('cur_y', data.get('y',200)))
        spr2=pygame.transform.scale(PLAYER_BELL_SPRITE,(sp_sz,sp_h))
        t_phase = data.get('phase', now2*2.0)
        if nick in pushed:
            pv = pushed[nick]; pt = pv['timer']
            # 빠르게 쓰러짐: 처음 15프레임에 0→-90도
            angle = -90.0 * min(1.0, (pv['max_t']-pt) / 15.0) if pt > pv['max_t']-15 else -90.0
            rot2 = pygame.transform.rotate(spr2, angle)
            surf.blit(rot2,(px2-rot2.get_width()//2,py2-rot2.get_height()//2))
        else:
            surf.blit(spr2,(px2-sp_sz//2,py2-sp_h//2))
            _draw_online_tentacles(surf,px2,py2,sp_sz,sp_h,t_phase,False)
        fn2=get_font(10,bold=True); nt2=fn2.render(data.get('nickname',nick),True,(255,255,255))
        surf.blit(nt2,(px2-nt2.get_width()//2,py2-sp_h//2-14))
        chat_t = _nick_chat(nick)
        if chat_t: _draw_online_chat_bubble(surf,px2,py2-sp_h//2-14,chat_t)
        # 다른 플레이어 착용 아이템
        _p_equip = data.get('equipped','')
        if _p_equip and nick not in pushed:
            draw_player_item(surf,px2,py2,sp_sz,sp_h,_p_equip)
        # 다른 플레이어 액션 애니메이션
        _p_action = data.get('action','')
        if _p_action and nick not in pushed:
            _draw_online_action(surf,px2,py2,sp_sz,sp_h,_p_action,data.get('action_phase',0.0))
        # 밀치기 버튼: 근접 시에만 표시 (55px 이내)
        dist_to_local = math.hypot(px2-lx, py2-ly)
        if selected == nick and nick not in pushed and dist_to_local < 55:
            bw,bh = 60,24
            bx2 = max(2, min(OW-bw-2, px2-bw//2))
            by2 = max(2, py2-sp_h//2-36)
            btn_s = pygame.Surface((bw,bh),pygame.SRCALPHA)
            btn_s.fill((200,65,35,235))
            pygame.draw.rect(btn_s,(255,140,100),(0,0,bw,bh),1,border_radius=5)
            surf.blit(btn_s,(bx2,by2))
            fb3=get_font(13,bold=True); tb3=fb3.render('밀치기',True,(255,235,220))
            surf.blit(tb3,(bx2+bw//2-tb3.get_width()//2,by2+bh//2-tb3.get_height()//2))
    # 로컬 플레이어
    spr_l=pygame.transform.scale(PLAYER_BELL_SPRITE,(sp_sz,sp_h))
    if self_pushed:
        _sp_t = self_pushed['timer']; _sp_max = self_pushed.get('max_t',70)
        _ang_s = -90.0*min(1.0,(_sp_max-_sp_t)/15.0) if _sp_t>_sp_max-15 else -90.0
        rot_l = pygame.transform.rotate(spr_l, _ang_s)
        surf.blit(rot_l,(int(lx)-rot_l.get_width()//2,int(ly)-rot_l.get_height()//2))
    else:
        surf.blit(spr_l,(int(lx)-sp_sz//2,int(ly)-sp_h//2))
        is_moving = any(online_keys.values()) if 'online_keys' in dir() else False
        _draw_online_tentacles(surf,int(lx),int(ly),sp_sz,sp_h,move_phase,is_moving)
    _nick_extra = {'hat':12,'deep_orb':16,'rabbit_ears':8,'frog_hat_item':8,'cherry_top':10,'angel_halo':10}.get(equipped_item or '',0)
    fn_l=get_font(10,bold=True); nt_l=fn_l.render(lnick,True,(255,240,140))
    _nick_y = int(ly)-sp_h//2-14-_nick_extra
    surf.blit(nt_l,(int(lx)-nt_l.get_width()//2, _nick_y))
    draw_player_item(surf, int(lx), int(ly), sp_sz, sp_h, equipped_item)
    if local_chat and now2-local_chat_t<10:
        _draw_online_chat_bubble(surf,int(lx),_nick_y,local_chat)
    # 밀치기 팔 애니메이션
    if push_anim_t > 0:
        _max_t = 18
        prog = 1.0 - push_anim_t / _max_t
        extend = math.sin(prog * math.pi)  # 0→peak→0
        arm_len = int(extend * 32)
        skin = (228,175,132)
        ax = int(lx + push_dir[0] * (sp_sz//2 + arm_len))
        ay = int(ly + push_dir[1] * (sp_h//2 + arm_len))
        pygame.draw.line(surf, skin, (int(lx), int(ly)), (ax, ay), 4)
        pygame.draw.circle(surf, skin, (ax, ay), 6)
    # 로컬 액션
    if move_phase and hasattr(move_phase,'__float__'):
        _draw_online_tentacles(surf,int(lx),int(ly),sp_sz,sp_h,move_phase,any(online_keys.values()) if 'online_keys' in dir() else False)
    # 채팅 영역
    chat_bg=pygame.Surface((OW,OH_CHAT),pygame.SRCALPHA)
    chat_bg.fill((5,15,35,215))
    surf.blit(chat_bg,(0,OH_PLAY))
    pygame.draw.line(surf,(40,100,80),(0,OH_PLAY),(OW,OH_PLAY),1)
    fc2=get_font(11)
    for idx,msg in enumerate(chat_msgs[-5:]):
        col3=(255,240,140) if msg.get('nick')==lnick else (185,225,200)
        mt=fc2.render(f"{msg.get('nick','?')}: {msg.get('text','')}", True, col3)
        surf.blit(mt,(8, OH_PLAY+8+idx*18))
    # 입력창
    inp_y=OH_PLAY+OH_CHAT-30
    inp_bg=pygame.Surface((OW-16,24),pygame.SRCALPHA)
    inp_bg.fill((20,50,40,200) if chat_active else (12,30,25,180))
    pygame.draw.rect(inp_bg,(60,160,100) if chat_active else (35,90,65),(0,0,OW-16,24),1,border_radius=5)
    surf.blit(inp_bg,(8,inp_y))
    disp2=(chat_input+chat_ime) if chat_active else '엔터키로 채팅 입력...'
    col4=(220,245,220) if chat_active else (100,140,115)
    fi2=get_font(11); ti2=fi2.render(disp2[:38],True,col4)
    surf.blit(ti2,(12,inp_y+4))
    # 액션 애니메이션 (로컬)
    if equipped_item == 'angel_halo':
        hlw = int(sp_sz*0.80); hlh = max(1,int(hlw*3//11))
        hls = pygame.transform.scale(HALO_BASE,(hlw,hlh))
        halo_y = int(ly)-sp_h//2-hlh-3+int(math.sin(move_phase)*2)
        surf.blit(hls,(int(lx)-hlw//2, halo_y))
    if action:
        _draw_online_action(surf,int(lx),int(ly),sp_sz,sp_h,action,action_phase)
    # 휠 아이콘
    wx_icon=OW-20; wy_icon=OH_PLAY-20
    draw_online_jelly_icon(surf,wx_icon,wy_icon,interact_open)
    if interact_open:
        draw_online_interact_list(surf,wx_icon,wy_icon,action)
    # 나가기
    bk=pygame.Surface((52,22),pygame.SRCALPHA)
    bk.fill((25,55,40,210))
    pygame.draw.rect(bk,(60,160,100),(0,0,52,22),1,border_radius=5)
    surf.blit(bk,(OW-58,4))
    fb2=get_font(11,bold=True); tb2=fb2.render('나가기',True,(155,225,175))
    surf.blit(tb2,(OW-58+26-tb2.get_width()//2,7))
    # 온라인 인원
    fo2=get_font(10); to2=fo2.render(f'접속자 {len(players)+1}명',True,(120,195,155))
    surf.blit(to2,(8,6))


def draw_player_item(surf, cx, cy, bw, bh, item_id):
    if not item_id: return
    if item_id == 'angel_halo':
        hlw2 = int(bw*0.80); hlh2 = max(1,int(hlw2*3//11))
        hls2 = pygame.transform.scale(HALO_BASE,(hlw2,hlh2))
        surf.blit(hls2,(cx-hlw2//2, cy-bh//2-hlh2-3))
    elif item_id == 'crown':
        pts = [(cx-9,cy-bh//2+1),(cx-5,cy-bh//2-8),(cx,cy-bh//2-3),(cx+5,cy-bh//2-8),(cx+9,cy-bh//2+1)]
        pygame.draw.polygon(surf,(255,210,50),pts)
        for px4 in [cx-5,cx,cx+5]: pygame.draw.circle(surf,(255,235,100),(px4,cy-bh//2-5),2)
    elif item_id == 'glasses':
        gy = cy + bh//8 + 3
        pygame.draw.circle(surf,(30,30,30),(cx-7,gy),7,2)
        pygame.draw.circle(surf,(30,30,30),(cx+7,gy),7,2)
        pygame.draw.line(surf,(30,30,30),(cx-1,gy),(cx+1,gy),1)
        pygame.draw.line(surf,(30,30,30),(cx-14,gy-1),(cx-14,gy+3),1)
        pygame.draw.line(surf,(30,30,30),(cx+14,gy-1),(cx+14,gy+3),1)
    elif item_id == 'ribbon':
        ry = cy - bh//2 + 2
        pygame.draw.circle(surf,(254,107,149),(cx-6,ry),6)
        pygame.draw.circle(surf,(254,107,149),(cx+6,ry),6)
        pygame.draw.circle(surf,(255,160,185),(cx,ry),4)
        pygame.draw.line(surf,(255,190,210),(cx,ry-3),(cx,ry+3),2)
    elif item_id == 'hat':
        hy = cy - bh//2
        pygame.draw.ellipse(surf,(80,40,145),(cx-11,hy+1,22,7))
        pygame.draw.rect(surf,(80,40,145),(cx-6,hy-13,12,15))
        pygame.draw.line(surf,(195,155,255),(cx-5,hy-4),(cx+5,hy-4),1)
        pygame.draw.circle(surf,(255,215,80),(cx,hy-13),3)
    elif item_id == 'redcap':
        ry2 = cy - bh//2 + 5
        # 돔 (큰 반원)
        dome2 = [(int(cx-1+13*math.cos(math.radians(a))), int(ry2+5-13*math.sin(math.radians(a)))) for a in range(0,181,10)]
        pygame.draw.polygon(surf,(220,40,40),[(cx-14,ry2+5)]+dome2+[(cx+12,ry2+5)])
        # 밴드
        pygame.draw.line(surf,(185,25,25),(cx-14,ry2+5),(cx+12,ry2+5),2)
        # 챙 (오른쪽)
        pygame.draw.polygon(surf,(185,25,25),[(cx+10,ry2+4),(cx+22,ry2+7),(cx+20,ry2+10),(cx+9,ry2+6)])
        # 하이라이트
        pygame.draw.arc(surf,(255,115,115),(cx-8,ry2-8,14,10),math.radians(35),math.radians(145),1)
        # 버튼
        pygame.draw.rect(surf,(185,25,25),(cx-1,ry2-9,4,2),border_radius=1)
    elif item_id == 'deep_orb':
        sy3 = cy - bh//2
        # 줄기
        pygame.draw.line(surf,(80,175,205),(cx,sy3),(cx,sy3-10),2)
        # 글로우
        gs2 = pygame.Surface((20,20),pygame.SRCALPHA)
        pygame.draw.circle(gs2,(48,218,178,55),(10,10),9)
        surf.blit(gs2,(cx-10,sy3-20))
        # 구슬
        pygame.draw.circle(surf,(48,218,178),(cx,sy3-10),6)
        pygame.draw.circle(surf,(180,255,235),(cx-1,sy3-12),3)
        pygame.draw.circle(surf,(220,255,242),(cx-2,sy3-13),1)
    elif item_id == 'angry_brow':
        col_ab = (14,8,8)
        thick_ab = max(2, bw//11)
        eye_y_ab = cy + bh//8
        eby_ab   = eye_y_ab - bh//7
        ox_ab    = bw//5
        # 왼쪽 눈썹 \
        pygame.draw.line(surf, col_ab,
                         (cx - bw//8 - ox_ab//2, eby_ab - bh//18),
                         (cx - bw//8 + ox_ab//2, eby_ab + bh//18), thick_ab)
        # 오른쪽 눈썹 /
        pygame.draw.line(surf, col_ab,
                         (cx + bw//8 - ox_ab//2, eby_ab + bh//18),
                         (cx + bw//8 + ox_ab//2, eby_ab - bh//18), thick_ab)
    elif item_id == 'headset':
        hy3 = cy - bh//4  # 아래로 내림
        _bk = (12,12,12); _dg = (50,50,50); _pd = (8,8,10)
        ec_w, ec_h = 10, 14  # 작게
        # 왼쪽 이어컵 (동그란 타원)
        _lx = cx - bw//2 - 3
        pygame.draw.ellipse(surf, _dg, (_lx, hy3, ec_w, ec_h))
        pygame.draw.ellipse(surf, _bk, (_lx, hy3, ec_w, ec_h), 1)
        pygame.draw.ellipse(surf, _pd, (_lx+1, hy3+1, ec_w-2, ec_h-2))
        # 오른쪽 이어컵 (동그란 타원)
        _rx = cx + bw//2 - 7
        pygame.draw.ellipse(surf, _dg, (_rx, hy3, ec_w, ec_h))
        pygame.draw.ellipse(surf, _bk, (_rx, hy3, ec_w, ec_h), 1)
        pygame.draw.ellipse(surf, _pd, (_rx+1, hy3+1, ec_w-2, ec_h-2))
        # 헤드밴드 아치
        _aw = _rx + ec_w//2 - (_lx + ec_w//2)
        _ax = _lx + ec_w//2
        pygame.draw.arc(surf, _bk, (_ax, hy3-8, _aw, 14), 0, math.pi, 2)
    elif item_id == 'rabbit_ears':
        rew = int(bw*0.55); reh = max(1, int(rew*6//8))
        res = pygame.transform.scale(RABBIT_EARS_BASE, (rew, reh))
        surf.blit(res, (cx-rew//2, cy-bh//2-reh+reh//4))
    elif item_id == 'cherry_top':
        bell_top = cy - bh//2
        cr2 = max(4, bw//9)
        cy2 = bell_top - cr2 + 2
        # 생크림
        for cxo3,cyo3 in [(0,-cr2//3),(-cr2//2,0),(cr2//2,0),(0,0)]:
            pygame.draw.circle(surf,(245,245,245),(cx+cxo3,cy2+cyo3),cr2)
        # 체리
        chr_r2 = max(3, bw//10)
        chr_y2 = cy2 - cr2 + 2
        pygame.draw.circle(surf,(148,8,8),(cx,chr_y2),chr_r2)
        pygame.draw.circle(surf,(195,18,18),(cx,chr_y2),chr_r2-1)
        pygame.draw.circle(surf,(235,55,55),(cx-chr_r2//3,chr_y2-chr_r2//3),max(1,chr_r2//3))
        pygame.draw.line(surf,(120,15,15),(cx,chr_y2-chr_r2),(cx+chr_r2//2,chr_y2-chr_r2-max(4,bw//8)),1)
    elif item_id == 'frog_hat_item':
        hw2 = int(bw*0.82); hh2 = max(1,int(hw2*5//10))
        fhs = pygame.transform.scale(FROG_HAT_BASE,(hw2,hh2))
        surf.blit(fhs,(cx-hw2//2, cy-bh//2-hh2+hh2//3))
    elif item_id == 'blossom_pin':
        def _bp2(sx,sy,sr):
            for _bi2 in range(5):
                _ba2=math.radians(_bi2*72-90)
                pygame.draw.circle(surf,(254,117,156),(int(sx+math.cos(_ba2)*sr),int(sy+math.sin(_ba2)*sr)),sr)
            pygame.draw.circle(surf,(255,230,100),(sx,sy),max(1,sr//2+1))
        pin_y = cy - bh//4
        pin_x_l = cx - bw//2 + 4; pin_x_r = cx + bw//2 - 4
        pygame.draw.line(surf,(180,140,160),(pin_x_l,pin_y+4),(pin_x_l,pin_y+10),1)
        pygame.draw.line(surf,(180,140,160),(pin_x_r,pin_y+4),(pin_x_r,pin_y+10),1)
        _bp2(pin_x_l, pin_y, 4); _bp2(pin_x_r, pin_y, 4)
    elif item_id == 'foxfire':
        _t_ff = pygame.time.get_ticks()*0.001
        for _i_ff in range(5):
            _a_ff = _t_ff*0.9 + _i_ff*(math.pi*2/5)
            _rx_ff = bw*(0.68+math.sin(_t_ff*0.35+_i_ff*1.8)*0.22)
            _ry_ff = bh*(0.58+math.cos(_t_ff*0.42+_i_ff*2.1)*0.20)
            _ox = cx + int(math.cos(_a_ff)*_rx_ff)
            _oy = cy + int(math.sin(_a_ff)*_ry_ff)
            _fl = 0.55+abs(math.sin(_t_ff*7.1+_i_ff*2.9))*0.45
            _or = max(2,int((2+abs(math.sin(_t_ff*4.3+_i_ff))*3)*_fl))
            _r2 = int(175+_fl*80); _g2 = int(8+_fl*28)
            _gs4 = pygame.Surface((_or*4+2,_or*4+2),pygame.SRCALPHA)
            _gs4.fill((0,0,0,0))
            pygame.draw.circle(_gs4,(_r2,_g2,5,int(18*_fl)),(_or*2+1,_or*2+1),_or*2)
            surf.blit(_gs4,(_ox-_or*2-1,_oy-_or*2-1))
            pygame.draw.circle(surf,(_r2,_g2,5),(_ox,_oy),_or)
            pygame.draw.circle(surf,(255,min(255,_g2+60),25),(_ox,_oy),max(1,_or-1))


def draw_online_jelly_icon(surf, x, y, highlighted=False):
    col = (165,245,200) if highlighted else (90,180,130)
    # bell (dome)
    pygame.draw.ellipse(surf, col, (x-9,y-12,18,14))
    # inner sheen
    sc = tuple(min(255,c+50) for c in col)
    pygame.draw.ellipse(surf, sc, (x-5,y-10,8,5))
    # tentacles
    for dx in (-6,-2,2,6):
        pygame.draw.line(surf, col, (x+dx,y+2),(x+dx-1,y+10),1)


def draw_online_interact_list(surf, wx, wy, action):
    items = [('banzai','만세하기'),(  'dance','춤추기')]
    iw, ih = 115, 36
    ly = wy - len(items)*ih - 8
    for i,(key,label) in enumerate(items):
        iy = ly + i*ih
        bg = pygame.Surface((iw,ih),pygame.SRCALPHA)
        active = action==key
        bg.fill((25,70,50,235) if active else (15,45,35,215))
        pygame.draw.rect(bg,(80,200,130) if active else (55,140,90),(0,0,iw,ih),1,border_radius=6)
        lx = min(wx-iw//2, OW-iw-5)
        surf.blit(bg,(lx,iy))
        fl=get_font(14,bold=True)
        tl=fl.render(label,True,(200,255,220) if active else (155,215,180))
        surf.blit(tl,(lx+iw//2-tl.get_width()//2, iy+ih//2-tl.get_height()//2))


def _draw_online_action(surf, cx, cy, bw, bh, action, phase):
    tc = (228,175,132); thick = max(2, bw//16)
    if action == 'banzai':
        # 만세: sin 곡선으로 한 번 들었다 내림
        lift = max(0.0, math.sin(phase * (math.pi / 3.6)))
        for side in (-1,1):
            sx=cx+side*int(bw*0.42); sy=cy+bh//6
            ex=cx+side*int(bw*0.72)
            ey=int(cy - int(bh*0.62)*lift + bh//5*(1.0-lift))
            pygame.draw.line(surf,(*tc,215),(sx,sy),(ex,ey),thick)
            pygame.draw.circle(surf,(*tc,195),(ex,ey),max(2,bw//18))
    elif action == 'dance':
        # 춤: 머리 양쪽에서 ~ ~ 웨이브
        for idx,side in enumerate((-1,1)):
            sx=cx+side*int(bw*0.38); sy=cy+bh//8
            wave=int(math.sin(phase*1.2+idx*0.8)*bh*0.32)
            ex=cx+side*int(bw*0.76); ey=sy+wave
            pygame.draw.line(surf,(*tc,215),(sx,sy),(ex,ey),thick)
            pygame.draw.circle(surf,(*tc,195),(ex,ey),max(2,bw//18))


def draw_settings_icon(surf, rect):
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    cx, cy, r = x+w//2, y+h//2, 8
    pygame.draw.circle(surf, (148,165,200), (cx,cy), r)
    pygame.draw.circle(surf, (30,50,90), (cx,cy), r-3)
    for i in range(6):
        a = i*(math.pi/3)
        tx=cx+int(math.cos(a)*(r+2)); ty=cy+int(math.sin(a)*(r+2))
        pygame.draw.circle(surf,(148,165,200),(tx,ty),3)


def draw_slider(surf, sx, sy, sw, value, color=(80,140,220)):
    h = 24
    # 트랙
    pygame.draw.rect(surf,(25,40,80),(sx,sy+h//2-3,sw,6),border_radius=3)
    # 채움
    fill_w = max(6, int(sw*value))
    pygame.draw.rect(surf,color,(sx,sy+h//2-3,fill_w,6),border_radius=3)
    # 썸
    tx = sx + int(sw*value)
    pygame.draw.circle(surf,(220,230,255),(tx,sy+h//2),10)
    pygame.draw.circle(surf,color,(tx,sy+h//2),8)


def draw_settings_screen(surf, bgm_vol, sfx_vol, chat_vol=0.7):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((5,10,30,245))
    surf.blit(overlay,(0,0))
    # 뒤로
    bb = pygame.Surface((75,28),pygame.SRCALPHA)
    bb.fill((22,42,88,210))
    pygame.draw.rect(bb,(65,120,210),(0,0,75,28),1,border_radius=6)
    surf.blit(bb,(15,12))
    fb=get_font(13,bold=True); tb=fb.render('◀ 닫기',True,(165,210,255))
    surf.blit(tb,(15+37-tb.get_width()//2,12+14-tb.get_height()//2))
    # 제목
    ft=get_font(19,bold=True); nt=ft.render('사운드 설정',True,(190,220,255))
    surf.blit(nt,(WIDTH//2-nt.get_width()//2,14))
    pygame.draw.line(surf,(50,90,160),(18,46),(WIDTH-18,46),1)
    # BGM
    fl=get_font(14,bold=True)
    surf.blit(fl.render('BGM',True,(175,215,250)),(SL_BGM[0],SL_BGM[1]-28))
    pct=get_font(13); tp=pct.render(f'{int(bgm_vol*100)}%',True,(220,235,255))
    surf.blit(tp,(SL_BGM[0]+SL_BGM[2]-tp.get_width(),SL_BGM[1]-28))
    draw_slider(surf,SL_BGM[0],SL_BGM[1],SL_BGM[2],bgm_vol,(65,145,230))
    # 효과음
    surf.blit(fl.render('효과음',True,(175,215,250)),(SL_SFX[0],SL_SFX[1]-28))
    tp2=pct.render(f'{int(sfx_vol*100)}%',True,(220,235,255))
    surf.blit(tp2,(SL_SFX[0]+SL_SFX[2]-tp2.get_width(),SL_SFX[1]-28))
    draw_slider(surf,SL_SFX[0],SL_SFX[1],SL_SFX[2],sfx_vol,(65,200,145))
    # 해파리 말소리
    surf.blit(fl.render('해파리 말소리',True,(175,215,250)),(SL_CHAT[0],SL_CHAT[1]-28))
    tp3=pct.render(f'{int(chat_vol*100)}%',True,(220,235,255))
    surf.blit(tp3,(SL_CHAT[0]+SL_CHAT[2]-tp3.get_width(),SL_CHAT[1]-28))
    draw_slider(surf,SL_CHAT[0],SL_CHAT[1],SL_CHAT[2],chat_vol,(200,130,220))


def draw_ranking_icon(surf, rect):
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    # 트로피
    pygame.draw.rect(surf, (188,148,22), (x+w//2-8, y+4, 16, 12), border_radius=2)
    pygame.draw.rect(surf, (222,185,50), (x+w//2-6, y+5, 12, 9), border_radius=2)
    pygame.draw.rect(surf, (188,148,22), (x+w//2-4, y+16, 8, 4))
    pygame.draw.rect(surf, (188,148,22), (x+w//2-7, y+20, 14, 3), border_radius=1)
    pygame.draw.rect(surf, (222,185,50), (x+w//2-3, y+7, 2, 5))  # 별
    t2 = pygame.time.get_ticks()*0.001
    for i in range(3):
        a2 = t2*1.2+i*(math.pi*2/3)
        sx2=x+w//2+int(math.cos(a2)*10); sy2=y+h//2+int(math.sin(a2)*10)
        pygame.draw.circle(surf,(255,235,100),(sx2,sy2),2)


def draw_nickname_input(surf, text, cursor_on):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((5, 10, 30, 245))
    surf.blit(overlay, (0,0))
    ft = get_font(20, bold=True)
    nt = ft.render('닉네임을 입력해주세요', True, (200,230,255))
    surf.blit(nt, (WIDTH//2-nt.get_width()//2, HEIGHT//2-80))
    fd = get_font(12)
    dt = fd.render('랭킹에 표시될 이름이에요 (최대 12자)', True, (120,155,195))
    surf.blit(dt, (WIDTH//2-dt.get_width()//2, HEIGHT//2-48))
    # 입력창
    box = pygame.Rect(WIDTH//2-110, HEIGHT//2-20, 220, 40)
    pygame.draw.rect(surf, (20,40,85), box, border_radius=8)
    pygame.draw.rect(surf, (80,140,220), box, 2, border_radius=8)
    disp = text + ('|' if cursor_on else '')
    fi = get_font(18, bold=True)
    ti = fi.render(disp, True, (220,240,255))
    surf.blit(ti, (box.x+12, box.y+box.h//2-ti.get_height()//2))
    # 확인 버튼
    if text:
        btn = pygame.Rect(WIDTH//2-50, HEIGHT//2+32, 100, 32)
        pygame.draw.rect(surf, (22,55,115,230), btn, border_radius=8)
        pygame.draw.rect(surf, (75,145,230), btn, 1, border_radius=8)
        fb = get_font(14, bold=True)
        tb = fb.render('확인 (Enter)', True, (165,210,255))
        surf.blit(tb, (btn.x+btn.w//2-tb.get_width()//2, btn.y+btn.h//2-tb.get_height()//2))


RANKING_NICK_BTN = pygame.Rect(WIDTH-95, 12, 80, 24)

def draw_ranking_screen(surf, rankings, loading, nickname=''):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((5, 10, 30, 245))
    surf.blit(overlay, (0,0))
    # 뒤로
    bb = pygame.Surface((75, 28), pygame.SRCALPHA)
    bb.fill((22,42,88,210))
    pygame.draw.rect(bb, (75,135,215), (0,0,75,28), 1, border_radius=6)
    surf.blit(bb, (15,12))
    fb = get_font(13, bold=True); tb = fb.render('◀ 닫기', True, (165,210,255))
    surf.blit(tb, (15+37-tb.get_width()//2, 12+14-tb.get_height()//2))
    # 제목
    ft = get_font(20, bold=True)
    nt = ft.render('🏆 랭킹', True, (255,220,60))
    surf.blit(nt, (WIDTH//2-nt.get_width()//2, 14))
    pygame.draw.line(surf, (80,120,200), (18,46), (WIDTH-18,46), 1)
    # 현재 닉네임 표시 (버튼 없이)
    fn_b = get_font(10)
    tn_b = fn_b.render(f'내 닉네임: {nickname[:12] or "?"}', True, (110,155,200))
    surf.blit(tn_b, (WIDTH//2-tn_b.get_width()//2, 34))
    if loading:
        fl = get_font(14); tl = fl.render('불러오는 중...', True, (120,155,200))
        surf.blit(tl, (WIDTH//2-tl.get_width()//2, HEIGHT//2))
        return
    if not rankings:
        fl = get_font(14); tl = fl.render('아직 기록이 없어.', True, (80,110,160))
        surf.blit(tl, (WIDTH//2-tl.get_width()//2, HEIGHT//2)); return
    medals = ['🥇','🥈','🥉']
    for idx, r in enumerate(rankings):
        y_r = 58 + idx*46
        row = pygame.Surface((WIDTH-32, 38), pygame.SRCALPHA)
        row.fill((18,35,80,185) if idx%2==0 else (12,25,60,185))
        pygame.draw.rect(row, (45,80,160,120), (0,0,WIDTH-32,38), 1, border_radius=6)
        surf.blit(row, (16, y_r))
        rank_s = medals[idx] if idx < 3 else f'{idx+1}.'
        fr = get_font(13, bold=True)
        tr = fr.render(rank_s, True, (255,220,60) if idx<3 else (140,175,225))
        surf.blit(tr, (24, y_r+10))
        fn2 = get_font(14, bold=True)
        tn2 = fn2.render(r.get('nickname','?'), True, (200,230,255))
        surf.blit(tn2, (60, y_r+10))
        fs = get_font(13, bold=True)
        sc_s = f"{r.get('score',0):,}점"
        ts = fs.render(sc_s, True, (255,235,100))
        surf.blit(ts, (WIDTH-28-ts.get_width(), y_r+10))


def draw_new_game_warning(surf):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 190))
    surf.blit(overlay, (0, 0))
    # 경고 박스
    box = pygame.Rect(WIDTH//2-120, HEIGHT//2-80, 240, 168)
    bg = pygame.Surface((box.w, box.h), pygame.SRCALPHA)
    bg.fill((18, 22, 48, 245))
    pygame.draw.rect(bg, (200, 60, 60), (0,0,box.w,box.h), 2, border_radius=12)
    surf.blit(bg, box.topleft)
    # 경고 아이콘 + 제목
    fw = get_font(16, bold=True)
    tw = fw.render('⚠  새 게임 시작', True, (255, 100, 100))
    surf.blit(tw, (WIDTH//2-tw.get_width()//2, box.y+14))
    pygame.draw.line(surf, (150,40,40), (box.x+12, box.y+38), (box.x+box.w-12, box.y+38), 1)
    # 경고 메시지
    for i, line in enumerate([
        '저장 데이터가 초기화됩니다.',
        '랭킹에 등록된 점수도',
        '0점으로 초기화됩니다.',
    ]):
        fl = get_font(12)
        tl = fl.render(line, True, (220, 195, 195))
        surf.blit(tl, (WIDTH//2-tl.get_width()//2, box.y+46+i*20))
    # 확인 버튼 (빨강)
    ob = pygame.Surface((WARN_OK_BTN.w, WARN_OK_BTN.h), pygame.SRCALPHA)
    ob.fill((140, 28, 28, 235))
    pygame.draw.rect(ob, (220,55,55), (0,0,WARN_OK_BTN.w,WARN_OK_BTN.h), 1, border_radius=8)
    surf.blit(ob, WARN_OK_BTN.topleft)
    fo = get_font(13, bold=True)
    to = fo.render('새 게임', True, (255,155,155))
    surf.blit(to, (WARN_OK_BTN.x+WARN_OK_BTN.w//2-to.get_width()//2,
                   WARN_OK_BTN.y+WARN_OK_BTN.h//2-to.get_height()//2))
    # 취소 버튼 (파랑)
    cb = pygame.Surface((WARN_CANCEL_BTN.w, WARN_CANCEL_BTN.h), pygame.SRCALPHA)
    cb.fill((20,48,100,235))
    pygame.draw.rect(cb, (70,130,215), (0,0,WARN_CANCEL_BTN.w,WARN_CANCEL_BTN.h), 1, border_radius=8)
    surf.blit(cb, WARN_CANCEL_BTN.topleft)
    fc = get_font(13, bold=True)
    tc = fc.render('취소', True, (155,200,255))
    surf.blit(tc, (WARN_CANCEL_BTN.x+WARN_CANCEL_BTN.w//2-tc.get_width()//2,
                   WARN_CANCEL_BTN.y+WARN_CANCEL_BTN.h//2-tc.get_height()//2))


def draw_cult_doc_list(surf, cult_docs):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((5, 12, 8, 240))
    surf.blit(overlay, (0, 0))

    ft = get_font(21, bold=True)
    title = ft.render('배양서 목록', True, (188, 240, 195))
    surf.blit(title, (WIDTH//2 - title.get_width()//2, 16))
    pygame.draw.line(surf, (50, 140, 80), (20, 46), (WIDTH-20, 46), 1)

    total = sum(cult_docs.values()) if cult_docs else 0
    fb = get_font(13)
    tb = fb.render(f'총 {total}개 보유', True, (130, 185, 145))
    surf.blit(tb, (WIDTH//2 - tb.get_width()//2, HEIGHT-24))

    y = 60
    has_any = False
    for doc_type in sorted(cult_docs):
        if doc_type not in CULT_DOC_NAMES:
            continue
        count = cult_docs[doc_type]
        if count <= 0:
            continue
        has_any = True
        name        = CULT_DOC_NAMES.get(doc_type, f'배양서 #{doc_type}')
        desc        = CULT_DOC_DESCS.get(doc_type, '')
        result_slot = CULT_DOC_RESULT.get(doc_type)
        card_h      = 96 if result_slot is not None else 72

        card = pygame.Surface((WIDTH-36, card_h), pygame.SRCALPHA)
        card.fill((12, 38, 20, 205))
        pygame.draw.rect(card, (45, 130, 72, 190), (0,0,WIDTH-36,card_h), 1, border_radius=8)
        surf.blit(card, (18, y))

        # 미니 배양서 아이콘
        sx, sy = 30, y+10
        pygame.draw.rect(surf, (242,235,210), (sx, sy, 26, 36), border_radius=3)
        pygame.draw.rect(surf, (188,165,118), (sx, sy, 26, 36), 1, border_radius=3)
        pygame.draw.polygon(surf, (210,198,168), [(sx+19,sy),(sx+26,sy+7),(sx+26,sy)])
        pygame.draw.line(surf,(188,165,118),(sx+19,sy),(sx+26,sy+7),1)
        for i in range(3):
            pygame.draw.line(surf,(168,145,100),(sx+4,sy+9+i*7),(sx+22,sy+9+i*7),1)

        fn = get_font(14, bold=True)
        nt = fn.render(name, True, (195, 242, 205))
        surf.blit(nt, (sx+34, y+8))

        fd = get_font(11)
        dt = fd.render(desc, True, (128, 175, 142))
        surf.blit(dt, (sx+34, y+26))

        # 교배 결과
        if result_slot is not None:
            r_name  = JELLY_NAMES[result_slot]
            r_grade = JELLY_GRADES.get(result_slot, 'common')
            r_gcol  = GRADE_COLORS[r_grade]
            fr = get_font(11, bold=True)
            rt = fr.render(f'교배 결과 →  {r_name}', True, (188, 230, 255))
            surf.blit(rt, (sx+34, y+44))
            # 등급 뱃지
            gl = get_font(9, bold=True)
            gl_t = gl.render(GRADE_LABEL[r_grade], True, (255,255,255))
            bw_g = gl_t.get_width()+10; bh_g = gl_t.get_height()+4
            bg_g = pygame.Surface((bw_g, bh_g), pygame.SRCALPHA)
            pygame.draw.rect(bg_g, (*r_gcol, 220), (0,0,bw_g,bh_g), border_radius=8)
            bg_g.blit(gl_t,(5,2)); surf.blit(bg_g,(sx+34+rt.get_width()+6, y+44))
            # 미니 해파리 스프라이트
            bi = _slot_base_idx(result_slot)
            mspr = (RAINBOW_BELL_SPRITE if result_slot==22
                    else PABUN_BELL_SPRITE if result_slot==23
                    else TWIN_BELL_SPRITE  if result_slot==27
                    else BELL_SPRITES[bi])
            mspr = pygame.transform.scale(mspr, (34, 26))
            surf.blit(mspr, (WIDTH-56, y+card_h//2-13))

        fc = get_font(15, bold=True)
        ct = fc.render(f'× {count}', True, (158, 255, 168))
        surf.blit(ct, (WIDTH-28-ct.get_width(), y+8))

        y += card_h + 8
        if y > HEIGHT - 50:
            break

    if not has_any:
        fe = get_font(14)
        et = fe.render('아직 획득한 배양서가 없어.', True, (72, 108, 82))
        surf.blit(et, (WIDTH//2-et.get_width()//2, HEIGHT//2-et.get_height()//2))


def draw_doc_detail(surf, doc_type, inventory):
    """배양서 상세 — 교배 레시피 표시."""
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((5, 12, 8, 245))
    surf.blit(overlay, (0, 0))

    # 뒤로 버튼
    back_r = pygame.Rect(15, 12, 75, 28)
    bb = pygame.Surface((back_r.w, back_r.h), pygame.SRCALPHA)
    bb.fill((20, 55, 30, 210))
    pygame.draw.rect(bb, (70, 160, 95), (0,0,back_r.w,back_r.h), 1, border_radius=6)
    surf.blit(bb, back_r.topleft)
    fb = get_font(13, bold=True)
    tb = fb.render('◀ 목록', True, (160, 230, 175))
    surf.blit(tb, (back_r.x+back_r.w//2-tb.get_width()//2,
                   back_r.y+back_r.h//2-tb.get_height()//2))

    name = CULT_DOC_NAMES.get(doc_type, f'배양서 #{doc_type}')
    ft = get_font(19, bold=True)
    nt = ft.render(name, True, (185, 245, 200))
    surf.blit(nt, (WIDTH//2-nt.get_width()//2, 52))
    pygame.draw.line(surf, (50, 140, 80), (20, 82), (WIDTH-20, 82), 1)

    recipe = CULT_DOC_RECIPE.get(doc_type)
    result_slot = CULT_DOC_RESULT.get(doc_type)

    if recipe and result_slot is not None:
        a_slot, b_slot = recipe
        # 스프라이트 크기
        sw, sh = 80, 60

        def draw_jelly_card(cx, cy, slot):
            bi  = _slot_base_idx(slot)
            spr = (RAINBOW_BELL_SPRITE if slot==22
                   else PABUN_BELL_SPRITE if slot==23
                   else TWIN_BELL_SPRITE  if slot==27
                   else BELL_SPRITES[bi])
            spr = pygame.transform.scale(spr, (sw, sh))
            if slot == 9:   spr.set_alpha(72)
            elif slot == 6: spr.set_alpha(175)
            surf.blit(spr, (cx-sw//2, cy-sh//2))
            # 도감과 동일하게 오버레이 적용 (pcy = cy - sh//2 + 4)
            _draw_slot_overlay(surf, slot, cx, cy - sh//2 + 4, sw, sh)
            fn2 = get_font(11)
            nm2 = fn2.render(JELLY_NAMES[slot], True, (185, 225, 198))
            surf.blit(nm2, (cx-nm2.get_width()//2, cy+sh//2+5))
            gr2 = JELLY_GRADES.get(slot, 'common')
            gc2 = GRADE_COLORS[gr2]
            gl2 = get_font(9, bold=True)
            gt2 = gl2.render(GRADE_LABEL[gr2], True, (255,255,255))
            bw2 = gt2.get_width()+10; bh2 = gt2.get_height()+4
            bg2 = pygame.Surface((bw2,bh2),pygame.SRCALPHA)
            pygame.draw.rect(bg2, (*gc2,215),(0,0,bw2,bh2),border_radius=8)
            bg2.blit(gt2,(5,2))
            surf.blit(bg2,(cx-bw2//2, cy+sh//2+22))

        # A + B
        cy_mid = 195
        draw_jelly_card(90,  cy_mid, a_slot)
        draw_jelly_card(290, cy_mid, b_slot)

        fp = get_font(28, bold=True)
        pt = fp.render('+', True, (168, 235, 180))
        surf.blit(pt, (WIDTH//2-pt.get_width()//2, cy_mid-pt.get_height()//2))

        # 화살표
        fa2 = get_font(22, bold=True)
        at2 = fa2.render('↓', True, (130, 200, 148))
        surf.blit(at2, (WIDTH//2-at2.get_width()//2, cy_mid+sh//2+44))

        # 결과 해파리
        cy_res = cy_mid + sh//2 + 90
        draw_jelly_card(WIDTH//2, cy_res, result_slot)

        # 설명
        fd2 = get_font(12)
        dt2 = fd2.render(CULT_DOC_DESCS.get(doc_type,''), True, (120,175,138))
        surf.blit(dt2, (WIDTH//2-dt2.get_width()//2, HEIGHT-80))

        # 만들기 버튼 (재료 보유 여부 확인)
        a_slot, b_slot = recipe
        can_make = inventory.get(a_slot,0) > 0 and inventory.get(b_slot,0) > 0
        btn_col  = (65, 185, 90) if can_make else (55, 80, 60)
        txt_col  = (155, 248, 170) if can_make else (90, 130, 95)
        btn_bg   = pygame.Surface((MAKE_BTN_RECT.w, MAKE_BTN_RECT.h), pygame.SRCALPHA)
        btn_bg.fill((15, 48, 22, 220) if can_make else (12, 28, 15, 180))
        pygame.draw.rect(btn_bg, btn_col, (0,0,MAKE_BTN_RECT.w,MAKE_BTN_RECT.h), 1, border_radius=10)
        surf.blit(btn_bg, MAKE_BTN_RECT.topleft)
        fb2 = get_font(16, bold=True)
        ft2 = fb2.render('만들기', True, txt_col)
        surf.blit(ft2, (MAKE_BTN_RECT.x+MAKE_BTN_RECT.w//2-ft2.get_width()//2,
                        MAKE_BTN_RECT.y+MAKE_BTN_RECT.h//2-ft2.get_height()//2))
        if not can_make:
            fe2 = get_font(10)
            et2 = fe2.render('재료 부족', True, (100, 130, 108))
            surf.blit(et2, (WIDTH//2-et2.get_width()//2, MAKE_BTN_RECT.y+MAKE_BTN_RECT.h+4))
    else:
        fd = get_font(13)
        nd = fd.render('교배 레시피가 없는 범용 배양서야.', True, (100, 155, 115))
        surf.blit(nd, (WIDTH//2-nd.get_width()//2, HEIGHT//2))


def draw_gacha_screen(surf, slot, timer):
    """가챠 성공 연출 — timer: GACHA_TOTAL → 0"""
    t        = pygame.time.get_ticks() * 0.001
    progress = 1.0 - timer / GACHA_TOTAL

    # 배경 페이드인
    bg = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    bg.fill((3, 5, 14, min(245, int(progress * 3 * 245))))
    surf.blit(bg, (0,0))

    if progress < 0.05:
        return

    # 무지개 글로우 링
    gp = min(1.0, (progress - 0.05) / 0.35)
    if gp > 0:
        for i, hue in enumerate(RAINBOW_HUES):
            r = int(WIDTH * (0.22 + i * 0.058) * gp)
            pulse = 0.9 + abs(math.sin(t*1.5+i*0.4))*0.1
            r = int(r * pulse)
            ga = int(28 * gp * (len(RAINBOW_HUES)-i) / len(RAINBOW_HUES))
            gs = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
            pygame.draw.ellipse(gs, (*hue, ga), (2,2,r*2,r*2))
            surf.blit(gs, (WIDTH//2-r-2, HEIGHT//2-r-2))

    # 해파리 줌인 + 오버슈트
    jp = min(1.0, max(0.0, (progress - 0.15) / 0.35))
    if jp > 0:
        if jp < 0.75:
            scale = jp / 0.75
        else:
            scale = 1.0 + math.sin((jp-0.75)/0.25*math.pi) * 0.12
        sw2 = max(10, int(178 * scale))
        sh2 = max(8,  int(134 * scale))
        cx2, cy2 = WIDTH//2, HEIGHT//2 - 18
        base_spr = (RAINBOW_BELL_SPRITE if slot==22
                    else PABUN_BELL_SPRITE if slot==23
                    else BELL_SPRITES[_slot_base_idx(slot)])
        spr2 = pygame.transform.scale(base_spr, (sw2, sh2))
        surf.blit(spr2, (cx2-sw2//2, cy2-sh2//2))
        _draw_slot_overlay(surf, slot, cx2, cy2 - sh2//2 + 4, sw2, sh2)

    # 이름
    np2 = min(1.0, max(0.0, (progress - 0.45) / 0.2))
    if np2 > 0:
        fn2 = get_font(22, bold=True)
        nt2 = fn2.render(JELLY_NAMES[slot], True, (215, 255, 220))
        nt2.set_alpha(int(np2*255))
        surf.blit(nt2, (WIDTH//2-nt2.get_width()//2, HEIGHT//2+92))

    # 메시지
    mp2 = min(1.0, max(0.0, (progress - 0.60) / 0.2))
    if mp2 > 0:
        fm2 = get_font(12, bold=True)
        mt2 = fm2.render(f'이제부터 {JELLY_NAMES[slot]}가 출몰합니다!', True, (165, 245, 182))
        mt2.set_alpha(int(mp2*255))
        surf.blit(mt2, (WIDTH//2-mt2.get_width()//2, HEIGHT//2+122))

    # 확인 버튼
    cp2 = min(1.0, max(0.0, (progress - 0.84) / 0.12))
    if cp2 > 0:
        bs2 = pygame.Surface((GACHA_CONFIRM_RECT.w, GACHA_CONFIRM_RECT.h), pygame.SRCALPHA)
        bs2.fill((15,50,25, int(cp2*220)))
        pygame.draw.rect(bs2,(65,185,90,int(cp2*255)),(0,0,GACHA_CONFIRM_RECT.w,GACHA_CONFIRM_RECT.h),1,border_radius=8)
        surf.blit(bs2, GACHA_CONFIRM_RECT.topleft)
        fb3 = get_font(15, bold=True)
        ft3 = fb3.render('확인', True, (155,245,170))
        ft3.set_alpha(int(cp2*255))
        surf.blit(ft3, (GACHA_CONFIRM_RECT.x+GACHA_CONFIRM_RECT.w//2-ft3.get_width()//2,
                        GACHA_CONFIRM_RECT.y+GACHA_CONFIRM_RECT.h//2-ft3.get_height()//2))


# ── 우클릭 잡기 메뉴 ──────────────────────────────────────────
class ContextMenu:
    def __init__(self, jelly):
        self.jelly = jelly
        self.w, self.bh_btn = 88, 36  # 버튼 하나당 높이

    def _base_pos(self):
        total_h = self.bh_btn * 2 + 4
        x = max(4, min(WIDTH-self.w-4, int(self.jelly.x)-self.w//2))
        y = max(4, min(HEIGHT-total_h-4,
                       int(self.jelly.y - self.jelly.bh0//2 - total_h - 8)))
        return x, y

    def get_kill_rect(self):
        x, y = self._base_pos()
        return pygame.Rect(x, y, self.w, self.bh_btn)

    def get_catch_rect(self):
        x, y = self._base_pos()
        return pygame.Rect(x, y + self.bh_btn + 4, self.w, self.bh_btn)

    def draw(self, surf):
        kr = self.get_kill_rect()
        cr = self.get_catch_rect()

        # 죽이기 버튼
        kb = pygame.Surface((kr.w, kr.h), pygame.SRCALPHA)
        kb.fill((52, 10, 10, 225))
        pygame.draw.rect(kb, (200, 55, 55), (0,0,kr.w,kr.h), 1, border_radius=7)
        surf.blit(kb, kr.topleft)
        kt = get_font(15).render('죽이기', True, (255, 110, 110))
        surf.blit(kt, (kr.x+kr.w//2-kt.get_width()//2, kr.y+kr.h//2-kt.get_height()//2))

        # 잡기 버튼
        cb = pygame.Surface((cr.w, cr.h), pygame.SRCALPHA)
        cb.fill((12, 22, 52, 225))
        pygame.draw.rect(cb, (80, 160, 210), (0,0,cr.w,cr.h), 1, border_radius=7)
        surf.blit(cb, cr.topleft)
        ct = get_font(17).render('잡기', True, (180, 230, 255))
        surf.blit(ct, (cr.x+cr.w//2-ct.get_width()//2, cr.y+cr.h//2-ct.get_height()//2))


# ── 인벤토리 화면 (3종) ───────────────────────────────────────
def _slot_base_idx(slot):
    return {0:0,1:1,2:0,3:0,4:2,5:0,6:3,7:4,8:5,9:6,10:7,11:8,12:9,13:10,14:11,15:12,16:13,17:14,18:15,19:16,20:17,21:18,22:23,23:24,24:19,25:20,26:21,27:22}.get(slot,0)

def _draw_slot_overlay(surf, slot, pcx, pcy, sw, sh, happy=False):
    """slot_idx에 따라 모자/안경/스파크/귀/코 오버레이 그리기."""
    if slot == 2:
        hw=int(sw*0.82); hh=int(hw*5//10)
        surf.blit(pygame.transform.scale(FROG_HAT_BASE,(hw,hh)),
                  (pcx-hw//2, pcy-4-hh+hh//3))
    elif slot == 3:
        gw=int(sw*0.84); gh=max(1,int(gw*3//10))
        surf.blit(pygame.transform.scale(GLASSES_BASE,(gw,gh)),
                  (pcx-gw//2, pcy+sh//8-gh//3))
    elif slot == 4:
        t4  = pygame.time.get_ticks() * 0.001
        ps4 = max(2, sw//12)
        cx4 = pcx; cy4 = pcy + sh//2 - 4
        for i4 in range(10):
            r4   = 0.18 + abs(math.sin(t4*2.3+i4*1.8))*0.52
            sx4  = cx4 + int(math.sin(t4*7.1+i4*2.5)*sw*r4)
            sy4  = cy4 + int(math.sin(t4*6.3+i4*1.9)*sh*r4*0.75)
            vis4 = abs(math.sin(t4*11.3+i4*3.1))
            if vis4 < 0.50: continue
            br4 = 205+int(vis4*50)
            col4 = (br4, int(br4*0.90), 8)
            seg4 = 1+int(abs(math.sin(t4*5.7+i4*1.3))*2)
            ori4 = int(abs(t4*3.1+i4*2.7))%4
            if ori4==0: pygame.draw.rect(surf,col4,(sx4,sy4,seg4*ps4,ps4))
            elif ori4==1: pygame.draw.rect(surf,col4,(sx4,sy4,ps4,seg4*ps4))
            elif ori4==2:
                for k4 in range(seg4): pygame.draw.rect(surf,col4,(sx4+k4*ps4,sy4-k4*ps4,ps4,ps4))
            else:
                for k4 in range(seg4): pygame.draw.rect(surf,col4,(sx4+k4*ps4,sy4+k4*ps4,ps4,ps4))
            pygame.draw.rect(surf,(255,255,215),(sx4,sy4,ps4,ps4))
    elif slot == 5:
        cw2=int(sw*0.82); ch2=max(1,int(cw2*4//10))
        surf.blit(pygame.transform.scale(CAT_EARS_BASE,(cw2,ch2)),
                  (pcx-cw2//2, pcy-4-ch2+ch2//4))
    elif slot == 7:  # 얼어붙은: 결정 샘플 몇 개
        for k in range(5):
            a2=k*0.9+0.5; s2=random.randint(3,6)
            ex2=pcx+int(math.cos(a2)*sw*0.65); ey2=pcy+sh//2+int(math.sin(a2)*sh*0.55)
            ss2=pygame.Surface((s2*2+2,s2*2+2),pygame.SRCALPHA)
            c2=s2+1
            pygame.draw.line(ss2,(210,240,255,200),(c2-s2,c2),(c2+s2,c2),1)
            pygame.draw.line(ss2,(210,240,255,200),(c2,c2-s2),(c2,c2+s2),1)
            surf.blit(ss2,(ex2-s2-1,ey2-s2-1))
    elif slot == 8:  # 천사: 링
        hlw=int(sw*0.80); hlh=max(1,int(hlw*3//11))
        surf.blit(pygame.transform.scale(HALO_BASE,(hlw,hlh)),
                  (pcx-hlw//2, pcy-4-hlh-2))
    elif slot == 10:  # 털복숭이: 인게임처럼 360° 털 2레이어
        col2=(172,128,78)
        for li,(r0,r1,ba) in enumerate([(0.08,0.24,145),(0.24,0.40,182)]):
            slen2=int(sw*(r1-r0)+2)
            for i in range(10):
                ang2=-math.pi+i/9*(math.pi*2)
                sx2=pcx+int(math.cos(ang2)*sw*r0)
                sy2=pcy+sh//2+int(math.sin(ang2)*sh*r0*0.75)
                hang2=ang2+math.sin(li*2.1+i*0.62)*0.15
                ex2=int(sx2+math.cos(hang2)*slen2)
                ey2=int(sy2+math.sin(hang2)*slen2)
                pygame.draw.line(surf,(col2[0],col2[1],col2[2],ba),(sx2,sy2),(ex2,ey2),2)
    elif slot == 11:  # 해파리 왕: 왕관 + 수염
        kw=int(sw*0.65); kh=max(1,int(kw*3//11))
        surf.blit(pygame.transform.scale(CROWN_BASE,(kw,kh)),
                  (pcx-kw//2, pcy-4-kh+kh//4))
        bdw=int(sw*0.60); bdh=max(1,int(bdw*5//9))
        surf.blit(pygame.transform.scale(BEARD_BASE,(bdw,bdh)),
                  (pcx-bdw//2, pcy-4+sh//2+sh*2//5))
    elif slot == 12:  # 썩은 해파리: 뇌
        brw=int(sw*0.30); brh=max(1,int(brw*7//10))
        surf.blit(pygame.transform.scale(BRAIN_BASE,(brw,brh)),
                  (pcx-brw//2, pcy-4-brh+brh//4))
    elif slot == 20:  # 눈사람: 작은 머리 + 당근코
        hw2=int(sw*0.58); hh2=int(sh*0.58)
        hs2=pygame.transform.scale(BELL_SPRITES[_slot_base_idx(slot)],(hw2,hh2))
        hy2=pcy-4-hh2+hh2//3
        surf.blit(hs2,(pcx-hw2//2,hy2))
        er5=max(1,hw2//16); ey5=hy2+hh2//2+hh2//8
        pygame.draw.rect(surf,(12,12,32),(pcx-hw2//8,ey5,er5+1,er5+1))
        pygame.draw.rect(surf,(12,12,32),(pcx+hw2//16,ey5,er5+1,er5+1))
        nw5=max(3,hw2//7); nh5=max(2,hw2//12)
        pygame.draw.rect(surf,(242,128,12),(pcx-nw5//2,ey5+er5+2,nw5,nh5))
    elif slot == 19:  # 선인장 해파리: 연노랑 가시 360°
        rx19=sw*0.375; ry19=sh*0.48
        for i in range(18):
            ang2=-math.pi+(i/18)*math.pi*2
            sx2=pcx+int(math.cos(ang2)*rx19)
            sy2=pcy+sh//2-4+int(math.sin(ang2)*ry19)
            ex2=sx2+int(math.cos(ang2)*4); ey2=sy2+int(math.sin(ang2)*4)
            pygame.draw.line(surf,(245,238,145),(sx2,sy2),(ex2,ey2),2)
    elif slot == 18:  # 저주받은 해파리: 발광 눈 + 여우불 (인게임에 가깝게)
        tinv  = pygame.time.get_ticks() * 0.001
        spy18 = pcy + sh//2 - 4  # 스프라이트 실제 중심 y
        # 발광 눈
        ey4 = spy18 + sh//8; er4 = max(2, sw//16)
        for ex4 in (pcx-sw//8, pcx+sw//16):
            pygame.draw.circle(surf,(220,15,15),(ex4,ey4),er4+1)
            pygame.draw.circle(surf,(255,60,60),(ex4,ey4),er4)
        # 여우불 오브 5개 — 인게임과 동일 궤도
        n18 = 5
        for i in range(n18):
            a4  = tinv*0.9 + i*(math.pi*2/n18)
            rx4 = sw * (0.68 + math.sin(tinv*0.35+i*1.8)*0.22)
            ry4 = sh * (0.58 + math.cos(tinv*0.42+i*2.1)*0.20)
            ox4 = pcx    + int(math.cos(a4)*rx4)
            oy4 = spy18  + int(math.sin(a4)*ry4)
            fl4 = 0.55 + abs(math.sin(tinv*7.1+i*2.9))*0.45
            or4 = max(2, int(3*fl4)); rc4 = int(175+fl4*80)
            # 꼬리
            for j in range(1,4):
                ta2=a4-j*0.18
                tx=pcx+int(math.cos(ta2)*rx4); ty=spy18+int(math.sin(ta2)*ry4)
                tr=max(1,or4-j); ta3=int(fl4*150*(4-j)//3)
                ts=pygame.Surface((tr*2+2,tr*2+2),pygame.SRCALPHA)
                pygame.draw.circle(ts,(rc4,8,5,ta3),(tr+1,tr+1),tr)
                surf.blit(ts,(tx-tr-1,ty-tr-1))
            # 글로우
            for gr4 in range(or4*4,0,-2):
                ga4=int(18*fl4*gr4//(or4*4))
                gs4=pygame.Surface((gr4*2+2,gr4*2+2),pygame.SRCALPHA)
                pygame.draw.circle(gs4,(rc4,8,5,ga4),(gr4+1,gr4+1),gr4)
                surf.blit(gs4,(ox4-gr4-1,oy4-gr4-1))
            pygame.draw.circle(surf,(rc4,8,5),(ox4,oy4),or4)
            pygame.draw.circle(surf,(255,min(255,36+60),25),(ox4,oy4),max(1,or4-1))
    elif slot == 17:  # 토끼 해파리: 토끼 귀
        rew=int(sw*0.78); reh=max(1,int(rew*6//8))
        surf.blit(pygame.transform.scale(RABBIT_EARS_BASE,(rew,reh)),
                  (pcx-rew//2, pcy-4-reh+reh//4))
    elif slot == 16:  # 멋쟁이 해파리: 탑햇
        hw2=int(sw*0.75); hh2=max(1,int(hw2*6//12))
        surf.blit(pygame.transform.scale(TOP_HAT_BASE,(hw2,hh2)),
                  (pcx-hw2//2, pcy-4-hh2+hh2//4))
    elif slot == 15:  # 화난 해파리: 눈썹 + 팔 미리보기
        col16 = (192, 44, 30)
        thick16 = max(2, sw // 11)
        # 눈 위치: pcy-4+sh//2(벨중심) + sh//8(눈오프셋) - sh//7(눈썹오프셋)
        eby16 = pcy - 4 + sh//2 + sh//8 - sh//7
        ox16  = sw // 5
        # 눈썹
        pygame.draw.line(surf, (14,8,8),
                         (pcx-sw//8-ox16//2, eby16-sh//18),
                         (pcx-sw//8+ox16//2, eby16+sh//18), thick16)
        pygame.draw.line(surf, (14,8,8),
                         (pcx+sw//8-ox16//2, eby16+sh//18),
                         (pcx+sw//8+ox16//2, eby16-sh//18), thick16)
        # 팔 (행복/댄스 중엔 숨김)
        if not happy:
            for s16 in (-1,1):
                shx16 = pcx+s16*(sw//2-2); shy16 = pcy+sh//5
                elx16 = pcx+s16*int(sw*0.72); ely16 = shy16+int(sh*0.42)
                hax16 = pcx+s16*int(sw*0.18); hay16 = ely16+int(sh*0.10)
                pygame.draw.line(surf,col16,(shx16,shy16),(elx16,ely16),max(2,sw//14))
                pygame.draw.line(surf,col16,(elx16,ely16),(hax16,hay16),max(2,sw//14))
    # slot 15 (구름 해파리)는 기본 스프라이트 그대로 표시
    elif slot == 13:  # 심해 해파리: 발광 낚싯대 간략 표시
        stalk_y = pcy - 4  # 실제 머리 꼭대기 (pcy = bell_top + 4)
        mid_x   = pcx + 4
        tip_x   = pcx + 8
        tip_y   = stalk_y - int(sw * 0.22)
        pygame.draw.line(surf, (75,92,108), (pcx, stalk_y), (mid_x, stalk_y-int(sw*0.11)), 1)
        pygame.draw.line(surf, (75,92,108), (mid_x, stalk_y-int(sw*0.11)), (tip_x, tip_y), 1)
        orb_r2 = max(2, sw//12)
        gs2 = pygame.Surface((orb_r2*4+2, orb_r2*4+2), pygame.SRCALPHA)
        pygame.draw.circle(gs2, (48,218,178,60), (orb_r2*2+1, orb_r2*2+1), orb_r2*2)
        surf.blit(gs2, (tip_x-orb_r2*2-1, tip_y-orb_r2*2-1))
        pygame.draw.circle(surf, (48,218,178), (tip_x, tip_y), orb_r2)
        pygame.draw.circle(surf, (220,255,242), (tip_x, tip_y), max(1,orb_r2-1))
    elif slot == 21:  # 황금 해파리: 타원 글로우 + 공전 별
        t21   = pygame.time.get_ticks() * 0.001
        pg21  = 0.6 + abs(math.sin(t21 * 2.2)) * 0.4
        spy21 = pcy + sh//2 - 4
        for ring in range(3, 0, -1):
            grw = int(sw * (1.0 + ring * 0.22 * pg21))
            grh = int(sh * (1.0 + ring * 0.18 * pg21))
            ga  = int(28 * pg21 * ring // 3)
            gs  = pygame.Surface((grw+4, grh+4), pygame.SRCALPHA)
            gs.fill((0,0,0,0))
            pygame.draw.ellipse(gs, (255,198,28,ga), (2,2,grw,grh))
            surf.blit(gs, (pcx-grw//2-2, spy21-grh//2-2))
        # 금전닢 부유 애니메이션
        for k in range(5):
            cp  = (t21 * 0.7 + k * 0.22) % 1.0
            cxc = pcx + int(math.sin(k*1.8 + t21*0.3) * sw * 0.42)
            cyc = spy21 + int(sh*0.55) - int(cp * sh * 1.2)
            if cp < 0.18:   ac = int(cp/0.18*220)
            elif cp > 0.72: ac = int((1.0-cp)/0.28*220)
            else:           ac = 220
            rc = max(2, int(sw*0.045))
            gc = pygame.Surface((rc*2+4,rc*2+4), pygame.SRCALPHA)
            cc = rc+2
            pygame.draw.circle(gc,(155,108,5,ac),(cc,cc),rc)
            pygame.draw.circle(gc,(238,190,28,ac),(cc,cc),max(1,rc-1))
            pygame.draw.circle(gc,(255,235,115,ac),(cc-rc//3,cc-rc//3),max(1,rc//3))
            surf.blit(gc,(cxc-rc-2,cyc-rc-2))
        # 돼지 귀
        pew21 = int(sw * 0.50); peh21 = max(1, int(pew21 // 4))
        pes21 = pygame.transform.scale(PIG_EARS_BASE, (pew21, peh21))
        surf.blit(pes21, (pcx - pew21//2, pcy - 4 - peh21 + peh21//4))
        # 돼지코
        pnw21 = max(4, sw * 5 // 16)
        pnh21 = max(2, pnw21 * 3 // 5)
        pns21 = pygame.transform.scale(PIG_NOSE_BASE, (pnw21, pnh21))
        surf.blit(pns21, (pcx - pnw21//2, pcy - 4 + sh * 5 // 8 + sh // 10))
    elif slot == 26:  # 벚꽃 해파리: 꽃 장식 + 꽃잎 파티클
        t26  = pygame.time.get_ticks() * 0.001
        spy26 = pcy - 4
        fr26  = max(3, sw//10)
        cy26  = spy26 - fr26 - 1
        for k26 in range(5):
            a26 = k26*(math.pi*2/5) - math.pi/2
            px26 = pcx + int(math.cos(a26)*fr26*1.4)
            py26 = cy26 + int(math.sin(a26)*fr26*1.0)
            pygame.draw.circle(surf, (255,185,202), (px26,py26), fr26)
            pygame.draw.circle(surf, (255,215,228), (px26,py26), max(1,fr26-1))
        pygame.draw.circle(surf, (255,232,120), (pcx,cy26), max(2,fr26//2))
        spy26c = pcy + sh//2 - 4
        for i26 in range(6):
            a_p26 = t26*0.6 + i26*(math.pi*2/6)
            px_p  = pcx + int(math.cos(a_p26)*sw*0.85 + math.sin(t26*1.2+i26)*sw*0.18)
            py_p  = spy26c + int(math.sin(a_p26)*sh*0.70)
            sp26  = abs(math.sin(t26*2.5+i26*1.5))
            if sp26 > 0.3:
                sz26 = max(3, int(sp26*5))
                ps26 = pygame.Surface((sz26*2+2, sz26+2), pygame.SRCALPHA)
                pygame.draw.ellipse(ps26, (255,195,210,int(sp26*200)), (1,1,sz26*2,sz26))
                rs26 = pygame.transform.rotate(ps26, math.degrees(a_p26))
                rw26,rh26 = rs26.get_size()
                surf.blit(rs26, (px_p-rw26//2, py_p-rh26//2))
    elif slot in (24, 25):  # 푸딩/소다 푸딩 해파리: 카라멜 + 생크림 + 체리
        spy24 = pcy - 4  # 벨 상단
        # 카라멜 소스
        caw = int(sw * 0.68); cah = max(3, int(sw * 0.10))
        pygame.draw.ellipse(surf, (115, 60, 4), (pcx-caw//2, spy24-cah//2, caw, cah))
        pygame.draw.ellipse(surf, (145, 80, 8), (pcx-caw//2+2, spy24-cah//2, caw-4, max(1,cah-1)))
        # 생크림
        cr24 = max(5, sw//9)
        cy24 = spy24 - cah//2 - cr24 + 2
        for cxo, cyo in [(0,-cr24//3),(-cr24//2,0),(cr24//2,0),(0,0)]:
            pygame.draw.circle(surf, (245,245,245), (pcx+cxo, cy24+cyo), cr24)
        pygame.draw.circle(surf, (255,255,255), (pcx-cr24//4, cy24-cr24//4), max(2,cr24//3))
        # 체리
        chr_r = max(4, sw//10)
        chr_y = cy24 - cr24 + 2
        pygame.draw.circle(surf, (148,8,8),   (pcx, chr_y), chr_r)
        pygame.draw.circle(surf, (195,18,18), (pcx, chr_y), chr_r-1)
        pygame.draw.circle(surf, (235,55,55), (pcx-chr_r//3, chr_y-chr_r//3), max(1,chr_r//3))
        pygame.draw.line(surf, (188,18,18), (pcx, chr_y-chr_r), (pcx+chr_r//2, chr_y-chr_r-max(5,sw//8)), 1)
    elif slot == 22:  # 무지개 해파리: 후광 + 아크
        t22   = pygame.time.get_ticks() * 0.001
        spy22 = pcy + sh//2 - 4
        n22   = len(RAINBOW_HUES)
        # 무지개 후광
        pg22 = 0.55 + abs(math.sin(t22 * 2.0)) * 0.45
        for i22 in range(5):
            hue22 = RAINBOW_HUES[(i22 + int(t22 * 2)) % n22]
            grw22 = int(sw * (1.0 + (i22+1) * 0.15 * pg22))
            grh22 = int(sh * (1.0 + (i22+1) * 0.12 * pg22))
            ga22  = int(24 * pg22 * (5-i22) // 5)
            gs22  = pygame.Surface((grw22+4, grh22+4), pygame.SRCALPHA)
            pygame.draw.ellipse(gs22, (*hue22, ga22), (2,2,grw22,grh22))
            surf.blit(gs22, (pcx-grw22//2-2, spy22-grh22//2-2))
        # 무지개 아크 — 해파리 외곽 궤도에서 2개가 서서히 사라졌다 나타남
        rw_arc22 = int(sw * 0.28)
        for arc_i in range(2):
            angle22  = t22 * 0.4 + arc_i * math.pi
            ax22 = pcx + int(math.cos(angle22) * sw * 0.82)
            ay22 = spy22 + int(math.sin(angle22) * sh * 0.72)
            al22 = int((0.45 + abs(math.sin(t22*0.5+arc_i*math.pi))*0.55) * 118)
            for i22 in range(7):
                rw22 = rw_arc22 - i22 * max(1, int(sw*0.015))
                rh22 = max(2, int(rw22*0.52))
                if rw22 < 4: continue
                a22f = int(al22*(1.0-i22*0.04))
                gs22 = pygame.Surface((rw22*2+4,rh22*2+4),pygame.SRCALPHA)
                pygame.draw.arc(gs22,(*RAINBOW_HUES[i22],a22f),
                                (2,2,rw22*2,rh22*2),0,math.pi,2)
                surf.blit(gs22,(ax22-rw22-2,ay22-rh22-2))


def draw_inventory(surf, inventory, page=0):
    SLOTS_PER_PAGE = 6
    total_slots    = len(JELLY_NAMES)
    total_pages    = max(1, math.ceil(total_slots / SLOTS_PER_PAGE))

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((5,10,30,238))
    surf.blit(overlay, (0,0))

    ft = get_font(21, bold=True)
    title = ft.render('해파리 가방', True, (175,228,255))
    surf.blit(title, (WIDTH//2-title.get_width()//2, 16))
    pygame.draw.line(surf, (50,90,140), (20,46), (WIDTH-20,46), 1)

    # 페이지 표시
    fp = get_font(12)
    pg_txt = fp.render(f'{page+1} / {total_pages}', True, (120,160,200))
    surf.blit(pg_txt, (WIDTH//2-pg_txt.get_width()//2, HEIGHT-48))

    # 3×2 그리드
    positions = [(65,158),(190,158),(315,158),
                 (65,365),(190,365),(315,365)]
    cw, ch = 108, 148
    start  = page * SLOTS_PER_PAGE

    for pos_i, (cx, cy) in enumerate(positions):
        slot = start + pos_i

        card = pygame.Surface((cw, ch), pygame.SRCALPHA)
        if slot < total_slots:
            count = inventory.get(slot, 0)
            if count > 0:
                card.fill((20,38,75,185))
                pygame.draw.rect(card,(60,128,188,180),(0,0,cw,ch),1,border_radius=8)
            else:
                card.fill((14,20,42,140))
                pygame.draw.rect(card,(38,48,80,120),(0,0,cw,ch),1,border_radius=8)
        else:
            card.fill((10,14,30,80))   # 빈 슬롯
            pygame.draw.rect(card,(28,35,60,80),(0,0,cw,ch),1,border_radius=8)
        surf.blit(card, (cx-cw//2, cy-ch//2))

        if slot >= total_slots:
            continue   # 빈 슬롯은 카드만

        count      = inventory.get(slot, 0)
        discovered = slot in inventory   # 어항에 모두 넣었어도 발견 유지
        pcx, pcy = cx, cy-ch//2+52
        sw, sh   = 58, 44
        spr = pygame.transform.scale(BELL_SPRITES[_slot_base_idx(slot)], (sw, sh))

        if count == 0 and not discovered:
            dark = spr.copy()
            dark.fill((30,30,50,210), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(dark, (pcx-sw//2, pcy-4))
            fq = get_font(26, bold=True)
            q  = fq.render('?', True, (70,80,108))
            surf.blit(q, (pcx-q.get_width()//2, pcy-q.get_height()//2+6))
        else:
            if slot == 9:    spr.set_alpha(72)
            elif slot == 6:  spr.set_alpha(175)
            elif slot == 22: spr = pygame.transform.scale(RAINBOW_BELL_SPRITE, (sw, sh))
            elif slot == 23: spr = pygame.transform.scale(PABUN_BELL_SPRITE, (sw, sh))
            elif slot == 27: spr = pygame.transform.scale(TWIN_BELL_SPRITE, (sw, sh))
            surf.blit(spr, (pcx-sw//2, pcy-4))
            _draw_slot_overlay(surf, slot, pcx, pcy, sw, sh)
            fc = get_font(12, bold=True)
            ct = fc.render(f'× {count}', True, (255,238,145))
            surf.blit(ct, (cx-ct.get_width()//2, cy+ch//2-46))

        fn  = get_font(11)
        nm  = JELLY_NAMES[slot] if (count > 0 or discovered) else '???'
        nc  = (168,210,235) if (count > 0 or discovered) else (68,78,108)
        ns2 = fn.render(nm, True, nc)
        surf.blit(ns2, (cx-ns2.get_width()//2, cy+ch//2-30))

        # 등급 뱃지 (발견한 종만)
        if count > 0 or discovered:
            grade = JELLY_GRADES.get(slot, 'common')
            gcol  = GRADE_COLORS[grade]
            fg2   = get_font(9, bold=True)
            gt    = fg2.render(GRADE_LABEL[grade], True, (255,255,255))
            bw2   = gt.get_width() + 12
            bh2   = gt.get_height() + 6
            bx2   = cx - bw2//2
            by2   = cy - ch//2 + 7

            if grade == 'epic':
                t = pygame.time.get_ticks() * 0.001
                pulse = 0.7 + abs(math.sin(t * 2.0)) * 0.3
                gcol  = (int(140+pulse*25), int(40+pulse*15), int(220+pulse*28))
                # 얇은 글로우 2겹
                for ring in range(2, 0, -1):
                    gw = bw2+ring*4; gh = bh2+ring*2
                    gs = pygame.Surface((gw, gh), pygame.SRCALPHA)
                    pygame.draw.rect(gs, (*gcol, int(30*pulse*(3-ring)//2)),
                                     (0,0,gw,gh), border_radius=11)
                    surf.blit(gs, (cx-gw//2, by2-ring))
                # 4개 작은 반짝 (공전 없이 자리에서 깜빡)
                for k in range(4):
                    sa  = k * (math.pi/2) + t * 0.6
                    spx = cx + int(math.cos(sa) * (bw2//2+7))
                    spy = by2 + bh2//2 + int(math.sin(sa) * (bh2//2+5))
                    sp  = abs(math.sin(t*3.5 + k*1.6))
                    if sp > 0.5:
                        ss = max(1, int(sp*3))
                        sc = (200, 120, 255)
                        pygame.draw.line(surf, sc, (spx-ss,spy),(spx+ss,spy), 1)
                        pygame.draw.line(surf, sc, (spx,spy-ss),(spx,spy+ss), 1)

            elif grade == 'legendary':
                t = pygame.time.get_ticks() * 0.001
                pulse = 0.65 + abs(math.sin(t * 2.8)) * 0.35
                gcol  = (int(215+pulse*40), int(145+pulse*30), int(8+pulse*12))
                # 황금 글로우 링
                for ring in range(4, 0, -1):
                    gw = bw2+ring*5; gh = bh2+ring*3
                    gs = pygame.Surface((gw, gh), pygame.SRCALPHA)
                    pygame.draw.rect(gs, (*gcol, int(38*pulse*(5-ring)//4)),
                                     (0,0,gw,gh), border_radius=12)
                    surf.blit(gs, (cx-gw//2, by2-ring))
                # 회전 반짝 별 파티클
                for k in range(6):
                    sa  = t * 2.0 + k * (math.pi*2/6)
                    spx = cx + int(math.cos(sa) * (bw2//2+9))
                    spy = by2 + bh2//2 + int(math.sin(sa) * (bh2//2+7))
                    sp  = abs(math.sin(t*5.5 + k*1.4))
                    if sp > 0.35:
                        ss  = max(1, int(sp*4))
                        sc  = (255, int(210+sp*45), int(40*sp))
                        pygame.draw.line(surf, sc, (spx-ss,spy),(spx+ss,spy), 1)
                        pygame.draw.line(surf, sc, (spx,spy-ss),(spx,spy+ss), 1)
                        pygame.draw.circle(surf, sc, (spx, spy), max(1,ss//2))

            elif grade == 'secret':
                t = pygame.time.get_ticks() * 0.001
                # 3색 부드러운 사이클
                phase = (math.sin(t * 1.2) + 1) / 2
                c1, c2, c3 = SECRET_COLS
                if phase < 0.33:
                    f = phase / 0.33
                    gcol = tuple(int(c1[i]+(c2[i]-c1[i])*f) for i in range(3))
                elif phase < 0.67:
                    f = (phase-0.33) / 0.34
                    gcol = tuple(int(c2[i]+(c3[i]-c2[i])*f) for i in range(3))
                else:
                    f = (phase-0.67) / 0.33
                    gcol = tuple(int(c3[i]+(c1[i]-c3[i])*f) for i in range(3))
                # 부드러운 글로우 3겹
                for ring in range(3, 0, -1):
                    gw = bw2+ring*4; gh = bh2+ring*2
                    gs = pygame.Surface((gw, gh), pygame.SRCALPHA)
                    pygame.draw.rect(gs, (*gcol, int(28*(4-ring)//3)),
                                     (0,0,gw,gh), border_radius=11)
                    surf.blit(gs, (cx-gw//2, by2-ring))
                # 3색 반짝 별 6개
                for k in range(6):
                    sa  = k*(math.pi/3) + t*0.7
                    spx = cx + int(math.cos(sa)*(bw2//2+8))
                    spy = by2 + bh2//2 + int(math.sin(sa)*(bh2//2+5))
                    sp  = abs(math.sin(t*3.2+k*1.5))
                    if sp > 0.4:
                        ss = max(1, int(sp*3))
                        sc = SECRET_COLS[(k+int(t*2))%3]
                        pygame.draw.line(surf, sc, (spx-ss,spy),(spx+ss,spy), 1)
                        pygame.draw.line(surf, sc, (spx,spy-ss),(spx,spy+ss), 1)

            badge = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
            pygame.draw.rect(badge, (*gcol, 222), (0,0,bw2,bh2), border_radius=10)
            border_col = (255,240,160,100) if grade=='legendary' else (255,255,255,50)
            pygame.draw.rect(badge, border_col, (0,0,bw2,bh2), 1, border_radius=10)
            badge.blit(gt, (6, 3))
            surf.blit(badge, (bx2, by2))

    # 이전/다음 버튼
    def draw_nav_btn(rect, label, active):
        bg = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        bg.fill((25,50,100,210) if active else (15,25,50,120))
        pygame.draw.rect(bg,(80,140,210) if active else (40,60,100),(0,0,rect.w,rect.h),1,border_radius=6)
        surf.blit(bg, rect.topleft)
        fc2 = get_font(13, bold=active)
        ft2 = fc2.render(label, True, (180,220,255) if active else (60,80,110))
        surf.blit(ft2, (rect.x+rect.w//2-ft2.get_width()//2,
                        rect.y+rect.h//2-ft2.get_height()//2))

    draw_nav_btn(INV_PREV_RECT, '◀ 이전', page > 0)
    draw_nav_btn(INV_NEXT_RECT, '다음 ▶', page < total_pages-1)

    total = sum(inventory.values())
    tb2 = get_font(13).render(f'총 {total}마리 획득', True, (140,175,210))
    surf.blit(tb2, (WIDTH//2-tb2.get_width()//2, HEIGHT-24))


# ── 도감 상세 화면 ────────────────────────────────────────────
DETAIL_BACK_RECT = pygame.Rect(15, 12, 75, 28)


def _wrap_text(text, font, max_width):
    words = text.split(' ')
    lines = []
    current = ''
    for word in words:
        test = (current + ' ' + word).strip() if current else word
        if font.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            if font.size(word)[0] > max_width:
                line = ''
                for ch in word:
                    if font.size(line + ch)[0] > max_width:
                        lines.append(line)
                        line = ch
                    else:
                        line += ch
                current = line
            else:
                current = word
    if current:
        lines.append(current)
    return lines


def draw_jelly_detail(surf, slot, inventory):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((3, 8, 25, 248))
    surf.blit(overlay, (0, 0))

    # 뒤로 버튼
    bb = pygame.Surface((DETAIL_BACK_RECT.w, DETAIL_BACK_RECT.h), pygame.SRCALPHA)
    bb.fill((25, 50, 100, 210))
    pygame.draw.rect(bb, (80, 140, 210), (0, 0, DETAIL_BACK_RECT.w, DETAIL_BACK_RECT.h), 1, border_radius=6)
    surf.blit(bb, DETAIL_BACK_RECT.topleft)
    fb = get_font(13, bold=True)
    tb = fb.render('◀ 목록', True, (180, 220, 255))
    surf.blit(tb, (DETAIL_BACK_RECT.x + DETAIL_BACK_RECT.w//2 - tb.get_width()//2,
                   DETAIL_BACK_RECT.y + DETAIL_BACK_RECT.h//2 - tb.get_height()//2))

    count      = inventory.get(slot, 0)
    discovered = slot in inventory
    info  = JELLY_INFO.get(slot, {})

    # 해파리 스프라이트
    sw, sh   = 120, 90
    pcx, pcy = WIDTH // 2, 122
    base_idx = _slot_base_idx(slot)
    spr = pygame.transform.scale(BELL_SPRITES[base_idx], (sw, sh))

    if count > 0 or discovered:
        if slot == 9:    spr.set_alpha(72)
        elif slot == 6:  spr.set_alpha(175)
        elif slot == 22: spr = pygame.transform.scale(RAINBOW_BELL_SPRITE, (sw, sh))
        elif slot == 23: spr = pygame.transform.scale(PABUN_BELL_SPRITE, (sw, sh))
        elif slot == 27: spr = pygame.transform.scale(TWIN_BELL_SPRITE, (sw, sh))
        surf.blit(spr, (pcx - sw//2, pcy - 4))
        _draw_slot_overlay(surf, slot, pcx, pcy, sw, sh)
    else:
        dark = spr.copy()
        dark.fill((20, 20, 40, 200), special_flags=pygame.BLEND_RGBA_MULT)
        surf.blit(dark, (pcx - sw//2, pcy - 4))
        fq = get_font(36, bold=True)
        q  = fq.render('?', True, (58, 72, 108))
        surf.blit(q, (pcx - q.get_width()//2, pcy - 4 + sh//2 - q.get_height()//2))

    # 이름
    name_y = pcy - 4 + sh + 10
    name   = JELLY_NAMES[slot] if (count > 0 or discovered) else '???'
    fn     = get_font(20, bold=True)
    nt     = fn.render(name, True, (220, 240, 255))
    surf.blit(nt, (pcx - nt.get_width()//2, name_y))

    # 등급 뱃지
    badge_y = name_y + fn.get_height() + 4
    if count > 0 or discovered:
        grade = JELLY_GRADES.get(slot, 'common')
        gcol  = GRADE_COLORS[grade]
        fg2   = get_font(10, bold=True)
        gt    = fg2.render(GRADE_LABEL[grade], True, (255, 255, 255))
        bw2   = gt.get_width() + 14
        bh2   = gt.get_height() + 6
        badge = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
        pygame.draw.rect(badge, (*gcol, 222), (0, 0, bw2, bh2), border_radius=10)
        pygame.draw.rect(badge, (255, 255, 255, 40), (0, 0, bw2, bh2), 1, border_radius=10)
        badge.blit(gt, (7, 3))
        surf.blit(badge, (pcx - bw2//2, badge_y))
        div_y = badge_y + bh2 + 10
    else:
        div_y = badge_y + 10

    # 구분선
    pygame.draw.line(surf, (50, 90, 140), (20, div_y), (WIDTH - 20, div_y), 1)

    y      = div_y + 12
    max_w  = WIDTH - 38
    fl     = get_font(12, bold=True)
    fd     = get_font(12)
    line_h = fd.get_height() + 2

    if (count > 0 or discovered) and info:
        # 서식지
        surf.blit(fl.render('서식지', True, (100, 180, 230)), (20, y))
        y += fl.get_height() + 2
        for line in _wrap_text(info.get('habitat', ''), fd, max_w):
            surf.blit(fd.render(line, True, (175, 212, 238)), (22, y))
            y += line_h
        y += 9

        # 성격
        surf.blit(fl.render('성격', True, (100, 180, 230)), (20, y))
        y += fl.get_height() + 2
        for line in _wrap_text(info.get('personality', ''), fd, max_w):
            surf.blit(fd.render(line, True, (175, 212, 238)), (22, y))
            y += line_h
        y += 14

        # 한마디 (가운데, 노란색)
        fq2 = get_font(12)
        for line in _wrap_text(info.get('quote', ''), fq2, max_w):
            qt = fq2.render(line, True, (255, 232, 100))
            surf.blit(qt, (pcx - qt.get_width()//2, y))
            y += fq2.get_height() + 2
    else:
        fd2 = get_font(13)
        nd  = fd2.render('아직 발견하지 못한 해파리야.', True, (72, 88, 128))
        surf.blit(nd, (pcx - nd.get_width()//2, y + 24))

    # 보유 수
    if discovered:
        fc = get_font(13)
        ct = fc.render(f'보유: {count}마리', True, (255, 238, 145))
        surf.blit(ct, (pcx - ct.get_width()//2, HEIGHT - 26))


# ── 팝 버블 / 배경 버블 ───────────────────────────────────────
class FloatText:
    def __init__(self, x, y, text, color=(255,230,100)):
        self.x = float(x); self.y = float(y)
        self.text = text; self.color = color
        self.timer = 70; self.max_t = 70
        self.vy = -0.7

    def update(self):
        self.y += self.vy; self.timer -= 1
        return self.timer > 0

    def draw(self, surf):
        a = 255 if self.timer > 15 else 0
        f = get_font(11, bold=True); t = f.render(self.text, True, self.color)
        t.set_alpha(a)
        surf.blit(t, (int(self.x)-t.get_width()//2, int(self.y)))


class PopBubble:
    def __init__(self, x, y):
        angle = random.uniform(-math.pi*0.9, -math.pi*0.1)
        speed = random.uniform(1.5, 3.5)
        self.x = float(x+random.uniform(-15,15))
        self.y = float(y+random.uniform(-5,10))
        self.vx = math.cos(angle)*speed
        self.vy = math.sin(angle)*speed
        self.r = random.randint(3,9)
        self.life = 1.0
        self.decay = random.uniform(0.018,0.032)

    def update(self):
        self.x+=self.vx; self.y+=self.vy
        self.vx*=0.97; self.life-=self.decay
        return self.life > 0

    def draw(self, surf):
        a=int(self.life*210); r=self.r
        s=pygame.Surface((r*2+4,r*2+4),pygame.SRCALPHA)
        pygame.draw.circle(s,(200,235,255,a),(r+2,r+2),r,2)
        pygame.draw.circle(s,(255,255,255,int(a*0.6)),(r+2-r//3,r+2-r//3),max(1,r//4))
        surf.blit(s,(int(self.x)-r-2,int(self.y)-r-2))


class Bubble:
    def __init__(self, y=None): self.reset(y)
    def reset(self, y=None):
        self.x=random.uniform(10,WIDTH-10)
        self.y=random.uniform(0,HEIGHT) if y is None else y
        self.r=random.randint(1,4)
        self.vy=random.uniform(0.3,1.0)
        self.wobble=random.uniform(0,math.pi*2)
        self.wobble_spd=random.uniform(0.01,0.03)
        self.alpha=random.randint(40,110)
    def update(self):
        self.wobble+=self.wobble_spd
        self.y-=self.vy; self.x+=math.sin(self.wobble)*0.4
        if self.y<-10: self.reset(HEIGHT+5)
    def draw(self, surf):
        s=pygame.Surface((self.r*2+2,self.r*2+2),pygame.SRCALPHA)
        pygame.draw.circle(s,(180,220,255,self.alpha),(self.r+1,self.r+1),self.r)
        surf.blit(s,(int(self.x)-self.r-1,int(self.y)-self.r-1))


# ── 배양서 드롭 이펙트 ────────────────────────────────────────
class CultDocDrop:
    def __init__(self, x, y):
        self.x  = float(x) + random.uniform(-12, 12)
        self.y  = float(y)
        self.vy = -1.4
        self.wobble = random.uniform(0, math.pi*2)
        self.scale  = 0.0
        self.life   = 1.0
        self.decay  = 0.006  # ~165프레임 (~2.8초)

    def update(self):
        self.y += self.vy
        self.vy  = max(self.vy * 0.97, -0.25)
        self.wobble += 0.07
        self.life   -= self.decay
        if self.scale < 1.0:
            self.scale = min(1.0, self.scale + 0.12)
        return self.life > 0

    def draw(self, surf):
        alpha = int(min(1.0, self.life * 1.6) * 225)
        sc  = self.scale
        pw  = max(4, int(30 * sc))
        ph  = max(3, int(38 * sc))
        ox  = int(self.x + math.sin(self.wobble) * 5)
        oy  = int(self.y)
        fold = max(3, pw // 4)

        s = pygame.Surface((pw+4, ph+4), pygame.SRCALPHA)
        # 종이 몸통
        pygame.draw.rect(s, (242,235,210), (2,2,pw,ph), border_radius=2)
        pygame.draw.rect(s, (188,165,118), (2,2,pw,ph), 1, border_radius=2)
        # 접힌 귀퉁이
        pygame.draw.polygon(s, (215,200,165),
                            [(pw-fold+2,2),(pw+2,fold+2),(pw+2,2)])
        pygame.draw.line(s, (175,152,110),(pw-fold+2,2),(pw+2,fold+2),1)
        # 줄
        for i in range(3):
            ly = 2 + 6 + i*6
            if ly+2 < ph+2:
                pygame.draw.line(s,(165,142,98),(4,ly),(pw-fold,ly),1)
        s.set_alpha(alpha)
        surf.blit(s,(ox-pw//2-2, oy-ph//2-2))

        # "+1 배양서" 레이블
        ft  = get_font(12, bold=True)
        tt  = ft.render('+1 배양서', True, (168, 240, 175))
        tt.set_alpha(alpha)
        surf.blit(tt,(ox-tt.get_width()//2, oy-ph//2-tt.get_height()-2))


# ── 해파리 ────────────────────────────────────────────────────
class Jellyfish:
    def __init__(self, scattered=True):
        self.bw0 = self.bh0 = self.th0 = 0   # _apply_type 에서 설정
        self._apply_type()

        total_h = self.bh0 + self.th0
        self.x = random.uniform(self.bw0//2+10, WIDTH-self.bw0//2-10)
        self.y = (random.uniform(-total_h, HEIGHT+total_h//2)
                  if scattered else HEIGHT+total_h)

        # 얼어붙은 해파리: 항상 아래서 시작 → 목표 위치로 천천히 올라옴
        if self.is_frozen:
            self.y = HEIGHT + total_h
        self.frozen_target_y = (random.uniform(total_h+50, HEIGHT-total_h-50)
                                 if self.is_frozen else 0)

        self.vy          = random.uniform(0.18,0.50)
        self.drift_phase = random.uniform(0,math.pi*2)
        self.drift_spd   = random.uniform(0.005,0.012)
        self.drift_amp   = random.uniform(0.2,0.5)
        self.pulse       = random.uniform(0,math.pi*2)
        self.pulse_spd   = random.uniform(0.025,0.05)
        self.squish_t      = -1
        self.chat_timer    = 0
        self.chat_text     = ''
        self.chat_cooldown = random.randint(180, 480)
        self.tent_phase  = random.uniform(0,math.pi*2)
        self.tent_spd    = random.uniform(0.04,0.07)
        self.burst_t     = -1
        self.elec_phase  = random.uniform(0,math.pi*2)
        self.demon_phase = random.uniform(0,math.pi*2)
        self.ice_particles = []
        # 썩은 해파리 뇌 낙하 상태
        self.brain_x  = 0.0; self.brain_y  = 0.0
        self.brain_vy = 0.0; self.brain_fp = 0.0

    def _apply_type(self):
        """스테이지(또는 DEV_MODE)에 따라 종류를 결정하고 크기 설정."""
        roll = random.random()
        self.has_hat = False; self.has_glasses = False
        self.is_electric = False; self.has_cat = False
        self.is_slime = False; self.is_frozen = False
        self.is_angel = False; self.is_ghost  = False
        self.is_hairy = False; self.is_king    = False
        self.is_zombie = False; self.is_deep  = False
        self.is_cloud  = False; self.is_angry  = False
        self.is_dapper = False; self.is_rabbit = False
        self.is_demon  = False
        self.is_cactus = False; self.is_snowman = False
        self.is_golden = False
        self.gold_particles = []
        self.is_pudding = False
        self.is_sakura  = False
        self.petal_particles = []
        self.is_twin    = False
        self.is_rainbow = False
        self.rainbow_phase = 0.0
        self.rainbow_arcs  = []
        self.is_dead   = False; self.dead_vy  = 0.0
        self.death_particles    = []
        self.death_letter_queue = []
        self.death_letter_timer = 0
        self.brain_falling = False
        self.brain_detached = False

        if not DEV_MODE:
            # 해금된 해파리 중 등급 가중치 기반 랜덤 선택
            slots   = [s for s in sorted(_unlocked_slots | _bred_slots)
                       if JELLY_GRADES.get(s,'common') != 'lock']
            weights = [GRADE_WEIGHTS.get(JELLY_GRADES.get(s,'common'),10) for s in slots]
            chosen  = random.choices(slots, weights=weights, k=1)[0]
            self.design_idx = chosen
            if   chosen == 0:  base_idx = 0
            elif chosen == 1:  base_idx = 1
            elif chosen == 2:  base_idx = random.randint(0,1); self.has_hat = True
            elif chosen == 3:  base_idx = random.randint(0,1); self.has_glasses = True
            elif chosen == 4:  base_idx = 2;  self.is_electric = True
            elif chosen == 5:  base_idx = random.randint(0,1); self.has_cat = True
            elif chosen == 6:  base_idx = 3;  self.is_slime  = True
            elif chosen == 7:  base_idx = 4;  self.is_frozen = True
            elif chosen == 8:  base_idx = 5;  self.is_angel  = True
            elif chosen == 9:  base_idx = 6;  self.is_ghost  = True
            elif chosen == 10: base_idx = 7;  self.is_hairy  = True
            elif chosen == 11: base_idx = 8;  self.is_king   = True
            elif chosen == 12: base_idx = 9;  self.is_zombie = True
            elif chosen == 13: base_idx = 10; self.is_deep   = True
            elif chosen == 14: base_idx = 11; self.is_cloud  = True
            elif chosen == 15: base_idx = 12; self.is_angry  = True
            elif chosen == 16: base_idx = 13; self.is_dapper = True
            elif chosen == 17: base_idx = 14; self.is_rabbit = True
            elif chosen == 18: base_idx = 15; self.is_demon  = True
            elif chosen == 19: base_idx = 16; self.is_cactus = True
            elif chosen == 20: base_idx = 17; self.is_snowman = True
            elif chosen == 21: base_idx = 18; self.is_golden = True
            elif chosen == 22: base_idx = 23; self.is_rainbow = True
            elif chosen == 23: base_idx = 24
            elif chosen == 26: base_idx = 21; self.is_sakura  = True
            elif chosen == 27: base_idx = 22; self.is_twin    = True
            elif chosen == 24: base_idx = 19; self.is_pudding = True
            elif chosen == 25: base_idx = 20; self.is_pudding = True
            else:              base_idx = 0
        else:  # DEV_MODE: 등급별 확률
            # ── Common 50% (5종) ────────────────────────────────────
            if   roll < 0.120: base_idx = 0;                   self.design_idx = 0   # 파랑
            elif roll < 0.240: base_idx = 1;                   self.design_idx = 1   # 분홍
            elif roll < 0.320: base_idx = 19;                  self.is_pudding = True; self.design_idx = 24 # 푸딩
            elif roll < 0.370: base_idx = 20;                  self.is_pudding = True; self.design_idx = 25 # 소다 푸딩
            elif roll < 0.420: base_idx = 21;                  self.is_sakura  = True; self.design_idx = 26 # 벚꽃
            elif roll < 0.470: base_idx = 16;                  self.is_cactus  = True; self.design_idx = 19 # 선인장
            elif roll < 0.500: base_idx = 17;                  self.is_snowman = True; self.design_idx = 20 # 눈사람
            # ── Uncommon 30% (6종 × 5%) ───────────────────────────
            elif roll < 0.550: base_idx = random.randint(0,1); self.has_cat      = True; self.design_idx = 5  # 고양이
            elif roll < 0.600: base_idx = random.randint(0,1); self.has_hat      = True; self.design_idx = 2  # 개구리모자
            elif roll < 0.650: base_idx = random.randint(0,1); self.has_glasses  = True; self.design_idx = 3  # 안경
            elif roll < 0.700: base_idx = 3;                   self.is_slime     = True; self.design_idx = 6  # 슬라임
            elif roll < 0.750: base_idx = 7;                   self.is_hairy     = True; self.design_idx = 10 # 털복숭이
            elif roll < 0.800: base_idx = 9;                   self.is_zombie    = True; self.design_idx = 12 # 썩은
            # ── Rare 10% (8종 × 1.25%) ────────────────────────────
            elif roll < 0.813: base_idx = 2;                   self.is_electric  = True; self.design_idx = 4  # 전기
            elif roll < 0.825: base_idx = 4;                   self.is_frozen    = True; self.design_idx = 7  # 얼어붙은
            elif roll < 0.838: base_idx = 5;                   self.is_angel     = True; self.design_idx = 8  # 천사
            elif roll < 0.850: base_idx = 6;                   self.is_ghost     = True; self.design_idx = 9  # 유령
            elif roll < 0.863: base_idx = 11;                  self.is_cloud     = True; self.design_idx = 14 # 구름
            elif roll < 0.875: base_idx = 12;                  self.is_angry     = True; self.design_idx = 15 # 화난
            elif roll < 0.888: base_idx = 13;                  self.is_dapper    = True; self.design_idx = 16 # 멋쟁이
            elif roll < 0.900: base_idx = 14;                  self.is_rabbit    = True; self.design_idx = 17 # 토끼
            # ── Epic 7% (2종 × 3.5%) ────────────────────────────────
            elif roll < 0.935: base_idx = 8;                   self.is_king      = True; self.design_idx = 11 # 해파리 왕
            elif roll < 0.970: base_idx = 17;                  self.is_snowman   = True; self.design_idx = 20 # 눈사람
            # ── Legendary 3% (4종 × 0.75%) ──────────────────────
            elif roll < 0.9775: base_idx = 10;                 self.is_deep      = True; self.design_idx = 13 # 심해
            elif roll < 0.985:  base_idx = 15;                 self.is_demon     = True; self.design_idx = 18 # 마왕
            elif roll < 0.9925: base_idx = 18;                 self.is_golden    = True; self.design_idx = 21 # 황금
            else:               base_idx = 23;                 self.is_rainbow   = True; self.design_idx = 22 # 무지개

        defn = JELLY_DEFS[base_idx]
        self.bell_sprite = BELL_SPRITES[base_idx]
        if self.is_rainbow:
            self.bell_sprite = RAINBOW_BELL_SPRITE
        elif self.design_idx == 23:
            self.bell_sprite = PABUN_BELL_SPRITE
        elif self.is_twin:
            self.bell_sprite = TWIN_BELL_SPRITE
        self.tc = defn['tc']; self.tb = defn['tb']
        self.BH         = len(defn['art'])
        self.body_color = defn['cmap'].get('M', self.tc)  # 눈 가리기용
        sf = random.uniform(0.88, 1.15)
        self.bw0 = max(16, int(W_PIX*defn['ps']*sf))
        self.bh0 = max(8,  int(self.BH*defn['ps']*sf))
        self.th0 = max(4,  int(10*defn['ps']*sf))
        if self.is_twin:
            self.bw0 = max(30, int(20*defn['ps']*sf))

    def hit_test(self, mx, my):
        return abs(mx-self.x)<self.bw0*0.5 and abs(my-self.y)<self.bh0*0.5

    def kill(self):
        self.is_dead = True
        self.dead_vy = 0.0
        # 글자 파티클 큐 준비
        self.death_letter_queue = list("B a d . . H u m a n . .")
        self.death_letter_timer = 0
        self.death_particles    = []

    def trigger(self):
        self.squish_t=0; self.burst_t=0
        if self.is_zombie and not self.brain_falling and not self.brain_detached:
            self.brain_falling = True
            self.brain_x  = float(self.x)
            self.brain_y  = float(self.y - self.bh0//2)
            self.brain_vy = -3.0   # 처음에 튕겨 올라갔다가 낙하
            self.brain_fp = 0.0

    def _sq(self):
        if self.is_dead:   return 0.0
        if self.squish_t<0: return 0.0
        return math.cos(self.squish_t*0.22)*0.42*math.exp(-self.squish_t*0.03)

    def _amp(self):
        if self.is_dead:   return 0.0   # 죽음 → 다리 힘없이
        if self.is_frozen: return 0.0
        base=2.2
        if self.burst_t<0: return base
        return base+4.5*math.exp(-self.burst_t*0.05)

    def _tspd(self):
        if self.burst_t<0: return self.tent_spd
        return self.tent_spd+0.18*math.exp(-self.burst_t*0.04)

    def update(self):
        self.pulse+=self.pulse_spd; self.drift_phase+=self.drift_spd

        # 죽은 해파리: 힘없이 아래로 낙하
        if self.is_dead:
            self.dead_vy = min(self.dead_vy + 0.07, 3.5)
            self.y += self.dead_vy

            # 글자 파티클 서서히 방출
            self.death_letter_timer += 1
            if self.death_letter_timer % 5 == 0 and self.death_letter_queue:
                ch = self.death_letter_queue.pop(0)
                if ch != ' ':
                    angle = random.uniform(0, math.pi * 2)
                    spd   = random.uniform(0.3, 0.9)
                    self.death_particles.append({
                        'ch': ch,
                        'x': float(self.x + random.uniform(-8, 8)),
                        'y': float(self.y + random.uniform(-6, 6)),
                        'vx': math.cos(angle) * spd,
                        'vy': math.sin(angle) * spd - 0.2,
                        'life': 1.0,
                        'decay': random.uniform(0.007, 0.013),
                    })

            # 파티클 업데이트
            next_p = []
            for p in self.death_particles:
                p['x'] += p['vx']; p['y'] += p['vy']
                p['vx'] *= 0.97;   p['life'] -= p['decay']
                if p['life'] > 0:  next_p.append(p)
            self.death_particles = next_p

            total_h = self.bh0 + self.th0
            if self.y > HEIGHT + total_h:
                self._apply_type()
                self.is_dead  = False
                self.dead_vy  = 0.0
                self.death_particles    = []
                self.death_letter_queue = []
                total_h = self.bh0 + self.th0
                self.y  = HEIGHT + total_h
                self.x  = random.uniform(self.bw0//2+10, WIDTH-self.bw0//2-10)
            return

        if self.is_frozen:
            self.x += math.sin(self.drift_phase)*0.12
            if self.y > self.frozen_target_y:
                self.y = max(self.frozen_target_y, self.y - 0.5)
            else:
                self.y -= 0.35   # 목표 도달 후 천천히 위로 → 화면 밖으로 사라짐
            # 얼음 결정 파티클 생성
            if random.random() < 0.22:
                angle = random.uniform(0, math.pi*2)
                dist  = random.uniform(self.bw0*0.28, self.bw0*0.65)
                self.ice_particles.append([
                    self.x + math.cos(angle)*dist,
                    self.y + math.sin(angle)*dist,
                    math.cos(angle)*random.uniform(0.05, 0.30),
                    random.uniform(-0.55, -0.08),
                    1.0, random.randint(3, 7)
                ])
            next_p = []
            for p in self.ice_particles:
                p[0]+=p[2]; p[1]+=p[3]; p[4]-=random.uniform(0.007,0.016)
                if p[4]>0: next_p.append(p)
            self.ice_particles = next_p
        else:
            self.tent_phase+=self._tspd()
            self.y-=self.vy+math.sin(self.pulse)*0.18
            self.x+=math.sin(self.drift_phase)*self.drift_amp
        self.x=max(self.bw0//2+5, min(WIDTH-self.bw0//2-5, self.x))
        if self.squish_t>=0:
            self.squish_t+=1
            if self.squish_t>130: self.squish_t=-1
        if self.burst_t>=0:
            self.burst_t+=1
            if self.burst_t>80: self.burst_t=-1
        if self.is_electric:
            self.elec_phase+=0.45
        if self.is_demon:
            self.demon_phase+=0.05
        # 말풍선
        if self.chat_timer > 0:
            self.chat_timer -= 1
        else:
            self.chat_cooldown -= 1
            if self.chat_cooldown <= 0:
                if random.random() < 0.10:
                    self.chat_text  = random.choice(JELLY_CHAT_MSGS)
                    self.chat_timer = 180
                    opts_c = [s for s in [SND_CHAT1, SND_CHAT2] if s]
                    if opts_c: random.choice(opts_c).play()
                self.chat_cooldown = random.randint(300, 700)
        if self.is_golden:
            self._update_gold_particles()
        if self.is_sakura:
            self._update_petal_particles()
        if self.is_rainbow:
            self.rainbow_phase += 0.025
            self._update_rainbow_arcs()
        if self.is_zombie and self.brain_falling:
            self.brain_vy += 0.12          # 중력
            self.brain_y  += self.brain_vy
            self.brain_fp += 0.14          # 좌우 흔들림 위상
            if self.brain_y > HEIGHT + 60:
                self.brain_falling  = False
                self.brain_detached = True   # 영구 소멸
        total_h=self.bh0+self.th0
        if self.y<-total_h*2:
            self._apply_type()   # 재등장 시 스테이지 기준으로 종류 재결정
            total_h=self.bh0+self.th0
            self.y=HEIGHT+total_h
            self.x=random.uniform(self.bw0//2+10,WIDTH-self.bw0//2-10)

    def draw(self, surf):
        x,y=int(self.x),int(self.y)
        sq=self._sq(); ps=1+math.sin(self.pulse)*0.04
        bw=max(8,int(self.bw0*ps*(1+sq)))
        bh=max(4,int(self.bh0*ps*(1-sq*0.5)))

        # 얼음 블록 (벨보다 먼저)
        if self.is_frozen:
            self._draw_ice(surf, x, y, bw, bh)

        # 무지개 후광 + 아크 (벨 뒤)
        if self.is_rainbow:
            self._draw_rainbow_halo(surf, x, y, bw, bh)
            self._draw_rainbow_arc(surf, x, y, bw, bh)

        # 황금 글로우 (벨 뒤 레이어)
        if self.is_golden:
            self._draw_golden_glow(surf, x, y, bw, bh)

        # 전기 이펙트
        if self.is_electric:
            self._draw_sparks(surf, x, y, bw, bh)

        # 벨 (유령/슬라임은 반투명)
        bell_s=pygame.transform.scale(self.bell_sprite,(bw,bh))
        if self.is_ghost:  bell_s.set_alpha(72)
        if self.is_slime:  bell_s.set_alpha(175)
        surf.blit(bell_s,(x-bw//2,y-bh//2))

        # 황금 시머 오버레이 (벨 위에 얇게)
        if self.is_golden:
            shimmer_a = int(18 + abs(math.sin(self.pulse * 3.5)) * 32)
            sh_s = pygame.Surface((bw, bh), pygame.SRCALPHA)
            sh_s.fill((255, 220, 40, shimmer_a))
            surf.blit(sh_s, (x - bw//2, y - bh//2))

        # 벚꽃 해파리 꽃 장식 + 꽃잎
        if self.is_sakura:
            self._draw_sakura_flower(surf, x, y - bh//2, bw)
            self._draw_petal_particles(surf)

        # 푸딩 해파리 카라멜 + 생크림 + 체리
        if self.is_pudding:
            bt = y - bh//2
            caw2 = int(bw*0.68); cah2 = max(3,int(bw*0.10))
            pygame.draw.ellipse(surf,(115,60,4),(x-caw2//2,bt-cah2//2,caw2,cah2))
            pygame.draw.ellipse(surf,(145,80,8),(x-caw2//2+2,bt-cah2//2,caw2-4,max(1,cah2-1)))
            cr2 = max(5,bw//9); cy2 = bt - cah2//2 - cr2 + 2
            for cxo,cyo in [(0,-cr2//3),(-cr2//2,0),(cr2//2,0),(0,0)]:
                pygame.draw.circle(surf,(245,245,245),(x+cxo,cy2+cyo),cr2)
            pygame.draw.circle(surf,(255,255,255),(x-cr2//4,cy2-cr2//4),max(2,cr2//3))
            chr_r2 = max(4,bw//10); chr_y2 = cy2-cr2+2
            pygame.draw.circle(surf,(148,8,8),(x,chr_y2),chr_r2)
            pygame.draw.circle(surf,(195,18,18),(x,chr_y2),chr_r2-1)
            pygame.draw.circle(surf,(235,55,55),(x-chr_r2//3,chr_y2-chr_r2//3),max(1,chr_r2//3))
            pygame.draw.line(surf,(188,18,18),(x,chr_y2-chr_r2),(x+chr_r2//2,chr_y2-chr_r2-max(5,bw//8)),1)

        # 황금 해파리 돼지 귀
        if self.is_golden:
            pew = int(bw * 0.50); peh = max(1, int(pew // 4))
            pes = pygame.transform.scale(PIG_EARS_BASE, (pew, peh))
            surf.blit(pes, (x - pew//2, y - bh//2 - peh + peh//4))

        # 황금 해파리 돼지코
        if self.is_golden:
            pnw = max(5, bw * 5 // 16)
            pnh = max(3, pnw * 3 // 5)
            pns = pygame.transform.scale(PIG_NOSE_BASE, (pnw, pnh))
            surf.blit(pns, (x - pnw//2, y + bh//8 + bh//10))

        # 눈사람: 작은 머리를 위에 올림
        if self.is_snowman:
            hw = int(bw*0.58); hh = int(bh*0.58)
            hs = pygame.transform.scale(self.bell_sprite,(hw,hh))
            hy = y-bh//2-hh+hh//3
            surf.blit(hs,(x-hw//2, hy))
            # 작은 머리에 눈 + 당근코
            ey2 = hy+hh//2+hh//8
            er2 = max(1,hw//16)
            pygame.draw.rect(surf,(12,12,32),(x-hw//8, ey2, er2+1, er2+1))
            pygame.draw.rect(surf,(12,12,32),(x+hw//16,ey2, er2+1, er2+1))
            # 당근코 (주황 픽셀)
            nw2 = max(3, hw//7); nh2 = max(2, hw//12)
            pygame.draw.rect(surf,(242,128,12),
                             (x-nw2//2, ey2+er2+2, nw2, nh2))

        # 선인장 가시 (벨 위에)
        if self.is_cactus:
            self._draw_cactus_spikes(surf, x, y, bw, bh)

        # 털 (벨 위에 그려서 온몸이 털처럼 보임)
        if self.is_hairy:
            self._draw_fur(surf, x, y, bw, bh)
            # 눈을 털 위 레이어로 다시 그림 (픽셀 아트 스타일 사각형)
            px_w = max(2, bw // 16)
            px_h = max(2, bh // 8)
            ey2  = y + bh // 8
            pygame.draw.rect(surf, (12,12,32), (x - bw//8,  ey2, px_w, px_h))
            pygame.draw.rect(surf, (12,12,32), (x + bw//16, ey2, px_w, px_h))

        # 개구리 모자
        if self.has_hat:
            hw=int(bw*0.82); hh=max(1,int(hw*5//10))
            hs=pygame.transform.scale(FROG_HAT_BASE,(hw,hh))
            surf.blit(hs,(x-hw//2, y-bh//2-hh+hh//3))

        # 안경
        if self.has_glasses:
            gw=int(bw*0.84); gh=max(1,int(gw*3//10))
            gs=pygame.transform.scale(GLASSES_BASE,(gw,gh))
            surf.blit(gs,(x-gw//2, y+bh//8-gh//3))

        # 고양이 귀
        if self.has_cat:
            cw2=int(bw*0.82); ch2=max(1,int(cw2*4//10))
            cs=pygame.transform.scale(CAT_EARS_BASE,(cw2,ch2))
            surf.blit(cs,(x-cw2//2, y-bh//2-ch2+ch2//4))

        # 가짜 해파리 얼굴 이미지 (안경+코+수염)

        # 왕관
        if self.is_king:
            kw=int(bw*0.65); kh=max(1,int(kw*3//11))
            ks=pygame.transform.scale(CROWN_BASE,(kw,kh))
            surf.blit(ks,(x-kw//2, y-bh//2-kh+kh//4))

        # 수염 (왕) - 눈 아래로 충분히 내림
        if self.is_king:
            bdw=int(bw*0.60); bdh=max(1,int(bdw*5//9))
            bds=pygame.transform.scale(BEARD_BASE,(bdw,bdh))
            surf.blit(bds,(x-bdw//2, y+bh*2//5))

        # 화난 해파리 팔 (벨 앞에 그려 어깨가 자연스럽게 겹침)
        if self.is_angry:
            self._draw_angry_arms(surf, x, y, bw, bh)

        # 심해 해파리 발광 낚싯대
        if self.is_deep:
            self._draw_lantern(surf, x, y - bh//2, bw)

        # 좀비 뇌 (뇌가 분리되지 않았을 때만 머리 위에 표시)
        if self.is_zombie and not self.brain_detached:
            if not self.brain_falling:
                self._draw_brain_at(surf, x, y-bh//2, bw)
            else:
                wx = int(math.sin(self.brain_fp)*7)
                self._draw_brain_at(surf, int(self.brain_x)+wx, int(self.brain_y), self.bw0)

        # 마왕 여우불 이펙트 (벨 뒤 레이어)
        if self.is_demon:
            self._draw_foxfire(surf, x, y, bw, bh)


        # 토끼 귀
        if self.is_rabbit:
            rew = int(bw*0.78); reh = max(1, int(rew*6//8))
            res = pygame.transform.scale(RABBIT_EARS_BASE, (rew, reh))
            surf.blit(res, (x-rew//2, y-bh//2-reh+reh//4))

        # 마왕 발광 눈 (벨 위에 덮어씀)
        if self.is_demon:
            pulse2 = 0.65 + abs(math.sin(self.demon_phase*3.0))*0.35
            ey3    = y + bh//8
            er3    = max(2, bw//16)
            ecol   = (int(195+pulse2*60), int(10+pulse2*12), int(8+pulse2*8))
            for ex3 in (x-bw//8, x+bw//16):
                for gr in range(er3*3,0,-2):
                    ga3=int(22*pulse2*gr//(er3*3))
                    ge=pygame.Surface((gr*2+2,gr*2+2),pygame.SRCALPHA)
                    pygame.draw.circle(ge,(255,12,12,ga3),(gr+1,gr+1),gr)
                    surf.blit(ge,(ex3-gr-1,ey3-gr-1))
                pygame.draw.circle(surf,ecol,(ex3,ey3),er3)

        # 멋쟁이 해파리 탑햇
        if self.is_dapper:
            hw = int(bw*0.75); hh = max(1, int(hw*6//12))
            hs = pygame.transform.scale(TOP_HAT_BASE, (hw, hh))
            surf.blit(hs, (x-hw//2, y-bh//2-hh+hh//5))


        # 화난 해파리 눈썹 (벨 위에 그림)
        if self.is_angry:
            self._draw_angry_eyebrows(surf, x, y, bw, bh)

        # 천사 링 (벨 위, 살짝 떠있음)
        if self.is_angel:
            hlw=int(bw*0.80); hlh=max(1,int(hlw*3//11))
            hls=pygame.transform.scale(HALO_BASE,(hlw,hlh))
            halo_y = y-bh//2-hlh-3+int(math.sin(self.pulse)*3)
            surf.blit(hls,(x-hlw//2, halo_y))

        # 촉수 — 얼어붙은만 기존 픽셀 방식, 나머지는 드립 스타일
        if self.is_frozen:
            self._draw_tent(surf, x, y+bh//2, bw)
        elif self.is_ghost:
            self._draw_slime_drips(surf, x, y+bh//2, bw, alpha_mult=0.38)
        elif self.is_rainbow:
            self._draw_rainbow_drips(surf, x, y+bh//2, bw)
        elif self.is_twin:
            # 각 머리 아래 2개씩, 총 4개 촉수
            for dx_t in (-0.42, -0.18, 0.18, 0.42):
                bx_t = x + int(dx_t*bw)
                amp_t = self._amp(); tc_t = self.tc
                base_t = int(bw*0.10); wave_t = int(math.sin(self.tent_phase*1.8)*bw*0.04)
                length_t = max(5, base_t+wave_t+int(amp_t*2))
                sway_t   = int(math.sin(self.tent_phase)*(1+amp_t*0.7))
                s_t = pygame.Surface((14,length_t+10),pygame.SRCALPHA)
                pygame.draw.line(s_t,(*tc_t,195),(7,0),(7+sway_t,length_t),3)
                pygame.draw.circle(s_t,(*tc_t,175),(7+sway_t,length_t),max(2,length_t//6))
                surf.blit(s_t,(bx_t-7,y+bh//2))
        else:
            self._draw_slime_drips(surf, x, y+bh//2, bw)

        # 황금 동전/골드바 파티클
        if self.is_golden:
            self._draw_gold_particles(surf)

        # Bad Human 글자 파티클
        if self.is_dead:
            fn_d = get_font(15, bold=True)
            for p in self.death_particles:
                t = fn_d.render(p['ch'], True, (220, 28, 28))
                t.set_alpha(int(p['life'] * 235))
                surf.blit(t, (int(p['x'])-t.get_width()//2,
                              int(p['y'])-t.get_height()//2))

        # 말풍선
        if self.chat_timer > 0 and not self.is_dead:
            t_c = self.chat_timer / 180.0
            if t_c > 0.85: alpha_c = int((1.0-t_c)/0.15 * 245)
            elif t_c < 0.20: alpha_c = int(t_c/0.20 * 245)
            else: alpha_c = 245
            fc = get_font(11, bold=True)
            tw_c = fc.render(self.chat_text, True, (30,30,50))
            pad = 8
            bw_c = tw_c.get_width() + pad*2
            bh_c = tw_c.get_height() + pad + 2
            bx_c = max(2, min(WIDTH-bw_c-2, x - bw_c//2))
            by_c = y - bh//2 - bh_c - 10
            if by_c < 5: by_c = y + bh//2 + 10
            # 말풍선 배경
            bs_c = pygame.Surface((bw_c, bh_c+6), pygame.SRCALPHA)
            pygame.draw.rect(bs_c, (255,255,255,alpha_c), (0,0,bw_c,bh_c), border_radius=8)
            pygame.draw.rect(bs_c, (180,210,240,alpha_c), (0,0,bw_c,bh_c), 1, border_radius=8)
            # 꼬리 삼각형
            tip_x = min(max(bw_c//2, 8), bw_c-8)
            pygame.draw.polygon(bs_c, (255,255,255,alpha_c),
                                [(tip_x-5,bh_c),(tip_x+5,bh_c),(tip_x,bh_c+6)])
            surf.blit(bs_c,(bx_c, by_c))
            tw_c.set_alpha(alpha_c)
            surf.blit(tw_c,(bx_c+pad, by_c+pad//2))

        # × 눈 (죽었을 때)
        if self.is_dead:
            ey2   = y + bh // 8
            xs    = max(3, bw // 12)
            cover = max(2, bw // 18)
            for ex2 in (x - bw//7, x + bw//7):
                pygame.draw.circle(surf, self.body_color, (ex2, ey2), cover + 2)
                pygame.draw.line(surf, (22,15,15),
                                 (ex2-xs, ey2-xs), (ex2+xs, ey2+xs), 4)
                pygame.draw.line(surf, (22,15,15),
                                 (ex2+xs, ey2-xs), (ex2-xs, ey2+xs), 4)

    def _draw_tent(self, surf, cx, top_y, bw):
        TH=10; amp=self._amp()
        dot=max(2,bw//W_PIX); th=self.th0
        t_surf=pygame.Surface((bw,th),pygame.SRCALPHA)
        for i,bx_pix in enumerate(self.tb):
            bx=int(bx_pix*bw/W_PIX)
            for row in range(TH):
                py=int(row*th/TH); ph=max(dot,int(th/TH))
                wave=math.sin(self.tent_phase+row*0.75+i*1.6)*amp
                px=int(bx+wave*bw/W_PIX)
                px=max(0,min(bw-dot,px))
                alpha=max(80,220-row*15)
                t_surf.fill((*self.tc,alpha),(px,py,dot,ph))
        surf.blit(t_surf,(cx-bw//2,top_y))

    def _draw_brain_at(self, surf, cx, cy, bw):
        """cx, cy = 머리 꼭대기 중심에 뇌 그리기."""
        brw = int(bw * 0.30)          # 크기 대폭 축소
        brh = max(1, int(brw * 7 // 10))   # 7행/10열 비율 (더 둥글게)
        bs  = pygame.transform.scale(BRAIN_BASE, (brw, brh))
        surf.blit(bs, (cx - brw//2, cy - brh + brh//4))

    def _draw_angry_eyebrows(self, surf, cx, cy, bw, bh):
        """화난 눈썹: 안쪽이 내려온 \ / 형태."""
        col   = (14, 8, 8)
        thick = max(2, bw // 11)
        eye_y = cy + bh // 8
        eby   = eye_y - bh // 7   # 눈썹 y (눈 위)
        ox    = bw // 5            # 눈썹 가로 폭

        # 왼쪽 눈썹 \  (바깥=높음, 안=낮음)
        pygame.draw.line(surf, col,
                         (cx - bw//8 - ox//2, eby - bh//18),
                         (cx - bw//8 + ox//2, eby + bh//18), thick)
        # 오른쪽 눈썹 /  (안=낮음, 바깥=높음)
        pygame.draw.line(surf, col,
                         (cx + bw//8 - ox//2, eby + bh//18),
                         (cx + bw//8 + ox//2, eby - bh//18), thick)

    def _draw_angry_arms(self, surf, cx, cy, bw, bh):
        """화난 해파리 팔: 허리에 팔을 올린 모양 (arms akimbo)."""
        col   = self.tc
        thick = max(2, bw // 14)   # 다리 두께와 비슷하게
        sway  = int(math.sin(self.pulse * 1.2) * 2)

        for side in (-1, 1):
            # 어깨 (벨 옆 하부)
            shx = cx + side * (bw // 2 - 2)
            shy = cy + bh // 5

            # 팔꿈치 (바깥쪽 + 아래로)
            elx = cx + side * int(bw * 0.72)
            ely = shy + int(bh * 0.42) + sway

            # 손 (다시 몸쪽으로 = 허리 위치)
            hax = cx + side * int(bw * 0.18)
            hay = ely + int(bh * 0.10)

            pygame.draw.line(surf, col, (shx, shy), (elx, ely), thick)
            pygame.draw.line(surf, col, (elx, ely), (hax, hay), thick)

    def _draw_lantern(self, surf, cx, bell_top_y, bw):
        """심해 아귀 스타일 발광 낚싯대."""
        stalk_h = int(bw * 0.52)
        sway    = int(math.sin(self.pulse * 1.3) * bw * 0.10)

        # 낚싯대 2단 꺾임
        pt0 = (cx, bell_top_y)
        pt1 = (cx + sway // 2, bell_top_y - stalk_h // 2)
        pt2 = (cx + sway,      bell_top_y - stalk_h)

        sc = (75, 92, 108)
        pygame.draw.line(surf, sc, pt0, pt1, 2)
        pygame.draw.line(surf, sc, pt1, pt2, 2)

        ox, oy = pt2
        # 발광 펄스
        pg = 0.55 + abs(math.sin(self.pulse * 2.5)) * 0.45
        orb_r   = max(3, int(bw * 0.062))
        glow_c  = (48, 218, 178)

        # glow 링 (SRCALPHA 서피스)
        for ring in range(5, 0, -1):
            gr = orb_r + int(ring * orb_r * 0.75 * pg)
            ga = int(22 * pg * ring / 5)
            gs = pygame.Surface((gr*2+2, gr*2+2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*glow_c, ga), (gr+1, gr+1), gr)
            surf.blit(gs, (ox-gr-1, oy-gr-1))

        # orb 본체
        pygame.draw.circle(surf, glow_c, (ox, oy), orb_r)
        pygame.draw.circle(surf, (215, 255, 242), (ox, oy), max(1, orb_r-1))
        # 하이라이트
        pygame.draw.circle(surf, (255, 255, 255),
                           (ox - orb_r//3, oy - orb_r//3), max(1, orb_r//3))

    def _draw_foxfire(self, surf, cx, cy, bw, bh):
        """붉은 여우불: 주변을 떠다니는 불꽃 구체."""
        t = self.demon_phase
        n = 5
        for i in range(n):
            # 리사주 궤도 (불규칙한 떠다님)
            a = t * 0.9 + i * (math.pi * 2 / n)
            rx = bw * (0.68 + math.sin(t * 0.35 + i * 1.8) * 0.22)
            ry = bh * (0.58 + math.cos(t * 0.42 + i * 2.1) * 0.20)
            ox = cx + int(math.cos(a) * rx)
            oy = cy + int(math.sin(a) * ry)

            # 깜빡임
            flick = 0.55 + abs(math.sin(t * 7.1 + i * 2.9)) * 0.45
            orb_r = max(2, int((2 + abs(math.sin(t * 4.3 + i)) * 3) * flick))

            r = int(175 + flick * 80)
            g = int(8  + flick * 28)

            # 글로우 링
            for gr in range(orb_r * 4, 0, -2):
                ga = int(18 * flick * gr // (orb_r * 4))
                gs = pygame.Surface((gr*2+2, gr*2+2), pygame.SRCALPHA)
                pygame.draw.circle(gs, (r, g, 5, ga), (gr+1, gr+1), gr)
                surf.blit(gs, (ox-gr-1, oy-gr-1))

            # 불꽃 꼬리 (이전 위치 3곳)
            for j in range(1, 4):
                ta2 = a - j * 0.18
                tx = cx + int(math.cos(ta2) * rx)
                ty = cy + int(math.sin(ta2) * ry)
                tr = max(1, orb_r - j)
                ta3 = int(flick * 150 * (4-j) // 3)
                ts = pygame.Surface((tr*2+2, tr*2+2), pygame.SRCALPHA)
                pygame.draw.circle(ts, (r, g, 5, ta3), (tr+1, tr+1), tr)
                surf.blit(ts, (tx-tr-1, ty-tr-1))

            # 핵심 구체
            pygame.draw.circle(surf, (r, g, 5), (ox, oy), orb_r)
            pygame.draw.circle(surf, (255, min(255, g+60), 25),
                               (ox, oy), max(1, orb_r-1))

    def _draw_spots(self, surf, cx, cy, bw, bh):
        """얼룩소 스타일 둥근 스팟."""
        col = (125, 58, 22)
        # 벨 안에 분포된 고정 스팟 위치 (rel_x, rel_y, rel_r)
        spots = [
            (-0.18, -0.22, 0.11), ( 0.12, -0.18, 0.09),
            (-0.05, -0.08, 0.08), ( 0.22,  0.00, 0.08),
            (-0.22,  0.08, 0.09), ( 0.08,  0.14, 0.10),
            (-0.10,  0.20, 0.07), ( 0.20,  0.16, 0.08),
            ( 0.00, -0.28, 0.07), (-0.28,  0.00, 0.07),
        ]
        for rx, ry, rr in spots:
            sx = cx + int(rx * bw)
            sy = cy + int(ry * bh)
            r  = max(2, int(rr * bw))
            pygame.draw.circle(surf, col, (sx, sy), r)

    def _draw_cactus_spikes(self, surf, cx, cy, bw, bh):
        """선인장 가시 전체 덮기 (연노랑, 360°)."""
        spine_col = (245, 238, 145)
        n    = 18
        slen = max(3, bw // 9)
        # 벨 픽셀 실제 가장자리: art에서 cols 2-13 / 16 → 수평 반지름 ≈ bw*0.375
        rx   = bw * 0.375
        ry   = bh * 0.48
        for i in range(n):
            ang = -math.pi + (i / n) * math.pi * 2
            sx  = int(cx + math.cos(ang) * rx)
            sy  = int(cy + math.sin(ang) * ry)
            ex  = int(sx + math.cos(ang) * slen)
            ey  = int(sy + math.sin(ang) * slen)
            pygame.draw.line(surf, spine_col, (sx, sy), (ex, ey), 2)

    def _draw_snowman_bell(self, surf, cx, cy, bw, bh):
        """눈사람 형태: 큰 몸통 + 작은 머리 두 원."""
        sq   = self._sq()
        cm   = (235, 242, 252)
        cs   = (210, 222, 240)
        cdk  = (158, 172, 198)
        # 몸통 (아래 큰 원)
        rb   = max(6, int(bw * 0.38 * (1 + sq * 0.08)))
        boty = cy + bh // 5
        pygame.draw.circle(surf, cdk, (cx, boty), rb + 2)
        pygame.draw.circle(surf, cs,  (cx, boty), rb + 1)
        pygame.draw.circle(surf, cm,  (cx, boty), rb)
        # 몸통 단추 3개
        for k, dy in enumerate([-rb//3, 0, rb//3]):
            pygame.draw.circle(surf, (40,38,38), (cx, boty+dy), max(1, rb//9))
        # 머리 (위 작은 원)
        rh   = max(4, int(bw * 0.24 * (1 - sq * 0.08)))
        topy = cy - bh // 4
        pygame.draw.circle(surf, cdk, (cx, topy), rh + 2)
        pygame.draw.circle(surf, cs,  (cx, topy), rh + 1)
        pygame.draw.circle(surf, cm,  (cx, topy), rh)
        # 눈
        ey2 = topy - rh // 4
        er2 = max(1, rh // 6)
        pygame.draw.circle(surf, (22,18,18), (cx - rh//3, ey2), er2)
        pygame.draw.circle(surf, (22,18,18), (cx + rh//3, ey2), er2)

    def _draw_fur(self, surf, cx, cy, bw, bh):
        col = self.tc
        # 2개 레이어: 안쪽 + 중간 (범위 축소)
        layers = [
            (0.08, 0.24, 145),   # 안쪽 레이어
            (0.24, 0.40, 182),   # 중간 레이어
        ]
        n = 12
        for li, (r0, r1, base_a) in enumerate(layers):
            length = int(bw * (r1 - r0) + 2)
            for i in range(n):
                t = i / (n - 1)
                # 전체 360° 커버
                ang = -math.pi + t * math.pi * 2
                sx = int(cx + math.cos(ang) * bw * r0)
                sy = int(cy + math.sin(ang) * bh * r0)
                sway = math.sin(self.pulse * 1.6 + i * 0.62 + li * 2.1) * 0.15
                hang = ang + sway
                for off, a_mult in [(0, 1.0), (0.20, 0.72)]:
                    ex = int(sx + math.cos(hang + off) * length)
                    ey = int(sy + math.sin(hang + off) * length)
                    pygame.draw.line(surf, (*col, int(base_a*a_mult)),
                                     (sx, sy), (ex, ey), 2)

    def _draw_slime_drips(self, surf, cx, top_y, bw, alpha_mult=1.0):
        col = self.tc
        amp = self._amp()
        for i, dx_frac in enumerate([-0.28, -0.10, 0.10, 0.28]):
            bx = cx + int(dx_frac * bw)
            base = int(bw * 0.20)
            wave = int(math.sin(self.tent_phase * 1.8 + i * 1.3) * bw * 0.06)
            length = max(5, base + wave + int(amp * 2))
            sway = int(math.sin(self.tent_phase + i) * (1 + amp * 0.7))
            s = pygame.Surface((14, length + 10), pygame.SRCALPHA)
            la = int(195 * alpha_mult)
            ba = int(175 * alpha_mult)
            pygame.draw.line(s, (*col, la), (7, 0), (7 + sway, length), 3)
            blob_r = max(2, length // 6)
            pygame.draw.circle(s, (*col, ba), (7 + sway, length), blob_r)
            surf.blit(s, (bx - 7, top_y))

    def _draw_ice(self, surf, cx, cy, bw, bh):
        for p in self.ice_particles:
            px, py, vx, vy, life, sz = p
            a = int(life * 215)
            s = sz; x2, y2 = int(px), int(py)
            col = (210, 240, 255, a)
            ss = pygame.Surface((s*2+2, s*2+2), pygame.SRCALPHA)
            c = s+1
            # 눈결정 모양 (+ × 합쳐서 ❄ 형태)
            pygame.draw.line(ss, col, (c-s, c),    (c+s, c),    1)
            pygame.draw.line(ss, col, (c, c-s),    (c, c+s),    1)
            pygame.draw.line(ss, col, (c-s//2, c-s//2), (c+s//2, c+s//2), 1)
            pygame.draw.line(ss, col, (c+s//2, c-s//2), (c-s//2, c+s//2), 1)
            surf.blit(ss, (x2-s-1, y2-s-1))

    def _draw_sparks(self, surf, cx, cy, bw, bh):
        """도트 캐주얼 파지직 전기 — 픽셀 블록 스파크."""
        t  = self.elec_phase
        ps = max(2, bw // 12)   # 픽셀 아트 한 칸 크기

        for i in range(10):
            # 불규칙 위치 (몸 안팎)
            r  = 0.18 + abs(math.sin(t*2.3 + i*1.8)) * 0.52
            sx = cx + int(math.sin(t*7.1 + i*2.5) * bw * r)
            sy = cy + int(math.sin(t*6.3 + i*1.9) * bh * r * 0.75)

            # 빠른 깜빡임
            vis = abs(math.sin(t*11.3 + i*3.1))
            if vis < 0.50:
                continue

            bright = 205 + int(vis * 50)
            col    = (bright, int(bright * 0.90), 8)
            seg    = 1 + int(abs(math.sin(t*5.7 + i*1.3)) * 2)  # 1~3 칸

            # 4방향 도트 선분 (수평/수직/대각선 ↗/↘)
            orient = int(abs(t*3.1 + i*2.7)) % 4
            if orient == 0:   # 수평 ─
                pygame.draw.rect(surf, col, (sx, sy, seg*ps, ps))
            elif orient == 1:  # 수직 │
                pygame.draw.rect(surf, col, (sx, sy, ps, seg*ps))
            elif orient == 2:  # 대각선 ↗
                for k in range(seg):
                    pygame.draw.rect(surf, col, (sx+k*ps, sy-k*ps, ps, ps))
            else:              # 대각선 ↘
                for k in range(seg):
                    pygame.draw.rect(surf, col, (sx+k*ps, sy+k*ps, ps, ps))

            # 중심 밝은 도트
            pygame.draw.rect(surf, (255, 255, 215), (sx, sy, ps, ps))

    def _draw_golden_glow(self, surf, cx, cy, bw, bh):
        """황금 해파리: 타원 펄스 글로우 + 공전 별 파티클."""
        t  = self.pulse
        pg = 0.55 + abs(math.sin(t * 2.2)) * 0.45
        gc = (255, 198, 28)

        # 타원형 글로우 5겹
        for ring in range(5, 0, -1):
            grw = int(bw * (1.0 + ring * 0.18 * pg))
            grh = int(bh * (1.0 + ring * 0.14 * pg))
            ga  = int(25 * pg * ring // 5)
            gs  = pygame.Surface((grw+4, grh+4), pygame.SRCALPHA)
            gs.fill((0,0,0,0))
            pygame.draw.ellipse(gs, (*gc, ga), (2, 2, grw, grh))
            surf.blit(gs, (cx - grw//2 - 2, cy - grh//2 - 2))

    def _draw_rainbow_halo(self, surf, cx, cy, bw, bh):
        """무지개 색상이 돌아가는 타원 후광."""
        t  = self.rainbow_phase
        pg = 0.55 + abs(math.sin(t * 2.0)) * 0.45
        n  = len(RAINBOW_HUES)
        for i in range(5):
            hue = RAINBOW_HUES[(i + int(t * 2)) % n]
            grw = int(bw * (1.0 + (i+1) * 0.15 * pg))
            grh = int(bh * (1.0 + (i+1) * 0.12 * pg))
            ga  = int(24 * pg * (5 - i) // 5)
            gs  = pygame.Surface((grw + 4, grh + 4), pygame.SRCALPHA)
            gs.fill((0,0,0,0))
            pygame.draw.ellipse(gs, (*hue, ga), (2, 2, grw, grh))
            surf.blit(gs, (cx - grw//2 - 2, cy - grh//2 - 2))

    def _update_rainbow_arcs(self):
        if len(self.rainbow_arcs) < 3 and random.random() < 0.030:
            angle = random.uniform(0, math.pi * 2)
            dist  = random.uniform(self.bw0 * 0.05, self.bw0 * 0.55)
            self.rainbow_arcs.append({
                'x':       self.x + math.cos(angle) * dist,
                'y':       self.y + math.sin(angle) * dist * 0.55,
                'age':     0,
                'max_age': random.randint(100, 160),
                'size':    random.uniform(0.72, 1.05),
            })
        next_a = []
        for a in self.rainbow_arcs:
            a['age'] += 1
            if a['age'] < a['max_age']:
                next_a.append(a)
        self.rainbow_arcs = next_a

    def _draw_rainbow_arc(self, surf, cx, cy, bw, bh):
        for arc in self.rainbow_arcs:
            t = arc['age'] / arc['max_age']
            if t < 0.18:
                alpha_t = t / 0.18
            elif t > 0.72:
                alpha_t = (1.0 - t) / 0.28
            else:
                alpha_t = 1.0
            base_alpha = int(alpha_t * 127)
            if base_alpha < 3:
                continue

            ax, ay   = int(arc['x']), int(arc['y'])
            rw_max   = int(bw * 0.40 * arc['size'])

            for i, hue in enumerate(RAINBOW_HUES[:7]):
                rw = rw_max - i * max(1, int(bw * 0.035))
                rh = max(3, int(rw * 0.52))
                if rw < 5:
                    continue
                alpha = int(base_alpha * (1.0 - i * 0.04))
                gs = pygame.Surface((rw*2 + 4, rh*2 + 4), pygame.SRCALPHA)
                pygame.draw.arc(gs, (*hue, alpha),
                                (2, 2, rw*2, rh*2),
                                0, math.pi, 2)
                surf.blit(gs, (ax - rw - 2, ay - rh - 2))

    def _draw_rainbow_sparkles(self, surf, cx, cy, bw, bh):
        t = self.rainbow_phase
        n = 8
        for i in range(n):
            a  = t * 0.8 + i * (math.pi * 2 / n)
            hue = RAINBOW_HUES[i % len(RAINBOW_HUES)]
            rx = bw * (0.88 + math.sin(t * 0.5 + i) * 0.12)
            ry = bh * (0.75 + math.cos(t * 0.4 + i) * 0.10)
            ox = cx + int(math.cos(a) * rx)
            oy = cy + int(math.sin(a) * ry)
            sp = abs(math.sin(t * 4.5 + i * 1.3))
            if sp > 0.25:
                ss = max(1, int(sp * 5))
                pygame.draw.line(surf, hue, (ox-ss, oy), (ox+ss, oy), 1)
                pygame.draw.line(surf, hue, (ox, oy-ss), (ox, oy+ss), 1)
                pygame.draw.circle(surf, (255,255,255), (ox,oy), max(1,ss//3))

    def _draw_rainbow_drips(self, surf, cx, top_y, bw):
        amp = self._amp()
        for i, dx_frac in enumerate([-0.28, -0.10, 0.10, 0.28]):
            bx  = cx + int(dx_frac * bw)
            col = RAINBOW_HUES[(i + int(self.rainbow_phase * 2)) % len(RAINBOW_HUES)]
            base   = int(bw * 0.20)
            wave   = int(math.sin(self.tent_phase * 1.8 + i * 1.3) * bw * 0.06)
            length = max(5, base + wave + int(amp * 2))
            sway   = int(math.sin(self.tent_phase + i) * (1 + amp * 0.7))
            s = pygame.Surface((14, length + 10), pygame.SRCALPHA)
            pygame.draw.line(s, (*col, 210), (7, 0), (7 + sway, length), 3)
            blob_r = max(2, length // 6)
            pygame.draw.circle(s, (*col, 190), (7 + sway, length), blob_r)
            surf.blit(s, (bx - 7, top_y))

    def _update_petal_particles(self):
        if len(self.petal_particles) < 8 and random.random() < 0.08:
            angle = random.uniform(0, math.pi*2)
            dist  = random.uniform(self.bw0*0.2, self.bw0*1.1)
            self.petal_particles.append({
                'x':   self.x + math.cos(angle)*dist,
                'y':   self.y + math.sin(angle)*dist*0.6,
                'vx':  random.uniform(-0.35, 0.35),
                'vy':  random.uniform(0.15, 0.5),
                'rot': random.uniform(0, math.pi*2),
                'rot_spd': random.uniform(-0.04, 0.04),
                'age': 0,
                'max_age': random.randint(90, 150),
                'size': random.randint(4, 7),
            })
        t_p = pygame.time.get_ticks() * 0.001
        next_p = []
        for p in self.petal_particles:
            p['x']   += p['vx'] + math.sin(t_p*1.2+p['rot'])*0.28
            p['y']   += p['vy']
            p['rot'] += p['rot_spd']
            p['age'] += 1
            if p['age'] < p['max_age']:
                next_p.append(p)
        self.petal_particles = next_p

    def _draw_petal_particles(self, surf):
        for p in self.petal_particles:
            t2 = p['age'] / p['max_age']
            if t2 < 0.15: alpha = int(t2/0.15*210)
            elif t2 > 0.75: alpha = int((1-t2)/0.25*210)
            else: alpha = 210
            sz = p['size']
            ps = pygame.Surface((sz*2+2, sz+2), pygame.SRCALPHA)
            pygame.draw.ellipse(ps, (255,195,210,alpha), (1,1,sz*2,sz))
            pygame.draw.ellipse(ps, (255,220,232,alpha//2), (2,1,sz*2-2,max(1,sz-2)))
            rs = pygame.transform.rotate(ps, math.degrees(p['rot']))
            rw, rh = rs.get_size()
            surf.blit(rs, (int(p['x'])-rw//2, int(p['y'])-rh//2))

    def _draw_sakura_flower(self, surf, cx, bell_top_y, bw):
        fr = max(4, bw//10)
        cy_f = bell_top_y - fr - 1
        for k in range(5):
            a = k*(math.pi*2/5) - math.pi/2
            px2 = cx + int(math.cos(a)*fr*1.4)
            py2 = cy_f + int(math.sin(a)*fr*1.0)
            pygame.draw.circle(surf, (255,185,202), (px2, py2), fr)
            pygame.draw.circle(surf, (255,215,228), (px2, py2), max(1,fr-1))
        pygame.draw.circle(surf, (255,232,120), (cx, cy_f), max(2,fr//2))
        pygame.draw.circle(surf, (255,248,195), (cx, cy_f), max(1,fr//3))

    def _update_gold_particles(self):
        if random.random() < 0.10:
            angle = random.uniform(0, math.pi * 2)
            dist  = random.uniform(self.bw0 * 0.25, self.bw0 * 0.85)
            self.gold_particles.append({
                'type': 'coin',
                'x':  self.x + math.cos(angle) * dist,
                'y':  self.y + math.sin(angle) * dist * 0.65,
                'vx': random.uniform(-0.25, 0.25),
                'vy': random.uniform(-0.7, -0.2),
                'age': 0,
                'max_age': random.randint(40, 65),
                'size': random.uniform(0.7, 1.2),
            })
        next_p = []
        for p in self.gold_particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['age'] += 1
            if p['age'] < p['max_age']:
                next_p.append(p)
        self.gold_particles = next_p

    def _draw_gold_particles(self, surf):
        for p in self.gold_particles:
            t = p['age'] / p['max_age']
            # 뿅 팝인(0~15%), 유지(15~70%), 페이드아웃(70~100%)
            if t < 0.15:
                alpha = int((t / 0.15) * 225)
                sf    = t / 0.15
            elif t > 0.70:
                alpha = int(((1.0 - t) / 0.30) * 225)
                sf    = 1.0
            else:
                alpha = 225
                sf    = 1.0
            if alpha <= 0:
                continue
            x, y = int(p['x']), int(p['y'])
            sz   = p['size'] * sf

            if p['type'] == 'coin':
                r  = max(2, int(6 * sz))
                s  = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
                cx2, cy2 = r+2, r+2
                pygame.draw.circle(s, (155, 108, 5,  alpha), (cx2, cy2), r)
                pygame.draw.circle(s, (238, 190, 28, alpha), (cx2, cy2), max(1, r-1))
                pygame.draw.circle(s, (255, 235, 115, alpha), (cx2-r//3, cy2-r//3), max(1, r//3))
                surf.blit(s, (x-r-2, y-r-2))
            else:  # bar
                w  = max(6, int(10 * sz))
                h  = max(4, int(6  * sz))
                s  = pygame.Surface((w+4, h+4), pygame.SRCALPHA)
                pygame.draw.rect(s, (138, 98,  4,  alpha), (1, 1, w,   h),   border_radius=1)
                pygame.draw.rect(s, (228, 182, 25, alpha), (2, 2, w-2, h-2), border_radius=1)
                if w > 6:
                    pygame.draw.rect(s, (255, 228, 95, alpha), (3, 2, max(1, (w-4)//2), max(1, h-4)))
                surf.blit(s, (x-w//2-2, y-h//2-2))


def make_bg_a():  # 배경 A: 심해 갓레이
    s = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / HEIGHT
        pygame.draw.line(s,(int(2+t*4),int(8+t*18),int(38+t*35)),(0,y),(WIDTH,y))
    ray = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    cx = WIDTH // 2
    for y in range(HEIGHT):
        yt = y / HEIGHT
        ch = int(26 + yt * 55)
        ba = max(0, int((1.0 - yt * 1.05) * 72))
        for dx in range(-ch, ch + 1):
            if 0 <= cx+dx < WIDTH:
                fade = (1.0 - abs(dx)/(ch+1))**1.8
                a = int(ba * fade)
                if a > 0:
                    br = int(fade * 85)
                    ray.set_at((cx+dx,y),(min(255,br),min(255,br+75),min(255,br+175),a))
    s.blit(ray,(0,0))
    rock = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    lp = [(0,0),(0,HEIGHT),(52,HEIGHT),(62,495),(44,415),(74,345),
          (50,272),(83,205),(58,135),(88,68),(70,0)]
    rp = [(WIDTH,0),(WIDTH,HEIGHT),(WIDTH-46,HEIGHT),(WIDTH-60,505),
          (WIDTH-36,425),(WIDTH-70,355),(WIDTH-46,280),(WIDTH-80,210),
          (WIDTH-53,140),(WIDTH-86,72),(WIDTH-66,0)]
    pygame.draw.polygon(rock,(6,13,40,235),lp)
    pygame.draw.polygon(rock,(6,13,40,235),rp)
    for i in range(4):
        al=int(42*(4-i)//4)
        pygame.draw.polygon(rock,(14,28,72,al),[(x+i*4,y) for x,y in lp])
        pygame.draw.polygon(rock,(14,28,72,al),[(x-i*4,y) for x,y in rp])
    s.blit(rock,(0,0))
    ps = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    rng = random.Random(42)
    for _ in range(50):
        px=rng.randint(38,WIDTH-38); py=rng.randint(25,HEIGHT-25)
        sz=rng.randint(1,3); a=rng.randint(70,215); br=rng.randint(155,255)
        for ddx in range(sz):
            for ddy in range(sz):
                if 0<=px+ddx<WIDTH and 0<=py+ddy<HEIGHT:
                    ps.set_at((px+ddx,py+ddy),(br,br,255,a))
    s.blit(ps,(0,0))
    return s


def make_bg():  # 현재 사용 배경 (B or A)
    return make_bg_a()


def make_bg_b():  # 배경 B: 밝은 산호초
    s = pygame.Surface((WIDTH, HEIGHT))
    # 밝은 청록 그라디언트
    for y in range(HEIGHT):
        t = y / HEIGHT
        pygame.draw.line(s,(int(22+t*14),int(158-t*60),int(195-t*62)),(0,y),(WIDTH,y))
    # 수면 빛 라인 (상단)
    sl = pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
    rng0=random.Random(5)
    for i in range(10):
        ly=12+i*7; lw=rng0.randint(35,115); lx=rng0.randint(15,WIDTH-130)
        pygame.draw.rect(sl,(210,245,255,35),(lx,ly,lw,2))
    s.blit(sl,(0,0))
    # 식물/산호 레이어
    pl=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
    # 왼쪽 초록 해초
    for sx,sh2,col3 in [(18,200,(68,168,52)),(34,165,(55,140,42)),(6,145,(85,188,65))]:
        for seg in range(0,sh2,11):
            wv=int(math.sin(seg*0.16)*5)
            pygame.draw.rect(pl,(*col3,225),(sx+wv,HEIGHT-55-seg,8,11))
    # 왼쪽 보라 산호
    for cx3,cy3,cr3,col4 in [(58,HEIGHT-32,17,(145,72,175)),(43,HEIGHT-26,13,(120,58,155)),(72,HEIGHT-22,11,(165,85,190))]:
        pygame.draw.circle(pl,(*col4,220),(cx3,cy3),cr3)
    # 왼쪽 주황 산호
    for dxx in range(-2,3):
        pygame.draw.line(pl,(215,105,38,200),(16,HEIGHT-42),(16+dxx*18,HEIGHT-82),4)
    # 오른쪽 암초 덩어리
    rrp=[(WIDTH,HEIGHT),(WIDTH-92,HEIGHT),(WIDTH-88,HEIGHT-58),(WIDTH-72,HEIGHT-98),
         (WIDTH-82,HEIGHT-148),(WIDTH-62,HEIGHT-178),(WIDTH-78,HEIGHT-218),
         (WIDTH-55,HEIGHT-198),(WIDTH-38,HEIGHT-238),(WIDTH,HEIGHT-238)]
    pygame.draw.polygon(pl,(25,42,85,242),rrp)
    # 오른쪽 분홍 산호
    for cx4,cy4,cr4,col5 in [(WIDTH-55,HEIGHT-248,21,(215,95,150)),(WIDTH-74,HEIGHT-233,14,(195,80,135)),(WIDTH-36,HEIGHT-240,11,(230,110,165))]:
        pygame.draw.circle(pl,(*col5,225),(cx4,cy4),cr4)
    # 오른쪽 주황 팬 산호
    for dxx2 in range(-2,3):
        pygame.draw.line(pl,(225,115,42,200),(WIDTH-28,HEIGHT-198),(WIDTH-28+dxx2*16,HEIGHT-238),3)
    # 오른쪽 초록 해초 (높은)
    for sx2,sh3,col6 in [(WIDTH-22,240,(68,168,52)),(WIDTH-12,205,(80,178,58))]:
        for seg2 in range(0,sh3,11):
            wv2=int(math.sin(seg2*0.14)*5)
            pygame.draw.rect(pl,(*col6,225),(sx2+wv2,HEIGHT-55-seg2,8,11))
    s.blit(pl,(0,0))
    # 해저 바닥
    bd=pygame.Surface((WIDTH,38),pygame.SRCALPHA)
    rng2=random.Random(77)
    for bx2 in range(0,WIDTH,8):
        bh2=rng2.randint(14,32); bc2=(25+rng2.randint(0,12),42+rng2.randint(0,12),82+rng2.randint(0,12))
        pygame.draw.rect(bd,(*bc2,235),(bx2,38-bh2,8,bh2))
    s.blit(bd,(0,HEIGHT-38))
    # 거품 방울
    bs2=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
    rng3=random.Random(99)
    for i in range(14):
        bpx2=WIDTH//2+rng3.randint(-28,28); bpy2=HEIGHT//2-i*28+rng3.randint(-8,8)
        if 0<bpy2<HEIGHT:
            pygame.draw.circle(bs2,(220,242,255,125),(bpx2,bpy2),3)
            pygame.draw.circle(bs2,(255,255,255,85),(bpx2-1,bpy2-1),1)
    s.blit(bs2,(0,0))
    return s


# ── 언락 메시지 그리기 ────────────────────────────────────────
def draw_unlock_msg(surf, msg, timer, by_override=None,
                    text_col=(255,232,100), border_col=(100,190,240), bg_col=(10,20,50),
                    font_size=13):
    if timer <= 0:
        return
    total = 180
    if timer > total - 30:
        a = int((total - timer) / 30 * 255)
    elif timer < 30:
        a = int(timer / 30 * 255)
    else:
        a = 255
    a = max(0, min(255, a))

    f  = get_font(font_size, bold=True)
    ms = f.render(msg, True, text_col)
    pw, ph = ms.get_width() + 26, ms.get_height() + 14
    bg_s = pygame.Surface((pw, ph), pygame.SRCALPHA)
    bg_s.fill((*bg_col, int(a * 0.85)))
    pygame.draw.rect(bg_s, (*border_col, a), (0, 0, pw, ph), 1, border_radius=8)
    ms.set_alpha(a)
    bx = WIDTH // 2 - pw // 2
    by = by_override if by_override is not None else HEIGHT - 95
    surf.blit(bg_s, (bx, by))
    surf.blit(ms, (bx + 13, by + 7))


def draw_intro_screen(surf, bg, has_save):
    surf.blit(bg, (0, 0))

    # 배경 버블
    t = pygame.time.get_ticks() * 0.001
    for i in range(10):
        bx = 15 + i * 37
        by = int((HEIGHT - (t * 22 + i * 65)) % HEIGHT)
        bs = pygame.Surface((8, 8), pygame.SRCALPHA)
        pygame.draw.circle(bs, (180, 220, 255, 55), (4, 4), 3, 1)
        surf.blit(bs, (bx, by))

    # 장식 해파리 (반투명)
    for slot, x, y, sc, al in [(0,55,210,0.75,70),(1,315,270,0.65,60),(0,175,430,0.55,50)]:
        bi2 = _slot_base_idx(slot)
        sw2 = int(64*sc); sh2 = int(48*sc)
        spr2 = pygame.transform.scale(BELL_SPRITES[bi2], (sw2, sh2))
        spr2.set_alpha(al)
        surf.blit(spr2, (x-sw2//2, y-sh2//2))

    # 타이틀
    ft1 = get_font(34, bold=True)
    tt1 = ft1.render('해파리 수족관', True, (205, 242, 255))
    surf.blit(tt1, (WIDTH//2-tt1.get_width()//2, 148))
    ft2 = get_font(14)
    tt2 = ft2.render('Jellyfish Aquarium', True, (115, 178, 220))
    surf.blit(tt2, (WIDTH//2-tt2.get_width()//2, 196))
    fv2 = get_font(11)
    tv2 = fv2.render(f'v{VERSION}', True, (72, 115, 158))
    surf.blit(tv2, (WIDTH//2-tv2.get_width()//2, 220))

    # 처음부터 시작 버튼
    nb = pygame.Surface((INTRO_NEW_BTN.w, INTRO_NEW_BTN.h), pygame.SRCALPHA)
    nb.fill((22, 55, 115, 228))
    pygame.draw.rect(nb, (78, 155, 235), (0,0,INTRO_NEW_BTN.w,INTRO_NEW_BTN.h), 2, border_radius=12)
    surf.blit(nb, INTRO_NEW_BTN.topleft)
    fn3 = get_font(17, bold=True)
    tn3 = fn3.render('처음부터 시작', True, (175, 222, 255))
    surf.blit(tn3, (INTRO_NEW_BTN.x+INTRO_NEW_BTN.w//2-tn3.get_width()//2,
                    INTRO_NEW_BTN.y+INTRO_NEW_BTN.h//2-tn3.get_height()//2))

    # 이어서 하기 버튼
    cb = pygame.Surface((INTRO_CONT_BTN.w, INTRO_CONT_BTN.h), pygame.SRCALPHA)
    if has_save:
        cb.fill((15, 42, 88, 228))
        pygame.draw.rect(cb, (52, 122, 205), (0,0,INTRO_CONT_BTN.w,INTRO_CONT_BTN.h), 2, border_radius=12)
        tc_col = (148, 202, 252)
    else:
        cb.fill((18, 26, 45, 155))
        pygame.draw.rect(cb, (42, 62, 90), (0,0,INTRO_CONT_BTN.w,INTRO_CONT_BTN.h), 1, border_radius=12)
        tc_col = (62, 88, 118)
    surf.blit(cb, INTRO_CONT_BTN.topleft)
    fn4 = get_font(17, bold=True)
    tn4 = fn4.render('이어서 하기', True, tc_col)
    surf.blit(tn4, (INTRO_CONT_BTN.x+INTRO_CONT_BTN.w//2-tn4.get_width()//2,
                    INTRO_CONT_BTN.y+INTRO_CONT_BTN.h//2-tn4.get_height()//2))
    if not has_save:
        fn5 = get_font(10)
        tn5 = fn5.render('저장 없음', True, (52, 72, 98))
        surf.blit(tn5, (INTRO_CONT_BTN.x+INTRO_CONT_BTN.w//2-tn5.get_width()//2,
                        INTRO_CONT_BTN.y+INTRO_CONT_BTN.h+5))

    # 하단 힌트 텍스트 (반짝거림)
    t_hint = pygame.time.get_ticks() * 0.001
    alpha_h = int(140 + math.sin(t_hint * 4.5) * 115)
    alpha_h = max(25, min(255, alpha_h))
    fh = get_font(12)
    ht = fh.render('해파리를 우클릭하여 수집을 시작하세요', True, (145, 195, 235))
    ht.set_alpha(alpha_h)
    surf.blit(ht, (WIDTH//2-ht.get_width()//2, HEIGHT-38))


# ── 메인 ──────────────────────────────────────────────────────
def main():
    global _current_stage
    bg          = make_bg()
    bubbles     = [Bubble() for _ in range(22)]
    pop_bubbles    = []
    cult_doc_drops = []
    inventory, loaded_stage, cult_docs, saved_aquarium, saved_bred, saved_nickname, bgm_vol, sfx_vol, chat_vol, saved_wardrobe, saved_equipped = load_game()
    pygame.mixer.music.set_volume(bgm_vol)
    for _s, _v_base in [(SND_KILL,0.7),(SND_FEED,0.8),(SND_BUBBLE,0.5),(SND_BELL,0.7),(SND_FANFARE,0.8),(SND_AQUARIUM,0.6)]:
        if _s: _s.set_volume(_v_base * sfx_vol)
    for _s2 in [SND_CHAT1, SND_CHAT2]:
        if _s2: _s2.set_volume(chat_vol)
    has_save = os.path.exists(SAVE_PATH)
    _bred_slots.update(saved_bred)
    update_unlocked_slots(inventory)
    player_nickname     = saved_nickname
    show_nickname_input = (player_nickname == '')
    nickname_text       = ''
    ime_composition     = ''
    cursor_blink        = 0
    show_ranking        = False
    show_new_game_warn  = False
    show_settings       = False
    show_online         = False
    online_x            = float(OW//2)
    online_y            = float(OH_PLAY//2)
    online_keys         = {'w':False,'a':False,'s':False,'d':False}
    online_chat_input   = ''
    online_chat_ime     = ''
    online_chat_active  = False
    online_sync_t       = 0
    online_fetch_t      = 0
    online_move_phase    = 0.0
    online_local_chat    = ''
    online_local_chat_t  = 0
    online_interact_open = False
    online_action        = None
    online_action_timer  = 0
    online_action_phase  = 0.0
    online_npc_t         = 0.0
    online_self_pushed   = None   # 로컬 플레이어 밀림 상태 {'timer','max_t','vx','vy'}
    push_fetch_t         = 0
    online_npc_cur_x     = float(OW//2+60)
    online_npc_cur_y     = float(OH_PLAY//2-40)
    online_selected      = None
    online_pushed        = {}
    online_push_anim_t   = 0
    online_push_dir      = (1.0, 0.0)
    settings_dragging   = None   # 'bgm', 'sfx', 'chat'
    if show_nickname_input:
        pygame.key.start_text_input()
    jellies = [Jellyfish(scattered=True) for _ in range(7)]
    show_intro = True
    if not DEV_MODE:
        _current_stage = loaded_stage
    show_bag     = False
    has_new      = False
    show_scroll       = False
    has_new_doc       = False
    scroll_doc_detail = None
    gacha_slot        = None
    gacha_timer       = 0
    show_dev_reset    = False
    show_dev_add      = False
    show_aquarium      = False
    aquarium_adding    = False
    aq_add_scroll      = 0
    aq_drag_y          = None   # 드래그 시작 y
    aquarium_context   = None
    aquarium           = saved_aquarium
    aquarium_fish_list = [AquariumFish(di) for di in saved_aquarium]
    food_pellets       = []
    glass_bottles      = []
    bottle_spawn_t     = random.randint(300, 540)
    feed_bonus         = 0.0   # 먹이 줄 때마다 +0.05, 드랍 시 리셋
    last_fed_fish      = None  # 마지막으로 먹이 준 해파리 객체
    float_texts        = []
    wardrobe_items     = set(saved_wardrobe)
    equipped_item      = saved_equipped
    _wardrobe_cache['items']    = wardrobe_items
    _wardrobe_cache['equipped'] = equipped_item
    wardrobe_context   = None   # right-clicked item_id
    show_wardrobe      = False
    item_msg           = ''
    item_msg_timer     = 0
    acquire_msg        = ''
    acquire_msg_timer  = 0
    context      = None
    unlock_msg   = ''
    unlock_timer = 0
    doc_msg      = ''
    doc_timer    = 0
    # 슬라이딩 공지 텍스트
    NOTICE_MSGS  = [
        '해파리를 죽이면 신비한 배양서를 얻을 수 있다는 전설이 있어',
        '해파리를 잡다보면 미획득 해파리도 볼 수 있을거야',
        '해파리를 어항에 넣으면 춤추는 해파리를 볼 수 있을거야. 아마도...',
        '등급이 높은 해파리일수록 점수를 많이 모을 수 있어. 랭킹을 확인해 봐~',
        '어항 속 해파리는 선물을 준다는 소문이 있어. 특수 해파리 전용 선물도 있다더라?',
    ]
    notice_x     = float(WIDTH)   # 현재 x 위치 (오른쪽에서 왼쪽으로)
    notice_idx   = 0
    notice_wait  = 600            # 다음 공지까지 대기 프레임
    inv_page     = 0
    inv_detail   = None

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                save_game(inventory, _current_stage, cult_docs, aquarium, player_nickname)
                running = False

            elif show_intro:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx2, my2 = event.pos
                    if show_new_game_warn:
                        if WARN_OK_BTN.collidepoint(mx2, my2):
                            # 경고 확인 → 초기화
                            inventory = {}; cult_docs = {}
                            aquarium = []; aquarium_fish_list = []
                            _bred_slots.clear(); update_unlocked_slots({})
                            if not DEV_MODE: _current_stage = 1
                            has_save = False
                            if player_nickname:
                                upload_score_bg(player_nickname, 0)
                            player_nickname = ''; nickname_text = ''; ime_composition = ''
                            show_nickname_input = True
                            show_new_game_warn = False
                            pygame.key.start_text_input()
                            save_game({}, 1, {}, [], '')
                            show_intro = False
                        elif WARN_CANCEL_BTN.collidepoint(mx2, my2):
                            show_new_game_warn = False
                    elif INTRO_NEW_BTN.collidepoint(mx2, my2):
                        if has_save:
                            show_new_game_warn = True  # 경고창 표시
                        else:
                            # 저장 없으면 바로 시작
                            inventory = {}; cult_docs = {}
                            aquarium = []; aquarium_fish_list = []
                            _bred_slots.clear(); update_unlocked_slots({})
                            if not DEV_MODE: _current_stage = 1
                            player_nickname = ''; nickname_text = ''; ime_composition = ''
                            show_nickname_input = True
                            pygame.key.start_text_input()
                            save_game({}, 1, {}, [], '')
                            show_intro = False
                    elif INTRO_CONT_BTN.collidepoint(mx2, my2) and has_save:
                        show_intro = False

            elif event.type == pygame.KEYDOWN:
                if show_online and not online_chat_active:
                    if event.key == pygame.K_RETURN:
                        online_chat_active=True; pygame.key.start_text_input()
                    elif event.key in (pygame.K_w,pygame.K_UP):    online_keys['w']=True
                    elif event.key in (pygame.K_s,pygame.K_DOWN):  online_keys['s']=True
                    elif event.key in (pygame.K_a,pygame.K_LEFT):  online_keys['a']=True
                    elif event.key in (pygame.K_d,pygame.K_RIGHT): online_keys['d']=True
                elif show_online and online_chat_active:
                    if event.key == pygame.K_RETURN and online_chat_input.strip():
                        import time as _tm3; online_local_chat=online_chat_input.strip(); online_local_chat_t=int(_tm3.time())
                        send_online_chat(player_nickname, online_chat_input.strip())
                        online_chat_input=''; online_chat_ime=''
                        online_chat_active=False; pygame.key.stop_text_input()
                    elif event.key == pygame.K_ESCAPE:
                        online_chat_active=False; online_chat_input=''; pygame.key.stop_text_input()
                    elif event.key == pygame.K_BACKSPACE and not online_chat_ime:
                        online_chat_input=online_chat_input[:-1]
                elif show_nickname_input:
                    if event.key == pygame.K_RETURN and nickname_text.strip():
                        player_nickname = nickname_text.strip()[:12]
                        show_nickname_input = False
                        pygame.key.stop_text_input()
                        save_game(inventory, _current_stage, cult_docs, aquarium, player_nickname)
                        upload_score_bg(player_nickname, calc_score(inventory))
                    elif event.key == pygame.K_BACKSPACE:
                        # 조합 중이면 조합 취소, 아니면 한 글자 삭제
                        if not ime_composition:
                            nickname_text = nickname_text[:-1]
                elif DEV_MODE and event.key == pygame.K_r and not show_bag and not show_scroll and not show_aquarium and not show_intro:
                    show_dev_add = False
                elif DEV_MODE and event.key == pygame.K_t and not show_bag and not show_scroll and not show_aquarium and not show_intro:
                    show_dev_add = not show_dev_add; show_dev_reset = False
                    show_dev_reset = not show_dev_reset
                elif event.key == pygame.K_ESCAPE:
                    if inv_detail is not None: inv_detail = None
                    elif show_bag: show_bag = False
                    elif aquarium_context is not None: aquarium_context = None
                    elif aquarium_adding: aquarium_adding = False
                    elif show_wardrobe:   show_wardrobe = False
                    elif show_aquarium:   show_aquarium = False
                    elif online_chat_active:         online_chat_active=False; pygame.key.stop_text_input()
                    elif show_online:
                        show_online=False; stop_sse_stream(); remove_online_player(player_nickname)
                    elif show_settings:             show_settings = False; settings_dragging = None
                    elif show_ranking:              show_ranking = False
                    elif show_dev_reset:           show_dev_reset = False
                    elif show_dev_add:             show_dev_add = False
                    elif gacha_slot is not None: gacha_slot = None; gacha_timer = 0
                    elif scroll_doc_detail is not None: scroll_doc_detail = None
                    elif show_scroll: show_scroll = False
                    elif context: context = None
                    else:
                        save_game(inventory, _current_stage, cult_docs, aquarium, player_nickname)
                        running = False

            elif event.type == pygame.TEXTINPUT:
                if online_chat_active and len(online_chat_input) < 40:
                    online_chat_input += event.text; online_chat_ime = ''
                elif show_nickname_input and len(nickname_text) < 12:
                    nickname_text += event.text; ime_composition = ''
            elif event.type == pygame.TEXTEDITING:
                if online_chat_active: online_chat_ime = event.text
                elif show_nickname_input: ime_composition = event.text
            elif event.type == pygame.MOUSEWHEEL:
                if aquarium_adding:
                    aq_add_scroll = max(0, aq_add_scroll - event.y * 35)
            elif event.type == pygame.KEYUP:
                if show_online:
                    if event.key in (pygame.K_w,pygame.K_UP):    online_keys['w']=False
                    elif event.key in (pygame.K_s,pygame.K_DOWN):  online_keys['s']=False
                    elif event.key in (pygame.K_a,pygame.K_LEFT):  online_keys['a']=False
                    elif event.key in (pygame.K_d,pygame.K_RIGHT): online_keys['d']=False
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                aq_drag_y = None
                if settings_dragging:
                    settings_dragging = None
                    save_game(inventory,_current_stage,cult_docs,aquarium,player_nickname,bgm_vol,sfx_vol)
            elif event.type == pygame.MOUSEMOTION:
                if settings_dragging:
                    mx_m = event.pos[0]
                    if settings_dragging == 'bgm':
                        bgm_vol = max(0.0, min(1.0, (mx_m-SL_BGM[0])/SL_BGM[2]))
                        pygame.mixer.music.set_volume(bgm_vol)
                    elif settings_dragging == 'sfx':
                        sfx_vol = max(0.0, min(1.0, (mx_m-SL_SFX[0])/SL_SFX[2]))
                        for _s,_vb in [(SND_KILL,0.7),(SND_FEED,0.8),(SND_BUBBLE,0.5),(SND_BELL,0.7),(SND_FANFARE,0.8),(SND_AQUARIUM,0.6)]:
                            if _s: _s.set_volume(_vb*sfx_vol)
                    elif settings_dragging == 'chat':
                        chat_vol = max(0.0, min(1.0, (mx_m-SL_CHAT[0])/SL_CHAT[2]))
                        for _sc in [SND_CHAT1,SND_CHAT2]:
                            if _sc: _sc.set_volume(chat_vol)
                elif aquarium_adding and aq_drag_y is not None:
                    aq_add_scroll = max(0, aq_add_scroll - (event.pos[1] - aq_drag_y))
                    aq_drag_y = event.pos[1]
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos

                if event.button == 1:
                    if show_online:
                        # 나가기 버튼
                        if pygame.Rect(OW-58,4,52,22).collidepoint(mx,my):
                            show_online=False; stop_sse_stream(); remove_online_player(player_nickname)
                        # 휠 아이콘
                        elif pygame.Rect(OW-32,OH_PLAY-32,24,24).collidepoint(mx,my):
                            online_interact_open = not online_interact_open
                        # 인터랙션 리스트 항목
                        elif online_interact_open:
                            items=[('banzai',24),('dance',180)]
                            iw,ih=115,36; wx_c=OW-20; ly_c=OH_PLAY-20-len(items)*ih-8
                            for i,(key,dur) in enumerate(items):
                                iy=ly_c+i*ih
                                lx_c=min(wx_c-iw//2, OW-iw-5)
                                if pygame.Rect(lx_c,iy,iw,ih).collidepoint(mx,my):
                                    online_action=key; online_action_timer=dur; online_action_phase=0.0
                                    online_interact_open=False; break
                            else:
                                online_interact_open=False
                        else:
                            # 밀치기 버튼 클릭 확인
                            _push_hit = False
                            if online_selected and online_selected in _online_players and online_selected not in online_pushed:
                                _sd = _online_players[online_selected]
                                _px = int(_sd.get('cur_x',_sd.get('x',190)))
                                _py = int(_sd.get('cur_y',_sd.get('y',200)))
                                _sp_h2 = int(40*0.75)
                                _bw,_bh = 60,24
                                _bx2 = max(2, min(OW-_bw-2, _px-_bw//2))
                                _by2 = max(2, _py-_sp_h2//2-36)
                                _dist_p = math.hypot(_px-online_x, _py-online_y)
                                if pygame.Rect(_bx2,_by2,_bw,_bh).collidepoint(mx,my) and _dist_p < 55:
                                    _ddx = _px-online_x; _ddy = _py-online_y
                                    _dlen = max(1.0, math.hypot(_ddx,_ddy))
                                    _vx = (_ddx/_dlen)*9.0; _vy = (_ddy/_dlen)*4.0
                                    _max_t = 70
                                    online_pushed[online_selected] = {'timer':_max_t,'max_t':_max_t,'vx':_vx,'vy':_vy}
                                    online_push_anim_t = 18
                                    online_push_dir = (_ddx/_dlen, _ddy/_dlen)
                                    # Firebase에 push 이벤트 전송 (NPC 제외)
                                    if online_selected != '__npc__':
                                        send_push_event(online_selected, _vx, _vy)
                                    online_selected = None
                                    _push_hit = True
                            if not _push_hit:
                                _found = None
                                _sp2 = 40; _sh2 = int(_sp2*0.75)
                                for _n2,_d2 in _online_players.items():
                                    _px2 = int(_d2.get('cur_x',_d2.get('x',190)))
                                    _py2 = int(_d2.get('cur_y',_d2.get('y',200)))
                                    if abs(mx-_px2)<_sp2//2 and abs(my-_py2)<_sh2//2+10:
                                        _found=_n2; break
                                online_selected = _found
                        # 채팅창 클릭
                        inp_y=OH_PLAY+OH_CHAT-30
                        if pygame.Rect(8,inp_y,OW-16,24).collidepoint(mx,my):
                            online_chat_active=True; pygame.key.start_text_input()
                    elif show_settings:
                        if pygame.Rect(15,12,75,28).collidepoint(mx,my):
                            show_settings = False
                            save_game(inventory,_current_stage,cult_docs,aquarium,player_nickname,bgm_vol,sfx_vol)
                        elif SL_BGM[0]<=mx<=SL_BGM[0]+SL_BGM[2] and abs(my-(SL_BGM[1]+12))<=16:
                            settings_dragging='bgm'
                            bgm_vol=max(0.0,min(1.0,(mx-SL_BGM[0])/SL_BGM[2]))
                            pygame.mixer.music.set_volume(bgm_vol)
                        elif SL_SFX[0]<=mx<=SL_SFX[0]+SL_SFX[2] and abs(my-(SL_SFX[1]+12))<=16:
                            settings_dragging='sfx'
                            sfx_vol=max(0.0,min(1.0,(mx-SL_SFX[0])/SL_SFX[2]))
                            for _s,_vb in [(SND_KILL,0.7),(SND_FEED,0.8),(SND_BUBBLE,0.5),(SND_BELL,0.7),(SND_FANFARE,0.8),(SND_AQUARIUM,0.6)]:
                                if _s: _s.set_volume(_vb*sfx_vol)
                        elif SL_CHAT[0]<=mx<=SL_CHAT[0]+SL_CHAT[2] and abs(my-(SL_CHAT[1]+12))<=16:
                            settings_dragging='chat'
                            chat_vol=max(0.0,min(1.0,(mx-SL_CHAT[0])/SL_CHAT[2]))
                            for _sc in [SND_CHAT1,SND_CHAT2]:
                                if _sc: _sc.set_volume(chat_vol)
                    elif show_ranking:
                        if pygame.Rect(15,12,75,28).collidepoint(mx,my):
                            show_ranking = False
                    elif aquarium_adding:
                        aq_drag_y = my
                    if show_dev_add:
                        if DEV_RESET_BACK.collidepoint(mx, my):
                            show_dev_add = False
                        else:
                            pos_a = 0
                            CWa, CHa = 110, 95
                            for slot_a in range(len(JELLY_NAMES)):
                                if inventory.get(slot_a, 0) > 0: continue
                                col_a = pos_a%3; row_a = pos_a//3
                                cx_a = 15+CWa//2+col_a*(CWa+5)
                                cy_a = 55+CHa//2+row_a*(CHa+5)
                                if abs(mx-cx_a)<CWa//2 and abs(my-cy_a)<CHa//2:
                                    inventory[slot_a] = 1
                                    save_game(inventory,_current_stage,cult_docs,aquarium)
                                    update_unlocked_slots(inventory)
                                    has_new = True
                                    break
                                pos_a += 1
                    elif show_dev_reset:
                        if DEV_RESET_BACK.collidepoint(mx, my):
                            show_dev_reset = False
                        else:
                            pos_r = 0
                            CWr, CHr = 110, 95
                            for slot_r in range(len(JELLY_NAMES)):
                                if slot_r not in inventory or inventory[slot_r] <= 0: continue
                                col_r = pos_r%3; row_r = pos_r//3
                                cx_r = 15+CWr//2+col_r*(CWr+5)
                                cy_r = 55+CHr//2+row_r*(CHr+5)
                                if abs(mx-cx_r)<CWr//2 and abs(my-cy_r)<CHr//2:
                                    del inventory[slot_r]
                                    aquarium_fish_list=[f for f in aquarium_fish_list if f.design_idx!=slot_r]
                                    aquarium=[di for di in aquarium if di!=slot_r]
                                    save_game(inventory,_current_stage,cult_docs,aquarium)
                                    update_unlocked_slots(inventory)
                                    break
                                pos_r += 1
                    elif _latest_ver and pygame.Rect(0,0,WIDTH,22).collidepoint(mx,my):
                        webbrowser.open(_release_url)
                    elif aquarium_adding:
                        if AQ_BACK_RECT.collidepoint(mx, my):
                            aquarium_adding = False
                        elif len(aquarium) < 5:
                            # 셀 클릭 감지 (draw_aquarium_add_screen 와 동일 레이아웃)
                            CW5, CH5 = 110, 95
                            cols5, mx5, sy5 = 3, 15, 55
                            pos_i5 = 0
                            for slot5 in range(len(JELLY_NAMES)):
                                if inventory.get(slot5, 0) <= 0:
                                    continue
                                col5 = pos_i5 % cols5
                                row5 = pos_i5 // cols5
                                cx5  = mx5 + CW5//2 + col5*(CW5+5)
                                cy5  = sy5 + CH5//2 + row5*(CH5+5) - aq_add_scroll
                                if abs(mx-cx5)<CW5//2 and abs(my-cy5)<CH5//2:
                                    aquarium.append(slot5)
                                    aquarium_fish_list.append(AquariumFish(slot5))
                                    inventory[slot5] = inventory.get(slot5,0) - 1
                                    save_game(inventory,_current_stage,cult_docs,aquarium,player_nickname,bgm_vol,sfx_vol)
                                    if len(aquarium) >= 5:
                                        aquarium_adding = False
                                    break
                                pos_i5 += 1
                    elif show_aquarium:
                        if show_wardrobe:
                            if AQ_BACK_RECT.collidepoint(mx, my):
                                show_wardrobe = False; wardrobe_context = None
                            elif wardrobe_context and wardrobe_context in wardrobe_items:
                                # 팝업 착용/해제 버튼 클릭 확인
                                ci_w = next((j for j,(iid,_) in enumerate(WARDROBE_ITEM_DEFS) if iid==wardrobe_context),0)
                                cw_w,ch_w,cols_w,gap_w = 82,80,4,6
                                total_w_w = cols_w*(cw_w+gap_w)-gap_w
                                sx_w = (WIDTH-total_w_w)//2; sy_w = 58
                                px_w = sx_w+(ci_w%cols_w)*(cw_w+gap_w)
                                py_w = sy_w+(ci_w//cols_w)*(ch_w+gap_w)
                                pop_x_w = min(px_w+cw_w+4, WIDTH-84); pop_y_w = max(py_w,4)
                                if pygame.Rect(pop_x_w,pop_y_w,80,32).collidepoint(mx,my):
                                    if equipped_item == wardrobe_context:
                                        equipped_item = None
                                    else:
                                        equipped_item = wardrobe_context
                                    _wardrobe_cache['equipped'] = equipped_item
                                    save_game(inventory,_current_stage,cult_docs,aquarium,player_nickname,bgm_vol,sfx_vol,wardrobe_items=wardrobe_items,equipped_item=equipped_item)
                                wardrobe_context = None
                            else:
                                wardrobe_context = None
                        elif aquarium_context is not None:
                            if aquarium_context.get_feed_rect().collidepoint(mx,my):
                                aquarium_context.fish.feed()
                                feed_bonus = min(feed_bonus + 0.05, 0.95)
                                last_fed_fish = aquarium_context.fish
                                _fx = aquarium_context.fish.x + random.uniform(-15,15)
                                _fy = aquarium_context.fish.y - aquarium_context.fish.bh0//2
                                float_texts.append(FloatText(_fx, _fy, '친밀도 +5%', color=(255,80,140)))
                                item_msg = random.choice(['해파리와 친해졌습니다!','해파리가 좋아합니다!','해파리가 선물을 준비합니다!'])
                                item_msg_timer = 120
                                if SND_FEED: SND_FEED.play()
                                for _ in range(3):
                                    food_pellets.append(FoodPellet(
                                        aquarium_context.fish.x,
                                        aquarium_context.fish.y-aquarium_context.fish.bh0//2))
                                aquarium_context = None
                            elif aquarium_context.get_release_rect().collidepoint(mx,my):
                                f_rel = aquarium_context.fish
                                aquarium_fish_list.remove(f_rel)
                                di_r = f_rel.design_idx
                                aquarium.remove(di_r)
                                if SND_RELEASE: SND_RELEASE.play()
                                if di_r not in inventory:
                                    inventory[di_r] = 0
                                save_game(inventory,_current_stage,cult_docs,aquarium,player_nickname,bgm_vol,sfx_vol,wardrobe_items=wardrobe_items)
                                aquarium_context = None
                            else:
                                aquarium_context = None
                        elif AQ_BACK_RECT.collidepoint(mx, my):
                            show_aquarium = False; aquarium_context = None
                        elif AQ_WARDROBE_RECT.collidepoint(mx, my):
                            show_wardrobe = True; play_ui_click()
                        elif AQUARIUM_ADD_BTN.collidepoint(mx, my) and len(aquarium)<5:
                            aquarium_adding = True
                        else:
                            # 유리병 클릭 확인
                            _bottle_clicked = False
                            for _b2 in glass_bottles:
                                if _b2.hit_test(mx, my) and not _b2.collected:
                                    _b2.collected = True
                                    wardrobe_items.add(_b2.item_id)
                                    acquire_msg = f'{_b2.item_name}을(를) 획득했습니다!'
                                    acquire_msg_timer = 180
                                    if SND_BELL: SND_BELL.play()
                                    for _ in range(random.randint(5,8)):
                                        pop_bubbles.append(PopBubble(_b2.x, _b2.y))
                                    save_game(inventory,_current_stage,cult_docs,aquarium,player_nickname,bgm_vol,sfx_vol,wardrobe_items=wardrobe_items,equipped_item=equipped_item)
                                    _bottle_clicked = True; break
                            if not _bottle_clicked:
                                # 좌클릭: 꿀렁 + 버블
                                for f_obj in aquarium_fish_list:
                                    if f_obj.hit_test(mx, my):
                                        f_obj.click_squish = 1.0
                                        opts_sq = [s for s in [SND_SQUEAK1,SND_SQUEAK2] if s]
                                        if opts_sq: random.choice(opts_sq).play()
                                        for _ in range(random.randint(3,5)):
                                            pop_bubbles.append(PopBubble(f_obj.x, f_obj.y))
                                        break
                    elif gacha_slot is not None:
                        # 확인 버튼 (progress > 0.84)
                        prog_g = 1.0 - gacha_timer / GACHA_TOTAL
                        if prog_g > 0.84 and GACHA_CONFIRM_RECT.collidepoint(mx, my):
                            _bred_slots.add(gacha_slot)  # 교배 해금 → 인게임 출몰
                            gacha_slot = None; gacha_timer = 0
                    elif show_scroll:
                        if scroll_doc_detail is not None:
                            # 만들기 버튼 클릭
                            if MAKE_BTN_RECT.collidepoint(mx, my):
                                recipe_d = CULT_DOC_RECIPE.get(scroll_doc_detail)
                                result_d = CULT_DOC_RESULT.get(scroll_doc_detail)
                                if recipe_d and result_d is not None:
                                    a_s, b_s = recipe_d
                                    if inventory.get(a_s,0)>0 and inventory.get(b_s,0)>0:
                                        gacha_slot  = result_d
                                        gacha_timer = GACHA_TOTAL
                                        if SND_FANFARE: SND_FANFARE.play()
                                        show_scroll = False; scroll_doc_detail = None
                            else:
                                # 뒤로 버튼 or 아무 곳이나 클릭 → 목록으로
                                scroll_doc_detail = None
                        else:
                            # 카드 클릭 감지
                            cy_card = 60
                            clicked_doc = None
                            for dt_c in sorted(cult_docs):
                                if dt_c not in CULT_DOC_NAMES:
                                    continue
                                if cult_docs.get(dt_c, 0) <= 0:
                                    continue
                                ch_c = 96 if CULT_DOC_RESULT.get(dt_c) else 72
                                if pygame.Rect(18, cy_card, WIDTH-36, ch_c).collidepoint(mx, my):
                                    clicked_doc = dt_c
                                    break
                                cy_card += ch_c + 8
                            if clicked_doc is not None and CULT_DOC_RECIPE.get(clicked_doc):
                                scroll_doc_detail = clicked_doc
                            else:
                                show_scroll = False; scroll_doc_detail = None
                    elif show_bag:
                        total_pages = max(1, math.ceil(len(JELLY_NAMES)/6))
                        if inv_detail is not None:
                            if DETAIL_BACK_RECT.collidepoint(mx, my):
                                inv_detail = None
                        elif INV_NEXT_RECT.collidepoint(mx, my) and inv_page < total_pages-1:
                            inv_page += 1
                        elif INV_PREV_RECT.collidepoint(mx, my) and inv_page > 0:
                            inv_page -= 1
                        else:
                            _SL = 6
                            _POS = [(65,158),(190,158),(315,158),(65,365),(190,365),(315,365)]
                            _CW, _CH = 108, 148
                            clicked = False
                            for pi, (cx2, cy2) in enumerate(_POS):
                                s2 = inv_page * _SL + pi
                                if s2 >= len(JELLY_NAMES): break
                                if pygame.Rect(cx2-_CW//2, cy2-_CH//2, _CW, _CH).collidepoint(mx, my):
                                    inv_detail = s2; clicked = True; break
                            if not clicked:
                                show_bag = False; context = None
                    elif context:
                        if context.get_kill_rect().collidepoint(mx, my):
                            j_killed = context.jelly
                            j_killed.kill()
                            if SND_KILL: SND_KILL.play()
                            # 무지개 배양서: 유령(9) 또는 슬라임(6) 해파리 죽일 때 10%
                            if j_killed.design_idx in (6, 9) and cult_docs.get(1,0)==0 and random.random()<0.10:
                                cult_docs[1]=1; has_new_doc=True
                                cult_doc_drops.append(CultDocDrop(j_killed.x, j_killed.y))
                                doc_msg='???배양서를 획득했습니다. 어떤 배양서를 얻었는지 확인해보세요.'
                                doc_timer=180
                                save_game(inventory, _current_stage, cult_docs, aquarium, player_nickname)
                            # 파분 배양서: 분홍 해파리(design_idx=1) 죽일 때 40%
                            if j_killed.design_idx==1 and cult_docs.get(2,0)==0 and random.random()<0.40:
                                cult_docs[2]=1; has_new_doc=True
                                cult_doc_drops.append(CultDocDrop(j_killed.x, j_killed.y))
                                if doc_timer<=0:
                                    doc_msg='???배양서를 획득했습니다. 어떤 배양서를 얻었는지 확인해보세요.'
                                    doc_timer=180
                                save_game(inventory, _current_stage, cult_docs, aquarium, player_nickname)
                            # 쌍둥이 배양서: 아무 해파리 죽일 때 10%
                            if cult_docs.get(3,0)==0 and random.random()<0.10:
                                cult_docs[3]=1; has_new_doc=True
                                cult_doc_drops.append(CultDocDrop(j_killed.x, j_killed.y))
                                if doc_timer<=0:
                                    doc_msg='???배양서를 획득했습니다. 어떤 배양서를 얻었는지 확인해보세요.'
                                    doc_timer=180
                                save_game(inventory, _current_stage, cult_docs, aquarium, player_nickname)
                            context = None
                        elif context.get_catch_rect().collidepoint(mx, my):
                            j = context.jelly
                            if SND_BUBBLE: SND_BUBBLE.play()
                            old_unlocked = frozenset(_unlocked_slots)
                            inventory[j.design_idx] = inventory.get(j.design_idx,0)+1
                            has_new = True
                            save_game(inventory, _current_stage, cult_docs, aquarium, player_nickname)
                            if player_nickname:
                                upload_score_bg(player_nickname, calc_score(inventory))
                            # 언락 감지
                            update_unlocked_slots(inventory)
                            new_slots = _unlocked_slots - old_unlocked
                            if new_slots:
                                newest = max(new_slots)
                                unlock_msg   = f'{JELLY_NAMES[newest]}가 출몰하기 시작했어!'
                                unlock_timer = 180
                                if SND_BELL: SND_BELL.play()
                            for _ in range(random.randint(6,10)):
                                pop_bubbles.append(PopBubble(j.x,j.y))
                            jellies.remove(j)
                            jellies.append(Jellyfish(scattered=False))
                            context = None
                        else:
                            context = None
                    elif BAG_RECT.collidepoint(mx, my):
                        play_ui_click()
                        show_bag = True; has_new = False; show_scroll = False
                        context = None; inv_page = 0; inv_detail = None
                    elif SCROLL_RECT.collidepoint(mx, my):
                        play_ui_click()
                        show_scroll = True; has_new_doc = False
                        show_bag = False; show_aquarium = False; inv_detail = None; context = None
                    elif AQUARIUM_RECT.collidepoint(mx, my):
                        show_aquarium = True
                        if SND_AQUARIUM: SND_AQUARIUM.play()
                        show_bag = False; show_scroll = False; context = None
                    elif RANKING_RECT.collidepoint(mx, my):
                        play_ui_click()
                        show_ranking = True; show_ranking_back = pygame.Rect(15,12,75,28)
                        fetch_rankings_bg()
                        show_bag=False; show_scroll=False; show_aquarium=False; context=None
                    elif ONLINE_RECT.collidepoint(mx, my) and player_nickname:
                        show_online = True
                        online_x = float(OW//2); online_y = float(OH_PLAY//2)
                        online_keys = {'w':False,'a':False,'s':False,'d':False}
                        online_npc_t = 0.0; online_selected = None; online_pushed = {}; online_push_anim_t = 0
                        if DEV_MODE:
                            _online_players['__npc__'] = {
                                'x': float(OW//2+60), 'y': float(OH_PLAY//2-40),
                                'cur_x': float(OW//2+60), 'cur_y': float(OH_PLAY//2-40),
                                'nickname': '테스트NPC', 'last_seen': 0
                            }
                        start_sse_stream(player_nickname)
                        fetch_online_bg(player_nickname)
                        show_bag=False; show_scroll=False; show_aquarium=False
                    elif SETTINGS_RECT.collidepoint(mx, my):
                        play_ui_click()
                        show_settings = True
                        show_bag=False; show_scroll=False; show_aquarium=False; context=None
                    else:
                        for j in jellies:
                            if j.hit_test(mx, my):
                                j.trigger()
                                if SND_BUBBLE: SND_BUBBLE.play()
                                for _ in range(random.randint(4,7)):
                                    pop_bubbles.append(PopBubble(j.x,j.y))
                                break

                elif event.button == 3:
                    if show_aquarium and show_wardrobe:
                        # 옷장 아이템 우클릭
                        cw_r,ch_r,cols_r,gap_r = 82,80,4,6
                        total_w_r = cols_r*(cw_r+gap_r)-gap_r
                        sx_r=(WIDTH-total_w_r)//2; sy_r=58
                        wardrobe_context = None
                        for j_r,(iid_r,_) in enumerate(WARDROBE_ITEM_DEFS):
                            if iid_r not in wardrobe_items: continue
                            ix_r=sx_r+(j_r%cols_r)*(cw_r+gap_r); iy_r=sy_r+(j_r//cols_r)*(ch_r+gap_r)
                            if pygame.Rect(ix_r,iy_r,cw_r,ch_r).collidepoint(mx,my):
                                wardrobe_context = iid_r; break
                    elif show_aquarium and not aquarium_adding:
                        aquarium_context = None
                        for f_obj in reversed(aquarium_fish_list):
                            if f_obj.hit_test(mx, my):
                                aquarium_context = AquariumContextMenu(f_obj)
                                break
                    elif not show_bag:
                        context = None
                        for j in jellies:
                            if j.hit_test(mx, my):
                                context = ContextMenu(j)
                                break

        if show_intro:
            draw_intro_screen(screen, bg, has_save)
            if show_new_game_warn:
                draw_new_game_warning(screen)
            pygame.display.flip()
            clock.tick(FPS)
            continue

        screen.blit(bg,(0,0))
        for b in bubbles: b.update(); b.draw(screen)
        jellies.sort(key=lambda j: j.bw0)
        for j in jellies: j.update(); j.draw(screen)
        pop_bubbles=[b for b in pop_bubbles if b.update()]
        for b in pop_bubbles: b.draw(screen)
        cult_doc_drops = [d for d in cult_doc_drops if d.update()]
        for d in cult_doc_drops: d.draw(screen)

        draw_bag_icon(screen, BAG_RECT, has_new)
        draw_scroll_icon(screen, SCROLL_RECT, has_new_doc)
        draw_aquarium_icon(screen, AQUARIUM_RECT)
        draw_ranking_icon(screen, RANKING_RECT)
        draw_settings_icon(screen, SETTINGS_RECT)
        draw_online_icon(screen, ONLINE_RECT)
        if show_online:
            # WASD 이동
            spd = 2.5
            if online_keys['w'] and not online_chat_active: online_y = max(30, online_y-spd)
            if online_keys['s'] and not online_chat_active: online_y = min(OH_PLAY-30, online_y+spd)
            if online_keys['a'] and not online_chat_active: online_x = max(20, online_x-spd)
            if online_keys['d'] and not online_chat_active: online_x = min(OW-20, online_x+spd)
            # 위치 동기화
            online_sync_t += 1
            if online_sync_t >= 10:
                online_sync_t = 0
                sync_online_pos(player_nickname, online_x, online_y, online_action, online_action_phase, equipped_item)
            online_fetch_t += 1
            if online_fetch_t >= 90:  # 채팅만 주기적으로 fetch
                online_fetch_t = 0
                fetch_online_bg(player_nickname)
            # 보간: cur_x/cur_y를 target x/y로 부드럽게 이동 (밀치기 중인 플레이어 제외)
            for _ok, _od in _online_players.items():
                if _ok in online_pushed: continue
                _od['cur_x'] = _od.get('cur_x', _od['x']) + (_od['x'] - _od.get('cur_x',_od['x'])) * 0.28
                _od['cur_y'] = _od.get('cur_y', _od['y']) + (_od['y'] - _od.get('cur_y',_od['y'])) * 0.28
            is_mv = any(online_keys[k] for k in online_keys)
            if is_mv: online_move_phase += 0.18
            # 액션 애니메이션 업데이트
            if online_action_timer > 0:
                online_action_timer -= 1
                online_action_phase += 0.15
                if online_action_timer == 0: online_action = None
            # 테스트 NPC (DEV_MODE 전용)
            if DEV_MODE:
                if '__npc__' not in _online_players:
                    _online_players['__npc__'] = {
                        'x': online_npc_cur_x, 'y': online_npc_cur_y,
                        'cur_x': online_npc_cur_x, 'cur_y': online_npc_cur_y,
                        'nickname': '테스트NPC', 'last_seen': 0
                    }
                _npc = _online_players['__npc__']
                if '__npc__' not in online_pushed:
                    online_npc_t += 0.018
                    _npc['x'] = OW//2 + 60 + math.sin(online_npc_t)*50
                    _npc['y'] = OH_PLAY//2 - 40 + math.cos(online_npc_t*0.7)*30
                    _npc['cur_x'] = _npc['x']; _npc['cur_y'] = _npc['y']
                _npc['phase'] = online_npc_t * 3.0
                online_npc_cur_x = float(_npc.get('cur_x', online_npc_cur_x))
                online_npc_cur_y = float(_npc.get('cur_y', online_npc_cur_y))
            # 밀치기 타이머 감소 + 피격자 위치 이동
            new_pushed = {}
            for _pk,_pv in online_pushed.items():
                t2 = _pv['timer'] - 1
                if t2 > 0:
                    new_vx = _pv['vx'] * 0.82; new_vy = _pv['vy'] * 0.82
                    new_pushed[_pk] = {'timer':t2,'max_t':_pv['max_t'],'vx':new_vx,'vy':new_vy}
                    if _pk in _online_players:
                        _op2 = _online_players[_pk]
                        _op2['cur_x'] = max(20, min(OW-20, _op2.get('cur_x',_op2['x']) + _pv['vx']))
                        _op2['cur_y'] = max(20, min(OH_PLAY-20, _op2.get('cur_y',_op2['y']) + _pv['vy']))
            online_pushed = new_pushed
            if online_push_anim_t > 0: online_push_anim_t -= 1
            # push_events fetch (1.5초마다)
            push_fetch_t += 1
            if push_fetch_t >= 90:
                push_fetch_t = 0
                fetch_push_events()
            # push_events 적용
            for _pn, _pe in list(_push_events.items()):
                _pmax = 70
                if _pn == player_nickname:
                    # 내가 밀렸을 때
                    if online_self_pushed is None:
                        online_self_pushed = {'timer':_pmax,'max_t':_pmax,'vx':_pe['vx'],'vy':_pe['vy']}
                elif _pn in _online_players and _pn not in online_pushed:
                    online_pushed[_pn] = {'timer':_pmax,'max_t':_pmax,'vx':_pe['vx'],'vy':_pe['vy']}
            # 로컬 플레이어 밀림 업데이트
            if online_self_pushed:
                online_self_pushed['timer'] -= 1
                online_x = max(20, min(OW-20, online_x + online_self_pushed['vx']))
                online_y = max(20, min(OH_PLAY-20, online_y + online_self_pushed['vy']))
                online_self_pushed['vx'] *= 0.82; online_self_pushed['vy'] *= 0.82
                if online_self_pushed['timer'] <= 0: online_self_pushed = None
            draw_online_world(screen, online_x, online_y, player_nickname,
                              _online_players, _online_chat,
                              online_chat_input, online_chat_active, online_chat_ime,
                              online_move_phase, online_local_chat, online_local_chat_t,
                              online_interact_open, online_action, online_action_phase,
                              online_selected, online_pushed,
                              online_push_anim_t, online_push_dir,
                              equipped_item, online_self_pushed)
        if show_settings:
            draw_settings_screen(screen, bgm_vol, sfx_vol, chat_vol)
        if show_ranking:
            draw_ranking_screen(screen, _rankings_cache, _rankings_loading, player_nickname)
        if show_nickname_input and not show_intro:
            cursor_blink = (cursor_blink+1)%60
            draw_nickname_input(screen, nickname_text + ime_composition, cursor_blink<30)
        if show_dev_reset:
            draw_dev_reset_screen(screen, inventory)
        if show_dev_add:
            draw_dev_add_screen(screen, inventory)
        # 어항 물고기 업데이트 (항상)
        for f_obj in aquarium_fish_list: f_obj.update()
        if context and not show_bag and not show_scroll and not show_aquarium: context.draw(screen)
        if show_aquarium:
            if aquarium_adding:
                draw_aquarium_add_screen(screen, inventory, aq_add_scroll)
            elif show_wardrobe:
                draw_wardrobe_screen(screen, wardrobe_items, equipped_item, wardrobe_context)
            else:
                draw_aquarium_screen(screen, aquarium_fish_list)
                # 유리병 스폰
                if aquarium_fish_list:
                    bottle_spawn_t -= 1
                    if bottle_spawn_t <= 0:
                        bottle_spawn_t = random.randint(320, 600)
                        if len(glass_bottles) < 3:
                            # 마지막으로 먹이 준 해파리 우선, 없으면 랜덤
                            fish_src = (last_fed_fish if last_fed_fish and last_fed_fish in aquarium_fish_list
                                        else random.choice(aquarium_fish_list))
                            _specific = [d for d in WARDROBE_DROP_MAP.get(fish_src.design_idx, []) if d not in wardrobe_items]
                            _common   = [d for d in WARDROBE_COMMON_DROPS if d not in wardrobe_items]
                            # 전용템 40%+보너스, 공용템 15%+보너스
                            _candidates = []
                            if _specific and random.random() < min(0.50+feed_bonus, 0.95): _candidates += _specific
                            if _common   and random.random() < min(0.20+feed_bonus, 0.95): _candidates += _common
                            if _candidates:
                                _drop_id = random.choice(_candidates)
                                _drop_item = next(x for x in WARDROBE_ITEM_DEFS if x[0]==_drop_id)
                                glass_bottles.append(GlassBottle(fish_src.x, fish_src.y, _drop_item))
                                feed_bonus = 0.0  # 드랍 발생 시 리셋
                                last_fed_fish = None
                # 유리병 업데이트/렌더
                glass_bottles = [b2 for b2 in glass_bottles if b2.update()]
                for b2 in glass_bottles: b2.draw(screen)
                # 사료 업데이트/렌더
                food_pellets = [fp for fp in food_pellets if fp.update()]
                for fp in food_pellets: fp.draw(screen)
                float_texts = [ft for ft in float_texts if ft.update()]
                for ft in float_texts: ft.draw(screen)
                # 컨텍스트 메뉴
                if aquarium_context:
                    aquarium_context.draw(screen)
                # 어항 위에 버블
                for b in pop_bubbles: b.draw(screen)
        if show_scroll:
            if scroll_doc_detail is not None:
                draw_doc_detail(screen, scroll_doc_detail, inventory)
            else:
                draw_cult_doc_list(screen, cult_docs)
        if show_bag:
            if inv_detail is not None:
                draw_jelly_detail(screen, inv_detail, inventory)
            else:
                draw_inventory(screen, inventory, inv_page)
        if gacha_slot is not None:
            draw_gacha_screen(screen, gacha_slot, gacha_timer)
            if gacha_timer > 0:
                gacha_timer -= 1
        if unlock_timer > 0:
            draw_unlock_msg(screen, unlock_msg, unlock_timer)
            unlock_timer -= 1
        if item_msg_timer > 0:
            _a2 = 255 if item_msg_timer > 15 else 0
            _fi = get_font(11, bold=True)
            _ti = _fi.render(item_msg, True, (255, 235, 100))
            _ti.set_alpha(_a2)
            screen.blit(_ti, ((AQ_L+AQ_R)//2 - _ti.get_width()//2, AQ_T+8))
            item_msg_timer -= 1
        if acquire_msg_timer > 0:
            _a3 = 255 if acquire_msg_timer > 20 else 0
            _fa = get_font(15, bold=True)
            _ta = _fa.render(acquire_msg, True, (255, 235, 100))
            _ta.set_alpha(_a3)
            screen.blit(_ta, (WIDTH//2 - _ta.get_width()//2, AQ_B - 52))
            acquire_msg_timer -= 1
        if doc_timer > 0:
            draw_unlock_msg(screen, doc_msg, doc_timer,
                            by_override=HEIGHT - 132,
                            text_col=(188, 248, 195),
                            border_col=(70, 180, 100),
                            bg_col=(8, 30, 15),
                            font_size=11)
            doc_timer -= 1

        # ── 슬라이딩 공지 ─────────────────────────────────────────
        if _latest_ver:
            # 업데이트 알림 배너 (스크롤 공지 대신 표시)
            ub = pygame.Surface((WIDTH, 22), pygame.SRCALPHA)
            ub.fill((255, 148, 0, 230))
            screen.blit(ub, (0, 0))
            fu2 = get_font(11, bold=True)
            ut2 = fu2.render(f'새 버전 {_latest_ver} 출시! 클릭해서 다운로드', True, (25, 12, 0))
            screen.blit(ut2, (WIDTH//2 - ut2.get_width()//2, 4))
        elif notice_wait > 0:
            notice_wait -= 1
        else:
            fn_n = get_font(12)
            msg_n = NOTICE_MSGS[notice_idx % len(NOTICE_MSGS)]
            tw_n  = fn_n.render(msg_n, True, (0,0,0)).get_width()
            if notice_x < -tw_n - 20:
                notice_x    = float(WIDTH)
                notice_idx  = random.randrange(len(NOTICE_MSGS))
                notice_wait = 600
            else:
                notice_x -= 1.5
                bar = pygame.Surface((WIDTH, 20), pygame.SRCALPHA)
                bar.fill((5, 10, 30, 175))
                screen.blit(bar, (0, 0))
                nt_s = fn_n.render(msg_n, True, (175, 218, 255))
                screen.blit(nt_s, (int(notice_x), 2))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == '__main__':
    main()
