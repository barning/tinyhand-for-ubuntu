"""
ArmView - GTK DrawingArea that renders the pointer hand.

Port of Sources/TinyHand/ArmView.swift to Python with GTK 3 and cairo.
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, GdkPixbuf, Gdk, GLib
import cairo
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .ink import Ink

if TYPE_CHECKING:
    # For type checking only - avoid circular import
    from . import pointer_style as ps_module
    PointerStyle = ps_module.PointerStyle
else:
    PointerStyle = None


@dataclass
class HandAsset:
    """
    Measured properties of a hand PNG image.

    All coordinates except aspect are normalized to image height (0..1).
    """
    image: GdkPixbuf.Pixbuf
    aspect: float
    hand_top: float
    tip: float
    wrist: float
    rod_end: float
    tip_x: float
    rod_x: float
    hand_min_x: float
    hand_max_x: float


def _int_rgb_to_float(ink: tuple) -> tuple:
    """Convert integer RGB (0-255) to float RGB (0-1)."""
    return tuple(v / 255.0 for v in ink)


class ArmView(Gtk.DrawingArea):
    """
    GTK DrawingArea that draws the currently selected pointer hand at the pointer position.

    Public API:
    - style: PointerStyle property (get/set)
    - held: bool property
    - press(): trigger short press animation
    - set_position(x, y): set pointer tip position in screen coordinates

    Attributes:
    - ink: Ink instance for stroke drawing
    """

    # Constants from Swift
    MIN_ROD_FRAC = 0.05
    GRIP_LEAN_FRAC = 0.30
    GRIP_DEPTH_FRAC = 0.12
    GRIP_FOLLOW = 0.08
    LIFT_FRAC = 0.06

    # Default pointer size
    DEFAULT_POINTER_SIZE = 0.13

    def __init__(self):
        """Initialize ArmView."""
        super().__init__()
        self.set_app_paintable(True)

        # State
        self._style: Optional[any] = None
        self._asset: Optional[HandAsset] = None
        self._display_pixbuf: Optional[GdkPixbuf.Pixbuf] = None
        self._held = False
        self._pointer_x = 0.0
        self._pointer_y = 0.0
        self._press_amount = 0.0
        self._grip_x: Optional[float] = None
        self._grip_target: Optional[float] = None
        self._hand_len_frac = self.DEFAULT_POINTER_SIZE
        self._show_shadow = True
        self._display_image_height = 0
        self._last_pose: list = []
        self._last_laser_pose: list = []
        self._pointer_hidden = False

        # Ink instance
        self.ink = Ink()

        # GTK-specific
        self.connect('draw', self._on_draw)
        self.connect('realize', self._on_realize)

        # Initialize PointerStyle reference
        self._ensure_pointer_style()

        # Set default style
        laser_style = self._get_laser_style()
        if laser_style:
            self.style = laser_style

    def _ensure_pointer_style(self):
        """Lazy import of PointerStyle from pointer_style module."""
        global PointerStyle
        if PointerStyle is None:
            try:
                from . import pointer_style
                PointerStyle = pointer_style.PointerStyle
            except ImportError:
                # Create a minimal stub if pointer_style not available
                from dataclasses import dataclass as dc
                @dc
                class PointerStyleStub:
                    id: str
                    name: str
                    kind: str
                    image_path: Optional[Path]
                    ink: tuple
                PointerStyle = PointerStyleStub

    def _get_laser_style(self):
        """Create or return a laser PointerStyle."""
        self._ensure_pointer_style()

        if PointerStyle is not None:
            try:
                from . import pointer_style
                return pointer_style.style_by_id('laser')
            except Exception:
                pass

        # Create a stub laser style
        class LaserStyle:
            id = 'laser'
            name = 'Laser dot'
            kind = 'laser'
            image_path = None
            ink = (1.0, 0.16, 0.12)
        return LaserStyle()

    @property
    def style(self) -> Optional[any]:
        """Get the current pointer style."""
        return self._style

    @style.setter
    def style(self, value: any):
        """Set the pointer style and reload its image."""
        self._style = value
        self._update_style()

        # Redraw
        if self.get_window() is not None:
            self.queue_draw()

    @property
    def held(self) -> bool:
        """Whether the hand shows its pressed look."""
        return self._held

    @held.setter
    def held(self, value: bool):
        self._held = value
        if self.get_window() is not None:
            self.queue_draw()

    @property
    def pointer_hidden(self) -> bool:
        """Whether the pointer is hidden."""
        return self._pointer_hidden

    @pointer_hidden.setter
    def pointer_hidden(self, value: bool):
        self._pointer_hidden = value
        if self.get_window() is not None:
            self.queue_draw()

    def _update_style(self):
        """Update the hand asset when style changes."""
        if self._style is None:
            return

        # Try to load the image
        if hasattr(self._style, 'kind') and self._style.kind == 'laser':
            self._asset = None
            return

        # Get the image path from the style
        image_path = self._style.image_path if hasattr(self._style, 'image_path') else None

        # Find and load the image
        # Try multiple locations
        from . import paths
        assets_dir = paths.ASSETS_DIR

        possible_paths: list = []
        if image_path is not None:
            # image_path might be a Path or a string
            if isinstance(image_path, Path):
                if image_path.exists():
                    possible_paths.append(str(image_path))
                # Also try relative to assets dir
                possible_paths.append(str(assets_dir / image_path.name))
            else:
                possible_paths.append(image_path)
                possible_paths.append(str(assets_dir / image_path))

        # Also try hand_<id>.png
        if hasattr(self._style, 'id'):
            possible_paths.append(str(assets_dir / f"hand_{self._style.id}.png"))

        # Try without assets dir
        if hasattr(self._style, 'id'):
            possible_paths.append(f"hand_{self._style.id}.png")
            possible_paths.append(f"assets/hand_{self._style.id}.png")

        pixbuf = None
        for p in possible_paths:
            if os.path.exists(p):
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file(p)
                    break
                except Exception:
                    continue

        if pixbuf is None:
            # Fall back to laser if we can't find the image
            self._style = self._get_laser_style()
            self._asset = None
            return

        # Measure the image to create HandAsset
        self._asset = self._measure_image(pixbuf)

    def _measure_image(self, pixbuf: GdkPixbuf.Pixbuf) -> HandAsset:
        """
        Measure a hand PNG image to extract geometric properties.

        This is a port of the HandAsset.measure() method from Swift.
        """
        width = pixbuf.get_width()
        height = pixbuf.get_height()

        # Get the alpha channel from the pixbuf
        rowstride = pixbuf.get_rowstride()
        pixels = pixbuf.get_pixels()
        n_channels = pixbuf.get_n_channels()

        # Extract alpha values
        alpha = bytearray(height * width)
        for y in range(height):
            for x in range(width):
                offset = y * rowstride + x * n_channels
                alpha[y * width + x] = pixels[offset + (n_channels - 1)]  # alpha is last channel

        def count_nontransparent(y: int) -> int:
            """Count non-transparent pixels in row y."""
            start = y * width
            end = start + width
            return sum(1 for i in range(start, end) if alpha[i] > 128)

        def center_x(y: int) -> float:
            """Find the center X of non-transparent pixels in row y."""
            start = y * width
            end = start + width
            pixels_in_row = [i for i in range(start, end) if alpha[i] > 128]
            if not pixels_in_row:
                return 0.5
            min_x = min(pixels_in_row) - start
            max_x = max(pixels_in_row) - start
            return (min_x + max_x) / 2 / width

        def find_min_max_x(y_start: int, y_end: int):
            """Find min and max X of non-transparent pixels between rows y_start and y_end."""
            min_x = width
            max_x = 0
            for y in range(y_start, min(y_end, height)):
                start = y * width
                for x in range(width):
                    if alpha[start + x] > 128:
                        min_x = min(min_x, x)
                        max_x = max(max_x, x)
            return min_x, max_x

        # Find the top row with non-transparent pixels
        counts = [count_nontransparent(y) for y in range(height)]

        top = None
        for y in range(height):
            if counts[y] > 0:
                top = y
                break

        if top is None:
            # Fallback if image is all transparent
            return HandAsset(
                image=pixbuf,
                aspect=width / height,
                hand_top=0, tip=0, wrist=0.5, rod_end=1.0,
                tip_x=0.5, rod_x=0.5, hand_min_x=0, hand_max_x=1
            )

        # Find wrist: where the hand narrows
        search_end = min(height, top + int(0.45 * height))
        max_w = max(counts[top:search_end]) if search_end > top else counts[top]

        if max_w == 0:
            return HandAsset(
                image=pixbuf,
                aspect=width / height,
                hand_top=0, tip=0, wrist=0.5, rod_end=1.0,
                tip_x=0.5, rod_x=0.5, hand_min_x=0, hand_max_x=1
            )

        fist = None
        for y in range(top, height):
            if counts[y] > 0.6 * max_w:
                fist = y
                break

        if fist is None:
            fist = top

        wrist = None
        for y in range(fist, height):
            if counts[y] < 0.35 * max_w:
                wrist = y
                break

        if wrist is None:
            wrist = height - 1

        # Find rodEnd
        rod_w = counts[min(height - 1, wrist + height // 50)]
        last_row = height - 1
        for y in range(last_row, wrist, -1):
            if counts[y] > 0:
                last_row = y
                break

        from_y = min(height - 1, wrist + height // 33)
        handle = None
        for y in range(from_y, height):
            if counts[y] > 1.8 * rod_w:
                handle = y
                break

        rod_end = handle if handle is not None else last_row

        # Find min/max X in hand region
        min_x, max_x = find_min_max_x(top, wrist)

        fh = float(height)

        return HandAsset(
            image=pixbuf,
            aspect=width / fh,
            hand_top=max(0, float(top) - 0.004 * fh) / fh,
            tip=float(top) / fh,
            wrist=float(wrist) / fh,
            rod_end=float(rod_end) / fh,
            tip_x=center_x(min(height - 1, top + height // 200)),
            rod_x=center_x((wrist + rod_end) // 2),
            hand_min_x=float(min_x) / float(width),
            hand_max_x=float(max_x) / float(width)
        )

    def press(self):
        """Trigger a short press animation."""
        self._press_amount = 1.0
        if self.get_window() is not None:
            self.queue_draw()
            # Schedule decrement
            if hasattr(self, '_press_timeout_id'):
                GLib.source_remove(self._press_timeout_id)
            self._press_timeout_id = GLib.timeout_add(50, self._press_animation_step)

    def _press_animation_step(self):
        """Animation step for press effect."""
        if self._held:
            if self.get_window() is not None:
                self.queue_draw()
            return True  # Keep running if held

        self._press_amount += (0 - self._press_amount) * 0.18
        if self._press_amount > 0.002:
            if self.get_window() is not None:
                self.queue_draw()
            return True

        self._press_amount = 0.0
        if self.get_window() is not None:
            self.queue_draw()
        return False

    def set_position(self, x: float, y: float):
        """Set the pointer tip position in screen coordinates."""
        self._pointer_x = x
        self._pointer_y = y
        if self.get_window() is not None:
            self.queue_draw()

    def aim(self, cursor_x: float, cursor_y: float):
        """Aim the pointer at the cursor position.

        This is the main drawing logic, called when the cursor moves.
        """
        self._pointer_x = cursor_x
        self._pointer_y = cursor_y
        self._aim_internal(cursor_x, cursor_y)

    def _aim_internal(self, cursor_x: float, cursor_y: float):
        """Internal aim implementation."""
        if not self.get_realized():
            return

        alloc = self.get_allocation()
        screen_h = alloc.height
        screen_w = alloc.width

        if screen_h <= 0:
            return

        target_x = cursor_x + self.GRIP_LEAN_FRAC * screen_w
        target_x = max(screen_w * 0.15, min(target_x, screen_w * 1.05))

        gx = self._grip_x + (target_x - self._grip_x) * self.GRIP_FOLLOW if self._grip_x is not None else target_x
        self._grip_x = gx
        self._grip_target = target_x

        # Grip sits below the bottom edge, as the group does in ArmView.swift.
        grip_y = (1 + self.GRIP_DEPTH_FRAC) * screen_h
        grip = (gx, grip_y)

        if not self._held:
            self._press_amount += (0 - self._press_amount) * 0.18

        if self._style is not None and hasattr(self._style, 'kind') and self._style.kind == 'laser':
            self._aim_laser(cursor_x, cursor_y)
            return

        if self._asset is None:
            return

        self._update_display_image(self._asset)

        dx = cursor_x - grip[0]
        dy = cursor_y - grip[1]
        reach = math.hypot(dx, dy)
        aim_angle = math.atan2(dy, dx)

        hand_pts = self._hand_len_frac * screen_h * (1 - 0.06 * self._press_amount)
        s = hand_pts / (self._asset.wrist - self._asset.hand_top)
        width_pts = s * self._asset.aspect
        hand_tip_pts = (self._asset.wrist - self._asset.tip) * s
        tip_off_x = (self._asset.tip_x - self._asset.rod_x) * width_pts

        along = math.sqrt(max(0, reach * reach - tip_off_x * tip_off_x))
        rod_len = max(self.MIN_ROD_FRAC * screen_h, along - hand_tip_pts)
        tip_angle = math.atan2(rod_len + hand_tip_pts, tip_off_x)
        # GTK's y axis points down, so the sign of the Swift rotation flips.
        rotation = aim_angle + tip_angle

        lift = self._current_lift(screen_h)
        sx = lift * 0.6
        sy = -lift

        # Calculate shadow offset with rotation
        shadow_offset_x = sx * math.cos(-rotation) - sy * math.sin(-rotation)
        shadow_offset_y = sx * math.sin(-rotation) + sy * math.cos(-rotation)

        pose = [
            rotation,
            rod_len,
            hand_pts,
            width_pts,
            grip[0],
            lift,
            self._press_amount,
            1 if self._show_shadow else 0,
            self._asset.aspect
        ]
        rounded_pose = [round(v * 100) for v in pose]

        if rounded_pose != self._last_pose:
            self._last_pose = rounded_pose
            if self.get_window() is not None:
                self.queue_draw()

    def _current_lift(self, screen_h: float) -> float:
        """Calculate current lift amount."""
        return self.LIFT_FRAC * screen_h * (1 - 0.8 * self._press_amount)

    def _aim_laser(self, cursor_x: float, cursor_y: float):
        """Aim the laser dot at the cursor position."""
        press = self._press_amount
        r = max(4, self.get_allocation().height * 0.0038 * self._hand_len_frac / 0.13) * (1 + 0.2 * press)
        laser_pose = [r, cursor_x, cursor_y]
        rounded_pose = [round(v * 100) for v in laser_pose]

        if rounded_pose != self._last_laser_pose:
            self._last_laser_pose = rounded_pose
            if self.get_window() is not None:
                self.queue_draw()

    def _update_display_image(self, asset: HandAsset):
        """Update the display image based on the current size."""
        full = asset.image
        scale = self.get_scale_factor() or 2
        rest_pts = self._hand_len_frac * self.get_allocation().height / (asset.wrist - asset.hand_top)
        step = 64
        needed = (int(round(rest_pts * scale)) + step - 1) // step * step
        height = needed if needed >= full.get_height() * 9 / 10 else max(step, needed)

        if height != self._display_image_height:
            self._display_image_height = height
            if height == full.get_height():
                self._display_pixbuf = full
            else:
                # Scale the image
                new_width = int(full.get_width() * height / full.get_height())
                self._display_pixbuf = full.scale_simple(
                    new_width,
                    height,
                    GdkPixbuf.InterpType.BILINEAR
                )

    def _on_realize(self, widget):
        """Handle realize event."""
        pass

    def _on_draw(self, widget, cr: cairo.Context):
        """Handle draw event - render the pointer and ink."""
        alloc = self.get_allocation()

        # Set up the cairo context for screen coordinates
        # In GTK, the drawing area's coordinate system has (0,0) at top-left

        # Draw ink strokes
        self.ink.draw(cr)

        # Check if pointer is hidden
        if self._pointer_hidden:
            return True

        # Check if style is laser
        if self._style is not None and hasattr(self._style, 'kind') and self._style.kind == 'laser':
            self._draw_laser(cr)
            return True

        # Draw hand/rod
        if self._asset is not None and self._grip_x is not None:
            self._draw_hand(cr)

        return True

    def _draw_laser(self, cr: cairo.Context):
        """Draw the laser dot."""
        if not self._last_laser_pose or len(self._last_laser_pose) < 3:
            return

        r = self._last_laser_pose[0] / 100
        cursor_x = self._last_laser_pose[1] / 100
        cursor_y = self._last_laser_pose[2] / 100

        press = self._press_amount
        core = r * 0.45

        # Get ink color from style or use red
        if self._style is not None and hasattr(self._style, 'ink'):
            ink_color = self._style.ink
            if isinstance(ink_color[0], int):  # if integer RGB
                rgb = tuple(v / 255.0 for v in ink_color)
            else:
                rgb = ink_color
        else:
            rgb = (1.0, 0.16, 0.12)  # Ink.RED

        cr.save()

        # Shadow
        shadow_radius = r * (2.2 + 1.0 * press)
        cr.set_source_rgba(rgb[0], rgb[1], rgb[2], 0.18)
        cr.arc(cursor_x, cursor_y, r + shadow_radius, 0, 2 * math.pi)
        cr.fill()

        # Dot
        cr.set_source_rgb(rgb[0], rgb[1], rgb[2])
        cr.arc(cursor_x, cursor_y, r, 0, 2 * math.pi)
        cr.fill()

        # Core
        cr.set_source_rgba(1, 0.86, 0.82, 0.95)
        cr.arc(cursor_x, cursor_y, core, 0, 2 * math.pi)
        cr.fill()

        cr.restore()

    def _draw_hand(self, cr: cairo.Context):
        """Draw the hand and rod, anchored at the grip below the view."""
        if not self._last_pose or len(self._last_pose) < 9:
            return
        if self._display_pixbuf is None or self._asset is None:
            return

        rotation = self._last_pose[0] / 100
        rod_len = self._last_pose[1] / 100
        hand_pts = self._last_pose[2] / 100
        width_pts = self._last_pose[3] / 100
        grip_x = self._last_pose[4] / 100

        grip_y = (1 + self.GRIP_DEPTH_FRAC) * self.get_allocation().height

        # Asset fractions are top-down (0 = image top): rod is wrist..rod_end, hand is hand_top..wrist.
        self._draw_layer(
            cr, self._display_pixbuf, rod_len, width_pts, grip_x, grip_y, rotation,
            0, self._asset.wrist, self._asset.rod_end)
        self._draw_layer(
            cr, self._display_pixbuf, hand_pts, width_pts, grip_x, grip_y, rotation,
            rod_len, self._asset.hand_top, self._asset.wrist)

    def _draw_layer(self, cr: cairo.Context, pixbuf: GdkPixbuf.Pixbuf,
                    height_pts: float, width_pts: float, grip_x: float, grip_y: float,
                    rotation: float, y_offset: float,
                    src_top: float, src_bottom: float):
        """Draw one layer (rod or hand) of the sprite, rotated about the grip.

        The layer covers local y in [-(y_offset + height), -y_offset]: local up is
        negative y, so the layer rises from the grip. The rows of the source image
        from src_top to src_bottom (fractions of the image height, top = 0) are
        scaled into that rectangle.
        """
        if width_pts <= 0 or height_pts <= 0:
            return
        img_w = pixbuf.get_width()
        img_h = pixbuf.get_height()
        src_y0 = src_top * img_h
        src_y1 = src_bottom * img_h
        src_h = src_y1 - src_y0
        if src_h <= 0:
            return

        top = -(y_offset + height_pts)
        cr.save()
        cr.translate(grip_x, grip_y)
        cr.rotate(rotation)
        # The grip is the rod's pivot column (rod_x), as in the Swift group anchor.
        cr.translate(-self._asset.rod_x * width_pts, 0)
        cr.rectangle(0, top, width_pts, height_pts)
        cr.clip()
        cr.translate(0, top)
        cr.scale(width_pts / img_w, height_pts / src_h)
        Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, -src_y0)
        cr.paint()
        cr.restore()

    def get_ink_width(self) -> float:
        """Get the ink line width based on current size."""
        return max(3, self.get_allocation().height * 0.0055)

    def set_hand_len_frac(self, value: float):
        """Set the hand length fraction."""
        self._hand_len_frac = value

    def set_show_shadow(self, value: bool):
        """Set whether to show shadow."""
        self._show_shadow = value
