# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
#
# Demo exercising the iveevi/slangpy fork's spy.ui additions: a progressive
# path tracer rendered into a dockable ui.Image viewport with plots and a scene
# inspector. F1 resets the layout, Esc quits.

from __future__ import annotations

import math
import os
import time
from pathlib import Path
from typing import Optional

import slangpy as spy


EXAMPLE_DIR = Path(__file__).parent
IMGUI_INI = "imgui.ini"


# Viewport resize-grip exclusion zone, in pixels.
GRIP_SIZE = 33.0


# Number of frame-time bars shown in the performance bar-group chart.
FRAME_BARS = 30

SCENE_TIME = 1.5


# Default tint for the user-tinted sphere (Nord frost #88C0D0).
TINT_DEFAULT = spy.float3(0.533, 0.753, 0.816)


class ForkDemo:
    def __init__(self, headless: bool = False) -> None:
        self.headless = headless
        self.window: Optional[spy.Window] = None
        self.surface = None

        if not headless:
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

        self.ui = spy.ui.Context(self.device)
        self._configure_style()

        program = self.device.load_program("scene", ["compute_main"])
        self.kernel = self.device.create_compute_kernel(program)
        self.pt_width = 1280
        self.pt_height = 720
        self.render_scale = 0.25  # per-axis -> 1/16 the pixel count
        self.scene_texture: Optional[spy.Texture] = None  # tonemapped output
        self.accum_texture: Optional[spy.Texture] = None  # running mean
        self.sample_count = 0

        self.cam_target = [0.0, 1.7, 0.0]  # roughly the box centre
        self.cam_yaw = 0.0
        self.cam_pitch = 0.06  # radians; + looks down at the scene
        self.cam_distance = 5.3
        self.focal = 1.5
        self._mouse_down = {"left": False, "right": False, "middle": False}
        self._last_mouse: Optional[tuple[float, float]] = None

        if not headless:
            self.window.on_keyboard_event = self._on_keyboard_event
            self.window.on_mouse_event = self._on_mouse_event
            self.window.on_resize = self._on_resize
        self._terminate = False

        self._build_widgets()

        self._needs_layout = not Path(IMGUI_INI).exists()
        if self._needs_layout:
            self.dock.request_split_horizontal(0.27)

    # ---------------------------------------------------------------- style

    def _configure_style(self) -> None:
        """Use the stock ImGui dark theme (no custom styling)."""
        self.ui.style.colors_dark()

    # -------------------------------------------------------------- widgets

    def _build_widgets(self) -> None:
        screen = self.ui.screen

        self.dock = spy.ui.DockSpace(screen)
        self.dock.passthru_central_node = False

        self.perf_window = spy.ui.Window(screen, "Performance", size=spy.float2(400, 900))
        self.viewport_window = spy.ui.Window(
            screen,
            "Viewport",
            position=spy.float2(440, 30),
            size=spy.float2(1100, 900),
        )
        self.inspector_window = spy.ui.Window(
            screen,
            "Scene Inspector",
            size=spy.float2(400, 900),
        )
        self.render_window = spy.ui.Window(
            screen,
            "Render Settings",
            size=spy.float2(400, 900),
        )

        def _reset(*_: object) -> None:
            self.sample_count = 0

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
        self.fog_density = spy.ui.SliderFloat(
            self.render_window,
            "Fog Density",
            value=0.05,
            min=0.0,
            max=0.6,
            callback=_reset,
        )

        self._frame_ms = [0.0] * FRAME_BARS
        self._frame_ms_ema = 0.0
        self.frame_plot = spy.ui.Plot(
            self.perf_window,
            label="Frame Time",
            y_label="ms",
            size=spy.float2(-1, -1),
        )
        self.frame_plot.add_bar_groups(["ms"], [self._frame_ms])

        self.viewport_window.padding = spy.float2(0.0, 0.0)
        self.viewport_image = spy.ui.Image(
            self.viewport_window,
            texture=None,
            size=spy.float2(0.0, 0.0),
        )

        spy.ui.CursorPos(self.viewport_window, spy.float2(12.0, 12.0))
        spy.ui.Button(
            self.viewport_window,
            "Reset",
            callback=_reset,
            border=True,
        )
        spy.ui.SameLine(self.viewport_window)
        spy.ui.Button(
            self.viewport_window,
            "Save",
            callback=self._save_screenshot,
            border=True,
        )

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
        title_h = 38.0
        pad_x = 12.0
        in_image = (
            wp.x + pad_x <= px <= wp.x + ws.x - pad_x and wp.y + title_h <= py <= wp.y + ws.y - 4.0
        )
        if not in_image:
            return False
        grip = GRIP_SIZE
        if px >= wp.x + ws.x - grip and py >= wp.y + ws.y - grip:
            return False
        if self.ui.is_any_item_hovered():
            return False
        for panel in (
            self.perf_window,
            self.inspector_window,
        ):
            if self._rect_contains(panel, px, py):
                return False
        return True

    def _on_mouse_event(self, event: spy.MouseEvent) -> None:
        et = spy.MouseEventType
        px, py = float(event.pos.x), float(event.pos.y)

        drag_active = any(self._mouse_down.values())

        if event.type == et.button_down:
            if self._click_targets_viewport(px, py):
                self._mouse_down[event.button.name] = True
                self._last_mouse = (px, py)
                return
            self.ui.handle_mouse_event(event)
            return

        if event.type == et.button_up:
            if self._mouse_down.get(event.button.name, False):
                self._mouse_down[event.button.name] = False
                self._last_mouse = None
                return
            self.ui.handle_mouse_event(event)
            return

        if event.type == et.move:
            if drag_active and self._last_mouse is not None:
                dx = px - self._last_mouse[0]
                dy = py - self._last_mouse[1]
                if self._mouse_down["left"]:
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

            self._frame_ms_ema = (
                dt_ms if frame_counter == 0 else 0.06 * dt_ms + 0.94 * self._frame_ms_ema
            )
            self._frame_ms.append(self._frame_ms_ema)
            del self._frame_ms[:-FRAME_BARS]
            self.frame_plot.add_bar_groups(["ms"], [self._frame_ms])

            # ---- compute (path-tracer sample) ----
            command_encoder = self.device.create_command_encoder()
            self._size_pt_to_viewport()
            assert self.scene_texture is not None and self.accum_texture is not None

            tint = self.tint.value
            exposure = self.exposure.value
            cam_pos, cam_right, cam_up, cam_fwd = self._camera_basis()

            self.sample_count += 1
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
