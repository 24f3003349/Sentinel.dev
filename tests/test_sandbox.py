from pathlib import Path

from sentinel.sandbox import run_attack
from sentinel.schemas import RunStatus
from sentinel.swarm_agents import decode_code, deterministic_chaos_plan


def test_local_arena_detects_oversell() -> None:
    target = Path(__file__).resolve().parents[1] / "dummy_target"
    result = run_attack(target, decode_code(deterministic_chaos_plan(2).attack_code_b64), prefer_docker=False)
    assert result.status == RunStatus.failed
    assert result.failure_kind == "race-condition"
