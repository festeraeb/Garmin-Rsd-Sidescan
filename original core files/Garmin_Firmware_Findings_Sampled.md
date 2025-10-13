# Garmin Firmware Deep-Dive — Findings (Sampled Scan)

This document summarizes model identifiers, channel mapping hints, and frequency/beamwidth signals derived from:
- Strings bundle: `/mnt/data/strings_extracted` (sampled head/tail reads)
- GCD summaries: `/mnt/data/_gcd_summaries_extracted` (first 300 CSVs)
- Decompressed resource blocks: `/mnt/data/firmware_block_carve/decomp` (first 120 blobs)

### Top model identifiers (string scan)
- **UHd** — 148 hits
- **UHD** — 75 hits
- **uhd** — 58 hits
- **UhD** — 53 hits
- **uhD** — 42 hits
- **Uhd** — 28 hits
- **uHd** — 21 hits
- **gT34** — 7 hits
- **echoMAP 95sv** — 6 hits
- **gT56** — 6 hits
- **GPSMAP 557x** — 6 hits
- **GPSMAP 751** — 6 hits
- **GPSMAP 557** — 6 hits
- **GPSMAP 751x** — 6 hits
- **uHD** — 5 hits

### Top frequency tokens (strings)
- **10hz** — 3 hits

### Top beamwidth tokens (strings)
- **2
deg** — 163 hits
- **5deg** — 26 hits
- **5
deg** — 18 hits
- **9deg** — 11 hits
- **6deg** — 7 hits
- **3deg** — 6 hits
- **1deg** — 5 hits
- **4deg** — 4 hits
- **4
deg** — 4 hits
- **7
deg** — 3 hits
- **0deg** — 3 hits
- **717
deg** — 2 hits
- **1
deg** — 2 hits
- **9
deg** — 2 hits
- **93
deg** — 2 hits

### Top frequency tokens (decompressed blobs)
_No strong signals detected._

### Top beamwidth tokens (decompressed blobs)
_No strong signals detected._

### Channel Map Snippets (heuristic)
_No explicit channel mapping strings found in sampled blobs._

## Artifacts
- `deep_analysis/string_hits.csv` — regex hits from sampled text files
- `deep_analysis/csv_semantic_samples.csv` — sampled structured columns
- `deep_analysis/blob_ascii_hits.csv` — freq/beam tokens from sampled blobs
- `deep_analysis/channel_map_snippets.csv` — possible port/starboard/down mappings
- `deep_analysis/deep_summary.json` — roll-ups of top tokens

