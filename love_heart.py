"""
💌 Love Heart - "I love you" in many languages forms a heart (terminal version)
Part of ASCII Studio: https://github.com/Giankp007/ascii-studio

Stand-alone file, only the Python standard library.
  Run:       Ctrl+Alt+N in VS Code (Code Runner)  or  python love_heart.py
  Stop:      Ctrl+C (or Esc) in the terminal
  Switch:    while it runs, open another model and press Ctrl+Alt+N again

How it works:
  1. Words trace the outline of the heart, starting at the tip and climbing both sides.
  2. Then more words fill the inside wherever they fit without overlapping.
  3. Finally the heart beats: colours pulse and single words sparkle white.
  The heart curve:  x = 16 sin³(a),  y = 13 cos(a) - 5 cos(2a) - 2 cos(3a) - cos(4a)
"""
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
import unicodedata

PHRASES = [
    "I love you", "Ich liebe dich", "Te amo", "Je t'aime", "Ti amo", "Eu te amo", "Te iubesc",
    "Seni seviyorum", "Ik hou van jou", "Jag älskar dig", "Jeg elsker deg", "Kocham cię",
    "Miluji tě", "Szeretlek", "Rakastan sinua", "Σ' αγαπώ", "Я тебя люблю", "Я тебе кохаю",
    "사랑해", "愛してる", "我爱你", "Anh yêu em", "Aku cinta kamu", "Mahal kita", "Nakupenda",
    "Ég elska þig", "Volim te", "Ljubim te", "T'estimo", "Maite zaitut", "Mi amas vin",
    "Ech hun dech gär", "I ha di gärn", "Bon a ti",
]
REDS = [(255, 42, 79), (255, 59, 92), (232, 32, 63), (255, 84, 112), (216, 27, 59), (255, 111, 134)]
FPS = 30


