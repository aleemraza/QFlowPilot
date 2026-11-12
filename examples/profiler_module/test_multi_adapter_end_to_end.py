
"""
QFlowPilot: Complete Multi-Adapter End-to-End Integration Test

Pipeline:
    Real MQT Bench QASM3 Circuit
        |
        v
    WorkloadProfiler
        |
        v
    CircuitProfiler
        |
        v
    TranspilationProfiler
        |
        +--------------------------+
        |                          |
        v                          v
    Ideal Aer                  Noisy Aer
    1024 shots                 1024 shots
        |                          |
        +-------------+------------+
                      |
                      v
              QualityProfiler
              LatencyProfiler
              CostEstimator
                      |
                      v
              Distribution Comparison
                      |
                      v
              Final Comparison Report

Important:
- Both adapters execute the same original circuit.
- Both adapters use 1024 shots.
- Noisy Aer uses a configurable synthetic noise model.
- TVD compares the noisy distribution against the ideal
  distribution.
- Cost estimates use illustrative configurable rates.
- This test uses local Qiskit Aer simulation.
- It does NOT measure real IBM QPU execution or billing.
"""

from __future__ import annotations

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

from qflowpilot.adapters import (
    AerIdealAdapter,
    AerNoisyAdapter,
)

from qflowpilot.profiler.circuit_profiler import (
    CircuitProfiler,
)

from qflowpilot.profiler.workload_profiler import (
    WorkloadProfiler,
)

from qflowpilot.profiler.transpilation_profiler import (
    TranspilationProfiler,
)

from qflowpilot.profiler.quality_profiler import (
    QualityProfiler,
)

from qflowpilot.profiler.latency_profiler import (
    LatencyProfiler,
)

from qflowpilot.profiler.cost_estimator import (
    CostEstimator,
    CostModelConfig,
    CostMode,
)


# ============================================================
# 1. CONFIGURATION
# ============================================================

CIRCUIT_FILENAME = "dj_nativegates_ibm_falcon_opt2_5.qasm"

CANDIDATE_PATHS = [
    Path("workloads/mqt_bench") / CIRCUIT_FILENAME,
    Path("dataset/mqt_bench") / CIRCUIT_FILENAME,
]

# Optional circuit path override:
#
# PowerShell:
# $env:QFLOWPILOT_CIRCUIT_PATH="C:\path\to\your\circuit.qasm"

if os.getenv("QFLOWPILOT_CIRCUIT_PATH"):
    CIRCUIT_PATH = Path(
        os.environ["QFLOWPILOT_CIRCUIT_PATH"]
    )
else:
    CIRCUIT_PATH = next(
        (
            path
            for path in CANDIDATE_PATHS
            if path.exists()
        ),
        CANDIDATE_PATHS[0],
    )

WORKLOAD_ID = "mqt_bench_dj_5"

SHOTS = 1024
SEED = 42

CONFIDENCE_LEVEL = 0.95

# Synthetic noise configuration.
SINGLE_QUBIT_ERROR = 0.001
TWO_QUBIT_ERROR = 0.01
READOUT_ERROR = 0.02


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def section(title: str) -> None:
    print("\n" + "=" * 75)
    print(title)
    print("=" * 75)


def subsection(title: str) -> None:
    print("\n" + "-" * 65)
    print(title)
    print("-" * 65)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

    print(f"PASS: {message}")


def print_metric(label: str, value) -> None:
    print(f"{label:<38}: {value}")


def normalize_counts(counts: dict) -> dict[str, int]:
    """
    Normalize measurement bitstrings.

    Qiskit can display spaces between classical registers.
    Remove spaces and combine duplicate normalized states.
    """

    normalized = {}

    for state, count in counts.items():

        clean_state = str(state).replace(" ", "")

        normalized[clean_state] = (
            normalized.get(clean_state, 0) + int(count)
        )

    return normalized


