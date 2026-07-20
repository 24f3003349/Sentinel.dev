"""One-click Sentinel demo with explicit live and deterministic modes."""
import argparse

from sentinel.cli import run_demo


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Sentinel.dev production-failure demo.")
    parser.add_argument("--mode", choices=("live", "deterministic"), default="live", help="live calls GPT-5.6; deterministic is a no-key local rehearsal.")
    raise SystemExit(run_demo(parser.parse_args().mode))
