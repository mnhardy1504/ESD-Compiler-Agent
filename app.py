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


def get_comps(df: pd.DataFrame, player_row: pd.Series) -> pd.DataFrame:
    """
    Comp matching per the percentile methodology skill:
    - same canonical_position only
    - exclude the player themselves
    - require all three percentiles present on both sides (option (a): exclude rather
      than compute on a partial subset)
    - Euclidean distance across the three percentiles, equal weighting
    - top 3 closest
    """
    position = player_row["canonical_position"]

    if player_row[["explosive_percentile", "speed_percentile"]].isna().any():
        return pd.DataFrame()  # require at least explosive and speed

    pool = df[
        (df["canonical_position"] == position)
        & (df["player_id"] != player_row["player_id"])
        & (pd.to_numeric(df["year"], errors='coerce').fillna(0) < int(player_row.get("year", 0) or 0))
    ].dropna(subset=["explosive_percentile", "speed_percentile"])

    if pool.empty:
        return pool

    import numpy as np
    diffs = pool[METRICS].to_numpy() - player_row[METRICS].to_numpy(dtype=float)
    pool = pool.copy()
    pool["distance"] = np.nansum(diffs ** 2, axis=1) ** 0.5

    return pool.sort_values("distance").head(MAX_COMPS)


def build_chart(player_row: pd.Series, comps: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    x_labels = [METRIC_LABELS[m] for m in METRICS]

    fig.add_trace(
        go.Bar(
            name=player_row["player_name"],
            x=x_labels,
            y=player_row[METRICS].tolist(),
            marker_color=PLAYER_COLOR,
            text=[f"{v:.0f}" for v in player_row[METRICS]],
            textposition="outside",
        )
    )

    for i, (_, comp) in enumerate(comps.iterrows()):
        label = f"{comp['player_name']} ({comp['distance']:.1f} away)"
        fig.add_trace(
            go.Bar(
                name=label,
                x=x_labels,
                y=comp[METRICS].tolist(),
                marker_color=COMP_COLORS[i % len(COMP_COLORS)],
                text=[f"{v:.0f}" for v in comp[METRICS]],
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

    if player_row[["explosive_percentile", "speed_percentile"]].isna().any():
        missing = [METRIC_LABELS[m] for m in ["explosive_percentile", "speed_percentile"] if pd.isna(player_row[m])]
        st.warning(
            f"{player_row['player_name']} is missing: {', '.join(missing)}. "
            "Comps require at least Explosive and Speed metrics."
        )
        st.stop()
        
    if pd.isna(player_row["dynamic_speed_percentile"]):
        st.info("Note: Player is missing Dynamic Speed. Comps will be matched on Explosive and Speed only.")

    comps = get_comps(df, player_row)
    if comps.empty:
        st.info(f"No eligible comps found for {player_row['canonical_position']} with complete data.")
        st.stop()

    st.plotly_chart(build_chart(player_row, comps), use_container_width=True)

    st.subheader("Closest comps")
    display_cols = ["player_name", "year", "School"] + METRICS + ["distance"]
    st.dataframe(
        comps[display_cols].rename(columns={**METRIC_LABELS, "distance": "Distance"}),
        hide_index=True,
    )


if __name__ == "__main__":
    main()
