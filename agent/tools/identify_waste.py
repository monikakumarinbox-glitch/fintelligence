"""
Fintelligence Agent — Tool 3: Identify Waste
=============================================
Cross-references Dynatrace signals with Gemini's
semantic classification to calculate exact savings
and generate ranked recommendations.

This is Step 3 of the 6-step agent flow.
"""

import json
from typing import Optional

# ─────────────────────────────────────────────
# GEMINI PRICING (per 1K tokens, as of 2026)
# ─────────────────────────────────────────────
PRICING = {
    "gemini-2.0-pro": {
        "input_per_1k":  0.00125,
        "output_per_1k": 0.005,
    },
    "gemini-2.0-flash": {
        "input_per_1k":  0.000075,
        "output_per_1k": 0.0003,
    },
    "gemini-3.0-pro-preview": {
        "input_per_1k":  0.00125,
        "output_per_1k": 0.005,
    }
}

# Context caching saves ~75% on cached input tokens
CACHE_SAVINGS_PCT = 0.75

# Risk levels for compliance approval
RISK_LEVELS = {
    "model_routing":    ("high",  True),   # (risk, requires_approval)
    "prompt_caching":   ("low",   False),
    "token_limit":      ("low",   False),
}


def calculate_model_routing_saving(endpoint: dict) -> Optional[dict]:
    """
    Calculates savings from routing from Pro → Flash
    for endpoints where simple tasks are detected.
    """
    model = endpoint.get("model", "")
    if "flash" in model.lower():
        return None  # Already using Flash

    monthly_requests = endpoint.get("monthly_requests", 0)
    avg_input = endpoint.get("avg_input_tokens", 0)
    avg_output = endpoint.get("avg_output_tokens", 0)

    pro_pricing = PRICING.get(model, PRICING["gemini-2.0-pro"])
    flash_pricing = PRICING["gemini-2.0-flash"]

    monthly_input_tokens = (avg_input * monthly_requests) / 1000
    monthly_output_tokens = (avg_output * monthly_requests) / 1000

    pro_monthly_cost = (
        monthly_input_tokens * pro_pricing["input_per_1k"] +
        monthly_output_tokens * pro_pricing["output_per_1k"]
    )
    flash_monthly_cost = (
        monthly_input_tokens * flash_pricing["input_per_1k"] +
        monthly_output_tokens * flash_pricing["output_per_1k"]
    )

    saving = pro_monthly_cost - flash_monthly_cost
    if saving <= 0:
        return None

    return {
        "type":                "model_routing",
        "title":               f"Route simple requests on {endpoint['name']} to Gemini Flash",
        "description":         (
            f"Sampled request patterns suggest this endpoint predominantly handles "
            f"simple tasks that Gemini Flash handles comparably at ~16x lower cost."
        ),
        "saving_per_month":    round(saving, 2),
        "saving_per_year":     round(saving * 12, 2),
        "current_cost":        round(pro_monthly_cost, 2),
        "projected_cost":      round(flash_monthly_cost, 2),
        "risk":                "high",
        "requires_approval":   True,
        "compliance_note":     (
            "Model changes to production AI require compliance sign-off. "
            "Review output quality on 10% traffic before full rollout."
        ),
        "latency_impact":      "-150ms (faster)",
        "quality_risk":        "Low — Flash handles simple classification tasks comparably",
        "action": {
            "type":         "update_model_config",
            "endpoint":     endpoint["name"],
            "current_model": model,
            "new_model":    "gemini-2.0-flash",
        }
    }


def calculate_caching_saving(endpoint: dict) -> Optional[dict]:
    """
    Calculates savings from enabling Vertex AI context caching
    for endpoints with large repeated system prompts.
    """
    avg_input = endpoint.get("avg_input_tokens", 0)
    monthly_requests = endpoint.get("monthly_requests", 0)
    model = endpoint.get("model", "gemini-2.0-pro")

    if avg_input < 1000:
        return None  # Not enough tokens to make caching worthwhile

    # Estimate cached portion (system prompt) vs dynamic portion
    estimated_system_prompt_tokens = avg_input * 0.75
    pricing = PRICING.get(model, PRICING["gemini-2.0-pro"])

    monthly_cached_tokens = (estimated_system_prompt_tokens * monthly_requests) / 1000
    saving = monthly_cached_tokens * pricing["input_per_1k"] * CACHE_SAVINGS_PCT

    if saving <= 0:
        return None

    return {
        "type":                "prompt_caching",
        "title":               f"Enable context caching on {endpoint['name']}",
        "description":         (
            f"This endpoint repeats a large system prompt (~{int(estimated_system_prompt_tokens)} tokens) "
            f"on every call. GCP context caching eliminates redundant token processing, "
            f"reducing costs by up to 75% on cached content."
        ),
        "saving_per_month":    round(saving, 2),
        "saving_per_year":     round(saving * 12, 2),
        "current_cost":        round(endpoint.get("monthly_cost_usd", 0), 2),
        "projected_cost":      round(endpoint.get("monthly_cost_usd", 0) - saving, 2),
        "risk":                "low",
        "requires_approval":   False,
        "compliance_note":     "Safe to apply automatically — no model or output changes.",
        "latency_impact":      "-200ms (faster — cached tokens skip processing)",
        "quality_risk":        "None — identical outputs, just faster and cheaper",
        "action": {
            "type":         "enable_context_cache",
            "endpoint":     endpoint["name"],
            "model":        model,
            "ttl_seconds":  3600,
        }
    }


