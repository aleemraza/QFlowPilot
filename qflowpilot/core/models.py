
"""
Core data models for QFlowPilot.

These models are backend-independent. They do not import Qiskit,
Aer, IBM Quantum, or any simulator-specific package.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Tuple


# ---------------------------------------------------------
# 1. Enumerations
# ---------------------------------------------------------

class WorkloadType(str, Enum):
    """Execution pattern of a workload."""

    BATCH = "batch"
    ITERATIVE = "iterative"
    APPLICATION = "application"


class ExecutionMode(str, Enum):
    """Type of execution environment."""

    IDEAL_SIMULATOR = "ideal_simulator"
    NOISY_SIMULATOR = "noisy_simulator"
    QUANTUM_HARDWARE = "quantum_hardware"
    CLASSICAL = "classical"


class ExecutionStatus(str, Enum):
    """Lifecycle status of an execution request."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RuntimeAction(str, Enum):
    """Actions that a runtime policy may recommend."""

    ACCEPT_RESULT = "accept_result"
    ALLOCATE_MORE_SHOTS = "allocate_more_shots"
    RETRY = "retry"
    FALLBACK_CLASSICAL = "fallback_classical"
    WAIT = "wait"
    REJECT_RESULT = "reject_result"
    TERMINATE = "terminate"


# ---------------------------------------------------------
# 2. Workload specification
# ---------------------------------------------------------

@dataclass
class WorkloadSpec:
    """
    Describes a workload submitted to QFlowPilot.

    Example:
        WorkloadSpec(
            workload_id="qaoa_001",
            name="Max-Cut problem",
            workload_type=WorkloadType.ITERATIVE,
            algorithm="QAOA",
            application="Max-Cut"
        )
    """

    workload_id: str
    name: str
    workload_type: WorkloadType
    algorithm: str

    application: Optional[str] = None
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.workload_id.strip():
            raise ValueError("workload_id cannot be empty.")

        if not self.name.strip():
            raise ValueError("Workload name cannot be empty.")

        if not self.algorithm.strip():
            raise ValueError("Algorithm cannot be empty.")

        if not isinstance(self.workload_type, WorkloadType):
            raise TypeError("workload_type must be a WorkloadType value.")


# ---------------------------------------------------------
# 3. Quantum circuit profile
# ---------------------------------------------------------

@dataclass
class CircuitProfile:
    """
    Stores structural characteristics of a quantum circuit.

    The profiler will populate this model after analyzing
    a circuit.
    """

    num_qubits: int
    depth: int
    total_gates: int
    two_qubit_gates: int

    gate_counts: Dict[str, int] = field(default_factory=dict)

    estimated_execution_time_s: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.num_qubits < 1:
            raise ValueError("num_qubits must be at least 1.")

        if self.depth < 0:
            raise ValueError("Circuit depth cannot be negative.")

        if self.total_gates < 0:
            raise ValueError("total_gates cannot be negative.")

        if not 0 <= self.two_qubit_gates <= self.total_gates:
            raise ValueError(
                "two_qubit_gates must be between 0 and total_gates."
            )

        for gate, count in self.gate_counts.items():
            if count < 0:
                raise ValueError(
                    f"Gate count for {gate} cannot be negative."
                )

        if self.estimated_execution_time_s is not None:
            if self.estimated_execution_time_s < 0:
                raise ValueError(
                    "Estimated execution time cannot be negative."
                )


# ---------------------------------------------------------
# 4. Execution request
# ---------------------------------------------------------

@dataclass
class ExecutionRequest:
    """
    Describes a request to execute a quantum workload.

    The execution adapter receives this request and sends
    the circuit to the selected execution backend.
    """

    request_id: str
    workload_id: str
    shots: int

    execution_mode: ExecutionMode
    backend_name: Optional[str] = None

    seed: Optional[int] = None
    timeout_s: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id cannot be empty.")

        if not self.workload_id.strip():
            raise ValueError("workload_id cannot be empty.")

        if self.shots <= 0:
            raise ValueError("shots must be greater than zero.")

        if not isinstance(self.execution_mode, ExecutionMode):
            raise TypeError(
                "execution_mode must be an ExecutionMode value."
            )

        if self.seed is not None and self.seed < 0:
            raise ValueError("seed cannot be negative.")

        if self.timeout_s is not None and self.timeout_s <= 0:
            raise ValueError("timeout_s must be greater than zero.")


