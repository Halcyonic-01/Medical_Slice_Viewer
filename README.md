# Medical Slice Viewer

A desktop medical imaging viewer for loading and inspecting 3D volumes from:

- NIfTI (`.nii`, `.nii.gz`)
- DICOM series (folder of DICOM slices)

The app displays synchronized orthogonal slice views (axial, coronal, sagittal), supports window/level controls, and includes basic ROI annotation tools.

## Features

- Open NIfTI files or DICOM folders
- Three synchronized slice views (axial/coronal/sagittal)
- Crosshair navigation across all views
- Window/Level adjustment controls
- Basic ROI annotation list with add/remove
- Save/load annotations as JSON

## Requirements

- macOS, Linux, or Windows
- Python 3.10+
- Recommended: use a virtual environment

Main dependencies:

- `PyQt6`
- `VTK`
- `numpy`
- `nibabel`
- `pydicom`

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

### Main mode (normal app)

```bash
source venv/bin/activate
python main.py
```

### Demo mode (synthetic sample volume)

```bash
source venv/bin/activate
python main.py --demo
```

## How to Use

1. Start the app in main mode.
2. Click `File -> Open Volume...`.
3. Choose one:
   - `NIfTI File` for `.nii`/`.nii.gz`
   - `DICOM Folder` for a directory containing DICOM slices
4. Navigate slices:
   - Click/drag in a view to move the crosshair
   - Use slice index controls in the right panel
5. Adjust contrast using `Window / Level` sliders.
6. Add/remove ROIs from the annotation panel.
7. Save or load annotations using JSON buttons/menu.

## Project Structure

```text
.
├── main.py
├── requirements.txt
├── pyproject.toml
├── src/
│   ├── core/         # Volume, crosshair, window/level state
│   ├── io/           # NIfTI and DICOM loaders
│   ├── ui/           # Main window, slice views, control panel
│   ├── annotation/   # ROI model + JSON persistence
│   └── utils/        # Logging + synthetic demo data
├── tests/
└── scripts/
```

## Testing

```bash
source venv/bin/activate
pytest
```

## Notes / Troubleshooting

- If `python main.py` fails due to missing packages, ensure you are using the project virtual environment (`venv`).
- For DICOM, select the directory containing the series files (not a single slice file).
- On some systems, graphics backend behavior can differ based on OpenGL/driver support.

## License

MIT (or project default if specified elsewhere).
