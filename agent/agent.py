"""
Fintelligence Agent — Main Orchestrator
=========================================
The core ADK agent that runs the full 6-step flow:

  1. OBSERVE    — Pull signals from Dynatrace MCP
  2. CLASSIFY   — Semantically analyze request patterns (Gemini)
  3. IDENTIFY   — Cross-reference signals + semantics → find waste
  4. PLAN       — Generate ranked optimization plan
  5. ACT        — Execute safe actions, queue risky ones for approval
  6. REPORT     — Generate plain-English compliance summary

Run locally:
    python3 agent.py

Environment variables required:
    GEMINI_API_KEY   — Google AI Studio API key
    DT_ENDPOINT      — https://YOUR_ENV.live.dynatrace.com
    DT_API_TOKEN     — Dynatrace API token
    DEMO_MODE        — true/false (default: false)
"""

import os
import json
import uuid
from datetime import datetime
from typing import Optional

# Import our tools
import sys
sys.path.append(os.path.dirname(__file__))

from tools.observe import pull_dynatrace_signals
from tools.classify import classify_request_patterns
from tools.identify_waste import identify_waste
from google.adk.agents import Agent
from google.adk.runners import Runner  
from google.adk.sessions import InMemorySessionService

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"

# Storage for pending approvals and applied actions
# In production this would be Firestore / Cloud SQL
PENDING_APPROVALS = []
APPLIED_ACTIONS = []
REJECTED_ACTIONS = []

def create_adk_agent():
    """
    Creates a Google ADK agent wrapping Fintelligence's
    optimization workflow. Required by Google Cloud Agent Builder.
    """
    fintelligence_agent = Agent(
        name="fintelligence",
        model="gemini-2.0-flash",
        description=(
            "Fintelligence is an AI workload optimization agent "
            "for financial services. It monitors Gemini-powered "
            "endpoints via Dynatrace MCP and identifies cost waste."
        ),
        instruction=(
            "You are Fintelligence, an AI cost optimization agent. "
            "Analyze Dynatrace signals for Gemini workloads and "
            "identify model routing, caching, and token optimization "
            "opportunities. Always prioritize compliance and safety."
        ),
    )
    return fintelligence_agent

# ─────────────────────────────────────────────
# STEP 4: PLAN
# ─────────────────────────────────────────────
def generate_plan(waste_results: dict) -> dict:
    """
    Step 4 — PLAN
    Summarizes the optimization plan with
    clear dollar amounts and risk levels.
    """
    print("\n📋 STEP 4: Generating optimization plan...")

    plan = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_monthly_saving": waste_results["total_monthly_saving"],
            "total_annual_saving": waste_results["total_annual_saving"],
            "auto_apply_saving": waste_results["auto_apply_saving"],
            "approval_saving": waste_results["approval_saving"],
            "auto_apply_count": len(waste_results["auto_apply"]),
            "approval_count": len(waste_results["needs_approval"]),
        },
        "auto_apply": waste_results["auto_apply"],
        "needs_approval": waste_results["needs_approval"],
    }

    print(f"  💰 Total savings identified: ${waste_results['total_monthly_saving']:.2f}/month")
    print(f"  ✅ Auto-apply: ${waste_results['auto_apply_saving']:.2f}/month")
    print(f"  🔐 Needs compliance approval: ${waste_results['approval_saving']:.2f}/month")

    return plan


# ─────────────────────────────────────────────
# STEP 5: ACT
# ─────────────────────────────────────────────
def execute_safe_actions(plan: dict) -> list:
    """
    Step 5a — ACT (Safe actions)
    Automatically applies low-risk optimizations.
    No human approval needed.
    """
    print("\n⚡ STEP 5a: Executing safe actions automatically...")

    executed = []

    for action in plan["auto_apply"]:
        action_id = str(uuid.uuid4())[:8]

        print(f"  Applying: {action['title']}")
        print(f"  Saving:   ${action['saving_per_month']:.2f}/month")

        # Simulate execution (in production: call GCP APIs)
        result = _simulate_action_execution(action)

        executed.append({
            "id": action_id,
            "title": action["title"],
            "type": action["type"],
            "saving_per_month": action["saving_per_month"],
            "status": "applied",
            "applied_at": datetime.now().isoformat(),
            "result": result,
            "compliance_note": action.get("compliance_note", ""),
        })

        print(f"  ✅ Applied (ID: {action_id})")

    APPLIED_ACTIONS.extend(executed)
    return executed


