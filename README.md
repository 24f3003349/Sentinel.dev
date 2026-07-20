![Sentinel.dev — Graphify-guided chaos testing](assets/sentinel-readme-banner.png)

# Sentinel.dev

**Graphify-guided chaos testing that finds a production-shaped failure, asks GPT‑5.6 Sol for a repair, and proves the repair in Docker.**

## What the demo proves

1. **Graphify maps the target** and identifies the blast radius.
2. **GPT‑5.6 Sol generates** a bounded localhost attack and a `main.py` remediation.
3. **Docker runs the real HTTP attack** against an intentionally vulnerable FastAPI target.
4. Sentinel creates a review branch, applies the patch, then **reruns the identical probe**.

The terminal ends only when it can show both:

```text
[AGENT] chaos plan: openrouter:openai/gpt-5.6-sol
[AGENT] remediation: openrouter:openai/gpt-5.6-sol
VERIFIED
```

Direct OpenAI runs show `openai:gpt-5.6-sol` instead.

## Run the live demo

Requirements: Docker Desktop, Python 3.12+, [uv](https://docs.astral.sh/uv/), and live API access. Use either OpenAI Platform or OpenRouter. ChatGPT/Codex plan credits do not power API calls.

```powershell
cd Sentinel.dev
uv sync --all-extras --frozen
$env:SENTINEL_LLM_PROVIDER = "openrouter"
$env:OPENROUTER_API_KEY = "your_openrouter_api_key"
$env:SENTINEL_LLM_MODEL = "openai/gpt-5.6-sol"
uv run python run_sentinel_demo.py
```

For direct OpenAI Platform access, set `SENTINEL_LLM_PROVIDER=openai`, `OPENAI_API_KEY`, and optionally `SENTINEL_LLM_MODEL=gpt-5.6-sol`. `run_sentinel_demo.py` requires live GPT‑5.6 Sol. It fails clearly if API access is missing; it never presents a deterministic fallback as an AI result.

## Included targets

| Target | Failure Sentinel exposes | Verified repair |
| --- | --- | --- |
| `race_condition` | Concurrent bookings oversell one SQLite ticket | Atomic conditional inventory update |
| `memory_leak` | A large export breaches the 256 MiB arena policy | Streaming response |
| `redos_attack` | Catastrophic regex input stalls validation | Linear-time allow-list validation |

Run a detection-only CI gate with:

```powershell
uv run python -m sentinel.cli attack dummy_targets/race_condition --no-patch
```

An intentional finding exits with code `1`, so it can fail CI.

## Safety and observability

The arena uses a throwaway `python:3.12-slim` image: no host volume mounts, no external network, read-only root filesystem, in-memory `/tmp`, 1 CPU, 256 MiB RAM, 64 PIDs, and a 10-second hard timeout. Reports stay local in `reports/latest.json`.

## Dashboard

```powershell
cd dashboard
npm ci
npm run dev
```

Open `http://localhost:3000` after a Sentinel run to inspect the Graphify blast-radius graph, Docker telemetry, terminal logs, finding, and verification result.

## Where Codex Accelerated Our Workflow

Codex accelerated the Graphify orchestration, hardened Docker arena, structured GPT‑5.6 contracts, report-driven dashboard, and repeatable verification workflow.
