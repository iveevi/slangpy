# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
#
# Showcase for every feature added by the iveevi/slangpy fork.
#
# Demonstrates, in a single program:
#
#   * spy.Window(decorated=False) -- borderless OS window
#   * ui.Context.add_font / push_font / pop_font -- font registry
#   * ui.Context.style + ui.Col + ui.Style.set_color -- live ImGuiStyle
#   * imgui.ini persistence (saved layout reload on second launch)
#   * ui.DockSpace with passthru_central_node and request_split_horizontal
#   * ui.Window with show_title_bar=False and programmatic dock_id
#   * ui.Image displaying a compute-written texture
#   * ui.Plot mixing line, histogram and bar-group series
#   * ui.LegendLocation + legend_outside + legend_horizontal
#   * ui.PlotLines (sparkline)
#   * ui.Separator (plain and labelled)
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
    def __init__(self) -> None:
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

        # ------------------------------------------------------------------
        # Default-decorated OS window so tiling WMs (niri etc.) manage
        # it as a normal tile. The fork's `decorated=False` flag is
        # documented in docs/fork/window.rst -- pass it through here if
        # you want a borderless surface (note: under a scrolling tiling
        # WM the resulting tile may park off-viewport).
        # ------------------------------------------------------------------
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
        # Progressive SDF path tracer. The kernel writes one new sample
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
        # Event wiring.
        # ------------------------------------------------------------------
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
        """Register fonts that exist; mark the body font as default."""
        body = _first_existing(FONT_CANDIDATES["body"])
        header = _first_existing(FONT_CANDIDATES["header"])
        if body is not None:
            self.ui.add_font("body", body, FONT_BODY_SIZE, is_default=True)
        if header is not None:
            self.ui.add_font("header", header, FONT_HEADER_SIZE)

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

        # Tabs
        s.set_color(spy.ui.Col.tab, _c(NORD1))
        s.set_color(spy.ui.Col.tab_hovered, _c(NORD3))
        s.set_color(spy.ui.Col.tab_selected, _c(NORD10))
        s.set_color(spy.ui.Col.tab_dimmed, _c(NORD1, 0.80))
        s.set_color(spy.ui.Col.tab_dimmed_selected, _c(NORD10, 0.80))

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

        # Controls panel: a normal titled window, docked to the left
        # node. Title makes it obviously a window; the fork's
        # show_title_bar=False feature is still exercised by the other
        # demo windows when you collapse them via the [v] arrow.
        self.left_window = spy.ui.Window(screen, "controls", size=spy.float2(400, 900))
        # Dedicated viewport window holding the ui.Image of the
        # path-tracer output. Docked to the right node so it fills the
        # entire right side of the layout. Mouse drag inside this
        # window's area drives the camera.
        self.viewport_window = spy.ui.Window(
            screen,
            "viewport",
            position=spy.float2(440, 30),
            size=spy.float2(1100, 900),
        )

        # -- left controls ------------------------------------------------
        # Organised into collapsible ui.Group sections.

        def _reset(*_: object) -> None:
            self.sample_count = 0

        # ----- group: rendering ---------------------------------------
        rendering = spy.ui.Group(self.left_window, "rendering")
        # When animate=True, the scene clock advances and accumulation
        # is reset every frame (1-spp motion). Untick to pause the
        # clock and let the path tracer converge.
        self.animate = spy.ui.CheckBox(rendering, "animate", value=True)
        # Exposure is post-accumulation, so no reset callback.
        self.exposure = spy.ui.SliderFloat(
            rendering,
            "exposure",
            value=1.0,
            min=0.1,
            max=5.0,
        )

        # Render-scale changes the PT target resolution; reallocating
        # the texture will reset the accumulator regardless, but make
        # it explicit so the slider feels responsive.
        def _set_scale(v: float) -> None:
            self.render_scale = v
            self.sample_count = 0

        self.render_scale_slider = spy.ui.SliderFloat(
            rendering,
            "render scale",
            value=self.render_scale,
            min=0.25,
            max=1.0,
            callback=_set_scale,
        )
        spy.ui.Button(rendering, "reset accumulation", callback=_reset)
        spy.ui.Button(rendering, "save screenshot", callback=self._save_screenshot)

        # ----- scene tree (nested TreeNodes) --------------------------
        # A scene-graph mirror of the SDF scene in scene.slang. TreeNode
        # widgets nest arbitrarily: a TreeNode parented to another
        # TreeNode renders indented inside it (ImGui TreeNodeEx/TreePop).
        # The leaves are live controls, so editing the tree drives the
        # path tracer and resets accumulation via _reset.
        scene = spy.ui.TreeNode(self.left_window, "scene", open=True)

        # geometry/
        geometry = spy.ui.TreeNode(scene, "geometry", open=True)

        orbiting = spy.ui.TreeNode(geometry, "orbiting spheres")
        self.tint = spy.ui.ColorPicker3(
            orbiting,
            "tint sphere",
            value=spy.float3(NORD8[0], NORD8[1], NORD8[2]),
            callback=_reset,
        )
        spy.ui.Text(orbiting, "+ 2 fixed diffuse spheres")

        mirror = spy.ui.TreeNode(geometry, "mirror sphere")
        spy.ui.Text(mirror, "metal . bobbing")

        back_row = spy.ui.TreeNode(geometry, "back row")
        spy.ui.Text(back_row, "5 x diffuse")

        # lights/  -- one intensity multiplier per light. 1.0 keeps the
        # shader's baked-in intensity; 0.0 turns the light off entirely.
        lights = spy.ui.TreeNode(scene, "lights", open=True)
        self.light_warm = spy.ui.SliderFloat(
            lights,
            "warm",
            value=1.0,
            min=0.0,
            max=3.0,
            callback=_reset,
        )
        self.light_cool = spy.ui.SliderFloat(
            lights,
            "cool",
            value=1.0,
            min=0.0,
            max=3.0,
            callback=_reset,
        )
        self.light_pink = spy.ui.SliderFloat(
            lights,
            "pink",
            value=1.0,
            min=0.0,
            max=3.0,
            callback=_reset,
        )
        self.light_lime = spy.ui.SliderFloat(
            lights,
            "lime",
            value=1.0,
            min=0.0,
            max=3.0,
            callback=_reset,
        )

        # environment/
        environment = spy.ui.TreeNode(scene, "environment")
        self.background = spy.ui.ColorEdit4(
            environment,
            "sky / ambient",
            value=spy.float4(0.0, 0.0, 0.0, 1.0),
            callback=_reset,
        )
        spy.ui.Text(environment, "ground plane")

        # ----- tree node: advanced (collapsible, open by default) -----
        advanced = spy.ui.TreeNode(self.left_window, "advanced", open=True)
        self.gamma = spy.ui.SliderFloat(
            advanced,
            "gamma",
            value=2.2,
            min=1.0,
            max=3.0,
            callback=_reset,
        )
        self.exposure = spy.ui.SliderFloat(
            advanced,
            "exposure",
            value=1.0,
            min=0.1,
            max=4.0,
            callback=_reset,
        )

        # ----- group: stats -------------------------------------------
        stats = spy.ui.Group(self.left_window, "stats")
        self.fps_text = spy.ui.Text(stats, "FPS: --")
        self.spp_text = spy.ui.Text(stats, "samples: 0")
        self.size_text = spy.ui.Text(stats, "render: -- x --")
        self.spark = spy.ui.PlotLines(
            stats,
            label="ms",
            values=[0.0] * 120,
            overlay="frame ms",
            size=spy.float2(0, 60),
        )

        # ----- key hints (outside groups) ----------------------------
        spy.ui.Separator(self.left_window)
        spy.ui.Text(
            self.left_window,
            "LMB drag: rotate    MMB/RMB drag: pan    wheel: zoom",
        )
        spy.ui.Text(
            self.left_window,
            "Space: play/pause    F1: reset dock layout    Esc: quit",
        )

        # -- viewport panel: ui.Image of the path-traced output ---------
        self.viewport_image = spy.ui.Image(
            self.viewport_window,
            texture=None,
            size=spy.float2(self.pt_width, self.pt_height),
        )

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
        self.left_window.dock_id = left
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
                # Toggle the animate checkbox. When pausing, also reset
                # the accumulator so the freshly-frozen scene converges
                # from scratch rather than blending with the prior
                # animated samples.
                self.animate.value = not self.animate.value
                if not self.animate.value:
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
        # Reject if any other panel covers the cursor -- avoids
        # camera-grabbing a click that's targeting that panel.
        if self._rect_contains(self.left_window, px, py):
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

    def _ensure_pt_textures(self, pt_w: int, pt_h: int, disp_w: float, disp_h: float) -> None:
        """Allocate / reallocate the path-tracer's textures so the
        render target is `(pt_w, pt_h)` pixels, and size the ui.Image
        widget to `(disp_w, disp_h)` so it fills the window content
        area. Triggers an accumulation reset on render-target resize."""
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
        # Always sync the display size -- the image stretches the
        # (lower-res) PT texture across the full window content area.
        self.viewport_image.size = spy.float2(disp_w, disp_h)

    def run(self) -> None:
        t_start = time.perf_counter()
        last_frame = t_start
        fps_avg = 0.0
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

            self.spark.push_value(dt_ms)
            fps_avg = 0.05 * (1.0 / max(dt, 1e-6)) + 0.95 * fps_avg
            self.fps_text.text = f"FPS: {fps_avg:5.1f}    ({dt_ms:5.2f} ms)"

            # ---- compute (path-tracer sample) ----
            command_encoder = self.device.create_command_encoder()
            # Compute the viewport's content area, then size the PT
            # render target to `content * render_scale`, capped at the
            # pixel budget. The ui.Image stretches the texture to fill
            # the full content area.
            wsize = self.viewport_window.size
            disp_w = max(64.0, wsize.x - 24.0)
            disp_h = max(64.0, wsize.y - 44.0)
            pt_w = max(64, int(disp_w * self.render_scale))
            pt_h = max(64, int(disp_h * self.render_scale))
            if pt_w * pt_h > self.pixel_budget:
                s = (self.pixel_budget / float(pt_w * pt_h)) ** 0.5
                pt_w = max(64, int(pt_w * s))
                pt_h = max(64, int(pt_h * s))
            self._ensure_pt_textures(pt_w, pt_h, disp_w, disp_h)
            assert self.scene_texture is not None and self.accum_texture is not None

            tint = self.tint.value
            sky = self.background.value
            exposure = self.exposure.value
            cam_pos, cam_right, cam_up, cam_fwd = self._camera_basis()

            # Scene clock: advance when animate is on (and force a
            # fresh sample so motion shows), else freeze and let the
            # accumulator converge on the paused snapshot.
            animate = self.animate.value
            if animate:
                self.t_freeze = t_total
                self.sample_count = 0
            g_time = t_total if animate else self.t_freeze

            self.sample_count += 1
            self.spp_text.text = f"samples: {self.sample_count}"
            self.size_text.text = f"render: {self.pt_width} x {self.pt_height}"

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
    demo = ForkDemo()
    demo.run()


if __name__ == "__main__":
    main()
