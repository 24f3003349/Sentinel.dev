![Sentinel.dev - Graphify-guided chaos testing](assets/sentinel-readme-banner.png)

# Sentinel.dev

**Graphify-guided chaos testing that finds a production-shaped failure, asks a live model for a repair, and proves the repair in Docker.**

## What the demo proves

1. The target's ordinary **local happy-path tests pass**.
2. **Graphify maps the target** and identifies the blast radius.
3. In live mode, the model selects a bounded probe from the Graphify context; Docker runs Sentinel's reviewed implementation of that production-shaped HTTP attack.
4. Sentinel creates a review branch, applies a remediation, then **reruns the identical probe**.

In `--mode live`, the configured model makes the Graphify-guided probe selection and drafts the remediation. Sentinel never executes model-authored arbitrary attack code: Docker receives a reviewed, target-bounded probe. In `--mode deterministic`, Sentinel uses the same Docker, Graphify, Git, and verification path with fixed safe fixtures—useful for rehearsing without API credentials.

Live output ends only when it can show:

```text
[PROBE] execution plan: google:gemini-3.5-flash
[MODEL] ... drafting remediation
VERIFIED
```

## Run the live demo

Requirements: Docker Desktop, Python 3.12+, [uv](https://docs.astral.sh/uv/), and live API access. Google AI Studio, OpenAI Platform, and OpenRouter are supported. ChatGPT/Codex plan credits do not power API calls.

**Before running either demo, open Docker Desktop and wait until its status says it is running.** Sentinel intentionally requires Docker for its isolated HTTP arena; it will not silently skip this proof.

## One-command judge rehearsal

```powershell
git clone https://github.com/24f3003349/Sentinel.dev.git
cd Sentinel.dev
uv sync --all-extras --frozen
# Open Docker Desktop and wait until it is running.
uv run python run_sentinel_demo.py --mode deterministic
```

This requires no API key and demonstrates the complete Graphify → Docker finding → patch diff → Docker verification path.

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

Each successful run leaves you on a generated `sentinel/fix-...` branch so the verified remediation is inspectable. Before running the failure demonstration again, reset only the checked-out branch—not files—with:

```powershell
git checkout main
```

Both modes visibly run `LOCAL TESTS PASS -> Graphify map -> chaos finding -> patch -> VERIFIED`. `deterministic-demo` means no model call. A provider/model label such as `google:gemini-3.5-flash` means a live model call.

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
