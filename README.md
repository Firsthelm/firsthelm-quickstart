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

You'll watch three actions happen:

1. `draft_message` — a harmless action that runs immediately (allowed).
2. `send_email` — a consequential action that **pauses mid-flight** and waits
   for your approval in the FirstHelm dashboard.
3. `delete_old_records` — a dangerous action that gets **blocked** by the
   constraint you'll create, and never executes.

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
export FIRSTHELM_API_KEY="fhk_your_api_key_here"
```

### 3. Create the demo constraints in the dashboard

In the FirstHelm dashboard:

1. Open **Constraints** and create a constraint for the agent you're about
   to register, or apply the sample rule set from `constraints.sample.json`.
2. The effect we want: `delete_*` actions are blocked outright, `send_*`
   actions require human approval, everything else is allowed.

No code needed — constraints are policy, not code. That's the point.

### 4. Run the agent

```bash
python3 agent.py
```

You'll see it register itself, attempt its three actions, and pause on the
email. Follow the console output to the dashboard, approve (or reject) the
pending request, and watch the agent continue — or stop — accordingly.

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
