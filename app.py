import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from skyfield.api import EarthSatellite, load
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Space Ops Room", page_icon="🛰️", layout="wide", initial_sidebar_state="collapsed")
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
        "center": {"lat": 56.1, "lon": 10.2},
        "zoom": 4.9,
        "capitals": [("Copenhagen", 55.6761, 12.5683)],
    },
    {
        "name": "BALTIC",
        "center": {"lat": 57.6, "lon": 20.5},
        "zoom": 3.5,
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
        "center": {"lat": 71.5, "lon": -18.0},
        "zoom": 1.9,
        "capitals": [
            ("Nuuk", 64.1835, -51.7216),
            ("Reykjavík", 64.1466, -21.9426),
            ("Oslo", 59.9139, 10.7522),
            ("Stockholm", 59.3293, 18.0686),
            ("Helsinki", 60.1699, 24.9384),
        ],
    },
]

st.markdown(
    """
    <style>
      :root {--bg:#071019;--panel:#0d1924;--panel2:#0a141d;--line:#203546;--text:#e8f1f7;--muted:#7890a3;--green:#71e6a8;--amber:#f5c66a;--red:#ff7f88;--white:#f5fbff;}
      html,body,[data-testid="stAppViewContainer"]{background:var(--bg);color:var(--text);}
      [data-testid="stHeader"],[data-testid="stToolbar"],#MainMenu,footer{visibility:hidden;height:0px;}
      .block-container{max-width:100%;padding:.55rem .8rem .5rem .8rem;}
      .ops-header{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1px solid var(--line);padding:.12rem 0 .5rem 0;margin-bottom:.5rem;}
      .ops-title{font-size:1.32rem;font-weight:800;letter-spacing:.08em;color:var(--white);}
      .ops-sub{font-size:.68rem;color:var(--muted);letter-spacing:.1em;margin-top:.12rem;}
      .live{font-size:.74rem;letter-spacing:.08em;color:var(--green);font-weight:800;}
      .panel{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line);border-radius:9px;padding:.6rem .7rem;height:100%;}
      .panel-title{font-size:.70rem;font-weight:800;letter-spacing:.11em;color:#9fb6c8;margin-bottom:.32rem;}
      .big-value{font-size:1.85rem;font-weight:800;color:var(--white);line-height:1;}
      .metric-label{color:var(--muted);font-size:.67rem;letter-spacing:.05em;}
      .metric-row{display:flex;justify-content:space-between;gap:.55rem;border-top:1px solid rgba(32,53,70,.75);padding:.32rem 0;font-size:.73rem;}
      .chip{display:inline-block;padding:.18rem .4rem;border-radius:999px;font-size:.62rem;font-weight:800;letter-spacing:.07em;border:1px solid;white-space:nowrap;}
      .normal{color:var(--green);border-color:#235b46;background:#0d2a20}.watch{color:var(--amber);border-color:#6b562b;background:#2a2110}.elevated{color:#ffae7b;border-color:#6e452a;background:#2c1a11}.impact{color:var(--red);border-color:#71353a;background:#2c1216}.limited{color:#a9bfd0;border-color:#3a5365;background:#12212c}
      .watch-item{border-left:3px solid var(--amber);padding:.38rem .5rem;margin:.28rem 0;background:#111d27;border-radius:4px;}
      .watch-item.normal-item{border-left-color:var(--green)}.watch-item.elevated-item{border-left-color:#ffae7b}
      .wi-title{font-size:.76rem;font-weight:800;color:var(--white);letter-spacing:.04em}.wi-sub{font-size:.65rem;color:var(--muted);margin-top:.1rem}
      .statusbar{display:grid;grid-template-columns:repeat(3,1fr);gap:.45rem;margin-top:.45rem}.statusbox{background:#0b1620;border:1px solid var(--line);border-radius:8px;padding:.45rem .6rem;display:flex;justify-content:space-between;align-items:center}.statusname{font-size:.68rem;color:#9fb6c8;font-weight:800;letter-spacing:.1em}.statusvalue{font-size:.72rem;font-weight:800}.tiny{font-size:.61rem;color:var(--muted)}.eventline{font-size:.66rem;color:#b4c6d3;padding:.14rem 0;border-top:1px solid rgba(32,53,70,.55)}
      .stDeployButton{display:none;}
    </style>
    """,
    unsafe_allow_html=True,
)

