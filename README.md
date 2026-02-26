# AREE — Autonomous Regulatory Escalation Engine

Stateful regulatory escalation infrastructure for environmental governance, built on Pathway.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Built with Pathway](https://img.shields.io/badge/Built%20with-Pathway-green)](https://pathway.com/)
[![Deployed on GCP](https://img.shields.io/badge/Deployed_on-GCP-blue?logo=googlecloud)](https://cloud.google.com/run)

## Table of Contents
1. [System Architecture](#1-system-architecture)
2. [Data Pipeline & API Dependencies](#2-data-pipeline--api-dependencies)
3. [Escalation State Machine](#3-escalation-state-machine)
4. [Decision Trace Example](#4-decision-trace-example)
5. [Configuration & Security](#5-configuration--security)
6. [Deployment Architecture](#6-deployment-architecture)
7. [Performance & Scalability Considerations](#7-performance--scalability-considerations)
8. [Failure Modes & Error Handling](#8-failure-modes--error-handling)
9. [Future Extensibility](#9-future-extensibility)
10. [Local Development Setup](#10-local-development-setup)
11. [License](#11-license)

---

## 1. System Architecture

AREE processes continuous live air quality monitoring feeds to deterministically output regulatory stage transitions. 


**Component Flow:**
*   **Ingestion Node:** Polls external APIs for continuous station data.
*   **Stateful Stream Processor:** Maintains sliding windows using Pathway to smooth transient sensor spikes.
*   **Rule Evaluator:** Applies static threshold logic (e.g., GRAP constraints) to the smoothed signal.
*   **Attribution Module:** Correlates local bounds with satellite fire data to establish regional transport metrics.
*   **Advisory Engine:** Retrieves contextual regulatory guidelines from a vector store based on the active state.
*   **Artifact Generator:** Renders structured audit logs and PDF reports.

## 2. Data Pipeline & API Dependencies

The system treats external data sources as upstream event emitters and normalizes payloads before processing.

*   **WAQI (World Air Quality Index) API:** Primary telemetry source. Provides real-time AQI and component pollutant metrics at the station level.
*   **NASA FIRMS (VIIRS NRT) API:** Telemetry source for active fire counts and radiative power, utilized to calculate the regional transport score.
*   **Google Gemini API:** Utilized strictly for language generation within the advisory context. Does *not* evaluate escalation logic.

## 3. Escalation State Machine

Escalation is treated as a deterministic state machine rather than a probabilistic outcome. 

**State Transition Constraints:**
*   **Persistence Window:** 3-minute tumbling/sliding window with a 1-minute hop interval.
*   **Hysteresis Guard:** A state transition requires `N` consecutive evaluations above threshold `T` within the window to prevent oscillating enforcement actions.
*   **Station Isolation:** Logic runs per station bounding box; city-wide averaging is strictly avoided to preserve localized enforcement capability.

## 4. Decision Trace Example

To ensure auditability, every state transition generates a structured decision trace payload.

```json
{
  "timestamp": "2024-10-27T14:32:01Z",
  "station_id": "STN-IN-DL-04",
  "evaluation_window_minutes": 3,
  "telemetry": {
    "aqi_current": 412,
    "aqi_persistence_flag": true,
    "trend_slope": 15.4
  },
  "attribution": {
    "nasa_firms_transport_score": 78,
    "wind_vector_alignment": true
  },
  "state_transition": {
    "previous_state": "GRAP_STAGE_2",
    "new_state": "GRAP_STAGE_3",
    "trigger_condition": "AQI > 400 AND persistence_flag == true"
  },
  "generated_artifacts": [
    "escalation_report_STN-IN-DL-04_1703688190.pdf"
  ]
}
```

## 5. Configuration & Security

The system is configured via environment variables.

| Variable | Requirement | Description |
| :--- | :--- | :--- |
| `WAQI_TOKEN` | Required | API key for World Air Quality Index data ingestion. |
| `FIRMS_API_KEY` | Required | API key for NASA FIRMS satellite telemetry. |
| `GEMINI_API_KEY` | Required | API key for advisory generation. |
| `EVALUATION_WINDOW_MIN` | Optional | Duration of the persistence window. Default: `3`. |
| `GRAP_THRESHOLDS_JSON` | Optional | Path to local threshold overrides. |

**Security Considerations:**
*   Secrets must be injected via secure context (e.g., GCP Secret Manager) during deployment.
*   No keys are logged in output traces.
*   Advisory generation prompts are strictly scoped to prevent prompt injection from affecting regulatory outputs.

## 6. Deployment Architecture

The production target is Google Cloud Run, leveraging a containerized, stateless compute layer wrapping the stateful stream.

*   **Compute:** Google Cloud Run (Containerized Python environment).
*   **Concurrency:** Handled via Gunicorn/Uvicorn workers depending on the streaming implementation constraints.
*   **State Management:** Pathway manages in-memory state for active windows. 
*   **Artifact Storage:** Scalable object storage (e.g., GCS) for generated PDF reports.

## 7. Performance & Scalability Considerations

*   **Memory Footprint:** Pathway state is bounded by the sliding window duration. Stale events are discarded. Memory usage scales linearly with the number of tracked stations `O(S)`.
*   **Compute Latency:** Evaluation logic is `O(1)` per window hop. Total processing time per tick is bounded by downstream rendering (PDF generation) and external advisory API calls.
*   **Network Bottlenecks:** NASA FIRMS and WAQI API rate limits dictate the minimum polling frequency. Caching layers are required for redundant geofence queries.

## 8. Failure Modes & Error Handling

*   **Upstream API Timeout:** If WAQI or FIRMS is unreachable, the station state is marked `STALE`. The window will not forcefully escalate on stale data.
*   **Missing Telemetry Data:** Handled via forward-filling for `T < 5 minutes`. Exceeding 5 minutes forces a `SENSOR_FAULT` state.
*   **LLM API Failure (Gemini):** If the advisory generation fails, the system degrades gracefully by outputting the raw static policy text mapped to the current state, ensuring escalation is not blocked.

## 9. Future Extensibility

*   **Alternative Rulesets:** Decoupling GRAP-specific logic to support arbitrary JSON-defined state machines for EU or US EPA AQI frameworks.
*   **Spatial Interpolation:** Adding inverse distance weighting (IDW) to estimate AQI values between adjacent physical monitoring stations.
*   **Webhooks:** Outbound webhook support for triggering external SMS gateways or downstream municipal IoT systems based on the decision trace.

## 10. Local Development Setup

### System Requirements
*   Python 3.10+
*   Virtual Environment (recommended)

### Installation
```bash
git clone https://github.com/jeyamoorthi/urbanlive-ai.git
cd urbanlive-ai
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### Execution
Define `.env` securely, then boot the stream:
```bash
streamlit run streamlit_app.py
```

## 11. License
Distributed under the MIT License. See `LICENSE` for more information.
