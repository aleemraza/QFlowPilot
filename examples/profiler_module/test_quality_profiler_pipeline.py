
from pathlib import Path
import sys
import math

from qiskit import QuantumCircuit, qasm3
from statistics import NormalDist

# ==================================================
# 1. PROJECT IMPORTS
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from qflowpilot.core.models import (
    WorkloadSpec,
    WorkloadType,
    ExecutionRequest,
    ExecutionMode,
    ExecutionStatus,
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

from qflowpilot.profiler.quality_profiler import (
    QualityProfiler,
)

from qflowpilot.adapters import AerIdealAdapter


# ==================================================
# STEP 1: QUANTUM WORKLOAD
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
    circuit = qasm3.loads(file.read())

workload = WorkloadSpec(
    workload_id="qflowpilot_quality_001",
    name="Deutsch-Jozsa Quantum Workload",
    workload_type=WorkloadType.BATCH,
    algorithm="Deutsch-Jozsa",
    description="Sequential quality profiling test.",
    metadata={
        "source": "MQT Bench",
        "circuit_file": circuit_path.name,
    },
)

circuits = [circuit]

print("Workload ID:", workload.workload_id)
print("Algorithm:", workload.algorithm)
print("Workload type:", workload.workload_type.value)
print("Circuit count:", len(circuits))
print("Qubits:", circuit.num_qubits)


# ==================================================
# STEP 2: WORKLOAD PROFILER
# ==================================================

print("\n" + "=" * 70)
print("STEP 2: WORKLOAD PROFILER")
print("=" * 70)

workload_profiler = WorkloadProfiler()

workload_profile = workload_profiler.profile_workload(
    workload,
    circuits,
)

print("Circuit count:", len(workload_profile.circuit_profiles))
print(
    "Total gates:",
    sum(p.total_gates for p in workload_profile.circuit_profiles),
)
print(
    "Total two-qubit gates:",
    sum(p.two_qubit_gates for p in workload_profile.circuit_profiles),
)


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
print("Depth:", circuit_profile.depth)
print("Gates:", circuit_profile.total_gates)
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
    raise RuntimeError("Transpilation failed.")

print("Logical gates:", transpilation_profile.logical_gate_count)
print("Transpiled gates:", transpilation_profile.transpiled_gate_count)
print("Logical depth:", transpilation_profile.logical_depth)
print("Transpiled depth:", transpilation_profile.transpiled_depth)
print("Depth overhead:", transpilation_profile.depth_overhead)


# ==================================================
# STEP 5: EXECUTION THROUGH AER IDEAL ADAPTER
# ==================================================

print("\n" + "=" * 70)
print("STEP 5: AER IDEAL ADAPTER")
print("=" * 70)

SHOTS = 1024
SEED = 42

execution_request = ExecutionRequest(
    request_id="qflowpilot_request_001",
    workload_id=workload.workload_id,
    shots=SHOTS,
    execution_mode=ExecutionMode.IDEAL_SIMULATOR,
    backend_name="aer_ideal",
    seed=SEED,
)

adapter = AerIdealAdapter(
    backend_name="aer_ideal",
    optimization_level=1,
)

# Execute the circuit produced by TranspilationProfiler.
execution_result = adapter.execute(
    execution_request,
    transpiled_circuit,
)

if execution_result.status != ExecutionStatus.COMPLETED:
    raise RuntimeError(
        f"Execution failed: {execution_result.error_message}"
    )

counts = execution_result.counts

if not counts:
    raise RuntimeError("No measurement counts returned.")

actual_shots = sum(counts.values())

print("Execution status:", execution_result.status.value)
print("Backend:", execution_result.backend_name)
print("Requested shots:", SHOTS)
print("Actual shots:", actual_shots)
print("Measurement counts:", counts)

assert actual_shots == SHOTS


# ==================================================
# STEP 6: QUALITY PROFILER
# ==================================================

# print("\n" + "=" * 70)
# print("STEP 6: QUALITY PROFILER")
# print("=" * 70)

# # Define a simple observable for this test:
# # Hamming weight = number of 1 bits in each measured bitstring.
# #
# # This is a statistical test observable, not an application-
# # specific Deutsch-Jozsa success criterion.

observable_values = {
    state: float(state.replace(" ", "").count("1"))
    for state in counts
}

quality_profiler = QualityProfiler()

# quality_estimate = quality_profiler.estimate_from_counts(
#     counts=counts,
#     observable_values=observable_values,
#     confidence_level=0.95,
# )

# print("Sample count:", quality_estimate.sample_count)
# print("Expectation value:", quality_estimate.expectation_value)
# print("Variance:", quality_estimate.variance)
# print("Standard error:", quality_estimate.standard_error)
# print("Confidence interval:", quality_estimate.confidence_interval)
# print("Success probability:", quality_estimate.success_probability)
# print("Application score:", quality_estimate.application_score)
# print("Quality satisfied:", quality_estimate.quality_satisfied)

# print(
#     "Measurement probabilities:",
#     quality_estimate.metadata["measurement_probabilities"],
# )

# print(
#     "Probability sum:",
#     quality_estimate.metadata["probability_sum"],
# )


# ---------------------------------------------------------
# STEP 6: QUALITY PROFILER
# ---------------------------------------------------------

# Define a test-specific success criterion.
# Replace this with the actual expected output of your
# Deutsch-Jozsa oracle when validating algorithm correctness.

success_states = ["1111"]

# Define an illustrative application score.
def application_score(bitstring: str) -> float:
    return 1.0 if bitstring in success_states else 0.0


# Configure illustrative quality thresholds.
quality_profiler = QualityProfiler(
    max_standard_error=0.05,
    min_success_probability=0.95,
    min_application_score=0.90,
)

quality_estimate = quality_profiler.estimate_from_counts(
    counts=execution_result.counts,
    observable_values=observable_values,
    confidence_level=0.95,
    success_states=success_states,
    score_function=application_score,
)

print("Sample count:", quality_estimate.sample_count)
print("Expectation value:", quality_estimate.expectation_value)
print("Variance:", quality_estimate.variance)
print("Standard error:", quality_estimate.standard_error)
print("Confidence interval:", quality_estimate.confidence_interval)

print("Success probability:", quality_estimate.success_probability)
print("Application score:", quality_estimate.application_score)
print("Quality satisfied:", quality_estimate.quality_satisfied)

print(
    "Measurement probabilities:",
    quality_estimate.metadata["measurement_probabilities"]
)



# ==================================================
# STEP 7: INDEPENDENT STATISTICAL VALIDATION
# ==================================================

print("\n" + "=" * 70)
print("STEP 7: INDEPENDENT QUALITY VALIDATION")
print("=" * 70)

total_shots = sum(counts.values())

probabilities = {
    state: count / total_shots
    for state, count in counts.items()
}

expected_mean = sum(
    probabilities[state] * observable_values[state]
    for state in counts
)

expected_variance = sum(
    probabilities[state]
    * (observable_values[state] - expected_mean) ** 2
    for state in counts
)

expected_standard_error = math.sqrt(
    expected_variance / total_shots
)

z_value = NormalDist().inv_cdf(0.975)

expected_ci = (
    expected_mean - z_value * expected_standard_error,
    expected_mean + z_value * expected_standard_error,
)

assert quality_estimate.sample_count == total_shots

assert math.isclose(
    quality_estimate.expectation_value,
    expected_mean,
    rel_tol=1e-9,
    abs_tol=1e-9,
)

assert math.isclose(
    quality_estimate.variance,
    expected_variance,
    rel_tol=1e-9,
    abs_tol=1e-9,
)

assert math.isclose(
    quality_estimate.standard_error,
    expected_standard_error,
    rel_tol=1e-9,
    abs_tol=1e-9,
)

assert math.isclose(
    quality_estimate.confidence_interval[0],
    expected_ci[0],
    rel_tol=1e-9,
    abs_tol=1e-9,
)

assert math.isclose(
    quality_estimate.confidence_interval[1],
    expected_ci[1],
    rel_tol=1e-9,
    abs_tol=1e-9,
)

assert math.isclose(
    sum(probabilities.values()),
    1.0,
    abs_tol=1e-9,
)

print("PASS: Measurement probabilities are normalized.")
print("PASS: Expectation value independently verified.")
print("PASS: Variance independently verified.")
print("PASS: Standard error independently verified.")
print("PASS: Confidence interval independently verified.")


# ==================================================
# STEP 8: SEQUENTIAL PIPELINE CONSISTENCY
# ==================================================

print("\n" + "=" * 70)
print("STEP 8: PIPELINE VALIDATION")
print("=" * 70)

# WorkloadProfiler versus CircuitProfiler

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

# CircuitProfiler versus TranspilationProfiler

assert (
    transpilation_profile.logical_num_qubits
    == circuit_profile.num_qubits
)

assert (
    transpilation_profile.logical_gate_count
    == circuit_profile.total_gates
)

assert (
    transpilation_profile.logical_depth
    == circuit_profile.depth
)

# Adapter versus QualityProfiler

assert quality_estimate.sample_count == execution_result.shots

assert (
    quality_estimate.sample_count
    == sum(execution_result.counts.values())
)

print("PASS: WorkloadProfiler consistency.")
print("PASS: CircuitProfiler consistency.")
print("PASS: TranspilationProfiler consistency.")
print("PASS: Adapter execution consistency.")
print("PASS: QualityProfiler consistency.")


# ==================================================
# FINAL RESULT
# ==================================================

print("\n" + "=" * 70)
print("QFLOWPILOT SEQUENTIAL QUALITY PIPELINE COMPLETED")
print("=" * 70)

print("1. Quantum Workload: PASS")
print("2. WorkloadProfiler: PASS")
print("3. CircuitProfiler: PASS")
print("4. TranspilationProfiler: PASS")
print("5. AerIdealAdapter: PASS")
print("6. QualityProfiler: PASS")

print("\nAll sequential pipeline checks passed.")
