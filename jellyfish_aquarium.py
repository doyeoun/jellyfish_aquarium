import pygame
import math
import random
import sys
import json
import os
import threading
import urllib.request as _url_req
import webbrowser

VERSION = '1.0.0'
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

def save_game(inventory, stage, cult_docs=None, aquarium=None):
    data = {
        'inventory': {str(k): v for k, v in inventory.items()},
        'stage': stage,
        'cult_docs': {str(k): v for k, v in (cult_docs or {}).items()},
        'aquarium':  list(aquarium or []),
        'bred_slots': list(_bred_slots),
    }
    try:
        with open(SAVE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_game():
    if not os.path.exists(SAVE_PATH):
        return {}, 1, {}, [], set()
    try:
        with open(SAVE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        inv       = {int(k): v for k, v in data.get('inventory', {}).items()}
        stage     = data.get('stage', 1)
        cult_docs = {int(k): v for k, v in data.get('cult_docs', {}).items()}
        aquarium    = [int(x) for x in data.get('aquarium', [])]
        bred_slots  = set(int(x) for x in data.get('bred_slots', []))
        return inv, stage, cult_docs, aquarium, bred_slots
    except Exception:
        return {}, 1, {}, [], set()

try:
    import ctypes
    CTYPES_OK = True
except ImportError:
    CTYPES_OK = False

pygame.init()

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
               '선인장 해파리', '눈사람 해파리', '황금 해파리', '무지개 해파리', '파분 해파리']

# ── 등급 시스템 ───────────────────────────────────────────────
GRADE_ORDER  = ['common', 'uncommon', 'rare', 'epic', 'legendary', 'secret']
GRADE_COLORS = {
    'common':    (55,  125, 250),
    'uncommon':  (72,  190,  72),
    'rare':      (220,  45,  45),
    'epic':      (165,  55, 248),
    'legendary': (255, 158,  12),
    'secret':    (212, 253, 246),
}
GRADE_LABEL = {
    'common':    'COMMON',
    'uncommon':  'UNCOMMON',
    'rare':      'RARE',
    'epic':      'EPIC',
    'legendary': 'LEGENDARY',
    'secret':    'SECRET',
}
SECRET_COLS   = [(253,200,253), (212,253,200), (200,253,246)]
GRADE_WEIGHTS = {'common':20,'uncommon':10,'rare':4,'epic':1.5,'legendary':0.5,'secret':4}

# ── 배양서 데이터 ──────────────────────────────────────────────
CULT_DOC_NAMES = {
    1: '무지개 해파리 배양서',
    2: '파분 해파리 배양서',
}
CULT_DOC_DESCS = {
    1: '영롱한 일곱 빛깔이 담긴 배양서. 무지개 해파리를 교배로 만들 수 있다.',
    2: '파랑과 분홍이 뒤섞인 배양서. 파분 해파리를 교배로 만들 수 있다.',
}
CULT_DOC_RESULT = {
    1: 22,    # → 무지개 해파리
    2: 23,    # → 파분 해파리
}
# (재료 A 슬롯, 재료 B 슬롯)
CULT_DOC_RECIPE = {
    1: (18, 21),  # 저주받은 해파리 + 황금 해파리 → 무지개 해파리
    2: (0,  1),   # 파란 해파리 + 분홍 해파리 → 파분 해파리
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
    u = {0}
    if i.get(0,0)>=5:                            u.add(1)   # 분홍
    if i.get(1,0)>=10:                           u.add(2)   # 개구리모자
    if i.get(2,0)>=6:                            u.add(3)   # 안경
    if i.get(3,0)>=9:                            u.add(4)   # 전기
    if i.get(4,0)>=10:                           u.add(5)   # 고양이
    if i.get(5,0)>=9:                            u.add(6)   # 슬라임
    if i.get(6,0)>=10:                           u.add(7)   # 얼어붙은
    if i.get(7,0)>=5:                            u.add(8)   # 천사
    if i.get(8,0)>=6:                            u.add(9)   # 유령
    if i.get(9,0)>=8:                            u.add(10)  # 털복숭이
    if i.get(10,0)>=7 and i.get(6,0)>=5:        u.add(11)  # 해파리왕
    if i.get(11,0)>=10:                          u.add(12)  # 썩은
    if i.get(12,0)>=3:                           u.add(13)  # 심해
    if i.get(13,0)>=5:                           u.add(14)  # 구름
    if i.get(14,0)>=5:                           u.add(15)  # 화난
    if i.get(15,0)>=6:                           u.add(16)  # 멋쟁이
    if i.get(16,0)>=5:                           u.add(17)  # 토끼
    if i.get(17,0)>=4:                           u.add(18)  # 저주받은
    if i.get(18,0)>=6:                           u.add(19)  # 선인장
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
GACHA_CONFIRM_RECT = pygame.Rect(WIDTH//2 - 52, HEIGHT - 58, 104, 34)
GACHA_TOTAL        = 300

# ── 가방 아이콘 ───────────────────────────────────────────────
BAG_RECT      = pygame.Rect(WIDTH-48,  6, 38, 38)
SCROLL_RECT   = pygame.Rect(WIDTH-48, 50, 38, 38)
AQUARIUM_RECT = pygame.Rect(WIDTH-48, 94, 38, 38)
AQ_L, AQ_R, AQ_T, AQ_B = 18, WIDTH-18, 82, HEIGHT-72
AQUARIUM_ADD_BTN = pygame.Rect(WIDTH//2-52, HEIGHT-46, 104, 30)
AQ_BACK_RECT     = pygame.Rect(15, 12, 75, 28)

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
        self.happy_timer = 0
        self.dance_phase = 0.0

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

    def feed(self):
        self.happy_timer = 120
        self.dance_phase  = 0.0

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        sq = math.cos(self.pulse*0.7)*0.08
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
               else BELL_SPRITES[bi])
        spr = pygame.transform.scale(spr, (bw, bh))
        if self.design_idx == 9: spr.set_alpha(72)
        defn_aq = JELLY_DEFS[bi]
        surf.blit(spr, (x-bw//2, y-bh//2))
        _draw_slot_overlay(surf, self.design_idx, x, y-bh//2+4, bw, bh)

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
                    hs = pygame.Surface((13,13),pygame.SRCALPHA)
                    hpa2 = min(255, int(hpa * 1.6))
                    pygame.draw.circle(hs,(255,90,135,hpa2),(4,4),3)
                    pygame.draw.circle(hs,(255,90,135,hpa2),(9,4),3)
                    pygame.draw.polygon(hs,(255,90,135,hpa2),[(1,6),(12,6),(6,12)])
                    surf.blit(hs,(hpx-6,hpy-6))

        # 촉수
        tc  = JELLY_DEFS[bi]['tc']
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


def draw_aquarium_add_screen(surf, inventory):
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
        cy5 = start_y + CH//2 + row*(CH+5)
        # 카드
        card = pygame.Surface((CW,CH),pygame.SRCALPHA)
        card.fill((18,42,92,195))
        pygame.draw.rect(card,(55,115,200,180),(0,0,CW,CH),1,border_radius=7)
        surf.blit(card,(cx5-CW//2,cy5-CH//2))
        # 스프라이트
        sw5,sh5 = 50,38
        bi5  = _slot_base_idx(slot)
        spr5 = RAINBOW_BELL_SPRITE if slot==22 else BELL_SPRITES[bi5]
        spr5 = pygame.transform.scale(spr5,(sw5,sh5))
        if slot==9: spr5.set_alpha(72)
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
            mspr = RAINBOW_BELL_SPRITE if result_slot==22 else BELL_SPRITES[bi]
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
                   else BELL_SPRITES[bi])
            spr = pygame.transform.scale(spr, (sw, sh))
            if slot == 9:
                spr.set_alpha(72)
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
    return {0:0,1:1,2:0,3:0,4:2,5:0,6:3,7:4,8:5,9:6,10:7,11:8,12:9,13:10,14:11,15:12,16:13,17:14,18:15,19:16,20:17,21:18,22:19,23:20}.get(slot,0)

def _draw_slot_overlay(surf, slot, pcx, pcy, sw, sh):
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
        for k in range(4):
            a=k*math.pi/2+0.4
            sx2=pcx+int(math.cos(a)*sw*0.55); sy2=pcy+sh//2+int(math.sin(a)*sh*0.50)
            ex2=pcx+int(math.cos(a)*sw*0.82); ey2=pcy+sh//2+int(math.sin(a)*sh*0.78)
            pygame.draw.line(surf,(245,215,30),(sx2,sy2),(ex2,ey2),2)
            pygame.draw.circle(surf,(255,255,140),(ex2,ey2),2)
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
        # 팔
        for s16 in (-1,1):
            shx16 = pcx+s16*(sw//2-2); shy16 = pcy+sh//5
            elx16 = pcx+s16*int(sw*0.72); ely16 = shy16+int(sh*0.42)
            hax16 = pcx+s16*int(sw*0.18); hay16 = ely16+int(sh*0.10)
            pygame.draw.line(surf,col16,(shx16,shy16),(elx16,ely16),max(2,sw//14))
            pygame.draw.line(surf,col16,(elx16,ely16),(hax16,hay16),max(2,sw//14))
    # slot 15 (구름 해파리)는 기본 스프라이트 그대로 표시
    elif slot == 13:  # 심해 해파리: 발광 낚싯대 간략 표시
        stalk_y = pcy - sh//2 - 4
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
            if slot == 9:
                spr.set_alpha(72)
            elif slot == 22:
                spr = pygame.transform.scale(RAINBOW_BELL_SPRITE, (sw, sh))
            elif slot == 23:
                spr = pygame.transform.scale(PABUN_BELL_SPRITE, (sw, sh))
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
        if slot == 9:
            spr.set_alpha(72)
        elif slot == 22:
            spr = pygame.transform.scale(RAINBOW_BELL_SPRITE, (sw, sh))
        elif slot == 23:
            spr = pygame.transform.scale(PABUN_BELL_SPRITE, (sw, sh))
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
        self.squish_t    = -1
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
            slots   = sorted(_unlocked_slots | _bred_slots)
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
            elif chosen == 22: base_idx = 19; self.is_rainbow = True
            else:              base_idx = 0
        else:  # DEV_MODE: 등급별 확률
            # ── Common 50% (4종) ────────────────────────────────────
            if   roll < 0.150: base_idx = 0;                   self.design_idx = 0   # 파랑
            elif roll < 0.300: base_idx = 1;                   self.design_idx = 1   # 분홍
            elif roll < 0.400: base_idx = 19;                  self.is_rainbow = True; self.design_idx = 22 # 무지개(임시커먼)
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
            else:               base_idx = 19;                 self.is_rainbow   = True; self.design_idx = 22 # 무지개

        defn = JELLY_DEFS[base_idx]
        self.bell_sprite = BELL_SPRITES[base_idx]
        if self.is_rainbow:
            self.bell_sprite = RAINBOW_BELL_SPRITE
        elif self.design_idx == 23:
            self.bell_sprite = PABUN_BELL_SPRITE
        self.tc = defn['tc']; self.tb = defn['tb']
        self.BH         = len(defn['art'])
        self.body_color = defn['cmap'].get('M', self.tc)  # 눈 가리기용
        sf = random.uniform(0.88, 1.15)
        self.bw0 = max(16, int(W_PIX*defn['ps']*sf))
        self.bh0 = max(8,  int(self.BH*defn['ps']*sf))
        self.th0 = max(4,  int(10*defn['ps']*sf))

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
        if self.is_golden:
            self._update_gold_particles()
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


def make_bg():
    s=pygame.Surface((WIDTH,HEIGHT))
    for y in range(HEIGHT):
        c=lerp_color((3,8,30),(8,38,82),y/HEIGHT)
        pygame.draw.line(s,c,(0,y),(WIDTH,y))
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


# ── 메인 ──────────────────────────────────────────────────────
def main():
    global _current_stage
    bg          = make_bg()
    jellies     = [Jellyfish(scattered=True) for _ in range(7)]
    bubbles     = [Bubble() for _ in range(22)]
    pop_bubbles    = []
    cult_doc_drops = []
    inventory, loaded_stage, cult_docs, saved_aquarium, saved_bred = load_game()
    _bred_slots.update(saved_bred)
    update_unlocked_slots(inventory)
    if not DEV_MODE:
        _current_stage = loaded_stage
    show_bag     = False
    has_new      = False
    show_scroll       = False
    has_new_doc       = False
    scroll_doc_detail = None
    gacha_slot        = None
    gacha_timer       = 0
    show_aquarium      = False
    aquarium_adding    = False
    aquarium_context   = None
    aquarium           = saved_aquarium
    aquarium_fish_list = [AquariumFish(di) for di in saved_aquarium]
    food_pellets       = []
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
                save_game(inventory, _current_stage, cult_docs, aquarium)
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if inv_detail is not None: inv_detail = None
                    elif show_bag: show_bag = False
                    elif aquarium_context is not None: aquarium_context = None
                    elif aquarium_adding: aquarium_adding = False
                    elif show_aquarium:   show_aquarium = False
                    elif gacha_slot is not None: gacha_slot = None; gacha_timer = 0
                    elif scroll_doc_detail is not None: scroll_doc_detail = None
                    elif show_scroll: show_scroll = False
                    elif context: context = None
                    else:
                        save_game(inventory, _current_stage, cult_docs, aquarium)
                        running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos

                if event.button == 1:
                    if _latest_ver and pygame.Rect(0,0,WIDTH,22).collidepoint(mx,my):
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
                                cy5  = sy5 + CH5//2 + row5*(CH5+5)
                                if abs(mx-cx5)<CW5//2 and abs(my-cy5)<CH5//2:
                                    aquarium.append(slot5)
                                    aquarium_fish_list.append(AquariumFish(slot5))
                                    inventory[slot5] = inventory.get(slot5,0) - 1
                                    if len(aquarium) >= 5:
                                        aquarium_adding = False
                                    break
                                pos_i5 += 1
                    elif show_aquarium:
                        if aquarium_context is not None:
                            if aquarium_context.get_feed_rect().collidepoint(mx,my):
                                aquarium_context.fish.feed()
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
                                # 방생: 바다로 보냄 — 발견 기록 유지(0으로 남김)
                                if di_r not in inventory:
                                    inventory[di_r] = 0
                                aquarium_context = None
                            else:
                                aquarium_context = None
                        elif AQ_BACK_RECT.collidepoint(mx, my):
                            show_aquarium = False; aquarium_context = None
                        elif AQUARIUM_ADD_BTN.collidepoint(mx, my) and len(aquarium)<5:
                            aquarium_adding = True
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
                            # 무지개 배양서: 유령(9) 또는 슬라임(6) 해파리 죽일 때 10%
                            if j_killed.design_idx in (6, 9) and cult_docs.get(1,0)==0 and random.random()<0.10:
                                cult_docs[1]=1; has_new_doc=True
                                cult_doc_drops.append(CultDocDrop(j_killed.x, j_killed.y))
                                doc_msg='???배양서를 획득했습니다. 어떤 배양서를 얻었는지 확인해보세요.'
                                doc_timer=180
                                save_game(inventory, _current_stage, cult_docs, aquarium)
                            # 파분 배양서: 분홍 해파리(design_idx=1) 죽일 때 40%
                            if j_killed.design_idx==1 and cult_docs.get(2,0)==0 and random.random()<0.40:
                                cult_docs[2]=1; has_new_doc=True
                                cult_doc_drops.append(CultDocDrop(j_killed.x, j_killed.y))
                                if doc_timer<=0:
                                    doc_msg='???배양서를 획득했습니다. 어떤 배양서를 얻었는지 확인해보세요.'
                                    doc_timer=180
                                save_game(inventory, _current_stage, cult_docs, aquarium)
                            context = None
                        elif context.get_catch_rect().collidepoint(mx, my):
                            j = context.jelly
                            old_unlocked = frozenset(_unlocked_slots)
                            inventory[j.design_idx] = inventory.get(j.design_idx,0)+1
                            has_new = True
                            save_game(inventory, _current_stage, cult_docs, aquarium)
                            # 언락 감지
                            update_unlocked_slots(inventory)
                            new_slots = _unlocked_slots - old_unlocked
                            if new_slots:
                                newest = max(new_slots)
                                unlock_msg   = f'{JELLY_NAMES[newest]}가 출몰하기 시작했어!'
                                unlock_timer = 180
                            for _ in range(random.randint(6,10)):
                                pop_bubbles.append(PopBubble(j.x,j.y))
                            jellies.remove(j)
                            jellies.append(Jellyfish(scattered=False))
                            context = None
                        else:
                            context = None
                    elif BAG_RECT.collidepoint(mx, my):
                        show_bag = True; has_new = False; show_scroll = False
                        context = None; inv_page = 0; inv_detail = None
                    elif SCROLL_RECT.collidepoint(mx, my):
                        show_scroll = True; has_new_doc = False
                        show_bag = False; show_aquarium = False; inv_detail = None; context = None
                    elif AQUARIUM_RECT.collidepoint(mx, my):
                        show_aquarium = True
                        show_bag = False; show_scroll = False; context = None
                    else:
                        for j in jellies:
                            if j.hit_test(mx, my):
                                j.trigger()
                                for _ in range(random.randint(4,7)):
                                    pop_bubbles.append(PopBubble(j.x,j.y))
                                break

                elif event.button == 3:
                    if show_aquarium and not aquarium_adding:
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
        # 어항 물고기 업데이트 (항상)
        for f_obj in aquarium_fish_list: f_obj.update()
        if context and not show_bag and not show_scroll and not show_aquarium: context.draw(screen)
        if show_aquarium:
            if aquarium_adding:
                draw_aquarium_add_screen(screen, inventory)
            else:
                draw_aquarium_screen(screen, aquarium_fish_list)
                # 사료 업데이트/렌더
                food_pellets = [fp for fp in food_pellets if fp.update()]
                for fp in food_pellets: fp.draw(screen)
                # 컨텍스트 메뉴
                if aquarium_context:
                    aquarium_context.draw(screen)
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
