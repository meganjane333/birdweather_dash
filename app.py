from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


API_URL = "https://app.birdweather.com/graphql"
STATION_ID = "12521"
REFRESH_SECONDS = 30
MIN_CONFIDENCE = 0.70
MIN_PROBABILITY = 0.70
LOCAL_TZ = ZoneInfo("Europe/London")


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
    page_title="Harper Adams Live Bird Detections",
    page_icon="🐦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .block-container {max-width: 1280px; padding-top: 1.4rem;}
      h1 {margin-bottom: 0.15rem;}
      .subtitle {color: #52645a; font-size: 1.05rem; margin-bottom: 1.1rem;}
      .live-dot {
        display: inline-block; width: 0.65rem; height: 0.65rem;
        border-radius: 50%; background: #2e8b57; margin-right: 0.4rem;
      }
      [data-testid="stMetric"] {
        background: #f3f7f4; border: 1px solid #dce7df;
        border-radius: 0.8rem; padding: 0.75rem 1rem;
      }
      .species-name {font-size: 2rem; font-weight: 700; line-height: 1.1;}
      .scientific-name {font-style: italic; color: #52645a; margin-bottom: 0.8rem;}
      footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)


def request_detections(period: dict, limit: int = 100) -> dict:
    variables = {
        "stationIds": [STATION_ID],
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
                "station_name": station.get("name", f"Station {STATION_ID}"),
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


@st.cache_data(ttl=20, show_spinner=False)
def get_today_data() -> tuple[dict, pd.DataFrame]:
    result = request_detections({"count": 1, "unit": "day"}, limit=100)
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
    table = frame.head(15).copy()
    table["Time"] = table["timestamp"].dt.strftime("%H:%M:%S")
    table["Species"] = table["common_name"]
    table["Scientific name"] = table["scientific_name"]
    table["Confidence"] = table["confidence"].map(lambda value: f"{value:.0%}")
    table["Probability"] = table["probability"].map(lambda value: f"{value:.0%}")
    return table[["Time", "Species", "Scientific name", "Confidence", "Probability"]]


def render_dashboard() -> None:
    checked_at = datetime.now(LOCAL_TZ)
    try:
        summary, detections = get_today_data()
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
            _, detections = get_archive_preview()
            showing_archive = not detections.empty
        except Exception:
            detections = pd.DataFrame()

    station_name = (
        detections.iloc[0]["station_name"]
        if not detections.empty
        else f"BirdWeather station {STATION_ID}"
    )

    st.markdown(
        f'<span class="live-dot"></span> Checking <strong>{station_name}</strong> '
        f'every {REFRESH_SECONDS} seconds',
        unsafe_allow_html=True,
    )
    st.caption(f"Last checked {checked_at:%H:%M:%S} · Station ID {STATION_ID}")

    if showing_archive:
        latest_date = detections.iloc[0]["timestamp"].strftime("%d %B %Y")
        st.warning(
            "No qualifying detections were received in the last 24 hours. "
            f"Showing an archive preview from the station; the latest is dated {latest_date}."
        )
    elif detections.empty:
        st.info(
            "No qualifying detections are available yet. Once the station begins uploading, "
            "new detections will appear here automatically."
        )

    metrics = st.columns(3)
    metrics[0].metric("Detections · last 24 hours", int(summary.get("totalCount", 0)))
    metrics[1].metric("Species · last 24 hours", int(summary.get("speciesCount", 0)))
    metrics[2].metric("Refresh interval", f"{REFRESH_SECONDS} sec")

    if detections.empty:
        return

    latest = detections.iloc[0]
    left, right = st.columns([1.15, 2], gap="large")

    with left:
        if latest.get("image_url"):
            st.image(latest["image_url"], use_container_width=True)
        st.markdown(
            f'<div class="species-name">{latest["common_name"]}</div>'
            f'<div class="scientific-name">{latest["scientific_name"]}</div>',
            unsafe_allow_html=True,
        )
        st.write(f'Latest detection: **{time_ago(latest["timestamp"])}**')
        st.caption(
            f'Confidence {latest["confidence"]:.0%} · '
            f'Probability {latest["probability"]:.0%}'
        )

    with right:
        st.subheader("Recent detections" if not showing_archive else "Archive preview")
        st.dataframe(
            recent_table(detections),
            hide_index=True,
            use_container_width=True,
            height=370,
        )

    if not showing_archive:
        st.subheader("Most frequently detected today")
        top_species = (
            detections.groupby("common_name")
            .size()
            .sort_values(ascending=False)
            .head(8)
            .rename("Detections")
        )
        st.bar_chart(top_species, horizontal=True, color="#2e8b57")

    st.caption(
        "Only detections with confidence and probability of at least 70% are shown. "
        "Automated acoustic classifications should be treated as indicative until verified."
    )


st.title("Harper Adams Live Bird Detections")
st.markdown(
    '<div class="subtitle">What is the landscape telling us right now?</div>',
    unsafe_allow_html=True,
)


@st.fragment(run_every=f"{REFRESH_SECONDS}s")
def live_fragment() -> None:
    render_dashboard()


live_fragment()

