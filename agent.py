#!/usr/bin/env python3
"""
FirstHelm quickstart agent — the governed hello world.

A deliberately tiny agent that runs one task with three actions of
increasing risk. Before EACH action it asks the FirstHelm control plane
for a verdict, and it only proceeds when the human in the loop says so.

Zero dependencies: standard-library Python only.

    export FIRSTHELM_API_KEY="fhk_..."     (macOS/Linux)
    $env:FIRSTHELM_API_KEY="fhk_..."       (Windows PowerShell)
    python agent.py
"""

import json
import os
import urllib.request
import urllib.error

API_URL = os.environ.get("FIRSTHELM_API_URL", "https://api.firsthelm.dev/functions")
API_KEY = os.environ.get("FIRSTHELM_API_KEY", "")

if not API_KEY:
    raise SystemExit("Set FIRSTHELM_API_KEY first — see the README, step 2.")


def call(function: str, payload: dict) -> dict:
    """POST JSON to a FirstHelm backend function and return the response."""
    req = urllib.request.Request(
        f"{API_URL}/{function}",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
            # Default "Python-urllib" is blocked by some API gateways;
            # identify ourselves properly instead.
            "User-Agent": "firsthelm-quickstart/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        raise SystemExit(
            f"\nAPI error {e.code} from {function}:\n{body}\n"
            "\nIf this is unexpected, paste the lines above back to us — "
            "they say exactly what the control plane refused."
        )
    except urllib.error.URLError as e:
        raise SystemExit(f"\nCould not reach {API_URL} ({e.reason}). "
                        "Check your connection and FIRSTHELM_API_URL.")



def extract_agent_id(response) -> str:
    """Pull the agent id out of a registerAgent response.

    Envelope: {"status": "ok", "agent": {"id": "...", ...}}
    Also tolerates {"id": ...} or {"data": {...}} shapes.
    """
    if not isinstance(response, dict):
        return "unknown"
    for candidate in (
        response.get("agent"),
        response.get("data") if isinstance(response.get("data"), dict) else None,
        response,
    ):
        if isinstance(candidate, dict) and candidate.get("id"):
            return candidate["id"]
    return "unknown"


def get_verdict(response: dict) -> str:
    """
    Extract the constraint verdict from an evaluateConstraint response.

    FirstHelm returns one of three verdicts:
        allowed         -> the agent may proceed
        blocked         -> the action is refused, it never executes
        needs_approval  -> the action pauses; a human must decide

    The key is read defensively so this demo keeps working even if the
    response envelope changes shape.
    """
    if not isinstance(response, dict):
        return "unknown"
    for candidate in (response, response.get("data") or {}):
        if isinstance(candidate, dict):
            for key in ("verdict", "status", "result", "decision"):
                if key in candidate:
                    return str(candidate[key])
    return "unknown"


def main() -> None:
    print("=" * 62)
    print("FirstHelm quickstart agent")
    print("=" * 62)

    # ------------------------------------------------------------------
    # Beat 1: Agent registry — you cannot govern what you cannot see.
    # ------------------------------------------------------------------
    print("\n[1] Registering agent with the control plane...")
    reg = call("registerAgent", {
        "name": "quickstart-agent",
        "framework": "custom",
        "description": "Quickstart demo agent — three actions, one governance loop.",
    })
    agent_id = extract_agent_id(reg)
    if agent_id == "unknown":
        raise SystemExit(
            "Could not find an agent id in the registerAgent response. "
            f"Raw response:\n{json.dumps(reg, indent=2)[:600]}"
        )
    print(f"    Agent ID: {agent_id}")
    print("    Open your dashboard → Agents: it should be there now.")

    # ------------------------------------------------------------------
    # Beat 2: The task. Three actions, increasing risk.
    # action_type is an enum — FirstHelm accepts: tool_call, reasoning,
    # communication, decision, error, waiting_approval, completed.
    # ------------------------------------------------------------------
    task = [
        {"type": "reasoning",    "description": "Draft a welcome email for customer #1042 (planning step)"},
        {"type": "communication", "description": "Send the welcome email to customer #1042"},
        {"type": "tool_call",     "description": "Delete records older than 90 days"},
    ]
    audit = []

    for action in task:
        print(f"\n[2] Agent wants to: {action['description']}")

        # -- Record the intended action on the audit trail ---------------
        call("logActivity", {
            "agent_id": agent_id,
            "action_type": action["type"],
            "description": action["description"],
        })

        # -- Pre-execution check: evaluate the constraint, get the verdict
        response = call("evaluateConstraint", {
            "agent_id": agent_id,
            "action_type": action["type"],
            "description": action["description"],
        })
        verdict = get_verdict(response)
        print(f"    Control plane says: {verdict.upper()}")
        if verdict == "unknown":
            print("    (Unrecognised response — paste this to us if unsure:)")
            print(f"    {json.dumps(response, default=str)[:400]}")
        audit.append((action["type"], verdict))

        if verdict == "blocked":
            # The constraint refused it. The action NEVER executes.
            print("    → Blocked before execution. Nothing was deleted. Good.")

        elif verdict == "needs_approval":
            # Beat 3: Human-in-the-loop. Pause mid-flight and ask.
            print("    → Pausing. Requesting human approval...")
            call("requestApproval", {
                "agent_id": agent_id,
                "action_description": action["description"],
            })
            print("    Check your dashboard → Approvals. Approve or reject it.")
            input("    Once you've decided in the dashboard, press Enter to continue... ")
            print("    → Decision made. The agent continues, and the call is on the record.")

        else:
            # allowed (or no constraint matches — also a useful thing to
            # notice: if nothing pauses, check step 3 in the README).
            print("    → Allowed. Action executes.")

    # ------------------------------------------------------------------
    # Beat 4: Audit trail — every action and verdict, on the record.
    # ------------------------------------------------------------------
    print("\n[3] Audit summary for this run:")
    for action_type, verdict in audit:
        print(f"    {action_type:<14} {verdict}")
    print("\nFull detail lives in your dashboard → Activity Log.")
    print("That's the loop: registry → pre-execution check → approval → audit.")
    print("Frameworks build agents. FirstHelm governs them.")


if __name__ == "__main__":
    main()
