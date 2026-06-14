# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

import slangpy as spy


def test_button_active_default() -> None:
    btn = spy.ui.Button(None, "b")
    assert btn.active is False


def test_button_active_ctor() -> None:
    btn = spy.ui.Button(None, "b", active=True)
    assert btn.active is True


def test_button_active_round_trip() -> None:
    btn = spy.ui.Button(None, "b")
    btn.active = True
    assert btn.active is True
    btn.active = False
    assert btn.active is False


def test_button_active_keeps_callback() -> None:
    calls = []
    btn = spy.ui.Button(None, "b", callback=lambda: calls.append(1), active=True)
    assert btn.active is True
    btn.callback()
    assert calls == [1]
