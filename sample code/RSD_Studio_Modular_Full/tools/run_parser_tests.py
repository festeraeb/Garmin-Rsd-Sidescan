#!/usr/bin/env python3
"""Test script for RSD parsers.
Tests both classic and nextgen parsers on sample RSD files.
"""

from pathlib import Path
import sys
import csv
import json
from typing import Dict, List, Tuple

# Add parent directories to path for imports
SCRIPT_DIR = Path(__file__).parent
sys.path.extend([
    str(SCRIPT_DIR.parent / "src"),
    str(SCRIPT_DIR.parent / "engine")
])

from engine_classic_varstruct import parse_rsd_records_classic as classic_parse
from engine_nextgen_syncfirst import parse_rsd_records_nextgen as nextgen_parse

def test_parser(parser_func, rsd_path: str, out_dir: str) -> Tuple[int, str, str]:
    """Run parser and return (record_count, csv_path, log_path)."""
    print(f"\nTesting parser {parser_func.__module__} on {Path(rsd_path).name}")
    try:
        count, csv_path, log_path = parser_func(rsd_path, out_dir)
        print(f"Success: {count} records written to {csv_path}")
        return count, csv_path, log_path
    except Exception as e:
        print(f"Error: {e}")
        return 0, "", ""

def analyze_csv(csv_path: str) -> Dict:
    """Analyze CSV output for key metrics."""
    if not csv_path or not Path(csv_path).exists():
        return {}
        
    stats = {
        "record_count": 0,
        "channels": set(),
        "depth_range": [float('inf'), float('-inf')],  # min, max
        "has_valid_coords": False
    }
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["record_count"] += 1
            stats["channels"].add(int(row["channel_id"]))
            
            depth = float(row["depth_m"])
            stats["depth_range"][0] = min(stats["depth_range"][0], depth)
            stats["depth_range"][1] = max(stats["depth_range"][1], depth)
            
            if float(row["lat"]) != 0 or float(row["lon"]) != 0:
                stats["has_valid_coords"] = True
                
    stats["channels"] = sorted(list(stats["channels"]))
    return stats

def main():
    test_dir = Path(SCRIPT_DIR).parent / "test_outputs"
    test_dir.mkdir(exist_ok=True)
    
    # Find RSD files
    rsd_files = []
    for ext in ["*.RSD", "*.rsd"]:
        rsd_files.extend(SCRIPT_DIR.parent.rglob(ext))
    
    if not rsd_files:
        print("No RSD files found!")
        return
        
    results = {}
    for rsd_path in rsd_files:
        file_results = {
            "filename": rsd_path.name,
            "path": str(rsd_path),
            "tests": {}
        }
        
        # Test both parsers
        parsers = [
            ("classic", classic_parse),
            ("nextgen", nextgen_parse)
        ]
        
        for name, parser in parsers:
            out_dir = test_dir / rsd_path.stem / name
            out_dir.mkdir(parents=True, exist_ok=True)
            
            count, csv_path, log_path = test_parser(parser, str(rsd_path), str(out_dir))
            
            stats = analyze_csv(csv_path)
            file_results["tests"][name] = {
                "record_count": count,
                "csv_path": csv_path,
                "log_path": log_path,
                "analysis": stats
            }
            
        results[rsd_path.name] = file_results
        
    # Write summary
    summary_path = test_dir / "test_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nTest summary written to {summary_path}")

if __name__ == "__main__":
    main()