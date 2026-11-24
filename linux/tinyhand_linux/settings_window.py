"""Settings window for TinyHand Linux port.

Port of SettingsWindow.swift and SettingsView.swift from the macOS app.
Uses GTK 3 for the UI.
"""

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Pango', '1.0')

from gi.repository import Gtk, Gdk, GLib, Pango
from enum import Enum


def set_font(widget, size, weight=None, style=None):
    """Set font on a widget using Pango font description."""
    desc = f'{size}'
    if weight:
        desc = f'{weight} {desc}'
    if style:
        desc = f'{style} {desc}'
    font_desc = Pango.FontDescription(desc)
    widget.override_font(font_desc)


# Enums used by settings - defined locally since pointer_style.py doesn't have them yet
class InteractKey(Enum):
    off = 'off'
    control = 'control'
    alt = 'alt'
    command = 'command'
    
    @property
    def title(self):
        titles = {'off': 'Off', 'control': 'Control', 'alt': 'Alt', 'command': 'Super'}
        return titles.get(self.value, self.value)


class InkChoice(Enum):
    match = 'match'
    black = 'black'
    white = 'white'
    red = 'red'
    green = 'green'
    blue = 'blue'
    
    @property
    def title(self):
        titles = {'match': 'Match', 'black': 'Black', 'white': 'White', 
                  'red': 'Red', 'green': 'Green', 'blue': 'Blue'}
        return titles.get(self.value, self.value)


class TapSoundChoice(Enum):
    pop = 'pop'
    click = 'click'
    tap = 'tap'
    thud = 'thud'
    
    @property
    def title(self):
        titles = {'pop': 'Pop', 'click': 'Click', 'tap': 'Tap', 'thud': 'Thud'}
        return titles.get(self.value, self.value)


# Section definitions matching SettingsSection in SettingsView.swift
SECTIONS = [
    ('general', 'General'),
    ('pointers', 'Pointers'),
    ('appearance', 'Appearance'),
    ('drawing', 'Drawing'),
    ('sound', 'Sound'),
    ('about', 'About'),
]


