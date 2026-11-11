
"""
Centralized exception definitions for QFlowPilot.

This module provides a consistent exception hierarchy for:
- Backend failures
- Invalid and unsupported workloads
- Execution timeouts
- Quality violations
- Runtime execution failures
"""


class QFlowPilotError(Exception):
    """
    Base exception for all QFlowPilot-specific errors.

    Attributes:
        message: Human-readable error description.
        details: Optional additional error information.
    """

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        """Convert exception information into a dictionary."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# ============================================================
# Backend Exceptions
# ============================================================

class BackendError(QFlowPilotError):
    """Base exception for quantum backend-related failures."""

    def __init__(
        self,
        message: str,
        backend_name: str | None = None,
        retryable: bool = False,
        details: dict | None = None,
    ):
        self.backend_name = backend_name
        self.retryable = retryable

        error_details = details.copy() if details else {}
        error_details.update({
            "backend_name": backend_name,
            "retryable": retryable,
        })

        super().__init__(message, error_details)


class BackendUnavailableError(BackendError):
    """Raised when the requested backend is unavailable."""


class BackendExecutionError(BackendError):
    """Raised when circuit execution fails on a backend."""


# ============================================================
# Workload Exceptions
# ============================================================

class WorkloadError(QFlowPilotError):
    """Base exception for workload-related failures."""

    def __init__(
        self,
        message: str,
        workload_id: str | None = None,
        details: dict | None = None,
    ):
        self.workload_id = workload_id

        error_details = details.copy() if details else {}
        error_details["workload_id"] = workload_id

        super().__init__(message, error_details)


class InvalidWorkloadError(WorkloadError):
    """Raised when workload input or configuration is invalid."""


class UnsupportedWorkloadError(WorkloadError):
    """Raised when a workload type or operation is unsupported."""


# ============================================================
# Execution Exceptions
# ============================================================

class ExecutionTimeoutError(QFlowPilotError):
    """Raised when workload execution exceeds its time limit."""

    def __init__(
        self,
        message: str,
        timeout_s: float | None = None,
        request_id: str | None = None,
        details: dict | None = None,
    ):
        self.timeout_s = timeout_s
        self.request_id = request_id

        error_details = details.copy() if details else {}
        error_details.update({
            "timeout_s": timeout_s,
            "request_id": request_id,
        })

        super().__init__(message, error_details)


# ============================================================
# Quality Exceptions
# ============================================================

class QualityViolationError(QFlowPilotError):
    """
    Raised when an execution result fails quality requirements.

    Examples:
        - Success probability is below the required threshold.
        - Standard error exceeds the allowed limit.
        - Application-level quality is insufficient.
    """

    def __init__(
        self,
        message: str,
        metric: str | None = None,
        observed_value: float | None = None,
        threshold: float | None = None,
        details: dict | None = None,
    ):
        self.metric = metric
        self.observed_value = observed_value
        self.threshold = threshold

        error_details = details.copy() if details else {}
        error_details.update({
            "metric": metric,
            "observed_value": observed_value,
            "threshold": threshold,
        })

        super().__init__(message, error_details)


# ============================================================
# Runtime Exceptions
# ============================================================

class RuntimeExecutionError(QFlowPilotError):
    """Raised when runtime orchestration or execution fails."""

    def __init__(
        self,
        message: str,
        component: str | None = None,
        request_id: str | None = None,
        details: dict | None = None,
    ):
        self.component = component
        self.request_id = request_id

        error_details = details.copy() if details else {}
        error_details.update({
            "component": component,
            "request_id": request_id,
        })

        super().__init__(message, error_details)
