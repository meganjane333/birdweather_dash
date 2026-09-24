from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


API_URL = "https://app.birdweather.com/graphql"
STATION_IDS = ["12521", "8106", "12664"]
REFRESH_SECONDS = 30
MIN_CONFIDENCE = 0.50
MIN_PROBABILITY = 0.50
LOCAL_TZ = ZoneInfo("Europe/London")
REPEAT_WINDOW_MINUTES = 5


QUERY = """
query LiveDetections(
  $stationIds: [ID!],
  $period: InputDuration,
  $first: Int,
  $confidenceGte: Float,
  $probabilityGte: Float
) {
  detections(
    stationIds: $stationIds,
    period: $period,
    first: $first,
    confidenceGte: $confidenceGte,
    probabilityGte: $probabilityGte
  ) {
    totalCount
    speciesCount
    edges {
      node {
        id
        timestamp
        confidence
        probability
        score
        species {
          commonName
          scientificName
          imageUrl
        }
        station {
          id
          name
        }
      }
    }
  }
}
"""


st.set_page_config(
    page_title="Harper Adams University Live Bird Detections",
    page_icon="🐦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        .block-container {
            max-width: 1450px !important;
            width: 94% !important;
            padding-top: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
            padding-bottom: 4rem;
            }

        h1 {margin-bottom: 0.1rem; font-size: 2rem !important;}
        h2, h3 {font-size: 1.5rem !important;}
        .subtitle {color: #52645a; font-size: 1.rem; margin-bottom: 1.35rem;}
        .live-dot {
            display: inline-block; width: 0.65rem; height: 0.65rem;
            border-radius: 50%; background: #2e8b57; margin-right: 0.4rem;
            }
        [data-testid="stMetric"] {  background: #f0f2f1;  border: 1px solid #d5dbd7;  border-radius: 0.8rem;  padding: 0.75rem 1rem;}
        [data-testid="stMetric"] * {  color: #1f2933 !important;}
        [data-testid="stMetricValue"] {font-size: 2rem !important;}
        [data-testid="stMetricLabel"] p {font-size: 1.15rem !important;}

        .species-name {font-size: 2rem; font-weight: 700; line-height: 1.1;}
        .scientific-name {font-size: 1.25rem; font-style: italic; color: #52645a; margin-bottom: 0.8rem;}

        [data-testid="stCaptionContainer"] p {font-size: 1rem !important;}

        .table-scroll {  max-height: 420px;  overflow-y: auto;  border: 1px solid #c8ceca;  border-radius: 0.5rem;}

        .event-table {  width: 100%;  border-collapse: collapse;  font-size: 18px;}

        .event-table th {  position: sticky;  top: 0;  z-index: 1;  padding: 0.75rem;  text-align: left;  background: #012169;
            color: #ffffff;  font-size: 18px;  font-weight: 700;  border-bottom: 2px solid #29382f;}

        .event-table td {  padding: 0.7rem 0.75rem;  background: #ffffff;  color: #1f2933;  font-size: 18px;  border-bottom: 1px solid #dfe4e1;}

        .event-table tr:nth-child(even) td {  background: #eef3fa;}

        .event-table tr:hover td {background: #e2ebe5;}

        .bird-count {
            text-align: center;
            }

        .bird-count-number {
            color: #012169;
            font-size: 2rem;
            font-weight: 700;
            line-height: 1;
            }

        .bird-count-label {
            color: #012169;
            font-size: 1rem;
            margin-top: 0.25rem;
            }

            .bird-card-text {
  line-height: 1.1;
}

            .bird-card-name {
            color: #1f2933;
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.1;
            margin: 0 0 0.15rem 0;
            }

            .bird-card-scientific {
            color: #52645a;
            font-size: 0.95rem;
            font-style: italic;
            line-height: 1.1;
            margin: 0 0 0.25rem 0;
            }

            .bird-card-events {
            color: #012169;
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.1;
            margin: 0;
            }

            .event-table td:nth-child(4) {
                font-style: italic;
            }

            .status-heading {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 1rem;
            font-size: 1.05rem;
            margin-bottom: 0.5rem;
            }

            .last-checked {
            color: #52645a;
            white-space: nowrap;
            }

        footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)


def request_detections(period: dict, limit: int = 100) -> dict:
    variables = {
        "stationIds": STATION_IDS,
        "period": period,
        "first": limit,
        "confidenceGte": MIN_CONFIDENCE,
        "probabilityGte": MIN_PROBABILITY,
    }
    response = requests.post(
        API_URL,
        json={"query": QUERY, "variables": variables},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0].get("message", "BirdWeather API error"))
    return payload["data"]["detections"]


def flatten_detections(result: dict) -> pd.DataFrame:
    rows = []
    for edge in result.get("edges", []):
        item = edge["node"]
        species = item.get("species") or {}
        station = item.get("station") or {}
        rows.append(
            {
                "record_id": item.get("id"),
                "timestamp": item.get("timestamp"),
                "common_name": species.get("commonName", "Unknown species"),
                "scientific_name": species.get("scientificName", ""),
                "image_url": species.get("imageUrl"),
                "station_id": station.get("id"),
                "station_name": station.get("name", f"Station {station.get('id', 'Unknown')}"),
                "confidence": item.get("confidence"),
                "probability": item.get("probability"),
                "score": item.get("score"),
            }
        )

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True).dt.tz_convert(LOCAL_TZ)
        frame = frame.sort_values("timestamp", ascending=False).reset_index(drop=True)
    return frame

def collapse_repeat_detections(
    frame: pd.DataFrame,
    window_minutes: int = REPEAT_WINDOW_MINUTES
) -> pd.DataFrame:

    if frame.empty:
        return frame

    frame = frame.sort_values(
        ["station_id", "common_name", "timestamp"],
        ascending=[True, True, True]
    ).copy()

    time_since_previous = (
    frame.groupby(
        ["station_id", "common_name"]
    )["timestamp"]
    .diff()
    )

    keep = (
        time_since_previous.isna()
        | (time_since_previous >= pd.Timedelta(minutes=window_minutes))
    )

    return (
        frame.loc[keep]
        .sort_values("timestamp", ascending=False)
        .reset_index(drop=True)
    )

@st.cache_data(ttl=20, show_spinner=False)
def get_today_data() -> tuple[dict, pd.DataFrame]:
    today = datetime.now(LOCAL_TZ).date()
    tomorrow = today + timedelta(days=1)

    result = request_detections(
        {
            "from": today.isoformat(),
            "to": tomorrow.isoformat()
        },
        limit=500
        )
    return result, flatten_detections(result)


@st.cache_data(ttl=300, show_spinner=False)
def get_archive_preview() -> tuple[dict, pd.DataFrame]:
    tomorrow = datetime.now(LOCAL_TZ).date() + timedelta(days=1)
    result = request_detections(
        {"from": "2024-01-01", "to": tomorrow.isoformat()},
        limit=20,
    )
    return result, flatten_detections(result)


def time_ago(timestamp: pd.Timestamp) -> str:
    now = datetime.now(LOCAL_TZ)
    seconds = max(0, int((now - timestamp.to_pydatetime()).total_seconds()))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} hr ago"
    return timestamp.strftime("%d %b %Y at %H:%M")


def recent_table(frame: pd.DataFrame) -> pd.DataFrame:
    table = frame.copy()
    table["Time"] = table["timestamp"].dt.strftime("%H:%M:%S")
    table["Species"] = table["common_name"]
    table["Scientific name"] = table["scientific_name"]
    table["Station"] = table["station_name"]
    table["Confidence"] = table["confidence"].map(lambda value: f"{value:.0%}")
    table["Probability"] = table["probability"].map(lambda value: f"{value:.0%}")
    return table[["Time", "Station", "Species", "Scientific name", "Confidence", "Probability"]]

def display_bird_card(bird, rank):
    with st.container(border=True):

        picture, bird_details = st.columns(
            [0.8, 1.6],
            vertical_alignment="center"
        )

        with picture:
            if pd.notna(bird.image_url) and bird.image_url:
                st.image(
                    bird.image_url,
                    width=70
                )
            else:
                st.markdown("🐦")

        with bird_details:
            st.markdown(
        f"""
        <div class="bird-card-text">
            <div class="bird-card-name">
                {rank}. {bird.common_name}
            </div>
            <div class="bird-card-scientific">
                {bird.scientific_name}
            </div>
            <div class="bird-card-events">
                {bird.n_events} events · {bird.n_obs} detections 
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_dashboard() -> None:
    checked_at = datetime.now(LOCAL_TZ)
    active_date = f"{checked_at.day} {checked_at:%b %Y}"
    try:
        summary, raw_detections = get_today_data()
        detections = collapse_repeat_detections(raw_detections)
    except Exception as error:
        st.error(
            "BirdWeather could not be reached on this refresh. "
            "The dashboard will try again automatically."
        )
        st.caption(f"Technical detail: {error}")
        return

    showing_archive = False
    if detections.empty:
        try:
            _, raw_detections = get_archive_preview()
            detections = collapse_repeat_detections(raw_detections)
            showing_archive = not detections.empty
        except Exception:
            detections = pd.DataFrame()

    if not detections.empty:
        station_details = (
            detections[
                ["station_name", "station_id"]
                ]
                .dropna()
                .drop_duplicates()
                .sort_values("station_name")
            )

        station_label = " and ".join(
            f"{row.station_name} ({row.station_id})"
            for row in station_details.itertuples()
        )
    else:
        station_label = f"{len(STATION_IDS)} BirdWeather stations"

    if showing_archive:
        latest_date = detections.iloc[0]["timestamp"].strftime("%d %B %Y")
        st.warning(
            "No qualifying detections were received today. "
            f"Showing an archive preview from the station; the latest is dated {latest_date}."
        )
    elif detections.empty:
        st.info(
            "No qualifying detections are available yet. Once the station begins uploading, "
            "new detections will appear here automatically."
        )

    if detections.empty:
        return

    latest = detections.iloc[0]


# ── Top section ──────────────────────────────────────────────────

    latest_column, top_birds_column,= st.columns(
        [1, 1],
        gap="large"
    )


# ── Left: top five species ───────────────────────────────────────

    with top_birds_column:
        st.subheader("Top Species by Detection Events")

        if not showing_archive:

            species_columns = [
                "common_name",
                "scientific_name"
            ]

            event_counts = (
                detections
                .groupby(
                    species_columns + ["image_url"],
                    dropna=False
                )
                .size()
                .reset_index(name="n_events")
            )

            observation_counts = (
                raw_detections
                .groupby(
                    species_columns,
                    dropna=False
                )
                .size()
                .reset_index(name="n_obs")
            )

            top_birds = (
                event_counts
                .merge(
                    observation_counts,
                    on=species_columns,
                    how="left"
                )
                .sort_values(
                    ["n_events", "n_obs"],
                    ascending=[False, False]
                )
                .reset_index(drop=True)
            )
            

            bird_column_one, bird_column_two = st.columns(
                2,
                gap="small"
            )

            with bird_column_one:
                for rank, bird in enumerate(
                    top_birds.iloc[:5].itertuples(),
                    start=1
                ):
                    display_bird_card(bird, rank)

            with bird_column_two:
                for rank, bird in enumerate(
                    top_birds.iloc[5:10].itertuples(),
                    start=6
                ):
                    display_bird_card(bird, rank)


# ── Right: metrics, latest species and status ────────────────────

    with latest_column:
        st.subheader("Latest Detection Summary")
        metric_one, metric_two = st.columns(2)

        metric_one.metric(
            f"Raw detections · {active_date}",
            int(summary.get("totalCount", 0))
        )

        metric_two.metric(
            f"Species detected · {active_date}",
            int(summary.get("speciesCount", 0))
        )


        # Latest species

        with st.container(border=True):

            bird_image, bird_details = st.columns(
                [1, 1],
                gap="medium",
                vertical_alignment="center"
            )

            with bird_image:
                if latest.get("image_url"):
                    st.image(
                        latest["image_url"],
                        use_container_width=True
                    )

            with bird_details:
                st.caption("LATEST SPECIES DETECTED")

                st.markdown(
                    f'<div class="species-name">'
                    f'{latest["common_name"]}'
                    f'</div>'
                    f'<div class="scientific-name">'
                    f'{latest["scientific_name"]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                st.write(
                    f'**Detected {time_ago(latest["timestamp"])}**'
                )

                st.caption(
                    f'Confidence {latest["confidence"]:.0%}  \n'
                    f'Probability {latest["probability"]:.0%}'
                )


    # Live status directly beneath latest species

        with st.container(border=True):
            st.markdown(
                f"""
                <div class="status-heading">
                    <div>
                        <span class="live-dot"></span>
                        <strong>Live status</strong>
                    </div>
                    <div class="last-checked">
                        <strong>Last retrieved from BirdWeather:</strong>
                        {checked_at:%H:%M:%S}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.write(f"**Stations:** {station_label}")

# ── Full-width detection-events table ────────────────────────────

    st.subheader(
        "Today's Detection Events"
        if not showing_archive
        else "Archive preview"
    )

    table_data = recent_table(detections)

    table_html = table_data.to_html(
        index=False,
        classes="event-table",
        border=0,
        escape=True
    )

    st.markdown(
        f'<div class="table-scroll">{table_html}</div>',
        unsafe_allow_html=True
    )


st.title("Harper Adams University Live Bird Detections")

@st.fragment(run_every=f"{REFRESH_SECONDS}s")
def live_fragment() -> None:
    render_dashboard()


live_fragment()

