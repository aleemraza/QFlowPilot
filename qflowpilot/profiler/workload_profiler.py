
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from qiskit import QuantumCircuit

from qflowpilot.core.models import (
    CircuitProfile,
    WorkloadSpec,
    WorkloadType,
)
from qflowpilot.profiler.circuit_profiler import CircuitProfiler


@dataclass
class WorkloadProfile:
    """Aggregated profile of a batch or iterative workload."""

    workload_id: str
    workload_name: str
    workload_type: WorkloadType

    circuit_profiles: list[CircuitProfile] = field(
        default_factory=list
    )

    round_profiles: list[list[CircuitProfile]] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class WorkloadProfiler:
    """
    Profiles the execution structure of QFlowPilot workloads.

    Supports:
        - Batch workloads: independent quantum circuits.
        - Iterative workloads: sequential rounds of quantum circuits.

    Circuit-level measurements are delegated to CircuitProfiler.
    This class does not execute circuits or perform scheduling.
    """

    def __init__(
        self,
        circuit_profiler: Optional[CircuitProfiler] = None,
    ) -> None:

        self.circuit_profiler = (
            circuit_profiler or CircuitProfiler()
        )

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    @staticmethod
    def _validate_workload(
        workload: WorkloadSpec,
        expected_type: WorkloadType,
    ) -> None:

        if not isinstance(workload, WorkloadSpec):
            raise TypeError(
                "workload must be a WorkloadSpec."
            )

        if workload.workload_type != expected_type:
            raise ValueError(
                f"Expected {expected_type.value} workload, "
                f"received {workload.workload_type.value}."
            )

    @staticmethod
    def _validate_circuits(
        circuits: Sequence[QuantumCircuit],
    ) -> None:

        if not circuits:
            raise ValueError(
                "At least one quantum circuit is required."
            )

        for index, circuit in enumerate(circuits):

            if not isinstance(circuit, QuantumCircuit):
                raise TypeError(
                    f"Item {index} is not a QuantumCircuit."
                )

    # ---------------------------------------------------------
    # Aggregate circuit characteristics
    # ---------------------------------------------------------

    @staticmethod
    def _aggregate(
        profiles: list[CircuitProfile],
    ) -> dict[str, Any]:

        if not profiles:
            return {
                "circuit_count": 0,
                "total_gates": 0,
                "total_two_qubit_gates": 0,
                "average_depth": 0.0,
                "maximum_depth": 0,
                "maximum_qubits": 0,
                "sum_of_circuit_qubits": 0,
            }

        count = len(profiles)

        total_gates = sum(
            profile.total_gates
            for profile in profiles
        )

        total_two_qubit_gates = sum(
            profile.two_qubit_gates
            for profile in profiles
        )

        return {
            "circuit_count": count,

            "total_gates": total_gates,

            "total_two_qubit_gates": (
                total_two_qubit_gates
            ),

            "average_depth": (
                sum(p.depth for p in profiles) / count
            ),

            "maximum_depth": max(
                p.depth for p in profiles
            ),

            "minimum_depth": min(
                p.depth for p in profiles
            ),

            "maximum_qubits": max(
                p.num_qubits for p in profiles
            ),

            # Sum across circuits, not simultaneous
            # backend qubit demand.
            "sum_of_circuit_qubits": sum(
                p.num_qubits for p in profiles
            ),
        }

    # ---------------------------------------------------------
    # Batch workload
    # ---------------------------------------------------------

    def profile_batch(
        self,
        workload: WorkloadSpec,
        circuits: Sequence[QuantumCircuit],
    ) -> WorkloadProfile:
        """
        Profile independent circuits in a batch workload.

        All circuits are profiled separately. No execution
        dependency is assumed between them.
        """

        self._validate_workload(
            workload,
            WorkloadType.BATCH,
        )

        self._validate_circuits(circuits)

        profiles = [
            self.circuit_profiler.profile_circuit(
                circuit,
                source=f"batch:{workload.workload_id}:circuit_{i}",
            )
            for i, circuit in enumerate(circuits)
        ]

        metadata = self._aggregate(profiles)

        metadata.update({
            "execution_structure": "independent",
            "dependency_between_circuits": False,
            "parallelizable_at_workload_level": True,
            "workload_description": workload.description,
        })

        return WorkloadProfile(
            workload_id=workload.workload_id,
            workload_name=workload.name,
            workload_type=WorkloadType.BATCH,
            circuit_profiles=profiles,
            metadata=metadata,
        )

    # ---------------------------------------------------------
    # Iterative workload
    # ---------------------------------------------------------

    def profile_iterative(
        self,
        workload: WorkloadSpec,
        rounds: Sequence[Sequence[QuantumCircuit]],
    ) -> WorkloadProfile:
        """
        Profile an iterative hybrid quantum-classical workload.

        Each round contains one or more quantum circuits.

        Rounds are treated as sequentially dependent by default.
        Circuits within one round are not assumed to depend
        on one another.
        """

        self._validate_workload(
            workload,
            WorkloadType.ITERATIVE,
        )

        if not rounds:
            raise ValueError(
                "An iterative workload requires at least one round."
            )

        all_profiles = []
        round_profiles = []

        for round_index, round_circuits in enumerate(rounds):

            if not round_circuits:
                raise ValueError(
                    f"Round {round_index} contains no circuits."
                )

            self._validate_circuits(round_circuits)

            profiles = [
                self.circuit_profiler.profile_circuit(
                    circuit,
                    source=(
                        f"iterative:{workload.workload_id}:"
                        f"round_{round_index}:circuit_{circuit_index}"
                    ),
                )
                for circuit_index, circuit in enumerate(
                    round_circuits
                )
            ]

            round_profiles.append(profiles)
            all_profiles.extend(profiles)

        round_summaries = [
            {
                "round_index": index,
                **self._aggregate(profiles),
            }
            for index, profiles in enumerate(round_profiles)
        ]

        metadata = self._aggregate(all_profiles)

        metadata.update({
            "execution_structure": "iterative",
            "number_of_rounds": len(round_profiles),

            "round_summaries": round_summaries,

            "sequential_round_dependency": True,

            "dependency_description": (
                "Each subsequent round is assumed to depend "
                "on the previous round's quantum measurement "
                "results and classical parameter update."
            ),

            "circuits_within_round_assumed_independent": True,

            "workload_description": workload.description,
        })

        return WorkloadProfile(
            workload_id=workload.workload_id,
            workload_name=workload.name,
            workload_type=WorkloadType.ITERATIVE,
            circuit_profiles=all_profiles,
            round_profiles=round_profiles,
            metadata=metadata,
        )

    # ---------------------------------------------------------
    # Unified workload profiling interface
    # ---------------------------------------------------------

    def profile_workload(
        self,
        workload: WorkloadSpec,
        circuits: Optional[
            Sequence[QuantumCircuit]
        ] = None,
        rounds: Optional[
            Sequence[Sequence[QuantumCircuit]]
        ] = None,
    ) -> WorkloadProfile:
        """
        Automatically profile based on WorkloadType.
        """

        if workload.workload_type == WorkloadType.BATCH:

            if circuits is None:
                raise ValueError(
                    "Batch workloads require 'circuits'."
                )

            return self.profile_batch(
                workload,
                circuits,
            )

        if workload.workload_type == WorkloadType.ITERATIVE:

            if rounds is None:
                raise ValueError(
                    "Iterative workloads require 'rounds'."
                )

            return self.profile_iterative(
                workload,
                rounds,
            )

        raise ValueError(
            f"Unsupported workload type: "
            f"{workload.workload_type}"
        )
