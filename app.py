import math
import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# ============================================================
# PAGE
# ============================================================
st.set_page_config(
    page_title="Space Ops Room",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st_autorefresh(interval=30_000, key="opsroom_refresh")

CET = ZoneInfo("Europe/Copenhagen")
NOW_UTC = datetime.now(timezone.utc)
NOW_LOCAL = NOW_UTC.astimezone(CET)

NOAA_KP = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
NOAA_KP_FORECAST = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json"
NOAA_SCALES = "https://services.swpc.noaa.gov/products/noaa-scales.json"

AOIS = [
    {
        "name": "DENMARK",
        "center": {"lat": 56.05, "lon": 10.6},
        "zoom": 5.05,
        "bounds": (54.3, 58.2, 7.5, 15.8),
        "capitals": [("Copenhagen", 55.6761, 12.5683)],
    },
    {
        "name": "BALTIC",
        "center": {"lat": 57.3, "lon": 20.8},
        "zoom": 3.55,
        "bounds": (52.0, 61.8, 8.0, 31.5),
        "capitals": [
            ("Copenhagen", 55.6761, 12.5683),
            ("Stockholm", 59.3293, 18.0686),
            ("Helsinki", 60.1699, 24.9384),
            ("Tallinn", 59.4370, 24.7536),
            ("Riga", 56.9496, 24.1052),
            ("Vilnius", 54.6872, 25.2797),
            ("Warsaw", 52.2297, 21.0122),
        ],
    },
    {
        "name": "ARCTIC",
        "center": {"lat": 71.0, "lon": -13.0},
        "zoom": 1.95,
        "bounds": (60.0, 90.0, -75.0, 45.0),
        "capitals": [
            ("Nuuk", 64.1835, -51.7216),
            ("Reykjavík", 64.1466, -21.9426),
            ("Oslo", 59.9139, 10.7522),
            ("Stockholm", 59.3293, 18.0686),
            ("Helsinki", 60.1699, 24.9384),
        ],
    },
]


# ============================================================
# STYLE
# ============================================================
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
        --green: #71e6a8;
        --amber: #f5c66a;
        --orange: #ffae7b;
        --red: #ff7f88;
        --white: #f5fbff;
        --cyan: #6fd3ff;
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
        padding: 0.48rem 0.78rem 0.45rem 0.78rem;
      }

      .ops-header {
        display:flex;
        justify-content:space-between;
        align-items:flex-end;
        border-bottom:1px solid var(--line);
        padding:0.1rem 0 0.46rem 0;
        margin-bottom:0.42rem;
      }

      .ops-title {
        font-size:1.28rem;
        font-weight:800;
        letter-spacing:0.08em;
        color:var(--white);
      }

      .ops-sub {
        font-size:0.66rem;
        color:var(--muted);
        letter-spacing:0.1em;
        margin-top:0.1rem;
      }

      .live {
        font-size:0.72rem;
        letter-spacing:0.08em;
        color:var(--green);
        font-weight:800;
      }

      .panel {
        background: linear-gradient(180deg, var(--panel), var(--panel2));
        border:1px solid var(--line);
        border-radius:9px;
        padding:0.56rem 0.66rem;
        height:100%;
      }

      .panel-title {
        font-size:0.69rem;
        font-weight:800;
        letter-spacing:0.11em;
        color:#9fb6c8;
        margin-bottom:0.28rem;
      }

      .aoi-header {
        display:flex;
        justify-content:space-between;
        align-items:center;
        margin-bottom:0.12rem;
      }

      .aoi-name {
        font-size:0.72rem;
        font-weight:850;
        letter-spacing:0.11em;
        color:#dbe9f2;
      }

      .big-value {
        font-size:1.72rem;
        font-weight:800;
        color:var(--white);
        line-height:1;
      }

      .metric-label {
        color:var(--muted);
        font-size:0.64rem;
        letter-spacing:0.05em;
      }

      .metric-row {
        display:flex;
        justify-content:space-between;
        gap:0.5rem;
        border-top:1px solid rgba(32,53,70,.75);
        padding:0.29rem 0;
        font-size:0.70rem;
      }

      .chip {
        display:inline-block;
        padding:0.16rem 0.37rem;
        border-radius:999px;
        font-size:0.59rem;
        font-weight:800;
        letter-spacing:0.07em;
        border:1px solid;
        white-space:nowrap;
      }

      .normal { color:var(--green); border-color:#235b46; background:#0d2a20; }
      .watch { color:var(--amber); border-color:#6b562b; background:#2a2110; }
      .elevated { color:var(--orange); border-color:#6e452a; background:#2c1a11; }
      .impact { color:var(--red); border-color:#71353a; background:#2c1216; }
      .limited { color:#a9bfd0; border-color:#3a5365; background:#12212c; }

      .watch-item {
        border-left:3px solid var(--amber);
        padding:0.34rem 0.46rem;
        margin:0.24rem 0;
        background:#111d27;
        border-radius:4px;
      }

      .watch-item.normal-item { border-left-color:var(--green); }
      .watch-item.elevated-item { border-left-color:var(--orange); }
      .watch-item.impact-item { border-left-color:var(--red); }
      .watch-item.limited-item { border-left-color:#597286; }

      .wi-title {
        font-size:0.73rem;
        font-weight:800;
        color:var(--white);
        letter-spacing:0.04em;
      }

      .wi-sub {
        font-size:0.62rem;
        color:var(--muted);
        margin-top:0.08rem;
      }

      .statusbar {
        display:grid;
        grid-template-columns: repeat(3, 1fr);
        gap:0.42rem;
        margin-top:0.42rem;
      }

      .statusbox {
        background:#0b1620;
        border:1px solid var(--line);
        border-radius:8px;
        padding:0.42rem 0.56rem;
        display:flex;
        justify-content:space-between;
        align-items:center;
      }

      .statusname {
        font-size:0.66rem;
        color:#9fb6c8;
        font-weight:800;
        letter-spacing:0.1em;
      }

      .statusvalue {
        font-size:0.70rem;
        font-weight:800;
      }

      .tiny {
        font-size:0.59rem;
        color:var(--muted);
      }

      .eventline {
        font-size:0.63rem;
        color:#b4c6d3;
        padding:0.12rem 0;
        border-top:1px solid rgba(32,53,70,.55);
      }

      div[data-testid="stPlotlyChart"] {
        background: transparent;
      }

      .stDeployButton { display:none; }

      @media (max-width: 1050px) {
        .ops-title { font-size:1.0rem; }
        .block-container { padding-left:0.45rem; padding-right:0.45rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# UTILITIES
# ============================================================
def utc_now():
    return datetime.now(timezone.utc)


def safe_get_json(url, timeout=12):
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "space-opsroom/0.3"})
        r.raise_for_status()
        return r.json(), None
    except Exception as exc:
        return None, str(exc)


def get_secret(name):
    try:
        return st.secrets[name]
    except Exception:
        return os.getenv(name)


def supabase_ready():
    return bool(get_secret("SUPABASE_URL") and get_secret("SUPABASE_ANON_KEY"))


def sb_get(table, params=None, timeout=12):
    if not supabase_ready():
        return [], "Supabase not configured"
    url = get_secret("SUPABASE_URL").rstrip("/") + f"/rest/v1/{table}"
    key = get_secret("SUPABASE_ANON_KEY")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    try:
        r = requests.get(url, headers=headers, params=params or {}, timeout=timeout)
        r.raise_for_status()
        return r.json(), None
    except Exception as exc:
        return [], str(exc)


def age_minutes(value):
    if not value:
        return None
    try:
        dt = pd.to_datetime(value, utc=True).to_pydatetime()
        return max(0, int((utc_now() - dt).total_seconds() / 60))
    except Exception:
        return None


def chip(text, level):
    cls = level.lower() if level else "limited"
    if cls not in {"normal", "watch", "elevated", "impact", "limited"}:
        cls = "limited"
    return f'<span class="chip {cls}">{text}</span>'


def status_rank(status):
    return {
        "NORMAL": 0,
        "UNKNOWN": 0,
        "DATA LIMITED": 0,
        "WATCH": 1,
        "ELEVATED": 2,
        "IMPACT": 3,
    }.get((status or "").upper(), 0)


def highest_status(statuses):
    vals = [s for s in statuses if s]
    return max(vals, key=status_rank) if vals else "DATA LIMITED"


def trend_label(values, hours):
    if not values:
        return "—"
    df = pd.DataFrame(values)
    if df.empty or "observed_at" not in df or "score" not in df:
        return "—"
    df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True, errors="coerce")
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df = df.dropna(subset=["observed_at", "score"]).sort_values("observed_at")
    if len(df) < 2:
        return "—"
    latest = df.iloc[-1]
    target = latest["observed_at"] - pd.Timedelta(hours=hours)
    prev = df[df["observed_at"] <= target]
    if prev.empty:
        return "—"
    delta = float(latest["score"] - prev.iloc[-1]["score"])
    arrow = "↑" if delta >= 1.0 else "↓" if delta <= -1.0 else "→"
    return f"{arrow} {delta:+.1f} pp"


# ============================================================
# NOAA LIVE + HISTORY
# ============================================================
@st.cache_data(ttl=300, show_spinner=False)
def get_noaa():
    kp, e1 = safe_get_json(NOAA_KP)
    forecast, e2 = safe_get_json(NOAA_KP_FORECAST)
    scales, e3 = safe_get_json(NOAA_SCALES)
    return kp, forecast, scales, [e for e in (e1, e2, e3) if e]


def parse_kp(kp_json):
    if not kp_json:
        return pd.DataFrame(columns=["time", "kp"])
    rows = []
    for row in kp_json:
        try:
            rows.append({
                "time": pd.to_datetime(row["time_tag"], utc=True),
                "kp": float(row["Kp"]),
            })
        except Exception:
            continue
    return pd.DataFrame(rows).sort_values("time")


def parse_forecast(data):
    if not data:
        return pd.DataFrame(columns=["time", "kp", "kind"])
    rows = []
    for row in data:
        try:
            rows.append({
                "time": pd.to_datetime(row["time_tag"], utc=True),
                "kp": float(row["kp"]),
                "kind": row.get("observed") or "",
            })
        except Exception:
            continue
    return pd.DataFrame(rows).sort_values("time")


def latest_scales(data):
    if not isinstance(data, dict):
        return {"G": 0, "R": 0, "S": 0}
    row = data.get("0", {})
    out = {}
    for key in ("G", "R", "S"):
        try:
            out[key] = int((row.get(key) or {}).get("Scale") or 0)
        except Exception:
            out[key] = 0
    return out


def space_weather_level(kp_value, scales):
    peak = max(scales.get("G", 0), scales.get("R", 0), scales.get("S", 0))
    if peak >= 4 or kp_value >= 8:
        return "IMPACT", "impact"
    if peak >= 2 or kp_value >= 6:
        return "ELEVATED", "elevated"
    if peak >= 1 or kp_value >= 4:
        return "WATCH", "watch"
    return "NORMAL", "normal"


def kp_trend(df, hours):
    if df.empty:
        return "—"
    latest = df.iloc[-1]
    target = latest["time"] - pd.Timedelta(hours=hours)
    prev = df[df["time"] <= target]
    if prev.empty:
        return "—"
    delta = float(latest["kp"] - prev.iloc[-1]["kp"])
    arrow = "↑" if delta > 0.34 else "↓" if delta < -0.34 else "→"
    return f"{arrow} {delta:+.1f}"


kp_json, forecast_json, scales_json, noaa_errors = get_noaa()
kp_df = parse_kp(kp_json)
fc_df = parse_forecast(forecast_json)
scales = latest_scales(scales_json)
current_kp = 0.0 if kp_df.empty else float(kp_df.iloc[-1]["kp"])
wx_text, wx_class = space_weather_level(current_kp, scales)


# ============================================================
# PERSISTENT DATA
# ============================================================
seven_days_ago = (utc_now() - timedelta(days=7)).isoformat()
one_day_ago = (utc_now() - timedelta(days=1)).isoformat()

gnss_cells, gnss_cells_err = sb_get(
    "latest_gnss_cells",
    {
        "select": "mode,observed_at,granularity,h3_index,lat,lon,affected_pct,affected_count,total_count",
        "limit": "5000",
    },
)

gnss_events, gnss_events_err = sb_get(
    "gnss_events",
    {
        "select": "mode,event_key,observed_date,start_time,end_time,lat,lon,collected_at",
        "collected_at": f"gte.{one_day_ago}",
        "order": "collected_at.desc",
        "limit": "250",
    },
)

gnss_history, gnss_history_err = sb_get(
    "gnss_aoi_snapshots",
    {
        "select": "observed_at,aoi,mode,score,status,confidence,affected_cells,max_pct,aircraft_count,granularity",
        "observed_at": f"gte.{seven_days_ago}",
        "order": "observed_at.asc",
        "limit": "2000",
    },
)

orbital_events, orbital_events_err = sb_get(
    "orbital_events",
    {
        "select": "detected_at,norad_cat_id,object_name,group_name,event_type,severity,confidence,summary,status,event_key",
        "detected_at": f"gte.{seven_days_ago}",
        "order": "detected_at.desc",
        "limit": "30",
    },
)

collector_status, collector_status_err = sb_get(
    "collector_status",
    {
        "select": "source,last_success,detail,rows_written",
        "order": "source.asc",
        "limit": "20",
    },
)


def latest_aoi_status(aoi_name, mode="jamming"):
    rows = [
        r for r in gnss_history
        if r.get("aoi") == aoi_name and r.get("mode") == mode
    ]
    if not rows:
        return {
            "status": "DATA LIMITED",
            "confidence": "—",
            "score": None,
            "max_pct": None,
            "aircraft_count": 0,
            "affected_cells": 0,
            "observed_at": None,
            "granularity": "—",
        }
    rows = sorted(rows, key=lambda r: r.get("observed_at") or "")
    return rows[-1]


def aoi_history(aoi_name, mode="jamming"):
    return [
        r for r in gnss_history
        if r.get("aoi") == aoi_name and r.get("mode") == mode
    ]


def cells_in_aoi(aoi):
    south, north, west, east = aoi["bounds"]
    out = []
    for r in gnss_cells:
        if r.get("mode") != "jamming":
            continue
        try:
            lat = float(r["lat"])
            lon = float(r["lon"])
        except Exception:
            continue
        if south <= lat <= north and west <= lon <= east:
            out.append(r)
    return out


def events_in_aoi(aoi):
    south, north, west, east = aoi["bounds"]
    out = []
    for r in gnss_events:
        try:
            lat = float(r["lat"])
            lon = float(r["lon"])
        except Exception:
            continue
        if south <= lat <= north and west <= lon <= east:
            out.append(r)
    return out


def make_aoi_map(aoi):
    fig = go.Figure()

    # GNSS jamming layer, derived from ADS-B integrity.
    cells = cells_in_aoi(aoi)
    if cells:
        pct = [min(25.0, max(0.0, float(r.get("affected_pct") or 0))) for r in cells]
        sizes = [5 + min(10, p * 0.45) for p in pct]
        fig.add_trace(
            go.Scattermap(
                lat=[float(r["lat"]) for r in cells],
                lon=[float(r["lon"]) for r in cells],
                mode="markers",
                marker={
                    "size": sizes,
                    "color": pct,
                    "cmin": 0,
                    "cmax": 20,
                    "colorscale": [
                        [0.0, "#3d7866"],
                        [0.10, "#6f9c75"],
                        [0.35, "#d8bb61"],
                        [0.60, "#e58a56"],
                        [1.0, "#ef626b"],
                    ],
                    "opacity": 0.72,
                    "showscale": False,
                },
                text=[
                    f'{float(r.get("affected_pct") or 0):.1f}% low-integrity reports'
                    f'<br>{int(r.get("total_count") or 0)} aircraft reports'
                    for r in cells
                ],
                hovertemplate="%{text}<extra>Stanford GPS Lab</extra>",
                name="GNSS interference",
            )
        )

    # Detected jamming / spoofing event centroids.
    evs = events_in_aoi(aoi)
    jam = [e for e in evs if e.get("mode") == "jamming"]
    spoof = [e for e in evs if e.get("mode") == "spoofing"]

    if jam:
        fig.add_trace(
            go.Scattermap(
                lat=[float(e["lat"]) for e in jam],
                lon=[float(e["lon"]) for e in jam],
                mode="markers",
                marker={"size": 11, "symbol": "circle"},
                text=["Jamming event" for _ in jam],
                hovertemplate="%{text}<extra>Stanford GPS Lab</extra>",
                name="Jamming events",
            )
        )

    if spoof:
        fig.add_trace(
            go.Scattermap(
                lat=[float(e["lat"]) for e in spoof],
                lon=[float(e["lon"]) for e in spoof],
                mode="markers",
                marker={"size": 12, "symbol": "triangle"},
                text=["Spoofing event" for _ in spoof],
                hovertemplate="%{text}<extra>Stanford GPS Lab</extra>",
                name="Spoofing events",
            )
        )

    # Capitals: fixed reference points, not arbitrary AOI markers.
    fig.add_trace(
        go.Scattermap(
            lat=[c[1] for c in aoi["capitals"]],
            lon=[c[2] for c in aoi["capitals"]],
            mode="markers+text",
            marker={"size": 6},
            text=[c[0] for c in aoi["capitals"]],
            textposition="top right",
            hovertemplate="<b>%{text}</b><extra>Capital</extra>",
            name="Capitals",
        )
    )

    fig.update_layout(
        map={
            "style": "carto-darkmatter",
            "center": aoi["center"],
            "zoom": aoi["zoom"],
        },
        height=318,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="#071019",
        font={"color": "#dce9f2", "size": 9},
        showlegend=False,
    )
    return fig


# ============================================================
# SOURCE HEALTH
# ============================================================
status_by_source = {r.get("source"): r for r in collector_status}

def source_ok(source, max_age_min):
    row = status_by_source.get(source)
    if not row:
        return False
    age = age_minutes(row.get("last_success"))
    return age is not None and age <= max_age_min

noaa_ok = not noaa_errors
stanford_ok = source_ok("stanford_gnss", 150)
celestrak_ok = source_ok("celestrak_orbits", 300)
source_ok_count = int(noaa_ok) + int(stanford_ok) + int(celestrak_ok)


# ============================================================
# HEADER
# ============================================================
db_label = "HISTORY ONLINE" if supabase_ready() else "HISTORY OFFLINE"
st.markdown(
    f"""
    <div class="ops-header">
      <div>
        <div class="ops-title">SPACE OPS // COMMON OPERATING PICTURE</div>
        <div class="ops-sub">
          AOI STATUS · DENMARK · BALTIC · ARCTIC
          &nbsp;&nbsp;|&nbsp;&nbsp; OPEN SOURCES ONLY
          &nbsp;&nbsp;|&nbsp;&nbsp; V0.3 · {db_label}
        </div>
      </div>
      <div style="text-align:right">
        <div class="live">● LIVE &nbsp; {NOW_LOCAL.strftime("%d %b %Y · %H:%M:%S %Z")}</div>
        <div class="tiny">SOURCES {source_ok_count}/3 ONLINE · SCREEN REFRESH 30s</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# THREE AOIs
# ============================================================
cols = st.columns([1.0, 1.16, 1.16], gap="small")

for col, aoi in zip(cols, AOIS):
    s = latest_aoi_status(aoi["name"], "jamming")
    status = s.get("status") or "DATA LIMITED"
    status_class = (
        "normal" if status == "NORMAL"
        else "watch" if status == "WATCH"
        else "elevated" if status == "ELEVATED"
        else "impact" if status == "IMPACT"
        else "limited"
    )
    score = s.get("score")
    score_text = f"{float(score):.1f}% low NIC" if score is not None else "no persistent feed"
    confidence = s.get("confidence") or "—"
    freshness = age_minutes(s.get("observed_at"))
    freshness_text = f"{freshness}m" if freshness is not None else "—"

    with col:
        st.markdown(
            f"""
            <div class="aoi-header">
              <span class="aoi-name">{aoi["name"]}</span>
              {chip(status, status_class)}
            </div>
            <div class="tiny">
              GNSS · {score_text} · confidence {confidence} · {freshness_text} old
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            make_aoi_map(aoi),
            use_container_width=True,
            config={"displayModeBar": False, "scrollZoom": False},
        )


# ============================================================
# WATCH ITEMS / SPACE WEATHER / NEXT UP
# ============================================================
st.markdown("<div style='height:.22rem'></div>", unsafe_allow_html=True)
c1, c2, c3 = st.columns([1.4, 0.95, 1.2], gap="small")

watch_items = []

# GNSS AOI watch items
for aoi in AOIS:
    s = latest_aoi_status(aoi["name"], "jamming")
    status = s.get("status") or "DATA LIMITED"
    if status in ("WATCH", "ELEVATED", "IMPACT"):
        history = aoi_history(aoi["name"], "jamming")
        watch_items.append({
            "rank": status_rank(status) + 4,
            "title": f"GNSS · {aoi['name']}",
            "sub": (
                f"{float(s.get('score') or 0):.1f}% low NIC · "
                f"{trend_label(history, 6)} / 6h · confidence {s.get('confidence') or '—'}"
            ),
            "cls": status.lower(),
        })

# Spoofing events in AOIs
for aoi in AOIS:
    spoof = [e for e in events_in_aoi(aoi) if e.get("mode") == "spoofing"]
    if spoof:
        watch_items.append({
            "rank": 8,
            "title": f"SPOOFING · {aoi['name']}",
            "sub": f"{len(spoof)} detected event(s) in latest 24h · ADS-B derived",
            "cls": "elevated",
        })

# Orbital changes
for e in orbital_events[:6]:
    sev = (e.get("severity") or "WATCH").upper()
    watch_items.append({
        "rank": status_rank(sev) + 3,
        "title": f"SDA · {e.get('object_name') or e.get('norad_cat_id')}",
        "sub": f"{e.get('summary') or 'Candidate orbital change'} · confidence {e.get('confidence') or 'MED'}",
        "cls": sev.lower(),
    })

# Space weather
if wx_text != "NORMAL":
    watch_items.append({
        "rank": status_rank(wx_text) + 2,
        "title": "SPACE WEATHER",
        "sub": f"Kp {current_kp:.2f} · G{scales['G']} R{scales['R']} S{scales['S']} · possible PNT/HF relevance",
        "cls": wx_class,
    })

watch_items = sorted(watch_items, key=lambda x: x["rank"], reverse=True)[:5]

with c1:
    html = '<div class="panel"><div class="panel-title">WATCH ITEMS // PRIORITY</div>'
    if not watch_items:
        html += (
            '<div class="watch-item normal-item">'
            '<div class="wi-title">NO ACTIVE WATCH ITEMS</div>'
            '<div class="wi-sub">No rule-based anomaly currently exceeds configured thresholds.</div>'
            '</div>'
        )
    else:
        for w in watch_items:
            cls = w["cls"] if w["cls"] in ("normal","watch","elevated","impact","limited") else "limited"
            item_class = (
                "normal-item" if cls == "normal"
                else "elevated-item" if cls == "elevated"
                else "impact-item" if cls == "impact"
                else "limited-item" if cls == "limited"
                else ""
            )
            html += (
                f'<div class="watch-item {item_class}">'
                f'<div class="wi-title">{w["title"]}</div>'
                f'<div class="wi-sub">{w["sub"]}</div>'
                f'</div>'
            )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

with c2:
    st.markdown(
        f"""
        <div class="panel">
          <div class="panel-title">SPACE WEATHER</div>
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
              <div class="metric-label">PLANETARY Kp</div>
              <div class="big-value">{current_kp:.2f}</div>
            </div>
            <div>{chip(wx_text, wx_class)}</div>
          </div>
          <div class="metric-row"><span>NOAA scales</span><b>G{scales["G"]} · R{scales["R"]} · S{scales["S"]}</b></div>
          <div class="metric-row"><span>6h trend</span><b>{kp_trend(kp_df, 6)}</b></div>
          <div class="metric-row"><span>24h trend</span><b>{kp_trend(kp_df, 24)}</b></div>
          <div class="metric-row"><span>7d trend</span><b>{kp_trend(kp_df, 168)}</b></div>
          <div class="tiny" style="margin-top:.25rem">NOAA SWPC · live feed cached 5 min</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:
    future = pd.DataFrame()
    if not fc_df.empty:
        future = fc_df[fc_df["time"] > pd.Timestamp.now(tz="UTC")].head(4)

    html = '<div class="panel"><div class="panel-title">NEXT UP // AOI RELEVANT</div>'
    if not future.empty:
        for _, row in future.iterrows():
            local = row["time"].tz_convert(CET)
            html += (
                f'<div class="metric-row"><span>{local.strftime("%H:%M")} · Kp forecast</span>'
                f'<b>{row["kp"]:.2f}</b></div>'
            )
    else:
        html += '<div class="metric-row"><span>Space weather forecast</span><b>—</b></div>'

    # Orbital candidate events are observations, not predictions. Keep NEXT UP honest.
    html += (
        '<div class="metric-row"><span>AOI satellite passes</span><b>PHASE 4</b></div>'
        '<div class="metric-row"><span>Reentry windows</span><b>PHASE 4</b></div>'
        '<div class="tiny" style="margin-top:.25rem">Only actual forecastable data is shown as forecast.</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# GNSS TREND + SDA CHANGE PANEL
# ============================================================
st.markdown("<div style='height:.22rem'></div>", unsafe_allow_html=True)
t1, t2 = st.columns([1.75, 1.25], gap="small")

with t1:
    st.markdown('<div class="panel-title">GNSS INTERFERENCE TREND // 7 DAYS</div>', unsafe_allow_html=True)
    trend_rows = [r for r in gnss_history if r.get("mode") == "jamming"]
    if trend_rows:
        df = pd.DataFrame(trend_rows)
        df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True, errors="coerce")
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
        df = df.dropna(subset=["observed_at", "score"])
        fig = go.Figure()
        for aoi_name in ["DENMARK", "BALTIC", "ARCTIC"]:
            d = df[df["aoi"] == aoi_name]
            if d.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=d["observed_at"],
                    y=d["score"],
                    mode="lines",
                    name=aoi_name,
                    hovertemplate=f"{aoi_name}<br>%{{x|%d %b %H:%M UTC}}<br>%{{y:.1f}}% low NIC<extra></extra>",
                )
            )
        fig.add_hline(y=2, line_dash="dot", opacity=0.25)
        fig.add_hline(y=10, line_dash="dot", opacity=0.35)
        fig.update_layout(
            height=145,
            margin={"l": 5, "r": 5, "t": 4, "b": 4},
            paper_bgcolor="#071019",
            plot_bgcolor="#071019",
            font={"color": "#9fb6c8", "size": 9},
            legend={"orientation": "h", "y": 1.02, "x": 0.0},
            xaxis={"showgrid": False, "zeroline": False},
            yaxis={"title": "% low NIC", "showgrid": True, "gridcolor": "#173040", "zeroline": False},
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown(
            '<div class="panel"><div class="wi-sub">Persistent GNSS history appears here after Supabase + collector are connected.</div></div>',
            unsafe_allow_html=True,
        )

with t2:
    st.markdown('<div class="panel-title">SDA // ORBITAL CHANGE CANDIDATES</div>', unsafe_allow_html=True)
    if orbital_events:
        for e in orbital_events[:5]:
            dt = pd.to_datetime(e.get("detected_at"), utc=True, errors="coerce")
            local = dt.tz_convert(CET).strftime("%d %b %H:%M") if not pd.isna(dt) else "—"
            sev = (e.get("severity") or "WATCH").upper()
            st.markdown(
                f"""
                <div class="watch-item {'elevated-item' if sev == 'ELEVATED' else ''}">
                  <div class="wi-title">{e.get("object_name") or e.get("norad_cat_id")} · {sev}</div>
                  <div class="wi-sub">{e.get("summary") or 'Candidate orbital change'} · {local} · {e.get("group_name") or '—'}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="panel"><div class="wi-sub">No orbital-change candidates yet. The collector needs two CelesTrak snapshots before change detection can start.</div></div>',
            unsafe_allow_html=True,
        )


# ============================================================
# EVENT STREAM + STATUS BAR
# ============================================================
st.markdown("<div style='height:.16rem'></div>", unsafe_allow_html=True)

stream = []
for e in orbital_events[:8]:
    stream.append((
        e.get("detected_at"),
        f"SDA · {e.get('object_name') or e.get('norad_cat_id')} · {e.get('severity') or 'WATCH'}",
    ))
for e in gnss_events[:12]:
    stream.append((
        e.get("collected_at"),
        f"{(e.get('mode') or 'GNSS').upper()} · event near {float(e.get('lat') or 0):.1f}°, {float(e.get('lon') or 0):.1f}°",
    ))
stream = sorted(stream, key=lambda x: x[0] or "", reverse=True)[:6]

st.markdown('<div class="panel-title">EVENT STREAM // RECENT CHANGE</div>', unsafe_allow_html=True)
if stream:
    cols_ev = st.columns(3, gap="small")
    for i, (when, label) in enumerate(stream):
        dt = pd.to_datetime(when, utc=True, errors="coerce")
        stamp = dt.tz_convert(CET).strftime("%H:%M") if not pd.isna(dt) else "—"
        with cols_ev[i % 3]:
            st.markdown(f'<div class="eventline">{stamp} &nbsp; {label}</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="eventline">No persistent events yet.</div>', unsafe_allow_html=True)

pnt_statuses = [latest_aoi_status(a["name"], "jamming").get("status") for a in AOIS]
pnt_overall = highest_status(pnt_statuses)
sda_overall = highest_status([(e.get("severity") or "NORMAL") for e in orbital_events[:10]]) if orbital_events else "NORMAL"

def status_color(status):
    return {
        "NORMAL": "#71e6a8",
        "WATCH": "#f5c66a",
        "ELEVATED": "#ffae7b",
        "IMPACT": "#ff7f88",
        "DATA LIMITED": "#a9bfd0",
        "UNKNOWN": "#a9bfd0",
    }.get(status, "#a9bfd0")

st.markdown(
    f"""
    <div class="statusbar">
      <div class="statusbox">
        <span class="statusname">PNT</span>
        <span class="statusvalue" style="color:{status_color(pnt_overall)}">{pnt_overall}</span>
      </div>
      <div class="statusbox">
        <span class="statusname">SDA</span>
        <span class="statusvalue" style="color:{status_color(sda_overall)}">{sda_overall}</span>
      </div>
      <div class="statusbox">
        <span class="statusname">SPACE WX</span>
        <span class="statusvalue" style="color:{status_color(wx_text)}">{wx_text}</span>
      </div>
    </div>
    <div class="tiny" style="margin-top:.3rem">
      GNSS layer: Stanford GPS Lab ADS-B-derived interference data. SDA: conservative candidate detection from changes in public CelesTrak GP elements.
      A candidate is not proof of a manoeuvre or hostile activity. Detailed history target: 30 days.
    </div>
    """,
    unsafe_allow_html=True,
)
