
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import (
    NoiseModel,
    ReadoutError,
    depolarizing_error,
)

from qflowpilot.core.exceptions import BackendExecutionError
from qflowpilot.core.models import (
    ExecutionResult,
    ExecutionStatus,
)
from qiskit.transpiler import generate_preset_pass_manager
from .base_adapter import BaseBackendAdapter


class AerNoisyAdapter(BaseBackendAdapter):
    """
    Noisy quantum circuit execution using Qiskit Aer.

    The configurable noise model includes:
      - Single-qubit depolarizing errors on SX gates.
      - Two-qubit depolarizing errors on CX gates.
      - Measurement readout errors.

    This is a synthetic noise model, not a hardware-calibrated model.
    """

    def __init__(
        self,
        backend_name: str = "aer_noisy",
        optimization_level: int = 1,
        single_qubit_error: float = 0.001,
        two_qubit_error: float = 0.01,
        readout_error: float = 0.02,
    ) -> None:

        if optimization_level not in range(4):
            raise ValueError(
                "optimization_level must be between 0 and 3."
            )

        error_parameters = {
            "single_qubit_error": single_qubit_error,
            "two_qubit_error": two_qubit_error,
            "readout_error": readout_error,
        }

        for name, value in error_parameters.items():
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                or value < 0
                or value > 1
            ):
                raise ValueError(
                    f"{name} must be a finite number between 0 and 1."
                )

        super().__init__(
            backend_name=backend_name,
            backend_type="noisy_simulator",
            backend_version=None,
            available=True,
        )

        self.optimization_level = optimization_level

        self.single_qubit_error = float(single_qubit_error)
        self.two_qubit_error = float(two_qubit_error)
        self.readout_error = float(readout_error)

        # Build the configurable quantum noise model.
        self._noise_model = self._build_noise_model()

        # Initialize Aer with the noise model.
        self._simulator = AerSimulator(
            noise_model=self._noise_model
        )
        self._pass_manager = generate_preset_pass_manager(
            optimization_level=self.optimization_level,
            backend=self._simulator,
        )

    def _build_noise_model(self) -> NoiseModel:
        """Construct the synthetic noise model."""

        noise_model = NoiseModel()

        # Single-qubit depolarizing error.
        if self.single_qubit_error > 0:
            single_qubit_noise = depolarizing_error(
                self.single_qubit_error,
                1,
            )

            noise_model.add_all_qubit_quantum_error(
                single_qubit_noise,
                ["sx"],
            )

        # Two-qubit depolarizing error.
        if self.two_qubit_error > 0:
            two_qubit_noise = depolarizing_error(
                self.two_qubit_error,
                2,
            )

            noise_model.add_all_qubit_quantum_error(
                two_qubit_noise,
                ["cx"],
            )

        # Measurement readout error.
        if self.readout_error > 0:
            readout_noise = ReadoutError(
                [
                    [
                        1 - self.readout_error,
                        self.readout_error,
                    ],
                    [
                        self.readout_error,
                        1 - self.readout_error,
                    ],
                ]
            )

            noise_model.add_all_qubit_readout_error(
                readout_noise
            )

        return noise_model

    def execute(
        self,
        request: Any,
        circuit: QuantumCircuit,
    ) -> ExecutionResult:
        """Execute a circuit with the configured noise model."""

        self._ensure_available()

        if not isinstance(circuit, QuantumCircuit):
            raise TypeError(
                "circuit must be a Qiskit QuantumCircuit."
            )

        if request.shots <= 0:
            raise ValueError("request.shots must be positive.")

        submitted_at = datetime.now(timezone.utc)

        try:
            # Step 1: Transpile using the noisy simulator's basis gates.
            # transpiled_circuit = transpile(
            #     circuit,
            #     self._simulator,
            #     optimization_level=self.optimization_level,
            #     basis_gates=self._noise_model.basis_gates,
            # )
            transpiled_circuit = self._pass_manager.run(circuit)

            started_at = datetime.now(timezone.utc)

            # Step 2: Configure execution.
            run_options = {
                "shots": request.shots,
            }

            if request.seed is not None:
                run_options["seed_simulator"] = request.seed

            # Step 3: Execute the noisy circuit.
            job = self._simulator.run(
                transpiled_circuit,
                **run_options,
            )

            backend_result = job.result()
            counts = backend_result.get_counts()

            # Step 4: Normalize measurement counts.
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

            # Step 5: Return the standardized result.
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
                    "simulation_type": "noisy",
                    "noise_model": "depolarizing_and_readout",
                    "single_qubit_error": self.single_qubit_error,
                    "two_qubit_error": self.two_qubit_error,
                    "readout_error": self.readout_error,
                    "optimization_level": self.optimization_level,
                    "circuit_qubits": circuit.num_qubits,
                    "circuit_depth_original": circuit.depth(),
                    "circuit_depth_transpiled": (
                        transpiled_circuit.depth()
                    ),
                    "transpiled_gate_count": (
                        transpiled_circuit.size()
                    ),
                    "noise_basis_gates": (
                        list(self._noise_model.basis_gates)
                    ),
                    "seed": request.seed,
                },
            )

        except Exception as exc:
            raise BackendExecutionError(
                message=f"Noisy Aer execution failed: {exc}",
                backend_name=self.backend_name,
                retryable=False,
            ) from exc

    def get_noise_parameters(self) -> dict[str, float]:
        """Return the configured synthetic noise parameters."""

        return {
            "single_qubit_error": self.single_qubit_error,
            "two_qubit_error": self.two_qubit_error,
            "readout_error": self.readout_error,
        }
