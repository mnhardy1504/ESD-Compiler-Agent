---
name: percentile-comp-methodology
description: >
  Locks in exactly how percentile ranks and "closest comp" matches are computed,
  so the logic stays consistent as new combine classes are added. Covers
  position-normalized percentile formula, Euclidean distance comp matching,
  weighting choices, and null/missing metric handling.
---

# Skill: Percentile & Comp Methodology

## Purpose
Locks in exactly how percentile ranks and "closest comp" matches are computed, so the
logic stays consistent as new combine classes are added and isn't silently re-decided
by the agent from session to session.

---

## Percentile Calculation

### 1. Normalize within canonical position group — not the whole pool
A WR's speed percentile must be computed against other WRs, not against OL. Group
by `canonical_position` (see schema skill's position normalization mapping) —
**never** the raw `POS` field, since raw values include inconsistent abbreviations
(e.g., NT/DT/DL) that would otherwise fragment one true group into several.

### 2. Recompute on every data update — not incrementally
Percentile rank is a function of the *current* full pool for that canonical position.
When a new combine class is added, recompute from scratch for the affected position
groups rather than patching old percentiles.

### 3. Formula
```
percentile = (rank of player's raw score within canonical position group)
           / (count of players in that position group with a non-null value for that metric)
           × 100
```
- Use the **"percentage of players at or below this score"** convention.
- Ties share the same percentile using the **average rank method** — consistent always.
- For explosive_score and dynamic_speed_score: higher raw score = higher percentile.
- For speed_score (SPEED): higher raw score = higher percentile (already sign-adjusted in formula).

### 4. Missing metrics
If a player is missing a raw score for one of the three metrics, leave that
percentile **null**. Do not zero-fill or use position average as a stand-in.

---

## Comp Matching

### 1. Input
The three percentiles (explosive, speed, dynamic speed) for the queried player.

### 2. Distance metric — Euclidean (default)
```
distance = sqrt(
  (p1_explosive − p2_explosive)²
  + (p1_speed − p2_speed)²
  + (p1_dynamic − p2_dynamic)²
)
```

### 3. Weighting
- **Default: equal weight across all three metrics.**
- If a custom weight multiplier is needed (e.g., speed weighted 2×), apply it before
  summing squares and document it here so weights don't drift.

### 4. Same canonical-position constraint
Only compare within the same `canonical_position` group. A comp must be someone in a
comparable role — not just someone with similar raw numbers across different positions.

### 5. Same draft-class exclusion
**Never return a comp from the same draft year as the queried player.**
Players in the same combine class share the same data-collection conditions — and
critically, any missing metrics (e.g., no 3-cone data for a full class) will cause
same-class players to artificially cluster together, producing comps that reflect
shared data gaps rather than true athletic similarity. Comps must always come from
a prior year.

### 5. Handling missing metrics in comparisons
**Option (b) — partial distance with annotation:**
- If either player is missing one of the three percentiles, compute distance on the
  available dimensions only and clearly note that the comp is based on fewer than three
  dimensions (e.g., "2-of-3 metrics: explosive + speed only").
- This applies to the 2025 and 2026 combine classes, which have no dynamic speed data.
- Comps matched on partial metrics are still surfaced but annotated; they are ranked
  among other partial-metric comps only (not mixed with full-3D comps without disclosure).

### 6. Output
Return the **top 3 closest matches** (lowest distance score) by default, along with:
- The distance value (so it's visible how close each comp actually is)
- The number of dimensions used in the match
- Each comp's name, canonical position, year, and the three percentile values

---

## Locked Decisions

| Decision | Choice |
|----------|--------|
| Position scope | Canonical-position-grouped (not pool-wide) |
| Metric weighting | Equal across all three |
| Adjacent position comps | Not allowed — strictly same canonical position |
| Tie-breaking in percentiles | Average rank method |
| Missing metric handling | Option (b): partial distance with annotation |
