"""
🎄 Winter Night - ASCII animation
Part of ASCII Studio: https://github.com/Giankp007/ascii-studio

Stand-alone file, needs only numpy.
  Run:       Ctrl+Alt+N in VS Code (Code Runner)  or  python 01_winter_night.py
  Stop:      Ctrl+C (or Esc) in the terminal
  Switch:    while it runs, open another model and press Ctrl+Alt+N again

What happens:
  A snowy night with a small moon and two rows of pine forest. A Christmas tree grows tier by
  tier, golden garlands with coloured bulbs wrap around it, baubles and bells pop in, presents
  drop into the snow, the star on top lights up - and then the fireworks start.

How it works:
  Unlike the other models this one does not just map brightness to characters. Every object is
  a shape (tree tiers, pines, moon, star, presents). Each character cell is sampled 12 times;
  full cells get a fill character, cells on the outline get a character that follows the edge
  ( / \\ | ( ) ^ _ ' ). Background colours add the glow of the moon, the star and the fireworks.
"""
import math
import os
import re
import shutil
import subprocess
import sys
import time

import numpy as np

FPS = 30

# timeline (seconds)
T_TREE = 0.3       # tree grows tier by tier
T_LIGHTS = 1.9     # small twinkling lights
T_GARLAND = 2.3    # golden garlands with bulbs
T_ORNAMENTS = 3.6  # baubles, bells, candy canes
T_PRESENTS = 4.4   # presents drop into the snow
T_STAR = 6.6       # star lights up
T_FIREWORKS = 7.6  # fireworks start

TREE_TOP, TREE_BOT = 0.175, 0.865
STAR_Y = 0.142


# =============================================================================
# Canvas: characters + foreground colour + background colour per cell
# =============================================================================
class Canvas:
    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.ch = np.full((rows, cols), " ", "<U1")
        self.fg = np.zeros((rows, cols, 3), np.float32)
        self.bg = np.zeros((rows, cols, 3), np.float32)
        self.mask = np.zeros((rows, cols), bool)
        self.tag = np.full((rows, cols), -1, np.int16)
        self.cw = 0.5 / rows               # width of one cell in "height units"
        self.a = cols * self.cw            # screen width in height units (height = 1)

    def copy(self):
        c = Canvas.__new__(Canvas)
        c.__dict__.update(self.__dict__)
        for k in ("ch", "fg", "bg", "mask", "tag"):
            setattr(c, k, getattr(self, k).copy())
        return c

    def cell(self, x, y):
        return int(math.floor(y * self.rows)), int(math.floor(x / self.cw + self.cols / 2))

    def put(self, x, y, ch, rgb, only_empty=False):
        r, c = self.cell(x, y)
        if 0 <= r < self.rows and 0 <= c < self.cols and (not only_empty or self.ch[r, c] == " "):
            self.ch[r, c] = ch
            self.fg[r, c] = rgb
            self.mask[r, c] = True

    def text(self, x, y, s, rgb):
        r, c = self.cell(x, y)
        c -= len(s) // 2
        for i, chr_ in enumerate(s):
            if 0 <= r < self.rows and 0 <= c + i < self.cols and chr_ != " ":
                self.ch[r, c + i] = chr_
                self.fg[r, c + i] = rgb
                self.mask[r, c + i] = True

    def paste(self, other, where=None, with_bg=True):
        m = other.mask if where is None else (other.mask & where)
        self.ch[m] = other.ch[m]
        self.fg[m] = other.fg[m]
        if with_bg:
            self.bg[m] = other.bg[m]


# sub-sample positions inside one cell (3 across, 4 down), relative to the centre
_sx, _sy = np.meshgrid((np.arange(3) + 0.5) / 3 - 0.5, (np.arange(4) + 0.5) / 4 - 0.5)
SUB_X, SUB_Y = _sx.ravel().astype(np.float32), _sy.ravel().astype(np.float32)
EDGES = {"r": "|", "l": "|", "/": "/", "\\": "\\", "d1": "_", "d2": "-", "u1": "'", "u2": "-"}


