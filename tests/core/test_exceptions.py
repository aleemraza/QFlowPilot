
import pytest

from qflowpilot.core.exceptions import (
    QFlowPilotError,
    BackendError,
    BackendUnavailableError,
    BackendExecutionError,
    InvalidWorkloadError,
    UnsupportedWorkloadError,
    ExecutionTimeoutError,
    QualityViolationError,
    RuntimeExecutionError,
)


def test_base_exception():
    error = QFlowPilotError("General error")

    assert str(error) == "General error"
    assert error.to_dict()["error_type"] == "QFlowPilotError"


def test_exception_details():
    error = QFlowPilotError(
        "Test error",
        details={"reason": "testing"},
    )

    assert error.details["reason"] == "testing"


def test_backend_unavailable():
    error = BackendUnavailableError(
        "Backend unavailable",
        backend_name="ibm_brisbane",
        retryable=True,
    )

    assert isinstance(error, BackendError)
    assert isinstance(error, QFlowPilotError)
    assert error.backend_name == "ibm_brisbane"
    assert error.retryable is True


def test_backend_execution_error():
    error = BackendExecutionError(
        "Circuit execution failed",
        backend_name="aer_simulator",
    )

    assert error.backend_name == "aer_simulator"


def test_invalid_workload():
    error = InvalidWorkloadError(
        "Invalid circuit",
        workload_id="workload_001",
    )

    assert error.workload_id == "workload_001"
    assert isinstance(error, QFlowPilotError)


def test_unsupported_workload():
    error = UnsupportedWorkloadError(
        "Unsupported workload",
        workload_id="workload_002",
    )

    assert error.workload_id == "workload_002"


def test_execution_timeout():
    error = ExecutionTimeoutError(
        "Execution timed out",
        timeout_s=300,
        request_id="request_001",
    )

    assert error.timeout_s == 300
    assert error.request_id == "request_001"


def test_quality_violation():
    error = QualityViolationError(
        "Quality threshold not met",
        metric="success_probability",
        observed_value=0.65,
        threshold=0.80,
    )

    assert error.metric == "success_probability"
    assert error.observed_value == 0.65
    assert error.threshold == 0.80


def test_runtime_execution_error():
    error = RuntimeExecutionError(
        "Runtime failed",
        component="execution_engine",
        request_id="request_001",
    )

    assert error.component == "execution_engine"
    assert error.request_id == "request_001"


def test_exception_serialization():
    error = QualityViolationError(
        "Quality not met",
        metric="success_probability",
        observed_value=0.65,
        threshold=0.80,
    )

    data = error.to_dict()

    assert data["error_type"] == "QualityViolationError"
    assert data["details"]["metric"] == "success_probability"
    assert data["details"]["threshold"] == 0.80


def test_catch_all_qflowpilot_errors():
    errors = [
        BackendUnavailableError("Backend offline"),
        InvalidWorkloadError("Invalid workload"),
        ExecutionTimeoutError("Timeout"),
        QualityViolationError("Quality violation"),
        RuntimeExecutionError("Runtime failure"),
    ]

    for error in errors:
        assert isinstance(error, QFlowPilotError)


def test_preserve_original_exception():
    original = ValueError("Original error")

    try:
        raise RuntimeExecutionError("Runtime failed") from original
    except RuntimeExecutionError as error:
        assert error.__cause__ is original
