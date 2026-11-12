
from pathlib import Path

from qiskit import QuantumCircuit

from qflowpilot.core.models import (
    WorkloadSpec,
    WorkloadType,
)
from qflowpilot.profiler.circuit_profiler import CircuitProfiler
from qflowpilot.profiler.workload_profiler import WorkloadProfiler


# =========================================================
# 1. Project and dataset configuration
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CIRCUIT_PATH = (
    PROJECT_ROOT
    / "workloads"
    / "mqt_bench"
    / "dj_nativegates_ibm_falcon_opt2_5.qasm"
)


# =========================================================
# 2. Create test circuits
# =========================================================

def create_test_circuits():

    if not CIRCUIT_PATH.exists():
        raise FileNotFoundError(
            f"Dataset circuit not found: {CIRCUIT_PATH}"
        )

    # Circuit 1: Real MQT Bench circuit
    circuit_1 = CircuitProfiler.load_circuit(CIRCUIT_PATH)

    # Circuit 2: Small two-qubit circuit
    circuit_2 = QuantumCircuit(2, 2, name="small_circuit")
    circuit_2.h(0)
    circuit_2.cx(0, 1)
    circuit_2.measure(0, 0)
    circuit_2.measure(1, 1)

    # Circuit 3: Three-qubit circuit
    circuit_3 = QuantumCircuit(3, 3, name="three_qubit_circuit")
    circuit_3.x(0)
    circuit_3.h(1)
    circuit_3.cx(0, 1)
    circuit_3.ccx(0, 1, 2)
    circuit_3.measure_all()

    return circuit_1, circuit_2, circuit_3


# =========================================================
# 3. Independent aggregation verification
# =========================================================

def verify_aggregation(profiles):

    count = len(profiles)

    expected_total_gates = sum(
        p.total_gates for p in profiles
    )

    expected_two_qubit_gates = sum(
        p.two_qubit_gates for p in profiles
    )

    expected_average_depth = (
        sum(p.depth for p in profiles) / count
    )

    expected_maximum_depth = max(
        p.depth for p in profiles
    )

    expected_minimum_depth = min(
        p.depth for p in profiles
    )

    expected_maximum_qubits = max(
        p.num_qubits for p in profiles
    )

    expected_sum_qubits = sum(
        p.num_qubits for p in profiles
    )

    return {
        "circuit_count":
            count,

        "total_gates":
            expected_total_gates,

        "total_two_qubit_gates":
            expected_two_qubit_gates,

        "average_depth":
            expected_average_depth,

        "maximum_depth":
            expected_maximum_depth,

        "minimum_depth":
            expected_minimum_depth,

        "maximum_qubits":
            expected_maximum_qubits,

        "sum_of_circuit_qubits":
            expected_sum_qubits,
    }


# =========================================================
# 4. Validation helper
# =========================================================

checks = {}


def check(name, condition):
    checks[name] = bool(condition)


# =========================================================
# 5. Initialize profiler and circuits
# =========================================================

print("\n" + "=" * 70)
print("QFLOWPILOT - WORKLOAD PROFILER TEST")
print("=" * 70)

circuits = create_test_circuits()

circuit_1, circuit_2, circuit_3 = circuits

print("\n[1] INPUT CIRCUITS")

for index, circuit in enumerate(circuits):
    print(
        f"Circuit {index + 1}: "
        f"name={circuit.name}, "
        f"qubits={circuit.num_qubits}, "
        f"depth={circuit.depth()}, "
        f"instructions={len(circuit.data)}"
    )

profiler = WorkloadProfiler()


# =========================================================
# 6. Test A: Batch workload
# =========================================================

print("\n" + "=" * 70)
print("[2] BATCH WORKLOAD TEST")
print("=" * 70)

batch_workload = WorkloadSpec(
    workload_id="test_batch_001",
    name="Batch Profiler Test",
    workload_type=WorkloadType.BATCH,
    algorithm="Multiple Quantum Circuits",
    application="Profiler Validation",
    description="Three independent quantum circuits.",
)

batch_profile = profiler.profile_batch(
    workload=batch_workload,
    circuits=circuits,
)

batch_metadata = batch_profile.metadata

print("\nBatch workload information:")
print("Workload ID:", batch_profile.workload_id)
print("Workload name:", batch_profile.workload_name)
print("Workload type:", batch_profile.workload_type.value)

print("\nBatch aggregation:")
for key, value in batch_metadata.items():
    print(f"{key}: {value}")

expected_batch = verify_aggregation(
    batch_profile.circuit_profiles
)

for key, expected_value in expected_batch.items():
    check(
        f"Batch aggregation: {key}",
        batch_metadata[key] == expected_value,
    )

check(
    "Batch workload type",
    batch_profile.workload_type == WorkloadType.BATCH,
)

check(
    "Batch circuit count",
    len(batch_profile.circuit_profiles) == 3,
)

check(
    "Batch execution structure",
    batch_metadata["execution_structure"] == "independent",
)

check(
    "Batch circuits have no assumed dependency",
    batch_metadata["dependency_between_circuits"] is False,
)

check(
    "Batch workload-level parallelizability",
    batch_metadata["parallelizable_at_workload_level"] is True,
)


# =========================================================
# 7. Test B: Iterative workload
# =========================================================

print("\n" + "=" * 70)
print("[3] ITERATIVE WORKLOAD TEST")
print("=" * 70)

iterative_workload = WorkloadSpec(
    workload_id="test_iterative_001",
    name="Iterative Profiler Test",
    workload_type=WorkloadType.ITERATIVE,
    algorithm="Iterative Quantum Algorithm",
    application="Profiler Validation",
    description="Three sequential rounds with two circuits per round.",
)

