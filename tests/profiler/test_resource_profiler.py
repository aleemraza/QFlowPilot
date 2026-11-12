
import pytest

from qflowpilot.profiler.resource_profiler import (
    ResourceProfiler,
    ResourceLimits,
)


def test_required_shots():
    profiler = ResourceProfiler()

    shots = profiler.estimate_required_shots(
        variance=0.25,
        target_precision=0.02,
        confidence_level=0.95,
    )

    assert shots == 2401


def test_qpu_utilization():
    profiler = ResourceProfiler()

    utilization = profiler.calculate_qpu_utilization(
        busy_time_s=70,
        available_time_s=100,
    )

    assert utilization == 0.70


def test_invalid_precision():
    profiler = ResourceProfiler()

    with pytest.raises(ValueError):
        profiler.estimate_required_shots(
            variance=0.25,
            target_precision=0,
        )


def test_invalid_utilization():
    profiler = ResourceProfiler()

    with pytest.raises(ValueError):
        profiler.calculate_qpu_utilization(
            busy_time_s=110,
            available_time_s=100,
        )


def test_resource_limit_violation():
    from qflowpilot.core.models import CircuitProfile

    profiler = ResourceProfiler()

    profiles = [
        CircuitProfile(
            num_qubits=8,
            depth=20,
            total_gates=30,
            two_qubit_gates=10,
        )
    ]

    result = profiler.profile_circuits(
        circuit_profiles=profiles,
        shots_per_circuit=1000,
        limits=ResourceLimits(
            max_qubits=5,
            max_shots=2000,
            max_circuit_depth=30,
        ),
    )

    assert result.feasible is False
    assert len(result.violations) > 0


def test_resource_profile_without_limits():
    from qflowpilot.core.models import CircuitProfile

    profiler = ResourceProfiler()

    profiles = [
        CircuitProfile(
            num_qubits=3,
            depth=5,
            total_gates=10,
            two_qubit_gates=2,
        )
    ]

    result = profiler.profile_circuits(
        circuit_profiles=profiles,
    )

    assert result.feasible is None
    assert result.quantum.required_qubits == 3


def test_empty_circuit_profiles():
    profiler = ResourceProfiler()

    with pytest.raises(ValueError):
        profiler.profile_circuits([])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
