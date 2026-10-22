
import array
import colorsys
import json
import math
import os
import random
import sys
from collections import deque

import pygame

# ----------------------------------------------------------------------------
# constants
# ----------------------------------------------------------------------------
W, H = 520, 720
FPS = 60
HOR = 235
GROUND = 640
D = 420.0
K = 1.2
CX = W / 2
LANE = 150
FAR = 2600
EYE = (GROUND - HOR) / K
ZONE_LEN = 60000.0           # world units per zone (~1000 m)
ECHO_LEAD = 340.0            # how far in front of you your echo runs
BPM = 112
BEAT = 60 / BPM              # one kick drum
BEAT_WIN = 0.10              # +- seconds that still count as "on the beat"
AUDIO_LAT = 0.03             # small output-latency compensation

GRAV = 2500
JUMP_V = 860
MIN_SPEED, START_SPEED, MAX_SPEED = 520, 640, 1500

CYAN = (80, 235, 255)
PINK = (255, 90, 190)
YELLOW = (255, 214, 70)
WHITE = (240, 240, 255)
GREEN = (120, 255, 170)
RED = (255, 90, 110)
SAVE_PATH = os.path.join(os.path.expanduser("~"), ".neon_runner2.json")

T = {}              # current (blended) theme, filled every frame
CAMX = 0.0          # camera x offset (follows the player a little)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def fog(c, z):
    t = clamp(z / FAR, 0.0, 1.0)
    return mix(c, T["fog"], (t ** 1.4) * 0.92)


def proj(x, y, z):
    s = D / (D + max(z, -D * 0.75))
    return CX + (x - CAMX) * s * K, HOR + (GROUND - HOR) * s - y * s * K, s


_fonts = {}


def font(size):
    f = _fonts.get(size)
    if f is None:
        f = _fonts[size] = pygame.font.Font(None, size)
    return f


_glow = {}


def glow(surf, pos, radius, color, level=1.0):
    r = int(max(4, radius)) // 4 * 4
    lv = clamp(int(level * 8 + 0.5), 1, 8)
    col = tuple(c // 16 * 16 + 8 for c in color)
    key = (r, col, lv)
    sp = _glow.get(key)
    if sp is None:
        if len(_glow) > 700:
            _glow.clear()
        sp = pygame.Surface((r * 2, r * 2))
        for rr in range(r, 0, -3):
            k = (1 - rr / r) ** 2.2 * lv / 8
            pygame.draw.circle(sp, (int(col[0] * k), int(col[1] * k), int(col[2] * k)), (r, r), rr)
        _glow[key] = sp
    surf.blit(sp, (pos[0] - r, pos[1] - r), special_flags=pygame.BLEND_RGB_ADD)


# ----------------------------------------------------------------------------
# themes (zones)
# ----------------------------------------------------------------------------
THEMES = [
    dict(name="SUNSET DRIVE", top=(10, 6, 36), mid=(74, 28, 112), fog=(170, 70, 140), ground=(20, 14, 40),
         sun=((255, 230, 110), (255, 70, 150)), moon=False,
         build=[(34, 28, 74), (44, 30, 82), (28, 36, 84), (52, 30, 70)],
         win=[(255, 205, 120), (120, 230, 255)], edgeL=CYAN, edgeR=PINK,
         road_a=(44, 40, 72), road_b=(52, 46, 84), rain=0.0),
    dict(name="MIDNIGHT CITY", top=(2, 4, 18), mid=(10, 24, 70), fog=(26, 74, 128), ground=(6, 10, 26),
         sun=((235, 240, 255), (150, 170, 220)), moon=True,
         build=[(12, 20, 50), (16, 26, 64), (10, 30, 60), (20, 22, 56)],
         win=[(255, 240, 170), (150, 255, 230)], edgeL=(80, 255, 170), edgeR=(90, 160, 255),
         road_a=(26, 34, 58), road_b=(32, 42, 70), rain=1.0),
    dict(name="TOXIC DAWN", top=(20, 10, 30), mid=(130, 52, 72), fog=(236, 150, 84), ground=(34, 18, 28),
         sun=((255, 250, 170), (255, 150, 60)), moon=False,
         build=[(66, 32, 62), (76, 38, 58), (56, 36, 72), (88, 42, 52)],
         win=[(255, 230, 140), (255, 120, 100)], edgeL=(255, 210, 70), edgeR=(255, 90, 60),
         road_a=(60, 42, 58), road_b=(70, 50, 68), rain=0.0),
    dict(name="THE VOID", top=(2, 0, 8), mid=(34, 4, 44), fog=(96, 12, 74), ground=(6, 2, 10),
         sun=((255, 60, 90), (120, 0, 60)), moon=False,
         build=[(24, 8, 32), (30, 10, 38), (20, 8, 36), (32, 10, 30)],
         win=[(255, 60, 100), (200, 60, 255)], edgeL=(255, 60, 100), edgeR=(190, 90, 255),
         road_a=(24, 14, 34), road_b=(32, 18, 44), rain=0.0),
]


def blend_theme(a, b, t):
    out = {}
    for k, va in a.items():
        vb = b[k]
        if isinstance(va, tuple) and isinstance(va[0], int):
            out[k] = mix(va, vb, t)
        elif isinstance(va, list):
            out[k] = [mix(x, y, t) for x, y in zip(va, vb)]
        elif isinstance(va, float):
            out[k] = lerp(va, vb, t)
        else:
            out[k] = va if t < 0.5 else vb
    return out


T.update(THEMES[0])

# ----------------------------------------------------------------------------
# skins & missions
# ----------------------------------------------------------------------------
SKINS = [
    dict(name="NEON", price=0, body=(255, 70, 160), legs=(40, 40, 110), shoe=(250, 250, 255), cap=(80, 235, 255),
         pack=(255, 214, 70), trail=(255, 90, 190), acc="cap"),
    dict(name="EMBER", price=300, body=(255, 120, 40), legs=(60, 30, 40), shoe=(255, 230, 200), cap=(90, 30, 30),
         pack=(40, 40, 50), trail=(255, 150, 50), acc="hood"),
    dict(name="MINT", price=500, body=(60, 220, 160), legs=(30, 60, 70), shoe=(255, 255, 255), cap=(245, 250, 255),
         pack=(40, 120, 200), trail=(90, 255, 190), acc="phones"),
    dict(name="VOID", price=800, body=(46, 46, 70), legs=(22, 22, 34), shoe=(190, 60, 255), cap=(110, 50, 200),
         pack=(190, 60, 255), trail=(190, 90, 255), acc="antenna"),
    dict(name="GOLD", price=1500, body=(250, 200, 60), legs=(120, 70, 30), shoe=(255, 250, 220), cap=(255, 240, 160),
         pack=(210, 90, 40), trail=(255, 220, 90), acc="cape"),
    dict(name="AURORA", price=2500, rainbow=True, acc="cap"),
]


def skin_palette(i, t):
    sk = SKINS[i]
    if not sk.get("rainbow"):
        return sk

    def hsv(h, s=0.75, v=1.0):
        return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h % 1.0, s, v))

    h = t * 0.2
    return dict(sk, body=hsv(h), legs=(30, 30, 80), shoe=(255, 255, 255), cap=hsv(h + 0.5), pack=hsv(h + 0.25),
                trail=hsv(h + 0.1))


# id, text, target, stat, mode, reward
MISSIONS = [
    ("coins1", "Collect {n} coins", 120, "coins", "sum", 100),
    ("coins2", "Collect {n} coins", 300, "coins", "sum", 220),
    ("dist1", "Run {n} m in total", 2000, "meters", "sum", 100),
    ("run800", "Run {n} m in a single run", 800, "meters", "max", 150),
    ("run1500", "Run {n} m in a single run", 1500, "meters", "max", 320),
    ("close1", "Pull off {n} close calls", 10, "close", "sum", 120),
    ("jump1", "Jump {n} times", 40, "jumps", "sum", 80),
    ("slide1", "Slide {n} times", 30, "slides", "sum", 80),
    ("power1", "Grab {n} power-ups", 6, "powers", "sum", 120),
    ("score1", "Score {n} in a single run", 3000, "score", "max", 200),
    ("jet1", "Fly the jetpack {n} times", 2, "jets", "sum", 150),
    ("rew1", "Rewind time {n} times", 3, "rewinds", "sum", 150),
    ("echo1", "Let your echo smash {n} obstacles", 3, "echo", "sum", 220),
    ("beat1", "Make {n} moves on the beat", 40, "beats", "sum", 150),
    ("beat2", "Reach a beat streak of {n}", 8, "beatmax", "max", 200),
]
MISSION_BY_ID = {m[0]: m for m in MISSIONS}

POWER_COLORS = {"shield": (70, 130, 255), "magnet": (235, 60, 90), "x2": (255, 200, 40), "jet": (255, 130, 40),
                "hourglass": (180, 110, 255)}
POWER_NAMES = {"shield": "SHIELD", "magnet": "MAGNET", "x2": "x2 COINS", "jet": "JETPACK", "hourglass": "REWIND +1"}
MAX_CHARGES = 3
SNAP_FIELDS = ("dist", "speed", "coins", "bonus", "combo", "px", "py", "vy", "lane", "slide_t", "queued_slide",
               "shield", "magnet", "x2", "jet", "invuln", "chase", "gap", "cc_count", "jumps", "slides", "powers",
               "jets_used")
FI = {f: i for i, f in enumerate(SNAP_FIELDS)}

ECHO_PAL = dict(body=(70, 230, 255), legs=(30, 120, 200), shoe=(210, 250, 255), cap=(150, 245, 255),
                pack=(40, 170, 230), skin=(160, 240, 255), acc="cap")
ECHO_PAL_GHOST = dict(ECHO_PAL, body=(255, 90, 190), legs=(160, 40, 120), cap=(255, 140, 220),
                      pack=(200, 60, 160), skin=(255, 160, 220), shoe=(255, 200, 240))


# ----------------------------------------------------------------------------
# audio
# ----------------------------------------------------------------------------
def make_tone(freq, dur, vol=0.25, slide=0.0, noise=0.0):
    n = int(22050 * dur)
    buf = array.array("h")
    for i in range(n):
        t = i / 22050
        env = (1 - i / n) ** 1.5
        v = math.sin(math.tau * (freq + slide * t) * t) * (1 - noise) + (random.random() * 2 - 1) * noise
        buf.append(int(32767 * vol * env * v))
    return pygame.mixer.Sound(buffer=buf.tobytes())


