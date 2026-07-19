"""One-click Sentinel demonstration that requires live GPT-5.6 Sol."""
import os

from sentinel.cli import run_demo


if __name__ == "__main__":
    # The hackathon entry point must demonstrate the real model. The offline
    # deterministic path remains available only for local engineering checks.
    if os.getenv("SENTINEL_OFFLINE_DEMO", "").lower() not in {"1", "true", "yes"}:
        os.environ["SENTINEL_REQUIRE_LIVE_AI"] = "1"
    raise SystemExit(run_demo())