def shape(cv, inside, bbox, fill, edges=None, full_at=0.75, min_cov=0.2, bg=None, tag=None):
    """Draws a shape. inside(X, Y) -> bool (X, Y in height units, X = 0 is the centre).
    fill(X, Y) -> (characters, rgb) for completely covered cells. Partly covered cells get an
    outline character chosen from the direction of the covered part."""
    x0, x1, y0, y1 = bbox
    c0 = max(0, int(math.floor(x0 / cv.cw + cv.cols / 2)))
    c1 = min(cv.cols, int(math.floor(x1 / cv.cw + cv.cols / 2)) + 1)
    r0 = max(0, int(math.floor(y0 * cv.rows)))
    r1 = min(cv.rows, int(math.floor(y1 * cv.rows)) + 1)
    if c0 >= c1 or r0 >= r1:
        return None
    rr, cc = np.mgrid[r0:r1, c0:c1]
    X = ((cc + 0.5 - cv.cols / 2) * cv.cw).astype(np.float32)
    Y = ((rr + 0.5) / cv.rows).astype(np.float32)
    inn = inside(X[..., None] + SUB_X * cv.cw, Y[..., None] + SUB_Y / cv.rows).astype(np.float32)
    cov = inn.mean(-1)
    n = np.maximum(inn.sum(-1), 1e-6)
    gx = (inn * SUB_X).sum(-1) / n * 0.5          # a cell is half as wide as it is tall
    gy = (inn * SUB_Y).sum(-1) / n
    ang = np.degrees(np.arctan2(gy, gx))
    e = dict(EDGES)
    e.update(edges or {})
    conds = [np.abs(ang) <= 13.3, np.abs(ang) >= 166.7,
             ((ang > 13.3) & (ang <= 58.3)) | ((ang > -166.7) & (ang <= -121.7)),
             ((ang >= 121.7) & (ang < 166.7)) | ((ang >= -58.3) & (ang < -13.3)),
             (ang > 58.3) & (ang < 121.7) & (cov < 0.5), (ang > 58.3) & (ang < 121.7),
             (ang < -58.3) & (ang > -121.7) & (cov < 0.5)]
    ech = np.select(conds, [e["r"], e["l"], e["/"], e["\\"], e["d1"], e["d2"], e["u1"]], e["u2"])
    chars, rgb = fill(X, Y)
    chars = np.broadcast_to(np.asarray(chars), cov.shape)
    rgb = np.broadcast_to(np.asarray(rgb, np.float32), cov.shape + (3,))
    full = cov >= full_at
    edge = (cov >= min_cov) & ~full
    sl = (slice(r0, r1), slice(c0, c1))
    ch, fg = cv.ch[sl], cv.fg[sl]
    ch[full] = chars[full]
    ch[edge] = ech[edge]
    fg[full] = rgb[full]
    fg[edge] = rgb[edge] * (0.6 + 0.4 * cov[edge])[:, None]
    drawn = full | edge
    cv.mask[sl] |= drawn
    if bg is not None:
        cv.bg[sl][drawn] = bg
    if tag is not None:
        cv.tag[sl][drawn] = tag
    return drawn


def ramp(chars, val):
    """Picks a character from `chars` for every value 0..1."""
    arr = np.array(list(chars))
    return arr[np.clip((val * len(chars)).astype(int), 0, len(chars) - 1)]


def mix(c1, c2, k):
    k = np.asarray(k, np.float32)[..., None]
    return np.asarray(c1, np.float32) * (1 - k) + np.asarray(c2, np.float32) * k


def hash01(*xs):
    v = np.sin(sum(np.asarray(x, np.float64) * m for x, m in zip(xs, (12.9898, 78.233, 37.719)))) * 43758.5453
    return v - np.floor(v)


# =============================================================================
# The scene, built once per terminal size (static parts) ...
# =============================================================================
def tree_halfwidth(y):
    return np.clip((y - TREE_TOP) / (TREE_BOT - TREE_TOP), 0, 1) * 0.25


def moon_pos(a):
    return -min(0.48, a / 2 - 0.12), 0.115


