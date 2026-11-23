"""
🔥 Campfire - ASCII animation
Part of ASCII Studio: https://github.com/Giankp007/ascii-studio

Stand-alone file, needs only numpy.
  Run:       Ctrl+Alt+N in VS Code (Code Runner)  or  python 05_campfire.py
  Stop:      Ctrl+C (or Esc) in the terminal
  Switch:    while it runs, open another model and press Ctrl+Alt+N again

How it works:
  `campfire(t, u, v, a, cols, rows)` computes a colour image for time t (seconds).
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
# The model: 🔥 Campfire
# =============================================================================
def campfire(t, u, v, a, cols, rows):
    img = np.zeros(u.shape + (3,), np.float32)
    img[:] = _c(0.02, 0.015, 0.03)
    _stars(img, t, cols, rows, vmax=0.5, n=120, crosses=False)
    base = 0.82
    h = (base - v) / 0.6
    wob = 0.03 * np.sin(v * 25 - t * 6) * h
    width = 0.17 * np.clip(1 - h, 0, 1) ** 0.7
    dx = np.abs((u - 0.5) * a + wob)
    shape = np.clip(1 - dx / np.maximum(width, 1e-3), 0, 1) * ((h > 0) & (h < 1))
    n = _noise(u * 18, v * 12 + t * 4, t * 2)
    heat = np.clip(shape * (0.5 + 0.8 * n) * (1.1 - h * 0.6), 0, 1.2)
    img += np.stack([np.clip(heat * 2.2, 0, 1), np.clip(heat * 2.2 - 0.7, 0, 1), np.clip(heat * 2.5 - 1.8, 0, 1)], -1)
    # Glühen am Boden
    g = np.clip(1 - _dist(u, v, 0.5, base, a) / 0.45, 0, 1) ** 2 * (v > base - 0.02)
    img += g[..., None] * _c(0.6, 0.25, 0.05) * (0.85 + 0.15 * np.sin(t * 9))
    # Holzscheite
    for k in (-1, 1):
        lx = (u - 0.5) * a
        ly = v - (base + 0.04)
        rot = ly - k * 0.35 * lx
        log = (np.abs(rot) < 0.025) & (np.abs(lx) < 0.2)
        img[log] = _c(0.35, 0.18, 0.07) + _c(0.4, 0.1, 0) * (np.abs(lx[log]) < 0.08)[:, None]
    # Funken steigen auf
    for sx, sy, ph in SPARKS:
        life = np.mod(t * (0.25 + 0.3 * ph) + sy, 1)
        py = base - 0.1 - life * 0.75
        px = 0.5 + ((sx - 0.5) * 0.25 + 0.05 * np.sin(t * 2 + ph * 10)) / a
        if 0 < py < 1 and 0 < px < 1:
            img[int(py * (rows - 1)), int(px * (cols - 1))] = _c(1, 0.6, 0.15) * (1 - life)
    return img


# =============================================================================
# Helpers and fixed random values
# =============================================================================
RNG = np.random.default_rng(5)
STARS = RNG.random((300, 3))
SPARKS = RNG.random((120, 3))
def _c(*rgb):
    return np.array(rgb, np.float32)


def _dist(u, v, cx, cy, a):
    return np.sqrt(((u - cx) * a) ** 2 + (v - cy) ** 2)


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
    play(campfire)
