
#!/usr/bin/env python3
"""
Garmin RSD QuickTrack (heuristic)
---------------------------------
- Finds record headers by magic 0xB7E9DA86 (any endianness), starting near 0x5000.
- For each record, searches a small window after the header for a pair of int32
  that decode as MapUnits to plausible lat/lon (Great Lakes bounds by default).
- Also tries to pick a plausible depth_mm int32 (0..150000 mm) within the same window.
- Writes CSV with time index, lat, lon, depth_m (if found); also writes a KML track.

Caveats: This avoids full varstruct decoding; it's a best-effort extractor to
unblock mapping quickly. For production, swap in the proper varstruct parser.
"""
import argparse
import mmap
import struct
from pathlib import Path

HEADER_MAGIC_BE = b"\xB7\xE9\xDA\x86"
HEADER_MAGIC_LE = b"\x86\xDA\xE9\xB7"
DEFAULT_START   = 0x5000

# Great Lakes rough bounds (lat, lon):
LAT_MIN, LAT_MAX = 40.0, 50.5
LON_MIN, LON_MAX = -93.5, -74.0

def find_all(data: bytes, token: bytes, start: int = 0):
    pos = start
    while True:
        i = data.find(token, pos)
        if i == -1:
            break
        yield i
        pos = i + 1

def mapunits_to_deg(x: int) -> float:
    # value * (360 / 2^32); mapunits are signed 32-bit
    return (x * (360.0 / (2**32)))

def plausible_lat_lon(lat_deg: float, lon_deg: float) -> bool:
    if not (LAT_MIN <= lat_deg <= LAT_MAX):
        return False
    if not (LON_MIN <= lon_deg <= LON_MAX):
        return False
    return True

def scan_window_for_latlon_and_depth(data: bytes, start: int, window: int = 160):
    """
    Look through [start, start+window) for a pair of consecutive int32 that decode
    to a plausible (lat, lon) in degrees. Return (lat, lon, depth_m or None, offset).
    Depth: choose the nearest int32 in mm that falls into [0, 150000] mm (<=150 m).
    """
    end = min(len(data), start + window)
    for i in range(start, end - 8):
        # read two int32 (little-endian signed)
        lat_i = struct.unpack_from("<i", data, i)[0]
        lon_i = struct.unpack_from("<i", data, i+4)[0]
        lat = mapunits_to_deg(lat_i)
        lon = mapunits_to_deg(lon_i)
        if plausible_lat_lon(lat, lon):
            # optional: find a nearby plausible depth_mm within +/- 24 bytes
            depth_m = None
            for j in range(max(i-24, start), min(i+24, end-4), 4):
                val = struct.unpack_from("<i", data, j)[0]
                if 0 <= val <= 150000:  # up to 150 m
                    depth_m = val / 1000.0
                    break
            return (lat, lon, depth_m, i)
    return None

def write_kml(coords, path: Path):
    def coord_str():
        return "\n        ".join(f"{lon:.7f},{lat:.7f},0" for lat, lon in coords)
    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>RSD QuickTrack</name>
    <Style id="trk"><LineStyle><width>3</width></LineStyle></Style>
    <Placemark>
      <name>Track</name>
      <styleUrl>#trk</styleUrl>
      <LineString><tessellate>1</tessellate><coordinates>
    {coord_str()}
      </coordinates></LineString>
    </Placemark>
  </Document>
</kml>"""
    path.write_text(kml, encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Path to Garmin SonarXXX.RSD")
    ap.add_argument("-o", "--outbase", default="quicktrack", help="Output base name (no extension)")
    ap.add_argument("--start", type=lambda x: int(x, 0), default=DEFAULT_START, help="Scan start offset (default 0x5000)")
    ap.add_argument("--max", type=int, default=1000000000, help="Max records to consider")
    ap.add_argument("--win", type=int, default=160, help="Scan window bytes after header (default 160)")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        raise SystemExit(f"Input not found: {src}")

    with src.open("rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        data = mm[:]
        mm.close()

    # Find candidate headers (both byte orders) starting at --start
    hits = sorted(set(list(find_all(data, HEADER_MAGIC_BE, args.start)) +
                      list(find_all(data, HEADER_MAGIC_LE, args.start))))
    if not hits:
        raise SystemExit("No record headers found (magic 0xB7E9DA86). Try --start 0x0.")

    # Iterate and extract heuristic lat/lon/depth
    rows = []
    coords = []
    last_ok = None
    t = 0  # relative index time
    for idx, off in enumerate(hits):
        if idx >= args.max:
            break
        best = scan_window_for_latlon_and_depth(data, off+4, window=args.win)
        if not best:
            # try minor skew near the header
            for shift in (2, 6, 0):
                best = scan_window_for_latlon_and_depth(data, off+4+shift, window=args.win)
                if best:
                    break
        if not best:
            continue
        lat, lon, depth_m, where = best
        # Smoothness check: discard wild jumps > ~2 km from previous point
        if last_ok is not None:
            dy = (lat - last_ok[0]) * 111000.0  # meters approx per deg lat
            dx = (lon - last_ok[1]) * 78000.0   # meters approx per deg lon at ~45N
            if (dx*dx + dy*dy) ** 0.5 > 2000.0:
                continue
        rows.append((t, lat, lon, depth_m if depth_m is not None else ""))
        coords.append((lat, lon))
        last_ok = (lat, lon)
        t += 1

    if len(rows) < 5:
        raise SystemExit("Extracted too few points. Try --start 0x0 and/or increase --win.")

    out_csv = src.with_name(f"{args.outbase}.csv")
    out_kml = src.with_name(f"{args.outbase}.kml")
    with out_csv.open("w", encoding="utf-8") as f:
        f.write("t_index,lat,lon,depth_m\n")
        for r in rows:
            f.write(",".join(str(x) for x in r) + "\n")

    write_kml(coords, out_kml)
    print(f"Wrote: {out_csv}  ({len(rows)} points)")
    print(f"Wrote: {out_kml}")

if __name__ == "__main__":
    main()
