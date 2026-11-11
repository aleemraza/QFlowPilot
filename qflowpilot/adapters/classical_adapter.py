from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from qflowpilot.core.exceptions import BackendExecutionError
from qflowpilot.core.models import (
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)
from .base_adapter import BaseBackendAdapter
class ClassicalAdapter(BaseBackendAdapter):
    """
    Local classical execution adapter for QFlowPilot.

    The circuit argument must be a callable accepting an
    ExecutionRequest and returning an application-level result.

    The classical output is stored in ExecutionResult.metadata,
    because a classical result is not necessarily a measurement
    count distribution.
    """

    def __init__(
        self,
        backend_name: str = "local_classical",
    ) -> None:

        super().__init__(
            backend_name=backend_name,
            backend_type="classical",
            backend_version=None,
            available=True,
        )

    def execute(
        self,
        request: ExecutionRequest,
        circuit: Any,
    ) -> ExecutionResult:
        """Execute a classical fallback computation."""

        self._ensure_available()

        if request.execution_mode != ExecutionMode.CLASSICAL:
            raise ValueError(
                "ClassicalAdapter requires CLASSICAL execution mode."
            )

        if not callable(circuit):
            raise TypeError(
                "circuit must be a callable classical computation "
                "that accepts an ExecutionRequest."
            )

        submitted_at = datetime.now(timezone.utc)

        try:
            started_at = datetime.now(timezone.utc)

            # Execute the classical fallback.
            classical_output = circuit(request)

            completed_at = datetime.now(timezone.utc)

            return ExecutionResult(
                result_id=str(uuid4()),
                request_id=request.request_id,
                status=ExecutionStatus.COMPLETED,
                counts={},
                shots=None,
                backend_name=self.backend_name,
                execution_mode=ExecutionMode.CLASSICAL,
                submitted_at=submitted_at,
                started_at=started_at,
                completed_at=completed_at,
                error_message=None,
                metadata={
                    "execution_environment": "local_classical",
                    "execution_type": "classical_fallback",
                    "classical_output": classical_output,
                    "classical_output_type": type(
                        classical_output
                    ).__name__,
                    "requested_quantum_shots_ignored": request.shots,
                },
            )

        except Exception as exc:
            raise BackendExecutionError(
                message=f"Classical execution failed: {exc}",
                backend_name=self.backend_name,
                retryable=False,
            ) from exc
