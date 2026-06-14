# Fork feature demo

A single program exercising every feature the `iveevi/slangpy` fork
adds on top of upstream. See `docs/fork/` for the per-feature
reference.

The compute workload is a **progressive path tracer** using analytic
ray/primitive intersection (ray-sphere, ray-plane, ray-box) -- not SDF
sphere tracing. The scene has a ground plane, orbiting diffuse spheres,
pillars, rotating boxes/cubes, a mirror sphere, refractive glass spheres
(dielectric, Fresnel reflect/refract), and animated emissive lights.
It runs 8-bounce path tracing with next-event estimation for diffuse
surfaces and specular chains for mirror/glass. Each frame produces one
new sample-per-pixel and accumulates into a running mean (Reinhard-
tonemapped on output). Tweaking any material / camera control resets the
accumulation.

## Run

```bash
python examples/fork_demo/fork_demo.py
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
| `spy.Window(decorated=False)` | *not exercised here* — covered in `docs/fork/window.rst`. Tiling WMs (niri etc.) may park borderless tiles off-viewport, so the demo uses the default `decorated=True`. |
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
| `ui.TreeNode` nested (scene graph) | `scene inspector` panel (geometry / lights / environment) |
| `ui.ColorPicker3` / `ColorEdit4` | left panel `tint` / `background` |
| `imgui.ini` persistence | enabled by default; saved layout reloads on second launch |

## Notes

* The first launch builds a 27/73 horizontal split. The left node holds
  the `performance` and `scene inspector` panels as tabs;
  the `viewport` fills the right. Drag tabs to
  rearrange; ImGui saves the layout to `imgui.ini` in the working
  directory.
* If you want to start from a clean layout, hit F1 or delete
  `imgui.ini` between runs.
* The font paths in `FONT_PATHS` are Linux-typical
  (DejaVu Sans). On other platforms, edit them or let the demo skip
  the font registration (it still runs, just with the ImGui default
  font).
