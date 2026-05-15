.. _sec-fork-internals:

Build System and Rendering Internals
====================================

This page covers the lower-level changes that make the new widgets
work: the ImPlot integration (fetch, ImGui-1.92 patch, symbol
visibility), and the two tightenings in ``ui::Context::end_frame``
that make ``ui.Image`` correctly display compute-written textures on
Vulkan.

ImPlot integration
------------------

ImPlot 0.16 is fetched alongside ImGui from ``external/CMakeLists.txt``.
There are three frictions worth being aware of.

ImGui 1.92 API drift
~~~~~~~~~~~~~~~~~~~~

ImPlot 0.16 was cut against an older ImGui. ImGui 1.92 removed or
moved several symbols ImPlot relies on, so the fork patches
``implot.cpp`` post-fetch:

* ``IM_FLOOR`` → ``ImFloor``.
* ``ImFont::FontSize`` and ``ImFont::FindGlyph`` were moved onto
  ``ImFontBaked``; the patch rewrites
  ``font->FindGlyph(...)`` → ``font->GetFontBaked(g.FontSize)->FindGlyph(...)``,
  and the ``g.FontSize / font->FontSize`` scale degenerates to ``1.0``.
* ``IM_OFFSETOF`` was removed; defined back to ``offsetof`` as a
  target compile definition.

Patching is done in CMake against the fetched source so re-fetches
don't accumulate drift.

Symbol visibility
~~~~~~~~~~~~~~~~~

ImPlot's translation units are compiled with ``-fvisibility=default``.
The binding layer in ``slangpy_ext`` links to ImPlot symbols out of
``libsgl``, which has hidden default visibility; without the override
those symbols don't resolve at link time.

Lifetime
~~~~~~~~

``ImPlot::CreateContext`` runs from ``ui::Context``'s constructor and
``ImPlot::DestroyContext`` from its destructor, so ImPlot calls are
valid wherever ImGui calls are.

``Context::end_frame`` --- rendering tightenings
------------------------------------------------

The original ``ui::Image`` widget would sample as black on Vulkan when
displaying a texture that had been written by a compute pass in the
same frame. Two issues, both fixed in ``end_frame``:

1. Auto state-transition before the render pass
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Before ``begin_render_pass`` the fork walks every draw list in the
frame, collects the unique ``ImTextureID`` values (which are
``sgl::Texture*``), and calls
``command_encoder->set_texture_state(tex, ResourceState::shader_resource)``
on each one.

Why: slang-rhi's per-encoder state tracker doesn't know about the
UAV → SRV transition for a texture that was just written by a compute
pass elsewhere. Without an explicit ``set_texture_state``, the Vulkan
layout barrier is missing and the ImGui sampler reads zeros.

2. Per-command pipeline rebind
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Inside the render loop, the pipeline is bound and the per-draw
uniforms (sampler / scale / offset / ``is_srgb_format``) are written
**before every draw command**, not just once at the top of the pass.

Why: slang-rhi's shader objects commit descriptor sets at
pipeline-bind time. Mid-pass ``set_texture_view`` modifications
don't reach the shader on subsequent draw commands unless the
pipeline is re-bound.

Together these two fixes are what make a compute kernel's output
texture appear correctly when displayed via ``ui.Image`` inside a
dockable ImGui window.

Layered effect
~~~~~~~~~~~~~~

The fix is conservative: it transitions every texture referenced by
ImGui to ``shader_resource`` every frame, and re-binds the pipeline
per draw command. On a typical UI frame this is a handful of textures
and a small number of draw commands, so the overhead is negligible
relative to the compute workload the textures came from. There's no
flag to disable it.

File map
--------

For anyone tracing changes against upstream:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Path
     - What the fork changes
   * - ``src/sgl/ui/widgets.h``
     - New widgets (``Image``, ``Plot``, ``PlotLines``, ``Separator``,
       ``ColorEdit3/4``, ``ColorPicker3/4``, ``DockSpace``), plus
       ``show_title_bar`` and ``dock_id`` on ``Window``.
   * - ``src/sgl/ui/ui.h`` / ``ui.cpp``
     - ``Col`` enum, ``Style`` class, ``add_font`` / ``push_font`` /
       ``pop_font``, ``imgui.ini`` enabled, ImPlot context
       create/destroy, ``end_frame`` rendering tightenings.
   * - ``src/sgl/ui/widgets.cpp``
     - Minor wiring for new widgets.
   * - ``src/slangpy_ext/ui/ui.cpp``
     - Python bindings for ``Col``, ``Style``, font API.
   * - ``src/slangpy_ext/ui/widgets.cpp``
     - Python bindings for new widgets and the ``LegendLocation`` enum.
   * - ``src/sgl/core/window.{h,cpp}``
     - ``WindowDesc.decorated`` flag.
   * - ``src/slangpy_ext/core/window.cpp``
     - ``decorated`` constructor kwarg on ``spy.Window``.
   * - ``src/sgl/app/app.h``
     - ``AppWindow::ui_context()`` accessor.
   * - ``src/slangpy_ext/app/app.cpp``
     - ``AppWindow.ui_context`` Python property.
   * - ``external/CMakeLists.txt``
     - Fetch ImPlot 0.16 + patches + visibility override.
   * - ``src/sgl/CMakeLists.txt``
     - Wire ImPlot sources into ``libsgl``.
