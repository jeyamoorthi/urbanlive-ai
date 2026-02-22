# Gemini structured risk interpretation
# Returns JSON only. Used for explanation, not enforcement.

import json
import time
import google.generativeai as genai
from config import GEMINI_API_KEY

_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        _model = genai.GenerativeModel("gemini-2.5-flash-lite")
        print("[LLM] gemini ready")
    except Exception as e:
        print(f"[LLM] init failed: {e}")

# rate limiting
_last_call = {}
_cache = {}
COOLDOWN = 10
MAX_TOKENS = 300
TEMP = 0.1

_FALLBACK = {
    "risk_trajectory": "unknown",
    "regulatory_escalation_likelihood": "unknown",
    "public_health_risk": "unknown",
    "anomaly_flag": False,
    "summary": "LLM analysis temporarily unavailable.",
}


def generate_llm_analysis(
    station, aqi, trend_direction, projected_5min,
    transport_score, policy_context,
    band="", grap_stage="", anomaly=False,
    projected_30min=None, vulnerability_max="low",
):
    if not _model:
        return {**_FALLBACK, "summary": "Gemini API key not configured.",
                "model": "N/A", "cached": False, "timestamp": None}

    now = time.time()
    if station in _last_call and now - _last_call[station] < COOLDOWN:
        cached = _cache.get(station)
        if cached:
            cached["cached"] = True
            return cached

    proj30_text = f"Projected 30-min AQI: {projected_30min}" if projected_30min else ""
    anomaly_text = "ANOMALY DETECTED: Current AQI deviates >2σ from recent trend." if anomaly else ""

    prompt = f"""You are a deterministic regulatory AI analyst.
Return ONLY valid JSON. Do not paraphrase numeric values. Use exact numbers provided.
Do not round or approximate. Do not infer beyond provided context.
Do not modify AQI values. Do not add numbers not present in the input.
Do not hallucinate predictions. Do not fabricate policy references.
The public_health_risk level MUST equal the highest vulnerable population category: {vulnerability_max}.

Station: {station}
Current AQI: {aqi} (exact)
CPCB Band: {band}
GRAP Stage: {grap_stage}
Trend: {trend_direction}
Projected 5-min AQI: {projected_5min} (exact)
{proj30_text}
Transport Score: {transport_score}/100
Highest Vulnerability Level: {vulnerability_max}
{anomaly_text}

Policy Context (verbatim):
{policy_context[:400]}

Return this exact JSON schema:
{{
  "risk_trajectory": "rising|stable|falling",
  "regulatory_escalation_likelihood": "low|moderate|high",
  "public_health_risk": "{vulnerability_max}",
  "anomaly_flag": {str(anomaly).lower()},
  "summary": "2-3 sentence explanation using exact numbers from input only"
}}"""

    try:
        response = _model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=TEMP,
                max_output_tokens=MAX_TOKENS,
            ),
        )
        raw = response.text.strip()

        # extract json from possible markdown blocks
        text = raw
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        parsed = json.loads(text)

        for key in ["risk_trajectory", "regulatory_escalation_likelihood", "public_health_risk", "summary"]:
            if key not in parsed:
                parsed[key] = _FALLBACK[key]

        parsed["anomaly_flag"] = anomaly
        parsed["model"] = "gemini-2.5-flash-lite"
        parsed["cached"] = False
        parsed["timestamp"] = now
        parsed["raw_response"] = raw[:500]

        _last_call[station] = now
        _cache[station] = parsed
        return parsed

    except json.JSONDecodeError:
        result = {**_FALLBACK,
                  "summary": raw[:300] if 'raw' in dir() else "JSON parse failed.",
                  "model": "gemini-2.5-flash-lite", "cached": False, "timestamp": now}
        _last_call[station] = now
        _cache[station] = result
        return result

    except Exception as e:
        cached = _cache.get(station)
        if cached:
            cached["cached"] = True
            return cached
        return {**_FALLBACK, "summary": f"LLM error: {str(e)[:100]}",
                "model": "gemini-2.5-flash-lite", "cached": False, "timestamp": None}