def make_music():
    sr = 22050
    beat = BEAT
    n = int(sr * beat * 16)
    buf = [0.0] * n
    roots = [45, 41, 48, 43]
    chords = [(0, 3, 7), (0, 4, 7), (0, 4, 7), (0, 4, 7)]

    def hz(m):
        return 440 * 2 ** ((m - 69) / 12)

    def add(start, dur, fn):
        s0 = int(start * sr)
        for i in range(int(dur * sr)):
            buf[(s0 + i) % n] += fn(i / sr)

    for bar in range(4):
        root, ch = roots[bar], chords[bar]
        for step in range(8):
            t0 = (bar * 8 + step) * beat / 2
            f = hz(root)
            add(t0, 0.22, lambda t, f=f: (2 * ((f * t) % 1) - 1) * 0.16 * math.exp(-t * 9))
            fa = hz(root + 24 + ch[[0, 1, 2, 1, 0, 2, 1, 2][step] % 3])
            add(t0, 0.26, lambda t, f=fa: (math.sin(math.tau * f * t) + 0.4 * math.sin(math.tau * 2 * f * t))
                * 0.075 * math.exp(-t * 11))
            if step % 2 == 0:
                add(t0, 0.18, lambda t: math.sin(math.tau * (45 + 100 * math.exp(-t * 28)) * t * 1.2) * 0.42
                    * math.exp(-t * 14))
            else:
                add(t0, 0.05, lambda t: (random.random() * 2 - 1) * 0.07 * math.exp(-t * 70))
        if bar % 2 == 1:
            t0 = (bar * 8 + 6) * beat / 2
            add(t0, 0.3, lambda t: (random.random() * 2 - 1) * 0.12 * math.exp(-t * 16))
    peak = max(abs(v) for v in buf) or 1
    out = array.array("h", (int(v / peak * 26000) for v in buf))
    return pygame.mixer.Sound(buffer=out.tobytes())


class Audio:
    def __init__(self):
        self.s = {}
        self.music = None
        self.muted = False
        self.ok = False
        self.t0 = None
        self.loop_len = 1.0
        try:
            try:
                pygame.mixer.init(22050, -16, 1, allowedchanges=0)   # keep the format the synth expects
            except Exception:
                pygame.mixer.init(22050, -16, 1)
            self.s = {
                "coin": make_tone(880, 0.12, 0.18, slide=1800),
                "jump": make_tone(300, 0.18, 0.2, slide=900),
                "slide": make_tone(220, 0.15, 0.15, slide=-300, noise=0.5),
                "hit": make_tone(120, 0.35, 0.35, slide=-200, noise=0.6),
                "shield": make_tone(500, 0.3, 0.25, slide=700),
                "power": make_tone(400, 0.4, 0.22, slide=1400),
                "over": make_tone(200, 0.7, 0.3, slide=-250, noise=0.2),
                "move": make_tone(500, 0.05, 0.08, slide=200),
                "close": make_tone(1100, 0.12, 0.15, slide=900),
                "mission": make_tone(660, 0.5, 0.22, slide=500),
                "rewind": make_tone(1700, 1.4, 0.22, slide=-1500, noise=0.15),
                "freeze": make_tone(160, 0.5, 0.3, slide=-100),
                "shatter": make_tone(90, 0.4, 0.32, slide=-60, noise=0.75),
                "beat": make_tone(1320, 0.05, 0.09, slide=500),
                "echo": make_tone(520, 0.9, 0.2, slide=-380, noise=0.1),
            }
            self.ok = True
        except Exception:
            self.s = {}

    def start_music(self):
        if not self.ok or self.music:
            return
        try:
            self.music = make_music()
            self.music.set_volume(0.0 if self.muted else 0.33)
            self.music.play(loops=-1)
            self.t0 = pygame.time.get_ticks()
            self.loop_len = self.music.get_length()
        except Exception:
            self.music = None

    def beat_clock(self, fallback):
        """Musical time in seconds (keeps counting across loops); falls back to game time."""
        if self.t0 is None or self.loop_len <= 0:
            return fallback
        el = (pygame.time.get_ticks() - self.t0) / 1000 - AUDIO_LAT
        return el * (16 * BEAT / self.loop_len)     # the loop is exactly 16 beats long

    def toggle(self):
        self.muted = not self.muted
        if self.music:
            self.music.set_volume(0.0 if self.muted else 0.33)

    def play(self, name):
        snd = self.s.get(name)
        if snd and not self.muted:
            try:
                snd.play()
            except Exception:
                pass


# ----------------------------------------------------------------------------
# world objects
# ----------------------------------------------------------------------------
class Obj:
    def __init__(self, kind, x, z, y=0, depth=0, half=60, color=None, vel=0):
        self.kind, self.x, self.y, self.z = kind, x, y, z
        self.depth, self.half, self.color, self.vel = depth, half, color, vel
        self.dead = False
        self.mingap, self.clear, self.slid, self.cc_done = 999, 999, False, False


TRAIN_COLORS = [(40, 160, 170), (150, 70, 200), (230, 110, 60), (60, 120, 220), (200, 60, 110)]
_bcache = {}


def bparams(idx, side):
    key = (idx, side)
    p = _bcache.get(key)
    if p is None:
        r = random.Random(idx * 7919 + side * 104729 + 11)
        p = dict(w=r.randint(90, 170), h=r.randint(170, 560), gap=r.randint(0, 30),
                 depth=r.randint(150, 230), ci=r.randrange(4), seed=r.getrandbits(32))
        if len(_bcache) > 600:
            _bcache.clear()
        _bcache[key] = p
    return p


class Button:
    def __init__(self, rect, label, cb, col=CYAN, hint=""):
        self.rect, self.label, self.cb, self.col, self.hint = pygame.Rect(rect), label, cb, col, hint


