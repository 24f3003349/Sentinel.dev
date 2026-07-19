from sentinel.sandbox import IMAGE_MEMORY_BYTES, _failure_from_logs
from sentinel.schemas import TelemetrySample


def test_marker_classification() -> None:
    failure, violations = _failure_from_logs("RACE_INVARIANT_VIOLATION", [])
    assert failure == "race-condition"
    assert violations == []


def test_memory_policy_classification() -> None:
    failure, violations = _failure_from_logs("", [TelemetrySample(elapsed_seconds=1, memory_bytes=int(IMAGE_MEMORY_BYTES * 0.81))], "memory_leak")
    assert failure == "resource-exhaustion"
    assert violations