# ---------------------------------------------------------
# 5. Execution result
# ---------------------------------------------------------

@dataclass
class ExecutionResult:
    """
    Stores the output and execution information returned
    by a quantum or classical execution adapter.
    """

    result_id: str
    request_id: str
    status: ExecutionStatus

    counts: Dict[str, int] = field(default_factory=dict)

    shots: Optional[int] = None
    backend_name: Optional[str] = None
    execution_mode: Optional[ExecutionMode] = None

    submitted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.result_id.strip():
            raise ValueError("result_id cannot be empty.")

        if not self.request_id.strip():
            raise ValueError("request_id cannot be empty.")

        if not isinstance(self.status, ExecutionStatus):
            raise TypeError(
                "status must be an ExecutionStatus value."
            )

        if self.shots is not None and self.shots <= 0:
            raise ValueError("shots must be greater than zero.")

        if self.execution_mode is not None:
            if not isinstance(self.execution_mode, ExecutionMode):
                raise TypeError(
                    "execution_mode must be an ExecutionMode value."
                )

        for bitstring, count in self.counts.items():
            if not isinstance(bitstring, str):
                raise TypeError("Measurement count keys must be strings.")

            if not isinstance(count, int) or isinstance(count, bool):
                raise TypeError("Measurement counts must be integers.")

            if count < 0:
                raise ValueError("Measurement counts cannot be negative.")

        timestamps = [
            self.submitted_at,
            self.started_at,
            self.completed_at,
        ]

        for timestamp in timestamps:
            if timestamp is not None and timestamp.tzinfo is None:
                raise ValueError("Timestamps must be timezone-aware.")

        if (
            self.submitted_at is not None
            and self.started_at is not None
            and self.started_at < self.submitted_at
        ):
            raise ValueError("started_at cannot precede submitted_at.")

        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at cannot precede started_at.")

    @property
    def execution_time_s(self) -> Optional[float]:
        """Return measured execution duration, if available."""

        if self.started_at is None or self.completed_at is None:
            return None

        return (
            self.completed_at - self.started_at
        ).total_seconds()


# ---------------------------------------------------------
# 6. Quality estimate
# ---------------------------------------------------------

@dataclass
class QualityEstimate:
    """
    Stores statistical and application-level quality estimates.

    Statistical measurements and application-level quality
    are kept separate because they represent different things.
    """

    sample_count: Optional[int] = None

    expectation_value: Optional[float] = None
    variance: Optional[float] = None
    standard_error: Optional[float] = None

    confidence_interval: Optional[Tuple[float, float]] = None

    success_probability: Optional[float] = None
    application_score: Optional[float] = None

    quality_satisfied: Optional[bool] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sample_count is not None and self.sample_count <= 0:
            raise ValueError("sample_count must be positive.")

        if self.variance is not None and self.variance < 0:
            raise ValueError("Variance cannot be negative.")

        if self.standard_error is not None:
            if self.standard_error < 0:
                raise ValueError("Standard error cannot be negative.")

        if self.confidence_interval is not None:
            lower, upper = self.confidence_interval

            if lower > upper:
                raise ValueError(
                    "Confidence interval lower bound cannot exceed upper bound."
                )

        if self.success_probability is not None:
            if not 0.0 <= self.success_probability <= 1.0:
                raise ValueError(
                    "success_probability must be between 0 and 1."
                )


# ---------------------------------------------------------
# 7. Runtime decision
# ---------------------------------------------------------

@dataclass
class RuntimeDecision:
    """
    Records a decision made by a QFlowPilot runtime policy.

    This model stores the decision; it does not execute it.
    """

    action: RuntimeAction
    reason: str

    additional_shots: Optional[int] = None
    target_backend: Optional[str] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.action, RuntimeAction):
            raise TypeError("action must be a RuntimeAction value.")

        if not self.reason.strip():
            raise ValueError("Decision reason cannot be empty.")

        if self.additional_shots is not None:
            if self.additional_shots <= 0:
                raise ValueError(
                    "additional_shots must be greater than zero."
                )

        if (
            self.action == RuntimeAction.ALLOCATE_MORE_SHOTS
            and self.additional_shots is None
        ):
            raise ValueError(
                "ALLOCATE_MORE_SHOTS requires additional_shots."
            )
