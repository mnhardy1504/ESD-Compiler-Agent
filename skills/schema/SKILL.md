---
name: combine-data-schema
description: >
  Gives the agent a persistent, correct understanding of the combine dataset
  so it never has to re-guess column names, units, or structure. Covers column
  definitions, data types, and the canonical position normalization table.
---

# Skill: Combine Data Schema

## Purpose
Gives the agent a persistent, correct understanding of the combine dataset so it never
has to re-guess column names, units, or structure in a new session.

## Source file
- `data/players.csv` — single consolidated sheet (one row per player).
- Enriched output: `data/players_with_percentiles.csv` — same rows + derived percentile columns.

## Columns

| Column              | Type    | Notes                                                                          |
|---------------------|---------|--------------------------------------------------------------------------------|
| player_id           | string  | Stable unique key. Do not reuse across different players.                      |
| player_name         | string  | Display name. Not used as the join key — player_id is.                        |
| year                | integer | Combine year. Used for context; percentiles are computed across all classes.   |
| POS                 | string  | Raw position abbreviation — NOT used for grouping. Use canonical_position.     |
| HT                  | float   | Height of player, gives context to composite scores.                           |
| WT                  | float   | Weight of player, gives context to composite scores.                           |
| ARM                 | float   | Arm length — store for research, no need to display.                           |
| HAND                | float   | Hand size — store for research, no need to display.                            |
| 40 yd               | float   | Official 40-yard dash time per NFL combine or Pro Day.                         |
| vert                | float   | Official vertical jump distance per NFL combine or Pro Day.                    |
| broad               | float   | Official broad jump distance per NFL combine or Pro Day.                       |
| explosive_score     | float   | (vert + 3.5×broad) × (weight/height) / 3000                                  |
| SPEED               | float   | 100 × (1 − (40 time / (0.0397×(weight/height) + 3.092)))                     |
| DYNAMIC SPEED       | float   | 100 × (1 − (3 Cone / (0.0573×(weight/height) + 4.8403)))                     |

## Derived columns (written by data pipeline, never entered manually)

| Column                   | Type  | Notes                                              |
|--------------------------|-------|----------------------------------------------------|
| canonical_position       | string| Mapped from POS using the normalization table below|
| explosive_percentile     | float | 0–100, recomputed whenever the pool changes        |
| speed_percentile         | float | 0–100, recomputed whenever the pool changes        |
| dynamic_speed_percentile | float | 0–100, recomputed whenever the pool changes        |

---

## Position Normalization (Canonical Mapping)

The raw `POS` column is **not reliable** for grouping or percentile comparison —
the same position has been recorded under different abbreviations across years
(e.g., interior defensive linemen logged as NT, DT, or DL depending on the year).
Left unfixed, this silently fragments what should be one group into several small ones,
which quietly distorts every percentile computed from it.

Every downstream step (percentile grouping, comp matching) uses `canonical_position`,
**never** the raw `POS` field.

### Canonical Mapping Table

Maintain this table as the single source of truth. Ask about new mappings — do not infer on your own.

| canonical_position | Accepted raw variants       |
|--------------------|-----------------------------|
| DT                 | DT, NT, DL, IDL             |
| EDGE               | ED, OLB                     |
| OL                 | OG, OC, IOL, OT             |
| CB                 | CB, BC, DC                  |
| S                  | S, DB, DS, SS, FS           |
| LB                 | LB, ILB                     |
| WR                 | WR                          |
| RB                 | RB                          |
| TE                 | TE                          |
| QB                 | QB                          |
| K                  | K                           |
| P                  | P                           |

### Rule for the agent

- On ingestion, map every raw `POS` value to its `canonical_position` using the
  table above — **exact match only, no fuzzy inference**.
- If a raw value appears that isn't in the table, **stop and flag it** rather than
  guessing a mapping or dropping the row.
- Never edit `canonical_position` directly on individual rows — fix the mapping table
  and re-run normalization instead.

---

## Rules for the agent

1. Never hand-edit the `_percentile` columns — they're always derived, never source data.
2. When new combine participants are added, append rows with `player_id`, `POS`,
   and the three raw scores. Percentiles are recalculated by the percentile skill.
3. If a player is missing one of the three raw scores, leave that cell blank —
   don't impute a value.
4. Treat `player_id` as immutable once assigned.
