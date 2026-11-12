
from datetime import datetime, timedelta, timezone

import pytest

from qflowpilot.core.models import (
    ExecutionResult,
    ExecutionStatus,
    ExecutionMode,
)
from qflowpilot.profiler.execution_profiler import ExecutionProfiler


@pytest.fixture
def profiler():
    return ExecutionProfiler()


def make_result():
    submitted = datetime(2026, 11, 11, 10, 0, 0, tzinfo=timezone.utc)
    started = submitted + timedelta(seconds=5)
    completed = started + timedelta(seconds=10)

    return ExecutionResult(
        result_id="result_001",
        request_id="request_001",
        status=ExecutionStatus.COMPLETED,
        counts={"00": 500, "11": 524},
        shots=1024,
        backend_name="aer_ideal",
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
        submitted_at=submitted,
        started_at=started,
        completed_at=completed,
    )


def test_execution_timing(profiler):
    profile = profiler.profile_execution(make_result())

    assert profile.queue_time_s == 5
    assert profile.execution_time_s == 10
    assert profile.end_to_end_latency_s == 15


def test_shot_metrics(profiler):
    profile = profiler.profile_execution(make_result())

    assert profile.requested_shots == 1024
    assert profile.observed_shots == 1024
    assert profile.shots_per_second == 102.4


def test_execution_status(profiler):
    profile = profiler.profile_execution(make_result())

    assert profile.successful is True
    assert profile.failed is False
    assert profile.status == "completed"


def test_invalid_result(profiler):
    with pytest.raises(TypeError):
        profiler.profile_execution("invalid")


def test_multiple_results(profiler):
    results = [make_result(), make_result()]

    profiles = profiler.profile_multiple(results)

    assert len(profiles) == 2


def test_empty_results(profiler):
    with pytest.raises(ValueError):
        profiler.profile_multiple([])


def test_summary(profiler):
    results = [make_result(), make_result()]

    profiles = profiler.profile_multiple(results)
    summary = profiler.summarize(profiles)

    assert summary["total_executions"] == 2
    assert summary["successful_executions"] == 2
    assert summary["failed_executions"] == 0
    assert summary["average_queue_time_s"] == 5
    assert summary["average_execution_time_s"] == 10
    assert summary["average_end_to_end_latency_s"] == 15
