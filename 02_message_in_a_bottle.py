"""
🍾 Message in a Bottle - ASCII animation
Part of ASCII Studio: https://github.com/Giankp007/ascii-studio

Stand-alone file, needs only numpy.
  Run:       Ctrl+Alt+N in VS Code (Code Runner)  or  python 02_message_in_a_bottle.py
  Stop:      Ctrl+C (or Esc) in the terminal
  Switch:    while it runs, open another model and press Ctrl+Alt+N again

How it works:
  `message_in_a_bottle(t, u, v, a, cols, rows)` computes a colour image for time t (seconds).
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
# The model: 🍾 Message in a Bottle
# =============================================================================
def message_in_a_bottle(t, u, v, a, cols, rows):
    img = np.zeros(u.shape + (3,), np.float32)
    hz = 0.56
    img[:] = np.stack([0.03 + 0.12 * v, 0.02 + 0.06 * v, 0.08 + 0.18 * v], -1)
    _stars(img, t, cols, rows, vmax=hz - 0.03)
    mx, my = 0.78, 0.2
    d = _dist(u, v, mx, my, a)
    img += (d < 0.06)[..., None] * _c(1.0, 0.85, 0.55) + (np.clip(1 - d / 0.2, 0, 1) ** 3)[..., None] * _c(.4, .25, .15)
    sea = v > hz
    depth = np.clip((v - hz) / (1 - hz), 0, 1)
    w = (np.sin(u * 28 / (0.3 + depth) + t * 1.8 + depth * 25) * 0.5
         + np.sin(u * 61 / (0.3 + depth) - t * 2.6 + depth * 40) * 0.3
         + np.sin(depth * 90 - t * 3) * 0.2)
    water = _c(0.02, 0.18, 0.30) + (0.05 + 0.25 * depth)[..., None] * _c(0.1, 0.5, 0.6) * (0.6 + 0.4 * w)[..., None]
    foam = np.clip((w - 0.55) * 3, 0, 1) * (0.3 + 0.7 * depth)
    water += foam[..., None] * _c(0.6, 0.9, 1.0)
    refl = np.exp(-((u - mx) * a / (0.02 + 0.12 * depth)) ** 2) * np.clip(w + 0.3, 0, 1)
    water += refl[..., None] * _c(1.0, 0.8, 0.5) * 0.9
    img[sea] = water[sea]
    # Flasche schaukelt
    by = 0.62 + 0.015 * np.sin(t * 1.5)
    ang = 0.25 + 0.12 * np.sin(t * 1.1)
    dx, dy = (u - 0.40) * a, v - by
    lx = dx * np.cos(ang) + dy * np.sin(ang)
    ly = -dx * np.sin(ang) + dy * np.cos(ang)
    body = (np.abs(lx) < 0.07) & (ly > -0.10) & (ly < 0.16)
    shoulder = (ly <= -0.10) & (ly > -0.17) & (np.abs(lx) < 0.025 + 0.045 * (ly + 0.17) / 0.07)
    neck = (np.abs(lx) < 0.026) & (ly <= -0.17) & (ly > -0.26)
    cork = (np.abs(lx) < 0.022) & (ly <= -0.26) & (ly > -0.31)
    glass = body | shoulder | neck
    edge = glass & ((np.abs(lx) > 0.055) | (lx < -0.045))
    under = v > hz + 0.06 + 0.01 * np.sin(u * 40 + t * 2)
    gcol = np.where(under[..., None], _c(0.05, 0.35, 0.3), _c(0.15, 0.6, 0.45))
    img[glass] = (img[glass] * 0.35 + gcol[glass])
    img[edge] += _c(0.4, 0.8, 0.6)
    scroll = (np.abs(lx) < 0.035) & (ly > -0.06) & (ly < 0.12)
    img[scroll] = np.where(under[scroll][:, None], _c(0.45, 0.38, 0.22), _c(0.95, 0.85, 0.6))
    img[scroll & (np.abs(np.mod(ly * 60, 1) - 0.5) < 0.12)] *= 0.55  # Schriftzeilen
    img[cork] = _c(0.6, 0.38, 0.18)
    # Glühwürmchen-Funken
    for sx, sy, ph in SPARKS[:40]:
        px = np.mod(sx + 0.03 * np.sin(t * 0.7 + ph * 9), 1)
        py = hz - 0.05 - np.mod(sy * 0.4 + t * 0.03 * (0.5 + ph), 0.45)
        img[int(py * (rows - 1)), int(px * (cols - 1))] = _c(1, 0.7, 0.3) * (0.5 + 0.5 * np.sin(t * 5 + ph * 20))
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
    play(message_in_a_bottle)
