
"""
QFlowPilot: Aer + LatencyProfiler integration test.

This test:
1. Loads a real MQT Bench QASM3 circuit.
2. Executes it using AerIdealAdapter.
3. Collects actual simulator counts.
4. Uses actual timestamps recorded by the adapter.
5. Profiles execution latency.

Run from the project root:

    python examples/profiler_module/test_latency_profiler_aer.py

Or provide a circuit path:

    python examples/profiler_module/test_latency_profiler_aer.py path/to/circuit.qasm
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace

from qiskit import qasm3

from qflowpilot.adapters.aer_ideal_adapter import AerIdealAdapter
from qflowpilot.core.models import ExecutionMode, ExecutionStatus
from qflowpilot.profiler.latency_profiler import LatencyProfiler


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


def load_real_circuit() :
    """Load an actual QASM3 circuit from the MQT Bench dataset."""

    project_root = Path(__file__).resolve().parents[2]

    if len(sys.argv) > 1:
        circuit_path = Path(sys.argv[1]).expanduser().resolve()
    else:
        circuit_path = project_root / CIRCUIT_RELATIVE_PATH

    if not circuit_path.exists():
        raise FileNotFoundError(
            f"MQT Bench circuit not found: {circuit_path}\n"
            "Provide the correct circuit path as a command-line argument."
        )

    print("\nCircuit file:", circuit_path)

    with open(circuit_path, "r", encoding="utf-8") as file:
        circuit = qasm3.loads(file.read())

    if not circuit.data:
        raise ValueError("Loaded circuit contains no instructions.")

    if circuit.num_clbits == 0:
        raise ValueError(
            "Circuit has no classical measurement registers. "
            "Choose a measured QASM3 circuit for this test."
        )

    return circuit


# ---------------------------------------------------------
# Main integration test
# ---------------------------------------------------------

def main():

    print("\n" + "=" * 70)
    print("QFLOWPILOT: AER + LATENCY PROFILER INTEGRATION TEST")
    print("=" * 70)

    # -----------------------------------------------------
    # STEP 1: Load actual MQT Bench circuit
    # -----------------------------------------------------

    print("\nSTEP 1: LOAD REAL QASM3 CIRCUIT")
    print("-" * 70)

    circuit = load_real_circuit()

    print("Qubits:", circuit.num_qubits)
    print("Classical bits:", circuit.num_clbits)
    print("Circuit depth:", circuit.depth())
    print("Circuit instructions:", len(circuit.data))

    check(circuit.num_qubits > 0, "Circuit has quantum bits")
    check(circuit.num_clbits > 0, "Circuit has classical bits")
    check(len(circuit.data) > 0, "Circuit contains instructions")

    # -----------------------------------------------------
    # STEP 2: Prepare execution request
    # -----------------------------------------------------

    print("\nSTEP 2: PREPARE SIMULATOR REQUEST")
    print("-" * 70)

    request = SimpleNamespace(
        request_id="qflowpilot_aer_latency_001",
        shots=SHOTS,
        seed=SEED,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
    )

    print("Request ID:", request.request_id)
    print("Shots:", request.shots)
    print("Seed:", request.seed)
    print("Execution mode:", request.execution_mode)

    # -----------------------------------------------------
    # STEP 3: Initialize existing Aer adapter
    # -----------------------------------------------------

    print("\nSTEP 3: INITIALIZE AER IDEAL ADAPTER")
    print("-" * 70)

    adapter = AerIdealAdapter(
        backend_name="aer_ideal",
        optimization_level=1,
    )

    print("Backend information:", adapter.get_backend_info())

    check(adapter.is_available(), "Aer adapter is available")

    # -----------------------------------------------------
    # STEP 4: Execute actual quantum circuit
    # -----------------------------------------------------

    print("\nSTEP 4: EXECUTE ACTUAL CIRCUIT ON AER")
    print("-" * 70)

    result = adapter.execute(
        request=request,
        circuit=circuit,
    )

    # The adapter records completed_at before returning.
    # Record the time at which the caller receives the result.
    returned_at = datetime.now(timezone.utc)

    # ExecutionResult.metadata is a mutable dictionary.
    result.metadata["returned_at"] = returned_at

    print("Execution status:", result.status)
    print("Backend:", result.backend_name)
    print("Execution mode:", result.execution_mode)
    print("Shots:", result.shots)
    print("Measurement counts:", result.counts)

    check(
        result.status == ExecutionStatus.COMPLETED,
        "Aer execution completed successfully",
    )

    check(
        result.backend_name == "aer_ideal",
        "Result identifies the Aer backend",
    )

    check(
        result.shots == SHOTS,
        "Result contains the requested shot count",
    )

    check(
        sum(result.counts.values()) == SHOTS,
        "Actual measurement counts sum to requested shots",
    )

    # -----------------------------------------------------
    # STEP 5: Inspect actual execution timestamps
    # -----------------------------------------------------

    print("\nSTEP 5: INSPECT EXECUTION TIMESTAMPS")
    print("-" * 70)

    print("Submitted at:", result.submitted_at)
    print("Started at:", result.started_at)
    print("Completed at:", result.completed_at)
    print("Returned at:", result.metadata["returned_at"])

    check(result.submitted_at is not None, "Submission timestamp exists")
    check(result.started_at is not None, "Start timestamp exists")
    check(result.completed_at is not None, "Completion timestamp exists")

    check(
        result.submitted_at <= result.started_at,
        "Submission precedes execution start",
    )

    check(
        result.started_at <= result.completed_at,
        "Execution start precedes completion",
    )

    check(
        result.completed_at <= returned_at,
        "Result completion precedes caller return",
    )

    # -----------------------------------------------------
    # STEP 6: Profile actual execution latency
    # -----------------------------------------------------

    print("\nSTEP 6: PROFILE ACTUAL EXECUTION LATENCY")
    print("-" * 70)

    latency_profiler = LatencyProfiler()

    latency_profile = latency_profiler.profile_execution(result)

    print("Result ID:", latency_profile.result_id)
    print("Queue/pre-execution delay:",
          latency_profile.queue_latency_s, "seconds")
    print("Simulator execution:",
          latency_profile.qpu_execution_latency_s, "seconds")
    print("End-to-end latency:",
          latency_profile.end_to_end_latency_s, "seconds")
    print("Successful:", latency_profile.successful)

    print(
        "Return timestamp source:",
        latency_profile.metadata["return_timestamp_source"],
    )

    check(
        latency_profile.queue_latency_s >= 0,
        "Pre-execution delay is non-negative",
    )

    check(
        latency_profile.qpu_execution_latency_s >= 0,
        "Simulator execution duration is non-negative",
    )

    check(
        latency_profile.end_to_end_latency_s >= 0,
        "End-to-end duration is non-negative",
    )

    check(
        latency_profile.successful is True,
        "LatencyProfiler recognizes successful execution",
    )

    check(
        latency_profile.metadata["return_timestamp_source"]
        == "metadata.returned_at",
        "Actual caller return timestamp is recognized",
    )

    # -----------------------------------------------------
    # STEP 7: Compare with adapter execution measurements
    # -----------------------------------------------------

    print("\nSTEP 7: CROSS-CHECK MEASUREMENTS")
    print("-" * 70)

    adapter_execution_s = (
        result.completed_at - result.started_at
    ).total_seconds()

    caller_end_to_end_s = (
        returned_at - result.submitted_at
    ).total_seconds()

    print("Adapter measured execution:", adapter_execution_s, "seconds")
    print("Caller observed end-to-end:", caller_end_to_end_s, "seconds")
    print(
        "LatencyProfiler execution:",
        latency_profile.qpu_execution_latency_s,
        "seconds",
    )

    check(
        abs(
            latency_profile.qpu_execution_latency_s
            - adapter_execution_s
        ) < 1e-6,
        "LatencyProfiler matches adapter execution timestamps",
    )

    check(
        abs(
            latency_profile.end_to_end_latency_s
            - caller_end_to_end_s
        ) < 1e-6,
        "LatencyProfiler matches caller-observed end-to-end duration",
    )

    # -----------------------------------------------------
    # STEP 8: Display simulator metadata
    # -----------------------------------------------------

    print("\nSTEP 8: SIMULATOR EXECUTION METADATA")
    print("-" * 70)

    for key, value in result.metadata.items():
        print(f"{key}: {value}")

    # -----------------------------------------------------
    # Final result
    # -----------------------------------------------------

    print("\n" + "=" * 70)
    print("AER + LATENCY PROFILER INTEGRATION TEST PASSED")
    print("=" * 70)

    print("Actual circuit:", circuit.num_qubits, "qubits")
    print("Actual shots:", result.shots)
    print("Observed outcomes:", len(result.counts))
    print(
        "Simulator execution:",
        f"{latency_profile.qpu_execution_latency_s:.6f} seconds",
    )
    print(
        "End-to-end latency:",
        f"{latency_profile.end_to_end_latency_s:.6f} seconds",
    )


if __name__ == "__main__":
    main()
