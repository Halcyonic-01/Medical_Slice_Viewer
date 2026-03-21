"""
main_window.py
--------------
Top-level Qt window.

Layout
------
  ┌───────────────────────────────────────┬────────────┐
  │  Axial      │  Coronal   │  Sagittal  │  Controls  │
  │  SliceView  │  SliceView │  SliceView │  Panel     │
  └───────────────────────────────────────┴────────────┘

The three slice views share a Crosshair, WindowLevel, and AnnotationStore.
The ControlPanel observes the same objects for its sliders / list widgets.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QAction

from src.annotation.annotation import AnnotationStore
from src.annotation.annotation_io import load_annotations, save_annotations
from src.core.crosshair import Crosshair
from src.core.volume import Volume
from src.core.window_level import WindowLevel
from src.io import load_volume
from src.ui.control_panel import ControlPanel
from src.ui.slice_view import SliceView

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Application shell."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Medical Slice Viewer")
        self.resize(1200, 700)

        # Shared state
        self._crosshair = Crosshair()
        self._wl = WindowLevel(window=400, level=40)
        self._ann_store = AnnotationStore()

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_status_bar()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # Three slice views
        self._views = [
            SliceView(axis=0, crosshair=self._crosshair, wl=self._wl,
                      ann_store=self._ann_store),  # Axial
            SliceView(axis=1, crosshair=self._crosshair, wl=self._wl,
                      ann_store=self._ann_store),  # Coronal
            SliceView(axis=2, crosshair=self._crosshair, wl=self._wl,
                      ann_store=self._ann_store),  # Sagittal
        ]

        # Connect crosshair_moved from each view
        for view in self._views:
            view.crosshair_moved.connect(self._on_crosshair_moved)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        for view in self._views:
            splitter.addWidget(view)
            splitter.setStretchFactor(splitter.count() - 1, 1)

        # Control panel
        self._panel = ControlPanel(
            wl=self._wl,
            crosshair=self._crosshair,
            ann_store=self._ann_store,
        )
        self._panel.save_requested.connect(self._save_annotations)
        self._panel.load_requested.connect(self._load_annotations)
        self._panel.setFixedWidth(240)

        root.addWidget(splitter, stretch=3)
        root.addWidget(self._panel, stretch=0)

    def _build_menu(self) -> None:
        bar = self.menuBar()

        file_menu = bar.addMenu("&File")
        open_act = QAction("&Open Volume…", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._open_volume_dialog)
        file_menu.addAction(open_act)

        file_menu.addSeparator()
        quit_act = QAction("&Quit", self)
        quit_act.setShortcut("Ctrl+Q")
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        ann_menu = bar.addMenu("&Annotations")
        save_act = QAction("&Save…", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self._save_annotations_dialog)
        ann_menu.addAction(save_act)

        load_act = QAction("&Load…", self)
        load_act.setShortcut("Ctrl+L")
        load_act.triggered.connect(self._load_annotations_dialog)
        ann_menu.addAction(load_act)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        open_act = QAction("Open Volume", self)
        open_act.triggered.connect(self._open_volume_dialog)
        tb.addAction(open_act)

    def _build_status_bar(self) -> None:
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("No volume loaded.  File → Open Volume…")

    # ------------------------------------------------------------------
    # Volume loading
    # ------------------------------------------------------------------

    def _open_volume_dialog(self) -> None:
        chooser = QMessageBox(self)
        chooser.setWindowTitle("Open Volume")
        chooser.setText("What would you like to open?")
        chooser.setInformativeText(
            "Choose a NIfTI file or a DICOM folder."
        )
        file_btn = chooser.addButton(
            "NIfTI File", QMessageBox.ButtonRole.AcceptRole
        )
        dir_btn = chooser.addButton(
            "DICOM Folder", QMessageBox.ButtonRole.AcceptRole
        )
        chooser.addButton(QMessageBox.StandardButton.Cancel)
        chooser.exec()

        clicked = chooser.clickedButton()
        if clicked == file_btn:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open NIfTI Volume",
                "",
                "NIfTI (*.nii *.nii.gz);;All files (*)",
            )
            if path:
                self._load_volume(path)
            return

        if clicked == dir_btn:
            path = QFileDialog.getExistingDirectory(
                self, "Open DICOM Directory"
            )
            if path:
                self._load_volume(path)

    def _load_volume(self, path: str) -> None:
        self._status.showMessage(f"Loading {path} …")
        try:
            volume = load_volume(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))
            logger.exception("Failed to load volume: %s", path)
            self._status.showMessage("Load failed.")
            return

        self._panel.bind_volume(volume)
        for view in self._views:
            view.set_volume(volume)

        ci, cj, ck = volume.center_indices()
        self._crosshair.set(ci, cj, ck)

        self._status.showMessage(
            f"Loaded: {Path(path).name}  |  "
            f"Shape: {volume.shape}  |  "
            f"Spacing: {tuple(f'{s:.2f}' for s in volume.spacing)} mm"
        )
        logger.info("Volume loaded: %s", path)

    # ------------------------------------------------------------------
    # Annotation persistence
    # ------------------------------------------------------------------

    def _save_annotations_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Annotations", "", "JSON (*.json)"
        )
        if path:
            self._save_annotations(path)

    def _load_annotations_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Annotations", "", "JSON (*.json)"
        )
        if path:
            self._load_annotations(path)

    def _save_annotations(self, path: str) -> None:
        try:
            save_annotations(self._ann_store, path)
            self._status.showMessage(f"Annotations saved to {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def _load_annotations(self, path: str) -> None:
        try:
            load_annotations(self._ann_store, path)
            self._status.showMessage(f"Annotations loaded from {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))

    # ------------------------------------------------------------------
    # Crosshair
    # ------------------------------------------------------------------

    def _on_crosshair_moved(self, i: int, j: int, k: int) -> None:
        self._status.showMessage(f"Voxel  i={i}  j={j}  k={k}")