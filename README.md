# 🏛 AREE v2.2 — Autonomous Regulatory Escalation Engine  
### Real-Time Environmental Governance Infrastructure  
Pathway Streaming | WAQI Direct | Satellite Verified | Policy Grounded | Deterministic Enforcement  

---

## 🚨 What This Is

AREE is a **deterministic, policy-grounded environmental enforcement engine**.

It continuously monitors live AQI across India, applies official CPCB/GRAP escalation rules with persistence logic, verifies regional pollution transport using NASA satellite data, and generates municipal-grade escalation reports — in real time.

This is not a visualization dashboard.  
This is regulatory infrastructure.

---

## 🎯 Problem Being Solved

Air quality enforcement systems today are:

- Reactive rather than predictive  
- City-averaged instead of station-specific  
- Not traceable to legal thresholds  
- Not satellite-verified  
- Not audit-ready  

AREE transforms environmental monitoring into:

✔ Deterministic escalation logic  
✔ Legally traceable trigger rules  
✔ Satellite-attributed causality  
✔ Predictive early warning  
✔ Governance-ready reporting  
✔ National monitoring capability  

---

## 🧠 Core Innovation

AREE combines five layers into one enforcement pipeline:

```
Live WAQI Feed (Station-Level)
        ↓
Sliding Window Persistence Engine
        ↓
Predictive Intelligence (Short-Term Forecast)
        ↓
Satellite Transport Verification (NASA FIRMS)
        ↓
Policy-Grounded Advisory (Pathway RAG)
        ↓
Municipal-Ready Escalation Report
```

All enforcement decisions are deterministic and traceable.

---

## ⚖ Deterministic Escalation Logic

Official GRAP trigger implementation:

- AQI ≥ 300 threshold  
- 3 consecutive sliding windows  
- 3-min duration, 1-min hop  
- 2 hysteresis confirmations  
- Direct WAQI AQI (no recomputation)  

Every decision includes:

- Trigger rule display  
- Decision trace  
- Persistence state  
- Remaining windows  
- Projected trigger time  

No generative AI influences escalation logic.

---

## 🇮🇳 Pan-India Monitoring Mode

AREE operates in two modes:

### 🔹 Single Station Mode
Full 16-section regulatory dashboard:
- AQI ingestion
- Persistence engine
- Predictive model
- Satellite attribution
- ERI scoring
- Policy grounding
- Vulnerable population risk
- PDF export

### 🔹 National Overview Mode
- Dynamic station loading (WAQI Search API)
- Up to 30 live Indian stations
- Real-time India map
- Top 5 Highest AQI ranking
- Top 5 Highest ERI ranking
- Focus station drill-down

This transforms AREE into a **National Environmental Command Console**.

---

## 🔮 Predictive Intelligence

Short-term early warning system:

- Linear regression (numpy.polyfit)
- 5-minute AQI projection
- 30-minute AQI projection
- Trend direction detection
- Escalation ETA
- Z-score anomaly detection

Fully deterministic.
No external ML APIs.

---

## 🛰 Satellite Transport Verification

Integrated NASA FIRMS (VIIRS_SNPP_NRT):

- Bounding box per station
- Confidence filtering
- Wind alignment physics
- Transport score (0–100)
- Attribution classification:
  - regional_transport
  - possible_transport
  - local_emission

Pollution source attribution becomes measurable.

---

## 📜 Policy Grounding (Pathway Streaming RAG)

- Pathway `DocumentStore` (Live Hybrid Index)
- Streaming policy re-indexing
- SentenceTransformer embeddings (384-dim)
- Similarity score transparency
- Index metadata display
- Live policy upload support

Used to ground advisory context.

Enforcement remains deterministic.

---

## 📊 Escalation Readiness Index (ERI)

Advisory readiness scoring:

```
AQI ≥ 200         → +40
Slope > 0.5       → +20
Persistence ≥ 1   → +20
Transport > 50    → +10
Exposure > 150    → +10
```

ERI does NOT affect GRAP trigger logic.  
It supports pre-emptive governance planning.

---

## 👥 Vulnerable Population Protection Engine (VPPE)

Deterministic multipliers:

- General ×1.0  
- Elderly ×1.4  
- Children ×1.6  
- Respiratory ×1.8  

Risk categories:

- LOW  
- MODERATE  
- HIGH  
- SEVERE  

Enables public health advisory planning.

---

## 📄 Municipal-Ready Governance Report

4-page structured PDF:

1. Executive Situation Brief  
2. Technical Escalation Detail  
3. Policy Grounding & Legal Basis  
4. System Transparency & Carbon Accounting  

Generated via `reportlab.platypus`.

No LLM-generated narrative included.

Audit-ready.

---

## 🤖 LLM Usage — Controlled & Constrained

Gemini 2.5 Flash Lite used strictly for:

- Structured JSON risk interpretation  
- No number modification  
- No policy inference  
- No enforcement authority  
- Rate limited + cached  

LLM is explanatory only.

This avoids hallucinated regulatory decisions.

---

## 🔍 Transparency & Auditability

Every station shows:

- WAQI Feed ID  
- API timestamp  
- Data freshness  
- Dominant pollutant  
- Pollutants available count  
- Escalation rule  
- Decision trace  
- RAG metadata  
- Embedding model  
- Index sync time  
- Carbon accounting  

The system is fully inspectable.

---

## 🏗 Architecture Overview

```
app.py                  → Orchestration
streamlit_app.py        → UI Layer
aqi_stream.py           → WAQI ingestion
firms_stream.py         → Satellite polling + transport score
station_loader.py       → Pan-India dynamic loader
advisory_engine.py      → Deterministic escalation engine
llm_engine.py           → Structured Gemini layer
report_generator.py     → Governance PDF generator
config.py               → Central configuration
policies/               → Live-indexed policy documents
```

---

## 🚀 How to Run

### 1️⃣ Install

```bash
pip install -r requirements.txt
```

### 2️⃣ Configure Environment

Create `.env`:

```env
WAQI_TOKEN=your_token
FIRMS_API_KEY=your_key
GEMINI_API_KEY=your_key
```

### 3️⃣ Start System

```bash
streamlit run streamlit_app.py
```

Runs at:

```
http://localhost:8501
```

---

## � Design Principles

1. Determinism over hallucination  
2. Policy grounding over generic advice  
3. Transparency over black-box prediction  
4. National scalability  
5. Governance-grade outputs  

---

## ⚠ Limitations

- Dependent on WAQI station availability  
- Satellite detection limited by FIRMS resolution  
- Linear regression (short-term forecast only)  
- Static population placeholder  
- GRAP logic Delhi-based (extendable to other state protocols)  

---

## 🏆 Positioning

AREE is positioned as:

> A Deterministic Environmental Enforcement Infrastructure  
> Not a dashboard  
> Not a chatbot  
> Not a generative demo  

Designed for:

- Municipal Corporations  
- State Pollution Control Boards  
- Environmental Command Centers  
- Regulatory Agencies  

---

## 🌱 Why This Matters

Environmental governance requires:

- Traceability  
- Threshold discipline  
- Early warning  
- Attribution  
- Legal defensibility  

AREE demonstrates that real-time environmental regulation can be:

- Predictive  
- Satellite-verified  
- Policy-grounded  
- Deterministic  
- Nationally scalable  

---

**AREE v2.2**  
Pathway × Real-Time Governance × Deterministic Intelligence