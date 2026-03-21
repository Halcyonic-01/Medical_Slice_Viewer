"""
main.py
-------
Entry point for the Medical Slice Viewer application.

Usage
-----
    python main.py                         # Open blank viewer
    python main.py path/to/scan.nii.gz     # Load NIfTI on startup
    python main.py path/to/dicom_dir/      # Load DICOM series on startup
    python main.py --demo                  # Load a synthetic sphere volume
    python main.py --log-level DEBUG       # Verbose logging
"""

from __future__ import annotations

import argparse
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from src.utils.logging_config import configure as configure_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="medical_slice_viewer",
        description="Orthogonal slice viewer for NIfTI and DICOM volumes.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to a .nii/.nii.gz file or a DICOM directory.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Load a synthetic sphere volume for a quick demo.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help="Optional file path for log output.",
    )
    return parser.parse_args()


def _load_demo(window) -> None:
    """Load the synthetic demo volume (called after the event loop starts)."""
    from src.utils.synthetic import make_sphere_volume
    volume = make_sphere_volume()
    window._panel.bind_volume(volume)
    for view in window._views:
        view.set_volume(volume)
    ci, cj, ck = volume.center_indices()
    window._crosshair.set(ci, cj, ck)
    window.statusBar().showMessage(
        "Demo mode – synthetic sphere volume loaded."
    )


def main() -> int:
    args = parse_args()
    configure_logging(level=args.log_level, log_file=args.log_file)

    # MacOS Apple Silicon + VTK + PyQt6 workaround:
    # We must configure the QSurfaceFormat globally *before* QApplication is
    # instantiated to prevent deadlocks in VTK's OpenGL to Metal translation.
    from PyQt6.QtGui import QSurfaceFormat
    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    fmt.setVersion(3, 2)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    fmt.setRedBufferSize(8)
    fmt.setGreenBufferSize(8)
    fmt.setBlueBufferSize(8)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    app.setApplicationName("Medical Slice Viewer")
    app.setOrganizationName("MedViz")

    # Import here so VTK initialises after QApplication
    from src.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    window.raise_()
    window.activateWindow()

    # On macOS, Python apps launched from a terminal may not come to
    # the foreground automatically.  Use PyObjC / Cocoa if available.
    try:
        from AppKit import NSApp, NSApplication  # type: ignore[import]
        NSApplication.sharedApplication()
        NSApp.activateIgnoringOtherApps_(True)
    except ImportError:
        pass

    # Defer volume loading until the event loop is running so that VTK
    # render windows are fully realised before any Render() calls.
    if args.demo:
        QTimer.singleShot(0, lambda: _load_demo(window))
    elif args.path:
        QTimer.singleShot(0, lambda: window._load_volume(args.path))

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())