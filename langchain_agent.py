#!/usr/bin/env python3
"""
FirstHelm quickstart — LangChain variant.

Same governance loop as agent.py, but slotted into a LangChain-style
workflow so you can see how the control plane wraps a real framework:

    @tool wrappers call logActivity BEFORE the tool's real logic runs.

This keeps the demo runnable without an OpenAI key: the "agent" is a
deterministic task loop, but the pattern is exactly what you'd bolt onto
a production LangChain agent.

    pip install -r requirements-langchain.txt
    export FIRSTHELM_API_KEY="fhk_..."
    export FIRSTHELM_API_URL="https://api.firsthelm.dev/functions"
    python3 langchain_agent.py
"""

import json
import os
import urllib.request
from functools import wraps

API_URL = os.environ.get("FIRSTHELM_API_URL", "https://api.firsthelm.dev/functions")
API_KEY = os.environ.get("FIRSTHELM_API_KEY", "")

if not API_KEY:
    raise SystemExit("Set FIRSTHELM_API_KEY first — see the README, step 2.")


def firsthelm_call(function: str, payload: dict) -> dict:
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
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def governed(tool_name: str, action_type: str):
    """
    Decorator that turns any function into a FirstHelm-governed tool.

    Every call is checked against your control-plane constraints BEFORE
    the function body runs. If the constraint says blocked or
    needs_approval, the real logic never executes until a human decides.

    This is the whole integration pattern in production, too: wrap your
    tools, not your agent.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(agent_id: str, *args, **kwargs):
            # record the intended action, then evaluate the constraint
            firsthelm_call("logActivity", {
                "agent_id": agent_id,
                "action_type": ACTION_TYPE,
                "description": fn.__doc__ or tool_name,
            })
            response = firsthelm_call("evaluateConstraint", {
                "agent_id": agent_id,
                "action_type": ACTION_TYPE,
                "description": fn.__doc__ or tool_name,
            })
            verdict = (
                response.get("verdict")
                or (response.get("data", {}) or {}).get("verdict")
                or "unknown"
                if isinstance(response, dict) else "unknown"
            )
            print(f"    [control plane] {tool_name} -> {verdict}")

            if verdict == "blocked":
                print("    [control plane] refusing to run tool: blocked by constraint")
                return {"status": "blocked", "result": None}

            if verdict == "needs_approval":
                firsthelm_call("requestApproval", {
                    "agent_id": agent_id,
                    "action_description": fn.__doc__ or tool_name,
                })
                print("    [control plane] paused: approve in the dashboard, then re-run")
                return {"status": "needs_approval", "result": None}

            return {"status": "allowed", "result": fn(*args, **kwargs)}

        return wrapper

    return decorator


# --- The "agent": a minimal LangChain-style task loop -------------------

@governed("send_email", action_type="communication")
def send_email(to: str, body: str) -> dict:
    """Send the welcome email to a customer."""
    print(f"    [tool] email sent to {to}")
    return {"sent": True, "to": to}


@governed("delete_old_records", action_type="tool_call")
def delete_old_records(days: int = 90) -> dict:
    """Delete records older than the given number of days."""
    print(f"    [tool] would delete records older than {days} days")
    return {"deleted": 0}


def main() -> None:
    print("=" * 62)
    print("FirstHelm quickstart — LangChain variant")
    print("=" * 62)

    reg = firsthelm_call("registerAgent", {
        "name": "quickstart-langchain-agent",
        "framework": "langchain",
        "description": "Quickstart demo — governed LangChain-style tools.",
        "autonomy_level": 2,
    })
    agent_id = (
        (reg.get("id") or (reg.get("data", {}) or {}).get("id") or "unknown")
        if isinstance(reg, dict) else "unknown"
    )
    print(f"\nAgent registered: {agent_id}")

    print("\nStep 1: draft the email (no tool call — just planning)")
    print("Step 2: send it (governed tool — watch the pre-execution check)")
    send_email(agent_id, "customer1042@example.com", "Welcome aboard!")

    print("\nStep 3: housekeeping (governed tool — this one should get blocked)")
    delete_old_records(agent_id, days=90)

    print("\nDone. Every call was checked before execution, and every")
    print("verdict is in your dashboard → Activity Log.")


if __name__ == "__main__":
    main()