def build(cols, rows):
    S = {}
    back = Canvas(cols, rows)
    a = back.a
    rr, cc = np.mgrid[0:rows, 0:cols]
    X = ((cc + 0.5 - cols / 2) * back.cw).astype(np.float32)
    Y = ((rr + 0.5) / rows).astype(np.float32)
    S["X"], S["Y"] = X, Y

    # --- sky: black at the top, deep blue towards the horizon, halo around the moon
    k = np.clip(Y / 0.56, 0, 1) ** 2
    back.bg[:] = mix((0.0, 0.0, 0.012), (0.02, 0.035, 0.10), k)
    mx, my = moon_pos(a)
    dm = np.sqrt((X - mx) ** 2 + (Y - my) ** 2)
    back.bg += (np.exp(-np.maximum(dm - 0.05, 0) / 0.05) * 0.10)[..., None] * np.array([0.55, 0.62, 0.85], np.float32)

    # --- moon with craters
    def moon_fill(X, Y):
        cr = (np.sin((X - mx) * 95 + 1.0) * np.sin((Y - my) * 80 + 0.5) + 0.6 * np.sin((X - mx) * 170 - (Y - my) * 60)) > 0.75
        ch = np.where(cr, "O", "@")
        rgb = np.where(cr[..., None], np.array([0.60, 0.64, 0.74], np.float32), np.array([0.92, 0.94, 1.0], np.float32))
        return ch, rgb
    R = 0.052
    shape(back, lambda X, Y: (X - mx) ** 2 + (Y - my) ** 2 < R * R, (mx - R, mx + R, my - R, my + R), moon_fill,
          edges={"r": "(", "l": ")", "d1": "_", "d2": ".", "u1": "'", "u2": "-"})

    # --- sky stars (twinkle every frame)
    r = np.random.default_rng(3)
    n = int(cols * rows / 70)
    sx, sy = r.uniform(-a / 2, a / 2, n), r.uniform(0.01, 0.5, n) ** 1.2
    ok = ((sx - mx) ** 2 + (sy - my) ** 2) > 0.09 ** 2
    S["stars"] = (sx[ok], sy[ok], r.random(ok.sum()))

    # --- pine forest, two rows
    front = Canvas(cols, rows)
    front.bg[:] = back.bg

    def forest(base, per_unit, h0, h1, seed, col, snow, chars):
        rg = np.random.default_rng(seed)
        m = int(per_unit * (a + 0.4)) + 2
        xs = np.sort(rg.uniform(-a / 2 - 0.15, a / 2 + 0.15, m))
        hs = rg.uniform(h0, h1, m)

        def inside(X, Y):
            res = np.zeros(X.shape, bool)
            for cx, hh in zip(xs, hs):
                rel = (base - Y) / hh
                fr = np.mod(rel * 3, 1.0)
                w = hh * 0.40 * (1 - rel) * (0.58 + 0.42 * (1 - fr))
                res |= (rel > -0.2) & (rel < 1) & (np.abs(X - cx) < np.where(rel < 0, hh * 0.3, w))
            return res

        def fill(X, Y):
            # height above the ground of the closest pine -> tier position -> snow on branch ends
            idx = np.clip(np.searchsorted(xs, X), 1, len(xs) - 1)
            near = np.where(np.abs(xs[idx - 1] - X) < np.abs(xs[idx] - X), idx - 1, idx)
            hh, cx = hs[near], xs[near]
            rel = (base - Y) / hh
            fr = np.mod(rel * 3, 1.0)
            edge = np.abs(X - cx) / np.maximum(hh * 0.40 * (1 - rel), 1e-3)
            sn = (fr < 0.28) & (edge > 0.35) & (rel > 0.05)
            tex = hash01(np.floor(X / front.cw), np.floor(Y * rows))
            ch = np.where(sn, "~", ramp(chars, tex))
            rgb = np.where(sn[..., None], np.array(snow, np.float32),
                           np.array(col, np.float32) * (0.75 + 0.35 * tex)[..., None])
            return ch, rgb
        top = base - h1
        shape(front, inside, (-a / 2, a / 2, top, base + 0.06), fill,
              edges={"d1": "^", "d2": "A", "u1": "~", "u2": "~"})

    forest(0.53, 26, 0.055, 0.12, 21, (0.10, 0.20, 0.52), (0.40, 0.50, 0.80), ":;i!")
    forest(0.605, 18, 0.06, 0.14, 22, (0.15, 0.30, 0.78), (0.62, 0.72, 0.98), "|il!I")

    # --- snowy ground with perspective drifts
    g0 = 0.60

    def ground_in(X, Y):
        return Y > g0 + 0.008 * np.sin(X * 9) + 0.004 * np.sin(X * 23 + 1)

    def ground_fill(X, Y):
        depth = np.clip((Y - g0) / (1 - g0), 0, 1)
        z = 1.0 / (Y - g0 + 0.05)
        drift = 0.5 + 0.5 * np.sin(z * 2.2 + np.sin(X * 4) * 1.5) * np.sin(X * 3 + z * 0.7)
        grain = hash01(np.floor(X / front.cw), np.floor(Y * rows), 7.0)
        val = np.clip(0.25 + 0.5 * drift + 0.35 * (grain - 0.5), 0, 1)
        ch = ramp("  ..,-~~=+", val)
        rgb = mix((0.18, 0.28, 0.62), (0.62, 0.74, 1.0), np.clip(val * 0.8 + depth * 0.3, 0, 1))
        return ch, rgb
    gm = shape(front, ground_in, (-a / 2, a / 2, g0 - 0.02, 1.0), ground_fill, edges={"d1": ".", "d2": "-"})
    gy = Y >= g0 - 0.01
    front.bg[gy] = mix((0.02, 0.04, 0.12), (0.05, 0.09, 0.22), np.clip((Y[gy] - g0) / (1 - g0), 0, 1))
    front.mask |= gy
    S["ground_cells"] = np.argwhere(gy & (front.ch != " ") & (r.random((rows, cols)) < 0.04))

    # --- the tree (tiers drawn bottom-up so every tier hangs over the next one)
    tree = Canvas(cols, rows)
    H = TREE_BOT - TREE_TOP
    tiers = 6
    for i in reversed(range(tiers)):
        ys = TREE_TOP + H * i / tiers - (0.035 if i else 0.0)
        ye = TREE_TOP + H * (i + 1) / tiers - 0.012
        W = 0.05 + 0.21 * (i + 1) / tiers
        w0 = 0.0 if i == 0 else W * 0.50

        def inside(X, Y, ys=ys, ye=ye, W=W, w0=w0):
            fr = np.clip((Y - ys) / (ye - ys), 0, 1)
            w = w0 + (W - w0) * fr ** 0.85
            droop = 0.036 * (np.abs(X) / W) ** 2 + 0.012 * np.abs(np.sin(X * 55))
            return (Y > ys) & (np.abs(X) < w) & (Y < ye + droop)

        def fill(X, Y, ys=ys, ye=ye, W=W):
            fr = np.clip((Y - ys) / (ye - ys), 0, 1)
            side = np.clip(-X / W, -1, 1)
            n_ = hash01(np.floor(X / tree.cw), np.floor(Y * rows), 3.0)
            val = np.clip(0.12 + 0.70 * fr ** 0.8 + 0.18 * side + 0.25 * (n_ - 0.5), 0, 1)
            ch = ramp(":=+*#%", val)
            rgb = mix((0.02, 0.30, 0.09), (0.36, 1.0, 0.42), val)
            return ch, rgb
        shape(tree, inside, (-W - 0.01, W + 0.01, ys, ye + 0.04), fill, tag=i,
              edges={"r": "/", "l": "\\", "d1": "^", "d2": "^", "u1": "'", "u2": "~"})
    # trunk
    shape(tree, lambda X, Y: (np.abs(X) < 0.028) & (Y > TREE_BOT - 0.01) & (Y < TREE_BOT + 0.04),
          (-0.04, 0.04, TREE_BOT - 0.02, TREE_BOT + 0.05),
          lambda X, Y: (np.where(hash01(np.floor(Y * rows), np.floor(X / tree.cw)) > 0.5, "H", "#"),
                        np.array([0.48, 0.27, 0.10], np.float32)), tag=9)
    S["tree_cells"] = int((tree.tag >= 0).sum())

    # tiny lights inside the tree
    cand = np.argwhere((tree.tag >= 0) & (tree.tag < 9) & (tree.ch != " "))
    r.shuffle(cand)
    S["lights"] = (cand[: max(8, len(cand) // 9)], r.random((max(8, len(cand) // 9), 3)))

    # --- garlands: golden bead strings with coloured bulbs, wrapping the tree
    garlands = []
    for j, (yc, tilt) in enumerate(((0.33, 0.035), (0.47, -0.04), (0.61, 0.045), (0.75, -0.045))):
        cells, seen = [], set()
        for u in np.linspace(-1, 1, 900):
            yy = yc + tilt * u + 0.03 * (1 - u * u)
            xx = u * tree_halfwidth(yy) * 0.93
            rc = (int(yy * rows), int(math.floor(xx / tree.cw + cols / 2)))
            if rc not in seen and 0 <= rc[0] < rows and 0 <= rc[1] < cols:
                seen.add(rc)
                cells.append((rc[0], rc[1], u))
        out = []
        for idx, (r_, c_, u) in enumerate(cells):
            prev = cells[idx - 1] if idx else cells[idx]
            nxt = cells[idx + 1] if idx + 1 < len(cells) else cells[idx]
            dr = nxt[0] - prev[0]
            ch = "-" if dr == 0 else ("\\" if dr > 0 else "/")
            out.append((r_, c_, u, ch, idx % 4 == 2))
        garlands.append(out)
    S["garlands"] = garlands
    gcells = {(r_, c_) for g in garlands for r_, c_, *_ in g}

    # --- ornaments: spread out, never on a garland
    cand = [tuple(p) for p in np.argwhere((tree.tag >= 0) & (tree.tag < 9) & (tree.ch != " "))
            if (p[0], p[1]) not in gcells and tree.ch[p[0], p[1]] not in "/\\^'~"]
    order = r.permutation(len(cand))
    taken, orn = np.zeros((rows, cols), bool), []
    limit = max(6, S["tree_cells"] // 15)
    kinds = (("O", (1.0, 0.16, 0.16)), ("@", (1.0, 0.80, 0.22)), ("o", (0.88, 0.92, 1.0)),
             ("0", (0.35, 0.55, 1.0)), ("O", (0.95, 0.20, 0.45)), ("A", (1.0, 0.75, 0.20)),
             ("J", (1.0, 0.25, 0.25)), ("*", (1.0, 0.92, 0.45)), ("@", (1.0, 0.25, 0.20)))
    for oi in order:
        r_, c_ = cand[oi]
        if taken[max(0, r_ - 1):r_ + 2, max(0, c_ - 2):c_ + 3].any():
            continue
        taken[r_, c_] = True
        orn.append((r_, c_) + kinds[len(orn) % len(kinds)])
        if len(orn) >= limit:
            break
    orn.sort(key=lambda o: (o[0], o[1]))     # pop in from top to bottom
    S["ornaments"] = orn

    # --- presents (3D boxes with ribbons and bows), each pre-rendered as a sprite
    presents = []
    base = 0.905
    specs = (  # x, width, height, depth, box, ribbon, pattern, bow
        (-0.42, 0.18, 0.15, 0.035, (0.85, 0.10, 0.12), (0.96, 0.96, 1.0), "plain", "\\(@)/"),
        (-0.26, 0.11, 0.09, 0.025, (0.88, 0.14, 0.10), (1.0, 0.80, 0.18), "stripes", "(@)"),
        (0.085, 0.10, 0.085, 0.022, (0.82, 0.08, 0.14), (0.96, 0.96, 1.0), "dots", ">o<"),
        (0.245, 0.17, 0.14, 0.035, (0.86, 0.12, 0.10), (1.0, 0.82, 0.20), "band", "\\(@)/"),
        (0.40, 0.11, 0.10, 0.025, (0.80, 0.10, 0.16), (0.96, 0.96, 1.0), "plain", "(o)"),
    )
    for k_, (px, pw, ph, pd, box, rib, pat, bow) in enumerate(specs):
        sp = Canvas(cols, rows)
        x0, x1, top = px - pw / 2, px + pw / 2, base - ph
        box, rib = np.array(box, np.float32), np.array(rib, np.float32)

        def front_fill(X, Y, x0=x0, x1=x1, top=top, px=px, pw=pw, ph=ph, box=box, rib=rib, pat=pat):
            ch = np.full(X.shape, "#")
            rgb = np.broadcast_to(box, X.shape + (3,)).copy()
            if pat == "stripes":
                st = np.mod(np.floor((X - x0) / sp.cw), 4) < 1
                rgb[st] = (1.0, 0.80, 0.20)
            elif pat == "dots":
                dt = (np.mod(np.floor((X - x0) / sp.cw), 3) == 1) & (np.mod(np.floor((Y - top) * rows), 2) == 0)
                ch = np.where(dt, "o", ch)
                rgb[dt] = (1.0, 1.0, 1.0)
            elif pat == "band":
                bd = np.abs(X - px) < pw * 0.16
                rgb[bd] = (1.0, 0.78, 0.18)
            vert = np.abs(X - px) < max(sp.cw * 0.9, pw * 0.07)
            hor = np.abs(Y - (top + ph * 0.45)) < 0.6 / rows
            ch = np.where(vert & hor, "+", np.where(vert, "|", np.where(hor, "=", ch)))
            rgb[vert | hor] = rib
            return ch, rgb
        shape(sp, lambda X, Y, x0=x0, x1=x1, top=top: (X > x0) & (X < x1) & (Y > top) & (Y < base),
              (x0, x1, top, base), front_fill, edges={"r": "|", "l": "|", "u1": "_", "u2": "_", "d1": "_", "d2": "_"})
        # top face (lighter) and side face (darker)
        lift = pd * 0.9

        def top_in(X, Y, x0=x0, x1=x1, top=top, pd=pd, lift=lift):
            k = (top - Y) / lift
            return (k > 0) & (k < 1) & (X > x0 + k * pd) & (X < x1 + k * pd)

        def top_fill(X, Y, top=top, px=px, pd=pd, lift=lift, pw=pw, box=box, rib=rib):
            k = (top - Y) / lift
            on_rib = np.abs(X - px - k * pd) < max(sp.cw * 0.9, pw * 0.07)
            return np.where(on_rib, "|", "="), np.where(on_rib[..., None], rib, np.minimum(box * 1.35, 1))
        shape(sp, top_in, (x0, x1 + pd, top - lift, top), top_fill, edges={"d1": "_", "d2": "_", "/": "/", "\\": "/"})

        def side_in(X, Y, x1=x1, top=top, pd=pd, lift=lift):
            k = (X - x1) / pd
            return (k > 0) & (k < 1) & (Y < base - k * lift) & (Y > top - k * lift)

        def side_fill(X, Y, x1=x1, top=top, pd=pd, lift=lift, ph=ph, box=box, rib=rib):
            k = (X - x1) / pd
            hor = np.abs(Y + k * lift - (top + ph * 0.45)) < 0.6 / rows
            return np.where(hor, "=", "%"), np.where(hor[..., None], rib * 0.7, box * 0.55)
        shape(sp, side_in, (x1, x1 + pd, top - lift, base), side_fill, edges={"r": "|", "l": "|", "/": "/", "\\": "/"})
        sp.text(px + pd * 0.5, top - lift - 0.5 / rows, bow, rib)
        idx = np.argwhere(sp.mask)
        presents.append((idx, sp, T_PRESENTS + k_ * 0.42))
    S["presents"] = presents

    # --- snowflakes in three layers (far ones fall behind the tree)
    flakes = []
    for layer, (dens, speed, chars, bright) in enumerate(((60, 0.035, ".", 0.55), (120, 0.06, ".+*", 0.8),
                                                          (330, 0.10, "*o", 1.0))):
        m = max(5, int(cols * rows / dens))
        flakes.append((r.random((m, 4)), speed, chars, bright))
    S["flakes"] = flakes

    # --- glow of the lit tree on the background
    dt = np.sqrt((X * 1.3) ** 2 + ((Y - 0.55) * 0.9) ** 2)
    S["tree_glow"] = (np.exp(-dt / 0.22) * 0.09)[..., None] * np.array([1.0, 0.75, 0.25], np.float32)
    S["star_glow"] = (np.exp(-np.sqrt(X ** 2 + (Y - STAR_Y) ** 2) / 0.07) * 0.16)[..., None] * np.array([1.0, 0.82, 0.35], np.float32)

    S["back"], S["front"], S["tree"] = back, front, tree
    S["fireworks"] = firework_schedule(a)
    return S


# =============================================================================
# ... and animated every frame
# =============================================================================
def render(t, cols, rows, cache={}):
    if cache.get("size") != (cols, rows):
        cache.clear()
        cache["size"] = (cols, rows)
        cache["S"] = build(cols, rows)
    S = cache["S"]
    cv = S["back"].copy()
    a = cv.a

    # twinkling stars
    sx, sy, sr = S["stars"]
    tw = 0.5 + 0.5 * np.sin(t * (1.0 + 2.5 * sr) + sr * 40)
    for x, y, rnd, w in zip(sx, sy, sr, tw):
        ch = "+" if (rnd > 0.93 and w > 0.8) else ("." if w > 0.25 else " ")
        if ch != " ":
            cv.put(x, y, ch, np.array([0.55, 0.62, 0.85]) * (0.4 + 0.6 * w), only_empty=True)

    shooting_star(cv, t)
    draw_fireworks(cv, t, S)
    snow(cv, t, S, layers=(0,))
    cv.paste(S["front"])

    # ground sparkles
    for (r_, c_) in S["ground_cells"]:
        if hash01(r_, c_, math.floor(t * 3)) > 0.88:
            cv.ch[r_, c_] = "*"
            cv.fg[r_, c_] = (0.85, 0.92, 1.0)

    # the tree grows tier by tier (bottom first), each tier fades in
    tree = S["tree"]
    lights_on = np.clip((t - T_LIGHTS) / 1.0, 0, 1)
    cv.bg += S["tree_glow"] * (lights_on * (0.85 + 0.15 * math.sin(t * 2.3)))
    appear = np.array([np.clip((t - T_TREE - (5 - i) * 0.22) / 0.35, 0, 1) for i in range(6)]
                      + [0, 0, 0, np.clip((t - T_TREE + 0.2) / 0.3, 0, 1)], np.float32)
    k = np.where(tree.tag >= 0, appear[np.clip(tree.tag, 0, 9)], 0)
    vis = tree.mask & (k > 0)
    cv.ch[vis] = tree.ch[vis]
    cv.fg[vis] = tree.fg[vis] * k[vis][:, None]

    # little lights that twinkle inside the tree
    cells, rnd = S["lights"]
    if lights_on > 0:
        for (r_, c_), (p0, p1, p2) in zip(cells, rnd):
            if t < T_LIGHTS + p0 * 1.2:
                continue
            w = math.sin(t * (1.5 + 3 * p1) + p2 * 30)
            if w > 0.55:
                cv.ch[r_, c_] = "*" if w > 0.9 else "+"
                cv.fg[r_, c_] = (1.0, 0.95, 0.75) if p2 < 0.6 else (0.75, 1.0, 0.8)

    # garlands
    bulbs = ((1.0, 0.2, 0.2), (1.0, 0.8, 0.2), (0.3, 0.6, 1.0), (0.3, 1.0, 0.4), (1.0, 0.45, 0.85))
    for j, g in enumerate(S["garlands"]):
        p = np.clip((t - T_GARLAND - 0.35 * j) / 0.7, 0, 1)
        if p <= 0:
            continue
        for n_, (r_, c_, u, ch, is_bulb) in enumerate(g):
            if u > -1 + 2 * p:
                break
            if is_bulb:
                col = bulbs[(n_ // 4 + j) % len(bulbs)]
                on = 0.35 + 0.65 * max(0.0, math.sin(t * 3.0 - n_ * 0.45 + j))
                cv.ch[r_, c_] = "o"
                cv.fg[r_, c_] = np.array(col) * on + 0.1
                cv.bg[r_, c_] += np.array(col, np.float32) * 0.10 * on
            else:
                sh = 0.65 + 0.35 * math.sin(u * 25 - t * 5)
                cv.ch[r_, c_] = ch
                cv.fg[r_, c_] = (1.0 * sh, 0.78 * sh, 0.25 * sh)

    # ornaments pop in (white flash first), sometimes a glint
    for i, (r_, c_, ch, col) in enumerate(S["ornaments"]):
        age = t - T_ORNAMENTS - i * 0.05
        if age < 0:
            continue
        if age < 0.12:
            cv.ch[r_, c_], cv.fg[r_, c_] = "*", (1, 1, 1)
        elif hash01(i, math.floor(t * 5)) > 0.97:
            cv.ch[r_, c_], cv.fg[r_, c_] = ch, (1, 1, 1)
        else:
            cv.ch[r_, c_], cv.fg[r_, c_] = ch, col

    # presents drop in and bounce
    for idx, sp, at in S["presents"]:
        age = t - at
        if age <= 0:
            continue
        if age < 0.45:
            dy = -0.45 * (1 - age / 0.45) ** 2
        elif age < 0.7:
            dy = -0.025 * math.sin(math.pi * (age - 0.45) / 0.25)
        else:
            dy = 0.0
        off = int(round(dy * rows))
        rr = idx[:, 0] + off
        ok = (rr >= 0) & (rr < rows)
        r0, c0, r1 = idx[ok, 0], idx[ok, 1], rr[ok]
        cv.ch[r1, c0] = sp.ch[r0, c0]
        cv.fg[r1, c0] = sp.fg[r0, c0]

    draw_star(cv, t, S)
    snow(cv, t, S, layers=(1, 2))
    return cv


def draw_star(cv, t, S):
    age = t - T_STAR
    if age <= 0:
        return
    s = 1 - math.exp(-age * 6) * math.cos(age * 9)          # springy scale-in
    pulse = 0.8 + 0.2 * math.sin(t * 2.4)
    cv.bg += S["star_glow"] * (min(1.0, age * 2) * pulse)
    R = max(0.05, 2.6 / cv.rows) * s
    if R <= 0.004:
        return
    if cv.rows < 72:                       # normal terminal: a hand-drawn ASCII star
        if age < 0.25:
            cv.text(0, STAR_Y, "*", (1, 1, 0.9))
        else:
            sprite = ("   /\\   ", "__/##\\__", "\\##@@##/", " /#/\\#\\ ", "/_/  \\_\\")
            for i, line in enumerate(sprite):
                y = STAR_Y + (i - 2) / cv.rows
                r_, c_ = cv.cell(0, y)
                c_ -= 4
                for j, ch in enumerate(line):
                    if ch != " " and 0 <= r_ < cv.rows and 0 <= c_ + j < cv.cols:
                        cv.ch[r_, c_ + j] = ch
                        cv.fg[r_, c_ + j] = ((1.0, 1.0, 0.85) if ch == "@" else
                                             (1.0, 0.88, 0.35) if ch == "#" else (1.0, 0.72, 0.18))
        R = 2.6 / cv.rows
        draw_rays(cv, t, age, pulse, R)
        return
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = R if i % 2 == 0 else R * 0.42
        pts.append((math.cos(ang) * rad, STAR_Y + math.sin(ang) * rad))

    def inside(X, Y):
        res = np.zeros(X.shape, bool)
        for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
            res ^= ((y1 > Y) != (y2 > Y)) & (X < x1 + (Y - y1) * (x2 - x1) / (y2 - y1 + 1e-9))
        return res

    def fill(X, Y):
        d = np.sqrt(X ** 2 + (Y - STAR_Y) ** 2) / R
        return np.where(d < 0.3, "@", "#"), mix((1.0, 1.0, 0.85), (1.0, 0.75, 0.15), np.clip(d, 0, 1))
    shape(cv, inside, (-R, R, STAR_Y - R, STAR_Y + R), fill, edges={"d1": "^", "d2": "A", "u1": "'", "u2": "V"})
    draw_rays(cv, t, age, pulse, R)


def draw_rays(cv, t, age, pulse, R):
    rays =((1, 0, "-", 0.13), (-1, 0, "-", 0.13), (0, -1, "|", 0.10),
            (1, -1, "/", 0.07), (-1, -1, "\\", 0.07), (1, 1, "\\", 0.05), (-1, 1, "/", 0.05))
    for dx, dy, ch, L in rays:
        L *= pulse * (1.6 if age < 0.6 else 1.0) * min(1.0, age * 1.5)
        n = int(L * cv.rows * (2 if dy == 0 else 1)) + 1
        norm = math.hypot(dx, dy)
        for i in range(1, n + 1):
            f = i / n
            dist = R * 1.1 + L * f
            x, y = dx / norm * dist, STAR_Y + dy / norm * dist
            b = (1 - f) ** 1.3 * (0.7 + 0.3 * math.sin(t * 7 - i))
            if b > 0.12:
                cv.put(x, y, ch if b > 0.35 else ".", (1.0 * b + 0.05, 0.85 * b, 0.4 * b))


def snow(cv, t, S, layers):
    a = cv.a
    wind = 0.015 * math.sin(t * 0.21)
    for layer in layers:
        F, speed, chars, bright = S["flakes"][layer]
        y = np.mod(F[:, 1] + t * speed * (0.8 + 0.4 * F[:, 2]), 1.0)
        x = np.mod(F[:, 0] + 0.012 * np.sin(t * (0.5 + F[:, 3]) + F[:, 2] * 9) + t * wind * (layer + 1), 1.0)
        r = np.clip((y * cv.rows).astype(int), 0, cv.rows - 1)
        c = np.clip((x * cv.cols).astype(int), 0, cv.cols - 1)
        ch = np.array(list(chars))[np.minimum((F[:, 3] * len(chars)).astype(int), len(chars) - 1)]
        b = bright * (0.65 + 0.35 * F[:, 2])
        cv.ch[r, c] = ch
        cv.fg[r, c] = (b[:, None] * np.array([0.9, 0.94, 1.0])).astype(np.float32)


def shooting_star(cv, t):
    ph = t % 14.0
    if not (5.0 < ph < 5.9):
        return
    p = (ph - 5.0) / 0.9
    x0 = cv.a * 0.32
    hx, hy = x0 - p * 0.6, 0.04 + p * 0.22
    for i in range(14):
        f = i / 14
        x, y = hx + f * 0.12, hy - f * 0.044
        b = (1 - f) * (1 - p * 0.5)
        cv.put(x, y, "*" if i == 0 else ("/" if f < 0.5 else "."), (b, b, b * 0.9 + 0.1), only_empty=True)


# =============================================================================
# Fireworks: rockets with a trail, then a burst of sparks (peony, ring, willow)
# =============================================================================
PALETTES = (((1.0, 0.55, 0.12), (1.0, 0.85, 0.35)), ((1.0, 0.22, 0.22), (1.0, 0.55, 0.65)),
            ((1.0, 0.82, 0.30), (1.0, 1.0, 0.85)), ((0.95, 0.30, 0.55), (1.0, 0.70, 0.30)),
            ((0.85, 0.90, 1.0), (0.45, 0.65, 1.0)), ((1.0, 0.45, 0.10), (1.0, 0.25, 0.20)))


def firework_schedule(a):
    r = np.random.default_rng(77)
    shows, tt = [], T_FIREWORKS
    for k in range(240):
        side = (-1 if k % 2 == 0 else 1) if r.random() < 0.8 else r.choice((-1, 1))
        wide = max(0.36, a / 2 - 0.10)
        kind = r.choice(("peony", "peony", "ring", "willow"))
        n = {"peony": 130, "ring": 70, "willow": 70}[kind]
        d = r.normal(size=(n, 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        if kind == "ring":
            th = r.uniform(0, 2 * np.pi, n)
            tilt = r.uniform(0.2, 0.6)
            d = np.stack([np.cos(th), np.sin(th) * tilt, np.zeros(n)], 1)
        shows.append(dict(t=tt, x=side * r.uniform(0.30, wide), y=r.uniform(0.09, 0.30), kind=kind, d=d,
                          rnd=r.random((n, 2)),
                          pal=((1.0, 0.75, 0.25), (1.0, 0.55, 0.15)) if kind == "willow" else PALETTES[r.integers(len(PALETTES))],
                          size=r.uniform(0.10, 0.16) * (1.2 if kind == "willow" else 1.0),
                          launch_x=r.uniform(-0.04, 0.04)))
        tt += r.uniform(0.7, 1.8)
    return shows


def draw_fireworks(cv, t, S):
    shows = S["fireworks"]
    if t < T_FIREWORKS:
        return
    span = shows[-1]["t"] - T_FIREWORKS
    tl = T_FIREWORKS + (t - T_FIREWORKS) % span
    X, Y = S["X"], S["Y"]
    rise = 0.9
    for sh in shows:
        tau = tl - sh["t"]
        if tau < 0:
            break
        life = 3.2 if sh["kind"] == "willow" else 2.3
        if tau > rise + life:
            continue
        cx, cy = sh["x"], sh["y"]
        if tau < rise:                                  # rocket going up
            p = tau / rise
            e = 1 - (1 - p) ** 2
            y = 0.58 + (cy - 0.58) * e
            x = cx + sh["launch_x"] * (1 - e)
            cv.put(x, y, "|", (1.0, 0.95, 0.75))
            for i in range(1, 6):
                b = (1 - i / 6) * 0.8
                cv.put(x + (hash01(i, tau * 30) - 0.5) * 0.004, y + i * 0.55 / cv.rows * 1.8,
                       "'" if i < 3 else ".", (1.0 * b, 0.55 * b, 0.15 * b))
            continue
        tb = tau - rise
        c1, c2 = sh["pal"]
        if tb < 0.5:                                    # flash lights up the sky
            d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
            cv.bg += (np.exp(-d / 0.11) * 0.22 * math.exp(-tb * 6))[..., None] * np.array(c1, np.float32)
        drag, grav = (1.8, 0.10) if sh["kind"] == "willow" else (3.2, 0.035)
        d, rnd = sh["d"], sh["rnd"]
        lags = (0.0, 0.08, 0.16) if sh["kind"] == "willow" else (0.0, 0.06, 0.12)
        for li in reversed(range(len(lags))):
            tt = tb - lags[li]
            if tt < 0:
                continue
            disp = sh["size"] * (1 - math.exp(-drag * tt)) * (0.75 + 0.25 * rnd[:, 0])
            px = cx + d[:, 0] * disp
            py = cy + d[:, 1] * disp + grav * tt * tt
            f = tb / life
            fade = max(0.0, 1 - f) ** 1.2
            flick = 0.6 + 0.4 * np.sin(tb * 30 + rnd[:, 1] * 40)
            b = fade * flick * (1.0 if li == 0 else 0.55 - 0.08 * li) * (0.8 + 0.2 * (d[:, 2] > 0))
            col = mix(c1, c2, np.clip(rnd[:, 1] * 0.6 + f, 0, 1)) * b[:, None]
            if li == 0 and tb < 0.12:
                col = np.full_like(col, 1.0)
            if li == 0:
                ch = "@" if f < 0.06 else ("*" if f < 0.45 else ("+" if f < 0.75 else "."))
                if sh["kind"] == "willow" and f > 0.5:
                    ch = "'"
            else:
                ch = "."
            r = np.round(py * cv.rows - 0.5).astype(int)
            c = np.round(px / cv.cw + cv.cols / 2 - 0.5).astype(int)
            ok = (r >= 0) & (r < cv.rows) & (c >= 0) & (c < cv.cols) & (b > 0.06)
            if f > 0.8 and li == 0:                     # crackle at the end
                ok &= hash01(rnd[:, 0] * 100, math.floor(tb * 12)) > 0.35
            cv.ch[r[ok], c[ok]] = ch
            cv.fg[r[ok], c[ok]] = col[ok]


# =============================================================================
# Player: draws the frames in the terminal
# =============================================================================
def to_text(cv):
    """Canvas -> text with 24-bit colours (ANSI). Foreground and background are only written
    when they change."""
    fg = (np.clip(cv.fg, 0, 1) * 255).astype(np.int32) // 8 * 8
    bg = (np.clip(cv.bg, 0, 1) * 255).astype(np.int32) // 5 * 5
    chars, fgl, bgl = cv.ch.tolist(), fg.tolist(), bg.tolist()
    out = []
    for y in range(cv.rows):
        parts, lf, lb = ["\x1b[%d;1H" % (y + 1)], None, None
        crow, frow, brow = chars[y], fgl[y], bgl[y]
        for x in range(cv.cols):
            b = brow[x]
            if b != lb:
                parts.append("\x1b[48;2;%d;%d;%dm" % tuple(b))
                lb = b
            ch = crow[x]
            if ch != " ":
                f = frow[x]
                if f != lf:
                    parts.append("\x1b[38;2;%d;%d;%dm" % tuple(f))
                    lf = f
            parts.append(ch)
        out.append("".join(parts))
    return "".join(out)


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
    """Write to the terminal in chunks. (With `python -u` - which Code Runner uses - Windows
    silently drops everything after ~32 KB of a single write, so big frames got cut off.)"""
    data = text.encode("utf-8")
    fd = sys.stdout.fileno()
    while data:
        n = os.write(fd, data[:16384])
        data = data[n:]


def play():
    os.system("")  # turns on ANSI colours on Windows
    emit("\x1b[?1049h\x1b[?25l\x1b[48;2;0;0;3m\x1b[2J")
    start, state, nxt, size = time.time(), {"typed": ""}, None, None
    try:
        while True:
            t0 = time.time()
            nxt = typed_command(state)
            if nxt:
                break
            width, height = terminal_size()
            cols, rows = max(40, width - 1), max(16, height - 1)
            if (cols, rows) != size:  # terminal was resized -> clear and redraw
                size = (cols, rows)
                emit("\x1b[0m\x1b[48;2;0;0;3m\x1b[2J")
            emit(to_text(render(time.time() - start, cols, rows)))
            time.sleep(max(0.0, 1 / FPS - (time.time() - t0)))
    except KeyboardInterrupt:
        pass
    finally:
        emit("\x1b[0m\x1b[?25h\x1b[?1049l")
    if nxt and nxt != "quit":  # another model was started -> switch to it
        sys.exit(subprocess.call([sys.executable, "-u", nxt]))


if __name__ == "__main__":
    play()
