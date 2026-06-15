# Fork feature demo

A single program exercising every feature the `iveevi/slangpy` fork
adds on top of upstream. See the generated API reference (`slangpy.ui`)
for per-widget documentation.

The compute workload is a **progressive path tracer** using analytic
ray/primitive intersection (ray-sphere, ray-plane, ray-box) -- not SDF
sphere tracing. The scene is a static Cornell-box-style enclosure: five
diffuse walls (red / green sides), two diffuse boxes, a perfectly
reflective sphere, a refractive glass sphere (dielectric, Fresnel
reflect/refract), a user-tinted diffuse sphere, and four square ceiling
area lights (sampled with next-event estimation), sitting in a gradient
sky. It runs 8-bounce path tracing with next-event estimation for
diffuse surfaces and specular chains for mirror/glass. An optional
homogeneous fog (a participating medium with controllable density,
isotropic single scattering via free-flight distance sampling) fills the
enclosure. Samples accumulate into a running mean until a material /
camera / fog / viewport change resets the accumulation. Per-frame
jittered primary rays antialias edges, and a small dither on output
removes 8-bit banding in the sky gradient. The output tone mapper is selectable (Reinhard, ACES,
Filmic, Clamp) and applied post-accumulation, so switching it does not
reset the running mean.

## Run

```bash
python examples/imgui/demo.py
```

Run from the repo root after building slangpy. The compute shader
(`scene.slang`) is loaded relative to this directory via the device's
`compiler_options.include_paths`.

## Controls

* **F1** — reset the dock layout (deletes `imgui.ini` and re-splits
  programmatically).
* **Esc** — quit.

## What's demonstrated

| Feature | Where in the code |
| --- | --- |
| `spy.Window(decorated=False)` | *not exercised here* — tiling WMs (niri etc.) may park borderless tiles off-viewport, so the demo uses the default `decorated=True`. |
| `ui.Context.add_font(...)` | `_register_fonts` — body font becomes default |
| `ui.Context.add_font(merge=True)` | `_register_fonts` — bundled FontAwesome (`fa-solid-900.ttf`) merged into the body font |
| `ui.CursorPos` + `ui.Button` + `ui.SameLine` | FontAwesome action toolbar + sample-count readout drawn over the `viewport` image |
| `ui.Context.style` + `ui.Col` | `_configure_style` — scalar/vec2/bool fields, flat borderless surfaces, color slots |
| `ui.DockSpace` + `passthru_central_node` | `_build_widgets` |
| `ui.DockSpace.request_split_horizontal` | `__init__` (only when no `imgui.ini`) and F1 handler |
| `ui.Window.dock_id = ...` | `_try_apply_layout` — programmatic dock assignment |
| `ui.Image` | scene panel; texture is the compute output |
| `ui.Plot` line + bar groups | `phases_plot` — frame phase telemetry |
| `ui.Plot` histogram | `hist_plot` — frame-time distribution |
| `ui.LegendLocation.south` + outside + horizontal | `phases_plot` |
| `ui.Plot.add_bar_groups` (rolling) | `performance` panel frame-time bar chart |
| `ui.TreeNode` (programmatic `open`) | `scene inspector` panel `scene` tree |
| `ui.TreeNode` nested (scene graph) | `scene inspector` panel (geometry + per-light object nodes) |
| `ui.ColorPicker3` | `scene inspector` `Tinted Sphere` tint |
| `ui.ComboBox` | `render settings` window — tone-map selector |
| `ui.SliderFloat` | `render settings` `Exposure` / `Fog Density` + per-light intensity sliders |
| `imgui.ini` persistence | enabled by default; saved layout reloads on second launch |

## Notes

* The first launch builds a 27/73 horizontal split. The left node holds
  the `performance` and `scene inspector` panels as tabs;
  the `viewport` fills the right. Drag tabs to
  rearrange; ImGui saves the layout to `imgui.ini` in the working
  directory.
* If you want to start from a clean layout, hit F1 or delete
  `imgui.ini` between runs.
* Fonts are bundled next to the demo (`FiraSans-Regular.ttf` and
  `fa-solid-900.ttf`, both SIL OFL 1.1) and loaded by fixed path, so the
  UI looks the same on every machine with no dependency on installed
  system fonts.
