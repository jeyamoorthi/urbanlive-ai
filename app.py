# Autonomous Regulatory Escalation Engine
# Pathway streaming + Observer pattern for cross-window state tracking

import os
import time
import threading
import numpy as np
from datetime import datetime, timedelta, timezone
from collections import deque

import pathway as pw
from dotenv import load_dotenv
from codecarbon import EmissionsTracker

from config import (
    STATIONS, CITY_NAMES, AQI_POLL_INTERVAL, FIRE_POLL_INTERVAL,
    PERSISTENCE_THRESHOLD, HIGH_AQI_THRESHOLD,
    WINDOW_DURATION_MINUTES, WINDOW_HOP_MINUTES,
    HYSTERESIS_CONFIRMATIONS, CPCB_BANDS, GRAP_STAGES,
    VULNERABILITY_MULTIPLIERS,
)
from ingestion.aqi_stream import fetch_aqi, _debug_data
from ingestion.fire_stream import fetch_fire_count
from ingestion.firms_stream import get_firms_data, compute_transport_score
from rag.advisory_engine import generate_grounded_advisory, _rag_state
from rag.llm_engine import generate_llm_analysis

load_dotenv()

# shared state dicts (read by streamlit)
latest_state = {}
carbon_state = {"total_gco2": 0.0, "decision_count": 0, "per_decision_gco2": 0.0}
escalation_log = deque(maxlen=50)

# rolling buffer for trend prediction
aqi_history = {}


def compute_short_term_forecast(history):
    """5-min and 30-min AQI projection via linear regression."""
    if len(history) < 3:
        return None

    times = np.arange(len(history))
    values = np.array([h["aqi"] for h in history])

    slope, intercept = np.polyfit(times, values, 1)
    projected_5min = max(0, min(500, int(slope * (len(history) + 5) + intercept)))
    projected_30min = max(0, min(500, int(slope * (len(history) + 30) + intercept)))
    current_aqi = values[-1]

    if slope > 2:
        direction = "rising"
    elif slope < -2:
        direction = "falling"
    else:
        direction = "stable"

    # how long until we hit the threshold
    escalation_eta = None
    if slope > 0 and current_aqi < HIGH_AQI_THRESHOLD:
        windows_to_threshold = (HIGH_AQI_THRESHOLD - current_aqi) / slope
        escalation_eta = round(windows_to_threshold * (AQI_POLL_INTERVAL / 60), 1)

    # z-score anomaly check
    mean_aqi = np.mean(values)
    std_aqi = np.std(values)
    anomaly = bool(std_aqi > 0 and abs(current_aqi - mean_aqi) > 2 * std_aqi)

    def _grap_for_aqi(a):
        for lo, hi, stage, _ in GRAP_STAGES:
            if lo <= a <= hi:
                return stage
        return "Stage IV (Severe+)" if a > 500 else "None"

    return {
        "slope": round(float(slope), 2),
        "direction": direction,
        "projected_5min": projected_5min,
        "projected_30min": projected_30min,
        "predicted_grap": _grap_for_aqi(projected_5min),
        "predicted_grap_30min": _grap_for_aqi(projected_30min),
        "exposure_score_30min": int(projected_30min * 0.6),
        "escalation_eta": escalation_eta,
        "anomaly": anomaly,
        "rate_per_min": round(float(slope) * (60 / AQI_POLL_INTERVAL), 2),
        "data_points": len(history),
    }


# consecutive window tracker (observer-side)
_consecutive_high = {}
_hysteresis_tracker = {}

# carbon tracking
tracker = EmissionsTracker(project_name="UrbanLive-AI", log_level="error", save_to_file=False)
tracker.start()
_last_carbon_flush = time.time()
_CARBON_FLUSH_INTERVAL = 30


def cpcb_band(aqi):
    if aqi is None:
        return "Unknown"
    for lo, hi, label in CPCB_BANDS:
        if lo <= aqi <= hi:
            return label
    return "Severe"


def get_grap_stage(aqi):
    if aqi is None:
        return "Unknown", "No data"
    for lo, hi, stage, desc in GRAP_STAGES:
        if lo <= aqi <= hi:
            return stage, desc
    return "Stage IV (Severe+)", "Emergency actions under GRAP Stage IV"


