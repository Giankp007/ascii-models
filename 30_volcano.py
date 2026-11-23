"""
🌋 Volcano - ASCII animation
Part of ASCII Studio: https://github.com/Giankp007/ascii-studio

Stand-alone file, needs only numpy.
  Run:       Ctrl+Alt+N in VS Code (Code Runner)  or  python 30_volcano.py
  Stop:      Ctrl+C (or Esc) in the terminal
  Switch:    while it runs, open another model and press Ctrl+Alt+N again

How it works:
  `volcano(t, u, v, a, cols, rows)` computes a colour image for time t (seconds).
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
# The model: 🌋 Volcano
# =============================================================================
def volcano(t, u, v, a, cols, rows):
    img = (_c(0.05, 0.01, 0.02) * (1 - v)[..., None] + _c(0.45, 0.08, 0.03) * v[..., None]).astype(np.float32)
    _stars(img, t, cols, rows, vmax=0.3, n=60, crosses=False)
    X = (u - 0.5) * a
    smoke = _noise(X * 6, v * 8 + t * 0.6, t * 0.2) * np.clip(1 - np.abs(X) * 2.5, 0, 1) * (v < 0.4)
    img = img * (1 - smoke * 0.7)[..., None] + (smoke * 0.35)[..., None] * _c(0.6, 0.5, 0.5)
    cone = (v > 0.38) & (np.abs(X) < 0.06 + (v - 0.38) * 1.1)
    img[cone] = _c(0.3, 0.18, 0.14) * (0.6 + 0.4 * _noise(u * 25, v * 25, 0))[cone][:, None]
    for k, off in enumerate((-0.25, 0.1, 0.32)):
        lx = 0.02 * off + (v - 0.38) * off + 0.015 * np.sin(v * 30 + k)
        lava = cone & (np.abs(X - lx) < 0.012 + 0.01 * (v - 0.38))
        fl = 0.7 + 0.3 * np.sin(v * 40 - t * 3 + k)
        img[lava] = (_c(1, 0.45, 0.05) * fl[..., None])[lava]
    crater = _dist(u, v, 0.5, 0.39, a)
    img += (np.clip(1 - crater / 0.12, 0, 1) ** 2 * (0.8 + 0.2 * np.sin(t * 7)))[..., None] * _c(1, 0.5, 0.1)
    s = np.mod(PX[:150, 1] * 2 + t, 2.0)
    vx = (PX[:150, 0] - 0.5) * 0.5
    vy = 0.5 + 0.5 * PX[:150, 2]
    pu = 0.5 + vx * s / a
    pv = 0.37 - vy * s + 0.35 * s * s
    _plot(img, pu, pv, _c(1, 0.6, 0.15), np.clip(1 - s / 2, 0, 1))
    return img


# =============================================================================
# Helpers and fixed random values
# =============================================================================
RNG = np.random.default_rng(5)
STARS = RNG.random((300, 3))
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


def _plot(img, us, vs, col, scale=1.0):
    """Punkte (u, v in 0..1) einzeichnen, hellster Wert gewinnt."""
    rows, cols = img.shape[:2]
    us, vs = np.asarray(us), np.asarray(vs)
    ok = (us >= 0) & (us < 1) & (vs >= 0) & (vs < 1)
    ix = (us[ok] * cols).astype(int)
    iy = (vs[ok] * rows).astype(int)
    c = np.asarray(col, np.float32)
    c = c[ok] if c.ndim == 2 else np.broadcast_to(c, (ok.sum(), 3))
    sc = np.asarray(scale, np.float32)
    if sc.ndim:
        c = c * sc[ok][:, None]
    else:
        c = c * sc
    img[iy, ix] = np.maximum(img[iy, ix], c)


RX = np.random.default_rng(23)
PX = RX.random((400, 4))


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
    play(volcano)
