
Garmin RSD Studio — Modular Full Build

Run GUI:
- Windows: run_gui.bat
- macOS:   ./run_gui.command

What you get:
1) Parser (threaded) → outputs <Outputs>/<stem>_records.csv
2) Per-channel row strips (no merging) → <Outputs>/<stem>_rows/chXX/*.png
3) Stitch preview per channel (correct flags --rows --csv --out)
4) Hinted auto-pick: load firmware hints JSON (engine/fw_hintscan.py can generate from dumps) to bias pairing
5) Override controls: choose any two channels, set seq window (20–50 typical), offset, flip/swap; build live preview
6) One-click render: MP4 (imageio/pyav) + KML line from CSV

Modularity:
- GUI calls small helpers: engine/build_rows_from_csv.py, engine/rows_from_csv_rsd.py, engine/make_video_from_stitch.py, engine/build_kml_from_csv.py
- group_suggest_hinted.py encapsulates pairing/offset suggestion; swap it without touching GUI
- preview_runner.py encapsulates color preview

Requirements:
pip install -r src/requirements.txt
(also installs Pillow, imageio, imageio-ffmpeg, av)

Firmware hints (optional):
python engine/fw_hintscan.py --in <folder_with_dumps> --out <Outputs>/fw_hints.json
Load the JSON in the GUI "Group & Preview" tab, click "Auto-pick Pair".
