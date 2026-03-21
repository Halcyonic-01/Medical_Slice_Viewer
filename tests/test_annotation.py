"""
test_annotation.py
------------------
Tests for the Annotation data model, AnnotationStore, and JSON I/O.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.annotation.annotation import (
    Annotation,
    AnnotationStore,
    AnnotationType,
)
from src.annotation.annotation_io import load_annotations, save_annotations


# ---------------------------------------------------------------------------
# Annotation model
# ---------------------------------------------------------------------------

class TestAnnotation:
    def test_default_uid_is_unique(self):
        a1 = Annotation()
        a2 = Annotation()
        assert a1.uid != a2.uid

    def test_area_triangle(self):
        ann = Annotation(points=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)])
        assert ann.area_voxels() == pytest.approx(0.5, abs=1e-6)

    def test_area_zero_for_fewer_than_3_points(self):
        ann = Annotation(points=[(0.0, 0.0), (1.0, 0.0)])
        assert ann.area_voxels() == 0.0

    def test_bounding_box(self):
        ann = Annotation(points=[(1.0, 2.0), (5.0, 4.0), (3.0, 0.0)])
        bb = ann.bounding_box()
        assert bb == (1.0, 0.0, 5.0, 4.0)

    def test_bounding_box_none_for_single_point(self):
        ann = Annotation(points=[(1.0, 2.0)])
        assert ann.bounding_box() is None

    def test_round_trip_serialisation(self):
        original = Annotation(
            ann_type=AnnotationType.ELLIPSE,
            axis=1,
            slice_idx=10,
            points=[(0.1, 0.2), (0.3, 0.4)],
            label="TestROI",
            color=(1.0, 0.0, 0.0, 0.8),
        )
        d = original.to_dict()
        restored = Annotation.from_dict(d)

        assert restored.uid == original.uid
        assert restored.ann_type == AnnotationType.ELLIPSE
        assert restored.axis == 1
        assert restored.slice_idx == 10
        assert restored.label == "TestROI"
        assert restored.points == [(0.1, 0.2), (0.3, 0.4)]
        assert restored.color == pytest.approx((1.0, 0.0, 0.0, 0.8))


# ---------------------------------------------------------------------------
# AnnotationStore
# ---------------------------------------------------------------------------

class TestAnnotationStore:
    def _store_with_three(self):
        store = AnnotationStore()
        a1 = Annotation(axis=0, slice_idx=5, label="A")
        a2 = Annotation(axis=0, slice_idx=5, label="B")
        a3 = Annotation(axis=1, slice_idx=3, label="C")
        store.add(a1)
        store.add(a2)
        store.add(a3)
        return store, a1, a2, a3

    def test_add_and_all(self):
        store, a1, a2, a3 = self._store_with_three()
        assert len(store.all()) == 3

    def test_for_slice_filters_correctly(self):
        store, a1, a2, a3 = self._store_with_three()
        result = store.for_slice(axis=0, slice_idx=5)
        uids = {a.uid for a in result}
        assert a1.uid in uids
        assert a2.uid in uids
        assert a3.uid not in uids

    def test_remove(self):
        store, a1, a2, a3 = self._store_with_three()
        store.remove(a1.uid)
        assert len(store.all()) == 2
        assert store.get(a1.uid) is None

    def test_remove_nonexistent_is_safe(self):
        store = AnnotationStore()
        store.remove("does-not-exist")  # should not raise

    def test_clear(self):
        store, *_ = self._store_with_three()
        store.clear()
        assert store.all() == []

    def test_observer_notified_on_add(self):
        store = AnnotationStore()
        calls = []
        store.subscribe(lambda: calls.append(1))
        store.add(Annotation())
        assert len(calls) == 1

    def test_observer_notified_on_remove(self):
        store = AnnotationStore()
        ann = Annotation()
        store.add(ann)
        calls = []
        store.subscribe(lambda: calls.append(1))
        store.remove(ann.uid)
        assert len(calls) == 1

    def test_observer_notified_on_clear(self):
        store = AnnotationStore()
        calls = []
        store.subscribe(lambda: calls.append(1))
        store.clear()
        assert len(calls) == 1

    def test_update(self):
        store = AnnotationStore()
        ann = Annotation(label="original")
        store.add(ann)
        ann.label = "updated"
        store.update(ann)
        assert store.get(ann.uid).label == "updated"


# ---------------------------------------------------------------------------
# JSON persistence
# ---------------------------------------------------------------------------

class TestAnnotationIO:
    def test_save_and_load_roundtrip(self):
        store = AnnotationStore()
        store.add(Annotation(label="ROI-1", points=[(0.1, 0.2)]))
        store.add(Annotation(label="ROI-2", axis=2, slice_idx=7))

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            save_annotations(store, path)

            new_store = AnnotationStore()
            load_annotations(new_store, path)

            labels = {a.label for a in new_store.all()}
            assert "ROI-1" in labels
            assert "ROI-2" in labels
            assert len(new_store.all()) == 2
        finally:
            path.unlink(missing_ok=True)

    def test_saved_file_is_valid_json(self):
        store = AnnotationStore()
        store.add(Annotation(label="X"))

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = Path(f.name)

        save_annotations(store, path)
        with open(path) as fh:
            data = json.load(fh)
        assert "annotations" in data
        path.unlink(missing_ok=True)

    def test_empty_store_round_trip(self):
        store = AnnotationStore()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        save_annotations(store, path)
        load_annotations(store, path)
        assert store.all() == []
        path.unlink(missing_ok=True)