def normalize_distribution(counts: dict) -> dict[str, float]:
    """Convert measurement counts into probabilities."""

    total = sum(counts.values())

    if total <= 0:
        raise ValueError(
            "Cannot normalize empty measurement counts."
        )

    return {
        state: count / total
        for state, count in counts.items()
    }


def create_observable_values(
    counts: dict[str, int],
) -> dict[str, float]:
    """
    Create a Hamming-weight observable.

    Example:
        1111 -> 4
        0101 -> 2
        0000 -> 0

    This is a measurement statistic, not a verified
    Deutsch-Jozsa application success criterion.
    """

    return {
        state: float(state.count("1"))
        for state in counts
    }


def validate_execution_result(
    result,
    adapter_name: str,
) -> None:

    check(
        result.status.name == "COMPLETED",
        f"{adapter_name} execution completed",
    )

    check(
        result.shots == SHOTS,
        f"{adapter_name} executed exactly {SHOTS} shots",
    )

    check(
        sum(result.counts.values()) == SHOTS,
        f"{adapter_name} measurement counts equal {SHOTS}",
    )

    check(
        bool(result.counts),
        f"{adapter_name} returned measurement counts",
    )


# ============================================================
# 3. WORKLOAD EXECUTION EVALUATION
# ============================================================

def evaluate_execution(
    result,
    quality_profiler: QualityProfiler,
    latency_profiler: LatencyProfiler,
):
    """
    Evaluate one adapter execution using:

        QualityProfiler
        LatencyProfiler

    Returns:
        quality_profile
        latency_profile
        normalized_counts
    """

    counts = normalize_counts(result.counts)

    observable_values = create_observable_values(counts)

    # -----------------------------------------
    # Quality estimation
    # -----------------------------------------

    quality_profile = quality_profiler.estimate_from_counts(
        counts=counts,
        observable_values=observable_values,
        confidence_level=CONFIDENCE_LEVEL,
    )

    check(
        quality_profile is not None,
        f"{result.backend_name}: quality estimation completed",
    )

    check(
        quality_profile.sample_count == SHOTS,
        f"{result.backend_name}: quality profiler processed 1024 samples",
    )

    # -----------------------------------------
    # Latency estimation
    # -----------------------------------------

    latency_profile = latency_profiler.profile_execution(
        result
    )

    check(
        latency_profile is not None,
        f"{result.backend_name}: latency profiling completed",
    )

    check(
        latency_profile.successful,
        f"{result.backend_name}: latency profile reports success",
    )

    check(
        latency_profile.qpu_execution_latency_s is not None,
        f"{result.backend_name}: execution duration is available",
    )

    check(
        latency_profile.end_to_end_latency_s is not None,
        f"{result.backend_name}: end-to-end latency is available",
    )

    return (
        quality_profile,
        latency_profile,
        counts,
    )


# ============================================================
# 4. COST ESTIMATION
# ============================================================

def estimate_execution_cost(
    result,
    latency_profile,
    cost_estimator: CostEstimator,
):
    """
    Estimate monetary cost and resource-proxy score.

    The execution duration is local Aer simulation time.
    It is not actual QPU execution time or provider billing.
    """

    execution_time = latency_profile.qpu_execution_latency_s

    # -----------------------------------------
    # Monetary estimation
    # -----------------------------------------

    monetary_estimate = cost_estimator.estimate_from_execution(
        qpu_execution_time_s=execution_time,
        shots=result.shots,
        classical_cpu_time_s=0.0,
        communication_bytes=0,
        mode=CostMode.MONETARY,
        metadata={
            "backend": result.backend_name,
            "execution_type": "local_aer_simulation",
            "real_qpu_execution": False,
            "provider_billing": False,
        },
    )

    check(
        monetary_estimate.is_complete,
        f"{result.backend_name}: monetary estimate is complete",
    )

    check(
        monetary_estimate.total_cost is not None,
        f"{result.backend_name}: monetary total is available",
    )

    check(
        monetary_estimate.total_cost >= 0,
        f"{result.backend_name}: monetary total is non-negative",
    )

    # Independently verify QPU monetary calculation.
    expected_qpu_cost = (
        execution_time
        * cost_estimator.config.qpu_cost_per_second
        + result.shots
        * cost_estimator.config.qpu_cost_per_shot
    )

    check(
        abs(
            monetary_estimate.qpu.monetary_cost
            - expected_qpu_cost
        ) < 1e-9,
        f"{result.backend_name}: QPU monetary calculation verified",
    )

    # -----------------------------------------
    # Resource-proxy estimation
    # -----------------------------------------

    resource_estimate = cost_estimator.estimate_from_execution(
        qpu_execution_time_s=execution_time,
        shots=result.shots,
        classical_cpu_time_s=0.0,
        communication_bytes=0,
        mode=CostMode.RESOURCE_PROXY,
        metadata={
            "backend": result.backend_name,
            "execution_type": "local_aer_simulation",
        },
    )

    check(
        resource_estimate.is_complete,
        f"{result.backend_name}: resource estimate is complete",
    )

    check(
        resource_estimate.total_resource_score is not None,
        f"{result.backend_name}: resource score is available",
    )

    check(
        resource_estimate.total_cost is None,
        f"{result.backend_name}: resource score is not monetary cost",
    )

    return monetary_estimate, resource_estimate


