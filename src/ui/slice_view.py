"""
slice_view.py
-------------
A single VTK-powered 2-D slice viewport.

Responsibilities
----------------
* Owns a vtkRenderWindow embedded in a Qt widget (QVTKRenderWindowInteractor).
* Renders one orthogonal slice plane (axial / coronal / sagittal).
* Draws annotation overlays as 2-D vtkPolyData actors.
* Updates when Crosshair or WindowLevel observables change.
* Emits crosshair_moved signal when the user clicks/drags.

VTK Pipeline (per view)
-----------------------
  vtkImageData  ←─── Volume.data (set once)
        │
  vtkImageReslice        (extract oblique / orthogonal slice)
        │
  vtkImageMapToColors    (apply window/level LUT)
        │
  vtkImageActor          (2-D textured quad in the renderer)
        │
  vtkRenderer  (background + image + annotation actors)
        │
  vtkRenderWindow  (embedded in QVTKRenderWindowInteractor)
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np
import vtk
from vtkmodules.util.numpy_support import numpy_to_vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QVBoxLayout

from src.core.crosshair import Crosshair
from src.core.volume import Volume
from src.core.window_level import WindowLevel
from src.annotation.annotation import Annotation, AnnotationStore

logger = logging.getLogger(__name__)

# Maps axis index → human-readable label
_AXIS_LABELS = {0: "Axial", 1: "Coronal", 2: "Sagittal"}


class SliceView(QFrame):
    """
    Qt widget that renders one orthogonal slice using VTK.

    Parameters
    ----------
    axis : int
        0 = Axial (XY), 1 = Coronal (XZ), 2 = Sagittal (YZ).
    crosshair : Crosshair
        Shared cursor state (observed + emitted).
    wl : WindowLevel
        Shared window/level state (observed).
    ann_store : AnnotationStore
        Shared annotation container (observed).
    """

    crosshair_moved = pyqtSignal(int, int, int)   # (i, j, k) voxel indices

    def __init__(
        self,
        axis: int,
        crosshair: Crosshair,
        wl: WindowLevel,
        ann_store: AnnotationStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.axis = axis
        self._crosshair = crosshair
        self._wl = wl
        self._ann_store = ann_store
        self._volume: Optional[Volume] = None
        self._drawing = False
        self._current_ann: Optional[Annotation] = None
        self._ann_actors: List[vtk.vtkActor2D] = []

        self._build_vtk()
        self._build_layout()

        crosshair.subscribe(self._on_crosshair_changed)
        wl.subscribe(self._on_wl_changed)
        ann_store.subscribe(self._on_annotations_changed)

    # ------------------------------------------------------------------
    # VTK pipeline construction
    # ------------------------------------------------------------------

    def _build_vtk(self) -> None:
        """Construct the VTK rendering pipeline.

        The image pipeline (reslice → color-map → actor) is prepared but
        the actor is NOT added to the renderer until a volume is loaded
        via ``set_volume``.  This avoids SIGABRT crashes that occur when
        VTK tries to render an empty ``vtkImageData`` during paintEvent.
        """
        self._vtk_widget = QVTKRenderWindowInteractor(self)

        # Renderer
        self._renderer = vtk.vtkRenderer()
        self._renderer.SetBackground(0.05, 0.05, 0.05)

        self._vtk_widget.GetRenderWindow().AddRenderer(self._renderer)

        # --- Image pipeline (deferred – actor added in set_volume) ---
        self._vtk_image = vtk.vtkImageData()

        self._reslice = vtk.vtkImageReslice()
        # NOTE: input data is connected in set_volume(), not here.
        self._reslice.SetOutputDimensionality(2)
        self._reslice.SetInterpolationModeToLinear()
        self._reslice.SetResliceAxes(self._make_reslice_matrix())

        self._lut = vtk.vtkLookupTable()
        self._lut.SetRange(0, 255)
        self._lut.SetValueRange(0, 1)
        self._lut.SetSaturationRange(0, 0)
        self._lut.SetRampToLinear()
        self._lut.Build()

        self._color_map = vtk.vtkImageMapToColors()
        self._color_map.SetInputConnection(self._reslice.GetOutputPort())
        self._color_map.SetLookupTable(self._lut)
        self._color_map.SetOutputFormatToRGB()

        self._image_actor = vtk.vtkImageActor()
        self._image_actor.GetMapper().SetInputConnection(
            self._color_map.GetOutputPort()
        )
        # Do NOT add image_actor to the renderer here; it will be added
        # once real data is available in set_volume().

        # --- Crosshair overlay (hidden until a volume is loaded) ---
        self._ch_h_actor = self._make_line_actor(color=(0.0, 1.0, 0.0))
        self._ch_v_actor = self._make_line_actor(color=(0.0, 1.0, 0.0))
        self._ch_h_actor.SetVisibility(False)
        self._ch_v_actor.SetVisibility(False)
        self._renderer.AddActor(self._ch_h_actor)
        self._renderer.AddActor(self._ch_v_actor)

        # Interactor style: image (pan/zoom; clicks & scroll handled by us)
        style = vtk.vtkInteractorStyleImage()
        self._vtk_widget.SetInteractorStyle(style)
        self._vtk_widget.AddObserver("LeftButtonPressEvent", self._on_click)
        self._vtk_widget.AddObserver("MouseMoveEvent", self._on_mouse_move)
        self._vtk_widget.AddObserver("LeftButtonReleaseEvent", self._on_release)
        self._vtk_widget.AddObserver("MouseWheelForwardEvent", self._on_scroll_fwd)
        self._vtk_widget.AddObserver("MouseWheelBackwardEvent", self._on_scroll_bwd)

        self._vtk_widget.Initialize()

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._vtk_widget)

    # ------------------------------------------------------------------
    # Volume loading
    # ------------------------------------------------------------------

    def set_volume(self, volume: Volume) -> None:
        """Load a new volume into the pipeline and reset the camera."""
        self._volume = volume
        data = volume.data
        sp = volume.spacing

        # Populate vtkImageData
        vtk_img = self._vtk_image
        ni, nj, nk = data.shape
        vtk_img.SetDimensions(nk, nj, ni)
        vtk_img.SetSpacing(sp[2], sp[1], sp[0])

        flat = data.flatten(order="C").astype(np.float32)
        arr = numpy_to_vtk(flat, deep=True)
        arr.SetName("Intensity")
        vtk_img.GetPointData().SetScalars(arr)

        # Now that we have real data, connect the reslice input and
        # add the image actor to the renderer.
        self._reslice.SetInputData(vtk_img)

        self._renderer.AddActor(self._image_actor)
        self._ch_h_actor.SetVisibility(True)
        self._ch_v_actor.SetVisibility(True)

        # Update reslice position to centre
        ci, cj, ck = volume.center_indices()
        self._update_reslice_position(ci, cj, ck)

        self._apply_wl()
        self._renderer.ResetCamera()
        self._vtk_widget.GetRenderWindow().Render()

    # ------------------------------------------------------------------
    # Reslice helpers
    # ------------------------------------------------------------------

    def _make_reslice_matrix(self) -> vtk.vtkMatrix4x4:
        """Return the reslice axes matrix for this view's orientation.

        The matrix maps output coordinates to input (VTK image) coordinates.
        VTK image axes: X = K (cols), Y = J (rows), Z = I (slices).

        For each view the output Z (normal) must point along the axis
        we are slicing through:
          Axial   → normal along Z (I)
          Coronal → normal along Y (J)
          Sagittal→ normal along X (K)
        """
        m = vtk.vtkMatrix4x4()
        m.Identity()
        if self.axis == 0:    # Axial: XY plane, normal = Z
            pass              # Identity is already correct
        elif self.axis == 1:  # Coronal: XZ plane, normal = Y
            # output X → input X,  output Y → input Z,  output Z → input -Y
            m.SetElement(1, 1, 0); m.SetElement(1, 2, -1)
            m.SetElement(2, 1, 1); m.SetElement(2, 2, 0)
        else:                 # Sagittal: YZ plane, normal = X
            # output X → input Y,  output Y → input Z,  output Z → input X
            m.SetElement(0, 0, 0); m.SetElement(0, 2, 1)
            m.SetElement(1, 0, 1); m.SetElement(1, 1, 0)
            m.SetElement(2, 1, 1); m.SetElement(2, 2, 0)
        return m

    def _update_reslice_position(self, i: int, j: int, k: int) -> None:
        """Move the reslice plane to the current crosshair position.

        The origin must be placed along the correct INPUT axis:
          Axial   → origin along input Z  (VTK Z = I axis)
          Coronal → origin along input Y  (VTK Y = J axis)
          Sagittal→ origin along input X  (VTK X = K axis)
        """
        if self._volume is None:
            return
        sp = self._volume.spacing

        m = self._make_reslice_matrix()
        # Start with origin at (0, 0, 0); set the slice-axis component.
        m.SetElement(0, 3, 0)
        m.SetElement(1, 3, 0)
        m.SetElement(2, 3, 0)

        if self.axis == 0:       # Axial: move along VTK Z (I)
            m.SetElement(2, 3, i * sp[0])
        elif self.axis == 1:     # Coronal: move along VTK Y (J)
            m.SetElement(1, 3, j * sp[1])
        else:                    # Sagittal: move along VTK X (K)
            m.SetElement(0, 3, k * sp[2])

        self._reslice.SetResliceAxes(m)
        self._reslice.Update()

    # ------------------------------------------------------------------
    # Crosshair overlay
    # ------------------------------------------------------------------

    def _make_line_actor(self, color=(0.0, 1.0, 0.0)) -> vtk.vtkActor2D:
        pts = vtk.vtkPoints()
        pts.InsertNextPoint(0, 0, 0)
        pts.InsertNextPoint(1, 0, 0)
        lines = vtk.vtkCellArray()
        lines.InsertNextCell(2)
        lines.InsertCellPoint(0)
        lines.InsertCellPoint(1)
        poly = vtk.vtkPolyData()
        poly.SetPoints(pts)
        poly.SetLines(lines)
        mapper = vtk.vtkPolyDataMapper2D()
        mapper.SetInputData(poly)
        actor = vtk.vtkActor2D()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*color)
        actor.GetProperty().SetLineWidth(1)
        actor.GetProperty().SetOpacity(0.6)
        return actor

    def _voxel_to_display_frac(self) -> Tuple[float, float]:
        """Return the (u, v) display fraction of the current crosshair."""
        ci, cj, ck = self._crosshair.as_int()
        ni, nj, nk = self._volume.shape
        if self.axis == 0:
            u = ck / max(nk - 1, 1)
            v = cj / max(nj - 1, 1)
        elif self.axis == 1:
            u = ck / max(nk - 1, 1)
            v = ci / max(ni - 1, 1)
        else:
            u = cj / max(nj - 1, 1)
            v = ci / max(ni - 1, 1)
        return u, v

    def _frac_to_display(self, u_frac: float, v_frac: float) -> Tuple[int, int]:
        """Convert image fraction [0,1] to display pixel, accounting for camera."""
        bounds = self._image_actor.GetBounds()
        wx = bounds[0] + u_frac * (bounds[1] - bounds[0])
        wy = bounds[2] + v_frac * (bounds[3] - bounds[2])
        coord = vtk.vtkCoordinate()
        coord.SetCoordinateSystemToWorld()
        coord.SetValue(wx, wy, 0)
        dp = coord.GetComputedDisplayValue(self._renderer)
        return int(dp[0]), int(dp[1])

    def _update_crosshair_lines(self) -> None:
        """Reposition the 2-D crosshair lines to match the current cursor."""
        if self._volume is None:
            return
        size = self._vtk_widget.GetRenderWindow().GetSize()
        w, h = size[0], size[1]

        u_frac, v_frac = self._voxel_to_display_frac()
        px, py = self._frac_to_display(u_frac, v_frac)

        # Horizontal line
        h_pts = self._ch_h_actor.GetMapper().GetInput().GetPoints()
        h_pts.SetPoint(0, 0, py, 0)
        h_pts.SetPoint(1, w, py, 0)
        h_pts.Modified()

        # Vertical line
        v_pts = self._ch_v_actor.GetMapper().GetInput().GetPoints()
        v_pts.SetPoint(0, px, 0, 0)
        v_pts.SetPoint(1, px, h, 0)
        v_pts.Modified()

    # ------------------------------------------------------------------
    # Window / level
    # ------------------------------------------------------------------

    def _apply_wl(self) -> None:
        if self._volume is None:
            return
        lo = self._wl.lower
        hi = self._wl.upper
        self._reslice.SetOutputScalarType(vtk.VTK_FLOAT)
        # Map [lo, hi] → [0, 255] via vtkImageShiftScale
        shift = -lo
        scale = 255.0 / max(hi - lo, 1.0)
        self._reslice.GetOutput()  # ensure pipeline is updated
        self._color_map.GetLookupTable().SetRange(lo, hi)
        self._color_map.Modified()

    # ------------------------------------------------------------------
    # Observer callbacks
    # ------------------------------------------------------------------

    def _on_crosshair_changed(self) -> None:
        ci, cj, ck = self._crosshair.as_int()
        self._update_reslice_position(ci, cj, ck)
        self._update_crosshair_lines()
        self._vtk_widget.GetRenderWindow().Render()

    def _on_wl_changed(self) -> None:
        self._apply_wl()
        self._vtk_widget.GetRenderWindow().Render()

    def _on_annotations_changed(self) -> None:
        self._redraw_annotations()
        self._vtk_widget.GetRenderWindow().Render()

    # ------------------------------------------------------------------
    # Mouse event handlers
    # ------------------------------------------------------------------

    def _display_to_voxel(self, x: int, y: int) -> Tuple[int, int, int]:
        """Convert display pixel (x, y) to voxel indices (i, j, k).

        Uses VTK coordinate conversion so the mapping stays correct
        after camera pan/zoom.
        """
        if self._volume is None:
            return 0, 0, 0

        # Display → world (accounts for camera zoom/pan)
        coord = vtk.vtkCoordinate()
        coord.SetCoordinateSystemToDisplay()
        coord.SetValue(x, y, 0)
        world = coord.GetComputedWorldValue(self._renderer)

        # World → normalised image fraction via actor bounds
        bounds = self._image_actor.GetBounds()
        x_range = bounds[1] - bounds[0]
        y_range = bounds[3] - bounds[2]
        if x_range < 1e-6 or y_range < 1e-6:
            return 0, 0, 0

        u = max(0.0, min(1.0, (world[0] - bounds[0]) / x_range))
        v = max(0.0, min(1.0, (world[1] - bounds[2]) / y_range))

        ni, nj, nk = self._volume.shape
        if self.axis == 0:
            k = int(u * (nk - 1))
            j = int(v * (nj - 1))
            i, _, _ = self._crosshair.as_int()
        elif self.axis == 1:
            k = int(u * (nk - 1))
            i = int(v * (ni - 1))
            _, j, _ = self._crosshair.as_int()
        else:
            j = int(u * (nj - 1))
            i = int(v * (ni - 1))
            _, _, k = self._crosshair.as_int()
        return (
            max(0, min(ni - 1, i)),
            max(0, min(nj - 1, j)),
            max(0, min(nk - 1, k)),
        )

    def _on_click(self, obj, event) -> None:
        x, y = self._vtk_widget.GetEventPosition()
        i, j, k = self._display_to_voxel(x, y)
        self._crosshair.set(i, j, k)
        self.crosshair_moved.emit(i, j, k)
        self._drawing = True

    def _on_mouse_move(self, obj, event) -> None:
        if not self._drawing:
            return
        x, y = self._vtk_widget.GetEventPosition()
        i, j, k = self._display_to_voxel(x, y)
        self._crosshair.set(i, j, k)

    def _on_release(self, obj, event) -> None:
        self._drawing = False

    def _on_scroll_fwd(self, obj, event) -> None:
        """Scroll wheel forward → next slice."""
        if self._volume is None:
            return
        ci, cj, ck = self._crosshair.as_int()
        ni, nj, nk = self._volume.shape
        if self.axis == 0:
            self._crosshair.set(min(ci + 1, ni - 1), cj, ck)
        elif self.axis == 1:
            self._crosshair.set(ci, min(cj + 1, nj - 1), ck)
        else:
            self._crosshair.set(ci, cj, min(ck + 1, nk - 1))

    def _on_scroll_bwd(self, obj, event) -> None:
        """Scroll wheel backward → previous slice."""
        if self._volume is None:
            return
        ci, cj, ck = self._crosshair.as_int()
        if self.axis == 0:
            self._crosshair.set(max(ci - 1, 0), cj, ck)
        elif self.axis == 1:
            self._crosshair.set(ci, max(cj - 1, 0), ck)
        else:
            self._crosshair.set(ci, cj, max(ck - 1, 0))

    # ------------------------------------------------------------------
    # Annotation rendering
    # ------------------------------------------------------------------

    def _redraw_annotations(self) -> None:
        """Remove old annotation actors and rebuild from store."""
        for actor in self._ann_actors:
            self._renderer.RemoveActor(actor)
        self._ann_actors.clear()

        ci, cj, ck = self._crosshair.as_int()
        if self.axis == 0:
            slice_idx = ci
        elif self.axis == 1:
            slice_idx = cj
        else:
            slice_idx = ck

        for ann in self._ann_store.for_slice(self.axis, slice_idx):
            actor = self._build_annotation_actor(ann)
            if actor:
                self._renderer.AddActor(actor)
                self._ann_actors.append(actor)

    def _build_annotation_actor(self, ann: Annotation) -> Optional[vtk.vtkActor2D]:
        """Convert an Annotation into a vtkActor2D polyline."""
        if len(ann.points) < 2:
            return None

        pts = vtk.vtkPoints()
        cells = vtk.vtkCellArray()
        n = len(ann.points)
        cells.InsertNextCell(n + 1)
        for idx, (u_frac, v_frac) in enumerate(ann.points):
            px, py = self._frac_to_display(u_frac, v_frac)
            pts.InsertNextPoint(px, py, 0)
            cells.InsertCellPoint(idx)
        cells.InsertCellPoint(0)  # close the loop

        poly = vtk.vtkPolyData()
        poly.SetPoints(pts)
        poly.SetLines(cells)

        mapper = vtk.vtkPolyDataMapper2D()
        mapper.SetInputData(poly)

        actor = vtk.vtkActor2D()
        actor.SetMapper(mapper)
        r, g, b, a = ann.color
        actor.GetProperty().SetColor(r, g, b)
        actor.GetProperty().SetOpacity(a)
        actor.GetProperty().SetLineWidth(2)
        return actor

    # ------------------------------------------------------------------
    # Qt lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._vtk_widget.GetRenderWindow().Finalize()
        self._vtk_widget.GetRenderWindow().GetInteractor().TerminateApp()
        super().closeEvent(event)