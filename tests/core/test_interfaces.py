
import pytest

from qflowpilot.core.interfaces import (
    QuantumBackendInterface,
    WorkloadInterface,
    ProfilerInterface,
    PolicyInterface,
    ValidatorInterface,
)

from qflowpilot.core.models import (
    WorkloadSpec,
    WorkloadType,
    ExecutionRequest,
    ExecutionResult,
    ExecutionMode,
    ExecutionStatus,
    CircuitProfile,
    QualityEstimate,
    RuntimeDecision,
    RuntimeAction,
)


# ---------------------------------------------------------
# 1. Incomplete implementations must not be instantiated
# ---------------------------------------------------------

def test_backend_interface_is_abstract():
    with pytest.raises(TypeError):
        QuantumBackendInterface()


def test_workload_interface_is_abstract():
    with pytest.raises(TypeError):
        WorkloadInterface()


def test_profiler_interface_is_abstract():
    with pytest.raises(TypeError):
        ProfilerInterface()


def test_policy_interface_is_abstract():
    with pytest.raises(TypeError):
        PolicyInterface()


def test_validator_interface_is_abstract():
    with pytest.raises(TypeError):
        ValidatorInterface()


# ---------------------------------------------------------
# 2. Concrete backend implementation
# ---------------------------------------------------------

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
        return {"name": "dummy_backend"}


def test_dummy_backend():
    backend = DummyBackend()

    request = ExecutionRequest(
        request_id="request_001",
        workload_id="workload_001",
        shots=1024,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
    )

    result = backend.execute(request, circuit=None)

    assert backend.is_available()
    assert backend.get_backend_info()["name"] == "dummy_backend"
    assert result.status == ExecutionStatus.COMPLETED
    assert sum(result.counts.values()) == 1024


# ---------------------------------------------------------
# 3. Concrete workload implementation
# ---------------------------------------------------------

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


def test_dummy_workload():
    workload = DummyWorkload()

    assert workload.get_spec().algorithm == "TestAlgorithm"
    assert workload.build_circuit() == "dummy_circuit"


# ---------------------------------------------------------
# 4. Concrete profiler implementation
# ---------------------------------------------------------

class DummyProfiler(ProfilerInterface):

    def profile_circuit(self, circuit):
        return CircuitProfile(
            num_qubits=2,
            depth=5,
            total_gates=8,
            two_qubit_gates=2,
        )

    def estimate_quality(self, result, workload):
        return QualityEstimate(
            sample_count=result.shots,
            expectation_value=0.8,
            variance=0.1,
        )


def test_dummy_profiler():
    profiler = DummyProfiler()

    profile = profiler.profile_circuit("dummy_circuit")

    assert profile.num_qubits == 2
    assert profile.depth == 5


# ---------------------------------------------------------
# 5. Concrete runtime policy implementation
# ---------------------------------------------------------

class DummyPolicy(PolicyInterface):

    def decide(self, workload, profile, quality, current_shots):
        return RuntimeDecision(
            action=RuntimeAction.ACCEPT_RESULT,
            reason="Test quality requirement satisfied.",
        )


def test_dummy_policy():
    policy = DummyPolicy()

    decision = policy.decide(
        workload=WorkloadSpec(
            workload_id="w1",
            name="Test",
            workload_type=WorkloadType.BATCH,
            algorithm="Test",
        ),
        profile=CircuitProfile(
            num_qubits=2,
            depth=5,
            total_gates=8,
            two_qubit_gates=2,
        ),
        quality=QualityEstimate(application_score=0.95),
        current_shots=1024,
    )

    assert decision.action == RuntimeAction.ACCEPT_RESULT


# ---------------------------------------------------------
# 6. Concrete validator implementation
# ---------------------------------------------------------

class DummyValidator(ValidatorInterface):

    def validate_execution(self, result, request):
        return (
            result.status == ExecutionStatus.COMPLETED
            and result.shots == request.shots
            and sum(result.counts.values()) == request.shots
        )

    def validate_quality(self, quality, workload):
        return (
            quality.application_score is not None
            and quality.application_score >= 0.90
        )


def test_dummy_validator():
    validator = DummyValidator()

    request = ExecutionRequest(
        request_id="request_001",
        workload_id="workload_001",
        shots=1024,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
    )

    result = ExecutionResult(
        result_id="result_001",
        request_id="request_001",
        status=ExecutionStatus.COMPLETED,
        counts={"0": 500, "1": 524},
        shots=1024,
    )

    quality = QualityEstimate(application_score=0.95)

    workload = WorkloadSpec(
        workload_id="workload_001",
        name="Test",
        workload_type=WorkloadType.BATCH,
        algorithm="Test",
    )

    assert validator.validate_execution(result, request)
    assert validator.validate_quality(quality, workload)

