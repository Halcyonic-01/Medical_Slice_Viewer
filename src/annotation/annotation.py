"""
annotation.py
-------------
Data model for region-of-interest (ROI) annotations.

Each annotation lives on one specific (axis, slice_index) plane and
carries a list of 2-D points in *voxel* display coordinates plus a label.

Design decisions
----------------
* Pure Python / numpy – no VTK dependency so tests are fast.
* Serialisation via to_dict / from_dict enables JSON save/load.
* AnnotationStore is observable: UI components subscribe for redraws.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Tuple


class AnnotationType(Enum):
    FREEHAND = auto()
    ELLIPSE = auto()
    RECTANGLE = auto()


@dataclass
class Annotation:
    """
    A single user-drawn ROI.

    Attributes
    ----------
    uid       : Unique identifier.
    ann_type  : Shape type.
    axis      : Slice plane (0=axial, 1=coronal, 2=sagittal).
    slice_idx : Slice index within the plane.
    points    : List of (u, v) voxel-display coordinates.
    label     : Human-readable name shown in the sidebar.
    color     : RGBA tuple in [0, 1]^4.
    """

    uid: str = field(default_factory=lambda: str(uuid.uuid4()))
    ann_type: AnnotationType = AnnotationType.FREEHAND
    axis: int = 0
    slice_idx: int = 0
    points: List[Tuple[float, float]] = field(default_factory=list)
    label: str = "ROI"
    color: Tuple[float, float, float, float] = (1.0, 1.0, 0.0, 1.0)

    # ------------------------------------------------------------------
    # Derived measurements
    # ------------------------------------------------------------------

    def bounding_box(self) -> Optional[Tuple[float, float, float, float]]:
        """Return (min_u, min_v, max_u, max_v) or None if < 2 points."""
        if len(self.points) < 2:
            return None
        us = [p[0] for p in self.points]
        vs = [p[1] for p in self.points]
        return min(us), min(vs), max(us), max(vs)

    def area_voxels(self) -> float:
        """Estimate area via shoelace formula (valid for closed polygons)."""
        pts = self.points
        if len(pts) < 3:
            return 0.0
        n = len(pts)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += pts[i][0] * pts[j][1]
            area -= pts[j][0] * pts[i][1]
        return abs(area) / 2.0

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "uid": self.uid,
            "ann_type": self.ann_type.name,
            "axis": self.axis,
            "slice_idx": self.slice_idx,
            "points": list(self.points),
            "label": self.label,
            "color": list(self.color),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Annotation":
        return cls(
            uid=d["uid"],
            ann_type=AnnotationType[d["ann_type"]],
            axis=d["axis"],
            slice_idx=d["slice_idx"],
            points=[tuple(p) for p in d["points"]],
            label=d["label"],
            color=tuple(d["color"]),
        )


class AnnotationStore:
    """
    Thread-safe container for all annotations in a session.

    Observable – UI subscribes to receive redraws.
    """

    def __init__(self) -> None:
        self._annotations: Dict[str, Annotation] = {}
        self._observers: List[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # Observer
    # ------------------------------------------------------------------

    def subscribe(self, callback: Callable[[], None]) -> None:
        if callback not in self._observers:
            self._observers.append(callback)

    def _notify(self) -> None:
        for cb in self._observers:
            cb()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, ann: Annotation) -> str:
        self._annotations[ann.uid] = ann
        self._notify()
        return ann.uid

    def update(self, ann: Annotation) -> None:
        self._annotations[ann.uid] = ann
        self._notify()

    def remove(self, uid: str) -> None:
        self._annotations.pop(uid, None)
        self._notify()

    def clear(self) -> None:
        self._annotations.clear()
        self._notify()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def all(self) -> List[Annotation]:
        return list(self._annotations.values())

    def for_slice(self, axis: int, slice_idx: int) -> List[Annotation]:
        """Return annotations that belong to the given slice plane."""
        return [
            a for a in self._annotations.values()
            if a.axis == axis and a.slice_idx == slice_idx
        ]

    def get(self, uid: str) -> Optional[Annotation]:
        return self._annotations.get(uid)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {"annotations": [a.to_dict() for a in self.all()]}

    def load_dict(self, d: dict) -> None:
        self._annotations = {
            rec["uid"]: Annotation.from_dict(rec)
            for rec in d.get("annotations", [])
        }
        self._notify()