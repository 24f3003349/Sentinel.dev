from pathlib import Path

from sentinel.swarm_agents import decode_code, deterministic_chaos_plan, deterministic_patch


def test_every_target_has_a_bounded_offline_probe() -> None:
    root = Path(__file__).resolve().parents[1] / "dummy_targets"
    expected = {"race_condition": "RACE_INVARIANT_VIOLATION", "memory_leak": "MEMORY_PRESSURE_VIOLATION", "redos_attack": "REDOS_TIMEOUT_VIOLATION"}
    for name, marker in expected.items():
        plan = deterministic_chaos_plan(root / name, 5)
        assert marker in decode_code(plan.attack_code_b64)


def test_every_target_has_a_main_patch() -> None:
    root = Path(__file__).resolve().parents[1] / "dummy_targets"
    for target in root.iterdir():
        assert "FastAPI" in decode_code(deterministic_patch(target).patched_source_b64)
