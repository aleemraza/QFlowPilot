
"""
Abstract interfaces for QFlowPilot components.

These interfaces define communication contracts between:
- Quantum execution backends
- Application workloads
- Profilers
- Runtime policies
- Result validators

The interfaces are backend-independent and do not import Qiskit,
Aer, IBM Quantum, or other execution frameworks.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from .models import (
    CircuitProfile,
    ExecutionRequest,
    ExecutionResult,
    QualityEstimate,
    RuntimeDecision,
    WorkloadSpec,
)


# ---------------------------------------------------------
# 1. Quantum backend interface
# ---------------------------------------------------------

class QuantumBackendInterface(ABC):
    """
    Common interface for quantum and classical execution backends.

    Implementations:
        - AerIdealAdapter
        - AerNoisyAdapter
        - IBMAdapter
        - ClassicalAdapter
    """

    @abstractmethod
    def execute(
        self,
        request: ExecutionRequest,
        circuit: Any,
    ) -> ExecutionResult:
        """
        Execute a circuit and return a standardized result.

        Args:
            request: Execution configuration, including shots
                     and execution mode.
            circuit: Backend-compatible circuit object.

        Returns:
            ExecutionResult containing counts, status,
            timing information and backend metadata.
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check whether the backend is available for execution.

        Returns:
            True if available, otherwise False.
        """
        raise NotImplementedError

    @abstractmethod
    def get_backend_info(self) -> Dict[str, Any]:
        """
        Return backend information.

        Examples:
            backend name, backend type, qubit capacity,
            and supported features.
        """
        raise NotImplementedError


# ---------------------------------------------------------
# 2. Workload interface
# ---------------------------------------------------------

class WorkloadInterface(ABC):
    """
    Common interface for application workloads.

    Implementations:
        - QAOA Max-Cut workload
        - VQE workload
        - Cellular localization workload
    """

    @abstractmethod
    def get_spec(self) -> WorkloadSpec:
        """
        Return the workload specification.

        The specification identifies the workload, algorithm,
        application and execution pattern.
        """
        raise NotImplementedError

    @abstractmethod
    def build_circuit(self) -> Any:
        """
        Construct and return the workload's quantum circuit.

        The returned object is intentionally typed as Any
        to avoid coupling the core to Qiskit.
        """
        raise NotImplementedError

    @abstractmethod
    def evaluate_result(
        self,
        result: ExecutionResult,
    ) -> QualityEstimate:
        """
        Evaluate execution results at the application level.

        For example:
            QAOA: objective value and solution quality.
            VQE: estimated energy and energy error.
            Localization: localization error or accuracy.

        This method evaluates application quality; it does
        not decide whether more shots should be executed.
        """
        raise NotImplementedError


# ---------------------------------------------------------
# 3. Profiler interface
# ---------------------------------------------------------

class ProfilerInterface(ABC):
    """
    Common interface for workload and execution profiling.

    Profilers collect circuit characteristics and estimate
    the quality of execution results.
    """

    @abstractmethod
    def profile_circuit(
        self,
        circuit: Any,
    ) -> CircuitProfile:
        """
        Analyze the circuit structure.

        Expected measurements:
            - Number of qubits
            - Circuit depth
            - Total gate count
            - Two-qubit gate count
            - Gate distribution
        """
        raise NotImplementedError

    @abstractmethod
    def estimate_quality(
        self,
        result: ExecutionResult,
        workload: WorkloadSpec,
    ) -> QualityEstimate:
        """
        Estimate statistical and measurement-related quality.

        The implementation may calculate:
            - Expectation value
            - Variance
            - Standard error
            - Confidence interval
            - Success probability, where applicable

        Application-specific quality can be supplied by
        the workload's evaluate_result() method.
        """
        raise NotImplementedError


# ---------------------------------------------------------
# 4. Runtime policy interface
# ---------------------------------------------------------

class PolicyInterface(ABC):
    """
    Common interface for runtime decision policies.

    Implementations:
        - FixedShotPolicy
        - AdaptiveShotPolicy
        - QualityAwarePolicy
        - FallbackPolicy
    """

    @abstractmethod
    def decide(
        self,
        workload: WorkloadSpec,
        profile: CircuitProfile,
        quality: QualityEstimate,
        current_shots: int,
    ) -> RuntimeDecision:
        """
        Recommend the next runtime action.

        Possible decisions:
            - Accept the result
            - Allocate additional shots
            - Retry execution
            - Use classical fallback
            - Wait
            - Reject the result
            - Terminate execution

        This method recommends an action. The runtime
        controller is responsible for carrying it out.
        """
        raise NotImplementedError


# ---------------------------------------------------------
# 5. Validator interface
# ---------------------------------------------------------

class ValidatorInterface(ABC):
    """
    Common interface for execution and quality validation.

    Implementations:
        - StatisticalValidator
        - ApplicationValidator
        - Combined result validator
    """

    @abstractmethod
    def validate_execution(
        self,
        result: ExecutionResult,
        request: ExecutionRequest,
    ) -> bool:
        """
        Check whether the execution result is valid.

        Examples:
            - Execution completed successfully.
            - Returned measurement counts are valid.
            - Returned shot count matches the request,
              where the backend reports it.
        """
        raise NotImplementedError

    @abstractmethod
    def validate_quality(
        self,
        quality: QualityEstimate,
        workload: WorkloadSpec,
    ) -> bool:
        """
        Check whether the estimated quality satisfies
        the workload's configured quality requirements.

        The concrete validator defines the applicable
        quality criteria for each workload.
        """
        raise NotImplementedError
