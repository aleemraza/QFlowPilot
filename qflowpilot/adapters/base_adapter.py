
"""
Base backend adapter for QFlowPilot.

All backend adapters should inherit from BaseBackendAdapter.

This module provides common backend metadata and availability
handling without depending on a particular quantum SDK.
"""

from abc import ABC
from typing import Any

from qflowpilot.core.interfaces import QuantumBackendInterface
from qflowpilot.core.exceptions import BackendUnavailableError


class BaseBackendAdapter(QuantumBackendInterface, ABC):
    """
    Common abstract base class for QFlowPilot backend adapters.

    Responsibilities:
        - Store backend identification information.
        - Provide standardized backend metadata.
        - Provide a common availability check.
        - Provide a shared availability guard.

    Subclasses must implement the execute() method inherited
    from QuantumBackendInterface.
    """

    def __init__(
        self,
        backend_name: str,
        backend_type: str,
        backend_version: str | None = None,
        available: bool = True,
    ) -> None:

        if not isinstance(backend_name, str) or not backend_name.strip():
            raise ValueError("backend_name must be a non-empty string.")

        if not isinstance(backend_type, str) or not backend_type.strip():
            raise ValueError("backend_type must be a non-empty string.")

        self.backend_name = backend_name
        self.backend_type = backend_type
        self.backend_version = backend_version
        self._available = available

    def is_available(self) -> bool:
        """
        Return whether the backend is currently available.

        Subclasses may override this method to perform
        backend-specific availability checks.
        """
        return self._available

    def get_backend_info(self) -> dict[str, Any]:
        """
        Return standardized backend information.

        Returns:
            Dictionary containing backend identity,
            type, version, and availability.
        """
        return {
            "backend_name": self.backend_name,
            "backend_type": self.backend_type,
            "backend_version": self.backend_version,
            "is_available": self.is_available(),
            "adapter": self.__class__.__name__,
        }

    def _ensure_available(self) -> None:
        """
        Raise an exception if the backend is unavailable.

        Backend adapters should call this before execution.
        """
        if not self.is_available():
            raise BackendUnavailableError(
                message=f"Backend '{self.backend_name}' is unavailable.",
                backend_name=self.backend_name,
                retryable=True,
            )

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"backend_name='{self.backend_name}', "
            f"backend_type='{self.backend_type}', "
            f"available={self.is_available()})"
        )
