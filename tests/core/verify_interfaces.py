"""
Manual verification script for qflowpilot.core.interfaces.

Run from the project root:
    py verify_interfaces.py

Prints a pass/fail line per case; exits non-zero on any failure.
"""

from __future__ import annotations

import sys

from qflowpilot.core.interfaces import (
    PolicyInterface,
    ProfilerInterface,
    QuantumBackendInterface,
    ValidatorInterface,
    WorkloadInterface,
)
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
# Harness
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
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        _report(name, False, f"unexpected {type(exc).__name__}: {exc}")
    else:
        _report(name, True)


def expect_raises(name: str, exc_type: type, fn, match: str | None = None) -> None:
    try:
        fn()
    except exc_type as exc:
        if match is not None and match not in str(exc):
            _report(name, False, f"message missing {match!r}: {exc}")
        else:
            _report(name, True)
    except Exception as exc:  # noqa: BLE001
        _report(name, False, f"raised {type(exc).__name__} instead of {exc_type.__name__}")
    else:
        _report(name, False, f"did not raise {exc_type.__name__}")


# ---------------------------------------------------------
# 1. Each interface refuses direct instantiation
# ---------------------------------------------------------

section("Abstract base classes")

for iface in (
    QuantumBackendInterface,
    WorkloadInterface,
    ProfilerInterface,
    PolicyInterface,
    ValidatorInterface,
):
    expect_raises(f"{iface.__name__}() -> TypeError", TypeError, iface)


# ---------------------------------------------------------
# 2. Every abstract method is individually enforced
# ---------------------------------------------------------

section("Each abstract method is enforced")


class _BackendFull(QuantumBackendInterface):
    def execute(self, request, circuit): ...
    def is_available(self): return True
    def get_backend_info(self): return {}


class _BackendMissingExecute(QuantumBackendInterface):
    def is_available(self): return True
    def get_backend_info(self): return {}


class _BackendMissingIsAvailable(QuantumBackendInterface):
    def execute(self, request, circuit): ...
    def get_backend_info(self): return {}


class _BackendMissingInfo(QuantumBackendInterface):
    def execute(self, request, circuit): ...
    def is_available(self): return True


class _WorkloadFull(WorkloadInterface):
    def get_spec(self): ...
    def build_circuit(self): ...
    def evaluate_result(self, result): ...


class _WorkloadMissingSpec(WorkloadInterface):
    def build_circuit(self): ...
    def evaluate_result(self, result): ...


class _WorkloadMissingCircuit(WorkloadInterface):
    def get_spec(self): ...
    def evaluate_result(self, result): ...


class _WorkloadMissingEval(WorkloadInterface):
    def get_spec(self): ...
    def build_circuit(self): ...


class _ProfilerFull(ProfilerInterface):
    def profile_circuit(self, circuit): ...
    def estimate_quality(self, result, workload): ...


class _ProfilerMissingProfile(ProfilerInterface):
    def estimate_quality(self, result, workload): ...


class _ProfilerMissingEstimate(ProfilerInterface):
    def profile_circuit(self, circuit): ...


class _PolicyFull(PolicyInterface):
    def decide(self, workload, profile, quality, current_shots): ...


class _PolicyMissing(QuantumBackendInterface):  # negative control
    pass


class _ValidatorFull(ValidatorInterface):
    def validate_execution(self, result, request): ...
    def validate_quality(self, quality, workload): ...


class _ValidatorMissingExec(ValidatorInterface):
    def validate_quality(self, quality, workload): ...


class _ValidatorMissingQuality(ValidatorInterface):
    def validate_execution(self, result, request): ...


# Full implementations must instantiate cleanly
expect_ok("QuantumBackendInterface full impl instantiates", _BackendFull)
expect_ok("WorkloadInterface full impl instantiates", _WorkloadFull)
expect_ok("ProfilerInterface full impl instantiates", _ProfilerFull)
expect_ok("PolicyInterface full impl instantiates", _PolicyFull)
expect_ok("ValidatorInterface full impl instantiates", _ValidatorFull)

# Omitting any single abstract method must block instantiation
expect_raises("Backend without execute -> TypeError", TypeError, _BackendMissingExecute, match="execute")
expect_raises("Backend without is_available -> TypeError", TypeError, _BackendMissingIsAvailable, match="is_available")
expect_raises("Backend without get_backend_info -> TypeError", TypeError, _BackendMissingInfo, match="get_backend_info")

expect_raises("Workload without get_spec -> TypeError", TypeError, _WorkloadMissingSpec, match="get_spec")
expect_raises("Workload without build_circuit -> TypeError", TypeError, _WorkloadMissingCircuit, match="build_circuit")
expect_raises("Workload without evaluate_result -> TypeError", TypeError, _WorkloadMissingEval, match="evaluate_result")

expect_raises("Profiler without profile_circuit -> TypeError", TypeError, _ProfilerMissingProfile, match="profile_circuit")
expect_raises("Profiler without estimate_quality -> TypeError", TypeError, _ProfilerMissingEstimate, match="estimate_quality")

expect_raises("Validator without validate_execution -> TypeError", TypeError, _ValidatorMissingExec, match="validate_execution")
expect_raises("Validator without validate_quality -> TypeError", TypeError, _ValidatorMissingQuality, match="validate_quality")


# ---------------------------------------------------------
# 3. Reference concrete implementations
# ---------------------------------------------------------

section("Reference implementations")


