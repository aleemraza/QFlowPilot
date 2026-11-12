
from pathlib import Path
import sys

from qiskit import QuantumCircuit

# --------------------------------------------------
# 1. Project imports
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from qflowpilot.profiler.transpilation_profiler import (
    TranspilationProfiler,
)


# --------------------------------------------------
# 2. Load one real circuit
# --------------------------------------------------

CIRCUIT_PATH = (
    PROJECT_ROOT
    / "workloads"
    / "mqt_bench"
    / "dj_nativegates_ibm_falcon_opt2_5.qasm"
)

if not CIRCUIT_PATH.exists():
    raise FileNotFoundError(
        f"Circuit not found: {CIRCUIT_PATH}"
    )

from qiskit import qasm3

with open(CIRCUIT_PATH, "r", encoding="utf-8") as file:
    qasm_source = file.read()

circuit = qasm3.loads(qasm_source)

print("\n" + "=" * 65)
print("QFLOWPILOT - TRANSPILATION PROFILER TEST")
print("=" * 65)

print("\nOriginal circuit:")
print(f"Qubits: {circuit.num_qubits}")
print(f"Depth:  {circuit.depth()}")
print(f"Instructions: {len(circuit.data)}")


# --------------------------------------------------
# 3. Independent metric calculation
# --------------------------------------------------

NON_GATE_OPERATIONS = {
    "measure",
    "barrier",
    "delay",
    "reset",
}


def independently_count_gates(qc):
    """Calculate gate metrics independently."""

    counts = {}
    two_qubit = 0
    multi_qubit = 0

    for instruction in qc.data:
        operation = instruction.operation
        name = operation.name.lower()

        if name in NON_GATE_OPERATIONS:
            continue

        if operation.num_qubits == 0:
            continue

        counts[name] = counts.get(name, 0) + 1

        if operation.num_qubits == 2:
            two_qubit += 1
        elif operation.num_qubits > 2:
            multi_qubit += 1

    return {
        "gate_counts": dict(sorted(counts.items())),
        "gate_count": sum(counts.values()),
        "two_qubit_gates": two_qubit,
        "multi_qubit_gates": multi_qubit,
    }


# --------------------------------------------------
# 4. Configure the profiler
# --------------------------------------------------

profiler = TranspilationProfiler(
    basis_gates=["rz", "sx", "x", "cx"],
    optimization_level=1,
    seed_transpiler=42,
)


# --------------------------------------------------
# 5. Run transpilation
# --------------------------------------------------

profile = profiler.profile_circuit(circuit)

transpiled = profile.transpiled_circuit

if transpiled is None:
    raise AssertionError("No transpiled circuit was returned.")


# --------------------------------------------------
# 6. Independently calculate expected metrics
# --------------------------------------------------

logical_expected = independently_count_gates(circuit)
physical_expected = independently_count_gates(transpiled)

expected_depth_overhead = (
    transpiled.depth() / max(1, circuit.depth())
)

expected_gate_overhead = (
    physical_expected["gate_count"]
    / max(1, logical_expected["gate_count"])
)

expected_swap_count = sum(
    instruction.operation.name.lower() == "swap"
    for instruction in transpiled.data
)

expected_routing_overhead = (
    expected_swap_count
    / max(1, logical_expected["two_qubit_gates"])
)


# --------------------------------------------------
# 7. Display results
# --------------------------------------------------

print("\n" + "-" * 65)
print("LOGICAL CIRCUIT")
print("-" * 65)

print("Qubits:", profile.logical_num_qubits)
print("Depth:", profile.logical_depth)
print("Gate count:", profile.logical_gate_count)
print("Two-qubit gates:", profile.logical_two_qubit_gates)
print("Gate distribution:", profile.logical_gate_counts)

print("\n" + "-" * 65)
print("TRANSPILED CIRCUIT")
print("-" * 65)

print("Qubits:", profile.transpiled_num_qubits)
print("Depth:", profile.transpiled_depth)
print("Gate count:", profile.transpiled_gate_count)
print("Two-qubit gates:", profile.transpiled_two_qubit_gates)
print("Gate distribution:", profile.transpiled_gate_counts)
print("Native gate counts:", profile.native_gate_counts)

print("\n" + "-" * 65)
print("LAYOUT AND OVERHEAD")
print("-" * 65)

print("Initial layout:", profile.initial_layout)
print("Final layout:", profile.final_layout)
print("Explicit SWAP count:", profile.explicit_swap_count)
print("Routing overhead:", profile.routing_overhead)
print("Depth overhead:", profile.depth_overhead)
print("Gate-count overhead:", profile.gate_count_overhead)

print("\n" + "-" * 65)
print("SCHEDULING")
print("-" * 65)

print("Scheduling method:", profile.scheduling_method)
print("Scheduled duration:", profile.scheduled_duration)
print("Explicit idle time:", profile.explicit_idle_time)

print("\nTranspilation time:", profile.transpilation_time_s)
print("Backend name:", profile.backend_name)


# --------------------------------------------------
# 8. Assertions: logical metrics
# --------------------------------------------------

