
"""
QFlowPilot: Transpilation Profiler

Profiles the transformation of a logical quantum circuit into a
backend-compatible circuit.

No quantum job is submitted by this module.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

from qiskit import QuantumCircuit
from qiskit.transpiler import generate_preset_pass_manager


@dataclass
class TranspilationProfile:
    """Metrics collected before and after circuit transpilation."""

    backend_name: Optional[str]
    optimization_level: int
    transpilation_time_s: float

    # Logical circuit metrics
    logical_num_qubits: int
    logical_depth: int
    logical_gate_count: int
    logical_two_qubit_gates: int
    logical_gate_counts: dict[str, int] = field(default_factory=dict)

    # Transpiled circuit metrics
    transpiled_num_qubits: int = 0
    transpiled_depth: int = 0
    transpiled_gate_count: int = 0
    transpiled_two_qubit_gates: int = 0
    transpiled_gate_counts: dict[str, int] = field(default_factory=dict)
    native_gate_counts: dict[str, int] = field(default_factory=dict)

    # Layout and routing
    initial_layout: dict[str, int] = field(default_factory=dict)
    final_layout: list[int] = field(default_factory=list)
    explicit_swap_count: int = 0
    routing_overhead: float = 0.0

    # Optimization overhead
    depth_overhead: float = 0.0
    gate_count_overhead: float = 0.0

    # Scheduling
    scheduling_method: Optional[str] = None
    scheduled_duration: Optional[float] = None
    scheduled_duration_unit: Optional[str] = None
    explicit_idle_time: Optional[float] = None
    idle_time_unit: Optional[str] = None

    # Additional information
    metadata: dict[str, Any] = field(default_factory=dict)

    # Keep the actual output circuit available for later execution.
    transpiled_circuit: Optional[QuantumCircuit] = field(
        default=None,
        repr=False,
    )


class TranspilationProfiler:
    """
    Analyze logical-to-physical circuit transpilation.

    Parameters
    ----------
    backend:
        Qiskit backend object. Optional if target or loose constraints
        are supplied to profile_circuit().
    target:
        Qiskit Target object.
    basis_gates:
        Optional target instruction names.
    coupling_map:
        Optional backend connectivity.
    optimization_level:
        Integer from 0 to 3.
    seed_transpiler:
        Random seed for reproducible transpiler choices.
    """

    NON_GATE_OPERATIONS = {
        "measure",
        "barrier",
        "delay",
        "reset",
    }

    def __init__(
        self,
        backend: Any = None,
        target: Any = None,
        basis_gates: Optional[list[str]] = None,
        coupling_map: Any = None,
        optimization_level: int = 1,
        seed_transpiler: Optional[int] = 42,
    ):
        if not isinstance(optimization_level, int):
            raise TypeError("optimization_level must be an integer.")

        if optimization_level not in (0, 1, 2, 3):
            raise ValueError(
                "optimization_level must be 0, 1, 2, or 3."
            )

        if backend is not None and target is not None:
            raise ValueError(
                "Provide either backend or target, not both."
            )

        self.backend = backend
        self.target = target
        self.basis_gates = basis_gates
        self.coupling_map = coupling_map
        self.optimization_level = optimization_level
        self.seed_transpiler = seed_transpiler

    @staticmethod
    def _backend_name(backend: Any) -> Optional[str]:
        """Extract a readable backend name."""

        if backend is None:
            return None

        name = getattr(backend, "name", None)

        if callable(name):
            name = name()

        if name is not None:
            return str(name)

        return backend.__class__.__name__

    @classmethod
    def _count_operations(
        cls,
        circuit: QuantumCircuit,
    ) -> dict[str, Any]:
        """
        Count quantum gates.

        Measurements, barriers, delays, and resets are excluded
        from the gate count.
        """

        gate_counts: Counter = Counter()
        two_qubit_gates = 0
        multi_qubit_gates = 0

        for instruction in circuit.data:
            operation = instruction.operation
            name = operation.name.lower()

            if name in cls.NON_GATE_OPERATIONS:
                continue

            if getattr(operation, "num_qubits", 0) == 0:
                continue

            gate_counts[name] += 1

            if operation.num_qubits == 2:
                two_qubit_gates += 1
            elif operation.num_qubits > 2:
                multi_qubit_gates += 1

        return {
            "gate_counts": dict(sorted(gate_counts.items())),
            "gate_count": sum(gate_counts.values()),
            "two_qubit_gates": two_qubit_gates,
            "multi_qubit_gates": multi_qubit_gates,
        }

    @staticmethod
    def _extract_initial_layout(
        original_circuit: QuantumCircuit,
        transpiled_circuit: QuantumCircuit,
    ) -> dict[str, int]:
        """
        Extract the initial virtual-to-physical qubit mapping.

        Only original logical qubits are included. Ancilla mappings
        are not mixed into this dictionary.
        """

        result: dict[str, int] = {}

        layout = getattr(transpiled_circuit, "layout", None)

        if layout is None:
            return result

        initial_layout = getattr(layout, "initial_layout", None)

        if initial_layout is None:
            return result

        try:
            virtual_to_physical = initial_layout.get_virtual_bits()

            for logical_index, virtual_qubit in enumerate(
                original_circuit.qubits
            ):
                physical_index = virtual_to_physical.get(virtual_qubit)

                if physical_index is not None:
                    result[f"logical_qubit_{logical_index}"] = int(
                        physical_index
                    )

        except (AttributeError, TypeError, ValueError):
            return {}

        return result

    @staticmethod
    def _extract_final_layout(
        transpiled_circuit: QuantumCircuit,
    ) -> list[int]:
        """
        Return the final physical index mapping when available.

        Qiskit's final_index_layout() maps original input qubit
        positions to their final output positions.
        """

        layout = getattr(transpiled_circuit, "layout", None)

        if layout is None:
            return []

        try:
            return [
                int(index)
                for index in layout.final_index_layout(
                    filter_ancillas=True
                )
            ]
        except (AttributeError, TypeError, ValueError):
            return []

    @staticmethod
    def _get_native_gate_names(
        backend: Any,
        target: Any,
        basis_gates: Optional[list[str]],
    ) -> set[str]:
        """Get native instruction names when the target exposes them."""

        if basis_gates is not None:
            return {str(name).lower() for name in basis_gates}

        if target is not None:
            names = getattr(target, "operation_names", None)

            if names is not None:
                return {str(name).lower() for name in names}

        if backend is not None:
            backend_target = getattr(backend, "target", None)

            if backend_target is not None:
                names = getattr(
                    backend_target,
                    "operation_names",
                    None,
                )

                if names is not None:
                    return {str(name).lower() for name in names}

            configuration = getattr(backend, "configuration", None)

            if callable(configuration):
                try:
                    config = configuration()
                    names = getattr(config, "basis_gates", None)

                    if names is not None:
                        return {str(name).lower() for name in names}
                except Exception:
                    pass

        return set()

    @staticmethod
    def _extract_scheduling_metrics(
        circuit: QuantumCircuit,
        scheduling_method: Optional[str],
    ) -> dict[str, Any]:
        """
        Extract scheduling information if scheduling was requested.

        Explicit idle time is the sum of durations of delay
        instructions. It is not an estimate of all possible idle
        intervals unless the scheduling pipeline inserted them.
        """

        if scheduling_method is None:
            return {
                "scheduled_duration": None,
                "scheduled_duration_unit": None,
                "explicit_idle_time": None,
                "idle_time_unit": None,
            }

        duration = getattr(circuit, "duration", None)
        unit = getattr(circuit, "unit", None)

        idle_time = 0.0
        found_delay = False

        for instruction in circuit.data:
            if instruction.operation.name.lower() != "delay":
                continue

            if instruction.operation.params:
                delay_value = instruction.operation.params[0]

                if isinstance(delay_value, (int, float)):
                    idle_time += float(delay_value)
                    found_delay = True

        return {
            "scheduled_duration": (
                float(duration) if duration is not None else None
            ),
            "scheduled_duration_unit": (
                str(unit) if unit is not None else None
            ),
            "explicit_idle_time": (
                idle_time if found_delay else 0.0
            ),
            "idle_time_unit": (
                str(unit) if unit is not None else None
            ),
        }

    def profile_circuit(
        self,
        circuit: QuantumCircuit,
        backend: Any = None,
        target: Any = None,
        basis_gates: Optional[list[str]] = None,
        coupling_map: Any = None,
        optimization_level: Optional[int] = None,
        initial_layout: Any = None,
        layout_method: Optional[str] = None,
        routing_method: Optional[str] = None,
        translation_method: Optional[str] = None,
        scheduling_method: Optional[str] = None,
        seed_transpiler: Optional[int] = None,
    ) -> TranspilationProfile:
        """
        Transpile a circuit and collect before/after metrics.

        This method compiles locally. It does not submit a quantum job.
        """

        if not isinstance(circuit, QuantumCircuit):
            raise TypeError(
                "circuit must be a qiskit.QuantumCircuit."
            )

        selected_backend = (
            backend if backend is not None else self.backend
        )
        selected_target = (
            target if target is not None else self.target
        )

        if selected_backend is not None and selected_target is not None:
            raise ValueError(
                "Provide either backend or target, not both."
            )

        selected_basis = (
            basis_gates
            if basis_gates is not None
            else self.basis_gates
        )

        selected_coupling = (
            coupling_map
            if coupling_map is not None
            else self.coupling_map
        )

        selected_level = (
            optimization_level
            if optimization_level is not None
            else self.optimization_level
        )

        selected_seed = (
            seed_transpiler
            if seed_transpiler is not None
            else self.seed_transpiler
        )

        if selected_level not in (0, 1, 2, 3):
            raise ValueError(
                "optimization_level must be 0, 1, 2, or 3."
            )

        logical = self._count_operations(circuit)

        pass_manager_options: dict[str, Any] = {
            "optimization_level": selected_level,
            "seed_transpiler": selected_seed,
        }

        if selected_backend is not None:
            pass_manager_options["backend"] = selected_backend

        if selected_target is not None:
            pass_manager_options["target"] = selected_target

        if selected_basis is not None:
            pass_manager_options["basis_gates"] = selected_basis

        if selected_coupling is not None:
            pass_manager_options["coupling_map"] = selected_coupling

        optional_options = {
            "initial_layout": initial_layout,
            "layout_method": layout_method,
            "routing_method": routing_method,
            "translation_method": translation_method,
            "scheduling_method": scheduling_method,
        }

        for name, value in optional_options.items():
            if value is not None:
                pass_manager_options[name] = value

        # Build the preset transpilation pipeline.
        pass_manager = generate_preset_pass_manager(
            **pass_manager_options
        )

        # Measure compilation time only.
        start_time = time.perf_counter()
        transpiled = pass_manager.run(circuit)
        transpilation_time = time.perf_counter() - start_time

        physical = self._count_operations(transpiled)

        explicit_swap_count = sum(
            1
            for instruction in transpiled.data
            if instruction.operation.name.lower() == "swap"
        )

        routing_overhead = (
            explicit_swap_count
            / max(1, logical["two_qubit_gates"])
        )

        depth_overhead = (
            transpiled.depth()
            / max(1, circuit.depth())
        )

        gate_count_overhead = (
            physical["gate_count"]
            / max(1, logical["gate_count"])
        )

        native_gate_names = self._get_native_gate_names(
            selected_backend,
            selected_target,
            selected_basis,
        )

        if native_gate_names:
            native_gate_counts = {
                name: count
                for name, count in physical["gate_counts"].items()
                if name in native_gate_names
            }
        else:
            native_gate_counts = {}

        scheduling_metrics = self._extract_scheduling_metrics(
            transpiled,
            scheduling_method,
        )

        backend_name = self._backend_name(selected_backend)

        if selected_target is not None and backend_name is None:
            backend_name = "custom_target"

        metadata = {
            "transpiler": "Qiskit generate_preset_pass_manager",
            "qiskit_backend_supplied": selected_backend is not None,
            "target_supplied": selected_target is not None,
            "basis_gates_supplied": selected_basis is not None,
            "coupling_map_supplied": selected_coupling is not None,
            "layout_method": layout_method,
            "routing_method": routing_method,
            "translation_method": translation_method,
            "seed_transpiler": selected_seed,
            "native_gate_names_available": bool(native_gate_names),
            "explicit_swap_count_is_not_total_routing_swaps": True,
            "routing_overhead_definition": (
                "explicit final-circuit SWAP count / "
                "max(1, logical two-qubit gate count)"
            ),
            "depth_overhead_definition": (
                "transpiled depth / max(1, logical depth)"
            ),
            "gate_count_definition": (
                "Excludes measure, barrier, delay, and reset."
            ),
            "idle_time_definition": (
                "Sum of explicit delay instruction durations; "
                "not a complete idle-time estimate in every pipeline."
            ),
        }

        return TranspilationProfile(
            backend_name=backend_name,
            optimization_level=selected_level,
            transpilation_time_s=transpilation_time,

            logical_num_qubits=circuit.num_qubits,
            logical_depth=circuit.depth(),
            logical_gate_count=logical["gate_count"],
            logical_two_qubit_gates=logical["two_qubit_gates"],
            logical_gate_counts=logical["gate_counts"],

            transpiled_num_qubits=transpiled.num_qubits,
            transpiled_depth=transpiled.depth(),
            transpiled_gate_count=physical["gate_count"],
            transpiled_two_qubit_gates=physical["two_qubit_gates"],
            transpiled_gate_counts=physical["gate_counts"],
            native_gate_counts=native_gate_counts,

            initial_layout=self._extract_initial_layout(
                circuit,
                transpiled,
            ),
            final_layout=self._extract_final_layout(transpiled),
            explicit_swap_count=explicit_swap_count,
            routing_overhead=routing_overhead,

            depth_overhead=depth_overhead,
            gate_count_overhead=gate_count_overhead,

            scheduling_method=scheduling_method,
            metadata=metadata,
            transpiled_circuit=transpiled,
            **scheduling_metrics,
        )

    def profile_multiple(
        self,
        circuits: list[QuantumCircuit],
        **kwargs: Any,
    ) -> list[TranspilationProfile]:
        """Profile multiple circuits using the same target settings."""

        if not isinstance(circuits, (list, tuple)):
            raise TypeError("circuits must be a list or tuple.")

        if not circuits:
            raise ValueError("circuits cannot be empty.")

        return [
            self.profile_circuit(circuit, **kwargs)
            for circuit in circuits
        ]
