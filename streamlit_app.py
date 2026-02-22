# Governance dashboard UI

import streamlit as st
import os
import time
from app import latest_state, carbon_state, escalation_log, _rag_state
from rag.advisory_engine import _scan_policy_files
from config import (
    STATIONS, CITY_NAMES, PERSISTENCE_THRESHOLD, HIGH_AQI_THRESHOLD,
    WINDOW_DURATION_MINUTES, WINDOW_HOP_MINUTES, STALE_DATA_THRESHOLD_SECONDS,
    POLICY_DIR,
)

st.set_page_config(
    page_title="AREE | Regulatory Escalation Engine",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def aqi_color(aqi):
    if aqi is None:
        return "#64748b"
    if aqi <= 50:
        return "#22c55e"
    if aqi <= 100:
        return "#84cc16"
    if aqi <= 200:
        return "#eab308"
    if aqi <= 300:
        return "#f97316"
    if aqi <= 400:
        return "#ef4444"
    return "#dc2626"


def grap_color(stage):
    s = str(stage)
    if "IV" in s:
        return "#dc2626"
    if "III" in s:
        return "#ef4444"
    if "II" in s:
        return "#f97316"
    if "I" in s and "II" not in s and "IV" not in s:
        return "#eab308"
    return "#22c55e"


# ── CSS ──
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap');

.stApp { background: #0a0f1a; color: #e2e8f0; font-family: 'Inter', -apple-system, sans-serif; }
.block-container { padding-top: 1rem !important; max-width: 100%; }
#MainMenu, footer, header { visibility: hidden }
div[data-testid="stMetric"] { display: none }
.stSelectbox label { color: #64748b !important; font-size: 11px !important; letter-spacing: 1px; text-transform: uppercase; font-weight: 600 !important; }
.stSelectbox > div > div { background: #111827 !important; border-color: #1e293b !important; color: #e2e8f0 !important; }
.sys-header { background: #111827; border: 1px solid #1e293b; border-radius: 8px; padding: 16px 24px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
.sys-title { font-size: 15px; font-weight: 700; color: #f1f5f9; letter-spacing: 1.5px }
.sys-sub { font-size: 11px; color: #475569; margin-top: 2px }
.live-ind { display: flex; align-items: center; gap: 6px }
.live-dot { width: 8px; height: 8px; background: #22c55e; border-radius: 50%; animation: pdot 2s ease-in-out infinite; }
@keyframes pdot { 0%, 100% { box-shadow: 0 0 0 0 rgba(34,197,94,0.4) } 50% { box-shadow: 0 0 0 6px rgba(34,197,94,0) } }
.live-lbl { color: #22c55e; font-size: 10px; font-weight: 600; letter-spacing: 1px }
.sec-h { font-size: 12px; font-weight: 700; color: #94a3b8; letter-spacing: 0.5px; margin: 20px 0 12px 0; padding-bottom: 6px; border-bottom: 1px solid #1e293b; }
.card { background: #111827; border: 1px solid #1e293b; border-radius: 8px; padding: 18px 20px; }
.card-label { font-size: 10px; font-weight: 600; color: #64748b; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 6px; }
.card-value { font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700; line-height: 1.1; }
.card-sub { font-size: 10px; color: #475569; margin-top: 4px }
.aqi-panel { background: #111827; border: 1px solid #1e293b; border-radius: 10px; padding: 32px; text-align: center; }
.aqi-number { font-family: 'JetBrains Mono', monospace; font-size: 64px; font-weight: 800; line-height: 1; margin: 4px 0; }
.aqi-band { font-size: 13px; font-weight: 700; letter-spacing: 0.5px }
.aqi-source { font-size: 10px; color: #475569; margin-top: 6px }
.grap-panel { background: #111827; border: 1px solid #1e293b; border-radius: 10px; padding: 24px; text-align: center; display: flex; flex-direction: column; justify-content: center; min-height: 160px; }
.grap-stage { font-size: 18px; font-weight: 800; margin: 6px 0 }
.grap-desc { font-size: 12px; color: #64748b }
.esc-triggered { background: rgba(239,68,68,0.06); border: 2px solid #ef4444; border-radius: 8px; padding: 16px 24px; text-align: center; animation: egl 2.5s ease-in-out infinite; }
@keyframes egl { 0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.2) } 50% { box-shadow: 0 0 12px 2px rgba(239,68,68,0.1) } }
.esc-watch { background: rgba(249,115,22,0.04); border: 2px solid #f97316; border-radius: 8px; padding: 16px 24px; text-align: center; }
.esc-normal { background: rgba(34,197,94,0.04); border: 2px solid #22c55e; border-radius: 8px; padding: 16px 24px; text-align: center; }
.esc-status { font-size: 16px; font-weight: 800; letter-spacing: 1.5px }
.esc-detail { font-size: 12px; color: #94a3b8; margin-top: 4px }
.prog-outer { background: #1e293b; border-radius: 4px; height: 4px; margin-top: 8px; overflow: hidden }
.prog-inner { height: 100%; border-radius: 4px; transition: width 0.5s }
.rule-box { background: #111827; border-left: 3px solid #3b82f6; border-radius: 0 6px 6px 0; padding: 12px 16px; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #94a3b8; line-height: 1.6; }
.adv-panel { background: #111827; border: 1px solid #1e293b; border-radius: 8px; padding: 20px 24px; }
.adv-st { font-size: 11px; font-weight: 700; color: #3b82f6; letter-spacing: 0.5px; margin: 14px 0 6px 0; padding-top: 10px; border-top: 1px solid #1e293b; }
.adv-st:first-child { border-top: none; margin-top: 0; padding-top: 0; }
.adv-text { font-family: 'JetBrains Mono', monospace; font-size: 11px; line-height: 1.7; color: #cbd5e1; white-space: pre-wrap; }
.rag-card { background: linear-gradient(145deg, #0f1a2e, #111827); border: 1px solid #1e3a5f; border-radius: 8px; padding: 16px 18px; }
.log-entry { background: #111827; border-left: 3px solid #ef4444; padding: 12px 16px; margin-bottom: 8px; border-radius: 0 6px 6px 0; }
.carbon-card { background: linear-gradient(145deg, #071a0f, #0d2818); border: 1px solid #14532d; border-radius: 8px; padding: 16px 18px; }
.carbon-lbl { font-size: 10px; font-weight: 600; color: #4ade80; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 6px; }
.carbon-val { font-family: 'JetBrains Mono', monospace; font-size: 20px; font-weight: 700; color: #86efac; }
.meth-box { background: #111827; border: 1px solid #1e293b; border-radius: 8px; padding: 18px 22px; }
.meth-text { font-size: 12px; line-height: 1.8; color: #94a3b8 }
.meth-hl { color: #e2e8f0; font-weight: 600 }
.val-card { background: #111827; border: 1px solid #1e293b; border-radius: 8px; padding: 16px 20px; text-align: center; }
.val-lbl { font-size: 10px; font-weight: 600; color: #64748b; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 6px }
.val-v { font-family: 'JetBrains Mono', monospace; font-size: 16px; font-weight: 700 }
.stale-banner { background: rgba(234,179,8,0.08); border: 2px solid #eab308; border-radius: 8px; padding: 12px 20px; text-align: center; margin-bottom: 16px; }
.stale-text { color: #eab308; font-size: 13px; font-weight: 700; letter-spacing: 0.5px }
.stale-sub { color: #94a3b8; font-size: 10px; margin-top: 4px }
.feed-err { background: rgba(239,68,68,0.05); border: 1px solid #7f1d1d; border-radius: 6px; padding: 10px 14px; margin-bottom: 16px; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="sys-header">
    <div>
        <div class="sys-title">AUTONOMOUS REGULATORY ESCALATION ENGINE</div>
        <div class="sys-sub">Real-Time Early Warning | Pathway Streaming | Satellite-Verified | CPCB Cross-Reference</div>
    </div>
    <div class="live-ind">
        <div class="live-dot"></div>
        <span class="live-lbl">STREAMING</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 1 — Monitoring Mode & Station Selection
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 1 — Monitoring Control</div>', unsafe_allow_html=True)

# Load Pan-India stations
from station_loader import get_all_stations
_all_stations = get_all_stations(STATIONS, limit=30)
_all_names = list(_all_stations.keys())

mode_col, sel_col = st.columns([1, 3])
with mode_col:
    view_mode = st.radio("Mode", ["Single Station", "National Overview"], index=0, label_visibility="collapsed")
with sel_col:
    if view_mode == "Single Station":
        selected = st.selectbox("Monitoring Sensor Node", _all_names, index=None)
    else:
        selected = st.selectbox("Focus Station (optional)", _all_names, index=None)

# ── NATIONAL OVERVIEW MODE ──
if view_mode == "National Overview":
    import pandas as pd
    st.markdown('<div class="sec-h">National Regulatory Overview</div>', unsafe_allow_html=True)

    _active = {k: v for k, v in latest_state.items()
               if isinstance(v, dict) and v.get("aqi") is not None and v.get("status") != "DATA_INVALID"}

    if _active:
        # Map visualization
        map_data = []
        for stn, vals in _active.items():
            stn_info = _all_stations.get(stn, STATIONS.get(stn, {}))
            if stn_info.get("lat") and stn_info.get("lon"):
                map_data.append({
                    "lat": stn_info["lat"],
                    "lon": stn_info["lon"],
                })
        if map_data:
            st.map(pd.DataFrame(map_data), zoom=4)

        # Top 5 Critical Stations
        t1, t2 = st.columns(2)
        top_aqi = sorted(_active.items(), key=lambda x: x[1].get("aqi", 0), reverse=True)[:5]
        top_eri = sorted(_active.items(), key=lambda x: x[1].get("eri_score", 0), reverse=True)[:5]

        with t1:
            st.markdown("""
            <div class="card" style="padding:12px 16px">
                <div class="card-label">Top 5 — Highest AQI</div>
            </div>""", unsafe_allow_html=True)
            for i, (stn, v) in enumerate(top_aqi):
                ac = aqi_color(v.get("aqi", 0))
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;padding:4px 8px;border-bottom:1px solid #1e293b">
                    <span style="color:#94a3b8;font-size:10px">#{i+1} {stn[:35]}</span>
                    <span style="color:{ac};font-weight:700;font-size:11px">{v.get('aqi', 0)}</span>
                </div>""", unsafe_allow_html=True)

        with t2:
            st.markdown("""
            <div class="card" style="padding:12px 16px">
                <div class="card-label">Top 5 — Highest ERI</div>
            </div>""", unsafe_allow_html=True)
            for i, (stn, v) in enumerate(top_eri):
                eri = v.get("eri_score", 0)
                ec = "#dc2626" if eri >= 76 else "#ef4444" if eri >= 51 else "#eab308" if eri >= 26 else "#22c55e"
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;padding:4px 8px;border-bottom:1px solid #1e293b">
                    <span style="color:#94a3b8;font-size:10px">#{i+1} {stn[:35]}</span>
                    <span style="color:{ec};font-weight:700;font-size:11px">{eri}</span>
                </div>""", unsafe_allow_html=True)

        st.markdown(f"""
        <div style="text-align:center;padding:8px 0">
            <span style="color:#334155;font-size:9px">{len(_active)} active stations | {len(_all_stations)} available | Auto-updated | WAQI Direct</span>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="card" style="text-align:center;padding:30px">
            <div style="color:#475569;font-size:11px">No station data yet. Select stations above and wait for data to stream...</div>
        </div>""", unsafe_allow_html=True)

    if not selected:
        st.stop()

if not selected:
    st.markdown("""
    <div style="background:rgba(234,179,8,0.08);border:2px solid #eab308;border-radius:8px;
                padding:40px;text-align:center;margin-top:20px">
        <div style="color:#eab308;font-size:15px;font-weight:700">Operator must select monitoring node</div>
        <div style="color:#94a3b8;font-size:11px;margin-top:6px">Select a station from the dropdown above to begin.</div>
    </div>""", unsafe_allow_html=True)
    st.stop()
info = _all_stations.get(selected, STATIONS.get(selected, {}))
data = latest_state.get(selected)

# Station metadata
st.markdown(f"""
<div style="display:flex;gap:20px;margin-top:6px;flex-wrap:wrap">
    <span style="color:#475569;font-size:10px">Latitude: <span style="color:#94a3b8">{info['lat']}</span></span>
    <span style="color:#475569;font-size:10px">Longitude: <span style="color:#94a3b8">{info['lon']}</span></span>
    <span style="color:#475569;font-size:10px">Feed: <span style="color:#94a3b8">{info['feed_id']}</span></span>
    <span style="color:#475569;font-size:10px">Source: <span style="color:#94a3b8">WAQI Real-Time Feed</span></span>
</div>
""", unsafe_allow_html=True)

if not data:
    st.markdown("""
    <div style="background:#111827; border:1px solid #1e293b; border-radius:8px;
                padding:80px; text-align:center">
        <div style="color:#64748b; font-size:13px; font-weight:600;
                    letter-spacing:1px">AWAITING TELEMETRY</div>
        <div style="color:#475569; font-size:11px; margin-top:6px">
            Pathway engine initializing. Data appears on first window close.</div>
    </div>
    """, unsafe_allow_html=True)
    time.sleep(3)
    st.rerun()

# ── Extract state ──
aqi = data.get("aqi", 0)
band = data.get("cpcb_band", "---")
grap = data.get("grap_stage", "---")
gdesc = data.get("grap_description", "")
consec = data.get("consecutive_windows", 0)
remaining = data.get("remaining_windows", PERSISTENCE_THRESHOLD)
projected = data.get("projected_trigger_time", "---")
gov_rule = data.get("governance_rule", "")
idx_type = data.get("rag_index_type", "Embedded Vector Index")
dominant = data.get("dominant_pollutant", "—")
n_poll = data.get("pollutants_available", 0)
waqi_aqi = data.get("waqi_aqi")
feed_id = data.get("feed_id", "")
waqi_ts = data.get("waqi_timestamp", "")
station_name_api = data.get("station_name_api", "")
stale_sec = data.get("stale_seconds")
api_time = data.get("api_time", "")
ingestion_status = data.get("ingestion_status", "ok")
ingestion_error = data.get("ingestion_error")
ac = aqi_color(aqi)
gc = grap_color(grap)
pct = min(100, int((consec / max(PERSISTENCE_THRESHOLD, 1)) * 100))
pc = "#ef4444" if pct >= 100 else "#f97316" if pct >= 50 else "#22c55e"

# ── STALE DATA WARNING ──
if stale_sec is not None and stale_sec > STALE_DATA_THRESHOLD_SECONDS:
    stale_min = int(stale_sec / 60)
    st.markdown(f"""
    <div class="stale-banner">
        <div class="stale-text">⚠ STALE DATA WARNING</div>
        <div class="stale-sub">WAQI timestamp is {stale_min} minutes old. Data may not reflect current conditions.</div>
    </div>""", unsafe_allow_html=True)

# ── INGESTION ERROR BANNER ──
if ingestion_status == "error" and ingestion_error:
    st.markdown(f"""
    <div class="feed-err">
        <span style="color:#ef4444;font-size:11px;font-weight:700">WAQI FEED TEMPORARILY UNAVAILABLE</span>
        <span style="color:#94a3b8;font-size:10px;margin-left:8px">{ingestion_error}</span>
    </div>""", unsafe_allow_html=True)


# ── AQI + GRAP panels ──
c1, c2 = st.columns([1, 1])
with c1:
    st.markdown(f"""
    <div class="aqi-panel">
        <div class="card-label">WAQI AQI (Direct from API)</div>
        <div class="aqi-number" style="color:{ac}">{aqi}</div>
        <div class="aqi-band" style="color:{ac}">{band}</div>
        <div class="aqi-source">Dominant: {dominant} | {n_poll} pollutants | Feed: {feed_id}</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""
    <div class="grap-panel">
        <div class="card-label">GRAP Regulatory Stage (Engine)</div>
        <div class="grap-stage" style="color:{gc}">{grap}</div>
        <div class="grap-desc">{gdesc}</div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 2 — Data Source Transparency
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 2 — Data Source Transparency</div>', unsafe_allow_html=True)

freshness_txt = f"{int(stale_sec)}s ago" if stale_sec is not None else "—"
freshness_clr = "#ef4444" if (stale_sec and stale_sec > STALE_DATA_THRESHOLD_SECONDS) else "#22c55e" if stale_sec is not None else "#64748b"

t1, t2, t3, t4, t5, t6 = st.columns(6)
with t1:
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:14px">
        <div class="card-label">WAQI Feed ID</div>
        <div style="color:#e2e8f0;font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700">{feed_id}</div>
    </div>""", unsafe_allow_html=True)
with t2:
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:14px">
        <div class="card-label">WAQI AQI</div>
        <div style="color:{ac};font-family:'JetBrains Mono',monospace;font-size:18px;font-weight:700">{waqi_aqi if waqi_aqi else '—'}</div>
    </div>""", unsafe_allow_html=True)
with t3:
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:14px">
        <div class="card-label">WAQI Timestamp</div>
        <div style="color:#e2e8f0;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600">{waqi_ts if waqi_ts else '—'}</div>
    </div>""", unsafe_allow_html=True)
with t4:
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:14px">
        <div class="card-label">Station Name (API)</div>
        <div style="color:#e2e8f0;font-size:11px;font-weight:600">{station_name_api if station_name_api else '—'}</div>
    </div>""", unsafe_allow_html=True)
with t5:
    pm25_v = data.get("raw_pm25")
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:14px">
        <div class="card-label">Raw PM2.5</div>
        <div style="color:#e2e8f0;font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700">{pm25_v if pm25_v is not None else '—'}</div>
    </div>""", unsafe_allow_html=True)
with t6:
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:14px">
        <div class="card-label">API Freshness</div>
        <div style="color:{freshness_clr};font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700">{freshness_txt}</div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 3 — Official Regulatory Context
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 3 — Official Regulatory Context</div>', unsafe_allow_html=True)

v1, v2, v3, v4 = st.columns(4)
with v1:
    if aqi >= HIGH_AQI_THRESHOLD and consec >= PERSISTENCE_THRESHOLD:
        mode_lbl, mode_clr = "TRIGGERED", "#ef4444"
    elif aqi >= HIGH_AQI_THRESHOLD and consec > 0:
        mode_lbl, mode_clr = "WATCH", "#f97316"
    else:
        mode_lbl, mode_clr = "NORMAL", "#22c55e"
    st.markdown(f"""
    <div class="val-card">
        <div class="val-lbl">Engine Mode</div>
        <div class="val-v" style="color:{mode_clr}">{mode_lbl}</div>
        <div class="card-sub">AQI threshold + persistence</div>
    </div>""", unsafe_allow_html=True)
with v2:
    st.markdown(f"""
    <div class="val-card">
        <div class="val-lbl">Data Type</div>
        <div class="val-v" style="color:#e2e8f0;font-size:13px">Real-Time Short Window</div>
        <div class="card-sub">Not 24h composite. Early warning.</div>
    </div>""", unsafe_allow_html=True)
with v3:
    st.markdown(f"""
    <div class="val-card">
        <div class="val-lbl">API Response</div>
        <div class="val-v" style="color:#94a3b8;font-size:14px">{api_time} UTC</div>
        <div class="card-sub">Last successful poll</div>
    </div>""", unsafe_allow_html=True)
with v4:
    st.markdown(f"""
    <div class="val-card">
        <div class="val-lbl">WAQI Timestamp</div>
        <div class="val-v" style="color:#94a3b8;font-size:12px">{waqi_ts if waqi_ts else '—'}</div>
        <div class="card-sub">From WAQI payload</div>
    </div>""", unsafe_allow_html=True)

# Pollutant checkmarks
st.markdown('<div style="margin-top:10px"></div>', unsafe_allow_html=True)
pm25 = data.get("raw_pm25")
pm10_v = data.get("raw_pm10")
no2_v = data.get("raw_no2")
so2_v = data.get("raw_so2")
o3_v = data.get("raw_o3")
co_v = data.get("raw_co")
pollutant_items = [
    ("PM2.5", pm25), ("PM10", pm10_v), ("NO2", no2_v),
    ("SO2", so2_v), ("O3", o3_v), ("CO", co_v),
]
poll_html = '<div style="display:flex;gap:16px;flex-wrap:wrap">'
for name, val in pollutant_items:
    if val is not None:
        poll_html += f'<span style="color:#22c55e;font-size:12px;font-weight:600">&#10004; {name} <span style="color:#94a3b8;font-weight:400">({val})</span></span>'
    else:
        poll_html += f'<span style="color:#334155;font-size:12px">&#10008; {name}</span>'
poll_html += '</div>'
st.markdown(f"""
<div class="card" style="padding:14px 18px">
    <div class="card-label">Pollutants Received</div>
    {poll_html}
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 4 — Persistence Engine Status
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 4 — Persistence Engine Status</div>', unsafe_allow_html=True)

if consec >= PERSISTENCE_THRESHOLD:
    bcls, bclr = "esc-triggered", "#ef4444"
    btxt = "ESCALATION TRIGGERED"
    bdet = f"{consec} consecutive windows with AQI >= {HIGH_AQI_THRESHOLD}. Immediate regulatory action required."
elif aqi >= HIGH_AQI_THRESHOLD and consec > 0:
    bcls, bclr = "esc-watch", "#f97316"
    btxt = "ESCALATION WATCH"
    bdet = f"{consec}/{PERSISTENCE_THRESHOLD} windows. {remaining} remaining. Projected: {projected}"
else:
    bcls, bclr = "esc-normal", "#22c55e"
    btxt = "NORMAL OPERATIONS"
    bdet = f"No sustained readings above {HIGH_AQI_THRESHOLD}."

st.markdown(f"""
<div class="{bcls}">
    <div class="esc-status" style="color:{bclr}">{btxt}</div>
    <div class="esc-detail">{bdet}</div>
</div>""", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f"""
    <div class="card">
        <div class="card-label">Persistence</div>
        <div class="card-value" style="color:{pc}">{consec}/{PERSISTENCE_THRESHOLD}</div>
        <div class="card-sub">consecutive windows</div>
        <div class="prog-outer"><div class="prog-inner" style="width:{pct}%;background:{pc}"></div></div>
    </div>""", unsafe_allow_html=True)
with m2:
    rc = "#22c55e" if remaining > 0 else "#ef4444"
    st.markdown(f"""
    <div class="card">
        <div class="card-label">Remaining</div>
        <div class="card-value" style="color:{rc}">{remaining}</div>
        <div class="card-sub">windows to threshold</div>
    </div>""", unsafe_allow_html=True)
with m3:
    pjc = "#ef4444" if projected == "ACTIVE NOW" else "#eab308"
    st.markdown(f"""
    <div class="card">
        <div class="card-label">Projected Trigger</div>
        <div class="card-value" style="color:{pjc};font-size:20px">{projected}</div>
        <div class="card-sub">from window timestamp</div>
    </div>""", unsafe_allow_html=True)
with m4:
    st.markdown(f"""
    <div class="card">
        <div class="card-label">Last Data Update</div>
        <div class="card-value" style="color:#94a3b8;font-size:16px">{api_time} UTC</div>
        <div class="card-sub">data freshness</div>
    </div>""", unsafe_allow_html=True)

rule_text = gov_rule if gov_rule else (
    f"AQI >= {HIGH_AQI_THRESHOLD} | {PERSISTENCE_THRESHOLD} Consecutive Windows | "
    f"{WINDOW_DURATION_MINUTES}min Sliding | {WINDOW_HOP_MINUTES}min Hop | "
    f"Hysteresis: 2 Confirmations | Protocol: CAQM GRAP Escalation"
)
st.markdown(f'<div class="rule-box">{rule_text}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 5 — Satellite Transport Intelligence
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 5 — Satellite Transport Intelligence</div>', unsafe_allow_html=True)

fire_count = data.get("fire_count", 0)
high_fires = data.get("high_conf_fires", 0)
t_score = data.get("transport_score", 0)
t_label = data.get("transport_label", "none")
a_fires = data.get("aligned_fires", 0)
conf = data.get("confidence_score", 50)
w_spd = data.get("wind_speed")
w_dir = data.get("wind_direction")
firms_sync = data.get("firms_sync", "—")
firms_status = data.get("firms_status", "awaiting")
firms_error = data.get("firms_error")
firms_ds = data.get("firms_dataset", "VIIRS_SNPP_NRT")

tl_map = {
    "regional_transport": ("#ef4444", "Regional Transport Likely"),
    "possible_transport": ("#f97316", "Possible Transport"),
    "local_emission": ("#22c55e", "Local Emission Dominant"),
    "calm": ("#64748b", "Wind Calm — Transport Unlikely"),
    "none": ("#64748b", "No High-Confidence Thermal Anomalies Detected"),
}
tl_clr, tl_txt = tl_map.get(t_label, ("#64748b", "Awaiting Satellite Data"))

s1, s2, s3, s4, s5 = st.columns(5)
with s1:
    fc_clr = "#ef4444" if fire_count > 5 else "#eab308" if fire_count > 0 else "#22c55e"
    st.markdown(f"""
    <div class="card" style="text-align:center">
        <div class="card-label">Fire Hotspots</div>
        <div class="card-value" style="color:{fc_clr}">{fire_count}</div>
        <div class="card-sub">{high_fires} high confidence</div>
    </div>""", unsafe_allow_html=True)
with s2:
    ts_clr = "#ef4444" if t_score > 50 else "#eab308" if t_score > 20 else "#22c55e"
    st.markdown(f"""
    <div class="card" style="text-align:center">
        <div class="card-label">Transport Score</div>
        <div class="card-value" style="color:{ts_clr}">{t_score}/100</div>
        <div class="card-sub">{a_fires} aligned fires</div>
    </div>""", unsafe_allow_html=True)
with s3:
    if w_spd is not None:
        w_s = f"{w_spd:.1f}"
        w_d_txt = f"{w_dir:.0f}°" if w_dir is not None else "—"
        wind_sub = f"Direction: {w_d_txt}"
    else:
        w_s = "—"
        wind_sub = "Wind telemetry unavailable from source feed"
    st.markdown(f"""
    <div class="card" style="text-align:center">
        <div class="card-label">Wind</div>
        <div class="card-value" style="color:#e2e8f0;font-size:16px">{w_s} m/s</div>
        <div class="card-sub">{wind_sub}</div>
    </div>""", unsafe_allow_html=True)
with s4:
    st.markdown(f"""
    <div class="card" style="text-align:center">
        <div class="card-label">Transport Source</div>
        <div style="color:{tl_clr};font-size:12px;font-weight:700;margin-top:8px">{tl_txt}</div>
    </div>""", unsafe_allow_html=True)
with s5:
    cf_clr = "#22c55e" if conf >= 70 else "#eab308" if conf >= 50 else "#ef4444"
    st.markdown(f"""
    <div class="card" style="text-align:center">
        <div class="card-label">Confidence</div>
        <div class="card-value" style="color:{cf_clr}">{conf}%</div>
        <div class="card-sub">AQI + satellite + wind</div>
    </div>""", unsafe_allow_html=True)

# NASA governance row
n1, n2, n3, n4 = st.columns(4)
with n1:
    status_clr = "#22c55e" if firms_status == "ok" else "#eab308" if firms_status == "awaiting" else "#ef4444"
    status_txt = "Active" if firms_status == "ok" else "Awaiting" if firms_status == "awaiting" else "Error"
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:12px">
        <div class="card-label">FIRMS Status</div>
        <div style="color:{status_clr};font-size:12px;font-weight:700">{status_txt}</div>
    </div>""", unsafe_allow_html=True)
with n2:
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:12px">
        <div class="card-label">Last NASA Sync</div>
        <div style="color:#e2e8f0;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:600">{firms_sync} UTC</div>
    </div>""", unsafe_allow_html=True)
with n3:
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:12px">
        <div class="card-label">Dataset</div>
        <div style="color:#e2e8f0;font-size:11px;font-weight:600">{firms_ds}</div>
    </div>""", unsafe_allow_html=True)
with n4:
    bbox = data.get("fire_bbox", "—")
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:12px">
        <div class="card-label">Bounding Box</div>
        <div style="color:#94a3b8;font-family:'JetBrains Mono',monospace;font-size:10px">{bbox if bbox else '—'}</div>
    </div>""", unsafe_allow_html=True)

if firms_error:
    st.markdown(f"""
    <div class="feed-err">
        <span style="color:#ef4444;font-size:10px;font-weight:600">SATELLITE VERIFICATION TEMPORARILY UNAVAILABLE</span>
        <span style="color:#94a3b8;font-size:10px;margin-left:8px">{firms_error}</span>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 6 — Data Methodology
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 6 — Data Methodology and Validation</div>', unsafe_allow_html=True)

st.markdown(f"""
<div class="meth-box">
    <div class="meth-text">
        <span class="meth-hl">WAQI AQI</span> is used directly from the API payload for all escalation logic.
        This value is the US EPA-standard AQI reported by the WAQI network.
        PM2.5 concentration is displayed in the transparency panel for reference only.
        Currently receiving <span class="meth-hl">{n_poll} of 6</span> pollutants.
    </div>
    <div class="meth-text" style="margin-top:10px">
        <span class="meth-hl">Escalation logic</span> triggers when WAQI AQI >= {HIGH_AQI_THRESHOLD}
        is sustained across {PERSISTENCE_THRESHOLD} consecutive sliding windows
        ({WINDOW_DURATION_MINUTES}min duration, {WINDOW_HOP_MINUTES}min hop).
        All decisions are traceable to the WAQI payload timestamp and feed ID.
    </div>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 7 — Regulatory Advisory
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 7 — Regulatory Advisory</div>', unsafe_allow_html=True)

advisory = data.get("advisory_text", "")
sections = {}
current_name = None
current_lines = []
for line in advisory.split("\n"):
    stripped = line.strip()
    if stripped and all(c == "=" for c in stripped):
        continue
    if (stripped and ":" not in stripped and not stripped.startswith("-")
            and not stripped.startswith(" ") and len(stripped) < 30
            and stripped == stripped.upper()):
        if current_name and current_lines:
            sections[current_name] = "\n".join(current_lines)
        current_name = stripped
        current_lines = []
    else:
        if stripped:
            current_lines.append(line)
if current_name and current_lines:
    sections[current_name] = "\n".join(current_lines)

panel_html = '<div class="adv-panel">'
for title, body in sections.items():
    panel_html += f'<div class="adv-st">{title}</div>'
    panel_html += f'<div class="adv-text">{body}</div>'
if not sections:
    panel_html += f'<div class="adv-text">{advisory}</div>'
panel_html += "</div>"
st.markdown(panel_html, unsafe_allow_html=True)

# Decision Trace Block
if data:
    _consec = data.get('consecutive_windows', 0)
    _thresh = 300
    _pers = 3
    _esc_status = 'TRIGGERED' if _consec >= _pers else 'Not triggered'
    _eng_mode = 'TRIGGERED' if _consec >= _pers else ('WATCH' if _consec > 0 else 'NORMAL')
    _mode_col = '#ef4444' if _eng_mode == 'TRIGGERED' else '#eab308' if _eng_mode == 'WATCH' else '#22c55e'
    st.markdown(f"""
    <div style="background:rgba(30,41,59,0.5);border:1px solid #334155;border-radius:6px;padding:10px 14px;margin-top:8px">
        <div style="color:#64748b;font-size:9px;font-weight:700;letter-spacing:1px;margin-bottom:6px">DECISION TRACE</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#94a3b8;line-height:1.9">
            Input AQI: <span style="color:#e2e8f0;font-weight:600">{data.get('aqi', 0)}</span><br>
            Threshold: <span style="color:#e2e8f0">{_thresh}</span><br>
            Persistence: <span style="color:#e2e8f0">{_consec}/{_pers}</span><br>
            Hysteresis: <span style="color:#e2e8f0">2 confirmations</span><br>
            Engine Mode: <span style="color:{_mode_col};font-weight:700">{_eng_mode}</span><br>
            Escalation: <span style="color:{'#ef4444' if _esc_status == 'TRIGGERED' else '#22c55e'};font-weight:600">{_esc_status}</span><br>
            Reason: AQI {data.get('aqi', 0)} {'≥' if data.get('aqi', 0) >= _thresh else '<'} {_thresh} for {_consec} window(s)
        </div>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
# SECTION 8 — Policy Retrieval Intelligence
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 8 — Policy Retrieval Intelligence</div>', unsafe_allow_html=True)

r1, r2, r3, r4, r5 = st.columns(5)
with r1:
    st.markdown(f"""
    <div class="rag-card">
        <div class="card-label">Index Type</div>
        <div style="color:#3b82f6;font-size:12px;font-weight:600">{idx_type}</div>
    </div>""", unsafe_allow_html=True)
with r2:
    st.markdown(f"""
    <div class="rag-card">
        <div class="card-label">Source Document</div>
        <div style="color:#e2e8f0;font-size:11px;font-weight:600;word-break:break-all">{data.get('rag_policy_file','N/A')}</div>
    </div>""", unsafe_allow_html=True)
with r3:
    s = data.get("rag_similarity_score", 0.0)
    sc = "#22c55e" if s > 0.5 else "#eab308" if s > 0.3 else "#ef4444"
    st.markdown(f"""
    <div class="rag-card">
        <div class="card-label">Similarity</div>
        <div style="color:{sc};font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700">{s}</div>
    </div>""", unsafe_allow_html=True)
with r4:
    st.markdown(f"""
    <div class="rag-card">
        <div class="card-label">Last Sync</div>
        <div style="color:#e2e8f0;font-size:12px;font-weight:600">{data.get('rag_last_updated','N/A')}</div>
    </div>""", unsafe_allow_html=True)
with r5:
    st.markdown(f"""
    <div class="rag-card">
        <div class="card-label">Docs Indexed</div>
        <div style="color:#e2e8f0;font-family:'JetBrains Mono',monospace;font-size:16px;font-weight:700">{data.get('rag_docs_indexed','—')}</div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 9 — Escalation History
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 9 — Escalation History</div>', unsafe_allow_html=True)

if len(escalation_log) == 0:
    st.markdown("""
    <div class="card" style="text-align:center;padding:20px">
        <div style="color:#475569;font-size:11px">No escalation events recorded.</div>
    </div>""", unsafe_allow_html=True)
else:
    for e in list(escalation_log)[:8]:
        ts = e.get("timestamp", "")
        log_city = e.get("city", "")
        log_aqi = e.get("aqi", "")
        log_from = e.get("from_stage", "")
        log_to = e.get("to_stage", "")
        log_trigger = e.get("trigger", "")
        log_band = e.get("band", "")
        st.markdown(f"""
        <div class="log-entry">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-weight:700;color:#f1f5f9;font-size:13px">{log_city}</span>
                <span style="font-size:9px;color:#475569;font-family:'JetBrains Mono',monospace">{ts} UTC</span>
            </div>
            <div style="margin-top:6px;font-size:11px;color:#94a3b8;line-height:1.7">
                AQI: <span style="color:#e2e8f0;font-weight:600">{log_aqi}</span> ({log_band})<br>
                Previous Stage: <span style="color:#e2e8f0">{log_from}</span><br>
                New Stage: <span style="color:#ef4444;font-weight:600">{log_to}</span><br>
                Reason: {log_trigger}
            </div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 10 — Carbon Intensity
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 10 — Carbon Intensity</div>', unsafe_allow_html=True)

g1, g2, g3 = st.columns(3)
with g1:
    st.markdown(f"""
    <div class="carbon-card">
        <div class="carbon-lbl">Total Emissions</div>
        <div class="carbon-val">{carbon_state.get('total_gco2', 0.0)} <span style="font-size:11px">gCO2eq</span></div>
    </div>""", unsafe_allow_html=True)
with g2:
    st.markdown(f"""
    <div class="carbon-card">
        <div class="carbon-lbl">Decisions Processed</div>
        <div class="carbon-val">{carbon_state.get('decision_count', 0)}</div>
    </div>""", unsafe_allow_html=True)
with g3:
    st.markdown(f"""
    <div class="carbon-card">
        <div class="carbon-lbl">Per-Decision</div>
        <div class="carbon-val">{carbon_state.get('per_decision_gco2', 0.0)} <span style="font-size:11px">gCO2eq</span></div>
    </div>""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center;padding:6px 0">
    <span style="color:#334155;font-size:9px">Carbon model: deterministic per-event cost assumption</span>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
# SECTION 11 — Predictive Intelligence
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 11 — Predictive Intelligence</div>', unsafe_allow_html=True)

forecast = data.get("forecast") if data else None
if forecast:
    trend_color = "#22c55e" if forecast["direction"] == "falling" else "#ef4444" if forecast["direction"] == "rising" else "#eab308"
    trend_icon = "📈" if forecast["direction"] == "rising" else "📉" if forecast["direction"] == "falling" else "➡️"
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown(f"""
        <div class="card" style="text-align:center;padding:14px">
            <div class="card-label">Trend Direction</div>
            <div style="color:{trend_color};font-size:16px;font-weight:700">{trend_icon} {forecast['direction'].upper()}</div>
            <div class="card-sub">Rate: {forecast['rate_per_min']} AQI/min</div>
        </div>""", unsafe_allow_html=True)
    with p2:
        proj_col = "#ef4444" if forecast["projected_5min"] >= 300 else "#eab308" if forecast["projected_5min"] >= 200 else "#22c55e"
        st.markdown(f"""
        <div class="card" style="text-align:center;padding:14px">
            <div class="card-label">Projected AQI (5 min)</div>
            <div style="color:{proj_col};font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700">{forecast['projected_5min']}</div>
            <div class="card-sub">Predicted GRAP: {forecast['predicted_grap']}</div>
        </div>""", unsafe_allow_html=True)
    with p3:
        eta_text = f"~{forecast['escalation_eta']} min" if forecast['escalation_eta'] else "No imminent escalation"
        eta_col = "#ef4444" if forecast['escalation_eta'] and forecast['escalation_eta'] < 15 else "#22c55e"
        st.markdown(f"""
        <div class="card" style="text-align:center;padding:14px">
            <div class="card-label">Escalation ETA</div>
            <div style="color:{eta_col};font-size:14px;font-weight:700">{eta_text}</div>
            <div class="card-sub">Data points: {forecast['data_points']}</div>
        </div>""", unsafe_allow_html=True)

    # Anomaly flag
    if forecast.get("anomaly"):
        st.markdown("""
        <div style="background:rgba(239,68,68,0.06);border:2px solid #ef4444;border-radius:8px;padding:10px 16px;margin-top:8px;text-align:center">
            <span style="color:#ef4444;font-size:12px;font-weight:700">⚠ ANOMALY DETECTED</span>
            <span style="color:#94a3b8;font-size:10px;margin-left:8px">Current AQI deviates significantly from recent trend (z-score &gt; 2σ)</span>
        </div>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="text-align:center;padding:4px 0">
        <span style="color:#334155;font-size:9px">Linear regression on last {forecast['data_points']} windows | Slope: {forecast['slope']} | Deterministic (no external API)</span>
    </div>""", unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="card" style="text-align:center;padding:20px">
        <div style="color:#475569;font-size:11px">Collecting data points... (need ≥3 windows for prediction)</div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 12 — Escalation Readiness Index (ERI)
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 12 — Escalation Readiness Index</div>', unsafe_allow_html=True)

eri_score = data.get("eri_score", 0) if data else 0
eri_cat = data.get("eri_category", "LOW READINESS") if data else "LOW READINESS"
eri_factors = data.get("eri_factors", []) if data else []

eri_col = "#dc2626" if eri_score >= 76 else "#ef4444" if eri_score >= 51 else "#eab308" if eri_score >= 26 else "#22c55e"

e1, e2 = st.columns([1, 2])
with e1:
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:18px">
        <div class="card-label">ERI Score</div>
        <div style="color:{eri_col};font-family:'JetBrains Mono',monospace;font-size:32px;font-weight:700">{eri_score}</div>
        <div style="color:{eri_col};font-size:11px;font-weight:700;margin-top:4px">{eri_cat}</div>
        <div style="background:#1e293b;border-radius:4px;height:8px;margin-top:8px;overflow:hidden">
            <div style="background:{eri_col};width:{eri_score}%;height:100%"></div>
        </div>
    </div>""", unsafe_allow_html=True)
with e2:
    if eri_factors:
        factors_html = "".join([f'<div style="color:#e2e8f0;font-size:10px;font-family:\'JetBrains Mono\',monospace;line-height:1.9">+ {f}</div>' for f in eri_factors])
    else:
        factors_html = '<div style="color:#22c55e;font-size:10px">No escalation factors active</div>'
    st.markdown(f"""
    <div class="card" style="padding:14px 18px">
        <div class="card-label">Contributing Factors</div>
        {factors_html}
    </div>""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center;padding:4px 0">
    <span style="color:#334155;font-size:9px">ERI is advisory only. Does NOT affect GRAP trigger logic. Formula: AQI>=200(+40) | Slope>0.5(+20) | Persistence>=1(+20) | Transport>50(+10) | Exposure>150(+10)</span>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 13 — Ward Comparative Ranking
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 13 — Ward Comparative Ranking</div>', unsafe_allow_html=True)

from app import latest_state as _all_states
_active = {k: v for k, v in _all_states.items() if isinstance(v, dict) and v.get("aqi") is not None and v.get("status") != "DATA_INVALID"}
_n_stations = len(_active)

if _n_stations >= 1:
    # Ranking categories
    def _rank_by(key, label, transform=None):
        ranked = sorted(_active.items(), key=lambda x: (transform or (lambda v: v.get(key, 0)))(x[1]), reverse=True)[:3]
        rows_html = ""
        for i, (stn, vals) in enumerate(ranked):
            val = (transform or (lambda v: v.get(key, 0)))(vals)
            hl = "font-weight:700;color:#e2e8f0" if stn == selected else "color:#94a3b8"
            rows_html += f'<div style="font-size:10px;{hl};line-height:1.8">#{i+1} {stn} — {val}</div>'
        return f"""
        <div class="card" style="padding:10px 14px">
            <div class="card-label">{label}</div>
            {rows_html}
        </div>"""

    r1, r2, r3, r4 = st.columns(4)
    with r1:
        st.markdown(_rank_by("aqi", "Highest AQI"), unsafe_allow_html=True)
    with r2:
        st.markdown(_rank_by("eri_score", "Highest ERI"), unsafe_allow_html=True)
    with r3:
        def _get_slope(v):
            fc = v.get("forecast")
            return fc.get("rate_per_min", 0) if fc else 0
        st.markdown(_rank_by(None, "Fastest Rising", transform=_get_slope), unsafe_allow_html=True)
    with r4:
        def _get_exp(v):
            fc = v.get("forecast")
            return fc.get("exposure_score_30min", 0) if fc else 0
        st.markdown(_rank_by(None, "Highest Exposure", transform=_get_exp), unsafe_allow_html=True)

    st.markdown(f"""
    <div style="text-align:center;padding:4px 0">
        <span style="color:#334155;font-size:9px">Cross-station intelligence | {_n_stations} active stations | Auto-updated on refresh | No new APIs</span>
    </div>""", unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="card" style="text-align:center;padding:20px">
        <div style="color:#475569;font-size:11px">Waiting for station data to populate ranking...</div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 14 — AI Risk Interpretation (Gemini — Structured)
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 14 — AI Risk Interpretation (Gemini)</div>', unsafe_allow_html=True)

llm = data.get("llm_analysis", {}) if data else {}
llm_summary = llm.get("summary", "Initializing...")
llm_model = llm.get("model", "N/A")
llm_cached = llm.get("cached", False)
risk_traj = llm.get("risk_trajectory", "unknown")
esc_like = llm.get("regulatory_escalation_likelihood", "unknown")
ph_risk = llm.get("public_health_risk", "unknown")
anom_flag = llm.get("anomaly_flag", False)

def _risk_color(val):
    colors = {"low": "#22c55e", "moderate": "#eab308", "high": "#ef4444", "severe": "#dc2626", "unknown": "#475569", "rising": "#ef4444", "stable": "#eab308", "falling": "#22c55e"}
    return colors.get(val, "#475569")

st.markdown(f"""
<div style="display:flex;gap:16px;margin-bottom:8px;flex-wrap:wrap">
    <span style="color:#475569;font-size:10px">Model: <span style="color:#94a3b8;font-weight:600">{llm_model}</span></span>
    <span style="color:#475569;font-size:10px">Temp: <span style="color:#94a3b8">0.1</span></span>
    <span style="color:#475569;font-size:10px">Cache: <span style="color:{'#22c55e' if llm_cached else '#eab308'};font-weight:600">{'HIT' if llm_cached else 'FRESH'}</span></span>
    <span style="color:#475569;font-size:10px">Mode: <span style="color:#94a3b8;font-weight:600">Structured JSON</span></span>
</div>""", unsafe_allow_html=True)

l1, l2, l3, l4 = st.columns(4)
with l1:
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:10px">
        <div class="card-label">Risk Trajectory</div>
        <div style="color:{_risk_color(risk_traj)};font-size:13px;font-weight:700">{risk_traj.upper()}</div>
    </div>""", unsafe_allow_html=True)
with l2:
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:10px">
        <div class="card-label">Escalation Likelihood</div>
        <div style="color:{_risk_color(esc_like)};font-size:13px;font-weight:700">{esc_like.upper()}</div>
    </div>""", unsafe_allow_html=True)
with l3:
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:10px">
        <div class="card-label">Public Health Risk</div>
        <div style="color:{_risk_color(ph_risk)};font-size:13px;font-weight:700">{ph_risk.upper()}</div>
    </div>""", unsafe_allow_html=True)
with l4:
    anom_col = "#ef4444" if anom_flag else "#22c55e"
    anom_txt = "DETECTED" if anom_flag else "NONE"
    st.markdown(f"""
    <div class="card" style="text-align:center;padding:10px">
        <div class="card-label">Anomaly</div>
        <div style="color:{anom_col};font-size:13px;font-weight:700">{anom_txt}</div>
    </div>""", unsafe_allow_html=True)

st.markdown(f"""
<div class="card" style="padding:14px 18px;margin-top:6px">
    <div style="color:#e2e8f0;font-size:11px;line-height:1.8;white-space:pre-wrap">{llm_summary}</div>
</div>""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center;padding:4px 0">
    <span style="color:#334155;font-size:9px">LLM explanation layer. Not used for escalation decisions. Structured JSON output. 10s cooldown per station.</span>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 15 — Public Health Impact Forecast (VPPE)
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 15 — Public Health Impact Forecast</div>', unsafe_allow_html=True)

vuln_risk = data.get("vulnerable_risk", {}) if data else {}
preempt = data.get("preemptive_advisory", []) if data else []

if forecast and vuln_risk:
    proj30 = forecast.get("projected_30min", 0)
    proj30_grap = forecast.get("predicted_grap_30min", "N/A")
    exp_score = forecast.get("exposure_score_30min", 0)
    exp_col = "#ef4444" if proj30 >= 300 else "#eab308" if proj30 >= 200 else "#22c55e"

    h1, h2, h3 = st.columns(3)
    with h1:
        st.markdown(f"""
        <div class="card" style="text-align:center;padding:14px">
            <div class="card-label">30-min Projected AQI</div>
            <div style="color:{exp_col};font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:700">{proj30}</div>
            <div class="card-sub">GRAP: {proj30_grap}</div>
        </div>""", unsafe_allow_html=True)
    with h2:
        st.markdown(f"""
        <div class="card" style="text-align:center;padding:14px">
            <div class="card-label">Exposure Score (30min)</div>
            <div style="color:{exp_col};font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:700">{exp_score}</div>
            <div class="card-sub">Deterministic: AQI × 0.6</div>
        </div>""", unsafe_allow_html=True)
    with h3:
        urgency = "CRITICAL" if proj30 >= 300 else "HIGH" if proj30 >= 200 else "MODERATE" if proj30 >= 100 else "LOW"
        urg_col = "#dc2626" if urgency == "CRITICAL" else "#ef4444" if urgency == "HIGH" else "#eab308" if urgency == "MODERATE" else "#22c55e"
        st.markdown(f"""
        <div class="card" style="text-align:center;padding:14px">
            <div class="card-label">Mitigation Urgency</div>
            <div style="color:{urg_col};font-size:18px;font-weight:700">{urgency}</div>
            <div class="card-sub">Based on 30-min projection</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div style="margin-top:10px;margin-bottom:4px;color:#64748b;font-size:10px;font-weight:600;letter-spacing:1px">VULNERABLE POPULATION RISK</div>', unsafe_allow_html=True)

    group_labels = {"general": "👤 General", "elderly": "🧓 Elderly (≥60)", "children": "👶 Children (<14)", "respiratory": "🫁 Respiratory"}
    vcols = st.columns(4)
    for i, (group, label) in enumerate(group_labels.items()):
        v = vuln_risk.get(group, {"score": 0, "level": "low", "multiplier": 1.0})
        lev = v["level"]
        lev_col = "#dc2626" if lev == "severe" else "#ef4444" if lev == "high" else "#eab308" if lev == "moderate" else "#22c55e"
        with vcols[i]:
            st.markdown(f"""
            <div class="card" style="text-align:center;padding:12px;border-left:3px solid {lev_col}">
                <div style="font-size:11px;color:#94a3b8;margin-bottom:4px">{label}</div>
                <div style="color:{lev_col};font-size:18px;font-weight:700">{v['score']}</div>
                <div style="color:{lev_col};font-size:10px;font-weight:600;text-transform:uppercase">{lev}</div>
                <div style="color:#334155;font-size:9px;margin-top:2px">× {v['multiplier']}</div>
            </div>""", unsafe_allow_html=True)

    if preempt:
        adv_items = "".join([f'<div style="color:#fbbf24;font-size:11px;line-height:1.8">▸ {a}</div>' for a in preempt])
        st.markdown(f"""
        <div style="background:rgba(239,68,68,0.04);border:2px solid #ef4444;border-radius:8px;padding:12px 18px;margin-top:10px">
            <div style="color:#ef4444;font-size:11px;font-weight:700;letter-spacing:1px;margin-bottom:6px">⚠ PRE-EMPTIVE PUBLIC HEALTH ADVISORY</div>
            {adv_items}
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center;padding:8px 0;margin-top:6px">
            <span style="color:#22c55e;font-size:10px;font-weight:600">✔ No pre-emptive advisory required at current trajectory</span>
        </div>""", unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center;padding:4px 0">
        <span style="color:#334155;font-size:9px">VPPE: Deterministic risk multipliers. No ML. Advisory-only — does not affect GRAP escalation logic.</span>
    </div>""", unsafe_allow_html=True)

    # Impact Radius
    from config import DEFAULT_IMPACT_RADIUS_KM, DEFAULT_EST_POPULATION
    ir1, ir2 = st.columns(2)
    with ir1:
        st.markdown(f"""
        <div class="card" style="text-align:center;padding:10px">
            <div class="card-label">Impact Radius</div>
            <div style="color:#3b82f6;font-size:16px;font-weight:700">{DEFAULT_IMPACT_RADIUS_KM} km</div>
        </div>""", unsafe_allow_html=True)
    with ir2:
        st.markdown(f"""
        <div class="card" style="text-align:center;padding:10px">
            <div class="card-label">Est. Population at Risk</div>
            <div style="color:#eab308;font-size:16px;font-weight:700">{DEFAULT_EST_POPULATION:,}</div>
        </div>""", unsafe_allow_html=True)
    st.markdown("""
    <div style="text-align:center;padding:2px 0">
        <span style="color:#334155;font-size:8px">Static placeholder — configurable via civic data integration</span>
    </div>""", unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="card" style="text-align:center;padding:20px">
        <div style="color:#475569;font-size:11px">Collecting data... VPPE activates after ≥3 sliding windows</div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# SECTION 16 — Policy Intelligence Console
# ══════════════════════════════════════════════════════════════════════
st.markdown('<div class="sec-h">Section 16 — Policy Intelligence Console</div>', unsafe_allow_html=True)

# PDF Report Download
if data:
    from report_generator import generate_escalation_report
    from app import carbon_state as _carbon_st
    if st.button("Download Escalation Report (PDF)", key="pdf_btn"):
        pdf_bytes = generate_escalation_report(selected, data, _carbon_st)
        st.download_button(
            label="Save Report",
            data=pdf_bytes,
            file_name=f"escalation_report_{selected.replace(' ', '_')[:30]}.pdf",
            mime="application/pdf",
            key="pdf_download",
        )

# Refresh file scan
_scan_policy_files()

# Index stats row
i1, i2, i3, i4 = st.columns(4)
with i1:
    idx_t = _rag_state.get("index_type", "Initializing")
    idx_c = "#22c55e" if "Pathway" in idx_t else "#eab308"
    st.markdown(f"""
    <div class="rag-card">
        <div class="card-label">Index Type</div>
        <div style="color:{idx_c};font-size:11px;font-weight:700">{idx_t}</div>
    </div>""", unsafe_allow_html=True)
with i2:
    st.markdown(f"""
    <div class="rag-card">
        <div class="card-label">Documents Indexed</div>
        <div style="color:#e2e8f0;font-family:'JetBrains Mono',monospace;font-size:20px;font-weight:700">{_rag_state.get('docs_indexed', 0)}</div>
    </div>""", unsafe_allow_html=True)
with i3:
    st.markdown(f"""
    <div class="rag-card">
        <div class="card-label">Embedding Model</div>
        <div style="color:#e2e8f0;font-size:11px;font-weight:600">{_rag_state.get('embed_model', 'N/A')}</div>
    </div>""", unsafe_allow_html=True)
with i4:
    lr = _rag_state.get("last_reindex", "—")
    ss = _rag_state.get("store_status", "starting")
    ss_c = "#22c55e" if ss == "active" else "#eab308" if ss == "starting" else "#ef4444"
    st.markdown(f"""
    <div class="rag-card">
        <div class="card-label">Live Index Status</div>
        <div style="color:{ss_c};font-size:12px;font-weight:700">{ss.upper()}</div>
        <div class="card-sub">Last refresh: {lr} UTC</div>
    </div>""", unsafe_allow_html=True)

# Indexed files table
st.markdown('<div style="margin-top:12px"></div>', unsafe_allow_html=True)
pf = _rag_state.get("policy_files", [])
if pf:
    table_html = '<div class="card" style="padding:14px 18px"><div class="card-label">Indexed Policy Documents</div>'
    table_html += '<table style="width:100%;border-collapse:collapse;margin-top:8px">'
    table_html += '<tr style="border-bottom:1px solid #1e293b">'
    table_html += '<th style="text-align:left;color:#64748b;font-size:10px;padding:6px 8px;font-weight:600">FILENAME</th>'
    table_html += '<th style="text-align:right;color:#64748b;font-size:10px;padding:6px 8px;font-weight:600">SIZE</th>'
    table_html += '<th style="text-align:right;color:#64748b;font-size:10px;padding:6px 8px;font-weight:600">MODIFIED</th>'
    table_html += '</tr>'
    for f in pf:
        table_html += f'<tr style="border-bottom:1px solid #0f172a">'
        table_html += f'<td style="color:#e2e8f0;font-size:11px;padding:6px 8px;font-family:JetBrains Mono,monospace">{f["name"]}</td>'
        table_html += f'<td style="color:#94a3b8;font-size:11px;padding:6px 8px;text-align:right">{f["size_kb"]} KB</td>'
        table_html += f'<td style="color:#94a3b8;font-size:11px;padding:6px 8px;text-align:right">{f["modified"]}</td>'
        table_html += '</tr>'
    table_html += '</table></div>'
    st.markdown(table_html, unsafe_allow_html=True)
else:
    st.markdown('<div class="card" style="text-align:center;padding:20px"><div style="color:#475569;font-size:11px">No policy documents found in policies/ folder.</div></div>', unsafe_allow_html=True)

# File upload
st.markdown('<div style="margin-top:12px"></div>', unsafe_allow_html=True)
uploaded = st.file_uploader("Upload Policy Document", type=["txt", "pdf", "docx"], key="policy_upload")
if uploaded:
    save_path = os.path.join(POLICY_DIR, uploaded.name)
    with open(save_path, "wb") as f:
        f.write(uploaded.getbuffer())
    _scan_policy_files()
    st.markdown(f"""
    <div style="background:rgba(34,197,94,0.06);border:1px solid #166534;border-radius:6px;padding:10px 14px;margin-top:8px">
        <span style="color:#22c55e;font-size:11px;font-weight:700">Document ingested and indexed in real-time.</span>
        <span style="color:#94a3b8;font-size:10px;margin-left:8px">{uploaded.name} saved to policies/</span>
    </div>""", unsafe_allow_html=True)

if _rag_state.get("error"):
    st.markdown(f"""
    <div class="feed-err" style="margin-top:8px">
        <span style="color:#ef4444;font-size:10px;font-weight:600">RAG ENGINE NOTE</span>
        <span style="color:#94a3b8;font-size:10px;margin-left:8px">{_rag_state['error']}</span>
    </div>""", unsafe_allow_html=True)


# Footer
st.markdown("""
<div style="text-align:center;padding:8px 0 16px 0">
    <span style="color:#1e293b;font-size:8px;letter-spacing:1.5px">
        AREE v2.1 | PATHWAY xLLM | WAQI-DIRECT | SATELLITE-VERIFIED | LIVE POLICY INDEX
    </span>
</div>""", unsafe_allow_html=True)

time.sleep(5)
st.rerun()