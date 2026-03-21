"""
window_level.py
---------------
Mutable window/level (brightness/contrast) state.

Window  = intensity range rendered to [0, 255].
Level   = centre of that window.

Follows the DICOM definition:
  output = clamp((value - (level - window/2)) / window * 255, 0, 255)
"""

from __future__ import annotations

from typing import Callable, List


class WindowLevel:
    """
    Observable W/L state.  Observers are notified on every change.

    Parameters
    ----------
    window : float  Intensity range.
    level  : float  Centre intensity value.
    """

    def __init__(self, window: float = 400.0, level: float = 40.0) -> None:
        self._window = max(window, 1.0)
        self._level = level
        self._observers: List[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # Observer pattern
    # ------------------------------------------------------------------

    def subscribe(self, callback: Callable[[], None]) -> None:
        """Register *callback* to be called after every change."""
        if callback not in self._observers:
            self._observers.append(callback)

    def _notify(self) -> None:
        for cb in self._observers:
            cb()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def window(self) -> float:
        return self._window

    @window.setter
    def window(self, value: float) -> None:
        self._window = max(float(value), 1.0)
        self._notify()

    @property
    def level(self) -> float:
        return self._level

    @level.setter
    def level(self, value: float) -> None:
        self._level = float(value)
        self._notify()

    def set(self, window: float, level: float) -> None:
        """Update both values atomically (single notification)."""
        self._window = max(float(window), 1.0)
        self._level = float(level)
        self._notify()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def lower(self) -> float:
        """Lower bound of the display window."""
        return self._level - self._window / 2.0

    @property
    def upper(self) -> float:
        """Upper bound of the display window."""
        return self._level + self._window / 2.0

    def apply(self, intensity: float) -> int:
        """Map a scalar intensity to a display value in [0, 255]."""
        normalised = (intensity - self.lower) / self._window
        return int(max(0.0, min(1.0, normalised)) * 255)