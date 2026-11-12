
"""
QFlowPilot: Complete End-to-End Integration Test

Flow:
    MQT Bench QASM3 Workload
        -> WorkloadProfiler
        -> CircuitProfiler
        -> TranspilationProfiler
        -> AerIdealAdapter
        -> QualityProfiler
        -> LatencyProfiler
        -> CostEstimator
        -> Final Execution Report

This test uses local Qiskit Aer simulation.
It does NOT measure real IBM QPU execution or provider billing.
"""

from pathlib import Path
from datetime import datetime, timezone
import os
import sys
import traceback

from qiskit import qasm3

from qflowpilot.core.models import (
    WorkloadSpec,
    WorkloadType,
    ExecutionRequest,
    ExecutionMode,
)

from qflowpilot.adapters import AerIdealAdapter

from qflowpilot.profiler.circuit_profiler import CircuitProfiler
from qflowpilot.profiler.workload_profiler import WorkloadProfiler
from qflowpilot.profiler.transpilation_profiler import TranspilationProfiler
from qflowpilot.profiler.quality_profiler import QualityProfiler
from qflowpilot.profiler.latency_profiler import LatencyProfiler
from qflowpilot.profiler.cost_estimator import (
    CostEstimator,
    CostModelConfig,
    CostMode,
)


# ============================================================
# CONFIGURATION
# ============================================================

CIRCUIT_FILENAME = "dj_nativegates_ibm_falcon_opt2_5.qasm"

CANDIDATE_PATHS = [
    Path("workloads/mqt_bench") / CIRCUIT_FILENAME,
    Path("dataset/mqt_bench") / CIRCUIT_FILENAME,
]

# Optional override:
# PowerShell:
# $env:QFLOWPILOT_CIRCUIT_PATH="C:\path\to\your\circuit.qasm"

if os.getenv("QFLOWPILOT_CIRCUIT_PATH"):
    CIRCUIT_PATH = Path(os.environ["QFLOWPILOT_CIRCUIT_PATH"])
else:
    CIRCUIT_PATH = next(
        (path for path in CANDIDATE_PATHS if path.exists()),
        CANDIDATE_PATHS[0],
    )

WORKLOAD_ID = "mqt_bench_dj_5"
REQUEST_ID = "qflowpilot_e2e_001"

SHOTS = 1024
SEED = 42


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def check(condition, message):
    if not condition:
        raise AssertionError(message)

    print(f"PASS: {message}")


def print_metric(label, value):
    print(f"{label:<35}: {value}")


# ============================================================
# MAIN END-TO-END TEST
# ============================================================

