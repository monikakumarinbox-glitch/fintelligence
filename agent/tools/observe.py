"""
Fintelligence Agent — Tool 1: Observe
======================================
Pulls runtime signals from Dynatrace via MCP server.
Falls back to mock data if DEMO_MODE=true or connection fails.

This is Step 1 of the 6-step agent flow.
"""

import os
import json
import asyncio
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DT_ENDPOINT = os.environ.get("DT_ENDPOINT", "").rstrip("/")
DT_API_TOKEN = os.environ.get("DT_API_TOKEN", "")
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"
DT_PLATFORM_TOKEN = os.environ.get("DT_PLATFORM_TOKEN", "")

# ─────────────────────────────────────────────
# MOCK DATA
# ─────────────────────────────────────────────
MOCK_SIGNALS = {
    "service": "fintelligence-demo-app",
    "source": "dynatrace_mcp",
    "endpoints": [
        {
            "name": "/api/fraud-detection",
            "display": "Fraud Detection",
            "model": "gemini-2.0-pro",
            "max_output_tokens": 50,
            "span_count": 80,
            "avg_input_tokens": 1211.70,
            "avg_output_tokens": 13.28,
            "avg_duration_ms": 675.13,
            "monthly_requests": 72000,
            "monthly_cost_usd": 1240,
            "waste_signals": {
                "low_output_ratio": True,
                "model_mismatch": True
            }
        },
        {
            "name": "/api/loan-eligibility",
            "display": "Loan Eligibility",
            "model": "gemini-2.0-pro",
            "max_output_tokens": 500,
            "span_count": 35,
            "avg_input_tokens": 4918.23,
            "avg_output_tokens": 277.34,
            "avg_duration_ms": 2197.31,
            "monthly_requests": 31500,
            "monthly_cost_usd": 980,
            "waste_signals": {
                "high_input_tokens": True,
                "cacheable": True
            }
        },
        {
            "name": "/api/wealth-summary",
            "display": "Wealth Management Summary",
            "model": "gemini-2.0-flash",
            "max_output_tokens": 4096,
            "span_count": 25,
            "avg_input_tokens": 852.64,
            "avg_output_tokens": 123.60,
            "avg_duration_ms": 486.75,
            "monthly_requests": 22500,
            "monthly_cost_usd": 340,
            "waste_signals": {
                "token_limit_waste": True
            }
        }
    ]
}


# ─────────────────────────────────────────────
# DYNATRACE MCP CONNECTION via ADK MCPToolset
# ─────────────────────────────────────────────
async def query_dynatrace_mcp() -> dict:
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StreamableHTTPConnectionParams

    dt_mcp_url = "https://evy70118.apps.dynatrace.com/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp"
    token = DT_PLATFORM_TOKEN or DT_API_TOKEN

    print(f"  Connecting to Dynatrace MCP: {dt_mcp_url}")

    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=dt_mcp_url,
            headers={"Authorization": f"Bearer {token}"}
        )
    )

    session = await toolset._mcp_session_manager.create_session()

    dql = """fetch spans, from:now()-7d
    | filter service.name == "gemini-fintech-app"
    | summarize {
    span_count = count(),
    avg_input_tokens = avg(toDouble(`gen_ai.usage.input_tokens`)),
    avg_output_tokens = avg(toDouble(`gen_ai.usage.output_tokens`)),
    avg_duration_ms = avg(toDouble(duration)/1000000)
    }, by: {span.name, `gen_ai.request.model`, `gen_ai.request.max_output_tokens`, `fintech.monthly_cost_usd`}"""

    print("  Executing DQL query via Dynatrace MCP...")
    result = await session.call_tool('execute-dql', {'dqlQueryString': dql})
    await toolset.close()

    records = result.structuredContent.get('records', [])
    print(f"  ✅ Got {len(records)} records from Dynatrace MCP")

    if not records:
        return None

    return {"result": {"records": records}}


