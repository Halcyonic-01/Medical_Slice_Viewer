"""
control_panel.py
----------------
Qt sidebar widget that exposes:
  - Window / Level sliders
  - Slice index spinboxes (one per axis)
  - Annotation list with add / remove / label-edit controls
  - Save / Load annotation buttons
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.annotation.annotation import Annotation, AnnotationStore, AnnotationType
from src.core.crosshair import Crosshair
from src.core.volume import Volume
from src.core.window_level import WindowLevel

logger = logging.getLogger(__name__)


class ControlPanel(QWidget):
    """
    Sidebar control panel.

    Signals
    -------
    save_requested : str  → path chosen by user
    load_requested : str  → path chosen by user
    """

    save_requested = pyqtSignal(str)
    load_requested = pyqtSignal(str)

    def __init__(
        self,
        wl: WindowLevel,
        crosshair: Crosshair,
        ann_store: AnnotationStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._wl = wl
        self._crosshair = crosshair
        self._ann_store = ann_store
        self._volume: Optional[Volume] = None
        self._updating = False  # prevent recursive signal loops

        self._build_ui()
        wl.subscribe(self._refresh_wl)
        crosshair.subscribe(self._refresh_sliders)
        ann_store.subscribe(self._refresh_ann_list)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self._build_wl_group())
        layout.addWidget(self._build_slice_group())
        layout.addWidget(self._build_annotation_group())
        layout.addStretch()

    def _build_wl_group(self) -> QGroupBox:
        grp = QGroupBox("Window / Level")
        layout = QVBoxLayout(grp)

        self._window_slider = _make_slider(1, 4000, 400)
        self._level_slider = _make_slider(-1000, 3000, 40)

        self._window_label = QLabel("Window: 400")
        self._level_label = QLabel("Level:  40")

        self._window_slider.valueChanged.connect(self._on_window_changed)
        self._level_slider.valueChanged.connect(self._on_level_changed)

        for widget in (
            self._window_label,
            self._window_slider,
            self._level_label,
            self._level_slider,
        ):
            layout.addWidget(widget)

        return grp

    def _build_slice_group(self) -> QGroupBox:
        grp = QGroupBox("Slice Indices")
        layout = QVBoxLayout(grp)

        self._axial_spin = QSpinBox(); self._axial_spin.setPrefix("Axial: ")
        self._coronal_spin = QSpinBox(); self._coronal_spin.setPrefix("Coronal: ")
        self._sagittal_spin = QSpinBox(); self._sagittal_spin.setPrefix("Sagittal: ")

        self._axial_spin.valueChanged.connect(
            lambda v: self._on_slice_changed(0, v)
        )
        self._coronal_spin.valueChanged.connect(
            lambda v: self._on_slice_changed(1, v)
        )
        self._sagittal_spin.valueChanged.connect(
            lambda v: self._on_slice_changed(2, v)
        )

        for spin in (self._axial_spin, self._coronal_spin, self._sagittal_spin):
            layout.addWidget(spin)

        return grp

    def _build_annotation_group(self) -> QGroupBox:
        grp = QGroupBox("Annotations")
        layout = QVBoxLayout(grp)

        # Plane selector for new ROIs
        plane_row = QHBoxLayout()
        plane_row.addWidget(QLabel("Plane:"))
        self._plane_combo = QComboBox()
        self._plane_combo.addItem("Axial", 0)
        self._plane_combo.addItem("Coronal", 1)
        self._plane_combo.addItem("Sagittal", 2)
        plane_row.addWidget(self._plane_combo)
        layout.addLayout(plane_row)

        self._ann_list = QListWidget()
        layout.addWidget(self._ann_list)

        btn_row = QHBoxLayout()
        self._btn_add = QPushButton("＋ Add ROI")
        self._btn_remove = QPushButton("✕ Remove")
        self._btn_add.clicked.connect(self._on_add_ann)
        self._btn_remove.clicked.connect(self._on_remove_ann)
        btn_row.addWidget(self._btn_add)
        btn_row.addWidget(self._btn_remove)
        layout.addLayout(btn_row)

        io_row = QHBoxLayout()
        self._btn_save = QPushButton("Save JSON")
        self._btn_load = QPushButton("Load JSON")
        self._btn_save.clicked.connect(self._on_save)
        self._btn_load.clicked.connect(self._on_load)
        io_row.addWidget(self._btn_save)
        io_row.addWidget(self._btn_load)
        layout.addLayout(io_row)

        return grp

    # ------------------------------------------------------------------
    # Volume binding
    # ------------------------------------------------------------------

    def bind_volume(self, volume: Volume) -> None:
        """Update spinbox ranges when a new volume is loaded."""
        self._volume = volume
        ni, nj, nk = volume.shape
        self._axial_spin.setRange(0, ni - 1)
        self._coronal_spin.setRange(0, nj - 1)
        self._sagittal_spin.setRange(0, nk - 1)

        w, l = volume.default_window, volume.default_level
        lo, hi = volume.data_range
        self._window_slider.setRange(1, int(hi - lo) or 4000)
        self._level_slider.setRange(int(lo), int(hi))
        self._wl.set(w, l)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_window_changed(self, val: int) -> None:
        if self._updating:
            return
        self._window_label.setText(f"Window: {val}")
        self._wl.window = float(val)

    def _on_level_changed(self, val: int) -> None:
        if self._updating:
            return
        self._level_label.setText(f"Level:  {val}")
        self._wl.level = float(val)

    def _on_slice_changed(self, axis: int, val: int) -> None:
        if self._updating:
            return
        i, j, k = self._crosshair.as_int()
        if axis == 0:
            self._crosshair.set(val, j, k)
        elif axis == 1:
            self._crosshair.set(i, val, k)
        else:
            self._crosshair.set(i, j, val)

    def _on_add_ann(self) -> None:
        if self._volume is None:
            logger.warning("Add ROI ignored: no volume loaded.")
            return

        i, j, k = self._crosshair.as_int()
        ni, nj, nk = self._volume.shape
        axis = self._plane_combo.currentData()

        # Compute ROI center in display-space [0, 1] based on the
        # selected plane.  Each view maps two of (i, j, k) to (u, v).
        if axis == 0:       # Axial: u=K, v=J
            u_center = k / max(nk - 1, 1)
            v_center = j / max(nj - 1, 1)
            slice_idx = i
        elif axis == 1:     # Coronal: u=K, v=I
            u_center = k / max(nk - 1, 1)
            v_center = i / max(ni - 1, 1)
            slice_idx = j
        else:               # Sagittal: u=J, v=I
            u_center = j / max(nj - 1, 1)
            v_center = i / max(ni - 1, 1)
            slice_idx = k

        half_size = 0.05
        u0 = max(0.0, u_center - half_size)
        u1 = min(1.0, u_center + half_size)
        v0 = max(0.0, v_center - half_size)
        v1 = min(1.0, v_center + half_size)

        ann = Annotation(
            ann_type=AnnotationType.FREEHAND,
            axis=axis,
            slice_idx=slice_idx,
            points=[(u0, v0), (u1, v0), (u1, v1), (u0, v1)],
            label=f"ROI-{len(self._ann_store.all()) + 1}",
        )
        uid = self._ann_store.add(ann)
        self._select_annotation(uid)

    def _on_remove_ann(self) -> None:
        item = self._ann_list.currentItem()
        if item is not None:
            uid = item.data(Qt.ItemDataRole.UserRole)
            self._ann_store.remove(uid)
            return

        # Fallback: if nothing is selected, remove the most recently added ROI.
        anns = self._ann_store.all()
        if anns:
            self._ann_store.remove(anns[-1].uid)

    def _on_save(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Annotations", "", "JSON Files (*.json)"
        )
        if path:
            self.save_requested.emit(path)

    def _on_load(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Annotations", "", "JSON Files (*.json)"
        )
        if path:
            self.load_requested.emit(path)

    # ------------------------------------------------------------------
    # Observer refresh methods
    # ------------------------------------------------------------------

    def _refresh_wl(self) -> None:
        self._updating = True
        self._window_slider.setValue(int(self._wl.window))
        self._level_slider.setValue(int(self._wl.level))
        self._window_label.setText(f"Window: {int(self._wl.window)}")
        self._level_label.setText(f"Level:  {int(self._wl.level)}")
        self._updating = False

    def _refresh_sliders(self) -> None:
        self._updating = True
        i, j, k = self._crosshair.as_int()
        self._axial_spin.setValue(i)
        self._coronal_spin.setValue(j)
        self._sagittal_spin.setValue(k)
        self._updating = False

    def _refresh_ann_list(self) -> None:
        self._ann_list.clear()
        for ann in self._ann_store.all():
            item = QListWidgetItem(f"[{_AXIS_LABELS[ann.axis]}:{ann.slice_idx}] {ann.label}")
            item.setData(Qt.ItemDataRole.UserRole, ann.uid)
            self._ann_list.addItem(item)

    def _select_annotation(self, uid: str) -> None:
        for idx in range(self._ann_list.count()):
            item = self._ann_list.item(idx)
            if item.data(Qt.ItemDataRole.UserRole) == uid:
                self._ann_list.setCurrentItem(item)
                return


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_AXIS_LABELS = {0: "Axial", 1: "Coronal", 2: "Sagittal"}


def _make_slider(min_val: int, max_val: int, default: int) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(min_val, max_val)
    s.setValue(default)
    return s