---
name: chart-comp-comparison
description: >
  Defines exactly how the Query Interface Agent renders the grouped bar chart
  comparing a queried player to their top comps. Covers chart type, axis rules,
  color palette, labeling, distance score display, and edge case handling.
---

# Skill: Comp Comparison Bar Chart

## Purpose
Defines exactly how the agent should render the bar chart comparing a queried player
to their top comps, so the visualization stays consistent across queries instead of
being redesigned each time.

---

## Input
- The queried player: name, canonical position, year, and up to 3 percentiles
  (explosive, speed, dynamic speed).
- Up to 3 comps (from the comp engine, already sorted by closeness): same fields each.
- Distance score and dimension count for each comp.

---

## Chart Type
**Grouped bar chart** — not stacked, not one-bar-per-player.

- **X-axis:** the 3 metrics as the groups → `Explosive`, `Speed`, `Dynamic Speed`
- **Within each group:** one bar per player (queried player + up to 3 comps = up to 4 bars per group)
- **Y-axis:** percentile, **fixed 0–100 scale** — do not auto-scale to the data range.
  Percentiles across different queries must be visually comparable.

This layout lets you see, metric by metric, exactly where a comp is close to the
player and where they diverge — which a single-bar-per-player layout hides.

---

## Styling Rules

1. **The queried player gets a fixed, distinct color every time.**
   Use **dark navy `#1B2A4A`** regardless of which comps are shown. This makes it
   easy to scan multiple queries and immediately spot "the player" vs. "the comps."

2. **Comps get a consistent secondary palette** — 3 shades of teal/green ordered
   from closest (darkest) to least close (lightest):
   - Comp 1 (closest): `#0F766E`
   - Comp 2: `#5EEAD4`
   - Comp 3 (furthest): `#CCFBF1`

3. **Label each bar with its exact percentile value** (not just position on the axis).
   The whole point of this tool is precision — don't make someone eyeball bar height.

4. **Include the comp's distance score in the legend or a subtitle**, so it's clear
   *how* close each comp actually is, not just that they were selected.
   Format: `{Player Name} ({Year}) — dist: {score:.1f}`

5. **Title format:** `"{Player Name} ({Position}, {Year}) vs. closest comps"`

---

## Output Format
- Default: inline HTML chart using Chart.js, rendered in the output file.
- Cap at **4 total bars per group** (player + 3 comps) for readability.
  If more comps are ever requested, surface additional ones as a text list below the chart.

---

## Edge Cases

- If the queried player or a comp is **missing a percentile** (null), show that bar as
  **absent / greyed** rather than zero. A missing metric must never visually read as
  "0th percentile."
- If a comp was matched on **fewer than 3 dimensions** (e.g., 2025/2026 dynamic speed
  absent), mark that comp's legend entry with `⚠ 2-of-3 metrics` and grey out the
  Dynamic Speed bar for that comp.
- If the queried player has **no comps** (e.g., unique profile with no same-position
  players), display a message instead of an empty chart.
