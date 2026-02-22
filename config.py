# Central configuration

import os
from dotenv import load_dotenv

load_dotenv()

# API keys
WAQI_TOKEN = os.getenv("WAQI_TOKEN", "")
FIRMS_API_KEY = os.getenv("FIRMS_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# verified WAQI feed IDs
STATIONS = {
    "SIDCO Kurichi (Coimbatore) — @11847": {
        "feed_id": "@11847",
        "lat": 11.0000,
        "lon": 76.9700,
        "city": "Coimbatore",
    },
    "BTM (Bangalore) — @8190": {
        "feed_id": "@8190",
        "lat": 12.9166,
        "lon": 77.6101,
        "city": "Bangalore",
    },
    "Tirumala (Tirupati) — @9069": {
        "feed_id": "@9069",
        "lat": 13.6833,
        "lon": 79.3500,
        "city": "Tirupati",
    },
    "NSIT Dwarka (Delhi) — A568246": {
        "feed_id": "A568246",
        "lat": 28.6100,
        "lon": 77.0400,
        "city": "Delhi",
    },
    "Anand Vihar (Delhi) — @2553": {
        "feed_id": "@2553",
        "lat": 28.6468,
        "lon": 77.3162,
        "city": "Delhi",
    },
}

CITY_NAMES = list(STATIONS.keys())

# polling intervals (seconds)
AQI_POLL_INTERVAL = 30
FIRE_POLL_INTERVAL = 60

# persistence / escalation
PERSISTENCE_THRESHOLD = 3
HIGH_AQI_THRESHOLD = 300
WINDOW_DURATION_MINUTES = 3
WINDOW_HOP_MINUTES = 1
HYSTERESIS_CONFIRMATIONS = 2

# CPCB bands
CPCB_BANDS = [
    (0,   50,  "Good"),
    (51,  100, "Satisfactory"),
    (101, 200, "Moderate"),
    (201, 300, "Poor"),
    (301, 400, "Very Poor"),
    (401, 500, "Severe"),
]

# GRAP stages (official CAQM table)
GRAP_STAGES = [
    (0,   100, "None",                   "No GRAP action required"),
    (101, 200, "Stage I (Poor)",         "Actions under GRAP Stage I"),
    (201, 300, "Stage II (Very Poor)",   "Actions under GRAP Stage II"),
    (301, 400, "Stage III (Severe)",     "Actions under GRAP Stage III"),
    (401, 500, "Stage IV (Severe+)",     "Emergency actions under GRAP Stage IV"),
]

# NASA FIRMS
FIRMS_DATASET = "VIIRS_SNPP_NRT"
FIRMS_POLL_MINUTES = 5
FIRMS_BBOX_DELTA = 0.15
FIRMS_LOOKBACK_DAYS = 1
FIRMS_CONFIDENCE_FILTER = ["high", "nominal"]
WIND_ALIGNMENT_THRESHOLD = 45
WIND_SPEED_MIN = 2.0
FIRE_TRANSPORT_THRESHOLD = 3

# stale data
STALE_DATA_THRESHOLD_SECONDS = 1200  # 20 min

# policy directory
POLICY_DIR = os.path.join(os.path.dirname(__file__), "policies")

# VPPE multipliers
VULNERABILITY_MULTIPLIERS = {
    "general": 1.0,
    "elderly": 1.4,
    "children": 1.6,
    "respiratory": 1.8,
}

# impact estimation (static placeholders)
DEFAULT_IMPACT_RADIUS_KM = 5
DEFAULT_EST_POPULATION = 500000
