# E-S-D Compiler Agent

> **A two-agent agentic system for finding NFL combine athletic comparisons using explosive, speed, and dynamic speed percentile rankings.**

Built with the [Google Antigravity](https://deepmind.google/) agent framework. Compares prospects against 7,200+ combine participants (1999–2026) using Euclidean distance matching across three composite athletic metrics.

---

## Architecture

```
┌─────────────────────┐
│   players.csv       │  Single combine sheet — one row per player
│   (7,207 players)   │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐     ┌──────────────────────┐
│    Data Agent       │◄────│   Schema Skill        │
│                     │◄────│   Percentile Skill    │
│  · Position map     │     └──────────────────────┘
│  · Percentile ranks │
│  · Euclidean comps  │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐     ┌──────────────────────┐
│  Query Interface    │◄────│   Chart Skill         │
│  Agent              │     └──────────────────────┘
│                     │
│  · Grouped bar chart│
│  · HTML output      │
└─────────────────────┘
```

**Two agents, three skills:**

| Component | Role |
|-----------|------|
| **Data Agent** | Loads data, normalizes positions, computes percentile ranks, runs comp matching |
| **Query Interface Agent** | Renders grouped bar chart comparing player to top 3 comps |
| `skills/schema` | Column definitions, units, canonical position normalization map |
| `skills/percentile-methodology` | Percentile formula (average-rank), Euclidean distance algorithm |
| `skills/chart-comp-comparison` | Grouped bar chart spec, color palette, null/missing metric handling |

---

## The Three Metrics

| Metric | Formula |
|--------|---------|
| **Explosive Score** | `(vert + 3.5 × broad) × (weight / height) / 3000` |
| **Speed Score** | `100 × (1 − (40yd / (0.0397 × (wt/ht) + 3.092)))` |
| **Dynamic Speed Score** | `100 × (1 − (3cone / (0.0573 × (wt/ht) + 4.8403)))` |

Percentiles are computed **within each canonical position group** — a WR is ranked against WRs, not OL. Comp matching uses **Euclidean distance** across all three percentile dimensions (or available dimensions if data is partial).

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/mnhardy1504/esd-compiler-agent.git
cd esd-compiler-agent

# 2. Compute percentiles (run once, or after any data update)
python3 data/process_data.py

# 3. Query a player
python3 orchestrator.py "Kenyon Sadiq"
python3 orchestrator.py "Armand Membou"

# 4. Multiple players at once
python3 orchestrator.py "Sam Roush" "Malik Muhammad" "Dillon Thieneman"
```

Output HTML charts are saved to `output/` and open automatically in your browser.

---

## Example Output

### Kenyon Sadiq (TE, 2026)
| Metric | Percentile |
|--------|-----------|
| Explosive | 99.6th |
| Speed | 99.8th |
| Dynamic Speed | — |

**Top Comps:** Vernon Davis (2006, dist: 0.5) · Noah Fant (2019, dist: 1.9) · Theo Johnson (2024, dist: 3.0)

### Armand Membou (OL, 2025)
| Metric | Percentile |
|--------|-----------|
| Explosive | 96.7th |
| Speed | 100th |
| Dynamic Speed | — |

**Top Comps:** David Moore (2021, dist: 1.1) · Sadarius Hutcherson (2021, dist: 1.7) · Quinn Meinerz (2021, dist: 2.7)

---

## Chart Design

- **Grouped bar chart** — 3 metric groups × up to 4 bars (player + 3 comps)
- **Y-axis fixed 0–100** — percentile scale never auto-adjusts
- **Queried player** always dark navy `#1B2A4A`
- **Comps** in teal gradient ordered closest → furthest
- **Exact percentile labels** on every bar — no eyeballing
- **Distance scores** in legend — comps are never presented as equally strong matches
- Missing metrics shown as absent bars, never as 0th percentile

---

## Project Structure

```
esd-compiler-agent/
├── agents/
│   ├── data_agent.md              # Data Agent system prompt
│   └── query_interface_agent.md   # Query Interface Agent system prompt
├── data/
│   ├── players.csv                # Source dataset (7,207 players, 1999–2026)
│   ├── players_with_percentiles.csv  # Enriched output (generated)
│   └── process_data.py            # Percentile computation pipeline
├── skills/
│   ├── schema/SKILL.md            # Column map + position normalization
│   ├── percentile-methodology/SKILL.md  # Percentile formula + comp distance
│   └── chart-comp-comparison/SKILL.md   # Bar chart spec
├── output/                        # Generated HTML charts
├── orchestrator.py                # Main entrypoint
└── README.md
```

---

## Position Normalization

Raw position values are inconsistent across combine years (e.g., `NT`, `DT`, and `DL` all refer to the same role). The schema skill maps every raw value to a **canonical position** before any percentile computation:

| Canonical | Raw Variants |
|-----------|-------------|
| DT | DT, NT, DL, IDL |
| EDGE | ED, OLB |
| OT | OT |
| IOL | OG, OC, IOL |
| OL | OL (generic) |
| CB | CB, BC, DC |
| S | S, DB, DS, SS, FS |
| LB | LB, ILB |

---

## Rules & Design Decisions

- **Comps always come from prior draft years** — same/future class players are excluded to prevent missing-data clustering
- **Missing metrics → null, never zero** — a missing broad jump is not 0th percentile
- **Equal weighting** across all three metrics by default
- **Strictly same canonical position** — no cross-position comps
- **Average-rank method** for ties in percentile computation

---

## Requirements

- Python 3.8+
- No external dependencies — uses only the standard library (`csv`, `math`, `json`, `pathlib`)
- Internet connection for Chart.js CDN in output charts

---

## Data Notes

- Dataset covers NFL combine participants from **1999–2026**
- **2025 and 2026 classes** have no dynamic speed (3-cone) data — comps for these players are matched on explosive + speed only and annotated accordingly
- Some players in recent classes have `broad = 0` (not blank) due to data entry; this is flagged as missing rather than treated as a real measurement

---

*Built with the Google Antigravity agent framework.*
