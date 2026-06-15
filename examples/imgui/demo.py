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
# Run from the repo root after building:  python examples/imgui/demo.py
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


# Fonts are bundled next to this script so the demo looks identical on
# every machine -- no dependency on what happens to be installed. Fira
# Sans (SIL OFL 1.1) is the text face, registered at a body and a header
# size; FontAwesome 6 Free Solid (SIL OFL 1.1) supplies the icon glyphs,
# merged into the body font via add_font(merge=True) so icon codepoints
# render inline in labels.
FONT_TEXT = EXAMPLE_DIR / "FiraSans-Regular.ttf"
FONT_ICONS = EXAMPLE_DIR / "fa-solid-900.ttf"
FONT_BODY_SIZE = 22.0
FONT_HEADER_SIZE = 28.0

ICON_RESET = "\uf021"  # arrows-rotate / refresh
ICON_CAMERA = "\uf030"  # camera


# Number of frame-time bars shown in the performance bar-group chart.
FRAME_BARS = 30

# The scene is static; this fixed time picks the pose fed to scene.slang
# (orbit angles, box/cube rotation, light positions). The path tracer then
# accumulates indefinitely until a reset (camera move, material edit, resize).
SCENE_TIME = 1.5


# Default tint for the user-tinted sphere (Nord frost #88C0D0).
TINT_DEFAULT = spy.float3(0.533, 0.753, 0.816)


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
                    "Re-run as:  DISPLAY=:1 python examples/imgui/demo.py"
                )
            self.window = spy.Window(
                width=1600,
                height=900,
                title="slangpy imgui demo",
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
        # The PT renders at 1/16 the viewport resolution -- a quarter of
        # the width and a quarter of the height of the viewport's content
        # area, i.e. a sixteenth of its pixel count. Re-allocated by
        # _ensure_pt_textures() whenever the viewport changes size; the
        # ui.Image bilinearly upscales the result to fill the viewport.
        self.pt_width = 1280
        self.pt_height = 720
        self.render_scale = 0.25  # per-axis -> 1/16 the pixel count
        self.scene_texture: Optional[spy.Texture] = None  # tonemapped output
        self.accum_texture: Optional[spy.Texture] = None  # running mean
        self.sample_count = 0

        # ------------------------------------------------------------------
        # Orbit camera (mouse-driven). LMB drag = rotate, MMB/RMB drag =
        # pan target, wheel = zoom.
        # ------------------------------------------------------------------
        self.cam_target = [0.0, 1.7, 0.0]  # roughly the box centre
        self.cam_yaw = 0.0
        self.cam_pitch = 0.06  # radians; + looks down at the scene
        self.cam_distance = 5.3
        self.focal = 1.5
        self._mouse_down = {"left": False, "right": False, "middle": False}
        self._last_mouse: Optional[tuple[float, float]] = None

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
        """Register the bundled fonts. Fira Sans becomes the default (body)
        font; FontAwesome is merged into it so icon glyphs render inline in
        labels (add_font(merge=True)); the same face at a larger size is
        kept as a named 'header' font for push_font('header')."""
        self.ui.add_font("body", str(FONT_TEXT), FONT_BODY_SIZE, is_default=True)
        # Merge must come right after the base font it overlays.
        self.ui.add_font("icons", str(FONT_ICONS), FONT_BODY_SIZE, merge=True)
        self.has_icons = True
        self.ui.add_font("header", str(FONT_TEXT), FONT_HEADER_SIZE)

    def _label(self, icon: str, text: str) -> str:
        """Prefix `text` with `icon` glyph when an icon font is loaded,
        else return the plain text."""
        return f"{icon}  {text}" if self.has_icons else text

    # ---------------------------------------------------------------- style

    def _configure_style(self) -> None:
        """Use the stock ImGui dark theme (no custom styling)."""
        self.ui.style.colors_dark()

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
        # Render settings: post-process / display controls (tone map,
        # exposure). Kept out of the scene inspector, which lists only
        # scene contents (objects + lights). Docked as a left-side tab.
        self.render_window = spy.ui.Window(
            screen,
            "Render Settings",
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

        walls = spy.ui.TreeNode(geometry, "Cornell Box", open=True)
        spy.ui.Text(walls, "5 diffuse walls (red / green) + 2 boxes")

        tinted = spy.ui.TreeNode(geometry, "Tinted Sphere", open=True)
        self.tint = spy.ui.ColorPicker3(
            tinted,
            "Tint Sphere",
            value=TINT_DEFAULT,
            callback=_reset,
        )

        mirror = spy.ui.TreeNode(geometry, "Mirror Sphere", open=True)
        spy.ui.Text(mirror, "Perfect reflection (ray-sphere)")

        glass = spy.ui.TreeNode(geometry, "Glass Sphere", open=True)
        spy.ui.Text(glass, "Refractive (dielectric, IOR 1.5)")

        # lights/  -- each of the four square ceiling emitters is its own
        # object node, with an intensity multiplier inside. 1.0 keeps the
        # shader's baked-in intensity; 0.0 turns the light off entirely.
        lights = spy.ui.TreeNode(scene, "Lights", open=True)

        def _light_slider(name: str) -> "spy.ui.SliderFloat":
            node = spy.ui.TreeNode(lights, name, open=True)
            return spy.ui.SliderFloat(
                node,
                "Intensity",
                value=1.0,
                min=0.0,
                max=3.0,
                callback=_reset,
            )

        self.light_warm = _light_slider("Warm Light")
        self.light_cool = _light_slider("Cool Light")
        self.light_pink = _light_slider("Pink Light")
        self.light_lime = _light_slider("Lime Light")

        # ===== window: render settings ================================
        # Post-process / display controls. Tone mapping and exposure are
        # applied on output from the accumulated mean, so changing them
        # only re-grades the displayed image -- no accumulation reset.
        self.tonemap = spy.ui.ComboBox(
            self.render_window,
            "Tone Map",
            value=0,
            items=["Reinhard", "ACES", "Filmic", "Clamp"],
        )
        self.exposure = spy.ui.SliderFloat(
            self.render_window,
            "Exposure",
            value=1.0,
            min=0.05,
            max=8.0,
        )
        # Homogeneous fog extinction (1 / mean-free-path). 0 disables it.
        # Unlike tone map / exposure this changes the rendered radiance, so
        # it resets accumulation.
        self.fog_density = spy.ui.SliderFloat(
            self.render_window,
            "Fog Density",
            value=0.05,
            min=0.0,
            max=0.6,
            callback=_reset,
        )

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
        # (no separate-window z-order issues). Camera drag ignores clicks
        # that land on a button (see _click_targets_viewport +
        # is_any_item_hovered).
        spy.ui.CursorPos(self.viewport_window, spy.float2(12.0, 12.0))
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
        # Stack the three left-side panels vertically by sub-splitting the
        # left node into three rows (performance / inspector / render) rather
        # than tabbing them all onto one node. Each split returns (top,
        # bottom); the first row takes ~1/3, then the remainder is halved.
        top, rest = self.dock.split_node(left, vertical=True, ratio=0.33)
        middle, bottom = self.dock.split_node(rest, vertical=True, ratio=0.5)
        self.perf_window.dock_id = top
        self.inspector_window.dock_id = middle
        self.render_window.dock_id = bottom
        # Viewport fills the right side completely.
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
                # Restart accumulation from scratch.
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
            path = f"imgui_demo_{self.sample_count:04d}spp.png"
            bmp.write_async(path)
            print(f"[imgui_demo] saved {path}")
        except Exception as e:
            print(f"[imgui_demo] screenshot failed: {e}")

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
                "g_exposure": self.exposure.value,
                "g_tonemap": self.tonemap.value,
                "g_fog_density": self.fog_density.value,
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
        """Size the PT render target to 1/16 the viewport resolution (a
        quarter of the width and height of the viewport's content area)."""
        content = self.viewport_window.content_size
        disp_w = max(64.0, content.x)
        disp_h = max(64.0, content.y)
        pt_w = max(64, int(disp_w * self.render_scale))
        pt_h = max(64, int(disp_h * self.render_scale))
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
        out_path: str = "imgui_demo_headless.png",
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

        for _ in range(frames):
            ce = self.device.create_command_encoder()
            self._size_pt_to_viewport()
            self.sample_count += 1
            self._update_spp_chip()
            self._dispatch_scene(ce, g_time=SCENE_TIME)
            self.ui.begin_frame(width, height)
            self._try_apply_layout()
            self.ui.end_frame(target, ce)
            self.device.submit_command_buffer(ce.finish())

        self.device.wait()
        target.to_bitmap().write(out_path)
        print(f"[imgui_demo] headless screenshot ({width}x{height}, {frames} frames) -> {out_path}")

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
            # Size the PT render target to 1/4 the viewport resolution.
            # content_size is the viewport window's actual inner area
            # (captured last render); the ui.Image stretches the texture
            # to fill it.
            self._size_pt_to_viewport()
            assert self.scene_texture is not None and self.accum_texture is not None

            tint = self.tint.value
            exposure = self.exposure.value
            cam_pos, cam_right, cam_up, cam_fwd = self._camera_basis()

            # Static scene (fixed pose at SCENE_TIME): the path tracer just
            # keeps accumulating. Resets come from the usual triggers --
            # camera move, material edits, viewport resize, Space.
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
                    "g_time": SCENE_TIME,
                    "g_tint": tint,
                    "g_exposure": exposure,
                    "g_tonemap": self.tonemap.value,
                    "g_fog_density": self.fog_density.value,
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
        const="imgui_demo_headless.png",
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
