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
    """Winter night: a Christmas tree decorates itself, presents appear, fireworks, snow."""
    key = (cols, rows)
    if key not in WN_CACHE:
        WN_CACHE.clear()
        WN_CACHE[key] = _wn_static(u, v, a, cols, rows)
    base, tree, ground_mask, x, tx, ty = WN_CACHE[key]
    img = base.copy()
    y = v

    # moon (small, top left) with a faint halo
    mx, my = (0.17 - 0.5) * a, 0.09
    md = np.sqrt((x - mx) ** 2 + (y - my) ** 2)
    moon = np.clip((0.05 - md) / 0.012, 0, 1)
    crater = 0.70 + 0.30 * (np.sin(x * 120 + 1) * np.sin(y * 110) > 0.25)
    img += moon[..., None] * np.array([0.80, 0.84, 0.92]) * crater[..., None]
    img += (np.clip(1 - md / 0.11, 0, 1) ** 3 * 0.06)[..., None] * np.array([0.5, 0.6, 0.9])

    # fireworks behind the tree (bursts left and right of it)
    img += _wn_fireworks(t, x, y, a, cols, rows)

    # tree: foliage with shimmering texture
    grow = np.clip(t / 1.2, 0, 1)
    shimmer = 0.85 + 0.15 * np.sin(tx * 90 + t * 2.0) * np.sin(ty * 70 - t * 1.3)
    tm = tree[..., 0] * grow
    leaf = tree[..., 1:] * shimmer[..., None]
    img = img * (1 - tm[..., None]) + leaf * tm[..., None]

    # garland (golden tinsel, spirals around the tree, appears from the top down)
    gar = _wn_garland(t, x, y)
    img += gar[..., None] * np.array([1.0, 0.78, 0.25])

    # tree lights: small twinkling points
    _wn_tree_lights(img, t, cols, rows, a)

    # ornaments pop in one after another
    _wn_ornaments(img, t, x, y)

    # star on top with rays
    _wn_star(img, t, x, y)

    # presents
    for px, pw, ph, box, rib, at in WN_PRESENTS:
        _wn_present(img, t - at, x, y, px, pw, ph, box, rib)

    # snow in front of everything
    _wn_snow(img, t, cols, rows)
    return img


# =============================================================================
# Helpers and fixed random values
# =============================================================================
WN_RNG = np.random.default_rng(5)
WN_SNOW = WN_RNG.random((900, 4))
WN_TREE_LIGHTS = WN_RNG.random((110, 3))
WN_ORNAMENTS = WN_RNG.random((60, 4))
WN_SPARK_DIRS = WN_RNG.normal(size=(320, 3))
WN_SPARK_RND = WN_RNG.random((320, 2))
WN_CACHE = {}
WN_PRESENTS = (
    # x centre (height units, relative to the tree), width, height, box colour, ribbon colour, appears at (s)
    (-0.40, 0.20, 0.15, (0.85, 0.10, 0.12), (0.95, 0.92, 0.90), 2.4),
    (-0.255, 0.11, 0.09, (0.80, 0.08, 0.10), (1.00, 0.78, 0.15), 3.0),
    (0.07, 0.10, 0.08, (0.80, 0.08, 0.12), (0.95, 0.92, 0.90), 3.6),
    (0.235, 0.16, 0.13, (0.85, 0.12, 0.10), (1.00, 0.80, 0.18), 4.1),
    (0.385, 0.11, 0.10, (0.82, 0.10, 0.14), (0.95, 0.92, 0.90), 4.6),
)
WN_FIREWORK_COLOURS = ((1.0, 0.55, 0.15), (1.0, 0.25, 0.25), (1.0, 0.80, 0.30), (0.85, 0.30, 0.50),
                       (0.95, 0.95, 1.0), (1.0, 0.65, 0.25))
