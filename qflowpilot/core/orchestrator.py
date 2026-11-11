
"""
Central execution orchestrator for QFlowPilot.

The orchestrator coordinates workload preparation, circuit profiling,
backend execution, quality estimation, runtime policy decisions,
and result validation.

It does not implement the internal logic of these components.
"""

from dataclasses import dataclass, fields, replace
from typing import Any
from uuid import uuid4

from qflowpilot.core.config import QFlowPilotConfig
from qflowpilot.core.exceptions import (
    BackendError,
    BackendExecutionError,
    BackendUnavailableError,
    ExecutionTimeoutError,
    InvalidWorkloadError,
    QualityViolationError,
    RuntimeExecutionError,
    UnsupportedWorkloadError,
    WorkloadError,
)
from qflowpilot.core.interfaces import (
    PolicyInterface,
    ProfilerInterface,
    QuantumBackendInterface,
    ValidatorInterface,
    WorkloadInterface,
)
from qflowpilot.core.models import (
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    QualityEstimate,
    RuntimeAction,
    RuntimeDecision,
)


@dataclass
class OrchestrationResult:
    """
    Contains the complete output of one orchestrated workload.

    Attributes:
        workload_id: Identifier of the submitted workload.
        execution_result: Final backend execution result.
        quality: Combined statistical and application-level quality.
        circuit_profile: Profile of the executed circuit.
        decisions: Runtime decisions made during execution.
        total_attempts: Number of backend execution attempts.
    """

    workload_id: str
    execution_result: ExecutionResult
    quality: QualityEstimate
    circuit_profile: Any
    decisions: list[RuntimeDecision]
    total_attempts: int


