"""src.annotation – ROI annotation data model and persistence."""

from .annotation import Annotation, AnnotationStore, AnnotationType
from .annotation_io import load_annotations, save_annotations

__all__ = [
    "Annotation",
    "AnnotationStore",
    "AnnotationType",
    "load_annotations",
    "save_annotations",
]