def _wn_static(u, v, a, cols, rows):
    x = (u - 0.5) * a          # height units (1 = full height), 0 = centre
    y = v
    img = np.zeros(u.shape + (3,), np.float32)
    # night sky: black (any brightness here would fill the sky with characters)
    img[:] = 0.0

    def forest(base, n_per_unit, h0, h1, seed, colour):
        """A row of pine trees: each tree is a narrow triangle with little steps (branches)."""
        r = np.random.default_rng(seed)
        n = int(n_per_unit * (a + 0.4)) + 2
        xs = np.sort(r.uniform(-a / 2 - 0.2, a / 2 + 0.2, n))
        hs = r.uniform(h0, h1, n)
        h = np.zeros_like(x)
        for cx, hh in zip(xs, hs):
            w = hh * 0.34
            steps = 1 - 0.18 * np.mod((x * 0 + (base - y)) / (hh / 4 + 1e-6), 1.0)
            h = np.maximum(h, hh * np.clip(1 - np.abs(x - cx) / (w * steps), 0, 1))
        mask = y > base - h
        tex = 0.6 + 0.4 * (np.sin(x * 220 + seed) * np.sin(y * 180 + x * 30) > -0.3)
        rowband = 0.8 + 0.2 * np.sin(y * rows * 1.9)
        fade = 0.75 + 0.25 * np.clip((y - (base - 0.15)) / 0.15, 0, 1)
        return mask, np.array(colour, np.float32) * (tex * rowband * fade)[..., None]

    m1, c1 = forest(0.52, 30, 0.06, 0.13, 21, (0.16, 0.34, 0.95))
    img[m1] = c1[m1]
    m2, c2 = forest(0.59, 22, 0.05, 0.12, 22, (0.20, 0.42, 1.0))
    img[m2] = c2[m2]

    # snowy ground: blue, textured with horizontal "drifts"
    g = y > 0.585
    depth = np.clip((y - 0.585) / 0.4, 0, 1)
    drift = 0.6 + 0.4 * np.sin(x * 9 + np.sin(y * 31) * 2) * np.sin(y * 57 + x * 3)
    noise = (np.sin(x * 413 + y * 97) * np.sin(x * 171 - y * 313)) > -0.35
    band = 0.75 + 0.25 * np.sign(np.sin(y * rows * 1.6 + x * 4))
    gc = np.stack([0.14 + 0.08 * depth, 0.30 + 0.15 * depth, 0.85 + 0.15 * depth], -1)
    gl = (0.45 + 0.35 * drift) * (0.55 + 0.45 * noise) * band
    img[g] = (gc * gl[..., None])[g]
    # soft transition from forest into ground
    edge = np.clip(1 - np.abs(y - 0.585) / 0.03, 0, 1) * 0.5
    img *= (1 - edge * 0.5)[..., None]

    # tree shape: tiers with drooping, scalloped edges
    top, bot = 0.175, 0.865
    tm = np.zeros_like(x)
    leaf = np.zeros(u.shape + (3,), np.float32)
    tiers = 6
    for i in range(tiers):
        t0 = top + (bot - top) * (i / tiers) ** 1.05 - (0.02 if i else 0)
        t1 = top + (bot - top) * ((i + 1) / tiers) ** 1.05 + 0.01
        hw_bot = 0.06 + 0.17 * ((i + 1) / tiers)
        frac = np.clip((y - t0) / (t1 - t0), 0, 1)
        hw = (0.012 + (hw_bot - 0.012) * (0.25 + 0.75 * frac)) if i else hw_bot * frac
        scallop = 0.012 * np.abs(np.sin(x * 70))
        inside = (y > t0) & (y < t1 + scallop) & (np.abs(x) < hw * (1 + 0.04 * np.sin(y * 300)))
        tm = np.maximum(tm, inside.astype(np.float32))
    # trunk hidden by lowest tier / snow, a little bit visible
    trunk = (np.abs(x) < 0.025) & (y > bot) & (y < bot + 0.02)
    # foliage colour: bright green, darker inside, light stripes like needle rows
    stripes = 0.75 + 0.25 * np.sin(y * rows * 3.1 + np.sin(x * 40) * 2)
    shade = 0.75 + 0.25 * np.sin(x * 33 + y * 20) - 0.15 * np.abs(x) * 3
    gval = np.clip(0.35 + 0.75 * stripes * shade, 0.6, 1.15)
    leaf[..., 0] = 0.14 * gval
    leaf[..., 1] = 1.00 * gval
    leaf[..., 2] = 0.28 * gval
    tree = np.concatenate([tm[..., None], leaf], -1)
    img[trunk] = (0.35, 0.18, 0.06)
    tx, ty = x, y
    return img, tree, g, x, tx, ty


def _wn_tree_halfwidth(y):
    top, bot = 0.175, 0.865
    return np.clip((y - top) / (bot - top), 0, 1) * 0.215


def _wn_garland(t, x, y):
    top, bot = 0.20, 0.85
    out = np.zeros_like(x)
    for k in range(4):
        y0 = top + (bot - top) * (k + 0.6) / 4.6
        hw = _wn_tree_halfwidth(y)
        line_y = y0 + 0.10 * (x / np.maximum(hw, 1e-3)) * (0.18 + 0.02 * k) * 1.4
        on = np.abs(y - line_y) < 0.010
        inside = np.abs(x) < hw * 0.95
        appear = np.clip((t - 1.6 - 0.45 * k) / 0.5, 0, 1)
        sparkle = 0.6 + 0.4 * np.sin(x * 120 + t * 6)
        out += (on & inside) * appear * sparkle * 0.85
    return out


