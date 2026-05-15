# SlangPy (iveevi fork)

Fork of [shader-slang/slangpy](https://github.com/shader-slang/slangpy)
that extends `spy.ui` for building real apps around slangpy compute
output through ImGui — dockable windows, the slangpy-rendered scene as
an `Image` widget, real ImPlot-backed graphs, programmatic docking
with horizontal/vertical splits, fonts, a live `ImGuiStyle` view, layout
persistence, color pickers and separators. Everything outside
`src/sgl/ui/`, `src/slangpy_ext/ui/`, the `decorated`/`ui_context` flag
additions, and the ImPlot fetch in `external/CMakeLists.txt` matches
upstream verbatim.

## Documentation

Per-feature reference for the fork lives in [`docs/fork/`](docs/fork/):

| Page | Covers |
|---|---|
| [`fork/index.rst`](docs/fork/index.rst) | Overview, motivation, summary table |
| [`fork/widgets.rst`](docs/fork/widgets.rst) | `Image`, `Plot`, `PlotLines`, `Separator`, `ColorEdit/Picker`, `DockSpace`, `Window` |
| [`fork/plotting.rst`](docs/fork/plotting.rst) | `Plot` deep-dive: line / histogram / bar groups, legend, axes |
| [`fork/context.rst`](docs/fork/context.rst) | Font API, `Style` + `Col`, `AppWindow.ui_context`, `imgui.ini` |
| [`fork/window.rst`](docs/fork/window.rst) | `decorated` / `show_title_bar` / `dock_id`, layout persistence |
| [`fork/internals.rst`](docs/fork/internals.rst) | ImPlot fetch + patches, `end_frame` rendering fixes |

The upstream Sphinx docs build cleanly with the fork pages mounted:

```bash
sphinx-build -b html docs docs/_build/html
```

## Example

See [`examples/fork_demo/`](examples/fork_demo/) — a single program
exercising essentially every fork feature in one app: a progressive SDF
path tracer rendered into a dockable `ui.Image` viewport, with an
orbit-camera (mouse drag), per-light intensity sliders, exposure /
render-scale controls, scene material editing, a Nord-themed live
`Style`, custom fonts, and persistent layout via `imgui.ini`.

```bash
python examples/fork_demo/fork_demo.py
```

The README inside `examples/fork_demo/` enumerates which fork feature
each part of the demo exercises and where in the code to look.

## Upstream

For the underlying API — `slangpy.Device`, the functional API
(`module.fn(args)` → kernel), `Tensor`, `Buffer`, ray-tracing helpers,
PyTorch integration, etc. — refer to the upstream documentation at
[slangpy.shader-slang.org](https://slangpy.shader-slang.org/) and the
upstream README. This fork doesn't change any of that.
