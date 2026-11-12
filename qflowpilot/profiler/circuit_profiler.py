from __future__ import annotations
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Optional
from qiskit import QuantumCircuit
from qflowpilot.core.models import CircuitProfile
class CircuitProfiler:
    """
    Comprehensive, backend-independent Qiskit circuit profiler.

    Supports:
        - Already-loaded QuantumCircuit objects
        - OpenQASM 2 files
        - OpenQASM 3 files
        - QPY files

    Extracts:
        - Circuit dimensions and complexity
        - Single-, two-, and multi-qubit operations
        - Gate and instruction distributions
        - Measurement information
        - Qubit connectivity
        - Per-qubit operation statistics
        - Parameter information
        - Circuit metadata
        - Optional instruction-level details

    This module does not execute circuits or submit hardware jobs.
    """

    NON_GATE_OPERATIONS = {
        "measure",
        "barrier",
        "reset",
        "delay",
    }

    CONTROL_FLOW_OPERATIONS = {
        "if_else",
        "while_loop",
        "for_loop",
        "switch_case",
    }

    def __init__(
        self,
        include_instruction_details: bool = False,
    ) -> None:
        self.include_instruction_details = (
            include_instruction_details
        )

    # ---------------------------------------------------------
    # Safe value conversion
    # ---------------------------------------------------------

    @staticmethod
    def _safe_value(value: Any) -> Any:
        """Convert common Qiskit values into serializable values."""

        if value is None or isinstance(
            value, (str, int, float, bool)
        ):
            return value

        if isinstance(value, dict):
            return {
                str(key): CircuitProfiler._safe_value(val)
                for key, val in value.items()
            }

        if isinstance(value, (list, tuple)):
            return [
                CircuitProfiler._safe_value(item)
                for item in value
            ]

        if hasattr(value, "name"):
            try:
                return str(value.name)
            except Exception:
                pass

        return str(value)

    # ---------------------------------------------------------
    # Circuit validation
    # ---------------------------------------------------------

    @staticmethod
    def _validate_circuit(
        circuit: QuantumCircuit,
    ) -> None:

        if not isinstance(circuit, QuantumCircuit):
            raise TypeError(
                "Expected a Qiskit QuantumCircuit."
            )

    # ---------------------------------------------------------
    # Main profiling method
    # ---------------------------------------------------------

    def profile_circuit(
        self,
        circuit: QuantumCircuit,
        source: Optional[str] = None,
    ) -> CircuitProfile:
        """
        Extract comprehensive structural information.

        Args:
            circuit:
                Input Qiskit QuantumCircuit.

            source:
                Optional source file path or dataset identifier.

        Returns:
            CircuitProfile.
        """

        self._validate_circuit(circuit)

        try:
            # ---------------------------------------------
            # 1. Basic circuit characteristics
            # ---------------------------------------------

            num_qubits = circuit.num_qubits
            num_clbits = circuit.num_clbits
            circuit_width = num_qubits + num_clbits

            depth = circuit.depth()

            # ---------------------------------------------
            # 2. Operation counters
            # ---------------------------------------------

            instruction_counts = Counter()
            gate_counts = Counter()

            single_qubit_gates = 0
            two_qubit_gates = 0
            multi_qubit_gates = 0

            measurement_count = 0
            reset_count = 0
            barrier_count = 0
            delay_count = 0

            control_flow_count = 0
            classical_operation_count = 0

            per_qubit_gate_counts = Counter()
            per_qubit_depth = [0] * num_qubits

            connectivity_edges = set()
            measurement_mapping = []

            instruction_details = []

            maximum_operation_width = 0

            # ---------------------------------------------
            # 3. Analyze every circuit instruction
            # ---------------------------------------------

            for index, instruction in enumerate(circuit.data):

                operation = instruction.operation
                name = operation.name.lower()

                qargs = instruction.qubits
                cargs = instruction.clbits

                operation_qubits = [
                    circuit.find_bit(bit).index
                    for bit in qargs
                ]

                operation_clbits = [
                    circuit.find_bit(bit).index
                    for bit in cargs
                ]

                num_operation_qubits = len(qargs)

                instruction_counts[name] += 1

                maximum_operation_width = max(
                    maximum_operation_width,
                    num_operation_qubits,
                )

                # -----------------------------------------
                # Special operations
                # -----------------------------------------

                if name == "measure":

                    measurement_count += 1

                    if operation_qubits and operation_clbits:
                        measurement_mapping.append({
                            "qubit": operation_qubits[0],
                            "classical_bit": operation_clbits[0],
                        })

                elif name == "barrier":
                    barrier_count += 1

                elif name == "reset":
                    reset_count += 1

                elif name == "delay":
                    delay_count += 1

                elif name in self.CONTROL_FLOW_OPERATIONS:
                    control_flow_count += 1

                elif num_operation_qubits == 0:
                    classical_operation_count += 1

                else:
                    # -------------------------------------
                    # Quantum computational operations
                    # -------------------------------------

                    gate_counts[name] += 1

                    if num_operation_qubits == 1:
                        single_qubit_gates += 1

                    elif num_operation_qubits == 2:
                        two_qubit_gates += 1

                    elif num_operation_qubits > 2:
                        multi_qubit_gates += 1

                    for qubit_index in operation_qubits:
                        per_qubit_gate_counts[qubit_index] += 1

                    # Build a logical qubit interaction graph.
                    if num_operation_qubits >= 2:
                        for pair in combinations(
                            sorted(operation_qubits), 2
                        ):
                            connectivity_edges.add(pair)

                    # Estimate logical operation depth.
                    if operation_qubits:
                        layer = max(
                            per_qubit_depth[q]
                            for q in operation_qubits
                        ) + 1

                        for q in operation_qubits:
                            per_qubit_depth[q] = layer

                # -----------------------------------------
                # Optional instruction-level information
                # -----------------------------------------

                if self.include_instruction_details:

                    instruction_details.append({
                        "index": index,
                        "name": name,
                        "num_qubits": num_operation_qubits,
                        "qubits": operation_qubits,
                        "classical_bits": operation_clbits,
                        "parameters": self._safe_value(
                            list(operation.params)
                        ),
                    })

            # ---------------------------------------------
            # 4. Circuit parameter information
            # ---------------------------------------------

            parameters = sorted(
                circuit.parameters,
                key=lambda parameter: parameter.name,
            )

            parameter_names = [
                parameter.name
                for parameter in parameters
            ]

            # ---------------------------------------------
            # 5. Derived complexity metrics
            # ---------------------------------------------

            total_gates = (
                single_qubit_gates
                + two_qubit_gates
                + multi_qubit_gates
            )

            two_qubit_gate_ratio = (
                two_qubit_gates / total_gates
                if total_gates > 0
                else 0.0
            )

            multi_qubit_gate_ratio = (
                multi_qubit_gates / total_gates
                if total_gates > 0
                else 0.0
            )

            logical_operation_depth = max(
                per_qubit_depth,
                default=0,
            )

            # ---------------------------------------------
            # 6. Circuit metadata
            # ---------------------------------------------

            metadata = {
                "source": source,
                "circuit_name": circuit.name,

                "num_qubits": num_qubits,
                "num_clbits": num_clbits,
                "circuit_width": circuit_width,

                "instruction_count": len(circuit.data),
                "total_gates": total_gates,

                "single_qubit_gates": single_qubit_gates,
                "two_qubit_gates": two_qubit_gates,
                "multi_qubit_gates": multi_qubit_gates,

                "two_qubit_gate_ratio": two_qubit_gate_ratio,
                "multi_qubit_gate_ratio": multi_qubit_gate_ratio,

                "measurement_count": measurement_count,
                "reset_count": reset_count,
                "barrier_count": barrier_count,
                "delay_count": delay_count,

                "control_flow_count": control_flow_count,
                "classical_operation_count": (
                    classical_operation_count
                ),

                "instruction_counts": dict(
                    sorted(instruction_counts.items())
                ),

                "per_qubit_gate_counts": {
                    str(qubit): count
                    for qubit, count in sorted(
                        per_qubit_gate_counts.items()
                    )
                },

                "per_qubit_depth": per_qubit_depth,

                "logical_operation_depth": (
                    logical_operation_depth
                ),

                "maximum_operation_width": (
                    maximum_operation_width
                ),

                "connectivity_edges": [
                    list(edge)
                    for edge in sorted(connectivity_edges)
                ],

                "measurement_mapping": measurement_mapping,

                "parameter_count": len(parameter_names),
                "parameter_names": parameter_names,
                "has_parameters": bool(parameter_names),

                "has_measurements": measurement_count > 0,

                "global_phase": self._safe_value(
                    circuit.global_phase
                ),

                "circuit_metadata": self._safe_value(
                    circuit.metadata or {}
                ),

                "gate_count_definition": (
                    "Quantum computational operations excluding "
                    "measurements, barriers, resets, delays, "
                    "control-flow operations and classical operations."
                ),

                "depth_definition": (
                    "Qiskit's native QuantumCircuit.depth()."
                ),
            }

            if self.include_instruction_details:
                metadata["instruction_details"] = (
                    instruction_details
                )

            # ---------------------------------------------
            # 7. Return standardized QFlowPilot profile
            # ---------------------------------------------

            return CircuitProfile(
                num_qubits=num_qubits,
                depth=depth,
                total_gates=total_gates,
                two_qubit_gates=two_qubit_gates,
                gate_counts=dict(sorted(gate_counts.items())),
                estimated_execution_time_s=None,
                metadata=metadata,
            )

        except Exception as exc:
            raise ValueError(
                f"Failed to profile circuit "
                f"'{getattr(circuit, 'name', 'unknown')}': {exc}"
            ) from exc

    # ---------------------------------------------------------
    # Load and profile circuit files
    # ---------------------------------------------------------

    @staticmethod
    def load_circuit(
        file_path: str | Path,
    ) -> QuantumCircuit:
        """
        Load a supported circuit file.

        Supported extensions:
            .qasm
            .qasm2
            .qasm3
            .qpy
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Circuit file not found: {path}"
            )

        suffix = path.suffix.lower()

        if suffix in {".qasm2", ".qasm3", ".qasm"}:

            qasm_text = path.read_text(encoding="utf-8")

            if suffix == ".qasm2":
                return QuantumCircuit.from_qasm_str(qasm_text)

            if suffix == ".qasm3":
                from qiskit import qasm3
                return qasm3.loads(qasm_text)

            # Auto-detect common OpenQASM 2 and 3 files.
            try:
                return QuantumCircuit.from_qasm_str(qasm_text)
            except Exception as qasm2_error:
                try:
                    from qiskit import qasm3
                    return qasm3.loads(qasm_text)
                except Exception as qasm3_error:
                    raise ValueError(
                        "Unable to parse QASM file as OpenQASM 2 "
                        f"or 3. QASM2 error: {qasm2_error}; "
                        f"QASM3 error: {qasm3_error}"
                    ) from qasm3_error

        if suffix == ".qpy":

            from qiskit import qpy

            with path.open("rb") as file:
                circuits = qpy.load(file)

            if not circuits:
                raise ValueError(
                    f"No circuits found in QPY file: {path}"
                )

            if len(circuits) != 1:
                raise ValueError(
                    f"QPY file contains {len(circuits)} circuits. "
                    "Use load_circuits() to load all circuits."
                )

            return circuits[0]

        raise ValueError(
            f"Unsupported circuit format: {suffix}. "
            "Supported formats: .qasm, .qasm2, .qasm3, .qpy"
        )

    @staticmethod
    def load_circuits(
        file_path: str | Path,
    ) -> list[QuantumCircuit]:
        """Load one or more circuits from a QPY file."""

        path = Path(file_path)

        if path.suffix.lower() == ".qpy":

            from qiskit import qpy

            with path.open("rb") as file:
                circuits = qpy.load(file)

            return list(circuits)

        return [CircuitProfiler.load_circuit(path)]

    def profile_file(
        self,
        file_path: str | Path,
    ) -> list[CircuitProfile]:
        """Load and profile all circuits contained in a file."""

        path = Path(file_path)
        circuits = self.load_circuits(path)

        return [
            self.profile_circuit(
                circuit,
                source=str(path),
            )
            for circuit in circuits
        ]

    # ---------------------------------------------------------
    # Profile an entire dataset directory
    # ---------------------------------------------------------

    def profile_dataset(
        self,
        dataset_dir: str | Path,
        recursive: bool = True,
    ) -> dict[str, Any]:
        """
        Profile all supported circuit files in a directory.

        Returns:
            Dictionary containing successful profiles and errors.

        A failed file does not stop processing other files.
        """

        root = Path(dataset_dir)

        if not root.exists():
            raise FileNotFoundError(
                f"Dataset directory not found: {root}"
            )

        if not root.is_dir():
            raise NotADirectoryError(
                f"Expected a dataset directory: {root}"
            )

        supported_extensions = {
            ".qasm",
            ".qasm2",
            ".qasm3",
            ".qpy",
        }

        files = (
            root.rglob("*")
            if recursive
            else root.glob("*")
        )

        circuit_files = sorted(
            path
            for path in files
            if path.is_file()
            and path.suffix.lower() in supported_extensions
        )

        profiles = []
        errors = []

        for path in circuit_files:

            try:
                file_profiles = self.profile_file(path)

                for profile in file_profiles:
                    profiles.append(profile)

            except Exception as exc:
                errors.append({
                    "file": str(path),
                    "error": str(exc),
                })

        return {
            "dataset_dir": str(root),
            "files_discovered": len(circuit_files),
            "circuits_profiled": len(profiles),
            "failed_files": len(errors),
            "profiles": profiles,
            "errors": errors,
        }
