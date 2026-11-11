"""
Manual verification script for qflowpilot.core.models.

Run from the project root:
    py verify_models.py

Prints a pass/fail line for every model and every validation branch.
Exits with code 0 if all cases pass, 1 otherwise.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from qflowpilot.core.models import (
    CircuitProfile,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    QualityEstimate,
    RuntimeAction,
    RuntimeDecision,
    WorkloadSpec,
    WorkloadType,
)


# ---------------------------------------------------------
# Tiny test harness
# ---------------------------------------------------------

_passed = 0
_failed = 0
_failures: list[str] = []


def _report(name: str, ok: bool, detail: str = "") -> None:
    global _passed, _failed
    if ok:
        _passed += 1
        print(f"  ✓ {name}")
    else:
        _failed += 1
        line = f"  ✗ {name}"
        if detail:
            line += f"  [{detail}]"
        print(line)
        _failures.append(name)


def section(title: str) -> None:
    print(f"\n== {title} ==")


def expect_ok(name: str, fn) -> None:
    """Call fn(); pass if no exception."""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        _report(name, False, f"unexpected {type(exc).__name__}: {exc}")
    else:
        _report(name, True)


def expect_raises(name: str, exc_type: type[BaseException], fn) -> None:
    """Call fn(); pass only if it raises exc_type."""
    try:
        fn()
    except exc_type:
        _report(name, True)
    except Exception as exc:  # noqa: BLE001
        _report(
            name,
            False,
            f"raised {type(exc).__name__} instead of {exc_type.__name__}",
        )
    else:
        _report(name, False, f"did not raise {exc_type.__name__}")


# ---------------------------------------------------------
# WorkloadSpec
# ---------------------------------------------------------

section("WorkloadSpec")


def workload_valid():
    w = WorkloadSpec(
        workload_id="qaoa_001",
        name="Max-Cut",
        workload_type=WorkloadType.ITERATIVE,
        algorithm="QAOA",
        application="Graph optimization",
    )
    assert w.workload_id == "qaoa_001"
    assert w.algorithm == "QAOA"
    assert w.metadata == {}


expect_ok("valid construction", workload_valid)
expect_raises(
    "empty workload_id -> ValueError",
    ValueError,
    lambda: WorkloadSpec(
        workload_id="",
        name="Max-Cut",
        workload_type=WorkloadType.ITERATIVE,
        algorithm="QAOA",
    ),
)
expect_raises(
    "empty name -> ValueError",
    ValueError,
    lambda: WorkloadSpec(
        workload_id="w1",
        name="",
        workload_type=WorkloadType.ITERATIVE,
        algorithm="QAOA",
    ),
)
expect_raises(
    "empty algorithm -> ValueError",
    ValueError,
    lambda: WorkloadSpec(
        workload_id="w1",
        name="Max-Cut",
        workload_type=WorkloadType.ITERATIVE,
        algorithm="",
    ),
)
expect_raises(
    "wrong workload_type -> TypeError",
    TypeError,
    lambda: WorkloadSpec(
        workload_id="w1",
        name="Max-Cut",
        workload_type="iterative",  # type: ignore[arg-type]
        algorithm="QAOA",
    ),
)


# ---------------------------------------------------------
# CircuitProfile
# ---------------------------------------------------------

section("CircuitProfile")


def circuit_valid():
    p = CircuitProfile(
        num_qubits=5,
        depth=20,
        total_gates=45,
        two_qubit_gates=12,
        gate_counts={"h": 5, "cx": 12, "rz": 28},
    )
    assert p.num_qubits == 5
    assert p.two_qubit_gates == 12


expect_ok("valid construction", circuit_valid)
expect_raises(
    "num_qubits=0 -> ValueError",
    ValueError,
    lambda: CircuitProfile(
        num_qubits=0, depth=20, total_gates=45, two_qubit_gates=12
    ),
)
expect_raises(
    "negative depth -> ValueError",
    ValueError,
    lambda: CircuitProfile(
        num_qubits=5, depth=-1, total_gates=45, two_qubit_gates=12
    ),
)
expect_raises(
    "negative total_gates -> ValueError",
    ValueError,
    lambda: CircuitProfile(
        num_qubits=5, depth=20, total_gates=-1, two_qubit_gates=0
    ),
)
expect_raises(
    "two_qubit_gates > total_gates -> ValueError",
    ValueError,
    lambda: CircuitProfile(
        num_qubits=5, depth=20, total_gates=10, two_qubit_gates=11
    ),
)
expect_raises(
    "negative gate count -> ValueError",
    ValueError,
    lambda: CircuitProfile(
        num_qubits=5,
        depth=20,
        total_gates=10,
        two_qubit_gates=2,
        gate_counts={"h": -1},
    ),
)
expect_raises(
    "negative estimated_execution_time_s -> ValueError",
    ValueError,
    lambda: CircuitProfile(
        num_qubits=5,
        depth=20,
        total_gates=10,
        two_qubit_gates=2,
        estimated_execution_time_s=-0.1,
    ),
)


# ---------------------------------------------------------
# ExecutionRequest
# ---------------------------------------------------------

section("ExecutionRequest")


def request_valid():
    r = ExecutionRequest(
        request_id="request_001",
        workload_id="qaoa_001",
        shots=1024,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
        backend_name="aer_simulator",
        seed=42,
    )
    assert r.shots == 1024
    assert r.seed == 42


expect_ok("valid construction", request_valid)
expect_raises(
    "shots=0 -> ValueError",
    ValueError,
    lambda: ExecutionRequest(
        request_id="r1",
        workload_id="w1",
        shots=0,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
    ),
)
expect_raises(
    "empty request_id -> ValueError",
    ValueError,
    lambda: ExecutionRequest(
        request_id="",
        workload_id="w1",
        shots=10,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
    ),
)
expect_raises(
    "empty workload_id -> ValueError",
    ValueError,
    lambda: ExecutionRequest(
        request_id="r1",
        workload_id="",
        shots=10,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
    ),
)
expect_raises(
    "wrong execution_mode -> TypeError",
    TypeError,
    lambda: ExecutionRequest(
        request_id="r1",
        workload_id="w1",
        shots=10,
        execution_mode="ideal_simulator",  # type: ignore[arg-type]
    ),
)
expect_raises(
    "negative seed -> ValueError",
    ValueError,
    lambda: ExecutionRequest(
        request_id="r1",
        workload_id="w1",
        shots=10,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
        seed=-1,
    ),
)
expect_raises(
    "timeout_s=0 -> ValueError",
    ValueError,
    lambda: ExecutionRequest(
        request_id="r1",
        workload_id="w1",
        shots=10,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
        timeout_s=0,
    ),
)


# ---------------------------------------------------------
# ExecutionResult
# ---------------------------------------------------------

section("ExecutionResult")


def result_valid():
    r = ExecutionResult(
        result_id="result_001",
        request_id="request_001",
        status=ExecutionStatus.COMPLETED,
        counts={"000": 500, "111": 524},
        shots=1024,
    )
    assert r.status == ExecutionStatus.COMPLETED
    assert sum(r.counts.values()) == 1024


def result_execution_time():
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    r = ExecutionResult(
        result_id="r",
        request_id="q",
        status=ExecutionStatus.COMPLETED,
        started_at=t0,
        completed_at=t0 + timedelta(seconds=2.5),
    )
    assert r.execution_time_s == 2.5


def result_execution_time_missing():
    r = ExecutionResult(
        result_id="r",
        request_id="q",
        status=ExecutionStatus.PENDING,
    )
    assert r.execution_time_s is None


expect_ok("valid construction", result_valid)
expect_ok("execution_time_s with both timestamps", result_execution_time)
expect_ok("execution_time_s returns None without timestamps", result_execution_time_missing)
expect_raises(
    "empty result_id -> ValueError",
    ValueError,
    lambda: ExecutionResult(
        result_id="",
        request_id="q",
        status=ExecutionStatus.COMPLETED,
    ),
)
expect_raises(
    "empty request_id -> ValueError",
    ValueError,
    lambda: ExecutionResult(
        result_id="r",
        request_id="",
        status=ExecutionStatus.COMPLETED,
    ),
)
expect_raises(
    "wrong status -> TypeError",
    TypeError,
    lambda: ExecutionResult(
        result_id="r",
        request_id="q",
        status="completed",  # type: ignore[arg-type]
    ),
)
expect_raises(
    "shots=0 -> ValueError",
    ValueError,
    lambda: ExecutionResult(
        result_id="r",
        request_id="q",
        status=ExecutionStatus.COMPLETED,
        shots=0,
    ),
)
expect_raises(
    "wrong execution_mode -> TypeError",
    TypeError,
    lambda: ExecutionResult(
        result_id="r",
        request_id="q",
        status=ExecutionStatus.COMPLETED,
        execution_mode="ideal",  # type: ignore[arg-type]
    ),
)
expect_raises(
    "negative measurement count -> ValueError",
    ValueError,
    lambda: ExecutionResult(
        result_id="r",
        request_id="q",
        status=ExecutionStatus.COMPLETED,
        counts={"000": -1},
    ),
)
expect_raises(
    "non-int measurement count -> TypeError",
    TypeError,
    lambda: ExecutionResult(
        result_id="r",
        request_id="q",
        status=ExecutionStatus.COMPLETED,
        counts={"000": 1.5},  # type: ignore[dict-item]
    ),
)
expect_raises(
    "bool measurement count -> TypeError",
    TypeError,
    lambda: ExecutionResult(
        result_id="r",
        request_id="q",
        status=ExecutionStatus.COMPLETED,
        counts={"000": True},  # type: ignore[dict-item]
    ),
)
expect_raises(
    "naive timestamp -> ValueError",
    ValueError,
    lambda: ExecutionResult(
        result_id="r",
        request_id="q",
        status=ExecutionStatus.COMPLETED,
        submitted_at=datetime(2026, 1, 1),
    ),
)
expect_raises(
    "started_at before submitted_at -> ValueError",
    ValueError,
    lambda: ExecutionResult(
        result_id="r",
        request_id="q",
        status=ExecutionStatus.COMPLETED,
        submitted_at=datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
        started_at=datetime(2026, 1, 1, 11, tzinfo=timezone.utc),
    ),
)
expect_raises(
    "completed_at before started_at -> ValueError",
    ValueError,
    lambda: ExecutionResult(
        result_id="r",
        request_id="q",
        status=ExecutionStatus.COMPLETED,
        started_at=datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, 11, tzinfo=timezone.utc),
    ),
)


# ---------------------------------------------------------
# QualityEstimate
# ---------------------------------------------------------

section("QualityEstimate")


def quality_valid():
    q = QualityEstimate(
        sample_count=1024,
        expectation_value=-0.75,
        variance=0.12,
        standard_error=0.0108,
        confidence_interval=(-0.77, -0.73),
        success_probability=0.82,
        application_score=0.90,
        quality_satisfied=True,
    )
    assert q.sample_count == 1024
    assert q.quality_satisfied is True


def quality_empty_ok():
    q = QualityEstimate()
    assert q.sample_count is None


expect_ok("valid construction", quality_valid)
expect_ok("empty construction (all defaults)", quality_empty_ok)
expect_raises(
    "sample_count=0 -> ValueError",
    ValueError,
    lambda: QualityEstimate(sample_count=0),
)
expect_raises(
    "negative variance -> ValueError",
    ValueError,
    lambda: QualityEstimate(variance=-0.1),
)
expect_raises(
    "negative standard_error -> ValueError",
    ValueError,
    lambda: QualityEstimate(standard_error=-0.1),
)
expect_raises(
    "CI lower > upper -> ValueError",
    ValueError,
    lambda: QualityEstimate(confidence_interval=(-0.5, -0.7)),
)
expect_raises(
    "success_probability=1.5 -> ValueError",
    ValueError,
    lambda: QualityEstimate(success_probability=1.5),
)
expect_raises(
    "success_probability=-0.1 -> ValueError",
    ValueError,
    lambda: QualityEstimate(success_probability=-0.1),
)


# ---------------------------------------------------------
# RuntimeDecision
# ---------------------------------------------------------

section("RuntimeDecision")


def decision_valid():
    d = RuntimeDecision(
        action=RuntimeAction.ALLOCATE_MORE_SHOTS,
        reason="The estimated quality does not meet the target.",
        additional_shots=2048,
    )
    assert d.additional_shots == 2048


def decision_accept_ok():
    d = RuntimeDecision(
        action=RuntimeAction.ACCEPT_RESULT,
        reason="Quality target met.",
    )
    assert d.additional_shots is None


expect_ok("valid ALLOCATE_MORE_SHOTS", decision_valid)
expect_ok("valid ACCEPT_RESULT (no extra shots required)", decision_accept_ok)
expect_raises(
    "ALLOCATE_MORE_SHOTS without additional_shots -> ValueError",
    ValueError,
    lambda: RuntimeDecision(
        action=RuntimeAction.ALLOCATE_MORE_SHOTS,
        reason="Additional measurements are required.",
    ),
)
expect_raises(
    "wrong action type -> TypeError",
    TypeError,
    lambda: RuntimeDecision(
        action="allocate_more_shots",  # type: ignore[arg-type]
        reason="x",
    ),
)
expect_raises(
    "empty reason -> ValueError",
    ValueError,
    lambda: RuntimeDecision(
        action=RuntimeAction.ACCEPT_RESULT,
        reason="   ",
    ),
)
expect_raises(
    "additional_shots=0 -> ValueError",
    ValueError,
    lambda: RuntimeDecision(
        action=RuntimeAction.ALLOCATE_MORE_SHOTS,
        reason="x",
        additional_shots=0,
    ),
)


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

print("\n" + "=" * 50)
total = _passed + _failed
print(f"  {_passed}/{total} passed, {_failed} failed")
if _failed:
    print("\n  Failures:")
    for name in _failures:
        print(f"    - {name}")
    sys.exit(1)
print("  All checks passed.")