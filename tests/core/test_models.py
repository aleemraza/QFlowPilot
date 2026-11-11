
import pytest

from qflowpilot.core.models import (
    WorkloadSpec,
    WorkloadType,
    CircuitProfile,
    ExecutionRequest,
    ExecutionMode,
    ExecutionResult,
    ExecutionStatus,
    QualityEstimate,
    RuntimeDecision,
    RuntimeAction,
)


def test_create_workload():
    workload = WorkloadSpec(
        workload_id="qaoa_001",
        name="Max-Cut",
        workload_type=WorkloadType.ITERATIVE,
        algorithm="QAOA",
        application="Graph optimization",
    )

    assert workload.workload_id == "qaoa_001"
    assert workload.algorithm == "QAOA"


def test_invalid_workload():
    with pytest.raises(ValueError):
        WorkloadSpec(
            workload_id="",
            name="Max-Cut",
            workload_type=WorkloadType.ITERATIVE,
            algorithm="QAOA",
        )


def test_create_circuit_profile():
    profile = CircuitProfile(
        num_qubits=5,
        depth=20,
        total_gates=45,
        two_qubit_gates=12,
        gate_counts={"h": 5, "cx": 12, "rz": 28},
    )

    assert profile.num_qubits == 5
    assert profile.two_qubit_gates == 12


def test_invalid_circuit_profile():
    with pytest.raises(ValueError):
        CircuitProfile(
            num_qubits=0,
            depth=20,
            total_gates=45,
            two_qubit_gates=12,
        )


def test_create_execution_request():
    request = ExecutionRequest(
        request_id="request_001",
        workload_id="qaoa_001",
        shots=1024,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
        backend_name="aer_simulator",
        seed=42,
    )

    assert request.shots == 1024
    assert request.seed == 42


def test_invalid_shots():
    with pytest.raises(ValueError):
        ExecutionRequest(
            request_id="request_001",
            workload_id="qaoa_001",
            shots=0,
            execution_mode=ExecutionMode.IDEAL_SIMULATOR,
        )


def test_create_execution_result():
    result = ExecutionResult(
        result_id="result_001",
        request_id="request_001",
        status=ExecutionStatus.COMPLETED,
        counts={"000": 500, "111": 524},
        shots=1024,
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert sum(result.counts.values()) == 1024


def test_invalid_measurement_counts():
    with pytest.raises(ValueError):
        ExecutionResult(
            result_id="result_001",
            request_id="request_001",
            status=ExecutionStatus.COMPLETED,
            counts={"000": -1},
        )


def test_create_quality_estimate():
    quality = QualityEstimate(
        sample_count=1024,
        expectation_value=-0.75,
        variance=0.12,
        standard_error=0.0108,
        confidence_interval=(-0.77, -0.73),
        success_probability=0.82,
        application_score=0.90,
        quality_satisfied=True,
    )

    assert quality.sample_count == 1024
    assert quality.quality_satisfied is True


def test_invalid_quality_probability():
    with pytest.raises(ValueError):
        QualityEstimate(success_probability=1.5)


def test_create_runtime_decision():
    decision = RuntimeDecision(
        action=RuntimeAction.ALLOCATE_MORE_SHOTS,
        reason="The estimated quality does not meet the target.",
        additional_shots=2048,
    )

    assert decision.additional_shots == 2048


def test_invalid_runtime_decision():
    with pytest.raises(ValueError):
        RuntimeDecision(
            action=RuntimeAction.ALLOCATE_MORE_SHOTS,
            reason="Additional measurements are required.",
        )
