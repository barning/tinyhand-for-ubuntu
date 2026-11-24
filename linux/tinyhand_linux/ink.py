"""
Ink - stroke storage and rendering for TinyHand.

Port of Sources/TinyHand/Ink.swift to Python with cairo.
"""

import cairo
import math
import time
from typing import List, Tuple, Optional


class Ink:
    """
    Stores strokes as lists of (x, y) points in screen coordinates
    (top-left origin, as GTK uses).

    Public API:
    - begin(x, y) - start a new stroke
    - extend(x, y) - add a point to the current stroke
    - end() - finish the current stroke
    - clear() - remove all strokes
    - has_strokes - property indicating if there are any strokes
    - arrow_on_last - property to enable arrowhead on last stroke
    - draw(cr, rgb) - render all strokes to a cairo context
    """

    # Default colors from Swift
    PURPLE = (0.53, 0.33, 0.95)
    RED = (1.0, 0.16, 0.12)

    @staticmethod
    def hex_to_rgb(v: int) -> Tuple[float, float, float]:
        """Convert a hex color value to RGB tuple (0..1)."""
        r = ((v >> 16) & 0xFF) / 255.0
        g = ((v >> 8) & 0xFF) / 255.0
        b = (v & 0xFF) / 255.0
        return (r, g, b)

    def __init__(self):
        """Initialize Ink with default settings."""
        # Completed strokes as (points, finished_at); finished_at is a time.monotonic() value.
        self._strokes: List[Tuple[List[Tuple[float, float]], float]] = []
        self._current_stroke: Optional[List[Tuple[float, float]]] = None
        self._arrow_on_last = False
        self._color = self.PURPLE
        self._line_width = 2.0
        self._scale = 2.0
        self._fade_seconds = 3.0  # default from Preferences

    @property
    def color(self) -> Tuple[float, float, float]:
        return self._color

    @color.setter
    def color(self, value: Tuple[float, float, float]):
        self._color = value

    @property
    def line_width(self) -> float:
        return self._line_width

    @line_width.setter
    def line_width(self, value: float):
        self._line_width = value

    @property
    def scale(self) -> float:
        return self._scale

    @scale.setter
    def scale(self, value: float):
        self._scale = value

    @property
    def fade_seconds(self) -> float:
        return self._fade_seconds

    @fade_seconds.setter
    def fade_seconds(self, value: float):
        self._fade_seconds = value

    @property
    def arrow_on_last(self) -> bool:
        return self._arrow_on_last

    @arrow_on_last.setter
    def arrow_on_last(self, value: bool):
        self._arrow_on_last = value

    @property
    def has_strokes(self) -> bool:
        """Returns True if there are any completed strokes."""
        return len(self._strokes) > 0

    @property
    def is_drawing(self) -> bool:
        """Returns True if currently drawing a stroke."""
        return self._current_stroke is not None

    def begin(self, x: float, y: float):
        """Start a new stroke at the given point."""
        self._current_stroke = [(x, y)]

    def extend(self, x: float, y: float):
        """Extend the current stroke to the given point.

        Only adds the point if it's at least 1.5 units away from the last point.
        """
        if self._current_stroke is None:
            return
        last_x, last_y = self._current_stroke[-1]
        distance = math.hypot(x - last_x, y - last_y)
        if distance < 1.5:
            return
        self._current_stroke.append((x, y))

    def end(self):
        """Finish the current stroke and add it to the stroke list."""
        if self._current_stroke is None:
            return

        # Add arrowhead if enabled
        if self._arrow_on_last and len(self._current_stroke) > 0:
            # The arrowhead is rendered during draw, not stored in points
            pass

        # Store the completed stroke
        self._strokes.append((self._current_stroke.copy(), time.monotonic()))
        self._current_stroke = None
        self._arrow_on_last = False

    def clear(self):
        """Remove all strokes (both completed and current)."""
        self._strokes.clear()
        self._current_stroke = None
        self._arrow_on_last = False

    def draw(self, cr: cairo.Context, rgb: Optional[Tuple[float, float, float]] = None):
        """Draw the strokes; finished ones fade out after fade_seconds (0 keeps them).

        Args:
            cr: cairo context to draw to
            rgb: optional RGB colour tuple (0..1) to override the ink colour
        """
        color = rgb if rgb is not None else self._color
        now = time.monotonic()
        fade = self._fade_seconds

        # Drop strokes that have faded out completely.
        if fade > 0:
            self._strokes = [(pts, t) for pts, t in self._strokes if now - t < fade]

        cr.save()
        cr.set_line_width(self._line_width)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

        for stroke, finished_at in self._strokes:
            alpha = 1.0
            if fade > 0:
                age = now - finished_at
                # Fade over the last second before the stroke is removed.
                alpha = min(1.0, max(0.0, (fade - age) / min(1.0, fade)))
            cr.set_source_rgba(color[0], color[1], color[2], alpha)
            self._draw_stroke_path(cr, stroke, False)
            cr.stroke()

        if self._current_stroke is not None and len(self._current_stroke) > 0:
            cr.set_source_rgba(color[0], color[1], color[2], 1.0)
            self._draw_stroke_path(cr, self._current_stroke, self._arrow_on_last)
            cr.stroke()

        cr.restore()

    def _draw_stroke_path(self, cr: cairo.Context, points: List[Tuple[float, float]], with_arrow: bool):
        """Create and stroke a path for the given points.

        Args:
            cr: cairo context
            points: list of (x, y) tuples
            with_arrow: whether to add arrowhead to the end
        """
        if len(points) == 0:
            return

        first = points[0]
        cr.move_to(first[0], first[1])

        if len(points) == 1:
            # Single point: draw a tiny line to make it visible
            cr.line_to(first[0], first[1])
        else:
            # Smooth path with quadratic curves (approximated with bezier curves)
            for i in range(1, len(points)):
                p = points[i]
                prev = points[i - 1]
                mid_x = (prev[0] + p[0]) / 2
                mid_y = (prev[1] + p[1]) / 2

                # Quadratic curve: move to prev, curve to mid with control at prev
                # In cairo, we use cubic bezier: P0 -> P2 with control P1
                # To approximate quadratic (P0 -> P2 with control C):
                # Use P0 -> (C*2/3 + P2*1/3) with control C*1/3 + P0*2/3 and C*2/3 + P2*1/3
                # Simpler: just use line segments for now, or use curve_to

                # For simplicity and to match the Swift smoothPath, we'll use line_to
                # But to get the smoothed effect, we need to use curve_to
                cx = prev[0]
                cy = prev[1]
                # Control point is the previous point
                cr.curve_to(mid_x, mid_y, mid_x, mid_y, p[0], p[1])

            # Add final line segment to last point
            if len(points) > 1:
                last = points[-1]
                cr.line_to(last[0], last[1])

        # Add arrowhead if requested
        if with_arrow and len(points) > 0:
            self._add_arrowhead(cr, points, cr.get_line_width())

    def _add_arrowhead(self, cr: cairo.Context, points: List[Tuple[float, float]], line_width: float):
        """Add an arrowhead to the end of the stroke path.

        The arrowhead is aimed along the last stretch of the stroke so a wobble
        at the very end doesn't twist it.
        """
        if len(points) == 0:
            return

        end = points[-1]

        # Find a point at least size*1.2 away from the end
        size = max(14, line_width * 3.2)
        back = end
        for i in range(len(points) - 2, -1, -1):
            candidate = points[i]
            dist = math.hypot(end[0] - candidate[0], end[1] - candidate[1])
            if dist >= size * 1.2:
                back = candidate
                break

        length = math.hypot(end[0] - back[0], end[1] - back[1])
        if length < 1:
            return

        head = min(size, length * 0.8)
        angle = math.atan2(end[1] - back[1], end[0] - back[0])
        spread = math.pi / 7

        for side in [-1, 1]:
            a = angle + math.pi + side * spread
            arrow_x = end[0] + math.cos(a) * head
            arrow_y = end[1] + math.sin(a) * head
            cr.move_to(end[0], end[1])
            cr.line_to(arrow_x, arrow_y)
