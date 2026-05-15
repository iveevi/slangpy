.. _sec-fork-widgets:

Widgets
=======

This page documents the widgets added by the fork. ``Plot`` has enough
surface area that it gets its own page (:ref:`sec-fork-plotting`).

``ui.Image``
------------

Wraps ``ImGui::Image``. Because ``ImTextureID`` is typedef'd to
``sgl::Texture*`` in ``imgui_config.h``, the widget takes a
:class:`sgl.Texture` directly --- no separate texture-id registration
step. This is the path for displaying a compute-written texture inside
a docked ImGui window.

.. code-block:: python

    img = ui.Image(parent, texture=tex, size=spy.float2(640, 360))
    # later, on resize:
    img.size = spy.float2(new_w, new_h)
    img.texture = new_tex

**Constructor**::

    ui.Image(parent, texture=None, size=(0, 0), uv0=(0, 0), uv1=(1, 1))

**Properties**: ``texture``, ``size``, ``uv0``, ``uv1`` (all
read/write). The widget renders only when ``visible``, ``texture`` is
not ``None``, and both components of ``size`` are positive.

See :ref:`sec-fork-internals` for the state-transition / pipeline-rebind
fixes in ``Context::end_frame`` that make sampling a freshly compute-
written texture work on Vulkan.

``ui.Separator``
----------------

::

    ui.Separator(parent, label="")

With an empty ``label`` calls ``ImGui::Separator()``; otherwise
``ImGui::SeparatorText(label)``. The ``label`` property is read/write.

``ui.ColorEdit3`` / ``ColorEdit4``
----------------------------------

Inline color-edit boxes over a ``float3`` / ``float4``
``ValueProperty``::

    color = ui.ColorEdit3(parent, label="tint", value=spy.float3(1, 1, 1))
    color = ui.ColorEdit4(parent, label="bg",   value=spy.float4(0, 0, 0, 1))

Each accepts a ``callback`` invoked on change. The current value is
available as the ``value`` property.

``ui.ColorPicker3`` / ``ColorPicker4``
--------------------------------------

Full inline color-picker blocks (``ImGui::ColorPicker3/4``). Same
``parent, label, value, callback`` signature as the edit variants.

``ui.DockSpace``
----------------

Drives ``ImGui::DockSpaceOverViewport`` --- a dockspace that fills the
main viewport. Two things you'll typically want from it:

1. **Passthru central node.** Set ``passthru_central_node = True`` to
   make the central pane transparent so the surface (or whatever sits
   behind ImGui) shows through where no docked window covers it. This
   is how you get the slangpy-rendered scene on screen with ImGui
   panels floating over it.

2. **Programmatic splits.** Drag-docking on first launch is a bad UX.
   Call ``request_split_horizontal(ratio)`` or
   ``request_split_vertical(ratio)`` once; on the next render the
   dockspace is rebuilt with two child nodes, and their ids appear on
   ``left_dock_id`` / ``right_dock_id``. Assign those to
   ``ui.Window.dock_id`` to place windows.

**Constructor**::

    ui.DockSpace(parent)

**Methods**

* ``request_split_horizontal(ratio: float)`` --- left pane occupies
  ``ratio`` of the viewport width on the next render.
* ``request_split_vertical(ratio: float)`` --- same vertically (left =
  top, right = bottom).
* ``passthru_central_node`` (property, read/write).

**Read-only ids** (populated after first render / after a split is
applied)

* ``dock_id`` --- the root dock node id.
* ``left_dock_id`` --- left or top child after a split.
* ``right_dock_id`` --- right or bottom child after a split.

**Typical first-launch layout**

.. code-block:: python

    dock = ui.DockSpace(screen)
    dock.passthru_central_node = True
    dock.request_split_horizontal(0.25)   # left pane = 25% of width

    left  = ui.Window(screen, "controls",  show_title_bar=False)
    right = ui.Window(screen, "telemetry", show_title_bar=False)

    # After first render, dock_id values are valid:
    left.dock_id  = dock.left_dock_id
    right.dock_id = dock.right_dock_id

After the first run, ``imgui.ini`` persists the layout (see
:ref:`sec-fork-context`), so the second launch reads the saved layout
and the ``request_split_*`` call can be skipped.

``ui.Window`` (changes)
-----------------------

The fork adds two parameters and one property to upstream's ``Window``::

    ui.Window(parent, title="", position=(10, 10), size=(400, 400),
              show_title_bar=True)

* ``show_title_bar`` (constructor + ``set_show_title_bar`` / property).
  When ``False``:

  * ``ImGuiWindowFlags_NoTitleBar`` is set, hiding the floating title
    strip.
  * The dock-node tab strip (the "▼ name ×" chrome shown for docked
    windows) is also suppressed via ``SetNextWindowClass`` plus an
    immediate ``LocalFlags`` OR on the dock node. Without the second
    step there's a one-frame lag on first launch where the tab strip
    flashes; see commit ``7453931b`` for the rationale.

* ``dock_id`` / ``set_dock_id(id)``. Setting this triggers
  ``ImGui::SetNextWindowDockID`` on the next render and then clears the
  pending flag. Pass ``0`` to detach.

``ui.PlotLines``
----------------

Lightweight ``ImGui::PlotLines`` wrapper for sparkline-style plots that
don't need axes, ticks or a legend. Use ``ui.Plot`` (see
:ref:`sec-fork-plotting`) when you need any of those.

::

    ui.PlotLines(parent, label="", values=[], overlay="",
                 scale_min=FLT_MAX, scale_max=FLT_MAX, size=(0, 80))

* ``values`` --- the float buffer drawn.
* ``push_value(v)`` --- rolling buffer: pops front, pushes ``v`` at the
  back. Useful for live telemetry without re-allocating.
* ``overlay`` --- text drawn on top of the plot.
* ``scale_min`` / ``scale_max`` --- pass ``FLT_MAX`` (default) for
  autofit, otherwise fixed range.
