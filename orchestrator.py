"""
E-S-D Compiler Agent — Orchestrator
=====================================
Coordinates the Data Agent and Query Interface Agent to produce
athletic comp results and a grouped bar chart for any queried player.

Usage:
    python orchestrator.py "Armand Membou"
    python orchestrator.py "Kenyon Sadiq"

Skills referenced:
  - combine-data-schema
  - percentile-comp-methodology
  - chart-comp-comparison
"""

import csv
import math
import json
import sys
import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

ENRICHED_CSV = DATA_DIR / "players_with_percentiles.csv"
PROCESS_SCRIPT = DATA_DIR / "process_data.py"

# ── Position map (mirrors data/process_data.py) ──────────────────────────────
POSITION_MAP = {
    "DT": "DT", "NT": "DT", "DL": "DT", "IDL": "DT",
    "ED": "EDGE", "OLB": "EDGE", "EDGE": "EDGE",
    "OG": "OL", "OC": "OL", "IOL": "OL", "OT": "OL", "OL": "OL",
    "CB": "CB", "BC": "CB", "DC": "CB",
    "S": "S", "DB": "S", "DS": "S", "SS": "S", "FS": "S",
    "LB": "LB", "ILB": "LB",
    "WR": "WR", "RB": "RB", "FB": "FB", "TE": "TE", "QB": "QB",
    "K": "K", "P": "P", "LS": "LS",
}


def safe_float(val):
    if val is None:
        return None
    val = str(val).strip()
    if val in ("", "#DIV/0!", "#N/A", "#VALUE!", "#REF!", "N/A"):
        return None
    try:
        return float(val)
    except ValueError:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# DATA AGENT
# ══════════════════════════════════════════════════════════════════════════════

