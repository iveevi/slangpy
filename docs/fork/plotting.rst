.. _sec-fork-plotting:

Plotting (``ui.Plot``)
======================

``ui.Plot`` wraps ``ImPlot::BeginPlot`` and exposes three series kinds
that can be mixed in a single widget:

* **Line series** --- ``ImPlot::PlotLine``.
* **Histogram series** --- ``ImPlot::PlotHistogram`` (raw samples, bins
  computed by ImPlot at render time).
* **Bar groups overlay** --- ``ImPlot::PlotBarGroups`` (one bar per
  group, stacked or side-by-side).

The widget supports configurable axes, manual or autofit limits, and
a positionable legend (9 compass anchors, optional outside-the-plot
placement, optional horizontal layout).

Constructor
-----------

::

    ui.Plot(parent,
            label="plot",
            x_label="", y_label="",
            size=(-1, 200),
            autofit_x=True, autofit_y=True,
            legend_location=ui.LegendLocation.north_west,
            legend_outside=False,
            legend_horizontal=False)

Each parameter has a matching read/write property.

Line series
-----------

::

    plot = ui.Plot(parent, "frame time",
                   x_label="frame", y_label="ms",
                   size=spy.float2(0, 280),
                   autofit_y=True)

    plot.add_line("ms", values_list)

``add_line(name, values)`` stores ``values`` by name. Calling it again
with the same name **replaces** the series and resets it to line kind.

Rolling buffer
~~~~~~~~~~~~~~

For live telemetry, use ``push_to_line`` to append samples and cap the
buffer length::

    plot.push_to_line("ms", dt_ms, max_history=600)

``max_history=0`` (the default) means unbounded. Despite the name,
``push_to_line`` works for histogram series too --- it just appends a
sample.

Histogram series
----------------

::

    plot = ui.Plot(parent, "frame time distribution",
                   x_label="ms", y_label="count",
                   autofit_x=True, autofit_y=True)

    plot.add_histogram("blocks", samples)              # bins=-1 (auto)
    plot.add_histogram("blocks", samples, bins=30)     # fixed 30 bins

* ``bins=-1`` (default) --- ImPlot's ``ImPlotBin_Sturges`` heuristic.
* ``bins > 0`` --- literal bin count.
* ``bar_scale`` (default ``1.0``) --- bar-width factor inside a bin.

A second ``add_histogram(name, ...)`` call with the same name replaces
the samples and resets bin / scale params. A subsequent ``add_line(name, ...)``
converts the series back to a line.

Bar groups overlay
------------------

For per-component breakdowns across N groups (e.g. stacked frame-phase
timings across rolling blocks)::

    plot.add_bar_groups(
        labels=["events", "compute", "ui", "present"],
        values_per_label=[
            [4.1, 4.2, 4.0, ...],   # one value per group, per label
            [1.3, 1.4, 1.3, ...],
            [0.8, 0.7, 0.9, ...],
            [2.0, 1.9, 2.1, ...],
        ],
        group_size=0.67,
        stacked=True,
    )

* ``labels`` --- per-segment names (``item_count``); shown in the
  legend.
* ``values_per_label`` --- per-segment, per-group values.
  ``values_per_label[i][g]`` is segment ``i`` for group ``g``. Inner
  lists should all share a length (= group count); shorter ones are
  zero-padded at render.
* ``group_size`` --- ``0..1``; bar width inside a group. ``0.67``
  matches ImPlot's default.
* ``stacked`` --- ``True`` stacks segments into a single column per
  group (sum-of-phases view); ``False`` places them side-by-side.

Storage is separate from line/histogram series, so a single ``Plot``
can mix all three --- e.g. an EMA line overlaid on stacked phase bars.

Use ``clear_bar_groups()`` to remove the overlay without touching
line/histogram series. ``clear()`` removes everything.

Axes & limits
-------------

* ``x_label`` / ``y_label`` --- axis labels.
* ``autofit_x`` / ``autofit_y`` --- when ``True``, the corresponding
  axis fits to data each frame.
* ``set_x_limits(lo, hi)`` / ``set_y_limits(lo, hi)`` --- explicit
  ranges; persists until ``clear_limits()``.

Manual limits override autofit on that axis.

Legend
------

The legend is positioned by a ``ui.LegendLocation`` enum that mirrors
``ImPlotLocation_`` bitwise:

.. code-block:: python

    ui.LegendLocation.center
    ui.LegendLocation.north
    ui.LegendLocation.south
    ui.LegendLocation.east
    ui.LegendLocation.west
    ui.LegendLocation.north_west   # default
    ui.LegendLocation.north_east
    ui.LegendLocation.south_west
    ui.LegendLocation.south_east

Two flags modify behaviour:

* ``legend_outside`` --- pushes the legend outside the plot frame
  (``ImPlotLegendFlags_Outside``).
* ``legend_horizontal`` --- spreads entries left-to-right and wraps to
  additional rows when the legend region runs out of width
  (``ImPlotLegendFlags_Horizontal``).

A common combination for a multi-row legend underneath the plot::

    ui.Plot(parent, ...,
            legend_location=ui.LegendLocation.south,
            legend_outside=True,
            legend_horizontal=True)

ImPlot doesn't expose a fixed column count for legends; wrapping is
driven purely by available width.
