# Sentinel.dev

Sentinel.dev is a Graphify-guided chaos-testing gate for AI-assisted software delivery. It proves that ordinary happy-path tests can pass while a production-shaped HTTP attack exposes a concurrency, memory, or CPU failure; it then creates a review branch, patches the target, and reruns the same probe to verify the repair.

## Included production-shaped targets

| Target | Happy-path test | Sentinel proof | Remediation |
| --- | --- | --- | --- |
| `race_condition` | one ticket checkout succeeds | concurrent HTTP requests oversell SQLite inventory | async booking lock |
| `memory_leak` | 1 MiB export succeeds | 384 MiB export crosses the 256 MiB arena policy | streaming response |
| `redos_attack` | ordinary input validates | catastrophic regex payload stalls the service | linear-time allow-list validation |

## One-click judge sandbox

Requirements: Docker Desktop, Python 3.12+, and [uv](https://docs.astral.sh/uv/). Graphify is required and installed as a project dependency. OpenAI is optional for the deterministic demo; with `OPENAI_API_KEY`, GPT-5.6 Sol produces structured, Base64-encoded probes and patches.

```powershell
uv sync --all-extras
uv run python run_sentinel_demo.py
```

The one-click demo maps the target with Graphify, builds an isolated Docker image without host volume mounts, sends a concurrent HTTP attack to the FastAPI service, captures CPU/RAM telemetry, creates a Git branch and commit, and verifies that the patched branch survives the identical attack.

Run every baseline test:

```powershell
uv run pytest
```

Run a detection-only CI gate; a vulnerability intentionally returns exit code `1`:

```powershell
uv run python -m sentinel.cli attack dummy_targets/race_condition --no-patch
uv run python -m sentinel.cli attack dummy_targets/memory_leak --no-patch
uv run python -m sentinel.cli attack dummy_targets/redos_attack --no-patch
```

## Safety model

Every arena is a throwaway `python:3.12-slim` image built from a temporary context. It has no host volume mount, no network, a read-only root filesystem, a writable in-memory `/tmp`, one CPU, 256 MiB memory, 64 PIDs, no-new-privileges, and a 10-second hard execution deadline. Docker telemetry is evaluated against memory and sustained-CPU policies; attack scripts only address `127.0.0.1` inside the container.

## Graphify and AI workflow

Graphify is the required structural map. Sentinel invokes `graphify extract --code-only --no-cluster` and passes the resulting scoped node-link graph plus the target source to the agent. The OpenAI path uses Responses structured parsing, Pydantic models, Base64 code transport, 120-second client timeouts, and three exponential-backoff attempts. If no key is configured, target-specific deterministic probes preserve a fully repeatable judge demo.

## Git and GitHub lifecycle

Sentinel never overwrites `main`. It refuses a dirty tracked workspace, creates a unique `sentinel/fix-*` branch, commits the patch, and reruns verification. With a GitHub `origin` and `GITHUB_TOKEN`, it pushes that branch and uses the GitHub API to create an actual PR. No token is stored in the repository.

## Dashboard

```powershell
cd dashboard
npm ci
npm run dev
```

The Next.js War Room polls `/api/report`, which reads `reports/latest.json` locally (or `SENTINEL_REPORT_PATH`). It renders Graphify nodes through React Flow, records Docker telemetry, and streams arena output through xterm.

## Where Codex Accelerated Our Workflow

Codex accelerated the repeatable systems work: Graphify orchestration, container hardening, test-target scaffolding, structured agent contracts, branch/PR automation, and the report-driven dashboard. The product decision remains deliberate: Sentinel validates survivability rather than generating another happy-path test.