# ----------------------------------------------------------------------------
# game
# ----------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        try:
            self.screen = pygame.display.set_mode((W, H), pygame.SCALED)
        except Exception:
            self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("NEON RUNNER 2: ECHO")
        self.clock = pygame.time.Clock()
        self.screen.fill((8, 4, 24))
        t = font(40).render("loading...", True, WHITE)
        self.screen.blit(t, t.get_rect(center=(W // 2, H // 2)))
        pygame.display.flip()
        self.audio = Audio()
        self.build_backgrounds()
        self.build_vignette()
        self.save = self.load_save()
        self.audio.muted = self.save.get("mute", False)
        self.audio.start_music()
        self.t = 0.0
        self.beat_ph = 0.5
        self.pulse = 0.0
        self.swipe = None
        self.shop_sel = self.save["skin"]
        self.rain = [[random.uniform(0, W), random.uniform(0, H)] for _ in range(110)]
        self.streaks = [[random.uniform(0, math.tau), random.uniform(0.1, 1.0)] for _ in range(26)]
        self.summary = None
        self.state = "menu"
        self.reset()
        self.set_state("menu")
        self.apply_theme()

    # ---- save -------------------------------------------------------------
    def load_save(self):
        d = dict(bank=0, best=0, owned=[0], skin=0, missions=[], mute=False, runs=0)
        try:
            with open(SAVE_PATH) as f:
                d.update(json.load(f))
        except Exception:
            pass
        d["missions"] = [m for m in d["missions"] if m.get("id") in MISSION_BY_ID][:3]
        while len(d["missions"]) < 3:
            d["missions"].append(self.new_mission([m["id"] for m in d["missions"]]))
        if 0 not in d["owned"]:
            d["owned"].append(0)
        return d

    def write_save(self):
        self.save["mute"] = self.audio.muted
        try:
            with open(SAVE_PATH, "w") as f:
                json.dump(self.save, f)
        except Exception:
            pass

    @staticmethod
    def new_mission(exclude):
        return dict(id=random.choice([m for m in MISSIONS if m[0] not in exclude])[0], p=0)

    # ---- static art -------------------------------------------------------
    def build_backgrounds(self):
        self.bgs, self.skys = [], []
        for th in THEMES:
            bg = pygame.Surface((W, H))
            for y in range(HOR):
                t = y / HOR
                c = mix(th["top"], th["mid"], t / 0.6) if t < 0.6 else mix(th["mid"], th["fog"], (t - 0.6) / 0.4)
                pygame.draw.line(bg, c, (0, y), (W, y))
            for y in range(HOR, H):
                t = min(1.0, (y - HOR) / 260)
                pygame.draw.line(bg, mix(th["fog"], th["ground"], t ** 0.6), (0, y), (W, y))
            rnd = random.Random(5)
            for _ in range(70):
                x, y = rnd.randint(0, W), rnd.randint(0, HOR - 90)
                c = rnd.randint(120, 255)
                bg.set_at((x, y), (c, c, c))
            cx, cy, r = CX, HOR - 52, 78 if not th["moon"] else 46
            if th["moon"]:
                cy = HOR - 120
                pygame.draw.circle(bg, th["sun"][0], (cx + 60, cy), r)
                for ox, oy, rr in ((-14, -8, 9), (10, 12, 6), (14, -16, 5)):
                    pygame.draw.circle(bg, th["sun"][1], (cx + 60 + ox, cy + oy), rr)
            else:
                for yy in range(-r, r):
                    half = int(math.sqrt(r * r - yy * yy))
                    if yy > 8 and ((yy - 8) // 7) % 2 == 0:
                        continue
                    c = mix(th["sun"][0], th["sun"][1], (yy + r) / (2 * r))
                    pygame.draw.line(bg, c, (cx - half, cy + yy), (cx + half, cy + yy))
            self.bgs.append(bg)
            layers = []
            for hmax, k, seed in ((120, 0.55, 1), (70, 0.32, 2)):
                surf = pygame.Surface((W + 160, 140), pygame.SRCALPHA)
                rr = random.Random(seed)
                x = 0
                while x < W + 160:
                    w, h = rr.randint(20, 54), rr.randint(25, hmax)
                    pygame.draw.rect(surf, mix(th["fog"], th["ground"], k + 0.25), (x, 140 - h, w, h))
                    for wy in range(140 - h + 6, 136, 9):
                        for wx in range(x + 4, x + w - 4, 8):
                            if rr.random() < 0.18:
                                pygame.draw.rect(surf, th["win"][0], (wx, wy, 3, 4))
                    x += w + rr.randint(0, 6)
                layers.append(surf)
            self.skys.append(layers)

    def build_vignette(self):
        v = pygame.Surface((W, H), pygame.SRCALPHA)
        for i in range(70):
            a = int(120 * (1 - i / 70) ** 2.2)
            pygame.draw.rect(v, (0, 0, 10, a), (i, i, W - 2 * i, H - 2 * i), 1)
        self.vignette = v
        sc = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(0, H, 4):
            pygame.draw.line(sc, (0, 0, 0, 70), (0, y), (W, y))
        self.scan = sc

    # ---- run state --------------------------------------------------------
    def reset(self):
        self.speed = START_SPEED
        self.dist = 0.0
        self.coins = 0
        self.bonus = 0
        self.combo = 0
        self.lane = 0
        self.px = self.py = self.vy = 0.0
        self.slide_t = 0.0
        self.queued_slide = False
        self.jump_buf = 0.0
        self.shield = False
        self.magnet = self.x2 = self.jet = 0.0
        self.invuln = self.chase = self.shake = self.flash = 0.0
        self.objs, self.parts, self.floats, self.toasts = [], [], [], []
        self.gap = 900
        self.zone = -1
        self.cc_count = self.jumps = self.slides = self.powers = self.jets_used = 0
        self.run_t = 0.0
        self.charges = 1
        self.rewinds = 0
        self.hist = deque(maxlen=90)       # one snapshot every 2 frames = 3 seconds
        self.snap_n = 0
        self.rewinding = False
        self.dying = 0.0                   # >0: frozen "last chance" window
        self.max_zone = 0
        self.rew_fx = 0.0
        self.rng = random.Random(random.getrandbits(32))   # world generator, rewound with time
        self.echo = None
        self.pending_echo = None
        self.echo_breaks = self.echo_coins = 0
        self.rings = []
        self.beat_streak = self.beat_hits = self.beat_best = 0
        self.last_beat = -1

    @property
    def meters(self):
        return int(self.dist / 60)

    @property
    def score(self):
        return self.meters + self.coins * 10 + self.bonus

    def start(self):
        self.reset()
        self.state = "play"
        self.buttons = []

    def finish_run(self):
        sv = self.save
        st = dict(coins=self.coins, meters=self.meters, close=self.cc_count, jumps=self.jumps,
                  slides=self.slides, powers=self.powers, score=self.score, jets=self.jets_used,
                  rewinds=self.rewinds, echo=self.echo_breaks, beats=self.beat_hits,
                  beatmax=self.beat_best)
        sv["bank"] += self.coins
        sv["runs"] += 1
        nb = self.score > sv["best"]
        if nb:
            sv["best"] = self.score
        done, keep = [], []
        for m in sv["missions"]:
            d = MISSION_BY_ID[m["id"]]
            if d[4] == "sum":
                m["p"] += st[d[3]]
            else:
                m["p"] = max(m["p"], st[d[3]])
            if m["p"] >= d[2]:
                sv["bank"] += d[5]
                done.append((d[1].format(n=d[2]), d[5]))
            else:
                keep.append(m)
        while len(keep) < 3:
            keep.append(self.new_mission([m["id"] for m in keep]))
        sv["missions"] = keep
        self.write_save()
        if done:
            self.audio.play("mission")
        return dict(st, done=done, new_best=nb)

    def die(self):
        self.audio.play("over")
        self.shake = 0.5
        self.summary = self.finish_run()
        self.set_state("over")

    # ---- state / buttons ----------------------------------------------------
    def set_state(self, st):
        self.state = st
        b = []
        if st == "menu":
            self.reset()
            b = [Button((W // 2 - 120, 320, 240, 66), "PLAY", self.start, YELLOW, "SPACE"),
                 Button((W // 2 - 120, 400, 116, 52), "SHOP", lambda: self.set_state("shop"), CYAN, "S"),
                 Button((W // 2 + 4, 400, 116, 52), "MISSIONS", lambda: self.set_state("missions"), PINK, "G")]
        elif st == "over":
            b = [Button((W // 2 - 120, 560, 240, 58), "RUN AGAIN", self.start, YELLOW, "SPACE"),
                 Button((W // 2 - 120, 628, 240, 46), "MENU", lambda: self.set_state("menu"), CYAN, "ESC")]
        elif st == "paused":
            b = [Button((W // 2 - 120, 300, 240, 60), "RESUME", lambda: self.set_state_play(), YELLOW, "P"),
                 Button((W // 2 - 120, 374, 240, 50), "QUIT RUN", self.quit_run, RED, "Q")]
        elif st == "shop":
            b = [Button((W // 2 - 110, 650, 220, 52), "BACK", lambda: self.set_state("menu"), CYAN, "ESC")]
        elif st == "missions":
            b = [Button((W // 2 - 110, 650, 220, 52), "BACK", lambda: self.set_state("menu"), CYAN, "ESC")]
        self.buttons = b

    def set_state_play(self):
        self.state = "play"
        self.buttons = []

    def quit_run(self):
        self.summary = self.finish_run()
        self.set_state("menu")

    # ---- spawning ---------------------------------------------------------
    def coin_line(self, lane, z0, n, y=34):
        for i in range(n):
            self.objs.append(Obj("coin", lane * LANE, z0 + i * 80, y=y))

    def arc_coins(self, lane, zc):
        for k in range(-2, 3):
            self.objs.append(Obj("coin", lane * LANE, zc + k * 80, y=25 + 75 * (1 - (k / 2) ** 2)))

    def spawn_row(self):
        R = self.rng
        z = FAR
        lanes = [-1, 0, 1]
        R.shuffle(lanes)
        diff = min(1.0, self.dist / 90000)
        r = R.random()
        extent = 0
        if r < 0.22:
            n = R.randint(6, 10)
            self.coin_line(lanes[0], z, n)
            if R.random() < 0.5:
                kinds = ["shield"] * 3 + ["magnet"] * 3 + ["x2"] * 2 + ["jet"] + ["hourglass"] * 2
                if self.shield:
                    kinds = [k for k in kinds if k != "shield"]
                if self.charges >= MAX_CHARGES:
                    kinds = [k for k in kinds if k != "hourglass"]
                self.objs.append(Obj(R.choice(kinds), lanes[1] * LANE, z + 240, y=60))
            extent = n * 80
        elif r < 0.54 + 0.12 * diff:
            k = 1 if R.random() < 0.6 - 0.2 * diff else 2
            depth = R.choice([320, 480, 640])
            col = R.choice(TRAIN_COLORS)
            vel = 380 if (diff > 0.1 and R.random() < 0.28) else 0
            for l in lanes[:k]:
                self.objs.append(Obj("block", l * LANE, z + (700 if vel else 0), depth=depth, half=62, color=col, vel=vel))
            if k == 1 and not vel and R.random() < 0.7:
                self.coin_line(lanes[1], z, depth // 80)
            extent = depth + (700 if vel else 0)
        else:
            for l in lanes:
                c = R.random()
                if c < 0.40:
                    self.objs.append(Obj("low", l * LANE, z, depth=30, half=58))
                    if R.random() < 0.6:
                        self.arc_coins(l, z + 15)
                elif c < 0.66:
                    self.objs.append(Obj("high", l * LANE, z, depth=14, half=62))
                elif R.random() < 0.3:
                    self.coin_line(l, z, 4)
        self.gap = max(760, self.speed * 0.8, extent + 460)

    # ---- actions ----------------------------------------------------------
    def move_lane(self, d):
        new = clamp(self.lane + d, -1, 1)
        if new != self.lane:
            self.lane = new
            self.audio.play("move")
            self.beat_action()

    def jump(self):
        if self.py <= 0.5 and self.jet <= 0:
            self.beat_action()
        self.jump_buf = 0.14

    def slide(self):
        if self.jet > 0:
            return
        self.beat_action()
        if self.py > 1:
            self.vy = -1500
            self.queued_slide = True
        else:
            self.slide_t = 0.65
            self.slides += 1
            self.audio.play("slide")

    def emit(self, x, y, vx, vy, life, color, grav=500, r=5):
        self.parts.append([x, y, vx, vy, life, color, grav, r, life])

    def burst(self, x, y, color, n=10, speed=240):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(speed * 0.25, speed)
            self.emit(x, y, math.cos(a) * sp, math.sin(a) * sp - 60, random.uniform(0.3, 0.7), color, 500, 6)

    def float_text(self, txt, x, y, color):
        self.floats.append([txt, x, y, 1.1, color])

    # ---- update -----------------------------------------------------------
    def apply_theme(self):
        global CAMX
        zf = self.dist / ZONE_LEN
        i = int(zf)
        t = clamp((zf - i - 0.85) / 0.15, 0.0, 1.0)
        a, b = i % len(THEMES), (i + 1) % len(THEMES)
        T.update(blend_theme(THEMES[a], THEMES[b], t))
        self.bg_idx = (a, b, t)
        if i != self.zone:
            self.zone = i
            if self.state == "play" and not self.rewinding:
                self.toasts.append(["ZONE %d  -  %s" % (i + 1, THEMES[a]["name"]), 3.0])
                if i > self.max_zone:
                    self.max_zone = i
                    if self.charges < MAX_CHARGES:
                        self.charges += 1
                        self.toasts.append(["+1 REWIND CHARGE", 3.0])
        CAMX += (self.px * 0.55 - CAMX) * 0.12

    def update(self, dt):
        self.t += dt
        self.beat_ph = (self.audio.beat_clock(self.t) / BEAT) % 1.0
        self.pulse = max(0.0, 1 - self.beat_ph * 2.6) ** 2
        for rg in self.rings:
            rg[2] += 320 * dt
            rg[3] -= dt
        self.rings = [rg for rg in self.rings if rg[3] > 0]
        for p in self.parts:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += p[6] * dt
            p[4] -= dt
        self.parts = [p for p in self.parts if p[4] > 0]
        for f in self.floats:
            f[2] -= 45 * dt
            f[3] -= dt
        self.floats = [f for f in self.floats if f[3] > 0]
        for tt in self.toasts:
            tt[1] -= dt
        self.toasts = [tt for tt in self.toasts if tt[1] > 0]
        self.shake = max(0.0, self.shake - dt)
        self.flash = max(0.0, self.flash - dt * 2)

        if self.state != "play":
            if self.state in ("menu", "shop", "missions", "over"):
                if self.state != "over":
                    self.dist += 520 * dt
                self.px += (0 - self.px) * min(1.0, 8 * dt)
            if self.state != "paused":
                self.apply_theme()
            return

        if self.dying > 0:                      # frozen last-chance window
            self.dying -= dt
            self.shake = max(self.shake, 0.05)
            if self.dying <= 0:
                self.die()
            return
        if self.rewinding:                      # play history backwards
            self.rew_fx = min(1.0, self.rew_fx + dt * 6)
            if self.hist:
                self.restore(self.hist.pop())
            if not self.hist:
                self.rewinding = False
                self.invuln = max(self.invuln, 1.8)
                self.jump_buf = 0.0
                self.flash = 0.5
                if self.pending_echo:
                    self.echo = dict(rec=self.pending_echo, i=0, t=0.0)
                    self.pending_echo = None
                    self.toasts.append(["ECHO RELEASED", 1.6])
                    self.audio.play("echo")
                else:
                    self.toasts.append(["BACK ON TRACK", 1.2])
            self.apply_theme()
            return
        self.rew_fx = max(0.0, self.rew_fx - dt * 4)
        self.snap_n += 1
        if self.snap_n % 2 == 0:
            self.hist.append(self.snapshot())

        self.run_t += dt
        self.speed = min(MAX_SPEED, self.speed + 7 * dt)
        dz = self.speed * dt * (1.3 if self.jet > 0 else 1.0)
        self.dist += dz
        self.invuln = max(0.0, self.invuln - dt)
        self.chase = max(0.0, self.chase - dt)
        self.magnet = max(0.0, self.magnet - dt)
        self.x2 = max(0.0, self.x2 - dt)
        if self.jet > 0:
            self.jet -= dt
            if self.jet <= 0:
                self.jet = 0.0
                self.invuln = 2.0
                self.toasts.append(["JETPACK OVER", 1.2])

        # player physics
        self.px += (self.lane * LANE - self.px) * min(1.0, 16 * dt)
        self.jump_buf -= dt
        self.slide_t -= dt
        if self.jet > 0:
            self.py += (240 - self.py) * min(1.0, 5 * dt)
            self.vy = 0
            sx, sy, _ = proj(self.px, self.py, 0)
            self.emit(sx + random.uniform(-6, 6), sy + 10, random.uniform(-30, 30), random.uniform(160, 300), 0.35,
                      random.choice([(255, 200, 60), (255, 120, 40)]), 0, 7)
        else:
            if self.jump_buf > 0 and self.py <= 0.5 and self.vy <= 0:
                self.vy, self.py, self.jump_buf, self.slide_t = JUMP_V, 1.0, 0, 0
                self.queued_slide = False
                self.jumps += 1
                self.audio.play("jump")
            if self.py > 0 or self.vy > 0:
                self.vy -= GRAV * dt
                self.py += self.vy * dt
                if self.py <= 0:
                    self.py, self.vy = 0.0, 0.0
                    if self.queued_slide:
                        self.queued_slide = False
                        self.slide_t = 0.65
                        self.slides += 1
                        self.audio.play("slide")
        if self.py < 2 and self.speed > 700 and random.random() < 0.7:
            sx, sy, _ = proj(self.px, 0, 0)
            sk = skin_palette(self.save["skin"], self.t)
            self.emit(sx + random.uniform(-10, 10), sy, random.uniform(-20, 20), 170 + self.speed * 0.15, 0.4,
                      sk["trail"], 0, 4)

        self.gap -= dz
        if self.gap <= 0:
            self.spawn_row()

        head = self.py + (45 if self.slide_t > 0 else 112)
        mid = self.py + (22 if self.slide_t > 0 else 55)
        for o in self.objs:
            o.z -= dz + (o.vel * dt if o.kind == "block" else 0)
            if o.dead:
                continue
            if o.kind == "coin" or o.kind in POWER_COLORS:
                if self.magnet > 0 and o.kind == "coin" and o.z < 1100:
                    o.x += (self.px - o.x) * min(1.0, 6 * dt)
                    o.y += (mid - o.y) * min(1.0, 6 * dt)
                    o.z -= 700 * dt
                if abs(o.x - self.px) < 48 and -30 < o.z < 30 and abs(o.y - mid) < 78:
                    self.collect(o)
                continue
            if self.jet > 0:
                continue
            dxm = abs(o.x - self.px) - (o.half + 22)
            if o.z <= 70 and o.z + o.depth >= -60:
                o.mingap = min(o.mingap, dxm)
                if dxm < 0 and o.kind == "low":
                    o.clear = min(o.clear, self.py - 45)
                if dxm < 0 and o.kind == "high" and self.slide_t > 0:
                    o.slid = True
            if not o.cc_done and o.z + o.depth < -22:
                o.cc_done = True
                if o.kind == "block":
                    close = 0 <= o.mingap < 40
                elif o.kind == "low":
                    close = (o.mingap < 0 and o.clear < 40) or (0 <= o.mingap < 40)
                else:
                    close = (o.mingap < 0 and o.slid) or (0 <= o.mingap < 40)
                if close:
                    self.close_call()
            if dxm > 0 or o.z > 18 or o.z + o.depth < -18:
                continue
            if o.kind == "low":
                hit = self.py < 45
            elif o.kind == "high":
                hit = head > 55 and self.py < 135
            else:
                hit = self.py < 170
            if hit:
                self.on_hit(o)
        self.update_echo(dt)
        self.objs = [o for o in self.objs if not o.dead and o.z + o.depth > -70]
        self.apply_theme()

    # ---- time rewind ------------------------------------------------------
    def snapshot(self):
        return (tuple(getattr(self, f) for f in SNAP_FIELDS),
                [(o, o.z, o.x, o.y, o.dead, o.cc_done, o.mingap, o.clear, o.slid) for o in self.objs],
                self.rng.getstate())

    def restore(self, snap):
        vals, objs, rs = snap
        self.rng.setstate(rs)
        for f, v in zip(SNAP_FIELDS, vals):
            setattr(self, f, v)
        self.objs = []
        for o, z, x, y, dead, cc, mg, cl, sl in objs:
            o.z, o.x, o.y, o.dead, o.cc_done, o.mingap, o.clear, o.slid = z, x, y, dead, cc, mg, cl, sl
            self.objs.append(o)
        self.parts, self.floats = [], []

    def can_rewind(self):
        return self.state == "play" and not self.rewinding and self.charges > 0 and len(self.hist) >= 15

    def begin_rewind(self):
        if not self.can_rewind():
            return
        self.charges -= 1
        self.rewinds += 1
        # the timeline we are about to erase becomes the echo's recording
        self.pending_echo = [(v[FI["dist"]], v[FI["px"]], v[FI["py"]], v[FI["slide_t"]] > 0, v[FI["jet"]] > 0)
                             for v, _, _ in self.hist]
        self.echo = None
        self.rewinding = True
        self.dying = 0.0
        self.flash = 0.7
        self.audio.play("rewind")

    def update_echo(self, dt):
        e = self.echo
        if not e:
            return
        rec = e["rec"]
        e["t"] += dt
        td = self.dist + ECHO_LEAD                     # where the echo is in the old timeline
        if len(rec) < 2 or td >= rec[-1][0]:
            self.echo_end()
            return
        i = e["i"]
        while i < len(rec) - 2 and rec[i + 1][0] <= td:
            i += 1
        e["i"] = i
        a, b = rec[i], rec[i + 1]
        f = clamp((td - a[0]) / max(1e-6, b[0] - a[0]), 0.0, 1.0)
        gx, gy = lerp(a[1], b[1], f), lerp(a[2], b[2], f)
        sl, jet = a[3], a[4]
        e.update(x=gx, y=gy, slide=sl, jet=jet)
        head = gy + (45 if sl else 112)
        mid = gy + (22 if sl else 55)
        for o in self.objs:
            if o.dead or o.kind in POWER_COLORS:
                continue
            if o.kind == "coin":
                if abs(o.x - gx) < 48 and abs(o.z - ECHO_LEAD) < 30 and abs(o.y - mid) < 78:
                    o.dead = True
                    v = 2 if self.x2 > 0 else 1
                    self.coins += v
                    self.echo_coins += v
                    sx, sy, _ = proj(o.x, o.y, o.z)
                    self.burst(sx, sy, CYAN, 4, 120)
                continue
            if jet or abs(o.x - gx) >= o.half + 22:
                continue
            if o.z > ECHO_LEAD + 40 or o.z + o.depth < ECHO_LEAD - 20:
                continue
            if o.kind == "low":
                hit = gy < 45
            elif o.kind == "high":
                hit = head > 55 and gy < 135
            else:
                hit = gy < 170
            if hit:
                self.echo_smash(o)

    def echo_smash(self, o):
        o.dead = True
        o.cc_done = True
        self.echo_breaks += 1
        self.bonus += 50
        zz = max(o.z, 0)
        sx, sy, _ = proj(o.x, 70, zz)
        self.burst(sx, sy, CYAN, 16, 340)
        self.burst(sx, sy, o.color or (255, 140, 60), 14, 280)
        self.rings.append([sx, proj(o.x, 0, zz)[1], 16, 0.5, CYAN])
        self.float_text("ECHO BREAK +50", sx, sy - 40, CYAN)
        self.shake = max(self.shake, 0.15)
        self.audio.play("shatter")

    def echo_end(self):
        """The recording ran out: the echo reached the moment you died. It sacrifices itself."""
        e, self.echo = self.echo, None
        if not e or "x" not in e:
            return
        gx = e["x"]
        n = 0
        for o in self.objs:
            if o.dead or o.kind == "coin" or o.kind in POWER_COLORS:
                continue
            if abs(o.x - gx) < o.half + 40 and o.z + o.depth >= ECHO_LEAD - 60 and o.z <= ECHO_LEAD + 240:
                self.echo_smash(o)
                n += 1
        sx, sy, _ = proj(gx, e["y"] + 60, ECHO_LEAD)
        self.burst(sx, sy, CYAN, 30, 380)
        self.burst(sx, sy, WHITE, 10, 200)
        self.rings.append([sx, proj(gx, 0, ECHO_LEAD)[1], 20, 0.7, CYAN])
        self.flash = max(self.flash, 0.25)
        self.toasts.append(["ECHO SACRIFICED" if n else "ECHO FADED", 1.4])

    def beat_action(self):
        """Called for every real move: lane change, jump, slide."""
        mt = self.audio.beat_clock(self.t)
        idx = round(mt / BEAT)
        if abs(mt - idx * BEAT) > BEAT_WIN:
            if self.beat_streak >= 3:
                sx, sy, _ = proj(self.px, self.py + 150, 0)
                self.float_text("OFF BEAT", sx, sy, (170, 150, 210))
            self.beat_streak = 0
            return
        if idx == self.last_beat:            # one credit per kick
            return
        self.last_beat = idx
        self.beat_streak += 1
        self.beat_hits += 1
        self.beat_best = max(self.beat_best, self.beat_streak)
        self.bonus += 5 * min(self.beat_streak, 10)
        self.audio.play("beat")
        sx, sy, _ = proj(self.px, 0, 0)
        self.rings.append([sx, sy, 12, 0.4, PINK])
        if self.beat_streak % 8 == 0:
            self.audio.play("mission")
            self.flash = max(self.flash, 0.2)
            if self.charges < MAX_CHARGES:
                self.charges += 1
                self.toasts.append(["BEAT FLOW  +1 REWIND", 1.8])
            else:
                self.bonus += 200
                self.toasts.append(["BEAT FLOW  +200", 1.8])

    def collect(self, o):
        o.dead = True
        sx, sy, _ = proj(self.px, self.py + 50, 0)
        if o.kind == "coin":
            v = 2 if self.x2 > 0 else 1
            self.coins += v
            self.audio.play("coin")
            self.burst(sx, sy, YELLOW if v == 1 else (255, 150, 60), 5, 160)
            return
        self.powers += 1
        self.audio.play("power")
        self.flash = 0.35
        self.burst(sx, sy, POWER_COLORS[o.kind], 18, 300)
        self.toasts.append([POWER_NAMES[o.kind] + "!", 1.4])
        if o.kind == "hourglass":
            self.charges = min(MAX_CHARGES, self.charges + 1)
        elif o.kind == "shield":
            self.shield = True
        elif o.kind == "magnet":
            self.magnet = 10.0
        elif o.kind == "x2":
            self.x2 = 15.0
        elif o.kind == "jet" and self.jet <= 0:
            self.jet = 6.0
            self.jets_used += 1
            self.slide_t = 0
            n = int(6.0 * self.speed * 1.3 / 85)
            for i in range(n):
                ln = clamp(int(round(math.sin(i * 0.13) * 1.3)), -1, 1)
                self.objs.append(Obj("coin", ln * LANE, 450 + i * 85, y=292))
            self.gap = max(self.gap, 2600)

    def close_call(self):
        self.combo += 1
        self.cc_count += 1
        pts = 25 + 5 * min(self.combo, 10)
        self.bonus += pts
        self.audio.play("close")
        sx, sy, _ = proj(self.px, self.py + 130, 0)
        self.float_text("CLOSE CALL +%d" % pts, sx, sy, CYAN)

    def on_hit(self, o):
        o.dead = True
        sx, sy, _ = proj(o.x, 60, max(o.z, 0))
        self.burst(sx, sy, (255, 140, 90) if o.kind != "block" else o.color, 22, 320)
        if self.invuln > 0:
            return
        if self.shield:
            self.shield = False
            self.invuln = 1.0
            self.audio.play("shield")
            self.flash = 0.4
            self.toasts.append(["SHIELD BROKE", 1.2])
            return
        self.combo = 0
        self.audio.play("hit")
        self.shake = 0.4
        if self.chase > 0:
            if self.can_rewind():
                self.dying = 1.4            # freeze: last chance to rewind
                self.audio.play("freeze")
            else:
                self.die()
        else:
            self.chase = 7.0
            self.invuln = 1.5
            self.speed = max(MIN_SPEED, self.speed * 0.65)
            self.flash = 0.6

    # ---- drawing primitives ----------------------------------------------
    def box(self, s, x0, x1, y0, y1, z0, z1, col):
        draw_front = z0 >= -60
        z0c = max(z0, -60)
        z1c = max(z1, z0c + 1)

        def P(x, y, z):
            return proj(x, y, z)[:2]

        sx = x1 if x1 <= 0 else (x0 if x0 >= 0 else None)
        if sx is not None:
            pygame.draw.polygon(s, fog(shade(col, 0.62), z0c), [P(sx, y0, z0c), P(sx, y0, z1c), P(sx, y1, z1c), P(sx, y1, z0c)])
        if y1 < EYE:
            pygame.draw.polygon(s, fog(shade(col, 1.3), z0c), [P(x0, y1, z0c), P(x1, y1, z0c), P(x1, y1, z1c), P(x0, y1, z1c)])
        tl, br = P(x0, y1, z0c), P(x1, y0, z0c)
        rect = pygame.Rect(int(tl[0]), int(tl[1]), max(1, int(br[0] - tl[0])), max(1, int(br[1] - tl[1])))
        if draw_front:
            pygame.draw.rect(s, fog(col, z0c), rect)
        else:
            rect.w = 0
        return rect

    def draw_road(self, s):
        def quad(x0, x1, z0, z1, col):
            pygame.draw.polygon(s, col, [proj(x0, 0, z0)[:2], proj(x1, 0, z0)[:2], proj(x1, 0, z1)[:2], proj(x0, 0, z1)[:2]])

        off = self.dist % 200
        k0 = int(self.dist // 200)
        for j in range(-1, FAR // 200 + 2):
            z1 = max(j * 200 - off, -120)
            z2 = j * 200 - off + 200
            if z2 <= -120:
                continue
            idx = k0 + j
            quad(-225, 225, z1, z2, fog(T["road_a"] if idx % 2 == 0 else T["road_b"], z1))
            if idx % 2 == 0:
                for lx in (-75, 75):
                    quad(lx - 3, lx + 3, z1, z2 - 60, fog((190, 190, 240), z1))
        for ex, col in ((-225, T["edgeL"]), (225, T["edgeR"])):
            quad(ex - 6, ex + 6, -120, FAR, mix(col, WHITE, 0.45 * self.pulse))
            for j in range(0, FAR // 400):
                z = j * 400 - self.dist % 400
                if z > 0:
                    gx, gy, gs = proj(ex, 2, z)
                    glow(s, (gx, gy), (26 + 10 * self.pulse) * gs * K + 4, col,
                         (0.35 + 0.6 * self.pulse) * (1 - z / FAR))

    def draw_scenery(self, s):
        step = 260
        off = self.dist % step
        base = int(self.dist // step)
        for j in range(FAR // step + 1, -2, -1):
            z = j * step - off
            idx = base + j
            for side in (-1, 1):
                p = bparams(idx, side)
                if side < 0:
                    x1 = -252 - p["gap"]
                    x0 = x1 - p["w"]
                else:
                    x0 = 252 + p["gap"]
                    x1 = x0 + p["w"]
                fr = self.box(s, x0, x1, 0, p["h"], z, z + p["depth"], T["build"][p["ci"]])
                if fr.w > 14 and z > -55:
                    cols = min(5, max(2, p["w"] // 30))
                    rows = min(14, max(3, p["h"] // 40))
                    cw, rh = fr.w / cols, fr.h / rows
                    for rr in range(rows):
                        for cc in range(cols):
                            if (p["seed"] >> ((rr * cols + cc) % 32)) & 1:
                                col = fog(T["win"][0] if (rr + cc) % 3 else T["win"][1], z)
                                pygame.draw.rect(s, col, (fr.x + cc * cw + cw * 0.25, fr.y + rr * rh + rh * 0.25,
                                                          max(1, cw * 0.5), max(1, rh * 0.45)))
            lz = z + 130
            for side in (-1, 1):
                x = side * 238
                self.box(s, x - 4, x + 4, 0, 130, lz, lz + 8, (70, 70, 110))
                gx, gy, gs = proj(x, 134, lz)
                if gs > 0.05:
                    c = T["edgeL"] if side < 0 else T["edgeR"]
                    pygame.draw.circle(s, fog(c, lz), (gx, gy), max(2, int(7 * gs)))
                    glow(s, (gx, gy), (30 + 16 * self.pulse) * gs + 5, c, 0.45 + 0.5 * self.pulse)

    @staticmethod
    def hourglass_shape(s, cx, cy, r, col):
        a = r * 0.55
        pygame.draw.polygon(s, col, [(cx - a, cy - r * .7), (cx + a, cy - r * .7), (cx, cy)])
        pygame.draw.polygon(s, col, [(cx - a, cy + r * .7), (cx + a, cy + r * .7), (cx, cy)])
        pygame.draw.line(s, col, (cx - a - 1, cy - r * .7), (cx + a + 1, cy - r * .7), max(2, int(r * .18)))
        pygame.draw.line(s, col, (cx - a - 1, cy + r * .7), (cx + a + 1, cy + r * .7), max(2, int(r * .18)))

    def draw_icon(self, s, kind, cx, cy, r, z=0):
        col = POWER_COLORS[kind]
        glow(s, (cx, cy), r * 2.6, col, 0.6)
        pygame.draw.circle(s, fog(shade(col, 0.45), z), (cx, cy), int(r))
        pygame.draw.circle(s, fog(col, z), (cx, cy), int(r), max(2, int(r * 0.14)))
        w = fog(WHITE, z)
        if r < 7:
            return
        if kind == "shield":
            pts = [(cx - r * .45, cy - r * .5), (cx + r * .45, cy - r * .5), (cx + r * .45, cy + r * .05), (cx, cy + r * .6), (cx - r * .45, cy + r * .05)]
            pygame.draw.polygon(s, w, pts)
        elif kind == "magnet":
            w2 = max(2, int(r * 0.26))
            pygame.draw.arc(s, w, (cx - r * .5, cy - r * .55, r, r), 0, math.pi, w2)
            pygame.draw.line(s, w, (cx - r * .5, cy - r * .05), (cx - r * .5, cy + r * .45), w2)
            pygame.draw.line(s, w, (cx + r * .5, cy - r * .05), (cx + r * .5, cy + r * .45), w2)
        elif kind == "hourglass":
            self.hourglass_shape(s, cx, cy, r * 0.8, w)
        elif kind == "x2":
            img = font(max(10, int(r * 1.25))).render("x2", True, (60, 30, 0))
            s.blit(img, img.get_rect(center=(cx, cy)))
        elif kind == "jet":
            pygame.draw.polygon(s, w, [(cx, cy - r * .6), (cx + r * .25, cy + r * .2), (cx - r * .25, cy + r * .2)])
            pygame.draw.polygon(s, fog((255, 200, 60), z), [(cx - r * .15, cy + r * .25), (cx + r * .15, cy + r * .25), (cx, cy + r * .65)])

    def draw_obj(self, s, o):
        z, x = o.z, o.x
        if z + o.depth < -70 or z > FAR:
            return
        if o.kind == "coin":
            sx, sy, sc = proj(x, o.y, z)
            r = 15 * sc * K
            spin = max(0.25, abs(math.cos(self.t * 5 + z * 0.008)))
            col = fog(YELLOW if self.x2 <= 0 else (255, 160, 50), z)
            rect = pygame.Rect(0, 0, max(2, int(r * 2 * spin)), max(2, int(r * 2)))
            rect.center = (sx, sy)
            if sc > 0.3:
                glow(s, (sx, sy), r * 2.2, col, 0.35)
            pygame.draw.ellipse(s, col, rect)
            pygame.draw.ellipse(s, fog((255, 245, 170), z), rect.inflate(-rect.w * 0.5, -rect.h * 0.5))
            pygame.draw.ellipse(s, fog((200, 140, 20), z), rect, 2)
        elif o.kind in POWER_COLORS:
            sx, sy, sc = proj(x, o.y + math.sin(self.t * 4 + z * 0.01) * 6, z)
            self.draw_icon(s, o.kind, sx, sy, 24 * sc * K, z)
        elif o.kind == "block":
            fr = self.box(s, x - 62, x + 62, 0, 170, z, z + o.depth, o.color)
            if z > -55 and fr.w > 6:
                w, h = fr.w, fr.h
                win = pygame.Rect(fr.x + w * 0.1, fr.y + h * 0.14, w * 0.8, h * 0.32)
                pygame.draw.rect(s, fog((18, 20, 40), z), win)
                pygame.draw.rect(s, fog((120, 230, 255), z), (win.x, win.y, win.w, max(1, win.h * 0.2)))
                pygame.draw.rect(s, fog(shade(o.color, 0.6), z), (fr.x, fr.y + h * 0.6, w, h * 0.08))
                lc = (255, 250, 190) if not o.vel else ((255, 60, 60) if int(self.t * 6) % 2 else (255, 210, 80))
                for fx in (0.18, 0.82):
                    c = (fr.x + w * fx, fr.y + h * 0.8)
                    pygame.draw.circle(s, fog(lc, z), c, max(2, int(w * 0.07)))
                    if o.vel and z < 1500:
                        glow(s, c, w * 0.25, lc, 0.6)
                pygame.draw.rect(s, fog(shade(o.color, 0.5), z), fr, max(1, int(w * 0.015)))
        elif o.kind == "low":
            fr = self.box(s, x - 58, x + 58, 0, 45, z, z + o.depth, (255, 140, 40))
            if fr.w > 6:
                n = 8
                for i in range(0, n, 2):
                    pygame.draw.rect(s, fog((30, 20, 40), z), (fr.x + fr.w * i / n, fr.y, fr.w / n + 1, fr.h))
                pygame.draw.rect(s, fog((40, 20, 10), z), fr, max(1, int(fr.w * 0.012)))
        elif o.kind == "high":
            for px_ in (x - 62, x + 50):
                self.box(s, px_, px_ + 12, 0, 135, z, z + o.depth, (100, 100, 140))
            fr = self.box(s, x - 62, x + 62, 58, 100, z, z + o.depth, (230, 50, 90))
            if fr.w > 6:
                n = 8
                for i in range(0, n, 2):
                    pygame.draw.rect(s, fog(YELLOW, z), (fr.x + fr.w * i / n, fr.y, fr.w / n + 1, fr.h))
                pygame.draw.rect(s, fog((60, 10, 30), z), fr, max(1, int(fr.w * 0.012)))

    def draw_runner(self, s, sx, sy, sc, pal, t, mode, lean=0.0):
        u = K * sc
        run = mode == "run"
        bob = abs(math.sin(t * 15)) * 4 if run else 0

        def P(x, y):
            y += bob
            return (sx + (x + lean * (y / 110.0)) * u, sy - y * u)

        def line(a, b, col, w):
            pygame.draw.line(s, col, a, b, max(2, int(w * u)))

        skin = pal.get("skin", (255, 214, 170))
        sw = math.sin(t * 15)
        acc = pal.get("acc", "cap")
        if mode == "slide":
            body = pygame.Rect(0, 0, int(92 * u), int(34 * u))
            body.center = P(0, 20)
            pygame.draw.ellipse(s, pal["body"], body)
            pygame.draw.ellipse(s, shade(pal["body"], 0.7), body, max(1, int(2 * u)))
            line(P(-34, 14), P(-80, 8), pal["legs"], 10)
            pygame.draw.circle(s, pal["shoe"], P(-82, 8), int(7 * u))
            pygame.draw.circle(s, pal["cap"], P(40, 24), int(13 * u))
            line(P(20, 18), P(52, 6), skin, 7)
            return
        if acc == "cape":
            pts = [P(-14, 94), P(14, 94), P(30 + sw * 7, 18), P(-30 + sw * 7, 22)]
            pygame.draw.polygon(s, pal["pack"], pts)
        hip, sho, head = P(0, 48), P(0, 92), P(0, 110)
        for sign in (1, -1):
            ang = sw * sign * 0.85 if run else sign * 0.55
            fx = math.sin(ang) * 40
            fy = max(0, 48 - math.cos(ang) * 44 + (max(0, sw * sign) * 16 if run else 18))
            line(hip, P(fx, fy - bob), pal["legs"], 10)
            pygame.draw.circle(s, pal["shoe"], P(fx, fy - bob + 2), int(7 * u))
        if acc != "cape":
            pygame.draw.rect(s, pal["pack"], pygame.Rect(*P(-13, 86), int(26 * u), int(34 * u)), border_radius=int(5 * u))
        pts = [P(-18, 94), P(18, 94), P(14, 46), P(-14, 46)]
        pygame.draw.polygon(s, pal["body"], pts)
        pygame.draw.polygon(s, shade(pal["body"], 0.68), pts, max(1, int(2 * u)))
        pygame.draw.line(s, shade(pal["body"], 0.7), P(0, 92), P(0, 48), max(1, int(2 * u)))
        for sign in (1, -1):
            if run:
                ang = -sw * sign * 0.9
                hx, hy = math.sin(ang) * 30, 70 - math.cos(ang) * 22
            else:
                hx, hy = sign * 26, 118
            line(P(sign * 16, 90), P(sign * 16 + hx * 0.8, hy), pal["body"], 8)
            pygame.draw.circle(s, skin, P(sign * 16 + hx * 0.8, hy), int(5 * u))
        pygame.draw.rect(s, skin, pygame.Rect(*P(-5, 98), int(10 * u), int(8 * u)))
        if acc == "hood":
            pygame.draw.circle(s, shade(pal["body"], 0.85), head, int(16 * u))
            pygame.draw.line(s, shade(pal["body"], 0.55), (head[0], head[1] - 14 * u), (head[0], head[1] + 8 * u), max(1, int(2 * u)))
        else:
            pygame.draw.circle(s, pal["cap"], head, int(14 * u))
        if acc == "cap":
            pygame.draw.rect(s, shade(pal["cap"], 0.7), pygame.Rect(head[0] - 14 * u, head[1] + 4 * u, 28 * u, 5 * u))
        elif acc == "phones":
            pygame.draw.arc(s, pal["pack"], (head[0] - 16 * u, head[1] - 16 * u, 32 * u, 32 * u), 0.2, math.pi - 0.2, max(2, int(4 * u)))
            for sgn in (-1, 1):
                pygame.draw.circle(s, pal["pack"], (head[0] + sgn * 15 * u, head[1] + 1 * u), int(6 * u))
        elif acc == "antenna":
            tip = (head[0] + sw * 3 * u, head[1] - 30 * u)
            pygame.draw.line(s, pal["shoe"], (head[0], head[1] - 12 * u), tip, max(1, int(2 * u)))
            pygame.draw.circle(s, pal["pack"], tip, int(4 * u))
            if sc > 0.8:
                glow(s, tip, 16 * u, pal["pack"], 0.8)

    def draw_player(self, s):
        sx, sy, _ = proj(self.px, self.py, 0)
        gx, gy, _ = proj(self.px, 0, 0)
        k = max(0.35, 1 - self.py / 260)
        sh = pygame.Surface((90, 24), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 110), sh.get_rect())
        sh = pygame.transform.smoothscale(sh, (int(90 * k), int(24 * k)))
        s.blit(sh, sh.get_rect(center=(gx, gy + 4)))
        if self.invuln > 0 and int(self.t * 16) % 2 == 0:
            return
        mode = "slide" if self.slide_t > 0 else ("jump" if (self.py > 2 or self.jet > 0) else "run")
        lean = clamp((self.lane * LANE - self.px) * 0.15, -18, 18)
        pal = skin_palette(self.save["skin"], self.t)
        if self.jet > 0:
            pygame.draw.rect(s, (90, 90, 110), pygame.Rect(sx - 22 * K, sy - 100 * K, 12 * K, 34 * K), border_radius=4)
            pygame.draw.rect(s, (90, 90, 110), pygame.Rect(sx + 10 * K, sy - 100 * K, 12 * K, 34 * K), border_radius=4)
        self.draw_runner(s, sx, sy, 1.0, pal, self.t, mode, lean)
        if self.shield:
            r = 78
            bub = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pulse = 0.5 + 0.5 * math.sin(self.t * 8)
            pygame.draw.circle(bub, (90, 160, 255, int(50 + 30 * pulse)), (r, r), r)
            pygame.draw.circle(bub, (170, 230, 255, 200), (r, r), r, 3)
            s.blit(bub, (sx - r, sy - 62 * K - r + 20))
        if self.magnet > 0:
            glow(s, (sx, sy - 60), 90 + 10 * math.sin(self.t * 9), (235, 60, 90), 0.35)

    def draw_echo_path(self, cv):
        """Dotted ribbon of the echo's future path + ring where you died in the old timeline."""
        e = self.echo
        if not e or self.state not in ("play", "paused"):
            return
        rec = e["rec"]
        for j in range(e["i"], len(rec), 2):
            d, x, y, _, _ = rec[j]
            z = d - self.dist
            if z < ECHO_LEAD + 30:
                continue
            if z > 1900:
                break
            gx, gy, gs = proj(x, y + 6, z)
            glow(cv, (gx, gy), 10 * gs * K + 5, CYAN, 0.6 * (1 - z / 1900))
        d, x, _, _, _ = rec[-1]
        z = d - self.dist
        if ECHO_LEAD - 40 < z < FAR:
            gx, gy, gs = proj(x, 0, z)
            w = 130 * gs * K
            r = pygame.Rect(0, 0, max(6, int(w)), max(4, int(w * 0.3)))
            r.center = (gx, gy)
            glow(cv, (gx, gy), w * 0.7 + 6, PINK, 0.55)
            pygame.draw.ellipse(cv, fog(PINK if int(self.t * 6) % 2 else WHITE, z), r, max(1, int(3 * gs * K)))

    def draw_echo(self, cv):
        """Your past self: a flickering, scan-lined hologram with a pink chromatic ghost."""
        e = self.echo
        if not e or "x" not in e or self.state not in ("play", "paused"):
            return
        sx, sy, sc = proj(e["x"], e["y"], ECHO_LEAD)
        mode = "slide" if e["slide"] else ("jump" if (e["y"] > 2 or e["jet"]) else "run")
        appear = clamp(e["t"] / 0.35, 0.0, 1.0)
        gw, gh, ax, ay = 200, 240, 100, 225
        glow(cv, (sx, sy - 55 * sc * K), 95 * sc + 20, CYAN, 0.45 * appear)
        for pal, dx, alpha in ((ECHO_PAL_GHOST, 4, 80), (ECHO_PAL, 0, 185)):
            surf = pygame.Surface((gw, gh), pygame.SRCALPHA)
            self.draw_runner(surf, ax, ay, sc, pal, self.t + 0.5, mode)
            for yy in range(int(self.t * 40) % 3, gh, 3):
                pygame.draw.line(surf, (0, 0, 0, 0), (0, yy), (gw, yy))
            surf.set_alpha(int(alpha * appear * (0.78 + 0.22 * math.sin(self.t * 37))))
            cv.blit(surf, (sx - ax + dx, sy - ay))
        if random.random() < 0.12:
            r = pygame.Rect(int(sx - 55), int(sy - random.uniform(10, 120 * sc * K)), 110, random.randint(3, 9))
            r = r.clip(cv.get_rect())
            if r.w > 0 and r.h > 0:
                sl = cv.subsurface(r).copy()
                cv.blit(sl, (r.x + random.randint(-14, 14), r.y))
        tag = font(20).render("ECHO", True, CYAN)
        cv.blit(tag, tag.get_rect(center=(sx, sy - 150 * sc * K)))

    def draw_beat_meter(self, s, y=H - 24):
        cx = W // 2
        ph = self.beat_ph
        base = PINK if self.beat_streak > 0 else (150, 130, 200)
        for k in range(4):
            off = (k + 1 - ph) * 50                       # upcoming kicks slide into the centre
            if off > 180:
                continue
            col = shade(base, 0.3 + 0.7 * clamp(1 - off / 180, 0, 1))
            for sg in (-1, 1):
                x = cx + sg * (off + 16)
                pygame.draw.line(s, col, (x, y - 9), (x, y + 9), 3)
        r = 10 + 8 * self.pulse
        if self.pulse > 0.05:
            glow(s, (cx, y), 36 + 30 * self.pulse, base, 0.15 + 0.4 * self.pulse)
        pts = [(cx, y - r), (cx + r, y), (cx, y + r), (cx - r, y)]
        pygame.draw.polygon(s, mix((40, 30, 80), base, 0.35 + 0.65 * self.pulse), pts)
        pygame.draw.polygon(s, WHITE, pts, 2)
        n = self.beat_streak % 8
        for i in range(8):
            pygame.draw.circle(s, PINK if i < n else (50, 40, 90), (cx - 52 + i * 15, y - 22), 4)
        if self.beat_streak >= 2:
            self.text(s, "BEAT x%d" % self.beat_streak, 26, PINK, (W - 20, 120), right=True)

    def draw_guard(self, s):
        if self.chase <= 0 or self.state not in ("play", "paused"):
            return
        sx = proj(self.px, 0, 0)[0] + math.sin(self.t * 3) * 6
        pal = dict(body=(40, 60, 150), legs=(25, 25, 60), shoe=(20, 20, 30), cap=(30, 40, 110), pack=(20, 20, 20), acc="cap")
        rise = 1.0 - min(1.0, self.chase / 7.0)
        sy = GROUND + 120 - rise * 40
        self.draw_runner(s, sx, sy, 1.35, pal, self.t * 0.9 + 1.3, "run")
        pygame.draw.circle(s, (255, 70, 70), (sx - 8, sy - 150), 3)

    def text(self, s, txt, size, col, pos, center=False, outline=True, right=False):
        f = font(size)
        img = f.render(txt, True, col)
        r = img.get_rect(center=pos) if center else (img.get_rect(topright=pos) if right else img.get_rect(topleft=pos))
        if outline:
            sh = f.render(txt, True, (10, 6, 28))
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (2, 2)):
                s.blit(sh, r.move(dx, dy))
        s.blit(img, r)
        return r

    def panel(self, s, rect, col=(18, 14, 44), border=CYAN, alpha=215, radius=14):
        r = pygame.Rect(rect)
        surf = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(surf, (*col, alpha), surf.get_rect(), border_radius=radius)
        s.blit(surf, r)
        pygame.draw.rect(s, border, r, 2, border_radius=radius)

    # ---- frame ------------------------------------------------------------
    def draw_world(self):
        cv = pygame.Surface((W, H))
        a, b, t = self.bg_idx
        cv.blit(self.bgs[a], (0, 0))
        if t > 0:
            self.bgs[b].set_alpha(int(255 * t))
            cv.blit(self.bgs[b], (0, 0))
        par = CAMX * 0.06
        for layer, mul in ((0, 0.6), (1, 1.0)):
            cv.blit(self.skys[a][layer], (-80 - par * mul, HOR - 138 + layer * 2))
            if t > 0:
                sf = self.skys[b][layer]
                sf.set_alpha(int(255 * t))
                cv.blit(sf, (-80 - par * mul, HOR - 138 + layer * 2))
        self.draw_road(cv)
        self.draw_scenery(cv)
        if self.pulse > 0.05:
            pygame.draw.line(cv, mix(T["fog"], WHITE, 0.7 * self.pulse), (CX - 170, HOR), (CX + 170, HOR), 2)
        self.draw_echo_path(cv)
        front = sorted([o for o in self.objs if o.z > 0], key=lambda o: -o.z)
        behind = sorted([o for o in self.objs if o.z <= 0], key=lambda o: -o.z)
        ghost_done = False
        for o in front:
            if not ghost_done and o.z < ECHO_LEAD:
                self.draw_echo(cv)
                ghost_done = True
            self.draw_obj(cv, o)
        if not ghost_done:
            self.draw_echo(cv)
        for x, y, r, life, col in self.rings:
            rr = pygame.Rect(0, 0, int(r * 2), max(8, int(r * 0.7)))
            rr.center = (int(x), int(y))
            pygame.draw.ellipse(cv, shade(col, clamp(life / 0.4, 0, 1)), rr, 3)
        self.draw_guard(cv)
        self.draw_player(cv)
        for o in behind:
            self.draw_obj(cv, o)
        for x, y, vx, vy, life, col, g, r0, l0 in self.parts:
            rad = max(1, int(r0 * life / l0))
            pygame.draw.circle(cv, col, (int(x), int(y)), rad)
        # rain + speed streaks
        if T["rain"] > 0.05:
            n = int(len(self.rain) * T["rain"])
            c = mix(T["fog"], (200, 220, 255), 0.6)
            for d in self.rain[:n]:
                d[1] += 14
                d[0] -= 2.5
                if d[1] > H:
                    d[0], d[1] = random.uniform(0, W + 40), -20
                pygame.draw.line(cv, c, (d[0], d[1]), (d[0] - 2.5, d[1] + 14), 1)
        fast = clamp((self.speed - 900) / 600, 0, 1) if self.state == "play" else 0
        if self.jet > 0:
            fast = 1.0
        if fast > 0:
            for st in self.streaks:
                st[1] += 0.035 * (0.6 + fast)
                if st[1] > 1.4:
                    st[0], st[1] = random.uniform(0, math.tau), random.uniform(0.05, 0.2)
                ca, sa = math.cos(st[0]), math.sin(st[0]) * 0.8
                r1, r2 = st[1] * 360, st[1] * 360 + 30 * fast + 10
                col = mix(T["fog"], WHITE, 0.6 * fast)
                pygame.draw.line(cv, col, (CX + ca * r1, HOR + 80 + sa * r1), (CX + ca * r2, HOR + 80 + sa * r2), 1)
        if self.rew_fx > 0:
            k = self.rew_fx
            for _ in range(5 if self.rewinding else 1):
                y, h = random.randint(0, H - 40), random.randint(4, 28)
                sl = cv.subsurface((0, y, W, h)).copy()
                cv.blit(sl, (random.randint(-16, 16), y))
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((40, 190, 255, int(70 * k)))
            cv.blit(ov, (0, 0))
            cv.blit(self.scan, (0, 0))
        cv.blit(self.vignette, (0, 0))
        if self.flash > 0:
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((255, 255, 255, int(120 * self.flash)))
            cv.blit(ov, (0, 0))
        if self.chase > 0 and self.state == "play":
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            al = int(60 + 40 * math.sin(self.t * 8)) * (1 if self.chase < 3 else 0.5)
            pygame.draw.rect(ov, (255, 20, 40, int(al)), (0, 0, W, H), 22)
            cv.blit(ov, (0, 0))
        ox = oy = 0
        if self.shake > 0:
            m = int(self.shake * 22)
            ox, oy = random.randint(-m, m), random.randint(-m, m)
        self.screen.fill((0, 0, 0))
        self.screen.blit(cv, (ox, oy))

    def draw_coin_icon(self, s, x, y, r=11):
        pygame.draw.circle(s, YELLOW, (x, y), r)
        pygame.draw.circle(s, (255, 245, 170), (x, y), int(r * 0.5))
        pygame.draw.circle(s, (200, 140, 20), (x, y), r, 2)

    def draw_hud(self):
        s = self.screen
        self.text(s, str(self.score), 72, WHITE, (18, 4))
        self.text(s, "%d m   best %d" % (self.meters, self.save["best"]), 22, (210, 200, 240), (20, 62))
        self.draw_coin_icon(s, W - 28, 26)
        self.text(s, str(self.coins), 38, YELLOW, (W - 48, 10), right=True)
        if self.combo >= 2:
            self.text(s, "COMBO x%d" % self.combo, 24, CYAN, (W - 20, 44), right=True)
        for i in range(MAX_CHARGES):
            cx, cy = W - 26 - i * 32, 98
            on = i < self.charges
            col = POWER_COLORS["hourglass"]
            pygame.draw.circle(s, shade(col, 0.4) if on else (28, 22, 54), (cx, cy), 13)
            pygame.draw.circle(s, col if on else (60, 50, 100), (cx, cy), 13, 2)
            self.hourglass_shape(s, cx, cy, 10, WHITE if on else (80, 70, 120))
            if on and self.rewinds < 1 and self.run_t < 12 and i == 0:
                glow(s, (cx, cy), 36 + 8 * math.sin(self.t * 6), col, 0.5)
        self.text(s, "E", 18, (200, 170, 255), (W - 26 - (MAX_CHARGES - 1) * 32 - 36, 90), outline=False)
        y = 92
        chips = []
        if self.shield:
            chips.append(("shield", 1.0, "READY"))
        if self.magnet > 0:
            chips.append(("magnet", self.magnet / 10, ""))
        if self.x2 > 0:
            chips.append(("x2", self.x2 / 15, ""))
        if self.jet > 0:
            chips.append(("jet", self.jet / 6, ""))
        for kind, frac, _ in chips:
            self.draw_icon(s, kind, 34, y + 14, 13)
            pygame.draw.rect(s, (30, 24, 60), (56, y + 9, 90, 10), border_radius=5)
            pygame.draw.rect(s, POWER_COLORS[kind], (56, y + 9, int(90 * frac), 10), border_radius=5)
            y += 34
        if self.echo and "x" in self.echo:
            rec = self.echo["rec"]
            frac = clamp((rec[-1][0] - self.dist - ECHO_LEAD) / max(1.0, rec[-1][0] - rec[0][0]), 0, 1)
            pygame.draw.circle(s, (20, 60, 80), (34, y + 14), 13)
            pygame.draw.circle(s, CYAN, (34, y + 14), 13, 2)
            self.text(s, "E", 22, CYAN, (34, y + 15), center=True, outline=False)
            pygame.draw.rect(s, (30, 24, 60), (56, y + 9, 90, 10), border_radius=5)
            pygame.draw.rect(s, CYAN, (56, y + 9, int(90 * frac), 10), border_radius=5)
        if self.state == "play" and not self.rewinding and self.dying <= 0:
            self.draw_beat_meter(s)
        if self.chase > 0:
            self.text(s, "GUARD ON YOUR TAIL!", 22, (255, 110, 120), (W // 2, 128), center=True)
            pygame.draw.rect(s, (60, 20, 40), (W // 2 - 70, 142, 140, 8), border_radius=4)
            pygame.draw.rect(s, (255, 80, 100), (W // 2 - 70, 142, int(140 * self.chase / 7.0), 8), border_radius=4)
        for f in self.floats:
            self.text(s, f[0], 24, f[4], (f[1], f[2]), center=True)
        for i, (txt, life) in enumerate(self.toasts[-2:]):
            a = clamp(life / 0.5, 0, 1)
            col = mix((20, 14, 44), WHITE, a)
            self.text(s, txt, 40, col, (W // 2, 190 + i * 40), center=True)
        if self.save["runs"] < 2 and self.run_t < 6 and self.state == "play":
            self.text(s, "LEFT/RIGHT lane  UP jump  DOWN slide  E rewind + echo", 21, (230, 230, 255), (W // 2, 300), center=True)
        if self.rewinding:
            if int(self.t * 8) % 2 == 0:
                self.text(s, "<< REWIND", 64, CYAN, (W // 2, 230), center=True)
            self.text(s, "-%.1fs" % (len(self.hist) * 2 / 60), 34, WHITE, (W // 2, 280), center=True)
        if self.dying > 0:
            frac = self.dying / 1.4
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((60, 10, 90, 110))
            s.blit(ov, (0, 0))
            glow(s, (W // 2, 300), 240, (180, 110, 255), 0.35)
            self.text(s, "REWIND TIME?", 70, WHITE, (W // 2, 250), center=True)
            self.text(s, "press E   (or tap)", 30, (220, 190, 255), (W // 2, 310), center=True)
            self.text(s, "your echo will clear the way", 22, CYAN, (W // 2, 380), center=True)
            pygame.draw.rect(s, (40, 20, 70), (W // 2 - 110, 345, 220, 12), border_radius=6)
            pygame.draw.rect(s, (200, 140, 255), (W // 2 - 110, 345, int(220 * frac), 12), border_radius=6)

    def draw_buttons(self):
        mp = pygame.mouse.get_pos()
        for b in self.buttons:
            hot = b.rect.collidepoint(mp)
            self.panel(self.screen, b.rect, (30, 24, 70) if hot else (16, 12, 40), b.col if hot else shade(b.col, 0.7), 235, 12)
            if hot:
                glow(self.screen, b.rect.center, max(b.rect.w, b.rect.h) * 0.9, b.col, 0.25)
            self.text(self.screen, b.label, 34 if b.rect.h > 56 else 28, WHITE, b.rect.center, center=True, outline=False)
            if b.hint:
                self.text(self.screen, b.hint, 16, shade(b.col, 0.9), (b.rect.right - 8, b.rect.bottom - 16), right=True, outline=False)

    def overlay(self, alpha):
        ov = pygame.Surface((W, H), pygame.SRCALPHA)
        ov.fill((6, 3, 20, alpha))
        self.screen.blit(ov, (0, 0))

    def draw_ui(self):
        s = self.screen
        st = self.state
        if st in ("play", "paused"):
            self.draw_hud()
        if st == "menu":
            self.overlay(80)
            bob = math.sin(self.t * 2) * 4
            glow(s, (W // 2, 160), 220, T["edgeR"], 0.25)
            self.text(s, "NEON", 104, CYAN, (W // 2, 92 + bob), center=True)
            self.text(s, "RUNNER 2", 92, PINK, (W // 2, 160 + bob), center=True)
            self.text(s, "E C H O", 34, mix(CYAN, WHITE, self.pulse), (W // 2 + random.choice((0, 0, 0, 2, -2)), 206 + bob),
                      center=True)
            self.text(s, "rewind  /  echo  /  ride the beat", 24, (225, 215, 255), (W // 2, 248), center=True)
            self.text(s, "best %d" % self.save["best"], 22, (210, 200, 240), (20, 16))
            self.draw_coin_icon(s, W - 28, 26)
            self.text(s, str(self.save["bank"]), 34, YELLOW, (W - 48, 10), right=True)
            self.draw_buttons()
            self.text(s, "M  sound %s     E  rewind + echo     move on the beat!" % ("off" if self.audio.muted else "on"), 18,
                      (190, 180, 225), (W // 2, H - 22), center=True)
            if self.summary and self.summary.get("done"):
                pass
        elif st == "paused":
            self.overlay(150)
            self.text(s, "PAUSED", 80, WHITE, (W // 2, 230), center=True)
            self.draw_buttons()
        elif st == "over":
            self.overlay(165)
            sm = self.summary
            self.text(s, "CAUGHT!", 84, RED, (W // 2, 100), center=True)
            self.text(s, "score %d" % self.score, 52, WHITE, (W // 2, 170), center=True)
            lines = ["%d m    %d coins    %d close calls" % (sm["meters"], sm["coins"], sm["close"])]
            self.text(s, lines[0], 24, (215, 205, 245), (W // 2, 206), center=True)
            self.text(s, "%d echo breaks    beat streak %d" % (sm["echo"], sm["beatmax"]), 24, CYAN,
                      (W // 2, 232), center=True)
            self.text(s, "NEW BEST!" if sm["new_best"] else "best %d" % self.save["best"], 32,
                      YELLOW if sm["new_best"] else (200, 190, 230), (W // 2, 264), center=True)
            y = 296
            self.text(s, "MISSIONS", 24, PINK, (W // 2, y), center=True)
            y += 28
            for d in sm["done"]:
                self.panel(s, (40, y, W - 80, 34), (20, 50, 40), GREEN, 235, 8)
                self.text(s, "DONE  " + d[0], 20, WHITE, (54, y + 9), outline=False)
                self.text(s, "+%d" % d[1], 24, YELLOW, (W - 54, y + 7), right=True, outline=False)
                y += 40
            for m in self.save["missions"]:
                d = MISSION_BY_ID[m["id"]]
                self.panel(s, (40, y, W - 80, 34), (16, 12, 40), (70, 60, 130), 230, 8)
                self.text(s, d[1].format(n=d[2]), 20, (215, 210, 245), (54, y + 9), outline=False)
                self.text(s, "%d / %d" % (min(m["p"], d[2]), d[2]), 20, CYAN, (W - 54, y + 9), right=True, outline=False)
                y += 40
            self.text(s, "bank  %d" % self.save["bank"], 26, YELLOW, (W // 2, 530), center=True)
            self.draw_buttons()
        elif st == "shop":
            self.draw_shop()
        elif st == "missions":
            self.draw_missions()

    def card_rect(self, i):
        col, row = i % 2, i // 2
        return pygame.Rect(18 + col * 252, 92 + row * 184, 232, 170)

    def draw_shop(self):
        s = self.screen
        self.overlay(205)
        self.text(s, "SHOP", 60, CYAN, (20, 14))
        self.draw_coin_icon(s, W - 28, 36)
        self.text(s, str(self.save["bank"]), 38, YELLOW, (W - 48, 20), right=True)
        for i, sk in enumerate(SKINS):
            r = self.card_rect(i)
            owned = i in self.save["owned"]
            equipped = self.save["skin"] == i
            sel = self.shop_sel == i
            border = GREEN if equipped else (CYAN if sel else (80, 70, 150))
            self.panel(s, r, (26, 20, 62) if sel else (16, 12, 40), border, 235, 14)
            if sel:
                glow(s, r.center, 130, border, 0.18)
            pal = skin_palette(i, self.t)
            self.draw_runner(s, r.centerx, r.y + 126, 0.62, pal, self.t + i, "run")
            self.text(s, sk["name"], 26, WHITE, (r.centerx, r.y + 20), center=True)
            if equipped:
                self.text(s, "EQUIPPED", 22, GREEN, (r.centerx, r.bottom - 18), center=True)
            elif owned:
                self.text(s, "OWNED  -  click to equip", 18, CYAN, (r.centerx, r.bottom - 18), center=True)
            else:
                afford = self.save["bank"] >= sk["price"]
                self.draw_coin_icon(s, r.centerx - 30, r.bottom - 18, 9)
                self.text(s, str(sk["price"]), 26, YELLOW if afford else (150, 110, 110), (r.centerx - 16, r.bottom - 30))
        self.draw_buttons()

    def draw_missions(self):
        s = self.screen
        self.overlay(205)
        self.text(s, "MISSIONS", 60, PINK, (20, 14))
        self.draw_coin_icon(s, W - 28, 36)
        self.text(s, str(self.save["bank"]), 38, YELLOW, (W - 48, 20), right=True)
        for i, m in enumerate(self.save["missions"]):
            d = MISSION_BY_ID[m["id"]]
            r = pygame.Rect(18, 100 + i * 128, W - 36, 114)
            self.panel(s, r, (16, 12, 40), (110, 70, 190), 235, 14)
            self.text(s, d[1].format(n=d[2]), 28, WHITE, (r.x + 18, r.y + 16))
            frac = clamp(m["p"] / d[2], 0, 1)
            bar = pygame.Rect(r.x + 18, r.y + 62, r.w - 150, 16)
            pygame.draw.rect(s, (36, 28, 72), bar, border_radius=8)
            pygame.draw.rect(s, PINK, (bar.x, bar.y, int(bar.w * frac), bar.h), border_radius=8)
            self.text(s, "%d / %d" % (min(m["p"], d[2]), d[2]), 20, (215, 205, 245), (bar.x, r.y + 84), outline=False)
            self.draw_coin_icon(s, r.right - 84, r.y + 70, 10)
            self.text(s, "+%d" % d[5], 30, YELLOW, (r.right - 66, r.y + 58))
        self.text(s, "Progress is added when a run ends.", 20, (190, 180, 225), (W // 2, 520), center=True)
        self.text(s, "runs played: %d     best score: %d" % (self.save["runs"], self.save["best"]), 22, (215, 205, 245), (W // 2, 560), center=True)
        self.draw_buttons()

    def draw(self):
        self.draw_world()
        self.draw_ui()
        pygame.display.flip()

    # ---- input ------------------------------------------------------------
    def shop_act(self, i):
        sv = self.save
        self.shop_sel = i
        if i in sv["owned"]:
            sv["skin"] = i
            self.audio.play("move")
        elif sv["bank"] >= SKINS[i]["price"]:
            sv["bank"] -= SKINS[i]["price"]
            sv["owned"].append(i)
            sv["skin"] = i
            self.audio.play("power")
        else:
            self.audio.play("hit")
        self.write_save()

    def handle(self, ev):
        if ev.type == pygame.QUIT:
            self.write_save()
            pygame.quit()
            sys.exit()
        st = self.state
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if st == "play":
                if self.dying > 0:
                    self.begin_rewind()
                    return
                self.swipe = ev.pos
            else:
                for b in self.buttons:
                    if b.rect.collidepoint(ev.pos):
                        b.cb()
                        return
                if st == "shop":
                    for i in range(len(SKINS)):
                        if self.card_rect(i).collidepoint(ev.pos):
                            self.shop_act(i)
        if ev.type == pygame.MOUSEBUTTONUP and self.swipe and st == "play":
            dx, dy = ev.pos[0] - self.swipe[0], ev.pos[1] - self.swipe[1]
            self.swipe = None
            if max(abs(dx), abs(dy)) < 20:
                self.jump()
            elif abs(dx) > abs(dy):
                self.move_lane(1 if dx > 0 else -1)
            elif dy < 0:
                self.jump()
            else:
                self.slide()
        if ev.type != pygame.KEYDOWN:
            return
        k = ev.key
        if k == pygame.K_m:
            self.audio.toggle()
            self.write_save()
            return
        if st == "menu":
            if k in (pygame.K_SPACE, pygame.K_RETURN):
                self.start()
            elif k == pygame.K_s:
                self.set_state("shop")
            elif k == pygame.K_g:
                self.set_state("missions")
            elif k == pygame.K_ESCAPE:
                self.write_save()
                pygame.quit()
                sys.exit()
        elif st == "over":
            if k in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_r):
                self.start()
            elif k == pygame.K_ESCAPE:
                self.set_state("menu")
        elif st == "paused":
            if k in (pygame.K_p, pygame.K_ESCAPE, pygame.K_SPACE):
                self.set_state_play()
            elif k == pygame.K_q:
                self.quit_run()
        elif st == "shop":
            n = len(SKINS)
            if k == pygame.K_ESCAPE:
                self.set_state("menu")
            elif k in (pygame.K_RIGHT, pygame.K_d):
                self.shop_sel = (self.shop_sel + 1) % n
            elif k in (pygame.K_LEFT, pygame.K_a):
                self.shop_sel = (self.shop_sel - 1) % n
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.shop_sel = (self.shop_sel + 2) % n
            elif k in (pygame.K_UP, pygame.K_w):
                self.shop_sel = (self.shop_sel - 2) % n
            elif k in (pygame.K_RETURN, pygame.K_SPACE):
                self.shop_act(self.shop_sel)
        elif st == "missions":
            if k in (pygame.K_ESCAPE, pygame.K_RETURN):
                self.set_state("menu")
        elif st == "play":
            if k in (pygame.K_e, pygame.K_LSHIFT, pygame.K_RSHIFT):
                self.begin_rewind()
                return
            if self.dying > 0 or self.rewinding:
                return
            if k in (pygame.K_p, pygame.K_ESCAPE):
                self.set_state("paused")
            elif k == pygame.K_r:
                self.start()
            elif k in (pygame.K_LEFT, pygame.K_a):
                self.move_lane(-1)
            elif k in (pygame.K_RIGHT, pygame.K_d):
                self.move_lane(1)
            elif k in (pygame.K_UP, pygame.K_w, pygame.K_SPACE):
                self.jump()
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.slide()

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000, 0.04)
            for ev in pygame.event.get():
                self.handle(ev)
            self.update(dt)
            self.draw()


if __name__ == "__main__":
    Game().run()