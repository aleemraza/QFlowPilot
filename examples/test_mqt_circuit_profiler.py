from pathlib import Path
from collections import Counter
from qflowpilot.profiler import CircuitProfiler
DATASET_DIR = Path("./workloads/mqt_bench/")


def main():

    profiler = CircuitProfiler(
        include_instruction_details=False
    )

    print("=" * 65)
    print("QFlowPilot - MQT Bench Circuit Profiling")
    print("=" * 65)

    result = profiler.profile_dataset(
        DATASET_DIR,
        recursive=True,
    )

    profiles = result["profiles"]

    print("\nDATASET SUMMARY")
    print("-" * 65)

    print("Files discovered:", result["files_discovered"])
    print("Circuits profiled:", result["circuits_profiled"])
    print("Failed files:", result["failed_files"])

    if not profiles:
        print("\nNo circuits were successfully profiled.")
        return

    total_qubits = 0
    total_gates = 0
    total_depth = 0
    total_two_qubit_gates = 0

    all_gate_counts = Counter()

    for profile in profiles:

        total_qubits += profile.num_qubits
        total_gates += profile.total_gates
        total_depth += profile.depth
        total_two_qubit_gates += profile.two_qubit_gates

        all_gate_counts.update(profile.gate_counts)

    count = len(profiles)

    print("\nAVERAGE CIRCUIT CHARACTERISTICS")
    print("-" * 65)

    print("Average qubits:", total_qubits / count)
    print("Average depth:", total_depth / count)
    print("Average gates:", total_gates / count)
    print(
        "Average two-qubit gates:",
        total_two_qubit_gates / count,
    )

    print("\nGATE DISTRIBUTION")
    print("-" * 65)

    for gate, gate_count in all_gate_counts.most_common():
        print(f"{gate:15s}: {gate_count}")

    print("\nFIRST 10 CIRCUITS")
    print("-" * 65)

    for index, profile in enumerate(profiles[:10], start=1):

        print(f"\nCircuit {index}")
        print("Name:", profile.metadata["circuit_name"])
        print("Qubits:", profile.num_qubits)
        print("Depth:", profile.depth)
        print("Gates:", profile.total_gates)
        print("Two-qubit gates:", profile.two_qubit_gates)

    if result["errors"]:
        print("\nFAILED FILES")
        print("-" * 65)

        for error in result["errors"][:10]:
            print("File:", error["file"])
            print("Error:", error["error"])

    print("\nProfiling completed.")


if __name__ == "__main__":
    main()