def _wn_tree_lights(img, t, cols, rows, a):
    top, bot = 0.20, 0.85
    L = WN_TREE_LIGHTS
    ly = top + (bot - top) * np.sqrt(L[:, 0])
    lx = (L[:, 1] * 2 - 1) * _wn_tree_halfwidth(ly) * 0.92
    on = np.clip((t - 0.8 - L[:, 2] * 3.0) * 3, 0, 1)
    tw = 0.5 + 0.5 * np.sin(t * (2 + L[:, 2] * 4) + L[:, 0] * 40)
    bright = on * (0.35 + 0.65 * tw ** 3)
    ix = np.clip(((lx / (a) + 0.5) * cols).astype(int), 0, cols - 1)
    iy = np.clip((ly * rows).astype(int), 0, rows - 1)
    col = np.where((L[:, 2] < 0.6)[:, None], np.array([0.85, 1.0, 0.85]), np.array([1.0, 0.95, 0.75]))
    np.maximum.at(img, (iy, ix), (col * bright[:, None]).astype(np.float32))


def _wn_ornaments(img, t, x, y):
    top, bot = 0.24, 0.83
    O = WN_ORNAMENTS
    palette = np.array([(0.95, 0.15, 0.15), (1.0, 0.78, 0.20), (0.95, 0.95, 1.0), (0.95, 0.15, 0.25),
                        (1.0, 0.65, 0.15)], np.float32)
    for i, (r0, r1, r2, r3) in enumerate(O):
        oy = top + (bot - top) * np.sqrt(r0)
        ox = (r1 * 2 - 1) * _wn_tree_halfwidth(oy) * 0.82
        at = 1.4 + i * 0.07
        s = np.clip((t - at) / 0.25, 0, 1)
        if s <= 0:
            continue
        pop = s * (1 + 0.35 * np.sin(np.clip(t - at, 0, 0.6) * 10) * (1 - s * 0.6))
        kind = int(r2 * 5)
        c = palette[kind]
        if kind in (1, 4):  # golden bell / little box
            m = (np.abs(x - ox) < 0.020 * pop) & (np.abs(y - oy) < 0.016 * pop)
            img[m] = c * (0.85 + 0.15 * np.sin(t * 3 + i))
            img[m & (np.abs(y - oy + 0.016 * pop) < 0.004)] = (1.0, 1.0, 0.8)
        else:  # bauble with highlight
            d = np.sqrt((x - ox) ** 2 + (y - oy) ** 2)
            m = d < 0.018 * pop
            img[m] = c * (0.9 - 4 * d[m][:, None])
            hl = np.sqrt((x - ox + 0.006) ** 2 + (y - oy + 0.006) ** 2) < 0.006 * pop
            img[hl] = (1, 1, 1)
            img[(np.abs(x - ox) < 0.004) & (y > oy - 0.026 * pop) & (y < oy - 0.016 * pop)] = (0.9, 0.8, 0.4)


def _wn_star(img, t, x, y):
    s = np.clip((t - 3.4) / 0.6, 0, 1)
    if s <= 0:
        return
    sx, sy = 0.0, 0.155
    dx, dy = x - sx, (y - sy) * 1.0
    ang = np.arctan2(dy, dx) + np.pi / 2
    r = np.sqrt(dx ** 2 + dy ** 2)
    spike = 0.5 + 0.5 * np.cos(5 * ang)
    rad = (0.022 + 0.026 * spike ** 2.5) * s
    m = r < rad
    img[m] = (1.0, 0.82, 0.25)
    img[r < rad * 0.45] = (1.0, 0.97, 0.75)
    pulse = 0.75 + 0.25 * np.sin(t * 2.4)
    rays = np.zeros_like(r)
    for k in range(8):
        th = k * np.pi / 4 + 0.15 * np.sin(t * 0.7)
        along = dx * np.cos(th) + dy * np.sin(th)
        across = np.abs(-dx * np.sin(th) + dy * np.cos(th))
        length = (0.11 if k % 2 == 0 else 0.06) * pulse
        rays += (across < 0.0035) * (along > 0) * np.clip(1 - along / length, 0, 1)
    glow = np.clip(1 - r / 0.12, 0, 1) ** 2 * 0.35
    img += ((rays * 0.9 + glow) * s * pulse)[..., None] * np.array([1.0, 0.85, 0.45])


