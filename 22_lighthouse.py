"""
🗼 Lighthouse - ASCII animation
Part of ASCII Studio: https://github.com/Giankp007/ascii-studio

Stand-alone file, needs only numpy.
  Run:       Ctrl+Alt+N in VS Code (Code Runner)  or  python 22_lighthouse.py
  Stop:      Ctrl+C (or Esc) in the terminal
  Switch:    while it runs, open another model and press Ctrl+Alt+N again

How it works:
  `lighthouse(t, u, v, a, cols, rows)` computes a colour image for time t (seconds).
  u and v are the position of every character (0..1, left->right, top->bottom),
  a is the aspect ratio (width/height). Returns rows x cols x RGB (0..1).
  The player at the bottom turns it into coloured text characters.
"""
import os
import re
import shutil
import subprocess
import sys
import time

import numpy as np


# =============================================================================
# The model: 🗼 Lighthouse
# =============================================================================
def lighthouse(t, u, v, a, cols, rows):
    img = np.stack([0.02 + 0.04 * v, 0.03 + 0.06 * v, 0.08 + 0.15 * v], -1).astype(np.float32)
    _stars(img, t, cols, rows, vmax=0.6, n=160, crosses=False)
    hz = 0.66
    sea = v > hz
    dep = np.clip((v - hz) / (1 - hz), 0, 1)
    w = np.sin(u * 30 / (0.3 + dep) + t * 1.6 + dep * 25) * 0.5 + np.sin(u * 70 / (0.3 + dep) - t * 2.3) * 0.5
    water = _c(0.02, 0.08, 0.16) + (0.1 + 0.2 * dep)[..., None] * _c(0.1, 0.3, 0.5) * (0.6 + 0.4 * w)[..., None]
    img[sea] = water[sea]
    lx, ly = 0.76, 0.22
    X, Y = (u - lx) * a, v - ly
    rock = ((X / 0.28) ** 2 + ((v - 0.74) / 0.08) ** 2 < 1) & (v > 0.62)
    img[rock] = _c(0.12, 0.11, 0.12) * (0.6 + 0.4 * _noise(u * 30, v * 30, 0))[rock][:, None]
    tw = 0.04 + 0.03 * np.clip((v - 0.25) / 0.43, 0, 1)
    tower = (v > 0.25) & (v < 0.68) & (np.abs(X) < tw)
    stripe = np.mod(v * 11, 1.0) < 0.5
    tcol = np.where(stripe[..., None], _c(0.85, 0.15, 0.15), _c(0.9, 0.9, 0.88))
    img[tower] = (tcol * (0.55 + 0.45 * np.cos(X / tw * 1.2))[..., None])[tower]
    lamp = (v > 0.19) & (v <= 0.25) & (np.abs(X) < 0.035)
    img[lamp] = _c(1, 0.9, 0.5)
    roof = (v > 0.14) & (v <= 0.19) & (np.abs(X) < 0.045 * (v - 0.14) / 0.05)
    img[roof] = _c(0.6, 0.1, 0.1)
    th = t * 1.1
    L = np.cos(th)
    dr = 1.0 if L >= 0 else -1.0
    along = X * dr
    wid = 0.02 + np.clip(along, 0, None) * 0.13
    perp = np.abs(Y - along * 0.04)
    beam = (along > 0.03) & (perp < wid)
    inten = abs(L) * np.exp(-np.clip(along, 0, None) * 0.9) * np.clip(1 - perp / wid, 0, 1) ** 0.7
    img[beam] = img[beam] + (inten[..., None] * _c(1, 0.95, 0.7) * 0.9)[beam]
    flare = (1 - abs(L)) ** 3
    img += (np.clip(1 - np.sqrt(X ** 2 + Y ** 2) / 0.12, 0, 1) ** 2 * flare)[..., None] * _c(1, 0.95, 0.7)
    return img


# =============================================================================
# Helpers and fixed random values
# =============================================================================
RNG = np.random.default_rng(5)
STARS = RNG.random((300, 3))
def _c(*rgb):
    return np.array(rgb, np.float32)


def _noise(x, y, t):
    """günstiges 'Wolken'-Rauschen aus überlagerten Sinuswellen, 0..1"""
    n = (np.sin(x * 1.7 + t * 1.1 + np.sin(y * 2.3 + t * 0.7))
         + 0.6 * np.sin(x * 3.9 - y * 2.1 + t * 1.9)
         + 0.4 * np.sin(y * 5.3 + x * 1.3 - t * 2.7)
         + 0.25 * np.sin(x * 9.1 + y * 7.7 + t * 3.3))
    return n / 4.5 + 0.5