def safe_get_json(url, timeout=12):
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "space-opsroom/0.2"})
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
    try:
        r = requests.get(CELESTRAK_TLE, params={"GROUP": group, "FORMAT": "TLE"}, timeout=15, headers={"User-Agent": "space-opsroom/0.2"})
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
            rows.append({"time": pd.to_datetime(row["time_tag"], utc=True), "kp": float(row["Kp"])})
        except Exception:
            continue
    return pd.DataFrame(rows).sort_values("time")

def parse_forecast(f_json):
    if not f_json:
        return pd.DataFrame(columns=["time", "kp", "kind"])
    rows = []
    for row in f_json:
        try:
            rows.append({"time": pd.to_datetime(row["time_tag"], utc=True), "kp": float(row["kp"]), "kind": row.get("observed") or ""})
        except Exception:
            continue
    return pd.DataFrame(rows).sort_values("time")

def latest_scales(scales_json):
    if not isinstance(scales_json, dict):
        return {"G":0,"R":0,"S":0}
    row = scales_json.get("0", {})
    out = {}
    for key in ("G","R","S"):
        try:
            out[key] = int((row.get(key) or {}).get("Scale") or 0)
        except Exception:
            out[key] = 0
    return out

def kp_level(kp_value, scales):
    peak = max(scales.get("G",0), scales.get("R",0), scales.get("S",0))
    if peak >= 4 or kp_value >= 8: return "IMPACT","impact"
    if peak >= 2 or kp_value >= 6: return "ELEVATED","elevated"
    if peak >= 1 or kp_value >= 4: return "WATCH","watch"
    return "NORMAL","normal"

def trend_at(df, hours):
    if df.empty: return None
    latest = df.iloc[-1]
    target = latest["time"] - pd.Timedelta(hours=hours)
    previous = df[df["time"] <= target]
    if previous.empty: return None
    old = previous.iloc[-1]["kp"]
    delta = float(latest["kp"] - old)
    arrow = "↑" if delta > .34 else "↓" if delta < -.34 else "→"
    return arrow, delta

def fmt_trend(t):
    if not t: return "—"
    arrow, delta = t
    return f"{arrow} {delta:+.1f}"