def parse_mcp_response(mcp_result: dict) -> dict:
    """Parses Dynatrace MCP/REST response into standard signals format."""
    if not mcp_result:
        return None
    try:
        records = []
        if isinstance(mcp_result, dict):
            records = mcp_result.get("result", {}).get("records", [])
        elif isinstance(mcp_result, list):
            records = mcp_result

        if not records:
            return None

        endpoints = []
        for r in records:
            endpoint_name = r.get("span.name", "unknown")
            avg_input = float(r.get("avg_input_tokens") or 0)
            avg_output = float(r.get("avg_output_tokens") or 0)
            avg_duration = float(r.get("avg_duration_ms") or 0)
            max_tokens = int(r.get("gen_ai.request.max_output_tokens") or 2048)
            model = r.get("gen_ai.request.model", "gemini-2.0-pro")
            monthly_cost = float(r.get("fintech.monthly_cost_usd") or 0)
            span_count = int(r.get("span_count") or 0)

            output_ratio = avg_output / max_tokens if max_tokens > 0 else 1
            input_output_ratio = avg_output / avg_input if avg_input > 0 else 1

            waste_signals = {
                "low_output_ratio":  output_ratio < 0.15,
                "model_mismatch":    (model == "gemini-2.0-pro" and input_output_ratio < 0.02),
                "high_input_tokens": avg_input > 3000,
                "cacheable":         avg_input > 3000,
                "token_limit_waste": output_ratio < 0.10
            }

            endpoints.append({
                "name":              endpoint_name,
                "display":           endpoint_name.replace("/api/", "").replace("-", " ").title(),
                "model":             model,
                "max_output_tokens": max_tokens,
                "span_count":        span_count,
                "avg_input_tokens":  round(avg_input, 2),
                "avg_output_tokens": round(avg_output, 2),
                "avg_duration_ms":   round(avg_duration, 2),
                "monthly_requests":  span_count * 450,
                "monthly_cost_usd":  monthly_cost,
                "waste_signals":     waste_signals
            })

        return {"service": "fintelligence-demo-app", "source": "dynatrace_mcp", "endpoints": endpoints}

    except Exception as e:
        print(f"  Error parsing MCP response: {e}")
        return None


# ─────────────────────────────────────────────
# FALLBACK — Direct REST API
# ─────────────────────────────────────────────
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def query_dynatrace_rest() -> dict:
    """Fallback: queries Dynatrace via REST API when MCP is unavailable."""
    url = f"{DT_ENDPOINT}/platform/storage/query/v1/query:execute"
    headers = {
        "Authorization": f"Api-Token {DT_API_TOKEN}",
        "Content-Type":  "application/json"
    }
    payload = {
        "query": "fetch spans | filter service.name == \"fintelligence-demo-app\" | summarize span_count = count(), avg_input_tokens = avg(toDouble(gen_ai.usage.input_tokens)), avg_output_tokens = avg(toDouble(gen_ai.usage.output_tokens)), avg_duration_ms = avg(toDouble(duration) / 1000000) , by: {span.name}",
        "defaultTimeframeStart": "now-24h",
        "defaultTimeframeEnd": "now"
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


# ─────────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────────
def pull_dynatrace_signals() -> dict:
    """
    Step 1 — OBSERVE
    Priority:
    1. Demo mode → mock data
    2. Dynatrace MCP server (via ADK MCPToolset)
    3. Dynatrace REST API (fallback)
    4. Mock data (final fallback)
    """

    if DEMO_MODE:
        print("  [DEMO MODE] Using mock Dynatrace signals")
        return MOCK_SIGNALS

    if not DT_ENDPOINT or not DT_API_TOKEN:
        print("  [FALLBACK] Dynatrace credentials not set → using mock data")
        return MOCK_SIGNALS

    # Try MCP first
    try:
        print("  Attempting Dynatrace MCP connection...")
        mcp_result = asyncio.run(query_dynatrace_mcp())
        parsed = parse_mcp_response(mcp_result)
        if parsed and parsed.get("endpoints"):
            print(f"  ✅ Got signals via Dynatrace MCP for {len(parsed['endpoints'])} endpoints")
            return parsed
        print("  MCP returned no data → trying REST API")
    except Exception as e:
        print(f"  MCP failed: {e} → trying REST API")

    # Try REST fallback
    try:
        print("  Querying Dynatrace via REST API...")
        rest_result = query_dynatrace_rest()
        records = rest_result.get("result", {}).get("records", [])
        parsed = parse_mcp_response({"result": {"records": records}})
        if parsed and parsed.get("endpoints"):
            print(f"  ✅ Got signals via REST API for {len(parsed['endpoints'])} endpoints")
            parsed["source"] = "dynatrace_rest"
            return parsed
    except Exception as e:
        print(f"  REST API failed: {e}")

    print("  [FALLBACK] All Dynatrace connections failed → using mock data")
    return MOCK_SIGNALS


if __name__ == "__main__":
    signals = pull_dynatrace_signals()
    print(json.dumps(signals, indent=2))
