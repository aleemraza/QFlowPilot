
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from qflowpilot.adapters.base_adapter import BaseBackendAdapter
from qflowpilot.core.models import (
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)
from qflowpilot.core.exceptions import (
    BackendExecutionError,
    BackendUnavailableError,
)


class IonQAdapter(BaseBackendAdapter):
    """
    IonQ backend adapter for QFlowPilot.

    Supported targets:
        1. ideal_simulator
        2. forte_noisy_simulator
        3. aria_noisy_simulator
        4. forte_qpu

    The API token must be supplied by the application.
    This adapter does not read environment variables or .env files.
    """

    TARGET_CONFIGS = {
        "ideal_simulator": {
            "backend_name": "ionq_simulator",
            "execution_mode": ExecutionMode.IDEAL_SIMULATOR,
            "noise_model": None,
            "simulator": True,
        },
        "forte_noisy_simulator": {
            "backend_name": "ionq_simulator",
            "execution_mode": ExecutionMode.NOISY_SIMULATOR,
            "noise_model": "forte-1",
            "simulator": True,
        },
        "aria_noisy_simulator": {
            "backend_name": "ionq_simulator",
            "execution_mode": ExecutionMode.NOISY_SIMULATOR,
            "noise_model": "aria-1",
            "simulator": True,
        },
        "forte_qpu": {
            "backend_name": "ionq_qpu.forte-1",
            "execution_mode": ExecutionMode.QUANTUM_HARDWARE,
            "noise_model": None,
            "simulator": False,
        },
    }

    def __init__(
        self,
        target: str,
        token: Optional[str] = None,
        provider: Optional[Any] = None,
        backend: Optional[Any] = None,
    ) -> None:

        if target not in self.TARGET_CONFIGS:
            raise ValueError(
                f"Unsupported IonQ target '{target}'. "
                f"Supported targets: {list(self.TARGET_CONFIGS)}"
            )

        config = self.TARGET_CONFIGS[target]

        self.target = target
        self.noise_model = config["noise_model"]
        self.execution_mode = config["execution_mode"]
        self.is_simulator = config["simulator"]

        self._provider = provider
        self._backend = backend

        super().__init__(
            backend_name=config["backend_name"],
            backend_type="ionq_simulator" if self.is_simulator else "ionq_qpu",
            backend_version="qiskit-ionq",
            available=False,
        )

        # Create the provider only when a backend/provider was not injected.
        if self._backend is None:

            if self._provider is None:

                if not token:
                    raise ValueError(
                        "An IonQ API token is required when no provider "
                        "or backend is supplied."
                    )

                try:
                    from qiskit_ionq import IonQProvider

                    self._provider = IonQProvider(token=token)

                except Exception as exc:
                    raise BackendUnavailableError(
                        message=f"Could not initialize IonQ provider: {exc}",
                        backend_name=self.backend_name,
                        retryable=True,
                    ) from exc

            try:
                self._backend = self._provider.get_backend(
                    self.backend_name
                )

            except Exception as exc:
                raise BackendUnavailableError(
                    message=(
                        f"Could not connect to IonQ backend "
                        f"'{self.backend_name}': {exc}"
                    ),
                    backend_name=self.backend_name,
                    retryable=True,
                ) from exc

        # Configure noisy simulator targets.
        # The ideal simulator uses the default ideal noise configuration.
        if self.is_simulator and self.noise_model is not None:
            try:
                self._backend.set_options(
                    noise_model=self.noise_model
                )
            except Exception as exc:
                raise BackendUnavailableError(
                    message=(
                        f"Could not configure IonQ noise model "
                        f"'{self.noise_model}': {exc}"
                    ),
                    backend_name=self.backend_name,
                    retryable=False,
                ) from exc

        self._available = self.is_available()

    # ---------------------------------------------------------
    # Availability
    # ---------------------------------------------------------

    def is_available(self) -> bool:
        if self._backend is None:
            return False

        try:
            return bool(self._backend.status())
        except Exception:
            return False

    # ---------------------------------------------------------
    # Backend information
    # ---------------------------------------------------------

    def get_backend_info(self) -> dict[str, Any]:

        info = super().get_backend_info()

        info.update({
            "provider": "IonQ",
            "target": self.target,
            "noise_model": self.noise_model,
            "is_simulator": self.is_simulator,
            "execution_mode": self.execution_mode.value,
            "num_qubits": getattr(
                self._backend,
                "num_qubits",
                None,
            ),
        })

        return info

    # ---------------------------------------------------------
    # Circuit validation
    # ---------------------------------------------------------

    def _validate_request(
        self,
        request: ExecutionRequest,
        circuit: Any,
    ) -> None:

        from qiskit import QuantumCircuit

        if not isinstance(circuit, QuantumCircuit):
            raise TypeError(
                "circuit must be a Qiskit QuantumCircuit."
            )

        if request.execution_mode != self.execution_mode:
            raise ValueError(
                f"Execution mode mismatch. "
                f"Adapter mode: {self.execution_mode.value}, "
                f"request mode: {request.execution_mode.value}."
            )

        if (
            request.backend_name is not None
            and request.backend_name != self.backend_name
        ):
            raise ValueError(
                f"Backend mismatch. Expected '{self.backend_name}', "
                f"received '{request.backend_name}'."
            )

        if not isinstance(request.shots, int) or isinstance(request.shots, bool):
            raise ValueError("shots must be a positive integer.")

        if request.shots <= 0:
            raise ValueError("shots must be greater than zero.")

        if self.target == "ideal_simulator" and request.shots != 1:
            raise ValueError(
                "IonQ's ideal state-vector simulator supports a maximum "
                "of one shot. Set request.shots=1. Use a noisy simulator "
                "for sampled shot-based execution."
            )

        if circuit.num_qubits == 0:
            raise ValueError("Circuit must contain at least one qubit.")

        if circuit.num_clbits == 0:
            raise ValueError(
                "Circuit must contain classical bits for measurement."
            )

        if not any(
            instruction.operation.name == "measure"
            for instruction in circuit.data
        ):
            raise ValueError(
                "Circuit must contain at least one measurement."
            )

        if circuit.parameters:
            raise ValueError(
                "Circuit contains unbound parameters. "
                "Bind all parameters before execution."
            )

    # ---------------------------------------------------------
    # Result probability extraction
    # ---------------------------------------------------------

    @staticmethod
    def _extract_probabilities(job: Any) -> dict[str, float]:

        raw = job.get_probabilities()

        # qiskit-ionq 1.1.1 documents a tuple containing
        # counts and probabilities for IonQJob.get_probabilities().
        if isinstance(raw, tuple) and len(raw) == 2:
            raw = raw[1]

        if not isinstance(raw, dict):
            raise BackendExecutionError(
                message="IonQ returned an unexpected probability format.",
                backend_name="ionq_simulator",
                retryable=False,
            )

        return {
            str(bitstring): float(probability)
            for bitstring, probability in raw.items()
        }

    # ---------------------------------------------------------
    # Execute circuit
    # ---------------------------------------------------------

    def execute(
        self,
        request: ExecutionRequest,
        circuit: Any,
    ) -> ExecutionResult:

        self._ensure_available()
        self._validate_request(request, circuit)

        from qiskit import transpile

        submitted_at = datetime.now(timezone.utc)
        started_at = None
        completed_at = None
        job = None

        try:
            # IonQ recommends optimization level 0 or 1.
            isa_circuit = transpile(
                circuit,
                backend=self._backend,
                optimization_level=1,
            )

            # Submit circuit to IonQ.
            job = self._backend.run(
                isa_circuit,
                shots=request.shots,
            )

            started_at = datetime.now(timezone.utc)

            # Wait for the job to finish.
            ionq_result = job.result(
                timeout=request.timeout_s
            )

            completed_at = datetime.now(timezone.utc)

            # Obtain the provider job ID.
            job_id = None
            try:
                job_id = job.job_id()
            except Exception:
                pass

            # Preserve ideal simulator probabilities separately.
            counts = {}
            probabilities = None

            if self.target == "ideal_simulator":
                probabilities = self._extract_probabilities(job)
            else:
                counts = ionq_result.get_counts()

                counts = {
                    str(bitstring): int(count)
                    for bitstring, count in counts.items()
                }

            metadata = {
                "provider": "IonQ",
                "target": self.target,
                "noise_model": self.noise_model,
                "job_id": job_id,
                "num_qubits": circuit.num_qubits,
                "num_clbits": circuit.num_clbits,
                "transpilation_optimization_level": 1,
                "seed_requested": request.seed,
                "seed_applied": False,
                "seed_note": (
                    "The simulator seed is not applied by this adapter "
                    "to IonQ cloud execution."
                ),
                "is_simulator": self.is_simulator,
            }

            if probabilities is not None:
                metadata["probabilities"] = probabilities

            return ExecutionResult(
                result_id=job_id or request.request_id,
                request_id=request.request_id,
                status=ExecutionStatus.COMPLETED,
                counts=counts,
                shots=request.shots,
                backend_name=self.backend_name,
                execution_mode=self.execution_mode,
                submitted_at=submitted_at,
                started_at=started_at,
                completed_at=completed_at,
                metadata=metadata,
            )

        except (ValueError, TypeError):
            raise

        except Exception as exc:
            raise BackendExecutionError(
                message=f"IonQ execution failed: {exc}",
                backend_name=self.backend_name,
                retryable=True,
            ) from exc
