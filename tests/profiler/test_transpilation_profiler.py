
import pytest

from qiskit import QuantumCircuit

from qflowpilot.profiler.transpilation_profiler import (
    TranspilationProfiler,
    TranspilationProfile,
)


@pytest.fixture
def profiler():
    return TranspilationProfiler(
        basis_gates=["rz", "sx", "x", "cx"],
        coupling_map=[
            [0, 1],
            [1, 0],
            [1, 2],
            [2, 1],
        ],
        optimization_level=1,
        seed_transpiler=42,
    )


def make_circuit():
    circuit = QuantumCircuit(3)
    circuit.h([0, 1, 2])
    circuit.cx(0, 1)
    circuit.cx(1, 2)
    circuit.measure_all()
    return circuit


def test_basic_transpilation(profiler):
    circuit = make_circuit()

    result = profiler.profile_circuit(circuit)

    assert isinstance(result, TranspilationProfile)
    assert result.transpiled_circuit is not None
    assert result.logical_num_qubits == 3
    assert result.transpiled_num_qubits >= 3
    assert result.transpiled_depth > 0


def test_logical_metrics(profiler):
    circuit = make_circuit()

    result = profiler.profile_circuit(circuit)

    assert result.logical_gate_count == 5
    assert result.logical_two_qubit_gates == 2
    assert result.logical_depth == circuit.depth()


def test_transpiled_metrics(profiler):
    circuit = make_circuit()

    result = profiler.profile_circuit(circuit)

    assert result.transpiled_gate_count > 0
    assert result.transpiled_two_qubit_gates >= 0
    assert isinstance(result.transpiled_gate_counts, dict)


def test_overhead_metrics(profiler):
    circuit = make_circuit()

    result = profiler.profile_circuit(circuit)

    assert result.routing_overhead >= 0
    assert result.depth_overhead >= 0
    assert result.gate_count_overhead >= 0


def test_transpilation_time(profiler):
    circuit = make_circuit()

    result = profiler.profile_circuit(circuit)

    assert result.transpilation_time_s >= 0


def test_invalid_circuit(profiler):
    with pytest.raises(TypeError):
        profiler.profile_circuit("not a circuit")


def test_invalid_optimization_level():
    with pytest.raises(ValueError):
        TranspilationProfiler(optimization_level=5)


def test_empty_multiple_circuits(profiler):
    with pytest.raises(ValueError):
        profiler.profile_multiple([])


def test_multiple_circuits(profiler):
    circuits = [make_circuit(), make_circuit()]

    results = profiler.profile_multiple(circuits)

    assert len(results) == 2
    assert all(
        isinstance(item, TranspilationProfile)
        for item in results
    )
