# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

import slangpy as spy


def test_imagebutton_defaults() -> None:
    btn = spy.ui.ImageButton(None)
    assert btn.texture is None
    assert btn.callback is None
    assert isinstance(btn, spy.ui.Widget)


def test_imagebutton_properties() -> None:
    btn = spy.ui.ImageButton(None, size=spy.float2(24, 24))
    assert btn.size == spy.float2(24, 24)
    btn.size = spy.float2(48, 32)
    assert btn.size == spy.float2(48, 32)
    btn.uv0 = spy.float2(0.1, 0.2)
    btn.uv1 = spy.float2(0.9, 0.8)
    assert btn.uv0 == spy.float2(0.1, 0.2)
    assert btn.uv1 == spy.float2(0.9, 0.8)


def test_imagebutton_callback_assignable() -> None:
    calls = []

    def cb() -> None:
        calls.append(1)

    btn = spy.ui.ImageButton(None, callback=cb)
    assert btn.callback is cb
    btn.callback()
    assert calls == [1]


def test_imagebutton_texture_round_trip() -> None:
    import numpy as np

    dev = spy.Device(enable_debug_layers=False)
    img = np.zeros((8, 8, 4), dtype=np.uint8)
    img[2:6, 2:6] = (255, 0, 0, 255)
    tex = dev.create_texture(
        format=spy.Format.rgba8_unorm,
        width=8,
        height=8,
        usage=spy.TextureUsage.shader_resource,
        data=img,
    )
    btn = spy.ui.ImageButton(None, texture=tex)
    assert btn.texture.width == 8
    assert btn.texture.height == 8


def test_imagebutton_parent_child() -> None:
    parent = spy.ui.Group(None, "g")
    btn = spy.ui.ImageButton(parent)
    assert len(parent) == 1
    assert parent[0] is btn
    assert btn.parent is parent
