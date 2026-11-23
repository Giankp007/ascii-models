"""
🕯️ Candle - ASCII animation
Part of ASCII Studio: https://github.com/Giankp007/ascii-studio

Stand-alone file, needs only numpy.
  Run:       Ctrl+Alt+N in VS Code (Code Runner)  or  python 20_candle.py
  Stop:      Ctrl+C (or Esc) in the terminal
  Switch:    while it runs, open another model and press Ctrl+Alt+N again

How it works:
  `candle(t, u, v, a, cols, rows)` computes a colour image for time t (seconds).
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
# The model: 🕯️ Candle
# =============================================================================
def candle(t, u, v, a, cols, rows):
    img = np.zeros(u.shape + (3,), np.float32)
    X = (u - 0.5) * a
    fl = 0.9 + 0.1 * np.sin(t * 13) * np.sin(t * 7.3)
    img[:] = _c(0.04, 0.02, 0.01)
    img += (np.clip(1 - _dist(u, v, 0.5, 0.33, a) / 0.6, 0, 1) ** 2 * fl)[..., None] * _c(0.55, 0.3, 0.1)
    body = (np.abs(X) < 0.075) & (v > 0.49) & (v < 0.92)
    shade = 0.55 + 0.45 * np.cos(X / 0.075 * 1.3)
    img[body] = (_c(0.95, 0.88, 0.72) * shade[..., None] * (1.1 - (v - 0.49))[..., None])[body]
    rim = (np.abs(X) < 0.078) & (np.abs(v - 0.49) < 0.012)
    img[rim] = _c(1, 0.95, 0.8)
    for dxp, ln in ((-0.06, 0.12), (0.045, 0.07), (0.068, 0.18)):
        drip = (np.abs(X - dxp) < 0.009) & (v > 0.49) & (v < 0.49 + ln)
        img[drip] = _c(1, 0.96, 0.85)
    wick = (np.abs(X) < 0.006) & (v > 0.445) & (v < 0.49)
    img[wick] = _c(0.1, 0.07, 0.05)
    h = (0.45 - v) / 0.24
    wob = 0.01 * np.sin(v * 30 - t * 9) * h + 0.004 * np.sin(t * 5)
    width = 0.04 * np.sin(np.pi * np.clip(h, 0, 1) ** 0.6) * (1 - 0.3 * h)
    e = np.abs(X - wob) / np.maximum(width, 1e-4)
    flame = (h > 0) & (h < 1) & (e < 1)
    fcol = _c(1, 0.97, 0.75) * (1 - e)[..., None] + _c(1, 0.5, 0.1) * e[..., None]
    fcol = np.where((h < 0.15)[..., None], _c(0.35, 0.45, 1.0), fcol)
    img[flame] = (fcol * fl)[flame]
    table = v > 0.92
    img[table] = (_c(0.25, 0.13, 0.06) * (0.6 + 0.4 * np.sin(u * 90))[..., None])[table] + 0.15 * fl
    return img


# =============================================================================
# Helpers and fixed random values
# =============================================================================
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
    play(candle)
