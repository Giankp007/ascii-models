"""
☁️ Cloudy Sky - ASCII animation
Part of ASCII Studio: https://github.com/Giankp007/ascii-studio

Stand-alone file, needs only numpy.
  Run:       Ctrl+Alt+N in VS Code (Code Runner)  or  python 31_cloudy_sky.py
  Stop:      Ctrl+C (or Esc) in the terminal
  Switch:    while it runs, open another model and press Ctrl+Alt+N again

How it works:
  `cloudy_sky(t, u, v, a, cols, rows)` computes a colour image for time t (seconds).
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
# The model: ☁️ Cloudy Sky
# =============================================================================
def cloudy_sky(t, u, v, a, cols, rows):
    img = (_c(0.15, 0.4, 0.85) * (1 - v)[..., None] + _c(0.6, 0.8, 1.0) * v[..., None]).astype(np.float32)
    d = _dist(u, v, 0.2, 0.2, a)
    img += (np.clip(1 - d / 0.3, 0, 1) ** 3)[..., None] * _c(1, 0.95, 0.7) + (d < 0.06)[..., None] * 0.6
    for layer, (sp, sc, th) in enumerate(((0.02, 3, 0.66), (0.04, 5, 0.7))):
        n = _noise(u * sc + t * sp * 10, v * sc * 1.8, t * 0.03 + layer)
        n2 = _noise(u * sc * 2.3 + t * sp * 12, v * sc * 4, t * 0.05)
        c = np.clip((n * 0.75 + n2 * 0.25 - th) * 6, 0, 1) * (v < 0.75)
        shade = 1 - 0.35 * np.clip((n - th) * 3, 0, 1)
        img = img * (1 - c)[..., None] + (c * shade)[..., None] * _c(1, 1, 1)
    px = np.mod(t * 0.05, 1.3) - 0.15
    plane = (np.abs((u - px) * a) < 0.02) & (np.abs(v - 0.3) < 0.006)
    img[plane] = 0.2
    trail = (u < px) & (u > px - 0.3) & (np.abs(v - 0.3) < 0.004)
    img[trail] = img[trail] * 0.5 + 0.5
    return img


# =============================================================================
# Helpers and fixed random values
# =============================================================================
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
    play(cloudy_sky)