# =============================================================================
# The model: a heart made of words
# =============================================================================
def width_of(text):
    """Terminal cells a text needs (Chinese/Japanese/Korean characters take 2 cells)."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def heart_point(a):
    """Classic heart curve, a goes once around from 0 to 2π."""
    x = 16 * math.sin(a) ** 3
    y = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
    return x, y


OUTLINE = [heart_point(i / 360 * 2 * math.pi) for i in range(360)]


def inside_heart(x, y):
    """Is (x, y) inside the heart curve? (ray casting against the outline polygon)"""
    inside = False
    for (x1, y1), (x2, y2) in zip(OUTLINE, OUTLINE[1:] + OUTLINE[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


class LoveHeart:
    def __init__(self, cols, rows, seed=11):
        self.cols, self.rows = cols, rows
        self.rng = random.Random(seed)
        # fit the heart (32 x 30 units) into the terminal; a character is ~2x as tall as wide
        self.sy = min(rows * 0.9 / 30, cols * 0.9 / 34 / 2)
        self.sx = self.sy * 2
        self.cx, self.cy = cols / 2, rows / 2 - 2.5 * self.sy   # heart spans y = -17 .. 12
        self.taken = [[False] * cols for _ in range(rows)]
        self.words = []          # (row, col, text, colour, born_frame)
        self.frame = 0
        self.outline_step = 0
        self.fill_tries = 0
        self.n_outline = max(10, int(rows * 0.9))

    def to_cell(self, x, y):
        return self.cx + x * self.sx, self.cy - y * self.sy

    def to_heart(self, col, row):
        return (col - self.cx) / self.sx, (self.cy - row) / self.sy

    def place(self, text, col, row, colour, must_be_inside=True):
        w = width_of(text)
        r, c0 = int(round(row)), int(round(col - w / 2))
        if r < 0 or r >= self.rows or c0 < 0 or c0 + w > self.cols:
            return False
        if must_be_inside and not all(inside_heart(*self.to_heart(c, r)) for c in (c0, c0 + w - 1)):
            return False
        lo, hi = max(0, c0 - 1), min(self.cols, c0 + w + 1)   # keep one free cell around words
        if any(self.taken[r][c] for c in range(lo, hi)):
            return False
        for c in range(c0, c0 + w):
            self.taken[r][c] = True
        self.words.append((r, c0, text, colour, self.frame))
        return True

    def step(self):
        rng = self.rng
        if self.outline_step < self.n_outline:              # 1) outline, both sides at once
            k = self.outline_step
            for side in (1, -1):
                a = math.pi + side * (k + 1.0) / (self.n_outline + 0.5) * math.pi
                col, row = self.to_cell(*heart_point(a))
                self.place(rng.choice(PHRASES), col, row, rng.choice(REDS), must_be_inside=False)
            self.outline_step += 1
        elif self.fill_tries < 3000:                         # 2) fill the inside
            for _ in range(40):
                self.fill_tries += 1
                x, y = rng.uniform(-16, 16), rng.uniform(-17, 13)
                if inside_heart(x, y):
                    self.place(rng.choice(PHRASES), *self.to_cell(x, y), rng.choice(REDS))
        self.frame += 1

    def frame_text(self):
        """Builds one frame: every word with its colour (fade in, then heartbeat + sparkle)."""
        f = self.frame
        done = self.fill_tries >= 3000
        beat = math.exp(-((f % 33) / 4.5)) + 0.6 * math.exp(-(((f - 8) % 33) / 4.5))
        out = []
        for r, c, text, (cr, cg, cb), born in self.words:
            k = min(1.0, (f - born) / 9)
            if done:
                k *= 0.62 + 0.38 * beat
            rgb = (int(cr * k), int(cg * k), int(cb * k))
            if done and self.rng.random() < 0.006:
                rgb = (255, 255, 255)
            out.append("\x1b[%d;%dH\x1b[38;2;%d;%d;%dm%s" % (r + 1, c + 1, *rgb, text))
        return "".join(out)


# =============================================================================
# Player: draws the heart in the terminal
# =============================================================================
def terminal_size():
    """Real size of the terminal (ignores stale LINES/COLUMNS environment values)."""
    for fd in (1, 2, 0):
        try:
            return os.get_terminal_size(fd)
        except OSError:
            pass
    return shutil.get_terminal_size((120, 40))


def emit(text):
    """Write to the terminal in chunks. (With `python -u` - which Code Runner uses - Windows
    silently drops everything after ~32 KB of a single write.)"""
    data = text.encode("utf-8")
    fd = sys.stdout.fileno()
    while data:
        n = os.write(fd, data[:16384])
        data = data[n:]


def typed_command(state):
    """VS Code (Ctrl+Alt+N) types the next command, e.g.  python -u "C:/.../03_eye.py",
    into this terminal. Returns that file, "quit" for Esc / q, otherwise None."""
    try:
        import msvcrt
    except ImportError:
        return None
    try:
        while msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch == "\x1b":
                return "quit"
            if ch in "\r\n":
                line, state["typed"] = state["typed"].strip(), ""
                if line.lower() in ("q", "quit", "exit"):
                    return "quit"
                m = re.search(r'"([^"]+\.py)"', line) or re.search(r"(\S+\.py)", line)
                if m and os.path.isfile(m.group(1)):
                    return m.group(1)
            else:
                state["typed"] += ch
    except OSError:
        pass
    return None


def play():
    os.system("")  # turns on ANSI colours on Windows
    old_cp = None
    if os.name == "nt":  # the terminal must read our bytes as UTF-8 (ä, Я, 사랑해 …)
        import ctypes
        old_cp = ctypes.windll.kernel32.GetConsoleOutputCP()
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    emit("\x1b[?1049h\x1b[?25l\x1b[48;2;0;0;0m\x1b[2J")
    state, nxt, heart, size = {"typed": ""}, None, None, None
    try:
        while True:
            t0 = time.time()
            nxt = typed_command(state)
            if nxt:
                break
            width, height = terminal_size()
            if (width, height) != size:      # new size -> start the heart again to fit
                size = (width, height)
                heart = LoveHeart(max(20, width - 1), max(8, height - 1))
                emit("\x1b[0m\x1b[48;2;0;0;0m\x1b[2J")
            heart.step()
            emit(heart.frame_text())
            time.sleep(max(0.0, 1 / FPS - (time.time() - t0)))
    except KeyboardInterrupt:
        pass
    finally:
        emit("\x1b[0m\x1b[?25h\x1b[?1049l")
        if old_cp:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(old_cp)
    if nxt and nxt != "quit":  # another model was started -> switch to it
        sys.exit(subprocess.call([sys.executable, "-u", nxt]))


if __name__ == "__main__":
    play()
