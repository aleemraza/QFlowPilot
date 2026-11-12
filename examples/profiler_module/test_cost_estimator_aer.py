
"""
QFlowPilot: Aer + LatencyProfiler + CostEstimator integration test.

Run from the project root:

    python examples/profiler_module/test_cost_estimator_aer.py
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace

from qiskit import qasm3

from qflowpilot.adapters.aer_ideal_adapter import AerIdealAdapter

from qflowpilot.core.models import (
    ExecutionMode,
    ExecutionStatus,
)

from qflowpilot.profiler.latency_profiler import LatencyProfiler

from qflowpilot.profiler.cost_estimator import (
    CostEstimator,
    CostModelConfig,
    CostMode,
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

SHOTS = 1024
SEED = 42

CIRCUIT_RELATIVE_PATH = (
    "workloads/mqt_bench/"
    "dj_nativegates_ibm_falcon_opt2_5.qasm"
)


# ---------------------------------------------------------
# Helper functions
# ---------------------------------------------------------

def check(condition: bool, description: str) -> None:

    if not condition:
        raise AssertionError(f"FAILED: {description}")

    print(f"PASS: {description}")


def load_circuit():

    project_root = Path(__file__).resolve().parents[2]

    if len(sys.argv) > 1:
        circuit_path = Path(sys.argv[1]).expanduser().resolve()
    else:
        circuit_path = project_root / CIRCUIT_RELATIVE_PATH

    if not circuit_path.exists():
        raise FileNotFoundError(
            f"Circuit not found: {circuit_path}"
        )

    with open(circuit_path, "r", encoding="utf-8") as file:
        circuit = qasm3.loads(file.read())

    return circuit


# ---------------------------------------------------------
# Main integration test
# ---------------------------------------------------------

def main():

    print("\n" + "=" * 70)
    print("QFLOWPILOT: AER + COST ESTIMATOR INTEGRATION TEST")
    print("=" * 70)

    # -----------------------------------------------------
    # STEP 1: Load actual MQT Bench circuit
    # -----------------------------------------------------

    print("\nSTEP 1: LOAD REAL QUANTUM WORKLOAD")
    print("-" * 70)

    circuit = load_circuit()

    print("Qubits:", circuit.num_qubits)
    print("Classical bits:", circuit.num_clbits)
    print("Circuit depth:", circuit.depth())

    check(circuit.num_qubits > 0, "Circuit loaded")
    check(circuit.num_clbits > 0, "Circuit has measurements")

    # -----------------------------------------------------
    # STEP 2: Prepare simulator request
    # -----------------------------------------------------

    print("\nSTEP 2: PREPARE EXECUTION REQUEST")
    print("-" * 70)

    request = SimpleNamespace(
        request_id="qflowpilot_cost_001",
        shots=SHOTS,
        seed=SEED,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
    )

    print("Request ID:", request.request_id)
    print("Shots:", request.shots)

    # -----------------------------------------------------
    # STEP 3: Execute actual circuit using Aer
    # -----------------------------------------------------

    print("\nSTEP 3: EXECUTE CIRCUIT ON AER")
    print("-" * 70)

    adapter = AerIdealAdapter(
        backend_name="aer_ideal",
        optimization_level=1,
    )

    result = adapter.execute(
        request=request,
        circuit=circuit,
    )

    returned_at = datetime.now(timezone.utc)
    result.metadata["returned_at"] = returned_at

    print("Status:", result.status)
    print("Backend:", result.backend_name)
    print("Shots:", result.shots)
    print("Counts:", result.counts)

    check(
        result.status == ExecutionStatus.COMPLETED,
        "Aer execution completed",
    )

    check(
        sum(result.counts.values()) == SHOTS,
        "Actual counts equal requested shots",
    )

    # -----------------------------------------------------
    # STEP 4: Measure execution latency
    # -----------------------------------------------------

    print("\nSTEP 4: MEASURE ACTUAL EXECUTION LATENCY")
    print("-" * 70)

    latency_profiler = LatencyProfiler()

    latency_profile = latency_profiler.profile_execution(result)

    qpu_time_proxy_s = (
        latency_profile.qpu_execution_latency_s
    )

    print("Pre-execution delay:",
          latency_profile.queue_latency_s, "seconds")

    print("Aer execution duration:",
          qpu_time_proxy_s, "seconds")

    print("End-to-end duration:",
          latency_profile.end_to_end_latency_s, "seconds")

    check(
        qpu_time_proxy_s >= 0,
        "Aer execution duration is valid",
    )

    # -----------------------------------------------------
    # STEP 5: Configure CostEstimator
    # -----------------------------------------------------

    print("\nSTEP 5: CONFIGURE COST MODEL")
    print("-" * 70)

    # Illustrative rates only.
    # These are NOT actual IBM Quantum prices.

    config = CostModelConfig(
        currency="USD",

        # Monetary rates
        qpu_cost_per_second=0.05,
        qpu_cost_per_shot=0.0001,
        classical_cost_per_cpu_second=0.001,
        communication_cost_per_gb=0.02,

        # Resource-proxy weights
        qpu_seconds_weight=0.1,
        shots_weight=0.0002,
        classical_cpu_seconds_weight=0.05,
        communication_gb_weight=0.04,
    )

    estimator = CostEstimator(config)

    print("Currency:", config.currency)
    print("QPU cost per second:", config.qpu_cost_per_second)
    print("QPU cost per shot:", config.qpu_cost_per_shot)

    # -----------------------------------------------------
    # STEP 6: Estimate monetary cost
    # -----------------------------------------------------

    print("\nSTEP 6: CALCULATE MONETARY COST")
    print("-" * 70)

    # Local Aer does not generate cloud network traffic.
    # No separate classical CPU stage is measured here.
    classical_cpu_time_s = 0.0
    communication_bytes = 0.0

    cost_estimate = estimator.estimate_from_execution(
        qpu_execution_time_s=qpu_time_proxy_s,
        shots=result.shots,
        classical_cpu_time_s=classical_cpu_time_s,
        communication_bytes=communication_bytes,
        mode=CostMode.MONETARY,
        metadata={
            "workload_id": "mqt_bench_dj_5",
            "backend": result.backend_name,
            "execution_type": "local_aer_simulation",
            "execution_result_id": result.result_id,
        },
    )

    print("\nQPU cost:", cost_estimate.qpu.monetary_cost)
    print("Classical cost:",
          cost_estimate.classical.monetary_cost)

    print("Communication cost:",
          cost_estimate.communication.monetary_cost)

    print("Total estimated cost:",
          cost_estimate.total_cost,
          cost_estimate.currency)

    print("Cost per shot:",
          cost_estimate.monetary_cost_per_shot)

    check(
        cost_estimate.is_complete,
        "All monetary components are available",
    )

    check(
        cost_estimate.total_cost is not None,
        "Total monetary estimate is available",
    )

    check(
        cost_estimate.total_cost >= 0,
        "Total cost is non-negative",
    )

    # Independently verify the QPU calculation.
    expected_qpu_cost = (
        qpu_time_proxy_s * config.qpu_cost_per_second
        + result.shots * config.qpu_cost_per_shot
    )

    check(
        abs(
            cost_estimate.qpu.monetary_cost
            - expected_qpu_cost
        ) < 1e-9,
        "QPU cost matches independent calculation",
    )

    # Independently verify total calculation.
    expected_total = (
        cost_estimate.qpu.monetary_cost
        + cost_estimate.classical.monetary_cost
        + cost_estimate.communication.monetary_cost
    )

    check(
        abs(cost_estimate.total_cost - expected_total) < 1e-9,
        "Total cost matches independent calculation",
    )

    # -----------------------------------------------------
    # STEP 7: Estimate resource-proxy score
    # -----------------------------------------------------

    print("\nSTEP 7: CALCULATE RESOURCE-PROXY SCORE")
    print("-" * 70)

    proxy_estimate = estimator.estimate_from_execution(
        qpu_execution_time_s=qpu_time_proxy_s,
        shots=result.shots,
        classical_cpu_time_s=classical_cpu_time_s,
        communication_bytes=communication_bytes,
        mode=CostMode.RESOURCE_PROXY,
        metadata={
            "workload_id": "mqt_bench_dj_5",
            "backend": result.backend_name,
        },
    )

    print("QPU resource score:",
          proxy_estimate.qpu.resource_score)

    print("Classical resource score:",
          proxy_estimate.classical.resource_score)

    print("Communication resource score:",
          proxy_estimate.communication.resource_score)

    print("Total resource score:",
          proxy_estimate.total_resource_score)

    check(
        proxy_estimate.is_complete,
        "All resource-proxy components are available",
    )

    check(
        proxy_estimate.total_resource_score is not None,
        "Total resource score is available",
    )

    check(
        proxy_estimate.total_cost is None,
        "Resource score is not treated as monetary cost",
    )

    # -----------------------------------------------------
    # STEP 8: Final report
    # -----------------------------------------------------

    print("\n" + "=" * 70)
    print("QFLOWPILOT COST ESTIMATION REPORT")
    print("=" * 70)

    print("Workload:", "MQT Bench DJ circuit")
    print("Qubits:", circuit.num_qubits)
    print("Shots:", result.shots)
    print("Actual counts:", result.counts)

    print(
        "Aer execution time:",
        f"{qpu_time_proxy_s:.8f} seconds",
    )

    print(
        "Estimated monetary cost:",
        f"{cost_estimate.total_cost:.10f}",
        cost_estimate.currency,
    )

    print(
        "Monetary cost per shot:",
        cost_estimate.monetary_cost_per_shot,
    )

    print(
        "Resource-proxy score:",
        proxy_estimate.total_resource_score,
    )

    print("Accounting mode:", cost_estimate.mode)
    print("Metadata:", cost_estimate.metadata)

    print("\n" + "=" * 70)
    print("AER + COST ESTIMATOR INTEGRATION TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
