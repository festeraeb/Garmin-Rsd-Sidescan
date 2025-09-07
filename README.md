Garmin RSD Parser & Viewer

This project provides a full pipeline for parsing and visualizing Garmin .RSD sonar recordings, including side-scan, down-scan, and depth overlays. It replicates much of the functionality of commercial tools like SonarTRX, with options to export images, Google Earth overlays, and videos.

Supports:

Colab (v5.4.5)

Jupyter (v1.4.5)

Desktop App with GUI (Windows v1.2.3 / macOS v1.2.3)

✨ Features

RSD Parsing

Custom CRC-32 validation (Garmin spec compliant).

Safe varstruct parser with resync on errors.

Supports .IDX when available.

Filters channels (sidescan = 45/46, downscan).

Visualization

Per-ping PNG strips (port/stbd, water column gap).

Waterfall preview (stitched).

Multiple palettes: grayscale, amber, blue, green, ironbow.

Intensity inversion, clipping, and gamma adjustment.

Geo-Outputs

KMZ overlays (gx:LatLonQuad) with options:

Full overlays.

Bucketed overlays (grouped).

Regionated overlays (LOD-friendly).

GPS track export (KML).

Depth overlays with configurable thresholds and percent-change markers.

Video

MP4 waterfall export.

Auto-padding for codec compatibility (macro_block_size=1).

Optional GPU acceleration (CuPy/Numba if available).

GUI (Desktop App)

File picker for .RSD.

Toggles for each output (CSV, KMZ, MP4, depth markers, etc.).

Progress bar with cancel option.

Output folder opener.

Runs in standalone .bat (Windows) or .command (Mac).

📦 Installation
Windows (Desktop App)

Unzip release package.

Run:

Desktop_App\run_windows_py312.bat


This creates a .venv, installs dependencies, and launches the GUI.

macOS (Desktop App)

Unzip release package.

In Terminal:

chmod +x Desktop_App/run_mac.command
./Desktop_App/run_mac.command

Jupyter
pip install pillow numpy simplekml imageio imageio-ffmpeg numba


Then open:

Jupyter/Garmin_RSD_Desktop_v1_4_5_GPU.ipynb

Colab

Upload:

Colab/Garmin_RSD_Colab_v5_4_5_GPU.ipynb

rsd_core_crc_plus.py

Then run the notebook.

🚀 Usage
GUI

Select .RSD file.

Toggle features (KMZ, MP4, depth markers).

Run pipeline.

Results saved in /output/<run_name>.

Colab/Jupyter

Set RSD_PATH.

Configure settings in the CONFIG cell.

Run all cells.

Outputs saved in OUT_DIR.

🔧 Configuration Options

Row height (px)

Swath width (m)

Decimation stride

Water column padding

Palettes (multiple can be generated per run)

Clip % and gamma

Depth marker thresholds

Video settings (fps, max frames)

CRC mode (strict, warn, off)

🧪 Versions

Colab → v5.4.5

Jupyter → v1.4.5

Desktop App → v1.2.3

⚡ GPU Acceleration

Optional: If CuPy/Numba are installed and GPU available, slant correction + tone-mapping run on GPU.

Fallback: pure NumPy (CPU).

📂 Outputs

<base>_records.csv — parsed metadata

<base>_track.kml — GPS track

<base>_row_XXXXXX.png — per-ping strips

<base>_waterfall.png — preview waterfall

<base>_sidescan.kmz — Google Earth overlay

<base>_waterfall.mp4 — waterfall video

<base>_depth.csv + <base>_depth.kml — depth overlays

🗺️ Roadmap

Regionated KMZ tiling for large files.

Smarter auto-decimation (based on ping count).

Enhanced target detection (shipwrecks, features).

GUI improvements (multi-color export without rerun).

Direct zip auto-download in Colab.

[MIT](LICENSE)
