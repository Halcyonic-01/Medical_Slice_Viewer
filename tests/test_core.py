"""
test_core.py
------------
Unit tests for WindowLevel and Crosshair.
"""

import pytest

from src.core.crosshair import Crosshair
from src.core.window_level import WindowLevel


class TestWindowLevel:
    def test_defaults(self):
        wl = WindowLevel(window=400, level=40)
        assert wl.window == 400.0
        assert wl.level == 40.0

    def test_lower_upper(self):
        wl = WindowLevel(window=200, level=100)
        assert wl.lower == 0.0
        assert wl.upper == 200.0

    def test_minimum_window_clamped(self):
        wl = WindowLevel(window=-5, level=0)
        assert wl.window >= 1.0

    def test_observer_notified_on_window_change(self):
        wl = WindowLevel()
        calls = []
        wl.subscribe(lambda: calls.append(1))
        wl.window = 300.0
        assert len(calls) == 1

    def test_observer_notified_on_level_change(self):
        wl = WindowLevel()
        calls = []
        wl.subscribe(lambda: calls.append(1))
        wl.level = 50.0
        assert len(calls) == 1

    def test_set_single_notification(self):
        """set() must fire only ONE notification even though two values change."""
        wl = WindowLevel()
        calls = []
        wl.subscribe(lambda: calls.append(1))
        wl.set(500, 200)
        assert len(calls) == 1

    def test_apply_maps_within_window(self):
        wl = WindowLevel(window=200, level=100)
        # At level-window/2 == 0 → should map to 0
        assert wl.apply(0.0) == 0
        # At level+window/2 == 200 → should map to 255
        assert wl.apply(200.0) == 255

    def test_apply_clamps_below(self):
        wl = WindowLevel(window=100, level=50)
        assert wl.apply(-9999) == 0

    def test_apply_clamps_above(self):
        wl = WindowLevel(window=100, level=50)
        assert wl.apply(9999) == 255

    def test_duplicate_subscriber_not_added(self):
        wl = WindowLevel()
        calls = []
        cb = lambda: calls.append(1)
        wl.subscribe(cb)
        wl.subscribe(cb)  # duplicate
        wl.window = 300
        assert len(calls) == 1


class TestCrosshair:
    def test_initial_position(self):
        ch = Crosshair(1.0, 2.0, 3.0)
        assert ch.ijk == (1.0, 2.0, 3.0)

    def test_set_updates_all(self):
        ch = Crosshair()
        ch.set(10.0, 20.0, 30.0)
        assert ch.ijk == (10.0, 20.0, 30.0)

    def test_set_axis(self):
        ch = Crosshair(1.0, 2.0, 3.0)
        ch.set_axis(1, 99.0)
        assert ch.ijk == (1.0, 99.0, 3.0)

    def test_as_int_rounds(self):
        ch = Crosshair(1.6, 2.4, 3.5)
        i, j, k = ch.as_int()
        assert i == 2
        assert j == 2
        assert k == 4

    def test_observer_called_on_set(self):
        ch = Crosshair()
        calls = []
        ch.subscribe(lambda: calls.append(1))
        ch.set(5, 6, 7)
        assert len(calls) == 1

    def test_observer_called_on_set_axis(self):
        ch = Crosshair()
        calls = []
        ch.subscribe(lambda: calls.append(1))
        ch.set_axis(2, 15.0)
        assert len(calls) == 1