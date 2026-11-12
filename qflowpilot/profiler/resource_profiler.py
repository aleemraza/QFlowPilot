
"""
QFlowPilot ResourceProfiler.

Responsibilities:
- Aggregate quantum circuit resource requirements.
- Estimate required shots using Equation 10.
- Compare workload requirements with configured resource limits.
- Optionally calculate observable QPU utilization.

This module estimates and reports resource requirements.
It does not schedule jobs, allocate backend resources, or make runtime decisions.
"""

from dataclasses import dataclass, field
from math import ceil
from statistics import NormalDist
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class ResourceLimits:
    """Resource limits configured by the application or backend."""

    max_qubits: Optional[int] = None
    max_shots: Optional[int] = None
    max_circuit_depth: Optional[int] = None
    max_two_qubit_gates: Optional[int] = None
    max_classical_cpu_time_s: Optional[float] = None
    max_memory_mb: Optional[float] = None

    def __post_init__(self) -> None:
        for name in (
            "max_qubits",
            "max_shots",
            "max_circuit_depth",
            "max_two_qubit_gates",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative.")

        for name in (
            "max_classical_cpu_time_s",
            "max_memory_mb",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative.")


@dataclass
class QuantumResourceRequirements:
    """Estimated quantum resource requirements."""

    num_circuits: int = 0
    required_qubits: int = 0
    total_gates: int = 0
    total_two_qubit_gates: int = 0
    maximum_circuit_depth: int = 0

    shots_per_circuit: Optional[int] = None
    total_requested_shots: Optional[int] = None

    estimated_shots_per_circuit: Optional[int] = None
    estimated_total_required_shots: Optional[int] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClassicalResourceRequirements:
    """Classical resource measurements supplied by the application."""

    cpu_time_s: Optional[float] = None
    memory_mb: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceProfile:
    """Complete resource profile for a workload."""

    workload_id: Optional[str]

    quantum: QuantumResourceRequirements
    classical: ClassicalResourceRequirements

    limits: Optional[ResourceLimits] = None
    violations: List[str] = field(default_factory=list)
    feasible: Optional[bool] = None

    qpu_utilization: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


class ResourceProfiler:
    """Analyze quantum and classical resource requirements."""

    @staticmethod
    def estimate_required_shots(
        variance: float,
        target_precision: float,
        confidence_level: float = 0.95,
    ) -> int:
        """Estimate shots using Equation 10.

        N_required = z_(alpha/2)^2 * variance / target_precision^2

        This estimates the shot count needed for the specified precision
        of an observable mean. It does not guarantee application quality.
        """

        if variance < 0:
            raise ValueError("variance cannot be negative.")

        if target_precision <= 0:
            raise ValueError("target_precision must be greater than zero.")

        if not 0 < confidence_level < 1:
            raise ValueError("confidence_level must be between 0 and 1.")

        z_value = NormalDist().inv_cdf(
            (1.0 + confidence_level) / 2.0
        )

        required = (
            (z_value ** 2) * variance
            / (target_precision ** 2)
        )

        return max(1, ceil(required))

    @staticmethod
    def _get_value(profile: Any, field_name: str, default: Any = 0) -> Any:
        """Read a field from a dataclass-like profile or dictionary."""

        if isinstance(profile, dict):
            return profile.get(field_name, default)

        return getattr(profile, field_name, default)

    @classmethod
    def _aggregate_circuit_profiles(
        cls,
        circuit_profiles: Sequence[Any],
    ) -> Dict[str, int]:
        """Aggregate circuit-level resource measurements."""

        num_circuits = len(circuit_profiles)
        required_qubits = 0
        total_gates = 0
        total_two_qubit_gates = 0
        maximum_depth = 0

        for profile in circuit_profiles:
            required_qubits = max(
                required_qubits,
                int(cls._get_value(profile, "num_qubits", 0)),
            )

            total_gates += int(
                cls._get_value(profile, "total_gates", 0)
            )

            total_two_qubit_gates += int(
                cls._get_value(profile, "two_qubit_gates", 0)
            )

            maximum_depth = max(
                maximum_depth,
                int(cls._get_value(profile, "depth", 0)),
            )

        return {
            "num_circuits": num_circuits,
            "required_qubits": required_qubits,
            "total_gates": total_gates,
            "total_two_qubit_gates": total_two_qubit_gates,
            "maximum_circuit_depth": maximum_depth,
        }

    @staticmethod
    def _validate_optional_non_negative(
        name: str,
        value: Optional[float],
    ) -> None:
        if value is not None and value < 0:
            raise ValueError(f"{name} cannot be negative.")

    @staticmethod
    def calculate_qpu_utilization(
        busy_time_s: float,
        available_time_s: float,
    ) -> float:
        """Calculate observable QPU utilization.

        U_QPU = busy time / available time

        Both times must refer to the same resource and observation period.
        """

        if busy_time_s < 0 or available_time_s < 0:
            raise ValueError("QPU times cannot be negative.")

        if available_time_s == 0:
            raise ValueError("available_time_s must be greater than zero.")

        if busy_time_s > available_time_s:
            raise ValueError(
                "busy_time_s cannot exceed available_time_s."
            )

        return busy_time_s / available_time_s

    def profile_circuits(
        self,
        circuit_profiles: Sequence[Any],
        workload_id: Optional[str] = None,
        shots_per_circuit: Optional[int] = None,
        variance: Optional[float] = None,
        target_precision: Optional[float] = None,
        confidence_level: float = 0.95,
        limits: Optional[ResourceLimits] = None,
        classical_cpu_time_s: Optional[float] = None,
        memory_mb: Optional[float] = None,
        qpu_busy_time_s: Optional[float] = None,
        qpu_available_time_s: Optional[float] = None,
    ) -> ResourceProfile:
        """Create a resource profile from circuit profiles.

        shots_per_circuit:
            Planned shots for each circuit. Total requested shots are
            calculated as shots_per_circuit * number of circuits.

        variance and target_precision:
            When both are supplied, Equation 10 estimates the required
            shots per circuit.

        Classical CPU time and memory:
            Supply measured or independently estimated values. This method
            does not invent these values from circuit gate counts.
        """

        if not circuit_profiles:
            raise ValueError("circuit_profiles cannot be empty.")

        if shots_per_circuit is not None:
            if (
                not isinstance(shots_per_circuit, int)
                or isinstance(shots_per_circuit, bool)
                or shots_per_circuit < 0
            ):
                raise ValueError(
                    "shots_per_circuit must be a non-negative integer."
                )

        self._validate_optional_non_negative(
            "classical_cpu_time_s",
            classical_cpu_time_s,
        )
        self._validate_optional_non_negative(
            "memory_mb",
            memory_mb,
        )

        if (variance is None) != (target_precision is None):
            raise ValueError(
                "Provide both variance and target_precision, or neither."
            )

        aggregate = self._aggregate_circuit_profiles(circuit_profiles)

        num_circuits = aggregate["num_circuits"]

        total_requested_shots = (
            shots_per_circuit * num_circuits
            if shots_per_circuit is not None
            else None
        )

        estimated_shots_per_circuit = None
        estimated_total_required_shots = None

        if variance is not None and target_precision is not None:
            estimated_shots_per_circuit = self.estimate_required_shots(
                variance=variance,
                target_precision=target_precision,
                confidence_level=confidence_level,
            )

            estimated_total_required_shots = (
                estimated_shots_per_circuit * num_circuits
            )

        quantum = QuantumResourceRequirements(
            num_circuits=num_circuits,
            required_qubits=aggregate["required_qubits"],
            total_gates=aggregate["total_gates"],
            total_two_qubit_gates=aggregate["total_two_qubit_gates"],
            maximum_circuit_depth=aggregate["maximum_circuit_depth"],
            shots_per_circuit=shots_per_circuit,
            total_requested_shots=total_requested_shots,
            estimated_shots_per_circuit=estimated_shots_per_circuit,
            estimated_total_required_shots=estimated_total_required_shots,
            metadata={
                "shot_estimation_equation": (
                    "N_required = z^2 * variance / target_precision^2"
                    if estimated_shots_per_circuit is not None
                    else None
                ),
                "confidence_level": confidence_level,
                "variance": variance,
                "target_precision": target_precision,
            },
        )

        classical = ClassicalResourceRequirements(
            cpu_time_s=classical_cpu_time_s,
            memory_mb=memory_mb,
        )

        violations = self._check_limits(
            quantum=quantum,
            classical=classical,
            limits=limits,
        )

        qpu_utilization = None

        if qpu_busy_time_s is not None or qpu_available_time_s is not None:
            if (
                qpu_busy_time_s is None
                or qpu_available_time_s is None
            ):
                raise ValueError(
                    "Provide both qpu_busy_time_s and "
                    "qpu_available_time_s."
                )

            qpu_utilization = self.calculate_qpu_utilization(
                busy_time_s=qpu_busy_time_s,
                available_time_s=qpu_available_time_s,
            )

        return ResourceProfile(
            workload_id=workload_id,
            quantum=quantum,
            classical=classical,
            limits=limits,
            violations=violations,
            feasible=not violations if limits is not None else None,
            qpu_utilization=qpu_utilization,
            metadata={
                "resource_estimation_method": (
                    "aggregated circuit profiles and supplied measurements"
                ),
                "resource_limits_checked": limits is not None,
                "qpu_utilization_available": qpu_utilization is not None,
            },
        )

    def profile_workload(
        self,
        workload_profile: Any,
        **kwargs: Any,
    ) -> ResourceProfile:
        """Create a resource profile from WorkloadProfiler output."""

        circuit_profiles = self._get_value(
            workload_profile,
            "circuit_profiles",
            None,
        )

        if circuit_profiles is None:
            raise ValueError(
                "workload_profile must contain circuit_profiles."
            )

        workload_id = self._get_value(
            workload_profile,
            "workload_id",
            None,
        )

        return self.profile_circuits(
            circuit_profiles=circuit_profiles,
            workload_id=workload_id,
            **kwargs,
        )

    @staticmethod
    def _check_limits(
        quantum: QuantumResourceRequirements,
        classical: ClassicalResourceRequirements,
        limits: Optional[ResourceLimits],
    ) -> List[str]:
        """Check estimated requirements against configured limits."""

        if limits is None:
            return []

        violations: List[str] = []

        if (
            limits.max_qubits is not None
            and quantum.required_qubits > limits.max_qubits
        ):
            violations.append(
                f"Qubit requirement ({quantum.required_qubits}) exceeds "
                f"maximum ({limits.max_qubits})."
            )

        if (
            limits.max_shots is not None
            and quantum.total_requested_shots is not None
            and quantum.total_requested_shots > limits.max_shots
        ):
            violations.append(
                f"Requested shots ({quantum.total_requested_shots}) exceed "
                f"maximum ({limits.max_shots})."
            )

        if (
            limits.max_shots is not None
            and quantum.estimated_total_required_shots is not None
            and quantum.estimated_total_required_shots > limits.max_shots
        ):
            violations.append(
                f"Estimated required shots "
                f"({quantum.estimated_total_required_shots}) exceed "
                f"maximum ({limits.max_shots})."
            )

        if (
            limits.max_circuit_depth is not None
            and quantum.maximum_circuit_depth > limits.max_circuit_depth
        ):
            violations.append(
                f"Circuit depth ({quantum.maximum_circuit_depth}) exceeds "
                f"maximum ({limits.max_circuit_depth})."
            )

        if (
            limits.max_two_qubit_gates is not None
            and quantum.total_two_qubit_gates > limits.max_two_qubit_gates
        ):
            violations.append(
                f"Two-qubit gate count "
                f"({quantum.total_two_qubit_gates}) exceeds "
                f"maximum ({limits.max_two_qubit_gates})."
            )

        if (
            limits.max_classical_cpu_time_s is not None
            and classical.cpu_time_s is not None
            and classical.cpu_time_s > limits.max_classical_cpu_time_s
        ):
            violations.append(
                f"Classical CPU time ({classical.cpu_time_s}) exceeds "
                f"maximum ({limits.max_classical_cpu_time_s})."
            )

        if (
            limits.max_memory_mb is not None
            and classical.memory_mb is not None
            and classical.memory_mb > limits.max_memory_mb
        ):
            violations.append(
                f"Memory requirement ({classical.memory_mb} MB) exceeds "
                f"maximum ({limits.max_memory_mb} MB)."
            )

        return violations