class SettingsWindow(Gtk.Window):
    """Main settings window.

    Port of SettingsWindow.swift from the macOS app.

    Args:
        prefs: The Prefs object for accessing settings
        on_close: Optional callback when the window is closed
    """

    def __init__(self, prefs, on_close=None):
        super().__init__()
        self.prefs = prefs
        self.on_close = on_close
        self._current_section = 'general'
        self._section_buttons = {}
        self._pages = {}
        self._shortcut_recording_key = None
        self._shortcut_recording_button = None
        self._shortcut_original_label = None
        self._pinned_slots = []
        self._drag_source_row = None
        self._drag_target_pos = None

        self._setup_window()
        self._build_ui()
        self._ensure_css()

    def _setup_window(self):
        """Configure the window properties."""
        self.set_title('TinyHand Settings')
        self.set_default_size(780, 560)
        self.set_resizable(True)
        self.set_skip_taskbar_hint(True)
        self.connect('delete-event', lambda w, e: (self.on_close() if self.on_close else None, True)[1])
        self.connect('destroy', lambda w: self.on_close() if self.on_close else None)
        self.connect('key-press-event', self._on_key_press)
        self.add_events(Gdk.EventMask.KEY_PRESS_MASK)

    def show_section(self, name):
        """Show a specific section.

        Args:
            name: The section name ('general', 'pointers', 'appearance', 'drawing', 'sound', 'about')
        """
        if name in [s[0] for s in SECTIONS]:
            self._current_section = name
            self._content_stack.set_visible_child_name(name)
            self._update_sidebar()

    def show(self, section=None):
        """Show the window, optionally with a specific section selected.

        Args:
            section: Optional section name to show
        """
        if section:
            self._current_section = section
            self._content_stack.set_visible_child_name(section)
            self._update_sidebar()
        self.present()

    def _build_ui(self):
        """Build the main UI with sidebar and content area."""
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(main_box)

        # Sidebar
        sidebar = self._create_sidebar()
        main_box.pack_start(sidebar, False, False, 0)

        # Content stack
        self._content_stack = Gtk.Stack()
        self._content_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._content_stack.set_size_request(550, -1)
        main_box.pack_start(self._content_stack, True, True, 0)

        # Create pages
        for section_id, title in SECTIONS:
            page = self._create_page(section_id, title)
            self._content_stack.add_named(page, section_id)

    def _create_sidebar(self):
        """Create the sidebar with section buttons."""
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        sidebar.set_size_request(210, -1)
        sidebar.get_style_context().add_class('th-sidebar')
        sidebar.set_margin_top(52)
        sidebar.set_margin_bottom(0)
        sidebar.set_margin_start(10)
        sidebar.set_margin_end(10)

        # Section buttons
        for section_id, title in SECTIONS:
            btn = Gtk.Button()
            btn.set_halign(Gtk.Align.FILL)
            btn.get_style_context().add_class('th-section-btn')
            btn.set_name(f'th-btn-{section_id}')
            btn.connect('clicked', self._on_section_clicked, section_id)
            self._section_buttons[section_id] = btn

            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            hbox.set_margin_top(6)
            hbox.set_margin_bottom(6)
            hbox.set_margin_start(8)
            hbox.set_margin_end(8)
            btn.add(hbox)

            # Icon
            icon = Gtk.Label(label=self._get_section_icon(section_id))
            set_font(icon, 12, 'normal')
            icon.set_halign(Gtk.Align.CENTER)
            icon.set_valign(Gtk.Align.CENTER)
            icon.set_size_request(24, 24)
            hbox.pack_start(icon, False, False, 0)

            # Label
            label = Gtk.Label(label=title)
            label.set_halign(Gtk.Align.START)
            set_font(label, 13, 'normal')
            hbox.pack_start(label, True, True, 0)

            sidebar.pack_start(btn, False, False, 0)

        # Spacer
        sidebar.pack_start(Gtk.Box(), True, True, 0)

        # App info
        app_info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        app_info.set_margin_top(16)
        app_info.set_margin_bottom(16)
        app_info.set_margin_start(10)
        app_info.set_margin_end(10)

        app_icon = Gtk.Label(label='🖐️')
        set_font(app_icon, 22, 'normal')
        app_info.pack_start(app_icon, False, False, 0)

        app_name = Gtk.Label(label='TinyHand')
        set_font(app_name, 12, 'normal')
        app_name.get_style_context().add_class('th-app-name')
        app_info.pack_start(app_name, False, False, 0)

        app_info.pack_start(Gtk.Box(), True, True, 0)
        sidebar.pack_start(app_info, False, False, 0)

        return sidebar

    def _on_section_clicked(self, btn, section_id):
        """Handle section button click."""
        self._current_section = section_id
        self._content_stack.set_visible_child_name(section_id)
        self._update_sidebar()

    def _update_sidebar(self):
        """Update sidebar button states."""
        for section_id, btn in self._section_buttons.items():
            if section_id == self._current_section:
                btn.get_style_context().add_class('selected')
            else:
                btn.get_style_context().remove_class('selected')

    def _get_section_icon(self, section_id):
        """Get the icon for a section."""
        icons = {
            'general': '⚙️',
            'pointers': '👆',
            'appearance': '✨',
            'drawing': '✏️',
            'sound': '🔊',
            'about': 'ℹ️',
        }
        return icons.get(section_id, '?')

    def _create_page(self, section_id, title):
        """Create a content page for a section."""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.set_margin_start(28)
        page.set_margin_end(28)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        content.set_margin_top(48)
        content.set_margin_bottom(28)

        # Title
        title_label = Gtk.Label(label=title)
        title_label.set_halign(Gtk.Align.START)
        set_font(title_label, 22, 'bold')
        title_label.get_style_context().add_class('th-page-title')
        title_label.set_margin_top(6)
        content.pack_start(title_label, False, False, 0)

        # Section content
        self._add_section_content(content, section_id)

        scrolled.add(content)
        page.pack_start(scrolled, True, True, 0)

        return page

    def _add_section_content(self, parent, section_id):
        """Add section-specific content."""
        if section_id == 'general':
            self._add_general_content(parent)
        elif section_id == 'pointers':
            self._add_pointers_content(parent)
        elif section_id == 'appearance':
            self._add_appearance_content(parent)
        elif section_id == 'drawing':
            self._add_drawing_content(parent)
        elif section_id == 'sound':
            self._add_sound_content(parent)
        elif section_id == 'about':
            self._add_about_content(parent)

    # === General Section ===

    def _add_general_content(self, parent):
        """Add General section content."""
        # Shortcuts card
        card = self._create_card(parent, 'Shortcuts')
        
        toggle_btn = self._create_shortcut_button('shortcut.toggle')
        self._add_row(card, 'Turn the pointer on or off', widget=toggle_btn)
        self._add_separator(card)
        
        clear_btn = self._create_shortcut_button('shortcut.clear')
        self._add_row(card, 'Clear the drawing', widget=clear_btn)

        # Clicking for real card
        card = self._create_card(parent, 'Clicking for real')
        
        # Interact key
        combo = Gtk.ComboBoxText()
        for key in InteractKey:
            combo.append(key.value, key.title)
        try:
            combo.set_active_id(self.prefs.get('interactKey', 'off'))
        except Exception:
            pass
        combo.connect('changed', lambda c: self.prefs.set('interactKey', c.get_active_id()))
        self._add_row(card, 'Hold to use the app', detail='Clicks, drags and scrolls reach the app.', widget=combo)
        self._add_separator(card)

        # Double-tap Shift
        sw = self._create_toggle('doubleShiftClickThrough', True)
        self._add_row(card, 'Double-tap ⇧ to click through',
                       detail='Clicks reach the app and the hand stays. Double-tap again for taps.',
                       widget=sw)

        # Startup card
        card = self._create_card(parent, 'Startup')
        
        login_sw = self._create_toggle('launchAtLogin', False)
        self._add_row(card, 'Open TinyHand when you log in', widget=login_sw)

    # === Pointers Section ===

    def _add_pointers_content(self, parent):
        """Add Pointers section content."""
        # Toolbar card
        card = self._create_card(parent, 'Toolbar')
        
        toolbar_sw = self._create_toggle('showToolbar', True)
        self._add_row(card, 'Show the toolbar',
                      detail='Pops up when the pointer turns on and near the bottom of the screen.',
                      widget=toolbar_sw)
        self._add_separator(card)
        
        ink_sw = self._create_toggle('showInkButton', True)
        self._add_row(card, 'Ink button', detail='Change the colour while you present.', widget=ink_sw)

        # In your toolbar
        self._add_toolbar_slots(parent)
        
        # Your hands
        self._add_your_hands(parent)

    def _add_toolbar_slots(self, parent):
        """Add the toolbar slots section with drag-to-reorder support."""
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        group.set_margin_top(30)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_margin_start(4)
        header.set_margin_end(4)

        title = Gtk.Label(label='In your toolbar')
        title.set_halign(Gtk.Align.START)
        set_font(title, 12, 'semibold')
        title.get_style_context().add_class('th-section-subtitle')
        header.pack_start(title, True, True, 0)

        reset_btn = Gtk.Button.new_with_label('Reset')
        reset_btn.get_style_context().add_class('th-text-btn')
        reset_btn.connect('clicked', self._on_reset_toolbar)
        header.pack_start(reset_btn, False, False, 0)
        group.pack_start(header, False, False, 0)

        # Slots container using ListBox for reordering
        container = Gtk.Box()
        container.set_margin_top(10)
        container.set_margin_start(10)
        container.set_margin_end(10)
        container.set_margin_bottom(10)
        container.get_style_context().add_class('th-toolbar-row')

        try:
            pinned = self.prefs.get('pinnedStyles', [])
        except Exception:
            pinned = []

        # Create a ListBox for drag-and-drop reordering
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        listbox.set_activate_on_single_click(False)
        
        # Create a horizontal box to hold the listbox items
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        container.add(hbox)
        
        # Store reference to update order
        self._pinned_listbox = listbox
        
        # Build the row for pinned styles
        self._build_pinned_rows(hbox, pinned)
        
        # Connect reorder signal
        listbox.connect('row-reordered', self._on_pinned_reordered)
        
        group.pack_start(container, False, False, 0)

        # Description
        desc = Gtk.Label()
        if len(pinned) >= 5:
            desc.set_text('The toolbar is full. Remove a pointer to add another. Drag to reorder.')
        else:
            desc.set_text('Press + to add a pointer. Drag to reorder.')
        desc.set_halign(Gtk.Align.START)
        set_font(desc, 11, 'normal')
        desc.get_style_context().add_class('th-detail')
        desc.set_margin_start(4)
        desc.set_margin_end(4)
        group.pack_start(desc, False, False, 0)

        parent.pack_start(group, False, False, 0)

    def _add_your_hands(self, parent):
        """Add the Your hands section."""
        try:
            from tinyhand_linux.pointer_style import ALL_STYLES
        except Exception:
            ALL_STYLES = []
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        group.set_margin_top(30)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.set_margin_start(4)
        header.set_margin_end(4)

        title = Gtk.Label(label='Your hands')
        title.set_halign(Gtk.Align.START)
        set_font(title, 12, 'semibold')
        title.get_style_context().add_class('th-section-subtitle')
        header.pack_start(title, True, True, 0)

        # 'Make your own' is not available on Linux yet (see README: known limits).
        group.pack_start(header, False, False, 0)

        custom = [s for s in ALL_STYLES if s.kind == 'custom']
        if not custom:
            desc = Gtk.Label(label='Turn any idea into a hand with ChatGPT or another image tool.')
            desc.set_halign(Gtk.Align.START)
            set_font(desc, 11, 'normal')
            desc.get_style_context().add_class('th-detail')
            desc.set_margin_start(4)
            desc.set_margin_end(4)
            group.pack_start(desc, False, False, 0)
        else:
            chips = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            chips.set_margin_start(4)
            chips.set_margin_end(4)
            for style in custom:
                chip = self._create_hand_chip(style)
                chips.pack_start(chip, False, False, 0)
            group.pack_start(chips, False, False, 0)

        parent.pack_start(group, False, False, 0)

    def _create_hand_chip(self, style):
        """Create a chip for a custom hand."""
        chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        chip.get_style_context().add_class('th-hand-chip')
        chip.set_margin_top(5)
        chip.set_margin_bottom(5)
        chip.set_margin_start(6)
        chip.set_margin_end(6)

        icon = Gtk.Label(label=self._get_pointer_icon(style.id))
        set_font(icon, 24, 'normal')
        chip.pack_start(icon, False, False, 0)

        name = Gtk.Label(label=style.name)
        set_font(name, 12, 'normal')
        chip.pack_start(name, True, True, 0)

        return chip

    # === Appearance Section ===

    def _add_appearance_content(self, parent):
        """Add Appearance section content."""
        card = self._create_card(parent, 'Pointer')

        # Size slider
        size_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        small = Gtk.Label(label='👆')
        set_font(small, 10, 'normal')
        size_box.pack_start(small, False, False, 0)

        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        scale.set_range(0.05, 2.0)
        scale.set_increments(0.01, 0.05)
        scale.set_size_request(180, -1)
        try:
            scale.set_value(float(self.prefs.get('pointerSize', 0.13)))
        except Exception:
            scale.set_value(0.13)
        scale.connect('value-changed', lambda s: self.prefs.set('pointerSize', s.get_value()))
        size_box.pack_start(scale, True, True, 0)

        large = Gtk.Label(label='👆')
        set_font(large, 16, 'normal')
        size_box.pack_start(large, False, False, 0)

        self._add_row(card, 'Size', widget=size_box)
        self._add_separator(card)

        shadow_sw = self._create_toggle('showShadow', True)
        self._add_row(card, 'Shadow under the pointer', widget=shadow_sw)

    # === Drawing Section ===

    def _add_drawing_content(self, parent):
        """Add Drawing section content."""
        card = self._create_card(parent, 'Ink')

        # Ink choice
        ink_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        try:
            current_ink = self.prefs.get('inkChoice', 'match')
        except Exception:
            current_ink = 'match'

        for choice in InkChoice:
            btn = Gtk.Button()
            btn.set_size_request(26, 26)
            btn.get_style_context().add_class('th-ink-swatch')
            btn.connect('clicked', lambda b, c=choice: self.prefs.set('inkChoice', c.value))
            ink_box.pack_start(btn, False, False, 0)

        detail_text = 'Matches each pointer.' if current_ink == 'match' else f'All pointers draw in {current_ink}.'
        self._add_row(card, 'Ink colour', detail=detail_text, widget=ink_box)
        self._add_separator(card)

        # Fade
        fade_combo = Gtk.ComboBoxText()
        for label, val in [('After 3 seconds', '3'), ('After 6 seconds', '6'),
                            ('After 10 seconds', '10'), ('Keep until cleared', '0')]:
            fade_combo.append(val, label)
        try:
            fade_combo.set_active_id(str(self.prefs.get('fadeSeconds', 3)))
        except Exception:
            fade_combo.set_active_id('3')
        fade_combo.connect('changed', lambda c: self.prefs.set('fadeSeconds', int(c.get_active_id())))

        try:
            clear_shortcut = self.prefs.get('shortcut.clear', {}).get('display', 'Ctrl+Alt+X')
        except Exception:
            clear_shortcut = 'Ctrl+Alt+X'
        self._add_row(card, 'Lines fade', detail=f'Clear them any time with {clear_shortcut}.', widget=fade_combo)

    # === Sound Section ===

    def _add_sound_content(self, parent):
        """Add Sound section content."""
        # Tap sound group
        group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        title = Gtk.Label(label='Tap sound')
        title.set_halign(Gtk.Align.START)
        set_font(title, 12, 'semibold')
        title.get_style_context().add_class('th-section-subtitle')
        title.set_margin_start(4)
        title.set_margin_end(4)
        group.pack_start(title, False, False, 0)

        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(8)
        grid.set_margin_start(4)
        grid.set_margin_end(4)

        try:
            hand_sound = self.prefs.get('sound.hands', True)
            tap_sound = self.prefs.get('sound.tapSound', 'thock')
        except Exception:
            hand_sound = True
            tap_sound = 'thock'

        off_tile = self._create_sound_tile('Off', '🔇', not hand_sound)
        off_tile.connect('clicked', lambda w: self._set_sound(False))
        grid.attach(off_tile, 0, 0, 1, 1)

        col = 1
        for choice in TapSoundChoice:
            selected = hand_sound and tap_sound == choice.value
            tile = self._create_sound_tile(choice.title, '🎵', selected)
            tile.connect('clicked', lambda w, c=choice: self._set_tap_sound(c))
            grid.attach(tile, col, 0, 1, 1)
            col += 1

        group.pack_start(grid, False, False, 0)

        desc = Gtk.Label(label='Click a sound to hear it. It plays each time the hand taps.')
        desc.set_halign(Gtk.Align.START)
        set_font(desc, 11, 'normal')
        desc.get_style_context().add_class('th-detail')
        desc.set_margin_start(4)
        desc.set_margin_end(4)
        group.pack_start(desc, False, False, 0)

        parent.pack_start(group, False, False, 0)

        # Laser card
        card = self._create_card(parent, None)
        laser_sw = self._create_toggle('laserSound', False)
        laser_sw.set_sensitive(hand_sound)
        self._add_row(card, 'Laser dot taps too', detail='Off by default, for quiet pointing.', widget=laser_sw)
        card.set_opacity(0.5 if not hand_sound else 1.0)

    # === About Section ===

    def _add_about_content(self, parent):
        """Add About section content."""
        # App info
        app_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)

        icon = Gtk.Label(label='🖐️')
        set_font(icon, 72, 'normal')
        app_box.pack_start(icon, False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        name = Gtk.Label(label='TinyHand')
        name.set_halign(Gtk.Align.START)
        set_font(name, 18, 'bold')
        name.get_style_context().add_class('th-app-title')
        info.pack_start(name, False, False, 0)

        version = Gtk.Label(label='Version 1.1.0')
        version.set_halign(Gtk.Align.START)
        set_font(version, 12, 'normal')
        version.get_style_context().add_class('th-detail')
        info.pack_start(version, False, False, 0)

        desc = Gtk.Label(label='A tiny hand for your Mac. Free and open source.')
        desc.set_halign(Gtk.Align.START)
        set_font(desc, 12, 'normal')
        desc.get_style_context().add_class('th-detail')
        info.pack_start(desc, False, False, 0)

        app_box.pack_start(info, False, False, 0)
        app_box.pack_start(Gtk.Box(), True, True, 0)
        parent.pack_start(app_box, False, False, 0)

        # Links
        card = self._create_card(parent, None)
        links = [
            ('Website', 'tinyhand.app', 'https://tinyhand.app'),
            ('Source code', 'github.com/nilbuild/tinyhand', 'https://github.com/nilbuild/tinyhand'),
            ('Made by', '@nilbuild on X', 'https://x.com/nilbuild'),
            ('License', 'MIT', 'https://github.com/nilbuild/tinyhand/blob/main/LICENSE'),
        ]
        for title, detail, url in links:
            row = self._create_link_row(title, detail, url)
            card.pack_start(row, False, False, 0)
            if links.index((title, detail, url)) < len(links) - 1:
                card.pack_start(Gtk.Box(), False, False, 4)  # spacer

        # Reset button
        reset_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        reset_box.set_margin_top(22)
        reset_box.pack_start(Gtk.Box(), True, True, 0)

        reset_btn = Gtk.Button.new_with_label('Reset all settings...')
        reset_btn.get_style_context().add_class('th-text-btn')
        reset_btn.connect('clicked', self._on_reset_all)
        reset_box.pack_start(reset_btn, False, False, 0)
        parent.pack_start(reset_box, False, False, 0)

    # === Helper Methods ===

    def _create_card(self, parent, title):
        """Create a card container and add to parent."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.get_style_context().add_class('th-card')

        if title:
            title_label = Gtk.Label(label=title)
            title_label.set_halign(Gtk.Align.START)
            set_font(title_label, 12, 'normal')
            title_label.get_style_context().add_class('th-card-title')
            title_label.set_margin_start(4)
            card.pack_start(title_label, False, False, 0)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.get_style_context().add_class('th-card-content')
        card.pack_start(content, True, True, 0)
        parent.pack_start(card, False, False, 0)
        return content

    def _add_row(self, parent, title, detail=None, widget=None):
        """Add a row to a card."""
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hbox.set_margin_start(14)
        hbox.set_margin_end(14)
        hbox.set_margin_top(10)
        hbox.set_margin_bottom(10)
        hbox.set_size_request(-1, 44)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        title_label = Gtk.Label(label=title)
        title_label.set_halign(Gtk.Align.START)
        set_font(title_label, 13, 'normal')
        vbox.pack_start(title_label, False, False, 0)

        if detail:
            detail_label = Gtk.Label(label=detail)
            detail_label.set_halign(Gtk.Align.START)
            set_font(detail_label, 11, 'normal')
            detail_label.get_style_context().add_class('th-detail')
            vbox.pack_start(detail_label, False, False, 0)

        hbox.pack_start(vbox, True, True, 0)

        if widget:
            hbox.pack_start(widget, False, False, 0)

        parent.pack_start(hbox, False, False, 0)

    def _add_separator(self, parent):
        """Add a separator line."""
        sep = Gtk.Box()
        sep.set_size_request(-1, 1)
        sep.get_style_context().add_class('th-separator')
        sep.set_margin_start(14)
        parent.pack_start(sep, False, False, 0)

    def _create_toggle(self, key, default=False):
        """Create a switch bound to a preference."""
        sw = Gtk.Switch()
        try:
            sw.set_active(self.prefs.get(key, default))
        except Exception:
            sw.set_active(default)
        sw.connect('state-set', lambda s, g, k=key: self.prefs.set(k, s.get_active()))
        return sw

    def _create_shortcut_button(self, key):
        """Create a shortcut button."""
        btn = Gtk.Button()
        btn.set_size_request(132, 30)
        btn.get_style_context().add_class('th-shortcut-btn')
        value = self.prefs.get(key)
        label = value.get('display', 'Press keys') if isinstance(value, dict) else 'Press keys'
        btn.set_label(str(label))
        btn.connect('clicked', self._on_shortcut_button_clicked, key)
        return btn

    def _on_shortcut_button_clicked(self, btn, key):
        """Handle shortcut button click - enter recording mode."""
        if self._shortcut_recording_key is not None:
            # Already recording for another key, cancel that first
            self._cancel_shortcut_recording()
        
        self._shortcut_recording_key = key
        self._shortcut_recording_button = btn
        self._shortcut_original_label = btn.get_label()
        btn.set_label('Type shortcut…')
        self.grab_focus()

    def _on_key_press(self, widget, event):
        """Handle key press events for shortcut recording."""
        if self._shortcut_recording_key is None:
            return False
        
        # Get the keyval and state
        keyval = event.keyval
        state = event.state
        
        # Check for Escape to cancel
        keyval_name = Gdk.keyval_name(keyval)
        if keyval_name == 'Escape':
            self._cancel_shortcut_recording()
            return True
        
        # Check if this is a valid shortcut
        # Must have at least one of Ctrl, Alt, Super
        # Must have a non-modifier key
        
        # Get modifier masks
        # X11 modifier masks: Control=4, Alt=8 (Mod1), Super=64 (Mod4), Shift=1
        modifiers = 0
        if state & Gdk.ModifierType.CONTROL_MASK:
            modifiers |= 4
        if state & Gdk.ModifierType.MOD1_MASK:  # Typically Alt
            modifiers |= 8
        if state & Gdk.ModifierType.MOD4_MASK:  # Typically Super/Windows
            modifiers |= 64
        if state & Gdk.ModifierType.SHIFT_MASK:
            modifiers |= 1
        
        # If no required modifier (Ctrl, Alt, or Super), reject
        if modifiers & (4 | 8 | 64) == 0:
            return False
        
        # Check if this is a modifier-only key press
        # Get the keysym name
        keysym_name = Gdk.keyval_name(keyval)
        if keysym_name is None:
            return False
        
        # Map of GDK key names that should be treated as modifier-only
        modifier_only_keys = {
            'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Super_L', 'Super_R',
            'Shift_L', 'Shift_R', 'Meta_L', 'Meta_R', 'Hyper_L', 'Hyper_R',
        }
        
        if keysym_name in modifier_only_keys:
            return False
        
        # Valid shortcut - accept it
        self._accept_shortcut(keyval, state, modifiers, keysym_name)
        return True

    def _cancel_shortcut_recording(self):
        """Cancel shortcut recording mode."""
        if self._shortcut_recording_button is not None:
            self._shortcut_recording_button.set_label(self._shortcut_original_label)
        self._shortcut_recording_key = None
        self._shortcut_recording_button = None
        self._shortcut_original_label = None

    def _accept_shortcut(self, keyval, state, modifiers, keysym_name):
        """Accept the recorded shortcut and store it."""
        # Build the keysym: lowercase for letters
        keysym = keysym_name.lower() if keysym_name.isalpha() and len(keysym_name) == 1 else keysym_name
        
        # Map special GDK names to X keysym names
        # Common mappings where GDK and X11 differ
        keysym_map = {
            'Escape': 'Escape',
            'space': 'space',
            'Return': 'Return',
            'Tab': 'Tab',
            'BackSpace': 'BackSpace',
            'Delete': 'Delete',
            'Up': 'Up',
            'Down': 'Down',
            'Left': 'Left',
            'Right': 'Right',
            'Home': 'Home',
            'End': 'End',
            'Page_Up': 'Page_Up',
            'Page_Down': 'Page_Down',
            'comma': ',',
            'period': '.',
            'slash': '/',
            'semicolon': ';',
            'apostrophe': "'",
            'bracketleft': '[',
            'bracketright': ']',
            'minus': '-',
            'equal': '=',
            'backslash': '\\',
            'grave': '`',
        }
        
        # Apply mapping
        if keysym_name in keysym_map:
            keysym = keysym_map[keysym_name]
        else:
            # For alphabetic keys, ensure lowercase
            if keysym_name.isalpha() and len(keysym_name) == 1:
                keysym = keysym_name.lower()
            else:
                keysym = keysym_name
        
        # Build display string
        # Modifier order: Ctrl, Alt, Shift, Super
        display_parts = []
        if modifiers & 4:  # Control
            display_parts.append('Ctrl')
        if modifiers & 8:  # Alt (Mod1)
            display_parts.append('Alt')
        if modifiers & 1:  # Shift
            display_parts.append('Shift')
        if modifiers & 64:  # Super (Mod4)
            display_parts.append('Super')
        
        # Key name - uppercase for letters
        key_display = keysym_name
        if keysym_name.isalpha() and len(keysym_name) == 1:
            key_display = keysym_name.upper()
        # Handle special cases
        special_display_map = {
            'space': 'Space',
            'Escape': 'Escape',
            'Return': 'Return',
            'Tab': 'Tab',
            'BackSpace': 'Backspace',
            'Delete': 'Delete',
            'Up': '↑',
            'Down': '↓',
            'Left': '←',
            'Right': '→',
            'comma': ',',
            'period': '.',
            'slash': '/',
            'semicolon': ';',
            'apostrophe': "'",
            'bracketleft': '[',
            'bracketright': ']',
            'minus': '-',
            'equal': '=',
            'backslash': '\\',
            'grave': '`',
        }
        if keysym_name in special_display_map:
            key_display = special_display_map[keysym_name]
        
        display_parts.append(key_display)
        display = '+'.join(display_parts)
        
        # Store with prefs
        self.prefs.set(self._shortcut_recording_key, {
            'keysym': keysym,
            'modifiers': modifiers,
            'display': display
        })
        
        # Update button label
        self._shortcut_recording_button.set_label(display)
        
        # Exit recording mode
        self._cancel_shortcut_recording()

    def _create_sound_tile(self, title, icon, selected):
        """Create a sound tile."""
        btn = Gtk.Button()
        btn.set_size_request(104, -1)
        btn.get_style_context().add_class('th-sound-tile')
        if selected:
            btn.get_style_context().add_class('selected')

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_top(14)
        vbox.set_margin_bottom(14)

        icon_label = Gtk.Label(label=icon)
        set_font(icon_label, 18, 'medium')
        icon_label.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(icon_label, False, False, 0)

        title_label = Gtk.Label(label=title)
        set_font(title_label, 12, 'normal')
        title_label.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(title_label, False, False, 0)

        btn.add(vbox)
        return btn

    def _create_link_row(self, title, detail, url):
        """Create a link row."""
        btn = Gtk.Button()
        btn.set_size_request(-1, 44)
        btn.get_style_context().add_class('th-link-row')

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hbox.set_margin_start(14)
        hbox.set_margin_end(14)

        title_label = Gtk.Label(label=title)
        title_label.set_halign(Gtk.Align.START)
        set_font(title_label, 13, 'normal')
        hbox.pack_start(title_label, True, True, 0)

        detail_label = Gtk.Label(label=detail)
        detail_label.set_halign(Gtk.Align.END)
        set_font(detail_label, 12, 'normal')
        detail_label.get_style_context().add_class('th-detail')
        hbox.pack_start(detail_label, False, False, 0)

        arrow = Gtk.Label(label=' ↗')
        set_font(arrow, 10, 'semibold')
        arrow.get_style_context().add_class('th-detail')
        hbox.pack_start(arrow, False, False, 0)

        btn.add(hbox)
        btn.connect('clicked', self._on_link_clicked, url)
        return btn

    def _get_pointer_icon(self, style_id):
        """Get icon for a pointer style."""
        try:
            from tinyhand_linux.pointer_style import style_by_id
            style = style_by_id(style_id)
            if style:
                kind_icons = {'hand': '👆', 'custom': '🎨', 'laser': '🔴'}
                return kind_icons.get(style.kind, '?')
        except Exception:
            pass
        return '?'

    def _set_sound(self, enabled):
        """Set sound enabled."""
        self.prefs.set('sound.hands', enabled)

    def _set_tap_sound(self, choice):
        """Set tap sound choice."""
        self.prefs.set('sound.tapSound', choice.value)
        self.prefs.set('sound.hands', True)

    def _on_reset_toolbar(self, btn):
        """Reset toolbar to defaults."""
        try:
            # Default pinned styles from prefs.py
            default = ["lavender", "glove", "coral", "plush", "robot", "laser"]
            self.prefs.set('pinnedStyles', default)
        except Exception:
            pass

    def _on_add_pointer(self, btn):
        """Show pointer picker."""
        # In a real implementation, this would open a popover
        pass

    def _on_make_hand(self, btn):
        """Start making a hand."""
        pass

    def _on_reset_all(self, btn):
        """Reset all settings."""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text='Reset all settings?'
        )
        dialog.format_secondary_text(
            'Shortcuts, toolbar pointers, size, shadow, drawing and sound go back to how they were at first.'
        )
        if dialog.run() == Gtk.ResponseType.OK:
            self.prefs.reset_all()
        dialog.destroy()

    def _on_link_clicked(self, btn, url):
        """Open link in browser."""
        import subprocess
        subprocess.Popen(['xdg-open', url])

    def _ensure_css(self):
        """Ensure CSS styling is applied."""
        CSS = """
        .th-sidebar {
            background: @theme_bg_color;
        }
        .th-section-btn {
            background: transparent;
            border: none;
            border-radius: 8px;
        }
        .th-section-btn:hover {
            background-color: alpha(@theme_fg_color, 0.05);
        }
        .th-section-btn.selected {
            background-color: alpha(@theme_fg_color, 0.1);
        }
        .th-page-title {
            font-weight: bold;
        }
        .th-card {
            background: alpha(@theme_fg_color, 0.045);
            border-radius: 12px;
        }
        .th-card-title {
            color: @theme_fg_color;
            opacity: 0.6;
            font-weight: 600;
        }
        .th-card-content {
            background: alpha(@theme_fg_color, 0.045);
            border-radius: 12px;
        }
        .th-detail {
            color: @theme_fg_color;
            opacity: 0.6;
        }
        .th-toolbar-row {
            background: alpha(@theme_fg_color, 0.045);
            border-radius: 14px;
        }
        .th-empty-slot, .th-toolbar-slot, .th-add-slot {
            border-radius: 10px;
        }
        .th-empty-slot {
            background: alpha(@theme_fg_color, 0.035);
        }
        .th-toolbar-slot {
            background: rgba(255, 255, 255, 0.95);
            box-shadow: 0 1px 2px alpha(black, 0.08);
        }
        .th-toolbar-slot:hover {
            box-shadow: 0 4px 10px alpha(black, 0.22);
        }
        .th-add-slot {
            background: alpha(@theme_fg_color, 0.05);
            border: 1px dashed alpha(@theme_fg_color, 0.16);
        }
        .th-shortcut-btn {
            border-radius: 7px;
            background: alpha(@theme_fg_color, 0.05);
        }
        .th-text-btn {
            background: transparent;
            border: none;
            color: @theme_fg_color;
            opacity: 0.6;
        }
        .th-text-btn:hover {
            opacity: 1;
        }
        .th-link-row {
            background: transparent;
            border: none;
        }
        .th-link-row:hover {
            background: alpha(@theme_fg_color, 0.04);
        }
        .th-sound-tile {
            border-radius: 12px;
            background: alpha(@theme_fg_color, 0.035);
        }
        .th-sound-tile:hover {
            background: alpha(@theme_fg_color, 0.07);
        }
        .th-sound-tile.selected {
            background: alpha(@theme_selected_bg_color, 0.12);
            border: 1.5px solid alpha(@theme_selected_bg_color, 0.7);
        }
        .th-hand-chip {
            background: alpha(@theme_fg_color, 0.05);
            border-radius: 100px;
        }
        .th-hand-chip:hover {
            background: alpha(@theme_fg_color, 0.09);
        }
        .th-separator {
            background: alpha(@theme_fg_color, 0.07);
        }
        .th-app-name {
            font-weight: 600;
        }
        .th-app-title {
            font-weight: bold;
        }
        .th-ink-swatch {
            border-radius: 13px;
            background: alpha(@theme_fg_color, 0.06);
        }
        """
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


if __name__ == '__main__':
    # Self-test
    import sys

    class MockPrefs:
        def get(self, key, default=None):
            return default
        def set(self, key, value):
            pass
        def on_change(self, key, fn):
            pass
        def reset_all(self):
            pass

    try:
        if not Gtk.init_check()[0]:
            print("GTK initialization failed")
            sys.exit(1)
        prefs = MockPrefs()
        window = SettingsWindow(prefs)
        print("SettingsWindow created successfully")
        for section, _ in SECTIONS:
            window.show_section(section)
        print("All sections tested successfully")
        print("SUCCESS")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
