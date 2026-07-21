![Sentinel.dev - Graphify-guided chaos testing](assets/sentinel-readme-banner.png)

# Sentinel.dev

**Code at AI speed. Test at human-AI speed.**

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://github.com/codespaces/new?repo=24f3003349%2FSentinel.dev)

Sentinel uses Graphify to map a local service, runs a bounded Docker chaos probe, and verifies a remediation against that same probe.

## What is real

- **Graphify code graph:** Sentinel maps the local source tree and calculates the affected dependency blast radius.
- **Real Docker execution:** Sentinel builds and runs the target FastAPI service inside an isolated container, then sends concurrent HTTP requests to the live service.
- **Runtime telemetry:** Sentinel records Docker CPU and memory telemetry and enforces resource limits and a hard timeout.
- **Verified remediation:** Sentinel creates a review branch, commits the patch, and reruns the same Docker probe before reporting `VERIFIED`.
- **Optional GitHub PR:** With `GITHUB_TOKEN` configured, Sentinel can push the review branch and open a GitHub pull request.

## Judge demo — no API key required

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), and Docker Desktop.

**Open Docker Desktop first and wait until it says it is running.** The Docker arena is required; Sentinel will not silently skip it.

```powershell
git clone https://github.com/24f3003349/Sentinel.dev.git
cd Sentinel.dev
uv sync --all-extras --frozen
uv run python run_sentinel_demo.py --mode deterministic
```

The deterministic rehearsal performs the complete, reproducible flow:

1. Local happy-path test passes.
2. Graphify maps the dependency graph and blast radius.
3. Docker exposes a production-shaped failure that the local test missed.
4. Sentinel shows a remediation diff on a review branch.
5. Docker reruns the identical probe and prints `VERIFIED`.

Each successful run leaves the repository on a generated fix branch. To start the vulnerable demonstration again:

```powershell
git checkout main
```

## Live model demo

Live mode uses the configured provider to select the Graphify-guided bounded probe and the approved remediation strategy. Sentinel executes its reviewed probe and remediation implementations inside Docker; it does not execute arbitrary model-authored code.

```powershell
$env:SENTINEL_LLM_PROVIDER = "google"
$env:GEMINI_API_KEY = "your_google_ai_studio_key"
$env:SENTINEL_LLM_MODEL = "gemini-3.5-flash"
uv run python run_sentinel_demo.py --mode live
```

**Google AI Studio offers a free tier for eligible Gemini API usage. Add your own key locally; no API key is stored in this repository.**

Google AI Studio, OpenAI Platform, and OpenRouter are supported. ChatGPT/Codex plan credits do not supply API access.

## Included targets

| Target | Failure exposed | Verified repair |
| --- | --- | --- |
| `race_condition` | Concurrent bookings oversell one SQLite ticket | Atomic conditional inventory update |
| `memory_leak` | Large export breaches the 256 MiB arena limit | Streaming response |
| `redos_attack` | Catastrophic regex stalls validation | Linear-time allow-list validation |

## Safety and dashboard

The throwaway `python:3.12-slim` arena has no host volume mounts or external network, a read-only root filesystem, 1 CPU, 256 MiB RAM, 64 PIDs, and a 10-second hard timeout.

After a run, inspect the Graphify graph, logs, telemetry, finding, and verification in the dashboard:

```powershell
cd dashboard
npm ci
npm run dev
```

Open `http://localhost:3000`.

## Where Codex Accelerated Our Workflow

- Built the Graphify mapping, Docker arena, remediation workflow, and dashboard.
- Hardened the demo against timeouts, malformed model responses, and unsafe patches.
- Added deterministic and live demonstration paths with verification logs and patch diffs.
- Created tests, judge documentation, Git history, and the GitHub delivery workflow.
