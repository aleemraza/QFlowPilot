from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4
from qiskit import QuantumCircuit
from qiskit.transpiler import generate_preset_pass_manager
from qflowpilot.core.exceptions import (
    BackendExecutionError,
    BackendUnavailableError,
)
from qflowpilot.core.models import (
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
)

from .base_adapter import BaseBackendAdapter


class IBMAdapter(BaseBackendAdapter):
    """
    IBM Quantum hardware adapter using Qiskit Runtime SamplerV2.

    This adapter submits measured, parameter-bound Qiskit circuits
    to an IBM Quantum backend.

    Credentials can be loaded from a saved QiskitRuntimeService
    account or supplied when constructing the adapter.
    """

    def __init__(
        self,
        backend_name: str,
        channel: Optional[str] = None,
        token: Optional[str] = None,
        instance: Optional[str] = None,
        optimization_level: int = 1,
        service: Any = None,
        backend: Any = None,
    ) -> None:

        if not backend_name or not backend_name.strip():
            raise ValueError("backend_name must be a non-empty string.")

        if optimization_level not in range(4):
            raise ValueError(
                "optimization_level must be between 0 and 3."
            )

        super().__init__(
            backend_name=backend_name,
            backend_type="ibm_quantum_hardware",
            backend_version=None,
            available=False,
        )

        self.optimization_level = optimization_level
        self._service = service
        self._backend = backend
        self._initialization_error = None

        try:
            # Import the IBM package only when this adapter is created.
            from qiskit_ibm_runtime import QiskitRuntimeService

            if self._backend is None:
                if self._service is None:
                    service_options = {}

                    if channel is not None:
                        service_options["channel"] = channel

                    if token is not None:
                        service_options["token"] = token

                    if instance is not None:
                        service_options["instance"] = instance

                    self._service = QiskitRuntimeService(
                        **service_options
                    )

                self._backend = self._service.backend(
                    self.backend_name
                )

            self._available = self._check_backend_operational()

        except Exception as exc:
            self._initialization_error = str(exc)
            self._available = False

    def _check_backend_operational(self) -> bool:
        """Check whether the selected IBM backend is operational."""

        if self._backend is None:
            return False

        try:
            status = self._backend.status()
            return bool(status.operational)

        except Exception:
            return False

    def is_available(self) -> bool:
        """Check current backend availability."""

        if self._backend is None:
            return False

        self._available = self._check_backend_operational()
        return self._available

    def get_backend_info(self) -> dict[str, Any]:
        """Return information about the selected IBM backend."""

        info = super().get_backend_info()

        if self._backend is None:
            info["initialization_error"] = self._initialization_error
            return info

        try:
            status = self._backend.status()

            info.update({
                "backend_name": self.backend_name,
                "num_qubits": self._backend.num_qubits,
                "operational": bool(status.operational),
                "pending_jobs": status.pending_jobs,
                "basis_gates": list(
                    self._backend.operation_names
                ) if hasattr(self._backend, "operation_names") else [],
            })

        except Exception as exc:
            info["information_error"] = str(exc)

        return info

    def execute(
        self,
        request: ExecutionRequest,
        circuit: QuantumCircuit,
    ) -> ExecutionResult:
        """Transpile and execute a circuit on IBM Quantum hardware."""

        if not isinstance(circuit, QuantumCircuit):
            raise TypeError(
                "circuit must be a Qiskit QuantumCircuit."
            )

        if request.execution_mode != ExecutionMode.QUANTUM_HARDWARE:
            raise ValueError(
                "IBMAdapter requires QUANTUM_HARDWARE execution mode."
            )

        if request.backend_name is not None:
            if request.backend_name != self.backend_name:
                raise ValueError(
                    f"Request backend '{request.backend_name}' does not "
                    f"match adapter backend '{self.backend_name}'."
                )

        if circuit.num_clbits == 0 or len(circuit.cregs) != 1:
            raise ValueError(
                "IBMAdapter currently requires measured circuits "
                "with exactly one classical register. Use "
                "circuit.measure_all() for a standard measurement register."
            )

        if circuit.parameters:
            raise ValueError(
                "Circuit contains unbound parameters. Bind parameters "
                "before submitting it to IBM Quantum."
            )

        if not self.is_available():
            raise BackendUnavailableError(
                message=(
                    f"IBM backend '{self.backend_name}' is unavailable."
                ),
                backend_name=self.backend_name,
                retryable=True,
            )

        submitted_at = datetime.now(timezone.utc)

        try:
            from qiskit_ibm_runtime import SamplerV2

            # Stage 1: Transpile for the selected IBM backend.
            pass_manager = generate_preset_pass_manager(
                optimization_level=self.optimization_level,
                backend=self._backend,
            )

            isa_circuit = pass_manager.run(circuit)

            # Stage 2: Create the Runtime Sampler.
            sampler = SamplerV2(mode=self._backend)

            # Stage 3: Submit the job.
            started_at = datetime.now(timezone.utc)

            job = sampler.run(
                [isa_circuit],
                shots=request.shots,
            )

            job_id = job.job_id()

            # Stage 4: Wait for the result.
            primitive_result = job.result(
                timeout=request.timeout_s
            )

            completed_at = datetime.now(timezone.utc)

            # Stage 5: Extract counts from the circuit's register.
            pub_result = primitive_result[0]
            register_name = circuit.cregs[0].name

            bit_array = getattr(
                pub_result.data,
                register_name,
                None,
            )

            if bit_array is None:
                raise RuntimeError(
                    f"Measurement register '{register_name}' "
                    "was not found in the IBM result."
                )

            counts = bit_array.get_counts()

            normalized_counts = {
                str(state): int(count)
                for state, count in counts.items()
            }

            # Stage 6: Return the standardized QFlowPilot result.
            return ExecutionResult(
                result_id=str(uuid4()),
                request_id=request.request_id,
                status=ExecutionStatus.COMPLETED,
                counts=normalized_counts,
                shots=request.shots,
                backend_name=self.backend_name,
                execution_mode=ExecutionMode.QUANTUM_HARDWARE,
                submitted_at=submitted_at,
                started_at=started_at,
                completed_at=completed_at,
                error_message=None,
                metadata={
                    "provider": "IBM Quantum",
                    "execution_interface": "Qiskit Runtime SamplerV2",
                    "simulation_type": "real_quantum_hardware",
                    "job_id": job_id,
                    "optimization_level": self.optimization_level,
                    "circuit_qubits": circuit.num_qubits,
                    "circuit_depth_original": circuit.depth(),
                    "circuit_depth_transpiled": isa_circuit.depth(),
                    "transpiled_gate_count": isa_circuit.size(),
                    "measurement_register": register_name,
                    "seed": request.seed,
                    "seed_applied": False,
                    "seed_note": ("The simulator seed is not applied to real quantum hardware."),
                    "duration_semantics": (
                        "Client-side elapsed time including submission, "
                        "queue waiting, execution and result retrieval."
                    ),
                },
            )

        except Exception as exc:
            raise BackendExecutionError(
                message=f"IBM Quantum execution failed: {exc}",
                backend_name=self.backend_name,
                retryable=False,
            ) from exc
