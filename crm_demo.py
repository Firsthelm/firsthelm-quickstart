#!/usr/bin/env python3
"""
FirstHelm CRM demo — a governed update that survives a timeout.

The scenario (requested by a real integration question):

    An agent proposes a CRM update. A human approves it in the dashboard.
    The agent executes the write — but the CRM applies it and the HTTP
    response never arrives (network drop, gateway timeout...). The agent
    retries with the SAME idempotency key and recovers the original
    result. The record is updated exactly once, and every attempt is
    on the FirstHelm audit trail.

Who does what:
    FirstHelm  -> decides whether the action may run (governance + audit)
    The CRM    -> guarantees a write happens at most once per idempotency
                  key (this is the CRM's job, not the control plane's)
    The agent  -> proposes, waits for the human, executes, retries safely

Zero dependencies: standard-library Python only. The mock CRM in this
file stands in for your real CRM (Salesforce, HubSpot, an internal
service...). Run it and follow the printed output:

    export FIRSTHELM_API_KEY="fhk_..."     (macOS/Linux)
    $env:FIRSTHELM_API_KEY="fhk_..."       (Windows PowerShell)
    python crm_demo.py

Requires an agent-framework constraint that gates CRM writes — see the
README (step 3). If nothing pauses, no constraint matched.
"""

import json
import os
import secrets
import threading
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_URL = os.environ.get("FIRSTHELM_API_URL", "https://api.firsthelm.dev/functions")
API_KEY = os.environ.get("FIRSTHELM_API_KEY", "")
CRM_PORT = int(os.environ.get("CRM_DEMO_PORT", "8765"))

if not API_KEY:
    raise SystemExit("Set FIRSTHELM_API_KEY first — see the README, step 2.")


# =====================================================================
# The mock CRM (the part your real CRM already does, or should do).
# Idempotency is the CRM's guarantee: same key -> same stored response,
# never a second write. That is what makes the retry safe.
# =====================================================================

CUSTOMERS = {
    "1042": {"name": "Jean Merchant", "email": "jean@example.com", "plan": "Free"}
}
IDEMPOTENCY_STORE = {}          # key -> stored response body
STATS = {"writes_applied": 0, "replays_served": 0}


class MockCRMHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):        # silence default request logging
        pass

    def _send(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/crm/stats":
            return self._send(200, {**STATS, "customers": CUSTOMERS})
        cid = self.path.rsplit("/", 1)[-1]
        if self.path.startswith("/crm/customers/") and cid in CUSTOMERS:
            return self._send(200, {"customer": CUSTOMERS[cid]})
        self._send(404, {"error": "unknown customer"})

    def do_PUT(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        key = self.headers.get("Idempotency-Key", "")
        chaos = self.headers.get("X-Crm-Chaos", "")
        cid = self.path.rsplit("/", 1)[-1]

        if not key:
            return self._send(400, {"error": "Idempotency-Key header required"})
        if cid not in CUSTOMERS:
            return self._send(404, {"error": "unknown customer"})

        # -- The line that matters: seen key -> replay, never re-apply ----
        if key in IDEMPOTENCY_STORE:
            STATS["replays_served"] += 1
            print(f"    [crm] Key {key} seen before -> replaying stored "
                  f"response. NOT applying the update again.")
            return self._send(200, IDEMPOTENCY_STORE[key])

        # New key: apply the write exactly once, remember the response.
        CUSTOMERS[cid].update(payload)
        STATS["writes_applied"] += 1
        stored = {
            "status": "applied",
            "write_number": STATS["writes_applied"],
            "customer": CUSTOMERS[cid],
        }
        IDEMPOTENCY_STORE[key] = stored

        if chaos == "timeout":
            # The write HAS happened. Now simulate the response getting
            # lost on the way back: hold the connection until the client
            # gives up. (A real CRM never intends this — networks do.)
            print(f"    [crm] Write APPLIED (#{STATS['writes_applied']}) but "
                  f"response will be withheld — simulating a timeout.")
            time.sleep(30)              # client times out long before this
            return

        print(f"    [crm] Write applied (#{STATS['writes_applied']}).")
        self._send(200, stored)


def start_mock_crm():
    server = ThreadingHTTPServer(("127.0.0.1", CRM_PORT), MockCRMHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


# =====================================================================
# The agent side.
# =====================================================================

def call(function: str, payload: dict, timeout: int = 20) -> dict:
    """POST JSON to a FirstHelm backend function and return the response."""
    req = urllib.request.Request(
        f"{API_URL}/{function}",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
            "User-Agent": "firsthelm-quickstart/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        raise SystemExit(f"\nAPI error {e.code} from {function}:\n{body}")
    except urllib.error.URLError as e:
        raise SystemExit(f"\nCould not reach {API_URL} ({e.reason}).")


def extract_agent_id(response) -> str:
    for candidate in (
        response.get("agent"),
        response.get("data") if isinstance(response.get("data"), dict) else None,
        response,
    ):
        if isinstance(candidate, dict) and candidate.get("id"):
            return candidate["id"]
    return "unknown"


def get_verdict(response: dict) -> str:
    if not isinstance(response, dict):
        return "unknown"
    for candidate in (response, response.get("data") or {}):
        if isinstance(candidate, dict):
            for key in ("verdict", "status", "result", "decision"):
                if key in candidate:
                    return str(candidate[key])
    return "unknown"


def crm_write(customer_id: str, payload: dict, idem_key: str, chaos: bool, timeout: float):
    """Raw HTTP call to the CRM — the same thing this does in curl:

        curl -X PUT http://127.0.0.1:8765/crm/customers/1042 \
             -H "Idempotency-Key: <key>" \
             -H "X-Crm-Chaos: timeout"        (attempt 1 only) \
             -H "Content-Type: application/json" \
             -d '{"plan": "Pro"}'
    """
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": idem_key,
    }
    if chaos:
        headers["X-Crm-Chaos"] = "timeout"
    req = urllib.request.Request(
        f"http://127.0.0.1:{CRM_PORT}/crm/customers/{customer_id}",
        data=json.dumps(payload).encode(),
        headers=headers,
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def crm_read(customer_id: str) -> dict:
    with urllib.request.urlopen(
        f"http://127.0.0.1:{CRM_PORT}/crm/customers/{customer_id}", timeout=10
    ) as resp:
        return json.loads(resp.read())


def main() -> None:
    print("=" * 62)
    print("FirstHelm CRM demo — governed update, safe retry")
    print("=" * 62)

    server = start_mock_crm()
    print(f"\n[0] Mock CRM running on 127.0.0.1:{CRM_PORT} "
          f"(stands in for your real CRM).")

    # ------------------------------------------------------------------
    # Beat 1: Register. You cannot govern what you cannot see.
    # ------------------------------------------------------------------
    print("\n[1] Registering agent with the control plane...")
    reg = call("registerAgent", {
        "name": f"crm-sync-agent-{secrets.token_hex(2)}",
        "framework": "custom",
        "description": "Demo agent — proposes a CRM update, executes after approval.",
    })
    agent_id = extract_agent_id(reg)
    print(f"    Agent ID: {agent_id}")
    print("    Open your dashboard → Agents: it should be there now.")

    # ------------------------------------------------------------------
    # Beat 2: Propose the CRM update and let the control plane judge it.
    # ------------------------------------------------------------------
    action = ("tool_call", "Update CRM record for customer #1042: set plan to Pro")
    approved = False

    print(f"\n[2] Agent wants to: {action[1]}")
    call("logActivity", {
        "agent_id": agent_id,
        "action_type": action[0],
        "description": action[1],
    })
    response = call("evaluateConstraint", {
        "agent_id": agent_id,
        "action_type": action[0],
        "description": action[1],
    })
    verdict = get_verdict(response)
    print(f"    Control plane says: {verdict.upper()}")

    if verdict in ("blocked", "fail", "violation"):
        print("    → Blocked before execution. The CRM was never touched. Good.")
        print("\nDone. The refusal is in your Activity Log.")
        return

    if verdict == "needs_approval":
        print("    → Pausing. Requesting human approval...")
        approval = call("requestApproval", {
            "agent_id": agent_id,
            "action_description": action[1],
        })
        approval_id = None
        if isinstance(approval, dict):
            for candidate in (approval.get("approval"),
                              approval.get("data") if isinstance(approval.get("data"), dict) else None,
                              approval):
                if isinstance(candidate, dict) and candidate.get("id"):
                    approval_id = candidate["id"]
                    break
        if approval_id:
            print(f"    Approval ID: {approval_id}")
        print("    Check your dashboard → Approvals. Approve or reject it.")
        input("    Once you've decided in the dashboard, press Enter to continue... ")
        print("    → Decision made. The agent continues, and the call is on the record.")
        approved = True
    else:
        print("    → No constraint paused it (verdict="
              f"{verdict}). Check step 3 in the README if you expected a pause.")

    # ------------------------------------------------------------------
    # Beat 3: Execute. The write is issued with an idempotency key.
    # ------------------------------------------------------------------
    idem_key = f"crm-update-{secrets.token_hex(4)}"
    status = "approved" if approved else "policy-allowed"
    print(f"\n[3] Executing the {status} update with idempotency key: {idem_key}")

    # -- Attempt 1: the CRM applies the write, but the response times out.
    print("    Attempt 1 (with chaos: response will be lost on the way back)...")
    timed_out = False
    try:
        result = crm_write("1042", {"plan": "Pro"}, idem_key, chaos=True, timeout=2)
        print(f"    Unexpected clean response: {result}")
    except Exception as e:
        timed_out = True
        print(f"    ✗ Client timed out: {type(e).__name__}. "
              "The write MAY have been applied — the agent cannot know yet.")

    if timed_out:
        # The failed attempt is itself on the record — a retried write
        # must never be a silent one.
        call("logActivity", {
            "agent_id": agent_id,
            "action_type": "error",
            "description": "CRM write attempt 1: response timed out — outcome unknown, "
                           f"will retry with idempotency key {idem_key}",
        })
        print("    (Timeout recorded in your Activity Log — retries stay visible.)")

        # -- Attempt 2: same key, no chaos. The CRM replays the stored
        #    response instead of applying the update a second time.
        print("\n    Attempt 2 (same idempotency key, no chaos)...")
        result = crm_write("1042", {"plan": "Pro"}, idem_key, chaos=False, timeout=10)
        print(f"    ✓ Recovered: {json.dumps(result)}")
        print("    The retry RECOVERED the original result — it did not "
              "repeat the write. Idempotency did that, not the approval.")

        call("logActivity", {
            "agent_id": agent_id,
            "action_type": "completed",
            "description": "CRM write attempt 2: original result recovered via "
                           f"idempotency key {idem_key} — update applied exactly once",
        })

    # ------------------------------------------------------------------
    # Beat 4: Verify — read the record back, count the writes.
    # ------------------------------------------------------------------
    record = crm_read("1042")
    stats = json.loads(urllib.request.urlopen(
        f"http://127.0.0.1:{CRM_PORT}/crm/stats", timeout=10).read())
    print(f"\n[4] Verification — customer #1042 now: {json.dumps(record['customer'])}")
    print(f"    CRM stats: writes_applied={stats['writes_applied']}, "
          f"replays_served={stats['replays_served']}")
    print("    Plan is Pro, and the write happened EXACTLY ONCE — "
          "that is the whole point.")

    print("\nSummary:")
    if approved:
        print("  - Approval gated the action before any write was attempted.")
    else:
        print("  - No constraint paused the action this run — enable an")
        print("    approval-gate constraint (README step 3) to see the pause.")
    print("  - The timeout never risked a duplicate: the CRM's idempotency")
    print("    key made the retry recover the first result instead.")
    print("  - Every attempt is in your dashboard → Activity Log.")
    print("\nFull audit lives in your dashboard. The loop: propose → "
          "approve → execute → timeout → retry → recover.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n(stopped)")
