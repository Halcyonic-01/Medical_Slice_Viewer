"""
crosshair.py
------------
Shared cursor state expressed in voxel indices.

When the user clicks any viewport the cursor position is updated here.
All three SliceView widgets observe this object and redraw their
crosshair overlay when it changes.
"""

from __future__ import annotations

from typing import Callable, List, Tuple


class Crosshair:
    """
    Observable voxel-index cursor: (i, j, k).

    All three components are stored as floats to support sub-voxel
    precision during interactive dragging; slice indices are rounded
    by consumers.
    """

    def __init__(self, i: float = 0.0, j: float = 0.0, k: float = 0.0) -> None:
        self._ijk: List[float] = [i, j, k]
        self._observers: List[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # Observer pattern
    # ------------------------------------------------------------------

    def subscribe(self, callback: Callable[[], None]) -> None:
        if callback not in self._observers:
            self._observers.append(callback)

    def _notify(self) -> None:
        for cb in self._observers:
            cb()

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def ijk(self) -> Tuple[float, float, float]:
        return tuple(self._ijk)  # type: ignore[return-value]

    def set(self, i: float, j: float, k: float) -> None:
        self._ijk = [float(i), float(j), float(k)]
        self._notify()

    def set_axis(self, axis: int, value: float) -> None:
        """Update a single component without changing the others."""
        self._ijk[axis] = float(value)
        self._notify()

    def as_int(self) -> Tuple[int, int, int]:
        """Round to nearest integer indices (safe for array indexing)."""
        return tuple(int(round(v)) for v in self._ijk)  # type: ignore[return-value]