class DummyBackend(QuantumBackendInterface):
    def execute(self, request, circuit):
        return ExecutionResult(
            result_id="result_001",
            request_id=request.request_id,
            status=ExecutionStatus.COMPLETED,
            counts={"0": 500, "1": 524},
            shots=request.shots,
        )

    def is_available(self):
        return True

    def get_backend_info(self):
        return {"name": "dummy_backend", "type": "simulator"}


def backend_case():
    b = DummyBackend()
    req = ExecutionRequest(
        request_id="request_001",
        workload_id="workload_001",
        shots=1024,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
    )
    res = b.execute(req, circuit=None)
    assert b.is_available() is True
    assert b.get_backend_info()["name"] == "dummy_backend"
    assert res.status == ExecutionStatus.COMPLETED
    assert sum(res.counts.values()) == 1024
    assert res.shots == 1024


expect_ok("DummyBackend end-to-end", backend_case)


class DummyWorkload(WorkloadInterface):
    def get_spec(self):
        return WorkloadSpec(
            workload_id="workload_001",
            name="Test workload",
            workload_type=WorkloadType.BATCH,
            algorithm="TestAlgorithm",
        )

    def build_circuit(self):
        return "dummy_circuit"

    def evaluate_result(self, result):
        return QualityEstimate(
            sample_count=result.shots,
            application_score=0.95,
        )


def workload_case():
    w = DummyWorkload()
    assert w.get_spec().algorithm == "TestAlgorithm"
    assert w.build_circuit() == "dummy_circuit"
    q = w.evaluate_result(ExecutionResult(
        result_id="r", request_id="q",
        status=ExecutionStatus.COMPLETED, shots=1024,
    ))
    assert q.application_score == 0.95
    assert q.sample_count == 1024


expect_ok("DummyWorkload end-to-end", workload_case)


class DummyProfiler(ProfilerInterface):
    def profile_circuit(self, circuit):
        return CircuitProfile(num_qubits=2, depth=5, total_gates=8, two_qubit_gates=2)

    def estimate_quality(self, result, workload):
        return QualityEstimate(
            sample_count=result.shots,
            expectation_value=0.8,
            variance=0.1,
        )


def profiler_case():
    p = DummyProfiler()
    prof = p.profile_circuit("dummy_circuit")
    assert prof.num_qubits == 2 and prof.depth == 5
    q = p.estimate_quality(
        ExecutionResult(result_id="r", request_id="q",
                        status=ExecutionStatus.COMPLETED, shots=1024),
        WorkloadSpec(workload_id="w", name="n",
                     workload_type=WorkloadType.BATCH, algorithm="a"),
    )
    assert q.expectation_value == 0.8
    assert q.sample_count == 1024


expect_ok("DummyProfiler end-to-end", profiler_case)


class DummyPolicy(PolicyInterface):
    def decide(self, workload, profile, quality, current_shots):
        return RuntimeDecision(
            action=RuntimeAction.ACCEPT_RESULT,
            reason="Test quality requirement satisfied.",
        )


def policy_case():
    d = DummyPolicy().decide(
        workload=WorkloadSpec(workload_id="w1", name="Test",
                              workload_type=WorkloadType.BATCH, algorithm="Test"),
        profile=CircuitProfile(num_qubits=2, depth=5, total_gates=8, two_qubit_gates=2),
        quality=QualityEstimate(application_score=0.95),
        current_shots=1024,
    )
    assert d.action == RuntimeAction.ACCEPT_RESULT


expect_ok("DummyPolicy end-to-end", policy_case)


class DummyValidator(ValidatorInterface):
    def validate_execution(self, result, request):
        return (
            result.status == ExecutionStatus.COMPLETED
            and result.shots is not None
            and result.shots == request.shots
            and sum(result.counts.values()) == request.shots
        )

    def validate_quality(self, quality, workload):
        return (
            quality.application_score is not None
            and quality.application_score >= 0.90
        )


def validator_happy():
    v = DummyValidator()
    req = ExecutionRequest(
        request_id="request_001", workload_id="workload_001",
        shots=1024, execution_mode=ExecutionMode.IDEAL_SIMULATOR,
    )
    res = ExecutionResult(
        result_id="result_001", request_id="request_001",
        status=ExecutionStatus.COMPLETED,
        counts={"0": 500, "1": 524}, shots=1024,
    )
    q = QualityEstimate(application_score=0.95)
    w = WorkloadSpec(workload_id="workload_001", name="Test",
                     workload_type=WorkloadType.BATCH, algorithm="Test")
    assert v.validate_execution(res, req) is True
    assert v.validate_quality(q, w) is True


def validator_rejects_bad_counts():
    v = DummyValidator()
    req = ExecutionRequest(
        request_id="r", workload_id="w",
        shots=1024, execution_mode=ExecutionMode.IDEAL_SIMULATOR,
    )
    res = ExecutionResult(
        result_id="r", request_id="q",
        status=ExecutionStatus.COMPLETED,
        counts={"0": 10, "1": 10},  # only 20 total, not 1024
        shots=1024,
    )
    assert v.validate_execution(res, req) is False


def validator_rejects_low_quality():
    v = DummyValidator()
    w = WorkloadSpec(workload_id="w", name="n",
                     workload_type=WorkloadType.BATCH, algorithm="a")
    assert v.validate_quality(QualityEstimate(application_score=0.50), w) is False
    assert v.validate_quality(QualityEstimate(), w) is False  # application_score=None


expect_ok("DummyValidator happy path", validator_happy)
expect_ok("DummyValidator rejects wrong total", validator_rejects_bad_counts)
expect_ok("DummyValidator rejects low/missing score", validator_rejects_low_quality)


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