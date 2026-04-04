import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# import necessary parts
from src.core.volume import Volume
from src.core.crosshair import Crosshair
from src.core.window_level import WindowLevel
from src.annotation.annotation import AnnotationStore, Annotation, AnnotationType
from src.ui.main_window import MainWindow

# load dummy volumetric info
import numpy as np
data = np.zeros((100, 100, 100))
# Let's say we had a nice volume
from src.utils.synthetic import make_sphere_volume
vol = make_sphere_volume((30, 30, 30))

app = QApplication(sys.argv)
win = MainWindow()

def test_stuff():
    win._panel.bind_volume(vol)
    for v in win._views:
        v.set_volume(vol)
    
    # Place cursor at 10, 10, 10
    win._crosshair.set(10, 10, 10)
    
    # Add ROI on axial
    win._panel._plane_combo.setCurrentIndex(0) # Axial
    win._panel._on_add_ann()
    
    # Move crosshair away
    win._crosshair.set(20, 20, 20)
    
    # Simulate selecting the list item
    win._panel._ann_list.setCurrentRow(0)
    win._panel._on_ann_selected() # Call manually
    
    print(f"Crosshair after selection: {win._crosshair.as_int()}")
    app.quit()

QTimer.singleShot(100, test_stuff)
win.show()
sys.exit(app.exec())