# Three rounds, two circuits in each round.
rounds = [
    [circuit_1, circuit_2],
    [circuit_2, circuit_3],
    [circuit_3, circuit_1],
]

iterative_profile = profiler.profile_iterative(
    workload=iterative_workload,
    rounds=rounds,
)

iterative_metadata = iterative_profile.metadata

print("\nIterative workload information:")
print("Workload ID:", iterative_profile.workload_id)
print("Workload name:", iterative_profile.workload_name)
print("Workload type:", iterative_profile.workload_type.value)

print("\nIterative aggregation:")

for key, value in iterative_metadata.items():
    print(f"{key}: {value}")

expected_iterative = verify_aggregation(
    iterative_profile.circuit_profiles
)

for key, expected_value in expected_iterative.items():
    check(
        f"Iterative aggregation: {key}",
        iterative_metadata[key] == expected_value,
    )

check(
    "Iterative workload type",
    iterative_profile.workload_type == WorkloadType.ITERATIVE,
)

check(
    "Iterative total circuit count",
    len(iterative_profile.circuit_profiles) == 6,
)

check(
    "Iterative round count",
    len(iterative_profile.round_profiles) == 3,
)

check(
    "Iterative circuits per round",
    all(len(round_profile) == 2
        for round_profile in iterative_profile.round_profiles),
)

check(
    "Iterative execution structure",
    iterative_metadata["execution_structure"] == "iterative",
)

check(
    "Sequential round dependency",
    iterative_metadata["sequential_round_dependency"] is True,
)

check(
    "Circuits within each round assumed independent",
    iterative_metadata[
        "circuits_within_round_assumed_independent"
    ] is True,
)

check(
    "Round summary count",
    len(iterative_metadata["round_summaries"]) == 3,
)


# =========================================================
# 8. Test C: Verify each round separately
# =========================================================

print("\n" + "=" * 70)
print("[4] ROUND-BY-ROUND VALIDATION")
print("=" * 70)

for index, round_profile in enumerate(
    iterative_profile.round_profiles
):

    summary = iterative_metadata["round_summaries"][index]

    expected_round = verify_aggregation(round_profile)

    print(f"\nRound {index + 1}:")

    for key, expected_value in expected_round.items():

        actual_value = summary[key]

        print(
            f"  {key}: actual={actual_value}, "
            f"expected={expected_value}"
        )

        check(
            f"Round {index + 1}: {key}",
            actual_value == expected_value,
        )


# =========================================================
# 9. Test D: Unified profiling interface
# =========================================================

print("\n" + "=" * 70)
print("[5] UNIFIED INTERFACE TEST")
print("=" * 70)

unified_batch = profiler.profile_workload(
    workload=batch_workload,
    circuits=circuits,
)

unified_iterative = profiler.profile_workload(
    workload=iterative_workload,
    rounds=rounds,
)

check(
    "Unified batch interface",
    unified_batch.metadata["circuit_count"] == 3,
)

check(
    "Unified iterative interface",
    unified_iterative.metadata["number_of_rounds"] == 3,
)


# =========================================================
# 10. Test E: Input validation
# =========================================================

print("\n" + "=" * 70)
print("[6] INPUT VALIDATION TEST")
print("=" * 70)


def expect_error(test_name, expected_exception, function):

    try:
        function()

    except expected_exception:
        print(f"[PASS] {test_name}")
        check(test_name, True)

    except Exception as exc:
        print(
            f"[FAIL] {test_name}: "
            f"Unexpected {type(exc).__name__}: {exc}"
        )
        check(test_name, False)

    else:
        print(f"[FAIL] {test_name}: No exception raised")
        check(test_name, False)


expect_error(
    "Batch rejects empty circuit list",
    ValueError,
    lambda: profiler.profile_batch(
        batch_workload,
        [],
    ),
)

expect_error(
    "Iterative rejects empty rounds",
    ValueError,
    lambda: profiler.profile_iterative(
        iterative_workload,
        [],
    ),
)

expect_error(
    "Iterative rejects an empty round",
    ValueError,
    lambda: profiler.profile_iterative(
        iterative_workload,
        [[circuit_1], []],
    ),
)

expect_error(
    "Batch rejects the wrong workload type",
    ValueError,
    lambda: profiler.profile_batch(
        iterative_workload,
        circuits,
    ),
)

expect_error(
    "Iterative rejects the wrong workload type",
    ValueError,
    lambda: profiler.profile_iterative(
        batch_workload,
        rounds,
    ),
)

expect_error(
    "Batch rejects non-quantum circuit input",
    TypeError,
    lambda: profiler.profile_batch(
        batch_workload,
        [circuit_1, "invalid_circuit"],
    ),
)


# =========================================================
# 11. Final report
# =========================================================

print("\n" + "=" * 70)
print("[7] FINAL WORKLOAD PROFILER TEST REPORT")
print("=" * 70)

passed = sum(checks.values())
failed = len(checks) - passed

for name, result in checks.items():

    status = "PASS" if result else "FAIL"

    print(f"[{status}] {name}")

print("\n" + "=" * 70)
print(f"TOTAL CHECKS: {len(checks)}")
print(f"PASSED:       {passed}")
print(f"FAILED:       {failed}")
print("=" * 70)

if failed:
    raise AssertionError(
        f"WorkloadProfiler test failed: {failed} checks failed."
    )

print("\nWorkloadProfiler tests completed successfully.")