assert profile.logical_num_qubits == circuit.num_qubits
assert profile.logical_depth == circuit.depth()

assert profile.logical_gate_count == logical_expected["gate_count"]

assert (
    profile.logical_two_qubit_gates
    == logical_expected["two_qubit_gates"]
)

assert profile.logical_gate_counts == logical_expected["gate_counts"]


# --------------------------------------------------
# 9. Assertions: transpiled metrics
# --------------------------------------------------

assert profile.transpiled_num_qubits == transpiled.num_qubits
assert profile.transpiled_depth == transpiled.depth()

assert (
    profile.transpiled_gate_count
    == physical_expected["gate_count"]
)

assert (
    profile.transpiled_two_qubit_gates
    == physical_expected["two_qubit_gates"]
)

assert (
    profile.transpiled_gate_counts
    == physical_expected["gate_counts"]
)


# --------------------------------------------------
# 10. Assertions: overhead calculations
# --------------------------------------------------

assert profile.depth_overhead == expected_depth_overhead

assert (
    profile.gate_count_overhead
    == expected_gate_overhead
)

assert profile.explicit_swap_count == expected_swap_count

assert (
    profile.routing_overhead
    == expected_routing_overhead
)

assert profile.transpilation_time_s >= 0


# --------------------------------------------------
# 11. Assertions: native gates and scheduling
# --------------------------------------------------

expected_native_counts = {
    name: count
    for name, count in physical_expected["gate_counts"].items()
    if name in {"rz", "sx", "x", "cx"}
}

assert profile.native_gate_counts == expected_native_counts

assert profile.scheduling_method is None
assert profile.scheduled_duration is None
assert profile.explicit_idle_time is None


# --------------------------------------------------
# 12. Test multiple circuits
# --------------------------------------------------

second_circuit = QuantumCircuit(2)
second_circuit.h(0)
second_circuit.cx(0, 1)

multiple_profiles = profiler.profile_multiple(
    [circuit, second_circuit]
)

assert len(multiple_profiles) == 2
assert all(
    item.transpiled_circuit is not None
    for item in multiple_profiles
)


# --------------------------------------------------
# 13. Test invalid inputs
# --------------------------------------------------

try:
    profiler.profile_circuit("not a circuit")
    raise AssertionError("Invalid circuit was accepted.")
except TypeError:
    pass

try:
    profiler.profile_multiple([])
    raise AssertionError("Empty circuit list was accepted.")
except ValueError:
    pass

try:
    TranspilationProfiler(optimization_level=4)
    raise AssertionError("Invalid optimization level was accepted.")
except ValueError:
    pass


# --------------------------------------------------
# 14. Final result
# --------------------------------------------------

print("\n" + "=" * 65)
print("ALL TRANSPILATION PROFILER TESTS PASSED")
print("=" * 65)

print("Checks completed:")
print("1. Logical circuit metrics")
print("2. Transpiled circuit metrics")
print("3. Native gate counts")
print("4. Depth and gate-count overhead")
print("5. Routing overhead")
print("6. Transpilation timing")
print("7. Scheduling defaults")
print("8. Multiple circuit profiling")
print("9. Invalid input handling")

print("\nTranspilationProfiler test completed successfully.")

from pathlib import Path
import sys

from qiskit import QuantumCircuit

# --------------------------------------------------
# 1. Project imports
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from qflowpilot.core.models import (
    WorkloadSpec,
    WorkloadType,
)

from qflowpilot.profiler.workload_profiler import (
    WorkloadProfiler,
)

from qflowpilot.profiler.circuit_profiler import (
    CircuitProfiler,
)

from qflowpilot.profiler.transpilation_profiler import (
    TranspilationProfiler,
)


# ==================================================
# STEP 1: CREATE QUANTUM WORKLOAD
# ==================================================

print("\n" + "=" * 70)
print("STEP 1: QUANTUM WORKLOAD")
print("=" * 70)

circuit_path = (
    PROJECT_ROOT
    / "workloads"
    / "mqt_bench"
    / "dj_nativegates_ibm_falcon_opt2_5.qasm"
)

if not circuit_path.exists():
    raise FileNotFoundError(circuit_path)

with open(circuit_path, "r", encoding="utf-8") as file:
    qasm_source = file.read()

circuit = qasm3.loads(qasm_source)

workload = WorkloadSpec(
    workload_id="qflowpilot_test_001",
    name="Deutsch-Jozsa Quantum Workload",
    workload_type=WorkloadType.BATCH,
    algorithm="Deutsch-Jozsa",
    description="A single-circuit quantum workload for profiler testing.",
    metadata={
        "source": "MQT Bench",
        "circuit_file": circuit_path.name,
    },
)

# Workload contains one quantum circuit.
circuits = [circuit]

print("Workload ID:", workload.workload_id)
print("Workload name:", workload.name)
print("Workload type:", workload.workload_type.value)
print("Algorithm:", workload.algorithm)
print("Number of circuits:", len(circuits))
print("Circuit qubits:", circuit.num_qubits)


# ==================================================
# STEP 2: WORKLOAD PROFILER
# ==================================================

