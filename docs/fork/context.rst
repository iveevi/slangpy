.. _sec-fork-context:

UI Context, Fonts and Style
===========================

The fork extends ``ui::Context`` with a font API and a live
``ImGuiStyle`` view, and lifts ``imgui.ini`` persistence on by default.
ImPlot's context is also created and destroyed alongside ImGui's, so
ImPlot calls are valid wherever ImGui calls are.

Fonts
-----

``ui::Context`` exposes three font calls::

    ctx.add_font(name: str, path: str, size: float, is_default: bool = False)
    ctx.push_font(name: str)
    ctx.pop_font()

* ``add_font`` rasterises a TTF from disk at ``size`` pixels and
  registers it under ``name``. If ``is_default=True`` it becomes the
  ImGui default font (used when nothing is pushed).

  .. note::

     Must be called **before the first frame** --- adding fonts mid-frame
     invalidates ImGui's atlas.

* ``push_font(name)`` / ``pop_font()`` map to ``ImGui::PushFont`` /
  ``PopFont`` on a previously registered font.

Convenience: ``ImGui::PushFont(const char* name)`` is also exposed in
the ``ImGui`` namespace for C++ callers.

``AppWindow.ui_context``
~~~~~~~~~~~~~~~~~~~~~~~~

If you're using :class:`spy.AppWindow`, the ``ui::Context`` is owned by
the window and isn't directly constructed by user code. Use the
read-only ``ui_context`` property to reach it::

    app = spy.AppWindow(...)
    app.ui_context.add_font("body",  "fonts/Inter-Regular.ttf", 16)
    app.ui_context.add_font("title", "fonts/Inter-Bold.ttf",    20, is_default=True)

Style
-----

``Context.style`` returns a :class:`ui.Style` --- a thin object holding
the ``ImGuiContext*`` and reading/writing directly into its
``ImGuiStyle``. Mutations take effect on the next frame::

    s = ctx.style
    s.colors_dark()                                  # built-in preset
    s.window_padding   = spy.float2(10.0, 10.0)
    s.window_rounding  = 8.0
    s.frame_rounding   = 4.0
    s.set_color(ui.Col.button,       spy.float4(0.18, 0.34, 0.55, 1.0))
    s.set_color(ui.Col.slider_grab,  accent)

``ctx.style`` itself is read-only --- you mutate fields on the returned
object, not the property.

Presets
~~~~~~~

* ``colors_dark()`` --- ImGui's built-in dark theme.
* ``colors_light()`` --- ImGui's built-in light theme.
* ``colors_classic()`` --- ImGui's built-in classic theme.

The existing ``setup_style()`` (built-in dark + a few tweaks) still
runs at ``Context`` construction; anything you set through ``ctx.style``
overrides it.

Field accessors
~~~~~~~~~~~~~~~

Every scalar / ``ImVec2`` / bool field on ``ImGuiStyle`` is exposed as
a snake_case property. The mapping is mechanical:
``WindowPadding`` → ``window_padding``, ``FrameRounding`` →
``frame_rounding``, ``AntiAliasedLines`` → ``anti_aliased_lines``.

Float fields:
``alpha``, ``disabled_alpha``, ``window_rounding``,
``window_border_size``, ``child_rounding``, ``child_border_size``,
``popup_rounding``, ``popup_border_size``, ``frame_rounding``,
``frame_border_size``, ``indent_spacing``, ``columns_min_spacing``,
``scrollbar_size``, ``scrollbar_rounding``, ``grab_min_size``,
``grab_rounding``, ``log_slider_deadzone``, ``tab_rounding``,
``tab_border_size``, ``tab_bar_border_size``, ``tab_bar_overline_size``,
``separator_text_border_size``, ``docking_separator_size``,
``mouse_cursor_scale``, ``curve_tessellation_tol``,
``circle_tessellation_max_error``.

``float2`` (ImVec2) fields:
``window_padding``, ``window_min_size``, ``window_title_align``,
``frame_padding``, ``item_spacing``, ``item_inner_spacing``,
``cell_padding``, ``touch_extra_padding``, ``separator_text_align``,
``separator_text_padding``, ``button_text_align``,
``selectable_text_align``.

Bool fields:
``anti_aliased_lines``, ``anti_aliased_lines_use_tex``,
``anti_aliased_fill``.

Colors and the ``Col`` enum
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Read and write color slots through the ``ui.Col`` enum, which mirrors
``ImGuiCol_`` one-to-one in snake_case::

    c = s.get_color(ui.Col.window_bg)        # -> float4 RGBA in [0, 1]
    s.set_color(ui.Col.window_bg, spy.float4(0.10, 0.10, 0.12, 1.0))

The enum covers all 62 color slots that ImGui 1.92 (docking branch)
exposes, including the post-1.92 additions
(``tab_selected_overline``, ``tree_lines``, ``unsaved_marker``, ...).
Values are integer-compatible with ``ImGuiCol_``.

``imgui.ini`` persistence
-------------------------

Upstream sets ``io.IniFilename = nullptr``, which disables ImGui's
ini-file persistence. The fork sets it to ``"imgui.ini"``, so dockspace
layouts, window positions and sizes survive across runs. The file is
written in the working directory.

If you've set up an initial layout programmatically (``DockSpace`` +
``request_split_*`` + ``Window.dock_id``), the saved layout takes over
on the second launch --- typically you'll guard the programmatic setup
behind a "first run" check or simply leave it; ImGui prefers the
persisted layout once one exists.

ImPlot context
--------------

``ImPlot::CreateContext`` is called from ``Context``'s constructor and
``ImPlot::DestroyContext`` from its destructor. There's nothing
user-visible to do --- ``ui.Plot`` (and any direct ImPlot calls between
``begin_frame`` and ``end_frame``) will Just Work.
