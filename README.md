# SlangPy

Fork of [shader-slang/slangpy](https://github.com/shader-slang/slangpy)
that extends `spy.ui` for building real apps that display slangpy
compute output through ImGui — dockable windows, the slangpy-rendered
scene as an `Image` widget, real ImPlot-backed graphs, programmatic
docking with horizontal/vertical splits, color pickers, and a font API.
Everything outside `src/sgl/ui/` and `src/slangpy_ext/ui/` matches
upstream.

## What's added

### New widgets in `spy.ui`

| Widget | What it wraps |
|---|---|
| `ui.Image(parent, texture, size, uv0, uv1)` | `ImGui::Image()` — takes a `sgl.Texture` directly (`ImTextureID` is already typedef'd to `sgl::Texture*` in `imgui_config.h`), so you can display any compute-written texture in a docked window. |
| `ui.Plot(parent, label, x_label, y_label, size, autofit_x, autofit_y)` | `ImPlot::BeginPlot/SetupAxes/PlotLine/EndPlot`. Methods: `add_line(name, values)`, `push_to_line(name, value, max_history)`, `set_x_limits/set_y_limits`. Real axes, ticks, legend, grid. |
| `ui.PlotLines(parent, label, values, overlay, scale_min, scale_max, size)` | Lightweight `ImGui::PlotLines` wrapper for sparkline-style plots without the ImPlot dependency. |
| `ui.Separator(parent, label)` | `ImGui::Separator()` (no label) / `ImGui::SeparatorText(label)`. |
| `ui.ColorEdit3 / ColorEdit4 / ColorPicker3 / ColorPicker4` | `ImGui::ColorEdit3/4` and `ImGui::ColorPicker3/4` on `float3`/`float4` `ValueProperty`s. |
| `ui.DockSpace(parent)` | `ImGui::DockSpaceOverViewport` with optional `passthru_central_node` (transparent central pane so the surface shows through). Exposes `request_split_horizontal(ratio)` / `request_split_vertical(ratio)` plus `dock_id` / `left_dock_id` / `right_dock_id` for programmatic docking without dragging. |
| `ui.Window.dock_id` | Setter that calls `ImGui::SetNextWindowDockID` on the next render — the missing piece for first-launch dock layouts. |

### `ui.Context` API

- `add_font(name, path, size, is_default=False)` — load a TTF from disk
  and register it under `name`.
- `push_font(name)` / `pop_font()` — `ImGui::PushFont/PopFont` on a
  registered font.
- ImPlot context is created/destroyed alongside ImGui's.
- `io.IniFilename = "imgui.ini"` (was `nullptr`) so the dockspace layout
  persists across runs.

### `AppWindow.ui_context`

Read-only property exposing the `ui::Context` that `AppWindow` owns, so
you can call `add_font` / `push_font` on it after construction.

### Build system

- `external/CMakeLists.txt` fetches **ImPlot 0.16** alongside ImGui.
- ImPlot 0.16 references `IM_OFFSETOF`, `IM_FLOOR`, `ImFont::FontSize`,
  and `ImFont::FindGlyph`, all of which were removed or moved in
  ImGui 1.92. The fork patches `implot.cpp` post-fetch (`IM_FLOOR` →
  `ImFloor`, `font->FindGlyph` → `font->GetFontBaked(g.FontSize)->FindGlyph`,
  and the `g.FontSize / font->FontSize` scale degenerates to 1.0) and
  defines `IM_OFFSETOF=offsetof` as a target compile definition.
- ImPlot's TUs are compiled with `-fvisibility=default` so the binding
  layer in `slangpy_ext` can link to its symbols out of `libsgl`.

### Rendering fixes (for `ui.Image` correctness)

`Context::end_frame` was tightened in two places to make `ImGui::Image`
actually display foreign / compute-written textures on Vulkan:

1. **Auto state-transition.** Before beginning the ImGui render pass,
   `end_frame` walks the draw lists, collects every unique texture
   pointer, and calls `command_encoder->set_texture_state(.., shader_resource)`.
   Without this, slang-rhi's per-encoder state tracker doesn't insert
   the UAV → SRV layout barrier for textures that were just written by
   compute, and the sampler reads zero.
2. **Per-cmd pipeline rebind.** The render loop binds the pipeline and
   writes the uniforms (sampler / scale / offset / `is_srgb_format`)
   *before each draw command*, not just once per pass. slang-rhi's
   shader objects commit descriptor sets at pipeline-bind time, so
   mid-pass `set_texture_view` modifications didn't reach the shader on
   subsequent draws.

Together these let you put a compute kernel's output texture in a
dockable ImGui window via `ui.Image` and see the live contents.