# print("\n" + "=" * 70)
# print("STEP 2: WORKLOAD PROFILER")
# print("=" * 70)

workload_profiler = WorkloadProfiler()

workload_profile = workload_profiler.profile_workload(
    workload,
    circuits,
)


print("Workload ID:", workload_profile.workload_id)
print("Workload type:", workload_profile.workload_type)

print("Circuit count:", len(workload_profile.circuit_profiles))

# Get individual circuit profiles
profiles = workload_profile.circuit_profiles

# Independently calculate aggregate metrics
total_gates = sum(p.total_gates for p in profiles)

total_two_qubit_gates = sum(
    p.two_qubit_gates for p in profiles
)

depths = [p.depth for p in profiles]

average_depth = sum(depths) / len(depths)

maximum_depth = max(depths)
minimum_depth = min(depths)

maximum_qubits = max(p.num_qubits for p in profiles)

print("Total gates:", total_gates)
print("Total two-qubit gates:", total_two_qubit_gates)
print("Average depth:", average_depth)
print("Maximum depth:", maximum_depth)
print("Minimum depth:", minimum_depth)
print("Maximum qubits:", maximum_qubits)

# ==================================================
# STEP 3: CIRCUIT PROFILER
# ==================================================

print("\n" + "=" * 70)
print("STEP 3: CIRCUIT PROFILER")
print("=" * 70)

circuit_profiler = CircuitProfiler()

circuit_profile = circuit_profiler.profile_circuit(
    circuit,
    source=str(circuit_path),
)

print("Qubits:", circuit_profile.num_qubits)
print("Circuit depth:", circuit_profile.depth)
print("Total gates:", circuit_profile.total_gates)
print("Two-qubit gates:", circuit_profile.two_qubit_gates)
print("Gate distribution:", circuit_profile.gate_counts)


# ==================================================
# STEP 4: TRANSPILATION PROFILER
# ==================================================

print("\n" + "=" * 70)
print("STEP 4: TRANSPILATION PROFILER")
print("=" * 70)

transpilation_profiler = TranspilationProfiler(
    basis_gates=["rz", "sx", "x", "cx"],
    optimization_level=1,
    seed_transpiler=42,
)

transpilation_profile = (
    transpilation_profiler.profile_circuit(circuit)
)

transpiled_circuit = transpilation_profile.transpiled_circuit

if transpiled_circuit is None:
    raise RuntimeError("Transpilation did not return a circuit.")

print("\nLogical circuit:")
print("Qubits:", transpilation_profile.logical_num_qubits)
print("Depth:", transpilation_profile.logical_depth)
print("Gates:", transpilation_profile.logical_gate_count)
print(
    "Two-qubit gates:",
    transpilation_profile.logical_two_qubit_gates,
)

print("\nTranspiled circuit:")
print("Qubits:", transpilation_profile.transpiled_num_qubits)
print("Depth:", transpilation_profile.transpiled_depth)
print("Gates:", transpilation_profile.transpiled_gate_count)
print(
    "Two-qubit gates:",
    transpilation_profile.transpiled_two_qubit_gates,
)

print("\nTranspilation overhead:")
print("Depth overhead:", transpilation_profile.depth_overhead)
print("Gate overhead:", transpilation_profile.gate_count_overhead)
print("Explicit SWAP count:", transpilation_profile.explicit_swap_count)
print("Transpilation time:", transpilation_profile.transpilation_time_s)


# ==================================================
# STEP 5: SEQUENTIAL CONSISTENCY CHECKS
# ==================================================

print("\n" + "=" * 70)
print("STEP 5: SEQUENTIAL PIPELINE VALIDATION")
print("=" * 70)

# WorkloadProfiler and CircuitProfiler should agree
# on the individual circuit's basic metrics.

assert len(workload_profile.circuit_profiles) == 1

workload_circuit_profile = workload_profile.circuit_profiles[0]

assert (
    workload_circuit_profile.num_qubits
    == circuit_profile.num_qubits
)

assert (
    workload_circuit_profile.depth
    == circuit_profile.depth
)

assert (
    workload_circuit_profile.total_gates
    == circuit_profile.total_gates
)

assert (
    workload_circuit_profile.two_qubit_gates
    == circuit_profile.two_qubit_gates
)

# Transpilation logical metrics should agree with
# the original circuit metrics.

assert (
    transpilation_profile.logical_num_qubits
    == circuit_profile.num_qubits
)

assert (
    transpilation_profile.logical_depth
    == circuit_profile.depth
)

assert (
    transpilation_profile.logical_gate_count
    == circuit_profile.total_gates
)

assert (
    transpilation_profile.logical_two_qubit_gates
    == circuit_profile.two_qubit_gates
)

assert transpiled_circuit is not None

print("PASS: WorkloadProfiler output matches CircuitProfiler.")
print("PASS: CircuitProfiler output matches transpilation input.")
print("PASS: Transpilation returned a circuit.")
print("PASS: All sequential consistency checks passed.")

print("\n" + "=" * 70)
print("SEQUENTIAL PROFILING PIPELINE COMPLETED")
print("=" * 70)
