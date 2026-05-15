.. _sec-fork-window:

Window Decoration
=================

There are two independent "title bar" notions in slangpy: the host OS
window (a GLFW window) and an ImGui window inside the dockspace. The
fork adds a flag to each so chrome-less layouts are possible.

OS window: ``sgl.Window(decorated=...)``
----------------------------------------

``WindowDesc`` gains a ``decorated`` field (default ``True``). When
``False``, the GLFW window is created with
``GLFW_DECORATED=GLFW_FALSE`` --- the OS / WM draws no title bar, no
borders, and no min/max/close buttons.

Wired through to the Python binding::

    win = spy.Window(width=1920, height=1080, title="app",
                     mode=spy.WindowMode.normal,
                     resizable=True,
                     decorated=False)

Use cases:

* Custom title bar drawn by ImGui.
* Borderless full-app surface where the slangpy compute output is
  meant to fill the screen with no visible chrome.

This is **distinct** from ``ui::Window::show_title_bar``, which only
controls the ImGui-side chrome.

ImGui window: ``ui.Window(show_title_bar=...)``
-----------------------------------------------

``ui.Window`` accepts a ``show_title_bar`` constructor argument
(default ``True``) and a matching read/write property. When ``False``:

1. ``ImGuiWindowFlags_NoTitleBar`` is set on ``Begin()`` --- removes
   the floating window's title strip.
2. The dock-node tab strip is also suppressed. This is the
   second-order fix that matters: ``NoTitleBar`` is a no-op for a
   docked window, because ImGui implicitly hides the floating title
   bar and instead draws a dock-node tab strip ("▼ name ×"). Without
   the dock-side fix below, ``show_title_bar=False`` would have no
   visible effect on docked windows.

The fork's two-pronged fix:

* Before ``Begin()``: ``SetNextWindowClass`` with
  ``DockNodeFlagsOverrideSet = NoTabBar | NoDockingOverMe``. This
  propagates into the node's per-frame ``MergedFlags`` via
  ``LocalFlagsInWindows``.

* After ``Begin()``: if the window is docked, OR
  ``NoTabBar | NoDockingSplit | NoCloseButton`` directly into the
  dock node's persistent ``LocalFlags``. This is what
  ``DockBuilder`` does internally, sticks across frames, and survives
  in ``imgui.ini``. Without it the override path has a one-frame lag
  and the first frame after a fresh layout still shows the tab strip.

Layout persistence
------------------

The constructor-provided ``position`` and ``size`` are applied with
``ImGuiCond_FirstUseEver`` — they only take effect the first time a
window with this title is ever rendered. On subsequent launches the
position / size persisted in ``imgui.ini`` win. Calling
``set_position()`` / ``set_size()`` explicitly from Python forces an
override regardless of any saved state.

This is what makes window-layout persistence actually work: drag a
window once, close the demo, relaunch — the window re-appears where
you left it.

``ui.Window.dock_id``
---------------------

For programmatic first-launch docking, ``ui.Window`` has a
``dock_id`` property and ``set_dock_id(id)`` method. Setting either
triggers ``ImGui::SetNextWindowDockID(id)`` on the next render and
then clears the pending flag (so a subsequent render doesn't re-dock).

Pass ``0`` to detach (let the user dock manually).

The intended pairing is with :class:`ui.DockSpace`::

    dock = ui.DockSpace(screen)
    dock.request_split_horizontal(0.25)

    left  = ui.Window(screen, "controls",  show_title_bar=False)
    right = ui.Window(screen, "scene",     show_title_bar=False)

    # After the dockspace renders once, the split ids are populated:
    left.dock_id  = dock.left_dock_id
    right.dock_id = dock.right_dock_id

After ``imgui.ini`` has been written once, the saved layout takes over
on subsequent launches.
