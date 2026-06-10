"""
Fintelligence Agent — Tool 2: Classify
========================================
Uses Gemini to semantically classify request patterns
per endpoint and identify waste opportunities.

This is Step 2 of the 6-step agent flow.
This is the KEY INNOVATION of Fintelligence —
Dynatrace shows numbers, Gemini understands what they mean.
"""

import os
import json

import vertexai
from vertexai.generative_models import GenerativeModel

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

def get_gemini_client():
    """Returns a configured Gemini model via Vertex AI."""
    if not GCP_PROJECT_ID:
        raise ValueError("GCP_PROJECT_ID environment variable not set")
    vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
    return GenerativeModel(GEMINI_MODEL)


# ─────────────────────────────────────────────
# SAMPLE REQUESTS PER ENDPOINT
# These simulate what real request logs would look like
# In production, these would come from BigQuery logs
# ─────────────────────────────────────────────
SAMPLE_REQUESTS = {
    "/api/fraud-detection": [
        "Transaction ID: TXN-8821. Amount: $142.50. Merchant: Amazon. Location: Chennai. Is this fraudulent? Yes or No.",
        "Transaction ID: TXN-9934. Amount: $890.00. Merchant: Apple Store. Location: Mumbai. Flag this transaction: Fraud or Legitimate?",
        "Check transaction TXN-1122: $45.00 at Swiggy, Bangalore. Fraud? Respond with single word.",
        "TXN-5543: $2,400 wire transfer to account ending 8821. Suspicious? Yes/No only.",
        "Evaluate: TXN-7731, $18.99, Netflix subscription renewal. Fraudulent? One word answer.",
    ],
    "/api/loan-eligibility": [
        """You are a loan officer at a regulated financial institution. 
        You must follow RBI guidelines section 4.2.1, CIBIL scoring methodology v3, 
        and internal risk framework RF-2024. Always check debt-to-income ratio, 
        credit history length, and employment stability.
        Assess loan eligibility for: Age 32, Salary 85000/month, CIBIL 742, 
        existing EMI 12000/month. Loan amount: 500000.""",
        """You are a loan officer at a regulated financial institution. 
        You must follow RBI guidelines section 4.2.1, CIBIL scoring methodology v3, 
        and internal risk framework RF-2024. Always check debt-to-income ratio, 
        credit history length, and employment stability.
        Assess loan eligibility for: Age 28, Salary 45000/month, CIBIL 680, 
        existing EMI 8000/month. Loan amount: 200000.""",
        """You are a loan officer at a regulated financial institution. 
        You must follow RBI guidelines section 4.2.1, CIBIL scoring methodology v3, 
        and internal risk framework RF-2024. Always check debt-to-income ratio, 
        credit history length, and employment stability.
        Assess loan eligibility for: Age 45, Salary 150000/month, CIBIL 810, 
        existing EMI 35000/month. Loan amount: 2000000.""",
    ],
    "/api/wealth-summary": [
        "Summarize portfolio: HDFC Bank 500 shares, Reliance 200 shares, TCS 100 shares. Total value: ₹8,42,000.",
        "Portfolio update for client ID C-4421: Nifty50 index fund ₹2L, Gold ETF ₹50K, FD ₹1L.",
        "Generate wealth summary: Equity 60%, Debt 30%, Gold 10%. Monthly SIP: ₹25,000.",
    ]
}