def check_hysteresis(city, new_stage):
    rec = _hysteresis_tracker.get(city, {"stage": "None", "pending": None, "count": 0})

    if new_stage == rec["stage"]:
        rec["pending"] = None
        rec["count"] = 0
        _hysteresis_tracker[city] = rec
        return False, rec["stage"]

    if new_stage == rec.get("pending"):
        rec["count"] += 1
        if rec["count"] >= HYSTERESIS_CONFIRMATIONS:
            rec["stage"] = new_stage
            rec["pending"] = None
            rec["count"] = 0
            _hysteresis_tracker[city] = rec
            return True, new_stage
        _hysteresis_tracker[city] = rec
        return False, rec["stage"]
    else:
        rec["pending"] = new_stage
        rec["count"] = 1
        _hysteresis_tracker[city] = rec
        return False, rec["stage"]


# --- Pathway schemas ---

class AQISchema(pw.Schema):
    timestamp: pw.DateTimeUtc
    aqi: int
    city: str

class FireSchema(pw.Schema):
    timestamp: pw.DateTimeUtc
    fire_count: int


# --- Connectors (pan-india) ---

class AQIConnector(pw.io.python.ConnectorSubject):
    def run(self):
        from station_loader import get_all_stations
        stations = get_all_stations(STATIONS, limit=30)
        while True:
            for name, info in stations.items():
                record = fetch_aqi(name, info["feed_id"])
                if record:
                    if record["timestamp"].tzinfo is None:
                        record["timestamp"] = record["timestamp"].replace(tzinfo=timezone.utc)
                    self.next(**record)
            time.sleep(AQI_POLL_INTERVAL)

class FireConnector(pw.io.python.ConnectorSubject):
    def run(self):
        while True:
            record = fetch_fire_count()
            if record:
                if record["timestamp"].tzinfo is None:
                    record["timestamp"] = record["timestamp"].replace(tzinfo=timezone.utc)
                self.next(**record)
            time.sleep(FIRE_POLL_INTERVAL)


# --- Pathway DAG ---

aqi_table = pw.io.python.read(AQIConnector(), schema=AQISchema)
fire_table = pw.io.python.read(FireConnector(), schema=FireSchema)

# sliding window: max AQI per city per window
windowed = (
    aqi_table
    .windowby(
        pw.this.timestamp,
        window=pw.temporal.sliding(
            duration=pw.Duration(minutes=WINDOW_DURATION_MINUTES),
            hop=pw.Duration(minutes=WINDOW_HOP_MINUTES),
        ),
        instance=pw.this.city,
    )
    .reduce(
        timestamp=pw.reducers.max(pw.this.timestamp),
        city=pw.reducers.any(pw.this.city),
        aqi=pw.reducers.max(pw.this.aqi),
    )
)


# --- Observer: cross-window state tracking ---

