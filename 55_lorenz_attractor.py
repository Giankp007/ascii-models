"""
🦋 Lorenz Attractor - ASCII animation
Part of ASCII Studio: https://github.com/Giankp007/ascii-studio

Stand-alone file, needs only numpy.
  Run:       Ctrl+Alt+N in VS Code (Code Runner)  or  python 55_lorenz_attractor.py
  Stop:      Ctrl+C (or Esc) in the terminal
  Switch:    while it runs, open another model and press Ctrl+Alt+N again

How it works:
  `lorenz_attractor(t, u, v, a, cols, rows)` computes a colour image for time t (seconds).
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
# The model: 🦋 Lorenz Attractor
# =============================================================================
def lorenz_attractor(t, u, v, a, cols, rows):
    img = np.zeros(u.shape + (3,), np.float32)
    if "pts" not in GOL:
        p = np.empty((6000, 3), np.float32)
        x, y, z = 0.1, 0.0, 0.0
        for i in range(6000):
            dx, dy, dz = 10 * (y - x), x * (28 - z) - y, x * y - 8 / 3 * z
            x, y, z = x + dx * 0.008, y + dy * 0.008, z + dz * 0.008
            p[i] = (x, y, z)
        p -= p.mean(axis=0)
        GOL["pts"] = p / np.abs(p).max()
    p = GOL["pts"]
    n = int(np.clip(np.mod(t, 16) / 12, 0, 1) * (len(p) - 1)) + 1
    ang = t * 0.25
    xr = p[:n, 0] * np.cos(ang) + p[:n, 1] * np.sin(ang)
    zr = p[:n, 2]
    idx = np.arange(n) / len(p)
    col = _hue(idx * 2 + 0.5)
    _plot(img, xr * 0.42 / a + 0.5, -zr * 0.45 + 0.5, col, 0.5 + 0.5 * (idx > idx[-1] - 0.05))
    return img


# =============================================================================
# Helpers and fixed random values
# =============================================================================
TAU = 2 * np.pi
def _hue(h):
    h = np.asarray(h, np.float32)[..., None]
    return 0.5 + 0.5 * np.cos(TAU * (h + np.array([0, 1 / 3, 2 / 3], np.float32)))


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


GOL = {"shape": None, "grid": None, "trail": None, "step": 0, "seed": 0}


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
    play(lorenz_attractor)