def main():

    section("QFLOWPILOT COMPLETE END-TO-END INTEGRATION TEST")

    # --------------------------------------------------------
    # STEP 1: LOAD REAL QUANTUM WORKLOAD
    # --------------------------------------------------------

    section("STEP 1: LOAD REAL QUANTUM WORKLOAD")

    check(CIRCUIT_PATH.exists(), f"Circuit file exists: {CIRCUIT_PATH}")

    with open(CIRCUIT_PATH, "r", encoding="utf-8") as file:
        circuit = qasm3.loads(file.read())

    print_metric("Circuit file", CIRCUIT_PATH.name)
    print_metric("Qubits", circuit.num_qubits)
    print_metric("Classical bits", circuit.num_clbits)
    print_metric("Circuit depth", circuit.depth())
    print_metric("Total instructions", len(circuit.data))

    check(circuit.num_qubits > 0, "Circuit contains qubits")
    check(circuit.num_clbits > 0, "Circuit contains classical bits")

    has_measurements = any(
        instruction.operation.name == "measure"
        for instruction in circuit.data
    )

    check(has_measurements, "Circuit contains measurements")

    # --------------------------------------------------------
    # STEP 2: DEFINE WORKLOAD
    # --------------------------------------------------------

    section("STEP 2: DEFINE QFLOWPILOT WORKLOAD")

    workload = WorkloadSpec(
        workload_id=WORKLOAD_ID,
        name="MQT Bench Deutsch-Jozsa Workload",
        workload_type=WorkloadType.BATCH,
        algorithm="Deutsch-Jozsa",
        application="Quantum algorithm benchmarking",
        description="Five-qubit MQT Bench QASM3 circuit",
        metadata={
            "source": "MQT Bench",
            "circuit_file": CIRCUIT_PATH.name,
            "shots": SHOTS,
        },
    )

    print_metric("Workload ID", workload.workload_id)
    print_metric("Workload type", workload.workload_type)
    print_metric("Algorithm", workload.algorithm)

    # --------------------------------------------------------
    # STEP 3: WORKLOAD PROFILING
    # --------------------------------------------------------

    section("STEP 3: WORKLOAD PROFILER")

    workload_profiler = WorkloadProfiler()

    workload_profile = workload_profiler.profile_workload(
        workload,
        [circuit],
    )

    check(
        workload_profile is not None,
        "Workload profiling completed",
    )

    check(
        len(workload_profile.circuit_profiles) == 1,
        "One circuit profile generated",
    )

    print_metric(
        "Number of circuit profiles",
        len(workload_profile.circuit_profiles),
    )

    # --------------------------------------------------------
    # STEP 4: CIRCUIT PROFILING
    # --------------------------------------------------------

    section("STEP 4: CIRCUIT PROFILER")

    circuit_profiler = CircuitProfiler()

    circuit_profile = circuit_profiler.profile_circuit(
        circuit,
        source=str(CIRCUIT_PATH),
    )

    check(
        circuit_profile is not None,
        "Circuit profiling completed",
    )

    print("Circuit profile:")
    print(circuit_profile)

    # --------------------------------------------------------
    # STEP 5: TRANSPILATION PROFILING
    # --------------------------------------------------------

    section("STEP 5: TRANSPILATION PROFILER")

    transpilation_profiler = TranspilationProfiler(
        basis_gates=["rz", "sx", "x", "cx"],
        optimization_level=1,
        seed_transpiler=SEED,
    )

    transpilation_profile = (
        transpilation_profiler.profile_circuit(circuit)
    )

    check(
        transpilation_profile is not None,
        "Transpilation profiling completed",
    )

    transpiled_circuit = transpilation_profile.transpiled_circuit

    check(
        transpiled_circuit is not None,
        "Transpiled circuit is available",
    )

    print_metric(
        "Logical depth",
        transpilation_profile.logical_depth,
    )

    print_metric(
        "Transpiled depth",
        transpilation_profile.transpiled_depth,
    )

    print_metric(
        "Logical gate count",
        transpilation_profile.logical_gate_count,
    )

    print_metric(
        "Transpiled gate count",
        transpilation_profile.transpiled_gate_count,
    )

    print_metric(
        "Depth overhead",
        transpilation_profile.depth_overhead,
    )

    # --------------------------------------------------------
    # STEP 6: PREPARE EXECUTION REQUEST
    # --------------------------------------------------------

    section("STEP 6: PREPARE EXECUTION REQUEST")

    request = ExecutionRequest(
        request_id=REQUEST_ID,
        workload_id=WORKLOAD_ID,
        shots=SHOTS,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
        backend_name="aer_ideal",
        seed=SEED,
        metadata={
            "workload_id": WORKLOAD_ID,
            "circuit_file": CIRCUIT_PATH.name,
        },
    )

    print_metric("Request ID", request.request_id)
    print_metric("Shots", request.shots)
    print_metric("Execution mode", request.execution_mode)

    # --------------------------------------------------------
    # STEP 7: EXECUTE USING AER ADAPTER
    # --------------------------------------------------------

    section("STEP 7: AER IDEAL ADAPTER EXECUTION")

    adapter = AerIdealAdapter(
        backend_name="aer_ideal",
        optimization_level=1,
    )

    result = adapter.execute(request, circuit)

    # Record the time at which control returns to this caller.
    result.metadata["returned_at"] = datetime.now(timezone.utc)

    print_metric("Execution status", result.status)
    print_metric("Backend", result.backend_name)
    print_metric("Executed shots", result.shots)
    print_metric("Measurement counts", result.counts)

    check(
        result.status.name == "COMPLETED",
        "Aer execution completed successfully",
    )

    check(
        sum(result.counts.values()) == SHOTS,
        "Measurement counts equal requested shots",
    )

    # --------------------------------------------------------
    # STEP 8: QUALITY PROFILING
    # --------------------------------------------------------

    section("STEP 8: QUALITY PROFILER")

    quality_profiler = QualityProfiler()

    # Hamming-weight observable:
    # For example, 1111 -> 4 and 0101 -> 2.
    #
    # This is a measurement statistic, not an application-level
    # correctness score for the Deutsch-Jozsa algorithm.

    observable_values = {
        state: float(state.replace(" ", "").count("1"))
        for state in result.counts
    }

    quality_profile = quality_profiler.estimate_from_counts(
        counts=result.counts,
        observable_values=observable_values,
        confidence_level=0.95,
    )

    check(
        quality_profile is not None,
        "Quality estimation completed",
    )

    print_metric(
        "Total samples",
        quality_profile.sample_count,
    )

    print_metric(
        "Expectation value",
        quality_profile.expectation_value,
    )

    print_metric(
        "Variance",
        quality_profile.variance,
    )

    print_metric(
        "Standard error",
        quality_profile.standard_error,
    )

    print_metric(
        "Confidence interval",
        quality_profile.confidence_interval,
    )

    print_metric(
        "Success probability",
        quality_profile.success_probability,
    )

    # --------------------------------------------------------
    # STEP 9: LATENCY PROFILING
    # --------------------------------------------------------

    section("STEP 9: LATENCY PROFILER")

    latency_profiler = LatencyProfiler()

    latency_profile = latency_profiler.profile_execution(result)

    check(
        latency_profile is not None,
        "Execution latency profiling completed",
    )

    print_metric(
        "Pre-execution delay",
        f"{latency_profile.queue_latency_s:.8f} seconds",
    )

    print_metric(
        "Aer execution duration",
        f"{latency_profile.qpu_execution_latency_s:.8f} seconds",
    )

    print_metric(
        "End-to-end latency",
        f"{latency_profile.end_to_end_latency_s:.8f} seconds",
    )

    check(
        latency_profile.successful,
        "Latency profile reports successful execution",
    )

    check(
        latency_profile.end_to_end_latency_s >= 0,
        "End-to-end latency is non-negative",
    )

    # --------------------------------------------------------
    # STEP 10: COST MODEL CONFIGURATION
    # --------------------------------------------------------

    section("STEP 10: CONFIGURE COST MODEL")

    cost_config = CostModelConfig(
        qpu_cost_per_second=0.05,
        qpu_cost_per_shot=0.0001,
        classical_cost_per_cpu_second=0.001,
        communication_cost_per_gb=0.02,

        qpu_seconds_weight=0.1,
        shots_weight=0.0002,
        classical_cpu_seconds_weight=0.05,
        communication_gb_weight=0.04,

        currency="USD",
    )

    cost_estimator = CostEstimator(cost_config)

    print_metric("Currency", cost_config.currency)
    print_metric(
        "QPU rate per second",
        cost_config.qpu_cost_per_second,
    )
    print_metric(
        "QPU rate per shot",
        cost_config.qpu_cost_per_shot,
    )

   
    # --------------------------------------------------------
    # STEP 11: MONETARY COST ESTIMATION
    # --------------------------------------------------------

    section("STEP 11: MONETARY COST ESTIMATION")

    monetary_estimate = cost_estimator.estimate_from_execution(
        qpu_execution_time_s=latency_profile.qpu_execution_latency_s,
        shots=result.shots,
        classical_cpu_time_s=0.0,
        communication_bytes=0,
        mode=CostMode.MONETARY,
        metadata={
            "workload_id": WORKLOAD_ID,
            "backend": result.backend_name,
            "execution_type": "local_aer_simulation",
        },
    )

    print("QPU cost:", monetary_estimate.qpu.monetary_cost)
    print("Classical cost:", monetary_estimate.classical.monetary_cost)
    print("Communication cost:", monetary_estimate.communication.monetary_cost)
    print("Total cost:", monetary_estimate.total_cost)
    print("Currency:", monetary_estimate.currency)
    print("Cost per shot:", monetary_estimate.monetary_cost_per_shot)

    check(
        monetary_estimate.is_complete,
        "All monetary cost components are available",
    )

    check(
        monetary_estimate.total_cost is not None,
        "Total monetary cost is available",
    )

    check(
        monetary_estimate.total_cost >= 0,
        "Total monetary cost is non-negative",
    )

    expected_qpu_cost = (
        latency_profile.qpu_execution_latency_s
        * cost_config.qpu_cost_per_second
        + result.shots * cost_config.qpu_cost_per_shot
    )

    check(
        abs(
            monetary_estimate.qpu.monetary_cost - expected_qpu_cost
        ) < 1e-9,
        "QPU cost matches independent calculation",
    )

    expected_total = (
        monetary_estimate.qpu.monetary_cost
        + monetary_estimate.classical.monetary_cost
        + monetary_estimate.communication.monetary_cost
    )

    check(
        abs(monetary_estimate.total_cost - expected_total) < 1e-9,
        "Total cost matches independent calculation",
    )


   
    # --------------------------------------------------------
    # STEP 12: RESOURCE-PROXY ESTIMATION
    # --------------------------------------------------------

    section("STEP 12: RESOURCE-PROXY ESTIMATION")

    resource_estimate = cost_estimator.estimate_from_execution(
        qpu_execution_time_s=latency_profile.qpu_execution_latency_s,
        shots=result.shots,
        classical_cpu_time_s=0.0,
        communication_bytes=0,
        mode=CostMode.RESOURCE_PROXY,
        metadata={
            "workload_id": WORKLOAD_ID,
            "backend": result.backend_name,
        },
    )

    print("QPU resource score:", resource_estimate.qpu.resource_score)
    print("Classical resource score:", resource_estimate.classical.resource_score)
    print("Communication resource score:", resource_estimate.communication.resource_score)
    print("Total resource score:", resource_estimate.total_resource_score)

    check(
        resource_estimate.is_complete,
        "All resource-proxy components are available",
    )

    check(
        resource_estimate.total_resource_score is not None,
        "Total resource score is available",
    )

    check(
        resource_estimate.total_cost is None,
        "Resource score is not treated as monetary cost",
    )


    # --------------------------------------------------------
    # STEP 13: FINAL QFLOWPILOT REPORT
    # --------------------------------------------------------

    section("FINAL QFLOWPILOT END-TO-END REPORT")

    print_metric("Workload", WORKLOAD_ID)
    print_metric("Algorithm", workload.algorithm)
    print_metric("Circuit", CIRCUIT_PATH.name)

    print("\nWORKLOAD")
    print_metric("Circuit profiles", len(workload_profile.circuit_profiles))

    print("\nCIRCUIT")
    print_metric("Qubits", circuit.num_qubits)
    print_metric("Classical bits", circuit.num_clbits)
    print_metric("Original depth", circuit.depth())

    print("\nTRANSPILATION")
    print_metric(
        "Transpiled depth",
        transpilation_profile.transpiled_depth,
    )
    print_metric(
        "Transpiled gates",
        transpilation_profile.transpiled_gate_count,
    )

    print("\nEXECUTION")
    print_metric("Backend", result.backend_name)
    print_metric("Shots", result.shots)
    print_metric("Counts", result.counts)
    print_metric("Status", result.status)

    print("\nQUALITY")
    print_metric(
        "Expectation",
        quality_profile.expectation_value,
    )
    print_metric(
        "Variance",
        quality_profile.variance,
    )
    print_metric(
        "Standard error",
        quality_profile.standard_error,
    )

    print("\nLATENCY")
    print_metric(
        "Pre-execution delay",
        f"{latency_profile.queue_latency_s:.8f} s",
    )
    print_metric(
        "Aer execution duration",
        f"{latency_profile.qpu_execution_latency_s:.8f} s",
    )
    print_metric(
        "End-to-end latency",
        f"{latency_profile.end_to_end_latency_s:.8f} s",
    )

    
    print("Estimated monetary cost:", monetary_estimate.total_cost)
    print("Monetary cost per shot:", monetary_estimate.monetary_cost_per_shot)
    print("Resource-proxy score:", resource_estimate.total_resource_score)
    print("Accounting mode:", monetary_estimate.mode)
    print("Metadata:", monetary_estimate.metadata)

    print("\nEXECUTION CLASSIFICATION")
    print_metric("Execution environment", "Local Qiskit Aer")
    print_metric("Real QPU execution", False)
    print_metric("Real provider billing", False)
    print_metric("Cost rates", "Illustrative configurable rates")

    section("QFLOWPILOT END-TO-END TEST PASSED")

    print("All pipeline stages completed successfully.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:
        main()

    except Exception as error:
        section("QFLOWPILOT END-TO-END TEST FAILED")
        print(f"Error: {error}")
        traceback.print_exc()
        sys.exit(1)
