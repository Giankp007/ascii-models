"""
🎄 Winter Night - ASCII animation
Part of ASCII Studio: https://github.com/Giankp007/ascii-studio

Stand-alone file, needs only numpy.
  Run:       Ctrl+Alt+N in VS Code (Code Runner)  or  python 01_winter_night.py
  Stop:      Ctrl+C (or Esc) in the terminal
  Switch:    while it runs, open another model and press Ctrl+Alt+N again

How it works:
  `winter_night(t, u, v, a, cols, rows)` computes a colour image for time t (seconds).
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
# The model: 🎄 Winter Night
# =============================================================================
def winter_night(t, u, v, a, cols, rows):
    img = np.zeros(u.shape + (3,), np.float32)
    img[:] = np.stack([0.02 + 0.05 * v, 0.03 + 0.08 * v, 0.10 + 0.25 * v], -1)
    d = _dist(u, v, 0.18, 0.22, a)
    img += (d < 0.07)[..., None] * _c(0.95, 0.85, 0.45) + (np.clip(1 - d / 0.12, 0, 1) ** 2)[..., None] * _c(.3, .25, .1)
    sky = 0.62 + 0.05 * np.sin(u * 40) + 0.03 * np.sin(u * 97 + 1.3)
    band = (v > sky) & (v < 0.80)
    img[band] = img[band] * 0.3 + _c(0.08, 0.20, 0.55)
    g = v >= 0.80
    img[g] = _c(0.35, 0.45, 0.75) * (0.6 + 0.4 * np.sin(u[g] * 60 + v[g] * 30) ** 2)[:, None]
    cx, top, bot = 0.5, 0.18, 0.84
    half = (v - top) / (bot - top) * 0.44 / a
    tiers = 0.85 + 0.15 * np.mod((v - top) * 9, 1.0)
    tree = (v > top) & (v < bot) & (np.abs(u - cx) < half * tiers)
    img[tree] = _c(0.05, 0.55, 0.12) * (0.7 + 0.3 * np.sin(u[tree] * 90 + v[tree] * 50))[:, None]
    img[(v >= bot) & (v < 0.90) & (np.abs(u - cx) < 0.015)] = _c(0.35, 0.18, 0.05)
    pal = np.array([[1, .2, .2], [1, .85, .2], [.3, .6, 1], [1, 1, 1]], np.float32)
    for lx, ly, ph in LIGHTS:
        yy = top + 0.05 + ly * (bot - top - 0.08)
        xx = cx + (lx * 2 - 1) * (yy - top) / (bot - top) * 0.44 / a * 0.8
        on = 0.5 + 0.5 * np.sin(t * 4 + ph * 20)
        img += (_dist(u, v, xx, yy, a) < 0.018)[..., None] * pal[int(ph * 4) % 4] * on
    d = _dist(u, v, cx, top - 0.01, a)
    img += (np.clip(1 - d / 0.05, 0, 1) ** 1.5)[..., None] * _c(1, .85, .2) * (1.2 + .3 * np.sin(t * 3))
    for gx, gw, colr in ((0.22, 0.07, (.8, .1, .1)), (0.30, 0.05, (.9, .75, .1)),
                         (0.68, 0.08, (.8, .1, .15)), (0.78, 0.05, (.85, .85, .9))):
        box = (np.abs(u - gx) < gw) & (v > 0.80) & (v < 0.93)
        img[box] = colr
        img[box & ((np.abs(u - gx) < 0.006) | (np.abs(v - 0.865) < 0.008))] = (1, .9, .3)
    sx = np.mod(SNOW[:, 0] + 0.02 * np.sin(t + SNOW[:, 2] * 6), 1)
    sy = np.mod(SNOW[:, 1] + t * (0.03 + 0.06 * SNOW[:, 2]), 1)
    ix = np.clip((sx * cols).astype(int), 0, cols - 1)
    iy = np.clip((sy * rows).astype(int), 0, rows - 1)
    img[iy, ix] = np.maximum(img[iy, ix], 0.35 + 0.45 * SNOW[:, 2:3])
    return img


# =============================================================================
# Helpers and fixed random values
# =============================================================================
RNG = np.random.default_rng(5)
SNOW = RNG.random((320, 3))
LIGHTS = RNG.random((90, 3))
def _c(*rgb):
    return np.array(rgb, np.float32)


def _dist(u, v, cx, cy, a):
    return np.sqrt(((u - cx) * a) ** 2 + (v - cy) ** 2)


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
    play(winter_night)