def _stars(img, t, cols, rows, vmax=1.0, n=220, crosses=True):
    for sx, sy, ph in STARS[:n]:
        if sy > vmax:
            continue
        ix, iy = int(sx * (cols - 1)), int(sy * (rows - 1))
        b = 0.15 + 0.75 * max(0.0, np.sin(t * 2 + ph * 30)) ** 3
        img[iy, ix] = np.maximum(img[iy, ix], b)
        if crosses and ph > 0.94:
            L = 3
            sl = slice(max(0, ix - L), ix + L + 1)
            img[iy, sl] = np.maximum(img[iy, sl], b * 0.35)
            sl = slice(max(0, iy - 1), iy + 2)
            img[sl, ix] = np.maximum(img[sl, ix], b * 0.35)
            img[iy, ix] = b


# =============================================================================
# Player: draws the scene as coloured text characters in the terminal
# =============================================================================
CHARS = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"


def to_text(img):
    """Colour image (rows x cols x 3, values 0..1) -> text with 24-bit colours (ANSI)."""
    light = np.clip(img @ np.array([0.299, 0.587, 0.114], np.float32), 0, 1) ** 0.75
    idx = np.minimum((light * len(CHARS)).astype(int), len(CHARS) - 1)
    mx = img.max(axis=2, keepdims=True)
    colour = np.clip(img / np.maximum(mx, 1e-3) * np.maximum(mx, 0.25) * 1.35, 0, 1)
    colour = ((colour * 255).astype(int) // 8 * 8).tolist()
    lines = []
    for y, row in enumerate(idx.tolist()):
        parts, last = [], None
        for x, i in enumerate(row):
            ch = CHARS[i]
            if ch != " ":
                rgb = colour[y][x]
                if rgb != last:
                    parts.append("\x1b[38;2;%d;%d;%dm" % tuple(rgb))
                    last = rgb
            parts.append(ch)
        # every row gets its own cursor position -> no wrapping/newline surprises
        lines.append("\x1b[%d;1H" % (y + 1) + "".join(parts))
    return "".join(lines)


def terminal_size():
    """Real size of the terminal (ignores stale LINES/COLUMNS environment values)."""
    for fd in (1, 2, 0):
        try:
            return os.get_terminal_size(fd)
        except OSError:
            pass
    return shutil.get_terminal_size((120, 40))


def typed_command(state):
    """Reads what is typed into this terminal while the animation runs.
    VS Code (Ctrl+Alt+N) types the next command, e.g.  python -u "C:/.../03_eye.py",
    into this terminal. Returns the path of that file, "quit" for Esc / q, otherwise None."""
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


def emit(text):
    """Write to the terminal in chunks. (With `python -u` – which Code Runner uses – Windows
    silently drops everything after ~32 KB of a single write, so big frames got cut off.)"""
    data = text.encode("utf-8")
    fd = sys.stdout.fileno()
    while data:
        n = os.write(fd, data[:16384])
        data = data[n:]


def play(scene, fps=30):
    os.system("")  # turns on ANSI colours on Windows
    emit("\x1b[?1049h\x1b[?25l\x1b[48;2;10;10;14m\x1b[2J")
    start, state, nxt, size = time.time(), {"typed": ""}, None, None
    try:
        while True:
            t0 = time.time()
            nxt = typed_command(state)
            if nxt:
                break
            width, height = terminal_size()
            cols, rows = max(10, width - 1), max(5, height - 1)
            if (cols, rows) != size:  # terminal was resized -> clear and redraw
                size = (cols, rows)
                emit("\x1b[0m\x1b[48;2;10;10;14m\x1b[2J")
            y, x = np.mgrid[0:rows, 0:cols].astype(np.float32)
            u, v = x / cols, y / rows
            img = np.clip(scene(time.time() - start, u, v, cols / rows * 0.5, cols, rows), 0, 1)
            emit(to_text(img))
            time.sleep(max(0.0, 1 / fps - (time.time() - t0)))
    except KeyboardInterrupt:
        pass
    finally:
        emit("\x1b[0m\x1b[?25h\x1b[?1049l")
    if nxt and nxt != "quit":  # another model was started -> switch to it
        sys.exit(subprocess.call([sys.executable, "-u", nxt]))


if __name__ == "__main__":
    play(lighthouse)