# ============================================================
# 5. MAIN END-TO-END TEST
# ============================================================

def main():

    section(
        "QFLOWPILOT COMPLETE MULTI-ADAPTER END-TO-END TEST"
    )

    # ========================================================
    # STEP 1: LOAD REAL MQT BENCH CIRCUIT
    # ========================================================

    section("STEP 1: LOAD REAL MQT BENCH QASM3 CIRCUIT")

    check(
        CIRCUIT_PATH.exists(),
        f"Circuit file exists: {CIRCUIT_PATH}",
    )

    with open(
        CIRCUIT_PATH,
        "r",
        encoding="utf-8",
    ) as file:

        circuit = qasm3.loads(file.read())

    print_metric("Circuit file", CIRCUIT_PATH.name)
    print_metric("Qubits", circuit.num_qubits)
    print_metric("Classical bits", circuit.num_clbits)
    print_metric("Circuit depth", circuit.depth())
    print_metric("Total instructions", len(circuit.data))

    check(
        circuit.num_qubits > 0,
        "Circuit contains quantum bits",
    )

    check(
        circuit.num_clbits > 0,
        "Circuit contains classical bits",
    )

    has_measurements = any(
        instruction.operation.name == "measure"
        for instruction in circuit.data
    )

    check(
        has_measurements,
        "Circuit contains measurement operations",
    )

    # ========================================================
    # STEP 2: DEFINE WORKLOAD
    # ========================================================

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
            "experiment": "Ideal versus noisy simulation",
        },
    )

    print_metric("Workload ID", workload.workload_id)
    print_metric("Workload type", workload.workload_type)
    print_metric("Algorithm", workload.algorithm)
    print_metric("Shots per adapter", SHOTS)

    # ========================================================
    # STEP 3: WORKLOAD PROFILER
    # ========================================================

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
        "Circuit profiles",
        len(workload_profile.circuit_profiles),
    )

    print_metric(
        "Total gates",
        workload_profile.metadata["total_gates"],
    )

    print_metric(
        "Average depth",
        workload_profile.metadata["average_depth"],
    )

    print_metric(
        "Maximum qubits",
        workload_profile.metadata["maximum_qubits"],
    )

    # ========================================================
    # STEP 4: CIRCUIT PROFILER
    # ========================================================

    section("STEP 4: CIRCUIT PROFILER")

    circuit_profiler = CircuitProfiler(
        include_instruction_details=False
    )

    circuit_profile = circuit_profiler.profile_circuit(
        circuit,
        source=str(CIRCUIT_PATH),
    )

    check(
        circuit_profile is not None,
        "Circuit profiling completed",
    )

    print_metric("Qubits", circuit_profile.num_qubits)
    print_metric("Circuit depth", circuit_profile.depth)
    print_metric("Total gates", circuit_profile.total_gates)
    print_metric(
        "Two-qubit gates",
        circuit_profile.two_qubit_gates,
    )

    print_metric(
        "Gate counts",
        circuit_profile.gate_counts,
    )

    print_metric(
        "Measurement count",
        circuit_profile.metadata["measurement_count"],
    )

    print_metric(
        "Connectivity",
        circuit_profile.metadata["connectivity_edges"],
    )

    # ========================================================
    # STEP 5: TRANSPILATION PROFILER
    # ========================================================

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

    check(
        transpilation_profile.transpiled_circuit is not None,
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
        "Two-qubit gates after transpilation",
        transpilation_profile.transpiled_two_qubit_gates,
    )

    print_metric(
        "Depth overhead",
        transpilation_profile.depth_overhead,
    )

    print_metric(
        "Transpilation time",
        f"{transpilation_profile.transpilation_time_s:.8f} s",
    )

    # Note:
    # TranspilationProfiler independently compiles the circuit.
    # Both adapters receive the same original circuit and perform
    # their own internal transpilation.

    # ========================================================
    # STEP 6: PREPARE TWO EXECUTION REQUESTS
    # ========================================================

    section("STEP 6: PREPARE EXECUTION REQUESTS")

    ideal_request = ExecutionRequest(
        request_id="qflowpilot_ideal_001",
        workload_id=WORKLOAD_ID,
        shots=SHOTS,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
        backend_name="aer_ideal",
        seed=SEED,
        metadata={
            "workload_id": WORKLOAD_ID,
            "circuit_file": CIRCUIT_PATH.name,
            "simulation_type": "ideal",
        },
    )

    noisy_request = ExecutionRequest(
        request_id="qflowpilot_noisy_001",
        workload_id=WORKLOAD_ID,
        shots=SHOTS,
        execution_mode=ExecutionMode.NOISY_SIMULATOR,
        backend_name="aer_noisy",
        seed=SEED,
        metadata={
            "workload_id": WORKLOAD_ID,
            "circuit_file": CIRCUIT_PATH.name,
            "simulation_type": "noisy",
        },
    )

    print_metric("Ideal request ID", ideal_request.request_id)
    print_metric("Noisy request ID", noisy_request.request_id)
    print_metric("Shots per request", SHOTS)

    check(
        ideal_request.shots == noisy_request.shots == SHOTS,
        "Both requests use the same shot count",
    )

    # ========================================================
    # STEP 7: CREATE AER ADAPTERS
    # ========================================================

    section("STEP 7: INITIALIZE AER ADAPTERS")

    ideal_adapter = AerIdealAdapter(
        backend_name="aer_ideal",
        optimization_level=1,
    )

    noisy_adapter = AerNoisyAdapter(
        backend_name="aer_noisy",
        optimization_level=1,
        single_qubit_error=SINGLE_QUBIT_ERROR,
        two_qubit_error=TWO_QUBIT_ERROR,
        readout_error=READOUT_ERROR,
    )

    check(
        ideal_adapter.is_available(),
        "Ideal Aer adapter is available",
    )

    check(
        noisy_adapter.is_available(),
        "Noisy Aer adapter is available",
    )

    print_metric("Ideal backend", "aer_ideal")
    print_metric("Noisy backend", "aer_noisy")

    print_metric(
        "Single-qubit error",
        SINGLE_QUBIT_ERROR,
    )

    print_metric(
        "Two-qubit error",
        TWO_QUBIT_ERROR,
    )

    print_metric(
        "Readout error",
        READOUT_ERROR,
    )

    # ========================================================
    # STEP 8: EXECUTE IDEAL AER
    # ========================================================

    section("STEP 8: IDEAL AER EXECUTION")

    print("Executing the original circuit using Ideal Aer...")

    ideal_result = ideal_adapter.execute(
        ideal_request,
        circuit,
    )

    ideal_result.metadata["returned_at"] = (
        datetime.now(timezone.utc)
    )

    print_metric("Execution status", ideal_result.status)
    print_metric("Backend", ideal_result.backend_name)
    print_metric("Shots", ideal_result.shots)
    print_metric("Measurement counts", ideal_result.counts)

    validate_execution_result(
        ideal_result,
        "Ideal Aer",
    )

    # ========================================================
    # STEP 9: EXECUTE NOISY AER
    # ========================================================

    section("STEP 9: NOISY AER EXECUTION")

    print("Executing the same original circuit using Noisy Aer...")

    noisy_result = noisy_adapter.execute(
        noisy_request,
        circuit,
    )

    noisy_result.metadata["returned_at"] = (
        datetime.now(timezone.utc)
    )

    print_metric("Execution status", noisy_result.status)
    print_metric("Backend", noisy_result.backend_name)
    print_metric("Shots", noisy_result.shots)
    print_metric("Measurement counts", noisy_result.counts)

    validate_execution_result(
        noisy_result,
        "Noisy Aer",
    )

    # ========================================================
    # STEP 10: QUALITY AND LATENCY PROFILING
    # ========================================================

    section("STEP 10: QUALITY AND LATENCY PROFILING")

    quality_profiler = QualityProfiler()

    latency_profiler = LatencyProfiler()

    (
        ideal_quality,
        ideal_latency,
        ideal_counts,
    ) = evaluate_execution(
        ideal_result,
        quality_profiler,
        latency_profiler,
    )

    (
        noisy_quality,
        noisy_latency,
        noisy_counts,
    ) = evaluate_execution(
        noisy_result,
        quality_profiler,
        latency_profiler,
    )

    # --------------------------------------------------------
    # IDEAL QUALITY RESULTS
    # --------------------------------------------------------

    subsection("IDEAL AER QUALITY")

    print_metric(
        "Sample count",
        ideal_quality.sample_count,
    )

    print_metric(
        "Expectation value",
        ideal_quality.expectation_value,
    )

    print_metric(
        "Variance",
        ideal_quality.variance,
    )

    print_metric(
        "Standard error",
        ideal_quality.standard_error,
    )

    print_metric(
        "Confidence interval",
        ideal_quality.confidence_interval,
    )

    print_metric(
        "Success probability",
        ideal_quality.success_probability,
    )

    # --------------------------------------------------------
    # NOISY QUALITY RESULTS
    # --------------------------------------------------------

    subsection("NOISY AER QUALITY")

    print_metric(
        "Sample count",
        noisy_quality.sample_count,
    )

    print_metric(
        "Expectation value",
        noisy_quality.expectation_value,
    )

    print_metric(
        "Variance",
        noisy_quality.variance,
    )

    print_metric(
        "Standard error",
        noisy_quality.standard_error,
    )

    print_metric(
        "Confidence interval",
        noisy_quality.confidence_interval,
    )

    print_metric(
        "Success probability",
        noisy_quality.success_probability,
    )

    # --------------------------------------------------------
    # IDEAL LATENCY RESULTS
    # --------------------------------------------------------

    subsection("IDEAL AER LATENCY")

    print_metric(
        "Pre-execution delay",
        f"{ideal_latency.queue_latency_s:.8f} s",
    )

    print_metric(
        "Aer execution duration",
        f"{ideal_latency.qpu_execution_latency_s:.8f} s",
    )

    print_metric(
        "End-to-end latency",
        f"{ideal_latency.end_to_end_latency_s:.8f} s",
    )

    # --------------------------------------------------------
    # NOISY LATENCY RESULTS
    # --------------------------------------------------------

    subsection("NOISY AER LATENCY")

    print_metric(
        "Pre-execution delay",
        f"{noisy_latency.queue_latency_s:.8f} s",
    )

    print_metric(
        "Aer execution duration",
        f"{noisy_latency.qpu_execution_latency_s:.8f} s",
    )

    print_metric(
        "End-to-end latency",
        f"{noisy_latency.end_to_end_latency_s:.8f} s",
    )

    # ========================================================
    # STEP 11: IDEAL VS NOISY DISTRIBUTION COMPARISON
    # ========================================================

    section("STEP 11: MEASUREMENT DISTRIBUTION COMPARISON")

    ideal_distribution = normalize_distribution(
        ideal_counts
    )

    noisy_distribution = normalize_distribution(
        noisy_counts
    )

    print("\nIdeal probability distribution:")
    for state, probability in sorted(
        ideal_distribution.items()
    ):
        print(f"  {state}: {probability:.6f}")

    print("\nNoisy probability distribution:")
    for state, probability in sorted(
        noisy_distribution.items()
    ):
        print(f"  {state}: {probability:.6f}")

    # Use all observed states from both distributions.
    all_states = (
        set(ideal_distribution)
        | set(noisy_distribution)
    )

    ideal_reference = {
        state: ideal_distribution.get(state, 0.0)
        for state in all_states
    }

    noisy_observed = {
        state: noisy_distribution.get(state, 0.0)
        for state in all_states
    }

    tvd = quality_profiler.total_variation_distance(
        reference_distribution=ideal_reference,
        observed_distribution=noisy_observed,
    )

    print_metric(
        "Ideal vs Noisy TVD",
        tvd,
    )

    check(
        0.0 <= tvd <= 1.0,
        "TVD is within valid probability bounds",
    )

    # ========================================================
    # STEP 12: CONFIGURE COST ESTIMATOR
    # ========================================================

    section("STEP 12: CONFIGURE COST ESTIMATOR")

    cost_config = CostModelConfig(
        # Illustrative monetary rates.
        qpu_cost_per_second=0.05,
        qpu_cost_per_shot=0.0001,
        classical_cost_per_cpu_second=0.001,
        communication_cost_per_gb=0.02,

        # Illustrative resource-proxy weights.
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

    print_metric(
        "Classical rate per second",
        cost_config.classical_cost_per_cpu_second,
    )

    print_metric(
        "Communication rate per GB",
        cost_config.communication_cost_per_gb,
    )

    # ========================================================
    # STEP 13: IDEAL AER COST ESTIMATION
    # ========================================================

    section("STEP 13: IDEAL AER COST ESTIMATION")

    (
        ideal_monetary,
        ideal_resource,
    ) = estimate_execution_cost(
        ideal_result,
        ideal_latency,
        cost_estimator,
    )

    print("\nIDEAL AER MONETARY COST")

    print_metric(
        "QPU cost",
        ideal_monetary.qpu.monetary_cost,
    )

    print_metric(
        "Classical cost",
        ideal_monetary.classical.monetary_cost,
    )

    print_metric(
        "Communication cost",
        ideal_monetary.communication.monetary_cost,
    )

    print_metric(
        "Total monetary cost",
        ideal_monetary.total_cost,
    )

    print_metric(
        "Cost per shot",
        ideal_monetary.monetary_cost_per_shot,
    )

    print("\nIDEAL AER RESOURCE PROXY")

    print_metric(
        "QPU resource score",
        ideal_resource.qpu.resource_score,
    )

    print_metric(
        "Classical resource score",
        ideal_resource.classical.resource_score,
    )

    print_metric(
        "Communication resource score",
        ideal_resource.communication.resource_score,
    )

    print_metric(
        "Total resource score",
        ideal_resource.total_resource_score,
    )

    # ========================================================
    # STEP 14: NOISY AER COST ESTIMATION
    # ========================================================

    section("STEP 14: NOISY AER COST ESTIMATION")

    (
        noisy_monetary,
        noisy_resource,
    ) = estimate_execution_cost(
        noisy_result,
        noisy_latency,
        cost_estimator,
    )

    print("\nNOISY AER MONETARY COST")

    print_metric(
        "QPU cost",
        noisy_monetary.qpu.monetary_cost,
    )

    print_metric(
        "Classical cost",
        noisy_monetary.classical.monetary_cost,
    )

    print_metric(
        "Communication cost",
        noisy_monetary.communication.monetary_cost,
    )

    print_metric(
        "Total monetary cost",
        noisy_monetary.total_cost,
    )

    print_metric(
        "Cost per shot",
        noisy_monetary.monetary_cost_per_shot,
    )

    print("\nNOISY AER RESOURCE PROXY")

    print_metric(
        "QPU resource score",
        noisy_resource.qpu.resource_score,
    )

    print_metric(
        "Classical resource score",
        noisy_resource.classical.resource_score,
    )

    print_metric(
        "Communication resource score",
        noisy_resource.communication.resource_score,
    )

    print_metric(
        "Total resource score",
        noisy_resource.total_resource_score,
    )

    # ========================================================
    # STEP 15: FINAL SIDE-BY-SIDE COMPARISON
    # ========================================================

    section("STEP 15: FINAL IDEAL VS NOISY COMPARISON")

    print(
        f"{'METRIC':<34}"
        f"{'IDEAL AER':>19}"
        f"{'NOISY AER':>19}"
    )

    print("-" * 72)

    comparison_rows = [
        (
            "Shots",
            ideal_result.shots,
            noisy_result.shots,
        ),
        (
            "Expectation",
            ideal_quality.expectation_value,
            noisy_quality.expectation_value,
        ),
        (
            "Variance",
            ideal_quality.variance,
            noisy_quality.variance,
        ),
        (
            "Standard error",
            ideal_quality.standard_error,
            noisy_quality.standard_error,
        ),
        (
            "Pre-execution delay (s)",
            ideal_latency.queue_latency_s,
            noisy_latency.queue_latency_s,
        ),
        (
            "Execution duration (s)",
            ideal_latency.qpu_execution_latency_s,
            noisy_latency.qpu_execution_latency_s,
        ),
        (
            "End-to-end latency (s)",
            ideal_latency.end_to_end_latency_s,
            noisy_latency.end_to_end_latency_s,
        ),
        (
            "Monetary cost",
            ideal_monetary.total_cost,
            noisy_monetary.total_cost,
        ),
        (
            "Cost per shot",
            ideal_monetary.monetary_cost_per_shot,
            noisy_monetary.monetary_cost_per_shot,
        ),
        (
            "Resource proxy",
            ideal_resource.total_resource_score,
            noisy_resource.total_resource_score,
        ),
    ]

    for label, ideal_value, noisy_value in comparison_rows:

        print(
            f"{label:<34}"
            f"{str(ideal_value):>19}"
            f"{str(noisy_value):>19}"
        )

    print("-" * 72)

    print(f"{'Distribution TVD':<34}{'Reference':>19}{str(tvd):>19}")

    # ========================================================
    # STEP 16: FINAL REPORT AND VALIDATION
    # ========================================================

    section("FINAL QFLOWPILOT INTEGRATION REPORT")

    subsection("WORKLOAD")

    print_metric("Workload ID", WORKLOAD_ID)
    print_metric("Algorithm", workload.algorithm)
    print_metric("Circuit file", CIRCUIT_PATH.name)
    print_metric(
        "Number of circuits",
        len(workload_profile.circuit_profiles),
    )

    subsection("CIRCUIT")

    print_metric("Qubits", circuit_profile.num_qubits)
    print_metric("Classical bits", circuit.num_clbits)
    print_metric("Depth", circuit_profile.depth)
    print_metric("Total gates", circuit_profile.total_gates)
    print_metric(
        "Two-qubit gates",
        circuit_profile.two_qubit_gates,
    )

    subsection("TRANSPILATION")

    print_metric(
        "Transpiled depth",
        transpilation_profile.transpiled_depth,
    )

    print_metric(
        "Transpiled gate count",
        transpilation_profile.transpiled_gate_count,
    )

    print_metric(
        "Transpilation time",
        f"{transpilation_profile.transpilation_time_s:.8f} s",
    )

    subsection("EXECUTION")

    print_metric("Ideal shots", ideal_result.shots)
    print_metric("Noisy shots", noisy_result.shots)

    print_metric(
        "Ideal execution status",
        ideal_result.status,
    )

    print_metric(
        "Noisy execution status",
        noisy_result.status,
    )

    subsection("QUALITY")

    print_metric(
        "Ideal expectation",
        ideal_quality.expectation_value,
    )

    print_metric(
        "Noisy expectation",
        noisy_quality.expectation_value,
    )

    print_metric(
        "Ideal variance",
        ideal_quality.variance,
    )

    print_metric(
        "Noisy variance",
        noisy_quality.variance,
    )

    print_metric(
        "Ideal standard error",
        ideal_quality.standard_error,
    )

    print_metric(
        "Noisy standard error",
        noisy_quality.standard_error,
    )

    print_metric(
        "Distribution TVD",
        tvd,
    )

    subsection("LATENCY")

    print_metric(
        "Ideal execution duration",
        f"{ideal_latency.qpu_execution_latency_s:.8f} s",
    )

    print_metric(
        "Noisy execution duration",
        f"{noisy_latency.qpu_execution_latency_s:.8f} s",
    )

    print_metric(
        "Ideal end-to-end latency",
        f"{ideal_latency.end_to_end_latency_s:.8f} s",
    )

    print_metric(
        "Noisy end-to-end latency",
        f"{noisy_latency.end_to_end_latency_s:.8f} s",
    )

    subsection("COST")

    print_metric(
        "Ideal monetary cost",
        ideal_monetary.total_cost,
    )

    print_metric(
        "Noisy monetary cost",
        noisy_monetary.total_cost,
    )

    print_metric(
        "Ideal resource proxy",
        ideal_resource.total_resource_score,
    )

    print_metric(
        "Noisy resource proxy",
        noisy_resource.total_resource_score,
    )

    subsection("EXECUTION CLASSIFICATION")

    print_metric(
        "Execution environment",
        "Local Qiskit Aer",
    )

    print_metric(
        "Ideal simulation",
        True,
    )

    print_metric(
        "Synthetic noisy simulation",
        True,
    )

    print_metric(
        "Real QPU execution",
        False,
    )

    print_metric(
        "Real provider billing",
        False,
    )

    print_metric(
        "Cost rates",
        "Illustrative configurable rates",
    )

    print_metric(
        "Application-level success verified",
        False,
    )

    # --------------------------------------------------------
    # FINAL CHECKS
    # --------------------------------------------------------

    section("FINAL PIPELINE VALIDATION")

    check(
        workload_profile is not None,
        "WorkloadProfiler integrated",
    )

    check(
        circuit_profile is not None,
        "CircuitProfiler integrated",
    )

    check(
        transpilation_profile is not None,
        "TranspilationProfiler integrated",
    )

    check(
        ideal_result.status.name == "COMPLETED",
        "Ideal Aer execution successful",
    )

    check(
        noisy_result.status.name == "COMPLETED",
        "Noisy Aer execution successful",
    )

    check(
        ideal_quality is not None and noisy_quality is not None,
        "QualityProfiler evaluated both executions",
    )

    check(
        ideal_latency is not None and noisy_latency is not None,
        "LatencyProfiler evaluated both executions",
    )

    check(
        ideal_monetary is not None
        and noisy_monetary is not None,
        "CostEstimator calculated both monetary estimates",
    )

    check(
        ideal_resource is not None
        and noisy_resource is not None,
        "CostEstimator calculated both resource estimates",
    )

    check(
        0.0 <= tvd <= 1.0,
        "Ideal versus noisy distribution comparison completed",
    )

    section(
        "QFLOWPILOT MULTI-ADAPTER END-TO-END TEST PASSED"
    )

    print(
        "All pipeline stages completed successfully."
    )

    print(
        "Ideal Aer and Noisy Aer comparison completed."
    )

    print(
        "Both adapters executed the same circuit using 1024 shots."
    )

    print(
        "Quality, latency, cost, and distribution metrics generated."
    )


# ============================================================
# 6. ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:
        main()

    except Exception as error:

        section(
            "QFLOWPILOT MULTI-ADAPTER TEST FAILED"
        )

        print(f"Error: {error}")

        traceback.print_exc()

        sys.exit(1)
