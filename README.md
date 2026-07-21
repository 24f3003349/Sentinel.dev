![Sentinel.dev - Graphify-guided chaos testing](assets/sentinel-readme-banner.png)

# Sentinel.dev

**Graphify-guided chaos testing that finds a production-shaped failure, asks GPT-5.6 Sol for a repair, and proves the repair in Docker.**

## What the demo proves

1. The target's ordinary **local happy-path tests pass**.
2. **Graphify maps the target** and identifies the blast radius.
3. Docker runs a production-shaped concurrent HTTP attack that exposes what the local test missed.
4. Sentinel creates a review branch, applies a remediation, then **reruns the identical probe**.

In `--mode live`, GPT-5.6 Sol generates the attack and remediation. In `--mode deterministic`, Sentinel uses the same Docker, Graphify, Git, and verification path with fixed safe fixtures - useful for rehearsing without API credentials.

Live output ends only when it can show:

```text
[AGENT] chaos plan: openrouter:openai/gpt-5.6-sol
[AGENT] remediation: openrouter:openai/gpt-5.6-sol
VERIFIED
```

Direct OpenAI runs show `openai:gpt-5.6-sol` instead.

## Run the live demo

Requirements: Docker Desktop, Python 3.12+, [uv](https://docs.astral.sh/uv/), and live API access. Google AI Studio, OpenAI Platform, and OpenRouter are supported. ChatGPT/Codex plan credits do not power API calls.

```powershell
cd Sentinel.dev
uv sync --all-extras --frozen
$env:SENTINEL_LLM_PROVIDER = "google"
$env:GEMINI_API_KEY = "your_google_ai_studio_key"
$env:SENTINEL_LLM_MODEL = "gemini-3.5-flash"
uv run python run_sentinel_demo.py --mode live
```

For direct OpenAI Platform access, set `SENTINEL_LLM_PROVIDER=openai`, `OPENAI_API_KEY`, and optionally `SENTINEL_LLM_MODEL=gpt-5.6-sol`. OpenRouter remains available with `SENTINEL_LLM_PROVIDER=openrouter` and `OPENROUTER_API_KEY`. Live mode fails clearly if API access is missing; it never presents a deterministic result as an AI result.

## Rehearse without API access

```powershell
uv run python run_sentinel_demo.py --mode deterministic
```

Both modes visibly run `LOCAL TESTS PASS -> Graphify map -> chaos finding -> patch -> VERIFIED`. The agent label tells the truth: `deterministic-demo` means no LLM call; `openrouter:openai/gpt-5.6-sol` or `openai:gpt-5.6-sol` means a live model call.

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

Codex accelerated the Graphify orchestration, hardened Docker arena, structured GPT-5.6 contracts, report-driven dashboard, and repeatable verification workflow.
