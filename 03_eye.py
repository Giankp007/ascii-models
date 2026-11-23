"""
👁️ Eye - ASCII animation
Part of ASCII Studio: https://github.com/Giankp007/ascii-studio

Stand-alone file, needs only numpy.
  Run:       Ctrl+Alt+N in VS Code (Code Runner)  or  python 03_eye.py
  Stop:      Ctrl+C (or Esc) in the terminal
  Switch:    while it runs, open another model and press Ctrl+Alt+N again

How it works:
  `eye(t, u, v, a, cols, rows)` computes a colour image for time t (seconds).
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
# The model: 👁️ Eye
# =============================================================================
def eye(t, u, v, a, cols, rows):
    """Ein Auge: blinzelt alle paar Sekunden, schaut umher, Pupille atmet."""
    X, Y = (u - 0.5) * a, v - 0.5            # physikalische Koordinaten, Höhe = 1
    s = min(1.0, a / 1.6)                     # in schmalen Fenstern kleiner zeichnen
    img = np.zeros(u.shape + (3,), np.float32)
    # ruhiger, dunkler Hintergrund mit leichtem Schein ums Auge
    glow = np.clip(1 - np.sqrt((X / (0.75 * s)) ** 2 + (Y / 0.55) ** 2), 0, 1)
    img[:] = _c(0.03, 0.015, 0.02) + glow[..., None] ** 2 * _c(0.18, 0.08, 0.05)
    # Blinzeln: alle 4.5 s kurz zu (weich), sonst offen
    ph = np.mod(t, 4.5)
    open_ = 1.0 if ph > 0.32 else abs(np.cos(ph / 0.32 * np.pi))
    W = 0.62 * s                              # halbe Augenbreite
    ex = np.clip(X / W, -1.2, 1.2)
    shape = np.clip(1 - ex ** 2, 0, 1) ** 0.8
    top = -0.30 * s * shape * open_           # oberes Lid (Y nach unten positiv)
    bot = 0.22 * s * shape * max(open_, 0.15)  # unteres Lid
    eye = (Y > top) & (Y < bot) & (np.abs(ex) < 1)
    # Lederhaut: weiss, zu den Ecken leicht rosa/dunkler
    corner = np.clip(np.abs(ex) - 0.55, 0, 1) / 0.45
    sclera = _c(0.95, 0.93, 0.90) * (1 - 0.35 * corner)[..., None] + _c(0.25, 0.05, 0.05) * corner[..., None]
    img[eye] = sclera[eye]
    # Blickrichtung wandert sanft
    lx = 0.16 * s * np.sin(t * 0.55)
    ly = 0.03 * s * np.sin(t * 0.8 + 1.0)
    dx, dy = X - lx, Y - ly
    d = np.sqrt(dx ** 2 + dy ** 2)
    ang = np.arctan2(dy, dx)
    R = 0.19 * s
    rad = np.clip(d / R, 0, 1)
    fibers = 0.75 + 0.25 * np.sin(ang * 46) * np.sin(ang * 13 + 2.0)
    iris_col = (_c(1.0, 0.78, 0.25) * (1 - rad)[..., None] + _c(0.75, 0.32, 0.04) * rad[..., None]) * fibers[..., None]
    iris = eye & (d < R)
    img[iris] = iris_col[iris]
    img[eye & (d < R) & (d > R * 0.9)] = _c(0.3, 0.12, 0.02)      # dunkler Irisrand
    pr = R * (0.36 + 0.06 * np.sin(t * 1.3))                     # Pupille atmet
    img[eye & (d < pr)] = _c(0.01, 0.01, 0.02)
    hl = np.sqrt((dx + R * 0.35) ** 2 + (dy + R * 0.38) ** 2) < R * 0.16
    img[eye & hl] = _c(1, 1, 1)                                  # Lichtreflex
    # Lidränder + Wimpern oben
    lid = (np.abs(Y - top) < 0.018) & (np.abs(ex) < 1)
    img[lid] = _c(0.12, 0.05, 0.03)
    low = (np.abs(Y - bot) < 0.012) & (np.abs(ex) < 0.97)
    img[low] = _c(0.55, 0.3, 0.28)
    lash = (Y < top) & (Y > top - 0.06 * s) & (np.abs(ex) < 0.9) & (np.mod(X * 60 / s, 1.0) < 0.3)
    img[lash] = _c(0.08, 0.04, 0.03)
    return img


# =============================================================================
# Helpers and fixed random values
# =============================================================================
def _c(*rgb):
    return np.array(rgb, np.float32)


R = np.random.default_rng(11)


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
    play(eye)
