# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
#
# Showcase for every feature added by the iveevi/slangpy fork.
#
# Demonstrates, in a single program:
#
#   * spy.Window(decorated=False) -- borderless OS window
#   * ui.Context.add_font / push_font / pop_font -- font registry
#   * ui.Context.add_font(merge=True) -- FontAwesome icon-font merge
#   * ui.CursorPos + ui.Button -- FontAwesome action toolbar over the viewport
#   * ui.Context.style + ui.Col + ui.Style.set_color -- live ImGuiStyle
#   * imgui.ini persistence (saved layout reload on second launch)
#   * ui.DockSpace with passthru_central_node and request_split_horizontal
#   * ui.Window.dock_id -- programmatic docking
#   * ui.Image displaying a compute-written texture
#   * ui.Plot mixing line, histogram and bar-group series
#   * ui.LegendLocation + legend_outside + legend_horizontal
#   * ui.Plot.add_bar_groups (rolling frame-time bar chart)
#   * ui.TreeNode (nested scene inspector)
#   * ui.ColorEdit4 and ui.ColorPicker3
#
# Run from the repo root after building:  python examples/fork_demo/fork_demo.py
#
# Press F1 to reset the dock layout (deletes imgui.ini and re-splits).
# Press Esc to quit.

from __future__ import annotations

import math
import os
import time
from pathlib import Path
from typing import Optional

import slangpy as spy


EXAMPLE_DIR = Path(__file__).parent
IMGUI_INI = "imgui.ini"


