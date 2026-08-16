# Skill: Percentile & Comp Methodology

## Purpose
Locks in exactly how percentile ranks and "closest comp" matches are computed, so the
logic stays consistent as new combine classes are added and isn't silently re-decided
by the agent from session to session.

## Percentile calculation

1. **Normalize within position group, not the whole pool.**
   A WR's speed percentile should be computed against other WRs, not against OL. Group
   by `position_canonical` (see schema skill's position normalization mapping) —
   **never** the raw `position` field, since raw values include inconsistent
   abbreviations (e.g., NT/DT/DL) that would otherwise fragment one true group into
   several. (If you want a secondary "pool-wide" percentile for cross-position context
   later, that's a separate column — don't conflate the two.)

2. **Recompute on every data update, not incrementally.**
   Percentile rank is a function of the *current* full pool for that position. When a
   new combine class is added, recompute from scratch for the affected position groups
   rather than trying to patch old percentiles. This keeps the numbers always correct,
   at the cost of a full recompute — which is cheap given the dataset size.

3. **Formula:**
   `percentile = (rank of player's raw score within position group) / (count of players
   in that position group with a non-null value for that metric) * 100`
   Use the standard "percentage of players at or below this score" convention. Decide
   once whether ties share the same percentile (recommended: yes, average rank method)
   and keep it consistent.

4. **Missing metrics:** if a player is missing a raw score for one of the three metrics,
   leave that percentile null. Don't zero-fill or use position average as a stand-in —
   it will distort comp matching (see below).

## Comp matching

1. **Eligibility — two metrics are mandatory, one is optional.**
   `explosive_percentile` and `speed_percentile` must both be present for a player to
   be queryable at all, or to appear as a candidate comp. `dynamic_speed_percentile` is
   optional — a player missing only dynamic speed is still eligible, just compared on
   fewer dimensions (see below). A player missing explosive or speed is excluded
   entirely, same as before — that floor doesn't move.

   This matters given the dataset skews heavily incomplete on dynamic speed (roughly
   4,464 of 7,207 players have explosive + speed only, vs. 2,497 with all three) —
   requiring all three would exclude the majority of the pool from ever being shown as
   a comp.

2. **Distance metric — RMS, not raw Euclidean sum, so 2-metric and 3-metric comps stay
   comparable.**
   For each candidate, use whichever metrics *both* the queried player and the
   candidate have in common (always at least explosive + speed; dynamic speed included
   only if both sides have it). Use root-mean-square distance, not a raw sum of squared
   differences:
   `distance = sqrt( (sum of squared differences over shared metrics) / (count of shared metrics) )`
   Dividing by the metric count is what keeps a 2-dimension comparison from looking
   artificially closer than a 3-dimension one just because it's summing fewer terms —
   without this, players who happen to be missing dynamic speed would systematically
   look like better comps than they really are.

3. **Weighting (decide and document your choice):**
   - Default: equal weight across whichever metrics are being compared for that pair.
   - If you'd rather weight one metric more heavily (e.g., speed matters more for your
     evaluation), apply a multiplier to that term before averaging, and note the
     weights here so they don't drift between sessions.

4. **Same-position constraint:** only compare within the same position group by
   default. A comp should be someone in a comparable role, not just someone with
   similar raw numbers across different positions.

5. **Flag partial comps in the output.** Every comp result should note how many
   metrics it was based on (2 or 3) — don't present a 2-metric comp as if it were
   evaluated on the same basis as a 3-metric one. This is a transparency requirement,
   not optional polish: the whole point of showing distance is letting you judge comp
   quality, and a hidden dimension count undermines that.

6. **Output:** return the top 3 closest matches (lowest distance) by default, along
   with the distance value and the metric count used, so it's visible both how close
   each comp is and how much data that closeness is based on.

## Open decisions to confirm before locking this in
- [ ] Position-grouped vs. pool-wide percentiles — confirmed as position-grouped above;
      revisit if you want a cross-position view later.
- [ ] Equal weighting vs. custom weights across the three metrics.
- [ ] Whether to allow comps across adjacent/similar positions (e.g., CB vs. S) or
      strictly same position.
- [x] Missing-metric handling — confirmed above: explosive + speed mandatory, dynamic
      speed optional, RMS distance over shared metrics, partial comps flagged in output.
