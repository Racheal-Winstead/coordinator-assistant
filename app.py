from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


DATA_PATH = Path(__file__).with_name("netflix_titles.csv")

st.set_page_config(
    page_title="StreamVault coordinator",
    page_icon=":material/video_library:",
    layout="wide",
)

st.markdown(
    """
    <style>
    .st-key-catalog_results_section [role="columnheader"],
    .st-key-catalog_results_section [role="gridcell"] {
        font-size: 17px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_catalog(path: Path) -> pd.DataFrame:
    catalog = pd.read_csv(path)
    catalog["date_added"] = pd.to_datetime(
        catalog["date_added"].str.strip(), format="%B %d, %Y", errors="coerce"
    )
    catalog["genres"] = catalog["listed_in"].fillna("").str.split(", ")
    catalog["countries"] = catalog["country"].fillna("").str.split(", ")
    return catalog


def unique_values(series: pd.Series) -> list[str]:
    return sorted(
        {
            value
            for items in series
            for value in items
            if isinstance(value, str) and value.strip()
        }
    )


def apply_filters(
    catalog: pd.DataFrame,
    query: str,
    content_types: list[str],
    genres: list[str],
    countries: list[str],
    ratings: list[str],
    year_range: tuple[int, int],
) -> pd.DataFrame:
    mask = catalog["release_year"].between(*year_range)
    if query:
        searchable = catalog[["title", "description", "director", "cast"]].fillna("")
        mask &= searchable.apply(
            lambda column: column.str.contains(query, case=False, regex=False)
        ).any(axis=1)
    if content_types:
        mask &= catalog["type"].isin(content_types)
    if genres:
        mask &= catalog["genres"].apply(lambda items: bool(set(items) & set(genres)))
    if countries:
        mask &= catalog["countries"].apply(
            lambda items: bool(set(items) & set(countries))
        )
    if ratings:
        mask &= catalog["rating"].isin(ratings)
    return catalog.loc[mask].copy()


def count_list_values(frame: pd.DataFrame, column: str, label: str) -> pd.DataFrame:
    values = frame[column].explode()
    values = values[values.notna() & values.ne("")]
    return values.value_counts().rename_axis(label).reset_index(name="Titles")


def build_meeting_summary(frame: pd.DataFrame, recent_days: int) -> str:
    if frame.empty:
        return "No titles match the current filters."

    latest_date = frame["date_added"].max()
    recent_cutoff = latest_date - pd.Timedelta(days=recent_days)
    recent_count = int(frame["date_added"].ge(recent_cutoff).sum())
    top_genres = count_list_values(frame, "genres", "Genre").head(3)["Genre"].tolist()
    top_countries = count_list_values(frame, "countries", "Country").head(3)["Country"].tolist()
    movie_count = int(frame["type"].eq("Movie").sum())
    show_count = int(frame["type"].eq("TV Show").sum())

    return (
        f"## StreamVault catalog briefing\n\n"
        f"The current view contains **{len(frame):,} titles**: **{movie_count:,} movies** "
        f"and **{show_count:,} TV shows**. The most represented genres are "
        f"**{', '.join(top_genres) or 'not available'}**, while the leading production "
        f"countries are **{', '.join(top_countries) or 'not available'}**. "
        f"Using **{latest_date:%B %d, %Y}** as the catalog's latest recorded addition, "
        f"**{recent_count:,} titles** were added in the preceding {recent_days} days.\n\n"
        f"_This briefing reflects the active filters and should be reviewed alongside the "
        f"representation and data-quality views._"
    )


catalog = load_catalog(DATA_PATH)
st.session_state.setdefault("work_queue", {})

st.title("StreamVault coordinator")
st.caption(
    "Find titles, monitor representation, review recent additions, and prepare meeting-ready summaries."
)

all_genres = unique_values(catalog["genres"])
all_countries = unique_values(catalog["countries"])
all_ratings = sorted(catalog["rating"].dropna().unique().tolist())
min_year = int(catalog["release_year"].min())
max_year = int(catalog["release_year"].max())

with st.sidebar:
    st.header("Catalog filters")
    query = st.text_input(
        "Search catalog",
        placeholder="Title, description, director, or cast",
        icon=":material/search:",
    )
    selected_types = st.pills(
        "Content type", ["Movie", "TV Show"], selection_mode="multi"
    )
    selected_genres = st.multiselect("Genres", all_genres, placeholder="All genres")
    selected_countries = st.multiselect(
        "Countries and regions", all_countries, placeholder="All countries"
    )
    selected_ratings = st.multiselect("Ratings", all_ratings, placeholder="All ratings")
    selected_years = st.slider(
        "Release years",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year),
    )
    if st.button("Reset filters", icon=":material/restart_alt:", width="stretch"):
        for key in list(st.session_state):
            if key != "work_queue":
                del st.session_state[key]
        st.rerun()
    st.caption("Filters apply to every dashboard view.")

filtered = apply_filters(
    catalog,
    query,
    selected_types,
    selected_genres,
    selected_countries,
    selected_ratings,
    selected_years,
)

latest_catalog_date = catalog["date_added"].max()
recent_90 = filtered["date_added"].ge(latest_catalog_date - pd.Timedelta(days=90)).sum()
country_count = len(unique_values(filtered["countries"])) if not filtered.empty else 0
genre_count = len(unique_values(filtered["genres"])) if not filtered.empty else 0

with st.container(horizontal=True):
    st.metric("Matching titles", f"{len(filtered):,}", border=True)
    st.metric("Countries represented", f"{country_count:,}", border=True)
    st.metric("Genres represented", f"{genre_count:,}", border=True)
    st.metric("Added in latest 90 days", f"{recent_90:,}", border=True)

overview_tab, recent_tab, quality_tab, organize_tab = st.tabs(
    [
        ":material/analytics: Overview",
        ":material/new_releases: Recent additions",
        ":material/fact_check: Data quality",
        ":material/bookmarks: Organize",
    ]
)

with overview_tab:
    left, right = st.columns(2)
    genre_counts = count_list_values(filtered, "genres", "Genre").head(12)
    country_counts = count_list_values(filtered, "countries", "Country").head(12)

    with left.container(border=True):
        st.subheader("Genre representation")
        if genre_counts.empty:
            st.info("No genre data matches the current filters.", icon=":material/info:")
        else:
            st.bar_chart(
                genre_counts, x="Genre", y="Titles", horizontal=True, sort="-Titles"
            )

    with right.container(border=True):
        st.subheader("Country representation")
        if country_counts.empty:
            st.info("No country data matches the current filters.", icon=":material/info:")
        else:
            st.bar_chart(
                country_counts, x="Country", y="Titles", horizontal=True, sort="-Titles"
            )

    with st.container(border=True):
        st.subheader("Meeting briefing")
        summary_window = st.segmented_control(
            "Recent-addition window",
            [30, 90, 365],
            default=90,
            format_func=lambda days: f"{days} days",
            key="summary_window",
        )
        briefing = build_meeting_summary(filtered, summary_window)
        st.markdown(briefing)
        st.download_button(
            "Download briefing",
            briefing,
            file_name="streamvault_meeting_briefing.md",
            mime="text/markdown",
            icon=":material/download:",
        )

    with st.container(border=True, key="catalog_results_section"):
        st.subheader("Catalog results")
        st.caption(f"Showing {len(filtered):,} titles. Sort columns or narrow the sidebar filters.")
        display_columns = [
            "title", "type", "release_year", "rating", "duration", "country",
            "listed_in", "date_added",
        ]
        st.dataframe(
            filtered[display_columns],
            hide_index=True,
            column_config={
                "title": "Title",
                "type": "Type",
                "release_year": st.column_config.NumberColumn("Release year", format="%d"),
                "rating": "Rating",
                "duration": "Duration",
                "country": "Country",
                "listed_in": "Genres",
                "date_added": st.column_config.DatetimeColumn("Date added", format="MMM D, YYYY"),
            },
            key="catalog_results",
        )
        st.download_button(
            "Download filtered catalog",
            filtered.drop(columns=["genres", "countries"]).to_csv(index=False),
            file_name="streamvault_filtered_catalog.csv",
            mime="text/csv",
            icon=":material/download:",
        )

with recent_tab:
    st.subheader("Recent additions tracker")
    st.caption(
        f"Recency is measured against the latest date in this dataset: {latest_catalog_date:%B %d, %Y}."
    )
    recent_window = st.segmented_control(
        "Time window", [30, 90, 365], default=90,
        format_func=lambda days: f"{days} days", key="recent_window",
    )
    recent_cutoff = latest_catalog_date - pd.Timedelta(days=recent_window)
    recent_titles = filtered[filtered["date_added"].ge(recent_cutoff)].sort_values(
        "date_added", ascending=False
    )
    if recent_titles.empty:
        st.info("No recent titles match the current filters.", icon=":material/info:")
    else:
        monthly = (
            recent_titles.assign(Month=recent_titles["date_added"].dt.to_period("M").dt.to_timestamp())
            .groupby(["Month", "type"]).size().reset_index(name="Titles")
        )
        st.bar_chart(monthly, x="Month", y="Titles", color="type", stack=True)
        st.dataframe(
            recent_titles[["title", "type", "date_added", "country", "listed_in"]],
            hide_index=True,
            column_config={
                "title": "Title", "type": "Type",
                "date_added": st.column_config.DatetimeColumn("Date added", format="MMM D, YYYY"),
                "country": "Country", "listed_in": "Genres",
            },
        )

with quality_tab:
    st.subheader("Catalog quality checks")
    missing_fields = ["director", "cast", "country", "date_added", "rating", "duration"]
    quality_rows = []
    for field in missing_fields:
        missing = int(catalog[field].isna().sum())
        quality_rows.append({
            "Field": field.replace("_", " ").capitalize(),
            "Missing values": missing,
            "Completeness": 1 - (missing / len(catalog)),
        })
    quality = pd.DataFrame(quality_rows)
    duplicate_titles = int(catalog.duplicated(subset=["title", "type"], keep=False).sum())
    with st.container(horizontal=True):
        st.metric("Rows checked", f"{len(catalog):,}", border=True)
        st.metric("Potential duplicate rows", f"{duplicate_titles:,}", border=True)
        st.metric("Missing country", f"{catalog['country'].isna().sum():,}", border=True)
        st.metric("Missing date added", f"{catalog['date_added'].isna().sum():,}", border=True)
    st.dataframe(
        quality,
        hide_index=True,
        column_config={
            "Field": "Field",
            "Missing values": st.column_config.NumberColumn("Missing values", format="%d"),
            "Completeness": st.column_config.ProgressColumn(
                "Completeness", min_value=0, max_value=1, format="percent"
            ),
        },
    )
    if duplicate_titles:
        with st.expander("Review possible duplicate titles", icon=":material/content_copy:"):
            duplicates = catalog[catalog.duplicated(["title", "type"], keep=False)].sort_values("title")
            st.dataframe(
                duplicates[["title", "type", "release_year", "country"]], hide_index=True
            )

with organize_tab:
    st.subheader("Meeting work queue")
    st.caption("Labels are kept for this browser session and do not alter the source CSV.")
    title_options = filtered.sort_values("title")["title"].tolist()
    if not title_options:
        st.info("No titles are available to organize with the current filters.", icon=":material/info:")
    else:
        with st.form("queue_form", border=True):
            queue_title = st.selectbox("Title", title_options)
            queue_label = st.selectbox(
                "Label", ["Review", "Feature in meeting", "Needs metadata", "Follow up"]
            )
            queue_note = st.text_input("Note", placeholder="Optional context for the team")
            add_to_queue = st.form_submit_button(
                "Save to work queue", icon=":material/bookmark_add:"
            )
        if add_to_queue:
            st.session_state.work_queue[queue_title] = {
                "Title": queue_title, "Label": queue_label, "Note": queue_note,
            }
            st.toast(f"Saved {queue_title} to the work queue.", icon=":material/check_circle:")

    if st.session_state.work_queue:
        queue = pd.DataFrame(st.session_state.work_queue.values())
        st.dataframe(queue, hide_index=True)
        st.download_button(
            "Download work queue", queue.to_csv(index=False),
            file_name="streamvault_work_queue.csv", mime="text/csv",
            icon=":material/download:",
        )
    else:
        st.caption("Your work queue is empty.")