class Observer(pw.io.python.ConnectorObserver):
    def on_change(self, key, row, time, is_addition):
        global _last_carbon_flush

        if not is_addition:
            return

        city = row["city"]
        aqi = row["aqi"]
        window_ts = row["timestamp"]

        # validate payload
        try:
            aqi = int(aqi) if aqi is not None else -1
        except (ValueError, TypeError):
            aqi = -1
        if aqi < 0 or window_ts is None:
            latest_state[city] = {
                "status": "DATA_INVALID",
                "reason": "Bad payload",
                "aqi": 0, "timestamp": window_ts,
            }
            return

        # consecutive window tracking
        if aqi >= HIGH_AQI_THRESHOLD:
            _consecutive_high[city] = _consecutive_high.get(city, 0) + 1
        else:
            _consecutive_high[city] = 0

        consec = _consecutive_high[city]
        remaining = max(0, PERSISTENCE_THRESHOLD - consec)

        # projected trigger time
        if consec >= PERSISTENCE_THRESHOLD:
            projected = "ACTIVE NOW"
        else:
            mins = remaining * WINDOW_HOP_MINUTES
            if isinstance(window_ts, datetime):
                projected = (window_ts + timedelta(minutes=mins)).strftime("%H:%M:%S")
            else:
                projected = "Calculating..."

        band = cpcb_band(aqi)
        grap_stage, grap_desc = get_grap_stage(aqi)

        previous_stage = _hysteresis_tracker.get(city, {}).get("stage", "None")
        transitioned, effective_stage = check_hysteresis(city, grap_stage)

        if transitioned:
            escalation_log.appendleft({
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "city": city, "aqi": aqi,
                "from_stage": previous_stage, "to_stage": effective_stage,
                "trigger": f"AQI {aqi} sustained for {consec} consecutive windows",
                "band": band,
            })

        # satellite transport scoring
        debug = _debug_data.get(city, {})
        wind_speed = debug.get("wind_speed")
        wind_dir = debug.get("wind_direction")
        transport_score, aligned_fires, transport_label = compute_transport_score(
            city, wind_dir, wind_speed
        )
        firms = get_firms_data(city)

        # advisory
        advisory_result = generate_grounded_advisory(
            aqi=aqi, level=effective_stage, grap_description=grap_desc,
            band=band, fire_count=firms["fire_count"],
            high_count=consec, remaining_windows=remaining,
            projected_time=projected,
            transport_score=transport_score, transport_label=transport_label,
            wind_speed=wind_speed, wind_dir=wind_dir,
        )

        # trend prediction
        if city not in aqi_history:
            aqi_history[city] = deque(maxlen=10)
        aqi_history[city].append({"timestamp": window_ts, "aqi": aqi})
        forecast = compute_short_term_forecast(aqi_history[city])

        # vulnerable population risk
        vulnerable_risk = {}
        preemptive_advisory = []
        vulnerability_max = "low"
        if forecast:
            proj_30 = forecast["projected_30min"]
            for group, multiplier in VULNERABILITY_MULTIPLIERS.items():
                risk_score = int(proj_30 * multiplier)
                if risk_score >= 300:
                    level = "severe"
                elif risk_score >= 200:
                    level = "high"
                elif risk_score >= 100:
                    level = "moderate"
                else:
                    level = "low"
                vulnerable_risk[group] = {
                    "score": risk_score, "level": level, "multiplier": multiplier,
                }

            risk_levels = [v["level"] for v in vulnerable_risk.values()]
            if "severe" in risk_levels:
                vulnerability_max = "severe"
            elif "high" in risk_levels:
                vulnerability_max = "high"
            elif "moderate" in risk_levels:
                vulnerability_max = "moderate"

            # pre-emptive advisory triggers
            if forecast["direction"] == "rising" and proj_30 >= 200 and transport_score >= 40:
                preemptive_advisory = [
                    "Advise suspension of outdoor school activities",
                    "Increase dust suppression enforcement",
                    "Public health SMS advisory recommended",
                    "Traffic enforcement readiness advised",
                ]
            elif forecast["direction"] == "rising" and proj_30 >= 200:
                preemptive_advisory = [
                    "Outdoor activity caution advisory recommended",
                    "Construction dust suppression measures advised",
                ]
            elif forecast["direction"] == "rising" and proj_30 >= 150:
                preemptive_advisory = [
                    "Sensitive groups should reduce outdoor exposure",
                ]

        # gemini analysis (explanation only)
        llm_result = {"summary": "Initializing...", "model": "gemini-2.5-flash-lite",
                      "cached": False, "timestamp": None, "risk_trajectory": "unknown",
                      "regulatory_escalation_likelihood": "unknown",
                      "public_health_risk": "unknown", "anomaly_flag": False}
        try:
            trend_dir = forecast["direction"] if forecast else "insufficient_data"
            proj_5 = forecast["projected_5min"] if forecast else aqi
            proj_30 = forecast["projected_30min"] if forecast else aqi
            anom = forecast["anomaly"] if forecast else False
            llm_result = generate_llm_analysis(
                station=city, aqi=aqi, trend_direction=trend_dir,
                projected_5min=proj_5, transport_score=transport_score,
                policy_context=advisory_result.get("advisory", "")[:500],
                band=band, grap_stage=effective_stage, anomaly=anom,
                projected_30min=proj_30, vulnerability_max=vulnerability_max,
            )
        except Exception as e:
            llm_result["summary"] = f"LLM unavailable: {str(e)[:80]}"

        # confidence score (deterministic, min 50%)
        confidence_score = 50
        if debug.get("api_time"):
            confidence_score += 20
        if debug.get("pollutants_available", 0) >= 2:
            confidence_score += 10
        if firms["fire_count"] > 0 and wind_speed is not None:
            confidence_score += 20
        confidence_score = min(max(confidence_score, 50), 100)

        # build state
        latest_state[city] = {
            "aqi": aqi,
            "timestamp": window_ts,
            "cpcb_band": band,
            "grap_stage": effective_stage,
            "grap_description": grap_desc,
            "consecutive_windows": consec,
            "remaining_windows": remaining,
            "projected_trigger_time": projected,
            "advisory_text": advisory_result["advisory"],
            "rag_policy_file": advisory_result["policy_file"],
            "rag_similarity_score": advisory_result["similarity_score"],
            "rag_last_updated": advisory_result["policy_last_updated"],
            "rag_index_type": advisory_result.get("index_type", "Embedded Vector Index"),
            "rag_docs_indexed": advisory_result.get("docs_indexed", 0),
            "rag_embed_model": advisory_result.get("embed_model", "all-MiniLM-L6-v2"),
            "governance_rule": advisory_result.get("governance_rule", ""),
            "raw_pm25": debug.get("raw_pm25"),
            "raw_pm10": debug.get("raw_pm10"),
            "raw_no2": debug.get("raw_no2"),
            "raw_so2": debug.get("raw_so2"),
            "raw_o3": debug.get("raw_o3"),
            "raw_co": debug.get("raw_co"),
            "dominant_pollutant": debug.get("dominant_pollutant", "pm25"),
            "pollutants_available": debug.get("pollutants_available", 0),
            "wind_speed": wind_speed,
            "wind_direction": wind_dir,
            "waqi_aqi": debug.get("waqi_aqi"),
            "waqi_timestamp": debug.get("waqi_timestamp", ""),
            "station_name_api": debug.get("station_name_api", ""),
            "stale_seconds": debug.get("stale_seconds"),
            "ingestion_status": debug.get("status", "ok"),
            "ingestion_error": debug.get("error"),
            "feed_id": debug.get("feed_id", ""),
            "api_time": debug.get("api_time", ""),
            "fire_count": firms["fire_count"],
            "high_conf_fires": firms["high_confidence"],
            "fire_bbox": firms["bbox"],
            "firms_sync": firms["last_sync"],
            "firms_status": firms["status"],
            "firms_error": firms.get("error"),
            "firms_dataset": firms["dataset"],
            "transport_score": transport_score,
            "aligned_fires": aligned_fires,
            "transport_label": transport_label,
            "confidence_score": confidence_score,
            "forecast": forecast,
            "vulnerable_risk": vulnerable_risk,
            "vulnerability_max": vulnerability_max,
            "preemptive_advisory": preemptive_advisory,
            "llm_analysis": llm_result,
        }

        # ERI (advisory only, does not affect GRAP)
        eri_score = 0
        eri_factors = []
        if aqi >= 200:
            eri_score += 40
            eri_factors.append(f"AQI >= 200 (+40)")
        if forecast and forecast.get("rate_per_min", 0) > 0.5:
            eri_score += 20
            eri_factors.append(f"Slope > 0.5 AQI/min (+20)")
        if consec >= 1:
            eri_score += 20
            eri_factors.append(f"Persistence >= 1 window (+20)")
        if transport_score > 50:
            eri_score += 10
            eri_factors.append(f"Transport score > 50 (+10)")
        exp_score = forecast.get("exposure_score_30min", 0) if forecast else 0
        if exp_score > 150:
            eri_score += 10
            eri_factors.append(f"Exposure score > 150 (+10)")
        eri_score = min(100, max(0, eri_score))

        if eri_score >= 76:
            eri_category = "HIGH READINESS"
        elif eri_score >= 51:
            eri_category = "PRE-ESCALATION"
        elif eri_score >= 26:
            eri_category = "MONITOR"
        else:
            eri_category = "LOW READINESS"

        latest_state[city]["eri_score"] = eri_score
        latest_state[city]["eri_category"] = eri_category
        latest_state[city]["eri_factors"] = eri_factors

        # carbon flush (periodic)
        carbon_state["decision_count"] += 1
        try:
            now = time.time()
            if now - _last_carbon_flush >= _CARBON_FLUSH_INTERVAL:
                kg = tracker.flush()
                _last_carbon_flush = now
                if kg:
                    carbon_state["total_gco2"] = round(kg * 1000, 4)
                    if carbon_state["decision_count"] > 0:
                        carbon_state["per_decision_gco2"] = round(
                            carbon_state["total_gco2"] / carbon_state["decision_count"], 6
                        )
        except Exception:
            pass


pw.io.python.write(windowed, Observer())


def _run():
    pw.run(monitoring_level=pw.MonitoringLevel.NONE)

threading.Thread(target=_run, daemon=True).start()