def _wn_present(img, age, x, y, px, pw, ph, box, rib):
    if age <= 0:
        return
    drop = (1 - np.clip(age / 0.35, 0, 1)) ** 2 * 0.25
    base = 0.885 - drop
    top = base - ph
    hw = pw / 2
    m = (np.abs(x - px) < hw) & (y > top) & (y < base)
    if not m.any():
        return
    shade = 0.85 + 0.15 * np.sin((x - px) * 300) * np.sin(y * 260)
    side = np.clip((x - px) / hw, -1, 1)
    light = 1.0 - 0.25 * (side > 0.55)
    img[m] = (np.array(box) * (shade * light)[..., None])[m]
    lid = m & (y < top + ph * 0.18)
    img[lid] = np.array(box) * 1.15
    vert = m & (np.abs(x - px) < pw * 0.09)
    horiz = m & (np.abs(y - (top + ph * 0.48)) < ph * 0.08)
    img[vert | horiz] = rib
    # bow: two loops on the lid
    for sgn in (-1, 1):
        bx, by = px + sgn * pw * 0.13, top - 0.012
        d = np.sqrt(((x - bx) / 1.6) ** 2 + (y - by) ** 2)
        ring = (d < 0.016) & (d > 0.007)
        img[ring] = rib
    img[(np.abs(x - px) < 0.008) & (np.abs(y - top + 0.008) < 0.008)] = rib


def _wn_fireworks(t, x, y, a, cols, rows):
    out = np.zeros(x.shape + (3,), np.float32)
    period = 1.7
    n_since = int(t // period)
    for k in range(max(0, n_since - 2), n_since + 1):
        start = k * period + 3.0
        age = t - start
        if age < 0 or age > 3.2:
            continue
        r = np.random.default_rng(1000 + k)
        side = -1 if k % 2 == 0 else 1
        wide = max(0.33, a / 2 - 0.13)
        cx = side * r.uniform(0.30, wide)
        cy = r.uniform(0.12, 0.30)
        col = np.array(WN_FIREWORK_COLOURS[r.integers(len(WN_FIREWORK_COLOURS))], np.float32)
        R = r.uniform(0.10, 0.15)
        # short glow at the moment of the burst
        flash = np.exp(-age * 2.2)
        d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        out += (np.clip(1 - d / (R * 1.3), 0, 1) ** 3 * 0.12 * flash)[..., None] * col
        # sparks: a sphere of particles projected on the screen
        dirs = WN_SPARK_DIRS / np.linalg.norm(WN_SPARK_DIRS, axis=1, keepdims=True)
        spread = R * (1 - np.exp(-age * 3.2))
        px = cx + dirs[:, 0] * spread
        py = cy + dirs[:, 1] * spread + 0.03 * age ** 2
        fade = np.clip(1 - age / 3.0, 0, 1) ** 1.3
        flick = 0.6 + 0.4 * np.sin(age * 25 + WN_SPARK_RND[:, 0] * 30)
        bright = fade * flick * (0.7 + 0.3 * (dirs[:, 2] > 0))
        ix = np.round((px / (a) + 0.5) * cols).astype(int)
        iy = np.round(py * rows).astype(int)
        ok = (ix >= 0) & (ix < cols) & (iy >= 0) & (iy < rows)
        c = np.where((WN_SPARK_RND[:, 1] < 0.12)[:, None], np.array([1, 1, 0.9], np.float32), col)
        np.maximum.at(out, (iy[ok], ix[ok]), (c[ok] * bright[ok, None]).astype(np.float32))
    return out


def _wn_snow(img, t, cols, rows):
    S = WN_SNOW
    n = min(len(S), int(cols * rows / 26))
    S = S[:n]
    speed = 0.035 + 0.07 * S[:, 2]
    sy = np.mod(S[:, 1] + t * speed, 1.0)
    sx = np.mod(S[:, 0] + 0.012 * np.sin(t * (0.6 + S[:, 3]) + S[:, 2] * 9) + t * 0.004, 1.0)
    ix = np.clip((sx * cols).astype(int), 0, cols - 1)
    iy = np.clip((sy * rows).astype(int), 0, rows - 1)
    size = S[:, 2] ** 3
    b = (0.05 + 0.9 * size)[:, None] * np.array([0.92, 0.95, 1.0], np.float32)
    np.maximum.at(img, (iy, ix), b.astype(np.float32))
    big = S[:, 2] > 0.93
    ix2 = np.clip(ix[big] + 1, 0, cols - 1)
    np.maximum.at(img, (iy[big], ix2), (b[big] * 0.6).astype(np.float32))


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
    play(winter_night)
