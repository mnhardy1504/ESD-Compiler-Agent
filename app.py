"""
E-S-D Compiler Agent — Streamlit UI

Reads the already-computed players_with_percentiles.csv (written by orchestrator.py)
and provides a lookup: type a player name, get their closest comps + a comparison
bar chart. This file does NOT recompute percentiles or re-run the pipeline — it only
reads the finished output, per the split documented in the schema/percentile skills.
"""

import difflib

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA_PATH = "data/players_with_percentiles.csv"
METRICS = ["explosive_percentile", "speed_percentile", "dynamic_speed_percentile"]
REQUIRED_METRICS = ["explosive_percentile", "speed_percentile"]  # mandatory to be queryable/eligible
OPTIONAL_METRICS = ["dynamic_speed_percentile"]  # included in distance only if both sides have it
METRIC_LABELS = {
    "explosive_percentile": "Explosive",
    "speed_percentile": "Speed",
    "dynamic_speed_percentile": "Dynamic Speed",
}
MAX_COMPS = 3

# Fixed color for the queried player, consistent shades for comps (closest -> least close)
PLAYER_COLOR = "#1a1a2e"
COMP_COLORS = ["#e94560", "#f39c6b", "#f7c59f"]


@st.cache_data
def load_data() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH)


def find_name_matches(df: pd.DataFrame, query: str, limit: int = 5) -> list[str]:
    """Exact substring match first, then fuzzy fallback for typos — no LLM call needed."""
    query_lower = query.strip().lower()
    names = df["player_name"].dropna().unique().tolist()

    substring_hits = [n for n in names if query_lower in n.lower()]
    if substring_hits:
        return sorted(substring_hits)[:limit]

    return difflib.get_close_matches(query, names, n=limit, cutoff=0.6)


def is_eligible(row: pd.Series) -> bool:
    """Explosive + speed are mandatory; dynamic speed is optional."""
    return row[REQUIRED_METRICS].notna().all()


def rms_distance(a: pd.Series, b: pd.Series) -> tuple[float, int]:
    """
    Root-mean-square distance over whichever metrics both players share (always
    explosive + speed; dynamic speed only if both have it). RMS — not a raw sum of
    squared differences — keeps a 2-metric comparison from looking artificially closer
    than a 3-metric one just because it's averaging over fewer terms.
    Returns (distance, metric_count_used).
    """
    shared = [m for m in METRICS if pd.notna(a[m]) and pd.notna(b[m])]
    diffs = (a[shared].to_numpy(dtype=float) - b[shared].to_numpy(dtype=float)) ** 2
    return (diffs.mean()) ** 0.5, len(shared)


def get_comps(df: pd.DataFrame, player_row: pd.Series) -> pd.DataFrame:
    """
    Comp matching per the percentile methodology skill:
    - same canonical_position only
    - exclude the player themselves
    - eligibility: explosive + speed mandatory, dynamic speed optional
    - RMS distance over shared metrics (2 or 3), so partial comps aren't penalized
      or favored just for having fewer dimensions
    - top 3 closest, each flagged with how many metrics it was based on
    """
    position = player_row["canonical_position"]

    if not is_eligible(player_row):
        return pd.DataFrame()  # missing explosive or speed — can't comp at all

    pool = df[
        (df["canonical_position"] == position)
        & (df["player_id"] != player_row["player_id"])
    ]
    pool = pool[pool.apply(is_eligible, axis=1)]

    if pool.empty:
        return pool

    results = pool.apply(lambda row: rms_distance(player_row, row), axis=1)
    pool = pool.copy()
    pool["distance"] = [r[0] for r in results]
    pool["metrics_used"] = [r[1] for r in results]

    return pool.sort_values("distance").head(MAX_COMPS)


def bar_values_and_text(row: pd.Series) -> tuple[list, list[str]]:
    """None for a missing metric renders as a gap, never a 0-height bar (0th percentile)."""
    values = [None if pd.isna(row[m]) else row[m] for m in METRICS]
    text = ["—" if v is None else f"{v:.0f}" for v in values]
    return values, text


def build_chart(player_row: pd.Series, comps: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    x_labels = [METRIC_LABELS[m] for m in METRICS]

    values, text = bar_values_and_text(player_row)
    fig.add_trace(
        go.Bar(
            name=player_row["player_name"],
            x=x_labels,
            y=values,
            marker_color=PLAYER_COLOR,
            text=text,
            textposition="outside",
        )
    )

    for i, (_, comp) in enumerate(comps.iterrows()):
        label = f"{comp['player_name']} ({comp['distance']:.1f} away, {comp['metrics_used']} metrics)"
        values, text = bar_values_and_text(comp)
        fig.add_trace(
            go.Bar(
                name=label,
                x=x_labels,
                y=values,
                marker_color=COMP_COLORS[i % len(COMP_COLORS)],
                text=text,
                textposition="outside",
            )
        )

    fig.update_layout(
        barmode="group",
        yaxis=dict(range=[0, 100], title="Percentile"),
        title=f"{player_row['player_name']} ({player_row['canonical_position']}) vs. closest comps",
        legend=dict(orientation="h", yanchor="bottom", y=-0.3),
    )
    return fig


def main():
    st.set_page_config(page_title="E-S-D Compiler Agent", layout="centered")
    st.title("E-S-D Compiler Agent")
    st.caption(
        "Find a prospect's closest athletic comps by percentile rank across "
        "explosiveness, speed, and dynamic speed."
    )

    df = load_data()

    query = st.text_input("Player name", placeholder="e.g. Dillon Thieneman")
    if not query:
        st.stop()

    matches = find_name_matches(df, query)
    if not matches:
        st.warning("No matching player found. Check spelling and try again.")
        st.stop()

    selected_name = matches[0] if len(matches) == 1 else st.selectbox(
        "Multiple matches — pick one:", matches
    )

    candidates = df[df["player_name"] == selected_name]
    if len(candidates) > 1:
        # same name, different draft class — disambiguate with year + school
        candidates = candidates.copy()
        candidates["_label"] = (
            candidates["player_name"]
            + " — "
            + candidates["year"].astype(str)
            + " — "
            + candidates["School"].fillna("")
        )
        chosen_label = st.selectbox("Same name, multiple entries:", candidates["_label"])
        player_row = candidates[candidates["_label"] == chosen_label].iloc[0]
    else:
        player_row = candidates.iloc[0]

    if not is_eligible(player_row):
        missing = [METRIC_LABELS[m] for m in REQUIRED_METRICS if pd.isna(player_row[m])]
        st.warning(
            f"{player_row['player_name']} is missing: {', '.join(missing)}. "
            "Explosive and speed are both required to generate comps."
        )
        st.stop()

    if pd.isna(player_row["dynamic_speed_percentile"]):
        st.caption(
            "⚠️ No dynamic speed score on file for this player — comps are based on "
            "explosive + speed only (2 metrics)."
        )

    comps = get_comps(df, player_row)
    if comps.empty:
        st.info(f"No eligible comps found for {player_row['canonical_position']} with complete data.")
        st.stop()

    st.plotly_chart(build_chart(player_row, comps), use_container_width=True)

    st.subheader("Closest comps")
    display_cols = ["player_name", "year", "School"] + METRICS + ["distance", "metrics_used"]
    st.dataframe(
        comps[display_cols].rename(
            columns={**METRIC_LABELS, "distance": "Distance", "metrics_used": "Metrics used"}
        ),
        hide_index=True,
    )


if __name__ == "__main__":
    main()
