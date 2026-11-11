
import pytest

from qflowpilot.core.models import (
    WorkloadType,
    ExecutionMode,
    ExecutionStatus,
    RuntimeAction,
    WorkloadSpec,
    CircuitProfile,
    ExecutionResult,
    QualityEstimate,
    RuntimeDecision,
)

from qflowpilot.core.orchestrator import (
    QFlowPilotOrchestrator,
)

from qflowpilot.core.config import QFlowPilotConfig
from qflowpilot.core.exceptions import (
    BackendUnavailableError,
    QualityViolationError,
    RuntimeExecutionError,
)


# ---------------------------------------------------------
# Dummy workload
# ---------------------------------------------------------

class DummyWorkload:

    def get_spec(self):
        return WorkloadSpec(
            workload_id="test_workload",
            name="Test Workload",
            workload_type=WorkloadType.BATCH,
            algorithm="qaoa",
        )

    def build_circuit(self):
        return "dummy_quantum_circuit"

    def evaluate_result(self, result):
        return QualityEstimate(
            application_score=0.95,
        )


# ---------------------------------------------------------
# Dummy backend
# ---------------------------------------------------------

class DummyBackend:

    def __init__(self, available=True):
        self.available = available
        self.requests = []

    def is_available(self):
        return self.available

    def get_backend_info(self):
        return {"name": "dummy_backend"}

    def execute(self, request, circuit):
        self.requests.append(request)

        return ExecutionResult(
            result_id=f"result_{len(self.requests)}",
            request_id=request.request_id,
            status=ExecutionStatus.COMPLETED,
            counts={"00": request.shots},
            shots=request.shots,
        )


# ---------------------------------------------------------
# Dummy profiler
# ---------------------------------------------------------

class DummyProfiler:

    def profile_circuit(self, circuit):
        return CircuitProfile(
            num_qubits=2,
            depth=2,
            total_gates=3,
            two_qubit_gates=1,
        )

    def estimate_quality(self, result, workload):
        return QualityEstimate(
            success_probability=0.95,
            standard_error=0.01,
        )


# ---------------------------------------------------------
# Dummy policy
# ---------------------------------------------------------

class DummyPolicy:

    def __init__(self, actions=None):
        self.actions = actions or [
            RuntimeAction.ACCEPT_RESULT
        ]

    def decide(self, workload, profile, quality, current_shots):
        action = self.actions.pop(0)

        if action == RuntimeAction.ALLOCATE_MORE_SHOTS:
            return RuntimeDecision(
                action=action,
                reason="More shots are required.",
                additional_shots=100,
            )

        return RuntimeDecision(
            action=action,
            reason="Test policy decision.",
        )


# ---------------------------------------------------------
# Dummy validator
# ---------------------------------------------------------

class DummyValidator:

    def __init__(self, quality_valid=True):
        self.quality_valid = quality_valid

    def validate_execution(self, result, request):
        return True

    def validate_quality(self, quality, workload):
        return self.quality_valid


# ---------------------------------------------------------
# Test helpers
# ---------------------------------------------------------

def create_orchestrator(
    backend=None,
    policy=None,
    validator=None,
    classical_backend=None,
):

    return QFlowPilotOrchestrator(
        workload=DummyWorkload(),
        backend=backend or DummyBackend(),
        profiler=DummyProfiler(),
        policy=policy or DummyPolicy(),
        validator=validator or DummyValidator(),
        config=QFlowPilotConfig(),
        classical_backend=classical_backend,
    )


# ---------------------------------------------------------
# Tests
# ---------------------------------------------------------

def test_successful_orchestration():

    orchestrator = create_orchestrator()

    result = orchestrator.run()

    assert result.workload_id == "test_workload"
    assert result.execution_result.status == ExecutionStatus.COMPLETED
    assert result.quality.quality_satisfied is True
    assert result.total_attempts == 1
    assert len(result.decisions) == 1


def test_circuit_profile_is_returned():

    orchestrator = create_orchestrator()

    result = orchestrator.run()

    assert result.circuit_profile.num_qubits == 2
    assert result.circuit_profile.depth == 2


def test_additional_shots_action():

    backend = DummyBackend()

    policy = DummyPolicy([
        RuntimeAction.ALLOCATE_MORE_SHOTS,
        RuntimeAction.ACCEPT_RESULT,
    ])

    orchestrator = create_orchestrator(
        backend=backend,
        policy=policy,
    )

    result = orchestrator.run()

    assert len(backend.requests) == 2
    assert backend.requests[0].shots == 1024
    assert backend.requests[1].shots == 1124
    assert result.total_attempts == 2


def test_backend_unavailable():

    backend = DummyBackend(available=False)

    orchestrator = create_orchestrator(
        backend=backend,
    )

    with pytest.raises(BackendUnavailableError):
        orchestrator.run()


def test_quality_validation_failure():

    validator = DummyValidator(quality_valid=False)

    orchestrator = create_orchestrator(
        validator=validator,
    )

    with pytest.raises(QualityViolationError):
        orchestrator.run()


def test_classical_fallback():

    classical_backend = DummyBackend()

    policy = DummyPolicy([
        RuntimeAction.FALLBACK_CLASSICAL,
        RuntimeAction.ACCEPT_RESULT,
    ])

    orchestrator = create_orchestrator(
        policy=policy,
        classical_backend=classical_backend,
    )

    result = orchestrator.run()

    assert result.execution_result.status == ExecutionStatus.COMPLETED
    assert result.total_attempts == 2
    assert classical_backend.requests[0].execution_mode == ExecutionMode.CLASSICAL


def test_fallback_without_classical_backend():

    policy = DummyPolicy([
        RuntimeAction.FALLBACK_CLASSICAL,
    ])

    orchestrator = create_orchestrator(
        policy=policy,
    )

    with pytest.raises(RuntimeExecutionError):
        orchestrator.run()
