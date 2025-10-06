<!-- .github/copilot-instructions.md for Garmin RSD Studio (engines) -->
# Quick orientation for AI coding agents

This repository contains tools to parse Garmin RSD files, produce per-ping "rows" (images), preview them and export waterfall videos.
Keep instructions short, concrete and tied to real files so a code agent can act without guessing.

Core components (big picture)
- Parsers (binary → RSDRecord iterator)
  - `engine_classic_varstruct.py` — "classic" parser: strict CRC checking, conservative failure handling.
  - `engine_nextgen_syncfirst.py` — "next-gen" parser: tolerant (CRC warnings), hop/heuristic resync.
  - Both yield `RSDRecord` dataclass instances (see files for field list: ofs, channel_id, seq, time_ms, lat, lon, depth_m, sample_cnt, sonar_ofs, sonar_size, beam_deg, pitch_deg, roll_deg, heave_m, tx_ofs_m, rx_ofs_m, color_id, extras).

- Glue/CLI surface
  - `engine_glue.py` contains `run_engine(engine, rsd_path, csv_out, ...)` and `_rows_to_csv_stream()` which writes CSV rows. CSV columns are explicit in `_rows_to_csv_stream()` and should be preserved when adding features.
  - Note: the GUI currently calls `engine_glue.py` as a subprocess with `--input/--out/--prefer` flags, but `engine_glue.py` in this snapshot exposes functions (no top-level CLI argparse). Prefer using `run_engine()` programmatically or add a thin CLI wrapper if you need a command-line entrypoint.

- GUI and tools
  - `studio_gui_engines_v3_14.py` — Tkinter GUI used for parsing, stitching and preview/export. It uses subprocesses for the parser and dynamic imports for exporter/stitch modules.
  - `video_exporter.py` + `render_accel.py` — image composition, colormaps, alignment (phase-correlation), preview builder and `export_waterfall_mp4()`.
  - `block_pipeline.py` — utilities for grouping/pairing channel records (used by stitch/preview workflows).

Important shared primitives and patterns
- Progress reporting: use `core_shared.set_progress_hook(fn)` and emit progress via `_emit(pct, message)` so the GUI and other tools can show live feedback. Many parsers call `_emit` frequently (every ~250 records or during long chunk scans).
- Binary parsing: varstruct helpers live in `core_shared.py` (`_parse_varstruct`, varint/varuint helpers). Respect existing CRC modes: `crc_mode='strict'` (raise on mismatch) vs `'warn'` (log warning and continue).
- Magic-scan: `find_magic(mm, magic_bytes, start, end)` performs chunked searching and reports progress (useful for large files).
- Heuristic telemetry decoding: parsers place unknown fields in `extras` using `_decode_body_fields()`; these are deterministic hex/number heuristics — preserve the shape when extending.

Data contracts (examples)
- CSV output (columns written by `_rows_to_csv_stream`):
  ofs,channel_id,seq,time_ms,lat,lon,depth_m,sample_cnt,sonar_ofs,sonar_size,beam_deg,pitch_deg,roll_deg,heave_m,tx_ofs_m,rx_ofs_m,color_id,extras_json
- `RSDRecord` fields: refer to the top of `engine_classic_varstruct.py`/`engine_nextgen_syncfirst.py` for the exact dataclass definition and types.

Runtime / developer workflows (discoverable)
- Install deps (Windows PowerShell):
  python -m pip install -r requirements.txt
- Run the GUI (launches the Tk app that wires the other modules):
  python .\studio_gui_engines_v3_14.py
- Programmatic parse (quick smoke import):
  python -c "from engine_glue import run_engine; print(run_engine('classic','path/to.rsd','out_rows.csv', limit_rows=100))"
  (Prefer calling `run_engine()` from tests or small scripts — it returns the path(s) of generated CSVs.)
- Preview/export: import `video_exporter.build_preview_frame()` or `export_waterfall_mp4()` when automating; these accept a list of image paths and a cfg dict (see `studio_gui_engines_v3_14.py` for `cfg` keys used by the GUI).

Project-specific conventions & gotchas
- Parser variants: use `classic` when you need strict CRC/robustness; use `nextgen` for more tolerant parsing and better resync heuristics. The GUI default preference is `auto-nextgen-then-classic`.
- Progress emits are frequent and textual — code that consumes progress should tolerate None/percentage-less updates (the hook can receive None for pct).
- Video encoding: `VideoWorker` uses OpenCV's VideoWriter and falls back through codecs `mp4v`, `XVID`, `MJPG`, `avc1`. H.264 (`avc1`) may require OpenH264 or system codecs; surface a clear error to the user if all codecs fail.
- Image/row shapes: rows are simple grayscale or small RGB strips. `render_accel.py` contains several helpers (`_auto_split_valley`, `_phase_corr_shift`, `_align_join`) — reuse them rather than reimplementing alignment.

Where to look first when changing behavior
- CSV schema or extra telemetry: `engine_glue.py` and the two engine_* files.
- CRC behavior and varstruct parsing: `core_shared.py` and `_parse_varstruct()`.
- Alignment, preview and export behavior: `render_accel.py` and `video_exporter.py`.
- GUI wiring and example calls: `studio_gui_engines_v3_14.py` (shows typical parameter keys the GUI passes to exporter/stitchers).

If anything above is unclear or you want the file to include runnable snippets or test harnesses, tell me which area to expand (parser CLI, a small unit test, or a reproducible smoke test) and I will iterate.