class QFlowPilotOrchestrator:
    """
    Coordinates the main QFlowPilot execution workflow.

    Components are injected through the constructor. This keeps the
    orchestrator independent of particular backend, profiler, policy,
    workload, and validator implementations.
    """

    def __init__(
        self,
        workload: WorkloadInterface,
        backend: QuantumBackendInterface,
        profiler: ProfilerInterface,
        policy: PolicyInterface,
        validator: ValidatorInterface,
        config: QFlowPilotConfig | None = None,
        classical_backend: QuantumBackendInterface | None = None,
    ) -> None:
        self.workload = workload
        self.backend = backend
        self.profiler = profiler
        self.policy = policy
        self.validator = validator
        self.config = config or QFlowPilotConfig()
        self.classical_backend = classical_backend

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------

    def run(self) -> OrchestrationResult:
        """
        Execute one workload through the complete QFlowPilot workflow.

        Returns:
            OrchestrationResult containing the final result,
            quality estimate, circuit profile, and policy history.

        Raises:
            InvalidWorkloadError: Workload preparation failed.
            BackendUnavailableError: Selected backend is unavailable.
            BackendExecutionError: Backend execution failed.
            ExecutionTimeoutError: Execution exceeded its timeout.
            QualityViolationError: Final result violates quality rules.
            RuntimeExecutionError: Runtime orchestration failed.
        """

        try:
            workload_spec = self.workload.get_spec()

            if not workload_spec.workload_id:
                raise InvalidWorkloadError(
                    "Workload identifier cannot be empty."
                )

            circuit = self.workload.build_circuit()

            if circuit is None:
                raise InvalidWorkloadError(
                    "Workload returned an empty circuit.",
                    workload_id=workload_spec.workload_id,
                )

            circuit_profile = self.profiler.profile_circuit(circuit)

        except WorkloadError:
            raise
        except Exception as exc:
            raise InvalidWorkloadError(
                "Failed to prepare or profile the workload.",
                details={"cause": str(exc)},
            ) from exc

        shots = self.config.shots.initial_shots
        max_shots = self.config.shots.max_shots
        max_retries = self.config.runtime.max_retries

        active_backend = self.backend
        execution_mode = ExecutionMode(
            self.config.backend.execution_mode
        )

        decisions: list[RuntimeDecision] = []
        total_attempts = 0
        classical_fallback_used = False
        retry_count = 0

        self._check_backend(active_backend)

        while True:
            total_attempts += 1

            request = self._create_request(
                workload_id=workload_spec.workload_id,
                shots=shots,
                execution_mode=execution_mode,
            )

            try:
                execution_result = self._execute(
                    backend=active_backend,
                    request=request,
                    circuit=circuit,
                )

            except ExecutionTimeoutError:
                if retry_count >= max_retries:
                    raise

                retry_count += 1
                continue

            except BackendError as exc:
                if not exc.retryable or retry_count >= max_retries:
                    raise

                retry_count += 1
                continue

            if not self.validator.validate_execution(
                execution_result,
                request,
            ):
                raise BackendExecutionError(
                    "Backend returned an invalid execution result.",
                    backend_name=request.backend_name,
                )

            # Estimate statistical quality using the profiler.
            statistical_quality = self.profiler.estimate_quality(
                execution_result,
                workload_spec,
            )

            # Evaluate application-level quality using the workload.
            application_quality = self.workload.evaluate_result(
                execution_result
            )

            quality = self._combine_quality(
                statistical_quality,
                application_quality,
            )

            # Ask the runtime policy what should happen next.
            decision = self.policy.decide(
                workload=workload_spec,
                profile=circuit_profile,
                quality=quality,
                current_shots=shots,
            )

            decisions.append(decision)

            # ------------------------------------------------
            # Action 1: Accept result
            # ------------------------------------------------

            if decision.action == RuntimeAction.ACCEPT_RESULT:

                quality_valid = self.validator.validate_quality(
                    quality,
                    workload_spec,
                )

                if not quality_valid:
                    raise QualityViolationError(
                        "Result does not satisfy workload quality requirements.",
                        details={
                            "workload_id": workload_spec.workload_id,
                            "shots": shots,
                        },
                    )

                quality = replace(
                    quality,
                    quality_satisfied=True,
                )

                return OrchestrationResult(
                    workload_id=workload_spec.workload_id,
                    execution_result=execution_result,
                    quality=quality,
                    circuit_profile=circuit_profile,
                    decisions=decisions,
                    total_attempts=total_attempts,
                )

            # ------------------------------------------------
            # Action 2: Allocate additional shots
            # ------------------------------------------------

            elif decision.action == RuntimeAction.ALLOCATE_MORE_SHOTS:

                additional_shots = decision.additional_shots

                if additional_shots is None or additional_shots <= 0:
                    raise RuntimeExecutionError(
                        "Policy requested additional shots without "
                        "a valid additional_shots value."
                    )

                new_shots = shots + additional_shots

                if new_shots > max_shots:
                    raise QualityViolationError(
                        "Maximum shot budget reached before quality "
                        "requirements were satisfied.",
                        details={
                            "current_shots": shots,
                            "requested_shots": additional_shots,
                            "maximum_shots": max_shots,
                        },
                    )

                shots = new_shots
                continue

            # ------------------------------------------------
            # Action 3: Retry execution
            # ------------------------------------------------

            elif decision.action == RuntimeAction.RETRY:

                if retry_count >= max_retries:
                    raise RuntimeExecutionError(
                        "Maximum runtime retry limit reached.",
                        component="orchestrator",
                        request_id=request.request_id,
                    )

                retry_count += 1
                continue

            # ------------------------------------------------
            # Action 4: Classical fallback
            # ------------------------------------------------

            # elif decision.action == RuntimeAction.FALLBACK_CLASSICAL:

            #     if self.classical_backend is None:
            #         raise RuntimeExecutionError(
            #             "Classical fallback was requested, but no "
            #             "classical backend was configured.",
            #             component="orchestrator",
            #             request_id=request.request_id,
            #         )

            #     active_backend = self.classical_backend
            #     execution_mode = ExecutionMode.CLASSICAL

            #     self._check_backend(active_backend)

            #     # Reset the retry counter for the fallback execution.
            #     retry_count = 0
            #     continue
            
            elif decision.action == RuntimeAction.FALLBACK_CLASSICAL:
                if self.classical_backend is None:
                    raise RuntimeExecutionError(
                        "Classical fallback was requested, but no "
                        "classical backend was configured.",
                        component="orchestrator",
                        request_id=request.request_id,
                    )

                if classical_fallback_used:
                    raise RuntimeExecutionError(
                        "Classical fallback has already been attempted.",
                        component="orchestrator",
                        request_id=request.request_id,
                    )

                classical_fallback_used = True
                active_backend = self.classical_backend
                execution_mode = ExecutionMode.CLASSICAL

                self._check_backend(active_backend)
                retry_count = 0
                continue

            # ------------------------------------------------
            # Action 5: Reject result
            # ------------------------------------------------

            elif decision.action == RuntimeAction.REJECT_RESULT:

                raise QualityViolationError(
                    "Runtime policy rejected the execution result.",
                    details={
                        "workload_id": workload_spec.workload_id,
                        "reason": decision.reason,
                    },
                )

            # ------------------------------------------------
            # Action 6: Terminate
            # ------------------------------------------------

            elif decision.action == RuntimeAction.TERMINATE:

                raise RuntimeExecutionError(
                    "Runtime policy terminated workload execution.",
                    component="orchestrator",
                    request_id=request.request_id,
                    details={"reason": decision.reason},
                )

            # ------------------------------------------------
            # Action 7: Wait
            # ------------------------------------------------

            elif decision.action == RuntimeAction.WAIT:

                raise RuntimeExecutionError(
                    "WAIT action is not supported by the current "
                    "synchronous orchestrator.",
                    component="orchestrator",
                    request_id=request.request_id,
                )

            else:
                raise RuntimeExecutionError(
                    f"Unsupported runtime action: {decision.action}"
                )

    # --------------------------------------------------------
    # Internal helper methods
    # --------------------------------------------------------

    def _check_backend(
        self,
        backend: QuantumBackendInterface,
    ) -> None:
        """Check whether the selected backend is available."""

        try:
            available = backend.is_available()

        except Exception as exc:
            raise BackendUnavailableError(
                "Failed to check backend availability.",
                retryable=True,
                details={"cause": str(exc)},
            ) from exc

        if not available:
            raise BackendUnavailableError(
                "Selected backend is unavailable.",
                retryable=True,
            )

    def _create_request(
        self,
        workload_id: str,
        shots: int,
        execution_mode: ExecutionMode,
    ) -> ExecutionRequest:
        """Create an execution request from the current configuration."""

        return ExecutionRequest(
            request_id=str(uuid4()),
            workload_id=workload_id,
            shots=shots,
            execution_mode=execution_mode,
            # backend_name=self.config.backend.backend_name,
            backend_name=(self.config.backend.backend_name if execution_mode != ExecutionMode.CLASSICAL else None),
            seed=self.config.runtime.random_seed,
            timeout_s=self.config.runtime.execution_timeout_s,
        )

    def _execute(
        self,
        backend: QuantumBackendInterface,
        request: ExecutionRequest,
        circuit: Any,
    ) -> ExecutionResult:
        """Execute a circuit and normalize backend exceptions."""

        try:
            result = backend.execute(request, circuit)

        except TimeoutError as exc:
            raise ExecutionTimeoutError(
                "Backend execution exceeded its timeout.",
                timeout_s=request.timeout_s,
                request_id=request.request_id,
            ) from exc

        except (BackendError, ExecutionTimeoutError):
            raise

        except Exception as exc:
            raise BackendExecutionError(
                "Unexpected backend execution failure.",
                backend_name=request.backend_name,
                retryable=False,
                details={"cause": str(exc)},
            ) from exc

        if result is None:
            raise BackendExecutionError(
                "Backend returned no execution result.",
                backend_name=request.backend_name,
            )

        if result.status != ExecutionStatus.COMPLETED:
            raise BackendExecutionError(
                "Backend execution did not complete successfully.",
                backend_name=request.backend_name,
                details={
                    "status": str(result.status),
                    "error_message": result.error_message,
                },
            )

        return result

    @staticmethod
    def _combine_quality(
        statistical: QualityEstimate,
        application: QualityEstimate,
    ) -> QualityEstimate:
        """
        Combine statistical and application-level quality estimates.

        Non-None application values take precedence when both estimates
        provide the same field. Metadata from both estimates is retained.
        """

        if not isinstance(statistical, QualityEstimate):
            raise RuntimeExecutionError(
                "Profiler returned an invalid quality estimate."
            )

        if not isinstance(application, QualityEstimate):
            raise RuntimeExecutionError(
                "Workload returned an invalid quality estimate."
            )

        combined = {}

        for field in fields(QualityEstimate):
            name = field.name

            if name == "metadata":
                continue

            application_value = getattr(application, name)
            statistical_value = getattr(statistical, name)

            combined[name] = (
                application_value
                if application_value is not None
                else statistical_value
            )

        metadata = dict(statistical.metadata)
        metadata.update(application.metadata)

        combined["metadata"] = metadata

        return QualityEstimate(**combined)