def data_agent(player_name: str) -> dict:
    """
    DATA AGENT — equipped with combine-data-schema + percentile-comp-methodology skills.
    1. Locate queried player
    2. Read their percentiles
    3. Run Euclidean distance comp matching within same canonical position
    4. Return structured result JSON
    """
    print(f"\n[Data Agent] Querying: '{player_name}'")

    # Ensure enriched dataset exists
    if not ENRICHED_CSV.exists():
        print("[Data Agent] Enriched CSV not found — running process_data.py...")
        os.system(f"python3 '{PROCESS_SCRIPT}'")

    # Load data
    with open(ENRICHED_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # ── Step 1: Locate player ─────────────────────────────────────────────
    matches = [r for r in rows if r["player_name"].strip().lower() == player_name.strip().lower()]
    if not matches:
        # Fuzzy fallback — partial name match
        matches = [r for r in rows if player_name.strip().lower() in r["player_name"].strip().lower()]
    if not matches:
        return {"error": f"Player '{player_name}' not found in dataset."}
    if len(matches) > 1:
        print(f"[Data Agent] Multiple matches: {[(m['player_name'], m['year']) for m in matches]}")
        # Use most recent year
        matches = [max(matches, key=lambda r: int(r["year"]) if r["year"].isdigit() else 0)]
        print(f"[Data Agent] Selected most recent: {matches[0]['player_name']} ({matches[0]['year']})")

    player = matches[0]
    p_expl  = safe_float(player["explosive_percentile"])
    p_spd   = safe_float(player["speed_percentile"])
    p_dyn   = safe_float(player["dynamic_speed_percentile"])
    p_pos   = player.get("canonical_position", "").strip()

    print(f"[Data Agent] Found: {player['player_name']} ({player['year']}, {p_pos})")
    print(f"[Data Agent] Percentiles — Explosive: {p_expl}, Speed: {p_spd}, Dynamic: {p_dyn}")

    queried = {
        "player_id": player["player_id"],
        "player_name": player["player_name"],
        "year": player["year"],
        "school": player.get("School", ""),
        "canonical_position": p_pos,
        "explosive_percentile": p_expl,
        "speed_percentile": p_spd,
        "dynamic_speed_percentile": p_dyn,
    }

    # ── Step 2: Comp matching ─────────────────────────────────────────────
    # Filter same canonical position, exclude self, exclude same + future draft classes
    p_year = int(player.get("year", 0))
    candidates = [
        r for r in rows
        if r.get("canonical_position") == p_pos
        and r["player_id"] != player["player_id"]
        and int(r.get("year", 0) or 0) < p_year  # comps must be from prior years only
    ]

    # Euclidean distance — partial distance with annotation if nulls present
    def euclidean_distance(row):
        c_expl = safe_float(row["explosive_percentile"])
        c_spd  = safe_float(row["speed_percentile"])
        c_dyn  = safe_float(row["dynamic_speed_percentile"])

        terms = []
        dims_used = 0

        if p_expl is not None and c_expl is not None:
            terms.append((p_expl - c_expl) ** 2)
            dims_used += 1
        if p_spd is not None and c_spd is not None:
            terms.append((p_spd - c_spd) ** 2)
            dims_used += 1
        if p_dyn is not None and c_dyn is not None:
            terms.append((p_dyn - c_dyn) ** 2)
            dims_used += 1

        if dims_used == 0:
            return None, 0, c_expl, c_spd, c_dyn

        dist = math.sqrt(sum(terms))
        return dist, dims_used, c_expl, c_spd, c_dyn

    scored = []
    for row in candidates:
        dist, dims, c_expl, c_spd, c_dyn = euclidean_distance(row)
        if dist is None:
            continue
        scored.append({
            "player_name": row["player_name"],
            "year": row["year"],
            "school": row.get("School", ""),
            "canonical_position": row["canonical_position"],
            "explosive_percentile": c_expl,
            "speed_percentile": c_spd,
            "dynamic_speed_percentile": c_dyn,
            "distance": round(dist, 2),
            "dimensions_used": dims,
            "note": "" if dims == 3 else f"⚠ {dims}-of-3 metrics",
        })

    scored.sort(key=lambda x: x["distance"])
    top3 = scored[:3]

    # Add rank
    for i, comp in enumerate(top3, 1):
        comp["rank"] = i

    print(f"[Data Agent] Top comps: {[(c['player_name'], c['year'], c['distance']) for c in top3]}")

    return {"queried_player": queried, "comps": top3}


# ══════════════════════════════════════════════════════════════════════════════
# QUERY INTERFACE AGENT
# ══════════════════════════════════════════════════════════════════════════════

def query_interface_agent(data: dict, output_filename: str = None) -> str:
    """
    QUERY INTERFACE AGENT — equipped with chart-comp-comparison skill.
    Renders a grouped bar chart as a self-contained HTML file.
    """
    if "error" in data:
        print(f"[Query Interface Agent] Error: {data['error']}")
        return None

    player = data["queried_player"]
    comps  = data["comps"]

    print(f"\n[Query Interface Agent] Building chart for {player['player_name']}...")

    # Colors per chart skill spec
    COLORS = {
        "player": "#1B2A4A",
        "comp1":  "#0F766E",
        "comp2":  "#5EEAD4",
        "comp3":  "#CCFBF1",
    }
    BORDER_COLORS = {
        "player": "#1B2A4A",
        "comp1":  "#0F766E",
        "comp2":  "#3BBFB0",
        "comp3":  "#99E8DE",
    }

    metrics = ["Explosive", "Speed", "Dynamic Speed"]
    p_vals  = [
        player["explosive_percentile"],
        player["speed_percentile"],
        player["dynamic_speed_percentile"],
    ]

    def null_or_val(v):
        return "null" if v is None else str(round(v, 1))

    def pct_label(v):
        return "" if v is None else str(round(v, 1))

    # Build Chart.js datasets
    player_label = f"{player['player_name']} ({player['year']}) — queried"
    datasets = []

    # Queried player dataset
    datasets.append({
        "label": player_label,
        "data": [null_or_val(v) for v in p_vals],
        "backgroundColor": COLORS["player"],
        "borderColor": BORDER_COLORS["player"],
        "borderWidth": 2,
        "borderRadius": 4,
        "raw_vals": p_vals,
        "is_player": True,
    })

    comp_color_keys = ["comp1", "comp2", "comp3"]
    for comp, ck in zip(comps, comp_color_keys):
        c_vals = [
            comp["explosive_percentile"],
            comp["speed_percentile"],
            comp["dynamic_speed_percentile"],
        ]
        note_str = f" {comp['note']}" if comp["note"] else ""
        label = f"{comp['player_name']} ({comp['year']}){note_str} — dist: {comp['distance']:.1f}"
        datasets.append({
            "label": label,
            "data": [null_or_val(v) for v in c_vals],
            "backgroundColor": COLORS[ck],
            "borderColor": BORDER_COLORS[ck],
            "borderWidth": 2,
            "borderRadius": 4,
            "raw_vals": c_vals,
            "is_player": False,
        })

    # Serialize datasets for Chart.js
    def serialize_datasets(ds_list):
        parts = []
        for ds in ds_list:
            data_str = "[" + ", ".join(ds["data"]) + "]"
            raw_json = json.dumps(ds["raw_vals"], default=lambda x: None if x is None else x)
            parts.append(f"""{{
      label: {json.dumps(ds["label"])},
      data: {data_str},
      backgroundColor: {json.dumps(ds["backgroundColor"])},
      borderColor: {json.dumps(ds["borderColor"])},
      borderWidth: {ds["borderWidth"]},
      borderRadius: {ds["borderRadius"]},
      rawVals: {raw_json}
    }}""")
        return "[" + ",\n  ".join(parts) + "]"

    datasets_js = serialize_datasets(datasets)
    title = f"{player['player_name']} ({player['canonical_position']}, {player['year']}) vs. closest comps"

    # Text summary for comps
    comp_rows_html = ""
    for comp in comps:
        def fmt(v):
            return f"{v:.1f}" if v is not None else "—"
        note_html = f'<span class="warning">{comp["note"]}</span>' if comp["note"] else ""
        comp_rows_html += f"""
        <tr>
          <td class="rank">#{comp["rank"]}</td>
          <td class="name">{comp["player_name"]}</td>
          <td>{comp["year"]}</td>
          <td>{comp["school"]}</td>
          <td>{fmt(comp["explosive_percentile"])}</td>
          <td>{fmt(comp["speed_percentile"])}</td>
          <td>{fmt(comp["dynamic_speed_percentile"])}</td>
          <td class="dist">{comp["distance"]:.1f}</td>
          <td>{note_html}</td>
        </tr>"""

    def fmt_p(v):
        return f"{v:.1f}" if v is not None else "—"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Inter', -apple-system, sans-serif;
      background: #0D1117;
      color: #E6EDF3;
      min-height: 100vh;
      padding: 32px 24px;
    }}

    .container {{
      max-width: 960px;
      margin: 0 auto;
    }}

    /* ── Header ── */
    .header {{
      margin-bottom: 28px;
    }}
    .badge {{
      display: inline-block;
      background: #1B2A4A;
      color: #7DD3FC;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      padding: 4px 10px;
      border-radius: 4px;
      border: 1px solid #2A4A7A;
      margin-bottom: 12px;
    }}
    h1 {{
      font-size: 22px;
      font-weight: 700;
      color: #F0F6FF;
      line-height: 1.3;
      margin-bottom: 8px;
    }}
    .subtitle {{
      font-size: 13px;
      color: #8B949E;
    }}

    /* ── Card ── */
    .card {{
      background: #161B22;
      border: 1px solid #21262D;
      border-radius: 12px;
      padding: 28px;
      margin-bottom: 24px;
    }}
    .card-title {{
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: #8B949E;
      margin-bottom: 20px;
    }}

    /* ── Chart ── */
    .chart-wrapper {{
      position: relative;
      height: 380px;
    }}

    /* ── Player profile row ── */
    .profile-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
      margin-bottom: 0;
    }}
    .metric-box {{
      background: #0D1117;
      border: 1px solid #21262D;
      border-radius: 8px;
      padding: 14px 16px;
      text-align: center;
    }}
    .metric-box .label {{
      font-size: 11px;
      color: #8B949E;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 6px;
    }}
    .metric-box .value {{
      font-size: 28px;
      font-weight: 700;
      color: #7DD3FC;
    }}
    .metric-box .value.missing {{
      color: #4A5568;
      font-size: 20px;
    }}

    /* ── Comp table ── */
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th {{
      text-align: left;
      padding: 8px 10px;
      color: #8B949E;
      font-weight: 500;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-bottom: 1px solid #21262D;
    }}
    td {{
      padding: 10px 10px;
      border-bottom: 1px solid #161B22;
      color: #C9D1D9;
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #1C2130; }}
    td.rank {{ font-weight: 700; color: #7DD3FC; }}
    td.name {{ font-weight: 600; color: #E6EDF3; }}
    td.dist {{ font-weight: 600; color: #F0AB3D; }}
    .warning {{ color: #F0AB3D; font-size: 11px; }}

    /* ── Legend annotation ── */
    .legend-note {{
      font-size: 12px;
      color: #8B949E;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid #21262D;
      line-height: 1.6;
    }}
    .color-dot {{
      display: inline-block;
      width: 10px; height: 10px;
      border-radius: 50%;
      margin-right: 5px;
      vertical-align: middle;
    }}
  </style>
</head>
<body>
  <div class="container">

    <!-- Header -->
    <div class="header">
      <div class="badge">E-S-D Compiler Agent</div>
      <h1>{title}</h1>
      <div class="subtitle">Athletic comp matching via Euclidean distance on explosive · speed · dynamic speed percentiles</div>
    </div>

    <!-- Player Profile -->
    <div class="card">
      <div class="card-title">Queried Player — Percentile Profile</div>
      <div class="profile-grid">
        <div class="metric-box">
          <div class="label">Explosive</div>
          <div class="value {"" if p_vals[0] is not None else "missing"}">{fmt_p(p_vals[0])}</div>
        </div>
        <div class="metric-box">
          <div class="label">Speed</div>
          <div class="value {"" if p_vals[1] is not None else "missing"}">{fmt_p(p_vals[1])}</div>
        </div>
        <div class="metric-box">
          <div class="label">Dynamic Speed</div>
          <div class="value {"" if p_vals[2] is not None else "missing"}">{fmt_p(p_vals[2]) if p_vals[2] is not None else "No data"}</div>
        </div>
      </div>
    </div>

    <!-- Chart -->
    <div class="card">
      <div class="card-title">Grouped Comparison — Percentile by Metric</div>
      <div class="chart-wrapper">
        <canvas id="compChart"></canvas>
      </div>
    </div>

    <!-- Comp Table -->
    <div class="card">
      <div class="card-title">Top Comps — Detail</div>
      <table>
        <thead>
          <tr>
            <th>Rank</th>
            <th>Player</th>
            <th>Year</th>
            <th>School</th>
            <th>Explosive %ile</th>
            <th>Speed %ile</th>
            <th>Dyn Speed %ile</th>
            <th>Distance</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {comp_rows_html}
        </tbody>
      </table>
      <div class="legend-note">
        <span class="color-dot" style="background:#1B2A4A;border:1px solid #4A6A9A"></span>Queried player &nbsp;
        <span class="color-dot" style="background:#0F766E"></span>Closest comp &nbsp;
        <span class="color-dot" style="background:#5EEAD4"></span>2nd comp &nbsp;
        <span class="color-dot" style="background:#CCFBF1;border:1px solid #9ADFD8"></span>3rd comp &nbsp;&nbsp;
        | &nbsp; <span style="color:#F0AB3D">⚠</span> = matched on fewer than 3 metrics &nbsp;
        | &nbsp; <span style="color:#F0AB3D">Distance</span> = Euclidean distance (lower = closer athletic twin)
      </div>
    </div>

  </div>

  <script>
    const ctx = document.getElementById('compChart').getContext('2d');
    const datasets = {datasets_js};

    // Custom plugin: bar value labels
    const barLabelPlugin = {{
      id: 'barLabels',
      afterDatasetsDraw(chart) {{
        const {{ ctx }} = chart;
        chart.data.datasets.forEach((ds, dsIdx) => {{
          const meta = chart.getDatasetMeta(dsIdx);
          meta.data.forEach((bar, barIdx) => {{
            const rawVal = ds.rawVals ? ds.rawVals[barIdx] : null;
            if (rawVal === null || rawVal === undefined) return;
            const label = rawVal.toFixed(1);
            ctx.save();
            ctx.fillStyle = '#F0F6FF';
            ctx.font = '600 11px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            ctx.fillText(label, bar.x, bar.y - 3);
            ctx.restore();
          }});
        }});
      }}
    }};

    new Chart(ctx, {{
      type: 'bar',
      data: {{
        labels: ['Explosive', 'Speed', 'Dynamic Speed'],
        datasets: datasets
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{
            position: 'bottom',
            labels: {{
              color: '#C9D1D9',
              font: {{ family: 'Inter', size: 12 }},
              padding: 16,
              usePointStyle: true,
              pointStyleWidth: 12
            }}
          }},
          tooltip: {{
            backgroundColor: '#1C2130',
            titleColor: '#E6EDF3',
            bodyColor: '#8B949E',
            borderColor: '#21262D',
            borderWidth: 1,
            callbacks: {{
              label: (ctx) => {{
                const raw = ctx.dataset.rawVals ? ctx.dataset.rawVals[ctx.dataIndex] : null;
                if (raw === null || raw === undefined) return ` ${{ctx.dataset.label}}: No data`;
                return ` ${{ctx.dataset.label}}: ${{raw.toFixed(1)}}th percentile`;
              }}
            }}
          }}
        }},
        scales: {{
          x: {{
            grid: {{ color: '#21262D' }},
            ticks: {{ color: '#8B949E', font: {{ family: 'Inter', size: 12 }} }}
          }},
          y: {{
            min: 0,
            max: 100,
            grid: {{ color: '#21262D' }},
            ticks: {{
              color: '#8B949E',
              font: {{ family: 'Inter', size: 12 }},
              callback: (v) => v + 'th'
            }},
            title: {{
              display: true,
              text: 'Percentile (within canonical position group)',
              color: '#8B949E',
              font: {{ family: 'Inter', size: 11 }}
            }}
          }}
        }}
      }},
      plugins: [barLabelPlugin]
    }});
  </script>
</body>
</html>
"""

    # Write output
    safe_name = player["player_name"].replace(" ", "_").replace(".", "")
    if output_filename is None:
        output_filename = f"comp_{safe_name}_{player['year']}.html"
    out_path = OUTPUT_DIR / output_filename
    out_path.write_text(html, encoding="utf-8")
    print(f"[Query Interface Agent] Chart written → {out_path}")
    return str(out_path)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

def run(player_name: str):
    print(f"\n{'═'*60}")
    print(f"  E-S-D COMPILER AGENT — '{player_name}'")
    print(f"{'═'*60}")

    # Step 1: Data Agent
    result = data_agent(player_name)

    # Step 2: Query Interface Agent
    out_path = query_interface_agent(result)

    if out_path:
        print(f"\n✅ Done! Open your chart:\n   {out_path}")
    else:
        print(f"\n❌ Could not generate chart.")

    return result


if __name__ == "__main__":
    players = sys.argv[1:] if len(sys.argv) > 1 else ["Armand Membou", "Kenyon Sadiq"]
    for name in players:
        run(name)