def queue_for_approval(plan: dict) -> list:
    """
    Step 5b — ACT (Risky actions)
    Queues high-risk optimizations for compliance approval.
    These appear in the approval UI for human review.
    """
    print("\n🔐 STEP 5b: Queueing actions for compliance approval...")

    queued = []

    for action in plan["needs_approval"]:
        approval_id = str(uuid.uuid4())[:8]

        queued.append({
            "id": approval_id,
            "title": action["title"],
            "description": action["description"],
            "type": action["type"],
            "saving_per_month": action["saving_per_month"],
            "saving_per_year": action["saving_per_year"],
            "current_cost": action["current_cost"],
            "projected_cost": action["projected_cost"],
            "risk": action["risk"],
            "confidence": action.get("confidence", 0.8),
            "compliance_note": action["compliance_note"],
            "latency_impact": action["latency_impact"],
            "quality_risk": action["quality_risk"],
            "action_details": action["action"],
            "status": "pending",
            "queued_at": datetime.now().isoformat(),
        })

        print(f"  Queued: {action['title']}")
        print(f"  Saving: ${action['saving_per_month']:.2f}/month (awaiting approval)")

    PENDING_APPROVALS.extend(queued)
    return queued


def _simulate_action_execution(action: dict) -> str:
    """
    Simulates GCP API calls for demo purposes.
    In production, these would be real API calls:
    - Cloud Run service updates
    - Vertex AI caching configuration
    - Token limit updates via environment variables
    """
    action_type = action["action"]["type"]

    if action_type == "enable_context_cache":
        return f"Context cache enabled for {action['action']['endpoint']} (TTL: {action['action'].get('ttl_seconds', 3600)}s)"
    elif action_type == "update_token_limit":
        return (f"max_output_tokens updated: "
                f"{action['action']['current_max']} → {action['action']['recommended_max']} "
                f"on {action['action']['endpoint']}")
    elif action_type == "update_model_config":
        return (f"Model routing configured: "
                f"{action['action']['current_model']} → {action['action']['new_model']} "
                f"on {action['action']['endpoint']}")
    else:
        return f"Action {action_type} executed successfully"


# ─────────────────────────────────────────────
# STEP 6: REPORT
# ─────────────────────────────────────────────
def generate_report(
    signals: dict,
    plan: dict,
    executed: list,
    queued: list
) -> dict:
    """
    Step 6 — REPORT
    Generates a plain-English compliance report
    with full audit trail.
    """
    print("\n📊 STEP 6: Generating compliance report...")

    auto_saving = sum(e["saving_per_month"] for e in executed)
    approval_saving = sum(q["saving_per_month"] for q in queued)
    total_saving = auto_saving + approval_saving

    report = {
        "generated_at": datetime.now().isoformat(),
        "service": signals.get("service", "fintelligence-demo-app"),
        "period": "Weekly AI Efficiency Report",
        "summary": {
            "total_waste_identified": round(total_saving, 2),
            "auto_optimized": round(auto_saving, 2),
            "awaiting_approval": round(approval_saving, 2),
            "annual_savings_potential": round(total_saving * 12, 2),
        },
        "actions_taken": executed,
        "pending_approvals": queued,
        "audit_trail": [
            {
                "action": e["title"],
                "status": "AUTO-APPLIED",
                "saving": f"${e['saving_per_month']:.2f}/month",
                "timestamp": e["applied_at"],
                "compliance": e["compliance_note"]
            }
            for e in executed
        ] + [
            {
                "action": q["title"],
                "status": "PENDING APPROVAL",
                "saving": f"${q['saving_per_month']:.2f}/month",
                "timestamp": q["queued_at"],
                "compliance": q["compliance_note"]
            }
            for q in queued
        ],
        "plain_english_summary": (
            f"This week, Fintelligence analyzed your Gemini-powered financial services "
            f"and identified ${total_saving:.2f}/month (${total_saving*12:.2f}/year) in AI spend waste. "
            f"${auto_saving:.2f}/month has been optimized automatically with zero risk. "
            f"${approval_saving:.2f}/month more is awaiting your compliance approval. "
            f"Full audit trail generated for all actions."
        )
    }

    print(f"  ✅ Report generated")
    print(f"  📈 Total waste identified: ${total_saving:.2f}/month")
    print(f"  ✅ Auto-optimized: ${auto_saving:.2f}/month")
    print(f"  🔐 Awaiting approval: ${approval_saving:.2f}/month")

    return report


