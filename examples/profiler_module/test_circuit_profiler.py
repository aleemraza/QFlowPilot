
from pathlib import Path
from collections import Counter

from qflowpilot.profiler.circuit_profiler import CircuitProfiler


# ---------------------------------------------------------
# 1. Locate one circuit
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CIRCUIT_PATH = (
    PROJECT_ROOT
    / "workloads"
    / "mqt_bench"
    / "dj_nativegates_ibm_falcon_opt2_5.qasm"
)


# ---------------------------------------------------------
# 2. Load and profile the circuit
# ---------------------------------------------------------

print("\n" + "=" * 65)
print("QFLOWPILOT - CIRCUIT PROFILER TEST")
print("=" * 65)

if not CIRCUIT_PATH.exists():
    raise FileNotFoundError(
        f"Circuit file not found: {CIRCUIT_PATH}"
    )

profiler = CircuitProfiler(
    include_instruction_details=True
)

circuit = profiler.load_circuit(CIRCUIT_PATH)

profiles = profiler.profile_file(CIRCUIT_PATH)

if len(profiles) != 1:
    raise AssertionError(
        f"Expected one circuit, received {len(profiles)}"
    )

profile = profiles[0]
metadata = profile.metadata


# ---------------------------------------------------------
# 3. Independently calculate expected values
# ---------------------------------------------------------

excluded_operations = {
    "measure",
    "barrier",
    "reset",
    "delay",
    "if_else",
    "while_loop",
    "for_loop",
    "switch_case",
}

expected_gate_counts = Counter()

expected_single_qubit_gates = 0
expected_two_qubit_gates = 0
expected_multi_qubit_gates = 0
expected_measurements = 0

for instruction in circuit.data:

    operation = instruction.operation
    name = operation.name.lower()
    number_of_qubits = len(instruction.qubits)

    if name == "measure":
        expected_measurements += 1

    if name in excluded_operations:
        continue

    if number_of_qubits == 0:
        continue

    expected_gate_counts[name] += 1

    if number_of_qubits == 1:
        expected_single_qubit_gates += 1

    elif number_of_qubits == 2:
        expected_two_qubit_gates += 1

    else:
        expected_multi_qubit_gates += 1

expected_total_gates = (
    expected_single_qubit_gates
    + expected_two_qubit_gates
    + expected_multi_qubit_gates
)


# ---------------------------------------------------------
# 4. Compare profiler results with independent calculations
# ---------------------------------------------------------

checks = {
    "Number of qubits":
        profile.num_qubits == circuit.num_qubits,

    "Number of classical bits":
        metadata["num_clbits"] == circuit.num_clbits,

    "Circuit depth":
        profile.depth == circuit.depth(),

    "Total computational gates":
        profile.total_gates == expected_total_gates,

    "Single-qubit gates":
        metadata["single_qubit_gates"]
        == expected_single_qubit_gates,

    "Two-qubit gates":
        profile.two_qubit_gates
        == expected_two_qubit_gates,

    "Multi-qubit gates":
        metadata["multi_qubit_gates"]
        == expected_multi_qubit_gates,

    "Gate counts":
        profile.gate_counts == dict(
            sorted(expected_gate_counts.items())
        ),

    "Measurement count":
        metadata["measurement_count"]
        == expected_measurements,

    "Source path":
        metadata["source"] == str(CIRCUIT_PATH),

    "Execution time unavailable":
        profile.estimated_execution_time_s is None,
}


# ---------------------------------------------------------
# 5. Display circuit information
# ---------------------------------------------------------

print("\n[1] CIRCUIT INFORMATION")

print(f"Circuit name:       {circuit.name}")
print(f"Circuit file:       {CIRCUIT_PATH.name}")
print(f"Qubits:             {profile.num_qubits}")
print(f"Classical bits:     {metadata['num_clbits']}")
print(f"Circuit width:      {metadata['circuit_width']}")
print(f"Qiskit depth:       {profile.depth}")


# ---------------------------------------------------------
# 6. Display gate statistics
# ---------------------------------------------------------

print("\n[2] GATE STATISTICS")

print(f"Total instructions: {metadata['instruction_count']}")
print(f"Total gates:        {profile.total_gates}")
print(f"Single-qubit gates: {metadata['single_qubit_gates']}")
print(f"Two-qubit gates:    {profile.two_qubit_gates}")
print(f"Multi-qubit gates:  {metadata['multi_qubit_gates']}")

print("\nGate distribution:")

for gate_name, count in profile.gate_counts.items():
    print(f"  {gate_name:10s}: {count}")


# ---------------------------------------------------------
# 7. Display additional structural information
# ---------------------------------------------------------

print("\n[3] ADDITIONAL INFORMATION")

print(f"Measurements:       {metadata['measurement_count']}")
print(f"Resets:             {metadata['reset_count']}")
print(f"Barriers:           {metadata['barrier_count']}")
print(f"Delays:             {metadata['delay_count']}")

print(
    f"Logical operation depth: "
    f"{metadata['logical_operation_depth']}"
)

print(
    f"Maximum operation width: "
    f"{metadata['maximum_operation_width']}"
)

print(
    f"Connectivity edges: "
    f"{metadata['connectivity_edges']}"
)

print(
    f"Measurement mapping: "
    f"{metadata['measurement_mapping']}"
)

print(
    f"Parameters: "
    f"{metadata['parameter_names']}"
)


# ---------------------------------------------------------
# 8. Verify instruction-level details
# ---------------------------------------------------------

details = metadata.get("instruction_details", [])

print("\n[4] INSTRUCTION DETAILS")

print(f"Instruction details collected: {len(details)}")

for item in details[:5]:
    print(
        f"  Index={item['index']}, "
        f"Name={item['name']}, "
        f"Qubits={item['qubits']}"
    )

if len(details) > 5:
    print(f"  ... and {len(details) - 5} more instructions")


# ---------------------------------------------------------
# 9. Display independent verification results
# ---------------------------------------------------------

print("\n[5] VALIDATION RESULTS")

passed = 0
failed = 0

for check_name, result in checks.items():

    if result:
        print(f"[PASS] {check_name}")
        passed += 1
    else:
        print(f"[FAIL] {check_name}")
        failed += 1

print("\n" + "=" * 65)
print(f"PASSED: {passed}")
print(f"FAILED: {failed}")
print("=" * 65)

if failed:
    raise AssertionError(
        f"CircuitProfiler test failed: {failed} checks did not pass."
    )

print("\nCircuitProfiler structural test completed successfully.")