def calculate_token_limit_saving(endpoint: dict) -> Optional[dict]:
    """
    Calculates savings from reducing max_output_tokens
    to match actual usage patterns.
    """
    max_tokens = endpoint.get("max_output_tokens", 2048)
    avg_output = endpoint.get("avg_output_tokens", 0)
    monthly_requests = endpoint.get("monthly_requests", 0)
    model = endpoint.get("model", "gemini-2.0-pro")

    utilization = avg_output / max_tokens if max_tokens > 0 else 1

    if utilization > 0.20:
        return None  # Utilization is acceptable

    # Recommended limit: 2x the average with buffer
    recommended_max = max(int(avg_output * 2.5), 64)

    if recommended_max >= max_tokens:
        return None

    pricing = PRICING.get(model, PRICING["gemini-2.0-pro"])
    tokens_saved_per_request = (max_tokens - recommended_max) / 1000
    saving = tokens_saved_per_request * monthly_requests * pricing["output_per_1k"]

    if saving <= 0:
        return None

    return {
        "type":                "token_limit",
        "title":               f"Reduce max_output_tokens on {endpoint['name']}",
        "description":         (
            f"max_output_tokens is configured at {max_tokens} but actual output "
            f"averages only {int(avg_output)} tokens ({utilization*100:.1f}% utilization). "
            f"Reducing to {recommended_max} eliminates wasted token allocation."
        ),
        "saving_per_month":    round(saving, 2),
        "saving_per_year":     round(saving * 12, 2),
        "current_cost":        round(endpoint.get("monthly_cost_usd", 0), 2),
        "projected_cost":      round(endpoint.get("monthly_cost_usd", 0) - saving, 2),
        "risk":                "low",
        "requires_approval":   False,
        "compliance_note":     "Safe to apply automatically — reduces ceiling, does not change model behavior.",
        "latency_impact":      "Neutral",
        "quality_risk":        f"None — actual usage is {int(avg_output)} tokens, well below new limit of {recommended_max}",
        "action": {
            "type":              "update_token_limit",
            "endpoint":          endpoint["name"],
            "current_max":       max_tokens,
            "recommended_max":   recommended_max,
        }
    }


def identify_waste(signals: dict, classifications: list) -> dict:
    """
    Step 3 — IDENTIFY WASTE
    Cross-references Dynatrace signals with Gemini classifications
    to generate ranked, dollar-denominated recommendations.

    Returns:
        {
            "auto_apply": [...],    # safe, no approval needed
            "needs_approval": [...], # risky, compliance required
            "total_monthly_saving": float,
            "auto_apply_saving": float,
            "approval_saving": float,
        }
    """
    print("  Identifying waste and calculating savings...")

    # Map classifications by endpoint name
    class_map = {c["endpoint"]: c for c in classifications}

    auto_apply = []
    needs_approval = []

    for endpoint in signals.get("endpoints", []):
        name = endpoint["name"]
        classification = class_map.get(name, {})
        primary_waste = classification.get("primary_waste_pattern", "none")

        # Check each optimization type
        if (primary_waste == "model_mismatch" or
                classification.get("flash_eligible", False)):
            rec = calculate_model_routing_saving(endpoint)
            if rec:
                rec["confidence"] = classification.get("confidence", 0.8)
                needs_approval.append(rec)

        if (primary_waste == "cacheable_prompts" or
                classification.get("cache_eligible", False)):
            rec = calculate_caching_saving(endpoint)
            if rec:
                rec["confidence"] = classification.get("confidence", 0.8)
                auto_apply.append(rec)

        if (primary_waste == "token_limit_waste" or
                classification.get("token_reduction_eligible", False)):
            rec = calculate_token_limit_saving(endpoint)
            if rec:
                rec["confidence"] = classification.get("confidence", 0.9)
                auto_apply.append(rec)

    # Sort by saving (highest first)
    auto_apply.sort(key=lambda x: x["saving_per_month"], reverse=True)
    needs_approval.sort(key=lambda x: x["saving_per_month"], reverse=True)

    auto_saving = sum(r["saving_per_month"] for r in auto_apply)
    approval_saving = sum(r["saving_per_month"] for r in needs_approval)
    total_saving = auto_saving + approval_saving

    print(f"  ✅ Found ${total_saving:.2f}/month in waste")
    print(f"     Auto-apply: ${auto_saving:.2f}/month ({len(auto_apply)} actions)")
    print(f"     Needs approval: ${approval_saving:.2f}/month ({len(needs_approval)} actions)")

    return {
        "auto_apply":           auto_apply,
        "needs_approval":       needs_approval,
        "total_monthly_saving": round(total_saving, 2),
        "auto_apply_saving":    round(auto_saving, 2),
        "approval_saving":      round(approval_saving, 2),
        "total_annual_saving":  round(total_saving * 12, 2),
    }


if __name__ == "__main__":
    # Quick test
    from observe import MOCK_SIGNALS

    mock_classifications = [
        {
            "endpoint": "/api/fraud-detection",
            "primary_waste_pattern": "model_mismatch",
            "flash_eligible": True,
            "cache_eligible": False,
            "token_reduction_eligible": False,
            "confidence": 0.85
        },
        {
            "endpoint": "/api/loan-eligibility",
            "primary_waste_pattern": "cacheable_prompts",
            "flash_eligible": False,
            "cache_eligible": True,
            "token_reduction_eligible": False,
            "confidence": 0.90
        },
        {
            "endpoint": "/api/wealth-summary",
            "primary_waste_pattern": "token_limit_waste",
            "flash_eligible": False,
            "cache_eligible": False,
            "token_reduction_eligible": True,
            "confidence": 0.95
        }
    ]

    result = identify_waste(MOCK_SIGNALS, mock_classifications)
    print(json.dumps(result, indent=2))
