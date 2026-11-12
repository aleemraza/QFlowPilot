import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter
from qiskit import qasm2
from qflowpilot.profiler import CircuitProfiler
@pytest.fixture
def profiler():
    return CircuitProfiler()


def test_bell_circuit(profiler):
    circuit = QuantumCircuit(2, 2)

    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure([0, 1], [0, 1])

    profile = profiler.profile_circuit(circuit)

    assert profile.num_qubits == 2
    assert profile.total_gates == 2
    assert profile.two_qubit_gates == 1

    assert profile.gate_counts == {
        "cx": 1,
        "h": 1,
    }

    assert profile.metadata["measurement_count"] == 2
    assert profile.metadata["single_qubit_gates"] == 1
    assert profile.metadata["two_qubit_gates"] == 1


def test_multi_qubit_gate(profiler):
    circuit = QuantumCircuit(3)

    circuit.ccx(0, 1, 2)

    profile = profiler.profile_circuit(circuit)

    assert profile.total_gates == 1
    assert profile.metadata["multi_qubit_gates"] == 1
    assert profile.metadata["maximum_operation_width"] == 3


def test_parameterized_circuit(profiler):
    theta = Parameter("theta")

    circuit = QuantumCircuit(2)
    circuit.ry(theta, 0)
    circuit.cx(0, 1)

    profile = profiler.profile_circuit(circuit)

    assert profile.metadata["parameter_count"] == 1
    assert profile.metadata["has_parameters"] is True
    assert profile.total_gates == 2


def test_special_operations(profiler):
    circuit = QuantumCircuit(2, 2)

    circuit.h(0)
    circuit.reset(1)
    circuit.barrier()
    circuit.measure(0, 0)

    profile = profiler.profile_circuit(circuit)

    assert profile.total_gates == 1
    assert profile.metadata["reset_count"] == 1
    assert profile.metadata["barrier_count"] == 1
    assert profile.metadata["measurement_count"] == 1


def test_connectivity(profiler):
    circuit = QuantumCircuit(3)

    circuit.cx(0, 1)
    circuit.cx(1, 2)

    profile = profiler.profile_circuit(circuit)

    assert profile.metadata["connectivity_edges"] == [
        [0, 1],
        [1, 2],
    ]


def test_instruction_details():
    profiler = CircuitProfiler(
        include_instruction_details=True
    )

    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)

    profile = profiler.profile_circuit(circuit)

    details = profile.metadata["instruction_details"]

    assert len(details) == 2
    assert details[0]["name"] == "h"
    assert details[1]["name"] == "cx"


def test_empty_circuit(profiler):
    circuit = QuantumCircuit(3)

    profile = profiler.profile_circuit(circuit)

    assert profile.num_qubits == 3
    assert profile.total_gates == 0
    assert profile.two_qubit_gates == 0


def test_invalid_input(profiler):
    with pytest.raises(TypeError):
        profiler.profile_circuit("invalid circuit")


def test_qasm_file_loading(profiler, tmp_path):
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)

    qasm_file = tmp_path / "bell.qasm"

    qasm_file.write_text(
        qasm2.dumps(circuit),
        encoding="utf-8",
    )

    loaded_circuit = profiler.load_circuit(qasm_file)

    assert isinstance(loaded_circuit, QuantumCircuit)
    assert loaded_circuit.num_qubits == 2
    assert loaded_circuit.depth() == 2
