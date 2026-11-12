
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from statistics import mean
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from qflowpilot.core.models import ExecutionResult
@dataclass
class ExecutionLatencyProfile:
    """Latency measurements for one quantum execution."""

    result_id: Optional[str] = None
    request_id: Optional[str] = None
    backend_name: Optional[str] = None

    queue_latency_s: Optional[float] = None
    qpu_execution_latency_s: Optional[float] = None
    end_to_end_latency_s: Optional[float] = None

    submitted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None

    successful: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LatencyBreakdown:
    """Breakdown of end-to-end latency into execution stages."""

    compilation_time_s: float
    queue_time_s: float
    qpu_execution_time_s: float
    postprocessing_time_s: float
    communication_time_s: float

    total_latency_s: float
    observed_e2e_latency_s: Optional[float] = None
    decomposition_error_s: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkloadLatencyProfile:
    """Latency measurements for batch or iterative workloads."""

    workload_id: Optional[str]
    workload_type: str

    total_latency_s: float
    number_of_executions: int

    average_execution_latency_s: Optional[float] = None
    maximum_execution_latency_s: Optional[float] = None
    minimum_execution_latency_s: Optional[float] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


class LatencyProfiler:
    """
    Measure execution and workload latency for QFlowPilot.

    Implemented equations
    ---------------------
    Equation 11: Queue latency
        T_queue = t_start - t_submit

    Equation 12: QPU execution latency
        T_QPU = t_finish - t_start

    Equation 13: End-to-end latency
        T_E2E = t_return - t_submit

    Equation 14: Latency decomposition
        T_E2E = T_compile + T_queue + T_QPU
                + T_post + T_communication

    Equation 15: Iterative workload latency
        T_iterative = sum(T_round_r)

    Equation 16: Batch makespan
        T_batch = max(t_completion_i) - t_batch_start

    Important:
    - Timestamps must use compatible time zones.
    - Provider timestamps may not expose every execution stage.
    - Missing stage durations must not be invented.
    - completed_at is used as a return-time proxy when returned_at
      is not supplied separately.
    """

    def __init__(self) -> None:
        pass

    # ---------------------------------------------------------
    # Equation 11, 12 and 13: Profile one execution
    # ---------------------------------------------------------

    def profile_execution(
        self,
        result: ExecutionResult,
    ) -> ExecutionLatencyProfile:
        """
        Calculate queue, QPU and end-to-end latency.

        Uses:
            submitted_at
            started_at
            completed_at

        An optional metadata["returned_at"] timestamp can represent
        the time when the result became available to the application.
        """

        if not isinstance(result, ExecutionResult):
            raise TypeError(
                "result must be an ExecutionResult instance."
            )

        submitted_at = result.submitted_at
        started_at = result.started_at
        finished_at = result.completed_at

        returned_at = result.metadata.get("returned_at")
        if returned_at is None:
            returned_at = finished_at

        queue_latency = None
        qpu_latency = None
        e2e_latency = None

        if submitted_at is not None and started_at is not None:
            queue_latency = self._elapsed_seconds(
                submitted_at,
                started_at,
                "queue latency",
            )

        if started_at is not None and finished_at is not None:
            qpu_latency = self._elapsed_seconds(
                started_at,
                finished_at,
                "QPU execution latency",
            )

        if submitted_at is not None and returned_at is not None:
            e2e_latency = self._elapsed_seconds(
                submitted_at,
                returned_at,
                "end-to-end latency",
            )

        successful = (
            getattr(result.status, "value", result.status) == "completed"
        )

        return ExecutionLatencyProfile(
            result_id=result.result_id,
            request_id=result.request_id,
            backend_name=result.backend_name,
            queue_latency_s=queue_latency,
            qpu_execution_latency_s=qpu_latency,
            end_to_end_latency_s=e2e_latency,
            submitted_at=submitted_at,
            started_at=started_at,
            finished_at=finished_at,
            returned_at=returned_at,
            successful=successful,
            metadata={
                "timestamp_source": "ExecutionResult",
                "return_timestamp_source": (
                    "metadata.returned_at"
                    if result.metadata.get("returned_at") is not None
                    else "completed_at"
                ),
                "queue_latency_available": queue_latency is not None,
                "qpu_latency_available": qpu_latency is not None,
                "e2e_latency_available": e2e_latency is not None,
            },
        )

    # ---------------------------------------------------------
    # Equation 14: Latency decomposition
    # ---------------------------------------------------------

    def profile_latency_breakdown(
        self,
        queue_time_s: float,
        qpu_execution_time_s: float,
        compilation_time_s: float = 0.0,
        postprocessing_time_s: float = 0.0,
        communication_time_s: float = 0.0,
        observed_e2e_latency_s: Optional[float] = None,
    ) -> LatencyBreakdown:
        """
        Calculate the additive latency decomposition.

        All stage durations must be non-negative.

        Optional observed_e2e_latency_s allows comparison between
        the sum of measured stages and the observed total latency.

        If stages overlap, this additive decomposition is not valid
        without critical-path accounting.
        """

        stages = {
            "compilation_time_s": compilation_time_s,
            "queue_time_s": queue_time_s,
            "qpu_execution_time_s": qpu_execution_time_s,
            "postprocessing_time_s": postprocessing_time_s,
            "communication_time_s": communication_time_s,
        }

        for name, value in stages.items():
            stages[name] = self._validate_duration(value, name)

        if observed_e2e_latency_s is not None:
            observed_e2e_latency_s = self._validate_duration(
                observed_e2e_latency_s,
                "observed_e2e_latency_s",
            )

        total = sum(stages.values())

        decomposition_error = None
        if observed_e2e_latency_s is not None:
            decomposition_error = total - observed_e2e_latency_s

        return LatencyBreakdown(
            compilation_time_s=stages["compilation_time_s"],
            queue_time_s=stages["queue_time_s"],
            qpu_execution_time_s=stages["qpu_execution_time_s"],
            postprocessing_time_s=stages["postprocessing_time_s"],
            communication_time_s=stages["communication_time_s"],
            total_latency_s=total,
            observed_e2e_latency_s=observed_e2e_latency_s,
            decomposition_error_s=decomposition_error,
            metadata={
                "decomposition_method": "additive_stage_durations",
                "stages_assumed_non_overlapping": True,
                "all_stage_values_supplied": True,
                "observed_latency_comparison_available": (
                    observed_e2e_latency_s is not None
                ),
            },
        )

    # ---------------------------------------------------------
    # Equation 15: Iterative workload latency
    # ---------------------------------------------------------

    def profile_iterative(
        self,
        round_latencies_s: Sequence[float],
        workload_id: Optional[str] = None,
    ) -> WorkloadLatencyProfile:
        """
        Calculate total latency for sequential iterative rounds.

        Each value represents the elapsed duration of one round.

        Equation 15:
            T_iterative = sum(T_r)

        This method assumes rounds execute sequentially.
        """

        if (
            not isinstance(round_latencies_s, Sequence)
            or isinstance(round_latencies_s, (str, bytes))
            or len(round_latencies_s) == 0
        ):
            raise ValueError(
                "round_latencies_s must be a non-empty sequence."
            )

        durations = [
            self._validate_duration(value, f"round {index} latency")
            for index, value in enumerate(round_latencies_s)
        ]

        total_latency = sum(durations)

        return WorkloadLatencyProfile(
            workload_id=workload_id,
            workload_type="iterative",
            total_latency_s=total_latency,
            number_of_executions=len(durations),
            average_execution_latency_s=mean(durations),
            maximum_execution_latency_s=max(durations),
            minimum_execution_latency_s=min(durations),
            metadata={
                "round_latencies_s": durations,
                "execution_order": "sequential",
                "aggregation_method": "sum",
            },
        )

    # ---------------------------------------------------------
    # Equation 16: Batch makespan
    # ---------------------------------------------------------

    def profile_batch(
        self,
        batch_start: datetime,
        completion_times: Sequence[datetime],
        workload_id: Optional[str] = None,
    ) -> WorkloadLatencyProfile:
        """
        Calculate batch makespan.

        Equation 16:
            T_batch = max(t_completion_i) - t_batch_start

        Completion timestamps must represent the completion of
        each batch job, not merely its QPU execution finish if
        the batch result is returned later.
        """

        if not isinstance(batch_start, datetime):
            raise TypeError("batch_start must be a datetime.")

        if (
            not isinstance(completion_times, Sequence)
            or isinstance(completion_times, (str, bytes))
            or len(completion_times) == 0
        ):
            raise ValueError(
                "completion_times must be a non-empty sequence."
            )

        for index, timestamp in enumerate(completion_times):
            if not isinstance(timestamp, datetime):
                raise TypeError(
                    f"completion_times[{index}] must be a datetime."
                )

        completion_durations = [
            self._elapsed_seconds(
                batch_start,
                timestamp,
                f"batch job {index} completion time",
            )
            for index, timestamp in enumerate(completion_times)
        ]

        makespan = max(completion_durations)

        return WorkloadLatencyProfile(
            workload_id=workload_id,
            workload_type="batch",
            total_latency_s=makespan,
            number_of_executions=len(completion_times),
            average_execution_latency_s=mean(completion_durations),
            maximum_execution_latency_s=max(completion_durations),
            minimum_execution_latency_s=min(completion_durations),
            metadata={
                "batch_start": batch_start,
                "completion_times": list(completion_times),
                "completion_durations_s": completion_durations,
                "aggregation_method": "maximum_completion_time",
            },
        )

    # ---------------------------------------------------------
    # Multiple execution analysis
    # ---------------------------------------------------------

    def profile_multiple(
        self,
        results: Sequence[ExecutionResult],
    ) -> List[ExecutionLatencyProfile]:
        """Profile multiple execution results."""

        if not isinstance(results, Sequence):
            raise TypeError("results must be a sequence.")

        return [
            self.profile_execution(result)
            for result in results
        ]

    # ---------------------------------------------------------
    # Latency statistics
    # ---------------------------------------------------------

    def summarize(
        self,
        profiles: Sequence[ExecutionLatencyProfile],
        metric: str = "end_to_end_latency_s",
    ) -> Dict[str, Any]:
        """
        Summarize execution latency.

        Supported metrics:
            queue_latency_s
            qpu_execution_latency_s
            end_to_end_latency_s

        Percentiles use linear interpolation.
        """

        supported_metrics = {
            "queue_latency_s",
            "qpu_execution_latency_s",
            "end_to_end_latency_s",
        }

        if metric not in supported_metrics:
            raise ValueError(
                f"Unsupported metric {metric!r}. "
                f"Choose from {sorted(supported_metrics)}."
            )

        values = []

        for profile in profiles:
            value = getattr(profile, metric)

            if value is not None:
                values.append(
                    self._validate_duration(value, metric)
                )

        if not values:
            return {
                "metric": metric,
                "count": 0,
                "average_s": None,
                "minimum_s": None,
                "maximum_s": None,
                "p50_s": None,
                "p95_s": None,
                "p99_s": None,
            }

        return {
            "metric": metric,
            "count": len(values),
            "average_s": mean(values),
            "minimum_s": min(values),
            "maximum_s": max(values),
            "p50_s": self._percentile(values, 50),
            "p95_s": self._percentile(values, 95),
            "p99_s": self._percentile(values, 99),
        }

    # ---------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------

    @staticmethod
    def _validate_duration(value: float, name: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a finite non-negative number.")

        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{name} must be a finite non-negative number."
            ) from exc

        if not math.isfinite(number) or number < 0:
            raise ValueError(
                f"{name} must be a finite non-negative number."
            )

        return number

    @staticmethod
    def _elapsed_seconds(
        start: datetime,
        end: datetime,
        name: str,
    ) -> float:
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            raise TypeError(
                f"Timestamps for {name} must be datetime instances."
            )

        try:
            duration = (end - start).total_seconds()
        except TypeError as exc:
            raise ValueError(
                f"Timestamps for {name} must have compatible "
                "timezone information."
            ) from exc

        if not math.isfinite(duration) or duration < 0:
            raise ValueError(
                f"Invalid timestamps: {name} cannot be negative."
            )

        return duration

    @staticmethod
    def _percentile(values: Sequence[float], percentile: float) -> float:
        """Calculate percentile using linear interpolation."""

        ordered = sorted(values)

        if len(ordered) == 1:
            return ordered[0]

        position = (len(ordered) - 1) * percentile / 100.0

        lower_index = math.floor(position)
        upper_index = math.ceil(position)

        if lower_index == upper_index:
            return ordered[lower_index]

        fraction = position - lower_index

        return (
            ordered[lower_index]
            + fraction
            * (ordered[upper_index] - ordered[lower_index])
        )
