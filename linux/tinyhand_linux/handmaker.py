"""Hand image maker: checks a user's hand PNG and puts it on a stick.

Port of Sources/TinyHand/HandMaker.swift to Pillow. Rewritten from the Swift
source (the Linux file from the earlier session could not be fully recovered).

API (same contract as the rest of the port):
- make(input_path) -> (PIL.Image RGBA composed on a stick, ink_rgb as 0-255 tuple)
- write(image, out_path) -> saves a PNG
- HandProblem(message): raised with the same messages as the Swift code.
"""
from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Tuple, Union

from PIL import Image


class HandProblem(Exception):
    """A problem with the chosen image; `.message` is shown to the user."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


Problem = HandProblem  # Swift name, kept for compatibility


CANVAS_W = 1024
CANVAS_H = 1536
HAND_TOP = 150
HAND_HEIGHT = 560


def _alpha_grid(img: Image.Image):
    w, h = img.size
    data = list(img.getchannel("A").getdata())
    return w, h, data


def _bounds(w: int, h: int, alpha: list):
    minx, miny, maxx, maxy = w, h, -1, -1
    for i, a in enumerate(alpha):
        if a > 128:
            x = i % w
            y = i // w
            minx = min(minx, x)
            maxx = max(maxx, x)
            miny = min(miny, y)
            maxy = max(maxy, y)
    if maxx < 0:
        return None
    return minx, miny, maxx, maxy


def _bottom_span(w: int, alpha: list, box) -> Tuple[int, float]:
    minx, miny, maxx, maxy = box
    bh = maxy - miny + 1
    lo, hi = w, -1
    for y in range(max(miny, maxy - max(2, bh * 4 // 100)), maxy + 1):
        for x in range(minx, maxx + 1):
            if alpha[y * w + x] > 128:
                lo = min(lo, x)
                hi = max(hi, x)
    if hi < 0:
        return 0, (minx + maxx) / 2
    return hi - lo + 1, (lo + hi) / 2


def _check(img: Image.Image) -> None:
    w, h, alpha = _alpha_grid(img)

    # Edges must be transparent (the hand must not touch them).
    edge = 0
    edge_solid = 0
    for x in range(w):
        edge += 2
        edge_solid += (alpha[x] > 32) + (alpha[(h - 1) * w + x] > 32)
    for y in range(h):
        edge += 2
        edge_solid += (alpha[y * w] > 32) + (alpha[y * w + w - 1] > 32)
    if edge_solid / edge > 0.02:
        raise HandProblem("The background isn't transparent, or the hand touches the edge of the image.")

    # Must be one connected shape.
    step = max(1, min(w, h) // 256)
    gw, gh = w // step, h // step
    grid = [alpha[(gy * step) * w + gx * step] > 128 for gy in range(gh) for gx in range(gw)]
    seen = [False] * (gw * gh)
    sizes = []
    for start in range(len(grid)):
        if not grid[start] or seen[start]:
            continue
        queue = deque([start])
        seen[start] = True
        n = 0
        while queue:
            i = queue.pop()
            n += 1
            x, y = i % gw, i // gw
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < gw and 0 <= ny < gh:
                    j = ny * gw + nx
                    if grid[j] and not seen[j]:
                        seen[j] = True
                        queue.append(j)
        sizes.append(n)
    if not sizes:
        raise HandProblem("The image is empty.")
    if max(sizes) / sum(sizes) < 0.97:
        raise HandProblem("The image has more than one thing in it. Use a single hand.")

    box = _bounds(w, h, alpha)
    if box is None:
        raise HandProblem("The image is empty.")
    minx, miny, maxx, maxy = box
    bw = maxx - minx + 1
    bh = maxy - miny + 1
    aspect = bh / bw
    if aspect < 1.05 or aspect > 2.8:
        raise HandProblem("The hand should stand upright, taller than it is wide.")
    if bh / h < 0.5:
        raise HandProblem("The hand is too small in the image. Crop it closer.")

    # The top must be a single finger.
    top_band = max(2, bh * 8 // 100)
    fmin, fmax = w, 0
    for y in range(miny, miny + top_band):
        for x in range(minx, maxx + 1):
            if alpha[y * w + x] > 128:
                fmin = min(fmin, x)
                fmax = max(fmax, x)
    if fmax >= fmin and (fmax - fmin + 1) / bw > 0.4:
        raise HandProblem("The top of the image should be a single finger pointing up.")

    # The bottom must be a flat wrist or cuff.
    base_width, _ = _bottom_span(w, alpha, box)
    if base_width / bw < 0.2:
        raise HandProblem("The hand should end in a flat wrist or cuff at the bottom.")

    # No soft shadow or glow.
    soft = 0
    any_px = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            a = alpha[y * w + x]
            if a > 20:
                any_px += 1
                if a < 200:
                    soft += 1
    if soft / max(1, any_px) > 0.08:
        raise HandProblem("The hand has a soft shadow or glow around it. Ask for no shadow.")


def _ink(img: Image.Image) -> Tuple[int, int, int]:
    """Pick the most saturated mid-tone colour in the hand as its ink colour."""
    w, h = img.size
    px = img.load()
    buckets = {}
    for y in range(0, h, 3):
        for x in range(0, w, 3):
            r, g, b, a = px[x, y]
            if a <= 200:
                continue
            rf, gf, bf = r / 255, g / 255, b / 255
            key = (int(rf * 5), int(gf * 5), int(bf * 5))
            n, sr, sg, sb = buckets.get(key, (0, 0.0, 0.0, 0.0))
            buckets[key] = (n + 1, sr + rf, sg + gf, sb + bf)

    best = (-1.0, 0.53, 0.33, 0.95)
    for n, sr, sg, sb in buckets.values():
        r, g, b = sr / n, sg / n, sb / n
        hi, lo = max(r, g, b), min(r, g, b)
        sat = 0 if hi == 0 else (hi - lo) / hi
        lum = 0.3 * r + 0.59 * g + 0.11 * b
        score = n * (0.25 + sat) * (1 if 0.12 < lum < 0.85 else 0.15)
        if score > best[0]:
            best = (score, r, g, b)

    _, r, g, b = best
    hi, lo = max(r, g, b), min(r, g, b)
    if hi - lo < 0.08:
        r, g, b = 0.42, 0.45, 0.5
    elif hi > 0.82:
        r, g, b = r * 0.82 / hi, g * 0.82 / hi, b * 0.82 / hi
    return (min(255, int(r * 255)), min(255, int(g * 255)), min(255, int(b * 255)))


def _compose(img: Image.Image) -> Image.Image:
    """Scale the hand onto a canvas and draw a black stick under it."""
    w, h, alpha = _alpha_grid(img)
    box = _bounds(w, h, alpha)
    minx, miny, maxx, maxy = box
    bw = maxx - minx + 1
    bh = maxy - miny + 1
    scale = min(HAND_HEIGHT / bh, 700 / bw)
    draw_w = max(1, round(w * scale))
    draw_h = max(1, round(h * scale))
    _, wrist_center = _bottom_span(w, alpha, box)
    wrist_x = (wrist_center + 0.5) * scale
    origin_x = CANVAS_W / 2 - wrist_x
    origin_top = HAND_TOP - miny * scale
    hand_bottom = HAND_TOP + bh * scale

    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))

    rod_w = min(76, max(54, bw * scale * 0.18))
    rod_top = hand_bottom - 30
    rod_bottom = 1462
    rod_left = CANVAS_W / 2 - rod_w / 2
    rod = Image.new("RGBA", (round(rod_w), round(rod_bottom - rod_top)), (0, 0, 0, 0))
    rod_px = rod.load()
    stops = [(0.0, (0, 0, 0)), (0.22, (18, 18, 20)), (0.45, (58, 58, 62)), (0.75, (18, 18, 20)), (1.0, (0, 0, 0))]
    rw, rh = rod.size
    for x in range(rw):
        t = x / max(1, rw - 1)
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                k = (t - t0) / (t1 - t0)
                col = tuple(round(c0[j] + (c1[j] - c0[j]) * k) for j in range(3))
                break
        for y in range(rh):
            rod_px[x, y] = col + (255,)
    canvas.paste(rod, (round(rod_left), round(rod_top)), rod)

    hand = img.resize((draw_w, draw_h), Image.LANCZOS)
    canvas.alpha_composite(hand, (round(origin_x), round(origin_top)))
    return canvas


def make(input_path: Union[str, Path]) -> Tuple[Image.Image, Tuple[int, int, int]]:
    """Check a hand image and return (composed image, ink colour as 0-255 RGB)."""
    try:
        source = Image.open(input_path)
        has_alpha = source.mode in ("RGBA", "LA") or "transparency" in source.info
        img = source.convert("RGBA")
    except (OSError, ValueError):
        raise HandProblem("That file isn't an image TinyHand can read.")

    if not has_alpha:
        raise HandProblem("The image needs a transparent background. Save it as a PNG with transparency.")

    w, h = img.size
    if w < 64 or h < 64:
        raise HandProblem("The image is too small. Use one at least 512 pixels tall.")

    _check(img)
    return _compose(img), _ink(img)


def write(image: Image.Image, out_path: Union[str, Path]) -> None:
    """Save the composed hand as a PNG."""
    try:
        image.save(out_path, format="PNG")
    except OSError:
        raise HandProblem("TinyHand couldn't save the hand.")


if __name__ == "__main__":
    import sys
    import tempfile

    # Non-image file: must raise HandProblem.
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"not a png")
    try:
        make(f.name)
        raise SystemExit("expected HandProblem for a non-image file")
    except HandProblem as problem:
        print(f"non-image rejected: {problem.message}")

    # Tiny image: must raise HandProblem.
    tiny = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
    tiny_path = Path(tempfile.gettempdir()) / "th-tiny.png"
    tiny.save(tiny_path)
    try:
        make(tiny_path)
        raise SystemExit("expected HandProblem for a tiny image")
    except HandProblem as problem:
        print(f"tiny image rejected: {problem.message}")

    print("handmaker.py self-test passed")
    sys.exit(0)
