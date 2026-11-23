"""
🫧 Lava Lamp - ASCII animation
Part of ASCII Studio: https://github.com/Giankp007/ascii-studio

Stand-alone file, needs only numpy.
  Run:       Ctrl+Alt+N in VS Code (Code Runner)  or  python 16_lava_lamp.py
  Stop:      Ctrl+C (or Esc) in the terminal
  Switch:    while it runs, open another model and press Ctrl+Alt+N again

How it works:
  `lava_lamp(t, u, v, a, cols, rows)` computes a colour image for time t (seconds).
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
# The model: 🫧 Lava Lamp
# =============================================================================
def lava_lamp(t, u, v, a, cols, rows):
    img = np.zeros(u.shape + (3,), np.float32)
    X = (u - 0.5) * a
    img[:] = _c(0.03, 0.01, 0.04)
    img += (np.clip(1 - _dist(u, v, 0.5, 0.45, a) / 0.6, 0, 1) ** 2)[..., None] * _c(0.35, 0.08, 0.2)
    top, bot = 0.13, 0.78
    w = 0.10 + 0.07 * np.clip((v - top) / (bot - top), 0, 1)
    glass = (v > top) & (v < bot) & (np.abs(X) < w)
    liquid = _c(0.4, 0.05, 0.3) * (0.7 + 0.3 * np.cos(X / w * 1.5))[..., None]
    img[glass] = liquid[glass]
    field = np.zeros_like(u)
    for i, (bx, by, br) in enumerate(BLOBS):
        x = 0.05 * np.sin(t * 0.3 + i * 2) + (bx - 0.5) * 0.06
        y = 0.46 + 0.27 * np.sin(t * (0.18 + 0.05 * by) + i * 1.7)
        r = 0.035 + 0.03 * br
        field += r * r / ((X - x) ** 2 + (v - y) ** 2 + 1e-4)
    field += 0.0025 / np.maximum(bot - v, 1e-3) ** 2 * 0.5  # Pfütze unten
    blob = glass & (field > 1)
    sh = np.clip((field - 1) * 0.6, 0, 1)
    img[blob] = (_c(1, 0.35, 0.05) + _c(0, 0.45, 0.2) * sh[..., None])[blob]
    cap = (v > 0.06) & (v <= top) & (np.abs(X) < 0.05 + 0.05 * (v - 0.06) / 0.07)
    base = (v >= bot) & (v < 0.95) & (np.abs(X) < 0.17 + 0.04 * np.sin((v - bot) / 0.17 * np.pi))
    metal = _c(0.45, 0.45, 0.5) * (0.6 + 0.4 * np.cos(X * 18))[..., None]
    img[cap | base] = metal[cap | base]
    return img


# =============================================================================
# Helpers and fixed random values
# =============================================================================
def _c(*rgb):
    return np.array(rgb, np.float32)


def _dist(u, v, cx, cy, a):
    return np.sqrt(((u - cx) * a) ** 2 + (v - cy) ** 2)


R = np.random.default_rng(11)
BLOBS = R.random((7, 3))


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
    play(lava_lamp)