def parse_tle_text(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    sats=[]; i=0
    while i+2 < len(lines):
        if lines[i+1].startswith("1 ") and lines[i+2].startswith("2 "):
            sats.append((lines[i],lines[i+1],lines[i+2])); i += 3
        else: i += 1
    return sats

def satellite_positions(tle_text, max_sats=40):
    if not tle_text: return []
    ts = load.timescale(); t = ts.now(); out=[]
    for name,l1,l2 in parse_tle_text(tle_text)[:max_sats]:
        try:
            sat = EarthSatellite(l1,l2,name,ts); sub = sat.at(t).subpoint()
            out.append({"name":name,"lat":float(sub.latitude.degrees),"lon":float(sub.longitude.degrees),"alt_km":float(sub.elevation.km)})
        except Exception: continue
    return out

def chip(text, level):
    return f'<span class="chip {level}">{text}</span>'

def make_aoi_map(aoi, gps_pos, gal_pos):
    fig = go.Figure()
    fig.add_trace(go.Scattermapbox(
        lat=[c[1] for c in aoi["capitals"]], lon=[c[2] for c in aoi["capitals"]],
        mode="markers+text", marker={"size":7}, text=[c[0] for c in aoi["capitals"]],
        textposition="top right", hovertemplate="<b>%{text}</b><extra>Capital</extra>", name="Capitals"))
    if gps_pos:
        fig.add_trace(go.Scattermapbox(lat=[p["lat"] for p in gps_pos], lon=[p["lon"] for p in gps_pos], mode="markers", marker={"size":4}, text=[p["name"] for p in gps_pos], hovertemplate="%{text}<extra>GPS</extra>", name="GPS"))
    if gal_pos:
        fig.add_trace(go.Scattermapbox(lat=[p["lat"] for p in gal_pos], lon=[p["lon"] for p in gal_pos], mode="markers", marker={"size":4}, text=[p["name"] for p in gal_pos], hovertemplate="%{text}<extra>Galileo</extra>", name="Galileo"))
    fig.update_layout(mapbox={"style":"carto-darkmatter","center":aoi["center"],"zoom":aoi["zoom"]},height=325,margin={"l":0,"r":0,"t":0,"b":0},paper_bgcolor="#071019",font={"color":"#dce9f2","size":9},showlegend=False)
    return fig

kp_json, forecast_json, scales_json, noaa_errors = get_noaa()
kp_df = parse_kp(kp_json)
fc_df = parse_forecast(forecast_json)
scales = latest_scales(scales_json)
gps_tle, gps_err = get_tle("GPS-OPS")
gal_tle, gal_err = get_tle("GALILEO")
gps_pos = satellite_positions(gps_tle,36)
gal_pos = satellite_positions(gal_tle,36)
current_kp = 0.0 if kp_df.empty else float(kp_df.iloc[-1]["kp"])
wx_text, wx_class = kp_level(current_kp, scales)
source_count = 3
source_ok = int(not noaa_errors)+int(not gps_err)+int(not gal_err)

st.markdown(f'''<div class="ops-header"><div><div class="ops-title">SPACE OPS // COMMON OPERATING PICTURE</div><div class="ops-sub">AOI STATUS · DENMARK · BALTIC · ARCTIC &nbsp;&nbsp;|&nbsp;&nbsp; OPEN SOURCES ONLY &nbsp;&nbsp;|&nbsp;&nbsp; V0.2</div></div><div style="text-align:right"><div class="live">● LIVE &nbsp; {NOW_LOCAL.strftime("%d %b %Y · %H:%M:%S %Z")}</div><div class="tiny">SOURCES {source_ok}/{source_count} ONLINE · AUTO REFRESH 30s</div></div></div>''', unsafe_allow_html=True)

cols = st.columns([1.0,1.15,1.15], gap="small")
for col,aoi in zip(cols,AOIS):
    with col:
        st.markdown(f'<div class="panel-title">{aoi["name"]} // LIVE GEOGRAPHIC VIEW</div>', unsafe_allow_html=True)
        st.plotly_chart(make_aoi_map(aoi,gps_pos,gal_pos), use_container_width=True, config={"displayModeBar":False,"scrollZoom":False})

st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
c1,c2,c3 = st.columns([1.35,1.0,1.25], gap="small")

with c1:
    html='<div class="panel"><div class="panel-title">WATCH ITEMS // PRIORITY</div>'
    watch_items=[]
    if wx_text != "NORMAL": watch_items.append(("SPACE WEATHER",f"Kp {current_kp:.2f} · possible PNT/HF relevance",wx_class))
    else: watch_items.append(("SPACE WEATHER",f"No active watch · Kp {current_kp:.2f}","normal"))
    watch_items.append(("SDA BASELINE",f"{len(gps_pos)+len(gal_pos)} PNT satellites propagated · manoeuvre detection not enabled yet","normal"))
    watch_items.append(("GNSS INTERFERENCE","Feed not connected yet · no inference made","limited"))
    for title,sub,cls in watch_items:
        item_class="normal-item" if cls=="normal" else "elevated-item" if cls in ("elevated","impact") else ""
        html += f'<div class="watch-item {item_class}"><div class="wi-title">{title}</div><div class="wi-sub">{sub}</div></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

with c2:
    st.markdown(f'''<div class="panel"><div class="panel-title">SPACE WEATHER</div><div style="display:flex;justify-content:space-between;align-items:flex-start"><div><div class="metric-label">PLANETARY Kp</div><div class="big-value">{current_kp:.2f}</div></div><div>{chip(wx_text,wx_class)}</div></div><div class="metric-row"><span>NOAA scales</span><b>G{scales["G"]} · R{scales["R"]} · S{scales["S"]}</b></div><div class="metric-row"><span>6h trend</span><b>{fmt_trend(trend_at(kp_df,6))}</b></div><div class="metric-row"><span>24h trend</span><b>{fmt_trend(trend_at(kp_df,24))}</b></div><div class="metric-row"><span>7d trend</span><b>{fmt_trend(trend_at(kp_df,168))}</b></div><div class="tiny" style="margin-top:.3rem">NOAA SWPC · cached 5 min</div></div>''', unsafe_allow_html=True)

with c3:
    future = pd.DataFrame()
    if not fc_df.empty: future = fc_df[fc_df["time"] > pd.Timestamp.now(tz="UTC")].head(4)
    html='<div class="panel"><div class="panel-title">NEXT UP // AOI RELEVANT</div>'
    if future.empty: html += '<div class="wi-sub">No forecast data available.</div>'
    else:
        for _,row in future.iterrows():
            local=row["time"].tz_convert(CET)
            html += f'<div class="metric-row"><span>{local.strftime("%H:%M")} · Kp forecast</span><b>{row["kp"]:.2f}</b></div>'
    html += '<div class="tiny" style="margin-top:.3rem">Satellite passes and reentry windows are added in later phases.</div></div>'
    st.markdown(html, unsafe_allow_html=True)

st.markdown("<div style='height:.3rem'></div>", unsafe_allow_html=True)
t1,t2 = st.columns([1.1,2.9], gap="small")
with t1:
    st.markdown('<div class="panel-title">EVENT STREAM // RECENT CHANGE</div>', unsafe_allow_html=True)
    if kp_df.empty: st.markdown('<div class="eventline">No event data.</div>', unsafe_allow_html=True)
    else:
        for _,row in kp_df.tail(5).iloc[::-1].iterrows():
            loc=row["time"].tz_convert(CET)
            st.markdown(f'<div class="eventline">{loc.strftime("%H:%M")} &nbsp; Kp {row["kp"]:.2f}</div>', unsafe_allow_html=True)
with t2:
    st.markdown('<div class="panel-title">Kp TREND // 7 DAYS</div>', unsafe_allow_html=True)
    if not kp_df.empty:
        kfig=go.Figure()
        kfig.add_trace(go.Scatter(x=kp_df["time"],y=kp_df["kp"],mode="lines",line={"width":2},hovertemplate="%{x|%d %b %H:%M UTC}<br>Kp %{y:.2f}<extra></extra>"))
        kfig.add_hline(y=5,line_dash="dot",opacity=.4)
        kfig.update_layout(height=135,margin={"l":5,"r":5,"t":5,"b":5},paper_bgcolor="#071019",plot_bgcolor="#071019",font={"color":"#9fb6c8","size":9},showlegend=False,xaxis={"showgrid":False,"zeroline":False},yaxis={"range":[0,9],"showgrid":True,"gridcolor":"#173040","zeroline":False})
        st.plotly_chart(kfig,use_container_width=True,config={"displayModeBar":False})

st.markdown(f'''<div class="statusbar"><div class="statusbox"><span class="statusname">PNT</span><span class="statusvalue" style="color:#a9bfd0">DATA LIMITED</span></div><div class="statusbox"><span class="statusname">SDA</span><span class="statusvalue" style="color:#71e6a8">BASELINE</span></div><div class="statusbox"><span class="statusname">SPACE WX</span><span class="statusvalue">{wx_text}</span></div></div><div class="tiny" style="margin-top:.35rem">V0.2 · all three AOIs visible simultaneously · detailed Carto basemaps · capitals marked instead of arbitrary AOI points.</div>''', unsafe_allow_html=True)
