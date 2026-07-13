"""
Data Agent — Process Pipeline
==============================
Reads the raw combine CSV, applies canonical position normalization,
computes percentile ranks within each canonical position group,
and writes the enriched dataset to players_with_percentiles.csv.

Skills driving this script:
  - combine-data-schema      (column definitions, position mapping)
  - percentile-comp-methodology  (percentile formula, ranking rules)
"""

import csv
import math
import json
from pathlib import Path

# ── Canonical position map (from schema skill) ──────────────────────────────
POSITION_MAP = {
    # DT group
    "DT": "DT", "NT": "DT", "DL": "DT", "IDL": "DT",
    # EDGE group
    "ED": "EDGE", "OLB": "EDGE", "EDGE": "EDGE",
    # OL group
    "OG": "OL", "OC": "OL", "IOL": "OL", "OT": "OL", "OL": "OL",
    # CB group
    "CB": "CB", "BC": "CB", "DC": "CB",
    # S group
    "S": "S", "DB": "S", "DS": "S", "SS": "S", "FS": "S",
    # LB group
    "LB": "LB", "ILB": "LB",
    # Skill positions — pass-through
    "WR": "WR", "RB": "RB", "FB": "FB", "TE": "TE", "QB": "QB",
    "K": "K", "P": "P", "LS": "LS",
}

DATA_DIR = Path(__file__).parent
INPUT_CSV = DATA_DIR / "players.csv"
OUTPUT_CSV = DATA_DIR / "players_with_percentiles.csv"


def safe_float(val):
    """Return float or None for missing / error values."""
    if val is None:
        return None
    val = str(val).strip()
    if val in ("", "#DIV/0!", "#N/A", "#VALUE!", "#REF!", "N/A"):
        return None
    try:
        return float(val)
    except ValueError:
        return None


def average_rank_percentile(values):
    """
    Given a list of (index, raw_value) pairs (non-null only),
    return a dict {index: percentile} using average-rank method.
    Higher raw value → higher percentile.
    """
    n = len(values)
    if n == 0:
        return {}
    # Sort by raw value ascending
    sorted_vals = sorted(values, key=lambda x: x[1])
    # Assign rank groups (average rank for ties)
    ranks = {}
    i = 0
    while i < n:
        j = i
        while j < n - 1 and sorted_vals[j + 1][1] == sorted_vals[i][1]:
            j += 1
        avg_rank = (i + 1 + j + 1) / 2  # 1-indexed average rank
        for k in range(i, j + 1):
            ranks[sorted_vals[k][0]] = avg_rank
        i = j + 1
    # Convert to percentile: rank / n * 100
    return {idx: (ranks[idx] / n * 100) for idx in ranks}


def compute_percentiles(rows):
    """
    Compute explosive_percentile, speed_percentile, dynamic_speed_percentile
    within each canonical_position group. Returns updated rows.
    """
    metrics = [
        ("explosive_score", "explosive_percentile"),
        ("SPEED", "speed_percentile"),
        ("DYNAMIC SPEED", "dynamic_speed_percentile"),
    ]

    # Initialize percentile columns to None
    for row in rows:
        for _, pct_col in metrics:
            row[pct_col] = None

    # Group by canonical position
    position_groups = {}
    for idx, row in enumerate(rows):
        pos = row.get("canonical_position")
        if pos:
            position_groups.setdefault(pos, []).append(idx)

    for pos, indices in position_groups.items():
        for raw_col, pct_col in metrics:
            # Collect non-null values
            valid = []
            for idx in indices:
                val = safe_float(rows[idx].get(raw_col))
                if val is not None:
                    valid.append((idx, val))
            # Compute percentiles
            pcts = average_rank_percentile(valid)
            for idx, pct in pcts.items():
                rows[idx][pct_col] = round(pct, 2)

    return rows


def main():
    print("── E-S-D Compiler Agent: Data Processing Pipeline ──")
    print(f"Input : {INPUT_CSV}")
    print(f"Output: {OUTPUT_CSV}")
    print()

    # 1. Load CSV
    with open(INPUT_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} player rows.")

    # 2. Apply canonical position normalization
    unmapped = set()
    for row in rows:
        raw_pos = (row.get("POS") or "").strip()
        canonical = POSITION_MAP.get(raw_pos)
        if canonical is None and raw_pos:
            unmapped.add(raw_pos)
        row["canonical_position"] = canonical or raw_pos  # fallback keeps raw

    if unmapped:
        print(f"\n⚠  UNMAPPED positions (flagged — review schema skill): {sorted(unmapped)}")
    else:
        print("✓  All positions mapped to canonical form.")

    # 3. Compute percentiles
    rows = compute_percentiles(rows)
    print("✓  Percentiles computed within each canonical position group.")

    # 4. Write enriched CSV
    fieldnames = list(rows[0].keys())
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓  Wrote {len(rows)} rows → {OUTPUT_CSV.name}")

    # 5. Quick sanity check
    complete = [r for r in rows if r["explosive_percentile"] is not None
                and r["speed_percentile"] is not None
                and r["dynamic_speed_percentile"] is not None]
    partial = [r for r in rows if r["explosive_percentile"] is not None
               and r["speed_percentile"] is not None
               and r["dynamic_speed_percentile"] is None]

    print(f"\n── Dataset Summary ──")
    print(f"  Players with all 3 percentiles : {len(complete)}")
    print(f"  Players with expl + speed only : {len(partial)}")
    print(f"  Canonical positions in dataset : {sorted(set(r['canonical_position'] for r in rows if r['canonical_position']))}")


if __name__ == "__main__":
    main()
