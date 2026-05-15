.. _sec-fork:

Fork Extensions (``iveevi/slangpy``)
====================================

This section documents what's added in this fork on top of upstream
`shader-slang/slangpy <https://github.com/shader-slang/slangpy>`_. All
changes are confined to ``src/sgl/ui/``, ``src/slangpy_ext/ui/``,
``src/sgl/core/window.{h,cpp}`` (one flag), ``src/sgl/app/app.h``
(one accessor) and ``external/CMakeLists.txt`` (ImPlot fetch + patch).
Everything outside those paths matches upstream.

The motivation is making ``spy.ui`` capable enough to build a real
application around a slangpy compute pipeline: a borderless OS window,
a programmatic dock layout, the rendered surface visible through the
central node, the compute output displayed as an ``Image`` widget in a
docked panel, real ImPlot-backed plots for telemetry, a font API, and a
live ``ImGuiStyle`` view for theming.

.. toctree::
   :maxdepth: 1

   widgets
   plotting
   context
   window
   internals

Quick summary
-------------

**New widgets** (``spy.ui``)

* :class:`ui.Image` --- ``ImGui::Image`` taking a ``sgl.Texture`` directly.
* :class:`ui.Plot` --- ImPlot-backed widget mixing line, histogram and
  bar-group series with configurable axes and legend.
* :class:`ui.PlotLines` --- sparkline-style ``ImGui::PlotLines`` wrapper.
* :class:`ui.Separator` --- ``ImGui::Separator()`` / ``SeparatorText``.
* :class:`ui.ColorEdit3` / ``ColorEdit4`` / ``ColorPicker3`` /
  ``ColorPicker4``.
* :class:`ui.DockSpace` --- ``DockSpaceOverViewport`` with programmatic
  horizontal/vertical splits and a passthru central node.

**Window changes**

* ``sgl.Window(decorated=False)`` --- borderless GLFW window (no OS
  chrome).
* ``ui.Window(show_title_bar=False)`` --- no ImGui title strip; also
  suppresses the dock-node tab strip when docked.
* ``ui.Window.dock_id`` --- programmatic ``SetNextWindowDockID`` for
  first-launch layouts.

**Context API**

* ``ctx.add_font(name, path, size, is_default=False)`` /
  ``ctx.push_font(name)`` / ``ctx.pop_font()``.
* ``ctx.style`` --- live :class:`ui.Style` view over the active
  ``ImGuiStyle`` plus a ``ui.Col`` enum mirroring ``ImGuiCol_``.
* ImPlot context lifetime tied to ImGui's.
* ``imgui.ini`` is written by default (dock layout persists across runs).
* ``AppWindow.ui_context`` --- access the ``ui::Context`` that
  ``AppWindow`` owns.

**Build / internals**

* ImPlot 0.16 fetched alongside ImGui and patched for ImGui 1.92 API
  drift.
* ``ui::Context::end_frame`` auto-transitions every draw-list texture to
  ``shader_resource`` and rebinds the pipeline + uniforms per draw
  command so ``ui.Image`` correctly displays compute-written textures on
  Vulkan.