# ─────────────────────────────────────────────
# APPROVAL HANDLERS (called from UI)
# ─────────────────────────────────────────────
def approve_action(approval_id: str, mode: str = "full") -> dict:
    """
    Called when compliance officer approves a recommendation.
    mode: "full" = apply to 100% traffic
          "test" = apply to 10% traffic first
    """
    for approval in PENDING_APPROVALS:
        if approval["id"] == approval_id:
            approval["status"] = f"approved_{mode}"
            approval["approved_at"] = datetime.now().isoformat()
            approval["approval_mode"] = mode

            result = _simulate_action_execution({
                "action": approval["action_details"],
                "title": approval["title"],
                "type": approval["type"],
            })

            approval["execution_result"] = result
            APPLIED_ACTIONS.append(approval)
            PENDING_APPROVALS.remove(approval)

            return {
                "status": "approved",
                "mode": mode,
                "result": result,
                "saving_locked_in": approval["saving_per_month"]
            }

    return {"status": "error", "message": f"Approval ID {approval_id} not found"}


def reject_action(approval_id: str, reason: str = "") -> dict:
    """Called when compliance officer rejects a recommendation."""
    for approval in PENDING_APPROVALS:
        if approval["id"] == approval_id:
            approval["status"] = "rejected"
            approval["rejected_at"] = datetime.now().isoformat()
            approval["rejection_reason"] = reason
            REJECTED_ACTIONS.append(approval)
            PENDING_APPROVALS.remove(approval)
            return {"status": "rejected", "id": approval_id}

    return {"status": "error", "message": f"Approval ID {approval_id} not found"}


def get_pending_approvals() -> list:
    return PENDING_APPROVALS


def get_applied_actions() -> list:
    return APPLIED_ACTIONS


# ─────────────────────────────────────────────
# MAIN — Run the full agent flow
# ─────────────────────────────────────────────
def run_fintelligence_agent() -> dict:
    # Initialize Google ADK agent
    adk_agent = create_adk_agent()
    print(f"  ADK Agent initialized: {adk_agent.name}")
    
    """
    Runs the complete 6-step Fintelligence agent flow.
    Returns the final report.
    """
    print("=" * 60)
    print("  🚀 Fintelligence Agent Starting")
    print("  AI Workload Optimization for Financial Services")
    print("=" * 60)

    # ── Step 1: Observe ───────────────────────────────────────
    print("\n📡 STEP 1: Pulling signals from Dynatrace...")
    signals = pull_dynatrace_signals()
    print(f"  Found {len(signals['endpoints'])} endpoints to analyze")

    # ── Step 2: Classify ──────────────────────────────────────
    print("\n🧠 STEP 2: Classifying request patterns with Gemini...")
    classifications = []
    for endpoint in signals["endpoints"]:
        classification = classify_request_patterns(endpoint)
        classifications.append(classification)

    # ── Step 3: Identify Waste ────────────────────────────────
    print("\n🔍 STEP 3: Identifying waste patterns...")
    waste_results = identify_waste(signals, classifications)

    # ── Step 4: Plan ──────────────────────────────────────────
    plan = generate_plan(waste_results)

    # ── Step 5: Act ───────────────────────────────────────────
    executed = execute_safe_actions(plan)
    queued = queue_for_approval(plan)

    # ── Step 6: Report ────────────────────────────────────────
    report = generate_report(signals, plan, executed, queued)

    print("\n" + "=" * 60)
    print("  ✅ Fintelligence Agent Complete")
    print(f"  💰 Total savings identified: ${report['summary']['total_waste_identified']:.2f}/month")
    print(f"  ✅ Auto-applied: ${report['summary']['auto_optimized']:.2f}/month")
    print(f"  🔐 Awaiting approval: ${report['summary']['awaiting_approval']:.2f}/month")
    print("=" * 60)

    return report


if __name__ == "__main__":
    report = run_fintelligence_agent()
    print("\n📄 FULL REPORT:")
    print(json.dumps(report, indent=2))
