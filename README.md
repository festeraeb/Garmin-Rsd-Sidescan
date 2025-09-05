# Garmin RSD → Side-Scan → Google Earth

**Colab + Python pipeline** for parsing Garmin `.RSD` sonar logs and producing:
- Side-scan waterfall previews
- KMZ/KML overlays (single, bucketed, or regionated) for Google Earth
- Depth and GPS sanity markers
- Target detection (simple heuristics, expandable later)
- Optional waterfall video

## Quick start

👉 [Open in Colab](https://colab.research.google.com/github/yourname/garmin-rsd-sidescan/blob/main/notebooks/colab_rsd_v4_0.ipynb)

1. Upload a Garmin `.RSD` file in Colab (or mount Google Drive).
2. Configure parameters in the **🔧 Configure** cell.
3. Run all cells to generate outputs in `/content/rsd_runs/<run>/`.

Outputs include:
- `*_records.csv`, `*_track.kml`
- `*_sidescan.kmz` (Google Earth overlay)
- `*_waterfall.png` and optional `*_waterfall.mp4`
- `*_depth.csv` + `*_depth.kml`
- `*_targets.csv` + `*_targets.kml`
- `*_gpsmarkers.kml`

## Features

- Garmin `.RSD` parser (varuint/zigzag spec aligned)
- Multi-palette rendering (amber, blue, grayscale, ironbow, …)
- Auto-decimate + tiling to prevent Google Earth crashes
- Three KML modes:
  - **SINGLE** — simple KMZ with all tiles
  - **BUCKETED** — tiles grouped into geo-folders
  - **REGIONATED** — KML SuperOverlay with Region/LOD for large datasets

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
