
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from qiskit import QuantumCircuit

from qflowpilot.adapters.ibm_adapter import IBMAdapter
from qflowpilot.core.models import (
    ExecutionMode,
    ExecutionRequest,
    ExecutionStatus,
)
from qflowpilot.core.exceptions import (
    BackendExecutionError,
    BackendUnavailableError,
)


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def create_request(
    execution_mode=ExecutionMode.QUANTUM_HARDWARE,
    backend_name="ibm_test_backend",
):
    return ExecutionRequest(
        request_id="test-request-001",
        workload_id="test-workload-001",
        shots=1024,
        execution_mode=execution_mode,
        backend_name=backend_name,
        seed=42,
        timeout_s=300,
    )


def create_measured_circuit():
    circuit = QuantumCircuit(2, 2)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure([0, 1], [0, 1])
    return circuit


def create_mock_backend(operational=True):
    backend = MagicMock()

    backend.name = "ibm_test_backend"
    backend.num_qubits = 127
    backend.operation_names = ["rz", "sx", "x", "cx"]

    backend.status.return_value = SimpleNamespace(
        operational=operational,
        pending_jobs=2,
    )

    return backend


# ---------------------------------------------------------
# Fixtures
# ---------------------------------------------------------

@pytest.fixture
def mock_backend():
    return create_mock_backend()


@pytest.fixture
def adapter(mock_backend):
    return IBMAdapter(
        backend_name="ibm_test_backend",
        backend=mock_backend,
        service=MagicMock(),
    )


# ---------------------------------------------------------
# 1. Initialization
# ---------------------------------------------------------

def test_adapter_initialization(adapter):
    assert adapter.backend_name == "ibm_test_backend"
    assert adapter.backend_type == "ibm_quantum_hardware"


# ---------------------------------------------------------
# 2. Backend availability
# ---------------------------------------------------------

def test_backend_is_available(adapter):
    assert adapter.is_available() is True


def test_backend_is_unavailable():
    backend = create_mock_backend(operational=False)

    adapter = IBMAdapter(
        backend_name="ibm_test_backend",
        backend=backend,
        service=MagicMock(),
    )

    assert adapter.is_available() is False


# ---------------------------------------------------------
# 3. Backend information
# ---------------------------------------------------------

def test_get_backend_info(adapter):
    info = adapter.get_backend_info()

    assert info["backend_name"] == "ibm_test_backend"
    assert info["is_available"] is True
    assert info["num_qubits"] == 127


# ---------------------------------------------------------
# 4. Successful execution with mocked SamplerV2
# ---------------------------------------------------------

# @patch("qflowpilot.adapters.ibm_adapter.SamplerV2")
@patch("qiskit_ibm_runtime.SamplerV2")
@patch("qflowpilot.adapters.ibm_adapter.generate_preset_pass_manager")
def test_successful_execution(
    mock_pass_manager_factory,
    mock_sampler_class,
    adapter,
):
    circuit = create_measured_circuit()
    request = create_request()

    # Mock transpilation
    mock_pass_manager = MagicMock()
    mock_pass_manager.run.return_value = circuit
    mock_pass_manager_factory.return_value = mock_pass_manager

    # Mock measurement results
    mock_bit_array = MagicMock()
    mock_bit_array.get_counts.return_value = {
        "00": 520,
        "11": 504,
    }

    mock_pub_result = MagicMock()
    mock_pub_result.data = SimpleNamespace(
        c=mock_bit_array
    )

    mock_job = MagicMock()
    mock_job.job_id.return_value = "mock-job-123"
    mock_job.result.return_value = [mock_pub_result]

    mock_sampler = MagicMock()
    mock_sampler.run.return_value = mock_job
    mock_sampler_class.return_value = mock_sampler

    # Execute
    result = adapter.execute(request, circuit)

    # Assertions
    assert result.request_id == request.request_id
    assert result.status == ExecutionStatus.COMPLETED
    assert result.backend_name == "ibm_test_backend"
    assert result.execution_mode == ExecutionMode.QUANTUM_HARDWARE
    assert result.shots == 1024

    assert result.counts == {
        "00": 520,
        "11": 504,
    }

    assert result.metadata["job_id"] == "mock-job-123"
    assert result.metadata["seed_applied"] is False

    mock_sampler.run.assert_called_once()
    mock_job.result.assert_called_once_with(timeout=300)


# ---------------------------------------------------------
# 5. Reject incorrect execution mode
# ---------------------------------------------------------

def test_reject_ideal_simulator_mode(adapter):
    circuit = create_measured_circuit()

    request = create_request(
        execution_mode=ExecutionMode.IDEAL_SIMULATOR
    )

    with pytest.raises(ValueError):
        adapter.execute(request, circuit)


# ---------------------------------------------------------
# 6. Reject mismatched backend name
# ---------------------------------------------------------

def test_reject_wrong_backend_name(adapter):
    circuit = create_measured_circuit()

    request = create_request(
        backend_name="another_backend"
    )

    with pytest.raises(ValueError):
        adapter.execute(request, circuit)


# ---------------------------------------------------------
# 7. Reject unavailable backend
# ---------------------------------------------------------

def test_reject_unavailable_backend():
    backend = create_mock_backend(operational=False)

    adapter = IBMAdapter(
        backend_name="ibm_test_backend",
        backend=backend,
        service=MagicMock(),
    )

    request = create_request()
    circuit = create_measured_circuit()

    with pytest.raises(BackendUnavailableError):
        adapter.execute(request, circuit)


# ---------------------------------------------------------
# 8. Reject unmeasured circuit
# ---------------------------------------------------------

def test_reject_unmeasured_circuit(adapter):
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)

    request = create_request()

    with pytest.raises(ValueError):
        adapter.execute(request, circuit)


# ---------------------------------------------------------
# 9. Reject multiple classical registers
# ---------------------------------------------------------

def test_reject_multiple_classical_registers(adapter):
    from qiskit import ClassicalRegister

    circuit = QuantumCircuit(2)

    register_a = ClassicalRegister(1, "a")
    register_b = ClassicalRegister(1, "b")

    circuit.add_register(register_a)
    circuit.add_register(register_b)

    circuit.h(0)
    circuit.measure(0, register_a[0])
    circuit.measure(1, register_b[0])

    request = create_request()

    with pytest.raises(ValueError):
        adapter.execute(request, circuit)


# ---------------------------------------------------------
# 10. Reject non-QuantumCircuit input
# ---------------------------------------------------------

def test_reject_invalid_circuit(adapter):
    request = create_request()

    with pytest.raises(TypeError):
        adapter.execute(request, "not_a_quantum_circuit")


# ---------------------------------------------------------
# 11. Handle Sampler execution failure
# ---------------------------------------------------------

@patch("qflowpilot.adapters.ibm_adapter.SamplerV2")
@patch("qflowpilot.adapters.ibm_adapter.generate_preset_pass_manager")

def test_sampler_execution_failure(
    mock_pass_manager_factory,
    mock_sampler_class,
    adapter,
):
    circuit = create_measured_circuit()
    request = create_request()

    mock_pass_manager = MagicMock()
    mock_pass_manager.run.return_value = circuit
    mock_pass_manager_factory.return_value = mock_pass_manager

    mock_sampler = MagicMock()
    mock_sampler.run.side_effect = RuntimeError(
        "Mock IBM execution failure"
    )
    mock_sampler_class.return_value = mock_sampler

    with pytest.raises(BackendExecutionError):
        adapter.execute(request, circuit)