def classify_request_patterns(endpoint: dict) -> dict:
    """
    Step 2 — CLASSIFY
    Analyzes sample requests for an endpoint using Gemini
    to understand task complexity and identify waste patterns.

    Returns classification results with waste type and confidence.
    """

    endpoint_name = endpoint["name"]
    signals = endpoint

    print(f"  Classifying request patterns for {endpoint_name}...")

    # Get sample requests for this endpoint
    samples = SAMPLE_REQUESTS.get(endpoint_name, [])
    if not samples:
        samples = ["Sample request not available for this endpoint"]

    # Build the classification prompt
    prompt = f"""
You are an AI cost optimization expert analyzing Gemini API usage for a financial services company.

Analyze the following data for endpoint: {endpoint_name}

RUNTIME SIGNALS FROM DYNATRACE:
- Current model: {signals['model']}
- Average input tokens: {signals['avg_input_tokens']}
- Average output tokens: {signals['avg_output_tokens']}  
- Max output tokens configured: {signals['max_output_tokens']}
- Average latency: {signals['avg_duration_ms']}ms
- Monthly cost: ${signals['monthly_cost_usd']}

SAMPLE REQUESTS (last 5):
{chr(10).join([f"{i+1}. {req[:200]}..." for i, req in enumerate(samples)])}

Based on this data, classify the following and respond in JSON only:

{{
    "task_complexity": "simple|complex",
    "simple_task_pct": <0-100>,
    "complex_task_pct": <0-100>,
    "cacheable_pct": <0-100>,
    "primary_waste_pattern": "model_mismatch|cacheable_prompts|token_limit_waste|none",
    "waste_explanation": "<one sentence explaining the waste>",
    "flash_eligible": true|false,
    "cache_eligible": true|false,
    "token_reduction_eligible": true|false,
    "confidence": <0.0-1.0>,
    "output_token_utilization_pct": <0-100>
}}

Rules:
- model_mismatch: tasks are simple enough for a cheaper model
- cacheable_prompts: same system prompt repeated across many calls
- token_limit_waste: actual output much lower than max configured
- Respond with JSON only, no explanation text
"""

    try:
        model = get_gemini_client()
        response = model.generate_content(prompt)

        # Parse JSON response
        raw = response.text.strip()
        # Remove markdown code blocks if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        classification = json.loads(raw)
        classification["endpoint"] = endpoint_name
        print(f"  ✅ Classified: {classification['primary_waste_pattern']} "
              f"(confidence: {classification['confidence']})")
        return classification

    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON parse error: {e} → using signal-based classification")
        return _fallback_classification(endpoint)

    except Exception as e:
        print(f"  ⚠️  Gemini classification failed: {e} → using signal-based classification")
        return _fallback_classification(endpoint)


def _fallback_classification(endpoint: dict) -> dict:
    """
    Fallback classification based purely on Dynatrace signals
    when Gemini is unavailable.
    """
    waste_signals = endpoint.get("waste_signals", {})
    avg_input = endpoint.get("avg_input_tokens", 0)
    avg_output = endpoint.get("avg_output_tokens", 0)
    max_tokens = endpoint.get("max_output_tokens", 2048)

    output_utilization = (avg_output / max_tokens * 100) if max_tokens > 0 else 100
    output_input_ratio = (avg_output / avg_input) if avg_input > 0 else 1

    if waste_signals.get("model_mismatch") or output_input_ratio < 0.02:
        pattern = "model_mismatch"
        explanation = "Output tokens are very low relative to input — task is simpler than current model requires"
    elif waste_signals.get("cacheable") or avg_input > 3000:
        pattern = "cacheable_prompts"
        explanation = "High input token count suggests a large repeated system prompt that could be cached"
    elif waste_signals.get("token_limit_waste") or output_utilization < 10:
        pattern = "token_limit_waste"
        explanation = f"Only {output_utilization:.1f}% of max_output_tokens is actually used"
    else:
        pattern = "none"
        explanation = "No significant waste pattern detected"

    return {
        "endpoint": endpoint["name"],
        "task_complexity": "simple" if pattern == "model_mismatch" else "complex",
        "simple_task_pct": 75 if pattern == "model_mismatch" else 30,
        "complex_task_pct": 25 if pattern == "model_mismatch" else 70,
        "cacheable_pct": 70 if pattern == "cacheable_prompts" else 10,
        "primary_waste_pattern": pattern,
        "waste_explanation": explanation,
        "flash_eligible": pattern == "model_mismatch",
        "cache_eligible": pattern == "cacheable_prompts",
        "token_reduction_eligible": pattern == "token_limit_waste",
        "confidence": 0.80,
        "output_token_utilization_pct": round(output_utilization, 1)
    }


if __name__ == "__main__":
    # Quick test with mock endpoint data
    test_endpoint = {
        "name": "/api/fraud-detection",
        "model": "gemini-2.0-pro",
        "avg_input_tokens": 1211.70,
        "avg_output_tokens": 13.28,
        "max_output_tokens": 50,
        "avg_duration_ms": 675.13,
        "monthly_cost_usd": 1240,
        "waste_signals": {"model_mismatch": True}
    }
    result = classify_request_patterns(test_endpoint)
    print(json.dumps(result, indent=2))
