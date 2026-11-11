from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

from qflowpilot.core.exceptions import BackendExecutionError
from qflowpilot.core.models import (
    ExecutionResult,
    ExecutionStatus,
)
from .base_adapter import BaseBackendAdapter


class AerIdealAdapter(BaseBackendAdapter):
    """
    Ideal, noise-free quantum circuit execution using Qiskit Aer.

    This adapter:
    1. Accepts a Qiskit QuantumCircuit.
    2. Transpiles it for the Aer simulator.
    3. Executes it with the requested number of shots.
    4. Collects measurement counts.
    5. Returns a standardized ExecutionResult.
    """

    def __init__(
        self,
        backend_name: str = "aer_ideal",
        optimization_level: int = 1,
    ) -> None:

        if optimization_level not in range(4):
            raise ValueError(
                "optimization_level must be between 0 and 3."
            )

        super().__init__(
            backend_name=backend_name,
            backend_type="ideal_simulator",
            backend_version=None,
            available=True,
        )

        self.optimization_level = optimization_level
        self._simulator = AerSimulator(method="automatic")

    def execute(
        self,
        request: Any,
        circuit: QuantumCircuit,
    ) -> ExecutionResult:
        """
        Execute a quantum circuit using ideal Qiskit Aer simulation.
        """

        self._ensure_available()

        if not isinstance(circuit, QuantumCircuit):
            raise TypeError(
                "circuit must be a Qiskit QuantumCircuit."
            )

        if request.shots <= 0:
            raise ValueError("request.shots must be positive.")

        submitted_at = datetime.now(timezone.utc)

        try:
            # Step 1: Transpile the circuit for Aer.
            transpiled_circuit = transpile(
                circuit,
                self._simulator,
                optimization_level=self.optimization_level,
            )

            started_at = datetime.now(timezone.utc)

            # Step 2: Configure simulator execution.
            run_options = {
                "shots": request.shots,
            }

            if request.seed is not None:
                run_options["seed_simulator"] = request.seed

            # Step 3: Execute the circuit.
            job = self._simulator.run(
                transpiled_circuit,
                **run_options,
            )

            # Step 4: Retrieve the execution result.
            backend_result = job.result()
            counts = backend_result.get_counts()

            # Step 5: Normalize counts into a dictionary.
            if not isinstance(counts, dict):
                raise RuntimeError(
                    "Expected one circuit result, but received "
                    "multiple count dictionaries."
                )

            normalized_counts = {
                str(state): int(count)
                for state, count in counts.items()
            }

            completed_at = datetime.now(timezone.utc)

            # Step 6: Build the standardized QFlowPilot result.
            return ExecutionResult(
                result_id=str(uuid4()),
                request_id=request.request_id,
                status=ExecutionStatus.COMPLETED,
                counts=normalized_counts,
                shots=request.shots,
                backend_name=self.backend_name,
                execution_mode=request.execution_mode,
                submitted_at=submitted_at,
                started_at=started_at,
                completed_at=completed_at,
                error_message=None,
                metadata={
                    "simulator": "Qiskit Aer",
                    "simulation_type": "ideal",
                    "noise_model": None,
                    "optimization_level": self.optimization_level,
                    "circuit_qubits": circuit.num_qubits,
                    "circuit_depth_original": circuit.depth(),
                    "circuit_depth_transpiled": (
                        transpiled_circuit.depth()
                    ),
                    "transpiled_gate_count": (
                        transpiled_circuit.size()
                    ),
                    "seed": request.seed,
                },
            )

        except Exception as exc:
            raise BackendExecutionError(
                message=f"Ideal Aer execution failed: {exc}",
                backend_name=self.backend_name,
                retryable=False,
            ) from exc
