# FirstHelm Quickstart

Govern your first AI agent in **under 10 minutes**.

This repo contains a tiny demo agent (`agent.py`, zero dependencies — pure
standard-library Python) that connects to the
[FirstHelm control plane](https://firsthelm.dev) and demonstrates the full
governance loop:

```
register agent  →  run task  →  check constraint before each action
                →  approve the risky one in your dashboard  →  audit trail
```

The demo agent attempts three actions — drafting a message, sending an
email, and deleting old records — and each one is checked against your
policy *before* it executes. What you see depends on the constraints you
enable:

- **No constraints (or none that match)** — every action returns `PASS`
  and executes: the happy path, fully audited.
- **An Approval Gate enabled** — actions pause mid-flight with
  `NEEDS_APPROVAL` and wait for your decision in the FirstHelm dashboard.
  Silence is never treated as consent.
- **A Budget Limit or Time Window** — policy that governs by cost and
  schedule, no code required.

That's the whole pitch: frameworks build agents; FirstHelm governs them.

---

## Prerequisites

- Python 3.9+ (no packages to install for `agent.py`)
- A FirstHelm account: https://firsthelm.dev/register
- An API key: create one in the dashboard under **Settings → API keys**

## Steps

### 1. Get your API key

Sign up at https://firsthelm.dev and create an API key. Treat it like a
password — FirstHelm stores only a hash and a rotated key instantly
invalidates the old one.

### 2. Clone this repo and set your key

```bash
git clone https://github.com/Firsthelm/firsthelm-quickstart.git
cd firsthelm-quickstart
export FIRSTHELM_API_KEY="fhk_your_api_key_here"    # macOS / Linux
# Windows PowerShell (use single quotes — double quotes can mangle keys):
#   $env:FIRSTHELM_API_KEY='fhk_your_api_key_here'
```

### 3. Create the demo constraints in the dashboard

In the FirstHelm dashboard, open **Constraints**. Constraints are typed
policy templates — Approval Gate, Action Restriction, Budget Limit, Time
Window, Forbidden Action — with parameters, not code. For the classic demo:

1. Enable the **Approval Gate** to watch actions pause for your decision
   in **Dashboard → Approvals**.
2. Add a **Budget Limit** or **Time Window** to see policy that governs by
   cost and schedule.
3. Re-run `agent.py` as many times as you like — each run registers a
   fresh agent (random suffix), so your dashboard stays tidy if you delete
   the test agents afterwards.

No code needed — constraints are policy, not code. That's the point.

### 4. Run the agent

```bash
python3 agent.py
```

You'll see it register itself, then attempt its three actions with a
verdict before each one. With an Approval Gate on, it pauses mid-run —
approve or reject the pending request in **Dashboard → Approvals**, then
press Enter in the terminal to continue.

### 5. What just happened

- **Agent registry** — the agent self-registered and now appears in your
  dashboard with its framework, owner and autonomy level.
- **Pre-execution constraint checks** — every action was checked against
  your policy *before* it ran, returning one of three verdicts:
  `allowed`, `blocked`, or `needs_approval`.
- **Human-in-the-loop approval** — the risky action waited for a human
  decision. Silence was never treated as consent.
- **Audit trail** — every action, verdict and decision is in your
  Activity Log, exportable as evidence for auditors or regulators.

## The framework variant

`langchain_agent.py` wraps the same governance loop around a LangChain
agent, showing how the control plane slots into a real framework workflow
(see `requirements-langchain.txt`).

## Repo contents

| File | What it is |
|---|---|
| `agent.py` | The demo agent — read it, it's ~150 heavily-commented lines |
| `langchain_agent.py` | The same loop, LangChain-flavoured |
| `constraints.sample.json` | The demo rule set to mirror in the dashboard |
| `.env.example` | Environment variable template |

## Troubleshooting

- **401 Unauthorized** — your API key is wrong, revoked, or not exported
  in this shell. Re-run `export FIRSTHELM_API_KEY=...`.
- **403 with an HTML error page** — some corporate networks and proxies
  block requests that identify as `Python-urllib`. The demo sets a proper
  `User-Agent` to avoid this; if you use another client, do the same.
- **400 "Agent name must be unique"** — agent names are unique per
  organisation. The demo appends a random suffix, but if you rename it,
  pick a fresh name on each run.
- **Invalid authorization header** — the header must read exactly
  `Authorization: Bearer <your key>`. In PowerShell, set environment
  variables with single quotes so nothing gets mangled.
- **Agent not visible in dashboard** — make sure you registered it against
  the same organisation as your dashboard login.

## Learn more

- Website: https://firsthelm.dev
- Docs: https://firsthelm.dev/docs
- API reference: https://firsthelm.dev/docs/api-reference
- What is an AI agent control plane? https://firsthelm.dev/guides/what-is-an-ai-agent-control-plane
- Governance glossary: https://firsthelm.dev/glossary

---

*FirstHelm Ltd (company number 17455295, registered in England and Wales).
Quickstart code is MIT-licensed — see [LICENSE](LICENSE).*
