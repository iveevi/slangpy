# SlangPy (iveevi fork)

Fork of [shader-slang/slangpy](https://github.com/shader-slang/slangpy)
that extends `spy.ui` for building real apps around slangpy compute
output through ImGui — dockable windows, the slangpy-rendered scene as
an `Image` widget, real ImPlot-backed graphs, programmatic docking
with horizontal/vertical splits (rebuildable at runtime), docked panels
that rescale proportionally when the window resizes, menu bars / menus /
menu items, selectable rows, tree nodes, per-widget item widths, fonts,
a live `ImGuiStyle` view, configurable layout persistence (the ImGui ini
file can be redirected or disabled via `Context.ini_filename`), color
pickers and separators. Everything outside `src/sgl/ui/`,
`src/slangpy_ext/ui/`, the `decorated`/`ui_context` flag additions, and
the ImPlot fetch in `external/CMakeLists.txt` matches upstream verbatim.

## Documentation

The `spy.ui` widgets (including the fork's additions — `Image`, `Plot`,
`DockSpace`, `TreeNode`, `MenuBar`/`Menu`/`MenuItem`, `Selectable`,
`ColorEdit/Picker`, `Separator`, the font/style APIs, etc.) are documented
in the generated API reference under the `slangpy.ui` namespace, sourced
from the docstrings in `src/sgl/ui/`. The
Sphinx docs build with:

```bash
sphinx-build -b html docs docs/_build/html
```

## Example

See [`examples/imgui/`](examples/imgui/) — a single program exercising
essentially every fork feature in one app: a progressive path tracer
(analytic ray/primitive intersection, refractive glass) rendered into a
dockable `ui.Image` viewport, with an orbit-camera (mouse drag), per-light
intensity sliders, scene material editing, a viewport overlay toolbar +
sample-count chip, merged FontAwesome icons, and persistent layout via
`imgui.ini`.

```bash
python examples/imgui/demo.py
```

The README inside `examples/imgui/` enumerates which fork feature each
part of the demo exercises and where in the code to look. A separate
`examples/imgui_bundle/` holds the external-ImGui (imgui_bundle)
offscreen-rendering example.

## Upstream

For the underlying API — `slangpy.Device`, the functional API
(`module.fn(args)` → kernel), `Tensor`, `Buffer`, ray-tracing helpers,
PyTorch integration, etc. — refer to the upstream documentation at
[slangpy.shader-slang.org](https://slangpy.shader-slang.org/) and the
upstream README. This fork doesn't change any of that.
