# Sentinel.dev

Sentinel is a local, AST-aware chaos-testing gate for the failure class ordinary AI-generated happy-path tests miss: code that works for one request but fails under concurrent production pressure. It maps a scoped code graph, creates a bounded invariant probe, runs it inside a constrained Docker arena when Docker is available, captures execution telemetry, and creates a reviewable remediation commit on a new Git branch.

The included `dummy_target` makes the story reproducible. Its unit test passes, while the concurrent reservation probe detects overselling a one-ticket inventory.

## One-click Judge Sandbox

Prerequisites: Python 3.12+ and `pip`. The setup installs **Graphify** (`graphifyy`) as a required local dependency and Sentinel invokes Graphify's upstream extractor on every run, consuming only `dummy_target/graphify-out/graph.json`. Docker Desktop and an OpenAI API key are optional: the demo has a deterministic offline model mode, but it does not substitute Graphify or require Neo4j.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python run_sentinel_demo.py
```

Or, where `make` is installed: `make run-demo`.

The command invokes `python -m graphify extract dummy_target --force --code-only --no-cluster`, maps the target through Graphify, runs the race probe with a **10-second hard timeout**, records a report under `reports/latest.json`, and—after finding the flaw—creates `sentinel/fix-race-condition` with a real local Git commit. It never writes the patch to `main`.

Run the intended contrast manually:

```powershell
python -m pytest dummy_target/tests/test_main.py  # passes: one happy-path customer
python -m sentinel.cli attack dummy_target --no-patch  # fails: concurrent oversell
```

Use `python -m sentinel.cli doctor` to see which optional integrations are active. Set `OPENAI_API_KEY` and `SENTINEL_OPENAI_MODEL=gpt-5.6-sol` to use the OpenAI Responses SDK structured-output path; the executable attack payload is base64 inside the schema so JSON quoting cannot damage it. GPT-5.6 Sol supports structured outputs in the Responses API ([model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol)).

## Architecture and safeguards

| Layer | Implementation |
| --- | --- |
| Context | Required upstream Graphify (`graphifyy`) extractor; Sentinel normalizes its NetworkX node-link `graphify-out/graph.json`. No Neo4j service is required. |
| Chaos | Official OpenAI Python SDK with Pydantic structured parsing; deterministic bounded fallback without a key. |
| Arena | A throwaway `python:3.12-slim` image built from a temporary Dockerfile—**no host volume mounts**—with FastAPI, Uvicorn, Requests, Aiohttp, and Pytest installed. Runtime has no network, a read-only filesystem, 256 MB memory, one CPU, 64 PIDs, and a force-kill at 10 seconds. |
| Healing | A Pydantic patch plan applied only after a failing signal; GitPython makes a new branch and commit. |

Only the intentionally included local `dummy_target` is supported by the one-click demo. A production integration must add repository allow-listing, human approval, secret redaction, image provenance, and a per-organization sandbox policy before allowing arbitrary repositories or model output.

## Dashboard prototype

The `dashboard/` folder contains a lightweight Next.js SOC “War Room”: a DEFCON slider, scoped blast-radius diagram, and live-log presentation. Run `cd dashboard; npm install; npm run dev` to view it locally. A deployment (Vercel frontend plus a Docker-capable Fly.io or Modal backend) should set `OPENAI_API_KEY` only on the backend and expose a job API; do not place that key in the frontend.

## GitHub / CI usage

`.github/workflows/sentinel.yml` runs the test suite and a detection-only chaos gate on pull requests. In CI, a found invariant violation intentionally fails the check—this is the signal a Codex PR workflow can receive. The local demo makes a branch commit. When the repository has a GitHub `origin` and `GITHUB_TOKEN` is set, Sentinel pushes the review branch and uses the GitHub API to create a real pull request; no token is embedded or assumed.

## Where Codex Accelerated Our Workflow

Codex accelerated the repeatable engineering work: the constrained Docker harness, timeout/telemetry plumbing, Graphify-compatible adapter, Pydantic contracts, and Git branch workflow. That replaces more than 20 hours of integration boilerplate, while the core product judgment remains explicit: Sentinel tests survivability rather than simply generating another happy-path test.

## Scope and roadmap

The MVP demonstrates a concurrency invariant in a local Python service. Enterprise mode would move the graph index behind webhooks, use short-lived isolated runners, add policy-enforced repository scopes, and open a GitHub PR only after an approved CI result. This keeps the product’s meaningful distinction: static maps identify risk; Sentinel executes bounded evidence and proposes a reviewable fix.
