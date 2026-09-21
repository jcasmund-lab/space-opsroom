import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from skyfield.api import EarthSatellite, load
from streamlit_autorefresh import st_autorefresh


# ----------------------------
# Page + refresh
# ----------------------------
st.set_page_config(
    page_title="Space Ops Room",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Re-render every 30 seconds. External data calls are cached separately.
st_autorefresh(interval=30_000, key="opsroom_refresh")

CET = ZoneInfo("Europe/Copenhagen")
NOW_UTC = datetime.now(timezone.utc)
NOW_LOCAL = NOW_UTC.astimezone(CET)

NOAA_KP = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
NOAA_KP_FORECAST = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
NOAA_SCALES = "https://services.swpc.noaa.gov/products/noaa-scales.json"
CELESTRAK_TLE = "https://celestrak.org/NORAD/elements/gp.php"

AOIS = [
    {
        "name": "DENMARK",
        "lat_range": [52, 59.5],
        "lon_range": [-3, 19],
        "marker": (56.1, 10.0),
    },
    {
        "name": "BALTIC",
        "lat_range": [52, 61.5],
        "lon_range": [8, 32],
        "marker": (57.2, 21.0),
    },
    {
        "name": "ARCTIC",
        "lat_range": [58, 90],
        "lon_range": [-75, 55],
        "marker": (75.0, -15.0),
    },
]

# rotate AOI every 30 seconds
aoi_idx = int(time.time() // 30) % len(AOIS)
ACTIVE_AOI = AOIS[aoi_idx]


# ----------------------------
# Styling
# ----------------------------
st.markdown(
    """
    <style>
      :root {
        --bg: #071019;
        --panel: #0d1924;
        --panel2: #0a141d;
        --line: #203546;
        --text: #e8f1f7;
        --muted: #7890a3;
        --cyan: #6fd3ff;
        --green: #71e6a8;
        --amber: #f5c66a;
        --red: #ff7f88;
        --white: #f5fbff;
      }

      html, body, [data-testid="stAppViewContainer"] {
        background: var(--bg);
        color: var(--text);
      }

      [data-testid="stHeader"], [data-testid="stToolbar"],
      #MainMenu, footer {
        visibility: hidden;
        height: 0px;
      }

      .block-container {
        max-width: 100%;
        padding: 0.7rem 1rem 0.6rem 1rem;
      }

      .ops-header {
        display:flex;
        justify-content:space-between;
        align-items:flex-end;
        border-bottom:1px solid var(--line);
        padding:0.15rem 0 0.55rem 0;
        margin-bottom:0.55rem;
      }

      .ops-title {
        font-size:1.42rem;
        font-weight:750;
        letter-spacing:0.08em;
        color:var(--white);
      }

      .ops-sub {
        font-size:0.72rem;
        color:var(--muted);
        letter-spacing:0.12em;
        margin-top:0.12rem;
      }

      .live {
        font-size:0.78rem;
        letter-spacing:0.08em;
        color:var(--green);
        font-weight:700;
      }

      .panel {
        background: linear-gradient(180deg, var(--panel), var(--panel2));
        border:1px solid var(--line);
        border-radius:10px;
        padding:0.72rem 0.82rem;
        height:100%;
      }

      .panel-title {
        font-size:0.73rem;
        font-weight:800;
        letter-spacing:0.12em;
        color:#9fb6c8;
        margin-bottom:0.45rem;
      }

      .big-value {
        font-size:2.0rem;
        font-weight:800;
        color:var(--white);
        line-height:1;
      }

      .metric-label {
        color:var(--muted);
        font-size:0.70rem;
        letter-spacing:0.06em;
      }

      .metric-row {
        display:flex;
        justify-content:space-between;
        gap:0.6rem;
        border-top:1px solid rgba(32,53,70,.75);
        padding:0.42rem 0;
        font-size:0.78rem;
      }

      .metric-row:first-of-type { border-top:none; }

      .chip {
        display:inline-block;
        padding:0.20rem 0.44rem;
        border-radius:999px;
        font-size:0.66rem;
        font-weight:800;
        letter-spacing:0.07em;
        border:1px solid;
        white-space:nowrap;
      }

      .normal { color:var(--green); border-color:#235b46; background:#0d2a20; }
      .watch { color:var(--amber); border-color:#6b562b; background:#2a2110; }
      .elevated { color:#ffae7b; border-color:#6e452a; background:#2c1a11; }
      .impact { color:var(--red); border-color:#71353a; background:#2c1216; }
      .limited { color:#a9bfd0; border-color:#3a5365; background:#12212c; }

      .watch-item {
        border-left:3px solid var(--amber);
        padding:0.42rem 0.55rem;
        margin:0.32rem 0;
        background:#111d27;
        border-radius:4px;
      }

      .watch-item.normal-item { border-left-color:var(--green); }
      .watch-item.elevated-item { border-left-color:#ffae7b; }

      .wi-title {
        font-size:0.80rem;
        font-weight:800;
        color:var(--white);
        letter-spacing:0.04em;
      }

      .wi-sub {
        font-size:0.69rem;
        color:var(--muted);
        margin-top:0.12rem;
      }

      .statusbar {
        display:grid;
        grid-template-columns: repeat(3, 1fr);
        gap:0.55rem;
        margin-top:0.55rem;
      }

      .statusbox {
        background:#0b1620;
        border:1px solid var(--line);
        border-radius:8px;
        padding:0.55rem 0.7rem;
        display:flex;
        justify-content:space-between;
        align-items:center;
      }

      .statusname {
        font-size:0.72rem;
        color:#9fb6c8;
        font-weight:800;
        letter-spacing:0.1em;
      }

      .statusvalue {
        font-size:0.78rem;
        font-weight:800;
      }

      .tiny {
        font-size:0.65rem;
        color:var(--muted);
      }

      .eventline {
        font-size:0.70rem;
        color:#b4c6d3;
        padding:0.18rem 0;
        border-top:1px solid rgba(32,53,70,.55);
      }

      div[data-testid="stPlotlyChart"] {
        background: transparent;
      }

      .stDeployButton { display:none; }

      @media (max-width: 1100px) {
        .ops-title { font-size:1.1rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------
# Data helpers
# ----------------------------
def safe_get_json(url, timeout=12):
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "space-opsroom/0.1"})
        r.raise_for_status()
        return r.json(), None
    except Exception as exc:
        return None, str(exc)


@st.cache_data(ttl=300, show_spinner=False)
def get_noaa():
    kp, e1 = safe_get_json(NOAA_KP)
    forecast, e2 = safe_get_json(NOAA_KP_FORECAST)
    scales, e3 = safe_get_json(NOAA_SCALES)
    return kp, forecast, scales, [e for e in (e1, e2, e3) if e]


@st.cache_data(ttl=7200, show_spinner=False)
def get_tle(group):
    # CelesTrak GP data updates roughly every two hours; do not hammer this endpoint.
    params = {"GROUP": group, "FORMAT": "TLE"}
    try:
        r = requests.get(
            CELESTRAK_TLE,
            params=params,
            timeout=15,
            headers={"User-Agent": "space-opsroom/0.1"},
        )
        r.raise_for_status()
        return r.text.strip(), None
    except Exception as exc:
        return "", str(exc)


def parse_kp(kp_json):
    if not kp_json:
        return pd.DataFrame(columns=["time", "kp"])
    rows = []
    for row in kp_json:
        try:
            rows.append(
                {
                    "time": pd.to_datetime(row["time_tag"], utc=True),
                    "kp": float(row["Kp"]),
                }
            )
        except Exception:
            continue
    return pd.DataFrame(rows).sort_values("time")


def parse_forecast(f_json):
    if not f_json:
        return pd.DataFrame(columns=["time", "kp", "kind", "scale"])
    rows = []
    for row in f_json:
        try:
            rows.append(
                {
                    "time": pd.to_datetime(row["time_tag"], utc=True),
                    "kp": float(row["kp"]),
                    "kind": row.get("observed") or "",
                    "scale": row.get("noaa_scale"),
                }
            )
        except Exception:
            continue
    return pd.DataFrame(rows).sort_values("time")


def latest_scales(scales_json):
    if not isinstance(scales_json, dict):
        return {"G": 0, "R": 0, "S": 0, "stamp": None}
    row = scales_json.get("0", {})
    out = {"stamp": None}
    try:
        out["stamp"] = pd.to_datetime(
            f"{row.get('DateStamp')}T{row.get('TimeStamp')}Z", utc=True
        )
    except Exception:
        out["stamp"] = None
    for key in ("G", "R", "S"):
        try:
            out[key] = int((row.get(key) or {}).get("Scale") or 0)
        except Exception:
            out[key] = 0
    return out


def kp_level(kp_value, scales):
    g = scales.get("G", 0)
    r = scales.get("R", 0)
    s = scales.get("S", 0)
    peak = max(g, r, s)
    if peak >= 4 or kp_value >= 8:
        return "IMPACT", "impact"
    if peak >= 2 or kp_value >= 6:
        return "ELEVATED", "elevated"
    if peak >= 1 or kp_value >= 4:
        return "WATCH", "watch"
    return "NORMAL", "normal"


def trend_at(df, hours):
    if df.empty:
        return None
    latest = df.iloc[-1]
    target = latest["time"] - pd.Timedelta(hours=hours)
    previous = df[df["time"] <= target]
    if previous.empty:
        return None
    old = previous.iloc[-1]["kp"]
    delta = float(latest["kp"] - old)
    arrow = "↑" if delta > 0.34 else "↓" if delta < -0.34 else "→"
    return arrow, delta


def fmt_trend(t):
    if not t:
        return "—"
    arrow, delta = t
    return f"{arrow} {delta:+.1f}"


def parse_tle_text(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    sats = []
    i = 0
    while i + 2 < len(lines):
        if lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
            sats.append((lines[i], lines[i + 1], lines[i + 2]))
            i += 3
        else:
            i += 1
    return sats


def satellite_positions(tle_text, max_sats=40):
    if not tle_text:
        return []
    ts = load.timescale()
    t = ts.now()
    out = []
    for name, l1, l2 in parse_tle_text(tle_text)[:max_sats]:
        try:
            sat = EarthSatellite(l1, l2, name, ts)
            sub = sat.at(t).subpoint()
            out.append(
                {
                    "name": name,
                    "lat": float(sub.latitude.degrees),
                    "lon": float(sub.longitude.degrees),
                    "alt_km": float(sub.elevation.km),
                }
            )
        except Exception:
            continue
    return out


def minutes_old(ts):
    if ts is None or pd.isna(ts):
        return None
    now = pd.Timestamp.now(tz="UTC")
    return max(0, int((now - ts).total_seconds() / 60))


def chip(text, level):
    return f'<span class="chip {level}">{text}</span>'


# ----------------------------
# Load live data
# ----------------------------
kp_json, forecast_json, scales_json, noaa_errors = get_noaa()
kp_df = parse_kp(kp_json)
fc_df = parse_forecast(forecast_json)
scales = latest_scales(scales_json)

gps_tle, gps_err = get_tle("GPS-OPS")
gal_tle, gal_err = get_tle("GALILEO")
gps_pos = satellite_positions(gps_tle, max_sats=36)
gal_pos = satellite_positions(gal_tle, max_sats=36)

if kp_df.empty:
    current_kp = 0.0
    kp_time = None
else:
    current_kp = float(kp_df.iloc[-1]["kp"])
    kp_time = kp_df.iloc[-1]["time"]

wx_text, wx_class = kp_level(current_kp, scales)


# ----------------------------
# Header
# ----------------------------
source_count = 3
source_ok = int(not noaa_errors) + int(not gps_err) + int(not gal_err)
st.markdown(
    f"""
    <div class="ops-header">
      <div>
        <div class="ops-title">SPACE OPS // COMMON OPERATING PICTURE</div>
        <div class="ops-sub">AOI FOCUS · {ACTIVE_AOI["name"]} &nbsp;&nbsp;|&nbsp;&nbsp; OPEN SOURCES ONLY &nbsp;&nbsp;|&nbsp;&nbsp; V0.1</div>
      </div>
      <div style="text-align:right">
        <div class="live">● LIVE &nbsp; {NOW_LOCAL.strftime("%d %b %Y · %H:%M:%S %Z")}</div>
        <div class="tiny">SOURCES {source_ok}/{source_count} ONLINE · AUTO REFRESH 30s</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ----------------------------
# Main: map + right rail
# ----------------------------
left, right = st.columns([1.55, 1.0], gap="small")

with left:
    st.markdown(
        f'<div class="panel-title">AOI // {ACTIVE_AOI["name"]} · PNT CONSTELLATION SUBPOINTS</div>',
        unsafe_allow_html=True,
    )

    fig = go.Figure()

    # AOI centre
    fig.add_trace(
        go.Scattergeo(
            lon=[ACTIVE_AOI["marker"][1]],
            lat=[ACTIVE_AOI["marker"][0]],
            mode="markers+text",
            text=[ACTIVE_AOI["name"]],
            textposition="top center",
            marker=dict(size=10, symbol="circle-open", line=dict(width=2)),
            hoverinfo="text",
            name="AOI",
        )
    )

    # Denmark / Baltic / Arctic anchor markers
    fig.add_trace(
        go.Scattergeo(
            lon=[a["marker"][1] for a in AOIS],
            lat=[a["marker"][0] for a in AOIS],
            mode="markers",
            marker=dict(size=5),
            text=[a["name"] for a in AOIS],
            hovertemplate="%{text}<extra></extra>",
            name="AOIs",
        )
    )

    # GPS
    if gps_pos:
        fig.add_trace(
            go.Scattergeo(
                lon=[p["lon"] for p in gps_pos],
                lat=[p["lat"] for p in gps_pos],
                mode="markers",
                marker=dict(size=5, symbol="diamond"),
                text=[f'{p["name"]}<br>{p["alt_km"]:.0f} km' for p in gps_pos],
                hovertemplate="%{text}<extra>GPS</extra>",
                name="GPS",
            )
        )

    # Galileo
    if gal_pos:
        fig.add_trace(
            go.Scattergeo(
                lon=[p["lon"] for p in gal_pos],
                lat=[p["lat"] for p in gal_pos],
                mode="markers",
                marker=dict(size=5, symbol="circle"),
                text=[f'{p["name"]}<br>{p["alt_km"]:.0f} km' for p in gal_pos],
                hovertemplate="%{text}<extra>GALILEO</extra>",
                name="Galileo",
            )
        )

    fig.update_geos(
        projection_type="natural earth",
        lonaxis_range=ACTIVE_AOI["lon_range"],
        lataxis_range=ACTIVE_AOI["lat_range"],
        showland=True,
        landcolor="#0d1c27",
        showocean=True,
        oceancolor="#071019",
        showcountries=True,
        countrycolor="#294052",
        showcoastlines=True,
        coastlinecolor="#3b5669",
        bgcolor="#071019",
    )

    fig.update_layout(
        height=510,
        margin=dict(l=0, r=0, t=5, b=0),
        paper_bgcolor="#071019",
        plot_bgcolor="#071019",
        font=dict(color="#dce9f2", size=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=0.01,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(7,16,25,.75)",
        ),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with right:
    # Space weather card
    wx_age = minutes_old(kp_time)
    st.markdown(
        f"""
        <div class="panel">
          <div class="panel-title">SPACE WEATHER</div>
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <div class="metric-label">PLANETARY Kp</div>
              <div class="big-value">{current_kp:.2f}</div>
            </div>
            <div style="text-align:right">{chip(wx_text, wx_class)}</div>
          </div>
          <div class="metric-row"><span>NOAA scales</span><b>G{scales["G"]} · R{scales["R"]} · S{scales["S"]}</b></div>
          <div class="metric-row"><span>6h trend</span><b>{fmt_trend(trend_at(kp_df, 6))}</b></div>
          <div class="metric-row"><span>24h trend</span><b>{fmt_trend(trend_at(kp_df, 24))}</b></div>
          <div class="metric-row"><span>7d trend</span><b>{fmt_trend(trend_at(kp_df, 168))}</b></div>
          <div class="tiny" style="margin-top:.35rem">NOAA SWPC · {wx_age if wx_age is not None else "—"} min old</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:.45rem'></div>", unsafe_allow_html=True)

    # Watch items
    items = []
    if wx_text != "NORMAL":
        effect = "Potential PNT/HF effects — monitor trend" if scales["G"] or current_kp >= 5 else "Elevated solar/geomagnetic activity"
        items.append(("SPACE WEATHER", f"{effect} · Kp {current_kp:.2f}", wx_class))
    else:
        items.append(("SPACE WEATHER", f"No active watch · Kp {current_kp:.2f}", "normal"))

    items.append(
        (
            "SDA BASELINE",
            f"{len(gps_pos) + len(gal_pos)} PNT satellites propagated · anomaly engine next phase",
            "normal",
        )
    )
    items.append(
        (
            f"AOI · {ACTIVE_AOI['name']}",
            "GNSS interference layer not connected yet · no inference made",
            "limited",
        )
    )

    html = '<div class="panel"><div class="panel-title">WATCH ITEMS // PRIORITY</div>'
    for title, sub, cls in items[:3]:
        item_class = "normal-item" if cls == "normal" else "elevated-item" if cls in ("elevated", "impact") else ""
        html += f'<div class="watch-item {item_class}"><div class="wi-title">{title}</div><div class="wi-sub">{sub}</div></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    st.markdown("<div style='height:.45rem'></div>", unsafe_allow_html=True)

    # Next up
    future = pd.DataFrame()
    if not fc_df.empty:
        future = fc_df[fc_df["time"] > pd.Timestamp.now(tz="UTC")].head(4)

    html = '<div class="panel"><div class="panel-title">NEXT UP // AOI RELEVANT</div>'
    if future.empty:
        html += '<div class="wi-sub">No forecast data available.</div>'
    else:
        for _, row in future.iterrows():
            local = row["time"].tz_convert(CET)
            kind = str(row["kind"]).upper()
            html += (
                f'<div class="metric-row"><span>{local.strftime("%H:%M")} · Kp forecast</span>'
                f'<b>{row["kp"]:.2f} <span class="tiny">{kind}</span></b></div>'
            )
    html += f'<div class="tiny" style="margin-top:.35rem">Next map focus changes automatically every 30s.</div></div>'
    st.markdown(html, unsafe_allow_html=True)


# ----------------------------
# Kp strip
# ----------------------------
st.markdown("<div style='height:.45rem'></div>", unsafe_allow_html=True)
c1, c2 = st.columns([1.25, 2.75], gap="small")

with c1:
    st.markdown('<div class="panel-title">EVENT STREAM // RECENT CHANGE</div>', unsafe_allow_html=True)
    if kp_df.empty:
        st.markdown('<div class="eventline">No event data.</div>', unsafe_allow_html=True)
    else:
        recent = kp_df.tail(5).copy()
        for _, row in recent.iloc[::-1].iterrows():
            loc = row["time"].tz_convert(CET)
            st.markdown(
                f'<div class="eventline">{loc.strftime("%H:%M")} &nbsp; Kp {row["kp"]:.2f}</div>',
                unsafe_allow_html=True,
            )

with c2:
    st.markdown('<div class="panel-title">Kp TREND // 7 DAYS</div>', unsafe_allow_html=True)
    if not kp_df.empty:
        kfig = go.Figure()
        kfig.add_trace(
            go.Scatter(
                x=kp_df["time"],
                y=kp_df["kp"],
                mode="lines",
                line=dict(width=2),
                hovertemplate="%{x|%d %b %H:%M UTC}<br>Kp %{y:.2f}<extra></extra>",
            )
        )
        kfig.add_hline(y=5, line_dash="dot", opacity=0.4)
        kfig.update_layout(
            height=145,
            margin=dict(l=5, r=5, t=5, b=5),
            paper_bgcolor="#071019",
            plot_bgcolor="#071019",
            font=dict(color="#9fb6c8", size=9),
            showlegend=False,
            xaxis=dict(showgrid=False, zeroline=False),
            yaxis=dict(range=[0, 9], showgrid=True, gridcolor="#173040", zeroline=False),
        )
        st.plotly_chart(kfig, use_container_width=True, config={"displayModeBar": False})


# ----------------------------
# Operational status bar
# ----------------------------
sda_text = "BASELINE"
pnt_text = "DATA LIMITED"

st.markdown(
    f"""
    <div class="statusbar">
      <div class="statusbox">
        <span class="statusname">PNT</span>
        <span class="statusvalue" style="color:#a9bfd0">{pnt_text}</span>
      </div>
      <div class="statusbox">
        <span class="statusname">SDA</span>
        <span class="statusvalue" style="color:#71e6a8">{sda_text}</span>
      </div>
      <div class="statusbox">
        <span class="statusname">SPACE WX</span>
        <span class="statusvalue" style="color:{'#71e6a8' if wx_class == 'normal' else '#f5c66a'}">{wx_text}</span>
      </div>
    </div>
    <div class="tiny" style="margin-top:.45rem">
      V0.1 deliberately avoids claiming GNSS interference or orbital anomalies until those feeds and baselines are connected.
      CelesTrak GP data is cached for 2h; satellite positions are propagated locally every screen refresh.
    </div>
    """,
    unsafe_allow_html=True,
)
