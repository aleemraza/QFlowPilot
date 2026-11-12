
"""
QFlowPilot: Execution Profiler

Analyzes ExecutionResult objects returned by backend adapters.
It does not submit jobs or control backend execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Sequence

from qflowpilot.core.models import ExecutionResult, ExecutionStatus


@dataclass
class ExecutionProfile:
    """Execution performance measurements for one request."""

    result_id: str
    request_id: str
    backend_name: Optional[str]
    execution_mode: Optional[str]
    status: str

    submitted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    queue_time_s: Optional[float] = None
    execution_time_s: Optional[float] = None
    end_to_end_latency_s: Optional[float] = None

    requested_shots: Optional[int] = None
    observed_shots: Optional[int] = None
    shots_per_second: Optional[float] = None

    successful: bool = False
    failed: bool = False

    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutionProfiler:
    """
    Analyze execution results from QFlowPilot backend adapters.

    The profiler consumes ExecutionResult objects and calculates
    timing, throughput, and execution-status metrics.
    """

    @staticmethod
    def _enum_value(value: Any) -> Optional[str]:
        if value is None:
            return None

        return str(getattr(value, "value", value))

    @staticmethod
    def _duration(
        start: Optional[datetime],
        end: Optional[datetime],
        metric_name: str,
    ) -> Optional[float]:
        """Calculate elapsed seconds between two timestamps."""

        if start is None or end is None:
            return None

        if not isinstance(start, datetime) or not isinstance(end, datetime):
            raise TypeError(
                f"{metric_name} timestamps must be datetime objects."
            )

        try:
            duration = (end - start).total_seconds()
        except TypeError as exc:
            raise ValueError(
                f"Incompatible timestamps for {metric_name}. "
                "Check timezone awareness."
            ) from exc

        if duration < 0:
            raise ValueError(
                f"{metric_name} cannot be negative."
            )

        return duration

    @staticmethod
    def _count_observed_shots(counts: dict[str, int]) -> Optional[int]:
        """Calculate the total number of observations in result counts."""

        if not counts:
            return None

        total = 0

        for key, value in counts.items():
            if not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"Invalid measurement count for {key}: {value}"
                )

            total += value

        return total

    def profile_execution(
        self,
        result: ExecutionResult,
    ) -> ExecutionProfile:
        """Generate a performance profile for one execution result."""

        if not isinstance(result, ExecutionResult):
            raise TypeError(
                "result must be an ExecutionResult object."
            )

        queue_time = self._duration(
            result.submitted_at,
            result.started_at,
            "queue_time",
        )

        execution_time = self._duration(
            result.started_at,
            result.completed_at,
            "execution_time",
        )

        end_to_end_latency = self._duration(
            result.submitted_at,
            result.completed_at,
            "end_to_end_latency",
        )

        observed_shots = self._count_observed_shots(
            result.counts
        )

        # Prefer the observed count total when available.
        throughput_shots = (
            observed_shots
            if observed_shots is not None
            else result.shots
        )

        shots_per_second = None

        if (
            execution_time is not None
            and execution_time > 0
            and throughput_shots is not None
        ):
            shots_per_second = (
                throughput_shots / execution_time
            )

        status = self._enum_value(result.status) or "unknown"

        successful = result.status == ExecutionStatus.COMPLETED
        failed = result.status == ExecutionStatus.FAILED

        return ExecutionProfile(
            result_id=result.result_id,
            request_id=result.request_id,
            backend_name=result.backend_name,
            execution_mode=self._enum_value(
                result.execution_mode
            ),
            status=status,

            submitted_at=result.submitted_at,
            started_at=result.started_at,
            completed_at=result.completed_at,

            queue_time_s=queue_time,
            execution_time_s=execution_time,
            end_to_end_latency_s=end_to_end_latency,

            requested_shots=result.shots,
            observed_shots=observed_shots,
            shots_per_second=shots_per_second,

            successful=successful,
            failed=failed,

            error_message=result.error_message,
            metadata=dict(result.metadata),
        )

    def profile_multiple(
        self,
        results: Sequence[ExecutionResult],
    ) -> list[ExecutionProfile]:
        """Profile multiple execution results."""

        if not isinstance(results, (list, tuple)):
            raise TypeError(
                "results must be a list or tuple."
            )

        if not results:
            raise ValueError(
                "results cannot be empty."
            )

        return [
            self.profile_execution(result)
            for result in results
        ]

    @staticmethod
    def summarize(
        profiles: Sequence[ExecutionProfile],
    ) -> dict[str, Any]:
        """Calculate aggregate execution statistics."""

        if not profiles:
            raise ValueError(
                "profiles cannot be empty."
            )

        execution_times = [
            p.execution_time_s
            for p in profiles
            if p.execution_time_s is not None
        ]

        queue_times = [
            p.queue_time_s
            for p in profiles
            if p.queue_time_s is not None
        ]

        latencies = [
            p.end_to_end_latency_s
            for p in profiles
            if p.end_to_end_latency_s is not None
        ]

        successful = sum(p.successful for p in profiles)
        failed = sum(p.failed for p in profiles)

        def average(values: list[float]) -> Optional[float]:
            if not values:
                return None
            return sum(values) / len(values)

        return {
            "total_executions": len(profiles),
            "successful_executions": successful,
            "failed_executions": failed,
            "success_rate": successful / len(profiles),
            "average_queue_time_s": average(queue_times),
            "average_execution_time_s": average(execution_times),
            "average_end_to_end_latency_s": average(latencies),
            "completed_timing_samples": len(execution_times),
        }
