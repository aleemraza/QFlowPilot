
"""
Cost estimation for QFlowPilot.

Implements:
    C_total = C_QPU + C_classical + C_communication

Two accounting modes are supported:

1. monetary:
   Uses configurable monetary rates supplied by the application.

2. resource_proxy:
   Uses measured resource quantities and configurable weights to calculate
   an optional normalized resource-consumption score.

Important:
- No provider prices are assumed.
- Pass aggregate measurements, including any retries or mitigation overhead
  that should be included in the estimate.
- Do not pass the same retry or mitigation overhead twice.
- Communication volume is measured in bytes and converted using decimal GB
  (1 GB = 1,000,000,000 bytes).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class CostMode(str, Enum):
    MONETARY = "monetary"
    RESOURCE_PROXY = "resource_proxy"


@dataclass
class CostModelConfig:
    """Configurable monetary rates and resource-proxy weights.

    Monetary rates:
        qpu_cost_per_second:
            Monetary cost per QPU execution second.
        qpu_cost_per_shot:
            Additional monetary cost per submitted shot, if applicable.
        classical_cost_per_cpu_second:
            Monetary cost per classical CPU second.
        communication_cost_per_gb:
            Monetary cost per decimal GB transferred.

    Resource-proxy weights:
        qpu_seconds_weight:
            Resource-score weight per QPU second.
        shots_weight:
            Resource-score weight per shot.
        classical_cpu_seconds_weight:
            Resource-score weight per classical CPU second.
        communication_gb_weight:
            Resource-score weight per decimal GB transferred.

    Set a rate or weight to None when it is unavailable. The estimator will
    not silently assume that an unavailable rate is zero.
    """

    currency: str = "USD"

    qpu_cost_per_second: Optional[float] = None
    qpu_cost_per_shot: Optional[float] = None
    classical_cost_per_cpu_second: Optional[float] = None
    communication_cost_per_gb: Optional[float] = None

    qpu_seconds_weight: Optional[float] = None
    shots_weight: Optional[float] = None
    classical_cpu_seconds_weight: Optional[float] = None
    communication_gb_weight: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.currency or not self.currency.strip():
            raise ValueError("currency must be a non-empty string.")

        rate_fields = (
            "qpu_cost_per_second",
            "qpu_cost_per_shot",
            "classical_cost_per_cpu_second",
            "communication_cost_per_gb",
            "qpu_seconds_weight",
            "shots_weight",
            "classical_cpu_seconds_weight",
            "communication_gb_weight",
        )

        for name in rate_fields:
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative.")


@dataclass
class CostComponent:
    """Cost and resource information for one execution component."""

    name: str
    quantities: Dict[str, float] = field(default_factory=dict)
    monetary_cost: Optional[float] = None
    resource_score: Optional[float] = None
    monetary_available: bool = False
    proxy_available: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostEstimate:
    """Combined cost estimate for a workload or execution."""

    mode: CostMode

    qpu: CostComponent
    classical: CostComponent
    communication: CostComponent

    total_cost: Optional[float] = None
    currency: Optional[str] = None

    total_resource_score: Optional[float] = None

    shots: Optional[int] = None
    monetary_cost_per_shot: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """Whether all three components are available in the selected mode."""
        if self.mode == CostMode.MONETARY:
            return all(
                component.monetary_available
                for component in (
                    self.qpu,
                    self.classical,
                    self.communication,
                )
            )

        return all(
            component.proxy_available
            for component in (
                self.qpu,
                self.classical,
                self.communication,
            )
        )


class CostEstimator:
    """Estimate QPU, classical, and communication costs.

    Example:
        config = CostModelConfig(
            currency="USD",
            qpu_cost_per_second=0.05,
            qpu_cost_per_shot=0.0001,
            classical_cost_per_cpu_second=0.001,
            communication_cost_per_gb=0.02,
        )

        estimator = CostEstimator(config)

        estimate = estimator.estimate(
            qpu_execution_time_s=10.0,
            shots=1000,
            classical_cpu_time_s=2.0,
            communication_bytes=500_000_000,
            mode=CostMode.MONETARY,
        )
    """

    def __init__(
        self,
        config: Optional[CostModelConfig] = None,
    ) -> None:
        self.config = config or CostModelConfig()

    @staticmethod
    def _validate_non_negative(
        name: str,
        value: Optional[float],
    ) -> None:
        if value is not None and value < 0:
            raise ValueError(f"{name} cannot be negative.")

    def _estimate_qpu_monetary(
        self,
        execution_time_s: float,
        shots: int,
    ) -> CostComponent:
        rate_per_second = self.config.qpu_cost_per_second
        rate_per_shot = self.config.qpu_cost_per_shot

        available = (
            rate_per_second is not None
            or rate_per_shot is not None
        )

        cost = None
        if available:
            time_cost = (
                execution_time_s * rate_per_second
                if rate_per_second is not None
                else 0.0
            )
            shot_cost = (
                shots * rate_per_shot
                if rate_per_shot is not None
                else 0.0
            )
            cost = time_cost + shot_cost

        return CostComponent(
            name="qpu",
            quantities={
                "execution_time_s": execution_time_s,
                "shots": float(shots),
            },
            monetary_cost=cost,
            monetary_available=available,
            metadata={
                "cost_per_second": rate_per_second,
                "cost_per_shot": rate_per_shot,
            },
        )

    def _estimate_classical_monetary(
        self,
        cpu_time_s: float,
    ) -> CostComponent:
        rate = self.config.classical_cost_per_cpu_second
        available = rate is not None

        cost = cpu_time_s * rate if available else None

        return CostComponent(
            name="classical",
            quantities={
                "cpu_time_s": cpu_time_s,
            },
            monetary_cost=cost,
            monetary_available=available,
            metadata={
                "cost_per_cpu_second": rate,
            },
        )

    def _estimate_communication_monetary(
        self,
        communication_bytes: float,
    ) -> CostComponent:
        rate = self.config.communication_cost_per_gb
        communication_gb = communication_bytes / 1_000_000_000

        available = rate is not None
        cost = communication_gb * rate if available else None

        return CostComponent(
            name="communication",
            quantities={
                "communication_bytes": communication_bytes,
                "communication_gb": communication_gb,
            },
            monetary_cost=cost,
            monetary_available=available,
            metadata={
                "cost_per_gb": rate,
                "gb_definition": "decimal GB (1,000,000,000 bytes)",
            },
        )

    def _estimate_qpu_proxy(
        self,
        execution_time_s: float,
        shots: int,
    ) -> CostComponent:
        time_weight = self.config.qpu_seconds_weight
        shot_weight = self.config.shots_weight

        available = (
            time_weight is not None
            and shot_weight is not None
        )

        score = None
        if available:
            score = (
                execution_time_s * time_weight
                + shots * shot_weight
            )

        return CostComponent(
            name="qpu",
            quantities={
                "execution_time_s": execution_time_s,
                "shots": float(shots),
            },
            resource_score=score,
            proxy_available=available,
            metadata={
                "seconds_weight": time_weight,
                "shots_weight": shot_weight,
            },
        )

    def _estimate_classical_proxy(
        self,
        cpu_time_s: float,
    ) -> CostComponent:
        weight = self.config.classical_cpu_seconds_weight
        available = weight is not None

        score = cpu_time_s * weight if available else None

        return CostComponent(
            name="classical",
            quantities={
                "cpu_time_s": cpu_time_s,
            },
            resource_score=score,
            proxy_available=available,
            metadata={
                "cpu_seconds_weight": weight,
            },
        )

    def _estimate_communication_proxy(
        self,
        communication_bytes: float,
    ) -> CostComponent:
        weight = self.config.communication_gb_weight
        communication_gb = communication_bytes / 1_000_000_000

        available = weight is not None
        score = communication_gb * weight if available else None

        return CostComponent(
            name="communication",
            quantities={
                "communication_bytes": communication_bytes,
                "communication_gb": communication_gb,
            },
            resource_score=score,
            proxy_available=available,
            metadata={
                "communication_gb_weight": weight,
            },
        )

    def estimate(
        self,
        qpu_execution_time_s: float,
        shots: int,
        classical_cpu_time_s: float = 0.0,
        communication_bytes: float = 0.0,
        mode: CostMode = CostMode.MONETARY,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CostEstimate:
        """Estimate the combined workload cost.

        Args:
            qpu_execution_time_s:
                Aggregate QPU execution time in seconds. Include all attempts
                that should contribute to the workload cost.
            shots:
                Total shots submitted across the execution being estimated.
            classical_cpu_time_s:
                Aggregate classical CPU time in seconds.
            communication_bytes:
                Total communication volume in bytes.
            mode:
                MONETARY or RESOURCE_PROXY.
            metadata:
                Optional workload or measurement information.

        Returns:
            CostEstimate containing component breakdowns and the combined
            total when all required rates or weights are configured.
        """

        self._validate_non_negative(
            "qpu_execution_time_s",
            qpu_execution_time_s,
        )
        self._validate_non_negative(
            "classical_cpu_time_s",
            classical_cpu_time_s,
        )
        self._validate_non_negative(
            "communication_bytes",
            communication_bytes,
        )

        if not isinstance(shots, int) or isinstance(shots, bool) or shots < 0:
            raise ValueError("shots must be a non-negative integer.")

        if isinstance(mode, str):
            try:
                mode = CostMode(mode)
            except ValueError as exc:
                raise ValueError(
                    "mode must be 'monetary' or 'resource_proxy'."
                ) from exc

        if mode == CostMode.MONETARY:
            qpu = self._estimate_qpu_monetary(
                qpu_execution_time_s,
                shots,
            )
            classical = self._estimate_classical_monetary(
                classical_cpu_time_s,
            )
            communication = self._estimate_communication_monetary(
                communication_bytes,
            )

            components = (qpu, classical, communication)
            complete = all(c.monetary_available for c in components)

            total_cost = (
                sum(c.monetary_cost for c in components)
                if complete
                else None
            )

            cost_per_shot = (
                total_cost / shots
                if total_cost is not None and shots > 0
                else None
            )

            return CostEstimate(
                mode=mode,
                qpu=qpu,
                classical=classical,
                communication=communication,
                total_cost=total_cost,
                currency=self.config.currency if complete else None,
                shots=shots,
                monetary_cost_per_shot=cost_per_shot,
                metadata={
                    "accounting_method": "configurable monetary rates",
                    "equation": "C_total = C_QPU + C_classical + C_communication",
                    "missing_components": [
                        c.name for c in components
                        if not c.monetary_available
                    ],
                    **(metadata or {}),
                },
            )

        qpu = self._estimate_qpu_proxy(
            qpu_execution_time_s,
            shots,
        )
        classical = self._estimate_classical_proxy(
            classical_cpu_time_s,
        )
        communication = self._estimate_communication_proxy(
            communication_bytes,
        )

        components = (qpu, classical, communication)
        complete = all(c.proxy_available for c in components)

        total_score = (
            sum(c.resource_score for c in components)
            if complete
            else None
        )

        return CostEstimate(
            mode=mode,
            qpu=qpu,
            classical=classical,
            communication=communication,
            total_resource_score=total_score,
            shots=shots,
            metadata={
                "accounting_method": "weighted resource-consumption proxy",
                "score_interpretation": (
                    "Normalized score defined by configured weights; "
                    "not a monetary price or physical unit."
                ),
                "missing_components": [
                    c.name for c in components
                    if not c.proxy_available
                ],
                **(metadata or {}),
            },
        )

    def estimate_from_execution(
        self,
        qpu_execution_time_s: float,
        shots: int,
        classical_cpu_time_s: float = 0.0,
        communication_bytes: float = 0.0,
        mode: CostMode = CostMode.MONETARY,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CostEstimate:
        """Named convenience wrapper for execution-level cost estimation."""
        return self.estimate(
            qpu_execution_time_s=qpu_execution_time_s,
            shots=shots,
            classical_cpu_time_s=classical_cpu_time_s,
            communication_bytes=communication_bytes,
            mode=mode,
            metadata=metadata,
        )
