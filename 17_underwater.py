"""
🐠 Underwater - ASCII animation
Part of ASCII Studio: https://github.com/Giankp007/ascii-studio

Stand-alone file, needs only numpy.
  Run:       Ctrl+Alt+N in VS Code (Code Runner)  or  python 17_underwater.py
  Stop:      Ctrl+C (or Esc) in the terminal
  Switch:    while it runs, open another model and press Ctrl+Alt+N again

How it works:
  `underwater(t, u, v, a, cols, rows)` computes a colour image for time t (seconds).
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
# The model: 🐠 Underwater
# =============================================================================
def underwater(t, u, v, a, cols, rows):
    img = (_c(0.0, 0.35, 0.5) * (1 - v)[..., None] + _c(0.0, 0.05, 0.15) * v[..., None]).astype(np.float32)
    rays = np.clip(np.sin(u * 22 + v * 7 + np.sin(t * 0.5) * 2) * 0.5 + 0.5, 0, 1) ** 6 * (1 - v) * 0.4
    img += rays[..., None] * _c(0.4, 0.8, 0.9)
    surf = v < 0.04
    img[surf] = _c(0.5, 0.9, 1.0) * (0.5 + 0.5 * np.sin(u[surf] * 60 + t * 3))[:, None]
    sand = v > 0.88 + 0.02 * np.sin(u * 20)
    img[sand] = _c(0.7, 0.6, 0.38) * (0.6 + 0.4 * _noise(u * 40, v * 40, 0))[sand][:, None]
    for i, (sx, sh, ph) in enumerate(SEAWEED):
        x = sx + 0.02 * np.sin(v * 10 + t * 1.5 + ph * 6) * (1 - v)
        m = (np.abs(u - x) * cols < 1.2) & (v > 0.92 - 0.35 * sh)
        img[m] = _c(0.1, 0.6 + 0.3 * ph, 0.25)
    X, Y = u * a, v
    pal = [_c(1, 0.55, 0.1), _c(1, 0.85, 0.2), _c(0.3, 0.6, 1), _c(1, 0.3, 0.4)]
    for i, (f0, fy, sp, c) in enumerate(FISH):
        d = 1 if i % 2 == 0 else -1
        xf = (np.mod(f0 + d * t * (0.04 + 0.05 * sp), 1.4) - 0.2) * a
        yf = 0.2 + 0.6 * fy + 0.02 * np.sin(t * 2 + i)
        body = ((X - xf) / 0.06) ** 2 + ((Y - yf) / 0.028) ** 2 < 1
        bx = (X - xf) * d
        tail = (bx < -0.05) & (bx > -0.09) & (np.abs(Y - yf) < (-bx - 0.045) * 0.7)
        col = pal[int(c * 4) % 4]
        img[body | tail] = col
        eye = ((X - xf - d * 0.035) / 0.008) ** 2 + ((Y - yf + 0.005) / 0.008) ** 2 < 1
        img[eye] = 0.02
    life = np.mod(P1[:70, 1] + t * (0.05 + 0.08 * P1[:70, 2]), 1)
    _plot(img, P1[:70, 0] + 0.01 * np.sin(t * 3 + P1[:70, 3] * 9), 0.9 - life * 0.9, _c(0.7, 0.95, 1), 0.8)
    return img


# =============================================================================
# Helpers and fixed random values
# =============================================================================
def _c(*rgb):
    return np.array(rgb, np.float32)


def _noise(x, y, t):
    """günstiges 'Wolken'-Rauschen aus überlagerten Sinuswellen, 0..1"""
    n = (np.sin(x * 1.7 + t * 1.1 + np.sin(y * 2.3 + t * 0.7))
         + 0.6 * np.sin(x * 3.9 - y * 2.1 + t * 1.9)
         + 0.4 * np.sin(y * 5.3 + x * 1.3 - t * 2.7)
         + 0.25 * np.sin(x * 9.1 + y * 7.7 + t * 3.3))
    return n / 4.5 + 0.5


R = np.random.default_rng(11)
P1 = R.random((700, 4))
SEAWEED = R.random((10, 3))
FISH = R.random((6, 4))
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
    play(underwater)
