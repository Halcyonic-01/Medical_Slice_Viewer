"""
annotation_io.py
----------------
JSON persistence for AnnotationStore.
"""

from __future__ import annotations

import json
from pathlib import Path

from .annotation import AnnotationStore


def save_annotations(store: AnnotationStore, path: str | Path) -> None:
    """Write all annotations to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(store.to_dict(), fh, indent=2)


def load_annotations(store: AnnotationStore, path: str | Path) -> None:
    """Overwrite *store* with annotations read from a JSON file."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    store.load_dict(data)