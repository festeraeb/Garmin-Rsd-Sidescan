# Garmin RSD – Running Letter (Signature-Aware Parsing)
    *(living notes on what we’ve learned and how we’re using it)*

    ## Purpose
    Track discoveries about modern Garmin RSD structure and codify how we’ll parse/export
    robustly—even when CRCs/trailers are unreliable—so we can produce tracks/KML/CSV fast.

    ---

    ## Canonical anchors
    - **Header magic**: `0xD9264B7C` appears near the file start, sometimes offset by prelude bytes.
    - **Record header magic**: `0xB7E9DA86` (also appears byte-swapped in some scans).
    - **Trailer magic**: `0xF98EACBC` may be missing in modern files → don’t rely on it.
    - **MapUnits → degrees**: `deg = value * (360 / 2^32)`; signed 32-bit int.
    - **Depth**: int32 millimeters is common; use 0–150,000 mm heuristic when field ID is unknown.

    ---

    ## Findings from Sonar000.RSD (current evidence)
    - Header magic present but shifted: **don’t hard-code offset 0x0**; search the first ~0x100 bytes.
    - Record area **not rigidly at 0x5000**; first good header at **0x5002**, then 0x5033, etc. → **always scan**.
    - Trailers **not found** in bulk; prefer record-size = *next-header minus current-header*.
    - **Pattern lab** results (dominant behaviors):
      - **A1/B2 alternators** (`0xB2A1B2A1` / `0xA1B2A1B2`) cluster at ~**+160, +176, +192 bytes** from header; alternation run-length ~14–28 bytes → treat as **pad/sentinel**, **skip**.
      - **Float signatures** `50.0` (`0x42480000`) and `~0.6` (`0x3F19999A`) often at **+96/+112 bytes** → likely a small per-record float block; decode as floats and carry forward.
      - **0x00000001/02/03** repeat in structured ranges, probably counters/flags; log their offsets for cross-file correlation.
    - **QuickTrack (heuristic)** confirmed plausible georef extraction:
      {
  "points": 18,
  "track_length_km": 16.048,
  "bbox": [
    48.47823383286595,
    -92.57063498720528,
    48.51271212100983,
    -92.570446645841
  ],
  "depth_stats": {
    "min_m": 136.196,
    "median_m": 136.196,
    "max_m": 136.196
  }
}

    ---

    ## Parsing strategy (signature-aware, two-tier)
    1) **Header sweep**: scan the whole file (starting at ~0x5000 or 0x0) for `0xB7E9DA86` (and byte-swapped).
    2) **Record bounds**: define each record as `[hdr_i, hdr_{i+1})` (EOF for the last one), with sanity size limits.
    3) **Structured pass (if available)**: attempt normal var-struct decode; accept unknown field IDs (>6), skip safely.
    4) **Heuristic pass (fallback / fast)**:
       - Look for **float block** near `+96..+128` from header; decode a short run of 32-bit floats (4-aligned).
       - **Skip A1/B2 pad run** near `+160..+200` (measure alternation length; skip its span).
       - Search the remainder for **MapUnits** (two consecutive int32 that decode to plausible lat/lon for AOI).
       - Hunt a nearby **depth_mm int32** within ±24 bytes of the lat/lon pair (0–150,000 mm), else leave empty.
       - Apply small **continuity filter** (e.g., discard >2 km jumps) to reduce false positives.
    5) **Outputs**: track KML/GeoJSON, normalized CSV (`t_index, lat, lon, depth_m, f0, f1, …` for float block).
    6) **QA**: per-record offsets for the float-block start, pad-run extent, and lat/lon location are logged to help refine the structured parser later.

    ---

    ## How we use each discovery
    - **Shifted header** → Make header detection a search, not a fixed offset.
    - **Missing trailers** → Use *next-header sizing*; CRC becomes advisory only.
    - **A1/B2 pad** → Explicitly skip the alternation band before scanning payload → fewer false “lat/lon” hits.
    - **Float block** → Decode & preserve as unnamed floats; later correlate across files to assign meaning.
    - **MapUnits lat/lon** → Primary georef source when var-struct IDs aren’t stable; convert with the standard scale.
    - **Depth heuristic** → When field ID varies, look for an adjacent mm-range int32.

    ---

    ## Integration status
    - **rsd_core_signature.py**: new module added with `scan_headers(...)`, `parse_record_heuristic(...)`, and `extract_to_csv_kml(...)`.
    - **fasttrack_cli.py**: simple CLI wrapper to run the heuristic extractor on any `.RSD` and write CSV+KML.
    - These can run side-by-side with the strict parser; GUI can expose a **“Fast Track (heuristic)”** button.

    ---

    ## Validation & next steps
    - Validate across multiple files/firmware versions; confirm the +96/+112 float block and +160..+200 pad-run.
    - Add a **varuint probe** around the float block to detect length-prefix patterns.
    - Build a multi-file aggregator for pattern offsets → auto-learn stable field positions.
    - If desired: split by **beam/channel** once we isolate that field reliably.

    *Last updated:* now