# Optional font paths. Tries each candidate in order. The demo runs
# fine without these -- the font registry calls are skipped if no TTF
# is found at any candidate path.
FONT_CANDIDATES = {
    "body": [
        "/usr/share/fonts/TTF/FiraSans-Regular.ttf",
        "/usr/share/fonts/TTF/Roboto-Regular.ttf",
        "/usr/share/fonts/inter/Inter-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "header": [
        "/usr/share/fonts/TTF/FiraSans-Bold.ttf",
        "/usr/share/fonts/TTF/Roboto-Bold.ttf",
        "/usr/share/fonts/inter/Inter-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
}
FONT_BODY_SIZE = 22.0
FONT_HEADER_SIZE = 28.0

# Icon font (FontAwesome 6 Free Solid), merged into the body font via
# add_font(merge=True) so icon glyphs render inline in labels. The TTF is
# bundled next to this script (fa-solid-900.ttf, SIL OFL 1.1) so the icons
# always work -- no dependence on a system font being installed. System
# paths are kept as fallbacks. Codepoints are FontAwesome PUA values.
ICON_FONT_CANDIDATES = [
    str(EXAMPLE_DIR / "fa-solid-900.ttf"),
    "/usr/share/fonts/fontawesome/fa-solid-900.ttf",
    "/usr/share/fonts/TTF/fa-solid-900.ttf",
    str(Path.home() / ".local/share/fonts/fa-solid-900.ttf"),
]
ICON_PLAY = "\uf04b"  # play
ICON_PAUSE = "\uf04c"  # pause
ICON_RESET = "\uf021"  # arrows-rotate / refresh
ICON_CAMERA = "\uf030"  # camera


# Number of frame-time bars shown in the performance bar-group chart.
FRAME_BARS = 30


def _first_existing(paths: list[str]) -> Optional[str]:
    for p in paths:
        if os.path.isfile(p):
            return p
    return None


# Nord palette (https://www.nordtheme.com)
# Polar Night
NORD0 = (0.180, 0.204, 0.251, 1.0)  # #2E3440
NORD1 = (0.231, 0.259, 0.322, 1.0)  # #3B4252
NORD2 = (0.263, 0.298, 0.369, 1.0)  # #434C5E
NORD3 = (0.298, 0.337, 0.416, 1.0)  # #4C566A
# Snow Storm
NORD4 = (0.847, 0.871, 0.914, 1.0)  # #D8DEE9
NORD5 = (0.898, 0.914, 0.941, 1.0)  # #E5E9F0
NORD6 = (0.925, 0.937, 0.957, 1.0)  # #ECEFF4
# Frost
NORD7 = (0.561, 0.737, 0.733, 1.0)  # #8FBCBB
NORD8 = (0.533, 0.753, 0.816, 1.0)  # #88C0D0
NORD9 = (0.506, 0.631, 0.757, 1.0)  # #81A1C1
NORD10 = (0.369, 0.506, 0.675, 1.0)  # #5E81AC
# Aurora
NORD11 = (0.749, 0.380, 0.416, 1.0)  # #BF616A  red
NORD12 = (0.816, 0.529, 0.439, 1.0)  # #D08770  orange
NORD13 = (0.922, 0.796, 0.545, 1.0)  # #EBCB8B  yellow
NORD14 = (0.639, 0.745, 0.549, 1.0)  # #A3BE8C  green
NORD15 = (0.706, 0.557, 0.678, 1.0)  # #B48EAD  magenta


def _c(rgba: tuple[float, float, float, float], a: Optional[float] = None) -> "spy.float4":
    """Convenience: tuple -> spy.float4, optionally overriding alpha."""
    return spy.float4(rgba[0], rgba[1], rgba[2], rgba[3] if a is None else a)


class ForkDemo:
    def __init__(self, headless: bool = False) -> None:
        # Headless mode skips the OS window/surface so the UI can be rendered
        # to an offscreen texture (see render_headless) without a display --
        # useful for screenshots / inspection in CI or over SSH.
        self.headless = headless
        self.window: Optional[spy.Window] = None
        self.surface = None

        if not headless:
            # GLFW needs an X display (this build is X11-only). On a Wayland
            # session like niri, that means XWayland -- DISPLAY must point at
            # it (typically ":1" via xwayland-satellite). Give a useful
            # message instead of a bare "Failed to initialize GLFW".
            if not os.environ.get("DISPLAY"):
                raise RuntimeError(
                    "DISPLAY is unset. This demo's GLFW build is X11-only, so "
                    "it needs an X display (under Wayland, XWayland). On niri "
                    "with xwayland-satellite the value is typically ':1'. "
                    "Re-run as:  DISPLAY=:1 python examples/fork_demo/fork_demo.py"
                )
            self.window = spy.Window(
                width=1600,
                height=900,
                title="fork demo",
                resizable=True,
            )

        self.device = spy.Device(
            enable_debug_layers=False,
            compiler_options={"include_paths": [EXAMPLE_DIR]},
        )

        if not headless:
            self.surface = self.device.create_surface(self.window)
            self.surface.configure(width=self.window.width, height=self.window.height)

        # ------------------------------------------------------------------
        # UI context, fonts, style.
        # add_font must be called BEFORE the first frame (it builds the
        # ImGui font atlas). ImPlot's context is created/destroyed
        # alongside ImGui's so ui.Plot works out of the box.
        # ------------------------------------------------------------------
        self.ui = spy.ui.Context(self.device)
        self._register_fonts()
        self._configure_style()

        # ------------------------------------------------------------------
        # Progressive path tracer (analytic ray/primitive intersection).
        # The kernel writes one new sample
        # per dispatch into g_accum (running mean) and a tonemapped
        # version into g_output. g_output is blitted to the surface --
        # the passthru central node makes it the visible backdrop.
        # ------------------------------------------------------------------
        program = self.device.load_program("scene", ["compute_main"])
        self.kernel = self.device.create_compute_kernel(program)
        # PT renders at viewport_size * render_scale, clamped to a
        # pixel budget. Re-allocated by _ensure_pt_textures(...) when
        # the target size changes. The ui.Image upscales to fill the
        # viewport.
        self.pt_width = 1280
        self.pt_height = 720
        self.render_scale = 0.55
        self.exposure = 1.0  # post-accumulation tonemap exposure
        self.animate = True  # advance the scene clock (toggled from the overlay)
        self.pixel_budget = 500_000  # ~707x707; ~20ms / frame with NEE
        self.scene_texture: Optional[spy.Texture] = None  # tonemapped output
        self.accum_texture: Optional[spy.Texture] = None  # running mean
        self.sample_count = 0

        # ------------------------------------------------------------------
        # Orbit camera (mouse-driven). LMB drag = rotate, MMB/RMB drag =
        # pan target, wheel = zoom.
        # ------------------------------------------------------------------
        self.cam_target = [0.0, 0.55, 0.0]
        self.cam_yaw = 0.0
        self.cam_pitch = 0.25  # radians; + looks down at the scene
        self.cam_distance = 4.5
        self.focal = 1.5
        self._mouse_down = {"left": False, "right": False, "middle": False}
        self._last_mouse: Optional[tuple[float, float]] = None

        # Scene animation: g_time is fed to the shader for orbits / box
        # spin / mirror bob. When `animate` is False, t_freeze holds the
        # last g_time value so the scene pauses and the accumulator can
        # converge.
        self.t_freeze: float = 0.0

        # ------------------------------------------------------------------
        # The sparkline gets filled from the main loop; no other
        # telemetry state needed.

        # ------------------------------------------------------------------
        # Event wiring (only with a real window).
        # ------------------------------------------------------------------
        if not headless:
            self.window.on_keyboard_event = self._on_keyboard_event
            self.window.on_mouse_event = self._on_mouse_event
            self.window.on_resize = self._on_resize
        self._terminate = False

        # ------------------------------------------------------------------
        # Widgets.
        # ------------------------------------------------------------------
        self._build_widgets()

        # First-launch docking: if imgui.ini doesn't exist, request a
        # programmatic split. Otherwise the saved layout takes over.
        self._needs_layout = not Path(IMGUI_INI).exists()
        if self._needs_layout:
            self.dock.request_split_horizontal(0.27)

    # ---------------------------------------------------------------- fonts

    def _register_fonts(self) -> None:
        """Register fonts that exist; mark the body font as default. If an
        icon font is found, merge it into the body font so icon glyphs can
        be used inline in labels (add_font(merge=True))."""
        self.has_icons = False
        body = _first_existing(FONT_CANDIDATES["body"])
        header = _first_existing(FONT_CANDIDATES["header"])
        if body is not None:
            self.ui.add_font("body", body, FONT_BODY_SIZE, is_default=True)
            # Merge the icon font into the body font just registered. Merge
            # only makes sense once a base font exists, so it is nested here.
            icons = _first_existing(ICON_FONT_CANDIDATES)
            if icons is not None:
                self.ui.add_font("icons", icons, FONT_BODY_SIZE, merge=True)
                self.has_icons = True
        if header is not None:
            self.ui.add_font("header", header, FONT_HEADER_SIZE)

    def _label(self, icon: str, text: str) -> str:
        """Prefix `text` with `icon` glyph when an icon font is loaded,
        else return the plain text."""
        return f"{icon}  {text}" if self.has_icons else text

    # ---------------------------------------------------------------- style

    def _configure_style(self) -> None:
        """Theme the app via ctx.style (live wrapper on ImGuiStyle).

        Nord palette: Polar Night for surfaces, Snow Storm for text,
        Frost for accents (sliders/buttons/grabs), Aurora for plot
        series so they stand out.
        """
        s = self.ui.style
        s.colors_dark()  # baseline so all slots have sensible alpha

        # ----- shape / spacing -----------------------------------------
        s.window_padding = spy.float2(14.0, 12.0)
        s.frame_padding = spy.float2(10.0, 6.0)
        s.item_spacing = spy.float2(10.0, 8.0)
        s.window_rounding = 6.0
        s.frame_rounding = 4.0
        s.grab_rounding = 4.0
        s.tab_rounding = 4.0
        s.scrollbar_size = 0.0  # hide the gutter entirely
        s.scrollbar_rounding = 0.0
        # Flat, borderless surfaces (the rcgp-samples look): rounding does
        # the shaping, no 1px outlines on windows or frames.
        s.window_border_size = 0.0
        s.frame_border_size = 0.0

        # ----- Nord colour assignments ---------------------------------
        # Backgrounds (Polar Night)
        s.set_color(spy.ui.Col.window_bg, _c(NORD0))
        s.set_color(spy.ui.Col.child_bg, _c(NORD0))
        s.set_color(spy.ui.Col.popup_bg, _c(NORD1, 0.97))
        s.set_color(spy.ui.Col.frame_bg, _c(NORD1))
        s.set_color(spy.ui.Col.frame_bg_hovered, _c(NORD2))
        s.set_color(spy.ui.Col.frame_bg_active, _c(NORD3))
        s.set_color(spy.ui.Col.menu_bar_bg, _c(NORD1))
        s.set_color(spy.ui.Col.title_bg, _c(NORD1))
        s.set_color(spy.ui.Col.title_bg_active, _c(NORD10))
        s.set_color(spy.ui.Col.title_bg_collapsed, _c(NORD0, 0.75))

        # Border (Polar Night)
        s.set_color(spy.ui.Col.border, _c(NORD3, 0.50))
        s.set_color(spy.ui.Col.border_shadow, spy.float4(0, 0, 0, 0))

        # Text (Snow Storm)
        s.set_color(spy.ui.Col.text, _c(NORD6))
        s.set_color(spy.ui.Col.text_disabled, _c(NORD3))
        s.set_color(spy.ui.Col.text_selected_bg, _c(NORD10, 0.45))

        # Buttons / sliders / headers (Frost)
        s.set_color(spy.ui.Col.button, _c(NORD10))
        s.set_color(spy.ui.Col.button_hovered, _c(NORD9))
        s.set_color(spy.ui.Col.button_active, _c(NORD8))
        s.set_color(spy.ui.Col.header, _c(NORD10, 0.55))
        s.set_color(spy.ui.Col.header_hovered, _c(NORD9, 0.70))
        s.set_color(spy.ui.Col.header_active, _c(NORD8, 0.80))
        s.set_color(spy.ui.Col.slider_grab, _c(NORD8))
        s.set_color(spy.ui.Col.slider_grab_active, _c(NORD7))
        s.set_color(spy.ui.Col.check_mark, _c(NORD8))

        # Separators (Polar Night)
        s.set_color(spy.ui.Col.separator, _c(NORD3, 0.60))
        s.set_color(spy.ui.Col.separator_hovered, _c(NORD9))
        s.set_color(spy.ui.Col.separator_active, _c(NORD8))

        # Resize grips
        s.set_color(spy.ui.Col.resize_grip, _c(NORD3, 0.40))
        s.set_color(spy.ui.Col.resize_grip_hovered, _c(NORD9, 0.70))
        s.set_color(spy.ui.Col.resize_grip_active, _c(NORD8))

        # Tabs. The selected tab of the *focused* dock node gets the bright
        # accent fill plus a thick bright overline stripe on top; when the
        # node loses focus its selected tab drops to a dark tone with no
        # stripe, so the focused panel is unmistakable.
        s.tab_bar_overline_size = 4.0
        s.set_color(spy.ui.Col.tab, _c(NORD1))
        s.set_color(spy.ui.Col.tab_hovered, _c(NORD3))
        s.set_color(spy.ui.Col.tab_selected, _c(NORD10))
        s.set_color(spy.ui.Col.tab_selected_overline, _c(NORD8))
        s.set_color(spy.ui.Col.tab_dimmed, _c(NORD0))
        s.set_color(spy.ui.Col.tab_dimmed_selected, _c(NORD1))
        s.set_color(spy.ui.Col.tab_dimmed_selected_overline, _c(NORD1))

        # Docking
        s.set_color(spy.ui.Col.docking_preview, _c(NORD10, 0.70))
        s.set_color(spy.ui.Col.docking_empty_bg, _c(NORD0))

        # Scrollbars (hidden via scrollbar_size=0, but colour for completeness)
        s.set_color(spy.ui.Col.scrollbar_bg, spy.float4(0, 0, 0, 0))
        s.set_color(spy.ui.Col.scrollbar_grab, _c(NORD3))
        s.set_color(spy.ui.Col.scrollbar_grab_hovered, _c(NORD9))
        s.set_color(spy.ui.Col.scrollbar_grab_active, _c(NORD8))

        # Plot colours (Aurora) -- ImPlot uses its own palette but the
        # ImGui PlotLines / PlotHistogram fallback still hits these.
        s.set_color(spy.ui.Col.plot_lines, _c(NORD8))
        s.set_color(spy.ui.Col.plot_lines_hovered, _c(NORD7))
        s.set_color(spy.ui.Col.plot_histogram, _c(NORD14))
        s.set_color(spy.ui.Col.plot_histogram_hovered, _c(NORD13))

        # Table
        s.set_color(spy.ui.Col.table_header_bg, _c(NORD2))
        s.set_color(spy.ui.Col.table_border_strong, _c(NORD3))
        s.set_color(spy.ui.Col.table_border_light, _c(NORD2))
        s.set_color(spy.ui.Col.table_row_bg, spy.float4(0, 0, 0, 0))
        s.set_color(spy.ui.Col.table_row_bg_alt, _c(NORD1, 0.40))

    # -------------------------------------------------------------- widgets

    def _build_widgets(self) -> None:
        screen = self.ui.screen

        # DockSpace that fills the viewport. passthru_central_node is
        # OFF so the central area is filled by ImGui's docking_empty_bg
        # colour (Nord polar-night) -- the path-traced output goes in
        # the dedicated `viewport` window via ui.Image.
        self.dock = spy.ui.DockSpace(screen)
        self.dock.passthru_central_node = False

        # Left-side panels, each its own dock window (all tabbed into the
        # left node by _try_apply_layout; drag tabs to split them apart):
        #   performance  -- smoothed frame-time telemetry
        #   scene inspector -- nested scene tree (built below)
        self.perf_window = spy.ui.Window(screen, "Performance", size=spy.float2(400, 900))
        # Dedicated viewport window holding the ui.Image of the
        # path-tracer output. Docked to the right node so it fills the
        # entire right side of the layout. Mouse drag inside this
        # window's area drives the camera.
        self.viewport_window = spy.ui.Window(
            screen,
            "Viewport",
            position=spy.float2(440, 30),
            size=spy.float2(1100, 900),
        )
        # Scene inspector: its own window holding the nested scene tree,
        # docked as a tab alongside `controls` (see _try_apply_layout).
        self.inspector_window = spy.ui.Window(
            screen,
            "Scene Inspector",
            size=spy.float2(400, 900),
        )

        # -- left controls ------------------------------------------------
        # Organised into collapsible ui.Group sections.

        def _reset(*_: object) -> None:
            self.sample_count = 0

        # ----- scene inspector (own dock panel) -----------------------
        # A scene-graph mirror of the scene in scene.slang lives in
        # its own window, docked as a tab alongside `controls`. TreeNode
        # widgets nest arbitrarily: a TreeNode parented to another
        # TreeNode renders indented inside it (ImGui TreeNodeEx/TreePop).
        # The leaves are live controls, so editing the tree drives the
        # path tracer and resets accumulation via _reset.
        scene = spy.ui.TreeNode(self.inspector_window, "Scene", open=True)

        # geometry/
        geometry = spy.ui.TreeNode(scene, "Geometry", open=True)

        orbiting = spy.ui.TreeNode(geometry, "Orbiting Spheres", open=True)
        self.tint = spy.ui.ColorPicker3(
            orbiting,
            "Tint Sphere",
            value=spy.float3(NORD8[0], NORD8[1], NORD8[2]),
            callback=_reset,
        )
        spy.ui.Text(orbiting, "3 orbiting (ray-sphere)")

        mirror = spy.ui.TreeNode(geometry, "Mirror Sphere", open=True)
        spy.ui.Text(mirror, "Metal, bobbing")

        glass = spy.ui.TreeNode(geometry, "Glass Spheres", open=True)
        spy.ui.Text(glass, "2 refractive (dielectric, IOR 1.5)")

        back_row = spy.ui.TreeNode(geometry, "Back Row", open=True)
        spy.ui.Text(back_row, "5 x diffuse")

        # lights/  -- one intensity multiplier per light. 1.0 keeps the
        # shader's baked-in intensity; 0.0 turns the light off entirely.
        lights = spy.ui.TreeNode(scene, "Lights", open=True)
        self.light_warm = spy.ui.SliderFloat(
            lights,
            "Warm",
            value=1.0,
            min=0.0,
            max=3.0,
            callback=_reset,
        )
        self.light_cool = spy.ui.SliderFloat(
            lights,
            "Cool",
            value=1.0,
            min=0.0,
            max=3.0,
            callback=_reset,
        )
        self.light_pink = spy.ui.SliderFloat(
            lights,
            "Pink",
            value=1.0,
            min=0.0,
            max=3.0,
            callback=_reset,
        )
        self.light_lime = spy.ui.SliderFloat(
            lights,
            "Lime",
            value=1.0,
            min=0.0,
            max=3.0,
            callback=_reset,
        )

        # environment/
        environment = spy.ui.TreeNode(scene, "Environment", open=True)
        self.background = spy.ui.ColorEdit4(
            environment,
            "Sky / Ambient",
            value=spy.float4(0.0, 0.0, 0.0, 1.0),
            callback=_reset,
        )
        spy.ui.Text(environment, "Ground plane")

        # ===== window: performance ====================================
        # Frame-time history shown as a bar-group chart (ImPlot
        # PlotBarGroups): one "ms" series with FRAME_BARS columns, the
        # most recent frame on the right. Rolling buffer lives in
        # self._frame_ms and is pushed every frame in run(); values are
        # exponentially smoothed (self._frame_ms_ema) so the bars don't
        # flicker frame-to-frame.
        self._frame_ms = [0.0] * FRAME_BARS
        self._frame_ms_ema = 0.0
        # ImPlot routes size through ImGui::CalcItemSize: a 0 component
        # means "use the default size" (~400x300), NOT fill. A negative
        # component fills the available region (avail - |value|). So
        # x=-1 stretches to the panel width; height stays a sane fixed
        # value so the chart is wide rather than tall.
        self.frame_plot = spy.ui.Plot(
            self.perf_window,
            label="Frame Time",
            y_label="ms",
            size=spy.float2(-1, -1),
        )
        self.frame_plot.add_bar_groups(["ms"], [self._frame_ms])

        # -- viewport panel: ui.Image of the path-traced output ---------
        # size=(0,0) + zero padding fills the window edge-to-edge. (Trade-off:
        # the image covers the window's rounded bottom corners and the inner
        # part of the floating resize grip, which ImGui draws under content.)
        self.viewport_window.padding = spy.float2(0.0, 0.0)
        self.viewport_image = spy.ui.Image(
            self.viewport_window,
            texture=None,
            size=spy.float2(0.0, 0.0),
        )

        # ===== viewport action toolbar (overlaid on the image) ========
        # The toolbar lives INSIDE the viewport window: ui.CursorPos rewinds
        # the draw cursor back to the top-left after the image, so these
        # bordered FontAwesome buttons draw on top of it. Being in the same
        # window, they stay with the viewport whether docked or floating
        # (no separate-window z-order issues). The toggle glyph swaps to
        # reflect play/pause. Camera drag ignores clicks that land on a
        # button (see _click_targets_viewport + is_any_item_hovered).
        def _toggle_animate(*_: object) -> None:
            self.animate = not self.animate
            if not self.animate:
                self.sample_count = 0

        spy.ui.CursorPos(self.viewport_window, spy.float2(12.0, 12.0))
        self.toggle_btn = spy.ui.Button(
            self.viewport_window,
            ICON_PAUSE if self.has_icons else "||",
            callback=_toggle_animate,
            border=True,
        )
        spy.ui.SameLine(self.viewport_window)
        spy.ui.Button(
            self.viewport_window,
            ICON_RESET if self.has_icons else "R",
            callback=_reset,
            border=True,
        )
        spy.ui.SameLine(self.viewport_window)
        spy.ui.Button(
            self.viewport_window,
            ICON_CAMERA if self.has_icons else "S",
            callback=self._save_screenshot,
            border=True,
        )

        # Sample-count readout as a button-style chip pinned to the top-right
        # corner of the viewport. The CursorPos is repositioned each frame in
        # run() (content_size - chip width) to keep it flush-right, and the
        # chip label is updated there too. No callback -- it's a readout.
        self._spp_cursor = spy.ui.CursorPos(self.viewport_window, spy.float2(0.0, 12.0))
        self.spp_chip = spy.ui.Button(self.viewport_window, "Samples: 0", border=True)

    # -------------------------------------------------------- dock assignment

    def _try_apply_layout(self) -> None:
        """After the first DockSpace render the split child ids are valid;
        assign each window to its destination node once and stop."""
        if not self._needs_layout:
            return
        left = self.dock.left_dock_id
        right = self.dock.right_dock_id
        if left == 0 or right == 0:
            return
        # All left-side panels share the left node, so they dock as tabs.
        # Drag a tab out to split it off.
        self.perf_window.dock_id = left
        self.inspector_window.dock_id = left
        # Viewport fills the right side completely; phases /
        # distribution stay floating on top.
        self.viewport_window.dock_id = right
        self._needs_layout = False

    # ----------------------------------------------------------- input

    def _on_keyboard_event(self, event: spy.KeyboardEvent) -> None:
        if self.ui.handle_keyboard_event(event):
            return
        if event.type == spy.KeyboardEventType.key_press:
            if event.key == spy.KeyCode.escape:
                self._terminate = True
            elif event.key == spy.KeyCode.space:
                # Toggle animation. When pausing, also reset the accumulator
                # so the freshly-frozen scene converges from scratch rather
                # than blending with the prior animated samples.
                self.animate = not self.animate
                if not self.animate:
                    self.sample_count = 0
            elif event.key == spy.KeyCode.f1:
                # Reset dock layout: drop imgui.ini, re-request a split.
                try:
                    os.remove(IMGUI_INI)
                except FileNotFoundError:
                    pass
                self.dock.request_split_horizontal(0.27)
                self._needs_layout = True

    # ----------------------------------------------------- orbit camera

    def _camera_basis(self) -> tuple[spy.float3, spy.float3, spy.float3, spy.float3]:
        """Return (position, right, up, forward) for the orbit camera."""
        cp = math.cos(self.cam_pitch)
        sp = math.sin(self.cam_pitch)
        sy = math.sin(self.cam_yaw)
        cy = math.cos(self.cam_yaw)
        tx, ty, tz = self.cam_target
        d = self.cam_distance
        # Spherical -> Cartesian, camera orbiting around target.
        pos = (tx + d * cp * sy, ty + d * sp, tz + d * cp * cy)
        # Forward = target - pos (normalised)
        fx, fy, fz = (tx - pos[0], ty - pos[1], tz - pos[2])
        fl = math.sqrt(fx * fx + fy * fy + fz * fz) or 1.0
        forward = (fx / fl, fy / fl, fz / fl)
        # Right = forward x world_up
        wux, wuy, wuz = 0.0, 1.0, 0.0
        rx = forward[1] * wuz - forward[2] * wuy
        ry = forward[2] * wux - forward[0] * wuz
        rz = forward[0] * wuy - forward[1] * wux
        rl = math.sqrt(rx * rx + ry * ry + rz * rz) or 1.0
        right = (rx / rl, ry / rl, rz / rl)
        # Up = right x forward (gives a clean orthonormal basis)
        ux = right[1] * forward[2] - right[2] * forward[1]
        uy = right[2] * forward[0] - right[0] * forward[2]
        uz = right[0] * forward[1] - right[1] * forward[0]
        return (
            spy.float3(*pos),
            spy.float3(*right),
            spy.float3(ux, uy, uz),
            spy.float3(*forward),
        )

    def _rect_contains(
        self, w: "spy.ui.Window", px: float, py: float, inset_top: float = 0.0
    ) -> bool:
        wp = w.position
        ws = w.size
        return wp.x <= px <= wp.x + ws.x and wp.y + inset_top <= py <= wp.y + ws.y

    def _click_targets_viewport(self, px: float, py: float) -> bool:
        """The click is camera-drag intent iff it lands on the viewport
        window's *image area* (below the title bar, inside the padding)
        AND no other floating panel covers that point."""
        wp = self.viewport_window.position
        ws = self.viewport_window.size
        # Title-bar inset (rough, but the only ImGui geometry we don't
        # get from the binding). frame_padding.y=6 + font 22 ~= 38.
        title_h = 38.0
        pad_x = 12.0
        in_image = (
            wp.x + pad_x <= px <= wp.x + ws.x - pad_x and wp.y + title_h <= py <= wp.y + ws.y - 4.0
        )
        if not in_image:
            return False
        # Leave the bottom-right resize-grip corner to ImGui so a floating
        # viewport can still be resized (the grip is ~1.5 * font size).
        grip = 1.5 * FONT_BODY_SIZE
        if px >= wp.x + ws.x - grip and py >= wp.y + ws.y - grip:
            return False
        # Reject if the cursor is over an interactive ImGui item -- this is
        # how clicks on the viewport's own action toolbar (drawn over the
        # image) reach the buttons instead of starting a camera drag. The
        # inert ui.Image is not an item, so the rest of the image still
        # drives the camera.
        if self.ui.is_any_item_hovered():
            return False
        # Reject if any other panel covers the cursor -- avoids
        # camera-grabbing a click that's targeting that panel.
        for panel in (
            self.perf_window,
            self.inspector_window,
        ):
            if self._rect_contains(panel, px, py):
                return False
        return True

    def _on_mouse_event(self, event: spy.MouseEvent) -> None:
        et = spy.MouseEventType
        # Snapshot the position as plain floats; the MouseEvent object
        # may be a temporary view that becomes invalid after return.
        px, py = float(event.pos.x), float(event.pos.y)

        drag_active = any(self._mouse_down.values())

        if event.type == et.button_down:
            # Camera-drag intent: the click clearly targets the viewport
            # image AND no other panel covers that point. In that case
            # the event is consumed exclusively -- ImGui never sees it,
            # so no window-move / slider-grab fires alongside the camera.
            if self._click_targets_viewport(px, py):
                self._mouse_down[event.button.name] = True
                self._last_mouse = (px, py)
                return
            self.ui.handle_mouse_event(event)
            return

        if event.type == et.button_up:
            # If our camera was tracking this button, end the drag and
            # do NOT inform ImGui (it never saw the matching down).
            if self._mouse_down.get(event.button.name, False):
                self._mouse_down[event.button.name] = False
                self._last_mouse = None
                return
            self.ui.handle_mouse_event(event)
            return

        if event.type == et.move:
            # If a camera drag is in progress, swallow the event and
            # apply rotation / pan. Otherwise pass to ImGui (hover etc).
            if drag_active and self._last_mouse is not None:
                dx = px - self._last_mouse[0]
                dy = py - self._last_mouse[1]
                if self._mouse_down["left"]:
                    # Horizontal: drag right -> scene rotates right
                    # (camera orbits opposite the cursor, "trackball").
                    # Vertical: drag down -> camera looks down further.
                    self.cam_yaw -= dx * 0.005
                    self.cam_pitch += dy * 0.005
                    lim = math.pi * 0.5 - 0.05
                    self.cam_pitch = max(-lim, min(lim, self.cam_pitch))
                    self.sample_count = 0
                if self._mouse_down["middle"] or self._mouse_down["right"]:
                    _, right, up, _ = self._camera_basis()
                    speed = self.cam_distance * 0.0015
                    self.cam_target[0] += -right.x * dx * speed + up.x * dy * speed
                    self.cam_target[1] += -right.y * dx * speed + up.y * dy * speed
                    self.cam_target[2] += -right.z * dx * speed + up.z * dy * speed
                    self.sample_count = 0
                self._last_mouse = (px, py)
                return
            self.ui.handle_mouse_event(event)
            return

        if event.type == et.scroll:
            # Wheel zooms only if the cursor is over the viewport;
            # otherwise let ImGui scroll its panels.
            if self._click_targets_viewport(px, py):
                dy = float(event.scroll.y) if hasattr(event, "scroll") else 0.0
                if dy != 0.0:
                    self.cam_distance *= 1.15 ** (-dy)
                    self.cam_distance = max(1.2, min(25.0, self.cam_distance))
                    self.sample_count = 0
                return
            self.ui.handle_mouse_event(event)

    def _on_resize(self, width: int, height: int) -> None:
        self.device.wait()
        if width > 0 and height > 0:
            self.surface.configure(width=width, height=height)
        else:
            self.surface.unconfigure()

    # ----------------------------------------------------------- main loop

    def _save_screenshot(self) -> None:
        """Convert the current path-traced texture to a PNG in cwd.
        Names the file with the current sample count so successive
        clicks don't overwrite."""
        if self.scene_texture is None:
            return
        try:
            bmp = self.scene_texture.to_bitmap()
            bmp = bmp.convert(
                spy.Bitmap.PixelFormat.rgb,
                spy.Bitmap.ComponentType.uint8,
                srgb_gamma=False,  # the shader has already gamma'd
            )
            path = f"fork_demo_{self.sample_count:04d}spp.png"
            bmp.write_async(path)
            print(f"[fork_demo] saved {path}")
        except Exception as e:
            print(f"[fork_demo] screenshot failed: {e}")

    def _ensure_pt_textures(self, pt_w: int, pt_h: int) -> None:
        """Allocate / reallocate the path-tracer's textures so the render
        target is `(pt_w, pt_h)` pixels. The ui.Image fills the window
        content region on its own (size=(0,0)). Triggers an accumulation
        reset on render-target resize."""
        needs_remake = (
            self.scene_texture is None
            or self.scene_texture.width != pt_w
            or self.scene_texture.height != pt_h
        )
        if needs_remake:
            self.device.wait()
            self.scene_texture = self.device.create_texture(
                format=spy.Format.rgba16_float,
                width=pt_w,
                height=pt_h,
                usage=(spy.TextureUsage.shader_resource | spy.TextureUsage.unordered_access),
                label="pt_output",
            )
            self.accum_texture = self.device.create_texture(
                format=spy.Format.rgba16_float,
                width=pt_w,
                height=pt_h,
                usage=(spy.TextureUsage.shader_resource | spy.TextureUsage.unordered_access),
                label="pt_accum",
            )
            self.viewport_image.texture = self.scene_texture
            self.pt_width = pt_w
            self.pt_height = pt_h
            self.sample_count = 0

    def _dispatch_scene(self, command_encoder: "spy.CommandEncoder", g_time: float) -> None:
        """Run one path-tracer sample into scene_texture/accum_texture."""
        cam_pos, cam_right, cam_up, cam_fwd = self._camera_basis()
        self.kernel.dispatch(
            thread_count=[self.pt_width, self.pt_height, 1],
            vars={
                "g_output": self.scene_texture,
                "g_accum": self.accum_texture,
                "g_frame": self.sample_count,
                "g_sample_count": self.sample_count,
                "g_time": g_time,
                "g_tint": self.tint.value,
                "g_sky": self.background.value,
                "g_exposure": self.exposure,
                "g_cam_pos": cam_pos,
                "g_cam_right": cam_right,
                "g_cam_up": cam_up,
                "g_cam_forward": cam_fwd,
                "g_focal": self.focal,
                "g_light_intensity": spy.float4(
                    self.light_warm.value,
                    self.light_cool.value,
                    self.light_pink.value,
                    self.light_lime.value,
                ),
            },
            command_encoder=command_encoder,
        )

    def _size_pt_to_viewport(self) -> None:
        """Size the PT render target to the viewport's content area."""
        content = self.viewport_window.content_size
        disp_w = max(64.0, content.x)
        disp_h = max(64.0, content.y)
        pt_w = max(64, int(disp_w * self.render_scale))
        pt_h = max(64, int(disp_h * self.render_scale))
        if pt_w * pt_h > self.pixel_budget:
            s = (self.pixel_budget / float(pt_w * pt_h)) ** 0.5
            pt_w = max(64, int(pt_w * s))
            pt_h = max(64, int(pt_h * s))
        self._ensure_pt_textures(pt_w, pt_h)

    def _update_spp_chip(self) -> None:
        """Refresh the top-right sample-count chip label + position."""
        spp_label = f"Samples: {self.sample_count}"
        self.spp_chip.label = spp_label
        chip_w = self.ui.calc_text_size(spp_label).x + 2.0 * self.ui.style.frame_padding.x
        self._spp_cursor.pos = spy.float2(
            max(12.0, self.viewport_window.content_size.x - chip_w - 12.0), 12.0
        )

    def render_headless(
        self,
        width: int = 1600,
        height: int = 900,
        frames: int = 16,
        out_path: str = "fork_demo_headless.png",
    ) -> None:
        """Render the UI to an offscreen texture (no OS window) and write a
        PNG. Runs a few frames so the dock layout settles and the path tracer
        accumulates, then saves the final composite for inspection."""
        target = self.device.create_texture(
            format=spy.Format.rgba8_unorm,
            width=width,
            height=height,
            usage=spy.TextureUsage.render_target | spy.TextureUsage.shader_resource,
            label="headless_target",
        )

        # Force a fresh dock split so the layout is deterministic.
        self._needs_layout = True
        self.dock.request_split_horizontal(0.27)

        for f in range(frames):
            ce = self.device.create_command_encoder()
            self._size_pt_to_viewport()
            self.sample_count += 1
            self._update_spp_chip()
            self._dispatch_scene(ce, g_time=float(f) * 0.05)
            self.ui.begin_frame(width, height)
            self._try_apply_layout()
            self.ui.end_frame(target, ce)
            self.device.submit_command_buffer(ce.finish())

        self.device.wait()
        target.to_bitmap().write(out_path)
        print(f"[fork_demo] headless screenshot ({width}x{height}, {frames} frames) -> {out_path}")

    def run(self) -> None:
        t_start = time.perf_counter()
        last_frame = t_start
        frame_counter = 0

        # The body font registered with is_default=True is automatically
        # applied to every widget call. push_font / pop_font are useful
        # if you make direct ImGui calls between begin_frame and
        # end_frame; widget rendering happens inside begin_frame so
        # there's no Python hook point in between.

        while not self.window.should_close() and not self._terminate:
            # ---- events ----
            self.window.process_events()

            if not self.surface.config:
                continue

            surface_texture = self.surface.acquire_next_image()
            if not surface_texture:
                continue

            # Frame time accounting.
            now = time.perf_counter()
            dt = now - last_frame
            last_frame = now
            dt_ms = dt * 1000.0
            t_total = now - t_start

            # Exponential moving average smooths the per-frame jitter
            # before it goes into the bar chart (lower alpha = smoother).
            self._frame_ms_ema = (
                dt_ms if frame_counter == 0 else 0.06 * dt_ms + 0.94 * self._frame_ms_ema
            )
            self._frame_ms.append(self._frame_ms_ema)
            del self._frame_ms[:-FRAME_BARS]
            self.frame_plot.add_bar_groups(["ms"], [self._frame_ms])

            # ---- compute (path-tracer sample) ----
            command_encoder = self.device.create_command_encoder()
            # Size the PT render target to `content_size * render_scale`,
            # capped at the pixel budget. content_size is the viewport
            # window's actual inner area (captured last render); the
            # ui.Image stretches the texture to fill it.
            content = self.viewport_window.content_size
            disp_w = max(64.0, content.x)
            disp_h = max(64.0, content.y)
            pt_w = max(64, int(disp_w * self.render_scale))
            pt_h = max(64, int(disp_h * self.render_scale))
            if pt_w * pt_h > self.pixel_budget:
                s = (self.pixel_budget / float(pt_w * pt_h)) ** 0.5
                pt_w = max(64, int(pt_w * s))
                pt_h = max(64, int(pt_h * s))
            self._ensure_pt_textures(pt_w, pt_h)
            assert self.scene_texture is not None and self.accum_texture is not None

            tint = self.tint.value
            sky = self.background.value
            exposure = self.exposure
            cam_pos, cam_right, cam_up, cam_fwd = self._camera_basis()

            # Scene clock: advance when animate is on (and force a
            # fresh sample so motion shows), else freeze and let the
            # accumulator converge on the paused snapshot.
            animate = self.animate
            if animate:
                self.t_freeze = t_total
                self.sample_count = 0
            g_time = t_total if animate else self.t_freeze

            # Reflect play/pause state in the toolbar button: "pause" glyph
            # while playing, "play" glyph while paused.
            if self.has_icons:
                self.toggle_btn.label = ICON_PAUSE if animate else ICON_PLAY

            self.sample_count += 1
            # Update the top-right sample-count chip, kept a fixed 12px from
            # the viewport's right edge (same inset as the left toolbar).
            # Chip width = measured text width + button frame padding on both
            # sides, so the right gap is exact regardless of the digit count.
            spp_label = f"Samples: {self.sample_count}"
            self.spp_chip.label = spp_label
            chip_w = self.ui.calc_text_size(spp_label).x + 2.0 * self.ui.style.frame_padding.x
            self._spp_cursor.pos = spy.float2(
                max(12.0, self.viewport_window.content_size.x - chip_w - 12.0), 12.0
            )

            self.kernel.dispatch(
                thread_count=[self.pt_width, self.pt_height, 1],
                vars={
                    "g_output": self.scene_texture,
                    "g_accum": self.accum_texture,
                    "g_frame": frame_counter,
                    "g_sample_count": self.sample_count,
                    "g_time": g_time,
                    "g_tint": tint,
                    "g_sky": sky,
                    "g_exposure": exposure,
                    "g_cam_pos": cam_pos,
                    "g_cam_right": cam_right,
                    "g_cam_up": cam_up,
                    "g_cam_forward": cam_fwd,
                    "g_focal": self.focal,
                    "g_light_intensity": spy.float4(
                        self.light_warm.value,
                        self.light_cool.value,
                        self.light_pink.value,
                        self.light_lime.value,
                    ),
                },
                command_encoder=command_encoder,
            )
            # No surface blit: the output is displayed only via the
            # ui.Image inside the `viewport` window. The dockspace
            # central node fills the rest with docking_empty_bg.

            # ---- ui ----
            self.ui.begin_frame(surface_texture.width, surface_texture.height)
            self._try_apply_layout()
            self.ui.end_frame(surface_texture, command_encoder)

            # ---- present ----
            self.device.submit_command_buffer(command_encoder.finish())
            del surface_texture
            self.surface.present()

            frame_counter += 1


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Fork feature demo")
    parser.add_argument(
        "--headless",
        nargs="?",
        const="fork_demo_headless.png",
        default=None,
        metavar="PATH",
        help="Render the UI offscreen (no window) and save a PNG to PATH, then exit.",
    )
    parser.add_argument("--frames", type=int, default=16, help="Headless: frames to accumulate.")
    parser.add_argument("--width", type=int, default=1600, help="Headless: image width.")
    parser.add_argument("--height", type=int, default=900, help="Headless: image height.")
    args = parser.parse_args()

    if args.headless is not None:
        demo = ForkDemo(headless=True)
        demo.render_headless(
            width=args.width, height=args.height, frames=args.frames, out_path=args.headless
        )
        return

    demo = ForkDemo()
    demo.run()


if __name__ == "__main__":
    main()
